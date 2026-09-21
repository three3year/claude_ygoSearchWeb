"""值域正典:cdb 位元/整數/中文 → 短碼 → 中文 + 宣告序的單一來源。

住在建置期(ADR-0008)。產出兩樣東西:建置時把卡片解成短碼寫進前端索引,同時把
值域與中文表輸出成 `window.VOCAB`——HTML 不寫死任何選項,搜尋介面的按鈕由 VOCAB
生成。同一份宣告序同時是領域序排序的比較序,所以第三抄(排序表)不存在。

擋的是一種無聲失效:**值域漏一個碼,某批卡就從搜尋結果消失**,不報錯、不白屏。
因此有兩道相反方向的檢查:

- `problems()`——正典這份資料自己合不合法(重複短碼、缺中文、位元重疊、分組空洞)。
  這是接縫 2:`build_index` 吃的永遠是 repo 裡這一份,測不到「換一份壞的進來會
  怎樣」,所以正典自成一個接縫(理由與 tag_card 把 `rules` 自檢獨立出來同構)。
- `webindex` 那一側——索引出現正典沒有的值、或 cdb 的位元沒有被正典解釋,即建置
  失敗。**沒被登記的位元不是被忽略而是讓建置倒**:`type` 的 0x100(罠モンスター
  位元)與 0x8000(Rush)現在 0 張,哪天冒出來要吵不要靜。

不登記「沒有值」:屬性 0、種族 0、MD 未實裝這三種都是「卡片沒有這個參數」,由
索引省略欄位表示,不是值域的成員(見 ADR-0008 對 card-list 票07 的分界)。
"""
import hashlib
import json

# 來源側的形態。同一個值域只有一種形態,decode 因此不必猜。
SRC_BITMASK = "bitmask"  # cdb `type` 的位元集合(大類、卡片子類型、連結標記)
SRC_BIT = "bit"          # 單一位元值:欄位的值必須恰好等於某個成員(屬性、種族)
SRC_INT = "int"          # 整數值(ot)
SRC_TEXT = "text"        # 來源就是中文本身(效果類型、必發/選發、role、MD 稀有度)

CAT = "cat"
SUB = {"m": "sub_m", "s": "sub_s", "t": "sub_t"}
ATTR = "attr"
RACE = "race"
KIND = "kind"
OPTIONAL = "optional"
ROLE = "role"
LINK_MARKER = "lm"
RARITY = "rarity"
OT = "ot"
BAN_O = "ban_o"
BAN_T = "ban_t"
BAN_M = "ban_m"
TAG = "tag"
TIMING = "timing"


def entry(code, zh, src=None, filterable=True):
    """一個值域成員。src 為 None 時代表「來源側沒有這個值」:

    - SRC_TEXT 的成員預設 src 就是中文本身(效果類型等的來源值即中文)。
    - `fallback` 成員(魔法/陷阱的「通常」)沒有位元,由「其他位元都沒中」判定。

    filterable=False 的成員登記在正典裡但不做成按鈕([[衍生物]]:卡片總表本來
    就不收錄,登記它是為了位元解釋得動,而不是給使用者一顆永遠 0 筆的鈕)。
    """
    return {"code": code, "zh": zh, "src": src, "filter": filterable}


def domain(zh, src_kind, entries, groups=(), fallback=None, carriers=(),
           own=(), combos=()):
    """一個值域。entries 的順序就是宣告序:按鈕順序與排序比較序共用它。

    groups 是按鈕分組((組名, 成員碼...)),分組必須恰好蓋過全部可篩選成員——
    漏一個成員就是漏一顆按鈕,而那與漏一個碼的失效模式一模一樣(ADR-0008)。

    carriers 是「這個值域的值只出現在 [[效果類型]]的哪些成員上」(目前只有
    [[必發/選發]]有這種關係)。宣告在正典而不是在前端,理由與其他值域一樣:
    抄第二份就會漂移,而漂移的形狀是一組條件安靜地不出現。

    own 是「這個值域的值 → 本類的 (大類碼, 子類型碼)」((值碼, 大類碼, 子類型碼)
    的序列,ADR-0010,目前只有[[效果類型]]的魔陷十值有)。搜尋介面的跨類型排除與
    建置期的空值判定都照它走,同一條「不抄第二份」的理由。

    combos 是**組合條件**((組合碼, 效果類型碼, 值碼, 中文) 的序列,目前只有
    [[必發/選發]]的怪獸側四顆有,spec-optional-combo):一顆按鈕 = 「同一
    [[效果句]]是該效果類型**且**帶該值」。組合不是第三種值——值域的值仍只有
    entries 那幾個,組合是**條件的形狀**,所以另立宣告而不混進 entries
    (混進去的話 code_of 會把標記表裡不存在的來源值解出碼來)。
    """
    if src_kind == SRC_TEXT:
        entries = tuple(
            e if e["src"] is not None else dict(e, src=e["zh"])
            for e in entries)
    return {"zh": zh, "src_kind": src_kind, "entries": tuple(entries),
            "groups": tuple(groups), "fallback": fallback,
            "carriers": tuple(carriers), "own": tuple(own),
            "combos": tuple(combos)}


# ── 卡片種類大類 ─────────────────────────────────────────────
# 怪獸不細分(細分歸[[卡片子類型]],兩套值域不可互用,見 CONTEXT.md)。
_CAT = domain("大類", SRC_BITMASK, (
    entry("m", "怪獸", 0x1),
    entry("s", "魔法", 0x2),
    entry("t", "陷阱", 0x4),
))

