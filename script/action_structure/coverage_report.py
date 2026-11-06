"""覆蓋報告(純函式):全庫卡片結構 → 計數 → markdown。

單一接縫:`build_coverage(structures) → coverage`、`render_coverage(coverage) → md`。
讀產物、寫檔都在薄殼 `build_report.py`;報告正文不含時間與雜湊,同一份產物
兩次產出逐位元組相同(時間與雜湊由薄殼印到 stdout)。

計數的層次(spec「覆蓋報告」:各區塊種類、各段類別、各格解析出與解析不出的數量,
依原因分類、附卡號):
- 卡片層:卡片總表張數 = 有卡片結構的張數 + 無官方日文的張數(加總必須相等)。
- 區塊:依區塊種類計區塊數、解析出、解析不出、張數;解析不出依原因附卡號。
- 段:依段類別同上;段整段解析不出依原因附卡號。
- 段的各格:只對解析出的段計(整段解析不出的已依原因列過):有值、留空、解析不出
  (`{"reason"}` 形的格)依原因附卡號。對象線的從/到另依來源(明寫、繼承、推得、留空)計。
- 物件:依來源計;解析不出依原因附卡號。
- 不認得的「」名稱:名稱表列裡帶 `unparsed` 的(名稱表由票 04 填;這裡先留節與接點)。
卡號列表一律排序去重,「附卡號」列全部、不截斷。
"""
from collections import Counter, defaultdict

from structure_shape import (BLOCK_KINDS, OBJECT_SOURCES, POSITION_SOURCES,
                             SEGMENT_KINDS, iter_segments)

# 段的各格:鍵名 → 報告列名(spec「段」表的格;極性永遠有值,不列)。
SEGMENT_FIELDS = (
    ("actions", "動作詞"), ("lines", "對象線"), ("agent", "誰"),
    ("recipient", "受方"), ("cause", "原因"), ("duration", "期間"),
    ("timing", "時機"), ("trigger", "觸發形"), ("premise", "前提"),
    ("modified", "被改的屬性"), ("amount", "數量"), ("optional", "可選"),
    ("replaces", "代替誰"), ("predicate", "原述語字面"), ("voice", "態"),
)
POSITION_EMPTY = "留空"


def _is_unparsed_cell(value):
    """「解析不出」的格:`structure_shape.unparsed(reason)` 的形狀。"""
    return isinstance(value, dict) and set(value) == {"reason"}


def _reason_bucket():
    return {"count": 0, "cards": set()}


def _finish_reasons(reasons, unit):
    """原因 → {單位數, 卡號(排序去重)};原因依名稱排序,報告才穩定。"""
    return {reason: {unit: bucket["count"],
                     "cards": sorted(bucket["cards"])}
            for reason, bucket in sorted(reasons.items())}


def _finish_by_kind(by_kind, kinds, unit):
    return {kind: {unit: by_kind[kind]["count"],
                   "parsed": by_kind[kind]["parsed"],
                   "unparsed": by_kind[kind]["count"] - by_kind[kind]["parsed"],
                   "cards": len(by_kind[kind]["cards"])}
            for kind in kinds}


def _kind_bucket():
    return {"count": 0, "parsed": 0, "cards": set()}


