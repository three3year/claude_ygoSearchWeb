"""效果對應:段(或引用節點)在原文裡的位置 → 前端索引的效果句序號(spec「效果對應」)。

效果句的序號是它在前端索引 `tx` 裡的位置,也就是效果標記表裡這張卡的第幾句(前端索引照效果標記表的
順序寫 `tx`);前端索引裡沒有日文,日文原文從效果標記表來。

對法依序:
1. 編號:區塊有①②③編號時,對到同一個來源(主文 / 靈擺效果)裡同編號的效果句。同編號的有好幾句
   (①、①-●1、①-●2 這種 ● 子效果拆開的)時,再看位置落在哪一句。
2. 位置:沒有編號(或編號找不到效果句)時,看位置落在哪個效果句的日文原文裡。效果句的日文原文
   依序在來源原文裡找(忽略空白);找不到的那句不參與。
3. 都對不上就留空。
"""
from typing import NamedTuple

NUMBER, POSITION = "編號", "位置"
SECTION_OF_SOURCE = {"card_text": "main", "pen_effect": "pendulum"}


class _Located(NamedTuple):
    position: int            # 效果句的序號
    index: str               # 效果標記表的編號(①、①-●1、0、1…)
    start: int | None        # 在來源原文裡的範圍;找不到時 None
    end: int | None

    @property
    def number(self):
        return self.index.split("-")[0]

    def holds(self, offset):
        return self.start is not None and self.start <= offset < self.end


class ClauseMap:
    """`tag_cards`:效果標記表的卡;`texts`:{卡: {來源: 原文}}(攤平時拼回的)。"""

    def __init__(self, tag_cards, texts):
        self._clauses = {entry["id"]: entry.get("clauses") or [] for entry in tag_cards}
        self._texts = texts
        self._located = {}

    def of(self, card, place):
        """→ (效果句的序號, 對法);對不上時 (None, None)。"""
        clauses = self._sections(card).get(SECTION_OF_SOURCE.get(place.source), [])
        if place.label:
            same = [c for c in clauses if c.number == place.label]
            if same:
                hit = (_holding(same, place.start)
                       or next((c for c in same if c.index == place.label), same[0]))
                return hit.position, NUMBER
        hit = _holding(clauses, place.start)
        if hit:
            return hit.position, POSITION
        return None, None

    def _sections(self, card):
        if card not in self._located:
            texts = self._texts.get(card, {})
            sections = {}
            for position, clause in enumerate(self._clauses.get(card, [])):
                sections.setdefault(clause["section"], []).append((position, clause))
            source_of = {section: source for source, section in SECTION_OF_SOURCE.items()}
            self._located[card] = {
                section: _locate(entries, texts.get(source_of.get(section), ""))
                for section, entries in sections.items()}
        return self._located[card]


def _holding(clauses, offset):
    return next((c for c in clauses if c.holds(offset)), None)


def _locate(entries, text):
    """效果句依序在原文裡找(忽略空白):先從上一句的結尾往後找,找不到再從頭找。"""
    kept = [i for i, ch in enumerate(text) if not ch.isspace()]
    squeezed = "".join(text[i] for i in kept)
    located, cursor = [], 0
    for position, clause in entries:
        target = "".join(clause.get("text_ja", "").split())
        at = squeezed.find(target, cursor) if target else -1
        if at < 0 and target:
            at = squeezed.find(target)
        if at < 0:
            located.append(_Located(position, clause["index"], None, None))
            continue
        end = at + len(target)
        located.append(_Located(position, clause["index"], kept[at], kept[end - 1] + 1))
        cursor = end
    return located
