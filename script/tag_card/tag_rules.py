"""效果 Tag 規則層的規則登記處(ADR-0013:直接寫入,非影子預測)。

一條規則是一筆資料:編號、類別、掃描範圍、判別條件(人話 + 樣式)、發出的
tag(槽位中文值,`pos` 由掃描範圍決定)、新增票號、遮蔽測試成績。與效果類型
規則層(`rules.py`)的根本差異:tag 沒有[[官方明示]]可對照,所以規則**直接寫入**
`tags`(tag 標 `src: "rule"`),敘用前提是遮蔽測試門檻(錯標 0、recall ≥ 90%、
分母 ≥ 8)+ 首批人工抽驗(.scratch/effect-tag/rulings.md 批4 定案)。

**掃描範圍**是本模組的骨幹,三種:

- 「處理」—— 效果句的處理段(發動子句之後的文字;無發動子句時是整句)。
  發出的 tag `pos: "效果"`。觸發條件(「〜が特殊召喚された場合」)住在發動
  子句裡,處理段規則因此天然咬不到它——這是直貼精度的第一道結構保證。
- 「成本」—— 發動子句(含「発動」時才掃)。發出的 tag `pos: "成本"`。
- 「時機」—— 發動子句,產出的是[[觸發時機]]單值而不是 tag;同句多個時機取
  **最先寫出的**(裁定批4)。

文字的切段(發動子句/處理段)由 tagcard 那一側算好傳進來——切句是管線的
本行,規則層只認樣式。

貼標範圍(第一期):新式卡文效果句(index 帶①編號、kind 非效果外文本)。
分期推進由 PHASES 登記——只有已開貼類別的規則會上工,seal 的「零空缺」也
只問已開貼的類別。

詞彙見 CONTEXT.md:效果 Tag、動作類別、槽位、觸發時機。
"""
import hashlib
import re

# ── 槽位中文值(與 script/web/vocab.py 的 tag 值域同一套字面;索引建置與
#    tag seal 會驗「tags 值全在正典」,寫錯字建置就倒)──
CAT_MOVE = "區域移動"
CAT_DRAW = "抽牌/手牌交換"
CAT_NEGATE = "無效"
CAT_DESTROY = "破壞"
CAT_RESTRICT = "行動限制"
CAT_PROTECT = "耐性/保護"
CAT_STAT = "攻守調整"
CAT_DAMAGE = "效果傷害"
CAT_HEAL = "生命回復"
CAT_LP_PAY = "LP支付"
CAT_LP_LOSE = "LP失去"
CAT_POSITION = "表示形式變更"
CAT_CONTROL = "控制權轉移"
CAT_PROPERTY = "性質變更"
CAT_COUNTER = "計數器操作"
CAT_TRANSFORM = "放置轉換"
CAT_SUBSTITUTE = "素材代用/召喚放寬"
CAT_SUMMON_EXEC = "召喚執行"
CAT_BATTLE = "戰鬥規則"
CAT_INFO = "情報操作"
CAT_MISC = "其他"

ZONE_HAND = "手牌"
ZONE_DECK = "牌組"
ZONE_EXTRA = "額外牌組"
ZONE_GRAVE = "墓地"
ZONE_BANISH = "除外"
ZONE_FIELD = "場上"
ZONE_PZONE = "靈擺區"

POS_COST = "成本"
POS_EFFECT = "效果"
# 位置豁免類別(vocab.TAG_POS_EXEMPT 的中文面,裁定票15):正典沒有 pos
# 槽位。兩邊漂移時建置會倒在「宣告外的槽位」,不會無聲
_POS_EXEMPT_CATS = frozenset({CAT_LP_PAY})
SIDE_SELF = "自身"
SIDE_OWN = "我方"
SIDE_OPP = "對手"
SIDE_BOTH = "雙方"

TAG_SRC_RULE = "rule"
TAG_SRC_LLM = "llm"
TAG_SRC_LLM_THEN_RULE = "llm_then_rule"
TAG_SRC_MANUAL = "manual"
# 重跑時保留的 tag 來源(rule 不在其中:規則 tag 是當前規則對當前文本的純函式
# 輸出,每次重算,ADR-0013)
TAG_PRESERVED_SRC = (TAG_SRC_LLM, TAG_SRC_LLM_THEN_RULE, TAG_SRC_MANUAL)

SCOPE_PROCESS = "處理"
SCOPE_COST = "成本"
# 「對象」範圍:起點寫在發動子句的對象指定裡(「墓地の…を対象として発動できる」)
# 、動作寫在處理段的指示詞上(「そのモンスターを特殊召喚する」)。pattern 掃
# 發動子句、action 掃處理段,兩者都命中才開火;pos 一律「效果」——對象指定
# 不是代價。
SCOPE_TARGET = "對象"
SCOPES = (SCOPE_PROCESS, SCOPE_COST, SCOPE_TARGET)

# 分期開貼登記:類別 → 期次。只有登記了的類別規則會上工、出票、進 seal 的
# 零空缺檢查。第二期起照 .scratch/effect-tag/phase-plan.md 增列。
PHASES = {
    CAT_MOVE: "第1期",
    CAT_DESTROY: "第2期",
    CAT_NEGATE: "第2期",
    CAT_STAT: "第3期",
    CAT_DAMAGE: "第3期",
    CAT_HEAL: "第3期",
    CAT_LP_PAY: "第3期",
    CAT_LP_LOSE: "第3期",
    CAT_RESTRICT: "第4期",
    CAT_PROTECT: "第4期",
    CAT_POSITION: "第5期",
    CAT_CONTROL: "第5期",
    CAT_PROPERTY: "第5期",
    CAT_COUNTER: "第5期",
}

# 遮蔽測試門檻(rulings.md 批4)
MASKED_MAX_WRONG = 0
MASKED_MIN_RECALL = 0.90
MASKED_MIN_HITS = 8

_ID_RE = re.compile(r"^T[1-9][0-9]*$")

# 否定/耐性形:動作動詞後面跟的是「不能/不會」,不是動作(歸行動限制/耐性)
_NEG = r"できない|できず|されない|の対象にならない|扱わない|事はできない"

# 區域詞(span 防護用):起點詞與動詞之間插進另一個區域詞,代表句子換了話題
# (「墓地のモンスターを除外して、デッキから特殊召喚」),規則不得跨過去配對。
_Z = r"手札|デッキ|墓地|除外|フィールド|Pゾーン|EXデッキ|エクストラ"


# 動作動詞(span 防護用):起點與動詞之間出現另一個動作動詞,代表句子已換謂語
# (「手札から特殊召喚し、対象のモンスターを除外する」不得配成 手牌→除外)
_VERBS = r"特殊召喚|セット|リリース|捨て|ドロー|加え|戻[すし]|置[くき]"


def _sp(limit=70):
    """起點詞與動詞之間的安全 span:不含句號、其他區域詞與動作動詞。"""
    return r"(?:(?!(?:%s|%s))[^。]){0,%d}?" % (_Z, _VERBS, limit)


# 終點是場上/靈擺區的動詞(特殊召喚/セット/Pゾーンに置く)常在動詞前寫出終點
# (「相手フィールドに特殊召喚」「自分フィールドにセット」),span 因此放行
# フィールド與Pゾーン,只擋另一批起點詞。
_Z_SRC = r"手札|デッキ|墓地|除外|EXデッキ|エクストラ"


def _sp_f(limit=70):
    return (r"(?:(?!(?:%s|%s))[^。]){0,%d}?"
            % (_Z_SRC, r"セット|リリース|捨て|ドロー|加え|戻[すし]|置[くき]",
               limit))


# 動詞形(動作形限定;完成式條件「〜した場合」與否定形不算動作)
_V_SS = r"特殊召喚(する(?!事(は|が|も)?でき(ない|ず)|効果|度|場合)|できる|し、|し。)"
_V_ADD = r"手札に加え(?!る事(は|が|も)?でき(ない|ず)|る効果|る場合|られ)"
_V_SEND = r"墓地へ送(る(?!事(は|が|も)?でき(ない|ず)|効果|場合)|り|って)"
_V_RET_HAND = r"手札に戻(す(?!事(は|が|も)?でき(ない|ず)|場合)|し)"
_V_RET_DECK = r"(?<!EX)(?<!ラ)デッキに戻(す(?!事(は|が|も)?でき(ない|ず)|場合)|し)"
_V_RET_EXTRA = r"(EXデッキ|エクストラデッキ)に戻(す(?!事(は|が|も)?でき(ない|ず))|し)"
_V_BANISH = r"除外(する(?!事(は|が|も)?でき(ない|ず)|効果|場合)|し、|できる)"
_V_SET = r"セット(する(?!事(は|が|も)?でき(ない|ず)|効果|場合)|できる|し、|し。)"

# ── 第2期(票16):破壞/無效的動詞形與排除 ──
# 破壞動作形:完成式(破壊した=觸發)、被動(破壊され=狀態/耐性)、條件
# (破壊する場合)、描述(破壊する効果)都不算動作。
_V_DS = (r"破壊(する(?!事(は|が|も)?でき(ない|ず)|効果|場合|モンスター|カード)"
         r"|し、|し。|できる)")
# 「代わりに破壊」=代替破壞歸耐性,破壞規則與粗篩讓路(裁定批2);
# 「リリースの代わりに破壊」是儀式召喚的代價替代,是真破壞動作,不排除。
# 「無効にし破壊」不排除:附帶處置也是動作(第一期 mv 對附帶除外的先例),
# 無效帶 extra 槽位、破壞照貼(T127)。
_DS_EXCLUDE = r"(?<!リリースの)代わりに[^。]{0,30}?破壊|破壊する効果"
# 「無効化されない/無効にされない」=耐性,不是無效動作。
_NG_EXCLUDE = (r"無効化され(ない|ず)|無効に(され|でき)(ない|ず)"
               r"|無効にならない")

# 破壞/無效的槽位中文值
DS_MONSTER = "怪獸"
DS_SPELLTRAP = "魔陷"
DS_CARD = "卡"
RANGE_ONE = "單體"
RANGE_MULT = "複數"
RANGE_ALL = "全體"
NG_ACTIVATION = "發動"
NG_EFFECT = "效果"
NG_CONTINUOUS = "持續無效化"
NG_X_DESTROY = "破壞"
NG_X_BANISH = "除外"

# ── 第3期(票17):數值向五類的動詞形、主語錨與槽位值 ──
# 攻守調整的槽位中文值
ST_ATK = "攻擊"
ST_DEF = "守備"
ST_BOTH = "攻守"
DIR_UP = "上升"
DIR_DOWN = "下降"
DIR_BECOME = "變成"
FORM_FIXED = "固定值"
FORM_REF = "參照值"
FORM_RATIO = "比例"

# 主語錨:項目名+主語粒子。合記「攻撃力・守備力」由專屬規則發攻守,單獨規則
# 以負向斷言擋在合記裡誤配半邊(攻撃力後跟「・」不是粒子,天然不配;守備力
# 要擋「・守備力は」)。「攻撃力２０００アップの装備〜扱い」修飾形無主語粒子,
# 天然不配(修飾非動作,票17 裁定)。
_ST_A = r"攻撃力(?!・)[はがを]"
_ST_D = r"(?<!・)守備力[はがを]"
_ST_W = r"攻撃力・守備力[はがを]"
# 主語與動詞之間不得跨過另一個攻守動詞(「攻撃力は…アップし、守備力は…
# ダウン」不得配成 攻擊×下降);參照詞(「元々の攻撃力分アップ」)不是動詞、
# 「リンク状態になっている」的「になっ」也不是(擋的是 になる/になり),
# 都放行。
_ST_SP = r"(?:(?!(?:アップ|ダウン|にな[るり]|にす|入れ替))[^。]){0,60}?"
# 動作形限定:完成式(した)、否定(できない)、條件(する場合)、描述
# (する効果)、觸發(する度)都不算動作
_V_UP = r"アップ(する(?!事(は|が|も)?でき|効果|場合|度)|し、|し。|できる)"
_V_DOWN = r"ダウン(する(?!事(は|が|も)?でき|効果|場合|度)|し、|し。|できる)"
# 「になる」與「を…にする」都是變成(裁定批3:倍化/減半/變0/指定值一律
# 變成)。二形各綁各的主語粒子:「は/が」只接になる、「を」只接にする——
# 混用會讓參照句(「…の守備力を合計した数値になる」)與能力動詞(「効果を
# 無効にできる」)冒充主語錨。
_V_BEC_NARU = r"にな(る(?!事(は|が|も)?でき|場合|度)|り、|り。)"
_V_BEC_SURU = r"(にする(?!事(は|が|も)?でき|場合)|にし、|にし。|にできる)"


def _st_become(item):
    """攻守「變成」樣式:主語錨(は/が × になる、を × にする)二形合一。"""
    return (r"(%s[はが]%s%s|%sを%s%s)"
            % (item, _ST_SP, _V_BEC_NARU, item, _ST_SP, _V_BEC_SURU))

# 效果傷害/生命回復的動作形(「与えた」完成式、「与える度」觸發、「与える
# 効果/魔法/モンスター」修飾描述都不算)。(?<!戦闘) 擋戰鬥傷害:貫通句
# (「超えた分だけ戦闘ダメージを与える」)歸戰鬥規則、修飾歸「其他」,
# 都不是效果傷害(批3)。
_V_DEAL = (r"(?<!戦闘)ダメージを与え(る(?!事(は|が|も)?でき|効果|場合|度"
           r"|モンスター|魔法|罠|カード)|、|。)")
_V_TAKE = (r"(?<!戦闘)ダメージを受け(る(?!事(は|が|も)?でき|効果|場合|度"
           r"|ダメージ計算)|、|。)")
_V_HEAL = r"回復(する(?!事(は|が|も)?でき|効果|場合|度)|し、|し。|できる)"
_LP = r"(?:LP|ＬＰ)"
# 數值形:固定值的數字前不得是 ×/數字(「数×１００ダメージ」是參照值)
_NO_MUL = r"(?<![×Ｘ×ｘ０-９])"
_S_HAND = r"(?<!・)手札[かの]ら?"
_S_DECK = r"(?<!・)(?<!EX)(?<!ラ)デッキから"
_S_EXTRA = r"(EXデッキ|エクストラデッキ)から"
_S_GRAVE = r"(?<!・)墓地[のか]"
_S_BANISHED = r"((?<!・)(?<!び)除外されている|(?<!・)除外状態の)"
_S_FIELD = r"(?<!・)フィールドの"

# ── 第4期(票18):行動限制/耐性・保護 的否定形與槽位值 ──
RS_SP = "特殊召喚"
RS_ACT = "發動效果"
RS_ATK = "攻擊"
RS_POS = "表示形式"
RS_X = "其他"
TERM_CONT = "持續"
TERM_TURN = "單回合"
PT_BD = "戰鬥破壞"
PT_ED = "效果破壞"
PT_TG = "效果對象"
PT_BN = "除外"
PT_AE = "全效果"
PT_RP = "代替破壞"

# ── 第5期(票19):狀態向四類的槽位值與動詞形 ──
PS_ATK = "攻擊表示"
PS_DEF = "守備表示"
PS_FD = "裡側表示"
CT_GET = "取得"
CT_GIVE = "移交"
PP_NAME = "卡名"
PP_RACE = "種族"
PP_ATTR = "屬性"
PP_LV = "等級"
PP_RK = "階級"
PP_SC = "刻度"
CNT_PUT = "放置"
CNT_RM = "去除"

