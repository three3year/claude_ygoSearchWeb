"""前提:發動句開頭的狀態條件 → 條件式原子,並把物件的目前位置寫進區塊狀態。

前提與條件段不同:條件段是發生過的動作(「〜された場合」的那個「〜」),前提是狀態
(「このカードが手札に存在する場合」「相手ターンに」),所以在觸發形切分**之前**先剝掉,
否則「〜に存在する場合」會被當成條件段。規則是句型層級的:

- 位置:「Xが<區域>に存在する(場合|状態で|限り|時)、」X 是このカード或任何物件短語。
  「存在する」前可寫表示形式(「表側表示で存在する」),原子帶選填 `face`(表側/裏側)、
  `position`(攻擊/守備),只記有寫的一半。此卡 →
  `位置` 原子並把物件0 在本區塊的目前位置設成該區域(後續段的「從」繼承、不算推得);
  其他物件 → 新建物件(初始位置 = 該區域)加 `存在` 原子。
- 存在:「<區域>にXが存在する(場合|状態で|限り|時)、」→ 新建物件 + `存在` 原子;
  「〜が存在しない場合、」→ 非(存在)。前提裡關於物件的條件就在那個物件上(同一物件,
  後文「そのモンスター」指回它),這就是「併進該物件條件」。
- 遊戲狀態:「相手ターンに」「自分メインフェイズに」「自分・相手のバトルフェイズに」
  「ダメージステップに」→ `遊戲狀態` 原子(回合方 / 階段 / 傷害步驟);只出現在前提。
- 票 10 的存在前提 `{"op": "存在", "object", "in": 容器}`(「めくったカードの中に〜があった」)
  是同一個 op、以 `in` 分辨;它是那個條件段的本體,`split_premise` 把它與句首前提分開。
- 持有素材(m3 票 09):「Xが「Y」をX素材としている(場合|状態で|限り)、」也是 `存在`——物件是 X 的超量素材
  (物件種類 超量素材、所屬 `of` = X、條件式 = Y),原子帶 `held`(素材名詞「X素材」)而沒有區域。
- 段引用:`{"op": "本回合發生過", "segment": 段id}`(「〜したターン、」的條件段,由
  `segment_extract` 建、字面在被引用的段上);`{"op": "段已執行", "segment": 段id}` 只有形狀、尚未抽取。
- 時點「〜したターンの〈階段〉に」(m3 票 11,抽取在 `turn_phase`):`本回合發生過` 帶 `form: "の"`,
  後接階段原子(`form` 另可為「時に」「時」);時點列舉是 `{"op": "或", "form": "及び、", "args": [且(…)…]}`,
  模板只在段裡寫最後一支,前面各支的字面在段外(`timepoint_glue`)。

位置/存在原子的區域照方的來源還原;區域字面不是預設寫法(舊式「フィールド上」,票 11)時
原子另帶 `text`(區域短語原文,不含「に」),模板照它寫。

多個前提依字面順序組成「且」。接縫是 `split_premises(body, state, start)`:回傳
(前提條件式, 前提字面結束偏移, 子句開始偏移);沒有前提回 (None, start, start)。
`render_premise` 是反向檢查的模板,只從原子的格產生日文。
"""
import re

from quantity import (EXISTENCE_COUNT_PATTERN, FULLWIDTH_DIGITS, TO_FULLWIDTH_DIGITS,
                      is_existence_count, parse_existence_count, render_existence_count)
from structure_shape import DISPLAY_WORD, NoTemplate, display_value, display_word, zone
from synonyms import XYZ_MATERIAL_WORDS

GAME_STATE_TURN = "回合方"
GAME_STATE_PHASE = "階段"
GAME_STATE_DAMAGE_STEP = "傷害步驟"
# 階段字面 ↔ 值(長的在前,メインフェイズ１ 不能被 メインフェイズ 先吃掉)。
PHASE_WORDS = (("メインフェイズ１", "主要階段1"), ("メインフェイズ２", "主要階段2"),
               ("メインフェイズ", "主要階段"), ("バトルフェイズ", "戰鬥階段"),
               ("エンドフェイズ", "結束階段"), ("スタンバイフェイズ", "準備階段"),
               ("ドローフェイズ", "抽牌階段"))
