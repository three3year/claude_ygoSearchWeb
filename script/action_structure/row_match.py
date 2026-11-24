import itertools
from operator import attrgetter

from action_rows import IMPLIED_SELF, UNRESTRICTED
from condition_judge import OBJECT_THIS, eval_condition
from query_names import drop_blank_names, resolve_names

REPLACED = "被代替"
DEFAULT_KINDS = ("效果", "代價", "召喚手續")
MODIFIED_KEYS = ("attr", "form", "value")
VIA_GROUP = "經引用"
VIA_GENERIC = "經泛用引用"
SIDES = ("我方", "對手")
BOTH_SIDES = "雙方各自"
BROAD_ZONE_SIDES = ("任一方", BOTH_SIDES, "持有者")
CAUSE_KINDS = ("戰鬥", "效果", "戰鬥或效果", "戰鬥以外", "作為素材", "召喚方式", "方法", "規則")
CAUSE_COVERS = {"戰鬥或效果": ("戰鬥", "效果"), "戰鬥以外": ("效果",)}


def _normalise(query):
    q = {"actions": [], "from_zones": None, "to_zones": None, "card": None,
         "condition": None, "this_card": False, "targeting": False, "kinds": None,
         "block_kinds": None, "include_condition": False,
         "include_inferred": False, "replacement": False,
         "polarities": ("做",), "generic_only": False, "modified": None,
         "generic_reference": False, "agent": None, "include_unrestricted": False,
         "recipient": None, "cause": None}
    unknown = set(query) - set(q)
    if unknown:
        raise KeyError(f"查詢有不認得的欄位: {sorted(unknown)}")
    q.update(query)
    q["condition"] = drop_blank_names(q["condition"])
    if sum((bool(q["this_card"]), q["card"] is not None, q["condition"] is not None)) > 1:
        raise ValueError("被動作的卡三者擇一:this_card、card、condition 只能給一個")
    kinds = set(q["kinds"] or DEFAULT_KINDS)
    if q["include_condition"]:
        if q["kinds"] is None:
            kinds.add("條件")
    else:
        kinds.discard("條件")
    if q["replacement"]:
        if q["kinds"] is None:
            kinds.add("被代替")
    else:
        kinds.discard("被代替")
    q["allowed_kinds"] = kinds
    if q["agent"] is not None and q["agent"] not in SIDES:
        raise ValueError(f"agent 只能是 {SIDES}: {q['agent']!r}")
    if q["recipient"] is not None and q["recipient"] not in SIDES:
        raise ValueError(f"recipient 只能是 {SIDES}: {q['recipient']!r}")
    q["cause"] = _normalise_cause(q["cause"])
    if q["modified"] is not None and set(q["modified"]) - set(MODIFIED_KEYS):
        raise KeyError(f"modified 有不認得的鍵: {sorted(set(q['modified']) - set(MODIFIED_KEYS))}")
    q["line_constrained"] = any((q["from_zones"], q["to_zones"],
                                 q["card"] is not None, q["this_card"],
                                 q["condition"] is not None, q["targeting"]))
    return q


def _normalise_cause(cause):
    if cause is None:
        return None
    kind, side = (cause, None) if isinstance(cause, str) else (cause["kind"], cause.get("side"))
    if isinstance(cause, dict) and set(cause) - {"kind", "side"}:
        raise KeyError(f"cause 有不認得的鍵: {sorted(set(cause) - {'kind', 'side'})}")
    if kind not in CAUSE_KINDS:
        raise ValueError(f"cause 的種類只能是 {CAUSE_KINDS}: {kind!r}")
    if side is not None and side not in SIDES:
        raise ValueError(f"cause 的方只能是 {SIDES}: {side!r}")
    return kind, side


def modified_matches(want, have):
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
        block_hits.setdefault((head.card, head.block), []).append(head.segment)
        if _block_skipped(head.block_kind, q):
            continue
        hit = direct.get(head.card)
        if hit is None:
            hit = direct[head.card] = {"id": head.card, "segments": [], "group": "泛用"}
        hit["segments"].append(head.segment)
        if head.kind == REPLACED:
            replaced.setdefault(head.card, set()).add(head.segment)
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
    if replacing and not q["replacement"]:
        return False
    return kind in q["allowed_kinds"] and polarity in q["polarities"]


def _segment_hit_lines(rows, q, wanted):
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
    if q["recipient"] is not None and head.recipient not in (q["recipient"], BOTH_SIDES):
        return None
    if q["cause"] is not None and not cause_matches(q["cause"], head.cause,
                                                    q["include_unrestricted"]):
        return None
    lines = [row.line for row in rows if row.line is not None]
    if not q["line_constrained"]:
        return lines
    return [line for line in lines if _line_matches(line, q, wanted)] or None


def agent_matches(want, have, include_unrestricted):
    if have == UNRESTRICTED:
        return include_unrestricted
    if have == IMPLIED_SELF:
        return want == "我方"
    return have in (want, BOTH_SIDES)


def cause_matches(want, have, include_unrestricted):
    if have is None:
        return False
    kind, side = have
    if kind == UNRESTRICTED:
        return include_unrestricted
    if kind != want[0] and want[0] not in CAUSE_COVERS.get(kind, ()):
        return False
    return want[1] is None or side in (None, want[1], BOTH_SIDES)


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
        if side is None:
            if zone in pos.names:
                return True
        elif any((zone, have) in pos.zones for have in (side,) + BROAD_ZONE_SIDES):
            return True
    return False


def _replaced_by(index, card, replaced):
    found = {}
    for target, replacing in index.replacements.get(card, ()):
        if target in replaced:
            found[target] = replacing
    return found


def _unparsed(index, q, found):
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

    def __init__(self, index, block_hits, q):
        self.index = index
        self.block_hits = block_hits
        self.q = q
        self._reachable = _reachable(index, block_hits, q)
        self._candidates = {}

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

    def __init__(self, index, q):
        self.mask = None
        self.this_card = bool(q["this_card"])
        if q["card"] is not None:
            at = index.position.get(q["card"])
            self.mask = 0 if at is None else 1 << at
        elif q["condition"] is not None:
            condition = resolve_names(q["condition"], index.card_names)
            self.mask = index.condition_mask(
                q["condition"], lambda view: eval_condition(condition, view) is True)

    def fits(self, obj):
        if self.this_card:
            return obj.kind == OBJECT_THIS
        return self.mask is None or bool(obj.candidates.mask & self.mask)