# 表示變更動詞形:「〜表示にする/になる」。「守備表示で特殊召喚」是召喚時
# 表示指定(で 粒子),「守備表示になった」完成形是觸發、「にした」是修飾,
# 都天然不配(票19)。
_V_PS = (r"に(する(?!事(は|が|も)?でき|効果|場合)|し、|し。|できる"
         r"|な(る(?!事(は|が|も)?でき|場合)|り、|り。))")
# 「として扱う」動作形:「扱う」須止於標點——「として扱う通常モンスター」
# 修飾形後接名詞被邊界擋下;「扱う事ができる」是動作(素材時代稱等)。
_V_TREAT = (r"として(も)?扱(う(?=[。、）（]|$)|い、|い。"
            r"|う事ができ(る(?=[。、）（]|$)|、))")
# 性質「になる/にする」動作形(は/が × になる、を × にする,攻守二形
# 同構,票17)
_V_PP_NARU = r"にな(る(?!事(は|が|も)?でき|場合)|り、|り。)"
_V_PP_SURU = r"に(する(?!事(は|が|も)?でき|場合)|し、|し。|でき)"

# 否定動詞尾:「できない」須止於標點——「通常召喚できないモンスター」
# 「通常召喚できない「E・HERO」」修飾形後接名詞或卡名引號、「除外できない
# 場合」程序條件都被邊界擋下;「できなくなる」也是限制。されない 家族
# (耐性)同一套邊界。
_CANT = (r"(する事)?[はがも]?でき(ない(?=[。、）（]|$)|ず(?=[、。])"
         r"|なくな)")
_NOT = r"(ない(?=[。、）（]|$)|ず(?=[、。])|なくな)"
# 特殊召喚面的動詞:召喚法特定形(S/X/リンク/融合/儀式/P)歸特殊召喚,
# 與時機 TM2 同構(票18 裁定)。
_V_RS_SS = r"(特殊召喚|(S|X|リンク|融合|儀式|P)召喚)" + _CANT
# 發動限制的受詞名詞(「罠カードを１枚しか発動できない」的 カード 面);
# 「発動・セットできない」複合動詞的發動面照咬
_V_ACT_TAIL = r"発動(・セット)?" + _CANT
_V_RS_ACT = r"(効果|カード|罠|魔法)[をはも][^。]{0,14}?" + _V_ACT_TAIL
# 攻擊限制:直接攻撃歸戰鬥規則(批2);「攻撃対象に選択できない」的 攻撃 後
# 接 対象,天然不配。
_V_RS_ATK = r"(?<!直接)攻撃(宣言)?" + _CANT
# 「この効果は…発動できない」是自我使用條件、「このカードの発動は…にしか
# 発動できない」是發動時點條件,都不是限制動作;「この効果の発動に対して
# 相手は…発動できない」(の形)是真限制,不擋。
_RS_ACT_EXCLUDE = (r"この効果は[^。]{0,45}?発動でき(ない|ず)"
                   r"|このカード名の[^。]{0,60}?発動でき(ない|ず)"
                   r"|の発動は[^。]{0,30}?発動でき(ない|ず)")
# 單回合/持續的期間錨(票18:「次の/相手/自分ターン(の)終了時まで」等
# 跨回合形留空——照句內錨形填,機器可判的形式面切分)
# 「このターンに特殊召喚された」是對象修飾非期間,(?!に) 擋掉
_TERM_TURN_ANCHOR = (r"(このターン(?!に)|そのターン(?!に)"
                     r"|(?<!の)(?<!手)(?<!分)ターン終了時まで"
                     r"|発動(する|した)ターン)")


# 指示詞動作(對象範圍的處理段那一半)
def _anaphora(verb, limit=30):
    """指示詞要**名詞緊接、且短距內帶を**:「その後、…除外する」「対象の
    モンスターと同じ属性を持つ…」這類假指示詞(その後/對象的屬性描述)
    不得當成動作的受詞(遮蔽補抽 36016907 / 9251497)。「墓地の対象の…」
    的対象另有所指,負向後看擋掉。"""
    return (r"(その|それらの|(?<!の)対象の)(カード|モンスター)"
            r"[^。、を]{0,4}を"
            r"(?:(?!(?:%s|%s))[^。]){0,%d}?%s" % (_Z, _VERBS, limit, verb))


def _anaphora_f(verb, limit=30):
    """終點是場上的指示詞動作(「そのカードを自分フィールドにセットする」)。"""
    return (r"(その|それらの|(?<!の)対象の)(カード|モンスター)"
            r"[^。、を]{0,4}を"
            r"(?:(?!(?:%s))[^。]){0,%d}?%s" % (_Z_SRC, limit, verb))


def define(rid, cat, scope, condition, pattern, tag, ticket, exclude=None,
           action=None):
    """一條 tag 規則。tag 是發出的槽位值(單一 dict 或多個 dict 的序列——複合
    起點「手札・墓地から」一次發兩個 tag);不含 cat / pos / src,三者由框架補。

    pattern / exclude 掃**同一個切段**(處理段或發動子句):排除條件擋的是段內
    的反證(否定形、混合起點),掃整句會把住在發動子句裡的觸發事件也算成反證,
    規則就永遠不開火了。「對象」範圍的規則另帶 action(掃處理段的指示詞動作),
    pattern 掃的是發動子句的對象指定。
    """
    tags = (tag,) if isinstance(tag, dict) else tuple(tag)
    return {
        "id": rid,
        "cat": cat,
        "scope": scope,
        "condition": condition,
        "ticket": ticket,
        "pattern": re.compile(pattern),
        "exclude": re.compile(exclude) if exclude else None,
        "action": re.compile(action) if action else None,
        "tags": tuple(dict(t) for t in tags),
    }


