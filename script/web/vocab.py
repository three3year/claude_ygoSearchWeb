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


def entry(code, zh, src=None, filterable=True):
    """一個值域成員。src 為 None 時代表「來源側沒有這個值」:

    - SRC_TEXT 的成員預設 src 就是中文本身(效果類型等的來源值即中文)。
    - `fallback` 成員(魔法/陷阱的「通常」)沒有位元,由「其他位元都沒中」判定。

    filterable=False 的成員登記在正典裡但不做成按鈕([[衍生物]]:卡片總表本來
    就不收錄,登記它是為了位元解釋得動,而不是給使用者一顆永遠 0 筆的鈕)。
    """
    return {"code": code, "zh": zh, "src": src, "filter": filterable}


def domain(zh, src_kind, entries, groups=(), fallback=None):
    """一個值域。entries 的順序就是宣告序:按鈕順序與排序比較序共用它。

    groups 是按鈕分組((組名, 成員碼...)),分組必須恰好蓋過全部可篩選成員——
    漏一個成員就是漏一顆按鈕,而那與漏一個碼的失效模式一模一樣(ADR-0008)。
    """
    if src_kind == SRC_TEXT:
        entries = tuple(
            e if e["src"] is not None else dict(e, src=e["zh"])
            for e in entries)
    return {"zh": zh, "src_kind": src_kind, "entries": tuple(entries),
            "groups": tuple(groups), "fallback": fallback}


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
_SUB_M = domain("怪獸子類型", SRC_BITMASK, (
    entry("normal", "通常", 0x10),
    entry("effect", "效果", 0x20),
    entry("fusion", "融合", 0x40),
    entry("ritual", "儀式", 0x80),
    entry("synchro", "同調", 0x2000),
    entry("xyz", "超量", 0x800000),
    entry("pendulum", "靈擺", 0x1000000),
    entry("link", "連結", 0x4000000),
    entry("tuner", "調整", 0x1000),
    entry("flip", "反轉", 0x200000),
    entry("spsummon", "特殊召喚", 0x2000000),
    entry("dual", "二重", 0x800),
    entry("spirit", "靈魂", 0x200),
    entry("union", "同盟", 0x400),
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
    ("魔陷卡效果", ("sn", "sq", "sr", "sc", "se", "sf", "sp", "tn", "tc",
                    "tk")),
))
_OPTIONAL = domain("必發/選發", SRC_TEXT, (
    entry("m", "必發"),
    entry("o", "選發"),
))
_ROLE = domain("效果外文本種別", SRC_TEXT, (
    entry("mat", "素材指定"),
    entry("cond", "召喚條件"),
    entry("limit", "使用次數限制"),
))

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

DOMAINS = {
    CAT: _CAT,
    "sub_m": _SUB_M, "sub_s": _SUB_S, "sub_t": _SUB_T,
    ATTR: _ATTR, RACE: _RACE,
    KIND: _KIND, OPTIONAL: _OPTIONAL, ROLE: _ROLE,
    LINK_MARKER: _LINK_MARKER, RARITY: _RARITY, OT: _OT,
}

# 各值域的成員數。與 CONTEXT.md / spec 記的值域規模對帳用:少一個成員代表某批卡
# 的按鈕不見了,多一個代表有人加了值域卻沒改文件。子類型合計 25(怪獸側 15 +
# [[衍生物]] + 魔法側 6 + 陷阱側 3)。
EXPECTED_SIZES = {
    CAT: 3, "sub_m": 16, "sub_s": 6, "sub_t": 3,
    ATTR: 7, RACE: 26,
    KIND: 16, OPTIONAL: 2, ROLE: 3,
    LINK_MARKER: 8, RARITY: 4, OT: 3,
}

# cdb `type` 的位元由大類與三個子類型值域共同解釋;沒有被解釋的位元會讓建置倒
# (見模組 docstring)。
TYPE_DOMAINS = (CAT, "sub_m", "sub_s", "sub_t")


def entries(name, domains=None):
    return (domains or DOMAINS)[name]["entries"]


def codes(name, domains=None):
    return tuple(e["code"] for e in entries(name, domains))


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


def problems(domains=None):
    """正典自檢:回傳問題字串清單(空 = 合法)。

    測的是**正典這份資料本身**合不合法,不是管線的中間產物。八種:成員數與
    EXPECTED_SIZES 不符、短碼重複、缺短碼或缺中文、同值域內中文重複(按鈕會有
    兩顆長一樣的)、來源值重複或位元重疊(解碼時對到兩個成員)、fallback 指向
    不存在的成員、分組沒有恰好蓋過全部可篩選成員(宣告序有空洞)、分組列了
    不存在的成員。
    """
    domains = domains or DOMAINS
    found = []
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
    return found


def _group_problems(name, dom):
    """分組必須恰好蓋過全部可篩選成員:漏一個成員就是漏一顆按鈕。"""
    if not dom["groups"]:
        return []
    found = []
    members = [e["code"] for e in dom["entries"] if e["filter"]]
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
    return out


def digest(domains=None):
    """正典的雜湊:值域改了,索引的 META 就跟著改,看 diff 就知道。"""
    payload = json.dumps(export(domains), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
