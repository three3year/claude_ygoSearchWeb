"""種族、屬性修飾語的「・」列舉:字面 ↔ 屬性比較原子(形狀同票 10:`{"op": "屬性比較",
"attr": 種族|屬性, "cmp": "=", "value": 官方日文字面}`,位元對照在 `attribute_words`)。

字面規則(句型層級):
- 「魔法使い族」「ドラゴン族・鳥獣族」:種族,多個以「・」列舉是「或」(一張卡只有一個種族)。
- 「光属性」「光・闇属性」:屬性,「属性」只寫在最後一個;多個是「或」。
- 種族接屬性以「・」相連是「且」(「魔法使い族・光属性チューナー」),且 的 args 照字面順序。
- 「の」:多個種族的「或」後面接屬性時寫「の」(獣族・獣戦士族の炎属性,官方 14:7);
  屬性比較後面接「」名稱時寫「の」(ドラゴン族の「ドラグニティ」,61:0);接頭名詞不寫
  (属性モンスター 1,431:74)。少數派寫法(「闇属性のモンスター」)以字面不符列進報告,不另記旗標。
等級(レベルN)的單一原子在 `segment_extract.parse_modifier`,這裡只管列舉與「の」。
"""
import re

from attribute_words import ATTRIBUTE_JA, RACE_JA

_race_alt = "|".join(re.escape(w) for w in sorted(RACE_JA, key=len, reverse=True))
_attr_alt = "|".join(re.escape(w) for w in ATTRIBUTE_JA)
_RACES_RE = re.compile(f"^(?P<words>(?:{_race_alt})(?:・(?:{_race_alt}))*)(?P<no>の)?")
_ATTRS_RE = re.compile(f"^(?P<words>(?:{_attr_alt})(?:・(?:{_attr_alt}))*)属性(?P<no>の)?")
# 等級:「レベル１」緊接頭名詞;「レベル４以下の」「レベル５以上の」帶比較與「の」(joiner 照 cmp 寫回)。
_LEVEL_RE = re.compile("^レベル(?P<n>[０-９]+)(?P<cmp>以上|以下)?(?P<no>の)?")
_LEVEL_CMP = {None: "=", "以上": "≥", "以下": "≤"}
_LEVEL_CMP_TEXT = {v: k or "" for k, v in _LEVEL_CMP.items()}
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_TO_FULLWIDTH_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")


def _atom(attr, value):
    return {"op": "屬性比較", "attr": attr, "cmp": "=", "value": value}


def _or(atoms):
    return atoms[0] if len(atoms) == 1 else {"op": "或", "args": atoms}


def parse_modifier(text):
    """開頭的種族/屬性修飾語(含「・」列舉與後面的「の」)→ (原子, 字面長度);
    不是就回 (None, 0)。前面的「・」(種族接屬性的連接)也一併吃掉。"""
    skip = 1 if text.startswith("・") else 0
    rest = text[skip:]
    m = _RACES_RE.match(rest)
    if m:
        atoms = [_atom("種族", w) for w in m.group("words").split("・")]
        return _or(atoms), skip + m.end()
    m = _ATTRS_RE.match(rest)
    if m:
        atoms = [_atom("屬性", w) for w in m.group("words").split("・")]
        return _or(atoms), skip + m.end()
    m = _LEVEL_RE.match(rest)
    if m:
        # 「レベル１の」沒有這種寫法,等級相等時不吃「の」(留給後面的修飾語判)。
        end = m.end() - (1 if m.group("no") and not m.group("cmp") else 0)
        atom = {"op": "屬性比較", "attr": "等級", "cmp": _LEVEL_CMP[m.group("cmp")],
                "value": int(m.group("n").translate(_FULLWIDTH_DIGITS))}
        return atom, skip + end
    return None, 0


def render_level(atom):
    """等級原子 → 「レベル４以下」「レベル１」;不是等級比較回 None。"""
    if atom.get("op") != "屬性比較" or atom.get("attr") != "等級" \
            or atom.get("cmp") not in _LEVEL_CMP_TEXT:
        return None
    digits = str(atom["value"]).translate(_TO_FULLWIDTH_DIGITS)
    return "レベル" + digits + _LEVEL_CMP_TEXT[atom["cmp"]]


def is_param_atom(atom):
    """這個原子(或它的「或」)是帶值的種族/屬性/等級比較(「・」「の」的規則只管這些);
    票 07 的引用(`ref`)與卡片子類型有自己的模板,不算。"""
    if atom.get("op") == "或":
        return all(is_param_atom(a) for a in atom["args"])
    return (atom.get("op") == "屬性比較" and "ref" not in atom
            and atom.get("attr") in ("種族", "屬性", "等級"))


def render_group(atom):
    """「或」的種族/屬性列舉 → 字面(ドラゴン族・鳥獣族、光・闇属性);不是列舉回 None。"""
    if atom.get("op") != "或":
        return None
    attrs = {a.get("attr") for a in atom["args"]}
    if len(attrs) != 1 or any(a.get("cmp") != "=" for a in atom["args"]):
        return None
    attr = attrs.pop()
    if attr == "種族":
        return "・".join(a["value"] for a in atom["args"])
    if attr == "屬性":
        return "・".join(a["value"] for a in atom["args"]) + "属性"
    return None


def joiner(atom, following):
    """屬性比較原子與下一個修飾語之間的字:下一個也是屬性比較 → 「・」(多個種族的「或」後
    → 「の」);下一個是「」名稱等 → 「の」;等級的 以上/以下 後一律「の」。"""
    if atom.get("op") == "屬性比較" and atom.get("attr") == "等級" \
            and atom.get("cmp") in ("≥", "≤"):
        return "の"
    if following is None:
        return ""
    if is_param_atom(following):
        return "の" if atom.get("op") == "或" else "・"
    if following.get("op") == "屬性比較" and following.get("attr") == "卡片子類型":
        # 「ドラゴン族・闇属性Sモンスター」字母緊接,不寫「の」;「サイバース族の儀式モンスター」
        # 「恐竜族の融合モンスター」是整個詞,寫「の」。
        return "の" if following.get("value") in ("融合", "儀式") else ""
    return "の"