# 本批規則由票07/票10 從語料歸納(附錄計數見 rulings.md),每一條都以 200 句
# 遮蔽樣本驗證(docs/effect_tag_rules.md 的遮蔽測試一節)。判別條件一律看日文
# 原文,理由同效果類型規則層(繁中譯文經過翻譯會失真)。
#
# 同一句發出的 tag 走**內容吸收**(`match_tags`):泛用規則(只有終點)的 tag
# 被同類同終點、槽位更完整的 tag 吸收,所以泛用規則不必揹一長串「別的規則管的
# 句型」排除條件——排除條件只留給否定形這種真反證。
RULES = (
    # ── 區域移動:處理段(pos=效果)──
    define("T1", CAT_MOVE, SCOPE_PROCESS,
           "檢索「デッキから…手札に加える」",
           _S_DECK + _sp() + _V_ADD,
           {"from": ZONE_DECK, "to": ZONE_HAND}, "票07"),
    define("T2", CAT_MOVE, SCOPE_PROCESS,
           "墓地回收「墓地の/から…手札に加える」",
           _S_GRAVE + _sp() + _V_ADD,
           {"from": ZONE_GRAVE, "to": ZONE_HAND}, "票10"),
    define("T3", CAT_MOVE, SCOPE_PROCESS,
           "除外區回收「除外されている…手札に加える」",
           _S_BANISHED + _sp() + _V_ADD,
           {"from": ZONE_BANISH, "to": ZONE_HAND}, "票10"),
    define("T4", CAT_MOVE, SCOPE_PROCESS,
           "蘇生「墓地の/から…特殊召喚」",
           _S_GRAVE + _sp_f() + _V_SS,
           {"from": ZONE_GRAVE, "to": ZONE_FIELD}, "票10"),
    define("T5", CAT_MOVE, SCOPE_PROCESS,
           "手牌展開「手札から…特殊召喚」",
           _S_HAND + _sp_f() + _V_SS,
           {"from": ZONE_HAND, "to": ZONE_FIELD}, "票10"),
    define("T6", CAT_MOVE, SCOPE_PROCESS,
           "牌組展開「デッキから…特殊召喚」",
           _S_DECK + _sp_f() + _V_SS,
           {"from": ZONE_DECK, "to": ZONE_FIELD}, "票10"),
    define("T7", CAT_MOVE, SCOPE_PROCESS,
           "額外展開「EXデッキから…特殊召喚」",
           _S_EXTRA + _sp_f() + _V_SS,
           {"from": ZONE_EXTRA, "to": ZONE_FIELD}, "票10"),
    define("T8", CAT_MOVE, SCOPE_PROCESS,
           "除外區特召「除外されている…特殊召喚」",
           _S_BANISHED + _sp_f() + _V_SS,
           {"from": ZONE_BANISH, "to": ZONE_FIELD}, "票10"),
    define("T9", CAT_MOVE, SCOPE_PROCESS,
           "堆墓「デッキから…墓地へ送る」",
           _S_DECK + _sp(60) + _V_SEND,
           {"from": ZONE_DECK, "to": ZONE_GRAVE}, "票10"),
    define("T10", CAT_MOVE, SCOPE_PROCESS,
           "場上送墓「フィールドの…墓地へ送る」",
           _S_FIELD + _sp(60) + _V_SEND,
           {"from": ZONE_FIELD, "to": ZONE_GRAVE}, "票10"),
    define("T11", CAT_MOVE, SCOPE_PROCESS,
           "額外堆墓「EXデッキから…墓地へ送る」",
           _S_EXTRA + _sp(60) + _V_SEND,
           {"from": ZONE_EXTRA, "to": ZONE_GRAVE}, "票10"),
    define("T12", CAT_MOVE, SCOPE_PROCESS,
           "手牌送墓「手札から/の/を…墓地へ送る・捨てる」(處理段)",
           r"(?<!・)手札[のをか]"
           r"(?:(?!(?:デッキ|フィールド|除外|Pゾーン|EX|墓地へ送られ))[^。]){0,40}?"
           r"(墓地へ送(る(?!事(は|が|も)?でき(ない|ず)|効果|場合)|り|って)|捨て(?!る場合|られ))",
           {"from": ZONE_HAND, "to": ZONE_GRAVE}, "票10",
           exclude=r"捨てられ"),
    define("T13", CAT_MOVE, SCOPE_PROCESS,
           "彈回手牌「フィールドの…手札に戻す」",
           _S_FIELD + _sp() + _V_RET_HAND,
           {"from": ZONE_FIELD, "to": ZONE_HAND}, "票10",
           exclude=r"戻せない"),
    define("T14", CAT_MOVE, SCOPE_PROCESS,
           "泛用回手「…を(持ち主の)手札に戻す」(無明確起點,可被吸收)",
           r"(持ち主の)?" + _V_RET_HAND,
           {"to": ZONE_HAND}, "票10",
           exclude=r"戻せない"),
    define("T15", CAT_MOVE, SCOPE_PROCESS,
           "墓地回牌組「墓地の/から…デッキに戻す」",
           _S_GRAVE + _sp() + _V_RET_DECK,
           {"from": ZONE_GRAVE, "to": ZONE_DECK}, "票10",
           exclude=r"戻せない"),
    define("T16", CAT_MOVE, SCOPE_PROCESS,
           "場上回牌組「フィールドの…デッキに戻す」",
           _S_FIELD + _sp() + _V_RET_DECK,
           {"from": ZONE_FIELD, "to": ZONE_DECK}, "票10",
           exclude=r"戻せない"),
    define("T17", CAT_MOVE, SCOPE_PROCESS,
           "除外回牌組「除外されている…デッキに戻す」",
           _S_BANISHED + _sp() + _V_RET_DECK,
           {"from": ZONE_BANISH, "to": ZONE_DECK}, "票10",
           exclude=r"戻せない"),
    define("T18", CAT_MOVE, SCOPE_PROCESS,
           "泛用回牌組「…をデッキに戻す/デッキに加える」(無明確起點,可被吸收)",
           r"(持ち主の)?((?<!EX)(?<!ラ)デッキに戻(す(?!事(は|が|も)?でき(ない|ず)|場合)|し)"
           r"|(?<!EX)(?<!ラ)デッキに加え(?!る効果))",
           {"to": ZONE_DECK}, "票10",
           exclude=r"戻せない"),
    define("T19", CAT_MOVE, SCOPE_PROCESS,
           "回額外牌組「…をEXデッキに戻す/加える」",
           r"(EXデッキ|エクストラデッキ)に(表側で)?(戻(す(?!事(は|が|も)?でき(ない|ず))|し)"
           r"|加え(?!る効果))",
           {"to": ZONE_EXTRA}, "票10",
           exclude=r"戻せない"),
    define("T20", CAT_MOVE, SCOPE_PROCESS,
           "效果除外(墓地起點)「墓地の/から…除外する」",
           _S_GRAVE + _sp(60) + _V_BANISH,
           {"from": ZONE_GRAVE, "to": ZONE_BANISH}, "票10"),
    define("T21", CAT_MOVE, SCOPE_PROCESS,
           "效果除外(場上起點)「フィールドの…除外する」",
           _S_FIELD + _sp() + _V_BANISH,
           {"from": ZONE_FIELD, "to": ZONE_BANISH}, "票10"),
    define("T22", CAT_MOVE, SCOPE_PROCESS,
           "泛用效果除外「…を除外する」(無明確起點,可被吸收)",
           r"(を([^。、]{0,20}?まで)?|送らずに)除外(する(?!事(は|が|も)?でき(ない|ず)|効果|場合)|できる|し、)",
           {"to": ZONE_BANISH}, "票10"),
    define("T23", CAT_MOVE, SCOPE_PROCESS,
           "牌組蓋放「デッキから…セットする/できる」",
           _S_DECK + _sp_f() + _V_SET,
           {"from": ZONE_DECK, "to": ZONE_FIELD}, "票10",
           exclude=r"カード扱い"),
    define("T24", CAT_MOVE, SCOPE_PROCESS,
           "墓地蓋放「墓地の/から…セットする/できる」",
           _S_GRAVE + _sp_f() + _V_SET,
           {"from": ZONE_GRAVE, "to": ZONE_FIELD}, "票10",
           exclude=r"カード扱い"),
    define("T25", CAT_MOVE, SCOPE_PROCESS,
           "手牌蓋放「手札から…セットする/できる」",
           _S_HAND + _sp_f() + _V_SET,
           {"from": ZONE_HAND, "to": ZONE_FIELD}, "票10",
           exclude=r"カード扱い"),
    define("T27", CAT_MOVE, SCOPE_PROCESS,
           "靈擺區放置(牌組起點)「デッキから…Pゾーンに置く」",
           _S_DECK + _sp_f() + r"Pゾーンに置",
           {"from": ZONE_DECK, "to": ZONE_PZONE}, "票10"),
    define("T28", CAT_MOVE, SCOPE_PROCESS,
           "靈擺區放置(泛用)「…をPゾーンに置く」(可被吸收)",
           r"Pゾーンに置",
           {"to": ZONE_PZONE}, "票10"),
    define("T29", CAT_MOVE, SCOPE_PROCESS,
           "牌組頂/底回置「デッキの一番上/下に戻す・置く」(頂/底不獨立,歸牌組)",
           r"デッキの(一番)?(上|下)(または一番(上|下))?に(戻す|置く|戻し|置き)",
           {"to": ZONE_DECK}, "票10"),
    define("T36", CAT_MOVE, SCOPE_PROCESS,
           "牌組頂堆墓「デッキの一番上のカードを墓地へ送る」",
           r"デッキの一番上の?カード[^。]{0,12}?" + _V_SEND,
           {"from": ZONE_DECK, "to": ZONE_GRAVE}, "票10"),
    define("T37", CAT_MOVE, SCOPE_PROCESS,
           "自身特召「このカードを特殊召喚する/できる」(無明確起點,可被吸收)",
           r"このカードを特殊召喚(する|できる)",
           {"to": ZONE_FIELD, "side": SIDE_SELF}, "票10"),
    define("T38", CAT_MOVE, SCOPE_PROCESS,
           "泛用特召「…を特殊召喚する/できる」(無明確起點,可被吸收)",
           _V_SS,
           {"to": ZONE_FIELD}, "票10"),
    define("T39", CAT_MOVE, SCOPE_PROCESS,
           "泛用送墓「…を墓地へ送る」(無明確起點,可被吸收)",
           _V_SEND,
           {"to": ZONE_GRAVE}, "票10"),
    define("T40", CAT_MOVE, SCOPE_PROCESS,
           "泛用入手「…を手札に加える」(無明確起點,可被吸收)",
           _V_ADD,
           {"to": ZONE_HAND}, "票10"),
    define("T61", CAT_MOVE, SCOPE_PROCESS,
           "效果解放「…をリリースする」(處理段;場上→墓地)",
           r"リリース(する(?!事(は|が|も)?でき(ない|ず)|場合|ため)|し、|し。|、|できる)",
           {"from": ZONE_FIELD, "to": ZONE_GRAVE}, "票10",
           exclude=r"リリースされ|リリースして召喚|リリースして表側表示で"
                   r"|リリースしてアドバンス召喚|リリースしてA召喚"),
    define("T65", CAT_MOVE, SCOPE_PROCESS,
           "手牌除外「手札から/の…除外する」(限同一逗號子句)",
           r"(?<!・)手札[のをか]ら?"
           + r"(?:(?!(?:手札|デッキ|墓地|除外|フィールド))[^。、]){0,30}?"
           + _V_BANISH,
           {"from": ZONE_HAND, "to": ZONE_BANISH}, "票10"),
    define("T66", CAT_MOVE, SCOPE_PROCESS,
           "牌組頂除外「デッキの(一番)上から…除外する」",
           r"デッキの(一番)?上(から|の)[^。]{0,20}?除外(する|し、|できる)",
           {"from": ZONE_DECK, "to": ZONE_BANISH}, "票10"),
    define("T67", CAT_MOVE, SCOPE_PROCESS,
           "牌組頂堆墓「デッキの上から…墓地へ送る」",
           r"デッキの(一番)?上(から|の)[^。]{0,20}?" + _V_SEND,
           {"from": ZONE_DECK, "to": ZONE_GRAVE}, "票10"),
    define("T68", CAT_MOVE, SCOPE_PROCESS,
           "泛用蓋放「…をセットする/できる」(無明確起點,可被吸收)",
           _V_SET,
           {"to": ZONE_FIELD}, "票10",
           exclude=r"セットされ|カード扱い"),
    define("T69", CAT_MOVE, SCOPE_PROCESS,
           "靈擺區特召「Pゾーンの…を特殊召喚」",
           r"Pゾーンの" + _sp_f() + _V_SS,
           {"from": ZONE_PZONE, "to": ZONE_FIELD}, "票10"),
    define("T70", CAT_MOVE, SCOPE_PROCESS,
           "靈擺區放置(墓地起點)「墓地の/から…Pゾーンに置く」",
           _S_GRAVE + _sp_f() + r"Pゾーンに置",
           {"from": ZONE_GRAVE, "to": ZONE_PZONE}, "票10"),
    # ── 區域移動:複合起點(一次發多個 tag)──
    define("T41", CAT_MOVE, SCOPE_PROCESS,
           "複合展開「手札・墓地から…特殊召喚」",
           r"手札・墓地から" + _sp_f() + _V_SS,
           ({"from": ZONE_HAND, "to": ZONE_FIELD},
            {"from": ZONE_GRAVE, "to": ZONE_FIELD}), "票10"),
    define("T42", CAT_MOVE, SCOPE_PROCESS,
           "複合展開「手札・デッキから…特殊召喚」",
           r"手札・デッキから" + _sp_f() + _V_SS,
           ({"from": ZONE_HAND, "to": ZONE_FIELD},
            {"from": ZONE_DECK, "to": ZONE_FIELD}), "票10"),
    define("T43", CAT_MOVE, SCOPE_PROCESS,
           "複合蘇生檢索「デッキ・墓地から…手札に加える」",
           r"(?<!ラ)(?<!EX)デッキ・墓地から" + _sp() + _V_ADD,
           ({"from": ZONE_DECK, "to": ZONE_HAND},
            {"from": ZONE_GRAVE, "to": ZONE_HAND}), "票10"),
    define("T44", CAT_MOVE, SCOPE_PROCESS,
           "複合展開「デッキ・墓地から…特殊召喚」",
           r"(?<!ラ)(?<!EX)デッキ・墓地から" + _sp_f() + _V_SS,
           ({"from": ZONE_DECK, "to": ZONE_FIELD},
            {"from": ZONE_GRAVE, "to": ZONE_FIELD}), "票10"),
    define("T45", CAT_MOVE, SCOPE_PROCESS,
           "三源展開「手札・デッキ・墓地から…特殊召喚/加える」",
           r"手札・デッキ・墓地から" + _sp_f() + r"(特殊召喚|手札に加え)",
           ({"from": ZONE_HAND, "to": ZONE_FIELD},
            {"from": ZONE_DECK, "to": ZONE_FIELD},
            {"from": ZONE_GRAVE, "to": ZONE_FIELD}), "票10",
           exclude=r"手札に加え"),
    define("T46", CAT_MOVE, SCOPE_PROCESS,
           "複合送墓「手札・フィールドの…を墓地へ送る」",
           r"手札・フィールド[のか]ら?" + _sp(60) + _V_SEND,
           ({"from": ZONE_HAND, "to": ZONE_GRAVE},
            {"from": ZONE_FIELD, "to": ZONE_GRAVE}), "票10"),
    define("T47", CAT_MOVE, SCOPE_PROCESS,
           "複合檢索「手札・デッキから…手札に加える」等値形不存在,"
           "デッキ・EXデッキから…特殊召喚",
           r"デッキ・EXデッキから" + _sp_f() + _V_SS,
           ({"from": ZONE_DECK, "to": ZONE_FIELD},
            {"from": ZONE_EXTRA, "to": ZONE_FIELD}), "票10"),
    # ── 區域移動:對象範圍(起點在發動子句的對象指定、動作在處理段)──
    define("T50", CAT_MOVE, SCOPE_TARGET,
           "對象蘇生「墓地の…を対象…→ その…特殊召喚」",
           r"(?<!・)墓地の" + _sp(60) + r"対象",
           {"from": ZONE_GRAVE, "to": ZONE_FIELD}, "票10",
           action=_anaphora(_V_SS)),
    define("T51", CAT_MOVE, SCOPE_TARGET,
           "對象回收「墓地の…を対象…→ その…手札に加える」",
           r"(?<!・)墓地の" + _sp(60) + r"対象",
           {"from": ZONE_GRAVE, "to": ZONE_HAND}, "票10",
           action=_anaphora(_V_ADD)),
    define("T52", CAT_MOVE, SCOPE_TARGET,
           "對象回牌組「墓地の…を対象…→ その…デッキに戻す」",
           r"(?<!・)墓地の" + _sp(60) + r"対象",
           {"from": ZONE_GRAVE, "to": ZONE_DECK}, "票10",
           action=_anaphora(_V_RET_DECK, 40)),
    define("T53", CAT_MOVE, SCOPE_TARGET,
           "對象除外「墓地の…を対象…→ その…除外する」",
           r"(?<!・)墓地の" + _sp(60) + r"対象",
           {"from": ZONE_GRAVE, "to": ZONE_BANISH}, "票10",
           action=_anaphora(_V_BANISH)),
    define("T54", CAT_MOVE, SCOPE_TARGET,
           "對象特召「除外されている…を対象…→ その…特殊召喚」",
           r"除外されている" + _sp(60) + r"対象",
           {"from": ZONE_BANISH, "to": ZONE_FIELD}, "票10",
           action=_anaphora(_V_SS)),
    define("T55", CAT_MOVE, SCOPE_TARGET,
           "對象回收「除外されている…を対象…→ その…手札に加える」",
           r"除外されている" + _sp(60) + r"対象",
           {"from": ZONE_BANISH, "to": ZONE_HAND}, "票10",
           action=_anaphora(_V_ADD)),
    define("T56", CAT_MOVE, SCOPE_TARGET,
           "對象回牌組「除外されている…を対象…→ その…デッキに戻す」",
           r"除外されている" + _sp(60) + r"対象",
           {"from": ZONE_BANISH, "to": ZONE_DECK}, "票10",
           action=_anaphora(_V_RET_DECK, 40)),
    define("T57", CAT_MOVE, SCOPE_TARGET,
           "對象彈回「フィールドの…を対象…→ その…手札に戻す」",
           _S_FIELD + _sp(60) + r"対象",
           {"from": ZONE_FIELD, "to": ZONE_HAND}, "票10",
           action=_anaphora(_V_RET_HAND, 40)),
    define("T58", CAT_MOVE, SCOPE_TARGET,
           "對象回牌組「フィールドの…を対象…→ その…デッキに戻す」",
           _S_FIELD + _sp(60) + r"対象",
           {"from": ZONE_FIELD, "to": ZONE_DECK}, "票10",
           action=_anaphora(_V_RET_DECK, 40)),
    define("T59", CAT_MOVE, SCOPE_TARGET,
           "對象送墓「フィールドの…を対象…→ その…墓地へ送る」",
           _S_FIELD + _sp(60) + r"対象",
           {"from": ZONE_FIELD, "to": ZONE_GRAVE}, "票10",
           action=_anaphora(_V_SEND)),
    define("T60", CAT_MOVE, SCOPE_TARGET,
           "對象除外「フィールドの…を対象…→ その…除外する」",
           _S_FIELD + _sp(60) + r"対象",
           {"from": ZONE_FIELD, "to": ZONE_BANISH}, "票10",
           action=_anaphora(_V_BANISH)),
    # ── 區域移動:發動子句(pos=成本)──
    define("T30", CAT_MOVE, SCOPE_COST,
           "解放代價「…をリリースして発動」(場上→墓地)",
           r"リリースし",
           {"from": ZONE_FIELD, "to": ZONE_GRAVE}, "票10",
           exclude=r"リリースされ|リリースできない|手札から"),
    define("T31", CAT_MOVE, SCOPE_COST,
           "手牌代價「手札を/から…捨てて発動」",
           r"手札[をかの][^。]{0,30}?捨て",
           {"from": ZONE_HAND, "to": ZONE_GRAVE}, "票10",
           exclude=r"捨てられ"),
    define("T32", CAT_MOVE, SCOPE_COST,
           "墓地除外代價「墓地の/から…除外して発動」",
           _S_GRAVE + _sp(60) + r"除外し",
           {"from": ZONE_GRAVE, "to": ZONE_BANISH}, "票10"),
    define("T33", CAT_MOVE, SCOPE_COST,
           "自場除外代價「フィールドの/このカードを除外して発動」",
           r"(フィールドの" + _sp(50) + r"|このカード[をと]([^。、]{0,30}?を)?)除外し",
           {"from": ZONE_FIELD, "to": ZONE_BANISH}, "票10",
           exclude=r"墓地|除外され"),
    define("T34", CAT_MOVE, SCOPE_COST,
           "送墓代價「…を墓地へ送って発動」(無明確起點,可被吸收)",
           r"墓地へ送(り|って)",
           {"to": ZONE_GRAVE}, "票10",
           exclude=r"墓地へ送られ"),
    define("T35", CAT_MOVE, SCOPE_COST,
           "自場送墓代價「フィールドの…を墓地へ送って発動」",
           _S_FIELD + _sp(50) + r"墓地へ送(り|って)",
           {"from": ZONE_FIELD, "to": ZONE_GRAVE}, "票10",
           exclude=r"墓地へ送られ"),
    define("T48", CAT_MOVE, SCOPE_COST,
           "手牌送墓代價「手札から…を墓地へ送って発動」",
           _S_HAND + _sp(50) + r"墓地へ送(り|って)",
           {"from": ZONE_HAND, "to": ZONE_GRAVE}, "票10",
           exclude=r"墓地へ送られ"),
    define("T49", CAT_MOVE, SCOPE_COST,
           "牌組頂送墓代價「デッキの一番上のカードを墓地へ送って発動」",
           r"デッキの一番上の?カード[^。]{0,12}?墓地へ送(り|って)",
           {"from": ZONE_DECK, "to": ZONE_GRAVE}, "票10",
           exclude=r"墓地へ送られ"),
    define("T62", CAT_MOVE, SCOPE_COST,
           "回手代價「…を(持ち主の)手札に戻して発動」(場上→手牌)",
           r"手札に戻(し|して)",
           {"from": ZONE_FIELD, "to": ZONE_HAND}, "票10",
           exclude=r"墓地[のか][^。]{0,40}?戻|除外されている[^。]{0,40}?戻"
                   r"|戻せない|戻された"),
    define("T80", CAT_MOVE, SCOPE_COST,
           "手牌牌組複合除外代價「手札・デッキから…除外して発動」",
           r"手札・デッキから" + _sp(60) + r"除外(し|できる)",
           ({"from": ZONE_HAND, "to": ZONE_BANISH},
            {"from": ZONE_DECK, "to": ZONE_BANISH}), "票10"),
    define("T90", CAT_MOVE, SCOPE_COST,
           "手場複合送墓代價「手札及び(自分)フィールドの…墓地へ送って発動」",
           r"手札及び(自分)?フィールドの[^。]{0,60}?墓地へ送(り|って)",
           ({"from": ZONE_HAND, "to": ZONE_GRAVE},
            {"from": ZONE_FIELD, "to": ZONE_GRAVE}), "票10"),
    define("T91", CAT_MOVE, SCOPE_PROCESS,
           "具名牌組特召「デッキの「〜」…を特殊召喚」",
           r"デッキの「[^」]+」(モンスター|カード)?" + _sp_f(30) + _V_SS,
           {"from": ZONE_DECK, "to": ZONE_FIELD}, "票10"),
    define("T95", CAT_MOVE, SCOPE_PROCESS,
           "額外除外「EXデッキから…除外する」",
           _S_EXTRA + _sp(50)
           + r"除外(する(?!事(は|が|も)?でき(ない|ず)|効果|場合)|し、|できる)",
           {"from": ZONE_EXTRA, "to": ZONE_BANISH}, "票10"),
    define("T97", CAT_MOVE, SCOPE_COST,
           "手場複合解放代價「手札・フィールドから…リリースして発動」",
           r"手札・フィールド[のか]ら?" + _sp(60) + r"リリースし",
           ({"from": ZONE_HAND, "to": ZONE_GRAVE},
            {"from": ZONE_FIELD, "to": ZONE_GRAVE}), "票10",
           exclude=r"リリースされ"),
    define("T98", CAT_MOVE, SCOPE_COST,
           "牌組頂底回置代價「…をデッキの一番上/下に戻して発動」",
           r"デッキの(一番)?(上|下)(または一番(上|下))?に(戻し|戻して|置き|置いて)",
           {"to": ZONE_DECK}, "票10"),
    define("T99", CAT_MOVE, SCOPE_COST,
           "泛用回牌組代價「…をデッキに戻して発動」(無明確起點)",
           r"(?<!EX)(?<!ラ)デッキに戻(し|して)",
           {"to": ZONE_DECK}, "票10"),
    define("T100", CAT_MOVE, SCOPE_TARGET,
           "複合對象回收「墓地の…及び除外…対象 → その…手札に加える」",
           r"墓地の(モンスター|カード)及び(除外されている|除外状態の)"
           r"[^。]{0,60}?対象",
           ({"from": ZONE_GRAVE, "to": ZONE_HAND},
            {"from": ZONE_BANISH, "to": ZONE_HAND}), "票10",
           action=_anaphora(_V_ADD)),
    define("T101", CAT_MOVE, SCOPE_PROCESS,
           "三源送墓「手札・デッキ及び…フィールドの…墓地へ送る」",
           r"手札・デッキ及び(自分|相手)?フィールドの[^。]{0,60}?" + _V_SEND,
           ({"from": ZONE_HAND, "to": ZONE_GRAVE},
            {"from": ZONE_DECK, "to": ZONE_GRAVE},
            {"from": ZONE_FIELD, "to": ZONE_GRAVE}), "票10"),
    define("T102", CAT_MOVE, SCOPE_PROCESS,
           "複合堆墓「デッキ・EXデッキから…墓地へ送る」",
           r"(?<!・)デッキ・EXデッキから" + _sp(60) + _V_SEND,
           ({"from": ZONE_DECK, "to": ZONE_GRAVE},
            {"from": ZONE_EXTRA, "to": ZONE_GRAVE}), "票10"),
    define("T103", CAT_MOVE, SCOPE_PROCESS,
           "複合回手回額外「…を手札・EXデッキに戻す」",
           r"手札・EXデッキに戻(す(?!事(は|が|も)?でき(ない|ず)|場合)|し)",
           ({"to": ZONE_HAND}, {"to": ZONE_EXTRA}), "票10"),
    define("T104", CAT_MOVE, SCOPE_PROCESS,
           "墓地除外複合展開「墓地・除外状態の…特殊召喚」",
           r"墓地・除外状態の" + _sp_f() + _V_SS,
           ({"from": ZONE_GRAVE, "to": ZONE_FIELD},
            {"from": ZONE_BANISH, "to": ZONE_FIELD}), "票10"),
    define("T93", CAT_MOVE, SCOPE_PROCESS,
           "三源除外「手札・フィールド・墓地の/から…除外」(融合素材框架)",
           r"手札・フィールド・墓地[のか]ら?" + _sp(60)
           + r"除外(する(?!事(は|が|も)?でき(ない|ず)|効果|場合)|し、|し。|できる)",
           ({"from": ZONE_HAND, "to": ZONE_BANISH},
            {"from": ZONE_FIELD, "to": ZONE_BANISH},
            {"from": ZONE_GRAVE, "to": ZONE_BANISH}), "票10"),
    define("T87", CAT_MOVE, SCOPE_PROCESS,
           "手場複合解放「手札・フィールドの…リリース」(處理段)",
           r"手札・フィールド[のか]ら?" + _sp(60)
           + r"リリース(する(?!事(は|が|も)?でき(ない|ず)|場合|ため)|し)",
           ({"from": ZONE_HAND, "to": ZONE_GRAVE},
            {"from": ZONE_FIELD, "to": ZONE_GRAVE}), "票10",
           exclude=r"リリースされ"),
    define("T88", CAT_MOVE, SCOPE_COST,
           "三源除外代價「手札・フィールド・墓地の…除外して発動」",
           r"手札・フィールド・墓地の" + _sp(60) + r"除外(し|できる)",
           ({"from": ZONE_HAND, "to": ZONE_BANISH},
            {"from": ZONE_FIELD, "to": ZONE_BANISH},
            {"from": ZONE_GRAVE, "to": ZONE_BANISH}), "票10"),
    define("T89", CAT_MOVE, SCOPE_COST,
           "或格除外代價「手札または(自分)フィールドの…除外して発動」",
           r"手札または(自分)?フィールドの" + _sp(60) + r"除外(し|できる)",
           ({"from": ZONE_HAND, "to": ZONE_BANISH},
            {"from": ZONE_FIELD, "to": ZONE_BANISH}), "票10"),
    define("T82", CAT_MOVE, SCOPE_PROCESS,
           "額外墓地複合展開「EXデッキ・墓地から…特殊召喚」",
           r"(EXデッキ|エクストラデッキ)・墓地から" + _sp_f() + _V_SS,
           ({"from": ZONE_EXTRA, "to": ZONE_FIELD},
            {"from": ZONE_GRAVE, "to": ZONE_FIELD}), "票10"),
    define("T83", CAT_MOVE, SCOPE_PROCESS,
           "墓地與除外複合「墓地の…及び除外されている…セット/加える」",
           r"墓地の(カード|モンスター)及び(除外されている|除外状態の)"
           r"[^。]{0,60}?(" + _V_SET + r"|" + _V_ADD + r")",
           ({"from": ZONE_GRAVE, "to": ZONE_FIELD},
            {"from": ZONE_BANISH, "to": ZONE_FIELD}), "票10"),
    define("T84", CAT_MOVE, SCOPE_TARGET,
           "對象複合特召「墓地の…及び除外…対象 → その…特殊召喚」",
           r"墓地の(モンスター|カード)及び(除外されている|除外状態の)"
           r"[^。]{0,60}?対象",
           ({"from": ZONE_GRAVE, "to": ZONE_FIELD},
            {"from": ZONE_BANISH, "to": ZONE_FIELD}), "票10",
           action=_anaphora(_V_SS)),
    define("T85", CAT_MOVE, SCOPE_PROCESS,
           "牌組場上複合送墓「デッキ及び…フィールドの…墓地へ送る」",
           r"デッキ及び(自分|相手)?フィールドの[^。]{0,60}?" + _V_SEND,
           ({"from": ZONE_DECK, "to": ZONE_GRAVE},
            {"from": ZONE_FIELD, "to": ZONE_GRAVE}), "票10"),
    define("T79", CAT_MOVE, SCOPE_COST,
           "墓地自卡除外代價「(このカードが)墓地に存在…このカードを除外し」",
           r"墓地に存在(する状態|する場合|し)[^。]{0,60}?このカードを除外し",
           {"from": ZONE_GRAVE, "to": ZONE_BANISH, "side": SIDE_SELF},
           "票10"),
    define("T81", CAT_MOVE, SCOPE_COST,
           "手牌解放代價「手札から…をリリースして発動」(手牌→墓地)",
           r"手札から" + _sp(50) + r"リリースし",
           {"from": ZONE_HAND, "to": ZONE_GRAVE}, "票10",
           exclude=r"リリースされ"),
    define("T92", CAT_MOVE, SCOPE_TARGET,
           "複合對象回牌組「フィールド・墓地の…対象 → その…デッキに戻す」",
           r"フィールド・墓地の" + _sp(60) + r"対象",
           ({"from": ZONE_FIELD, "to": ZONE_DECK},
            {"from": ZONE_GRAVE, "to": ZONE_DECK}), "票10",
           action=_anaphora(_V_RET_DECK, 40)),
    define("T63", CAT_MOVE, SCOPE_TARGET,
           "對象蓋放「墓地の…を対象…→ その…セットする」",
           r"(?<!・)墓地の" + _sp(60) + r"対象",
           {"from": ZONE_GRAVE, "to": ZONE_FIELD}, "票10",
           action=_anaphora_f(_V_SET, 40)),
    # ── 區域移動:複合起點(續)──
    define("T71", CAT_MOVE, SCOPE_PROCESS,
           "墓地・除外回收「墓地・除外状態の…手札に加える」",
           r"墓地・除外状態の" + _sp() + _V_ADD,
           ({"from": ZONE_GRAVE, "to": ZONE_HAND},
            {"from": ZONE_BANISH, "to": ZONE_HAND}), "票10"),
    define("T72", CAT_MOVE, SCOPE_PROCESS,
           "場上墓地複合除外「フィールド・墓地の…除外する」(處理段)",
           r"フィールド・墓地[のか]" + _sp(60) + _V_BANISH,
           ({"from": ZONE_FIELD, "to": ZONE_BANISH},
            {"from": ZONE_GRAVE, "to": ZONE_BANISH}), "票10"),
    define("T73", CAT_MOVE, SCOPE_COST,
           "場上墓地複合除外代價「フィールド・墓地の…除外して発動」",
           r"フィールド・墓地[のか](から)?" + _sp(60) + r"除外(し|できる)",
           ({"from": ZONE_FIELD, "to": ZONE_BANISH},
            {"from": ZONE_GRAVE, "to": ZONE_BANISH}), "票10"),
    define("T74", CAT_MOVE, SCOPE_COST,
           "手牌墓地複合除外代價「手札・墓地の…除外して発動」",
           r"手札・墓地[のか]" + _sp(60) + r"除外し",
           ({"from": ZONE_HAND, "to": ZONE_BANISH},
            {"from": ZONE_GRAVE, "to": ZONE_BANISH}), "票10"),
    define("T75", CAT_MOVE, SCOPE_COST,
           "墓地・除外回牌組代價「墓地・除外状態の…デッキに戻して発動」",
           r"墓地・除外状態の"
           + r"(?:(?!(?:手札|墓地|フィールド|Pゾーン))[^。]){0,70}?"
           + r"デッキに戻(し|して)",
           ({"from": ZONE_GRAVE, "to": ZONE_DECK},
            {"from": ZONE_BANISH, "to": ZONE_DECK}), "票10"),
    define("T76", CAT_MOVE, SCOPE_COST,
           "牌組除外代價「デッキから…除外して発動」",
           _S_DECK + _sp(50) + r"除外し",
           {"from": ZONE_DECK, "to": ZONE_BANISH}, "票10"),
    define("T77", CAT_MOVE, SCOPE_COST,
           "手牌除外代價「手札の/から…除外して発動」",
           r"(?<!・)手札[のをか]ら?" + _sp(50) + r"除外し",
           {"from": ZONE_HAND, "to": ZONE_BANISH}, "票10",
           exclude=r"墓地"),
    define("T78", CAT_MOVE, SCOPE_COST,
           "墓地回牌組代價「墓地の…をデッキに戻して発動」",
           _S_GRAVE + _sp() + r"デッキに戻(し|して)",
           {"from": ZONE_GRAVE, "to": ZONE_DECK}, "票10"),
    # ══ 第2期(票16):破壞 ══════════════════════════════════
    # 「無効にし(、|て)破壊」是無效的附帶槽位(裁定批2),破壞規則與粗篩都
    # 讓路;「代わりに破壊」是代替破壞歸耐性,一律排除。
    define("T110", CAT_DESTROY, SCOPE_PROCESS,
           "泛用效果破壞「…を破壊する」(無槽位,可被吸收)",
           _V_DS,
           {}, "票16",
           exclude=_DS_EXCLUDE),
    define("T111", CAT_DESTROY, SCOPE_PROCESS,
           "全體怪獸破壞「モンスターを全て破壊」",
           r"モンスターを全て破壊",
           {"what": DS_MONSTER, "scope": RANGE_ALL}, "票16",
           exclude=_DS_EXCLUDE),
    define("T112", CAT_DESTROY, SCOPE_PROCESS,
           "全體卡破壞「カードを全て破壊」(不限種;魔陷區限定句歸 T113 面)",
           r"(?<!罠)(?<!法)カードを全て破壊",
           {"what": DS_CARD, "scope": RANGE_ALL}, "票16",
           exclude=_DS_EXCLUDE + r"|魔法＆罠ゾーン|宣言した種類"),
    define("T113", CAT_DESTROY, SCOPE_PROCESS,
           "全體魔陷破壞「魔法・罠カード/魔法＆罠ゾーンのカードを全て破壊」",
           r"(魔法・罠(カード|ゾーンのカード)|魔法＆罠ゾーンのカード)を全て破壊",
           {"what": DS_SPELLTRAP, "scope": RANGE_ALL}, "票16",
           exclude=_DS_EXCLUDE),
    define("T114", CAT_DESTROY, SCOPE_PROCESS,
           "對手場破壞「相手フィールドの…破壊」(處理段直述)",
           r"相手フィールドの(?:(?!(?:自分|お互い|" + _VERBS + r"))[^。]){0,50}?"
           + _V_DS,
           {"side": SIDE_OPP}, "票16",
           exclude=_DS_EXCLUDE),
    define("T115", CAT_DESTROY, SCOPE_PROCESS,
           "自壞「このカードを破壊する」",
           r"このカードを破壊(する|し、|し。|できる)",
           {"side": SIDE_SELF}, "票16",
           exclude=r"代わりに"),
    define("T117", CAT_DESTROY, SCOPE_PROCESS,
           "單體怪獸破壞「モンスター１体を…破壊」(處理段直述)",
           r"モンスター１体を[^。、]{0,15}?破壊(する|し、|し。|できる)",
           {"what": DS_MONSTER, "scope": RANGE_ONE}, "票16",
           exclude=_DS_EXCLUDE),
    define("T118", CAT_DESTROY, SCOPE_PROCESS,
           "單體卡破壞「カード１枚を…破壊」(處理段直述,不限種)",
           r"(?<!罠)(?<!法)(?<!ー)カード１枚を[^。、]{0,15}?破壊(する|し、|し。|できる)",
           {"what": DS_CARD, "scope": RANGE_ONE}, "票16",
           exclude=_DS_EXCLUDE + r"|フィールドゾーンのカード"),
    define("T119", CAT_DESTROY, SCOPE_PROCESS,
           "單體魔陷破壞「魔法・罠カード１枚を…破壊」(處理段直述)",
           r"魔法・罠カード１枚を[^。、]{0,15}?破壊(する|し、|し。|できる)",
           {"what": DS_SPELLTRAP, "scope": RANGE_ONE}, "票16",
           exclude=_DS_EXCLUDE),
    define("T127", CAT_DESTROY, SCOPE_PROCESS,
           "無效附帶破壞的破壞面「無効にし(、|て)破壊」(破壞那一張=單體)",
           r"無効にし(、|て)?破壊(する|し、|し。|できる)",
           {"scope": RANGE_ONE}, "票16"),
    define("T116", CAT_DESTROY, SCOPE_COST,
           "破壞代價「…を破壊して発動」(戰鬥破壞的觸發敘述不算)",
           r"破壊し(て|、)",
           {}, "票16",
           exclude=r"戦闘[でに]|破壊された|破壊されな"),
    define("T120", CAT_DESTROY, SCOPE_TARGET,
           "對象單怪破壞「モンスター１体を対象…→ その…破壊」",
           r"モンスター１体を対象",
           {"what": DS_MONSTER, "scope": RANGE_ONE}, "票16",
           action=_anaphora(_V_DS)),
    define("T121", CAT_DESTROY, SCOPE_TARGET,
           "對象複數怪破壞「モンスター(を)〜体(まで)対象…→ その…破壊」",
           r"モンスター(を)?[２-９]体(まで)?(を)?対象",
           {"what": DS_MONSTER, "scope": RANGE_MULT}, "票16",
           action=_anaphora(_V_DS)),
    define("T122", CAT_DESTROY, SCOPE_TARGET,
           "對象單卡破壞「カード１枚を対象…→ その…破壊」"
           "(不限種;場地區限定=魔陷,排除)",
           r"(?<!罠)(?<!法)(?<!ー)カード１枚を対象",
           {"what": DS_CARD, "scope": RANGE_ONE}, "票16",
           exclude=r"フィールドゾーンのカード",
           action=_anaphora(_V_DS)),
    define("T123", CAT_DESTROY, SCOPE_TARGET,
           "對象複數卡破壞「カード(を)〜枚(まで)対象…→ その…破壊」(不限種)",
           r"(?<!罠)(?<!法)(?<!ー)カード(を)?[２-９]枚(まで)?(を)?対象",
           {"what": DS_CARD, "scope": RANGE_MULT}, "票16",
           action=_anaphora(_V_DS)),
    define("T124", CAT_DESTROY, SCOPE_TARGET,
           "對象單魔陷破壞「魔法・罠カード１枚を対象…→ その…破壊」",
           r"魔法・罠カード１枚を対象",
           {"what": DS_SPELLTRAP, "scope": RANGE_ONE}, "票16",
           action=_anaphora(_V_DS)),
    define("T125", CAT_DESTROY, SCOPE_TARGET,
           "對象複數魔陷破壞「魔法・罠カード(を)〜枚(まで)対象…→ その…破壊」",
           r"魔法・罠カード(を)?[２-９]枚(まで)?(を)?対象",
           {"what": DS_SPELLTRAP, "scope": RANGE_MULT}, "票16",
           action=_anaphora(_V_DS)),
    define("T126", CAT_DESTROY, SCOPE_TARGET,
           "對象對手單怪破壞「相手フィールドのモンスター１体を対象…→ 破壊」",
           r"相手フィールドの(?:(?!自分)[^。]){0,30}?モンスター１体を対象",
           {"what": DS_MONSTER, "scope": RANGE_ONE, "side": SIDE_OPP},
           "票16",
           action=_anaphora(_V_DS)),
    # ══ 第2期(票16):無效 ══════════════════════════════════
    define("T140", CAT_NEGATE, SCOPE_PROCESS,
           "泛用無效「…を無効にする/無効化される」(無槽位,可被吸收)",
           r"無効に(する(?!事(は|が|も)?でき|効果)|し|できる)|無効化され(る|、)",
           {}, "票16",
           exclude=_NG_EXCLUDE),
    define("T141", CAT_NEGATE, SCOPE_PROCESS,
           "發動無效「発動を無効に」(連鎖上)",
           r"発動を無効に(する|し|できる)",
           {"what": NG_ACTIVATION}, "票16",
           exclude=_NG_EXCLUDE),
    define("T142", CAT_NEGATE, SCOPE_PROCESS,
           "效果無效「効果を無効に」(を形=一次性;召喚修飾形歸 T148)",
           r"効果を無効に(する|し|できる)",
           {"what": NG_EFFECT}, "票16",
           exclude=_NG_EXCLUDE
           + r"|効果を無効にして[^。、]{0,8}?(特殊召喚|セット)"),
    define("T143", CAT_NEGATE, SCOPE_PROCESS,
           "發動無效附帶破壞「発動を無効にし(、|て)破壊」",
           r"発動を無効にし(、|て)?破壊",
           {"what": NG_ACTIVATION, "extra": NG_X_DESTROY}, "票16"),
    define("T144", CAT_NEGATE, SCOPE_PROCESS,
           "發動無效附帶除外「発動を無効にし…除外」",
           r"発動を無効にし(、|て)?(そのカードを|それを|「[^」]+」を)?除外",
           {"what": NG_ACTIVATION, "extra": NG_X_BANISH}, "票16"),
    define("T145", CAT_NEGATE, SCOPE_PROCESS,
           "效果無效附帶破壞「効果を無効にし(、|て)破壊」",
           r"効果を無効にし(、|て)?破壊",
           {"what": NG_EFFECT, "extra": NG_X_DESTROY}, "票16"),
    define("T146", CAT_NEGATE, SCOPE_PROCESS,
           "持續無效化「効果は/が(〜まで)無効化される」",
           r"効果[はが][^。、]{0,16}?無効化され(る|、)",
           {"what": NG_CONTINUOUS}, "票16",
           exclude=_NG_EXCLUDE),
    define("T147", CAT_NEGATE, SCOPE_PROCESS,
           "召喚無效附帶破壞「召喚を無効にし…破壊」(值域無召喚值,what 缺值)",
           r"召喚を無効にし(、|て)?[^。]{0,10}?破壊",
           {"extra": NG_X_DESTROY}, "票16"),
    define("T148", CAT_NEGATE, SCOPE_PROCESS,
           "封效特召「効果を無効にして特殊召喚/セット」(修飾形=持續無效化;"
           "被召喚者即被封效者,無逗點短距限定)",
           r"効果を無効にして[^。、]{0,8}?(特殊召喚|セット)",
           {"what": NG_CONTINUOUS}, "票16"),
    define("T149", CAT_NEGATE, SCOPE_PROCESS,
           "效果無效附帶除外「効果を無効にし…除外」",
           r"効果を無効にし(、|て)?(そのカードを|それを|そのモンスターを)?除外",
           {"what": NG_EFFECT, "extra": NG_X_BANISH}, "票16"),
    # ══ 第3期(票17):攻守調整 ══════════════════════════════════
    # item × dir 九宮格:主語錨(單獨/合記)×動詞形(アップ/ダウン/になる),
    # 主語與動詞間不跨另一個攻守動詞(_ST_SP)。
    define("T160", CAT_STAT, SCOPE_PROCESS,
           "攻擊上升「攻撃力は/が/を…アップ」",
           _ST_A + _ST_SP + _V_UP,
           {"item": ST_ATK, "dir": DIR_UP}, "票17"),
    define("T161", CAT_STAT, SCOPE_PROCESS,
           "守備上升「守備力は/が/を…アップ」",
           _ST_D + _ST_SP + _V_UP,
           {"item": ST_DEF, "dir": DIR_UP}, "票17"),
    define("T162", CAT_STAT, SCOPE_PROCESS,
           "攻守上升「攻撃力・守備力は…アップ」",
           _ST_W + _ST_SP + _V_UP,
           {"item": ST_BOTH, "dir": DIR_UP}, "票17"),
    define("T163", CAT_STAT, SCOPE_PROCESS,
           "攻擊下降「攻撃力は/が/を…ダウン」",
           _ST_A + _ST_SP + _V_DOWN,
           {"item": ST_ATK, "dir": DIR_DOWN}, "票17"),
    define("T164", CAT_STAT, SCOPE_PROCESS,
           "守備下降「守備力は/が/を…ダウン」",
           _ST_D + _ST_SP + _V_DOWN,
           {"item": ST_DEF, "dir": DIR_DOWN}, "票17"),
    define("T165", CAT_STAT, SCOPE_PROCESS,
           "攻守下降「攻撃力・守備力は…ダウン」",
           _ST_W + _ST_SP + _V_DOWN,
           {"item": ST_BOTH, "dir": DIR_DOWN}, "票17"),
    define("T166", CAT_STAT, SCOPE_PROCESS,
           "攻擊變成「攻撃力は…になる/を…にする」(倍化/減半/變0/指定值)",
           _st_become(r"攻撃力(?!・)"),
           {"item": ST_ATK, "dir": DIR_BECOME}, "票17"),
    define("T167", CAT_STAT, SCOPE_PROCESS,
           "守備變成「守備力は…になる/を…にする」",
           _st_become(r"(?<!・)守備力"),
           {"item": ST_DEF, "dir": DIR_BECOME}, "票17"),
    define("T168", CAT_STAT, SCOPE_PROCESS,
           "攻守變成「攻撃力・守備力は…になる/を…にする」",
           _st_become(r"攻撃力・守備力"),
           {"item": ST_BOTH, "dir": DIR_BECOME}, "票17"),
    define("T169", CAT_STAT, SCOPE_PROCESS,
           "攻守互換「攻撃力と/・守備力を…入れ替える」(變成的一種)",
           r"攻撃力[と・]守備力を[^。]{0,25}?入れ替え",
           {"item": ST_BOTH, "dir": DIR_BECOME}, "票17"),
    # ══ 第3期(票17):效果傷害 ══════════════════════════════════
    # side 與 form 各自獨立發 tag(內容互為補集,遮蔽比對走子集語意);
    # 戰鬥傷害修飾(「戦闘ダメージは倍になる」)無「ダメージを与え/受け」
    # 動作形,天然不配(歸「其他」,批3)。
    define("T180", CAT_DAMAGE, SCOPE_PROCESS,
           "對手承受「相手に…ダメージを与える/ダメージを相手に与える」",
           r"(相手に(?:(?!自分[はもに])[^。]){0,30}?" + _V_DEAL
           + r"|ダメージを相手に与え(る(?!効果|場合|度)|、|。))",
           {"side": SIDE_OPP}, "票17"),
    define("T181", CAT_DAMAGE, SCOPE_PROCESS,
           "泛用給傷「…ダメージを与える」(無槽位,可被吸收)",
           _V_DEAL,
           {}, "票17"),
    define("T182", CAT_DAMAGE, SCOPE_PROCESS,
           "自傷「自分は…ダメージを受ける」(擋跨主語,參照詞放行)",
           r"自分[はも](?:(?!相手[はも])[^。]){0,40}?" + _V_TAKE,
           {"side": SIDE_OWN}, "票17"),
    define("T186", CAT_DAMAGE, SCOPE_PROCESS,
           "對手承受「相手は…ダメージを受ける」(「コントローラーから見て"
           "相手」是相對承受方,side 留給判定)",
           r"相手[はも](?:(?!自分[はも])[^。]){0,40}?" + _V_TAKE,
           {"side": SIDE_OPP}, "票17",
           exclude=r"から見て相手"),
    define("T183", CAT_DAMAGE, SCOPE_PROCESS,
           "雙方承受「お互い(に)…ダメージを与える/受ける」",
           r"お互い[^。]{0,35}?(" + _V_DEAL + r"|" + _V_TAKE + r")",
           {"side": SIDE_BOTH}, "票17"),
    define("T184", CAT_DAMAGE, SCOPE_PROCESS,
           "固定值傷害「N ダメージを与える/受ける」(數字前非×)",
           _NO_MUL + r"[０-９]+(の)?ダメージを[^。]{0,12}?"
           r"(与え(る(?!効果|場合|度)|、|。)|受け(る(?!効果|場合|度)|、|。))",
           {"form": FORM_FIXED}, "票17"),
    define("T185", CAT_DAMAGE, SCOPE_PROCESS,
           "參照值傷害「×N/分の/半分の/数値分だけ…ダメージ」",
           r"((×[０-９]+の?|分の?|の半分の|と同じ数値の?)ダメージ"
           r"|(数値分|の半分)だけ[^。]{0,8}?ダメージ)を[^。]{0,12}?"
           r"(与え(る(?!効果|場合|度)|、|。)|受け(る(?!効果|場合|度)|、|。))",
           {"form": FORM_REF}, "票17"),
    # ══ 第3期(票17):生命回復 ══════════════════════════════════
    define("T190", CAT_HEAL, SCOPE_PROCESS,
           "自分回復「自分は…回復する/自分のLPを回復」(「相手の手札の数×」"
           "這類參照詞放行,只擋對向主語與對向LP)",
           r"(自分[はも](?:(?!相手[はも]|相手の" + _LP + r")[^。]){0,45}?"
           r"|(?<![かはび])自分の" + _LP + r"を[^。]{0,20}?)" + _V_HEAL,
           {"side": SIDE_OWN}, "票17"),
    define("T191", CAT_HEAL, SCOPE_PROCESS,
           "相手回復「相手は…回復する/相手のLPを回復」(「自分か/または/及び"
           "相手の」二擇形不配,side 留給判定)",
           r"(相手[はも](?:(?!自分[はも]|自分の" + _LP + r")[^。]){0,45}?"
           r"|(?<![かはび])相手の" + _LP + r"を[^。]{0,20}?)" + _V_HEAL,
           {"side": SIDE_OPP}, "票17"),
    define("T192", CAT_HEAL, SCOPE_PROCESS,
           "泛用回復「…LP回復する」(無槽位,可被吸收)",
           _V_HEAL,
           {}, "票17"),
    define("T193", CAT_HEAL, SCOPE_PROCESS,
           "固定值回復「N LP回復/LPをN回復」(數字前非×;動作形限定)",
           r"(" + _NO_MUL + r"[０-９]+" + _LP + r"(を|分)?"
           r"|" + _LP + r"を[０-９]+(だけ)?)" + _V_HEAL,
           {"form": FORM_FIXED}, "票17"),
    define("T194", CAT_HEAL, SCOPE_PROCESS,
           "參照值回復「×N LP回復/分だけ…回復」(動作形限定)",
           r"(×[０-９]+" + _LP + r"?を?"
           r"|分(だけ|の)(?:(?!。)[^。]){0,20}?)" + _V_HEAL,
           {"form": FORM_REF}, "票17"),
    # ══ 第3期(票17):LP支付(無位置槽位,裁定票15)══════════════
    # 發動代價的支付方恆為發動者(=我方);處理段的維持/通行費形支付方照
    # 句面錨,錨不到留空。
    define("T200", CAT_LP_PAY, SCOPE_COST,
           "支付代價「LPを払って/払い発動」(「相手がLPを払って…」是觸發"
           "敘述不配)",
           _LP + r"を[^。]{0,12}?払(い|って)",
           {"side": SIDE_OWN}, "票17",
           exclude=r"相手が(LP|ＬＰ)を払"),
    define("T201", CAT_LP_PAY, SCOPE_COST,
           "固定值支付「N LPを払う」",
           _NO_MUL + r"[０-９]+" + _LP + r"を払",
           {"side": SIDE_OWN, "form": FORM_FIXED}, "票17",
           exclude=r"相手が(LP|ＬＰ)を払"),
    define("T202", CAT_LP_PAY, SCOPE_COST,
           "比例支付「LPを半分払う」",
           _LP + r"を半分払",
           {"side": SIDE_OWN, "form": FORM_RATIO}, "票17",
           exclude=r"相手が(LP|ＬＰ)を払"),
    define("T203", CAT_LP_PAY, SCOPE_PROCESS,
           "維持/通行費支付「LPを払う。/払う事ができる/払わなければ/払えば」"
           "(處理段;「払って…発動する度」「払う場合」是觸發敘述不配)",
           _LP + r"を[^。]{0,12}?払(う[。、（]|う事ができる|わなければ|えば)",
           {}, "票17"),
    define("T204", CAT_LP_PAY, SCOPE_PROCESS,
           "對手通行費「相手は…LPを払わなければ/払う」",
           r"相手[はがも](?:(?!自分)[^。]){0,20}?" + _LP
           + r"を払(わなければ|う[。、]|う事ができる|えば)",
           {"side": SIDE_OPP}, "票17"),
    define("T205", CAT_LP_PAY, SCOPE_PROCESS,
           "處理段固定值支付「N LPを払う。/払わなければ」",
           _NO_MUL + r"[０-９]+" + _LP
           + r"を払(う[。、]|う事ができる|わなければ|えば)",
           {"form": FORM_FIXED}, "票17"),
    define("T206", CAT_LP_PAY, SCOPE_PROCESS,
           "自我通行費「自分は…LPを払わなければならない」(攻擊宣言稅等)",
           r"自分[はも](?:(?!相手)[^。]){0,15}?" + _LP
           + r"を払(わなければ|う[。、]|えば)",
           {"side": SIDE_OWN}, "票17"),
    # ══ 第3期(票17):LP失去 ══════════════════════════════════
    define("T210", CAT_LP_LOSE, SCOPE_PROCESS,
           "自分失去「自分は…LPを失う」(擋跨主語,參照詞放行)",
           r"自分[はも](?:(?!相手[はも])[^。]){0,45}?" + _LP
           + r"を失う(?!事|場合|度)",
           {"side": SIDE_OWN}, "票17"),
    define("T211", CAT_LP_LOSE, SCOPE_PROCESS,
           "相手失去「相手は…LPを失う」",
           r"相手[はも](?:(?!自分[はも])[^。]){0,45}?" + _LP
           + r"を失う(?!事|場合|度)",
           {"side": SIDE_OPP}, "票17"),
    define("T212", CAT_LP_LOSE, SCOPE_PROCESS,
           "泛用失去「…LPを失う」(無槽位,可被吸收)",
           _LP + r"を失う(?!事|場合|度)",
           {}, "票17"),
    define("T213", CAT_LP_LOSE, SCOPE_PROCESS,
           "參照值失去「×N LPを失う」",
           r"×[０-９]+の?" + _LP + r"を失う(?!事|場合|度)",
           {"form": FORM_REF}, "票17"),
    define("T214", CAT_LP_LOSE, SCOPE_PROCESS,
           "固定值失去「N LPを失う」(數字前非×)",
           _NO_MUL + r"[０-９]+" + _LP + r"を失う(?!事|場合|度)",
           {"form": FORM_FIXED}, "票17"),
    # ══ 第4期(票18):行動限制 ══════════════════════════════════
    # 否定尾邊界(_CANT)擋修飾形(「通常召喚できないモンスター」)與程序
    # 條件(「できない場合」);side 錨與跨主語防護沿第3期路數。
    define("T220", CAT_RESTRICT, SCOPE_PROCESS,
           "泛用特召限制「特殊召喚/S・X・リンク等召喚できない」(可被吸收)",
           _V_RS_SS,
           {"what": RS_SP}, "票18"),
    define("T221", CAT_RESTRICT, SCOPE_PROCESS,
           "對手特召限制「相手は…特殊召喚できない」(「から見て相手」是"
           "相對指涉,side 留給判定)",
           r"相手[はも](?:(?!自分)[^。]){0,40}?" + _V_RS_SS,
           {"what": RS_SP, "side": SIDE_OPP}, "票18",
           exclude=r"から見て相手"),
    define("T222", CAT_RESTRICT, SCOPE_PROCESS,
           "自我特召限制「自分は…特殊召喚できない」(誓約尾句,批2)",
           r"自分[はも](?:(?!相手)[^。]){0,40}?" + _V_RS_SS,
           {"what": RS_SP, "side": SIDE_OWN}, "票18"),
    define("T223", CAT_RESTRICT, SCOPE_PROCESS,
           "雙方特召限制「お互いに…特殊召喚できない」",
           r"お互い[はにも]{1,2}[^。]{0,40}?" + _V_RS_SS,
           {"what": RS_SP, "side": SIDE_BOTH}, "票18"),
    define("T224", CAT_RESTRICT, SCOPE_PROCESS,
           "通常召喚面限制「(通常/アドバンス/無印)召喚できない」(值域無"
           "通常值=其他,票18;特殊與召喚法特定形歸 T220 由負向後看擋)",
           r"(?<!殊)(?<!P)(?<!S)(?<!X)(?<!ク)(?<!合)(?<!式)(?<!転)召喚"
           + _CANT,
           {"what": RS_X}, "票18"),
    define("T225", CAT_RESTRICT, SCOPE_PROCESS,
           "合記召喚限制「召喚・特殊召喚できない」的通常面(特召面歸 T220)",
           r"召喚・特殊召喚" + _CANT,
           {"what": RS_X}, "票18"),
    define("T226", CAT_RESTRICT, SCOPE_PROCESS,
           "泛用發動限制「効果/カードを発動できない」(可被吸收)",
           _V_RS_ACT,
           {"what": RS_ACT}, "票18",
           exclude=_RS_ACT_EXCLUDE),
    define("T227", CAT_RESTRICT, SCOPE_PROCESS,
           "對手發動限制「相手は…発動できない」",
           r"相手[はも](?:(?!自分)[^。]){0,40}?" + _V_ACT_TAIL,
           {"what": RS_ACT, "side": SIDE_OPP}, "票18",
           exclude=_RS_ACT_EXCLUDE + r"|から見て相手"),
    define("T228", CAT_RESTRICT, SCOPE_PROCESS,
           "自我發動限制「自分は…発動できない」(誓約尾句)",
           r"自分[はも](?:(?!相手)[^。]){0,40}?" + _V_ACT_TAIL,
           {"what": RS_ACT, "side": SIDE_OWN}, "票18",
           exclude=_RS_ACT_EXCLUDE),
    define("T229", CAT_RESTRICT, SCOPE_PROCESS,
           "雙方發動限制「お互いに…発動できない」",
           r"お互い[はにも]{1,2}[^。]{0,40}?" + _V_ACT_TAIL,
           {"what": RS_ACT, "side": SIDE_BOTH}, "票18",
           exclude=_RS_ACT_EXCLUDE),
    define("T230", CAT_RESTRICT, SCOPE_PROCESS,
           "泛用攻擊限制「攻撃(宣言)できない」(直接攻擊歸戰鬥規則,批2;"
           "可被吸收)",
           _V_RS_ATK,
           {"what": RS_ATK}, "票18"),
    define("T231", CAT_RESTRICT, SCOPE_PROCESS,
           "自身攻擊限制「このカードは攻撃できない」",
           r"このカード[はも](?:(?!モンスター|その|相手|自分)[^。]){0,20}?"
           + _V_RS_ATK,
           {"what": RS_ATK, "side": SIDE_SELF}, "票18"),
    define("T232", CAT_RESTRICT, SCOPE_PROCESS,
           "對手側攻擊限制「(〜の)相手モンスターは攻撃できない」",
           r"相手(フィールドの)?(?:(?!自分)[^。]){0,30}?モンスターは"
           r"[^。]{0,20}?" + _V_RS_ATK,
           {"what": RS_ATK, "side": SIDE_OPP}, "票18",
           exclude=r"から見て相手"),
    define("T233", CAT_RESTRICT, SCOPE_PROCESS,
           "我方側攻擊限制「(他の)自分のモンスターは攻撃できない」",
           r"自分の(?:(?!相手)[^。]){0,30}?モンスターは[^。]{0,20}?"
           + _V_RS_ATK,
           {"what": RS_ATK, "side": SIDE_OWN}, "票18"),
    define("T234", CAT_RESTRICT, SCOPE_PROCESS,
           "強制攻擊「攻撃しなければならない」(禁止與強制都是限制,票18)",
           r"攻撃しなければならない",
           {"what": RS_ATK}, "票18"),
    define("T235", CAT_RESTRICT, SCOPE_PROCESS,
           "表示形式限制「表示形式を/の変更(も)できない」",
           r"表示形式[のはを]?変更" + _CANT,
           {"what": RS_POS}, "票18"),
    define("T236", CAT_RESTRICT, SCOPE_PROCESS,
           "解放限制「リリースできない」(值域無對應保護值=其他,票18)",
           r"リリース" + _CANT,
           {"what": RS_X}, "票18"),
    define("T237", CAT_RESTRICT, SCOPE_PROCESS,
           "素材限制「素材にできない/素材とする事はできない」",
           r"素材[にと]" + _CANT,
           {"what": RS_X}, "票18"),
    define("T238", CAT_RESTRICT, SCOPE_PROCESS,
           "蓋放限制「セットできない」",
           r"セット" + _CANT,
           {"what": RS_X}, "票18"),
    define("T239", CAT_RESTRICT, SCOPE_PROCESS,
           "單回合特召限制「このターン/ターン終了時まで…特殊召喚できない」",
           _TERM_TURN_ANCHOR + r"、?[^。]*?" + _V_RS_SS,
           {"what": RS_SP, "term": TERM_TURN}, "票18"),
    define("T240", CAT_RESTRICT, SCOPE_PROCESS,
           "單回合發動限制「このターン/ターン終了時まで…発動できない」",
           _TERM_TURN_ANCHOR + r"、?[^。]*?" + _V_ACT_TAIL,
           {"what": RS_ACT, "term": TERM_TURN}, "票18",
           exclude=_RS_ACT_EXCLUDE),
    define("T241", CAT_RESTRICT, SCOPE_PROCESS,
           "單回合攻擊限制「このターン…攻撃できない」",
           _TERM_TURN_ANCHOR + r"、?[^。]*?" + _V_RS_ATK,
           {"what": RS_ATK, "term": TERM_TURN}, "票18"),
    define("T242", CAT_RESTRICT, SCOPE_PROCESS,
           "持續特召限制「〜限り、…特殊召喚できない」(「しない限り」是"
           "條件不是期間)",
           r"(?<!ない)限り、?[^。]*?" + _V_RS_SS,
           {"what": RS_SP, "term": TERM_CONT}, "票18"),
    define("T243", CAT_RESTRICT, SCOPE_PROCESS,
           "持續發動限制「〜限り、…発動できない」",
           r"(?<!ない)限り、?[^。]*?" + _V_ACT_TAIL,
           {"what": RS_ACT, "term": TERM_CONT}, "票18",
           exclude=_RS_ACT_EXCLUDE),
    define("T244", CAT_RESTRICT, SCOPE_PROCESS,
           "持續攻擊限制「〜限り、…攻撃できない」",
           r"(?<!ない)限り、?[^。]*?" + _V_RS_ATK,
           {"what": RS_ATK, "term": TERM_CONT}, "票18"),
    define("T245", CAT_RESTRICT, SCOPE_PROCESS,
           "素材使用限制「〜召喚に(も)しか使用できない」(素材にできない"
           "的使用形)",
           r"召喚に(も|は)?しか使用でき(ない|ず)",
           {"what": RS_X}, "票18"),
    # ══ 第4期(票18):耐性/保護 ══════════════════════════════════
    define("T250", CAT_PROTECT, SCOPE_PROCESS,
           "戰鬥破壞耐性「戦闘(・/及び〜効果)では破壊されない」(合記兩面"
           "各貼)",
           r"戦闘((・|及び)[^。]{0,15}?効果)?では破壊され" + _NOT,
           {"what": PT_BD}, "票18"),
    define("T251", CAT_PROTECT, SCOPE_PROCESS,
           "效果破壞耐性「(〜の)効果で(は/も)破壊されない」",
           r"効果で(は|も)?破壊され" + _NOT,
           {"what": PT_ED}, "票18",
           exclude=r"この効果で(は)?[^。]{0,20}?破壊され(ない|ず)"),
    define("T252", CAT_PROTECT, SCOPE_PROCESS,
           "效果對象耐性「効果の対象にならない/にできない」(能動形同義,"
           "票18)",
           r"効果の対象に(な(?:ら|れ)?" + _NOT + r"|でき" + _NOT + r")",
           {"what": PT_TG}, "票18"),
    define("T253", CAT_PROTECT, SCOPE_PROCESS,
           "全效果耐性「効果を受けない」(不論限定範圍一律全效果,票18)",
           r"効果[をは]受け" + _NOT,
           {"what": PT_AE}, "票18"),
    define("T254", CAT_PROTECT, SCOPE_PROCESS,
           "除外耐性「除外できない/除外されない」(「この効果で…除外"
           "できない」是自我效果限制不貼)",
           r"除外(され" + _NOT + r"|(する事)?[はがも]?でき"
           r"(ない(?=[。、）（]|$)|ず(?=[、。])|なくな))",
           {"what": PT_BN}, "票18",
           exclude=r"この(カード名の)?(この)?効果で[^。]{0,25}?除外でき"),
    define("T255", CAT_PROTECT, SCOPE_PROCESS,
           "代替破壞「破壊される場合…代わりに〜」(耐性,批2)",
           r"破壊される(場合|モンスター|カード)[^。]{0,20}?代わりに",
           {"what": PT_RP}, "票18"),
    define("T256", CAT_PROTECT, SCOPE_PROCESS,
           "無效化保護「無効化されない/無効にされない・できない」"
           "(值域無對應 what 值,缺值只貼類別)",
           r"無効化され(ない|ず)|無効に(され|でき)(ない|ず)|無効にならない",
           {}, "票18"),
    define("T257", CAT_PROTECT, SCOPE_PROCESS,
           "自身側保護「このカードは…されない/受けない」",
           r"このカード[はも](?:(?!モンスター)[^。]){0,45}?"
           r"(破壊され(ない|ず)|効果[をは]受け(ない|ず)|除外でき(ない|ず)"
           r"|効果の対象にな(らない|らず))",
           {"side": SIDE_SELF}, "票18"),
    define("T258", CAT_PROTECT, SCOPE_PROCESS,
           "自身對象保護「このカードを効果の対象にできない」(span 收緊,"
           "「このカードをリンク先とする〜モンスター」的受詞是別人)",
           r"このカードを[^。]{0,12}?効果の対象にでき(ない|ず)",
           {"what": PT_TG, "side": SIDE_SELF}, "票18"),
    define("T259", CAT_PROTECT, SCOPE_PROCESS,
           "我方側保護「自分フィールド/墓地の…されない/にできない」",
           r"自分(フィールド|の墓地)の(?:(?!このカード)[^。]){0,45}?"
           r"(破壊され(ない|ず)|効果[をは]受け(ない|ず)|除外でき(ない|ず)"
           r"|効果の対象に(なら|でき)(ない|ず))",
           {"side": SIDE_OWN}, "票18"),
    # ══ 第5期(票19):表示形式變更 ══════════════════════════════════
    # to 映射照字面:裏側(守備)表示=裡側、表側守備/守備=守備、表側攻撃/
    # 攻撃=攻擊;「表示形式を変更」自由選 to 缺值(裁定批3)。
    define("T260", CAT_POSITION, SCOPE_PROCESS,
           "自由變更「表示形式を変更する」(to 缺值,可被吸收)",
           r"表示形式を変更(する(?!事(は|が|も)?でき|効果|場合)"
           r"|できる|し、|し。)",
           {}, "票19"),
    define("T261", CAT_POSITION, SCOPE_PROCESS,
           "變成攻擊表示「(表側)攻撃表示にする/になる」",
           r"攻撃表示" + _V_PS,
           {"to": PS_ATK}, "票19"),
    define("T262", CAT_POSITION, SCOPE_PROCESS,
           "變成守備表示「(表側)守備表示にする/になる」(裏側形歸 T263)",
           r"(?<!裏側)守備表示" + _V_PS,
           {"to": PS_DEF}, "票19"),
    define("T263", CAT_POSITION, SCOPE_PROCESS,
           "變成裡側表示「裏側(守備)表示にする/になる」",
           r"裏側(守備)?表示" + _V_PS,
           {"to": PS_FD}, "票19"),
    define("T264", CAT_POSITION, SCOPE_PROCESS,
           "或格「攻撃表示か裏側守備表示にする」兩面各貼(或格都貼,票17)",
           r"攻撃表示(か|または)裏側守備表示" + _V_PS,
           ({"to": PS_ATK}, {"to": PS_FD}), "票19"),
    define("T268", CAT_POSITION, SCOPE_PROCESS,
           "或格「攻撃表示か/または表側守備表示にする」兩面各貼",
           r"攻撃表示(か|または)表側守備表示" + _V_PS,
           ({"to": PS_ATK}, {"to": PS_DEF}), "票19"),
    define("T265", CAT_POSITION, SCOPE_PROCESS,
           "自身變守備「このカードを守備表示にする」",
           r"このカードを守備表示" + _V_PS,
           {"to": PS_DEF, "side": SIDE_SELF}, "票19"),
    define("T266", CAT_POSITION, SCOPE_PROCESS,
           "自身變裡側「このカードを裏側守備表示にする」",
           r"このカードを裏側(守備)?表示" + _V_PS,
           {"to": PS_FD, "side": SIDE_SELF}, "票19"),
    define("T267", CAT_POSITION, SCOPE_PROCESS,
           "自身自由變更「このカードの表示形式を変更する」",
           r"このカードの表示形式を変更(する(?!事(は|が|も)?でき|効果|場合)"
           r"|できる|し、|し。)",
           {"side": SIDE_SELF}, "票19"),
    # ══ 第5期(票19):控制權轉移 ══════════════════════════════════
    # 「コントロールを得た」完成/修飾形非動作(動詞形天然不配);期間
    # (エンドフェイズまで等)不建模。
    define("T270", CAT_CONTROL, SCOPE_PROCESS,
           "奪取「コントロールを(〜まで)得る」(「得る事ができる」選擇性"
           "動作照貼,払う事ができる先例)",
           r"コントロールを[^。]{0,25}?得(る(?!事(は|が|も)?でき(ない|ず)"
           r"|効果)|て|、)",
           {"dir": CT_GET}, "票19"),
    define("T271", CAT_CONTROL, SCOPE_PROCESS,
           "移交「コントロールを相手に移す」",
           r"コントロールを相手に移(す(?!事(は|が|も)?でき)|し)",
           {"dir": CT_GIVE}, "票19"),
    define("T272", CAT_CONTROL, SCOPE_PROCESS,
           "互換「コントロールを入れ替える」兩向各貼(代行裁定,票19)",
           r"コントロールを入れ替え(る(?!事(は|が|も)?でき)|、|。)",
           ({"dir": CT_GET}, {"dir": CT_GIVE}), "票19"),
    # ══ 第5期(票19):性質變更 ══════════════════════════════════
    # item 錨在六值名詞上;值域外的扱う形(チューナー/通常モンスター)缺值
    # 只貼類別(無效化保護 what 缺值先例);「(〜としては扱わない)」括弧
    # 註記與「元々の〜」參照形無動作動詞,天然不配。
    define("T280", CAT_PROPERTY, SCOPE_PROCESS,
           "卡名歸屬「カード名を/は…として扱う」",
           r"カード名[はを][^。]{0,40}?" + _V_TREAT,
           {"item": PP_NAME}, "票19"),
    define("T281", CAT_PROPERTY, SCOPE_PROCESS,
           "具名代稱「「X」(モンスター/カード)として扱う」(卡名/字段歸屬)",
           r"「[^」]+」(モンスター|カード)?" + _V_TREAT,
           {"item": PP_NAME}, "票19"),
    define("T282", CAT_PROPERTY, SCOPE_PROCESS,
           "種族變更「〜族になる」",
           r"族" + _V_PP_NARU,
           {"item": PP_RACE}, "票19"),
    define("T283", CAT_PROPERTY, SCOPE_PROCESS,
           "屬性變更「〜属性になる」",
           r"属性" + _V_PP_NARU,
           {"item": PP_ATTR}, "票19"),
    define("T284", CAT_PROPERTY, SCOPE_PROCESS,
           "種族屬性合記「種族・属性になる」兩面各貼",
           r"種族・属性にな",
           ({"item": PP_RACE}, {"item": PP_ATTR}), "票19"),
    define("T285", CAT_PROPERTY, SCOPE_PROCESS,
           "屬性視同「〜属性として(も)扱う」",
           r"属性(モンスター)?" + _V_TREAT,
           {"item": PP_ATTR}, "票19"),
    define("T286", CAT_PROPERTY, SCOPE_PROCESS,
           "等級變成「レベルは/が…になる」(含「〜と同じ/合計したレベル"
           "になる」主語前置形)",
           r"(レベル[はが][^。]{0,32}?|と同じレベル|したレベル)"
           + _V_PP_NARU,
           {"item": PP_LV}, "票19"),
    define("T287", CAT_PROPERTY, SCOPE_PROCESS,
           "等級指定「レベルを…にする」",
           r"レベルを[^。]{0,30}?" + _V_PP_SURU,
           {"item": PP_LV}, "票19"),
    define("T288", CAT_PROPERTY, SCOPE_PROCESS,
           "等級升降「レベルを…上げる/下げる」(或格都貼同一 tag;"
           "「上げる事ができる」選擇性動作照貼)",
           r"レベルを[^。]{0,25}?(上|下)げ(る(?!事(は|が|も)?でき(ない|ず))"
           r"|、|。|て)",
           {"item": PP_LV}, "票19"),
    define("T289", CAT_PROPERTY, SCOPE_PROCESS,
           "等級自升降「レベルは/が…上がる/下がる」(參照長句 span 放寬)",
           r"レベル[はが][^。]{0,32}?(上|下)が(る(?!事(は|が|も)?でき)"
           r"|り、|り。)",
           {"item": PP_LV}, "票19"),
    define("T290", CAT_PROPERTY, SCOPE_PROCESS,
           "階級操作「ランクを…上げる/下げる/にする」",
           r"ランクを[^。]{0,25}?((上|下)げ(る(?!事(は|が|も)?でき(ない|ず))"
           r"|、|。|て)"
           r"|に(する(?!事(は|が|も)?でき)|し、|でき))",
           {"item": PP_RK}, "票19"),
    define("T291", CAT_PROPERTY, SCOPE_PROCESS,
           "階級變成「ランクは/が…になる/上がる/下がる」",
           r"ランク[はが][^。]{0,30}?(にな(る(?!事(は|が|も)?でき)|り、|り。)"
           r"|(上|下)が(る(?!事(は|が|も)?でき)|り、|り。))",
           {"item": PP_RK}, "票19"),
    define("T292", CAT_PROPERTY, SCOPE_PROCESS,
           "等階合記「レベル・/またはランクを…」兩面各貼",
           r"レベル(・|または)ランク[をはが][^。]{0,30}?"
           r"((上|下)げ|(上|下)が|にな[るり]|に(する|し、|でき))",
           ({"item": PP_LV}, {"item": PP_RK}), "票19"),
    define("T293", CAT_PROPERTY, SCOPE_PROCESS,
           "刻度變更「(P)スケールは/を…になる/にする」",
           r"スケール[はをが][^。]{0,30}?(にな(る(?!事(は|が|も)?でき)"
           r"|り、|り。)|に(する(?!事(は|が|も)?でき)|し、|し。|でき))",
           {"item": PP_SC}, "票19"),
    define("T294", CAT_PROPERTY, SCOPE_PROCESS,
           "素材時等級視同「レベルを N として扱う」",
           r"レベルを[^。]{0,12}?" + _V_TREAT,
           {"item": PP_LV}, "票19"),
    define("T295", CAT_PROPERTY, SCOPE_PROCESS,
           "調整視同「チューナー(以外のモンスター)として扱う」(值域無 "
           "item 值,缺值只貼類別)",
           r"チューナー(以外のモンスター)?" + _V_TREAT,
           {}, "票19"),
    define("T296", CAT_PROPERTY, SCOPE_PROCESS,
           "通常怪視同「通常モンスターとして扱う」(缺值只貼類別)",
           r"通常モンスター" + _V_TREAT,
           {}, "票19"),
    define("T297", CAT_PROPERTY, SCOPE_PROCESS,
           "卡名×持續「存在する限り…カード名を…として扱う」(兩序皆收)",
           r"(存在する限り、?[^。]{0,25}?カード名[はを]"
           r"|カード名[はを][^。]{0,30}?存在する限り)[^。]{0,40}?" + _V_TREAT,
           {"item": PP_NAME, "term": TERM_CONT}, "票19"),
    define("T298", CAT_PROPERTY, SCOPE_PROCESS,
           "通常怪視同×持續「存在する限り、通常モンスターとして扱う」",
           r"存在する限り、?通常モンスター" + _V_TREAT,
           {"term": TERM_CONT}, "票19"),
    define("T299", CAT_PROPERTY, SCOPE_PROCESS,
           "調整視同×單回合「このターン…チューナーとして扱う」",
           _TERM_TURN_ANCHOR + r"、?[^。]{0,25}?チューナー" + _V_TREAT,
           {"term": TERM_TURN}, "票19"),
    # ══ 第5期(票19):計數器操作 ══════════════════════════════════
    # カウンター 錨擋「X素材を取り除く」;「置く効果を持つ」修飾形與
    # 「置く事ができるカード」參照形由動詞邊界擋;「カウンターが置かれた」
    # 觸發形無を粒子,天然不配。
    define("T310", CAT_COUNTER, SCOPE_PROCESS,
           "放置「カウンターを(N つ)置く」",
           r"カウンターを[^。]{0,20}?置(く(?=[。、（]|$)|き、|き。"
           r"|く事ができ(る(?=[。、（]|$)|、))",
           {"act": CNT_PUT}, "票19"),
    define("T311", CAT_COUNTER, SCOPE_PROCESS,
           "去除「カウンターを(N つ)取り除く」(處理段;代替破壞附帶照貼;"
           "「〜につき」句形 span 放寬)",
           r"カウンターを[^。]{0,30}?取り除(く(?=[。、（]|$)|き、|き。|ける"
           r"|く事ができ(る(?=[。、（]|$)|、))",
           {"act": CNT_RM}, "票19"),
    define("T312", CAT_COUNTER, SCOPE_COST,
           "去除代價「カウンターを…取り除いて/取り除き発動」",
           r"カウンターを[^。]{0,30}?取り除(き|いて)",
           {"act": CNT_RM}, "票19"),
)