# ── 卡片子類型 ───────────────────────────────────────────────
# 一側一個值域:短碼在同一側內唯一,跨側的「通常」「永續」「儀式」名稱相同但屬於
# 不同值域,由卡片的大類決定讀哪一份。合成一個值域的話,cdb 位元 0x80(儀式)會
# 同時對到怪獸側與魔法側兩個成員,位元重疊檢查就得為此開例外。
# 魔法/陷阱的「通常」在 cdb 裡沒有位元(通常魔法 type 就只有 0x2),由 fallback
# 表示「其他子類型位元都沒中」。
# 中文名以**繁中卡文的用詞**為準(同步/協調/聯合,不是同調/調整/同盟):使用者在
# 同一個畫面上讀卡文也讀按鈕,兩邊用不同的詞指同一件事會看起來像兩件事。
_SUB_M = domain("怪獸子類型", SRC_BITMASK, (
    entry("normal", "通常", 0x10),
    entry("effect", "效果", 0x20),
    entry("fusion", "融合", 0x40),
    entry("ritual", "儀式", 0x80),
    entry("synchro", "同步", 0x2000),
    entry("xyz", "超量", 0x800000),
    entry("pendulum", "靈擺", 0x1000000),
    entry("link", "連結", 0x4000000),
    entry("tuner", "協調", 0x1000),
    entry("flip", "反轉", 0x200000),
    entry("spsummon", "特殊召喚", 0x2000000),
    entry("dual", "二重", 0x800),
    entry("spirit", "靈魂", 0x200),
    entry("union", "聯合", 0x400),
    entry("toon", "卡通", 0x400000),
    # [[衍生物]]:卡片總表不收錄(0 張),登記位元但不做按鈕
    entry("token", "衍生物", 0x4000, filterable=False),
), groups=(
    ("卡框", ("normal", "effect", "fusion", "ritual", "synchro", "xyz",
              "pendulum", "link")),
    ("能力", ("tuner", "flip", "spsummon", "dual", "spirit", "union",
              "toon")),
))
_SUB_S = domain("魔法子類型", SRC_BITMASK, (
    entry("normal", "通常"),
    entry("quick", "速攻", 0x10000),
    entry("continuous", "永續", 0x20000),
    entry("equip", "裝備", 0x40000),
    entry("field", "場地", 0x80000),
    entry("ritual", "儀式", 0x80),
), fallback="normal")
_SUB_T = domain("陷阱子類型", SRC_BITMASK, (
    entry("normal", "通常"),
    entry("continuous", "永續", 0x20000),
    entry("counter", "反擊", 0x100000),
), fallback="normal")

# ── 屬性與種族 ───────────────────────────────────────────────
# 宣告序取 cdb 位元序:它與位元宣告逐一對照得上,不需要第二份人工排的順序。
_ATTR = domain("屬性", SRC_BIT, (
    entry("earth", "地", 0x1),
    entry("water", "水", 0x2),
    entry("fire", "炎", 0x4),
    entry("wind", "風", 0x8),
    entry("light", "光", 0x10),
    entry("dark", "闇", 0x20),
    entry("divine", "神", 0x40),
))
_RACE = domain("種族", SRC_BIT, (
    entry("warrior", "戰士族", 0x1),
    entry("spellcaster", "魔法使族", 0x2),
    entry("fairy", "天使族", 0x4),
    entry("fiend", "惡魔族", 0x8),
    entry("zombie", "不死族", 0x10),
    entry("machine", "機械族", 0x20),
    entry("aqua", "水族", 0x40),
    entry("pyro", "炎族", 0x80),
    entry("rock", "岩石族", 0x100),
    entry("winged_beast", "鳥獸族", 0x200),
    entry("plant", "植物族", 0x400),
    entry("insect", "昆蟲族", 0x800),
    entry("thunder", "雷族", 0x1000),
    entry("dragon", "龍族", 0x2000),
    entry("beast", "獸族", 0x4000),
    entry("beast_warrior", "獸戰士族", 0x8000),
    entry("dinosaur", "恐龍族", 0x10000),
    entry("fish", "魚族", 0x20000),
    entry("sea_serpent", "海龍族", 0x40000),
    entry("reptile", "爬蟲類族", 0x80000),
    entry("psychic", "超能族", 0x100000),
    entry("divine_beast", "幻神獸族", 0x200000),
    entry("creator_god", "創造神族", 0x400000),
    entry("wyrm", "幻龍族", 0x800000),
    entry("cyberse", "電子界族", 0x1000000),
    entry("illusion", "幻想魔族", 0x2000000),
))

