"""段的原因、極性、時機(延遲)、期間、被改的屬性與代替格(票 08):抽取與句型模板成對放在一起。

- 原因(`cause`):「戦闘で」「効果で」「相手の効果で」「戦闘・効果で」→ `{"kind": 戰鬥|效果|戰鬥或效果,
  "text": 字面, "side": 我方/對手(效果含誰的,有寫才有)}`;字面只認閉集 `CAUSE_FORMS`,模板照字面寫。
  帶「は」的字面(効果では、戦闘及び効果では…)、誰的效果(`OWNER_FORMS`、`OWNER_PATTERN`)。
- 每回合次數(`per_turn`):抗性的「(それぞれ)１ターンに１度だけ」→ {"value", "text"}。
- 極性(`polarity`):述語語尾給的極性(`synonyms.TAILS`)之外,「Xは〜できる」(助詞は)是
  永續的許可(直接攻撃できる)→ 極性「可以」、不是可選的動作;「Xを〜できる」仍是可選的「做」
  (票 10 的決定)。`resolve_polarity` 是抽取與反向檢查共用的一把尺。
- 時機(`timing`):「次のスタンバイフェイズに」「このターンのエンドフェイズに」→
  `{"kind": "延遲", "text": 字面, "phase": 階段, "turn": 次の/このターンの, "side": 方}`;
  序列中段出現條件段之後的段也算延遲,但沒有字面:`{"kind": "延遲"}`。延遲段不標取對象(spec)。
- 期間(`duration`):「そのターンの終了時まで」「ターン終了時まで」→ `{"kind": "本回合", "text"}`;
  其他「〜まで」→ `{"kind": "到X為止", "text"}`。形狀允許出現在任何段、本回合可帶選填 `range`
  (整回合/發動後,`structure_shape.DURATION_RANGES`)。句中的「〜まで」只從性質變更句抽出;
  另有句子層的兩種:「〜限り、」前提 → 持續(沒有字面);句首時間狀語(`LEADING_DURATIONS`:
  このターン、/この効果の発動後、ターン終了時まで/このカード・この効果を発動するターン、)→ 本回合
  (帶 range),套到同一句的每個段、字面只在第一段,模板寫在段的最前面(`split_duration`)。
- 被改的屬性(`modified`):性質變更句「その攻撃力はそのターンの終了時まで元々の攻撃力の倍になる」
  「このカードの攻撃力は０になる」→ 動作詞「性質變更」、`{"attr": [屬性…], "form": 倍|半分|數值,
  "base": 「元々の攻撃力」(倍/半分時), "value": 整數(數值時)}`(attr 是清單,值域與選填 limit
  `{"cmp", "text"}` 見 `structure_shape.MODIFY_ATTRS`/`MODIFY_FORMS`);對象線的 `ref` 記提及的字面
  (「その」「このカードの」「そのモンスターの」)。後續段要讀改後的屬性時,往前找同區塊作用在同一物件
  上的性質變更段即可(段上就有 `modified`),不另存狀態。增減「〜は３００アップ/ダウンする」
  → form 增/減、value 差量(整數)或算式字面 `{"kind": "算式", "text"}`(寫在主語前的「〜だけ、」另帶
  `placement` 主語前),舊式「Nポイント」記 `unit`;攻守同時是 attr 兩項(「・」);attr 加等級、屬性、
  種族、卡名(「レベルは４になる」「レベルはそのモンスターと同じになる」= 數值、value 算式);主語是
  「[區域の][全ての]物件短語の」(區域記對象線的從、「全ての」記對象線的數量);「攻撃力は、」的讀點
  記進對象線的助詞字面。期間只照字面抽,沒寫不推斷。
- 代替(`replaces`):「〜場合、代わりに〜」的條件段改標「被代替」,後面的段記 `replaces` = 被代替段 id,
  段的範圍含「代わりに」;模板在段前寫「代わりに」。
"""
import re

from premise import PHASE_WORDS
from structure_shape import (AMOUNT_FORMULA, DISPLAY_WORD, DURATION_KINDS, FULLWIDTH_DIGITS,
                             PLACEMENT_DISPLAY_WORD, TO_FULLWIDTH_DIGITS, NoTemplate,
                             display_value, placement_form)