# ── 觸發時機規則(掃描發動子句;同句多個時機取最先寫出的)──
# 值域見 vocab 的 timing;只上在誘發系承載類型(q/t/魔陷十值)、且發動子句
# 帶「発動」的效果句。樣式的順序無關緊要——取的是**命中位置最靠前**的那一條;
# 位置相同(同一個字起頭)時取樣式更長的(特殊召喚 vs 召喚 由排除字元處理)。
def timing(rid, value, condition, pattern, exclude=None, fallback=False):
    """fallback 規則只在**沒有任何具名規則命中**時才開火(「其他」兜底):
    比命中位置的話,句首的觸發連接詞會搶走具名時機的位置優勢。"""
    return {
        "id": rid,
        "value": value,
        "condition": condition,
        "pattern": re.compile(pattern),
        "exclude": re.compile(exclude) if exclude else None,
        "fallback": fallback,
    }


TIMING_RULES = (
    timing("TM1", "召喚成功時",
           "「召喚に成功した/召喚した場合・時」(排除特殊召喚;反轉召喚與"
           "A召喚是通常召喚家族,照歸本值)",
           r"(?<!特殊)召喚(・反転召喚)?(・特殊召喚)?"
           r"(に成功した|した場合|した時|する度)"),
    timing("TM2", "特殊召喚成功時",
           "「特殊召喚に成功した/した・された場合・時/する際」與召喚法特定形"
           "(S/X/リンク/融合/儀式/P召喚した)",
           r"特殊召喚(に成功した|した場合|した時|された場合|された時|する際)|"
           r"(S|X|リンク|融合|儀式|P)召喚(に成功した|した場合|した時)"),
    timing("TM3", "反轉時", "「リバースした」",
           r"リバースした"),
    timing("TM4", "被破壞時", "「破壊された/破壊され」(戰鬥/效果合寫不拆)",
           r"破壊され"),
    timing("TM5", "被送去墓地時", "「墓地へ送られた」",
           r"墓地へ送られた"),
    timing("TM6", "從場上離開時", "「フィールドから離れた」",
           r"フィールドから離れた"),
    timing("TM7", "被除外時", "「除外された」",
           r"除外された(場合|時)"),
    timing("TM8", "攻擊宣言時", "「攻撃宣言時/攻撃を宣言した」",
           r"攻撃宣言時|攻撃を宣言した"),
    timing("TM9", "傷害步驟時點", "「ダメージステップ/ダメージ計算」",
           r"ダメージステップ|ダメージ計算"),
    timing("TM10", "給予戰鬥傷害時", "「戦闘ダメージを与えた」",
           r"戦闘ダメージを与えた"),
    timing("TM11", "受到傷害時", "「ダメージを受けた」",
           r"ダメージを受けた"),
    timing("TM12", "準備階段", "「スタンバイフェイズに発動」",
           r"スタンバイフェイズ"),
    timing("TM13", "主要階段", "「メインフェイズに発動」(誘發系)",
           r"メインフェイズ"),
    timing("TM14", "戰鬥階段", "「バトルフェイズに発動」",
           r"バトルフェイズ"),
    timing("TM15", "結束階段", "「エンドフェイズに発動」",
           r"エンドフェイズ"),
    timing("TM16", "對手發動效果時", "「相手が…発動した時/場合」",
           r"相手[がの][^。]{0,30}?発動(した|する)(時|場合|際)"),
    timing("TM19", "被送去墓地時", "「(手札から)捨てられた」(棄牌即送墓)",
           r"捨てられた"),
    timing("TM20", "攻擊宣言時", "「攻撃対象に選択された時」(選定發生於宣言時點)",
           r"攻撃対象に選択された"),
    timing("TM21", "其他",
           "兜底:發動子句帶觸發事件、但不落在 16 個具名值的任何一個"
           "(リリースされた/装備された/カウンター/宣言/セットされた/"
           "手札に加わった等,值域裁定不細分)",
           r"た場合|た時|時に|時、|する際|ダメージ計算|ダメージステップ"
           r"|攻撃宣言|フェイズに発動", fallback=True),
)