# ── 效果句層級的值域 ─────────────────────────────────────────
# 效果類型十六值:怪獸側六類 + [[魔陷卡效果]]十值(CONTEXT.md、ADR-0004/0005)。
# 兩組是兩個維度的東西,按鈕排在一起時要分得出來(Story 23),所以分組。
_KIND = domain("效果類型", SRC_TEXT, (
    entry("x", "效果外文本"),
    entry("u", "無種類效果"),
    entry("c", "永續效果"),
    entry("q", "誘發即時效果(2速)"),
    entry("t", "誘發效果(1速)"),
    entry("i", "啟動效果"),
    entry("sn", "通常魔法卡效果"),
    entry("sq", "速攻魔法卡效果"),
    entry("sr", "儀式魔法卡效果"),
    entry("sc", "永續魔法卡效果"),
    entry("se", "裝備魔法卡效果"),
    entry("sf", "場地魔法卡效果"),
    entry("sp", "靈擺魔法卡效果"),
    entry("tn", "通常陷阱卡效果"),
    entry("tc", "永續陷阱卡效果"),
    entry("tk", "反擊陷阱卡效果"),
), groups=(
    ("怪獸側", ("x", "u", "c", "q", "t", "i")),
    # 群組標題是「跨類型」:這十顆鈕只收自身[[卡片種類]]與值不一致的卡(ADR-0010)
    ("跨類型魔陷效果", ("sn", "sq", "sr", "sc", "se", "sf", "sp", "tn", "tc",
                        "tk")),
), own=(
    # 魔陷十值的本類對應:自身卡片種類與值一致(本類)的卡不進該值按鈕的成員——
    # 裝備魔法卡自己的裝備魔法卡效果是卡片種類的重言,「所有裝備魔法卡」歸
    # [[卡片子類型]]軸。前九值對同名子類型;靈擺魔法卡效果的本類是**靈擺怪獸**
    # (照字面比對的話那顆鈕會變回「全部靈擺怪獸」,ADR-0010)。
    ("sn", "s", "normal"),
    ("sq", "s", "quick"),
    ("sr", "s", "ritual"),
    ("sc", "s", "continuous"),
    ("se", "s", "equip"),
    ("sf", "s", "field"),
    ("sp", "m", "pendulum"),
    ("tn", "t", "normal"),
    ("tc", "t", "continuous"),
    ("tk", "t", "counter"),
))
# [[必發/選發]]只長在**有觸發事件的發動句**上:誘發即時效果(2速)、誘發效果(1速)
# 與[[魔陷卡效果]]十值。啟動效果與魔陷卡本身的發動本就由玩家主動選擇開啟(不記值),
# 永續效果、無種類效果、效果外文本則根本不發動(CONTEXT.md「必發/選發」)。
# 這條關係兩個方向都有人用:搜尋介面照它決定「必發/選發」那一組條件出不出得來
# (Story 25——「永續效果是必發」是一個永遠零結果的條件,不該設得出來),建置期
# 照它擋下標記表把值貼到不承載的類型上。抄在前端一份的話,某天多一個承載型的
# 效果類型時那一組會安靜地不出現——與漏一個碼同一個失效模式(ADR-0008)。
# 搜尋介面上這個屬性是同一軸的兩組條件(spec-optional-combo):「全部」組是
# 值本身的兩顆,「怪獸側」組是效果類型×值的四顆組合鈕——必發/選發的使用情境
# 大多落在怪獸效果上(必發 1,830 卡裡 1,481 卡是怪獸側),「怪獸的必發效果」
# 該是一顆鈕而不是跨兩軸三顆。魔陷側不設組合:軸內排除優先本來就表達得出來
# (全部必發包含+怪獸側兩顆必發排除)。組合的鈕面省略「效果」與速度標注,
# 與效果類型軸的全名「誘發即時效果(2速)」對得起來又不佔滿一列。
_OPTIONAL = domain("必發/選發", SRC_TEXT, (
    entry("m", "必發"),
    entry("o", "選發"),
), groups=(
    ("全部", ("m", "o")),
    ("怪獸側", ("qm", "qo", "tm", "to")),
), carriers=("q", "t", "sn", "sq", "sr", "sc", "se", "sf", "sp", "tn", "tc",
             "tk"), combos=(
    ("qm", "q", "m", "誘發即時(必發)"),
    ("qo", "q", "o", "誘發即時(選發)"),
    ("tm", "t", "m", "誘發(必發)"),
    ("to", "t", "o", "誘發(選發)"),
))
_ROLE = domain("效果外文本種別", SRC_TEXT, (
    entry("mat", "素材指定"),
    entry("cond", "召喚條件"),
    entry("limit", "使用次數限制"),
))

# ── 效果 Tag:動作類別與槽位(2026-09-20 體系凍結,.scratch/effect-tag/rulings.md)──
# 動作類別 21 值。值住在效果句的 tags 陣列(`cat` 欄),來源值即中文(SRC_TEXT)。
# 分組是側欄按鈕的排列;凍結後追加類別需新裁定票(LP支付/LP失去即 2026-09-21
# 站主覆核裁定票15 增補——支付/失去/傷害三分)。
_TAG = domain("動作類別", SRC_TEXT, (
    entry("mv", "區域移動"),
    entry("dw", "抽牌/手牌交換"),
    entry("ng", "無效"),
    entry("ds", "破壞"),
    entry("rs", "行動限制"),
    entry("pt", "耐性/保護"),
    entry("st", "攻守調整"),
    entry("dm", "效果傷害"),
    entry("hp", "生命回復"),
    entry("lpp", "LP支付"),
    entry("lpl", "LP失去"),
    entry("ps", "表示形式變更"),
    entry("ct", "控制權轉移"),
    entry("pp", "性質變更"),
    entry("cnt", "計數器操作"),
    entry("tf", "放置轉換"),
    entry("su", "素材代用/召喚放寬"),
    entry("se", "召喚執行"),
    entry("bt", "戰鬥規則"),
    entry("in", "情報操作"),
    entry("misc", "其他"),
), groups=(
    ("移動與資源", ("mv", "dw")),
    ("妨害", ("ng", "ds", "rs", "pt")),
    ("數值與狀態", ("st", "dm", "hp", "lpp", "lpl", "ps", "ct", "pp", "cnt")),
    ("轉換與召喚", ("tf", "su", "se")),
    ("其他", ("bt", "in", "misc")),
))

