"""條件式原子(票 07):記載、卡名範圍、屬性比較(引用)、位置、卡片子類型的抽取與句型模板。

放獨立模組是為了把一個原子的「抽取」與「模板」放在一起:`noun_phrase.parse_modifiers`
認不得修飾語時交給 `parse_modifier`,`noun_phrase` 的原子模板沒模板時交給 `render_atom`;
加一個原子只改這裡。原子的查詢判斷在 `action_query.eval_condition`;狀態原子(不是卡的屬性、
指定卡代入時不看卡片參數的)的代入規則是 `action_query.STATE_ATOMS` 那張表。
和「指誰」有關的原子(他の、召喚方式、只修飾此卡的狀態;m3 票 05)在 `state_atoms`,這裡的 `parse_modifier`、
`render_atom` 先問它。

- 記載(名稱):「X」のカード名が記された → {"op": "記載", "name": 名稱列 id};
  「X」またはそのカード名が記された → 或(卡名∋X, 記載 X)。查詢時掃卡文含「X」(含括號)。
- 卡名範圍:「A」～「B」のいずれかの → {"op": "卡名範圍", "names": [A 的列 id, B 的列 id]};
  端點是「共同前綴 + 數字」,卡名的數字落在兩端之間就符合(No.101～No.107)。
- 位置:EXデッキの、自分フィールドの → {"op": "位置", "zones": [...]};判斷代入時任何卡都算
  (位置不是卡的屬性),泛用物件的定義把它當泛用原子。
- 卡片子類型:「No.」Xモンスター、Sモンスター 的 X/S/L/P/融合/儀式 →
  {"op": "屬性比較", "attr": "卡片子類型", "cmp": "=", "value": "超量"};片假名全寫(リンク、シンクロ、
  エクシーズ)值同字母,另帶 `text` 記字面。
- 屬性比較(引用):種族か属性が見せたモンスターと同じで、→ 或(種族 = 物件.種族, 屬性 = 物件.屬性);
  そのモンスターのランクと同じ数値のレベルを持つ → 等級 = 物件.階級。
  引用 {"object": 物件 id, "attr": 屬性名, "text": 指回的字面};`form` 記句型(同じで / 同じ数值)
  讓模板放回原字面。指回的物件由 `BlockState.resolve_reference` 解。
- 控制方:修飾語開頭的「自分の」「相手の」(自分の「EM」モンスター、相手の表側表示モンスター),
  或緊接頭名詞的「相手」「自分」(相手モンスター)→ {"op": "控制方", "value": 我方|對手, "text": 字面};
  「自分フィールドの」是位置,不在此列。代入時任何卡都算(泛用原子)。
- 此卡以外:「このカード以外の」→ 非(同一張 物件0):{"op": "非", "arg": {"op": "同一張",
  "object": 此卡的物件 id, "text": "このカード"}};代入的是卡而不是那一張實體,任何卡都代得進去
  (同名的另一張也算),但不是泛用原子(泛用物件的定義不變)。
- 位置的非預設區域字面:「エクストラデッキの」= 額外牌組,原子另帶 `text`(區域字面),模板照它寫。
- 以此卡為對象:「このカードを対象とする(Xの)効果」→ {"op": "以此卡為對象", "object": 此卡的
  物件 id, "text": 字面};效果所屬的卡的狀態,代入時任何卡都算、不是泛用原子。
- 位置的區域列舉:「フィールド（表側表示）・墓地の」→ 位置原子多個區域,「（表側表示）」記在
  那個區域的 `face`;原子帶 `text`(區域字面),模板驗過與區域一致後照它寫。
- 回指物件以外:「そのモンスター以外の、」→ 非(同一張 指回的物件),同此卡以外;
  後接讀點時 非 原子帶 `text`(含讀點的整個字面)。
- 被裝備者:緊接頭名詞的「装備」(装備モンスター)、「このカードを装備した」、
  「このカードの効果でこのカードを装備した」→ {"op": "被裝備者", "equip": 裝備卡物件, "text": 字面};
  裝備卡是「このカード」指的物件(內嵌效果裡是綁定的物件)。被裝備是狀態不是卡的屬性:代入時任何卡
  都算,但不是泛用原子(spec 泛用判定不變)。
- m3 票 04:卡片子類型閉集加 効果、デュアル、スピリット、トゥーン、ユニオン、リバース 與魔陷的 永続、速攻、
  フィールド、カウンター,「・」列舉(融合・S・X・L)是或;位置的區域字面取整張 `ZONE_WORDS`(Pゾーン、
  メインモンスターゾーン、除外状態…);表示形式加只寫攻守的 攻撃表示、守備表示;控制方加「自分または相手の」
  (任一方);「特殊召喚された」沒寫出發地就不帶 zones。寫成連體子句的位置與表示形式
  (「除外されている」「〜にセットされた」「〜に表側表示で存在する」)在 `position_atoms`。
"""
import re

