"""比對列:攤平出來的列(`action_rows.flatten`)+ 查詢 → 與 `run_query` 同形的結果。

只讀列,不讀卡片結構。查詢的鍵與判法照 `action_query` 的模組說明;這一版只做直接命中
(特定、泛用、全部三組與命中段),未解析組、經引用、代替(被代替段的連結)留給票 04,那幾組先回空的。
"""
import itertools
from operator import attrgetter

from action_query import VIA_GROUP, _normalise, eval_condition, modified_matches


def match_rows(index, query):
    q = _normalise(query)
    wanted = _Wanted(index, q)
    hits, by_card = [], {}
    for _, rows in itertools.groupby(index.rows, key=attrgetter("seq")):
        rows = list(rows)
        lines = _segment_hit_lines(rows, q, wanted)
        if lines is None:
            continue
        head = rows[0]
        hit = by_card.get(head.card)
        if hit is None:
            hit = by_card[head.card] = {"id": head.card, "segments": [], "group": "泛用"}
            hits.append(hit)
        hit["segments"].append(head.segment)
        # 泛用 = 只靠泛用物件命中;沒有物件的段(支付 LP)不算泛用。
        if not lines or not all(line.object is not None and line.object.generic
                                for line in lines):
            hit["group"] = "特定"
    if q["generic_only"]:
        hits = [hit for hit in hits if hit["group"] == "泛用"]
    groups = {"特定": [h["id"] for h in hits if h["group"] == "特定"],
              "泛用": [h["id"] for h in hits if h["group"] == "泛用"],
              "全部": [h["id"] for h in hits],
              VIA_GROUP: [],
              "未解析": []}
    return {"hits": hits, "groups": groups, "unparsed": []}


def _segment_hit_lines(rows, q, wanted):
    """一段(同一個段序號的列)命中時回傳命中的線(可為空列表);不命中回 None。"""
    head = rows[0]
    if q["block_kinds"] and head.block_kind not in q["block_kinds"]:
        return None
    if head.replacing and not q["replacement"]:
        return None
    if head.kind not in q["allowed_kinds"] or head.polarity not in q["polarities"]:
        return None
    if any(a not in head.actions for a in q["actions"]):
        return None
    if q["modified"] is not None and not modified_matches(q["modified"], head.modified):
        return None
    lines = [row.line for row in rows if row.line is not None]
    if not q["line_constrained"]:
        return lines
    return [line for line in lines if _line_matches(line, q, wanted)] or None


def _line_matches(line, q, wanted):
    if line.doer:
        return False
    if q["targeting"] and not line.targeting:
        return False
    if q["from_zones"] and not _zones_match(q["from_zones"], line.from_, q["include_inferred"]):
        return False
    if q["to_zones"] and not _zones_match(q["to_zones"], line.to, q["include_inferred"]):
        return False
    return line.object is not None and wanted.fits(line.object)


def _zones_match(query_zones, pos, include_inferred):
    if pos is None or (pos.inferred and not include_inferred):
        return False
    for want in query_zones:
        zone, side = (want["zone"], want["side"]) if isinstance(want, dict) else (want, None)
        if (zone in pos.names) if side is None else ((zone, side) in pos.zones):
            return True
    return False


class _Wanted:
    """查詢要代入物件的卡:指定卡是總表的一個位置,給條件是滿足查詢條件的卡的位元集。"""

    def __init__(self, index, q):
        self.mask = None
        if q["card"] is not None:
            at = index.position.get(q["card"])
            self.mask = 0 if at is None else 1 << at
        elif q["condition"] is not None:
            self.mask = index.mask_of(i for i, view in enumerate(index.views)
                                      if eval_condition(q["condition"], view) is True)

    def fits(self, obj):
        return self.mask is None or bool(obj.candidates.mask & self.mask)