# 槽位值域(逐類宣告於 TAG_SLOTS)。這些值域不是卡片欄位,不進 CODED_FIELDS 那張
# 表;索引側對 tags 的驗證走 webindex 的 tag 專屬檢查,失效模式與卡片欄位相同
# (正典外值即建置失敗)。
_TAG_ZONE = domain("區域", SRC_TEXT, (
    entry("h", "手牌"),
    entry("d", "牌組"),
    entry("e", "額外牌組"),
    entry("g", "墓地"),
    entry("b", "除外"),
    entry("f", "場上"),
    entry("p", "靈擺區"),
))
_TAG_SIDE = domain("對象方", SRC_TEXT, (
    entry("s", "自身"),
    entry("m", "我方"),
    entry("o", "對手"),
    entry("w", "雙方"),
))
_TAG_POS = domain("位置", SRC_TEXT, (
    entry("c", "成本"),
    entry("e", "效果"),
))
_TAG_CARRY = domain("抽牌附帶", SRC_TEXT, (
    entry("dc", "捨棄"),
    entry("db", "回牌組"),
))
_TAG_STAT_ITEM = domain("攻守項目", SRC_TEXT, (
    entry("a", "攻擊"),
    entry("d", "守備"),
    entry("ad", "攻守"),
))
_TAG_STAT_DIR = domain("攻守方向", SRC_TEXT, (
    entry("up", "上升"),
    entry("dn", "下降"),
    entry("bc", "變成"),
))
_TAG_FORM = domain("數值型態", SRC_TEXT, (
    entry("fx", "固定值"),
    entry("rf", "參照值"),
    entry("rt", "比例"),
))
_TAG_NG_WHAT = domain("無效對象", SRC_TEXT, (
    entry("ac", "發動"),
    entry("ef", "效果"),
    entry("cn", "持續無效化"),
))
_TAG_NG_EXTRA = domain("無效附帶", SRC_TEXT, (
    entry("ds", "破壞"),
    entry("bn", "除外"),
))
_TAG_DS_WHAT = domain("破壞對象", SRC_TEXT, (
    entry("mo", "怪獸"),
    entry("st", "魔陷"),
    entry("cd", "卡"),
))
_TAG_SCOPE = domain("範圍", SRC_TEXT, (
    entry("one", "單體"),
    entry("mult", "複數"),
    entry("all", "全體"),
))
_TAG_RS_WHAT = domain("限制內容", SRC_TEXT, (
    entry("sp", "特殊召喚"),
    entry("ac", "發動效果"),
    entry("at", "攻擊"),
    entry("ps", "表示形式"),
    entry("x", "其他"),
))
_TAG_TERM = domain("期間型態", SRC_TEXT, (
    entry("ct", "持續"),
    entry("tn", "單回合"),
))
_TAG_PT_WHAT = domain("耐性內容", SRC_TEXT, (
    entry("bd", "戰鬥破壞"),
    entry("ed", "效果破壞"),
    entry("tg", "效果對象"),
    entry("bn", "除外"),
    entry("ae", "全效果"),
    entry("rp", "代替破壞"),
))
_TAG_PS_TO = domain("變更為", SRC_TEXT, (
    entry("a", "攻擊表示"),
    entry("d", "守備表示"),
    entry("fd", "裡側表示"),
))
_TAG_CT_DIR = domain("控制權方向", SRC_TEXT, (
    entry("get", "取得"),
    entry("give", "移交"),
))
_TAG_PP_ITEM = domain("性質項目", SRC_TEXT, (
    entry("nm", "卡名"),
    entry("rc", "種族"),
    entry("at", "屬性"),
    entry("lv", "等級"),
    entry("rk", "階級"),
    entry("sc", "刻度"),
))
_TAG_CNT_ACT = domain("計數器動作", SRC_TEXT, (
    entry("put", "放置"),
    entry("rm", "去除"),
))
_TAG_TF_TO = domain("轉換為", SRC_TEXT, (
    entry("eq", "裝備卡"),
    entry("cs", "永續魔法"),
    entry("ctp", "永續陷阱"),
    entry("set", "魔陷覆蓋"),
))
_TAG_SE_METHOD = domain("召喚法", SRC_TEXT, (
    entry("rit", "儀式"),
    entry("fus", "融合"),
    entry("syn", "同步"),
    entry("xyz", "超量"),
    entry("lnk", "連結"),
))
_TAG_BT_WHAT = domain("戰鬥規則內容", SRC_TEXT, (
    entry("pi", "貫通"),
    entry("ma", "連續攻擊"),
    entry("da", "直接攻擊"),
    entry("ta", "攻擊對象操作"),
))
_TAG_IN_WHAT = domain("情報操作內容", SRC_TEXT, (
    entry("pk", "確認"),
    entry("rv", "展示"),
    entry("rd", "隨機決定"),
))

# 各類別的槽位宣告:(槽位鍵, 槽位值域名) 的序列,順序即索引短碼的欄位序。
# 「位置」是通用槽位(裁定批1),每一類都有;凍結後增刪槽位需新裁定票。
# 例外(裁定票15):LP支付不設「位置」——支付本身就是代價,位置軸對它無意義,
# 搜尋一律命中(前端從 slots 缺 pos 這件事自己看出來,不另立旗標)。
TAG_POS_EXEMPT = frozenset({"lpp"})
TAG_SLOTS = {
    "mv": (("from", "tag_zone"), ("to", "tag_zone"), ("side", "tag_side"),
           ("pos", "tag_pos")),
    "dw": (("side", "tag_side"), ("extra", "tag_carry"), ("pos", "tag_pos")),
    "ng": (("what", "tag_ng_what"), ("extra", "tag_ng_extra"),
           ("pos", "tag_pos")),
    "ds": (("what", "tag_ds_what"), ("scope", "tag_scope"),
           ("side", "tag_side"), ("pos", "tag_pos")),
    "rs": (("what", "tag_rs_what"), ("side", "tag_side"),
           ("term", "tag_term"), ("pos", "tag_pos")),
    "pt": (("what", "tag_pt_what"), ("side", "tag_side"), ("pos", "tag_pos")),
    "st": (("item", "tag_stat_item"), ("dir", "tag_stat_dir"),
           ("pos", "tag_pos")),
    "dm": (("side", "tag_side"), ("form", "tag_form"), ("pos", "tag_pos")),
    "hp": (("side", "tag_side"), ("form", "tag_form"), ("pos", "tag_pos")),
    "lpp": (("side", "tag_side"), ("form", "tag_form")),
    "lpl": (("side", "tag_side"), ("form", "tag_form"), ("pos", "tag_pos")),
    "ps": (("to", "tag_ps_to"), ("side", "tag_side"), ("pos", "tag_pos")),
    "ct": (("dir", "tag_ct_dir"), ("pos", "tag_pos")),
    "pp": (("item", "tag_pp_item"), ("term", "tag_term"), ("pos", "tag_pos")),
    "cnt": (("act", "tag_cnt_act"), ("pos", "tag_pos")),
    "tf": (("to", "tag_tf_to"), ("pos", "tag_pos")),
    "su": (("pos", "tag_pos"),),
    "se": (("method", "tag_se_method"), ("pos", "tag_pos")),
    "bt": (("what", "tag_bt_what"), ("pos", "tag_pos")),
    "in": (("what", "tag_in_what"), ("pos", "tag_pos")),
    "misc": (("pos", "tag_pos"),),
}