SIDE_PREFIX = {"自分": "我方", "相手": "對手", "自分・相手の": "任一方"}
# 遊戲狀態原子的 form(後面的助詞,帶不帶讀點都照原文記)。「時に」「時」只出現在
# 「〜したターンの〈階段〉時(に)」(舊式;`turn_phase`),句首的遊戲狀態前提只認「に」。
GAME_STATE_FORMS = ("に", "に、", "時に", "時に、", "時", "時、")
# 「〜したターンの〈階段〉に」(m3 票 11,`turn_phase`):`本回合發生過` 原子接到階段原子的字面,
# 與時點列舉(或)的連接字。
TURN_OF = "の"
TIMEPOINT_OR_FORMS = ("及び、", "及び")
_PHASE_TEXT = {value: word for word, value in PHASE_WORDS}
_SIDE_TEXT = {value: word for word, value in SIDE_PREFIX.items()}

# 遊戲狀態後面的讀點有寫、沒寫都有(「相手ターンに、」「相手ターンに自分フィールドに」),
# 沒有句型層級的規則可判,所以把「に」或「に、」記進原子的 form,模板照它寫。
_GAME_STATE_RE = re.compile(
    "^(?P<side>自分・相手の|自分|相手)?"
    "(?P<what>ターン|" + "|".join(w for w, _ in PHASE_WORDS) + "|ダメージステップ)"
    "(?P<form>に、?)")
# 位置/存在原子的形式:「限り」是持續的前提(段的期間記持續,
# `KAGIRI`);「時」只在後面接讀點、「に」或句尾時才是前提(「存在する時の」是名詞修飾)。
KAGIRI = "限り"
# 「場合に」「時に」(m3 票 12):前提後面直接接子句(「〜存在しない場合にこのカードは破壊される」);
# 句尾的「に」(「〜場合に発動できる」)與「には」不算形式,留在前提外。
PREMISE_FORMS = ("場合", "状態で", KAGIRI, "時", "場合に", "時に")
_WHEN = "(?:場合|時(?=、|に|$))(?:に(?!は|$))?"
_FORM = f"(?P<form>{_WHEN}|状態で|{KAGIRI})"
# 連用形串接(m3 票 12):「Aが存在し、Bが〜」「Aが存在せず、Bが〜」,後面一定有讀點;字面 → 是不是否定。
# 記在原子的 `form`(「し、」「せず、」),和後面的前提照舊組成且。
CONTINUATIVE_FORMS = {"し": False, "せず": True}
_VERB = (f"存在(?:(?P<verb>する|しない){_FORM}"
         f"|(?P<cont>{'|'.join(CONTINUATIVE_FORMS)})(?=、))")
# 列舉(m3 票 12,讀法見 GLOSSARY「前提」):
# - 「A及びB」「AとB」が存在 = 且:每個物件各一個 存在 原子,前面各個的 `form` 是連接字、沒有動詞;
#   後面各個帶 `joined`(區域只在第一個前面寫一次)。
# - 「〜のいずれか」が存在 = 或:物件本身是列舉(「融合・Lモンスター」的或),原子帶 `any` 記字面。
# - 「〜がそれぞれ存在」= 每種各一(且):同上,原子帶 `each` 記字面。
# - 「〜場合、または〜場合」= 兩個前提的或:`{"op": "或", "form": "または", "args": [前提原子, 前提原子]}`。
ENUM_FORMS = ("及び", "と")
ANY_OF, EACH = "のいずれか", "それぞれ"
PREMISE_OR = "または"
# 沒寫區域的「Xが表側表示で存在する場合」(m3 票 12):預設場上(沒有方),原子帶 `inferred`、
# 物件的目前位置算推得。要寫了表示形式才認(表示形式只有場上的卡有)。
DEFAULT_ZONE = "場上"


def _tail(display_required=False):
    """「存在する」前後:[表示形式で][それぞれ][數量]存在(する|しない)(形式) 或連用形。"""
    return (f"(?:(?P<display>{DISPLAY_WORD})で){'' if display_required else '?'}"
            f"(?P<each>{EACH})?(?P<count>{EXISTENCE_COUNT_PATTERN})?" + _VERB)


