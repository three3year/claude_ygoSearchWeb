"""比對列:攤平出來的列(`action_rows.flatten`)+ 查詢 → `run_query` 的結果。

只讀列,不讀卡片結構。查詢的鍵、判法與回傳照 `action_query` 的模組說明;查詢鍵的預設值與正規化在這裡:
先算每張卡直接命中的段(特定、泛用),命中的被代替段帶 `replaced_by`;
直接沒命中的卡沿引用節點的列展開到底(經引用組,`via`、`mark`);
都沒命中的卡,字面含查詢動作詞、結構又不完整的段進未解析組。
"""
import itertools
from operator import attrgetter

from action_query import eval_condition
from action_rows import IMPLIED_SELF, OBJECT_THIS, UNRESTRICTED

REPLACED = "被代替"
DEFAULT_KINDS = ("效果", "代價", "召喚手續")
MODIFIED_KEYS = ("attr", "form", "value")
VIA_GROUP = "經引用"
VIA_GENERIC = "經泛用引用"
AGENTS = ("我方", "對手")
BOTH_SIDES = "雙方各自"


def _normalise(query):
    q = {"actions": [], "from_zones": None, "to_zones": None, "card": None,
         "condition": None, "this_card": False, "targeting": False, "kinds": None,
         "block_kinds": None, "include_condition": False,
         "include_inferred": False, "replacement": False,
         "polarities": ("做",), "generic_only": False, "modified": None,
         "generic_reference": False, "agent": None, "include_unrestricted": False}
    unknown = set(query) - set(q)
    if unknown:
        raise KeyError(f"查詢有不認得的欄位: {sorted(unknown)}")
    q.update(query)
    if sum((bool(q["this_card"]), q["card"] is not None, q["condition"] is not None)) > 1:
        raise ValueError("被動作的卡三者擇一:this_card、card、condition 只能給一個")
    # 條件段看開關:沒指定段類別時,開關開就把條件段加進預設範圍;
    # 指定了段類別仍受開關閘門,開關關就不看條件段。
    kinds = set(q["kinds"] or DEFAULT_KINDS)
    if q["include_condition"]:
        if q["kinds"] is None:
            kinds.add("條件")
    else:
        kinds.discard("條件")
    # 代替:被代替段與做代替的段(帶「代替誰」)都只在查詢含「代替」時看。
    if q["replacement"]:
        if q["kinds"] is None:
            kinds.add("被代替")
    else:
        kinds.discard("被代替")
    q["allowed_kinds"] = kinds
    if q["agent"] is not None and q["agent"] not in AGENTS:
        raise ValueError(f"agent 只能是 {AGENTS}: {q['agent']!r}")
    if q["modified"] is not None and set(q["modified"]) - set(MODIFIED_KEYS):
        raise KeyError(f"modified 有不認得的鍵: {sorted(set(q['modified']) - set(MODIFIED_KEYS))}")
    q["line_constrained"] = any((q["from_zones"], q["to_zones"],
                                 q["card"] is not None, q["this_card"],
                                 q["condition"] is not None, q["targeting"]))
    return q


def modified_matches(want, have):
    """查詢的 modified(attr/form/value 任一子集)對段的被改屬性:attr 看段的清單含不含它
    (修飾段的 attr 是單值),其餘相等。"""
    if not have:
        return False
    for key, value in want.items():
        if key == "attr":
            attrs = have.get("attr")
            if value not in (attrs if isinstance(attrs, list) else [attrs]):
                return False
        elif have.get(key) != value:
            return False
    return True


def match_rows(index, query):
    q = _normalise(query)
    wanted = _Wanted(index, q)
    direct, block_hits, replaced = {}, {}, {}
    for _, rows in itertools.groupby(index.rows, key=attrgetter("seq")):
        rows = list(rows)
        lines = _segment_hit_lines(rows, q, wanted)
        if lines is None:
            continue
        head = rows[0]
        # 經引用看被引用卡指定部分的命中段,不受查詢的區塊種類篩選。
        block_hits.setdefault((head.card, head.block), []).append(head.segment)
        if _block_skipped(head.block_kind, q):
            continue
        hit = direct.get(head.card)
        if hit is None:
            hit = direct[head.card] = {"id": head.card, "segments": [], "group": "泛用"}
        hit["segments"].append(head.segment)
        if head.kind == REPLACED:
            replaced.setdefault(head.card, set()).add(head.segment)
        # 泛用 = 只靠泛用物件命中;沒有物件的段(支付 LP)不算泛用。
        if not lines or not all(line.object is not None and line.object.generic
                                for line in lines):
            hit["group"] = "特定"
    for card, segments in replaced.items():
        direct[card]["replaced_by"] = _replaced_by(index, card, segments)

    found = dict(direct)
    expansion = _Expansion(index, block_hits, q)
    for card in index.referencing:
        if card not in direct:
            hit = expansion.hit(card)
            if hit is not None:
                found[card] = hit
    hits = sorted(found.values(), key=lambda hit: index.card_order[hit["id"]])
    if q["generic_only"]:
        hits = [hit for hit in hits if hit["group"] == "泛用"]
    unparsed = sorted(_unparsed(index, q, found), key=lambda u: index.card_order[u["id"]])
    groups = {"特定": [h["id"] for h in hits if h["group"] == "特定"],
              "泛用": [h["id"] for h in hits if h["group"] == "泛用"],
              "全部": [h["id"] for h in hits if h["group"] != VIA_GROUP],
              VIA_GROUP: [h["id"] for h in hits if h["group"] == VIA_GROUP],
              "未解析": [u["id"] for u in unparsed]}
    return {"hits": hits, "groups": groups, "unparsed": unparsed}


