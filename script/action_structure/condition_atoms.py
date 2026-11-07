"""條件式原子(票 07):記載、卡名範圍、屬性比較(引用)、位置、卡片子類型的抽取與句型模板。

放獨立模組是為了把一個原子的「抽取」與「模板」放在一起:`segment_extract.parse_modifiers`
認不得修飾語時交給 `parse_modifier`,`reverse_check._render_atom` 沒模板時交給 `render_atom`;
加一個原子只改這裡。原子的查詢判斷在 `action_query.eval_condition`。

- 記載(名稱):「X」のカード名が記された → {"op": "記載", "name": 名稱列 id};
  「X」またはそのカード名が記された → 或(卡名∋X, 記載 X)。查詢時掃卡文含「X」(含括號)。
- 卡名範圍:「A」～「B」のいずれかの → {"op": "卡名範圍", "names": [A 的列 id, B 的列 id]};
  端點是「共同前綴 + 數字」,卡名的數字落在兩端之間就符合(No.101～No.107)。
- 位置:EXデッキの、自分フィールドの → {"op": "位置", "zones": [...]};判斷代入時任何卡都算
  (位置不是卡的屬性),泛用物件的定義把它當泛用原子。
- 卡片子類型:「No.」Xモンスター、Sモンスター 的 X/S/L/P/融合/儀式 →
  {"op": "屬性比較", "attr": "卡片子類型", "cmp": "=", "value": "超量"}。
- 屬性比較(引用):種族か属性が見せたモンスターと同じで、→ 或(種族 = 物件.種族, 屬性 = 物件.屬性);
  そのモンスターのランクと同じ数値のレベルを持つ → 等級 = 物件.階級。
  引用 {"object": 物件 id, "attr": 屬性名, "text": 指回的字面};`form` 記句型(同じで / 同じ数值)
  讓模板放回原字面。指回的物件由 `BlockState.resolve_reference` 解。
"""
import re

from structure_shape import DEFAULT_ZONE_WORD, zone

# 「X」(１体)またはそのカード名が記された:名稱後可帶數量字面(「「ブラック・マジシャン」１体または
# そのカード名が記されたカード１枚」,票 09),記在卡名原子的 count、模板放回。
_MENTION_OR_RE = re.compile(
    "^「(?P<name>[^「」]+)」(?P<count>[０-９]+(?:体|枚))?またはそのカード名が記された")
_MENTION_RE = re.compile("^「(?P<name>[^「」]+)」のカード名が記された")
_RANGE_RE = re.compile("^「(?P<lo>[^「」]+)」～「(?P<hi>[^「」]+)」のいずれかの")
# 名詞修飾的位置只認這五個區域的預設字面(「墓地のモンスター」「EXデッキの「No.」Xモンスター」);
# 字面取自共用的區域字面表(structure_shape.ZONE_WORDS),子區域(デッキの上)與舊式「フィールド上」不在此列。
_ZONE_NAMES = ("額外牌組", "牌組", "手牌", "場上", "墓地")
_ZONE_NAME = {DEFAULT_ZONE_WORD[name]: name for name in _ZONE_NAMES}
_ZONE_ALT = "|".join(_ZONE_NAME)
_ZONE_RE = re.compile(f"^(?P<side>自分|相手)?(?P<zone>{_ZONE_ALT})の")
# 曾被特殊召喚(票 08):「EXデッキから特殊召喚された」→ {"op": "曾被特殊召喚", "zones": [出發地]};
# 查詢時從額外牌組特殊召喚的只有額外牌組的怪獸(融合/同步/超量/連結/靈擺)代得進去,其餘任何卡都算。
_SUMMONED_FROM_RE = re.compile(
    f"^(?P<side>自分|相手)?の?(?P<zone>{_ZONE_ALT})から特殊召喚された")
SUBTYPE_LETTERS = (("融合", "融合"), ("儀式", "儀式"), ("S", "同步"), ("X", "超量"),
                   ("L", "連結"), ("P", "靈擺"))
