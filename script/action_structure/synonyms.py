"""同義表:述語字面 → 動作詞、語尾 → 態與極性、取對象的字面(舊式「選択して」、新式「対象として」)。

收法(spec「段」、票 11):
- 機制相同、寫法不同收成同一動作詞,被動與主動、舊式與新式都收:「ゲームから除外」= 「除外」、
  「生け贄に捧げ」= 「リリース」(解放)、「墓地に送」= 「墓地へ送」(送墓)、「する事ができる」= 「できる」。
- 機制不同分開:捨てる ≠ 墓地へ送る、時 ≠ 場合、取對象 ≠ 選擇。
- 舊式「〜体を選択して」是取對象(標在對象線 `targeting`),不是動作詞「選擇」;新式「を対象として」同一機制。
- 原述語字面保留在段的 `predicate`,合併或拆開動作詞只改這裡的表、不重抽。
- 抗性與限制(m2 票 04)用既有動作詞加極性:受到效果影響、攻擊家族(攻擊 > 直接攻擊、多次攻擊、
  全體攻擊;次數與「全てに１回ずつ」寫在述語「攻撃」前,`attack_times`)、選為攻擊對象、取對象
  (只有非「做」的語尾)、作為素材、變更表示形式、變更控制權;「無効化」= 無效。
各舊式用語在官方 DB 文本上的出現次數見 `.scratch/action-structure/report/old_style_phrases.md`
(`stats/old_style_phrases.py` 可重跑)。
"""
import re
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
    # m2 票 12:「Xモンスター１体のX召喚を行う」(物件 + 助詞「の」;述語含「を」,`PREDICATE_NOUNS`)。
    # 語尾「う」不在 TAILS,終止形整串收(同「戦闘を行う」)。
    *((f"{kind}を行う", kind, None) for kind in ("融合召喚", "S召喚", "X召喚", "L召喚")),
    *((f"{kind}を行", kind, None) for kind in ("融合召喚", "S召喚", "X召喚", "L召喚")),
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
    ("効果を受け", "受到效果影響", None),   # m2 票 04:「〜の効果を受けない」(原因帶誰的效果)
    ("効果の対象に", "取對象", None),       # m2 票 04:只在非「做」(〜の対象にならない)
    # m2 票 04:作為素材(「シンクロ素材にできない」;哪種召喚的素材留在原述語字面)。
    ("融合素材に", "作為素材", None), ("シンクロ素材に", "作為素材", None),
    ("S素材に", "作為素材", None), ("エクシーズ素材に", "作為素材", None),
    ("X素材に", "作為素材", None), ("リンク素材に", "作為素材", None),
    ("L素材に", "作為素材", None), ("素材に", "作為素材", None),
    # m2 票 04:「(Xの)表示形式を変更できない」「(Xの)コントロールは変更できない」。
    ("表示形式を変更", "變更表示形式", None), ("表示形式は変更", "變更表示形式", None),
    ("コントロールを変更", "變更控制權", None), ("コントロールは変更", "變更控制權", None),
    # m2 票 04:攻擊家族。長的字面在前(「攻撃対象に選択」「攻撃宣言」不能被「攻撃」先吃掉);
    # 「攻撃をする」的を是述語的一部分(句型層 `PREDICATE_NOUNS`)。
    ("攻撃対象に選択", "選為攻擊對象", None),
    ("攻撃宣言", "攻擊", None),
    ("攻撃を", "攻擊", None),
    ("攻撃", "攻擊", None),
    ("になる", "性質變更", None),       # 性質變更句「〜攻撃力は〜になる」(票 08,segment_fields)
    # m2 票 08:增減「〜攻撃力は３００アップする」(句型在 segment_fields;一般子句的受詞是屬性名詞,
    # 物件解析不出);未解析組的字面比對也用這兩個字幹。
    ("アップ", "性質變更", None),
    ("ダウン", "性質變更", None),
    ("装備", "裝備", None),             # 票 06:〜を装備魔法カード扱いで〜に装備できる
    ("払", "支付", None),               # 票 09:１０００LPを払って(段無物件,數量格)
    ("無効化", "無效", None),           # m2 票 04:「無効化されない」併進無效
    ("無効に", "無效", None),           # 票 09:その発動を無効にし破壊する(し 串接)
    ("通常召喚", "通常召喚", None),     # 票 09:召喚條件句「このカードは通常召喚できない」
    # m2 票 06:傷害(与える/受ける 同一詞)、回復。「ダメージを」接在字幹裡:一般子句的述語不含を,
    # 只有 damage 的句型會產生傷害段;未解析組的字面比對也用這兩個字幹。
    ("ダメージを与え", "傷害", None),
    ("ダメージを受け", "傷害", None),
    ("回復", "回復", None),
    # m2 票 07:「Xと戦闘を行う」;語尾「う」不在 TAILS(加了會影響所有字幹),終止形整串收。
    ("戦闘を行う", "戰鬥", None),
    ("戦闘を行", "戰鬥", None),
    # m2 票 05:「置」單字當字幹會讓未解析組比中「位置」「配置」,所以連語尾一起寫。
    ("置く", "放置", None),
    ("置き", "放置", None),             # 連用形串接「〜に表側表示で置き、」
    ("置い", "放置", None),             # 置いて、置いた
    ("セット", "覆蓋", None),
    # m2 票 11:去除(取り除く)。字幹連語尾一起寫(同 置く);被動「取り除かれた」的語尾 れた/れる。
    ("取り除く", "去除", None),
    ("取り除き", "去除", None),         # 連用形串接「〜を１つ取り除き、」
    ("取り除い", "去除", None),         # 取り除いて、取り除いた
    ("取り除か", "去除", None),         # 取り除かれた、取り除かれる
    # m2 票 10:抽牌(「通常のドローをした」的を接在字幹裡);「ドローフェイズ」是階段字面,
    # 查詢未解析組比字面時扣掉(STEM_FALSE_FRIENDS)。自動詞「手札に加わ」併進加入手牌。
    ("ドローを", "抽牌", None),
    ("ドロー", "抽牌", None),
    ("手札に加わ", "加入手牌", "手牌"),
)
# 字幹出現在別的詞裡、不是那個動作的字面(查詢未解析組比字面時扣掉;m2 票 04)。
STEM_FALSE_FRIENDS = {"攻撃": ("攻撃力", "攻撃表示", "攻撃対象"), "ドロー": ("ドローフェイズ",)}
MODIFY_ACTION = "性質變更"
MODIFY_PREDICATE = "になる"
# 動作回指(「めくったカード」「特殊召喚したモンスター」)用的過去形。
ACTION_PAST = {"翻開": "めくった", "特殊召喚": "特殊召喚した", "破壞": "破壊した",
               "除外": "除外した", "送墓": "墓地へ送った", "捨棄": "捨てた",
               "解放": "リリースした", "加入手牌": "手札に加えた", "返回": "戻した",
               "融合召喚": "融合召喚した", "S召喚": "S召喚した", "X召喚": "X召喚した",
               "L召喚": "L召喚した", "展示": "見せた", "發動": "発動した",
               "裝備": "装備した", "支付": "払った", "無效": "無効にした",
               "通常召喚": "通常召喚した", "放置": "置いた", "覆蓋": "セットした",
               "去除": "取り除いた", "抽牌": "ドローした"}