import position_atoms
import state_atoms
from structure_shape import DEFAULT_ZONE_WORD, ZONE_WORDS, zone

# 「X」(１体)またはそのカード名が記された:名稱後可帶數量字面(「「ブラック・マジシャン」１体または
# そのカード名が記されたカード１枚」,票 09),記在卡名原子的 count、模板放回。
_MENTION_OR_RE = re.compile(
    "^「(?P<name>[^「」]+)」(?P<count>[０-９]+(?:体|枚))?またはそのカード名が記された")
_MENTION_RE = re.compile("^「(?P<name>[^「」]+)」のカード名が記された")
_RANGE_RE = re.compile("^「(?P<lo>[^「」]+)」～「(?P<hi>[^「」]+)」のいずれかの")
# 名詞修飾的位置(「墓地のモンスター」「EXデッキの「No.」Xモンスター」「Pゾーンの「DD」カード」):字面取自
# 共用的區域字面表(structure_shape.ZONE_WORDS)。這五個區域的預設字面不另記;其餘字面(m3 票 04:
# Pゾーン、魔法＆罠ゾーン、メインモンスターゾーン、除外状態、舊式「フィールド上」…)原子另帶 `text`。
_ZONE_NAMES = ("額外牌組", "牌組", "手牌", "場上", "墓地")
_ZONE_NAME = {DEFAULT_ZONE_WORD[name]: name for name in _ZONE_NAMES}
_NON_DEFAULT_ZONE_WORDS = {word: name for word, name in ZONE_WORDS if word not in _ZONE_NAME}
_POSITION_ZONE_ALT = "|".join(word for word, _ in ZONE_WORDS)   # 長的在前
_ZONE_RE = re.compile(f"^(?P<side>自分|相手)?(?P<zone>{_POSITION_ZONE_ALT})の")
_NOT_SELF_RE = re.compile("^(?P<text>このカード|その(?:モンスター|カード))以外の(?P<pause>、)?")
SELF_TEXT = "このカード"
FACE_UP_NOTE = "（表側表示）"
_ZONE_ITEM = f"(?:{_POSITION_ZONE_ALT})(?:{FACE_UP_NOTE})?"
_ZONE_LIST_RE = re.compile(
    f"^(?P<text>(?P<side>自分|相手)?(?:{_ZONE_ITEM}(?:・{_ZONE_ITEM})+"
    f"|(?:{_POSITION_ZONE_ALT}){FACE_UP_NOTE}))の")
SAME_CARD = state_atoms.SAME_CARD
# 曾被特殊召喚(票 08):「EXデッキから特殊召喚された」→ {"op": "曾被特殊召喚", "zones": [出發地]};
# 查詢時從額外牌組特殊召喚的只有額外牌組的怪獸(融合/同步/超量/連結/靈擺)代得進去,其餘任何卡都算。
# 沒寫出發地(「特殊召喚されたモンスター」,m3 票 04)就不帶 zones。
SUMMONED_TEXT = "特殊召喚された"
_SUMMONED_FROM_RE = re.compile(
    f"^(?:(?P<side>自分|相手)?の?(?P<zone>{_POSITION_ZONE_ALT})から)?{SUMMONED_TEXT}")
SUBTYPE_LETTERS = (("融合", "融合"), ("儀式", "儀式"), ("S", "同步"), ("X", "超量"),
                   ("L", "連結"), ("P", "靈擺"),
                   ("通常", "通常"),   # 「「ホール」通常罠カード」「通常モンスター」
                   # m3 票 04:怪獸的 効果〜リバース,魔陷的 永続〜カウンター(值域同 script/web/vocab.py)。
                   ("効果", "效果"), ("デュアル", "二重"), ("スピリット", "靈魂"),
                   ("トゥーン", "卡通"), ("ユニオン", "聯合"), ("リバース", "反轉"),
                   ("永続", "永續"), ("速攻", "速攻"), ("フィールド", "場地"),
                   ("カウンター", "反擊"))