# ---------------------------------------------------------------- 套用

def active(rules=RULES):
    """已開貼類別(PHASES)的規則——體系凍結後,規則跟著期次上工。"""
    return [rule for rule in rules if rule["cat"] in PHASES]


def emit(text, scope_rules, pos, action_text=None):
    """一個切段 × 一批規則 → 發出的 tag 清單(已帶 cat / pos / src / rule)。

    「對象」範圍的規則要 pattern(對象指定)與 action(指示詞動作)兩段都
    命中;action_text 是那個動作段(處理段)。
    """
    tags = []
    for rule in scope_rules:
        if not text or not rule["pattern"].search(text):
            continue
        if rule["exclude"] is not None and rule["exclude"].search(text):
            continue
        if rule["action"] is not None and not (
                action_text and rule["action"].search(action_text)):
            continue
        for template in rule["tags"]:
            tag = {"cat": rule["cat"], **template, "pos": pos,
                   "src": TAG_SRC_RULE, "rule": rule["id"]}
            # 位置豁免類別(LP支付,裁定票15):正典沒有 pos 槽位,帶著會
            # 編不進索引短碼——在源頭拿掉,不是留給 webindex 炸
            if rule["cat"] in _POS_EXEMPT_CATS:
                del tag["pos"]
            tags.append(tag)
    return tags