# 下位詞:S、X、L、融合召喚是特殊召喚的下位(spec「動作詞」),查「特殊召喚」要含它們;
# 推得表與角色也照上位詞算(票 07)。
ACTION_PARENT = {"融合召喚": "特殊召喚", "S召喚": "特殊召喚", "X召喚": "特殊召喚",
                 "L召喚": "特殊召喚",
                 # m2 票 04:攻擊 > 直接攻擊、多次攻擊、全體攻擊(spec「攻擊系只做兩層夠嗎?」)
                 "直接攻擊": "攻擊", "多次攻擊": "攻擊", "全體攻擊": "攻擊"}
ATTACK = "攻擊"
MULTIPLE_ATTACK = "多次攻擊"
ALL_ATTACK = "全體攻擊"
ATTACK_FAMILY = (ATTACK, "直接攻擊", MULTIPLE_ATTACK, ALL_ATTACK)


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
    "れた": ("被動", "做"), "れる": ("被動", "做"),   # m2 票 11:取り除かれた
    "に成功した": ("被動", "做"), "に成功する": ("被動", "做"),
    "できる": ("主動", "做", True), "る事ができる": ("主動", "做", True),
    "する事ができる": ("主動", "做", True), "事ができる": ("主動", "做", True),
    "す事ができる": ("主動", "做", True),    # 戻す事ができる
    "できない": ("主動", "不能"), "できず": ("主動", "不能"),
    "する事ができない": ("主動", "不能"), "る事ができない": ("主動", "不能"),
    "す事ができない": ("主動", "不能"),
    # m2 票 10:「手札に加える事ができず、」(連用形串接的不能)。
    "る事ができず": ("主動", "不能"), "する事ができず": ("主動", "不能"),
    "す事ができず": ("主動", "不能"),
    # 舊式「〜事はできない」= 「〜できない」
    "する事はできない": ("主動", "不能"), "る事はできない": ("主動", "不能"),
    "す事はできない": ("主動", "不能"),
    "しない": ("主動", "不會"), "されない": ("被動", "不會"),
    "られない": ("被動", "不會"),
    "なければならない": ("主動", "必須"),    # 舊式儀式卡「生け贄に捧げなければならない」
    "が可能": ("主動", "做", True),
    # m2 票 04:「効果を受けない/受けず」「効果の対象にならない/ならず」
    "ない": ("主動", "不會"), "ず": ("主動", "不會"),
    "ならない": ("主動", "不會"), "ならず": ("主動", "不會"),
    "されず": ("被動", "不會"), "られず": ("被動", "不會"),   # 「効果では破壊されず、〜」          # 舊式「攻撃が可能」「特殊召喚が可能」= できる(m2 票 04)
}
_TAILS_LONGEST_FIRST = sorted(TAILS, key=len, reverse=True)