from synonyms import ATTACK_FAMILY, MODIFY_PREDICATE, ONLY, ONLY_MARKER

# 字面 → (種類, 方);閉集,反向檢查只認這些。
CAUSE_FORMS = {
    "戦闘によって": ("戰鬥", None), "戦闘で": ("戰鬥", None),
    # 「〜ならず、戦闘では破壊されない」的主語省略右半。
    "戦闘では": ("戰鬥", None),
    # 帶「は」的寫法(では、によっては)與「その戦闘で」。
    "その戦闘で": ("戰鬥", None), "その戦闘では": ("戰鬥", None),
    "戦闘によっては": ("戰鬥", None),
    "効果では": ("效果", None), "カードの効果では": ("效果", None),
    "効果によっては": ("效果", None), "カードの効果によっては": ("效果", None),
    "自分の効果では": ("效果", "我方"), "相手の効果では": ("效果", "對手"),
    "相手の効果によっては": ("效果", "對手"),
    "相手のカードの効果では": ("效果", "對手"), "相手のカードの効果によっては": ("效果", "對手"),
    "戦闘・効果では": ("戰鬥或效果", None), "戦闘及び効果では": ("戰鬥或效果", None),
    "戦闘及び効果で": ("戰鬥或效果", None), "戦闘または効果では": ("戰鬥或效果", None),
    "カードの効果によって": ("效果", None), "効果によって": ("效果", None),
    "カードの効果で": ("效果", None), "効果で": ("效果", None),
    "自分の効果で": ("效果", "我方"), "相手の効果で": ("效果", "對手"),
    "自分のカードの効果で": ("效果", "我方"), "相手のカードの効果で": ("效果", "對手"),
    # 受到傷害的原因(「相手のカードの効果によって自分がダメージを受けた時」)。
    "自分のカードの効果によって": ("效果", "我方"), "相手のカードの効果によって": ("效果", "對手"),
    "戦闘またはカードの効果によって": ("戰鬥或效果", None),
    "戦闘・効果で": ("戰鬥或效果", None), "戦闘・効果によって": ("戰鬥或效果", None),
    "戦闘または効果で": ("戰鬥或效果", None),
    # ガスタ・ファルコ「戦闘以外によって墓地へ送られた時」。
    "戦闘以外によって": ("戰鬥以外", None), "戦闘以外で": ("戰鬥以外", None),
    # 站主裁定:「相手によって(フィールドから離れた)」= 對手的攻擊或對手的卡片效果。
    "相手によって": ("戰鬥或效果", "對手"),
}
# 作為X素材(票 09):「S素材として墓地へ送られた」→ {"kind": "作為素材", "text": 字面, "summon": 卡片子類型}
# (「素材として」沒寫哪種召喚就沒有 summon)。
CAUSE_MATERIAL = "作為素材"
MATERIAL_FORMS = {
    "融合素材として": "融合", "S素材として": "同步", "シンクロ素材として": "同步",
    "X素材として": "超量", "エクシーズ素材として": "超量", "L素材として": "連結",
    "リンク素材として": "連結", "素材として": None,
    "シンクロ召喚の素材として": "同步",   # 舊式寫全「召喚の」
}
CAUSE_PATTERN = "|".join(sorted(map(re.escape, [*CAUSE_FORMS, *MATERIAL_FORMS]),
                                key=len, reverse=True))
# 誰的效果:「〜の効果を受けない」「〜の効果の対象にならない」的「〜の」是原因,
# 「効果を受け」「効果の対象に」留在述語。方的字面閉集記 side;其餘是物件短語(「A及びB」多個),
# 原因記 {"kind": 效果, "text": "の", "objects": [...]}(`cause_phrase.parse_cause_phrase`)。
OWNER_FORMS = {"相手の": "對手", "自分の": "我方", "カードの": None,
               "相手のカードの": "對手", "自分のカードの": "我方"}
OWNER_TEXT = "の"
OWNER_PATTERN = "(?:「[^「」]*」|[^を、「」])+?の(?=効果を受け|効果の対象に)"
OWNER_JOINER = "及び"
REPLACEMENT_PREFIX = "代わりに"