def build_coverage(structures):
    """全庫卡片結構 → 覆蓋計數(純資料,給 `render_coverage` 與測試)。"""
    no_text = []
    block_kinds = defaultdict(_kind_bucket)
    block_reasons = defaultdict(_reason_bucket)
    seg_kinds = defaultdict(_kind_bucket)
    seg_reasons = defaultdict(_reason_bucket)
    fields = {key: {"filled": 0, "empty": 0, "unparsed": 0,
                    "reasons": defaultdict(_reason_bucket)}
              for key, _ in SEGMENT_FIELDS}
    positions = {"from": Counter(), "to": Counter()}
    lines = 0
    obj_sources = Counter()
    obj_reasons = defaultdict(_reason_bucket)
    objects_total = objects_unparsed = 0
    unknown_names = defaultdict(set)

    for card in structures:
        cid = card["id"]
        if card["unparsed"]:
            no_text.append(cid)
            continue
        for obj in card["objects"]:
            objects_total += 1
            obj_sources[obj["source"]["kind"]] += 1
            if obj["unparsed"]:
                objects_unparsed += 1
                bucket = obj_reasons[obj["unparsed"]["reason"]]
                bucket["count"] += 1
                bucket["cards"].add(cid)
        for row in card["names"]:
            if row.get("unparsed"):
                unknown_names[row["text"]].add(cid)
        counted = set()
        for block in card["blocks"]:
            _count_block(block, cid, block_kinds, block_reasons)
            for owner, seg in iter_segments(block):
                if owner is not block and owner["id"] not in counted:
                    # 內嵌效果的區塊也各算一個區塊(一次)。
                    counted.add(owner["id"])
                    _count_block(owner, cid, block_kinds, block_reasons)
                kind = seg_kinds[seg["kind"]]
                kind["count"] += 1
                kind["cards"].add(cid)
                if seg["unparsed"]:
                    bucket = seg_reasons[seg["unparsed"]["reason"]]
                    bucket["count"] += 1
                    bucket["cards"].add(cid)
                    continue
                kind["parsed"] += 1
                for key, _ in SEGMENT_FIELDS:
                    _count_field(fields[key], seg[key], cid)
                for line in seg["lines"]:
                    lines += 1
                    for side in ("from", "to"):
                        pos = line[side]
                        positions[side][pos["source"] if pos else POSITION_EMPTY] += 1

    blocks_total = sum(b["count"] for b in block_kinds.values())
    blocks_parsed = sum(b["parsed"] for b in block_kinds.values())
    segs_total = sum(s["count"] for s in seg_kinds.values())
    segs_parsed = sum(s["parsed"] for s in seg_kinds.values())
    return {
        "cards": len(structures),
        "with_structure": len(structures) - len(no_text),
        "no_official_text": sorted(no_text),
        "blocks": {"total": blocks_total, "parsed": blocks_parsed,
                   "unparsed": blocks_total - blocks_parsed,
                   "by_kind": _finish_by_kind(block_kinds, BLOCK_KINDS, "blocks"),
                   "reasons": _finish_reasons(block_reasons, "blocks")},
        "segments": {"total": segs_total, "parsed": segs_parsed,
                     "unparsed": segs_total - segs_parsed,
                     "by_kind": _finish_by_kind(seg_kinds, SEGMENT_KINDS,
                                                "segments"),
                     "reasons": _finish_reasons(seg_reasons, "segments")},
        "fields": {key: {"filled": cell["filled"], "empty": cell["empty"],
                         "unparsed": cell["unparsed"],
                         "reasons": _finish_reasons(cell["reasons"], "segments")}
                   for key, cell in fields.items()},
        "lines": lines,
        "positions": {side: {source: positions[side][source]
                             for source in POSITION_SOURCES + (POSITION_EMPTY,)}
                      for side in ("from", "to")},
        "objects": {"total": objects_total,
                    "parsed": objects_total - objects_unparsed,
                    "unparsed": objects_unparsed,
                    "by_source": {s: obj_sources[s] for s in OBJECT_SOURCES},
                    "reasons": _finish_reasons(obj_reasons, "objects")},
        "unknown_names": {name: sorted(cards)
                          for name, cards in sorted(unknown_names.items())},
    }


def _count_block(block, cid, block_kinds, block_reasons):
    kind = block_kinds[block["kind"]]
    kind["count"] += 1
    kind["cards"].add(cid)
    if block["unparsed"]:
        bucket = block_reasons[block["unparsed"]["reason"]]
        bucket["count"] += 1
        bucket["cards"].add(cid)
    else:
        kind["parsed"] += 1


def _count_field(cell, value, cid):
    if _is_unparsed_cell(value):
        cell["unparsed"] += 1
        bucket = cell["reasons"][value["reason"]]
        bucket["count"] += 1
        bucket["cards"].add(cid)
    elif value is None or value == [] or value == {}:
        cell["empty"] += 1
    else:
        cell["filled"] += 1


# ── 輸出 ─────────────────────────────────────────────────────
def _n(value):
    return f"{value:,}"


def _card_lines(cards):
    """附卡號:一行一個,列全部不截斷(git diff 才讀得出哪張卡進出)。"""
    return [f"- `{cid}`" for cid in cards]


def _reason_sections(reasons, unit, unit_label, level="####"):
    out = []
    for reason, bucket in reasons.items():
        out.append(f"{level} {reason}({_n(bucket[unit])} {unit_label} / "
                   f"{_n(len(bucket['cards']))} 張)")
        out.append("")
        out.extend(_card_lines(bucket["cards"]))
        out.append("")
    if not reasons:
        out.append("(無)")
        out.append("")
    return out