# ── 取對象:述語前的字面(「Xを選択して破壊する」「Xを対象として発動できる」)。
# 舊式「選択して」與新式「対象として」同一機制;「以下の効果から１つを選択して」是分歧(票 06),
# 物件短語解析不出就不會標成取對象。
TARGETING_PREFIXES = ("選択して", "対象として")
# 指回取對象物件的回指字面(「選択したモンスター」;新式用「そのモンスター」,或「対象のモンスター」,
# m2 票 12:「〜を対象として発動できる。〜を対象のモンスターに装備する」)。
TARGET_REF = "(?:選択した|対象の)"
# 發動句語尾:舊式「発動する事ができる」= 「発動できる」。長的在前,正規式才不會先吃短的。
# 「自分メインフェイズにこの効果を発動できる」「〜を対象としてこの効果を発動できる」的「この効果を」
# 是語尾的一部分(m2 票 09),不是代價子句;「〜を対象としてこのカードを発動できる」(魔陷卡的發動,
# m2 票 08)的「このカードを」也屬於語尾。
ACTIVATION_SUFFIXES = ("この効果を発動する事ができる", "この効果を発動できる", "この効果を発動する",
                       "このカードを発動できる", "発動する事ができる", "発動できる", "発動する")
# 舊式代價句的接著詞:「(代價)る事で、(效果)」= 新式「(代價)て発動できる。(效果)」。
COST_GLUE = "事で"

