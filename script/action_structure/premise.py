"""前提:發動句開頭的狀態條件 → 條件式原子,並把物件的目前位置寫進區塊狀態。

前提與條件段不同:條件段是發生過的動作(「〜された場合」的那個「〜」),前提是狀態
(「このカードが手札に存在する場合」「相手ターンに」),所以在觸發形切分**之前**先剝掉,
否則「〜に存在する場合」會被當成條件段。規則是句型層級的:

- 位置:「Xが<區域>に存在する(場合|状態で)、」X 是このカード或任何物件短語。此卡 →
  `位置` 原子並把物件0 在本區塊的目前位置設成該區域(後續段的「從」繼承、不算推得);
  其他物件 → 新建物件(初始位置 = 該區域)加 `存在` 原子。
- 存在:「<區域>にXが存在する(場合|状態で)、」→ 新建物件 + `存在` 原子;
  「〜が存在しない場合、」→ 非(存在)。前提裡關於物件的條件就在那個物件上(同一物件,
  後文「そのモンスター」指回它),這就是「併進該物件條件」。
- 遊戲狀態:「相手ターンに」「自分メインフェイズに」「自分・相手のバトルフェイズに」
  「ダメージステップに」→ `遊戲狀態` 原子(回合方 / 階段 / 傷害步驟);只出現在前提。
- 票 10 的存在前提 `{"op": "存在", "object", "in": 容器}`(「めくったカードの中に〜があった」)
  是同一個 op、以 `in` 分辨;它是那個條件段的本體,`split_premise` 把它與句首前提分開。
- 段引用(形狀,尚未抽取):`{"op": "段已執行", "segment": 段id}`、
  `{"op": "本回合發生過", "segment": 段id}`;要用到它的卡(滅びの黒魔術師的召喚條件)
  在那張票補句型與模板。

位置/存在原子的區域照方的來源還原;區域字面不是預設寫法(舊式「フィールド上」,票 11)時
原子另帶 `text`(區域短語原文,不含「に」),模板照它寫。

多個前提依字面順序組成「且」。接縫是 `split_premises(body, state, start)`:回傳
(前提條件式, 前提字面結束偏移, 子句開始偏移);沒有前提回 (None, start, start)。
`render_premise` 是反向檢查的模板,只從原子的格產生日文。
"""
import re

from structure_shape import zone

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
# 「Xが<區域>に存在する場合、」:X 不含讀點;區域短語交給 parse_zones 認,認不得就不是前提。
_OBJECT_FIRST_RE = re.compile(
    "^(?P<obj>[^、]+?)が(?P<zones>[^、]+?)に存在(?P<neg>し)?(?:する|ない)"
    "(?P<form>場合|状態で)")
# 「<區域>にXが存在する場合、」。
_ZONE_FIRST_RE = re.compile(
    "^(?P<zones>[^、]+?)に(?P<obj>[^、]+?)が存在(?P<neg>し)?(?:する|ない)"
    "(?P<form>場合|状態で)")


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
    `state` 是 segment_extract.BlockState(要寫位置、建物件);`parse_zones` 是區域短語
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
        zones = parse_zones(m.group("zones"))
        if zones is None:
            continue
        obj_id, _, _ = state.object_at(m.group("obj"), offset)
        if obj_id is None:
            continue
        if obj_id == state.self_id and not m.group("neg"):
            atom = {"op": "位置", "object": obj_id, "zones": zones,
                    "form": m.group("form")}
        else:
            atom = {"op": "存在", "object": obj_id, "zones": zones,
                    "form": m.group("form"), "order": first}
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


# ── 模板(反向檢查)────────────────────────────────────────────
class NoPremiseTemplate(Exception):
    """前提原子寫不出字面:訊息是 detail。"""


def render_game_state(atom, last):
    """遊戲狀態原子 → 字面;form 是「に」或「に、」,最後一個原子後面沒有子句時不寫讀點。"""
    state = atom.get("state")
    form = atom.get("form")
    if form not in ("に", "に、"):
        raise NoPremiseTemplate("遊戲狀態形式無模板")
    if last and form == "に、":
        form = "に"
    if state == GAME_STATE_TURN:
        if atom.get("value") not in ("我方", "對手"):
            raise NoPremiseTemplate("回合方無模板")
        return _SIDE_TEXT[atom["value"]] + "ターン" + form
    if state == GAME_STATE_DAMAGE_STEP:
        return "ダメージステップ" + form
    if state == GAME_STATE_PHASE:
        word = _PHASE_TEXT.get(atom.get("value"))
        side = atom.get("side")
        if word is None or (side is not None and side not in _SIDE_TEXT):
            raise NoPremiseTemplate("階段無模板")
        return (_SIDE_TEXT[side] if side else "") + word + form
    raise NoPremiseTemplate(f"遊戲狀態無模板:{state}")


def render_premise(premise, render_zones, render_object, followed=True):
    """前提條件式 → 日文。`render_zones(區域列表, 原文字面或 None) → 字面`、
    `render_object(物件id) → 字面`
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
        negated = False
        if op == "非" and atom.get("arg", {}).get("op") == "存在":
            atom, negated, op = atom["arg"], True, "存在"
        if op not in ("位置", "存在"):
            raise NoPremiseTemplate(f"前提原子無模板:{op}")
        verb = "存在しない" if negated else "存在する"
        if atom.get("form") not in ("場合", "状態で"):
            raise NoPremiseTemplate("前提形式無模板")
        if atom.get("elided"):
            # 分歧引導句的「存在しない場合」:物件與區域承前省略(segment_tree)。
            if not negated:
                raise NoPremiseTemplate("省略的存在前提只能是否定")
            pieces.append(verb + atom["form"] + ("" if last else "、"))
            continue
        obj = render_object(atom["object"])
        zones = render_zones(atom["zones"], atom.get("text"))
        if op == "位置" or atom.get("order") == "物件":
            text = f"{obj}が{zones}に{verb}{atom.get('form', '')}"
        else:
            text = f"{zones}に{obj}が{verb}{atom.get('form', '')}"
        pieces.append(text + ("" if last else "、"))
    return "".join(pieces)
