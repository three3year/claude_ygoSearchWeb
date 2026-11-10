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
- 段引用:`{"op": "本回合發生過", "segment": 段id}`(「〜したターン、」的條件段,由
  `segment_extract` 建、字面在被引用的段上);`{"op": "段已執行", "segment": 段id}` 只有形狀、尚未抽取。

位置/存在原子的區域照方的來源還原;區域字面不是預設寫法(舊式「フィールド上」,票 11)時
原子另帶 `text`(區域短語原文,不含「に」),模板照它寫。

多個前提依字面順序組成「且」。接縫是 `split_premises(body, state, start)`:回傳
(前提條件式, 前提字面結束偏移, 子句開始偏移);沒有前提回 (None, start, start)。
`render_premise` 是反向檢查的模板,只從原子的格產生日文。
"""
import re

from structure_shape import DISPLAY_WORD, NoTemplate, display_value, display_word

GAME_STATE_TURN = "回合方"
GAME_STATE_PHASE = "階段"
GAME_STATE_DAMAGE_STEP = "傷害步驟"
# 階段字面 ↔ 值(長的在前,メインフェイズ１ 不能被 メインフェイズ 先吃掉)。
PHASE_WORDS = (("メインフェイズ１", "主要階段1"), ("メインフェイズ２", "主要階段2"),
               ("メインフェイズ", "主要階段"), ("バトルフェイズ", "戰鬥階段"),
               ("エンドフェイズ", "結束階段"), ("スタンバイフェイズ", "準備階段"),
               ("ドローフェイズ", "抽牌階段"))
SIDE_PREFIX = {"自分": "我方", "相手": "對手", "自分・相手の": "任一方"}
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
PREMISE_FORMS = ("場合", "状態で", KAGIRI, "時")
_FORM = f"(?P<form>場合|状態で|{KAGIRI}|時(?=、|に|$))"
_DISPLAY = f"(?:(?P<display>{DISPLAY_WORD})で)?"
# 「Xが<區域>に存在する場合、」:X 不含讀點;區域短語交給 parse_zones 認,認不得就不是前提。
# 物件後的助詞也可以是「は」(「このカードはモンスターゾーンに存在する限り、〜を受けない」):
# 這時 X 也是後面主語省略的子句的主語(`state.subject`),原子帶 `particle`。
_OBJECT_FIRST_RE = re.compile(
    # 「」裡的字與「または」的「は」不是助詞。
    "^(?P<obj>(?:「[^「」]*」|[^、「」])+?)(?P<particle>が|(?<!また)は)"
    "(?P<zones>[^、]+?)に" + _DISPLAY
    + "存在(?P<neg>し)?(?:する|ない)" + _FORM)
# 「<區域>にXが存在する場合、」。
_ZONE_FIRST_RE = re.compile(
    "^(?P<zones>[^、]+?)に(?P<obj>[^、]+?)が" + _DISPLAY
    + "存在(?P<neg>し)?(?:する|ない)" + _FORM)


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


def split_premises(body, state, start, parse_zones, zone_literal=lambda phrase: None):
    """發動句主體開頭的前提 → (條件式或 None, 前提字面結束偏移, 子句開始偏移)。
    `state` 是 block_state.BlockState(要寫位置、建物件);`parse_zones` 是區域短語
    的解析函式(「自分の手札・フィールド」→ 區域列表,認不得回 None);`zone_literal` 回傳
    區域短語要不要留原文字面(不是預設寫法時回該短語,否則 None)。
    偏移相對於區塊原文,`start` 是 body 在區塊裡的位置。"""
    atoms = []
    pos = 0
    text_end = start
    while pos < len(body):
        rest = body[pos:]
        atom, length = parse_game_state(rest)
        if atom is None:
            atom, length = _parse_existence(rest, state, parse_zones, zone_literal,
                                            start + pos)
        if atom is None:
            break
        atoms.append(atom)
        pos += length
        text_end = start + pos - (1 if body[pos - 1] == "、" else 0)
        if body.startswith("、", pos):
            # 位置/存在原子後的讀點有寫沒寫都有(「状態で、」「状態で」),記進 form,模板照它寫(票 09)。
            target = atom["arg"] if atom.get("op") == "非" else atom
            if target.get("op") in ("位置", "存在"):
                target["form"] += "、"
            pos += 1
    if not atoms:
        return None, start, start
    premise = atoms[0] if len(atoms) == 1 else {"op": "且", "args": atoms}
    return premise, text_end, start + pos


def _parse_existence(text, state, parse_zones, zone_literal, offset):
    for pattern, first in ((_OBJECT_FIRST_RE, "物件"), (_ZONE_FIRST_RE, "區域")):
        m = pattern.match(text)
        if not m:
            continue
        topic = m.groupdict().get("particle") == "は"
        if topic and m.group("neg"):
            continue
        zones = parse_zones(m.group("zones"))
        if zones is None:
            continue
        if m.group("obj") == f"「{state.card['name_ja']}」":
            # 前提裡的本卡卡名是另一張同名卡(「自分フィールド上に「古代の歯車」が表側表示で
            # 存在する時、手札からこのカードを〜」),不是物件0。
            obj_id, ref, _ = state.new_object(m.group("obj"), offset, {"kind": "新建"})
        else:
            obj_id, ref, _ = state.object_at(m.group("obj"), offset)
        if obj_id is None:
            continue
        if obj_id == state.self_id and not m.group("neg"):
            atom = {"op": "位置", "object": obj_id, "zones": zones,
                    "form": m.group("form")}
        else:
            atom = {"op": "存在", "object": obj_id, "zones": zones,
                    "form": m.group("form"), "order": first}
        if topic:
            atom["particle"] = "は"
            state.subject = obj_id
        if m.group("display"):
            atom.update({k: v for k, v in display_value(m.group("display")).items() if v})
        if ref is not None:
            atom["ref"] = ref
        literal = zone_literal(m.group("zones"))
        if literal is not None:
            atom["text"] = literal
        if m.group("neg"):
            atom = {"op": "非", "arg": atom}
        if not m.group("neg"):
            obj = state.find(obj_id)
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = [dict(z) for z in zones]
            state.positions[obj_id] = {"zones": [dict(z) for z in zones],
                                       "inferred": False}
        return atom, m.end()
    return None, 0


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
    if form not in ("に", "に、"):
        raise NoTemplate("遊戲狀態形式無模板")
    if last and form == "に、":
        form = "に"
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


def render_premise(premise, render_zones, render_object, followed=True):
    """前提條件式 → 日文。`render_zones(區域列表, 原文字面或 None) → 字面`、
    `render_object(物件id, 回指字面或 None) → 字面`
    由反向檢查提供(位置與物件的字面規則在那裡,前提只負責排列)。
    位置/存在原子後面接讀點(`、`)——除非它是最後一個且後面沒有子句(`followed`);
    遊戲狀態原子照它的 form(「に」或「に、」)寫,同樣的例外。"""
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    pieces = []
    for i, atom in enumerate(atoms):
        last = i == len(atoms) - 1 and not followed
        op = atom.get("op")
        if op == "遊戲狀態":
            pieces.append(render_game_state(atom, last))
            continue
        if op == "本回合發生過":
            # 段引用(票 09):字面在被引用的條件段(「〜したターン」)上,這裡不寫。
            if not atom.get("segment"):
                raise NoTemplate("段引用無模板:沒有段 id")
            continue
        negated = False
        if op == "非" and atom.get("arg", {}).get("op") == "存在":
            atom, negated, op = atom["arg"], True, "存在"
        if op not in ("位置", "存在"):
            raise NoTemplate(f"前提原子無模板:{op}")
        verb = "存在しない" if negated else "存在する"
        form = atom.get("form") or ""
        if form.rstrip("、") not in PREMISE_FORMS:
            raise NoTemplate("前提形式無模板")
        if last:
            form = form.rstrip("、")   # 後面沒有子句時讀點不在原文範圍內
        if atom.get("elided"):
            # 分歧引導句的「存在しない場合」:物件與區域承前省略(segment_tree)。
            if not negated:
                raise NoTemplate("省略的存在前提只能是否定")
            pieces.append(verb + form)
            continue
        obj = render_object(atom["object"], atom.get("ref"))
        zones = render_zones(atom["zones"], atom.get("text"))
        if atom.get("face") or atom.get("position"):
            verb = display_word(atom.get("face"), atom.get("position")) + "で" + verb
        if op == "位置" or atom.get("order") == "物件":
            particle = atom.get("particle", "が")
            if particle not in ("が", "は"):
                raise NoTemplate("前提的助詞無模板")
            pieces.append(f"{obj}{particle}{zones}に{verb}{form}")
        else:
            pieces.append(f"{zones}に{obj}が{verb}{form}")
    return "".join(pieces)