REASON_PREDICATE = "述語解析不出"
REASON_TAIL = "述語語尾不明"
# 極性「只能」(票 09):述語前的「のみ〜できる」「しか〜できない」;字面留在原述語字面開頭。
ONLY_PREFIXES = ("のみ", "しか")
ONLY = "只能"
# 「Xしか〜できない」:「しか」寫在物件後、與述語之間可隔著從(EXデッキから),記成對象線的助詞(m2 票 03)。
ONLY_MARKER = "しか"


# 「選んで」(m2 票 09):照取對象字面的拆法留在原述語字面開頭(「選んで破壊する」),但不標取對象、
# 不是動作詞;物件照常走新建/子集/剩餘。單獨的「選んで」(「デッキから〜１枚を選んで発動する」的
# 代價子句)是沒有動作詞的選取宣告。
SELECT_PREFIX = "選んで"


def split_select(pred):
    """述語字面 → (選取字面或 None, 其餘述語)。「選んで破壊する」→ ("選んで", "破壊する")。"""
    if pred.startswith(SELECT_PREFIX):
        return SELECT_PREFIX, pred[len(SELECT_PREFIX):]
    return None, pred
# 攻擊的下位詞寫在述語「攻撃」前面的字面(m2 票 04,閉集):次數 → 多次攻擊(段的 `times`,
# 「もう１度」是第二次攻擊,記 2);「相手モンスター全てに１回ずつ」→ 全體攻擊。字面留在原述語字面裡,
# 反向檢查照 `attack_times` 驗段的 `times`。
TIMES_PATTERN = ("(?:１度のバトルフェイズ中に|そのターンのバトルフェイズ中に|バトルフェイズ中に?"
                 "|１ターンに)?(?P<n>[２-９])回|もう１度(?:だけ)?(?:続けて)?")
ALL_ATTACK_PATTERN = ("(?:相手モンスター全てに|相手フィールド(?:上に存在する|上の|の)全ての"
                      "モンスターに)１回ずつ")
_ATTACK_PREFIX_RE = re.compile(
    f"^(?:(?P<times>{TIMES_PATTERN})|(?P<all>{ALL_ATTACK_PATTERN}))(?=攻撃)")
# 給句型正規式嵌進述語槽用(不帶具名群組)。
ATTACK_PREFIX_PATTERN = re.sub(r"\(\?P<\w+>", "(?:",
                               f"(?:{TIMES_PATTERN}|{ALL_ATTACK_PATTERN})(?=攻撃)")
# 述語本身含「を/は」的動作(m2 票 04):句型的述語槽不收「を」,這幾個「名詞+を/は」字面例外,
# 寫在述語開頭(攻撃をする、効果を受けない、表示形式を変更、コントロールは変更)。
# m2 票 12 加「X召喚を」等(「Xモンスター１体のX召喚を行う」)。
SUMMON_NOUNS = ("融合召喚を", "S召喚を", "X召喚を", "L召喚を")
PREDICATE_NOUNS = ("攻撃を", "効果を", "表示形式を", "表示形式は", "コントロールを",
                   "コントロールは") + SUMMON_NOUNS
PREDICATE_NOUN_PATTERN = "|".join(PREDICATE_NOUNS)
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def attack_times(pred):
    """原述語字面開頭的攻擊次數 → `times` 格 {"value", "text"};沒有回 None。"""
    m = _ATTACK_PREFIX_RE.match(pred or "")
    if not m or not m.group("times"):
        return None
    value = int(m.group("n").translate(_FULLWIDTH_DIGITS)) if m.group("n") else 2
    return {"value": value, "text": m.group("times")}


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
    prefix = _ATTACK_PREFIX_RE.match(pred)
    if prefix:
        parsed, reason = parse_predicate(pred[prefix.end():])
        if parsed is None:
            return None, reason
        if parsed.action != ATTACK:
            return None, REASON_TAIL
        return parsed._replace(
            action=MULTIPLE_ATTACK if prefix.group("times") else ALL_ATTACK), None
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

