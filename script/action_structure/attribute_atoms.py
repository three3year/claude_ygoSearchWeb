"""屬性比較原子:物件修飾語裡的種族、屬性 → `{"op": "屬性比較", "attr", "cmp", "value"}`。

值用卡片總表(cards.json)的位元,鍵名照總表的欄位(`race`、`attribute`);查詢側帶同樣的
原子直接比。字面規則(句型層級):
- 「魔法使い族」「ドラゴン族・鳥獣族」:種族,多個以「・」列舉是「或」。
- 「光属性」「光・闇属性」:屬性,「属性」只寫在最後一個;多個是「或」。
- 種族接屬性以「・」相連是「且」(「魔法使い族・光属性チューナー」),
  且 的 args 照字面順序;反向檢查把相鄰的兩個屬性比較原子以「・」接回。
- 後面接「の」只在下一個修飾語是「」名稱時(「ドラゴン族の「ドラグニティ」モンスター」);
  「闇属性のモンスター」這種寫法會以字面不符列進報告,不另記旗標。
等級(「レベル４以下の」)與引用(等級 = 物件1.階級)留給之後的票,原子形狀相同。
"""
import re

RACE_WORDS = (
    ("戦士族", 0x1), ("魔法使い族", 0x2), ("天使族", 0x4), ("悪魔族", 0x8),
    ("アンデット族", 0x10), ("機械族", 0x20), ("水族", 0x40), ("炎族", 0x80),
    ("岩石族", 0x100), ("鳥獣族", 0x200), ("植物族", 0x400), ("昆虫族", 0x800),
    ("雷族", 0x1000), ("ドラゴン族", 0x2000), ("獣族", 0x4000),
    ("獣戦士族", 0x8000), ("恐竜族", 0x10000), ("魚族", 0x20000),
    ("海竜族", 0x40000), ("爬虫類族", 0x80000), ("サイキック族", 0x100000),
    ("幻神獣族", 0x200000), ("創造神族", 0x400000), ("幻竜族", 0x800000),
    ("サイバース族", 0x1000000), ("幻想魔族", 0x2000000),
)
ATTRIBUTE_WORDS = (
    ("地", 0x1), ("水", 0x2), ("炎", 0x4), ("風", 0x8), ("光", 0x10), ("闇", 0x20),
    ("神", 0x40),
)
_RACE_BY_WORD = dict(RACE_WORDS)
_ATTR_BY_WORD = dict(ATTRIBUTE_WORDS)
_RACE_BY_VALUE = {v: w for w, v in RACE_WORDS}
_ATTR_BY_VALUE = {v: w for w, v in ATTRIBUTE_WORDS}

_race_alt = "|".join(re.escape(w) for w, _ in RACE_WORDS)
_attr_alt = "|".join(re.escape(w) for w, _ in ATTRIBUTE_WORDS)
_RACES_RE = re.compile(f"^(?P<words>(?:{_race_alt})(?:・(?:{_race_alt}))*)(?P<no>の)?")
_ATTRS_RE = re.compile(f"^(?P<words>(?:{_attr_alt})(?:・(?:{_attr_alt}))*)属性(?P<no>の)?")


def _atom(attr, value):
    return {"op": "屬性比較", "attr": attr, "cmp": "=", "value": value}


def _or(atoms):
    return atoms[0] if len(atoms) == 1 else {"op": "或", "args": atoms}


def parse_modifier(text):
    """開頭的種族/屬性修飾語 → (原子, 字面長度);不是就回 (None, 0)。
    前面的「・」(種族接屬性的連接)也一併吃掉。"""
    skip = 1 if text.startswith("・") else 0
    rest = text[skip:]
    m = _RACES_RE.match(rest)
    if m:
        atoms = [_atom("race", _RACE_BY_WORD[w]) for w in m.group("words").split("・")]
        return _or(atoms), skip + m.end()
    m = _ATTRS_RE.match(rest)
    if m:
        atoms = [_atom("attribute", _ATTR_BY_WORD[w])
                 for w in m.group("words").split("・")]
        return _or(atoms), skip + m.end()
    return None, 0


def is_param_atom(atom):
    """這個原子(或它的「或」)是種族/屬性比較。"""
    if atom.get("op") == "或":
        return all(is_param_atom(a) for a in atom["args"])
    return atom.get("op") == "屬性比較" and atom.get("attr") in ("race", "attribute")


def render_modifier(atom):
    """屬性比較原子 → 字面(不含後面的「・」「の」,由呼叫端依下一個原子決定);
    寫不出回 None。"""
    atoms = atom["args"] if atom.get("op") == "或" else [atom]
    attrs = {a.get("attr") for a in atoms}
    if len(attrs) != 1 or any(a.get("cmp") != "=" for a in atoms):
        return None
    attr = attrs.pop()
    table = _RACE_BY_VALUE if attr == "race" else _ATTR_BY_VALUE
    try:
        words = [table[a["value"]] for a in atoms]
    except KeyError:
        return None
    return "・".join(words) + ("" if attr == "race" else "属性")
