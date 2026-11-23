import json
from typing import NamedTuple

from candidate_cards import CandidateCards
from condition_judge import (OBJECT_CANDIDATES, OBJECT_UNDECIDABLE, is_generic, object_kind,
                             same_different_undecidable)
from condition_atoms import referenced_objects
from effect_reference import is_reference, iter_reference_sites, selected_blocks
from structure_shape import iter_nodes, iter_segments, zone_names
from synonyms import PREDICATE_STEMS, STEM_FALSE_FRIENDS, action_ancestors

SYMMETRIC_ACTION = "戰鬥"
REASON_REF_MISSING = "引用的物件找不到"
REASON_SAME_DIFFERENT = "異同判不了"
IMPLIED_SELF = "算我方"
UNRESTRICTED = "不限定"
IMPLIED_SELF_KINDS = ("效果", "代價", "召喚手續")
PASSIVE = "被動"


class Position(NamedTuple):
    zones: frozenset
    names: frozenset
    inferred: bool


class Candidates:
    __slots__ = ("_index", "_owner", "_line", "_mask")

    def __init__(self, index, owner, line):
        self._index, self._owner, self._line = index, owner, line
        self._mask = None

    def resolve(self):
        if self._mask is None:
            self._mask = self._index.candidate_mask(self._owner, self._line)
        return self._mask

    mask = property(resolve)


class LineObject(NamedTuple):
    generic: bool
    candidates: Candidates
    kind: str = OBJECT_CANDIDATES


class Line(NamedTuple):
    doer: bool
    targeting: bool
    from_: Position | None
    to: Position | None
    object: LineObject | None


class Place(NamedTuple):
    source: str
    label: str | None
    start: int


class Row(NamedTuple):
    card: int
    segment: str
    seq: int
    block: str
    block_kind: str
    kind: str
    polarity: str
    replacing: bool
    actions: frozenset
    modified: dict | None
    place: Place
    line: Line | None
    agent: str
    recipient: str | None
    cause: tuple | None


class Unresolved(NamedTuple):
    card: int
    block_kind: str
    block_reason: str | None
    segment: str | None
    kind: str | None
    polarity: str | None
    replacing: bool
    reason: str | None
    reason_substituting: str | None
    literal_actions: frozenset
    text: str


class Reference(NamedTuple):
    card: int
    block: str
    generic: bool
    candidates: tuple
    effect: str
    place: Place


