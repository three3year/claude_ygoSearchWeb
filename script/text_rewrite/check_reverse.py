"""子批審查檔的**反向檢查**:進站前找「不能是這樣」的證據(text-rewrite 子批流程)。

擬稿既有的兩道機檢都是**正向**的:詞彙表(`check_draft.py`)問「用詞有沒有照
條目」,審核台(`build_review_page.py`)問「改了什麼」。兩道都答不了改寫最常出錯
的那個問題——**我寫的這個形,庫裡到底存不存在**。票12 站主抽查一輪抓出四種錯,事後回看成因全同一個:每一次都查了「有沒有支持我的證據」,沒查「有沒有
否定我的證據」。本殼把那些「不能是…」補成機檢。

六條反向判準(每條都是否定式,命中即列,理由與計數一起印出來):

    R1 自造句式      新文本的子句在庫內計數不能是 0
    R2 缺發動        [[效果標記表]]判啟動/誘發/誘發即時的段不能沒有「發動」
    R3 主要階段      舊譯寫了「我方主要階段」,新文本不能拿掉(2026-08-27 裁示)
    R4 候選集沒列全  改動用詞時,新形的庫內計數不能低於舊形;同時印出同位置的
                     **全部異形**,免得只比手上想到的兩個候選
    R5 同家族先例    同 setcode 的家族裡已有新格式卡寫過同一句日文時,不能不對齊
    R6 官方已刪子句  官方在改寫現行文本時刪掉的子句,不能當漏譯補譯出來
    R7 官方新寫子句  官方加寫/改寫的子句,不能因為只讀舊文本而漏掉
                     (含結構檢查:官方自帶的圈號段數,不能和新文本對不上)

R6/R7 是一對:兩邊都在比**審查檔的「日文原文」欄(官方現行文本)** 與
**「舊日文」欄(`faq_info` 的官方 Q&A 頁文本)**。2026-08-27 站主裁示把改寫基底
換成官方現行文本、`faq_info` 降為查漏翻/多翻的對照組後,這兩條就是那道對照的
機檢面:R6 問「舊有現行無 → 我有沒有把官方刪掉的補回去」,R7 問「現行有舊無
→ 我有沒有漏掉官方改寫過的內容」。審查檔沒有「舊日文」欄(兩份逐字相同)時
兩條都不觸發。

計數一律先正規化再比:阿拉伯數字收成 `N`、「」內的卡名收成 `「X」`——不然
「攻擊力上升300」與「攻擊力上升500」會被當成兩個不同的句型,計數全部失真。

報告式,不阻擋任何建置、不改任何檔案;命中要不要改由站主裁示。與
`check_draft.py` 同屬審查側薄殼,照 spec 的 Testing Decisions 不另立測試。

用法(於 repo 任意位置執行皆可):
    python script/text_rewrite/check_reverse.py .scratch/text-rewrite/review-41-monster-03.md
    python script/text_rewrite/check_reverse.py <審查檔> --out <報告路徑>
"""
import argparse
import difflib
import json
import os
import re
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(_ROOT, "script", "text_glossary"))

from check_draft import parse_review          # noqa: E402  審查檔解析共用一份

CARDS = os.path.join(_ROOT, "data", "cards.json")
TAGS = os.path.join(_ROOT, "data", "tag_cards.json")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
# 會發動、會形成連鎖區塊的三類:段內一定要有「發動」(§3.4/§3.5)
ACTIVATED_KINDS = ("啟動效果", "誘發效果(1速)", "誘發即時效果(2速)")
NON_EFFECT = "效果外文本"