def parse_cause(text):
    """原因字面 → cause 格;不在閉集回 None。"""
    if text in MATERIAL_FORMS:
        cause = {"kind": CAUSE_MATERIAL, "text": text}
        if MATERIAL_FORMS[text]:
            cause["summon"] = MATERIAL_FORMS[text]
        return cause
    if text in OWNER_FORMS:
        kind, side = "效果", OWNER_FORMS[text]
    elif text not in CAUSE_FORMS:
        return None
    else:
        kind, side = CAUSE_FORMS[text]
    cause = {"kind": kind, "text": text}
    if side:
        cause["side"] = side
    return cause


def render_cause(cause):
    """cause 格 → 字面;字面與種類、方對不上(不在閉集)丟 NoTemplate。"""
    if not cause:
        return ""
    text = cause.get("text")
    if cause.get("kind") == CAUSE_MATERIAL:
        if text not in MATERIAL_FORMS or MATERIAL_FORMS[text] != cause.get("summon"):
            raise NoTemplate(f"原因無模板:{cause.get('kind')}")
        return text
    expected = (("效果", OWNER_FORMS[text]) if text in OWNER_FORMS
                else CAUSE_FORMS.get(text))
    if expected is None or expected != (cause.get("kind"), cause.get("side")):
        raise NoTemplate(f"原因無模板:{cause.get('kind')}")
    return text


# 永續許可的動作詞:「Xは直接攻撃できる」是卡在場上時一直成立的許可,不是一次做的動作;
# 「このカードは手札から特殊召喚できる」仍是可選的做(票 05/11 的斷言),所以只認不移動卡的動作。
# 含攻擊家族(攻擊、直接攻擊、多次攻擊、全體攻擊;spec「永續許可擴到攻擊家族」)。
PERMISSION_ACTIONS = ATTACK_FAMILY


def resolve_polarity(parsed, marker):
    """述語解析結果(parse_predicates 的列表)+ 物件助詞 → (極性, 可選)。
    「Xは〜できる」且動作詞是永續許可的(攻擊家族)→ 極性「可以」、不可選;主語省略的子句
    (助詞 None:「相手フィールド上の全てのモンスターに１回ずつ攻撃が可能」)主語是「Xは」的 X 或此卡,
    同「は」;助詞後的讀點(「Xは、」)不影響。
    「Xしか〜できない」(助詞しか)→ 極性「只能」,同述語開頭的「しか」;其餘照語尾。"""
    polarity = parsed[-1].polarity
    optional = True if any(p.optional for p in parsed) else None
    marker = marker.rstrip("、") if marker else marker
    if marker == ONLY_MARKER and polarity == "不能" and not optional:
        return ONLY, None
    if (optional and marker in ("は", None) and polarity == "做"
            and all(p.action in PERMISSION_ACTIONS for p in parsed)):
        return "可以", None
    return polarity, optional


PER_TURN_PATTERN = "(?:それぞれ)?１ターンに[１-９]度だけ"
_PER_TURN_RE = re.compile("^(?:それぞれ)?１ターンに(?P<n>[１-９])度だけ$")


def parse_per_turn(text):
    """「１ターンに１度だけ」→ {"value", "text"}。"""
    m = _PER_TURN_RE.match(text)
    return {"value": int(m.group("n").translate(FULLWIDTH_DIGITS)), "text": text}


def render_per_turn(per_turn):
    """per_turn 格 → 字面;字面與次數對不上丟 NoTemplate。"""
    if not per_turn:
        return ""
    m = _PER_TURN_RE.match(per_turn.get("text") or "")
    if not m or int(m.group("n").translate(FULLWIDTH_DIGITS)) != per_turn.get("value"):
        raise NoTemplate("每回合次數無模板")
    return per_turn["text"]


_PHASE_ALT = "|".join(w for w, _ in PHASE_WORDS)
TIMING_PATTERN = f"(?:次の|このターンの)?(?:自分・相手の|自分|相手)?(?:{_PHASE_ALT})に"
_TIMING_RE = re.compile(
    f"^(?P<turn>次の|このターンの)?(?P<side>自分・相手の|自分|相手)?(?P<phase>{_PHASE_ALT})に$")
_SIDE = {"自分": "我方", "相手": "對手", "自分・相手の": "任一方"}
_SIDE_TEXT = {v: k for k, v in _SIDE.items()}
_PHASE_TEXT = {value: word for word, value in PHASE_WORDS}
DELAY = "延遲"


