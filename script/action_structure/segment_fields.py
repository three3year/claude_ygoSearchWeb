"""段的原因、極性、時機(延遲)、期間、被改的屬性與代替格(票 08):抽取與句型模板成對放在一起。

- 原因(`cause`):「戦闘で」「効果で」「相手の効果で」「戦闘・効果で」→ `{"kind": 戰鬥|效果|戰鬥或效果,
  "text": 字面, "side": 我方/對手(效果含誰的,有寫才有)}`;字面只認閉集 `CAUSE_FORMS`,模板照字面寫。
- 極性(`polarity`):述語語尾給的極性(`segment_extract.TAILS`)之外,「Xは〜できる」(助詞は)是
  永續的許可(直接攻撃できる)→ 極性「可以」、不是可選的動作;「Xを〜できる」仍是可選的「做」
  (票 10 的決定)。`resolve_polarity` 是抽取與反向檢查共用的一把尺。
- 時機(`timing`):「次のスタンバイフェイズに」「このターンのエンドフェイズに」→
  `{"kind": "延遲", "text": 字面, "phase": 階段, "turn": 次の/このターンの, "side": 方}`;
  序列中段出現條件段之後的段也算延遲,但沒有字面:`{"kind": "延遲"}`。延遲段不標取對象(spec)。
- 期間(`duration`):「そのターンの終了時まで」「ターン終了時まで」→ `{"kind": "本回合", "text"}`;
  其他「〜まで」→ `{"kind": "到X為止", "text"}`。形狀允許出現在任何段、本回合可帶選填 `range`
  (整回合/發動後,`structure_shape.DURATION_RANGES`)。句中的「〜まで」只從性質變更句抽出;
  m2 票 03 加句子層的兩種:「〜限り、」前提 → 持續(沒有字面);句首時間狀語(`LEADING_DURATIONS`:
  このターン、/この効果の発動後、ターン終了時まで/このカード・この効果を発動するターン、)→ 本回合
  (帶 range),套到同一句的每個段、字面只在第一段,模板寫在段的最前面(`split_duration`)。
- 被改的屬性(`modified`):性質變更句「その攻撃力はそのターンの終了時まで元々の攻撃力の倍になる」
  「このカードの攻撃力は０になる」→ 動作詞「性質變更」、`{"attr": [攻擊力|守備力], "form": 倍|半分|數值,
  "base": 「元々の攻撃力」(倍/半分時), "value": 整數(數值時)}`(attr 是清單,值域與 form 的增/減、
  選填 limit `{"cmp", "text"}` 見 `structure_shape.MODIFY_ATTRS`/`MODIFY_FORMS`,目前只抽出這兩種);對象線的 `ref` 記提及的字面
  (「その」「このカードの」「そのモンスターの」)。後續段要讀改後的屬性時,往前找同區塊作用在同一物件
  上的性質變更段即可(段上就有 `modified`),不另存狀態。
- 代替(`replaces`):「〜場合、代わりに〜」的條件段改標「被代替」,後面的段記 `replaces` = 被代替段 id,
  段的範圍含「代わりに」;模板在段前寫「代わりに」。
"""
import re

from premise import PHASE_WORDS
from structure_shape import DURATION_KINDS, NoTemplate, placement_form
from synonyms import MODIFY_PREDICATE, ONLY, ONLY_MARKER

# 字面 → (種類, 方);閉集,反向檢查只認這些。
CAUSE_FORMS = {
    "戦闘によって": ("戰鬥", None), "戦闘で": ("戰鬥", None),
    # 「〜ならず、戦闘では破壊されない」的主語省略右半(里程碑二票 02);其餘「では」字面歸票 04。
    "戦闘では": ("戰鬥", None),
    "カードの効果によって": ("效果", None), "効果によって": ("效果", None),
    "カードの効果で": ("效果", None), "効果で": ("效果", None),
    "自分の効果で": ("效果", "我方"), "相手の効果で": ("效果", "對手"),
    "自分のカードの効果で": ("效果", "我方"), "相手のカードの効果で": ("效果", "對手"),
    # m2 票 06:受到傷害的原因(「相手のカードの効果によって自分がダメージを受けた時」)。
    "自分のカードの効果によって": ("效果", "我方"), "相手のカードの効果によって": ("效果", "對手"),
    "戦闘またはカードの効果によって": ("戰鬥或效果", None),
    "戦闘・効果で": ("戰鬥或效果", None), "戦闘・効果によって": ("戰鬥或效果", None),
    "戦闘または効果で": ("戰鬥或效果", None),
}
# 作為X素材(票 09):「S素材として墓地へ送られた」→ {"kind": "作為素材", "text": 字面, "summon": 卡片子類型}
# (「素材として」沒寫哪種召喚就沒有 summon)。
CAUSE_MATERIAL = "作為素材"
MATERIAL_FORMS = {
    "融合素材として": "融合", "S素材として": "同步", "シンクロ素材として": "同步",
    "X素材として": "超量", "エクシーズ素材として": "超量", "L素材として": "連結",
    "リンク素材として": "連結", "素材として": None,
}
CAUSE_PATTERN = "|".join(sorted(map(re.escape, [*CAUSE_FORMS, *MATERIAL_FORMS]),
                                key=len, reverse=True))
