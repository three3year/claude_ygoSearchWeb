from typing import NamedTuple

NUMBER, POSITION = "編號", "位置"
SECTION_OF_SOURCE = {"card_text": "main", "pen_effect": "pendulum"}


class _Located(NamedTuple):
    position: int
    index: str
    start: int | None
    end: int | None

    @property
    def number(self):
        return self.index.split("-")[0]

    def holds(self, offset):
        return self.start is not None and self.start <= offset < self.end


class ClauseMap:

    def __init__(self, tag_cards, texts):
        self._clauses = {entry["id"]: entry.get("clauses") or [] for entry in tag_cards}
        self._texts = texts
        self._located = {}

    def of(self, card, place):
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