# 「Xが<區域>に存在する場合、」:X 不含讀點;區域短語交給 parse_zones 認,認不得就不是前提。
# 物件後的助詞也可以是「は」(「このカードはモンスターゾーンに存在する限り、〜を受けない」):
# 這時 X 也是後面主語省略的子句的主語(`state.subject`),原子帶 `particle`。
_OBJECT_FIRST_RE = re.compile(
    # 「」裡的字與「または」的「は」不是助詞。
    f"^(?P<obj>(?:「[^「」]*」|[^、「」])+?)(?P<any>{ANY_OF})?(?P<particle>が|(?<!また)は)"
    "(?P<zones>[^、]+?)に" + _tail())
# 「<區域>にXが存在する場合、」。
_ZONE_FIRST_RE = re.compile(
    f"^(?P<zones>[^、]+?)に(?P<obj>[^、]+?)(?P<any>{ANY_OF})?が" + _tail())
_NO_ZONE_RE = re.compile(
    "^(?P<obj>(?:「[^「」]*」|[^、「」])+?)(?P<particle>が)" + _tail(display_required=True))
# LP 比較(m3 票 12):「自分のLPが相手より(N以上)少ない/多い(場合|時)」「〜少なく、/多く、」→ 遊戲狀態原子
# `{"op": "遊戲狀態", "state": "LP比較", "value": 少|多, "word": LP 的字面, "form"}`,差距有寫才帶 `margin`。
# 只收和對手比的;和定值比(「自分のLPが１０００以下の場合」)不收。
GAME_STATE_LP = "LP比較"
LP_WORDS = ("LP", "ライフポイント")
LP_STEMS = {"少な": "少", "多": "多"}   # 形容詞語幹 ↔ 值(我方的 LP 比對手少/多)
LP_CONTINUATIVE = "く"
_LP_RE = re.compile(
    f"^自分の(?P<word>{'|'.join(LP_WORDS)})が相手より(?:(?P<margin>[０-９]+)以上)?"
    f"(?P<stem>{'|'.join(LP_STEMS)})(?:い(?P<form>{_WHEN})|(?P<cont>{LP_CONTINUATIVE})(?=、))")
# 持有素材(m3 票 09):「Xが「Y」をX素材としている(場合|状態で|限り)、」→ `存在` 原子,物件是 X 的超量素材、
# 條件是 Y(`{"op": "存在", "object": 超量素材物件, "held": "X素材", "form"}`;所屬 X 在物件的 `of`)。
# 沒有區域(`zones`),以 `held` 分辨。
HELD_AS = "としている"
_HELD_RE = re.compile(
    "^(?P<holder>(?:「[^「」]*」|[^、「」をが])+?)が(?P<material>(?:「[^「」]*」|[^、を「」])+?)を"
    "(?P<word>" + "|".join(XYZ_MATERIAL_WORDS) + ")" + HELD_AS + _FORM)


def parse_game_state(text):
    """開頭的遊戲狀態短語 → (原子, 字面長度);不是就回 (None, 0)。
    「ターンに」一定帶方(回合方沒有「任一方」:那就不是條件)。"""
    m = _GAME_STATE_RE.match(text)
    if not m:
        return None, 0
    side = SIDE_PREFIX.get(m.group("side"))
    what = m.group("what")
    if what == "ターン":
        if side not in ("我方", "對手"):
            return None, 0
        atom = {"op": "遊戲狀態", "state": GAME_STATE_TURN, "value": side}
    elif what == "ダメージステップ":
        if side is not None:
            return None, 0
        atom = {"op": "遊戲狀態", "state": GAME_STATE_DAMAGE_STEP}
    else:
        atom = {"op": "遊戲狀態", "state": GAME_STATE_PHASE,
                "value": dict(PHASE_WORDS)[what], "side": side}
    atom["form"] = m.group("form")
    return atom, m.end()


