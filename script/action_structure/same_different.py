"""異同原子:「與某物件的某屬性相同/不同」的抽取與句型模板成對放在一起。

`condition_atoms.parse_modifier` 最後問這裡的 `parse_modifier`,`condition_atoms.render_atom` 問這裡的
`render_atom`;查詢判斷在 `action_query.same_different_fits`。

原子:{"op": "異同", "attrs": [屬性名…], "cmp": "="|"≠", "text": 字面},另帶(有才寫):
- `original`:寫了「元々の」。
- `kinds`:屬性是 種類 時括號裡列的種類(「種類（モンスター・魔法・罠）」→ 怪獸、魔法、陷阱)。
- `ref`:比較對象是別的物件 {"object": 物件 id, "text": 指它的字面};沒有 `ref` 的比較對象是同一個物件群裡的
  其他成員(「カード名が異なるカード３枚」「同名モンスター×２」)。同一串修飾語裡前面的異同原子寫了比較對象、
  這一個沒寫時,比的是同一個物件(「そのモンスターとはカード名が異なり、攻撃力が同じ〜」的攻撃力):
  {"object": 物件 id, "elided": True}(`link_elided`)。
屬性寫了好幾個(「種族・属性が同じ」「種族と属性が異なる」)是每一個都相同/每一個都不同。

字面(`_read`,抽取與模板共用;開頭的「Xと」「Xとは」是比較對象):
- [Xと(は)][元々の]〈屬性〉が 異なる|同じ、[元々の]〈屬性〉の異なる;「異なり、」是連用形(句子不在這個讀點切,
  `clause_join.NOT_CONTINUATIVE`),「同じで(、)」後面接下一個條件。
- [Xと]同じ〈屬性〉の、〜を持つ、〜で。
- [元々の]〈屬性〉が Xと同じ。
- 同名、同名の、Xと同名の、Xの同名、その同名(その = 最近提過的那一張)。
比較對象只收指得到既有物件的字面(此卡、その〜、対象の〜、動作回指),不建新物件;指不到的標「指回的物件找不到」。
"""
import re
from typing import NamedTuple

from structure_shape import REASON_REF

SAME_DIFFERENT = "異同"
SAME, DIFFERENT = "=", "≠"
NAME_ATTR, KIND_ATTR = "卡名", "種類"
ATTR_WORDS = (("カード名", NAME_ATTR), ("種族", "種族"), ("属性", "屬性"), ("レベル", "等級"),
              ("ランク", "階級"), ("攻撃力", "攻擊力"), ("守備力", "守備力"),
              ("リンクマーカーの数", "連結值"))
# 「種類（モンスター・魔法・罠）」「種類（儀式・融合・S・X）」:括號裡列的是大類或卡片子類型。
KIND_WORD = "種類"
KIND_WORDS = (("モンスター", "怪獸"), ("魔法", "魔法"), ("罠", "陷阱"), ("儀式", "儀式"),
              ("融合", "融合"), ("S", "同步"), ("X", "超量"), ("P", "靈擺"), ("L", "連結"),
              ("リンク", "連結"))
SELF_TEXT = "このカード"
# 「その同名カード」的「その」:最近提過的那一張(任何大類)。
THAT, THAT_CARD = "その", "そのカード"
_ATTR_NAME = dict(ATTR_WORDS)
_KIND_NAME = dict(KIND_WORDS)
_KIND_ALT = "|".join(word for word, _ in KIND_WORDS)
_KINDS = f"{KIND_WORD}（(?:{_KIND_ALT})(?:・(?:{_KIND_ALT}))+）"
_ATTR = "|".join([word for word, _ in ATTR_WORDS] + [_KINDS])
_ATTRS = f"(?:{_ATTR})(?:(?:・|と)(?:{_ATTR}))*"
_ATTR_RE = re.compile(_ATTR)
# 比較對象的字面:此卡,或以頭名詞收尾的短語(その〜、対象の〜、リリースした〜);不跨讀點、「」與助詞,
# 也不跨「及び」(「X及びXと同じ属性を持つモンスター」是兩個物件的聯集,一個條件式表達不了)。
_REF = f"(?P<ref>{SELF_TEXT}|(?:(?!及び)[^、「」をがはと])+?(?:モンスター|カード))"
_ORIGINAL = "(?P<original>元々の)?"
# 同名、Xと同名の、Xの同名、その同名。
_SAME_NAME_RE = re.compile(f"^(?:{_REF}(?:と|の)|(?P<that>{THAT}))?同名の?")
# [Xと]同じ〈屬性〉の/を持つ/で。
_SAME_AHEAD_RE = re.compile(
    f"^(?:{_REF}と)?同じ{_ORIGINAL}(?P<attrs>{_ATTRS})(?:の|を持つ、?|で、?)")
# 〈屬性〉が Xと同じ。
_SAME_AS_RE = re.compile(f"^{_ORIGINAL}(?P<attrs>{_ATTRS})が{_REF}と同じ(?:で、?)?")
# [Xと(は)]〈屬性〉が 異なる|異なり|同じ、〈屬性〉の異なる。
_COMPARE_RE = re.compile(
    f"^(?:{_REF}とは?)?{_ORIGINAL}(?P<attrs>{_ATTRS})"
    "(?:が(?P<word>異なる|異なり、?|同じ(?:で、?)?)|の(?P<of_word>異なる))")
