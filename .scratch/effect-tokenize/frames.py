# -*- coding: utf-8 -*-
"""框架抽取(票 effect-tokenize#04,實作票 05〜07;約束框架線票 01〜06):分詞結果 →
每句的框架清單——動作框架與約束框架混排、依原文位置排序。

接在分詞鏈之後:讀 tokens.json(tokenize.py 的輸出)逐句抽框架,寫 frames.json
(決定性建置產物,不入版控)。測試接縫是 extract(text, context, extra=None,
card_type=None):一句效果句原文(帶同卡同段上文;extra 標效果外文本,沒給時看字首
①：/● 判;card_type 是卡片子類型 融合/儀式/同調/超量/連結,主程式從 data/cards.json
帶入)→ 框架清單,內部呼叫真的分詞器與詞典。

每個框架帶 kind:動作 或 約束。約束框架(constraints.py)由句型認出——限制(次數/
事件回合禁用/誓約/召喚條件)、時機、素材——被認成約束的句子/子句不再出動作框架
(取代規則:約束框架吃掉的詞序列範圍內的錨點不出框架)。

動作框架(一個動作一個框架,依原文順序):
    action    動作(動作詞元):動詞以 lexicon.json 的 lemma 歸詞元;サ変名詞+する
              家族記名詞(破壊|する → 破壊),攻撃|宣言、直接|攻撃 連前一個詞記
              (COMPOUND_ACTIONS);召喚法+召喚記 法+召喚(特殊召喚);「N に する/なる」
              的狀態/角色詞補語併入動作(無効にする、対象になる),補語是值或屬性時不併、
              整段進目的(action_lemmas 的補語不併判準);「〜を対象として」記 対象とする。以上是
              抽取內部用的原詞元,框架產出前過詞元對照表(action_lemmas.normalize;frame-lemma-unify、
              ADR-0016)成正規詞元:戻る→戻す、になる→にする、無効化→無効にする、
              上げる/上がる→アップ、アドバンス召喚→A召喚…
    object    對象(を 前的詞)、source 來源(から 前)、goal 目的(に/へ 前)
              ——述語往前、同一子句內依助詞收;值保留原詞(指示綁定、列舉前項
              補全值、數量約束、卡名佔位);時間語(ターン/フェイズ/時…)的 に 不收
    position  位置:代價/效果/條件——發動句(以 発動できる/発動する 收尾的第一
              句)裡的付出是代價、處理段的動作是效果、觸發句(…場合/…時/…限り)
              與發動條件(対象として、狀態述語、被動)是條件
    polarity  極性:肯定/否定/可能——ない/されない/できない 系否定、できる 系可能
    sentence  句序(。 與 ● 切開的第幾句,0 起)、span 對應詞序列範圍 [start, end)、
              clause 子句字面(span 內 token 字面相連,供拆解頁對照)
    option    選項(ADR-0015):出自第 n 個 ● 選項的框架記 n,第一個 ● 之前為 None;
              label 是「●自分ターン：」這類標籤冒號前的值(沒有標籤時 None),
              標籤本身不出框架
    count/period/window  可選(約束框架票 06):效果內容的次數(１度だけ、もう１度、
              主題後的 １ターンに１度、)與期間、非發動句的階段窗口(追加召喚的
              自分メインフェイズに)——這些不是約束框架
    turn      可選(frame-args-v2 票 04):處理句裡「〜したターン/そのターン/次のターン
              の(階段)に」的回合限定詞原文,與 window(階段)並列
    enumeration  可選(票 01):純列舉項(● 項全部沒有框架)掛在母句「以下の」所指框架上的
              有序字串清單;對象欄不改字
    link/group   可選(票 02):か 並列的述語各記 連接=或、群組=n(一句效果句內從 1 起編)
    backfill  可選(票 03):か 群組與選ぶ鏈之後缺對象的述語從前面接過 object 與區域,
              此欄列出被填的欄名;值是上游框架的字面(frame-args-v3 起值域多 topic/place,
              與附加子句移過來的 subject)
    topic/subject  可選(frame-args-v3 票 02/03):は 片語(主題)、が 片語(主語)的字面,
              同一子句取離述語最近的;主題在同一句內延續給沒有自己主題的子句(回填記 topic)
    place     可選(票 04):受事者(主動句對象;被動句主語,沒有時主題)片語裡切出的區域——
              移動類動作(MOVE_ACTIONS)記在 source,其餘記在 place(所在);受事者欄只少掉那一段
    inferred  可選(票 05):規則依動作補上的 source/goal 欄名(INFERRED;原文沒寫才補)
    voice     可選(frame-lemma-unify 票 01/03):態 他動/自動/受身——受身是述語錨點判出的被動
              (取代 2026-10-27 前的 passive 旗標),他動/自動只在詞元對照表合併的詞元上記;
              沒值時不帶(空是沒判,不是他動)
    anaphora  可選(action-patient-anaphora,anaphora.py):受事者位的指示詞(そのモンスター、対象の
              カード、その発動)指的目標——字面 text、區域 place、玩家 player、事件主語或主人 subject、
              只寫在子句裡的數量 count、找法 via(対象/欄位/字面/事件);不是卡、修飾語、找不到時不帶

單位是效果句(一個編號效果的全文,連同它的 ● 選項;tokenize.py 的 assemble 把
拆開的領起句與子效果句接回一段):選項邊界 token「●」與「。」同樣結束一句,
發動句、位置、極性各句照既有規則判定,選項各有自己的發動句。

子句切分:一子句至多一個述語錨點——錨點(含活用尾/可能/否定/形式名詞 後綴與
其後的助詞、讀點)結束處即下一子句的起點;定語用法(動詞後直接接名詞:
特殊召喚したモンスター)不當錨點,留在名詞片語裡。〜よう(に) 收尾的子句後面同一句還有
述語時是它的連用修飾(frame-args-v3 票 09):不出框架,字面併入下一個述語的子句;量條件
(よう 子句的主語、目的)不結構化,對象/來源/主題交給下一個述語。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/frames.py
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from constraints import KIND_ACTION, KIND_CONSTRAINT, ConstraintFinder  # noqa: E402
import action_lemmas  # noqa: E402
import anaphora  # noqa: E402
from places import parse_place  # noqa: E402
from report import frame_stats, token_kind  # noqa: E402

LEXICON = os.path.join(HERE, "lexicon.json")
TOKENS = os.path.join(HERE, "tokens.json")
OUT = os.path.join(HERE, "frames.json")
CARDS = os.path.join(HERE, "..", "..", "data", "cards.json")
# 卡片子類型(cards.json 的 type 位元 → 素材框架的召喚法;與 script/tag_card/tagcard.py 同值)
CARD_TYPE_BITS = (("融合", 0x40), ("儀式", 0x80), ("同調", 0x2000), ("超量", 0x800000),
                  ("連結", 0x4000000))


def card_type_of(type_bits):
    """卡片的 type 位元 → 融合/儀式/同調/超量/連結,都不是時 None。"""
    return next((label for label, bit in CARD_TYPE_BITS if type_bits & bit), None)

# ── 封閉類(述語家族與功能詞)──
SURU_ACTIVE = {"する", "した", "して", "し", "すれば"}
SURU_PASSIVE = {"され", "される", "された", "されて"}
SURU_NEG = {"されない", "されず", "せず"}
POTENTIAL = {"できる", "でき"}
POTENTIAL_NEG = {"できない", "できず"}
SURU_FAMILY = SURU_ACTIVE | SURU_PASSIVE | SURU_NEG | POTENTIAL | POTENTIAL_NEG
# 錨點後的否定/補助/活用尾
NEGATORS = {"ない", "なく", "なかった", "ず", "なければ"}
AUXILIARY = {"いる", "いた", "いない", "いれば", "ある", "あった", "あれば"}
TAILS = {"た", "て", "る", "った"}
# 形式名詞:動詞後接這些仍是述語錨點(不算定語);條件類給 條件 位置
NOMINALIZERS = {"場合", "時", "際", "度", "限り", "ターン", "状態", "事", "ため",
                "よう", "まま", "後", "前", "間", "つき"}
CONDITIONAL_NOMINALIZERS = {"場合", "時", "際", "度", "限り", "ターン", "状態",
                            "間"}
CONDITIONAL_FORMS = {"すれば", "あれば", "いれば", "なければ"}
# 「N に する/なる」的補語不吸收這些詞(量化詞/比較詞:全て裏側守備表示にする
# 的 全て 是副詞;レベル以上になる 的 以上 是比較結果,留在目的論元;指示詞 その/この
# 不併入補語:そのX素材とする → X素材とする,frame-lemma-unify 票 02)
FOLD_STOP = {"全て", "それぞれ", "お互い", "両", "元々", "以上", "以下", "未満",
             "同名", "任意", "他", "次", "残り", "その", "この"}
# サ変名詞直接接 時 也是事件(攻撃宣言時/発動時/成功時);終了時/開始時/
# ダメージ計算時 是時點,不是動作
EVENT_NOUNS = {"宣言", "成功", "リバース"}
# 動作名完整(frame-lemma-unify 票 04):前一個詞 + サ変名詞 是一個動作,不論述語形
# (攻撃宣言できない/攻撃宣言した/攻撃宣言時 → 攻撃宣言;直接攻撃できる → 直接攻撃)
COMPOUND_ACTIONS = {("攻撃", "宣言"): "攻撃宣言", ("直接", "攻撃"): "直接攻撃"}
# 「・」並列的述語名詞(召喚・特殊召喚した/特殊召喚・リバースした):各出一框架
SAHEN_NOUNS = {"発動", "召喚", "破壊", "存在", "除外", "アップ", "リリース", "成功",
               "攻撃", "ドロー", "セット", "装備", "選択", "無効化", "適用", "宣言",
               "ダウン", "回復", "リバース", "確認", "無視", "発生", "使用", "変更",
               "移動", "シャッフル", "合計", "チェーン", "終了", "スキップ", "指定",
               "公開", "勝利", "代用", "相互リンク", "コントロール"}
# 法鏈的原詞元(融合・S・X・リンク召喚、融合・S・X素材にする):一法一框(_each_method)
_METHOD_CHAIN = re.compile(r"(.+?)(召喚|素材[にと](?:する|なる))")
# 「Xが Yの N」的屬性主語(攻撃力と守備力が０の悪魔族モンスター):併入名詞片語
# (與補語不併判準共用一份,定義在 action_lemmas)
ATTR_NOUNS = action_lemmas.ATTRIBUTE_NOUNS
# 片語開頭的副詞/接續詞/時間語不屬論元
LEADING_ADVERBS = {"さらに", "また", "もう", "既に", "その後", "それぞれ"}
# 「〜に」的方式副詞(ランダムに/順に/お互いに/〜の代わりに):不是目的論元
MANNER_NI = {"代わり", "ランダム", "お互い", "順"}
# 狀態/變化述語:在發動句裡是條件、不是代價
STATE_LEMMAS = {"存在", "ある", "いる", "持つ", "なる", "成功", "含む", "異なる",
                "違う", "超える", "揃う", "記す", "当たる", "出る", "離れる",
                "加わる", "戻る", "移る", "上がる", "下がる", "入れ替わる",
                "満たす", "リンク", "相互リンク", "だ", "無い", "多い", "少ない",
                "高い", "低い"}
LIGHT_VERBS = {"する", "なる"}
# 時間語的 に(ターン/フェイズ/時…)不收成目的論元
TIME_HEADS = {"ターン", "時", "場合", "際", "度", "後", "前", "間", "内", "中",
              "以降", "開始", "終了", "デュエル", "フェイズ", "毎"}
CASE_ROLE = {"を": "object", "から": "source", "に": "goal", "へ": "goal"}
# 主題(は 前)與主語(が 前)(frame-args-v3 票 02);後綴型(には/では/とは)不算主題
TOPIC_ROLES = {"は": "topic", "が": "subject"}
# 其他格助詞:切片語但不收成論元(手段/期間);後綴型(にも/には)併入前一格
CASE_OTHER = {"が", "は", "で", "まで", "より", "として", "しか", "のみ", "だけ",
              "ずつ", "も"}
CASE_SUFFIX = {"も", "は", "のみ", "だけ", "しか", "ずつ"}
COORDINATORS = {"と", "や", "または", "及び", "か", "など"}
FUNCTIONAL = (SURU_FAMILY | NEGATORS | AUXILIARY | TAILS
              | {"な", "だった", "さらに", "また", "もう", "既に", "それ", "それら",
                 "いずれ", "よる", "よって", "よらず", "ない", "通常の"})
# 純平假名的詞元只有這幾個是動詞(よう/ため/まま 這類形式名詞詞元也以 う/る 結尾)
HIRAGANA_VERBS = {"なる", "めくる", "なくす"}
# 定語動詞只吸收這些格的片語(其餘動詞:往前吸到讀點或主題 は 為止)——
# 「カード名が記されたモンスター」的 が 屬定語,前面的 から 是主句的來源
RELATIVE_SCOPE = {"記す": {"が", "に"}, "持つ": {"を", "として"}, "含む": {"を"},
                  "異なる": {"が"}, "受ける": {"が"}, "違う": {"が"},
                  "決める": {"に"}, "存在": {"に", "で", "が"},
                  "なる": {"と", "に", "が", "で"}, "な": {"に", "が"},
                  "同じ": {"と", "が"}, "高い": {"が", "より", "と"},
                  "低い": {"が", "より", "と"}, "多い": {"が", "より", "と"},
                  "少ない": {"が", "より", "と"}, "無い": {"が", "に"},
                  "ない": {"が", "に"}}
# 定語吸收不越過的片語(方式/手段副詞、●標籤)
NON_ABSORB_ROLES = {"に(方式)", "によって", "に対して", "に加えて", "：", "は"}
# 連用形/て形不當定語(選んで特殊召喚、リリースして発動)
NON_ATTRIBUTIVE_SURU = {"し", "して", "され", "されて", "せず", "されず"}
ADJECTIVE_LEMMAS = {"高い", "低い", "多い", "少ない", "大きい", "小さい", "正しい",
                    "無い", "ない"}
SPECIAL_POTENTIAL = {"出せ", "出せる", "選べ", "行え", "取り除け", "除け"}
# 接 する家族 也不是動作的名詞:に対して(對…)、〜な、通常の
NON_PREDICATE_NOUNS = {"対", "な", "通常の", "際", "後", "前"}
# 「N に する/なる」能併入動作的補語:至多三格、全是名詞類、不含數字
FOLD_MAX = 3
PHRASE_JOINERS = {"p:の", "・", "～", "p:か", "p:または", "p:及び", "p:や"}   # 回指字面片語的連接
IRREALIS_TAIL = "あかさたなはまやらわがざだばぱ"
NOUN_KINDS = {"name", "dem", "elided", "attr", "method", "cname", "num", "quant",
              "range", "counter"}
PUNCT_IN_PHRASE = set("・／～（）『』")
_PASSIVE_RE = re.compile(r"[らかまさわたばがな]れ")
_TE_GODAN_RE = re.compile(r"(って|いて|んで|して)$")

POS_COST, POS_EFFECT, POS_COND = "代價", "效果", "條件"
POL_AFFIRM, POL_NEG, POL_CAN = "肯定", "否定", "可能"
OPTION = "●"                  # 選項邊界 token(tokenize.OPTION)
# ── 第二版論元(frame-args-v2)──
LINK_OR = "或"                # か 並列的連接值(票 02,值域只有這一個)
SELECT_ACTIONS = {"選ぶ", "選択"}   # 選ぶ鏈的起點(票 03)
# 回填不碰的動作(票 03):全語料實際上不帶對象的動作——2026-10-14 從 frames.json 算一次:
# 動作框架 ≥ 20 個且帶對象的比例 ≤ 5%(嚴格「從不帶」會漏掉 ドロー:舊式卡文「このカードを
# ドローした時」18 例);「〜なる」家族(になる/同じになる/倍になる…)另以字尾判
NO_OBJECT_ACTIONS = {"存在", "成功", "ドロー", "離れる", "無効化", "攻撃宣言", "リバース",
                     "戻る", "加わる", "素材にする", "違う", "行く", "上がる", "異なる",
                     "チェーン", "L素材にする", "S素材にする"}
# ── 第三版論元(frame-args-v3)──
# 受事者候選的論元鍵:主動句的受事者是對象,被動句是主語(沒有時是主題)(票 04)
PATIENT_KEYS = ("object", "topic", "subject")
# 〜よう 子句交給下一個述語的論元(票 09);主語與目的是量條件,不交
ABSORBED_KEYS = ("object", "source", "topic")
# 移動類(區域移動與召喚兩個大類的成員;素材類不算,規格決定 2026-10-17):受事者的區域記
# 來源,其餘動作記所在(票 04)
MOVE_ACTIONS = {"加える", "ドロー", "送る", "捨てる", "リリース", "除外", "戻す", "戻る", "置く",
                "セット", "装備", "移動", "特殊召喚", "召喚", "通常召喚", "アドバンス召喚",
                "A召喚", "融合召喚", "儀式召喚", "S召喚", "X召喚", "リンク召喚", "L召喚", "P召喚"}
# 移動類裡的自動詞:移動的卡是主語(沒有時主題),受事者照被動句的取法(v3-round1)
INTRANSITIVE_MOVES = {"戻る"}
# 〜を素材として 之後緊接的這些動作,對象就是素材(v3-round1)
MATERIAL_DESTINATIONS = {"除外", "送る", "戻す", "リリース"}
# 沒成錨點的條件子句(形容詞述語:自分のLPが相手より少ない場合):前面的 が 屬該子句
UNANCHORED_CONDITIONS = {"場合", "限り"}
QUANTITY_KINDS = {"num", "counter", "quant", "range"}
# 屬性 が(攻撃力か守備力が|２０００のモンスター)併進的名詞片語可以是這些格(v3-round2 起含主語/主題)
ATTR_HEAD_ROLES = ("を", None, "が", "は")
# 區域字面前的玩家詞;自身の/持ち主の 照區域辨識記玩家「相對」,仍隨區域切出
PLAYER_WORDS = {"自分", "相手", "お互い", "自身", "持ち主"}
# 受事者片語裡並列段的分隔(各段切自己的區域);區域字面內部的並列(自分か相手の、手札・墓地)
PATIENT_COORDINATORS = {"p:と", "p:か", "p:や", "p:及び", "p:または"}
PLACE_JOINERS = {"・", "p:か", "p:または", "p:及び", "p:や"}
DECK_POSITIONS = {"一番上", "一番下", "上", "下"}
# 推得值(票 05):動作 → 由動作唯一決定的 來源/目的 區域字面;原文沒寫時補上並標推得。
# 装備(目的是被裝備的怪獸)、リリース、破壊(去處會被改寫)不補(規格決定 2026-10-17)
_ON_FIELD = {"goal": "フィールド"}
INFERRED = dict({"除外": {"goal": "除外"}, "捨てる": {"source": "手札", "goal": "墓地"},
                 "ドロー": {"source": "デッキ", "goal": "手札"}, "セット": _ON_FIELD,
                 "加える": {"goal": "手札"}},
                **{action: _ON_FIELD for action in (
                    "特殊召喚", "召喚", "通常召喚", "アドバンス召喚", "A召喚", "融合召喚",
                    "儀式召喚", "S召喚", "X召喚", "リンク召喚", "L召喚", "P召喚")})
INFERRED_FIELDS = ("source", "goal")          # 推得欄的值,依框架表的欄序
# 區域前的位置限定語(自分の中央の|メインモンスターゾーン)
POSITION_WORDS = {"中央", "左端", "右端", "両端"}
# 「と」後接這些詞時是比較(…と同じ/と異なる),不是並列受事者
COMPARE_AFTER_TO = {"同じ", "異なる", "違う", "共に", "一緒"}
PAREN_MAX = 3                 # 區域後括號註記(フィールド（表側表示）)的最多詞數
# 片語是數量(…の数×100、…の合計)時區域修飾的是數量,不切
COUNT_WORDS = {"数", "合計"}
OBJECT, REGION = "object", "region"   # 回填接過的兩部分(區域再依下游動作轉欄)
# 屬性主題「Xの攻撃力」(票 03):延續給下一子句時改用屬性的主人 X;
# 光禿禿的屬性主題(効果は)是延續中 X 的屬性,不換掉 X
_TOPIC_ATTRIBUTE = r"(?:元々の)?(?:攻撃力・守備力|攻撃力|守備力|レベル|ランク|種族|属性|効果)"
ATTRIBUTE_TOPIC = re.compile(r"(.+?)の" + _TOPIC_ATTRIBUTE)
BARE_ATTRIBUTE_TOPIC = re.compile(_TOPIC_ATTRIBUTE)
LABEL_MAX_CHARS = 30          # ●標籤「●…：」冒號前的最大字數(與 tokenize._LABEL 同)


def _load_tokenizer_module():
    """tokenize.py 與標準庫同名:照路徑載入。"""
    spec = importlib.util.spec_from_file_location(
        "effect_tokenize", os.path.join(HERE, "tokenize.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Lexicon:
    def __init__(self, entries):
        self.entries = entries
        self.surface_of = {e["id"]: e["surface"] for e in entries}
        self.lemma_of = {e["id"]: e.get("lemma", e["surface"]) for e in entries}
        self.closed_of = {e["id"]: e.get("closed") for e in entries}

    def is_verb(self, wid):
        lemma = self.lemma_of[wid]
        surface = self.surface_of[wid]
        if surface in FUNCTIONAL or lemma in ADJECTIVE_LEMMAS:
            return False
        if lemma in ("する", "される", "できる", "ある", "いる", "だ"):
            return False
        if all("ぁ" <= ch <= "ゟ" for ch in lemma):
            return lemma in HIRAGANA_VERBS
        return lemma[-1] in "うくぐすつぬぶむる"


def verb_form(surface, lemma):
    """動詞詞形分類:te/stem/past/neg/cond/dict/irrealis/potential。"""
    if surface in SPECIAL_POTENTIAL:
        return "potential"
    if surface.endswith("ず"):
        return "stem"
    if surface.endswith(("ない", "なく", "なかった")):
        return "neg"
    if surface.endswith("ば"):
        return "cond"
    if surface == lemma:
        return "dict"
    if surface.endswith(("た", "だ")):
        return "past"
    if surface.endswith(("て", "で")) and (
            surface[:-1] + "る" == lemma or _TE_GODAN_RE.search(surface)):
        return "te"
    if surface[-1] in IRREALIS_TAIL:
        return "irrealis"
    return "stem"


class FrameExtractor:
    def __init__(self, lexicon_entries):
        self.lex = Lexicon(lexicon_entries)
        tokenize = _load_tokenizer_module()
        self.tokenizer = tokenize.Tokenizer(lexicon_entries)
        self.char_offsets = tokenize.char_offsets
        self.finder = ConstraintFinder(self)

    # ── token 讀取 ──
    def surface(self, token):
        kind = token_kind(token)
        if kind == "lex":
            return self.lex.surface_of[token]
        if kind == "dem":
            _, dem, wid = token.split(":", 2)
            return dem + self.lex.surface_of[wid]
        if kind == "quant":
            _, wid, val, counter, cmp_word = token.split(":", 4)
            return ((self.lex.surface_of[wid] if wid else "") + val + counter
                    + cmp_word)
        if kind == "cname":
            return "〈%s〉カウンター" % token[2:]
        if kind == "name":
            return "「%s」" % token.split(":", 1)[1]
        if kind == "elided":
            _, head, wid = token.split(":", 2)
            return "%s(%s)" % (head, self.lex.surface_of[wid][len(head):])
        if kind == "range":
            _, lo, hi, counter = token.split(":", 3)
            return "%s～%s%s" % (lo, hi, counter)
        if kind == "punct":
            return token
        return token.split(":", 1)[1]

    def word(self, token):
        """詞典詞的字面;非詞典詞回 None。"""
        return self.lex.surface_of[token] if token.startswith("W") else None

    def is_noun_like(self, token):
        kind = token_kind(token)
        if kind in NOUN_KINDS:
            return True
        if kind != "lex":
            return False
        surface = self.lex.surface_of[token]
        if surface in FUNCTIONAL or surface in NOMINALIZERS:
            return False
        if self.lex.is_verb(token) or self.lex.lemma_of[token] in ADJECTIVE_LEMMAS:
            return False
        return True

    @staticmethod
    def _method_prefix(tokens, m, start):
        """tokens[m] 往前連續的召喚法 token(法・法…)→ (字串前綴, 第一個法的位置)。
        沒有召喚法時回 ("", m + 1)。"""
        parts = []
        while m >= start and token_kind(tokens[m]) == "method":
            parts.insert(0, tokens[m][2:])
            m -= 1
        return "・".join(parts), m + 1

    # ── 錨點辨識 ──
    def anchor_at(self, tokens, i, clause_start):
        """tokens[i] 起是否為述語錨點。回 dict(head, end, action, polarity,
        form, passive, nominalizer, fold) 或 None。end 是後綴鏈結束位置。"""
        t = tokens[i]
        n = len(tokens)
        w = self.word(t)
        head, action, form, passive = i, None, None, False
        j = i + 1
        polarity = POL_AFFIRM
        fold = 0                      # 併入動作的前置 token 數(N に する)
        complement = None             # N に する/なる 的補語不併時是 する/なる(票 05)
        obligation = False            # 〜しなければならない(召喚條件的「必須」)

        def nxt(k):
            return self.word(tokens[k]) if k < n else None

        if w == "対象" and j < n and tokens[j] == "p:として":
            return self._finish(tokens, i, i, j + 1, "対象とする", POL_AFFIRM,
                                "te", False, 0, clause_start)
        # 〜を素材として/〜をX素材として:當作素材(動作 素材とする);〜の素材として扱う 的
        # 述語是 扱う(視同),素材として 不成框架(frame-lemma-variants 票 05)
        if w is not None and w.endswith("素材") and j < n \
                and tokens[j] == "p:として" and not (
                    i - 1 >= clause_start and tokens[i - 1] == "p:の"
                    and j + 1 < n and tokens[j + 1].startswith("W")
                    and self.lex.lemma_of[tokens[j + 1]] == "扱う"):
            prefix, head = self._method_prefix(tokens, head - 1, clause_start)
            return self._finish(tokens, head, i, j + 1, prefix + w + "とする",
                                POL_AFFIRM, "te", False, 0, clause_start)
        if w == "対象" and j < n and tokens[j] == "p:と" and nxt(j + 1) in SURU_FAMILY:
            action, j, form = "対象とする", j + 1, None
        elif token_kind(t) == "method" or w == "召喚":
            # 召喚法鏈 法(・法)*+召喚(+する家族)
            k = i
            parts = []
            while k < n and token_kind(tokens[k]) == "method":
                parts.append(tokens[k][2:])
                if k + 1 < n and tokens[k + 1] == "・" and k + 2 < n \
                        and token_kind(tokens[k + 2]) == "method":
                    k += 2
                else:
                    k += 1
                    break
            if nxt(k) != "召喚":
                return None
            after = nxt(k + 1)
            if after in SURU_FAMILY:
                action, j, form = "・".join(parts) + "召喚", k + 1, None
            elif after == "時" and not parts:
                return None
            elif after == "時":
                action, j, form = "・".join(parts) + "召喚", k + 1, "noun"
            else:
                return None
        elif w is not None and self.lex.is_verb(t):
            lemma = self.lex.lemma_of[t]
            form = verb_form(w, lemma)
            # 〜でなければならない:繫詞「必須是」,不是動作 なる
            if lemma == "なる" and i - 1 >= clause_start and tokens[i - 1] == "p:で":
                return None
            # 〜扱いで/〜扱いとして:「當作…」的修飾語,不是動作
            if w == "扱い" and j < n and token_kind(tokens[j]) == "particle":
                return None
            # 続けて攻撃できる 的 続けて 是副詞;通常召喚に加えて 的 加えて 是慣用
            if w == "続けて" and j < n and token_kind(tokens[j]) != "punct":
                return None
            if w == "加えて" and i - 2 >= clause_start and tokens[i - 1] == "p:に" \
                    and self.word(tokens[i - 2]) == "召喚":
                return None
            passive = bool(_PASSIVE_RE.search(w)) and lemma not in ("離れる",)
            action = lemma
            if form == "neg" or w.endswith("ず"):
                polarity = POL_NEG
            elif form == "potential":
                polarity = POL_CAN
            if lemma in LIGHT_VERBS:
                # N に/と なる:補語併入動作(無効になる/対象になる/同じになる);対象にもならない
                # 的 も 夾在 に 與 なる 之間不擋(frame-lemma-variants 票 05)
                skip = int(i - 2 >= clause_start and tokens[i - 1] == "p:も"
                           and tokens[i - 2] in ("p:に", "p:と"))
                action, fold, complement = self._fold_complement(tokens, i - skip,
                                                                 clause_start, lemma)
                fold += skip
        elif w is not None and w in SURU_FAMILY:
            # 裸 する家族(前面不是サ変名詞):N に/と する → 併入動作
            # (無効にする/裏側守備表示にする/リンク素材とする);補語是數字時
            # 動作記 にする、數字留在目的論元(攻撃力を０にする)
            prev = tokens[i - 1] if i - 1 >= clause_start else None
            # 対象にもできない:後綴助詞(も/は)夾在 に 與 する 之間
            skip = 0
            if (prev in ("p:も", "p:は") and i - 2 >= clause_start
                    and tokens[i - 2] in ("p:に", "p:と")):
                prev, skip = tokens[i - 2], 1
            if prev in ("p:に", "p:と"):
                action, fold, complement = self._fold_complement(tokens, i - skip,
                                                                 clause_start, "する")
                fold += skip
            elif prev == "p:を" and w in SURU_ACTIVE:
                action = "する"        # 通常のドローをした
            elif w in POTENTIAL | POTENTIAL_NEG:
                # 「〜の特殊召喚は１ターンに１度しかできない」:主題是動作名詞時
                # 動作就是它(効果は…できない 視為 使用)
                action = self._topic_action(tokens, i, clause_start)
                if action is None:
                    return None
            else:
                return None
            form = None
            j = i                      # 本 token 就是 する家族,下面統一吃
        elif w is not None and w not in FUNCTIONAL and w not in NOMINALIZERS \
                and w not in NON_PREDICATE_NOUNS and not self.lex.is_verb(t) \
                and self.lex.lemma_of[t] not in ADJECTIVE_LEMMAS:
            after = nxt(j)
            if after in SURU_FAMILY:
                action, form = w, None
            elif after == "時" and w in EVENT_NOUNS:
                action, form = w, "noun"
            else:
                return None
            compound = self._compound_action(tokens, i, clause_start)
            if compound is not None:
                action, head = compound, i - 1
        else:
            return None

        # ── 後綴鏈:する家族 → 否定 → 補助 → 事ができる → 形式名詞 ──
        suru_form = None
        if j < n and self.word(tokens[j]) in SURU_FAMILY and form != "noun":
            s = self.word(tokens[j])
            suru_form = s
            if s in SURU_NEG or s in POTENTIAL_NEG:
                polarity = POL_NEG
            elif s in POTENTIAL:
                polarity = POL_CAN
            if s in SURU_PASSIVE or s in SURU_NEG - {"せず"}:
                passive = True
            j += 1
        if form is None:
            form = {"し": "stem", "して": "te", "され": "stem", "されて": "te",
                    "せず": "stem", "されず": "stem",
                    "できず": "stem", "でき": "stem"}.get(suru_form, "dict")
            if suru_form in ("した", "された"):
                form = "past"
        if j < n and self.word(tokens[j]) in TAILS:
            tail = self.word(tokens[j])
            if tail in ("て", "った"):
                form = "te"
            elif tail == "た":
                form = "past"
            j += 1
        if j < n and self.word(tokens[j]) in NEGATORS:
            polarity = POL_NEG
            if self.word(tokens[j]) == "なく":
                form = "te"
            elif self.word(tokens[j]) in ("ない", "なかった"):
                form = "neg"           # 存在しない+名詞 是定語
            elif self.word(tokens[j]) == "ず":
                form = "stem"          # 戻さず手札に加える:連用否定
            elif self.word(tokens[j]) == "なければ":
                form = "cond"          # 送らなければ攻撃宣言できない:條件形,不是定語
            j += 1
            # 〜しなければならない/ならず:義務,不是否定
            if (j + 1 < n and self.word(tokens[j - 1]) == "なければ"
                    and self.word(tokens[j]) == "なら"
                    and self.word(tokens[j + 1]) in ("ない", "ず")):
                polarity = POL_AFFIRM
                form = "dict" if self.word(tokens[j + 1]) == "ない" else "stem"
                obligation = True
                j += 2
        aux_cond = False
        if j < n and self.word(tokens[j]) in AUXILIARY:
            # 〜している/〜されている:補助動詞後直接接名詞仍是定語;
            # 〜ていれば/〜てあれば 是条件形
            if self.word(tokens[j]) == "いない":
                polarity = POL_NEG
            aux_cond = self.word(tokens[j]) in CONDITIONAL_FORMS
            form = "cond" if aux_cond else "dict"
            j += 1
            if j < n and self.word(tokens[j]) in NEGATORS:
                polarity = POL_NEG
                j += 1
        if (j + 2 < n and self.word(tokens[j]) == "事"
                and tokens[j + 1] in ("p:が", "p:も", "p:は")
                and self.word(tokens[j + 2]) in POTENTIAL | POTENTIAL_NEG):
            polarity = (POL_NEG if self.word(tokens[j + 2]) in POTENTIAL_NEG
                        else POL_CAN)
            j += 3
        conditional = suru_form in CONDITIONAL_FORMS or form == "cond" \
            or aux_cond or (w is not None and w in CONDITIONAL_FORMS)
        anchor = self._finish(tokens, head, i, j, action, polarity, form, passive,
                              fold, clause_start, conditional)
        if anchor is not None and obligation:
            anchor["obligation"] = True
        if anchor is not None and complement:
            anchor["complement"] = complement
        return anchor

    def _topic_action(self, tokens, i, clause_start):
        """裸 できる/できない 的主題(は 前的名詞)是動作名詞時回它的動作名。"""
        for k in range(i - 1, clause_start, -1):
            if tokens[k] != "p:は":
                continue
            head = self.word(tokens[k - 1])
            if head == "発動" and k - 3 >= clause_start and tokens[k - 2] == "p:の" \
                    and tokens[k - 3].startswith("d:この:"):
                return None           # このカードの発動は手札からもできる
            if head == "召喚":
                return self._method_prefix(tokens, k - 2, clause_start)[0] + "召喚"
            if head == "効果":
                return "できる"       # 効果は１ターンに１度しかできない:述語就是 できる
            if head in SAHEN_NOUNS:
                return self._compound_action(tokens, k - 1, clause_start) or head
            break
        # 攻撃宣言もできない/特殊召喚ができない:も/が 前的動作名詞
        if i - 2 >= clause_start and tokens[i - 1] in ("p:も", "p:しか", "p:が"):
            head = self.word(tokens[i - 2])
            if head == "召喚":
                return self._method_prefix(tokens, i - 3, clause_start)[0] + "召喚"
            if head in SAHEN_NOUNS:
                return self._compound_action(tokens, i - 2, clause_start) or head
        return None

    def _summon_phrases(self, tokens, start, stop):
        """[start, stop) 裡的召喚片語「(法(・法)*)召喚」的字面,依原文順序。"""
        out = []
        for m in range(start, stop):
            if self.word(tokens[m]) != "召喚":
                continue
            s = m
            while s - 1 >= start and token_kind(tokens[s - 1]) == "method":
                s -= 1
                if s - 2 >= start and tokens[s - 1] == "・" \
                        and token_kind(tokens[s - 2]) == "method":
                    s -= 1
            out.append(self._text(tokens[s:m + 1]))
        return out

    def _performed_summons(self, tokens, a, args):
        """行う 的對象是召喚時(frame-lemma-variants 票 01):回 [(召喚的原詞元, 論元)],否則 None。
        對象(を;主題形 このカードの融合召喚は…行えない 是 は;しか 型沒有對象)以召喚片語收尾:
        「の」前的名詞片語是新的對象(連同切出的區域),沒有「の」時對象空;主題形的所有格只留子句
        字面。「〜を３回まで行う」的上限數量併進了對象(通常召喚3回まで):召喚片語接「…まで」
        也算,數量只留子句字面、對象空。「召喚・特殊召喚」的 ・ 並列與「AのS召喚またはBのX召喚」
        各出一組、各帶自己的對象;
        受事者片語切出的區域是整段的,分不到哪一組,這時不帶(語料 1 句、沒有區域)。法鏈
        (融合・S・X・リンク召喚)由呼叫端照召喚並列展開。"""
        phrases = sorted(self._summon_phrases(tokens, a["clause_start"], a["head"]),
                         key=len, reverse=True)
        if not phrases:
            return None
        if args.get("object"):
            role = "object"
        elif args.get("topic") and any(args["topic"].endswith(q) for q in phrases):
            role = "topic"
        elif tokens[a["head"] - 1] == "p:しか" and self.word(tokens[a["head"] - 2]) == "召喚":
            return [(self._summon_phrases(tokens, a["clause_start"], a["head"] - 1)[-1], args)]
        else:
            return None
        out = []
        split = args.get("split", {}).get(role)
        parts = []
        for part in args[role].split("または"):
            pieces = part.split("・")
            # 召喚・特殊召喚:・ 並列的召喚片語各一組(法鏈 融合・S召喚 整段就是一個片語)
            parts += pieces if part not in phrases and all(p in phrases for p in pieces) \
                else [part]
        for part in parts:
            phrase = next((q for q in phrases if part == q or part.endswith("の" + q)
                           or role == "object" and len(parts) == 1 and part.startswith(q)
                           and part.endswith("まで")), None)
            if phrase is None:
                return None
            owner = part[:-len(phrase) - 1] if part.endswith("の" + phrase) else None
            argued = dict(args, split={key: v for key, v in args.get("split", {}).items()
                                       if key != role})
            argued[role] = owner if role == "object" else None
            if role == "object" and owner and split and len(parts) == 1:
                place, rest = split
                if rest is not None and rest.endswith("の" + phrase):
                    rest = rest[:-len(phrase) - 1]
                argued["split"]["object"] = (place, rest)
            out.append((phrase, argued))
        return out

    def _compound_action(self, tokens, k, clause_start):
        """tokens[k] 的サ変名詞連同前一個詞是完整動作名(攻撃|宣言、直接|攻撃;票 04)時回它,
        否則 None。"""
        if k - 1 < clause_start:
            return None
        return COMPOUND_ACTIONS.get((self.word(tokens[k - 1]), self.word(tokens[k])))

    def _fold_complement(self, tokens, i, clause_start, lemma):
        """tokens[i] 是 する/なる,前一格是 に/と:回 (動作, 併入格數, 不併的補語)。
        補語全是名詞類且不含數字時併入動作 → (補語+助詞+詞元, 格數, None);補語是數字或沒有補語
        → (助詞+詞元, 0, None);補語最後一個詞是封閉值域字面或屬性名詞(action_lemmas 的補語不併
        判準;frame-lemma-unify 票 05)→ (助詞+詞元, 0, 詞元 する/なる)——整段補語是目的論元
        (時間語也收)。"""
        if i - 1 < clause_start or tokens[i - 1] not in ("p:に", "p:と"):
            return lemma, 0, None
        particle = tokens[i - 1][2:]
        k = i - 1
        while (k - 1 >= clause_start and (i - 1) - (k - 1) <= FOLD_MAX
               and token_kind(tokens[k - 1]) in ("lex", "elided", "method", "attr")
               and self.is_noun_like(tokens[k - 1])
               and self.word(tokens[k - 1]) not in FOLD_STOP):
            k -= 1
        if k == i - 1:
            return particle + lemma, 0, None
        if self._is_value_complement(tokens[k:i - 1]):
            return particle + lemma, 0, lemma
        text = "".join(self.surface(t) for t in tokens[k:i - 1])
        methods = self._material_methods(tokens, k, clause_start) if text == "素材" else None
        if methods:
            text = methods + text      # 融合・S・X召喚の素材 → 融合・S・X素材(呼叫端一法一框)
        return text + particle + lemma, i - k, None

    def _material_methods(self, tokens, k, clause_start):
        """tokens[k] 的 素材 前面是「法(・法)*召喚の」(frame-lemma-variants 票 02)→ 法鏈字面
        (融合・S・X),否則 None;法要都是有素材詞元的(action_lemmas.MATERIAL_METHODS,
        リンク 照寫法歸一算 L)。"""
        if k - 2 < clause_start or tokens[k - 1] != "p:の" or self.word(tokens[k - 2]) != "召喚":
            return None
        phrase = self._summon_phrases(tokens, clause_start, k - 1)[-1][:-2]
        if phrase and all(action_lemmas.spell(m + "素材")[:-2] in action_lemmas.MATERIAL_METHODS
                          for m in phrase.split("・")):
            return phrase
        return None

    def _is_value_complement(self, complement):
        """補語的最後一個詞是「值」或「屬性」(闇属性、裏側守備表示、エンドフェイズ、レベル、
        数値、以下の効果…):action_lemmas.COMPLEMENT_VALUE_CLASSES 的封閉值域字面、COMPLEMENT_ATTRIBUTES
        (合計|値、合計|分 兩詞連起來比)或 COMPLEMENT_VALUE_HEADS。"""
        words = [self._base_word(t) for t in complement[-2:]]
        last = complement[-1]
        if words[-1] is None:
            return False
        wid = last.split(":", 2)[-1]            # 詞典詞本身或 指示詞/省略寫法 指的詞
        return (self.lex.closed_of[wid] in action_lemmas.COMPLEMENT_VALUE_CLASSES
                or words[-1] in action_lemmas.COMPLEMENT_ATTRIBUTES
                or words[-1] in action_lemmas.COMPLEMENT_VALUE_HEADS
                or (None not in words
                    and "".join(words) in action_lemmas.COMPLEMENT_ATTRIBUTES))

    def splits_complement(self, lemma):
        """「N に/と する」形的詞元,補語會被不併判準拆開(值或屬性:裏側守備表示にする、属性にする)
        時為真——框架抽取產不出這種詞元(類別樹建置檢查用,category-lemma-followup 票 05)。"""
        tokens = self.tokenizer.tokenize(lemma)
        if len(tokens) < 3 or self.word(tokens[-1]) != "する":
            return False
        _, _, unfolded = self._fold_complement(tokens, len(tokens) - 1, 0, "する")
        return unfolded is not None

    def _finish(self, tokens, head, verb_at, j, action, polarity, form, passive,
                fold, clause_start, conditional=False):
        n = len(tokens)
        nominalizer = None
        if j < n and self.word(tokens[j]) in AUXILIARY and j + 1 < n \
                and self.word(tokens[j + 1]) in NOMINALIZERS:
            j += 1                    # 〜としている場合
            form = "dict"
        turn_at = self._event_turn_after(tokens, j) if form in ("past", "neg", "dict") \
            else None
        if j < n and self.word(tokens[j]) in NOMINALIZERS:
            nominalizer = self.word(tokens[j])
            j += 1
        elif turn_at is not None:
            # 〜した次のターン/〜された自分・相手ターン:ターン 仍是形式名詞(事件界定的
            # 回合),與「〜したターン」一致出條件框架;中間的 次の/玩家 留在子句裡
            # (v2-round1)
            nominalizer = "ターン"
            j = turn_at + 1
        elif form not in ("te", "stem", "cond") and j < n \
                and self.is_noun_like(tokens[j]):
            return None               # 定語:動詞直接修飾後面的名詞
        elif form in ("dict", "past", "neg") and j + 1 < n and tokens[j] == "、" \
                and self.is_noun_like(tokens[j + 1]):
            return None               # 「X」を除く、…モンスター:隔讀點的定語
        if form == "noun" and nominalizer is None:
            return None
        end = j
        # 子句尾:形式名詞/述語後的助詞與讀點一併收進本子句
        while j < n and (token_kind(tokens[j]) == "particle" or tokens[j] == "、"):
            j += 1
        return {"head": head, "verb_at": verb_at, "end": end, "tail": j,
                "action": action, "polarity": polarity, "form": form,
                "passive": passive, "nominalizer": nominalizer,
                "fold": fold, "conditional": conditional
                or nominalizer in CONDITIONAL_NOMINALIZERS}

    def _event_turn_after(self, tokens, j):
        """tokens[j] 起是否為「(次 の)(自分/相手/お互い(・)…)ターン」→ ターン 的位置,
        否則 None。動詞後直接接這段時,ターン 是事件界定的回合的形式名詞。"""
        n = len(tokens)
        k = j
        if k + 1 < n and self.word(tokens[k]) == "次" and tokens[k + 1] == "p:の":
            k += 2
        seen_player = False
        while k < n and (self.word(tokens[k]) in ("自分", "相手", "お互い")
                         or tokens[k] == "・" and seen_player):
            seen_player = seen_player or self.word(tokens[k]) is not None
            k += 1
        if k < n and seen_player and tokens[k] == "p:の":
            k += 1                    # お互いのターン
        if k > j and k < n and self.word(tokens[k]) == "ターン":
            return k
        return None

    # ── 論元 ──
    def chunks(self, tokens, start, stop):
        """[start, stop) 依格助詞切片語 → [(role, [tokens], hard_before)]。"""
        out, cur, hard = [], [], False
        k = start - 1
        while k + 1 < stop:
            k += 1
            t = tokens[k]
            kind = token_kind(t)
            if kind == "particle":
                p = t[2:]
                # 助詞後接 の(への戦闘ダメージ/EXデッキからの特殊召喚/１～６までの)
                # 是修飾,留在片語裡;に対して(對…)整組不是論元
                if p != "の" and k + 1 < stop and tokens[k + 1] == "p:の":
                    cur.append(t)
                    continue
                # 後綴助詞後接格助詞(１体のみを):不切;〜とは(そのモンスターとは
                # 種族が異なる)的 は 是定語子句的主題,不切
                if p in CASE_SUFFIX and k + 1 < stop and token_kind(
                        tokens[k + 1]) == "particle" and tokens[k + 1][2:] in CASE_ROLE:
                    continue
                if p == "は" and cur and cur[-1] == "p:と":
                    cur.append(t)
                    continue
                # 〜としている:として+補助動詞 是一個述語(定語用法留在片語裡)
                if (p == "として" and k + 1 < stop
                        and self.word(tokens[k + 1]) in AUXILIARY):
                    cur.append(t)
                    continue
                if p in CASE_ROLE and not cur:
                    continue              # 開頭副詞被剝掉後的裸助詞(このターンに)
                # 通常召喚に加えて:慣用,整組不是論元
                if (p == "に" and k + 1 < stop and self.word(tokens[k + 1]) == "加えて"
                        and cur and self.word(cur[-1]) == "召喚"):
                    out.append(["に加えて", cur, hard])
                    cur, hard = [], False
                    k += 1
                    continue
                if (p == "に" and k + 2 < stop and self.word(tokens[k + 1]) == "対"
                        and self.word(tokens[k + 2]) in ("して", "し")):
                    out.append(["に対して", cur, hard])
                    cur, hard = [], False
                    k += 2
                    continue
                # によって/による(依…)、〜の代わりに(代替)、ランダムに:手段/
                # 方式,不是目的論元
                if (p == "に" and k + 1 < stop
                        and self.word(tokens[k + 1]) in ("よって", "よる", "より")):
                    out.append(["によって", cur, hard])
                    cur, hard = [], False
                    k += 1
                    continue
                if p == "で" and cur and (token_kind(cur[-1]) == "quant" or (
                        token_kind(cur[-1]) == "lex"
                        and self.lex.closed_of[cur[-1]] == "種族")) and any(
                            tokens[m] == "p:の" for m in range(k + 1, min(stop, k + 4))):
                    cur.append(t)         # 種族で属性の:並列修飾
                    continue
                if p == "に" and cur and self.word(cur[-1]) in MANNER_NI:
                    out.append(["に(方式)", cur, hard])
                    cur, hard = [], False
                    continue
                if p in CASE_ROLE or (p in CASE_OTHER and p not in CASE_SUFFIX):
                    # 片語開頭的裸數量/全て(カードを３枚墓地へ、モンスターを全て
                    # 墓地へ)屬前一個 を 片語
                    lead = 0
                    while lead < len(cur) and (
                            token_kind(cur[lead]) in ("num", "counter", "quant",
                                                      "range")
                            or self.word(cur[lead]) in ("全て", "それぞれ")):
                        lead += 1
                    # 裸數字後面不是量詞(１ターンに 的 １)不算數量
                    if lead and token_kind(cur[lead - 1]) == "num":
                        lead = 0
                    if 0 < lead < len(cur) and out and out[-1][0] == "を":
                        out[-1][1] = out[-1][1] + [
                            t for t in cur[:lead]
                            if self.word(t) not in ("全て", "それぞれ")]
                        cur = cur[lead:]
                    out.append([p, cur, hard])
                    cur, hard = [], False
                elif p in CASE_SUFFIX:
                    if cur:
                        out.append([p, cur, hard])
                        cur, hard = [], False
                    # 後綴型(にも/には):前一格照舊
                elif p == "と" and k == stop - 1:
                    # 述語緊前的 と(〜となる/〜とする 的補語)當目的論元
                    out.append(["と", cur, hard])
                    cur, hard = [], False
                elif p == "と" and k + 1 < stop and self.word(tokens[k + 1]) == "戦闘":
                    out.append(["と(共同)", cur, hard])   # モンスターと戦闘を行う
                    cur, hard = [], False
                elif p in COORDINATORS or p == "の":
                    cur.append(t)
                continue
            if kind == "punct":
                if t == "、":
                    # 定語動詞後的讀點(「X」を除く、…モンスター)在名詞片語裡;
                    # 卡名列舉的讀點(「A」、「B」、「C」モンスター)也是
                    if cur and self._predicate_lemma(cur, len(cur) - 1) is not None:
                        continue
                    if (cur and token_kind(cur[-1]) == "name" and k + 1 < stop
                            and token_kind(tokens[k + 1]) == "name"):
                        continue
                    if k + 1 < stop and tokens[k + 1] in ("p:または", "p:及び"):
                        continue
                    if cur and cur[-1] == "p:の":
                        continue          # そのモンスター以外の、…
                    if cur:
                        out.append([None, cur, hard])
                    cur, hard = [], True
                elif t == "：":
                    # ●選項標籤「●…：」:標籤不是論元,也是硬邊界
                    out.append(["：", cur, hard])
                    cur, hard = [], True
                elif t in PUNCT_IN_PHRASE:
                    cur.append(t)
                continue
            # 片語開頭的副詞/接續詞/このターン 不屬論元
            if not cur and (self.word(t) in LEADING_ADVERBS or (
                    t.startswith("d:") and self.word(t.split(":", 2)[2]) == "ターン")):
                continue
            cur.append(t)
        if cur:
            out.append([None, cur, hard])
        return out

    def _predicate_lemma(self, chunk, k):
        """chunk[k] 是定語位置的述語時回它的詞元(含 た/いる 尾往前找動詞)。"""
        w = self.word(chunk[k])
        if w is None:
            return None
        if w in TAILS or w in AUXILIARY:
            for m in range(k - 1, -1, -1):
                v = self.word(chunk[m])
                if v is None:
                    # 〜としている+名詞:として+いる 是定語(X素材としているモンスター)
                    return "とする" if chunk[m] == "p:として" and w in AUXILIARY \
                        else None
                if v in TAILS or v in AUXILIARY or v in NEGATORS:
                    continue
                if v in SURU_FAMILY:
                    prev = self.word(chunk[m - 1]) if m else None
                    return prev or v
                return self.lex.lemma_of[chunk[m]] if self.lex.is_verb(
                    chunk[m]) else None
            return None
        if w in SURU_FAMILY and w not in NON_ATTRIBUTIVE_SURU:
            prev = self.word(chunk[k - 1]) if k else None
            return prev or w
        if w in NEGATORS and k >= 1 and self.lex.is_verb(chunk[k - 1]):
            return self.lex.lemma_of[chunk[k - 1]]      # レベルを持たない
        if w in NEGATORS or w == "な" or w == "同じ":
            return w
        if self.lex.lemma_of[chunk[k]] in ADJECTIVE_LEMMAS:
            return self.lex.lemma_of[chunk[k]]    # レベルが高いモンスター
        if self.lex.is_verb(chunk[k]) and verb_form(
                w, self.lex.lemma_of[chunk[k]]) not in ("te", "stem", "irrealis"):
            return self.lex.lemma_of[chunk[k]]
        return None

    def _relative_verb(self, chunk, trailing=False):
        """片語含定語動詞(動詞/する家族後直接接名詞)→ 回該定語的詞元;
        前面的片語屬同一名詞片語。連用形/て形不算。trailing:片語尾的動詞也算
        (後面接的是併入動作的名詞:戦闘を行う|攻撃宣言時)。"""
        for k, (a, b) in enumerate(zip(chunk, chunk[1:])):
            if not self.is_noun_like(b):
                continue
            lemma = self._predicate_lemma(chunk, k)
            if lemma is not None:
                return lemma
        if trailing and chunk:
            return self._predicate_lemma(chunk, len(chunk) - 1)
        return None

    def arguments(self, tokens, start, stop, trailing=False, complement=None):
        """[start, stop) 的論元 → (args, carry):args 是本述語的對象/來源/目的,
        carry 是多個 を 時留給下一個述語的論元(そのモンスターを効果を無効にして
        特殊召喚し:無効にする 只拿最後一個 を,前面的 を 與 から 給 特殊召喚)。
        complement:最後一格是 N に/と なる/する 不併的補語時是 する/なる(frame-lemma-unify
        票 05)——時間語(エンドフェイズになる)也收成目的;補語裡的定語不吸收述語的期間
        (ターン終了時まで宣言した属性になる),する 的補語也不吸收句裡唯一的 を(そのモンスターの
        レベルを|宣言したレベルにする:を 是 にする 的對象)。"""
        parts = self.chunks(tokens, start, stop)
        merged = []
        for idx, (role, chunk, hard) in enumerate(parts):
            rel = self._relative_verb(chunk, trailing and idx == len(parts) - 1)
            if rel is None and merged and merged[-1][0] == "が" and merged[-1][1] \
                    and self.word(merged[-1][1][-1]) in ATTR_NOUNS \
                    and "p:の" in chunk[:3] and role in ATTR_HEAD_ROLES:
                rel = "が"              # 攻撃力と守備力が|０の悪魔族モンスター
            own = chunk
            front_hard = hard
            if rel is not None and merged and not hard:
                # 往前併到讀點或主題(は)為止;特定動詞只吸收自己的格
                scope = RELATIVE_SCOPE.get(rel)
                absorbed = []
                verb_rel = rel not in ("が", "な", "同じ") \
                    and rel not in ADJECTIVE_LEMMAS and rel not in NEGATORS \
                    and rel not in RELATIVE_SCOPE
                taken = set()
                # 不併的補語(票 05):期間與 する 的唯一對象屬述語,不屬補語裡的定語
                is_complement = complement is not None and idx == len(parts) - 1
                while merged and merged[-1][0] not in NON_ABSORB_ROLES:
                    r, c, h = merged.pop()
                    complement_stop = is_complement and bool(c) and (
                        (r == "まで" and self._is_time(c))
                        or (complement == "する" and r == "を"
                            and all(m[0] != "を" for m in merged)))
                    if (scope is not None and (r not in scope or r in taken)) or (
                            verb_rel and r == "が" and c
                            and self.word(c[-1]) in ATTR_NOUNS) or complement_stop:
                        merged.append([r, c, h])
                        break
                    taken.add(r)
                    absorbed.insert(0, c + (["p:" + r] if r else []))
                    front_hard = h
                    if h or rel == "が":
                        break
                chunk = [t for c in absorbed for t in c] + chunk
            # 定語動詞停在屬性 が 前時(攻撃力か守備力が|２０００の通常召喚できないモンスター、
            # 属性が|…と同じ…モンスター):屬性 が 仍屬名詞片語,併進來(frame-args-v3 v3-round1)
            if (rel not in (None, "が") and merged and merged[-1][0] == "が" and merged[-1][1]
                    and not front_hard and role in ATTR_HEAD_ROLES
                    and self.word(merged[-1][1][-1]) in ATTR_NOUNS
                    and ("p:の" in own[:3]
                         or any(self.word(t) in COMPARE_AFTER_TO for t in own))):
                chunk = merged.pop()[1] + ["p:が"] + chunk
            merged.append([role, chunk, hard])
        # 並列(と/や/または/及び/か 結尾)併入下一格
        joined = []
        for role, chunk, hard in merged:
            if (joined and joined[-1][0] is None and joined[-1][1]
                    and token_kind(joined[-1][1][-1]) == "particle"):
                prev = joined.pop()
                chunk = prev[1] + chunk
            joined.append([role, chunk, hard])
        # 多個 を:只有最後一個屬本述語,前面的(連同其前的 から)留給下一個述語
        carry = {}
        wo_at = [k for k, (role, chunk, _h) in enumerate(joined) if role == "を"]
        if len(wo_at) >= 2:
            cut = wo_at[-2] + 1
            carried, joined = joined[:cut], joined[cut:]
            for role, chunk, _h in carried:
                key = CASE_ROLE.get(role)
                if key and chunk and key not in carry:
                    carry[key] = "".join(self.surface(t) for t in self._trim(chunk))
                    found = self.split_place(self._trim(chunk)) if key == "object" else None
                    if found:
                        carry["split"] = {"object": found}
        args = {}
        spans = {}                    # 論元的詞序列(受事者切區域用,票 04)
        last_key = None
        for idx, (role, chunk, _hard) in enumerate(joined):
            # 主題(は 前)與主語(が 前;frame-args-v3 票 02):同一子句有多個時取離述語最近的
            if role in TOPIC_ROLES and self._trim(chunk):
                key = TOPIC_ROLES[role]
                if key == "subject" and self._embedded_subject(joined, idx):
                    last_key = None
                    continue
                spans[key] = self._clause_tail(self._trim(chunk))
                args[key] = "".join(self.surface(t) for t in spans[key])
                # 主題在主語之前(このカードは、相手モンスターが…場合):條件子句的主題屬主句(票 03)
                args["topic_first"] = key == "subject" and "topic" in args
                last_key = None
                continue
            if role == "まで" and last_key == "object" and chunk and all(
                    token_kind(t) in QUANTITY_KINDS
                    for t in chunk):
                # 「〜を２枚まで」:上限數量併回對象
                args[last_key] += "".join(self.surface(t) for t in chunk) + "まで"
                spans[last_key] = spans[last_key] + chunk + ["p:まで"]
                continue
            key = CASE_ROLE.get(role, "goal" if role == "と" else None)
            if key is None or not chunk:
                last_key = None
                continue
            is_complement = complement is not None and idx == len(joined) - 1
            if key == "goal" and self._is_time(chunk) and not is_complement:
                last_key = None
                continue
            chunk = self._trim(chunk)
            if is_complement:
                # このターンのエンドフェイズ:開頭的 このターン 已剝掉,剩下的 の 不屬補語;
                # 「…は全て守備表示になる」的 全て 是主題的量化詞(lemma-round1)
                while chunk and (chunk[0] == "p:の" or self.word(chunk[0]) in ("全て", "それぞれ")):
                    chunk = chunk[1:]
            if not chunk:
                continue
            text = "".join(self.surface(t) for t in chunk)
            args[key] = text if key not in args else args[key] + "、" + text
            spans[key] = chunk if key not in spans else spans[key] + ["、"] + chunk
            last_key = key
        # 受事者候選(對象/主題/主語)片語裡的區域(票 04);用哪一個由框架依被動決定
        args["split"] = {key: found for key in PATIENT_KEYS if key in spans
                         for found in [self.split_place(spans[key])] if found}
        return args, carry

    def _embedded_subject(self, joined, idx):
        """joined[idx] 的 が 片語不是本述語的主語(v3-round1):後面緊接定語述語(攻撃力が|超えた
        分)、或後面還有沒成錨點的條件子句(自分のLPが相手より少ない場合、…)。"""
        if idx + 1 < len(joined) and joined[idx + 1][1] \
                and self._is_predicate(joined[idx + 1][1][0]):
            return True
        return any(self.word(t) in UNANCHORED_CONDITIONS
                   for _r, chunk, _h in joined[idx + 1:] for t in chunk)

    def _clause_tail(self, chunk):
        """主題/主語片語裡夾著沒成錨點的連用子句(自分のLPが相手より少なく、このカード):只取
        最後一個連用形述語之後的部分。"""
        for i in range(len(chunk) - 2, -1, -1):
            if self._is_predicate(chunk[i]) and self._is_continuative(chunk[i]):
                return [t for t in chunk[i + 1:] if t != "、"] or chunk
        return chunk

    def _is_continuative(self, token):
        """形容詞的連用形(少なく、高く):後面是另一個子句。動詞的て形/連用形常在定語子句
        裡(…を使用して儀式召喚したこのカード、送られていない),不算。"""
        return self.word(token).endswith("く") and self.lex.lemma_of[token] in ADJECTIVE_LEMMAS

    # ── 受事者的區域切分(frame-args-v3 票 04)──
    def split_place(self, chunk):
        """受事者片語的詞序列 → (區域字面, 剩餘字面);受事者本身就是區域(整個片語是區域:
        手札、相手のEXデッキ;或片語以區域收尾:このカード以外の手札)時剩餘為 None、受事者
        欄不動;沒有區域回 None。每個並列段(と/か/や/及び/または 隔開;と同じ 的 と 是比較,
        不算)切它第一段「(玩家の)區域の」——片語開頭、の/讀點/定語述語之後都算段首;段裡的
        區域後面隔著定語述語又出現區域時,前面那個在定語子句裡、不是受事者的,改用後面的。
        多段的區域依字面順序以「・」並列、去重。"""
        n = len(chunk)
        found = []                  # (切的起點, 切的終點或 None(不切), 區域字面)
        k, at_boundary, part_found, reopen = 0, True, False, False
        while k < n:
            t = chunk[k]
            if self._coordinates(chunk, k):
                k, at_boundary, part_found, reopen = k + 1, True, False, False
                continue
            if part_found and self._is_predicate(t):
                reopen = True           # 定語述語之後若還有區域,前面那個在定語子句裡
            if at_boundary and (not part_found or reopen) and not self._counts_from(chunk, k):
                end = self._place_segment(chunk, k)
                head = end is not None and self._head_end(chunk, end)
                # 除外されている(自分の)X:狀態寫法的區域直接修飾名詞,後面沒有 の
                banished = end is not None and not head and chunk[end] != "p:の" \
                    and self._base_word(chunk[k]) == "除外" and self.word(chunk[k + 1]) == "されて"
                if end is not None and (head or banished or chunk[end] == "p:の"):
                    lo = self._qualified_start(chunk, k, end)
                    if part_found:
                        found.pop()
                    found.append((lo, None if head else end if banished else end + 1,
                                  self._text(chunk[lo:end])))
                    part_found, reopen = True, False
                    k, at_boundary = (end if head or banished else end + 1), True
                    continue
            # 段首:の/讀點之後,或定語述語(含む、された)之後;助詞之後不算(この効果で|除外
            # されている:區域詞是定語子句自己的述語)
            at_boundary = t in ("p:の", "、") or self._is_predicate(t) \
                or self.word(t) in COMPARE_AFTER_TO
            k += 1
        if not found:
            return None
        places = []
        for _lo, _hi, text in found:
            if text not in places:
                places.append(text)
        cuts = [(lo, hi) for lo, hi, _text in found if hi is not None]
        rest = [t for i, t in enumerate(chunk) if not any(lo <= i < hi for lo, hi in cuts)]
        return "・".join(places), (self._text(rest) if cuts and rest else None)

    def _head_end(self, chunk, end):
        """區域段結尾 end 之後到並列分隔前什麼都沒有、或只有數量(手札を１枚):區域就是受事者本身。"""
        for k in range(end, len(chunk)):
            if self._coordinates(chunk, k):
                return True
            if token_kind(chunk[k]) not in QUANTITY_KINDS:
                return False
        return True

    def _coordinates(self, chunk, k):
        """chunk[k] 是並列受事者的分隔;「と同じ/と異なる」的比較、「となる」的引用 と 不算
        (並列的 と 後面接名詞)。"""
        return chunk[k] in PATIENT_COORDINATORS and not (
            chunk[k] == "p:と" and k + 1 < len(chunk)
            and (self.word(chunk[k + 1]) in COMPARE_AFTER_TO
                 or not self.is_noun_like(chunk[k + 1])))

    def _is_predicate(self, token):
        """片語裡的定語述語(含む、された、持つ、なる、高い…):動詞、形容詞、する家族與補助/
        否定/活用尾;通常の、それ 這類功能詞不算。"""
        if token_kind(token) != "lex":
            return False
        w = self.word(token)
        return self.lex.is_verb(token) or self.lex.lemma_of[token] in ADJECTIVE_LEMMAS \
            or w in SURU_FAMILY or w in AUXILIARY or w in TAILS or w in NEGATORS

    def _qualified_start(self, chunk, k, end):
        """區域前的位置限定語連同玩家一起切(自分の中央の|メインモンスターゾーン):回切的起點。"""
        lo = k
        if lo >= 2 and chunk[lo - 1] == "p:の" and self.word(chunk[lo - 2]) in POSITION_WORDS:
            lo -= 2
            if lo >= 1 and chunk[lo - 1] == "・":
                return k              # 左端・右端の:並列的限定語不併,只切區域
            if lo >= 2 and chunk[lo - 1] == "p:の" and self.word(chunk[lo - 2]) in PLAYER_WORDS:
                lo -= 2
        return lo if lo == k or parse_place(self._text(chunk[lo:end]))[1] else k

    def _counts_from(self, chunk, k):
        """chunk[k] 起到下一個並列分隔前是數量(…の数×100ダメージ、…の合計):區域修飾的是
        數量,受事者不在那裡。"""
        for t in chunk[k:]:
            if t in PATIENT_COORDINATORS:
                return False
            if self.word(t) in COUNT_WORDS or t == "×":
                return True
        return False

    def _text(self, tokens):
        return "".join(self.surface(t) for t in tokens)

    def _place_segment(self, chunk, k):
        """chunk[k] 起是不是一段區域字面:(玩家(か|・…玩家)の)區域(・|か…區域)(の 一番上),
        或 除外されている(玩家)——回這段的結尾(不含),不是時 None;最後由區域辨識
        (places.parse_place)確認認得出區域。"""
        n = len(chunk)
        m = k
        if (m + 2 < n and self._base_word(chunk[m]) == "除外" and self.word(chunk[m + 1]) == "されて"
                and self.word(chunk[m + 2]) == "いる"):
            m += 3
            if m < n and self.word(chunk[m]) in PLAYER_WORDS:
                m += 1
        else:
            if self.word(chunk[m]) in PLAYER_WORDS:
                m += 1
                while (m + 1 < n and chunk[m] in PLACE_JOINERS
                       and self.word(chunk[m + 1]) in PLAYER_WORDS):
                    m += 2
                if m + 1 < n and chunk[m] in PLACE_JOINERS \
                        and self._zone_end(chunk, m + 1) is not None:
                    m += 1            # 自分または|相手フィールド:玩家與帶玩家的區域詞並列
                elif m + 1 >= n or chunk[m] != "p:の":
                    return None
                else:
                    m += 1
            m = self._zone_end(chunk, m)
            if m is None:
                return None
            while m + 1 < n and chunk[m] in PLACE_JOINERS \
                    and self._zone_end(chunk, m + 1) is not None:
                m = self._zone_end(chunk, m + 1)
            # デッキの一番上:牌組頂/底仍是區域(位置併進區域字面)
            if (m + 1 < n and chunk[m] == "p:の" and self.word(chunk[m + 1]) in DECK_POSITIONS
                    and (self._base_word(chunk[m - 1]) or "").endswith("デッキ")):
                m += 2
        return m if parse_place(self._text(chunk[k:m]))[1] else None

    def _zone_end(self, chunk, m):
        """chunk[m] 起是一個區域詞(含 除外|状態 兩詞、指示詞 その墓地、其後的括號註記
        フィールド（表側表示）)→ 回結尾(不含),否則 None。"""
        n = len(chunk)
        if m >= n:
            return None
        if m + 1 < n and self._base_word(chunk[m]) == "除外" and self.word(chunk[m + 1]) == "状態":
            m += 2
        elif self._base_word(chunk[m]) and "の" not in self._base_word(chunk[m]) \
                and parse_place(self._base_word(chunk[m]) if token_kind(chunk[m]) == "elided"
                                else self.surface(chunk[m]))[1]:
            m += 1
        else:
            return None
        if m < n and chunk[m] == "（" and "）" in chunk[m:m + PAREN_MAX + 2]:
            m = chunk.index("）", m) + 1
        return m

    def _base_word(self, token):
        """詞典詞的字面,指示詞取被指的詞(その墓地 → 墓地)、省略寫法取完整的詞(自分(フィールド)
        → 自分フィールド);其餘 None。"""
        kind = token_kind(token)
        if kind == "lex":
            return self.lex.surface_of[token]
        if kind in ("dem", "elided"):
            return self.lex.surface_of[token.split(":", 2)[2]]
        return None

    @staticmethod
    def _trim(chunk):
        """片語兩端不成對的括弧是註記邊界,不屬論元字面。"""
        while chunk and chunk[0] in ("（", "）") and (
                chunk[0] == "）" or chunk.count("（") > chunk.count("）")):
            chunk = chunk[1:]
        while chunk and chunk[-1] in ("（", "）") and (
                chunk[-1] == "（" or chunk.count("）") > chunk.count("（")):
            chunk = chunk[:-1]
        return chunk

    def _is_time(self, chunk):
        last = chunk[-1]
        w = self.word(last)
        if w in TIME_HEADS or (last.startswith("W")
                               and self.lex.closed_of[last] == "階段名"):
            return True
        if token_kind(last) == "counter" and last[2:] in ("度", "回"):
            return True
        return False

    # ── 整句 ──
    def _option_of_sentence(self, tokens, sentence):
        """句子以 ● 開頭時回它的標籤值(「●自分ターン：」冒號前的字面;沒有標籤時
        "");不是選項句回 None。"""
        start, end = sentence
        if start >= end or tokens[start] != OPTION:
            return None
        label = []
        for k in range(start + 1, end):
            t = tokens[k]
            if t == "：":
                text = "".join(label)
                return text if 0 < len(text) <= LABEL_MAX_CHARS else ""
            if t in ("。", OPTION):
                break
            label.append(self.surface(t))
        return ""

    def frames_of_tokens(self, tokens, text=None, extra=False, card_type=None):
        """一句效果句的詞序列 → 框架清單(動作框架與約束框架混排、依原文位置排序)。
        text 是原文(約束框架的對象欄用它取回 ①② 這類分詞器丟掉的字);extra 標
        效果外文本(召喚條件、素材行只在效果外文本認);card_type 是卡片子類型
        (素材框架的召喚法)。"""
        n = len(tokens)
        offsets = self.char_offsets(text, tokens, self.lex.surface_of) \
            if text is not None else None

        def text_of(start, end):
            """詞序列範圍的原文字面(對不回原文時退回 token 字面相連)。從前一個 token
            的結尾起算,分詞器丟掉的圈號(②の効果 的 ②)才留得住;呼叫端自己去頭尾。"""
            if offsets is not None and start < end <= len(offsets):
                lead = offsets[start - 1][1] if start else offsets[0][0]
                return text[lead:offsets[end - 1][1]]
            return "".join(self.surface(t) for t in tokens[start:end])
        sentences = []
        start = 0
        for k, t in enumerate(tokens):
            if t == "。":
                sentences.append((start, k + 1))
                start = k + 1
            elif t == OPTION and k > start:      # 選項邊界:● 開新的一句
                sentences.append((start, k))
                start = k
        if start < n:
            sentences.append((start, n))

        # 選項:第 n 個 ● 起的句子都屬選項 n,標籤取自 ● 句自己
        option_of, label_of = {}, {}
        option, label = None, None
        for s_idx, sentence in enumerate(sentences):
            found = self._option_of_sentence(tokens, sentence)
            if found is not None:
                option = (option or 0) + 1
                label = found or None
            option_of[s_idx], label_of[s_idx] = option, label

        anchors_by_sentence = []
        for s_start, s_end in sentences:
            anchors = []
            clause_start = s_start
            i = s_start
            while i < s_end:
                a = self.anchor_at(tokens, i, clause_start) \
                    if tokens[i] not in ("。", OPTION) else None
                if a is None:
                    i += 1
                    continue
                a["clause_start"] = clause_start
                # て形/連用形子句後面緊接定語動詞+名詞(〜を素材としてX召喚した
                # モンスター):整段是名詞片語,不是動作
                if a["form"] in ("te", "stem") and self._inside_relative(
                        tokens, a["end"], s_end):
                    i = a["tail"]
                    continue
                anchors.append(a)
                clause_start = a["tail"]
                i = a["tail"]
            # 〜よう(に) 子句(票 09):後面同一句還有述語時是它的連用修飾——不出框架,字面併入
            # 下一個述語的子句(span_start);論元仍照自己的範圍抽,交給下一個述語
            for a, b in zip(anchors, anchors[1:]):
                if a["nominalizer"] == "よう":
                    a["absorbed"] = True
                    b["span_start"] = span_start(a)
            anchors_by_sentence.append(anchors)

        # 括弧深度:（…）裡的註記(この効果は相手ターンでも発動できる)不算
        # 發動句的收尾,也不參與代價/條件判定
        depth, depth_at = 0, []
        for t in tokens:
            if t == "（":
                depth += 1
            depth_at.append(depth)
            if t == "）":
                depth = max(0, depth - 1)

        # 發動句:以 発動できる/発動する 收尾(括弧外、後接 。/（ 或句尾)的句子都是
        # (●選項各有自己的發動句);この効果は…発動できる 的速度註記除外
        marker_of = {}
        for s_idx, anchors in enumerate(anchors_by_sentence):
            s_start, s_end = sentences[s_idx]
            if self._topic_is_this_effect(tokens, sentences[s_idx]):
                continue
            for k, a in enumerate(anchors):
                if (a["action"] == "発動" and a["polarity"] != POL_NEG
                        and a["nominalizer"] is None
                        and depth_at[a["verb_at"]] == 0
                        and (a["end"] >= s_end - 1
                             or tokens[a["end"]] in ("。", "（"))):
                    m_args, _c = self.arguments(tokens, a["clause_start"],
                                                a["head"])
                    if "goal" in m_args:
                        continue
                    marker_of[s_idx] = k
                    break

        frames = []
        made = []                    # (句序, 錨點序, 錨點, 動作框架):第二版論元的後處理用
        for s_idx, anchors in enumerate(anchors_by_sentence):
            marker_idx = marker_of.get(s_idx)
            in_activation = marker_idx is not None
            # 約束框架(constraints.py):由句型認出;被吃掉範圍內的錨點不出動作框架
            found, consumed = self.finder.find(
                tokens, sentences[s_idx], anchors, marker_idx, depth_at,
                extra=extra, card_type=card_type, text_of=text_of)
            for fr in found:
                span = fr["span"]
                fr.update({"kind": KIND_CONSTRAINT, "sentence": s_idx,
                           "option": option_of[s_idx], "label": label_of[s_idx],
                           "clause": " ".join(self.surface(t)
                                              for t in tokens[span[0]:span[1]])})
                frames.append(fr)
            # 「この効果は…発動できない/発動できる」整句是效果本身的註記(速度/
            # 時機限制),句內的條件子句也不是這張卡的動作
            if self._topic_is_this_effect(tokens, sentences[s_idx]) and any(
                    self.word(t) == "発動"
                    for t in tokens[sentences[s_idx][0]:sentences[s_idx][1]]):
                continue
            # 條件鏈:發動句裡條件子句之前的子句都是條件;處理句裡緊接條件子句的
            # 連用/て形子句(存在し、…場合)也是條件
            cond_after = [False] * len(anchors)
            seen = False
            limit = marker_idx - 1 if in_activation else len(anchors) - 1
            s_end = sentences[s_idx][1]
            for k in range(limit, -1, -1):
                nxt_head = anchors[k + 1]["head"] if k + 1 < len(anchors) else s_end
                baai_ahead = anchors[k]["action"] in STATE_LEMMAS and any(
                    self.word(t) in ("場合", "時")
                    for t in tokens[anchors[k]["tail"]:nxt_head])
                cond_after[k] = seen if in_activation else baai_ahead or (
                    k + 1 < len(anchors) and anchors[k + 1]["conditional"]
                    and (anchors[k]["action"] in STATE_LEMMAS
                         or anchors[k]["form"] == "te"
                         and anchors[k]["polarity"] == POL_AFFIRM
                         and "、" not in tokens[anchors[k]["end"]:anchors[k]["tail"]]))
                if anchors[k]["conditional"]:
                    seen = True
            carry = {}
            pending_subject = None        # 附加子句(〜を素材として/〜するために)的主語,給下一個述語
            for k, a in enumerate(anchors):
                if any(lo <= a["verb_at"] < hi for lo, hi in consumed):
                    continue
                is_marker = in_activation and k == marker_idx
                before_marker = in_activation and k < marker_idx \
                    and depth_at[a["verb_at"]] == 0
                args, next_carry = self.arguments(
                    tokens, a["clause_start"], a["head"] - a["fold"],
                    trailing=a["form"] == "noun" or a["fold"] > 0,
                    complement=a.get("complement"))
                own = set(args)
                for key, value in carry.items():
                    if key != "split":
                        args.setdefault(key, value)
                for key, found in carry.get("split", {}).items():
                    if key not in own:
                        args["split"][key] = found
                carry = next_carry
                if a["action"].endswith("なる") and "source" in args:
                    carry["source"] = args.pop("source")   # 〜からリリースし
                subject_moved = False
                if pending_subject and not args.get("subject") and not args.get("topic"):
                    args["subject"], split = pending_subject
                    if split:
                        args["split"]["subject"] = split
                    subject_moved = True
                pending_subject = None
                if args.get("subject") and (
                        a["action"].endswith("素材とする") and a["form"] == "te"
                        or a["nominalizer"] == "ため"):
                    pending_subject = (args.pop("subject"), args["split"].pop("subject", None))
                if a.get("absorbed"):
                    # 〜よう 子句:主語(含附加子句移過來的)與目的是量條件(不結構化),
                    # 對象/來源/主題屬下一個述語
                    for key in ABSORBED_KEYS:
                        if args.get(key):
                            carry[key] = args[key]
                            if key in args["split"]:
                                carry.setdefault("split", {})[key] = args["split"][key]
                    continue
                # 発動 本身:發動句的收尾(このカードを発動できる)、速度註記、
                # 〜するために 都不是動作;有別的對象/來源(〜を発動できない、
                # デッキから「X」を発動できる)才成框架
                if a["action"] == "発動" and a["polarity"] != POL_NEG and (
                        a["nominalizer"] in (None, "ため")
                        and not ("object" in args or "source" in args
                                 or "goal" in args)
                        or a["nominalizer"] == "ため"
                        or args.get("object") in ("このカード", "この効果")
                        or a["nominalizer"] is None
                        and (args.get("object") or "").endswith("効果")):
                    continue
                if a["conditional"] or a["action"] == "対象とする":
                    position = POS_COND
                elif is_marker:
                    position = POS_EFFECT
                elif before_marker:
                    if (a["passive"] or a["action"] in STATE_LEMMAS
                            or cond_after[k]
                            or a["form"] in ("dict", "past", "neg")
                            and a["nominalizer"] != "事"
                            or a["action"] in ("選択", "選ぶ")
                            and args.get("source", "").startswith("以下")):
                        position = POS_COND
                    else:
                        position = POS_COST
                elif cond_after[k]:
                    position = POS_COND
                else:
                    position = POS_EFFECT
                span = (span_start(a), a["end"])
                clause = " ".join(self.surface(t) for t in tokens[span[0]:span[1]])
                # 效果內容的次數/窗口(１度だけ、追加召喚的 自分メインフェイズに)記在
                # 動作框架自己身上(約束框架票 06)
                # 〜よう 子句併入時從併入的起點掃,上一個錨點是併入段之前的那個(票 09)
                prev = next((b for b in reversed(anchors[:k]) if not b.get("absorbed")), None)
                fields = self.finder.action_fields(
                    tokens, span_start(a), a["head"], in_activation, prev_anchor=prev)
                # 條件子句裡主題在自己的主語之前:主題屬主句,不給條件框架,交給後面延續(票 03)
                a["lifted_topic"] = args.pop("topic") if (
                    a["conditional"] and args.get("topic_first")) else None
                # 「・」並列的述語名詞(召喚・特殊召喚した)與召喚法鏈(儀式・融合・
                # S・X召喚):各出一框架,共用後綴;行う 的對象是召喚時記那個召喚(票 01;
                # 主題先交給主句再分框)
                targets = [(action, args) for action in
                           self._coordinated_actions(tokens, a) + [a["action"]]]
                if a["action"] == "行う":
                    targets = self._performed_summons(tokens, a, args) or targets
                targets = [(each, argued) for action, argued in targets
                           for each in _each_method(action)]
                for action, own_args in targets:
                    # 第三版論元(票 02/04):主題、主語、所在 是可選欄,只在有值時帶;被動是抽取內部的
                    # 標記,正規化時轉成 態=受身
                    argued = self._frame_arguments(own_args, action, a["passive"])
                    frame = dict({"kind": KIND_ACTION, "sentence": s_idx,
                                  "action": action,
                                  "object": argued.pop("object"),
                                  "source": argued.pop("source"),
                                  "goal": own_args.get("goal"),
                                  "position": position,
                                  "polarity": a["polarity"],
                                  "option": option_of[s_idx],
                                  "label": label_of[s_idx],
                                  "span": list(span), "clause": clause},
                                 **fields, **argued)
                    self._infer(frame)
                    if subject_moved:
                        frame.setdefault("backfill", []).insert(0, "subject")
                    frames.append(frame)
                    made.append((s_idx, k, a, frame))
        # frame-args-v2:か 並列的連接與群組(票 02)→ 回填對象與來源(票 03)→ 純列舉項
        # 掛進列舉欄(票 01)
        self._link_groups(tokens, anchors_by_sentence, made, marker_of)
        self._carry_topic(made)
        self._backfill(tokens, made)
        self._attach_enumeration(tokens, sentences, option_of, frames, text_of)
        # 動作詞元正規化(frame-lemma-unify):以上規則都看原詞元,最後才過詞元對照表、記態
        for fr in frames:
            if fr["kind"] == KIND_ACTION:
                _normalize(fr)
        # 依原文位置混排;同起點時約束框架在前(穩定排序保住並列述語的順序)
        frames.sort(key=lambda f: (f["sentence"], f["span"][0],
                                   f["kind"] != KIND_CONSTRAINT))
        # 回指(action-patient-anaphora):讀回填、正規化之後的值,跨句號,所以排在最後
        anaphora.resolve(frames, self._phrases(tokens, sentences, option_of))
        return frames

    def _phrases(self, tokens, sentences, option_of):
        """回指的字面備援:一個編號效果裡的名詞片語 → [anaphora.Phrase],依原文順序;沒出框架的子句
        (戦闘を行う|ダメージ計算時)也找得到。片語是名詞的連續段,の、・、～、か、または、及び、や
        連著的不切開,と 只連 自分と相手。"""
        def joins(k):
            return (tokens[k] in PHRASE_JOINERS
                    or tokens[k] == "p:と" and self.word(tokens[k - 1]) == "自分")

        out = []
        for s_idx, (s_start, s_end) in enumerate(sentences):
            k = s_start
            while k < s_end:
                if not self.is_noun_like(tokens[k]):
                    k += 1
                    continue
                m = k + 1
                while m < s_end and (self.is_noun_like(tokens[m]) or (
                        joins(m) and m + 1 < s_end and self.is_noun_like(tokens[m + 1]))):
                    m += 1
                agent = activator = None
                # 発動 本身也是片語,發動者在它前一段
                if (k - 3 >= s_start and tokens[k - 3] == "p:が" and len(out) >= 2
                        and self.word(tokens[k - 2]) == "発動" and self.word(tokens[k - 1]) == "した"):
                    activator = out[-2].text
                elif k - 1 >= s_start and tokens[k - 1] == "p:が" and out and out[-1].sentence == s_idx:
                    agent = out[-1].text
                out.append(anaphora.Phrase(s_idx, k, option_of[s_idx],
                                           "".join(self.surface(t) for t in tokens[k:m]),
                                           agent, activator))
                k = m
        return out

    # ── 第二版論元(frame-args-v2 票 01〜03)──
    def _link_groups(self, tokens, anchors_by_sentence, made, marker_of):
        """か 並列(票 02):同一句裡「述語か述語(か述語)する」——錨點尾到子句尾之間只有 か
        (可帶讀點)且下一個錨點的子句就從那裡起——的成員各自仍是一個框架,全部記
        連接=或、群組=n(一句效果句內依出現順序從 1 起編)。名詞間的 か 不在錨點尾,不算;
        沒出框架的成員(被約束框架吃掉、発動 收尾)不計,剩不到兩個成員時不成群組。"""
        group_no = 0
        for s_idx, anchors in enumerate(anchors_by_sentence):
            def linked(k):
                a = anchors[k]
                return (k + 1 < len(anchors)
                        and tokens[a["end"]:a["tail"]] in (["p:か"], ["p:か", "、"])
                        and anchors[k + 1]["clause_start"] == a["tail"])

            marker = marker_of.get(s_idx)
            chains, chain, k = [], [], 0
            while k < len(anchors):
                if linked(k):
                    chain = chain or [k]
                    # か 之後的成員是那個選項的收尾述語:跳過て形/連用形的修飾鏈
                    # (戻すか召喚条件を無視して|特殊召喚する → 特殊召喚;v2-round1),
                    # 不跨過讀點(戻すか墓地へ送り、…与える 的成員是 送る)、不跨過發動句
                    # 的收尾(〜して発動できる)
                    m = k + 1
                    while m + 1 < len(anchors) and anchors[m]["form"] in ("te", "stem") \
                            and "、" not in tokens[anchors[m]["end"]:anchors[m]["tail"]] \
                            and (marker is None or m + 1 < marker):
                        m += 1
                    chain.append(m)
                    k = m
                    continue
                if chain:
                    chains.append(chain)
                    chain = []
                k += 1
            if chain:
                chains.append(chain)
            for chain in chains:
                members = [(kk, fr) for si, kk, _a, fr in made
                           if si == s_idx and kk in chain]
                # 成員得來自兩個以上的錨點(召喚・リバース 的「・」並列是一個錨點出兩個
                # 框架,不是 か 並列)
                if len({kk for kk, _fr in members}) >= 2:
                    group_no += 1
                    for _kk, fr in members:
                        fr["link"] = LINK_OR
                        fr["group"] = group_no

    @staticmethod
    def _frame_arguments(args, action, passive):
        """論元 → 框架的對象/來源與第三版可選欄(主題、主語、所在;票 02/04),被動時另帶抽取內部的
        被動標記(正規化時轉成 態=受身)。受事者(主動句是對象;被動句是主語,沒有時是主題)片語裡
        的區域切出:移動類記來源、其餘記所在,受事者欄只少掉區域那一段(整段就是區域時不動);原文
        已有 から 來源時不切。"""
        out = {"object": args.get("object"), "source": args.get("source")}
        out.update((key, args[key]) for key in ("topic", "subject") if args.get(key))
        patient = "object" if not (passive or action in INTRANSITIVE_MOVES) \
            else ("subject" if args.get("subject") else "topic")
        split = args.get("split", {}).get(patient)
        if split and not args.get("source") and out.get(patient):
            place, rest = split
            if rest is not None:
                out[patient] = rest
            out[region_key(action)] = place
        if passive:
            out["passive"] = True     # 抽取內部用;正規化時轉成 態=受身(_normalize)
        return out

    @staticmethod
    def _infer(frame):
        """推得值(票 05):對照表裡的動作,原文沒寫的 來源/目的 補上規則值,框架記 推得=被補的
        欄名;原文有字面時用原文。否定框架也補(欄位說的是這個動作的去處,極性另記)。"""
        table = INFERRED.get(frame["action"], {})
        filled = [key for key in INFERRED_FIELDS if key in table and not frame.get(key)]
        for key in filled:
            frame[key] = table[key]
        if filled:
            frame["inferred"] = filled

    def _carry_topic(self, made):
        """主題延續(frame-args-v3 票 03):子句沒有自己的主題時沿用同一句內前一個主題,框架的
        回填欄記 topic;到句號、新的主題、或一個自己帶 が/は 的條件子句為止(條件框架不接、
        延續也到此停)。屬性主題(Xの攻撃力は…)延續下去的是 X。條件子句裡主題在自己主語
        之前時(このカードは、相手モンスターが攻撃した場合、…),主題屬主句:條件框架不帶,
        從它之後接著延續。光禿禿的屬性主題(…の攻撃力・守備力は０になり、効果は無効化され、…)
        不算新的主題,補成「Xの効果」(標回填),延續中的 X 照舊往下接。主語不延續。"""
        current, cur_sentence = None, None
        for s_idx, _k, a, fr in made:
            if s_idx != cur_sentence:
                current, cur_sentence = None, s_idx
            if a.get("lifted_topic"):
                current = a["lifted_topic"]
                continue
            if fr.get("topic"):
                if current and BARE_ATTRIBUTE_TOPIC.fullmatch(fr["topic"]):
                    fr["topic"] = current + "の" + fr["topic"]
                    fr["topic_literal"] = True   # 抽取內部用:原文有主題,態照自己的主題判(_normalize)
                    self._mark_carried_topic(fr)
                    continue
                # 「Xの攻撃力は…アップし、…破壊されない」:延續下去的是屬性的主人 X
                owner = ATTRIBUTE_TOPIC.fullmatch(fr["topic"])
                current = owner.group(1) if owner else fr["topic"]
                continue
            if a["conditional"] and fr.get("subject"):
                current = None
                continue
            if current:
                fr["topic"] = current
                self._mark_carried_topic(fr)

    def _mark_carried_topic(self, fr):
        fr.setdefault("backfill", []).append("topic")
        patient_is_topic = fr.get("passive") or fr["action"] in INTRANSITIVE_MOVES
        if patient_is_topic and not fr.get("subject") and not _region(fr):
            self._cut_carried_topic(fr)

    def _cut_carried_topic(self, fr):
        """延續來的主題落在沒有主語的被動框架:主題就是受事者,區域照票 04 切出(移動類記來源、
        其餘記所在),該欄也標回填。延續值是字串,重新分詞後再切。"""
        found = self.split_place(self.tokenizer.tokenize(fr["topic"], ""))
        if not found:
            return
        place, rest = found
        if rest is not None:
            fr["topic"] = rest
        _put_region(fr, place)

    def _backfill(self, tokens, made):
        """回填(票 03):(b)選ぶ/選択 框架有對象時,它之後同一句內缺對象的述語接過它的對象,
        缺區域時也接區域——到句號、自己有對象的述語、新的主題「〜は」為止;(a)か 群組裡缺
        對象/區域的成員拿群組內第一個有該欄的成員(含它回填到的值)。從不帶對象的動作
        (NO_OBJECT_ACTIONS、〜なる)不填;不動目的;框架記 backfill=被填的欄名。
        區域轉欄(frame-args-v3 票 06):上游的區域(來源,沒有時所在;推得的不算)交給下游時,
        下游是移動類放來源、否則放所在;下游原文自己有來源或所在時不填;接到的區域蓋過下游
        推得的同欄(上游原文的字優先於規則補的字)。"""
        own_object = {id(fr): bool(fr["object"]) for _s, _k, _a, fr in made}

        def fill(fr, donor, parts=(OBJECT, REGION)):
            """parts:要接的部分——OBJECT 對象、REGION 區域(轉成來源或所在)。"""
            if OBJECT in parts and not fr.get("object") and donor.get("object"):
                fr["object"] = donor["object"]
                fr.setdefault("backfill", []).append("object")
            if REGION in parts and _region(donor) and not _region(fr):
                _put_region(fr, _region(donor))

        def fillable(fr):
            return fr["action"] not in NO_OBJECT_ACTIONS \
                and not fr["action"].endswith("なる")

        # (b) 選ぶ鏈:依原文順序掃每一句
        donor, cur_sentence = None, None
        for s_idx, _k, a, fr in made:
            if s_idx != cur_sentence:
                donor, cur_sentence = None, s_idx
            if fr["action"] in SELECT_ACTIONS and own_object[id(fr)]:
                donor = fr
                continue
            if donor is None:
                continue
            if own_object[id(fr)] or "p:は" in tokens[span_start(a):a["head"]]:
                donor = None
                continue
            if fillable(fr):
                fill(fr, donor)
        # 素材として:被當素材的卡就是緊接著被 除外/送る/戻す/リリース 的卡(一步,v3-round1)
        for (s1, _k1, a1, f1), (s2, _k2, _a2, f2) in zip(made, made[1:]):
            if (s1 == s2 and f1["action"].endswith("素材とする") and a1["form"] == "te"
                    and own_object[id(f1)] and not own_object[id(f2)]
                    and f2["action"] in MATERIAL_DESTINATIONS):
                fill(f2, f1)
        # (a) か 群組
        groups = {}
        for _s, _k, _a, fr in made:
            if fr.get("group") is not None:
                groups.setdefault(fr["group"], []).append(fr)
        for members in groups.values():
            for key, has in ((OBJECT, lambda m: m.get("object")), (REGION, _region)):
                donor = next((m for m in members if has(m)), None)
                if donor is None:
                    continue
                for m in members:
                    if m is not donor and fillable(m):
                        fill(m, donor, (key,))

    def _attach_enumeration(self, tokens, sentences, option_of, frames, text_of):
        """純列舉(票 01):效果句的 ● 項全部沒有框架時,各項原文(去 ● 與尾端句號,項目內部
        不拆)依序掛進母句裡對象含「以下の」的框架的 enumeration 欄;沒有時掛子句含詞
        「以下」的框架(主語「以下のモンスターが」、定語、主題);兩者都沒有時不掛。"""
        option_sentences = [s for s in range(len(sentences)) if option_of[s] is not None]
        if not option_sentences or any(fr["sentence"] in option_sentences
                                       for fr in frames):
            return
        items, texts = [], {}
        for s_idx in option_sentences:
            s_start, s_end = sentences[s_idx]
            if tokens[s_start] == OPTION:
                s_start += 1
            texts.setdefault(option_of[s_idx], []).append(text_of(s_start, s_end))
        for option in sorted(texts):
            item = "".join(texts[option]).strip("●\n 　、").rstrip("。").strip()
            if item:
                items.append(item)
        if not items:
            return
        mother = [fr for fr in frames if fr["sentence"] not in option_sentences]
        target = next((fr for fr in mother if fr["kind"] == KIND_ACTION
                       and "以下の" in (fr.get("object") or "")), None)
        if target is None:
            target = next((fr for fr in mother if any(
                self.word(t) == "以下" for t in tokens[fr["span"][0]:fr["span"][1]])),
                None)
        if target is not None:
            target["enumeration"] = items

    def _topic_is_this_effect(self, tokens, sentence):
        """句子以「この効果は」為主題(この効果は相手ターンでも発動できる);括弧裡的
        註記(…発動できる（この効果は相手ターンでも発動できる）)不算本句的主題。"""
        start, end = sentence
        depth = 0
        for k in range(start, end):
            t = tokens[k]
            if t == "（":
                depth += 1
            elif t == "）":
                depth = max(0, depth - 1)
            elif (depth == 0 and t.startswith("d:この:")
                  and self.word(t.split(":", 2)[2]) == "効果"
                  and k + 1 < end and tokens[k + 1] == "p:は"):
                return True
        return False

    def _inside_relative(self, tokens, start, stop):
        """start 起到下一個助詞/句讀前,出現「定語動詞+名詞」→ 前面的子句在
        名詞片語裡。"""
        for k in range(start, min(stop, start + 8) - 1):
            t = tokens[k]
            if token_kind(t) in ("particle", "punct"):
                return False
            w = self.word(t)
            if w is None:
                continue
            # 〜を素材として持っている、元々の種族が…のXモンスター:いる 後隔讀點
            # 接名詞片語也是定語(round6)
            if w in ("いる", "いた", "いない") and tokens[k + 1] == "、" \
                    and k + 2 < stop and self.is_noun_like(tokens[k + 2]):
                return True
            # 補助動詞 いる/いた 收尾也是定語(〜を素材として持っているXモンスター、
            # 〜X素材としているモンスター;round5)
            attributive = (w in SURU_FAMILY and w not in NON_ATTRIBUTIVE_SURU) \
                or (w in AUXILIARY and w not in CONDITIONAL_FORMS) \
                or (self.lex.is_verb(t) and verb_form(
                    w, self.lex.lemma_of[t]) in ("dict", "past"))
            if attributive and self.is_noun_like(tokens[k + 1]):
                return True
        return False

    def _coordinated_actions(self, tokens, a):
        """錨點前以 ・ 並列的述語名詞(召喚・|特殊召喚、特殊召喚・|リバース),
        與 または 並列的素材(融合素材または|リンク素材として)。"""
        out = []
        k = a["head"] - 1
        if a["action"].endswith("素材とする"):
            while k - 1 >= a["clause_start"] and tokens[k] in ("p:または", "・") \
                    and (self.word(tokens[k - 1]) or "").endswith("素材"):
                prefix, m = self._method_prefix(tokens, k - 2, a["clause_start"])
                out.insert(0, prefix + self.word(tokens[k - 1]) + "とする")
                k = m - 1
            return out
        while k - 1 >= a["clause_start"] and tokens[k] == "・":
            w = self.word(tokens[k - 1])
            if w == "召喚":
                prefix, m = self._method_prefix(tokens, k - 2, a["clause_start"])
                out.insert(0, prefix + "召喚")
                k = m - 1
            elif w in SAHEN_NOUNS:
                out.insert(0, w)
                k -= 2
            else:
                break
        return out

    def extract(self, text, context="", extra=None, card_type=None):
        if extra is None:
            # 沒說是不是效果外文本時看字首:編號效果(①：/●)是效果,其餘當效果外
            extra = not (text[:1] == OPTION or 0x2460 <= ord(text[:1] or " ") < 0x2500)
        return self.frames_of_tokens(self.tokenizer.tokenize(text, context),
                                     text=text, extra=extra, card_type=card_type)


def _normalize(frame):
    """動作框架過詞元對照表(action_lemmas.normalize):原詞元 → 動作詞元,態記在 voice(只在有值時
    帶);抽取內部的被動標記併入 態=受身。アップ/ダウン 的態只看框架自己的原文——回填的對象、延續來的
    主題/主語不算(延續來的主題多半是執行者「自分は…」);光禿禿的屬性主題補了主人的(攻撃力は →
    Xの攻撃力)原文有主題,照自己的算。目的併入詞元的(攻撃対象に選択)先併。"""
    frame["action"], frame["goal"] = action_lemmas.fold_goal(frame["action"], frame["goal"])
    backfilled = frame.get("backfill") or ()
    topic_literal = frame.pop("topic_literal", False)
    own = {key: bool(frame.get(key)) and (key not in backfilled or (key == "topic" and topic_literal))
           for key in ("object", "subject", "topic")}
    frame["action"], voice = action_lemmas.normalize(
        frame["action"], passive=frame.pop("passive", False), has_object=own["object"],
        has_subject=own["subject"] or own["topic"])
    if voice:
        frame["voice"] = voice


def _each_method(action):
    """召喚法鏈(融合・S・X・リンク召喚)→ 各法的召喚;素材的法鏈(融合・S・X素材にする,票 02)→
    各法的素材詞元;一法一框。其餘動作原樣。"""
    chain = _METHOD_CHAIN.fullmatch(action) if "・" in action else None
    if chain is None:
        return [action]
    return [method + chain.group(2) for method in chain.group(1).split("・")]


def _literal(frame, key):
    """論元欄的原文值(含切分與回填);推得的格(票 05)當作沒寫。"""
    return None if key in (frame.get("inferred") or ()) else frame.get(key)


def region_key(action):
    """受事者的區域放哪一欄:移動類記來源、其餘記所在(票 04)。"""
    return "source" if action in MOVE_ACTIONS else "place"


def span_start(anchor):
    """錨點的子句字面起點:〜よう 子句併入時是併入段的起點(票 09),否則就是子句起點。"""
    return anchor.get("span_start", anchor["clause_start"])


def _region(frame):
    """框架的區域:來源(推得的不算),沒有時所在。"""
    return _literal(frame, "source") or frame.get("place")


def _put_region(frame, place):
    """把規則接過來的區域放進框架(回填):依動作放來源或所在、標回填,蓋過推得的同欄。"""
    key = region_key(frame["action"])
    frame[key] = place
    frame.setdefault("backfill", []).append(key)
    if key in (frame.get("inferred") or ()):
        frame["inferred"].remove(key)
        if not frame["inferred"]:
            del frame["inferred"]


_DEFAULT = None


def default_extractor():
    global _DEFAULT
    if _DEFAULT is None:
        with open(LEXICON, encoding="utf-8") as f:
            _DEFAULT = FrameExtractor(json.load(f))
    return _DEFAULT


def extract(text, context="", extra=None, card_type=None):
    """接縫:一句效果句原文(整段,含 ● 選項;帶同卡同段上文;可選 效果外文本 旗標與
    卡片子類型)→ 框架清單(動作框架與約束框架混排)。"""
    return default_extractor().extract(text, context, extra, card_type)


def main():
    extractor = default_extractor()
    with open(TOKENS, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(CARDS, encoding="utf-8") as f:
        card_type = {c["id"]: card_type_of(c["type"]) for c in json.load(f)}
    out = []
    for s in sentences:
        # 效果外文本看效果類型(含子效果句的領起句雖算效果層,仍是效果外文本的句型);
        # 卡片子類型從卡片總表帶入(素材框架的召喚法)
        frames = extractor.frames_of_tokens(
            s["tokens"], text=s["text_ja"], extra=s["kind"] == "效果外文本",
            card_type=card_type.get(s["card"]))
        for k, fr in enumerate(frames):
            fr["order"] = k
        out.append({"card": s["card"], "section": s["section"],
                    "index": s["index"], "stratum": s["stratum"],
                    "parts": s["parts"], "frames": frames})
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
        f.write("\n")
    stats, _position, _polarity, _actions, constraints = frame_stats(out)
    for key in ("effect", "extra"):
        st = stats[key]
        print("%s: 有框架的句 %d / %d(%.2f%%);動作框架 %d、約束框架 %d" % (
            key, st["covered"], st["records"],
            100.0 * st["covered"] / max(1, st["records"]),
            st["frames"] - st["constraints"], st["constraints"]))
    print("約束框架分佈:" + "、".join(
        "%s %d" % (k, v) for k, v in sorted(constraints.items())))
    print("框架總數 %d;已寫出 %s" % (
        sum(st["frames"] for st in stats.values()), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