def parse_lp_compare(text):
    """開頭的 LP 比較 → (遊戲狀態原子, 字面長度);不是就回 (None, 0)。讀點不算在長度內。"""
    m = _LP_RE.match(text)
    if not m:
        return None, 0
    atom = {"op": "遊戲狀態", "state": GAME_STATE_LP, "value": LP_STEMS[m.group("stem")],
            "word": m.group("word")}
    if m.group("margin"):
        atom["margin"] = int(m.group("margin").translate(FULLWIDTH_DIGITS))
    atom["form"] = m.group("form") or m.group("cont")
    return atom, m.end()


def split_premises(body, state, start, parse_zones, zone_literal=lambda phrase: None):
    """發動句主體開頭的前提 → (條件式或 None, 前提字面結束偏移, 子句開始偏移)。
    `state` 是 block_state.BlockState(要寫位置、建物件);`parse_zones` 是區域短語
    的解析函式(「自分の手札・フィールド」→ 區域列表,認不得回 None);`zone_literal` 回傳
    區域短語要不要留原文字面(不是預設寫法時回該短語,否則 None)。
    偏移相對於區塊原文,`start` 是 body 在區塊裡的位置。
    前提一個接一個認(連用形「〜存在し、」後面接下一個前提或子句),依字面順序組成且;
    「〜場合、または〜場合」的兩個存在前提組成或(`_can_alternate`)。"""
    atoms = []
    pos = 0
    text_end = start
    while pos < len(body):
        rest = body[pos:]
        skip = len(PREMISE_OR) if rest.startswith(PREMISE_OR) and _can_alternate(atoms) else 0
        found, length = _parse_atoms(rest[skip:], state, parse_zones, zone_literal,
                                     start + pos + skip)
        if not found or (skip and not _is_alternative(found)):
            break
        if skip:
            previous = atoms.pop()
            earlier = previous["args"] if previous.get("op") == "或" else [previous]
            found = [{"op": "或", "form": PREMISE_OR, "args": earlier + found}]
        atoms.extend(found)
        pos += skip + length
        text_end = start + pos - (1 if body[pos - 1] == "、" else 0)
        if body.startswith("、", pos):
            # 位置/存在原子與 LP 比較後的讀點有寫沒寫都有(「状態で、」「状態で」),記進 form,模板照它寫(票 09)。
            target = atoms[-1]["args"][-1] if skip else atoms[-1]
            target = target["arg"] if target.get("op") == "非" else target
            if target.get("op") in ("位置", "存在") or target.get("state") == GAME_STATE_LP:
                target["form"] += "、"
            pos += 1
    if not atoms:
        return None, start, start
    premise = atoms[0] if len(atoms) == 1 else {"op": "且", "args": atoms}
    return premise, text_end, start + pos


def _parse_atoms(text, state, parse_zones, zone_literal, offset):
    """開頭的一個前提 → (原子列表, 字面長度);列舉「A及びB」是多個原子。不是前提回 ([], 0)。"""
    atom, length = parse_game_state(text)
    if atom is None:
        atom, length = parse_lp_compare(text)
    if atom is not None:
        return [atom], length
    found, length = _parse_existence(text, state, parse_zones, zone_literal, offset)
    if found:
        return found, length
    atom, length = _parse_held(text, state, offset)
    return ([atom] if atom is not None else []), length


def _is_alternative(found):
    """「〜場合、または〜場合」的一邊:單一個帶區域的 存在(或其否定)原子,形式是「場合」。
    位置(此卡)不收:它會改寫此卡的目前位置,放進或裡不成立。"""
    if len(found) != 1:
        return False
    atom = found[0]["arg"] if found[0].get("op") == "非" else found[0]
    return (atom.get("op") == "存在" and "zones" in atom and not atom.get("joined")
            and atom.get("form", "").rstrip("、") == "場合")


def _can_alternate(atoms):
    """已認得的前提後面可不可以接「または〜場合」:最後一個是存在前提(或已經是前提的或),
    它前面只有遊戲狀態——「Aが存在し、Bが存在する場合、またはCが〜」的或管到哪裡判不了,不收。"""
    if not atoms or any(atom.get("op") != "遊戲狀態" for atom in atoms[:-1]):
        return False
    last = atoms[-1]
    if last.get("op") == "或":
        return last.get("form") == PREMISE_OR
    return _is_alternative([last])