REPLACEMENT_PREFIX = "代わりに"


def parse_cause(text):
    """原因字面 → cause 格;不在閉集回 None。"""
    if text in MATERIAL_FORMS:
        cause = {"kind": CAUSE_MATERIAL, "text": text}
        if MATERIAL_FORMS[text]:
            cause["summon"] = MATERIAL_FORMS[text]
        return cause
    if text not in CAUSE_FORMS:
        return None
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
    expected = CAUSE_FORMS.get(text)
    if expected is None or expected != (cause.get("kind"), cause.get("side")):
        raise NoTemplate(f"原因無模板:{cause.get('kind')}")
    return text


# 永續許可的動作詞:「Xは直接攻撃できる」是卡在場上時一直成立的許可,不是一次做的動作;
# 「このカードは手札から特殊召喚できる」仍是可選的做(票 05/11 的斷言),所以只認不移動卡的動作。
PERMISSION_ACTIONS = ("直接攻擊",)


def resolve_polarity(parsed, marker):
    """述語解析結果(parse_predicates 的列表)+ 物件助詞 → (極性, 可選)。
    「Xは〜できる」且動作詞是永續許可的(直接攻擊)→ 極性「可以」、不可選;
    「Xしか〜できない」(助詞しか,m2 票 03)→ 極性「只能」,同述語開頭的「しか」;其餘照語尾。"""
    polarity = parsed[-1].polarity
    optional = True if any(p.optional for p in parsed) else None
    if marker == ONLY_MARKER and polarity == "不能" and not optional:
        return ONLY, None
    if (optional and marker == "は" and polarity == "做"
            and all(p.action in PERMISSION_ACTIONS for p in parsed)):
        return "可以", None
    return polarity, optional


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
# treat 的字面可帶讀點(「装備魔法カード扱いで、」),種類照去掉讀點的字面查。
TREAT_FORMS = {"装備魔法カード扱いで": "裝備卡", "装備カード扱いで": "裝備卡"}
ORDER_FORMS = ("好きな順番で",)
TREAT_PATTERN = "(?:" + "|".join(map(re.escape, TREAT_FORMS)) + ")、?"
ORDER_PATTERN = "|".join(map(re.escape, ORDER_FORMS))


def parse_placement_form(treat_text=None, order_text=None):
    """放置形式字面 → placement_form;兩個都沒寫回 None。"""
    if not treat_text and not order_text:
        return None
    treat = ({"text": treat_text, "kind": TREAT_FORMS[treat_text.rstrip("、")]}
             if treat_text else None)
    order = {"text": order_text} if order_text else None
    return placement_form(treat=treat, order=order)


def render_placement_form(form):
    """placement_form → 寫在區域前的字面(treat、order 照字面);treat 的字面與種類對不上、
    或有表示形式(display 還沒有模板)丟 NoTemplate。"""
    if not form:
        return ""
    if form.get("display"):
        raise NoTemplate("放置形式無模板:display")
    text = ""
    treat = form.get("treat")
    if treat:
        if TREAT_FORMS.get((treat.get("text") or "").rstrip("、")) != treat.get("kind"):
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