# 觸發時機:句層單值軸,只長在誘發系承載類型上(裁定批4:carriers 與必發/選發
# 完全同一組,理由同 ADR-0004——有觸發事件的發動句才有時機可言)。
_TIMING = domain("觸發時機", SRC_TEXT, (
    entry("ns", "召喚成功時"),
    entry("sp", "特殊召喚成功時"),
    entry("fp", "反轉時"),
    entry("dd", "被破壞時"),
    entry("gy", "被送去墓地時"),
    entry("lv", "從場上離開時"),
    entry("bn", "被除外時"),
    entry("ad", "攻擊宣言時"),
    entry("dst", "傷害步驟時點"),
    entry("bd", "給予戰鬥傷害時"),
    entry("td", "受到傷害時"),
    entry("sb", "準備階段"),
    entry("mp", "主要階段"),
    entry("bp", "戰鬥階段"),
    entry("ep", "結束階段"),
    entry("oa", "對手發動效果時"),
    entry("x", "其他"),
), carriers=("q", "t", "sn", "sq", "sr", "sc", "se", "sf", "sp", "tn", "tc",
             "tk"))

# ── 其餘卡面欄位 ─────────────────────────────────────────────
# 連結標記:宣告序＝九宮格的讀法(左上到右下),呈現層直接照序擺格子。
_LINK_MARKER = domain("連結標記", SRC_BITMASK, (
    entry("TL", "↖", 0x40),
    entry("T", "↑", 0x80),
    entry("TR", "↗", 0x100),
    entry("L", "←", 0x8),
    entry("R", "→", 0x20),
    entry("BL", "↙", 0x1),
    entry("B", "↓", 0x2),
    entry("BR", "↘", 0x4),
))
# MD 未實裝的 416 張不是值域成員,是「沒有這個欄位」(同屬性 0、種族 0)
_RARITY = domain("MD 稀有度", SRC_TEXT, (
    entry("N", "N"),
    entry("R", "R"),
    entry("SR", "SR"),
    entry("UR", "UR"),
))
_OT = domain("OCG・TCG", SRC_INT, (
    entry("o", "OCG 限定", 1),
    entry("t", "TCG 限定", 2),
    entry("b", "兩者", 3),
))
# [[禁限狀態]]:三賽制統一三值(2026-08-22 使用者裁示;MD 的 Limited 1/2 在
# 建置端先正規化成限制/準限制)。未上榜的已發行卡是「沒有這個欄位」——
# 「無限制」「未發行」不是值域成員,由呈現層以 ot / MD 稀有度推導(spec banlist)。
_BAN_O = domain("OCG 禁限", SRC_TEXT, (
    entry("f", "禁止"),
    entry("l", "限制"),
    entry("s", "準限制"),
))
_BAN_T = domain("TCG 禁限", SRC_TEXT, (
    entry("f", "禁止"),
    entry("l", "限制"),
    entry("s", "準限制"),
))
# MD 的來源字面(Limited 1/2)在建置端已正規化,進值域的與 OCG/TCG 同一套
_BAN_M = domain("MD 禁限", SRC_TEXT, (
    entry("f", "禁止"),
    entry("l", "限制"),
    entry("s", "準限制"),
))

DOMAINS = {
    CAT: _CAT,
    "sub_m": _SUB_M, "sub_s": _SUB_S, "sub_t": _SUB_T,
    ATTR: _ATTR, RACE: _RACE,
    KIND: _KIND, OPTIONAL: _OPTIONAL, ROLE: _ROLE,
    LINK_MARKER: _LINK_MARKER, RARITY: _RARITY, OT: _OT,
    BAN_O: _BAN_O, BAN_T: _BAN_T, BAN_M: _BAN_M,
    TAG: _TAG, TIMING: _TIMING,
    "tag_zone": _TAG_ZONE, "tag_side": _TAG_SIDE, "tag_pos": _TAG_POS,
    "tag_carry": _TAG_CARRY, "tag_stat_item": _TAG_STAT_ITEM,
    "tag_stat_dir": _TAG_STAT_DIR, "tag_form": _TAG_FORM,
    "tag_ng_what": _TAG_NG_WHAT, "tag_ng_extra": _TAG_NG_EXTRA,
    "tag_ds_what": _TAG_DS_WHAT, "tag_scope": _TAG_SCOPE,
    "tag_rs_what": _TAG_RS_WHAT, "tag_term": _TAG_TERM,
    "tag_pt_what": _TAG_PT_WHAT, "tag_ps_to": _TAG_PS_TO,
    "tag_ct_dir": _TAG_CT_DIR, "tag_pp_item": _TAG_PP_ITEM,
    "tag_cnt_act": _TAG_CNT_ACT, "tag_tf_to": _TAG_TF_TO,
    "tag_se_method": _TAG_SE_METHOD, "tag_bt_what": _TAG_BT_WHAT,
    "tag_in_what": _TAG_IN_WHAT,
}