SUBTYPE_WORDS = (("リンク", "連結"), ("シンクロ", "同步"), ("エクシーズ", "超量"),
                 ("リバース効果", "反轉"))   # 舊式「リバース効果モンスター」
_SUBTYPE = "|".join([word for word, _ in SUBTYPE_WORDS]
                    + [letter for letter, _ in SUBTYPE_LETTERS])
# 字段後的子類型可以是「・」列舉(「「トリックスター」融合・Lモンスター」,m3 票 12):字段 且 或(子類型…)。
_ARCHETYPE_SUBTYPE_RE = re.compile(
    f"^「(?P<name>[^「」]+)」(?P<sub>(?:{_SUBTYPE})(?:・(?:{_SUBTYPE}))*)$")
_SUBTYPE_RE = re.compile(f"^(?P<sub>{_SUBTYPE})$")
# 子類型的「・」列舉(「融合・S・X・Lモンスター」)是或:一張卡符合其中一種就算。
_SUBTYPE_LIST_RE = re.compile(f"^(?:{_SUBTYPE})(?:・(?:{_SUBTYPE}))+$")
# 表示形式(表側、裏側是狀態,不是卡的屬性;spec「區域」;票 06):閉集,值就是字面。
FACE_WORDS = ("表側攻撃表示", "表側守備表示", "裏側守備表示", "表側表示", "裏側表示",
              "攻撃表示", "守備表示")   # 只寫攻守的(「守備表示モンスター」,m3 票 04)
# 後接「の」的(「エクストラデッキの表側表示の「X」モンスター」)原子另帶 text(含「の」)。
_FACE_RE = re.compile("^(?P<face>" + "|".join(FACE_WORDS) + ")(?P<of>の)?")
ATTR_WORDS = (("種族", "種族"), ("属性", "屬性"), ("レベル", "等級"), ("ランク", "階級"))
_ATTR = "|".join(word for word, _ in ATTR_WORDS)
_REF = "(?:見せた|その|それらの)(?:モンスター|カード)"
_SAME_AS_RE = re.compile(
    f"^(?P<attrs>(?:{_ATTR})(?:か(?:{_ATTR}))*)が(?P<ref>{_REF})と同じで、?")
_SAME_VALUE_RE = re.compile(
    f"^(?P<ref>{_REF})の(?P<rattr>{_ATTR})と同じ数値の(?P<attr>{_ATTR})を持つ")
REASON_REF = "指回的物件找不到"

_SIDE = {"自分": "我方", "相手": "對手"}
# 控制方另收「自分または相手の」「自分か相手の」(任一方;m3 票 04),長的先比。
_CONTROLLER_SIDE = {"自分または相手": "任一方", "自分か相手": "任一方", **_SIDE}
_CONTROLLER_RE = re.compile("^(?P<side>" + "|".join(_CONTROLLER_SIDE) + ")(?:の|$)")
EQUIPPED = "被裝備者"
EQUIPPED_FORMS = ("装備", "このカードを装備した", "このカードの効果でこのカードを装備した")
_EQUIPPED_RE = re.compile("^(?:" + "|".join(sorted(EQUIPPED_FORMS, key=len, reverse=True))
                          + ")$")
TARGETING_THIS = "以此卡為對象"
TARGETING_THIS_FORMS = ("このカードを対象とする",)
_TARGETING_THIS_RE = re.compile("^(?:" + "|".join(TARGETING_THIS_FORMS) + ")")
_SIDE_TEXT = {v: k for k, v in _SIDE.items()}
_ZONE_TEXT = {v: k for k, v in _ZONE_NAME.items()}
_ATTR_NAME = dict(ATTR_WORDS)
_ATTR_TEXT = {v: k for k, v in ATTR_WORDS}
_SUBTYPE_NAME = dict(SUBTYPE_LETTERS + SUBTYPE_WORDS)
_SUBTYPE_TEXT = {v: k for k, v in SUBTYPE_LETTERS}