def _block_skipped(block_kind, q):
    return bool(q["block_kinds"]) and block_kind not in q["block_kinds"]


def _in_scope(replacing, kind, polarity, q):
    """段類別、極性、代替的篩選;命中與未解析組共用。做代替的段與被代替段一樣只在查詢含代替時看。"""
    if replacing and not q["replacement"]:
        return False
    return kind in q["allowed_kinds"] and polarity in q["polarities"]


def _segment_hit_lines(rows, q, wanted):
    """一段(同一個段序號的列)命中時回傳命中的線(可為空列表);不命中回 None。區塊種類另外篩。"""
    head = rows[0]
    if not _in_scope(head.replacing, head.kind, head.polarity, q):
        return None
    if any(a not in head.actions for a in q["actions"]):
        return None
    if q["modified"] is not None and not modified_matches(q["modified"], head.modified):
        return None
    if q["agent"] is not None and not agent_matches(q["agent"], head.agent,
                                                    q["include_unrestricted"]):
        return None
    lines = [row.line for row in rows if row.line is not None]
    if not q["line_constrained"]:
        return lines
    return [line for line in lines if _line_matches(line, q, wanted)] or None


def agent_matches(want, have, include_unrestricted):
    """誰:寫明的值相同或是雙方各自命中;算我方只在查我方時命中;不限定只在開關開時命中。"""
    if have == UNRESTRICTED:
        return include_unrestricted
    if have == IMPLIED_SELF:
        return want == "我方"
    return have in (want, BOTH_SIDES)


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


def _replaced_by(index, card, replaced):
    """命中的被代替段 → 做代替的段。"""
    found = {}
    for target, replacing in index.replacements.get(card, ()):
        if target in replaced:
            found[target] = replacing
    return found


def _unparsed(index, q, found):
    """未解析組:無官方日文的卡,與沒命中(直接或經引用)的卡裡字面含查詢動作詞、結構不完整的段。"""
    out = [{"id": card, "reason": reason, "segments": []} for card, reason in index.no_text]
    if not q["actions"]:
        return out
    substituting = q["card"] is not None or q["condition"] is not None
    by_card = {}
    for source in index.unresolved:
        if source.card in found or any(a not in source.literal_actions for a in q["actions"]):
            continue
        reason = _unresolved_reason(source, q, substituting)
        if reason:
            by_card.setdefault(source.card, []).append(
                {"segment": source.segment, "reason": reason, "text": source.text})
    out.extend({"id": card, "reason": None, "segments": segments}
               for card, segments in by_card.items())
    return out


def _unresolved_reason(source, q, substituting):
    """這一段(或解析不出的引用節點)在這個查詢下進未解析組的原因;不進回 None。
    被區塊種類篩掉的區塊只有種類判不出的才列,原因是區塊的;引用節點不看段類別、極性。"""
    skipped = _block_skipped(source.block_kind, q)
    if source.segment is None:
        return None if skipped else source.reason
    if skipped and not source.block_reason:
        return None
    if not _in_scope(source.replacing, source.kind, source.polarity, q):
        return None
    if skipped:
        return source.block_reason
    return source.reason_substituting if substituting else source.reason


