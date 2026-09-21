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

# 起點詞(複合起點「手札・墓地から」由專屬規則發多個 tag,單一起點規則以
# 負向後看擋在「・」之後誤配半邊)
_S_HAND = r"(?<!・)手札[かの]ら?"
_S_DECK = r"(?<!・)(?<!EX)(?<!ラ)デッキから"
_S_EXTRA = r"(EXデッキ|エクストラデッキ)から"
_S_GRAVE = r"(?<!・)墓地[のか]"
_S_BANISHED = r"((?<!・)(?<!び)除外されている|(?<!・)除外状態の)"
_S_FIELD = r"(?<!・)フィールドの"

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
            CAT_PROTECT, CAT_STAT, CAT_DAMAGE, CAT_HEAL, CAT_POSITION,
            CAT_CONTROL, CAT_PROPERTY, CAT_COUNTER, CAT_TRANSFORM,
            CAT_SUBSTITUTE, CAT_SUMMON_EXEC, CAT_BATTLE, CAT_INFO, CAT_MISC}
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