def parse_timing(text):
    """「次のスタンバイフェイズに」→ 延遲的 timing 格;不是就回 None。"""
    m = _TIMING_RE.match(text or "")
    if not m:
        return None
    timing = {"kind": DELAY, "text": text, "phase": dict(PHASE_WORDS)[m.group("phase")]}
    if m.group("turn"):
        timing["turn"] = m.group("turn")
    if m.group("side"):
        timing["side"] = _SIDE[m.group("side")]
    return timing


def implicit_delay():
    """序列中段出現條件段之後的段:延遲,沒有字面。"""
    return {"kind": DELAY}


def render_timing(timing):
    """timing 格 → 字面(沒有字面的延遲寫空字串);格與字面對不上丟 NoTemplate。"""
    if not timing:
        return ""
    if timing.get("kind") != DELAY:
        raise NoTemplate(f"時機無模板:{timing.get('kind')}")
    if "text" not in timing:
        return ""
    phase = _PHASE_TEXT.get(timing.get("phase"))
    side = timing.get("side")
    text = None
    if phase is not None and (side is None or side in _SIDE_TEXT):
        text = (timing.get("turn") or "") + (_SIDE_TEXT[side] if side else "") + phase + "に"
    if text != timing["text"]:
        raise NoTemplate(f"時機無模板:{timing.get('kind')}")
    return text


def is_delayed(seg):
    return bool(seg.get("timing")) and seg["timing"].get("kind") == DELAY


# 到的放置形式(對象線 `to.form`,`structure_shape.placement_form`):字面閉集。
# treat 的字面可帶讀點(「装備魔法カード扱いで、」),種類照去掉讀點的字面查;寫在區域前。
TREAT_FORMS = {"装備魔法カード扱いで": "裝備卡", "装備カード扱いで": "裝備卡",
               "装備カード扱いとして": "裝備卡",
               "永続魔法カード扱いで": "永續魔法", "永続罠カード扱いで": "永續陷阱",
               "魔法カード扱いで": "魔法"}
ORDER_FORMS = ("好きな順番で",)
TREAT_PATTERN = ("(?:" + "|".join(map(re.escape, sorted(TREAT_FORMS, key=len, reverse=True)))
                 + ")、?")
ORDER_PATTERN = "|".join(map(re.escape, ORDER_FORMS))
# 放置形式的表示形式寫在述語前:「表側表示で」「表側攻撃表示か裏側守備表示で」(二選一;
# 「表側守備表示または裏側守備表示で」同)。
_DISPLAY_OR = "(?:か|または)"
DISPLAY_PATTERN = f"{PLACEMENT_DISPLAY_WORD}(?:{_DISPLAY_OR}{PLACEMENT_DISPLAY_WORD})?で"
_DISPLAY_RE = re.compile(
    f"^(?P<a>{PLACEMENT_DISPLAY_WORD})(?:{_DISPLAY_OR}(?P<b>{PLACEMENT_DISPLAY_WORD}))?で$")


# 「以下の効果を持つ装備魔法カード扱いで」:被當成裝備卡的物件帶後面 ● 列舉的效果
# (`segment_tree` 在裝備段後接內嵌效果節點);前綴屬於 treat 字面。
EFFECT_HOLDER_PREFIX = "以下の効果を持つ"


def _treat_kind(text):
    delta = parse_treat_delta(text)
    base = text[len(delta[0]) + 1:] if delta else text
    if base.startswith(EFFECT_HOLDER_PREFIX):
        base = base[len(EFFECT_HOLDER_PREFIX):]
    return TREAT_FORMS.get(base.rstrip("、"))


def parse_display(text):
    """「表側攻撃表示か裏側守備表示で」→ {"text", "alternatives": [{"face", "position"}...]}。"""
    m = _DISPLAY_RE.match(text)
    words = [w for w in (m.group("a"), m.group("b")) if w]
    return {"text": text, "alternatives": [display_value(w) for w in words]}