# 各值域的成員數。與 CONTEXT.md / spec 記的值域規模對帳用:少一個成員代表某批卡
# 的按鈕不見了,多一個代表有人加了值域卻沒改文件。子類型合計 25(怪獸側 15 +
# [[衍生物]] + 魔法側 6 + 陷阱側 3)。
EXPECTED_SIZES = {
    CAT: 3, "sub_m": 16, "sub_s": 6, "sub_t": 3,
    ATTR: 7, RACE: 26,
    KIND: 16, OPTIONAL: 2, ROLE: 3,
    LINK_MARKER: 8, RARITY: 4, OT: 3,
    BAN_O: 3, BAN_T: 3, BAN_M: 3,
    TAG: 21, TIMING: 17,
    "tag_zone": 7, "tag_side": 4, "tag_pos": 2, "tag_carry": 2,
    "tag_stat_item": 3, "tag_stat_dir": 3, "tag_form": 3,
    "tag_ng_what": 3, "tag_ng_extra": 2, "tag_ds_what": 3, "tag_scope": 3,
    "tag_rs_what": 5, "tag_term": 2, "tag_pt_what": 6, "tag_ps_to": 3,
    "tag_ct_dir": 2, "tag_pp_item": 6, "tag_cnt_act": 2, "tag_tf_to": 4,
    "tag_se_method": 5, "tag_bt_what": 4, "tag_in_what": 3,
}

# cdb `type` 的位元由大類與三個子類型值域共同解釋;沒有被解釋的位元會讓建置倒
# (見模組 docstring)。
TYPE_DOMAINS = (CAT, "sub_m", "sub_s", "sub_t")


def entries(name, domains=None):
    return (domains or DOMAINS)[name]["entries"]


def codes(name, domains=None):
    return tuple(e["code"] for e in entries(name, domains))


def carriers(name, domains=None):
    """承載這個值域的[[效果類型]]短碼(沒有這種關係的值域是空的)。"""
    return (domains or DOMAINS)[name]["carriers"]


def own_types(domains=None):
    """[[魔陷卡效果]]值 → 本類的 (大類碼, 子類型碼)(ADR-0010)。"""
    return {code: (cat, sub)
            for code, cat, sub in (domains or DOMAINS)[KIND]["own"]}


def zh(name, code, domains=None):
    for e in entries(name, domains):
        if e["code"] == code:
            return e["zh"]
    return None


def code_of(name, value, domains=None):
    """單值值域的來源值 → 短碼(屬性、種族的位元;ot 的整數;效果類型的中文)。

    0 與空字串代表「卡片沒有這個參數」,回傳 None、由呼叫端省略欄位。對不到任何
    成員的值(例如屬性寫成 3、效果類型是個沒登記的詞)同樣回傳 None,呼叫端會把
    它當未知值報上去——兩者的差別在呼叫端知道來源值是不是空的。
    """
    if not value:
        return None
    for e in entries(name, domains):
        if e["src"] == value:
            return e["code"]
    return None


def bitmask_codes(name, value, domains=None):
    """位元集合 → 短碼陣列(宣告序)。fallback 成員在其餘位元全沒中時補上。"""
    dom = (domains or DOMAINS)[name]
    hit = [e["code"] for e in dom["entries"]
           if e["src"] is not None and value & e["src"]]
    if not hit and dom["fallback"]:
        return (dom["fallback"],)
    return tuple(hit)


def unexplained_type_bits(value, domains=None):
    """`type` 裡沒有被任何值域解釋的位元。非空即代表正典漏了一個碼。"""
    known = 0
    for name in TYPE_DOMAINS:
        for e in entries(name, domains):
            if e["src"] is not None:
                known |= e["src"]
    return value & ~known


def subtypes(type_value, domains=None):
    """cdb `type` → (大類碼, 子類型碼陣列)。大類對不出來時回傳 (None, ())。"""
    cats = bitmask_codes(CAT, type_value, domains)
    if len(cats) != 1:
        return None, ()
    cat = cats[0]
    return cat, bitmask_codes(SUB[cat], type_value, domains)