def parse_modifier(rest, state):
    """修飾語開頭認得的原子 → (原子列表, 原因, 吃掉的長度);認不得回 None。
    原子列表為空時表示名稱或引用對不到(原因帶著),呼叫端把那截標解析不出。"""
    pointing = state_atoms.parse_modifier(rest, state)   # 他の、召喚方式…(m3 票 05)
    if pointing is not None:
        return pointing
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
        if not m.group("zone"):
            return [{"op": "曾被特殊召喚"}], None, m.end()
        return [_zone_atom("曾被特殊召喚", m.group("zone"), _SIDE.get(m.group("side")))], None, m.end()
    m = _NOT_SELF_RE.match(rest)
    if m:
        text = m.group("text")
        obj_id = state.self_id if text == SELF_TEXT else state.resolve_reference(text)
        if obj_id is None:
            return [], REASON_REF, m.end()
        atom = {"op": "非", "arg": {"op": SAME_CARD, "object": obj_id, "text": text}}
        if m.group("pause"):
            atom["text"] = m.group()
        return [atom], None, m.end()
    m = _ZONE_LIST_RE.match(rest)
    if m:
        return ([{"op": "位置", "zones": parse_zone_list(m.group("text")),
                  "text": m.group("text")}], None, m.end())
    m = _ZONE_RE.match(rest)
    if m:
        return [_zone_atom("位置", m.group("zone"), _SIDE.get(m.group("side")))], None, m.end()
    m = _CONTROLLER_RE.match(rest)
    if m:
        return ([{"op": "控制方", "value": _CONTROLLER_SIDE[m.group("side")], "text": m.group()}],
                None, m.end())
    m = _TARGETING_THIS_RE.match(rest)
    if m:
        return [targeting_this_atom(state, m.group())], None, m.end()
    m = _EQUIPPED_RE.match(rest)
    if m:
        return ([{"op": EQUIPPED, "equip": state.self_id, "text": m.group()}], None, m.end())
    m = _ARCHETYPE_SUBTYPE_RE.match(rest)
    if m:
        atom, why = state.name_atom("字段", m.group("name"))
        if atom is None:
            return [], why, m.end()
        subtypes = [_subtype_atom(word) for word in m.group("sub").split("・")]
        return ([atom, subtypes[0] if len(subtypes) == 1 else {"op": "或", "args": subtypes}],
                why, m.end())
    m = _SUBTYPE_RE.match(rest)
    if m:
        return [_subtype_atom(m.group("sub"))], None, m.end()
    m = _SUBTYPE_LIST_RE.match(rest)
    if m:
        return ([{"op": "或", "args": [_subtype_atom(word) for word in rest.split("・")]}],
                None, m.end())
    m = _FACE_RE.match(rest)
    if m:
        atom = {"op": "表示形式", "value": m.group("face")}
        if m.group("of"):
            atom["text"] = m.group()
        return [atom], None, m.end()
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
    clause = position_atoms.parse_modifier(rest)
    if clause:
        return clause[0], None, clause[1]
    return None


def _zone_atom(op, word, side):
    """單一區域的原子;不是那五個區域的預設字面就另帶 `text`。"""
    atom = {"op": op, "zones": [zone(_NON_DEFAULT_ZONE_WORDS.get(word) or _ZONE_NAME[word], side)]}
    if word in _NON_DEFAULT_ZONE_WORDS:
        atom["text"] = word
    return atom


def targeting_this_atom(state, text):
    """「このカードを対象とする」→ 以此卡為對象原子。"""
    return {"op": TARGETING_THIS, "object": state.self_id, "text": text}


def parse_zone_list(text):
    """區域列舉字面(「自分フィールド（表側表示）・墓地」)→ 區域列表;「（表側表示）」記在該區域的 face。"""
    m = re.match("^(?P<side>自分|相手)?(?P<rest>.*)$", text)
    side = _SIDE.get(m.group("side"))
    zones = []
    for item in m.group("rest").split("・"):
        word = item.removesuffix(FACE_UP_NOTE)
        name = _NON_DEFAULT_ZONE_WORDS.get(word) or _ZONE_NAME.get(word)
        if name is None:
            return None
        entry = zone(name, side)
        if word != item:
            entry["face"] = "表側"
        zones.append(entry)
    return zones