def _split_enumeration(state, phrase):
    """物件短語是「A及びB」「AとB」的列舉 → (連接字, 各物件短語);每一截都要是認得全的物件短語
    (`BlockState.parses_cleanly`),不是就回 None(「「X」と名のついたモンスター」的と不是)。"""
    tokens = re.findall("「[^「」]*」|.", phrase)
    for form in ENUM_FORMS:
        parts, current, i = [], "", 0
        while i < len(tokens):
            if "".join(tokens[i:i + len(form)]) == form:
                parts.append(current)
                current, i = "", i + len(form)
            else:
                current += tokens[i]
                i += 1
        parts.append(current)
        if len(parts) > 1 and all(part and state.parses_cleanly(part) for part in parts):
            return form, parts
    return None


def _parse_existence(text, state, parse_zones, zone_literal, offset):
    """開頭的位置/存在前提 → (原子列表, 字面長度);不是就回 ([], 0)。"""
    for pattern, first in ((_OBJECT_FIRST_RE, "物件"), (_ZONE_FIRST_RE, "區域"),
                           (_NO_ZONE_RE, None)):
        m = pattern.match(text)
        if not m:
            continue
        g = m.groupdict()
        negated = g["verb"] == "しない" or CONTINUATIVE_FORMS.get(g["cont"], False)
        topic = g.get("particle") == "は"
        if topic and negated:
            continue
        zones = [zone(DEFAULT_ZONE)] if first is None else parse_zones(g["zones"])
        if zones is None:
            continue
        form = g["form"] or g["cont"]
        enumeration = None
        if first == "區域" and not (negated or g["any"] or g["each"] or g["count"]):
            enumeration = _split_enumeration(state, g["obj"])
        connector, phrases = enumeration or (None, [g["obj"]])
        atoms = []
        for i, phrase in enumerate(phrases):
            last = i == len(phrases) - 1
            atom = _existence_atom(state, phrase, offset, zones, first, negated,
                                   form if last else connector)
            if atom is None or (g["count"] and not _count_object(state, atom, g["count"])):
                break
            if topic:
                atom["particle"] = "は"
                state.subject = atom["object"]
            if g["display"] and last:
                atom.update({k: v for k, v in display_value(g["display"]).items() if v})
            literal = zone_literal(g["zones"]) if first is not None else None
            if literal is not None:
                atom["text"] = literal
            if first is None:
                atom["inferred"] = True
            if g.get("any"):
                atom["any"] = g["any"]
            if g["each"]:
                atom["each"] = g["each"]
            if i:
                atom["joined"] = True
            if not negated:
                _place(state, atom, zones, inferred=first is None)
            atoms.append({"op": "非", "arg": atom} if negated else atom)
        else:
            return atoms, m.end()
    return [], 0


def _existence_atom(state, phrase, offset, zones, first, negated, form):
    """物件短語 → 位置原子(此卡)或存在原子;認不出物件回 None。"""
    if phrase == f"「{state.card['name_ja']}」":
        # 前提裡的本卡卡名是另一張同名卡(「自分フィールド上に「古代の歯車」が表側表示で
        # 存在する時、手札からこのカードを〜」),不是物件0。
        obj_id, ref, _ = state.new_object(phrase, offset, {"kind": "新建"})
    else:
        obj_id, ref, _ = state.object_at(phrase, offset)
    if obj_id is None:
        return None
    if obj_id == state.self_id and not negated:
        atom = {"op": "位置", "object": obj_id, "zones": zones, "form": form}
    else:
        atom = {"op": "存在", "object": obj_id, "zones": zones, "form": form}
        if first is not None:
            atom["order"] = first
    if ref is not None:
        atom["ref"] = ref
    return atom


def _count_object(state, atom, count_text):
    """「存在する」前的數量記進物件的數量格;物件要是這個前提新建的、名詞後沒有另寫數量,否則回 False。"""
    obj = state.find(atom["object"])
    if (atom["op"] != "存在" or "ref" in atom or obj["source"]["kind"] != "新建"
            or obj["count"] is not None):
        return False
    obj["count"] = parse_existence_count(count_text)
    return True