_CIRCLE_HEAD_RE = re.compile(rf"^[{CIRCLED}]：")
_DIGITS_RE = re.compile(r"[0-9０-９]+")
_NAME_RE = re.compile(r"「[^」]*」")
# 子句切點:只切逗號句號,頓號在句子內部當並列用,切開會把片語剁碎
_SPLIT_RE = re.compile(r"[，。]")
# R1 的滑窗長度。**不是**拿整句去比對——整句幾乎永遠是 0 例(句子是零件組出來
# 的,組合本來就少見),那樣每一句都會命中、報告等於沒有。改成滑一個 8 字窗:
# 全部的窗都在庫內出現過 = 這句話由現成零件組成,放行;有窗 0 例 = 那一段是
# 新造的,把最長的那一段印出來。8 字是實測值(子批 3 的 50 卡:W=8 → 11 筆、
# W=10 → 17 筆),再短會被通用片語淹掉、再長會開始收假陽性。
WINDOW = 8
# R4 的上下文長度:取改動片語後方這麼多字當定位錨
CONTEXT = 6
# R6 的句子相似度門檻:低於這個值視為「官方把這句拿掉了」而不是換句話說。
# 0.45 是實測值(子批 3 的 50 卡 → 6 筆,含兩筆已知案例:31 骷髏騎士的洗牌句、
# 50 螺旋機人的括號注);放寬到 0.55 會跳到 17 筆、開始收官方只是改寫的句子。
DROPPED_THRESHOLD = 0.45
# R7 的門檻。方向是 R6 的鏡像,尺卻不同——因為兩邊的**斷句不對稱**:官方
# 現代化文本一律把發動句和處理句拆成兩句(「①：〜に発動する。」+「〜を墓地へ
# 送る。」),舊文本是合成一句的。拿 R6 那把「句對句相似度」量現代化文本,每一次
# 拆句都會被報成官方新寫(實測 20 筆,一半是拆句假陽性)。改成問「這句的內容在
# 舊文本**整段**裡找不找得到」——最長共同子序列的覆蓋率。0.65 是實測值
# (子批 3 的 50 卡 → 15 筆);0.55 會漏掉 #34 阿基多那種局部改寫,0.8 起
# 假陽性(用字現代化:ゲームから除外→除外 之類)開始灌進來。
COVERED_THRESHOLD = 0.65


def normalise(text):
    """計數前的正規化:數字 → `N`,卡名 → `「X」`。

    不做這一步,「攻擊力上升300」與「攻擊力上升500」會各自計數,句型的庫內
    支持度就永遠是 1、每一句都像自造句。
    """
    return _DIGITS_RE.sub("N", _NAME_RE.sub("「X」", text))


def load_corpus():
    """全庫卡文 → (正規化全文, {密碼: 卡片})。"""
    with open(CARDS, encoding="utf-8") as f:
        cards = json.load(f)
    blob = normalise("\n".join(c.get("desc") or "" for c in cards))
    return blob, {c["id"]: c for c in cards}


def load_kinds():
    """效果標記表 → {密碼: [(index, kind), ...]}(只取 main 段,依序)。"""
    with open(TAGS, encoding="utf-8") as f:
        tags = json.load(f)
    return {c["id"]: [(cl["index"], cl["kind"]) for cl in c["clauses"]
                      if cl["section"] == "main"] for c in tags}


def count(blob, text):
    """正規化後的庫內出現次數。"""
    probe = normalise(text)
    return blob.count(probe) if probe else 0


def strip_head(line):
    """去掉「①：」與「●」領頭,只留句子本體。"""
    return _CIRCLE_HEAD_RE.sub("", line).lstrip("●").strip()


def spans_of(line):
    """一行新文本 → 子句清單(R1 的檢查單位)。"""
    return [s.strip() for s in _SPLIT_RE.split(strip_head(line))
            if len(s.strip()) >= WINDOW]


def novel_run(blob, span):
    """子句裡**庫內查無**的最長連續片段;整句都由現成零件組成則回 None。"""
    text = normalise(span)
    if len(text) < WINDOW:
        return None
    misses = [i for i in range(len(text) - WINDOW + 1)
              if blob.count(text[i:i + WINDOW]) == 0]
    if not misses:
        return None
    runs, start, prev = [], misses[0], misses[0]
    for i in misses[1:]:
        if i == prev + 1:
            prev = i
        else:
            runs.append((start, prev))
            start = prev = i
    runs.append((start, prev))
    head, tail = max(runs, key=lambda r: r[1] - r[0])
    return text[head:tail + WINDOW]


# ---------------------------------------------------------------- 六條反向判準

def r1_invented(card, blob):
    """R1:新文本不能出現庫內查無的片段(自造句式)。"""
    out = []
    for line in card["draft"].splitlines():
        for span in spans_of(line):
            run = novel_run(blob, span)
            if run:
                out.append({
                    "rule": "R1 自造句式", "span": run,
                    "why": f"這一段庫內 0 例(所在子句:{span})"
                           "——規範未載的句型要先查計數再定寫法"})
    return out


