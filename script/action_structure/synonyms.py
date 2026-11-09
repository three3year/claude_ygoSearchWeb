"""同義表:述語字面 → 動作詞、語尾 → 態與極性、取對象的字面(舊式「選択して」、新式「対象として」)。

收法(spec「段」、票 11):
- 機制相同、寫法不同收成同一動作詞,被動與主動、舊式與新式都收:「ゲームから除外」= 「除外」、
  「生け贄に捧げ」= 「リリース」(解放)、「墓地に送」= 「墓地へ送」(送墓)、「する事ができる」= 「できる」。
- 機制不同分開:捨てる ≠ 墓地へ送る、時 ≠ 場合、取對象 ≠ 選擇。
- 舊式「〜体を選択して」是取對象(標在對象線 `targeting`),不是動作詞「選擇」;新式「を対象として」同一機制。
- 原述語字面保留在段的 `predicate`,合併或拆開動作詞只改這裡的表、不重抽。
各舊式用語在官方 DB 文本上的出現次數見 `.scratch/action-structure/report/old_style_phrases.md`
(`stats/old_style_phrases.py` 可重跑)。
"""
from typing import NamedTuple

from structure_shape import VOICE_MIXED


class Predicate(NamedTuple):
    """一個述語拆回的格:動作詞、態、極性、述語本身寫明的終點、可選。"""
    action: str
    voice: str
    polarity: str
    to: str | None
    optional: bool


# ── 述語字面 → 動作詞;第三欄是述語本身寫明的終點(「墓地へ送る」「ゲームから除外する」)。
# 同一動作詞多個字面時,長的、舊式的排前面(startswith 逐一試,「生け贄に捧げ」不能被更短的字面先吃掉)。
PREDICATE_STEMS = (
    ("特殊召喚", "特殊召喚", None),
    ("融合召喚", "融合召喚", None),
    ("S召喚", "S召喚", None),
    ("X召喚", "X召喚", None),
    ("L召喚", "L召喚", None),
    ("見せ", "展示", None),
    ("破壊", "破壞", None),
    ("捨て", "捨棄", None),
    ("リリース", "解放", None),
    ("生け贄に捧げ", "解放", None),          # 舊式:生け贄に捧げる = リリース
    ("ゲームから除外", "除外", "除外"),      # 舊式:ゲームから除外する = 除外する
    ("除外", "除外", "除外"),
    ("墓地へ送", "送墓", "墓地"),
    ("墓地に送", "送墓", "墓地"),            # 舊式助詞 に
    ("手札に加え", "加入手牌", "手牌"),
    ("めく", "翻開", None),
    ("戻", "返回", None),
    ("発動", "發動", None),            # 効果を発動(卡片發動句的 発動できる 在句型層先剝掉)
    ("直接攻撃", "直接攻擊", None),
    ("になる", "性質變更", None),       # 性質變更句「〜攻撃力は〜になる」(票 08,segment_fields)
    ("装備", "裝備", None),             # 票 06:〜を装備魔法カード扱いで〜に装備できる
    ("払", "支付", None),               # 票 09:１０００LPを払って(段無物件,數量格)
    ("無効に", "無效", None),           # 票 09:その発動を無効にし破壊する(し 串接)
    ("通常召喚", "通常召喚", None),     # 票 09:召喚條件句「このカードは通常召喚できない」
    # m2 票 07:「Xと戦闘を行う」;語尾「う」不在 TAILS(加了會影響所有字幹),終止形整串收。
    ("戦闘を行う", "戰鬥", None),
    ("戦闘を行", "戰鬥", None),
)
MODIFY_ACTION = "性質變更"
MODIFY_PREDICATE = "になる"
# 動作回指(「めくったカード」「特殊召喚したモンスター」)用的過去形。
ACTION_PAST = {"翻開": "めくった", "特殊召喚": "特殊召喚した", "破壞": "破壊した",
               "除外": "除外した", "送墓": "墓地へ送った", "捨棄": "捨てた",
               "解放": "リリースした", "加入手牌": "手札に加えた", "返回": "戻した",
               "融合召喚": "融合召喚した", "S召喚": "S召喚した", "X召喚": "X召喚した",
               "L召喚": "L召喚した", "展示": "見せた", "發動": "発動した",
               "裝備": "装備した", "支付": "払った", "無效": "無効にした",
               "通常召喚": "通常召喚した"}
# 下位詞:S、X、L、融合召喚是特殊召喚的下位(spec「動作詞」),查「特殊召喚」要含它們;
# 推得表與角色也照上位詞算(票 07)。
ACTION_PARENT = {"融合召喚": "特殊召喚", "S召喚": "特殊召喚", "X召喚": "特殊召喚",
                 "L召喚": "特殊召喚"}


def action_ancestors(action):
    """動作詞與它的全部上位詞(含自己):融合召喚 → [融合召喚, 特殊召喚]。"""
    out = [action]
    while action in ACTION_PARENT:
        action = ACTION_PARENT[action]
        out.append(action)
    return out



