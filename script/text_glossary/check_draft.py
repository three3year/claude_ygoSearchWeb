"""子批審查檔的擬稿 × 卡文詞彙表:進站前的機檢殼(text-rewrite 子批流程)。

`verify_texts.py` 掃的是**新格式新卡層**的現行卡文;改寫卡進站後歸「本站已改寫」
層,不在那個掃描範圍內——所以子批擬稿只有進站前這一次機會過詞彙表。本殼把
記錄來源換成審查檔的「日文原文 / 新文本」兩欄,比對照樣走 `glossary.check_texts`
純函式(同一把尺,零新接縫)。

同時以同一把尺量「查牌網舊譯」當**對照組**,分出:
    舊譯本就命中的  → 改寫沒把情況變糟,多半是誤報或慣用語分工
    新文本獨有的    → **改寫引入的**,這一類要當成擬稿瑕疵處理(目標 0 筆)

逐筆的處置照詞彙表慣例:確認違規者直接改擬稿(詞彙表是站主已核可的規則表,
不另開裁示);判「不用修」者在審查檔該卡加「殘留」欄寫明理由待站主裁示。
**改之前先查該卡的補足情報**——已知兩種系統性誤報都只有補足情報看得出來:
官方讀替(如『エンドフェイズ時』は『ターン終了時』に読み替えます)、官方改寫
時已刪去的子句(中文跟著官方走,詞彙表卻仍以舊日文卡文為門)。

排除欄(新文本寫「不進站」的卡)整卡跳過;報告式,不阻擋任何建置。

用法(於 repo 任意位置執行皆可):
    python script/text_glossary/check_draft.py .scratch/text-rewrite/review-41-monster-01.md
    python script/text_glossary/check_draft.py <審查檔> --out <報告路徑>
"""
import argparse
import json
import os
import re
import sys

from glossary import check_texts, parse_glossary

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_GLOSSARY = os.path.join(_ROOT, "docs", "text_glossary.md")

HEAD_RE = re.compile(r"^## (\d+)\. `(\d+)` (.+?)(?:\((.+)\))?$")


def _quoted(block, label):
    """`**標籤**` 後緊接的 `>` 引用區 → 行清單(空行或非引用行即止)。"""
    i = block.find(f"**{label}**")
    if i < 0:
        return []
    lines = []
    for line in block[i:].splitlines()[1:]:
        if line.startswith("> "):
            lines.append(line[2:].rstrip())
        elif line.strip() == "":
            if lines:
                break
        else:
            break
    return lines


def parse_review(md_text):
    """審查檔全文 → 每卡 {no, id, name, text_ja, draft, old, skipped}。"""
    cards = []
    for block in re.split(r"\n(?=## \d+\. `)", md_text):
        head = HEAD_RE.match(block.splitlines()[0])
        if not head:
            continue
        draft = _quoted(block, "新文本")
        cards.append({
            "no": head.group(1), "id": int(head.group(2)),
            "name": head.group(3).strip(),
            "text_ja": "\n".join(_quoted(block, "日文原文")),
            "draft": "\n".join(draft),
            "old": "\n".join(_quoted(block, "查牌網舊譯")),
            "skipped": any("不進站" in line for line in draft),
        })
    return cards


def findings_of(glossary_md, cards, field):
    """cards 的某一欄(draft/old)當中文側 → check_texts 的不一致清單。"""
    records = [{"id": c["id"], "name": c["name"], "text_ja": c["text_ja"],
                "text_zh": c[field]} for c in cards]
    return check_texts(glossary_md, records)


def _key(finding):
    return (finding["id"], finding["level"], finding["entry"],
            finding["problem"])


def render(cards, live, draft_findings, old_findings, entries, review_path):
    introduced = {_key(f) for f in draft_findings} - {_key(f)
                                                      for f in old_findings}
    no_by_id = {c["id"]: c["no"] for c in cards}
    hit_ids = {f["id"] for f in draft_findings}
    lines = [
        "# 子批擬稿 × 卡文詞彙表對照",
        "",
        "<!-- 由 script/text_glossary/check_draft.py 產生,不要手改;報告式,"
        "不阻擋建置。 -->",
        "",
        f"審查檔:`{review_path}`;詞彙表:docs/text_glossary.md"
        f"({len(entries)} 條)。",
        f"進站候選 {len(live)} 張(排除 {len(cards) - len(live)} 張)、"
        f"命中 {len(hit_ids)} 張 / {len(draft_findings)} 筆;"
        f"零命中 {len(live) - len(hit_ids)} 張。",
        "",
        f"同尺對照組(查牌網舊譯):{len(old_findings)} 筆 → "
        f"**新文本獨有(改寫引入){len(introduced)} 筆**"
        "(這一類是擬稿瑕疵,目標 0 筆;其餘多為誤報或慣用語分工)。",
        "",
        "處置:確認違規直接改擬稿(詞彙表是已核可的規則表,不另開裁示);"
        "判「不用修」者在審查檔該卡加「殘留」欄寫明理由待站主裁示。"
        "**改之前先查該卡補足情報**——官方讀替與官方已刪子句都只有補足看得出來。",
        "",
        f"## 逐筆(共 {len(draft_findings)} 筆)",
    ]
    if not draft_findings:
        lines += ["", "(無)"]
    for finding in draft_findings:
        mark = " **[改寫引入]**" if _key(finding) in introduced else ""
        note = ("用禁譯:" + "、".join(finding["banned"])) if finding["banned"] \
            else finding["problem"]
        lines += [
            "",
            f"### #{no_by_id[finding['id']]} `{finding['id']}` "
            f"{finding['name']}——〔{finding['level']}〕{note}{mark}",
            "",
            f"- 條目:{finding['entry']} → {finding['expected']}",
            f"- 日:{finding['text_ja']}",
            f"- 中(新):{finding['text_zh']}",
        ]
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="子批審查檔擬稿的卡文詞彙表對照(進站前機檢)")
    parser.add_argument("review", help="子批審查檔 md 路徑")
    parser.add_argument("--glossary", default=DEFAULT_GLOSSARY,
                        help="卡文詞彙表 (預設 docs/text_glossary.md)")
    parser.add_argument("--out", help="報告輸出路徑 (預設只印摘要不寫檔)")
    args = parser.parse_args(argv)

    with open(args.glossary, encoding="utf-8") as f:
        glossary_md = f.read()
    entries = parse_glossary(glossary_md)  # 格式壞了在讀檔階段就吵出來
    with open(args.review, encoding="utf-8") as f:
        cards = parse_review(f.read())
    if not cards:
        print(f"{args.review}:找不到 `## N. \\`密碼\\` 卡名` 的卡片小節")
        return 1

    live = [c for c in cards if not c["skipped"]]
    draft_findings = findings_of(glossary_md, live, "draft")
    old_findings = findings_of(glossary_md, live, "old")
    introduced = ({_key(f) for f in draft_findings}
                  - {_key(f) for f in old_findings})

    report = render(cards, live, draft_findings, old_findings, entries,
                    os.path.relpath(args.review, _ROOT).replace("\\", "/"))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
        print(f"已寫出 {args.out}")
    else:
        print(report)
    print(f"進站候選 {len(live)} 張;不一致 {len(draft_findings)} 筆"
          f"(舊譯同尺 {len(old_findings)} 筆);"
          f"新文本獨有(改寫引入){len(introduced)} 筆")
    return 0


if __name__ == "__main__":
    sys.exit(main())