def _content(tag):
    return tuple(sorted((k, v) for k, v in tag.items()
                        if k not in ("src", "rule", "ticket")))


def _absorb(tags):
    """同內容去重(第一個到的規則具名)。

    **不做子集吸收**:「フィールド・墓地・除外状態の…手札に加える」這種多源
    列舉句,特定規則只認得起點之一(除外→手牌),泛用規則(→手牌)才蓋得住
    其餘起點——把泛用讓給特定會漏掉場上/墓地那幾條腿(票10 遮蔽補抽實測)。
    泛用 tag 是特定 tag 的子集時兩個都留:內容誠實,搜尋語意不受影響。
    """
    kept = []
    for tag in tags:
        if any(_content(prior) == _content(tag) for prior in kept):
            continue
        kept.append(tag)
    return kept


def match_tags(activation, process, rules=None):
    """效果句的切段 → 規則層發出的 tag 清單(已做內容吸收)。

    activation 是**含「発動」的**發動子句(不含時傳 None,成本與對象規則不掃);
    process 是處理段(發動子句之後的文字;無發動子句時是整句)。
    """
    rules = active(RULES) if rules is None else rules
    tags = emit(process, [r for r in rules if r["scope"] == SCOPE_PROCESS],
                POS_EFFECT)
    tags += emit(activation, [r for r in rules if r["scope"] == SCOPE_COST],
                 POS_COST)
    tags += emit(activation,
                 [r for r in rules if r["scope"] == SCOPE_TARGET],
                 POS_EFFECT, action_text=process)
    return _absorb(tags)