def r2_missing_activation(card, kinds):
    """R2:標記表判啟動/誘發/誘發即時的段不能沒有「發動」。"""
    rows = kinds.get(card["id"])
    if rows is None:
        return [{"rule": "R2 缺發動", "span": "(未對位)",
                 "why": "效果標記表查無此卡,未檢查"}]
    circled = [ln for ln in card["draft"].splitlines()
               if _CIRCLE_HEAD_RE.match(ln)]
    effects = [(i, k) for i, k in rows if k != NON_EFFECT]
    if len(circled) != len(effects):
        return [{"rule": "R2 缺發動", "span": "(未對位)",
                 "why": f"新文本 {len(circled)} 個圈號段 vs 標記表 "
                        f"{len(effects)} 條效果句,段數對不上——請人工核對"}]
    out = []
    for line, (index, kind) in zip(circled, effects):
        if kind in ACTIVATED_KINDS and "發動" not in line:
            out.append({"rule": "R2 缺發動", "span": line,
                        "why": f"標記表判 {kind}(原 [{index}] 段),"
                               "會形成連鎖區塊 → §3.4/§3.5 須以"
                               "「發動。/可以發動。」收尾"})
    return out


def r3_main_phase(card):
    """R3:舊譯寫了「我方主要階段」,新文本不能拿掉(2026-08-27 站主裁示)。"""
    if "主要階段" in card["old"] and "主要階段" not in card["draft"]:
        return [{"rule": "R3 主要階段", "span": "(整卡)",
                 "why": "舊譯有「我方主要階段」、新文本沒有。裁示:舊譯有就維持"
                        "——起動効果的主要階段限制官方多半只寫在補足,"
                        "「卡文沒寫」不是刪除依據(§3.4)"}]
    return []


def variants(blob, new_span, context):
    """同一個位置上,庫內出現過的**全部異形** → [(異形, 計數), ...]。

    R4 的重點不是「我選的那個對不對」,而是「候選集有沒有列全」——票12 的
    同步素材領起句就是只比了兩個候選、漏掉真正的多數形。用改動片語後方的
    上下文當錨,把同一格填過的字全撈出來,不靠人想得到幾個。
    """
    if len(context) < 3:
        return []
    probe = re.escape(normalise(context))
    found = re.findall(rf"([^，。、\n]{{1,12}}){probe}", blob)
    tally = {}
    for filler in found:
        tally[filler] = tally.get(filler, 0) + 1
    ranked = sorted(tally.items(), key=lambda kv: -kv[1])[:6]
    if len(ranked) < 2:
        return []
    return ranked


def r4_worse_wording(card, blob):
    """R4:改動用詞時,新形的庫內計數不能低於舊形;順帶印出全部異形。"""
    old = "\n".join(strip_head(l) for l in card["old"].splitlines())
    new = "\n".join(strip_head(l) for l in card["draft"].splitlines())
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace":
            continue
        old_span, new_span = old[i1:i2].strip(), new[j1:j2].strip()
        if len(old_span) < 3 or len(new_span) < 3:
            continue
        # 卡名替換(漆黑獵豹 → 光輝苔蘚)不是用詞取捨,計數比對對它沒有意義
        if _NAME_RE.sub("", old_span).strip() == "" \
                or _NAME_RE.sub("", new_span).strip() == "":
            continue
        old_n, new_n = count(blob, old_span), count(blob, new_span)
        context = new[j2:j2 + CONTEXT]
        alts = variants(blob, new_span, context)
        if new_n < old_n:
            out.append({
                "rule": "R4 用詞倒退", "span": f"{old_span} → {new_span}",
                "why": f"新形庫內 {new_n} 例 < 舊形 {old_n} 例",
                "alts": alts})
        elif alts and alts[0][0] != normalise(new_span) \
                and alts[0][1] > max(new_n, 1) * 2:
            out.append({
                "rule": "R4 候選集", "span": f"{old_span} → {new_span}",
                "why": f"新形庫內 {new_n} 例,但同位置的「{alts[0][0]}」有 "
                       f"{alts[0][1]} 例——候選集可能沒列全",
                "alts": alts})
    return out