def _place(state, atom, zones, inferred):
    """肯定的位置/存在前提:物件的目前位置就是那個區域;新建物件沒有初始位置時一併寫入
    (預設場上的只記目前位置、算推得)。"""
    obj = state.find(atom["object"])
    if not inferred and obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
        obj["initial_position"] = [dict(z) for z in zones]
    state.positions[atom["object"]] = {"zones": [dict(z) for z in zones], "inferred": inferred}


def _parse_held(text, state, offset):
    """「Xが「Y」をX素材としている場合」→ (存在 原子, 字面長度);不是、或 X、Y 認不出物件就回 (None, 0)。
    超量素材物件由 `state.held_material` 建(所屬 X、條件 Y)。"""
    m = _HELD_RE.match(text)
    if not m:
        return None, 0
    material_id = state.held_material(m.group("holder"), m.group("material"), offset)
    if material_id is None:
        return None, 0
    return {"op": "存在", "object": material_id, "held": m.group("word"),
            "form": m.group("form")}, m.end()


def is_lasting(premise):
    """前提裡有「〜限り」的位置/存在原子:整句的段期間是持續。"""
    if premise is None:
        return False
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    return any((a["arg"] if a.get("op") == "非" else a).get("form", "").startswith(KAGIRI)
               for a in atoms)


def split_premise(premise):
    """段的前提 → (句首前提或 None, 票 10 的存在前提原子或 None)。"""
    if premise is None:
        return None, None
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    inner = [a for a in atoms if a.get("op") == "存在" and "in" in a]
    leading = [a for a in atoms if not (a.get("op") == "存在" and "in" in a)]
    existence = inner[0] if inner else None
    if not leading:
        return None, existence
    return (leading[0] if len(leading) == 1 else {"op": "且", "args": leading}), existence


def render_game_state(atom, last):
    """遊戲狀態原子 → 字面;form 是「に」或「に、」,最後一個原子後面沒有子句時不寫讀點。"""
    state = atom.get("state")
    form = atom.get("form")
    if form not in GAME_STATE_FORMS:
        raise NoTemplate("遊戲狀態形式無模板")
    if last:
        form = form.rstrip("、")
    if state == GAME_STATE_TURN:
        if atom.get("value") not in ("我方", "對手"):
            raise NoTemplate("回合方無模板")
        return _SIDE_TEXT[atom["value"]] + "ターン" + form
    if state == GAME_STATE_DAMAGE_STEP:
        return "ダメージステップ" + form
    if state == GAME_STATE_PHASE:
        word = _PHASE_TEXT.get(atom.get("value"))
        side = atom.get("side")
        if word is None or (side is not None and side not in _SIDE_TEXT):
            raise NoTemplate("階段無模板")
        return (_SIDE_TEXT[side] if side else "") + word + form
    raise NoTemplate(f"遊戲狀態無模板:{state}")


def render_premise(premise, render_zones, render_object, followed=True,
                   count_of=lambda obj_id: None):
    """前提條件式 → 日文。`render_zones(區域列表, 原文字面或 None) → 字面`、
    `render_object(物件id, 回指字面或 None) → 字面`、`count_of(物件id) → 物件的數量格`
    由反向檢查提供(位置與物件的字面規則在那裡,前提只負責排列)。
    位置/存在原子後面接讀點(`、`)——除非它是最後一個且後面沒有子句(`followed`);
    遊戲狀態原子照它的 form(「に」或「に、」)寫,同樣的例外。"""
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    pieces = []
    for i, atom in enumerate(atoms):
        last = i == len(atoms) - 1 and not followed
        op = atom.get("op")
        if op == "遊戲狀態":
            pieces.append(_render_lp(atom, last) if atom.get("state") == GAME_STATE_LP
                          else render_game_state(atom, last))
        elif op == "本回合發生過":
            # 段引用(票 09):字面在被引用的條件段(「〜したターン」)上,這裡不寫;
            # 「〜したターンの〈階段〉に」(m3 票 11)只寫接到階段的「の」。
            if not atom.get("segment"):
                raise NoTemplate("段引用無模板:沒有段 id")
            if atom.get("form") not in (None, TURN_OF):
                raise NoTemplate("段引用形式無模板")
            pieces.append(atom.get("form") or "")
        elif op == "或" and atom.get("form") == PREMISE_OR:
            # 「〜場合、または〜場合」:兩邊各照存在前提寫,中間接「または」。
            args = atom.get("args") or ()
            if len(args) < 2 or not all(_is_alternative([arg]) for arg in args):
                raise NoTemplate("前提的或無模板")
            pieces.append(PREMISE_OR.join(
                _render_existence(arg, None, last and arg is args[-1], render_zones,
                                  render_object, count_of) for arg in args))
        elif op == "或":
            pieces.append(_render_last_timepoint(atom, last))
        else:
            pieces.append(_render_existence(atom, atoms[i - 1] if i else None, last,
                                            render_zones, render_object, count_of))
    return "".join(pieces)