def _subtype_atom(letter):
    atom = {"op": "屬性比較", "attr": "卡片子類型", "cmp": "=",
            "value": _SUBTYPE_NAME[letter]}
    if letter in dict(SUBTYPE_WORDS):
        atom["text"] = letter
    return atom


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
    名稱列找不到回 None。noun_phrase 的名稱原子模板也用這一支。"""
    name_id = atom_or_id if isinstance(atom_or_id, str) else atom_or_id.get("name")
    row = names.get(name_id)
    return None if row is None else f"「{row['text']}」"


def render_atom(atom, names):
    """原子 → 修飾語字面;這裡沒模板的回 None(呼叫端記「無模板」)。"""
    pointing = state_atoms.render_atom(atom)   # 他の、召喚方式…(m3 票 05)
    if pointing is not None:
        return pointing
    op = atom.get("op")
    clause = position_atoms.render_atom(atom)
    if clause is not None:
        return clause
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
    if op == "位置" and _ZONE_LIST_RE.match((atom.get("text") or "") + "の"):
        zones = [{**zone(z["zone"], z.get("side")), **({"face": z["face"]} if z.get("face") else {})}
                 for z in atom["zones"]]
        return atom["text"] + "の" if parse_zone_list(atom["text"]) == zones else None
    if op in ("位置", "曾被特殊召喚"):
        # 條件式裡的區域不經 load_structures 補格,產物省略的 side 要用 get。
        zones = atom.get("zones")
        if op == "曾被特殊召喚" and zones is None:
            return SUMMONED_TEXT
        if "form" in atom or len(zones) != 1:
            return None
        word = atom.get("text") or _ZONE_TEXT.get(zones[0]["zone"])
        if word is None or _NON_DEFAULT_ZONE_WORDS.get(word, _ZONE_NAME.get(word)) != zones[0]["zone"]:
            return None
        side = zones[0].get("side")
        prefix = (_SIDE_TEXT.get(side, "") if side else "") + word
        return prefix + ("の" if op == "位置" else "から" + SUMMONED_TEXT)
    if op == "表示形式":
        value = atom.get("value")
        if value not in FACE_WORDS or atom.get("text", value) not in (value, value + "の"):
            return None
        return atom.get("text", value)
    if op == "非" and atom.get("arg", {}).get("op") == SAME_CARD:
        text = atom["arg"].get("text")
        if not text or not _NOT_SELF_RE.match(text + "以外の"):
            return None
        literal = atom.get("text") or text + "以外の"
        return literal if literal in (text + "以外の", text + "以外の、") else None
    if op == "控制方":
        m = _CONTROLLER_RE.fullmatch(atom.get("text") or "")
        return atom["text"] if m and _CONTROLLER_SIDE[m.group("side")] == atom.get("value") else None
    if op == TARGETING_THIS:
        ok = atom.get("text") in TARGETING_THIS_FORMS and atom.get("object")
        return atom["text"] if ok else None
    if op == EQUIPPED:
        return atom["text"] if atom.get("text") in EQUIPPED_FORMS and atom.get("equip") else None
    if op == "屬性比較":
        return _render_compare([atom])
    if op == "或" and all(a.get("op") == "屬性比較" for a in atom.get("args", ())):
        return _render_compare(atom["args"])
    return None


def _render_compare(atoms):
    """屬性比較:卡片子類型 = X 寫成字母(多個是「・」列舉);引用的兩種句型照 form 放回。"""
    first = atoms[0]
    if all(a.get("attr") == "卡片子類型" and "ref" not in a for a in atoms):
        words = [_subtype_text(a) for a in atoms]
        return None if None in words else "・".join(words)
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


def _subtype_text(atom):
    if atom.get("cmp") != "=":
        return None
    if "text" in atom:
        return atom["text"] if (atom["text"], atom.get("value")) in SUBTYPE_WORDS else None
    return _SUBTYPE_TEXT.get(atom.get("value"))


def _is_name_or_mention(atom):
    """或(卡名∋X, 記載 X) 且兩個引用同一個名稱列。"""
    args = atom.get("args", [])
    return (len(args) == 2 and args[0].get("op") == "卡名"
            and args[1].get("op") == "記載"
            and args[0].get("name") == args[1].get("name"))