def r5_family(card, cards, kinds, tag_text):
    """R5:同 setcode 的家族裡已有新格式卡寫過同一句日文時,不能不對齊。"""
    me = cards.get(card["id"])
    if not me or not me.get("setcode"):
        return []
    mine = [t for t in tag_text.get(card["id"], []) if t[1]]
    out = []
    for other_id, other in cards.items():
        if other_id == card["id"] or other.get("setcode") != me["setcode"]:
            continue
        if not any(ch in (other.get("desc") or "") for ch in CIRCLED):
            continue                      # 只拿已改新格式的家族成員當先例
        for _, ja, _ in mine:
            for _, other_ja, other_zh in tag_text.get(other_id, []):
                if not other_ja or not other_zh:
                    continue
                ratio = difflib.SequenceMatcher(
                    None, normalise(ja), normalise(other_ja)).ratio()
                if ratio < 0.85:
                    continue
                if normalise(strip_head(other_zh)) in normalise(card["draft"]):
                    continue              # 已經對齊了
                out.append({
                    "rule": "R5 同家族先例", "span": other_zh,
                    "why": f"`{other_id}` {other['name_zh']} 的日文同句"
                           f"(相似度 {ratio:.2f})已是新格式,中文如上"
                           "——官方改寫過的家族成員就是現成答案"})
    return out


def _sentences(text):
    """日文卡文 → 句子清單(以「。」斷句,去空白)。"""
    flat = re.sub(r"\s+", "", text or "")
    return [s for s in re.split(r"(?<=。)", flat) if len(s) >= 6]


def r6_dropped_clause(card):
    """R6:官方改寫現行文本時刪掉的句子,不能當漏譯補譯出來。

    **逐句**比對而不是逐字 diff——舊卡的現代化文本幾乎整段重寫(生け贄→
    リリース 之類),逐字 diff 會把每一次改寫都報成刪除,報告等於沒有。
    改成拿舊卡文的每一句去跟現代化文本的**所有**句子求最佳相似度:對得上
    某一句 = 官方只是換句話說;誰都對不上 = 官方把這件事整句拿掉了。
    """
    old = card.get("text_ja_faq")
    if not old:
        return []                      # 兩份逐字相同,審查檔不寫舊日文欄
    modern_sents = [normalise(s) for s in _sentences(card["text_ja"])]
    if not modern_sents:
        return []
    out = []
    for sent in _sentences(old):
        probe = normalise(sent)
        best = max(difflib.SequenceMatcher(None, probe, m).ratio()
                   for m in modern_sents)
        if best >= DROPPED_THRESHOLD:
            continue
        out.append({
            "rule": "R6 官方已刪子句", "span": sent,
            "why": f"官方現行文本(日文原文欄)裡沒有對應的句子"
                   f"(最佳相似度 {best:.2f})——這一句只存在於舊日文欄。"
                   "確認新文本沒把它當漏譯補譯出來(有意保留要在判斷點寫明理由)"})
    return out


def covered(probe, haystack):
    """`probe` 有多少字能在 `haystack` 裡對上(最長共同子序列的覆蓋率)。"""
    matcher = difflib.SequenceMatcher(None, haystack, probe, autojunk=False)
    return sum(b.size for b in matcher.get_matching_blocks()) / max(len(probe), 1)


def r7_modern_only(card):
    """R7:官方現代化時**加寫或改寫**的句子,不能因為只讀舊文本而漏掉。

    R6 的鏡像。`faq_info` 對未再版舊卡是舊文本,兩個方向都會出事:官方刪掉的
    被當漏譯補回(R6 抓),官方改寫過的則整段讀不到——融合咒印生物-光
    `15717011` 的①就是後者,舊文本讀不出官方已把適用時機、可代用的位置、
    括號注全部改掉(2026-08-27 站主指出)。

    另附一條結構檢查:現代化文本**自帶官方的圈號分層**,段數對不上就表示
    §4.1 的分層判斷和官方不同,要人工核對(改寫本來是靠補足推分層的)。
    """
    now = card["text_ja"]
    if not now:
        return [{"rule": "R7 官方新寫子句", "span": "(無日文原文)",
                 "why": "審查檔沒有日文原文欄,未檢查"}]
    out = []
    official = sum(1 for ch in CIRCLED if ch in now)
    drafted = sum(1 for ln in card["draft"].splitlines()
                  if _CIRCLE_HEAD_RE.match(ln))
    if official and official != drafted:
        out.append({
            "rule": "R7 圈號段數", "span": f"官方 {official} 段 / 新文本 {drafted} 段",
            "why": "官方現代化文本自帶圈號分層,段數與新文本對不上"
                   "——§4.1 的分層是靠補足推的,官方版才是現成答案,請人工核對"})
    old_flat = normalise(strip_head(re.sub(r"\s+", "",
                                           card.get("text_ja_faq") or "")))
    if not old_flat:
        return out                     # 兩份逐字相同,沒有落差可查
    for sent in _sentences(now):
        hit = covered(normalise(strip_head(sent)), old_flat)
        if hit >= COVERED_THRESHOLD:
            continue
        out.append({
            "rule": "R7 官方新寫子句", "span": sent,
            "why": f"官方現行文本有這句、舊日文(`faq_info`)只對得上 "
                   f"{hit:.0%}——確認新文本沒有漏掉官方改寫過的內容"})
    return out


