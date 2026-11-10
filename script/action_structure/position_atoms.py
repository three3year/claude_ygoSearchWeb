"""連體子句寫的位置與表示形式(m3 票 04):抽取與句型模板成對放在一起。

名詞修飾的位置平常寫「<區域>の」(`condition_atoms`);這裡收寫成連體子句的幾種,用的是同樣的
位置、表示形式原子,只多記句型字面:

- 「<區域>に存在する」(舊式,= <區域>の)→ 位置,`form`「に存在する」。
- 「<區域>に表側表示で存在する」→ 位置(`form`「に」)+ 表示形式(字面「表側表示で存在する」)。
- 「<區域>にセットされた/セットされている」→ 位置(`form`「に」)+ 表示形式 裏側表示(字面「セットされた」)。
- 單獨的「セットされた」「セットされている」→ 表示形式 裏側表示。
- 「除外されている[自分の|相手の|自分または相手の]」「ゲームから除外されている〜」→ 位置 除外,方照寫的;
  `form`「除外されている」,`text` 是整個字面。

位置原子的 `text` 是區域短語(可帶方:「相手フィールド上」「自分の墓地」),模板驗過與 `zones` 一致後照它寫。
"""
import re

from structure_shape import DISPLAY_WORDS, ZONE_WORDS, zone

_SIDE = {"自分": "我方", "相手": "對手", "自分または相手": "任一方", "自分か相手": "任一方"}
_SIDE_ALT = "|".join(sorted(_SIDE, key=len, reverse=True))
_ZONE_NAME = dict(ZONE_WORDS)
_ZONE_ALT = "|".join(word for word, _ in ZONE_WORDS)
_DISPLAY_ALT = "|".join(sorted((word for word, _, _ in DISPLAY_WORDS), key=len, reverse=True))
SET_WORDS = ("セットされた", "セットされている")
_SET_ALT = "|".join(sorted(SET_WORDS, key=len, reverse=True))
FACE_DOWN = "裏側表示"
EXISTS = "で存在する"
FORM_AT, FORM_EXISTS, FORM_BANISHED = "に", "に存在する", "除外されている"
_ZONE_PHRASE_RE = re.compile(
    f"^(?:(?P<side>自分|相手)の?)?(?P<zones>(?:{_ZONE_ALT})(?:・(?:{_ZONE_ALT}))*)$")
_LOCATED_RE = re.compile(
    f"^(?P<phrase>(?:(?:自分|相手)の?)?(?:{_ZONE_ALT})(?:・(?:{_ZONE_ALT}))*)に"
    f"(?:(?P<set>{_SET_ALT})|(?:(?P<display>{_DISPLAY_ALT})で)?存在する)")
_SET_RE = re.compile(f"^(?:{_SET_ALT})")
_BANISHED_RE = re.compile(f"^(?:ゲームから)?除外されている(?:(?P<side>{_SIDE_ALT})の)?")


def _zones(phrase):
    """區域短語 → 區域列表(方寫了就每個區域都帶);不是區域短語回 None。"""
    m = _ZONE_PHRASE_RE.match(phrase)
    if not m:
        return None
    side = _SIDE.get(m.group("side"))
    return [zone(_ZONE_NAME[word], side) for word in m.group("zones").split("・")]


def parse_modifier(rest):
    """修飾語開頭的連體子句 → (原子列表, 吃掉的長度);不是就回 None。"""
    m = _LOCATED_RE.match(rest)
    if m:
        located = {"op": "位置", "zones": _zones(m.group("phrase")), "text": m.group("phrase")}
        if m.group("set"):
            face = {"op": "表示形式", "value": FACE_DOWN, "text": m.group("set")}
        elif m.group("display"):
            face = {"op": "表示形式", "value": m.group("display"),
                    "text": m.group("display") + EXISTS}
        else:
            return [{**located, "form": FORM_EXISTS}], m.end()
        return [{**located, "form": FORM_AT}, face], m.end()
    m = _SET_RE.match(rest)
    if m:
        return [{"op": "表示形式", "value": FACE_DOWN, "text": m.group()}], m.end()
    m = _BANISHED_RE.match(rest)
    if m:
        return [_banished_atom(m)], m.end()
    return None


def _banished_atom(m):
    return {"op": "位置", "zones": [zone("除外", _SIDE.get(m.group("side")))],
            "text": m.group(), "form": FORM_BANISHED}


def render_atom(atom):
    """這裡的原子 → 字面;不是這裡管的(沒有句型字面的位置、一般寫法的表示形式)回 None。"""
    op = atom.get("op")
    text = atom.get("text") or ""
    if op == "位置" and atom.get("form") in (FORM_AT, FORM_EXISTS):
        return text + atom["form"] if _zones(text) == _plain_zones(atom) else None
    if op == "位置" and atom.get("form") == FORM_BANISHED:
        m = _BANISHED_RE.fullmatch(text)
        return text if m and _banished_atom(m)["zones"] == _plain_zones(atom) else None
    if op == "表示形式":
        if text in SET_WORDS:
            return text if atom.get("value") == FACE_DOWN else None
        if text.endswith(EXISTS) and text == str(atom.get("value")) + EXISTS:
            return text if re.fullmatch(_DISPLAY_ALT, atom["value"]) else None
    return None


def _plain_zones(atom):
    """條件式裡的區域不經 load_structures 補格(產物省略空的 side),比對前補回來。"""
    return [zone(z["zone"], z.get("side")) for z in atom.get("zones") or ()]