class ActionIndex:

    def __init__(self, cards, structures):
        self.cards = cards
        self._candidates = CandidateCards(cards, structures)
        self.position = {}
        for i, entry in enumerate(cards):
            self.position[entry["id"]] = i
        for i, entry in enumerate(cards):
            for alt in entry.get("alt_ids", ()):
                self.position.setdefault(alt, i)
        self.views = [self._candidates.view(entry) for entry in cards]
        self._masks = {}         # 清單留著,id 才不會被重用
        self._shared = {}
        self._condition_masks = {}
        self.rows = []
        self.card_order = {}
        self.no_text = []
        self.blocks = {}
        self.texts = {}
        self.unresolved = []
        self.references = {}
        self.referencing = set()
        self.replacements = {}
        self._structure_by_id = {s["id"]: s for s in structures}
        self._effects = {}
        self._parts = {}

    def mask_of(self, positions):
        bits = bytearray((len(self.cards) + 7) // 8)
        for i in positions:
            bits[i >> 3] |= 1 << (i & 7)
        return int.from_bytes(bits, "little")

    def candidate_mask(self, owner, line):
        found = self._candidates.of_line(owner, line)
        if id(found) not in self._masks:
            mask = self.mask_of(self.position[entry["id"]] for entry in found)
            self._masks[id(found)] = (found, self._shared.setdefault(mask, mask))
        return self._masks[id(found)][1]

    def resolve_candidates(self):
        """每條有物件的線先求好候選卡:建置要量這一段的時間,查詢則等第一次比到才求。"""
        for row in self.rows:
            if row.line is not None and row.line.object is not None:
                row.line.object.candidates.resolve()

    def condition_mask(self, condition, fits):
        key = json.dumps(condition, sort_keys=True, ensure_ascii=False)
        if key not in self._condition_masks:
            self._condition_masks[key] = self.mask_of(
                i for i, view in enumerate(self.views) if fits(view))
        return self._condition_masks[key]

    def part(self, card_id, effect):
        key = (card_id, effect)
        if key not in self._parts:
            self._parts[key] = tuple(block["id"] for block in selected_blocks(
                self._structure_by_id[card_id], self._effects[effect]))
        return self._parts[key]


_CACHE = []
_CACHE_SIZE = 2


def index_of(structures, cards):
    for i, (s, c, index) in enumerate(_CACHE):
        if s is structures and c is cards:
            _CACHE.append(_CACHE.pop(i))
            return index
    index = flatten(structures, cards)
    _CACHE.append((structures, cards, index))
    del _CACHE[:-_CACHE_SIZE]
    return index


def flatten(structures, cards):
    index = ActionIndex(cards, structures)
    seq = 0
    for order, card in enumerate(structures):
        index.card_order[card["id"]] = order
        if card["unparsed"]:
            index.no_text.append((card["id"], card["unparsed"]["reason"]))
            continue
        objects = {obj["id"]: obj for obj in card["objects"]}
        segments = {seg["id"]: seg for block in card["blocks"] for _, seg in iter_segments(block)}
        blocks = index.blocks[card["id"]] = []
        index.texts[card["id"]] = _source_texts(card)
        for block in card["blocks"]:
            blocks.append((block["id"], block["kind"]))
            block_reason = block["unparsed"]["reason"] if block["unparsed"] else None
            for inner, seg in iter_segments(block):
                if seg["replaces"]:
                    index.replacements.setdefault(card["id"], []).append(
                        (seg["replaces"], seg["id"]))
                _add_unresolved_segment(index, card["id"], block["kind"], block_reason, seg,
                                        objects)
                if seg["unparsed"] or seg["unstructured"]:
                    continue
                head = (card["id"], seg["id"], seq, block["id"], block["kind"], seg["kind"],
                        seg["polarity"], bool(seg["replaces"]), frozenset(segment_actions(seg)),
                        seg["modified"], _place(block, inner, seg["span"][0]))
                seq += 1
                tail = (agent_of(seg, segments), recipient_of(seg), cause_of(seg))
                if not seg["lines"]:
                    index.rows.append(Row(*head, None, *tail))
                    continue
                recipient_targeted = bool(isinstance(seg["recipient"], dict)
                                          and seg["recipient"].get("targeting"))
                for line in seg["lines"]:
                    index.rows.append(Row(*head, _line(index, card, objects, seg, line,
                                                       recipient_targeted), *tail))
            for reason, text in _unparsed_references(block):
                index.unresolved.append(Unresolved(
                    card["id"], block["kind"], block_reason, None, None, None, False,
                    reason, reason, _literal_actions(text), text))
            for inner, node in iter_reference_sites(block):
                if not node.get("unparsed"):
                    index.referencing.add(card["id"])
                    index.references.setdefault((card["id"], block["id"]), []).append(
                        _reference(index, card["id"], block["id"], node,
                                   _place(block, inner, node["span"][0])))
    return index


def _place(block, inner, offset):
    return Place(block["source"], block["label"], inner["span"][0] + offset)


def _source_texts(card):
    pieces = {}
    for part in [*card["blocks"], *card["omitted"]]:
        pieces.setdefault(part["source"], []).append(part)
    texts = {}
    for source, parts in pieces.items():
        chars = [" "] * max(part["span"][1] for part in parts)
        for part in parts:
            start = part["span"][0]
            chars[start:start + len(part["text"])] = part["text"]
        texts[source] = "".join(chars)
    return texts


def segment_actions(seg):
    return {a for action in seg["actions"] for a in action_ancestors(action)}


def agent_of(seg, segments):
    agent = seg["agent"]
    if isinstance(agent, dict):
        if "ref" in agent:
            referred = segments.get(agent["segment"])
            if referred is not None:
                return agent_of(referred, segments)
            agent = None
        else:
            agent = agent["side"]
    if agent is not None:
        return agent
    if seg["kind"] in IMPLIED_SELF_KINDS and seg["voice"] != "被動":
        return IMPLIED_SELF
    return UNRESTRICTED


def recipient_of(seg):
    recipient = seg["recipient"]
    if isinstance(recipient, dict):
        return recipient.get("side")
    return recipient


def cause_of(seg):
    cause = seg["cause"]
    if cause is not None:
        return cause["kind"], cause.get("side")
    if seg["voice"] == PASSIVE:
        return UNRESTRICTED, None
    return None


def _is_doer(line, seg):
    return (line["role"] == "施事" and SYMMETRIC_ACTION not in seg["actions"]
            and any(other["role"] != "施事" for other in seg["lines"]))


def incomplete_reason(seg, objects, substituting=False):
    if seg["unparsed"]:
        return seg["unparsed"]["reason"]
    for line in seg["lines"]:
        obj = objects.get(line["object"])
        if obj is None:
            continue
        reason = _object_incomplete_reason(obj, substituting)
        if reason is not None:
            return reason
        for ref_id in referenced_objects(obj["condition"]):
            ref = objects.get(ref_id)
            if ref is None:
                return REASON_REF_MISSING
            reason = _object_incomplete_reason(ref, substituting)
            if reason is not None:
                return reason
    return None


def _object_incomplete_reason(obj, substituting):
    if obj["unparsed"]:
        return obj["unparsed"]["reason"]
    if substituting and same_different_undecidable(obj):
        return REASON_SAME_DIFFERENT
    return None


def _add_unresolved_segment(index, card_id, block_kind, block_reason, seg, objects):
    reason = incomplete_reason(seg, objects)
    reason_substituting = incomplete_reason(seg, objects, substituting=True)
    if not (block_reason or reason or reason_substituting):
        return
    index.unresolved.append(Unresolved(
        card_id, block_kind, block_reason, seg["id"], seg["kind"], seg["polarity"],
        bool(seg["replaces"]), reason, reason_substituting, _literal_actions(seg["text"]),
        seg["text"]))


def _unparsed_references(block):
    for node in iter_nodes(block["tree"]["items"]):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from _unparsed_references(node["block"])
        if is_reference(node) and node.get("unparsed"):
            start, end = node["span"]
            yield node["unparsed"]["reason"], block["text"][start:end]


def _reference(index, card_id, block_id, node, place):
    effect = json.dumps(node["reference"]["effect"], sort_keys=True, ensure_ascii=False)
    index._effects.setdefault(effect, node["reference"]["effect"])
    return Reference(card_id, block_id, bool(node.get("any")),
                     tuple(node["reference"]["candidates"]), effect, place)


def _literal_actions(text):
    found = set()
    for stem, action, _ in PREDICATE_STEMS:
        if _has_stem(stem, text):
            found.update(action_ancestors(action))
    return frozenset(found)


def _has_stem(stem, text):
    for word in STEM_FALSE_FRIENDS.get(stem, ()):
        text = text.replace(word, "")
    return stem in text


def _line(index, card, objects, seg, line, recipient_targeted):
    obj = objects.get(line["object"])
    return Line(doer=_is_doer(line, seg),
                targeting=bool(line["targeting"]) or recipient_targeted,
                from_=_position(line["from"]), to=_position(line["to"]),
                object=None if obj is None else LineObject(
                    generic=is_generic(obj, objects),
                    candidates=Candidates(index, card, line),
                    kind=line_object_kind(obj, objects)))


def line_object_kind(obj, objects):
    kind = object_kind(obj, objects)
    if kind != OBJECT_CANDIDATES:
        return kind
    for ref_id in referenced_objects(obj["condition"]):
        ref = objects.get(ref_id)
        if ref is None or _object_incomplete_reason(ref, substituting=True) is not None:
            return OBJECT_UNDECIDABLE
    return OBJECT_CANDIDATES


def _position(pos):
    if pos is None:
        return None
    pairs = frozenset((name, have["side"]) for have in pos["zones"]
                      for name in zone_names(have["zone"]))
    return Position(zones=pairs, names=frozenset(name for name, _ in pairs),
                    inferred=bool(pos["inferred"]))