def load_tag_text():
    """效果標記表 → {密碼: [(index, text_ja, text_zh), ...]}(R5 用)。"""
    with open(TAGS, encoding="utf-8") as f:
        tags = json.load(f)
    return {c["id"]: [(cl["index"], cl.get("text_ja"), cl.get("text_zh"))
                      for cl in c["clauses"] if cl["section"] == "main"]
            for c in tags}


def check(cards_in_review, blob, cards, kinds, tag_text):
    """審查檔的每一張 → 命中的反向判準清單。"""
    results = []
    for card in cards_in_review:
        if card["skipped"]:
            continue
        hits = (r1_invented(card, blob)
                + r2_missing_activation(card, kinds)
                + r3_main_phase(card)
                + r4_worse_wording(card, blob)
                + r5_family(card, cards, kinds, tag_text)
                + r6_dropped_clause(card)
                + r7_modern_only(card))
        if hits:
            results.append((card, hits))
    return results


def render(review_path, total, results):
    by_rule = {}
    for _, hits in results:
        for hit in hits:
            by_rule[hit["rule"]] = by_rule.get(hit["rule"], 0) + 1
    count_all = sum(by_rule.values())
    lines = [
        "# 子批擬稿的反向檢查",
        "",
        "<!-- 由 script/text_rewrite/check_reverse.py 產生,不要手改;"
        "報告式,不阻擋建置。 -->",
        "",
        f"審查檔:`{review_path}`;進站候選 {total} 張,"
        f"命中 {len(results)} 張 / {count_all} 筆。",
        "",
        "六條判準都是**否定式**——問的是「有沒有否定我的證據」,"
        "不是「有沒有支持我的證據」。命中不等於錯,但每一筆都要有回答。",
        "",
    ]
    if by_rule:
        lines += ["| 判準 | 筆數 |", "|---|---:|"]
        lines += [f"| {rule} | {n} |" for rule, n in sorted(by_rule.items())]
        lines.append("")
    if not results:
        lines += ["(全數通過)", ""]
    for card, hits in results:
        lines += [f"## #{card['no']} `{card['id']}` {card['name']}", ""]
        for hit in hits:
            lines += [f"- **{hit['rule']}**:`{hit['span']}`",
                      f"  - {hit['why']}"]
            for filler, n in hit.get("alts") or []:
                lines.append(f"    - 同位置異形:`{filler}` {n} 例")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="子批審查檔的反向檢查(進站前機檢,報告式)")
    parser.add_argument("review", help="子批審查檔 md 路徑")
    parser.add_argument("--out", help="報告輸出路徑 (預設只印到 stdout)")
    args = parser.parse_args(argv)

    with open(args.review, encoding="utf-8") as f:
        in_review = parse_review(f.read())
    if not in_review:
        print(f"{args.review}:找不到 `## N. \\`密碼\\` 卡名` 的卡片小節")
        return 1

    blob, cards = load_corpus()
    kinds = load_kinds()
    tag_text = load_tag_text()
    live = [c for c in in_review if not c["skipped"]]
    results = check(in_review, blob, cards, kinds, tag_text)

    report = render(os.path.relpath(args.review, _ROOT).replace("\\", "/"),
                    len(live), results)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
        print(f"已寫出 {args.out}")
    else:
        print(report)
    hit_count = sum(len(h) for _, h in results)
    print(f"進站候選 {len(live)} 張;反向檢查命中 {len(results)} 張 / "
          f"{hit_count} 筆")
    return 0


if __name__ == "__main__":
    sys.exit(main())