def match_timing(activation, rules=TIMING_RULES):
    """發動子句 → (時機值, 規則編號);判不出時回 (None, None)。

    同句多個時機取**最先寫出的**(裁定批4):比的是命中位置,不是規則順序。
    """
    if not activation:
        return None, None
    best = None
    fallback = None
    for rule in rules:
        match = rule["pattern"].search(activation)
        if match is None:
            continue
        if rule["exclude"] is not None and rule["exclude"].search(activation):
            continue
        if rule.get("fallback"):
            if fallback is None:
                fallback = (match.start(), rule["value"], rule["id"])
            continue
        if best is None or match.start() < best[0]:
            best = (match.start(), rule["value"], rule["id"])
    best = best or fallback
    return (best[1], best[2]) if best else (None, None)


# 時機粗篩:發動子句帶這些觸發事件寫法才算時機候選(純速度型的「相手ターン
# にも発動できる」沒有時機可標)。與 TM21 兜底規則同一張事件表——兩處各改
# 會讓零空缺母體與兜底漂移,所以住同一個模組、比鄰宣告。
TIMING_SCREEN = re.compile(
    r"た場合|た時|時に|時、|する際|ダメージ計算|ダメージステップ|攻撃宣言"
    r"|フェイズに")


# ---------------------------------------------------------------- 粗篩