class _Expansion:
    """經引用:沿引用節點的列展開到底,走到走過的卡就停。

    展開時「走過的卡」隨路徑不同,結果不能照被引用卡記住;但泛用引用的候選卡上千張,逐張往下展開
    在全庫上是指數級的(「儀式召喚」開泛用引用約五千萬次)。所以先不管走過的卡、求每個
    (被引用卡, 指定的部分)走不走得到命中段(`_reachable`):走不到的,不論路徑怎麼走都是空的,
    先從候選卡裡拿掉;結果與逐張展開相同。"""

    def __init__(self, index, block_hits, q):
        self.index = index
        self.block_hits = block_hits
        self.q = q
        self._reachable = _reachable(index, block_hits, q)
        self._candidates = {}    # id(引用列)→ 走得到命中段的候選卡(順序照原本)

    def hit(self, card):
        blocks = [(card, block) for block, kind in self.index.blocks[card]
                  if not _block_skipped(kind, self.q)]
        via = self.via(blocks, {card})
        if not via:
            return None
        hit = {"id": card, "segments": [], "group": VIA_GROUP, "via": via}
        if all(entry.get("generic") for entry in via):
            hit["mark"] = VIA_GENERIC
        return hit

    def via(self, blocks, visiting):
        """區塊裡的引用節點經由的卡:[{"id", "segments"(該卡指定部分的命中段), "via"(再往下展開的,
        有才寫), "generic"(經泛用引用節點,有才寫)}];同一張卡只列一次。"""
        out, seen = [], set()
        for key in blocks:
            for ref in self.index.references.get(key, ()):
                if ref.generic and not self.q["generic_reference"]:
                    continue
                for cid in self.candidates(ref):
                    if cid in visiting or cid in seen:
                        continue
                    entry = self.entry(cid, ref.effect, visiting)
                    if entry is None:
                        continue
                    if ref.generic:
                        entry["generic"] = True
                    seen.add(cid)
                    out.append(entry)
        return out

    def candidates(self, ref):
        """引用列的候選卡裡有結構、又走得到命中段的。"""
        if id(ref) not in self._candidates:
            self._candidates[id(ref)] = [cid for cid in ref.candidates
                                         if self._reachable(cid, ref.effect)]
        return self._candidates[id(ref)]

    def entry(self, target, effect, visiting):
        part = self.index.part(target, effect)
        segments = [seg for block in part for seg in self.block_hits.get((target, block), ())]
        if segments:
            return {"id": target, "segments": segments}
        nested = self.via([(target, block) for block in part], visiting | {target})
        if nested:
            return {"id": target, "segments": [], "via": nested}
        return None


def _reachable(index, block_hits, q):
    """(被引用卡, 指定的部分的 JSON)→ 不管走過的卡,沿引用節點走不走得到命中段。
    沒有引用節點的卡只看自己指定的部分有沒有命中段;有引用節點的卡(全庫幾十張)求不動點。"""
    hit_blocks = set(block_hits)
    owners = index.referencing
    direct_memo = {}

    def direct(card, effect):
        key = (card, effect)
        if key not in direct_memo:
            direct_memo[key] = any((card, block) in hit_blocks
                                   for block in index.part(card, effect))
        return direct_memo[key]

    def followed(ref):
        return not ref.generic or q["generic_reference"]

    # 每個引用列:候選卡裡沒有引用節點的卡有沒有直接命中;有引用節點的卡另列,留給不動點。
    leads = {}
    for refs in index.references.values():
        for ref in filter(followed, refs):
            outside = any(cid in index.blocks and cid not in owners and direct(cid, ref.effect)
                          for cid in ref.candidates)
            leads[id(ref)] = (outside, [(cid, ref.effect) for cid in ref.candidates
                                        if cid in owners])
    effects = {ref.effect for refs in index.references.values() for ref in refs}
    nodes = {(owner, effect) for owner in owners for effect in effects}
    good = {node for node in nodes if direct(*node)}
    changed = True
    while changed:
        changed = False
        for owner, effect in nodes - good:
            for block in index.part(owner, effect):
                if any(leads[id(ref)][0] or any(n in good for n in leads[id(ref)][1])
                       for ref in filter(followed, index.references.get((owner, block), ()))):
                    good.add((owner, effect))
                    changed = True
                    break

    def reachable(card, effect):
        if card not in index.blocks:
            return False
        return (card, effect) in good if card in owners else direct(card, effect)
    return reachable


class _Wanted:
    """查詢要代入物件的卡:指定卡是總表的一個位置,給條件是滿足查詢條件的卡的位元集。
    這張卡自己不代入:只比物件是不是此卡(條件式剛好讓這張卡滿足的不算)。"""

    def __init__(self, index, q):
        self.mask = None
        self.this_card = bool(q["this_card"])
        if q["card"] is not None:
            at = index.position.get(q["card"])
            self.mask = 0 if at is None else 1 << at
        elif q["condition"] is not None:
            self.mask = index.condition_mask(
                q["condition"], lambda view: eval_condition(q["condition"], view) is True)

    def fits(self, obj):
        if self.this_card:
            return obj.kind == OBJECT_THIS
        return self.mask is None or bool(obj.candidates.mask & self.mask)