def render_coverage(cov):
    """覆蓋計數 → markdown;不寫時間,排序全部固定。"""
    out = [
        "# 覆蓋報告(動作搜尋的卡片結構)",
        "",
        "<!-- 由 script/action_structure/build_report.py 產生,不要手改;"
        "重建卡片結構後重跑即刷新。 -->",
        "",
        "計數對象是 `data/action_structure.json`(卡片結構產物)。「解析不出」的定義與"
        "原因字串在 script/action_structure/ 各模組的 `REASON_*`;"
        "段的各格只對解析出的段計數,整段解析不出的段已依原因列在「段」一節;"
        "無官方日文的卡沒有結構,不計區塊、段、物件(連物件0 也不算,所以物件數比"
        "build_structure.py 印的少 20)。",
        "",
        "## 總覽",
        "",
        f"卡片總表 {_n(cov['cards'])} 張 = 有卡片結構 {_n(cov['with_structure'])} 張"
        f" + 無官方日文 {_n(len(cov['no_official_text']))} 張。",
        "",
        "| 層次 | 總數 | 解析出 | 解析不出 |",
        "|---|---|---|---|",
    ]
    for label, key in (("區塊", "blocks"), ("段", "segments"), ("物件", "objects")):
        node = cov[key]
        out.append(f"| {label} | {_n(node['total'])} | {_n(node['parsed'])} | "
                   f"{_n(node['unparsed'])} |")
    out += ["", "## 卡片層:無官方日文"
                f"({_n(len(cov['no_official_text']))} 張)", "",
            "整張標未解析,原因「無官方日文」,不納入抽取(spec、ADR-0006)。", ""]
    out += _card_lines(cov["no_official_text"]) or ["(無)"]
    out += ["", "## 區塊", "", "| 區塊種類 | 區塊數 | 解析出 | 解析不出 | 張數 |",
            "|---|---|---|---|---|"]
    for kind, row in cov["blocks"]["by_kind"].items():
        out.append(f"| {kind} | {_n(row['blocks'])} | {_n(row['parsed'])} | "
                   f"{_n(row['unparsed'])} | {_n(row['cards'])} |")
    out += ["", "### 區塊解析不出的原因", ""]
    out += _reason_sections(cov["blocks"]["reasons"], "blocks", "區塊")
    out += ["## 段", "", "| 段類別 | 段數 | 解析出 | 解析不出 | 張數 |",
            "|---|---|---|---|---|"]
    for kind, row in cov["segments"]["by_kind"].items():
        out.append(f"| {kind} | {_n(row['segments'])} | {_n(row['parsed'])} | "
                   f"{_n(row['unparsed'])} | {_n(row['cards'])} |")
    out += ["", "### 段解析不出的原因", ""]
    out += _reason_sections(cov["segments"]["reasons"], "segments", "段")
    out += ["## 段的各格", "",
            f"對象是解析出的 {_n(cov['segments']['parsed'])} 段。", "",
            "| 格 | 有值 | 留空 | 解析不出 |", "|---|---|---|---|"]
    for key, label in SEGMENT_FIELDS:
        cell = cov["fields"][key]
        out.append(f"| {label} | {_n(cell['filled'])} | {_n(cell['empty'])} | "
                   f"{_n(cell['unparsed'])} |")
    out += ["", f"### 對象線的從/到(共 {_n(cov['lines'])} 條)", "",
            "| 來源 | 從 | 到 |", "|---|---|---|"]
    for source in POSITION_SOURCES + (POSITION_EMPTY,):
        out.append(f"| {source} | {_n(cov['positions']['from'][source])} | "
                   f"{_n(cov['positions']['to'][source])} |")
    out += ["", "### 各格解析不出的原因", ""]
    any_field = False
    for key, label in SEGMENT_FIELDS:
        reasons = cov["fields"][key]["reasons"]
        if not reasons:
            continue
        any_field = True
        out += [f"#### {label}", ""]
        out += _reason_sections(reasons, "segments", "段", level="#####")
    if not any_field:
        out += ["(無)", ""]
    out += ["## 物件", "", "| 來源 | 物件數 |", "|---|---|"]
    for source, count in cov["objects"]["by_source"].items():
        out.append(f"| {source} | {_n(count)} |")
    out += ["", "### 物件解析不出的原因", ""]
    out += _reason_sections(cov["objects"]["reasons"], "objects", "個")
    out += [f"## 不認得的「」名稱({_n(len(cov['unknown_names']))} 個)", "",
            "名稱表裡對不到卡名、字段、宣言的「」名稱;該條件標未解析、建置照常通過"
            "(名稱表由票 04 接上,接點是名稱表列的 `unparsed`)。", ""]
    if cov["unknown_names"]:
        for name, cards in cov["unknown_names"].items():
            out.append(f"- 「{name}」({_n(len(cards))} 張):"
                       + "、".join(f"`{cid}`" for cid in cards))
    else:
        out.append("(無)")
    out.append("")
    return "\n".join(out)