def problems(domains=None, tag_slots=None):
    """正典自檢:回傳問題字串清單(空 = 合法)。

    測的是**正典這份資料本身**合不合法,不是管線的中間產物。十種:成員數與
    EXPECTED_SIZES 不符、短碼重複、缺短碼或缺中文、同值域內中文重複(按鈕會有
    兩顆長一樣的)、來源值重複或位元重疊(解碼時對到兩個成員)、fallback 指向
    不存在的成員、分組沒有恰好蓋過全部可篩選成員(宣告序有空洞)、分組列了
    不存在的成員、承載者不是效果類型的成員、本類對應解不動(ADR-0010)、
    組合條件解不動(spec-optional-combo)。外加槽位宣告的四種
    (`_tag_slot_problems`,效果 Tag 線)。
    """
    domains = domains or DOMAINS
    found = list(_tag_slot_problems(domains,
                                    TAG_SLOTS if tag_slots is None
                                    else tag_slots))
    for name in sorted(set(domains) | set(EXPECTED_SIZES)):
        dom = domains.get(name)
        if dom is None:
            found.append(f"{name}: 值域不存在")
            continue
        expected = EXPECTED_SIZES.get(name)
        if expected is not None and len(dom["entries"]) != expected:
            found.append(
                f"{name}: 成員數 {len(dom['entries'])} 與預期 {expected} 不符")
        seen_code, seen_zh, seen_src = {}, {}, {}
        mask = 0
        for e in dom["entries"]:
            if not e["code"]:
                found.append(f"{name}: 有成員缺短碼(中文 {e['zh']!r})")
            if not e["zh"]:
                found.append(f"{name}: 成員 {e['code']!r} 缺中文")
            if e["code"] in seen_code:
                found.append(f"{name}: 短碼重複 {e['code']!r}")
            seen_code[e["code"]] = True
            if e["zh"] in seen_zh:
                found.append(f"{name}: 中文重複 {e['zh']!r}")
            seen_zh[e["zh"]] = True
            src = e["src"]
            if src is None:
                continue
            if src in seen_src:
                found.append(f"{name}: 來源值重複 {src!r}"
                             f"({seen_src[src]!r} 與 {e['code']!r})")
            seen_src[src] = e["code"]
            if dom["src_kind"] == SRC_BITMASK:
                if mask & src:
                    found.append(f"{name}: 位元重疊 {e['code']!r} {src:#x}")
                mask |= src
        if dom["fallback"] and dom["fallback"] not in seen_code:
            found.append(f"{name}: fallback {dom['fallback']!r} 不是成員")
        found.extend(_group_problems(name, dom))
        found.extend(_carrier_problems(name, dom, domains))
        found.extend(_combo_problems(name, dom, domains))
        found.extend(_own_problems(name, dom, domains))
    return found


def _tag_slot_problems(domains, tag_slots):
    """槽位宣告必須兩側都解得動:類別是動作類別的成員、值域存在、鍵不重複、
    每一類都有宣告且含通用槽位「位置」(裁定批1;TAG_POS_EXEMPT 列名的類別
    除外——裁定票15)。

    寫壞的下場與其他宣告同族:索引短碼照這份宣告的欄位序編出來,類別對不上或
    值域缺席時,那一類的 tag 要嘛編不出來、要嘛前端解不回中文——都是無聲失效。
    """
    if TAG not in domains:
        return
    tag_codes = {e["code"] for e in domains[TAG]["entries"]}
    for code in sorted(set(tag_slots) - tag_codes):
        yield f"tag: 槽位宣告的類別 {code!r} 不是動作類別的成員"
    for code in sorted(tag_codes - set(tag_slots)):
        yield f"tag: 類別 {code!r} 沒有槽位宣告"
    for code, slots in tag_slots.items():
        keys = [key for key, _ in slots]
        if len(set(keys)) != len(keys):
            yield f"tag: 類別 {code!r} 的槽位鍵重複"
        if "pos" not in keys and code not in TAG_POS_EXEMPT:
            yield f"tag: 類別 {code!r} 缺通用槽位「位置」"
        for key, domain_name in slots:
            if domain_name not in domains:
                yield (f"tag: 類別 {code!r} 槽位 {key!r} 的值域 "
                       f"{domain_name!r} 不存在")


def _own_problems(name, dom, domains):
    """本類對應必須兩側都解得動:值是自己的成員、大類與子類型是各自值域的成員。

    寫壞的下場是**排除安靜地不生效**:一致判定永遠不成立,本類卡照舊全數出現在
    跨類型按鈕裡(ADR-0010 的語意整個沒了)——與承載關係寫壞同一族的無聲失效。
    """
    if not dom.get("own"):
        return []
    found = []
    own_codes = {e["code"] for e in dom["entries"]}
    seen = set()
    for code, cat, sub in dom["own"]:
        if code in seen:
            found.append(f"{name}: 本類對應重複 {code!r}")
        seen.add(code)
        if code not in own_codes:
            found.append(f"{name}: 本類對應 {code!r} 不是成員")
        side = SUB.get(cat)
        if side is None or side not in domains:
            found.append(f"{name}: 本類對應 {code!r} 的大類 {cat!r} 不存在")
            continue
        if sub not in {e["code"] for e in domains[side]["entries"]}:
            side_zh = domains[side]["zh"].replace("子類型", "側")
            found.append(f"{name}: 本類對應 {code!r} 的子類型 {sub!r} "
                         f"不是{side_zh}的成員")
    return found


def _combo_problems(name, dom, domains):
    """組合條件(效果類型×自身值)必須兩側都解得動,且只長在怪獸側的承載者上。

    寫壞的下場與承載關係同族:按鈕由分組長出來、命中規則由這份宣告決定,
    碼對不上時那一顆鈕在畫面上,點了卻永遠零結果。「怪獸側」的判別走結構而
    不是組名:魔陷十值全部有本類對應(ADR-0010)、怪獸側六類都沒有,所以
    「沒有本類對應的承載者」恰好就是誘發即時(2速)與誘發(1速)。
    """
    combos = dom.get("combos") or ()
    if not combos:
        return []
    found = []
    members = {e["code"] for e in dom["entries"]}
    zhs = {e["zh"] for e in dom["entries"]}
    seen = set(members)
    own = ({code for code, _, _ in domains[KIND]["own"]}
           if KIND in domains else set())
    for code, kind, value, zh_label in combos:
        if code in seen:
            found.append(f"{name}: 組合短碼重複 {code!r}")
        seen.add(code)
        if not zh_label:
            found.append(f"{name}: 組合 {code!r} 缺中文")
        elif zh_label in zhs:
            found.append(f"{name}: 中文重複 {zh_label!r}")
        zhs.add(zh_label)
        if value not in members:
            found.append(f"{name}: 組合 {code!r} 的值 {value!r} 不是成員")
        if kind not in dom["carriers"]:
            found.append(
                f"{name}: 組合 {code!r} 的效果類型 {kind!r} 不是承載者")
        elif kind in own:
            found.append(
                f"{name}: 組合 {code!r} 的效果類型 {kind!r} 不是怪獸側")
    return found