_CLAUSE_SUBJECT_RE = re.compile("(?:カード|モンスター)が")
# 「Xと〜」的「と」後面接的是比較(不是「AとB」兩個物件):物件短語不在這個「と」切。
_COMPARISON_AHEAD_RE = re.compile(
    f"と(?:同名|同じ(?:元々の)?(?:{_ATTR})|は?(?:元々の)?(?:{_ATTRS})(?:が(?:異な|同じ)|の異なる))")


class _Reading(NamedTuple):
    """一截異同字面拆出的格。"""
    ref: str | None        # 寫出來的比較對象字面;沒寫是 None
    original: bool
    attrs: tuple
    kinds: tuple | None
    cmp: str
    length: int


def _attrs(words):
    """屬性字面(「種族・属性」「種類（儀式・融合・S・X）」)→ (屬性名…, 種類的括號內容或 None)。"""
    attrs, kinds = [], None
    for word in _ATTR_RE.findall(words):
        if word.startswith(KIND_WORD):
            attrs.append(KIND_ATTR)
            kinds = tuple(_KIND_NAME[kind] for kind in word[len(KIND_WORD) + 1:-1].split("・"))
        else:
            attrs.append(_ATTR_NAME[word])
    return tuple(attrs), kinds


def _read(text):
    """修飾語開頭的異同字面 → `_Reading`;不是回 None。後面緊接「カードが」「モンスターが」的
    (「同名カードが自分フィールドに存在しない「R.B.」モンスター」)是連體子句裡的主語,不是這個名詞的修飾語。"""
    reading = _read_literal(text)
    if reading is not None and _CLAUSE_SUBJECT_RE.match(text, reading.length):
        return None
    return reading


def _read_literal(text):
    m = _SAME_NAME_RE.match(text)
    if m:
        return _Reading(m.group("ref") or m.group("that"), False, (NAME_ATTR,), None, SAME, m.end())
    m = _SAME_AHEAD_RE.match(text) or _SAME_AS_RE.match(text)
    if m:
        attrs, kinds = _attrs(m.group("attrs"))
        return _Reading(m.group("ref"), bool(m.group("original")), attrs, kinds, SAME, m.end())
    m = _COMPARE_RE.match(text)
    if m:
        attrs, kinds = _attrs(m.group("attrs"))
        differs = bool(m.group("of_word")) or m.group("word").startswith("異な")
        return _Reading(m.group("ref"), bool(m.group("original")), attrs, kinds,
                        DIFFERENT if differs else SAME, m.end())
    return None


def compares_after(phrase, index):
    """`phrase[index]` 的「と」後面接的是比較(「そのモンスターとはカード名が異なる〜」「Xと同名の〜」)。"""
    return bool(_COMPARISON_AHEAD_RE.match(phrase, index))


def _atom(reading, text):
    atom = {"op": SAME_DIFFERENT, "attrs": list(reading.attrs), "cmp": reading.cmp, "text": text}
    if reading.original:
        atom["original"] = True
    if reading.kinds:
        atom["kinds"] = list(reading.kinds)
    return atom


def parse_modifier(rest, state):
    """修飾語開頭的異同字面 → (原子列表, 原因, 吃掉的長度);不是回 None。比較對象指不到既有物件時
    原子列表是空的、原因是「指回的物件找不到」。"""
    reading = _read(rest)
    if reading is None:
        return None
    atom = _atom(reading, rest[:reading.length])
    if reading.ref is not None:
        if reading.ref == SELF_TEXT:
            obj_id = state.self_id
        else:
            obj_id = state.resolve_reference(THAT_CARD if reading.ref == THAT else reading.ref)
        if obj_id is None:
            return [], REASON_REF, reading.length
        atom["ref"] = {"object": obj_id, "text": reading.ref}
    return [atom], None, reading.length


def link_elided(atoms):
    """同一串修飾語裡,沒寫比較對象的異同原子接在寫了的後面時,比的是同一個物件(就地補 `ref`)。"""
    compared = None
    for atom in atoms:
        if atom.get("op") != SAME_DIFFERENT:
            continue
        if "ref" in atom:
            compared = atom["ref"]["object"]
        elif compared is not None:
            atom["ref"] = {"object": compared, "elided": True}


def elided_backed(atoms):
    """省略的比較對象都接得上前面寫出來的那一個(模板據此才寫得回)。"""
    written = None
    for atom in atoms:
        ref = atom.get("ref") if atom.get("op") == SAME_DIFFERENT else None
        if ref is None:
            continue
        if not ref.get("elided"):
            written = ref.get("object")
        elif ref.get("object") != written:
            return False
    return True


def render_atom(atom):
    """異同原子 → 修飾語字面;不是異同原子、或字面照抽取規則拆不回同一個原子回 None。"""
    if atom.get("op") != SAME_DIFFERENT:
        return None
    text = atom.get("text") or ""
    reading = _read(text)
    if reading is None or reading.length != len(text):
        return None
    ref = atom.get("ref")
    written = None if ref is None or ref.get("elided") else ref.get("text")
    if written != reading.ref or (ref is not None and written is None and not ref.get("elided")):
        return None
    return text if _atom(reading, text) == {k: v for k, v in atom.items() if k != "ref"} else None