# 述語語尾 → (態, 極性[, 可選])。語尾不在表內的述語標「述語語尾不明」,不猜。
# 「〜できる」「〜事ができる」「〜する事ができる」(舊式)都是可選的效果,極性仍是做(票 10 的決定)。
TAILS = {
    "": ("主動", "做"), "る": ("主動", "做"), "する": ("主動", "做"),
    "した": ("主動", "做"), "し": ("主動", "做"), "して": ("主動", "做"),
    "て": ("主動", "做"), "た": ("主動", "做"), "った": ("主動", "做"), "って": ("主動", "做"),
    "す": ("主動", "做"), "り": ("主動", "做"),   # 連用形串接「〜に戻り、」(票 08)
    "え": ("主動", "做"),                         # 連用形串接「〜手札に加え、」(票 06)
    "い": ("主動", "做"),                         # 連用形串接「〜LPを払い、」(票 09)
    "される": ("被動", "做"), "された": ("被動", "做"), "され": ("被動", "做"),
    "されて": ("被動", "做"),
    "られる": ("被動", "做"), "られた": ("被動", "做"), "られ": ("被動", "做"),
    "られて": ("被動", "做"),
    "に成功した": ("被動", "做"), "に成功する": ("被動", "做"),
    "できる": ("主動", "做", True), "る事ができる": ("主動", "做", True),
    "する事ができる": ("主動", "做", True), "事ができる": ("主動", "做", True),
    "す事ができる": ("主動", "做", True),    # 戻す事ができる
    "できない": ("主動", "不能"), "できず": ("主動", "不能"),
    "する事ができない": ("主動", "不能"), "る事ができない": ("主動", "不能"),
    "す事ができない": ("主動", "不能"),
    # 舊式「〜事はできない」= 「〜できない」
    "する事はできない": ("主動", "不能"), "る事はできない": ("主動", "不能"),
    "す事はできない": ("主動", "不能"),
    "しない": ("主動", "不會"), "されない": ("被動", "不會"),
    "られない": ("被動", "不會"),
    "なければならない": ("主動", "必須"),    # 舊式儀式卡「生け贄に捧げなければならない」
}
_TAILS_LONGEST_FIRST = sorted(TAILS, key=len, reverse=True)

# ── 取對象:述語前的字面(「Xを選択して破壊する」「Xを対象として発動できる」)。
# 舊式「選択して」與新式「対象として」同一機制;「以下の効果から１つを選択して」是分歧(票 06),
# 物件短語解析不出就不會標成取對象。
TARGETING_PREFIXES = ("選択して", "対象として")
# 指回取對象物件的回指字面(「選択したモンスター」;新式用「そのモンスター」)。
TARGET_REF = "選択した"
# 發動句語尾:舊式「発動する事ができる」= 「発動できる」。長的在前,正規式才不會先吃短的。
ACTIVATION_SUFFIXES = ("発動する事ができる", "発動できる", "発動する")
# 舊式代價句的接著詞:「(代價)る事で、(效果)」= 新式「(代價)て発動できる。(效果)」。
COST_GLUE = "事で"

REASON_PREDICATE = "述語解析不出"
REASON_TAIL = "述語語尾不明"
# 極性「只能」(票 09):述語前的「のみ〜できる」「しか〜できない」;字面留在原述語字面開頭。
ONLY_PREFIXES = ("のみ", "しか")
ONLY = "只能"
# 「Xしか〜できない」:「しか」寫在物件後、與述語之間可隔著從(EXデッキから),記成對象線的助詞(m2 票 03)。
ONLY_MARKER = "しか"


def split_targeting(pred):
    """述語字面 → (取對象字面或 None, 其餘述語)。「選択して破壊する」→ ("選択して", "破壊する");
    單獨的「選択して」(發動句的取對象宣告)→ ("選択して", "")。"""
    for prefix in TARGETING_PREFIXES:
        if pred.startswith(prefix):
            return prefix, pred[len(prefix):]
    return None, pred


def parse_predicate(pred):
    """述語字面 → (Predicate, None) 或 (None, 原因)。
    「のみ特殊召喚できる」「しか特殊召喚できない」→ 極性只能、不可選。"""
    for only in ONLY_PREFIXES:
        if pred.startswith(only):
            parsed, reason = parse_predicate(pred[len(only):])
            if parsed is None:
                return None, reason
            if (only, parsed.polarity, parsed.optional) not in (
                    ("のみ", "做", True), ("しか", "不能", False)):
                return None, REASON_TAIL
            return parsed._replace(polarity=ONLY, optional=False), None
    for stem, action, to in PREDICATE_STEMS:
        if pred.startswith(stem):
            tail = pred[len(stem):]
            if tail not in TAILS:
                return None, REASON_TAIL
            voice, polarity, *optional = TAILS[tail]
            return Predicate(action, voice, polarity, to, bool(optional and optional[0])), None
    return None, REASON_PREDICATE


def parse_predicates(pred):
    """て形串接的述語字面(めくられて墓地へ送られた)、連用形串接(無効にし破壊する)→
    ([Predicate], None) 或 (None, 原因)。單一述語也走這裡;串接時前面的語尾必須是
    て/で 或連用形的「し」。"""
    parsed, reason = parse_predicate(pred)
    if parsed is not None:
        return [parsed], None
    for stem, action, to in PREDICATE_STEMS:
        if not pred.startswith(stem):
            continue
        rest = pred[len(stem):]
        for tail in _TAILS_LONGEST_FIRST:
            if tail and (tail.endswith(("て", "で")) or tail == "し") \
                    and rest.startswith(tail) and len(rest) > len(tail):
                following, reason = parse_predicates(rest[len(tail):])
                if following is not None:
                    voice, polarity, *optional = TAILS[tail]
                    head = Predicate(action, voice, polarity, to, bool(optional and optional[0]))
                    return [head] + following, None
        return None, REASON_TAIL
    return None, reason


def merged_voice(parsed):
    """串接的多個述語的態:全部相同就是那個態,不同是「混合」;沒有述語(取對象宣告)是 None。
    抽取與反向檢查共用這一把尺。"""
    voices = {p.voice for p in parsed}
    if len(voices) == 1:
        return voices.pop()
    return VOICE_MIXED if voices else None