_SUBTYPE = "|".join(letter for letter, _ in SUBTYPE_LETTERS)
_ARCHETYPE_SUBTYPE_RE = re.compile(f"^「(?P<name>[^「」]+)」(?P<sub>{_SUBTYPE})$")
_SUBTYPE_RE = re.compile(f"^(?P<sub>{_SUBTYPE})$")
# 表示形式(表側、裏側是狀態,不是卡的屬性;spec「區域」;票 06):閉集,值就是字面。
FACE_WORDS = ("表側攻撃表示", "表側守備表示", "裏側守備表示", "表側表示", "裏側表示")
_FACE_RE = re.compile("^(?P<face>" + "|".join(FACE_WORDS) + ")")
ATTR_WORDS = (("種族", "種族"), ("属性", "屬性"), ("レベル", "等級"), ("ランク", "階級"))
_ATTR = "|".join(word for word, _ in ATTR_WORDS)
_REF = "(?:見せた|その|それらの)(?:モンスター|カード)"
_SAME_AS_RE = re.compile(
    f"^(?P<attrs>(?:{_ATTR})(?:か(?:{_ATTR}))*)が(?P<ref>{_REF})と同じで、?")
_SAME_VALUE_RE = re.compile(
    f"^(?P<ref>{_REF})の(?P<rattr>{_ATTR})と同じ数値の(?P<attr>{_ATTR})を持つ")
REASON_REF = "指回的物件找不到"

_SIDE = {"自分": "我方", "相手": "對手"}
_SIDE_TEXT = {v: k for k, v in _SIDE.items()}
_ZONE_TEXT = {v: k for k, v in _ZONE_NAME.items()}
_ATTR_NAME = dict(ATTR_WORDS)
_ATTR_TEXT = {v: k for k, v in ATTR_WORDS}
_SUBTYPE_NAME = dict(SUBTYPE_LETTERS)
_SUBTYPE_TEXT = {v: k for k, v in SUBTYPE_LETTERS}


def parse_modifier(rest, state):
    """修飾語開頭認得的原子 → (原子列表, 原因, 吃掉的長度);認不得回 None。
    原子列表為空時表示名稱或引用對不到(原因帶著),呼叫端把那截標解析不出。"""
    m = _MENTION_OR_RE.match(rest)
    if m:
        named, why = state.name_atom("卡名", m.group("name"))
        mention, _ = state.name_atom("記載", m.group("name"))
        if named and m.group("count"):
            named["count"] = m.group("count")
        atoms = [{"op": "或", "args": [named, mention]}] if named else []
        return atoms, why, m.end()
    m = _MENTION_RE.match(rest)
    if m:
        atom, why = state.name_atom("記載", m.group("name"))
        return ([atom] if atom else []), why, m.end()
    m = _RANGE_RE.match(rest)
    if m:
        lo, why_lo = state.name_atom("卡名", m.group("lo"))
        hi, why_hi = state.name_atom("卡名", m.group("hi"))
        if lo is None or hi is None:
            return [], why_lo or why_hi, m.end()
        return ([{"op": "卡名範圍", "names": [lo["name"], hi["name"]]}],
                why_lo or why_hi, m.end())
    m = _SUMMONED_FROM_RE.match(rest)
    if m:
        side = _SIDE.get(m.group("side"))
        return ([{"op": "曾被特殊召喚",
                  "zones": [zone(_ZONE_NAME[m.group("zone")], side)]}], None, m.end())
    m = _ZONE_RE.match(rest)
    if m:
        side = _SIDE.get(m.group("side"))
        return ([{"op": "位置", "zones": [zone(_ZONE_NAME[m.group("zone")], side)]}],
                None, m.end())
    m = _ARCHETYPE_SUBTYPE_RE.match(rest)
    if m:
        atom, why = state.name_atom("字段", m.group("name"))
        if atom is None:
            return [], why, m.end()
        return [atom, _subtype_atom(m.group("sub"))], why, m.end()
    m = _SUBTYPE_RE.match(rest)
    if m:
        return [_subtype_atom(m.group("sub"))], None, m.end()
    m = _FACE_RE.match(rest)
    if m:
        return [{"op": "表示形式", "value": m.group("face")}], None, m.end()
    m = _SAME_AS_RE.match(rest)
    if m:
        obj_id = state.resolve_reference(m.group("ref"))
        if obj_id is None:
            return [], REASON_REF, m.end()
        atoms = [_compare(_ATTR_NAME[word], obj_id, _ATTR_NAME[word], m.group("ref"),
                          "同じで")
                 for word in m.group("attrs").split("か")]
        return [atoms[0] if len(atoms) == 1 else {"op": "或", "args": atoms}], None, m.end()
    m = _SAME_VALUE_RE.match(rest)
    if m:
        obj_id = state.resolve_reference(m.group("ref"))
        if obj_id is None:
            return [], REASON_REF, m.end()
        return [_compare(_ATTR_NAME[m.group("attr")], obj_id,
                         _ATTR_NAME[m.group("rattr")], m.group("ref"), "同じ数値")], None, m.end()
    return None