def _render_existence(atom, previous, last, render_zones, render_object, count_of):
    """位置/存在原子(與存在的否定)→ 字面。`previous` 是同一個且裡的前一個原子(列舉「A及びB」的後一個
    要對它);`last` = 後面沒有子句,讀點不寫。"""
    negated = False
    op = atom.get("op")
    if op == "非" and atom.get("arg", {}).get("op") == "存在":
        atom, negated, op = atom["arg"], True, "存在"
    if op not in ("位置", "存在"):
        raise NoTemplate(f"前提原子無模板:{op}")
    form = atom.get("form") or ""
    bare = form.rstrip("、")
    if last:
        form = bare   # 後面沒有子句時讀點不在原文範圍內
    marks = [atom.get(key) for key in ("any", "each", "face", "position", "inferred")]
    if bare in ENUM_FORMS:
        # 列舉「A及びB」前面的各個:[區域に]A及び,沒有動詞。
        if (op != "存在" or negated or atom.get("order") != "區域" or any(marks)
                or atom.get("held") or atom.get("elided")
                or is_existence_count(count_of(atom["object"]))):
            raise NoTemplate("前提的列舉無模板")
        return (_enumeration_lead(atom, previous, render_zones)
                + render_object(atom["object"], atom.get("ref")) + bare)
    if bare in CONTINUATIVE_FORMS:
        # 連用形「存在し、」「存在せず、」:肯定/否定要和字面一致,後面一定有讀點。
        if CONTINUATIVE_FORMS[bare] != negated or form == bare:
            raise NoTemplate("前提形式無模板")
        verb = "存在" + form
    elif bare in PREMISE_FORMS:
        verb = ("存在しない" if negated else "存在する") + form
    else:
        raise NoTemplate("前提形式無模板")
    if atom.get("held"):
        # 持有素材:物件的字面是「Xが「Y」を」(所屬與條件都在超量素材物件上),這裡接素材名詞與形式。
        if negated or atom["held"] not in XYZ_MATERIAL_WORDS or bare in CONTINUATIVE_FORMS:
            raise NoTemplate("持有素材的前提無模板")
        return render_object(atom["object"], None) + atom["held"] + HELD_AS + form
    if atom.get("elided"):
        # 分歧引導句的「存在しない場合」:物件與區域承前省略(segment_tree)。
        if not negated:
            raise NoTemplate("省略的存在前提只能是否定")
        return verb
    if atom.get("any") not in (None, ANY_OF) or atom.get("each") not in (None, EACH):
        raise NoTemplate("前提的列舉無模板")
    obj = render_object(atom["object"], atom.get("ref")) + (atom.get("any") or "")
    lead = ""
    if atom.get("face") or atom.get("position"):
        lead = display_word(atom.get("face"), atom.get("position")) + "で"
    lead += atom.get("each") or ""
    count = count_of(atom["object"])
    if is_existence_count(count):
        lead += render_existence_count(count)
    if atom.get("inferred"):
        # 沒寫區域:要寫了表示形式,區域只能是預設的場上。
        if (atom.get("zones") != [zone(DEFAULT_ZONE)] or not (atom.get("face") or atom.get("position"))
                or atom.get("joined") or atom.get("text") or atom.get("particle", "が") != "が"):
            raise NoTemplate("沒寫區域的前提無模板")
        return f"{obj}が{lead}{verb}"
    if atom.get("joined"):
        if op != "存在" or atom.get("order") != "區域":
            raise NoTemplate("前提的列舉無模板")
        return f"{_enumeration_lead(atom, previous, render_zones)}{obj}が{lead}{verb}"
    zones = render_zones(atom["zones"], atom.get("text"))
    if op == "位置" or atom.get("order") == "物件":
        particle = atom.get("particle", "が")
        if particle not in ("が", "は"):
            raise NoTemplate("前提的助詞無模板")
        return f"{obj}{particle}{zones}に{lead}{verb}"
    return f"{zones}に{obj}が{lead}{verb}"


