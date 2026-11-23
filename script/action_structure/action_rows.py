"""攤平:卡片結構 + 卡片總表 → 完整的列(spec「動作索引」)。

解讀卡片結構的程式只在這裡;比對(`row_match`)只讀攤平出來的列。

列的單位是對象線:每條對象線一列,沒有線的段以段為一列(`line` 為 None)。同一段的列共用 `seq`。
每一欄都是解讀完的值:
- 段的欄:卡、段 id、段序號、所在的(頂層)區塊與區塊種類、段類別、極性、是不是做代替的段、
  動作詞(上位詞已展開)、被改的屬性。
- 線的欄(`Line`):做動作的一方(查詢比的是被動作的卡,這條線不比)、取對象(受方是被取對象的物件的段,
  每條線都算)、從、到(子區域算在上位區域內,推得值另標)、物件。
- 物件(`LineObject`):是不是泛用物件、候選卡。候選卡以對象線為單位(同一個物件在不同線上「從」不同,
  卡名與字段的位置條件就不同),用到才算(`Candidates`),同一份攤平裡算過的不再算。

另外三種列(票 04):
- 未解析組的來源(`Unresolved`):可能進未解析組的段(段解析不出、對象線的物件判不了、所在區塊種類判不出)
  與解析不出的引用節點,帶原文字面含的動作詞、原因、原文。無官方日文的卡另列(`no_text`)。
- 引用節點(`Reference`):引用它的卡與區塊、被引用物件的候選卡、指定的部分、是不是泛用引用。
- 代替的連結(`replacements`):被代替段 → 做代替的段。

未結構化的段(重複到停為止)不命中,不出命中用的列。

同一份輸入(同一個物件)重複查詢時用 `index_of`:攤平與算過的候選卡跨呼叫共用。
"""
import json
from typing import NamedTuple

from action_query import is_generic, same_different_undecidable
from candidate_cards import CandidateCards
from condition_atoms import referenced_objects
from effect_reference import is_reference, iter_references, selected_blocks
from structure_shape import iter_nodes, iter_segments, zone_names
from synonyms import PREDICATE_STEMS, STEM_FALSE_FRIENDS, action_ancestors

# 雙方對等的動作詞:施事線與受事線一樣當被比的物件(`_is_doer`)。
SYMMETRIC_ACTION = "戰鬥"
REASON_REF_MISSING = "引用的物件找不到"
REASON_SAME_DIFFERENT = "異同判不了"


class Position(NamedTuple):
    """從或到:`zones` 是 (區域, 方) 的集合,區域含全部上位區域;`names` 是只看區域時的集合。"""
    zones: frozenset
    names: frozenset
    inferred: bool          # 推得值或繼承自推得值


class Candidates:
    """一條對象線上物件的候選卡:卡片總表位置的位元集(第 i 位 = 總表第 i 張卡),第一次用到才算。"""
    __slots__ = ("_index", "_owner", "_line", "_mask")

    def __init__(self, index, owner, line):
        self._index, self._owner, self._line = index, owner, line
        self._mask = None

    @property
    def mask(self):
        if self._mask is None:
            self._mask = self._index.candidate_mask(self._owner, self._line)
        return self._mask


class LineObject(NamedTuple):
    generic: bool
    candidates: Candidates


class Line(NamedTuple):
    doer: bool
    targeting: bool
    from_: Position | None
    to: Position | None
    object: LineObject | None   # 物件表裡找不到時 None


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
    line: Line | None


class Unresolved(NamedTuple):
    """未解析組的來源:一段,或一個解析不出的引用節點(`segment` 為 None,不看段類別與極性)。"""
    card: int
    block_kind: str
    block_reason: str | None    # 所在區塊種類判不出:區塊被區塊種類篩掉時用這個原因
    segment: str | None
    kind: str | None
    polarity: str | None
    replacing: bool
    reason: str | None          # 不代入卡時的原因
    reason_substituting: str | None   # 代入卡(指定卡、給條件)時的原因
    literal_actions: frozenset  # 原文字面含的動作詞(經同義表,上位詞已展開)
    text: str


class Reference(NamedTuple):
    """解析出的引用節點:`card` 的 `block`(頂層區塊)裡,引用 `candidates` 這些卡的 `effect` 部分。"""
    card: int
    block: str
    generic: bool               # 被引用物件是泛用物件(泛用引用開關開才展開)
    candidates: tuple
    effect: str                 # 指定的部分(效果的 JSON);`ActionIndex.part` 換成被引用卡的區塊