def _subtype_atom(letter):
    return {"op": "屬性比較", "attr": "卡片子類型", "cmp": "=",
            "value": _SUBTYPE_NAME[letter]}


def _compare(attr, obj_id, ref_attr, ref_text, form):
    return {"op": "屬性比較", "attr": attr, "cmp": "=",
            "ref": {"object": obj_id, "attr": ref_attr, "text": ref_text},
            "form": form}


def referenced_objects(condition):
    """條件式裡引用到的物件 id(屬性比較的 ref),查詢判斷據此找被引用物件的候選卡。"""
    found = []
    stack = [condition]
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        ref = node.get("ref")
        if ref and ref["object"] not in found:
            found.append(ref["object"])
        stack.extend(node.get("args", ()))
        if "arg" in node:
            stack.append(node["arg"])
    return found


def quoted_name(atom_or_id, names):
    """名稱原子(或名稱列 id)→ 「X」:只從名稱表取字面(查詢側才會直接帶 text,結構裡不會);
    名稱列找不到回 None。reverse_check 的名稱原子模板也用這一支。"""
    name_id = atom_or_id if isinstance(atom_or_id, str) else atom_or_id.get("name")
    row = names.get(name_id)
    return None if row is None else f"「{row['text']}」"


def render_atom(atom, names):
    """原子 → 修飾語字面;這裡沒模板的回 None(呼叫端記「無模板」)。"""
    op = atom.get("op")
    if op == "記載":
        quoted = quoted_name(atom, names)
        return None if quoted is None else quoted + "のカード名が記された"
    if op == "或" and _is_name_or_mention(atom):
        quoted = quoted_name(atom["args"][0], names)
        count = atom["args"][0].get("count") or ""
        if quoted is None or not re.fullmatch("(?:[０-９]+(?:体|枚))?", count):
            return None
        return quoted + count + "またはそのカード名が記された"
    if op == "卡名範圍":
        lo, hi = (quoted_name(n, names) for n in atom["names"])
        return None if lo is None or hi is None else f"{lo}～{hi}のいずれかの"
    if op in ("位置", "曾被特殊召喚"):
        # 條件式裡的區域不經 load_structures 補格,產物省略的 side 要用 get。
        zones = atom["zones"]
        if len(zones) != 1 or zones[0]["zone"] not in _ZONE_TEXT:
            return None
        side = zones[0].get("side")
        prefix = (_SIDE_TEXT.get(side, "") if side else "") + _ZONE_TEXT[zones[0]["zone"]]
        return prefix + ("の" if op == "位置" else "から特殊召喚された")
    if op == "表示形式":
        return atom.get("value") if atom.get("value") in FACE_WORDS else None
    if op == "屬性比較":
        return _render_compare([atom])
    if op == "或" and all(a.get("op") == "屬性比較" for a in atom.get("args", ())):
        return _render_compare(atom["args"])
    return None


def _render_compare(atoms):
    """屬性比較:卡片子類型 = X 寫成字母;引用的兩種句型照 form 放回。"""
    first = atoms[0]
    if first.get("attr") == "卡片子類型" and len(atoms) == 1:
        return _SUBTYPE_TEXT.get(first.get("value"))
    ref = first.get("ref")
    if ref is None or any(a.get("ref", {}).get("text") != ref["text"]
                          or a.get("form") != first.get("form") for a in atoms):
        return None
    if first.get("form") == "同じで":
        if any(a["attr"] != a["ref"]["attr"] for a in atoms):
            return None
        return "か".join(_ATTR_TEXT[a["attr"]] for a in atoms) + "が" + ref["text"] + "と同じで、"
    if first.get("form") == "同じ数値" and len(atoms) == 1:
        return (ref["text"] + "の" + _ATTR_TEXT[ref["attr"]] + "と同じ数値の"
                + _ATTR_TEXT[first["attr"]] + "を持つ")
    return None


def _is_name_or_mention(atom):
    """或(卡名∋X, 記載 X) 且兩個引用同一個名稱列。"""
    args = atom.get("args", [])
    return (len(args) == 2 and args[0].get("op") == "卡名"
            and args[1].get("op") == "記載"
            and args[0].get("name") == args[1].get("name"))
