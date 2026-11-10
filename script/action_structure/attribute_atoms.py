"""種族、屬性修飾語的「・」列舉:字面 ↔ 屬性比較原子(形狀同票 10:`{"op": "屬性比較",
"attr": 種族|屬性, "cmp": "=", "value": 官方日文字面}`,位元對照在 `attribute_words`)。

字面規則(句型層級):
- 「魔法使い族」「ドラゴン族・鳥獣族」:種族,多個以「・」列舉是「或」(一張卡只有一個種族)。
- 「光属性」「光・闇属性」:屬性,「属性」只寫在最後一個;多個是「或」。
- 種族接屬性以「・」相連是「且」(「魔法使い族・光属性チューナー」),且 的 args 照字面順序。
- 「の」:多個種族的「或」後面接屬性時寫「の」(獣族・獣戦士族の炎属性,官方 14:7);
  屬性比較後面接「」名稱時寫「の」(ドラゴン族の「ドラグニティ」,61:0);接頭名詞不寫
  (属性モンスター 1,431:74)。少數派寫法(「闇属性のモンスター」)以字面不符列進報告,不另記旗標。
數值屬性(レベルN、ランクN、リンクN、攻撃力N、守備力N,可帶 以上/以下)也在這裡。
"""
import re

from attribute_words import ATTRIBUTE_JA, RACE_JA

_race_alt = "|".join(re.escape(w) for w in sorted(RACE_JA, key=len, reverse=True))
_attr_alt = "|".join(re.escape(w) for w in ATTRIBUTE_JA)
_RACES_RE = re.compile(f"^(?P<words>(?:{_race_alt})(?:・(?:{_race_alt}))*)(?P<no>の)?")
_ATTRS_RE = re.compile(f"^(?P<words>(?:{_attr_alt})(?:・(?:{_attr_alt}))*)属性(?P<no>の)?")
# 數值屬性(m3 票 04 加 階級、連結值、攻擊力、守備力):「レベル１」「ランク４の」「攻撃力１５００以下の」
# 「リンク３以上の」,帶比較與「の」(joiner 照 cmp 寫回)。
NUMBER_WORDS = (("レベル", "等級"), ("ランク", "階級"), ("リンク", "連結值"),
                ("攻撃力", "攻擊力"), ("守備力", "守備力"))
_NUMBER_ATTR = dict(NUMBER_WORDS)
_NUMBER_TEXT = {attr: word for word, attr in NUMBER_WORDS}
NUMBER_ATTRS = tuple(_NUMBER_TEXT)
# 一張怪獸只有等級、階級、連結值其中一種,所以這三種的「・」列舉(「レベル７・８」
# 「レベル２・ランク２・リンク２」)是或;後面的數字沒寫屬性就沿用前一個。攻守不在此列。
_SCALE_WORDS = "レベル|ランク|リンク"
SCALE_ATTRS = ("等級", "階級", "連結值")
_NUMBER_RE = re.compile(
    "^(?P<word>" + "|".join(word for word, _ in NUMBER_WORDS) + ")(?P<n>[０-９]+)"
    f"(?P<more>(?:・(?:{_SCALE_WORDS})?[０-９]+)+)?(?P<cmp>以上|以下)?(?P<no>の)?")
_MORE_RE = re.compile(f"・(?P<word>{_SCALE_WORDS})?(?P<n>[０-９]+)")
_LEVEL_CMP = {None: "=", "以上": "≥", "以下": "≤"}
_LEVEL_CMP_TEXT = {v: k or "" for k, v in _LEVEL_CMP.items()}
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_TO_FULLWIDTH_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")


def _atom(attr, value):
    return {"op": "屬性比較", "attr": attr, "cmp": "=", "value": value}


def _or(atoms):
    return atoms[0] if len(atoms) == 1 else {"op": "或", "args": atoms}


EXCEPT = "以外の"
# 屬性比較之間的連接字:「・」;攻守並列寫「／」(「攻撃力８００／守備力１０００のモンスター」,且)。
SEPARATORS = ("・", "／")


def parse_modifier(text):
    """開頭的種族/屬性修飾語(含「・」列舉與後面的「の」)→ (原子, 字面長度);
    不是就回 (None, 0)。前面的「・」(種族接屬性的連接)也一併吃掉。
    後接「以外の」(水属性以外のモンスター)→ 非(原子)。"""
    skip = 1 if text.startswith(SEPARATORS) else 0
    rest = text[skip:]
    for pattern, attr in ((_RACES_RE, "種族"), (_ATTRS_RE, "屬性")):
        m = pattern.match(rest)
        if not m:
            continue
        atom = _or([_atom(attr, w) for w in m.group("words").split("・")])
        if not m.group("no") and rest.startswith(EXCEPT, m.end()):
            return {"op": "非", "arg": atom}, skip + m.end() + len(EXCEPT)
        return atom, skip + m.end()
    m = _NUMBER_RE.match(rest)
    if m:
        atom = _number_atom(m)
        if atom is not None:
            return atom, skip + m.end()
    return None, 0


