"""卡文詞彙表驗證殼:新格式新卡層的中日句對照 → 不一致報告(票01)。

比對全部來自 glossary.check_texts(純函式接縫),這裡只做讀檔、選層、
分組、排版——薄 IO 殼,不立測試(spec Testing Decisions)。報告式、
不阻擋建置;落在 .scratch,不進 docs、不進前端。冪等:同一份輸入重跑,
輸出逐位元組相同(不寫時間戳,排序全部固定)。

掃描範圍:三級分類「新格式新卡」層(classify_card 判 TIER_NEW 的段)的
效果標記表句對照;無日文側的句(ot=2 繁中單側)由接縫整筆跳過。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/text_glossary/verify_texts.py                 # 全掃(票03)
    python script/text_glossary/verify_texts.py --limit 300     # 子集 demo
"""
import argparse
import json
import os
import sys

from glossary import check_texts, parse_glossary

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# 分級復用 text_format 的 classify(它載入時自己 append tag_card 的路徑)。
# 用 append 而非 insert:不讓這個目錄有機會遮蔽標準庫或既有模組。
sys.path.append(os.path.join(_ROOT, "script", "text_format"))
from classify import TIER_NEW, classify_card  # noqa: E402
from ocg_dates import align_ocg_dates, load_ocg_dates  # noqa: E402
from official_dates import merge_aligned_dates  # noqa: E402

DEFAULT_GLOSSARY = os.path.join(_ROOT, "docs", "text_glossary.md")
DEFAULT_CARDS = os.path.join(_ROOT, "data", "cards.json")
DEFAULT_TAGS = os.path.join(_ROOT, "data", "tag_cards.json")
DEFAULT_DATES = os.path.join(_ROOT, "data", "sources", "ocg-dates.json")
DEFAULT_OFFICIAL_DATES = os.path.join(_ROOT, "data", "sources",
                                      "official-dates.json")
DEFAULT_OUT = os.path.join(_ROOT, ".scratch", "text-glossary", "report.md")


def collect_records(cards, tag_cards, dates, limit=0):
    """新格式新卡層的卡 → 效果標記表句對照記錄(卡片密碼升冪)。

    limit > 0 時取該層前 limit 張(demo 用);句對照含段內全部效果句
    (效果外文本的前言/次數限制句也在層內,同段同層)。
    回傳 (records, 張數)。
    """
    clauses_by_id = {entry["id"]: entry["clauses"] for entry in tag_cards}
    records, card_count = [], 0
    for card in sorted(cards, key=lambda c: c["id"]):
        cid = card["id"]
        segs = classify_card(card, dates.get(cid))
        new_sections = {seg["section"] for seg in segs
                        if seg["tier"] == TIER_NEW}
        if not new_sections:
            continue
        if limit and card_count >= limit:
            break
        card_count += 1
        for clause in clauses_by_id.get(cid, []):
            if clause["section"] in new_sections:
                records.append({
                    "id": cid, "name": card["name_zh"],
                    "text_ja": clause.get("text_ja") or "",
                    "text_zh": clause.get("text_zh") or "",
                })
    return records, card_count


# ---------------------------------------------------------------- 排版

def _group_findings(entries, findings):
    """(級, 條目) → 筆清單;群序照詞彙表條目序(findings 已照記錄序)。"""
    order = {(entry["level"], entry["ja"]): pos
             for pos, entry in enumerate(entries)}
    groups = {}
    for finding in findings:
        groups.setdefault((finding["level"], finding["entry"]),
                          []).append(finding)
    return sorted(groups.items(), key=lambda item: order[item[0]])


def _problem_note(finding):
    if finding["banned"]:
        return f"用禁譯:{'、'.join(finding['banned'])}"
    return finding["problem"]