def parse_placement_form(treat_text=None, order_text=None, display_literal=None):
    """放置形式字面 → placement_form;一個都沒寫回 None。"""
    if not treat_text and not order_text and not display_literal:
        return None
    treat = ({"text": treat_text, "kind": _treat_kind(treat_text)}
             if treat_text else None)
    order = {"text": order_text} if order_text else None
    display = parse_display(display_literal) if display_literal else None
    return placement_form(treat=treat, display=display, order=order)


def render_display(form):
    """placement_form 的 display → 寫在述語前的字面(照 text 原樣寫,但 text 要能拆回同一組
    alternatives);沒有 display 回空字串。"""
    display = (form or {}).get("display")
    if not display:
        return ""
    text = display.get("text") or ""
    if not _DISPLAY_RE.match(text) or parse_display(text) != display:
        raise NoTemplate("放置形式無模板:display")
    return text


def render_placement_form(form):
    """placement_form → 寫在區域前的字面(treat、order 照字面);treat 的字面與種類對不上丟
    NoTemplate。display 寫在述語前,另由 `render_display` 寫。"""
    if not form:
        return ""
    text = ""
    treat = form.get("treat")
    if treat:
        if _treat_kind(treat.get("text") or "") != treat.get("kind"):
            raise NoTemplate(f"放置形式無模板:{treat.get('kind')}")
        text += treat["text"]
    if form.get("order"):
        text += form["order"]["text"]
    return text


DURATION_LASTING = "持續"
DURATION_TURN = "本回合"


def lasting():
    """「〜限り、」前提給的期間:持續,沒有字面(字面在前提的 form)。"""
    return {"kind": DURATION_LASTING}


# 句首時間狀語:字面閉集 → range(None = 沒有 range)。期間都是本回合;誓約
# 「このカードを発動するターン、」是整回合(發動前後都算),「この効果の発動後、」是發動後。
# 字面含讀點,反向檢查原樣寫在段的最前面。
LEADING_DURATIONS = {
    "このターン、": None,
    "この効果の発動後、ターン終了時まで、": "發動後",
    "この効果の発動後、ターン終了時まで": "發動後",
    "このカードの発動後、ターン終了時まで、": "發動後",
    "このカードの発動後、ターン終了時まで": "發動後",
    "このカードを発動するターン、": "整回合",
    "このターン中、": None,
    "この効果を発動するターン、": "整回合",
}
_LEADING_DURATION_RE = re.compile(
    "^(?:" + "|".join(map(re.escape, sorted(LEADING_DURATIONS, key=len, reverse=True))) + ")")


def parse_leading_duration(text):
    """句首時間狀語 → (duration 格, 字面長度);不是就回 (None, 0)。"""
    m = _LEADING_DURATION_RE.match(text)
    if not m:
        return None, 0
    duration = {"kind": DURATION_TURN, "text": m.group()}
    if LEADING_DURATIONS[m.group()]:
        duration["range"] = LEADING_DURATIONS[m.group()]
    return duration, m.end()


def inherited_duration(duration):
    """同一句後面的段:期間照抄、字面只在第一段。"""
    return {k: v for k, v in duration.items() if k != "text"}


def split_duration(duration):
    """段的期間 → (寫在段最前面的句首字面, 留給性質變更句模板的句中期間或 None)。
    句首字面要與種類、range 對得上;沒有字面的期間(持續、同句後段承襲的)不寫;
    其餘有字面的是句中的「〜まで」,只有性質變更句模板寫得出。"""
    if not duration:
        return "", None
    text = duration.get("text")
    if text is None:
        if duration.get("kind") not in DURATION_KINDS:
            raise NoTemplate(f"期間無模板:{duration.get('kind')}")
        return "", None
    if text in LEADING_DURATIONS:
        if (duration.get("kind"), duration.get("range")) != (DURATION_TURN,
                                                              LEADING_DURATIONS[text]):
            raise NoTemplate(f"期間無模板:{duration.get('kind')}")
        return text, None
    return "", duration


DURATION_THIS_TURN = ("そのターンの終了時まで", "ターン終了時まで", "このターンの終了時まで")
_DURATION_RE = re.compile("^(?P<text>.+?まで)")
DURATION_BATTLE = "該戰鬥"
BATTLE_DURATION_PATTERN = ("(?:その|(?:相手)?モンスターに攻撃する)?"
                           "(?:ダメージ計算時のみ|ダメージステップの間)、?")