def _carrier_problems(name, dom, domains):
    """承載者必須是[[效果類型]]的成員:對不到 = 一條永遠不生效的規則。

    寫壞的兩個下場都糟:搜尋介面照它決定條件出不出得來(碼對不上就永遠不出來),
    建置期照它擋資料(碼對不上就永遠不擋)。
    """
    if not dom["carriers"]:
        return []
    kinds = codes(KIND, domains) if KIND in domains else ()
    return [f"{name}: 承載者 {code!r} 不是效果類型的成員"
            for code in dom["carriers"] if code not in kinds]


def _group_problems(name, dom):
    """分組必須恰好蓋過全部可篩選成員:漏一個成員就是漏一顆按鈕。"""
    if not dom["groups"]:
        return []
    found = []
    members = [e["code"] for e in dom["entries"] if e["filter"]]
    # 組合條件也是按鈕(spec-optional-combo),分組要蓋到它們
    members += [c[0] for c in dom.get("combos") or ()]
    grouped = []
    for label, group in dom["groups"]:
        if not label:
            found.append(f"{name}: 有分組缺組名")
        grouped.extend(group)
    for code in grouped:
        if code not in members:
            found.append(f"{name}: 分組列了非可篩選成員 {code!r}")
    for code in members:
        if code not in grouped:
            found.append(f"{name}: 成員 {code!r} 不在任何分組(宣告序有空洞)")
    dup = [c for c in set(grouped) if grouped.count(c) > 1]
    for code in sorted(dup):
        found.append(f"{name}: 成員 {code!r} 出現在多個分組")
    return found


def export(domains=None):
    """給 `window.VOCAB` 的形態:值域名 → 成員陣列(宣告序)+ 分組。

    前端只需要碼、中文、能不能做成按鈕與分組;cdb 位元不出去(那是建置期的事)。
    """
    domains = domains or DOMAINS
    out = {}
    for name, dom in domains.items():
        out[name] = {
            "zh": dom["zh"],
            "items": [{"code": e["code"], "zh": e["zh"]}
                      for e in dom["entries"] if e["filter"]],
        }
        if dom["groups"]:
            out[name]["groups"] = [{"zh": label, "codes": list(group)}
                                   for label, group in dom["groups"]]
        if dom.get("combos"):
            out[name]["items"].extend(
                {"code": code, "zh": zh_label}
                for code, _, _, zh_label in dom["combos"])
            out[name]["combos"] = {code: f"{kind}:{value}"
                                   for code, kind, value, _ in dom["combos"]}
        if dom["carriers"]:
            out[name]["carriers"] = list(dom["carriers"])
        if dom["own"]:
            out[name]["own"] = {code: f"{cat}:{sub}"
                                for code, cat, sub in dom["own"]}
    if TAG in out:
        # 槽位宣告隨 VOCAB 出去:索引短碼的欄位序、前端下拉與 badge 的解碼
        # 都讀這一份(ADR-0008——抄第二份就會漂移)
        out[TAG]["slots"] = {code: [[key, domain_name]
                                    for key, domain_name in slots]
                             for code, slots in TAG_SLOTS.items()}
    return out


def digest(domains=None):
    """正典的雜湊:值域改了,索引的 META 就跟著改,看 diff 就知道。"""
    payload = json.dumps(export(domains), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ── 效果 Tag 的短碼編解 ─────────────────────────────────────

def tag_code(tag, domains=None):
    """一個 tag 物件(中文值)→ 索引短碼;解不動時回 (None, 問題字串)。

    形狀:`類別碼:槽位碼:…`,槽位照 TAG_SLOTS 宣告序,缺值留空欄。`src` 與
    來歷欄位(rule / ticket)不進索引——搜尋不問判定是誰做的。
    """
    domains = domains or DOMAINS
    cat = code_of(TAG, tag.get("cat"), domains)
    if cat is None:
        return None, f"cat {tag.get('cat')!r} 不在動作類別值域"
    parts = [cat]
    slots = dict(TAG_SLOTS)[cat]
    known = {key for key, _ in slots} | {"cat", "src", "rule", "ticket"}
    for key in tag:
        if key not in known:
            return None, f"{tag.get('cat')} 有宣告外的槽位 {key!r}"
    for key, domain_name in slots:
        value = tag.get(key)
        if value is None:
            parts.append("")
            continue
        code = code_of(domain_name, value, domains)
        if code is None:
            return None, (f"{tag.get('cat')} 槽位 {key} 的值 {value!r} "
                          f"不在 {domain_name} 值域")
        parts.append(code)
    return ":".join(parts), None


def tag_digest(domains=None, tag_slots=None):
    """效果 Tag 體系定稿的指紋(動作類別、槽位值域、槽位宣告、觸發時機)。

    tag seal 的「體系定稿無異動」對的就是這個數字——動作類別或任何槽位值域
    動了它就變,其他值域(種族、禁限)動了它不變。
    """
    domains = domains or DOMAINS
    tag_slots = TAG_SLOTS if tag_slots is None else tag_slots
    names = sorted([TAG, TIMING] + [d for _, d in
                                    {(k, d) for slots in tag_slots.values()
                                     for k, d in slots}])
    payload = json.dumps({
        "domains": {name: [[e["code"], e["zh"]]
                           for e in domains[name]["entries"]]
                    for name in names if name in domains},
        "slots": {code: list(map(list, slots))
                  for code, slots in tag_slots.items()},
        "timing_carriers": list(domains[TIMING]["carriers"])
        if TIMING in domains else [],
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