class ActionIndex:
    """攤平的結果:列,加上比對「指定卡」「給條件」要用的卡片總表位置與代入用的卡(CardView)。"""

    def __init__(self, cards, structures):
        self.cards = cards
        self._judge = CandidateCards(cards, structures)
        self.position = {}       # 卡片密碼(含別號)→ 總表位置
        for i, entry in enumerate(cards):
            self.position[entry["id"]] = i
        for i, entry in enumerate(cards):
            for alt in entry.get("alt_ids", ()):
                self.position.setdefault(alt, i)
        self.views = [self._judge.view(entry) for entry in cards]
        self._masks = {}         # id(候選卡清單)→ (清單, 位元集);清單留著,id 才不會被重用
        self._shared = {}        # 位元集 → 同一個位元集(內容相同的共用一份)
        self._condition_masks = {}   # 查詢條件的 JSON → 滿足它的卡的位元集
        self.rows = []
        self.card_order = {}     # 卡片密碼 → 在卡片結構裡的順序(回傳照這個順序)
        self.no_text = []        # 無官方日文的卡:(卡片密碼, 原因)
        self.blocks = {}         # 有結構的卡 → [(頂層區塊 id, 區塊種類)]
        self.unresolved = []
        self.references = {}     # (卡, 頂層區塊 id)→ [Reference]
        self.referencing = set()  # 有解析出的引用節點的卡
        self.replacements = {}   # 卡 → [(被代替段 id, 做代替的段 id)]
        self._structure_by_id = {s["id"]: s for s in structures}
        self._effects = {}       # 效果的 JSON → 效果
        self._parts = {}         # (卡, 效果的 JSON)→ 指定的部分(頂層區塊 id)

    def mask_of(self, positions):
        """總表位置 → 位元集。"""
        bits = bytearray((len(self.cards) + 7) // 8)
        for i in positions:
            bits[i >> 3] |= 1 << (i & 7)
        return int.from_bytes(bits, "little")

    def candidate_mask(self, owner, line):
        found = self._judge.of_line(owner, line)
        if id(found) not in self._masks:
            mask = self.mask_of(self.position[entry["id"]] for entry in found)
            self._masks[id(found)] = (found, self._shared.setdefault(mask, mask))
        return self._masks[id(found)][1]

    def condition_mask(self, condition, fits):
        """滿足查詢條件的卡的位元集;`fits(view)` 判一張卡。同一個條件只算一次。"""
        key = json.dumps(condition, sort_keys=True, ensure_ascii=False)
        if key not in self._condition_masks:
            self._condition_masks[key] = self.mask_of(
                i for i, view in enumerate(self.views) if fits(view))
        return self._condition_masks[key]

    def part(self, card_id, effect):
        """被引用卡上引用節點指定的部分:頂層區塊 id(找不到指定的部分時是整張)。"""
        key = (card_id, effect)
        if key not in self._parts:
            self._parts[key] = tuple(block["id"] for block in selected_blocks(
                self._structure_by_id[card_id], self._effects[effect]))
        return self._parts[key]


_CACHE = []          # [(卡片結構, 卡片總表, ActionIndex)],最近用的在最後
_CACHE_SIZE = 2


def index_of(structures, cards):
    """同一份輸入(同一個物件)的攤平只做一次,候選卡也跨呼叫共用。輸入在兩次呼叫之間不可就地修改。
    快取留著輸入本身,物件 id 才不會被別的輸入重用。"""
    for i, (s, c, index) in enumerate(_CACHE):
        if s is structures and c is cards:
            _CACHE.append(_CACHE.pop(i))
            return index
    index = flatten(structures, cards)
    _CACHE.append((structures, cards, index))
    del _CACHE[:-_CACHE_SIZE]
    return index


def flatten(structures, cards):
    """全庫卡片結構 + 卡片總表 → ActionIndex。"""
    index = ActionIndex(cards, structures)
    seq = 0
    for order, card in enumerate(structures):
        index.card_order[card["id"]] = order
        if card["unparsed"]:
            index.no_text.append((card["id"], card["unparsed"]["reason"]))
            continue
        objects = {obj["id"]: obj for obj in card["objects"]}
        blocks = index.blocks[card["id"]] = []
        for block in card["blocks"]:
            blocks.append((block["id"], block["kind"]))
            block_reason = block["unparsed"]["reason"] if block["unparsed"] else None
            for _, seg in iter_segments(block):
                if seg["replaces"]:
                    index.replacements.setdefault(card["id"], []).append(
                        (seg["replaces"], seg["id"]))
                _add_unresolved_segment(index, card["id"], block["kind"], block_reason, seg,
                                        objects)
                if seg["unparsed"] or seg["unstructured"]:
                    continue
                head = (card["id"], seg["id"], seq, block["id"], block["kind"], seg["kind"],
                        seg["polarity"], bool(seg["replaces"]), frozenset(segment_actions(seg)),
                        seg["modified"])
                seq += 1
                if not seg["lines"]:
                    index.rows.append(Row(*head, None))
                    continue
                recipient_targeted = bool(isinstance(seg["recipient"], dict)
                                          and seg["recipient"].get("targeting"))
                for line in seg["lines"]:
                    index.rows.append(Row(*head, _line(index, card, objects, seg, line,
                                                       recipient_targeted)))
            for reason, text in _unparsed_references(block):
                index.unresolved.append(Unresolved(
                    card["id"], block["kind"], block_reason, None, None, None, False,
                    reason, reason, _literal_actions(text), text))
            for node in iter_references(block):
                if not node.get("unparsed"):
                    index.referencing.add(card["id"])
                    index.references.setdefault((card["id"], block["id"]), []).append(
                        _reference(index, card["id"], block["id"], node))
    return index


def segment_actions(seg):
    """段的動作詞連同上位詞:段寫「融合召喚」,查「特殊召喚」也要對得上。"""
    return {a for action in seg["actions"] for a in action_ancestors(action)}


def _is_doer(line, seg):
    """做動作的主語線(「このカードが戦闘によって相手モンスターを破壊した」的このカード):查詢指定的
    卡、物件條件、從/到比的是被作用的物件,段裡另有受詞時主語不比。戰鬥的雙方對等(「Xが Yと 戦闘を
    行う」),施事照比;只有主語的段(「このカードが相手に戦闘ダメージを与えた」)也照比。"""
    return (line["role"] == "施事" and SYMMETRIC_ACTION not in seg["actions"]
            and any(other["role"] != "施事" for other in seg["lines"]))


def incomplete_reason(seg, objects, substituting=False):
    """段沒命中時,它結構不完整的原因;結構完整(只是不符查詢)回 None。
    先看段自己,再看對象線引用的物件(物件解析不出時指定卡代入判不了);查詢要把卡代入物件
    (`substituting`:指定卡或只給條件)時,數量一張又沒寫比較對象的異同也判不了。"""
    if seg["unparsed"]:
        return seg["unparsed"]["reason"]
    for line in seg["lines"]:
        obj = objects.get(line["object"])
        if obj is None:
            continue
        reason = _object_incomplete_reason(obj, substituting)
        if reason is not None:
            return reason
        # 條件式引用的物件(等級 = 物件1.階級)解析不出,代入也判不了。
        for ref_id in referenced_objects(obj["condition"]):
            ref = objects.get(ref_id)
            if ref is None:
                return REASON_REF_MISSING
            reason = _object_incomplete_reason(ref, substituting)
            if reason is not None:
                return reason
    return None


def _object_incomplete_reason(obj, substituting):
    """物件解析不出,或要代入卡時數量一張又沒寫比較對象的異同:判不了的原因;判得了回 None。"""
    if obj["unparsed"]:
        return obj["unparsed"]["reason"]
    if substituting and same_different_undecidable(obj):
        return REASON_SAME_DIFFERENT
    return None


def _add_unresolved_segment(index, card_id, block_kind, block_reason, seg, objects):
    """段可能進未解析組時記一列:段解析不出、對象線的物件判不了,或所在區塊種類判不出。"""
    reason = incomplete_reason(seg, objects)
    reason_substituting = incomplete_reason(seg, objects, substituting=True)
    if not (block_reason or reason or reason_substituting):
        return
    index.unresolved.append(Unresolved(
        card_id, block_kind, block_reason, seg["id"], seg["kind"], seg["polarity"],
        bool(seg["replaces"]), reason, reason_substituting, _literal_actions(seg["text"]),
        seg["text"]))


def _unparsed_references(block):
    """區塊(含內嵌效果的區塊、分歧各支)裡解析不出的引用節點:(原因, 原文);原文相對於節點所在的區塊。"""
    for node in iter_nodes(block["tree"]["items"]):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from _unparsed_references(node["block"])
        if is_reference(node) and node.get("unparsed"):
            start, end = node["span"]
            yield node["unparsed"]["reason"], block["text"][start:end]


def _reference(index, card_id, block_id, node):
    effect = json.dumps(node["reference"]["effect"], sort_keys=True, ensure_ascii=False)
    index._effects.setdefault(effect, node["reference"]["effect"])
    return Reference(card_id, block_id, bool(node.get("any")),
                     tuple(node["reference"]["candidates"]), effect)


def _literal_actions(text):
    """原文字面含的動作詞:字面含某個述語字面,那個述語的動作詞連同上位詞都算(查「特殊召喚」
    的字面也含「融合召喚」)。"""
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
                    candidates=Candidates(index, card, line)))


def _position(pos):
    if pos is None:
        return None
    pairs = frozenset((name, have["side"]) for have in pos["zones"]
                      for name in zone_names(have["zone"]))
    return Position(zones=pairs, names=frozenset(name for name, _ in pairs),
                    inferred=bool(pos["inferred"]))