_BATTLE_DURATION_RE = re.compile(BATTLE_DURATION_PATTERN)


# 簡單子句述語前的期間:「エンドフェイズまで表側で除外する」「次のスタンバイフェイズまで
# 除外する」;模板寫在述語前(到之前)。只收階段與「ターン終了時」的「〜まで」。
CLAUSE_DURATION_PATTERN = (f"(?:次のターンの|次の)?(?:自分|相手)?(?:{_PHASE_ALT})まで"
                           "|(?:その)?ターン終了時まで")
_CLAUSE_DURATION_RE = re.compile(f"^(?:{CLAUSE_DURATION_PATTERN})$")


def is_clause_duration(duration):
    """簡單子句模板寫得出的句中期間:字面在閉集裡、種類與字面對得上。"""
    text = (duration or {}).get("text") or ""
    return bool(_CLAUSE_DURATION_RE.match(text)) and duration == parse_duration(text)
def _bare(text):
    return text[:-1] if text.endswith("、") else text


def parse_duration(text):
    """「〜まで」→ duration 格;本回合的字面是閉集,其餘是「到X為止」;戰鬥時點的字面是該戰鬥。
    字面可帶讀點(「攻撃力・守備力はターン終了時まで、〜分ダウンする」)。"""
    if _bare(text) in DURATION_THIS_TURN:
        return {"kind": "本回合", "text": text}
    if _bare(text).endswith("まで"):
        return {"kind": "到X為止", "text": text}
    if _BATTLE_DURATION_RE.fullmatch(text):
        return {"kind": DURATION_BATTLE, "text": text}
    return None


def find_battle_duration(clause):
    """子句裡任何位置的該戰鬥字面 → duration 格;沒有回 None。子句其餘部分解不解得出都記。"""
    m = _BATTLE_DURATION_RE.search(clause)
    return {"kind": DURATION_BATTLE, "text": m.group()} if m else None


def render_duration(duration):
    if not duration:
        return ""
    text = duration.get("text")
    if duration.get("kind") == "本回合":
        return text if text and _bare(text) in DURATION_THIS_TURN else None
    if duration.get("kind") == "到X為止":
        return text if text and _bare(text).endswith("まで") else None
    if duration.get("kind") == DURATION_BATTLE:
        return text if text and _BATTLE_DURATION_RE.fullmatch(text) else None
    return None


STAT_WORDS = (("攻撃力", "攻擊力"), ("守備力", "守備力"), ("レベル", "等級"),
              ("属性", "屬性"), ("種族", "種族"), ("カード名", "卡名"))
_STAT_NAME = dict(STAT_WORDS)
_STAT_TEXT = {v: k for k, v in STAT_WORDS}
_STAT_ALT = "|".join(w for w, _ in STAT_WORDS)
# 被改的屬性可以「・」列舉(攻守同時:「攻撃力・守備力」),attr 清單照字面順序。
STAT_JOINER = "・"
_ATTRS = f"(?:{_STAT_ALT})(?:{STAT_JOINER}(?:{_STAT_ALT}))*"
# 倍/半分的基準只有攻守(「元々の攻撃力の倍」)。
_BASE_ALT = "元々の(?:攻撃力|守備力)"
# 提及的字面:「その攻撃力」的その是回指(物件是最近的物件),「このカードの」是物件0。
# 其餘主語是「物件短語 + の」,物件照一般規則解析(`stat_modify._modify_subject`)。
MENTION_FORMS = ("その", "それらの", "このカードの", "そのモンスターの", "そのカードの",
                 "それらのモンスターの", "それらのカードの")