def render(entries, findings, scanned_cards, scanned_clauses, limit):
    term_count = sum(1 for e in entries if e["level"] == "譯詞")
    scope = (f"新格式新卡層依卡片密碼升冪取前 {scanned_cards:,} 張(--limit "
             f"{limit})" if limit else f"新格式新卡層全部 {scanned_cards:,} 張")
    lines = [
        "# 卡文詞彙表驗證報告",
        "",
        "<!-- 由 script/text_glossary/verify_texts.py 產生,不要手改;"
        "報告式,不阻擋建置。 -->",
        "",
        f"詞彙表:docs/text_glossary.md(譯詞 {term_count} 條、句式 "
        f"{len(entries) - term_count} 條)。掃描範圍:{scope},中日句對照 "
        f"{scanned_clauses:,} 句(無日文側的句由接縫跳過)。",
        "",
        "逐筆裁示:確認誤譯者走[[卡文勘誤表]]進站;裁示「不用修」者把卡片"
        "密碼記入詞彙表該條目「例外」欄(理由記備註),重跑即不再出現。",
        "",
        f"## 不一致(依條目分組,共 {len(findings):,} 筆)",
    ]
    groups = _group_findings(entries, findings)
    for (level, entry), rows in groups:
        expected = rows[0]["expected"]
        lines += ["", f"### 〔{level}〕{entry} → {expected}"
                  f"({len(rows):,} 筆)", ""]
        for finding in rows:
            lines += [f"- `{finding['id']}` {finding['name']}——"
                      f"{_problem_note(finding)}",
                      f"  - 日:{finding['text_ja']}",
                      f"  - 中:{finding['text_zh']}"]
    if not findings:
        lines += ["", "(無)"]
    lines += [
        "",
        "## 摘要",
        "",
        f"- 總筆數:{len(findings):,}",
        "- 依條目分布:",
        "",
        "| 級 | 條目 | 筆數 |",
        "|---|---|---|",
    ]
    lines += [f"| {level} | {entry} | {len(rows):,} |"
              for (level, entry), rows in groups]
    lines += [
        "",
        "- 誤報比例抽樣評估:待站主於首跑全掃報告上抽樣裁示(票03)。",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="卡文詞彙表驗證報告(新格式新卡層)")
    parser.add_argument("--glossary", default=DEFAULT_GLOSSARY,
                        help="卡文詞彙表 (預設 docs/text_glossary.md)")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表 JSON (預設 data/cards.json)")
    parser.add_argument("--tags", default=DEFAULT_TAGS,
                        help="效果標記表 JSON (預設 data/tag_cards.json)")
    parser.add_argument("--dates", default=DEFAULT_DATES,
                        help="OCG 首發日來源 JSON "
                             "(預設 data/sources/ocg-dates.json)")
    parser.add_argument("--official-dates", default=DEFAULT_OFFICIAL_DATES,
                        help="官方 DB 収録シリーズ後備日期 JSON "
                             "(預設 data/sources/official-dates.json,"
                             "檔案不存在時只用 YGOPRODeck)")
    parser.add_argument("--limit", type=int, default=0,
                        help="只掃該層前 N 張(卡片密碼升冪;0=全掃)")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="報告輸出路徑 (預設 .scratch/text-glossary/"
                             "report.md)")
    args = parser.parse_args(argv)

    with open(args.glossary, encoding="utf-8") as f:
        glossary_md = f.read()
    entries = parse_glossary(glossary_md)  # 格式壞了在讀檔階段就吵出來

    with open(args.cards, encoding="utf-8") as f:
        cards = json.load(f)
    with open(args.tags, encoding="utf-8") as f:
        tag_cards = json.load(f)
    dates = align_ocg_dates(cards, load_ocg_dates(args.dates))
    if os.path.exists(args.official_dates):
        fallback = align_ocg_dates(cards, load_ocg_dates(args.official_dates))
        dates, _ = merge_aligned_dates(dates, fallback)
    records, card_count = collect_records(cards, tag_cards, dates, args.limit)
    findings = check_texts(glossary_md, records)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(entries, findings, card_count, len(records),
                       args.limit))

    print(f"詞彙表條目: {len(entries)};掃描 {card_count:,} 張 / "
          f"{len(records):,} 句;不一致 {len(findings):,} 筆")
    print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