def _enumeration_lead(atom, previous, render_zones):
    """列舉「<區域>にA及びBが存在する」裡一個物件前面的字面:第一個寫區域,後面的(`joined`)不寫——
    它的區域要和前一個(形式是連接字的存在原子)相同。"""
    if not atom.get("joined"):
        return render_zones(atom["zones"], atom.get("text")) + "に"
    if (previous is None or previous.get("op") != "存在"
            or (previous.get("form") or "") not in ENUM_FORMS
            or previous.get("zones") != atom.get("zones")
            or previous.get("text") != atom.get("text")):
        raise NoTemplate("前提的列舉無模板")
    return ""


def _render_lp(atom, last):
    """LP 比較 → 「自分のLPが相手より(N以上)少ない場合」「〜少なく、」。"""
    stems = {value: stem for stem, value in LP_STEMS.items()}
    form = atom.get("form") or ""
    bare = form.rstrip("、")
    if last:
        form = bare
    if atom.get("value") not in stems or atom.get("word") not in LP_WORDS:
        raise NoTemplate("LP 比較無模板")
    if bare == LP_CONTINUATIVE:
        if form == bare:
            raise NoTemplate("LP 比較形式無模板")
        tail = form
    elif re.fullmatch(_WHEN, bare):
        tail = "い" + form
    else:
        raise NoTemplate("LP 比較形式無模板")
    margin = atom.get("margin")
    if margin is not None and not isinstance(margin, int):
        raise NoTemplate("LP 比較的差距無模板")
    written = "" if margin is None else str(margin).translate(TO_FULLWIDTH_DIGITS) + "以上"
    return f"自分の{atom['word']}が相手より{written}{stems[atom['value']]}{tail}"


def _timepoints(atom):
    """時點列舉的或 → 各支的 (本回合發生過原子, 階段原子);形狀不是時點列舉就丟 NoTemplate。"""
    pairs = []
    for arg in atom.get("args") or ():
        happened, phase = arg.get("args", (None, None)) if arg.get("op") == "且" and len(
            arg.get("args", ())) == 2 else (None, None)
        if (happened is None or happened.get("op") != "本回合發生過" or not happened.get("segment")
                or happened.get("form") != TURN_OF or phase.get("op") != "遊戲狀態"
                or phase.get("state") != GAME_STATE_PHASE):
            raise NoTemplate("前提的或無模板:不是時點列舉")
        pairs.append((happened, phase))
    if len(pairs) < 2 or atom.get("form") not in TIMEPOINT_OR_FORMS:
        raise NoTemplate("前提的或無模板:不是時點列舉")
    return pairs


def _render_last_timepoint(atom, last):
    """時點列舉的或:最後一支的「の〈階段〉に」寫在這一段裡,前面各支的字面在段外(`timepoint_glue`)。"""
    _, phase = _timepoints(atom)[-1]
    return TURN_OF + render_game_state(phase, last)


def timepoint_glue(premise):
    """前提裡時點列舉前面各支的段外字面(「の〈階段〉及び、」,夾在兩個「〜したターン」條件段之間);
    反向檢查從區塊殘留裡扣掉。沒有時點列舉回空列表。"""
    if premise is None:
        return []
    pieces = []
    for atom in premise["args"] if premise.get("op") == "且" else [premise]:
        if atom.get("op") != "或" or atom.get("form") == PREMISE_OR:
            continue
        for _, phase in _timepoints(atom)[:-1]:
            # 助詞只寫在最後一支後:前面各支寫階段字面,不寫 form。
            word = render_game_state(phase, last=True)
            pieces.append(TURN_OF + word[:len(word) - len(phase["form"].rstrip("、"))]
                          + atom["form"])
    return pieces