# 屬性後的助詞:「攻撃力は、」的讀點記進對象線的助詞字面(同「自分フィールドの、」記進從的字面)。
MODIFY_MARKERS = ("は", "は、")
# 增減:述語字面 アップ/ダウン + する/し(連用形串接);差量的單位只有舊式「ポイント」。
DELTA_WORDS = {"アップ": "增", "ダウン": "減"}
_DELTA_TEXT = {v: k for k, v in DELTA_WORDS.items()}
DELTA_TAILS = ("する", "し")
DELTA_UNIT = "ポイント"
# 「Nになる」的目標值可以是引用其他值的算式字面「そのモンスターと同じ」。
SAME_AS = "と同じ"
# 差量寫在主語前(「その差分×５００だけこのカードの攻撃力はアップする」):算式字面以「だけ」收尾,
# 可帶讀點;value 另記 placement 主語前。
LEADING_FORMULA = "主語前"
_MODIFY_RE = re.compile(
    "^(?P<lead>[^、]+?だけ、?)?"
    f"(?P<subject>その|[^、]+?の)(?P<attr>{_ATTRS})(?P<marker>は、?)"
    f"(?P<duration>[^、]+?まで、?|{BATTLE_DURATION_PATTERN})?"
    "(?:"
    f"(?:(?P<base>{_BASE_ALT})の(?P<form>倍|半分)|(?P<value>[０-９]+)|(?P<same>[^、]+?{SAME_AS}))"
    f"{MODIFY_PREDICATE}"
    f"|(?:(?P<delta>[０-９]+)(?P<unit>{DELTA_UNIT})?|(?P<formula>[^、]+?))?"
    f"(?P<direction>{'|'.join(DELTA_WORDS)})(?P<tail>{'|'.join(DELTA_TAILS)})"
    ")$")


def _attrs(text):
    return [_STAT_NAME[word] for word in text.split(STAT_JOINER)]


def parse_modify(clause):
    """性質變更句 → {"subject": 主語字面(含の), "marker": は|は、, "modified", "duration", "predicate"};
    不是就回 None。「Nになる」是數值(目標值;「〜と同じになる」是算式字面)、倍、半分;
    「Nアップ/ダウンする」是增/減,`value` 是差量(整數)或算式字面 `{"kind": "算式", "text"}`,
    沒寫數值時沒有 value;舊式「Nポイント」另記 `unit`。"""
    m = _MODIFY_RE.match(clause)
    if not m:
        return None
    modified = {"attr": _attrs(m.group("attr"))}
    if m.group("direction"):
        modified["form"] = DELTA_WORDS[m.group("direction")]
        if m.group("delta"):
            modified["value"] = int(m.group("delta").translate(FULLWIDTH_DIGITS))
            if m.group("unit"):
                modified["unit"] = m.group("unit")
        elif m.group("formula"):
            modified["value"] = {"kind": AMOUNT_FORMULA, "text": m.group("formula")}
        if m.group("lead"):
            if "value" in modified:
                return None
            modified["value"] = {"kind": AMOUNT_FORMULA, "text": m.group("lead"),
                                 "placement": LEADING_FORMULA}
        predicate = m.group("direction") + m.group("tail")
    else:
        if m.group("form"):
            modified["form"] = m.group("form")
            modified["base"] = m.group("base")
        else:
            modified["form"] = "數值"
            modified["value"] = (
                int(m.group("value").translate(FULLWIDTH_DIGITS)) if m.group("value")
                else {"kind": AMOUNT_FORMULA, "text": m.group("same")})
        if m.group("lead"):
            return None
        predicate = MODIFY_PREDICATE
    duration = parse_duration(m.group("duration")) if m.group("duration") else None
    return {"subject": m.group("subject"), "marker": m.group("marker"),
            "modified": modified, "duration": duration, "predicate": predicate}


def mention_head(mention):
    """提及字面指回哪一種物件:このカードの → 物件0(回 None);その/それらの → 最近的任何物件;
    そのモンスターの → 最近的怪獸。"""
    if mention == "このカードの":
        return None
    return "モンスター" if "モンスター" in mention else "カード"


def render_attrs(modified):
    """attr 清單 → 「攻撃力・守備力」;清單空或有閉集外的值丟 NoTemplate。"""
    attrs = modified.get("attr") or []
    if not attrs or any(a not in _STAT_TEXT for a in attrs):
        raise NoTemplate("被改的屬性無模板")
    return STAT_JOINER.join(_STAT_TEXT[a] for a in attrs)


