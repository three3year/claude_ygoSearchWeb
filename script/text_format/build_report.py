"""三級分類報表殼:全庫盤點 → .scratch/text-format/report.md(票05)。

三個佇列——舊文本(改寫佇列)、官方已改寫(優先稽核佇列)、新格式新卡
(一般稽核佇列)——加「日期不明」獨立區,末尾附「含①卡的舊詞彙訊號命中」
人工抽查附錄(僅供抽查,不保證準確,不混入正式佇列)。

分級與標籤全部來自 classify.classify_card(純函式),這裡只做讀檔、分組、
排版——報表產生器是薄殼,不立測試(spec Testing Decisions)。冪等:同一份
輸入重跑,輸出逐位元組相同(不寫時間戳,排序全部固定);資料更新後重跑,
清單即刷新。報表落在 .scratch,不進 docs、不進前端。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/text_format/build_report.py
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from itertools import groupby

# 先 import classify:tag_card 的搜尋路徑由它在載入時 append,tagcard 那行
# 才找得到模組——這兩行的順序是依賴,不是字母序巧合
from classify import (OLD_PATTERNS, TIER_NEW, TIER_OLD, TIER_REWRITTEN,
                      TIER_UNDATED, classify_card, old_pattern_labels)
from ocg_dates import align_ocg_dates, load_ocg_dates
from tagcard import (FOOTNOTE_RE, TYPE_MONSTER, TYPE_SPELL, TYPE_TRAP,
                     _segments, _zh_sections, is_pure_normal)

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CARDS = os.path.join(_ROOT, "data", "cards.json")
DEFAULT_DATES = os.path.join(_ROOT, "data", "sources", "ocg-dates.json")
DEFAULT_OUT = os.path.join(_ROOT, ".scratch", "text-format", "report.md")

GUIDE = "docs/text_format_guide.md"
# 沒命中任何具體條目的舊段:只需 §4.1 缺圈號分層(全部舊段適用的基礎條目)
BASE_LABEL = "僅基礎條目"
BASE_REF = "§4.1"

# 分群用的大類三分;排列順序即群與群之間的排序
CATEGORIES = ((TYPE_MONSTER, "怪獸"), (TYPE_SPELL, "魔法"), (TYPE_TRAP, "陷阱"))

_LABEL_POS = {key: pos for pos, (key, _, _) in enumerate(OLD_PATTERNS)}
_LABEL_REF = {key: ref for key, ref, _ in OLD_PATTERNS}


def category(ctype):
    """type 位元 → 大類名稱與排序位(怪獸/魔法/陷阱)。"""
    for pos, (bit, label) in enumerate(CATEGORIES):
        if ctype & bit:
            return pos, label
    return len(CATEGORIES), "其他"


def _pendulum_mark(section):
    return "(靈擺)" if section == "pendulum" else ""


def scan(cards, dates):
    """全庫一次掃描 → 各區塊要用的資料(分級都來自 classify_card)。"""
    stats = {"cards": len(cards), "pure_normal": 0, "no_segments": 0}
    seg_counts = Counter()
    card_sets = defaultdict(set)
    groups = defaultdict(list)   # (標籤組合, 大類序, 大類) → [(id, 名, 段)]
    dated = {TIER_REWRITTEN: {}, TIER_NEW: {}}   # 分級 → {id: (首發日, 名)}
    undated = []                 # [(id, 名)]
    signals = defaultdict(list)  # 條目 → [(id, 名, 段, 分級)]
    for card in cards:
        if is_pure_normal(card.get("type", 0)):
            stats["pure_normal"] += 1
            continue
        date = dates.get(card["id"])
        segs = classify_card(card, date)
        if not segs:
            stats["no_segments"] += 1
            continue
        cid, name = card["id"], card["name_zh"]
        cat_pos, cat = category(card["type"])
        for seg in segs:
            tier = seg["tier"]
            seg_counts[tier] += 1
            card_sets[tier].add(cid)
            if tier == TIER_OLD:
                groups[(tuple(seg["labels"]), cat_pos, cat)].append(
                    (cid, name, seg["section"]))
            elif tier != TIER_UNDATED:
                dated[tier][cid] = (date, name)
        if any(seg["tier"] == TIER_UNDATED for seg in segs):
            undated.append((cid, name))
        # 附錄的訊號只掃①段自身的文字(不含前言段),與規範 §4 各條目的
        # 誤報統計同一個參照面(新式段)——換個掃描面,那些數字就對不上
        tier_by_section = {seg["section"]: seg["tier"] for seg in segs}
        sections, _ = _zh_sections(FOOTNOTE_RE.sub("", card.get("desc") or ""))
        for section, text in sections:
            _, numbered, _ = _segments(text)
            if not numbered:
                continue
            hits = {label for _, (start, end) in numbered
                    for label in old_pattern_labels(text[start:end])}
            for label in sorted(hits, key=_LABEL_POS.get):
                signals[label].append(
                    (cid, name, section, tier_by_section[section]))
    return stats, seg_counts, card_sets, groups, dated, undated, signals


# ---------------------------------------------------------------- 排版

def _overview(stats, seg_counts, card_sets):
    lines = [
        "## 總覽",
        "",
        f"掃描基準:卡片總表 {stats['cards']:,} 張;純通常怪獸整張排除 "
        f"{stats['pure_normal']:,} 張、無段可判 {stats['no_segments']:,} 張"
        "(空卡文或只剩風味文)。",
        "",
        "| 分級 | 段數 | 張數 | 去向 |",
        "|---|---|---|---|",
    ]
    for tier, queue in ((TIER_OLD, "改寫佇列"),
                        (TIER_REWRITTEN, "優先稽核佇列"),
                        (TIER_NEW, "一般稽核佇列"),
                        (TIER_UNDATED, "獨立列出,不進佇列")):
        lines.append(f"| {tier} | {seg_counts[tier]:,} | "
                     f"{len(card_sets[tier]):,} | {queue} |")
    lines += [
        "",
        "靈擺卡各段獨立判級,同一張卡可同時出現在多個分級;張數是「至少有"
        "一段屬該級」的卡數,各級張數合計因此可大於實卡數。舊文本的段集合"
        "= tagcard 報告的 pending_split(同一把尺,test_classify.py 迴歸"
        "釘住這個等式)。",
    ]
    return lines


def _group_title(labels):
    if not labels:
        return f"{BASE_LABEL}({BASE_REF})"
    return "+".join(f"{label}({_LABEL_REF[label]})" for label in labels)


def _rewrite_queue(seg_counts, card_sets, groups):
    lines = [
        f"## 改寫佇列(舊文本,{seg_counts[TIER_OLD]:,} 段 / "
        f"{len(card_sets[TIER_OLD]):,} 張)",
        "",
        f"依「所需對應表條目(多標籤)× 大類」分群——同一群的段落共用同一組"
        f"舊→新對應規則({GUIDE} §4,偵測樣式維護於 "
        "script/text_format/classify.py 的 `OLD_PATTERNS`)。條目是近似訊號,"
        "服務分群、不是建置關卡;命中多條的段落自成一群(整組規則一起套),"
        f"沒命中任何條目的段落歸「{BASE_LABEL}」——只需 {BASE_REF} 缺圈號"
        "分層。靈擺欄的段落以「(靈擺)」標注。",
    ]
    def group_order(item):
        (labels, cat_pos, _), _ = item
        return tuple(_LABEL_POS[label] for label in labels), cat_pos

    for (labels, _, cat), rows in sorted(groups.items(), key=group_order):
        lines += ["", f"### {_group_title(labels)} × {cat}({len(rows):,} 段)",
                  ""]
        lines += [f"- `{cid}` {name}{_pendulum_mark(section)}"
                  for cid, name, section in sorted(rows)]
    return lines


def _audit_queue(title, note, rows):
    lines = [f"## {title}", "", note]
    ordered = sorted((date, cid, name)
                     for cid, (date, name) in rows.items())
    for year, batch in groupby(ordered, key=lambda row: row[0][:4]):
        batch = list(batch)
        lines += ["", f"### {year} 年({len(batch):,} 張)", ""]
        lines += [f"- `{cid}` {name}({date})" for date, cid, name in batch]
    return lines


def _undated_section(seg_counts, undated):
    lines = [
        f"## 日期不明({seg_counts[TIER_UNDATED]:,} 段 / "
        f"{len(undated):,} 張)",
        "",
        "有①但查無 OCG 首發日;獨立列出,不併入任何佇列、不猜。來源補到"
        "日期後重跑,這批會自動歸隊。",
        "",
    ]
    lines += [f"- `{cid}` {name}" for cid, name in sorted(undated)]
    return lines


def _signals_appendix(signals):
    lines = [
        "## 附錄:含①卡的舊詞彙訊號命中",
        "",
        "**僅供人工抽查,不保證準確**——偵測樣式是為舊文本段設計的,掃在"
        f"新式段上以偽陽性為主(各條目的誤報樣態見 {GUIDE} §4 逐條);此清單"
        "不混入上方任何佇列。掃描對象是①段自身的文字(不含前言段),與 §4 "
        "的誤報參照組同一個口徑。",
    ]
    for label, _, _ in OLD_PATTERNS:
        rows = signals.get(label, [])
        lines += ["", f"### {label}({_LABEL_REF[label]},{len(rows):,} 段)",
                  ""]
        lines += [f"- `{cid}` {name}{_pendulum_mark(section)}——{tier}"
                  for cid, name, section, tier in sorted(rows)] or ["(無)"]
    return lines


def render(stats, seg_counts, card_sets, groups, dated, undated, signals):
    sections = (
        [
            "# 三級分類報表(文本世代盤點)",
            "",
            "<!-- 由 script/text_format/build_report.py 產生,不要手改;"
            "資料更新後重跑即刷新。 -->",
            "",
            "分級判準見 CONTEXT.md「舊式卡文/新式卡文」與 "
            "script/text_format/classify.py:①編號段為界的二分,再以 OCG "
            "首發日對 9 期界日(2014-03-21)細分。",
        ],
        _overview(stats, seg_counts, card_sets),
        _rewrite_queue(seg_counts, card_sets, groups),
        _audit_queue(
            f"優先稽核佇列(官方已改寫,{seg_counts[TIER_REWRITTEN]:,} 段 / "
            f"{len(dated[TIER_REWRITTEN]):,} 張)",
            "有①、OCG 首發日在 9 期界日之前——官方把舊卡文機械式改寫成新"
            "格式,譯文品質更可疑,稽核優先。依首發日排序、按年分批。",
            dated[TIER_REWRITTEN]),
        _audit_queue(
            f"一般稽核佇列(新格式新卡,{seg_counts[TIER_NEW]:,} 段 / "
            f"{len(dated[TIER_NEW]):,} 張)",
            "有①、9 期界日(含)以後首發——生來就是新格式。依首發日排序、"
            "按年分批。",
            dated[TIER_NEW]),
        _undated_section(seg_counts, undated),
        _signals_appendix(signals),
    )
    # 每一節後面補一個空行,最後那個空行就是檔案結尾的換行
    return "\n".join(line for section in sections for line in [*section, ""])


def main(argv=None):
    parser = argparse.ArgumentParser(description="三級分類報表(文本世代盤點)")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表 JSON (預設 data/cards.json)")
    parser.add_argument("--dates", default=DEFAULT_DATES,
                        help="OCG 首發日來源 JSON "
                             "(預設 data/sources/ocg-dates.json)")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="報表輸出路徑 (預設 .scratch/text-format/report.md)")
    args = parser.parse_args(argv)

    with open(args.cards, encoding="utf-8") as f:
        cards = json.load(f)
    dates = align_ocg_dates(cards, load_ocg_dates(args.dates))

    stats, seg_counts, card_sets, groups, dated, undated, signals = scan(
        cards, dates)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(stats, seg_counts, card_sets, groups, dated, undated,
                       signals))

    for tier in (TIER_OLD, TIER_REWRITTEN, TIER_NEW, TIER_UNDATED):
        print(f"{tier}: {seg_counts[tier]:,} 段 / {len(card_sets[tier]):,} 張")
    print(f"改寫佇列分群: {len(groups)} 群;"
          f"附錄訊號命中: {sum(len(v) for v in signals.values()):,} 段")
    print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