# 類別粗篩:圈出「應該屬於這一類」的候選句(判定票的入選條件、seal 零空缺的
# 母體)。錨在**動作動詞**上,否定形(できない/されない)與純觸發條件不算候選
# ——那些句子本來就不該貼這一類。粗篩的漏網是已接受的殘餘風險(ADR-0013)。
_SCREENS = {
    CAT_MOVE: (
        re.compile(
            r"手札に加え|特殊召喚(する|できる|し、)|墓地へ送(る|り|って)|"
            r"を除外(する|し、|できる)|除外して|手札に戻(す|し)|"
            r"デッキに戻(す|し)|捨て(る|、|て発動)|リリースし|"
            r"セット(する|できる)|Pゾーンに置|デッキの一番(上|下)に|"
            r"デッキに加え"),
        re.compile(r"特殊召喚できない|特殊召喚されない|除外できない|"
                   r"除外されない|戻せない"
                   r"|リリースして(表側表示で)?(召喚|A召喚|アドバンス召喚)"
                   r"|リリースして[^。]{0,10}?召喚する事もできる"),
    ),
    # 第2期(票16):破壞——動作形與代價形;「無効にし破壊」讓給無效的附帶
    # 槽位、「代わりに破壊」讓給耐性(代替破壞),與規則排除同一組樣式。
    CAT_DESTROY: (
        re.compile(r"破壊(する(?!事(は|が|も)?でき(ない|ず)|効果|場合"
                   r"|モンスター|カード)"
                   r"|し、|し。|できる|し(て|、)[^。]{0,30}?発動できる)"),
        re.compile(r"(?<!リリースの)代わりに[^。]{0,30}?破壊"
                   r"|破壊する効果|戦闘[でに][^。]{0,15}?破壊し"),
    ),
    # 第2期(票16):無效——「無効化されない/無効にされない」是耐性不圈。
    CAT_NEGATE: (
        re.compile(r"無効に(する(?!事(は|が|も)?でき)|し|できる)"
                   r"|無効化され(る|、)"),
        re.compile(r"無効化され(ない|ず)|無効に(され|でき)(ない|ず)"
                   r"|無効にならない"),
    ),
    # 第3期(票17):攻守調整——主語粒子錨(「攻撃力２０００アップの装備〜
    # 扱い」修飾形無粒子,天然不圈);完成式/否定/描述形不圈。
    CAT_STAT: (
        re.compile(r"(攻撃力|守備力)[はがを][^。]{0,60}?"
                   r"(アップ(する|し、|し。|できる)"
                   r"|ダウン(する|し、|し。|できる))"
                   r"|(攻撃力|守備力)[はが][^。]{0,60}?にな(る|り、|り。)"
                   r"|(攻撃力|守備力)を[^。]{0,60}?(にする|にし、|にし。"
                   r"|にできる)"
                   r"|攻撃力[と・]守備力を[^。]{0,25}?入れ替え"),
        re.compile(r"(アップ|ダウン)(する事(は|が|も)?でき(ない|ず)"
                   r"|する(効果|場合|度))"
                   r"|にな(る事(は|が|も)?でき(ない|ず)|る場合)"),
    ),
    # 第3期(票17):效果傷害——「ダメージを与え/受け」動作形;戰鬥傷害不圈
    # ((?<!戦闘) 擋貫通句與修飾)、「自分にダメージを与える魔法…」修飾形由
    # 排除樣式剝掉。
    CAT_DAMAGE: (
        re.compile(r"(?<!戦闘)ダメージを[^。]{0,15}?"
                   r"(与え(る|、|。)|受け(る|、|。))"),
        re.compile(r"(与え|受け)る(効果|場合|度)"
                   r"|与える(魔法|モンスター|罠|カード)"
                   r"|ダメージを(与え|受け)(られ)?な"),
    ),
    # 第3期(票17):生命回復——動作形;「回復した場合/時」是觸發不圈。
    CAT_HEAL: (
        re.compile(r"回復(する|し、|し。|できる)"),
        re.compile(r"回復(する(効果|場合|度)|できな|させる事はできな)"),
    ),
    # 第3期(票17):LP支付——「払うLPが必要なくなる」(支付免除)歸「其他」
    # 不圈;「払って…発動する度」是觸發敘述,但同句常伴其他支付形,由規則層
    # 與判定裁邊界,粗篩照圈。
    CAT_LP_PAY: (
        re.compile(r"(LP|ＬＰ)を[^。]{0,12}?払"),
        re.compile(r"払う(LP|ＬＰ)が必要なくな"),
    ),
    # 第3期(票17):LP失去。
    CAT_LP_LOSE: (
        re.compile(r"(LP|ＬＰ)を[^。]{0,20}?失う"),
        re.compile(r"失わない"),
    ),
    # 第4期(票18):行動限制——できない 家族錨在限制動詞上;修飾形
    # (「通常召喚できないモンスター」後接名詞)、自我使用條件(「この効果は
    # …発動できない」)、直接攻擊與攻擊對象(戰鬥規則,批2)都不圈。
    # 使用できない/ドローできない/手札に加える事はできない 等零星形不圈,
    # 是已接受的粗篩漏網(ADR-0013,票18 記錄)。
    CAT_RESTRICT: (
        re.compile(
            r"(特殊召喚|(S|X|リンク|融合|儀式|P)召喚"
            r"|(?<!殊)(?<!P)(?<!S)(?<!X)(?<!ク)(?<!合)(?<!式)(?<!転)召喚"
            r"|発動|(?<!直接)攻撃(宣言)?|表示形式[のはを]?変更"
            r"|リリース|素材[にと]|セット)(する事)?[はがも]?"
            r"でき(ない|ず|なくな)"
            r"|攻撃しなければならない|召喚に(も|は)?しか使用でき(ない|ず)"),
        re.compile(
            r"召喚でき(ない|ず)(?![。、）（])"
            r"|この効果は[^。]{0,45}?発動でき(ない|ず)"
            r"|このカード名の[^。]{0,60}?発動でき(ない|ず)"
            r"|の発動は[^。]{0,30}?発動でき(ない|ず)"
            r"|でき(ない|ず)場合"),
    ),
    # 第4期(票18):耐性/保護——されない/にならない/にできない 家族與代替
    # 破壞;「攻撃対象に」歸戰鬥規則不圈;「この効果では破壊されない」處理
    # 註記不圈。
    CAT_PROTECT: (
        re.compile(
            r"破壊され(ない|ず|なくな)"
            r"|効果の対象に(な(ら|れ)?(ない|ず)|でき(ない|ず))"
            r"|効果[をは]受け(ない|ず|なくな)"
            r"|除外(する事)?[はがも]?でき(ない|ず|なくな)|除外され(ない|ず)"
            r"|破壊される(場合|モンスター|カード)[^。]{0,20}?代わりに"
            r"|無効化され(ない|ず)|無効に(され|でき)(ない|ず)"
            r"|無効にならない"),
        re.compile(
            r"除外でき(ない|ず)場合"
            r"|この効果で(は)?[^。]{0,20}?破壊され(ない|ず)"
            r"|この(カード名の)?(この)?効果で[^。]{0,25}?除外でき(ない|ず)"),
    ),
    # 第5期(票19):表示形式變更——「守備表示で特殊召喚」召喚時表示指定
    # (で 粒子)與「表示形式が変更された」觸發形天然不圈;變更限制歸行動
    # 限制(T235)。
    CAT_POSITION: (
        re.compile(r"表示形式を変更(する|できる|し、|し。)"
                   r"|(攻撃|守備|表側)表示に(する|し、|し。|できる|な[るり])"),
        re.compile(r"表示形式[のはを]?変更(する事)?[はがも]?でき(ない|ず)"),
    ),
    # 第5期(票19):控制權轉移——「得た」完成/修飾形與「移った」觸發形
    # 不圈;否定形(変更できない)歸行動限制家族。
    CAT_CONTROL: (
        re.compile(r"コントロールを[^。]{0,25}?得(る|て)"
                   r"|コントロールを相手に移"
                   r"|コントロールを入れ替え"
                   r"|コントロールは[^。]{0,25}?戻る"),
        re.compile(r"コントロールを得る効果"),
    ),
    # 第5期(票19):性質變更——item 六值名詞+值域外扱う形(チューナー/
    # 通常モンスター);「(〜としては扱わない)」括弧註記與否定形不圈。
    CAT_PROPERTY: (
        re.compile(r"カード名[はを][^。]{0,40}?として扱"
                   r"|」(モンスター|カード)?として(も)?扱"
                   r"|(チューナー(以外のモンスター)?|通常モンスター)"
                   r"として(も)?扱"
                   r"|(種族|属性)にな[るり]|族にな[るり]"
                   r"|属性(モンスター)?として(も)?扱"
                   r"|レベル[はがを][^。]{0,32}?(にな[るり]|にする|にし、"
                   r"|にでき|として扱|(上|下)げ|(上|下)が)"
                   r"|レベル(・|または)ランク[をはが][^。]{0,30}?"
                   r"((上|下)げ|(上|下)が|にな[るり]|にする|にし、|にでき)"
                   r"|ランク[はがを][^。]{0,30}?(にな[るり]|にする"
                   r"|(上|下)げ|(上|下)が)"
                   r"|スケール[はがを][^。]{0,30}?(にな[るり]|にする|にし、"
                   r"|にでき)"),
        re.compile(r"として(は)?扱わない"
                   r"|レベル[はがを][^。]{0,30}?でき(ない|ず)"),
    ),
    # 第5期(票19):計數器操作——カウンター 錨擋「X素材を取り除く」;
    # 「が置かれた」觸發形無を粒子不圈;修飾/參照形交規則層動詞邊界。
    CAT_COUNTER: (
        re.compile(r"カウンターを[^。]{0,30}?(置|取り除)"),
        re.compile(r"カウンターを置く(効果|事ができる(カード|モンスター))"
                   r"|カウンターを[^。]{0,20}?置く事[はも]?でき(ない|ず)"
                   r"|カウンターを置いた(場合|時|ターン)"),
    ),
}


def screen_hit(cat, text_ja):
    """這一句是不是該類別的候選?(判定票入選與 seal 零空缺共用同一把尺)"""
    found = _SCREENS.get(cat)
    if found is None or not text_ja:
        return False
    include, exclude = found
    if not include.search(text_ja):
        return False
    # 排除樣式只擋「整句只有否定形」:句子同時有動作形與否定形時仍是候選
    # (「特殊召喚する。そのモンスターは効果を発動できない」)
    stripped = exclude.sub("", text_ja)
    return bool(include.search(stripped))


# ---------------------------------------------------------------- 自檢與指紋

def problems(rules=RULES, timing_rules=TIMING_RULES):
    """規則清單本身的毛病;必須是空的,否則規則層不上工。"""
    found = []
    ids = [rule["id"] for rule in rules]
    for rid in sorted({rid for rid in ids if ids.count(rid) > 1}):
        found.append(f"{rid}: 編號重複")
    cats = {CAT_MOVE, CAT_DRAW, CAT_NEGATE, CAT_DESTROY, CAT_RESTRICT,
            CAT_PROTECT, CAT_STAT, CAT_DAMAGE, CAT_HEAL, CAT_LP_PAY,
            CAT_LP_LOSE, CAT_POSITION, CAT_CONTROL, CAT_PROPERTY, CAT_COUNTER,
            CAT_TRANSFORM, CAT_SUBSTITUTE, CAT_SUMMON_EXEC, CAT_BATTLE,
            CAT_INFO, CAT_MISC}
    for rule in rules:
        rid = rule["id"]
        if not _ID_RE.match(rid):
            found.append(f"{rid}: 編號格式須為 T + 正整數")
        if rule["cat"] not in cats:
            found.append(f"{rid}: 類別不是動作類別的成員")
        if rule["scope"] not in SCOPES:
            found.append(f"{rid}: 掃描範圍不是 {SCOPES}")
        if not rule["condition"] or not rule["ticket"]:
            found.append(f"{rid}: 判別條件與新增票號不得為空")
        if not rule["tags"]:
            found.append(f"{rid}: 沒有 tag 樣板")
        for template in rule["tags"]:
            if "cat" in template or "pos" in template:
                found.append(f"{rid}: tag 樣板不得自帶 cat / pos(由框架補)")
        if (rule["scope"] == SCOPE_TARGET) != (rule["action"] is not None):
            found.append(f"{rid}: 「對象」範圍規則必須帶 action、"
                         f"其他範圍不得帶")
    for cat in PHASES:
        if cat not in cats:
            found.append(f"PHASES: {cat!r} 不是動作類別的成員")
        if cat not in _SCREENS:
            found.append(f"PHASES: {cat!r} 已開貼但沒有粗篩定義")
    tids = [rule["id"] for rule in timing_rules]
    for rid in sorted({rid for rid in tids if tids.count(rid) > 1}):
        found.append(f"{rid}: 編號重複")
    return found


def digest(rules=RULES, timing_rules=TIMING_RULES):
    """規則**定義**的指紋(含分期登記與粗篩)。覆蓋條數不算在內。"""
    parts = []
    for rule in rules:
        parts.append("|".join((
            rule["id"], rule["cat"], rule["scope"], rule["condition"],
            rule["pattern"].pattern,
            rule["exclude"].pattern if rule["exclude"] else "",
            rule["action"].pattern if rule["action"] else "",
            repr([sorted(t.items()) for t in rule["tags"]]), rule["ticket"])))
    for rule in timing_rules:
        parts.append("|".join((
            rule["id"], rule["value"], rule["condition"],
            rule["pattern"].pattern,
            rule["exclude"].pattern if rule["exclude"] else "")))
    for cat in sorted(PHASES):
        include, exclude = _SCREENS.get(cat, (None, None))
        parts.append("|".join((cat, PHASES[cat],
                               include.pattern if include else "",
                               exclude.pattern if exclude else "")))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:16]