# 句首時間狀語(m2 票 03):字面閉集 → range(None = 沒有 range)。期間都是本回合;誓約
# 「このカードを発動するターン、」是整回合(發動前後都算),「この効果の發動後、」是發動後。
# 字面含讀點,反向檢查原樣寫在段的最前面。
LEADING_DURATIONS = {
    "このターン、": None,
    "この効果の発動後、ターン終了時まで、": "發動後",
    "この効果の発動後、ターン終了時まで": "發動後",
    "このカードを発動するターン、": "整回合",
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
# 該戰鬥(m2 票 07):「(その)ダメージ計算時のみ」「ダメージステップの間」「ダメージステップ時のみ」,
# 字面可帶讀點;句中出現,寫在性質變更句的期間槽([屬性]は[期間][值]になる)。
DURATION_BATTLE = "該戰鬥"
BATTLE_DURATION_PATTERN = "(?:その)?(?:ダメージ計算時のみ|ダメージステップの間|ダメージステップ時のみ)、?"
_BATTLE_DURATION_RE = re.compile(BATTLE_DURATION_PATTERN)


def parse_duration(text):
    """「〜まで」→ duration 格;本回合的字面是閉集,其餘是「到X為止」;戰鬥時點的字面是該戰鬥。"""
    if text in DURATION_THIS_TURN:
        return {"kind": "本回合", "text": text}
    if text.endswith("まで"):
        return {"kind": "到X為止", "text": text}
    if _BATTLE_DURATION_RE.fullmatch(text):
        return {"kind": DURATION_BATTLE, "text": text}
    return None


def find_battle_duration(clause):
    """子句裡任何位置的該戰鬥字面 → duration 格;沒有回 None。子句其餘部分解不解得出都記
    (「攻撃力はそのダメージ計算時のみ３０００アップする」的增減是票 08)。"""
    m = _BATTLE_DURATION_RE.search(clause)
    return {"kind": DURATION_BATTLE, "text": m.group()} if m else None


def render_duration(duration):
    if not duration:
        return ""
    text = duration.get("text")
    if duration.get("kind") == "本回合":
        return text if text in DURATION_THIS_TURN else None
    if duration.get("kind") == "到X為止":
        return text if text and text.endswith("まで") else None
    if duration.get("kind") == DURATION_BATTLE:
        return text if text and _BATTLE_DURATION_RE.fullmatch(text) else None
    return None


STAT_WORDS = (("攻撃力", "攻擊力"), ("守備力", "守備力"))
_STAT_NAME = dict(STAT_WORDS)
_STAT_TEXT = {v: k for k, v in STAT_WORDS}
_STAT_ALT = "|".join(w for w, _ in STAT_WORDS)
# 提及的字面:「その攻撃力」的その是回指(物件是最近的物件),「このカードの」是物件0。
MENTION_FORMS = ("その", "それらの", "このカードの", "そのモンスターの", "そのカードの",
                 "それらのモンスターの", "それらのカードの")
_MENTION_ALT = "|".join(MENTION_FORMS)
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_TO_FULLWIDTH_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")
_MODIFY_RE = re.compile(
    f"^(?P<mention>{_MENTION_ALT})(?P<attr>{_STAT_ALT})は"
    f"(?P<duration>[^、]+?まで|{BATTLE_DURATION_PATTERN})?"
    f"(?:(?P<base>元々の(?:{_STAT_ALT}))の(?P<form>倍|半分)|(?P<value>[０-９]+)){MODIFY_PREDICATE}$")


def parse_modify(clause):
    """性質變更句 → (提及字面, modified 格, duration 格或 None);不是就回 None。"""
    m = _MODIFY_RE.match(clause)
    if not m:
        return None
    modified = {"attr": [_STAT_NAME[m.group("attr")]]}
    if m.group("form"):
        modified["form"] = m.group("form")
        modified["base"] = m.group("base")
    else:
        modified["form"] = "數值"
        modified["value"] = int(m.group("value").translate(_FULLWIDTH_DIGITS))
    duration = parse_duration(m.group("duration")) if m.group("duration") else None
    return m.group("mention"), modified, duration


def mention_head(mention):
    """提及字面指回哪一種物件:このカードの → 物件0(回 None);その/それらの → 最近的任何物件;
    そのモンスターの → 最近的怪獸。"""
    if mention == "このカードの":
        return None
    return "モンスター" if "モンスター" in mention else "カード"


def render_modify(mention, modified, duration):
    """性質變更句模板:[提及][屬性]は[期間][值]になる;格與閉集對不上丟 NoTemplate
    (期間由 `render_duration` 驗,它回 None 時也是這裡丟)。attr 清單目前只認一項。"""
    attrs = modified.get("attr") or []
    attr = _STAT_TEXT.get(attrs[0]) if len(attrs) == 1 else None
    period = render_duration(duration)
    form = modified.get("form")
    value = None
    if form in ("倍", "半分"):
        base = modified.get("base") or ""
        if re.fullmatch(f"元々の(?:{_STAT_ALT})", base):
            value = f"{base}の{form}"
    elif form == "數值" and isinstance(modified.get("value"), int):
        value = str(modified["value"]).translate(_TO_FULLWIDTH_DIGITS)
    if mention not in MENTION_FORMS or attr is None or period is None or value is None:
        raise NoTemplate("被改的屬性無模板")
    return f"{mention}{attr}は{period}{value}{MODIFY_PREDICATE}"
