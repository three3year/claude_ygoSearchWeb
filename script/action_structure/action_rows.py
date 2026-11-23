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

未結構化的段(重複到停為止)不命中,不出列;解析不出的段、引用節點、被代替段的連結留給票 04。
"""
from typing import NamedTuple

from action_query import _is_doer, is_generic, segment_actions
from candidate_cards import CandidateCards
from structure_shape import iter_segments, zone_names


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
        self.rows = []

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


def flatten(structures, cards):
    """全庫卡片結構 + 卡片總表 → ActionIndex。"""
    index = ActionIndex(cards, structures)
    seq = 0
    for card in structures:
        if card["unparsed"]:
            continue
        objects = {obj["id"]: obj for obj in card["objects"]}
        for block in card["blocks"]:
            for _, seg in iter_segments(block):
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
    return index


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