def render_change(modified, predicate):
    """被改的值與述語 → 「３００ダウンする」「元々の攻撃力の倍になる」「そのモンスターと同じになる」;
    form、value、unit、述語字面對不上丟 NoTemplate。"""
    form, value = modified.get("form"), modified.get("value")
    if modified.get("limit") or (modified.get("unit") and form not in DELTA_WORDS.values()):
        raise NoTemplate("被改的屬性無模板")
    if form in DELTA_WORDS.values():
        word = _DELTA_TEXT[form]
        if not predicate or not predicate.startswith(word) \
                or predicate[len(word):] not in DELTA_TAILS:
            raise NoTemplate("增減的述語無模板")
        return _render_value(value, modified.get("unit"), allow_none=True) + predicate
    if predicate != MODIFY_PREDICATE:
        raise NoTemplate("被改的屬性無模板")
    if form in ("倍", "半分"):
        base = modified.get("base") or ""
        if not re.fullmatch(_BASE_ALT, base):
            raise NoTemplate("被改的屬性無模板")
        return f"{base}の{form}{predicate}"
    if form == "數值":
        if isinstance(value, dict) and not (value.get("text") or "").endswith(SAME_AS):
            raise NoTemplate("被改的屬性無模板")
        return _render_value(value, None, allow_none=False) + predicate
    raise NoTemplate("被改的屬性無模板")


def _render_value(value, unit, allow_none):
    if value is None and allow_none:
        return ""
    if isinstance(value, int) and unit in (None, DELTA_UNIT):
        return str(value).translate(TO_FULLWIDTH_DIGITS) + (unit or "")
    if isinstance(value, dict) and value.get("kind") == AMOUNT_FORMULA and value.get("text") \
            and unit is None:
        return value["text"]
    raise NoTemplate("被改的屬性無模板")


def render_modify(subject, marker, modified, duration, predicate):
    """性質變更句模板:[主語の][屬性]は[、][期間][值]述語(になる|アップする|ダウンする…);
    格與閉集對不上丟 NoTemplate(期間由 `render_duration` 驗,它回 None 時也是這裡丟)。"""
    period = render_duration(duration)
    if marker not in MODIFY_MARKERS or period is None:
        raise NoTemplate("被改的屬性無模板")
    value = modified.get("value")
    if isinstance(value, dict) and value.get("placement") is not None:
        text = value.get("text") or ""
        if value["placement"] != LEADING_FORMULA or not _bare(text).endswith("だけ")                 or modified.get("form") not in DELTA_WORDS.values():
            raise NoTemplate("被改的屬性無模板")
        rest = {k: v for k, v in modified.items() if k != "value"}
        return f"{text}{subject}{render_attrs(rest)}{marker}{period}{render_change(rest, predicate)}"
    return f"{subject}{render_attrs(modified)}{marker}{period}{render_change(modified, predicate)}"


# 「攻撃力・守備力３００アップの装備カード扱いで」:放置形式 treat 字面前的增減,
# 拆出一段衍生的性質變更段(`derived_from`),它的範圍是「攻撃力・守備力３００アップ」。
TREAT_DELTA_PATTERN = (f"{_ATTRS}[０-９]+(?:{DELTA_UNIT})?(?:{'|'.join(DELTA_WORDS)})の")
_TREAT_DELTA_RE = re.compile(
    f"^(?P<attr>{_ATTRS})(?P<delta>[０-９]+)(?P<unit>{DELTA_UNIT})?"
    f"(?P<direction>{'|'.join(DELTA_WORDS)})の")


def parse_treat_delta(treat_text):
    """treat 字面 → (增減字面, modified, 述語字面)或 None(沒有增減前綴)。"""
    m = _TREAT_DELTA_RE.match(treat_text or "")
    if not m:
        return None
    modified = {"attr": _attrs(m.group("attr")), "form": DELTA_WORDS[m.group("direction")],
                "value": int(m.group("delta").translate(FULLWIDTH_DIGITS))}
    if m.group("unit"):
        modified["unit"] = m.group("unit")
    return m.group()[:-1], modified, m.group("direction")


def render_treat_delta(modified, predicate):
    """衍生段模板:[屬性][差量]アップ(述語字面只有 アップ/ダウン,不帶語尾)。"""
    if predicate not in DELTA_WORDS or DELTA_WORDS[predicate] != modified.get("form") \
            or not isinstance(modified.get("value"), int):
        raise NoTemplate("衍生的性質變更段無模板")
    return render_attrs(modified) + _render_value(modified["value"], modified.get("unit"),
                                                  allow_none=False) + predicate