def _number_atom(m):
    """數值屬性的比對 → 原子;「・」列舉是或(只收等級、階級、連結值,而且不帶 以上/以下)。"""
    attr = _NUMBER_ATTR[m.group("word")]
    cmp = _LEVEL_CMP[m.group("cmp")]

    def compare(attr, digits):
        return {"op": "屬性比較", "attr": attr, "cmp": cmp,
                "value": int(digits.translate(_FULLWIDTH_DIGITS))}

    atoms = [compare(attr, m.group("n"))]
    if not m.group("more"):
        return atoms[0]
    if attr not in SCALE_ATTRS or m.group("cmp"):
        return None
    for more in _MORE_RE.finditer(m.group("more")):
        attr = _NUMBER_ATTR[more.group("word")] if more.group("word") else attr
        atoms.append(compare(attr, more.group("n")))
    return {"op": "或", "args": atoms}


def render_number(atom):
    """數值屬性的原子 → 「レベル４以下」「レベル１」「攻撃力１５００以下」;不是就回 None。"""
    if atom.get("op") != "屬性比較" or atom.get("attr") not in _NUMBER_TEXT \
            or "ref" in atom or atom.get("cmp") not in _LEVEL_CMP_TEXT:
        return None
    digits = str(atom["value"]).translate(_TO_FULLWIDTH_DIGITS)
    return _NUMBER_TEXT[atom["attr"]] + digits + _LEVEL_CMP_TEXT[atom["cmp"]]


def is_param_atom(atom):
    """這個原子(或它的「或」)是帶值的種族/屬性/數值屬性比較(「・」「の」的規則只管這些);
    票 07 的引用(`ref`)與卡片子類型有自己的模板,不算。"""
    if atom.get("op") == "或":
        return all(is_param_atom(a) for a in atom["args"])
    return (atom.get("op") == "屬性比較" and "ref" not in atom
            and atom.get("attr") in ("種族", "屬性") + NUMBER_ATTRS)


def render_group(atom):
    """「或」的種族/屬性/等級列舉 → 字面(ドラゴン族・鳥獣族、光・闇属性、レベル７・８);不是列舉回 None。"""
    if atom.get("op") != "或":
        return None
    scales = render_scales(atom)
    if scales is not None:
        return scales
    attrs = {a.get("attr") for a in atom["args"]}
    if len(attrs) != 1 or any(a.get("cmp") != "=" for a in atom["args"]):
        return None
    attr = attrs.pop()
    if attr == "種族":
        return "・".join(a["value"] for a in atom["args"])
    if attr == "屬性":
        return "・".join(a["value"] for a in atom["args"]) + "属性"
    return None


def render_scales(atom):
    """等級、階級、連結值的「・」列舉 → 「レベル７・８」「レベル２・ランク２・リンク２」
    (與前一個同屬性的不重寫屬性);不是這種或回 None。"""
    if atom.get("op") != "或" or any(
            a.get("op") != "屬性比較" or a.get("attr") not in SCALE_ATTRS or a.get("cmp") != "="
            or "ref" in a for a in atom["args"]):
        return None
    pieces, previous = [], None
    for a in atom["args"]:
        digits = str(a["value"]).translate(_TO_FULLWIDTH_DIGITS)
        pieces.append(digits if a["attr"] == previous else _NUMBER_TEXT[a["attr"]] + digits)
        previous = a["attr"]
    return "・".join(pieces)


def joiner(atom, following):
    """屬性比較原子與下一個修飾語之間的字:下一個也是屬性比較 → 「・」(多個種族的「或」後
    → 「の」);下一個是「」名稱等 → 「の」;數值屬性的 以上/以下 後一律「の」。"""
    if atom.get("op") == "屬性比較" and atom.get("attr") in NUMBER_ATTRS \
            and atom.get("cmp") in ("≥", "≤"):
        return "の"
    if following is None:
        return ""
    if is_param_atom(following):
        return "の" if atom.get("op") == "或" else "・"
    if following.get("op") == "屬性比較" and following.get("attr") == "卡片子類型":
        # 「ドラゴン族・闇属性Sモンスター」字母緊接,不寫「の」;「サイバース族の儀式モンスター」
        # 「恐竜族の融合モンスター」是整個詞,寫「の」。
        # 「ドラゴン族の通常モンスター」同;但「レベル４通常モンスター」緊接(官方 11:3)。
        if following.get("value") == "通常":
            return "" if atom.get("attr") == "等級" else "の"
        return "の" if following.get("value") in ("融合", "儀式") else ""
    return "の"
