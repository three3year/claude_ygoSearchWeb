"""效果標記表管線:卡片總表 + 補足情報 → 效果標記表(拆句骨架)。

單一接縫:build_tag_cards(卡片總表條目, 補足情報條目[, 既有標記表, 判定結果,
    拆句表]) → (entries, report)
純函式,不碰網路與檔案系統。詞彙見 CONTEXT.md:效果標記表、效果句、效果類型、
效果外文本、必發/選發、拆句表。

三個選用參數的生效時機不同,順序是本模組的骨幹(ADR-0003):
    拆句表 → 官方明示抽取 → 必發/選發 → 判定結果 → 既有標記表 → 影子預測
拆句表決定效果句的**集合**、判定結果決定效果句上的**值**。
"""
import hashlib
import json
import re
from collections import Counter

import official
import rules
from official import (BULLET, INDEX_PREAMBLE, INDEX_UNNUMBERED,
                      KIND_NON_EFFECT, KIND_QUICK, KIND_TRIGGER, NUMERALS,
                      OPTIONAL_MANDATORY, OPTIONAL_OPTIONAL, SPELLTRAP_KINDS)

# NUMERALS:效果編號字元。官方目前最多用到⑤,official 多留幾個位以防新卡。
# BULLET:● 子效果的記號,拆句與歸屬對位都要認它,定義放在 official 一份。
FULLWIDTH_COLON = "："

# 卡片總表 type 位元(與 script/card_list/cardlist.py 同一套)
TYPE_MONSTER = 0x1
TYPE_NORMAL = 0x10
TYPE_FUSION = 0x40
TYPE_RITUAL = 0x80
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_PENDULUM = 0x1000000
TYPE_LINK = 0x4000000
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_QUICKPLAY = 0x10000
TYPE_CONTINUOUS = 0x20000
TYPE_EQUIP = 0x40000
TYPE_FIELD = 0x80000
TYPE_COUNTER = 0x100000
# 這些怪獸的卡文第一行是素材指定(卡文的硬性寫作慣例)
MATERIAL_TYPES = TYPE_FUSION | TYPE_RITUAL | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK

# [[卡片種類]]的細分。一列 = (魔法或陷阱的位元, 細分位元→名稱, 沒有細分位元時的名稱);
# 細分位元的順序即優先序,先命中的先算。
CARD_TYPE_TABLE = (
    (TYPE_SPELL,
     ((TYPE_QUICKPLAY, "速攻魔法"), (TYPE_RITUAL, "儀式魔法"),
      (TYPE_CONTINUOUS, "永續魔法"), (TYPE_EQUIP, "裝備魔法"),
      (TYPE_FIELD, "場地魔法")),
     "通常魔法"),
    (TYPE_TRAP,
     ((TYPE_COUNTER, "反擊陷阱"), (TYPE_CONTINUOUS, "永續陷阱")),
     "通常陷阱"),
)


ROLE_MATERIAL = "素材指定"
ROLE_SUMMON = "召喚條件"
ROLE_USAGE = "使用次數限制"
SOURCE_RULE = "rule"
SOURCE_LLM = "llm"
SOURCE_LLM_THEN_RULE = "llm_then_rule"
SOURCE_MANUAL = "manual"
SOURCES = (official.SOURCE_OFFICIAL, SOURCE_RULE, SOURCE_LLM,
           SOURCE_LLM_THEN_RULE, SOURCE_MANUAL)
CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"

SECTION_MAIN = "main"
SECTION_PENDULUM = "pendulum"

# 只有這兩類寫必發/選發:啟動效果本就由玩家主動開啟,其餘三類不發動
ACTIVATED_KINDS = (KIND_QUICK, KIND_TRIGGER)
# [[魔陷卡效果]]的行也可以帶必發/選發,但只在**有觸發事件的發動句**上(ADR-0004):
# 卡本身要不要發動永遠是玩家的選擇,寫「選發」是廢話;墓地/場上被動觸發的那族
# 才有強制與否的資訊。這組值因此只吃官方明示與判定,不用規則補值。
OPTIONAL_KINDS = ACTIVATED_KINDS + SPELLTRAP_KINDS

HEAD_PENDULUM = "【靈擺效果】"
HEAD_MONSTER_RE = re.compile(r"【怪獸(效果|敘述|描述)】")
# 通常怪獸的敘述段。來源資料有一張寫成「描述」,只認「敘述」會漏掉。
FLAVOR_HEADS = ("敘述", "描述")
# 繁中來源在卡文尾端附的別名註記(如「\n\n※白銀之城的狂時鐘」),不是卡文本體
FOOTNOTE_RE = re.compile(r"\n\n※[^\n]*$")

CLAUSE_FIELDS = ("index", "section", "text_zh", "text_ja", "text_hash", "kind",
                 "optional", "role", "source", "needs_review", "rule_predicted",
                 "confidence", "tags")


def card_type_label(ctype):
    """卡片總表的 type 位元 → [[卡片種類]]的名稱;認不出來時回 None。

    判定規範 §5.8 的「這張卡本身的發動」由卡片種類決定[[效果類型]],而**卡文分不
    出來**——通常魔法與速攻魔法的卡文寫法完全一樣,判定票只讀批次檔的話沒有別的
    來源。怪獸不細分:§5.8 只問是不是魔法・陷阱卡。
    """
    if ctype & TYPE_MONSTER:
        return "怪獸"
    for bit, subtypes, plain in CARD_TYPE_TABLE:
        if ctype & bit:
            return next((label for mask, label in subtypes if ctype & mask),
                        plain)
    return None


# ---------------------------------------------------------------- 拆句

def _cut_points(text):
    """效果編號的切割點:行首、緊接換行、或後接全角冒號的編號字元。

    文中編號(「這個卡名的①②效果1回合各能使用1次」)三者皆不符合,不會被切開。
    官方日文卡文常整段不換行,只用行首規則會完全切不開,故納入全角冒號規則;
    繁中卡文上兩條規則實測完全一致(報告的 zh_cut_rule_disagree 監看此前提)。
    """
    return [i for i, ch in enumerate(text)
            if ch in NUMERALS
            and (i == 0 or text[i - 1] == "\n"
                 or text[i + 1:i + 2] == FULLWIDTH_COLON)]


def _line_start_cut_points(text):
    """只取行首或緊接換行的編號字元(用於監看繁中側兩條切割規則是否仍一致)。"""
    return [i for i, ch in enumerate(text)
            if ch in NUMERALS and (i == 0 or text[i - 1] == "\n")]


def _strip_span(text, start, end):
    """去掉首尾空白後的 (start, end);全為空白時回傳 None。

    回傳位移而非字串,讓每一段都保證是原文的連續子字串。
    """
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if start < end else None


def _segments(text):
    """段落文字 → (前言 span, [(編號字元, span), ...], 無編號全段 span)。

    有編號時前言 span 為第一個切割點之前的非空文字(可為 None),無編號全段為 None;
    無編號時反之。三者皆為 (start, end) 位移或 None。
    """
    cuts = _cut_points(text)
    if not cuts:
        return None, [], _strip_span(text, 0, len(text))
    preamble = _strip_span(text, 0, cuts[0])
    numbered = []
    for pos, start in enumerate(cuts):
        end = cuts[pos + 1] if pos + 1 < len(cuts) else len(text)
        span = _strip_span(text, start, end)
        if span is not None:
            numbered.append((text[start], span))
    return preamble, numbered, None


def _zh_sections(desc):
    """繁中卡文 → ([(section, 段落文字), ...], 丟棄敘述段)。

    靈擺卡靠卡文標頭字串分段,不看 type 位元:38 張靈擺通常怪獸同時帶 Normal 與
    Pendulum 位元,只看位元會把整張當敘述文。【怪獸敘述】/【怪獸描述】段整段丟棄。
    """
    if HEAD_PENDULUM not in desc:
        return [(SECTION_MAIN, desc)], False
    pend_start = desc.index(HEAD_PENDULUM) + len(HEAD_PENDULUM)
    head = HEAD_MONSTER_RE.search(desc, pend_start)
    if head is None:
        return [(SECTION_PENDULUM, desc[pend_start:])], False
    sections = [(SECTION_PENDULUM, desc[pend_start:head.start()])]
    if head.group(1) in FLAVOR_HEADS:
        return sections, True
    sections.append((SECTION_MAIN, desc[head.end():]))
    return sections, False


# ---------------------------------------------------------------- 前言段 role

# 「我方1回合只能特殊召喚1次「某卡」」也算此卡自身的召喚限制
_SUMMON_RE = re.compile(
    r"不能通常召喚|不能特殊召喚|不能召喚|不能同步召喚|不能超量召喚|不能連結召喚"
    r"|不能融合召喚|不能儀式召喚|不能作為|才能特殊召喚|只能特殊召喚"
    r"|只能.{0,40}?召喚|規則上.{0,20}?當作等級"
    r"|此卡.{0,30}?上級召喚|必須解放.{0,20}?召喚|此卡.{0,20}?不能.{0,20}?召喚")
_USAGE_RE = re.compile(
    r"1回合.{0,30}?(?:使用|發動|選擇)|回合只能|各能使用|最多.{0,4}次"
    r"|決鬥中.{0,10}?(?:使用|發動)|同一連鎖上.{0,10}?(?:使用|發動)")
# 儀式怪獸的「藉由「〜」降臨」與儀式魔法卡的「〜的降臨所必需」都是素材指定
_MATERIAL_TEXT_RE = re.compile(r"藉由.{0,30}?降臨|降臨所必需|降臨所必須|降臨必需")
# 素材行不以句號結尾(「「青眼白龍」+「青眼白龍」」「等級4怪獸×2」),其餘句子都有
_SEGMENT_SEP_RE = re.compile(r"[\n。，]")


def _looks_like_material_line(text, ctype):
    """卡文第一行是素材指定嗎?

    只認融合/儀式/同調/超量/連結怪獸,且第一行不以句號結尾——素材行是名詞片語,
    句子則一律以「。」收尾,這是卡文的硬性寫作慣例。
    """
    if not (ctype & TYPE_MONSTER and ctype & MATERIAL_TYPES):
        return False
    first = text.split("\n", 1)[0].strip()
    return bool(first) and not first.endswith("。")


def _preamble_role(text, ctype):
    """前言段 → 素材指定 / 召喚條件 / 使用次數限制 / None。

    先看第一行是否為素材行,再逐子句掃描——卡文的書寫順序固定是
    素材 → 召喚條件 → 使用次數限制,所以「第一個判得出來的子句」就是這段的主旨。
    子句內的優先序為 素材 > 召喚條件 > 使用次數限制。
    """
    if _looks_like_material_line(text, ctype):
        return ROLE_MATERIAL
    for segment in _SEGMENT_SEP_RE.split(text):
        if not segment.strip():
            continue
        if _MATERIAL_TEXT_RE.search(segment):
            return ROLE_MATERIAL
        if _SUMMON_RE.search(segment):
            return ROLE_SUMMON
        if _USAGE_RE.search(segment):
            return ROLE_USAGE
    return None


# ---------------------------------------------------------------- 效果句

def _text_hash(text_ja, text_zh):
    """**判定基礎文本**的雜湊(身分變動偵測用);兩側都空時為 None。

    絕大多數卡的判定基礎是日文原文。無官方日文文本的那批(TCG 限定卡,ADR-0006)
    以繁中卡文為判定基礎,雜湊就跟著判定基礎走——寫成日文的雜湊會讓那批行永遠
    是 None,繁中卡文改了也沒有人會知道。
    """
    body = text_ja or text_zh
    if not body:
        return None
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def _clause(index, section, text_zh, text_ja, confidence,
            kind=None, role=None, source=None):
    return {
        "index": index,
        "section": section,
        "text_zh": text_zh,
        "text_ja": text_ja,
        "text_hash": _text_hash(text_ja, text_zh),
        "kind": kind,
        "optional": None,
        "role": role,
        "source": source,
        "needs_review": False,
        "rule_predicted": None,
        "confidence": confidence,
        "tags": [],
    }


def _slice(text, span):
    return "" if span is None else text[span[0]:span[1]]


# ------------------------------------------------------------ 拆句的共用驗證

# ● 分項與[[拆句表]]兩條拆句路徑共用同一套檢查:切出來的段落串接後必須等於
# 原文,而官方 『原文』 引用不得被拆點切開。兩者都不需要標準答案就能自動檢查。

def _condense(text):
    """去掉全部空白 → (壓縮後的文字, 每個字元在原文的位移)。"""
    kept = [(ch, pos) for pos, ch in enumerate(text) if not ch.isspace()]
    return "".join(ch for ch, _ in kept), [pos for _, pos in kept]


def _cover_spans(text, parts):
    """段落原文子字串 → 各段在原文的 span;串接對不上原文時回 None。

    **驗證一・無遺漏覆蓋**:比對忽略空白,但切出來的一律是原文的連續子字串。
    「連續子字串」擋得住竄改卻擋不住漏掉,而漏掉是判定者唯一的沉默失效模式。
    """
    body, offsets = _condense(text)
    condensed = [_condense(part)[0] for part in parts]
    if "".join(condensed) != body:
        return None
    sizes = [len(part) for part in condensed]
    spans = []
    start = 0
    for size in sizes:
        spans.append((offsets[start], offsets[start + size - 1] + 1)
                     if size else None)
        start += size
    return spans


def _quotes_cut_apart(text_ja, spans, supplement):
    """**驗證二・引用交叉驗證**:被拆點切成兩半的官方 『原文』 引用。

    不需要標準答案就能自動檢查——引用橫跨拆點,就證明那兩段是同一個效果句。
    """
    if not text_ja:
        return []
    body = official.normalise(text_ja)
    segments = [official.normalise(_slice(text_ja, span)) for span in spans]
    cut = []
    for quoted in official.quotes(supplement):
        needle = official.normalise(quoted)
        if needle and needle in body and not any(needle in segment
                                                 for segment in segments):
            cut.append(quoted)
    return cut


# ---------------------------------------------------------------- 前言段拆分

# 前言段以**日文官方換行**為拆點(ADR-0009):日文以換行區分前言裡的不同單位
# (素材指定/召喚條件/使用次數限制),繁中來源常缺這些換行。拆點可由卡文重算,
# 所以住在建置期而不是拆句表——存檔只會製造會過期的複本。
# [[補足情報]]的 『…』 引用橫跨拆點時整段退回不拆(引用合併是票66):引用是
# 官方視為一體的單位,機械規則不猜測。
FALLBACK_UNITS = "單位數不合"
FALLBACK_QUOTE = "引用跨界"


def _line_spans(text, span):
    """span 內各非空行的 (start, end),已照 `_strip_span` 慣例剝首尾空白。"""
    start, end = span
    spans = []
    pos = start
    while pos < end:
        cut = text.find("\n", pos, end)
        stop = end if cut < 0 else cut
        line = _strip_span(text, pos, stop)
        if line is not None:
            spans.append(line)
        pos = stop + 1
    return spans


def _zh_unit_spans(text, span):
    """中文前言 → 對位單位的 span:自身換行切行塊,行塊內再以句號切句。

    無句號的行塊整塊算一個單位——素材行是名詞片語不以句號收尾,不這樣算
    兩側的單位數永遠對不上(2133971 形態)。
    """
    units = []
    for start, end in _line_spans(text, span):
        pos = start
        while pos < end:
            cut = text.find("。", pos, end)
            stop = end if cut < 0 else cut + 1
            unit = _strip_span(text, pos, stop)
            if unit is not None:
                units.append(unit)
            pos = stop
    return units


def _split_preamble(zh_body, ja_body, supplement):
    """前言段兩側原文 → ([(zh span, ja span), ...], None) 或 (None, 退回原因)。

    日文單行時回 (None, None):不進拆分也不進退回清單。日文每行的單位數 =
    句號數(無句號行算 1),中文單位總數與之相等時依序分組,否則退回——
    分組假設中日句序一致,句序調換且句數恰好相等時會錯配且不報錯,防線是
    抽查(ADR-0009 已知限制)。
    """
    lines = _line_spans(ja_body, (0, len(ja_body)))
    if len(lines) < 2:
        return None, None
    if _quotes_cut_apart(ja_body, lines, supplement):
        return None, FALLBACK_QUOTE
    counts = [_slice(ja_body, span).count("。") or 1 for span in lines]
    units = _zh_unit_spans(zh_body, (0, len(zh_body)))
    if len(units) != sum(counts):
        return None, FALLBACK_UNITS
    pairs = []
    pos = 0
    for span, count in zip(lines, counts):
        pairs.append(((units[pos][0], units[pos + count - 1][1]), span))
        pos += count
    return pairs, None


# ---------------------------------------------------------------- ● 子效果

def _bullet_parts(text):
    """文字 → (第一個 ● 之前的段落, [● 分項, ...]);兩者都已去首尾空白。"""
    positions = [i for i, ch in enumerate(text) if ch == BULLET]
    if not positions:
        return text.strip(), []
    bounds = list(zip(positions, positions[1:] + [len(text)]))
    return text[:positions[0]].strip(), [text[s:e].strip() for s, e in bounds]


def _bullet_authorised(clause, supplement, headers):
    """官方認可這一段的 ● 是獨立子效果嗎?三種依據,證據強度相同。

    官方都是拿整個 `●` 當一個東西在講:`【●…について】` 標頭(票03)、行內
    `『●…』` 引用逐項給裁定(票16),或**逐項給出不同的類型**(票58)。第二種
    只對**賦予型領起句**開火——領起句自己就寫了發動時 `●` 只是同一個發動的
    選項列舉,拆了反而製造出官方沒有認可的效果句,而票14 實測那一族的官方類型
    本來就是對的。

    第三種不受領起句形態限制,因為它的證據是官方**已經把這些 `●` 判成不同的
    類型**:不拆的話一條效果句只有一個類型欄位,必然有一半是錯的(查詢層也就
    定位不到那一半)。只給一種類型時不開火,整段照那一種判即可。
    """
    if headers:
        return True
    if official.bullets_typed_apart(supplement, clause["text_ja"]):
        return True
    return (official.grant_lead(clause["text_ja"]) is not None
            and bool(official.quoted_bullets(supplement, clause["text_ja"])))


def _bullet_pieces(cid, section, clause, supplement, headers, report):
    """一個效果句 → 拆開的 ● 分項;沒有依據或驗證不成立時回 None(不拆)。

    拆之前兩道驗證比照[[拆句表]]:分項串接後必須等於原文(`_cover_spans`,同時
    讓每一段都從原文切片,連續子字串因此是結構上的保證),官方 `『原文』` 引用
    不得被 ● 拆點切開——引用橫跨拆點就證明那兩段是同一個效果句(ADR-0003)。
    """
    both = clause["text_zh"] + clause["text_ja"]
    if official._is_preamble(clause["index"]) or BULLET not in both:
        return None
    if not _bullet_authorised(clause, supplement, headers):
        return None

    row = {"id": cid, "section": section, "index": clause["index"]}
    zh_head, zh_bullets = _bullet_parts(clause["text_zh"])
    if clause["text_ja"]:
        ja_head, ja_bullets = _bullet_parts(clause["text_ja"])
    else:
        ja_head, ja_bullets = "", [""] * len(zh_bullets)
    if len(ja_bullets) != len(zh_bullets):
        report["bullet_split_mismatch"].append(row)
        return None
    zh_spans = _cover_spans(clause["text_zh"], [zh_head, *zh_bullets])
    ja_spans = (_cover_spans(clause["text_ja"], [ja_head, *ja_bullets])
                if clause["text_ja"] else [None] * (len(ja_bullets) + 1))
    if zh_spans is None or ja_spans is None:
        report["bullet_coverage_failed"].append(
            {**row, "side": "zh" if zh_spans is None else "ja"})
        return None
    cut = _quotes_cut_apart(clause["text_ja"], ja_spans, supplement)
    if cut:
        report["bullet_quote_violations"].append({**row, "quotes": cut})
        return None

    def piece(index, pos):
        return _clause(index, section, _slice(clause["text_zh"], zh_spans[pos]),
                       _slice(clause["text_ja"], ja_spans[pos]),
                       clause["confidence"])

    pieces = []
    if zh_head or ja_head:
        pieces.append(piece(clause["index"], 0))
    for pos in range(1, len(zh_spans)):
        pieces.append(piece(f"{clause['index']}-{BULLET}{pos}", pos))
    report["bullet_clauses"] += len(zh_bullets)
    if not headers:
        # 兩道驗證都過了才算數,計數放在這裡才對得上實際拆出來的段
        report["bullet_quote_splits"] += 1
    return pieces


def _split_bullets(cid, section, clauses, supplement, report):
    """官方認可 ● 是獨立子效果時,把 ● 分項拆成獨立效果句。

    沒有依據的 ● 只是同一個效果的選項列舉,拆了反而製造出官方沒有認可的效果句;
    繁中與日文的 ● 數量不一致時同樣不拆。
    """
    headers = bool(official.bullet_specs(supplement))
    split = []
    for clause in clauses:
        pieces = _bullet_pieces(cid, section, clause, supplement, headers,
                                report)
        split.extend(pieces if pieces is not None else [clause])
    return split


# ---------------------------------------------------------------- 拆句表

# 拆出來的段落 index:效果外文本段 "0" / "0-2" / "0-3",效果句 "1" / "2" / "3"。
# "1" 沿用整團現在的 index,只有一段效果句的卡拆完後 index 不變、不製造孤兒。
_SPLIT_INDEX_RE = re.compile(r"^(?:0(?:-[2-9][0-9]*)?|[1-9][0-9]*)$")
_SPLIT_HASH_SEP = "\x1f"


def split_hash(text_zh, text_ja):
    """拆句當時的卡文雜湊(兩側一起算)。

    對「偵測變動」是冗餘的——無遺漏覆蓋等式已經涵蓋任何一個字元的變動。留著是為了
    **診斷**:出事時能一眼看出這筆拆點是對著哪一版卡文切的(ADR-0003)。
    寫拆句表的程式與讀拆句表的骨架共用這一支,兩邊不會各算各的。
    """
    body = f"{text_zh}{_SPLIT_HASH_SEP}{text_ja}"
    return hashlib.sha1(body.encode("utf-8")).hexdigest()[:16]


def _index_splits(splits):
    """拆句表 → {(卡片密碼, section): 紀錄}。"""
    return {(record["id"], record["section"]): record
            for record in splits or ()}


def _ja_order(record, count):
    """日文的閱讀順序(段落位置的排列);不是合法排列時回 None。

    `segments` 照**繁中**順序列,兩側語序不一致的卡因此需要另記日文那一側怎麼讀
    (票51)。沒有這個欄位就是恆等排列——既有紀錄一個字都不用改。
    """
    order = record.get("ja_order")
    if order is None:
        return list(range(count))
    # 結果檔是人寫的 JSON,型別也可能是壞的("1" 而不是 1、true 而不是 1),
    # 所以先逐項驗型別再驗排列——直接 sorted() 混型別的清單會拋例外而不是拒收
    if not isinstance(order, list) or any(
            type(pos) is not int for pos in order):
        return None
    return order if sorted(order) == list(range(count)) else None


def _validate_split(record, blob, supplement):
    """拆句表的一筆 → ({側: 各段 span}, None) 或 (None, 不能用的理由)。

    順序即優先序:結構不合法 → 卡文已變動 → 覆蓋不成立 → 引用被切開。**驗證三・
    卡文變動即失效**走的是前兩道,一律退回整團而不保留舊拆點——保留失效的斷言會讓
    歸屬階梯在假前提上開火,那正是票11 的錯誤。

    回傳的 span 一律照 `segments` 的順序(繁中順序)。日文那一側只在**驗覆蓋時**
    照 `ja_order` 排——無遺漏覆蓋問的是「照這一側的閱讀順序串接起來等不等於原文」,
    而呼叫端要的是「第 i 段的兩側各在哪裡」,兩者的順序不同(票51)。
    """
    segments = record.get("segments") or ()
    indexes = [segment.get("index") for segment in segments]
    order = _ja_order(record, len(segments))
    if (not segments or not record.get("text_hash") or order is None
            or len(set(indexes)) != len(indexes)
            or any(not _SPLIT_INDEX_RE.match(index or "")
                   for index in indexes)):
        return None, ("split_malformed", {})
    if record["text_hash"] != split_hash(blob["text_zh"], blob["text_ja"]):
        return None, ("split_stale", {})

    spans = {}
    for side, reading in (("zh", range(len(segments))), ("ja", order)):
        covered = _cover_spans(
            blob[f"text_{side}"],
            [segments[pos].get(f"text_{side}", "") for pos in reading])
        if covered is None:
            return None, ("split_coverage_failed", {"side": side})
        spans[side] = [None] * len(segments)
        for span, pos in zip(covered, reading):
            spans[side][pos] = span
    # 引用交叉驗證只問「引用有沒有完整落在某一段裡」,與段落順序無關
    cut = _quotes_cut_apart(blob["text_ja"], spans["ja"], supplement)
    if cut:
        return None, ("split_quote_violations", {"quotes": cut})
    return spans, None


def _apply_split(cid, section, record, blob, ctype, supplement, report):
    """拆句表的一筆 → 切開整團的效果句;任一道驗證不成立時回 None(退回整團)。"""
    spans, problem = _validate_split(record, blob, supplement)
    if problem is not None:
        key, extra = problem
        report[key].append({"id": cid, "section": section, **extra})
        return None

    clauses = []
    for segment, zh_span, ja_span in zip(record["segments"], spans["zh"],
                                         spans["ja"]):
        index = segment["index"]
        text_zh = _slice(blob["text_zh"], zh_span)
        text_ja = _slice(blob["text_ja"], ja_span)
        if index.startswith(INDEX_PREAMBLE):
            # 效果外文本段走的是前言段那條位置規則,不送判定
            role = _preamble_role(text_zh, ctype)
            clauses.append(_clause(index, section, text_zh, text_ja,
                                   blob["confidence"], kind=KIND_NON_EFFECT,
                                   role=role, source=SOURCE_RULE))
            report["preambles"] += 1
            report["role_counts"][role or "null"] += 1
        else:
            clauses.append(_clause(index, section, text_zh, text_ja,
                                   blob["confidence"]))
            report["split_clauses"] += 1
    report["split_records"] += 1
    return clauses


# ---------------------------------------------------------------- 官方明示

def _apply_attestations(cid, section, clauses, name_ja, supplement, unsplit,
                        split_indexes, report):
    """官方明示的效果類型寫進效果句;歸屬不確定的只進報告,不猜測。

    回傳官方寫了「必ず発動」的效果句 index 集合,交給必發/選發那一層使用。
    """
    assignments, mandatory, notes = official.attest(name_ja, supplement,
                                                    clauses, unsplit)
    by_index = {clause["index"]: clause for clause in clauses}
    for index, (kind, ladder) in assignments.items():
        clause = by_index[index]
        clause["kind"] = kind
        clause["source"] = official.SOURCE_OFFICIAL
        report["official_clauses"] += 1
        report["official_coverage"][ladder] += 1
        if index in split_indexes:
            # 票11 撤掉的那 1,146 條裡「其實是對的」那一部分從這裡回來
            report["split_new_official"] += 1
    for key, rows in notes.items():
        for row in rows:
            report[key].append({"id": cid, "section": section, **row})
    return set(mandatory)


# ---------------------------------------------------------------- 必發/選發

# 發動子句的結尾。日文卡文的硬性寫作慣例:能不能發動寫在發動子句的句尾。
_OPTIONAL_ENDINGS = ("できる", "できます")
_ACTIVATION_MARK = "発動"
# 舊式的代價句型「〜する事で、…する。」:發動子句不以「できる」結尾,句尾規則因此
# 推定必發,但那個「事で」正是「付這個代價就可以」的意思(繁中一律譯作「可以藉由
# …」),一律選發。規範 §4 第三層。
#
# 條件是「發動子句裡有〈辭書形〉事で」,兩件事都**不**要求:
# 逗號——「〜送る事で「ホルスの黒炎竜 LV８」１体を…」(11224103)後面直接接引號;
# 發動子句不含「発動」——「相手が…効果を発動した時、このカードをリリースする事で
# …」(7841112)的「発動」是觸發事件裡的,不是這一句自己的可否。
#
# 但**「た事で」不算**:那是「因為發生了這件事」而不是「付這個代價就可以」,官方
# 對它判必發(`装備モンスターがフィールドから離れた事でこのカードが墓地へ送られた
# 場合に発動する`,51686645 / 90673413)。少了這道排除,官方明示的必發獨立驗證會從
# 847/848 掉到 845/848。
_COST_PARTICLE_RE = re.compile(r"(?<!た)事で")
# 規則判不出的三種原因,報告的驗證集分別計數
_UNPREDICTED_KEYS = {"未拆句": "unsplit", "無日文卡文": "no_text",
                     "找不到發動子句": "no_activation"}
_PAREN_OPEN = "（("
_PAREN_CLOSE = "）)"
# 發動子句末尾的補述(「〜発動できる(同一チェーン上では１度まで)。」)
_TRAILING_PAREN_RE = re.compile(r"[（(][^（()）]*[）)]\s*$")


def _first_sentence(text):
    """第一個**不在括號內**的句號之前的文字。

    官方把補述寫在發動子句的句尾括號裡,而括號內常自帶句號
    (「〜発動できる(この効果は１ターンに１度しか使えない。)。」),
    直接切第一個「。」會把發動子句斷在括號中間。
    """
    depth = 0
    for pos, ch in enumerate(text):
        if ch in _PAREN_OPEN:
            depth += 1
        elif ch in _PAREN_CLOSE:
            depth = max(depth - 1, 0)
        elif ch == "。" and depth == 0:
            return text[:pos]
    return text


def _activation_clause(text_ja):
    """效果句的日文原文 → 發動子句(到第一個句號為止);抓不到時回 None。

    掃描起點是這一句自己的開頭、終點是第一個句號。效果句在拆句時已經切開,
    掃描因此天然停在效果句邊界內,不會咬到下一個編號效果的「発動できる」——
    官方日文卡文整段不換行(`①：…。②：…。`)時這是唯一的防線。

    句尾的括號補述要剝掉再看結尾:「〜発動できる(同一チェーン上では１度まで)」
    的可否仍寫在括號之前。
    """
    text = text_ja.strip()
    if text[:1] in NUMERALS:
        text = text[1:].lstrip("：:").strip()
    elif text[:1] == BULLET:
        text = text[1:].strip()
    head = _first_sentence(text).strip()
    while True:
        stripped = _TRAILING_PAREN_RE.sub("", head).strip()
        if stripped == head:
            return head or None
        head = stripped


def _optional_by_rule(clause, unsplit):
    """效果句 → (必發/選發, 發動子句);規則判不出時回 (None, 原因)。

    舊式無編號卡文還沒依語意拆開,第一句常是素材指定或召喚條件而不是發動子句
    (實測這樣硬掃會把官方明示為必發的 79 條標成選發),因此整團留待判定。

    第一句既沒有「できる」也沒提到発動時(「②：…は以下の効果を得る。●…」這種
    領起句)不算發動子句——真正的發動寫在後面的 ● 分項裡,推定必發會錯。

    代價句型「〜する事で、…」在「できる」之後、其餘兩條之前結算:它一樣不以
    「できる」結尾,句尾規則會推定必發或乾脆認不出發動子句,而「事で」已經寫明了
    「付這個代價就可以」(票19,§4 第三層)。
    """
    if clause["index"] in unsplit:
        return None, "未拆句"
    if not clause["text_ja"]:
        return None, "無日文卡文"
    activation = _activation_clause(clause["text_ja"])
    if activation is None:
        return None, "找不到發動子句"
    if activation.endswith(_OPTIONAL_ENDINGS):
        return OPTIONAL_OPTIONAL, activation
    if _COST_PARTICLE_RE.search(activation):
        return OPTIONAL_OPTIONAL, activation
    if _ACTIVATION_MARK not in activation:
        return None, "找不到發動子句"
    return OPTIONAL_MANDATORY, activation


def _apply_optional(cid, section, clauses, attested, unsplit, judged, report):
    """必發/選發四層:官方明示 → 判定結果 → 日文發動子句規則 → 留 null 待判。

    官方明示的那批同時當獨立驗證集:遮住答案跑一次規則,一致率進報告。

    回傳**官方寫的那一批**的 `(section, index)`。重跑合併要靠它分辨這一格是官方
    的裁定還是規則層對當前文本的猜測——猜測可以重算,裁定不行(見 `_merge_clause`)。
    """
    official_optional = set()
    for clause in clauses:
        predicted, detail = _optional_by_rule(clause, unsplit)
        is_attested = clause["index"] in attested
        if is_attested:
            _validate_optional(cid, section, clause, predicted, detail, report)
        if clause["kind"] in SPELLTRAP_KINDS:
            # [[魔陷卡效果]]的必發/選發只在有觸發事件的發動句上有意義,而規則層的
            # 發動子句掃描分不出「卡本身發動」與「觸發型」——所以只吃官方明示與
            # 判定,不用規則補值,也不列待判:空著就是「這一句不帶此屬性」
            if is_attested:
                clause["optional"] = OPTIONAL_MANDATORY
                official_optional.add((section, clause["index"]))
                report["optional_official"] += 1
            elif judged.get(clause["index"]):
                clause["optional"] = judged[clause["index"]]
                report["optional_llm"] += 1
            continue
        if clause["kind"] not in ACTIVATED_KINDS:
            # 官方說必發、但類型還沒定(或定成不發動的類型)時一律不寫值——
            # 必發/選發的值域規則優先,類型定案後重跑會自然補上
            if is_attested and clause["kind"] is None:
                report["mandatory_kind_unknown"] += 1
            elif is_attested:
                report["mandatory_other_kind"].append(
                    {"id": cid, "section": section, "index": clause["index"],
                     "kind": clause["kind"]})
            if judged.get(clause["index"]):
                report["judgment_optional_dropped"].append(
                    {"id": cid, "section": section, "index": clause["index"],
                     "kind": clause["kind"],
                     "optional": judged[clause["index"]]})
            continue
        if is_attested:
            clause["optional"] = OPTIONAL_MANDATORY
            official_optional.add((section, clause["index"]))
            report["optional_official"] += 1
        elif judged.get(clause["index"]):
            clause["optional"] = judged[clause["index"]]
            report["optional_llm"] += 1
        elif predicted is not None:
            clause["optional"] = predicted
            report["optional_rule"] += 1
        else:
            report["optional_pending"].append(
                {"id": cid, "section": section, "index": clause["index"],
                 "reason": detail})
    return official_optional


def _validate_optional(cid, section, clause, predicted, detail, report):
    """官方說必發的效果句 → 遮住答案跑規則,記一致率與所有不一致的條目。"""
    validation = report["optional_validation"]
    validation["attested"] += 1
    if predicted is None:
        validation[_UNPREDICTED_KEYS[detail]] += 1
        return
    validation["predicted"] += 1
    if predicted == OPTIONAL_MANDATORY:
        validation["agree"] += 1
    else:
        validation["disagree"].append(
            {"id": cid, "section": section, "index": clause["index"],
             "predicted": predicted, "activation": detail})


# ---------------------------------------------------------------- 判定結果

def _index_judgments(judgments):
    """判定結果檔 → {(卡片密碼, section, index): 那一行的判定}。"""
    rows = {}
    for record in judgments or ():
        for row in record.get("clauses", ()):
            rows[(record["id"], record["section"], row["index"])] = row
    return rows


def _apply_judgments(cid, section, clauses, judgments, report):
    """判定結果 → 效果句上的 kind / role;回傳 {index: 判定給的必發/選發}。

    官方明示高於判定:一致時留 official(這一行不占 ADR-0002 的判定額度),不一致
    時保留判定並把這一行標 needs_review——呼叫端會把整張卡一起標,因為這條路徑上
    不一致的最可能成因是拆錯而不是判錯,只標一行會讓人去看錯的東西。

    位置規則已經定案的效果外文本段不被判定覆蓋,結論不同時只進報告。
    """
    judged = {}
    for clause in clauses:
        row = judgments.get((cid, section, clause["index"]))
        if row is None:
            continue
        if clause["source"] == official.SOURCE_OFFICIAL:
            if row.get("kind") and row["kind"] != clause["kind"]:
                report["late_official_conflicts"].append(_merge_row(
                    cid, clause, existing=row["kind"],
                    official=clause["kind"], source=SOURCE_LLM))
                clause["kind"] = row["kind"]
                clause["source"] = SOURCE_LLM
                clause["needs_review"] = True
                report["judgment_clauses"] += 1
            else:
                report["judgment_confirmed_by_official"] += 1
            # 兩道階梯各走各的:官方接手了[[效果類型]]不代表它也寫了[[必發/選發]]。
            # 舊式卡文常是「官方只給類型、卡文又沒有發動子句」,綁在一起會把判定者
            # 填的那一格連帶丟掉——票18 實測 200 張裡 20 條被留成 null
            judged[clause["index"]] = row.get("optional")
            continue
        if clause["kind"] is not None:
            if row.get("kind") != clause["kind"]:
                report["judgment_vs_rule"].append(_merge_row(
                    cid, clause, existing=clause["kind"],
                    judged=row.get("kind")))
            continue
        if not row.get("kind"):
            report["judgment_blank"].append(_merge_row(
                cid, clause, note=row.get("note") or ""))
            continue
        clause["kind"] = row["kind"]
        clause["role"] = row.get("role")
        clause["source"] = SOURCE_LLM
        report["judgment_clauses"] += 1
        judged[clause["index"]] = row.get("optional")
    return judged


def _report_judgment_orphans(entries, judgments, report):
    """結果檔涵蓋的效果句集合必須與標記表對得上;多出來的一筆就是判錯批次。"""
    present = {(entry["id"], clause["section"], clause["index"])
               for entry in entries for clause in entry["clauses"]}
    report["judgment_orphans"] = [
        {"id": cid, "section": section, "index": index}
        for cid, section, index in sorted(set(judgments) - present)]


# ---------------------------------------------------------------- 重跑合併

# 判定一次就算數的來源:人工修正、官方權威、判定票的產出。rule 不在其中——
# 它是當前規則層對當前文本的純函式輸出,規則改了就該重算(Story 49)。
PRESERVED_SOURCES = (SOURCE_MANUAL, official.SOURCE_OFFICIAL, SOURCE_LLM,
                     SOURCE_LLM_THEN_RULE)
# 改判(結果檔逐行帶 `rejudge`)動得了的來源。ADR-0002 的「判定一次就算數」講的是
# **重跑不覆蓋**,不是「判錯了也不能改」;規範改版後回頭修判定要一張自己的票,而
# 官方明示與人工修正的權威高於判定票,改判動不了它們(票52)。
REJUDGEABLE_SOURCES = (SOURCE_LLM, SOURCE_LLM_THEN_RULE)
# 沿用既有行時整組帶過來的判定欄位
JUDGED_FIELDS = ("kind", "optional", "role", "source", "tags")
# 官方明示能決定的欄位(tags 不在其列)
ATTESTED_FIELDS = ("kind", "optional", "role", "source")


def _index_existing(existing):
    """既有標記表 → {(卡片密碼, section, index): 效果句}。"""
    index = {}
    for entry in existing or ():
        for clause in entry.get("clauses", ()):
            index[(entry["id"], clause["section"], clause["index"])] = clause
    return index


def _judgment(clause):
    return tuple(clause.get(field) for field in ("kind", "optional", "role"))


def _judgment_text(clause):
    """判定的可讀摘要,給報告的差異列用(如「效果外文本/召喚條件」)。"""
    return "/".join(part for part in
                    (clause.get("kind") or "—", clause.get("role"),
                     clause.get("optional")) if part)


def _merge_row(cid, clause, **extra):
    return {"id": cid, "section": clause["section"], "index": clause["index"],
            **extra}


def _apply_late_attestation(cid, merged, fresh, prior, report):
    """遲到的官方明示:不沿用而是比對;回傳是否升為 official。

    補足情報是會成長的來源(官方替舊卡補寫、新卡的 Q&A 頁面陸續出現),因此
    既有判定碰上新出現的官方明示時,比對本身就是一次免費的準確率驗證。
    一致則 `source` 升為 official;不一致則保留原判定並列進衝突清單。
    人工修正即使一致也保留 manual 的來歷——那是使用者看過這一行的證據。
    """
    if prior["kind"] is not None and prior["kind"] != fresh["kind"]:
        report["late_official_conflicts"].append(_merge_row(
            cid, fresh, existing=prior["kind"], official=fresh["kind"],
            source=prior["source"]))
        return False
    if prior["source"] == SOURCE_MANUAL:
        return False
    for field in ATTESTED_FIELDS:
        # 類型既已確認一致,這一行整組改吃本次的官方+規則結果;但本次算不出來的
        # 欄位(如規則抓不到發動子句的 optional)不把既有的值洗成 null
        if fresh[field] is not None or merged[field] is None:
            merged[field] = fresh[field]
    report["late_official_upgrades"] += 1
    return True


def _merge_clause(cid, fresh, prior, official_optional, report,
                  rejudge=False):
    """本次重跑的效果句 + 既有標記表的同一行 → 寫進標記表的那一行。

    首次建置時 prior 一律是 None,與重跑走同一條路徑。文本欄位(text_zh /
    text_ja / text_hash)與規則層欄位(rule_predicted / confidence)永遠取本次
    的值——它們是來源資料的投影,不是判定。

    `official_optional` 是本次由[[官方明示]]寫出[[必發/選發]]的 `(section, index)`。
    `rejudge` 是結果檔在這一行寫了改判旗標,見 `REJUDGEABLE_SOURCES`。
    """
    prior_source = prior.get("source") if prior else None
    if prior_source not in PRESERVED_SOURCES:
        if prior_source == SOURCE_RULE and _judgment(fresh) != _judgment(prior):
            report["rule_changed"].append(_merge_row(
                cid, fresh, existing=_judgment_text(prior),
                rebuilt=_judgment_text(fresh)))
        return fresh

    if (prior_source == official.SOURCE_OFFICIAL
            and fresh["source"] == official.SOURCE_OFFICIAL):
        # 官方改了自己的裁定:兩邊同權威,以最新的來源資料為準。但**只管官方這次
        # 真的寫了的欄位**——官方多半只寫[[效果類型]]不寫[[必發/選發]],那一格是
        # 判定票依 §4 階梯二填的,本次算出來的是[[規則層]]對當前文本的猜測。整行
        # 換掉會把判定翻掉、還冒充成官方改了裁定(票18 實測一次重跑翻掉 22 條)
        merged = dict(fresh)
        for field in ATTESTED_FIELDS:
            if fresh[field] is None and prior.get(field) is not None:
                merged[field] = prior[field]
        if ((fresh["section"], fresh["index"]) not in official_optional
                and prior.get("optional") is not None):
            merged["optional"] = prior["optional"]
        if _judgment(merged) != _judgment(prior):
            report["official_changed"].append(_merge_row(
                cid, fresh, existing=_judgment_text(prior),
                official=_judgment_text(merged)))
        return merged

    if rejudge and fresh["source"] == SOURCE_LLM:
        # 改判票:這一行的既有判定是要被換掉的東西,不是要被保留的東西。值本來就
        # 相同時什麼都不做也不報告——改判票與其他票一樣要能單獨重跑(Story 39)
        changed = _judgment(fresh) != _judgment(prior)
        row = _merge_row(cid, fresh, existing=_judgment_text(prior),
                         judged=_judgment_text(fresh), source=prior_source)
        if prior_source in REJUDGEABLE_SOURCES:
            if changed:
                report["judgment_rejudged"].append(row)
            # [[效果 Tag]]是另一條軸,不隨效果類型改判而消失
            return {**fresh, "tags": prior.get("tags", fresh["tags"])}
        if changed:
            # 官方明示與人工修正改判動不了,而且默默擋掉會讓改判票以為改上去了。
            # 這一行接下來照既有那一行保留,底下的 judgment_overridden 不必再說
            # 一次同一件事
            report["judgment_rejudge_refused"].append(row)

    if (fresh["source"] == SOURCE_LLM and not rejudge
            and _judgment(fresh) != _judgment(prior)):
        # 本次的判定被既有那一行擋下來(ADR-0002:判定一次就算數)。要是判定票是
        # 回頭重判的,靜靜擋掉會讓人以為改上去了,所以這一筆必須看得見
        report["judgment_overridden"].append(_merge_row(
            cid, fresh, existing=_judgment_text(prior),
            judged=_judgment_text(fresh), source=prior["source"]))

    merged = dict(fresh)
    for field in JUDGED_FIELDS:
        merged[field] = prior.get(field, fresh[field])
    # 本次才標上的旗標(判定與官方明示打架)不會被既有那一行的乾淨狀態洗掉
    merged["needs_review"] = bool(prior.get("needs_review")
                                  or fresh["needs_review"])
    upgraded = (fresh["source"] == official.SOURCE_OFFICIAL
                and _apply_late_attestation(cid, merged, fresh, prior, report))
    if not upgraded:
        report["preserved_judgments"] += 1

    hash_changed = fresh["text_hash"] != prior.get("text_hash")
    if hash_changed:
        # 這一行的身分已經改變,但判定是使用者/官方/判定票的成果,不覆蓋
        merged["needs_review"] = True
    if merged["needs_review"]:
        report["needs_review"].append(_merge_row(
            cid, merged, source=merged["source"], kind=merged["kind"],
            hash_changed=hash_changed))
    return merged


def _merge_clauses(cid, clauses, existing_index, matched, official_optional,
                   judgments, report):
    merged = []
    for clause in clauses:
        key = (cid, clause["section"], clause["index"])
        if key in existing_index:
            matched.add(key)
        rejudge = bool((judgments.get(key) or {}).get("rejudge"))
        merged.append(_merge_clause(cid, clause, existing_index.get(key),
                                    official_optional, report,
                                    rejudge=rejudge))
    return merged


def _report_orphans(existing_index, matched, entries, report):
    """既有標記表裡對不到任何一行的判定——拆句法變動時使用者的修正會落在這裡。

    前言段被重拆成 `0-1`、`0-2`…的卡,舊的官方明示前言列(`"0"`)不算孤兒:
    官方明示每次重跑都由補足情報重算,已改落在新的細段上,沒有人工成果被丟掉
    (ADR-0009;前言列的 source 只有 rule 與 official,零 manual)。
    """
    resplit = {(entry["id"], clause["section"]) for entry in entries
               for clause in entry["clauses"]
               if clause["index"].startswith(INDEX_PREAMBLE + "-")}
    for key, clause in existing_index.items():
        if key in matched or clause.get("source") not in PRESERVED_SOURCES:
            continue
        cid, section, index = key
        if (official._is_preamble(index)
                and clause["source"] == official.SOURCE_OFFICIAL
                and (cid, section) in resplit):
            continue
        report["orphaned_judgments"].append(
            {"id": cid, "section": section, "index": index,
             "source": clause["source"], "kind": clause.get("kind")})
    report["orphaned_judgments"].sort(
        key=lambda row: (row["id"], row["section"], row["index"]))


# ------------------------------------------------- 效果類型規則層(影子預測)

def _rule_targets(entries):
    """規則層的管轄範圍:有日文原文的效果句。

    前言段不在其中——它的類型由位置規則決定(第一個效果編號之前的段落即
    效果外文本),不是歸納出來的效果類型規則管得到的事。
    """
    for entry in entries:
        for clause in entry["clauses"]:
            if not official._is_preamble(clause["index"]) and clause["text_ja"]:
                yield entry["id"], clause


def _bullet_leads(entries):
    """{(卡片密碼, section, ● 子效果 index): 領起句的日文原文}。

    `●` 拆成獨立效果句之後,「這個 `●` 底下的發動寫在哪裡」只有領起句那一行答得
    出來,而規則層一次只看一條效果句(票61)。領起句不存在時記空字串——「看不到
    領起句」與「這一行不是 `●` 子效果」是兩件事,帶 lead 前提的規則要分得出來。
    """
    leads = {}
    for entry in entries:
        by_index = {(c["section"], c["index"]): c for c in entry["clauses"]}
        for clause in entry["clauses"]:
            head, sep, _ = clause["index"].partition(f"-{BULLET}")
            if not sep:
                continue
            lead = by_index.get((clause["section"], head))
            leads[(entry["id"], clause["section"], clause["index"])] = (
                lead["text_ja"] if lead else "")
    return leads


def _rule_row(cid, clause, rule_ids, **extra):
    return {"id": cid, "section": clause["section"], "index": clause["index"],
            "rules": rule_ids, **extra}


def _compare_prediction(cid, clause, rule_ids, report):
    """影子預測 × 既有判定:一致的升級、不一致的列清單,兩種都不動判定。

    官方明示那批走的是另一條路——它們是規則層的驗證集而不是被規則檢查的對象,
    一致率進報告的獨立驗證,不一致列進獨立的清單(與 票04 必發/選發的驗證同一
    個做法)。判定票的產出(llm)才是 ADR-0002 所說的獨立對照。
    """
    predicted = clause["rule_predicted"]
    kind, source = clause["kind"], clause["source"]
    if kind in SPELLTRAP_KINDS:
        # 規則層歸納的是怪獸效果的六類;判成[[魔陷卡效果]]的行不在其管轄範圍,
        # 影子預測留著(換規範前的痕跡)但不比對、不升級(ADR-0004)。官方明示
        # 也寫得出這一族的值(票56),所以這道範圍閘門在官方分支之前
        report["rule_spelltrap_skipped"] += 1
        return
    if source == official.SOURCE_OFFICIAL:
        for rule_id in rule_ids:
            counts = report["rule_validation"][rule_id]
            counts["attested"] += 1
            counts["agree" if kind == predicted else "disagree"] += 1
        if kind != predicted:
            report["rule_official_disagree"].append(_rule_row(
                cid, clause, rule_ids, official=kind, predicted=predicted))
        return
    if kind is None:
        return  # 尚未判定:只留影子預測,類型仍等判定票決定(ADR-0002)
    if kind != predicted:
        report["rule_conflicts"].append(_rule_row(
            cid, clause, rule_ids, existing=kind, predicted=predicted,
            source=source))
    elif source == SOURCE_LLM:
        # 判定與規則各自到達同一個結論:這一行從此是雙重確認的
        clause["source"] = SOURCE_LLM_THEN_RULE
        report["rule_upgrades"] += 1


def _predict(cid, clause, matched, report):
    """一個效果句 → 影子預測。多條規則結論不同時不寫,那是規則層該修了。"""
    if not matched:
        return
    rule_ids = [rule["id"] for rule in matched]
    kinds = {rule["kind"] for rule in matched}
    if len(kinds) > 1:
        # 判別條件重疊且結論不同:規則層自相矛盾,不猜哪一條對
        report["rule_overlaps"].append(_rule_row(
            cid, clause, rule_ids, kinds=sorted(kinds)))
        return
    clause["rule_predicted"] = kinds.pop()
    report["rule_predictions"] += 1
    if clause["kind"] is None:
        # 判定票要吃的就是這一批:有影子預測、但類型仍待判定的行
        report["rule_predictions_pending"] += 1
    _compare_prediction(cid, clause, rule_ids, report)


def _apply_rules(entries, existing_index, report):
    """規則層跑兩趟:先量覆蓋條數,再讓覆蓋足夠的規則寫影子預測。

    覆蓋條數必須由本次全表算出來(票06「不靠人工計數」),而門檻要在寫預測之前
    就知道,所以量與寫不能合成一趟。規則清單本身有毛病時整層不上工——寧可沒有
    影子預測,也不要拿一份自己都對不起來的規則去對照判定。
    """
    report["rules_problems"] = rules.problems()
    registry = [] if report["rules_problems"] else rules.active()
    leads = _bullet_leads(entries)
    targets = []
    for cid, clause in _rule_targets(entries):
        key = (cid, clause["section"], clause["index"])
        targets.append((cid, clause, existing_index.get(key), rules.matching(
            clause["text_ja"], _activation_clause(clause["text_ja"]),
            registry, leads.get(key))))

    report["rule_targets"] = len(targets)
    coverage = Counter()
    for _, _, _, matched in targets:
        coverage.update(rule["id"] for rule in matched)
    applied = {rule["id"] for rule in registry
               if coverage[rule["id"]] >= rules.MIN_COVERAGE}
    report["rule_validation"] = {
        rule_id: {"attested": 0, "agree": 0, "disagree": 0}
        for rule_id in applied}

    for cid, clause, prior, matched in targets:
        matched = [rule for rule in matched if rule["id"] in applied]
        _predict(cid, clause, matched, report)
        before = prior.get("rule_predicted") if prior else None
        if before != clause["rule_predicted"]:
            # 規則一改,全表重跑後的逐行差異就在這裡(Story 49 / 票06)
            report["rule_prediction_changed"].append(_rule_row(
                cid, clause, [rule["id"] for rule in matched], before=before,
                after=clause["rule_predicted"]))

    report["rules"] = [_registry_row(rule, coverage, applied, report)
                       for rule in rules.RULES]
    report["rule_below_threshold"] = [
        row["id"] for row in report["rules"]
        if not row["merged_into"] and not row["applied"]]
    # 分母下限只問上工中的規則:被合併或覆蓋不足的那些本來就不寫影子預測,
    # 沒有驗證基礎也影響不到任何一行(票12)
    report["rule_below_attested"] = [
        row["id"] for row in report["rules"]
        if row["applied"] and row["attested"] < rules.MIN_ATTESTED]


def _registry_row(rule, coverage, applied, report):
    """一條規則在本次全表的成績,給報告與 docs/effect_kind_rules.md 用。

    `merged_into` 有值代表這一條已被合併、退出規則層;`applied` 代表它本輪確實
    上工(未被合併,且覆蓋條數過門檻)。兩者都不是就是覆蓋不足。
    """
    validation = report["rule_validation"].get(
        rule["id"], {"attested": 0, "agree": 0, "disagree": 0})
    return {"id": rule["id"], "kind": rule["kind"], "scope": rule["scope"],
            "condition": rule["condition"], "ticket": rule["ticket"],
            "changes": rule["changes"], "merged_into": rule["merged_into"],
            "applied": rule["id"] in applied,
            "coverage": coverage[rule["id"]], **validation}


def _new_report():
    return {
        "cards": 0,
        "clauses": 0,
        "preambles": 0,
        "pure_normal": 0,
        "flavor_dropped": 0,
        "pendulum_sections": 0,
        "footnote_stripped": 0,
        "role_counts": {ROLE_MATERIAL: 0, ROLE_SUMMON: 0, ROLE_USAGE: 0,
                        "null": 0},
        "preamble_splits": 0,
        "preamble_split_clauses": 0,
        "preamble_split_fallbacks": [],
        "pending_split": [],
        "numeral_mismatch": [],
        "numeral_relabelled": [],
        "preamble_one_sided": [],
        "no_japanese_text": [],
        "zh_judged_clauses": 0,
        "empty_section_with_japanese": [],
        "low_confidence": [],
        "pendulum_bit_without_header": [],
        "header_without_pendulum_bit": [],
        "normal_with_numerals": [],
        "duplicate_index": [],
        "substring_violations": [],
        "zh_cut_rule_disagree": 0,
        "split_records": 0,
        "split_clauses": 0,
        "split_new_official": 0,
        "split_malformed": [],
        "split_stale": [],
        "split_coverage_failed": [],
        "split_quote_violations": [],
        "split_unused": [],
        "judgment_clauses": 0,
        "judgment_confirmed_by_official": 0,
        "judgment_blank": [],
        "judgment_vs_rule": [],
        "judgment_optional_dropped": [],
        "judgment_overridden": [],
        "judgment_rejudged": [],
        "judgment_rejudge_refused": [],
        "judgment_orphans": [],
        "rule_spelltrap_skipped": 0,
        "official_clauses": 0,
        "official_coverage": {ladder: 0 for ladder in official.LADDERS},
        "kind_counts": {kind: 0
                        for kind in official.KINDS + official.SPELLTRAP_KINDS},
        "optional_counts": {OPTIONAL_MANDATORY: 0, OPTIONAL_OPTIONAL: 0,
                            "null": 0},
        "optional_official": 0,
        "optional_llm": 0,
        "optional_rule": 0,
        "optional_pending": [],
        "kind_missing": [],
        "optional_on_wrong_kind": [],
        "role_on_wrong_kind": [],
        "mandatory_kind_unknown": 0,
        "mandatory_other_kind": [],
        "optional_validation": {
            "attested": 0, "predicted": 0, "agree": 0, "disagree": [],
            **{key: 0 for key in _UNPREDICTED_KEYS.values()}},
        "bullet_clauses": 0,
        "bullet_quote_splits": 0,
        "bullet_split_mismatch": [],
        "bullet_coverage_failed": [],
        "bullet_quote_violations": [],
        "source_counts": {**{source: 0 for source in SOURCES}, "null": 0},
        "preserved_judgments": 0,
        "needs_review": [],
        "late_official_upgrades": 0,
        "late_official_conflicts": [],
        "official_changed": [],
        "rule_changed": [],
        "orphaned_judgments": [],
        "rules": [],
        "rules_digest": rules.digest(),
        "rules_problems": [],
        "rule_targets": 0,
        "rule_predictions": 0,
        "rule_predictions_pending": 0,
        "rule_upgrades": 0,
        "rule_conflicts": [],
        "rule_official_disagree": [],
        "rule_overlaps": [],
        "rule_prediction_changed": [],
        "rule_below_threshold": [],
        "rule_below_attested": [],
        "rule_validation": {},
        **{key: [] for key in official.NOTE_KEYS},
    }


def _build_section(card, section, zh_text, ja_text, supplement, name_ja,
                   split, judgments, report):
    """單一段落 → 效果句清單。繁中負責拆句,日文靠編號序列對位。

    split 是這一段的[[拆句表]]紀錄(沒有則為 None),judgments 是全表的判定結果
    索引。兩者的生效時機夾著官方明示的抽取:拆句在前,判定在後(ADR-0003)。
    """
    cid = card["id"]
    ctype = card.get("type", 0)
    confidence = CONFIDENCE_HIGH if supplement else CONFIDENCE_LOW
    zh_pre, zh_nums, zh_all = _segments(zh_text)
    ja_pre, ja_nums, ja_all = _segments(ja_text)

    if zh_pre is None and zh_all is None and not zh_nums:
        if ja_text.strip():
            report["empty_section_with_japanese"].append(
                {"id": cid, "section": section})
        return [], set()

    # 對位:編號數量相同才逐段配對,任何不一致都不猜測
    aligned = bool(ja_text.strip()) and len(zh_nums) == len(ja_nums)
    if not ja_text.strip():
        if cid not in report["no_japanese_text"]:
            report["no_japanese_text"].append(cid)
    elif not aligned:
        report["numeral_mismatch"].append(
            {"id": cid, "section": section,
             "zh": "".join(n for n, _ in zh_nums),
             "ja": "".join(n for n, _ in ja_nums)})

    labels = [n for n, _ in zh_nums]
    if aligned and len(set(labels)) != len(labels):
        ja_labels = [n for n, _ in ja_nums]
        if len(set(ja_labels)) == len(ja_labels):
            # 繁中誤植重複編號(來源資料 2 張):取日文編號保住鍵的唯一性
            report["numeral_relabelled"].append(
                {"id": cid, "section": section, "zh": "".join(labels),
                 "ja": "".join(ja_labels)})
            labels = ja_labels

    def preamble_clause(index, text_zh, text_ja):
        role = _preamble_role(text_zh, ctype)
        report["preambles"] += 1
        report["role_counts"][role or "null"] += 1
        return _clause(index, section, text_zh, text_ja, confidence,
                       kind=KIND_NON_EFFECT, role=role, source=SOURCE_RULE)

    clauses = []
    if zh_pre is not None:
        if aligned and ja_pre is None:
            report["preamble_one_sided"].append(
                {"id": cid, "section": section, "present": "zh"})
        zh_body = _slice(zh_text, zh_pre)
        ja_body = _slice(ja_text, ja_pre) if aligned else ""
        pairs, fallback = (_split_preamble(zh_body, ja_body, supplement)
                           if ja_body else (None, None))
        if pairs is not None:
            clauses.extend(
                preamble_clause(f"{INDEX_PREAMBLE}-{pos}",
                                _slice(zh_body, zh_span),
                                _slice(ja_body, ja_span))
                for pos, (zh_span, ja_span) in enumerate(pairs, start=1))
            report["preamble_splits"] += 1
            report["preamble_split_clauses"] += len(pairs)
        else:
            if fallback is not None:
                report["preamble_split_fallbacks"].append(
                    {"id": cid, "section": section, "text_zh": zh_body,
                     "text_ja": ja_body, "reason": fallback})
            clauses.append(preamble_clause(INDEX_PREAMBLE, zh_body, ja_body))
    elif aligned and ja_pre is not None:
        report["preamble_one_sided"].append(
            {"id": cid, "section": section, "present": "ja"})

    for pos, (_, span) in enumerate(zh_nums):
        ja_span = ja_nums[pos][1] if aligned else None
        clauses.append(_clause(labels[pos], section, _slice(zh_text, span),
                               _slice(ja_text, ja_span), confidence))

    unsplit = set()
    split_indexes = set()
    if zh_all is not None:
        blob = _clause(INDEX_UNNUMBERED, section, _slice(zh_text, zh_all),
                       _slice(ja_text, ja_all) if aligned else "", confidence)
        segments = None if split is None else _apply_split(
            cid, section, split, blob, ctype, supplement, report)
        if segments is None:
            # 無編號舊式卡文還沒拆:整團先當單一效果句,語意拆分交給判定者。
            # 待拆清單帶著整團的兩側原文與雜湊,因為 ● 待會可能把這一行切掉一塊
            # ——批次檔要給判定者看的、與拆句表要對的,都是這裡這一份整團
            clauses.append(blob)
            report["pending_split"].append(
                {"id": cid, "section": section, "text_zh": blob["text_zh"],
                 "text_ja": blob["text_ja"],
                 "text_hash": split_hash(blob["text_zh"], blob["text_ja"])})
            unsplit.add(INDEX_UNNUMBERED)
        else:
            clauses.extend(segments)
            split_indexes = {clause["index"] for clause in segments}
    elif split is not None:
        report["split_unused"].append({"id": cid, "section": section})

    clauses = _split_bullets(cid, section, clauses, supplement, report)
    if split_indexes:
        # 整團是這一段唯一的效果句(無編號才會有整團),所以拆完之後這一段的每一行
        # 都出自拆句表——● 又把某一段拆得更細時,新的 index 也算在內
        split_indexes = {clause["index"] for clause in clauses}
    attested = _apply_attestations(cid, section, clauses, name_ja, supplement,
                                   unsplit, split_indexes, report)
    judged = _apply_judgments(cid, section, clauses, judgments, report)
    official_optional = _apply_optional(cid, section, clauses, attested,
                                        unsplit, judged, report)
    return clauses, official_optional


def _dedupe_indexes(cid, clauses, report):
    """(卡片密碼, section, index) 必須唯一;真的撞了就加尾碼並列進報告。"""
    seen = set()
    for clause in clauses:
        key = (clause["section"], clause["index"])
        if key not in seen:
            seen.add(key)
            continue
        report["duplicate_index"].append({
            "id": cid, "section": clause["section"], "index": clause["index"]})
        suffix = 2
        while (clause["section"], f"{clause['index']}-{suffix}") in seen:
            suffix += 1
        clause["index"] = f"{clause['index']}-{suffix}"
        seen.add((clause["section"], clause["index"]))


def _check_substrings(cid, clauses, desc, ja_texts, report):
    for clause in clauses:
        if clause["text_zh"] not in desc:
            report["substring_violations"].append(
                {"id": cid, "index": clause["index"], "side": "zh"})
        haystack = ja_texts.get(clause["section"], "")
        if clause["text_ja"] and clause["text_ja"] not in haystack:
            report["substring_violations"].append(
                {"id": cid, "index": clause["index"], "side": "ja"})


def _count_clauses(entries, report):
    """全表的欄位統計。

    規則層會把比對一致的 `llm` 行升成 `llm_then_rule`,所以來源分布必須等它跑完
    才數,否則報告印的是升級前的數字。
    """
    zh_judged = set(report["no_japanese_text"])
    for entry in entries:
        if entry["id"] in zh_judged:
            # 無官方日文文本那批的效果句數(ADR-0006):判定基礎是繁中卡文,
            # 沒有官方明示也沒有影子預測,票09 的定版報告要單獨列出來
            report["zh_judged_clauses"] += len(entry["clauses"])
        for clause in entry["clauses"]:
            if clause["kind"] is not None:
                report["kind_counts"][clause["kind"]] += 1
            report["optional_counts"][clause["optional"] or "null"] += 1
            report["source_counts"][clause["source"] or "null"] += 1
            key = {"id": entry["id"], "section": clause["section"],
                   "index": clause["index"]}
            if clause["kind"] is None:
                # 還沒判的效果句。定版時必須是空的——「已處理且確實沒有效果」由
                # 純通常怪獸的空 clauses 表達,不是由 kind 留 null 表達(票09)
                report["kind_missing"].append(key)
            if (clause["optional"] is not None
                    and clause["kind"] not in OPTIONAL_KINDS):
                report["optional_on_wrong_kind"].append(key)
            if clause["role"] is not None and clause["kind"] != KIND_NON_EFFECT:
                # role 是效果外文本的子分類,別的類型上有值就是填錯欄位
                report["role_on_wrong_kind"].append(key)
        report["clauses"] += len(entry["clauses"])


def build_tag_cards(cards, faq_entries, existing=None, judgments=None,
                    splits=None):
    """卡片總表 + 補足情報 → (效果標記表條目, 報告)。

    cards: 卡片總表條目(需 id / desc / type)。
    faq_entries: 補足情報條目(需 password,取 card_text / supplement /
        pen_effect / pen_supplement)。
    existing: 既有標記表(上一次的輸出)。以 (卡片密碼, section, index) 對應回
        既有行,保留已判定的成果;首次建置傳 None,兩者走同一條路徑。
        效果類型規則層的影子預測在合併之後才跑,因此既有判定與本次規則的比對
        (升為 llm_then_rule、或列進衝突清單)看的是合併後的那一行。
    judgments: 判定結果,一卡一物件、內含 clauses。決定效果句上的**值**
        (kind / optional / role),在官方明示抽取**之後**合併。
    splits: 拆句表,一張卡一筆、鍵為 (卡片密碼, section)。決定效果句的**集合**,
        在官方明示抽取**之前**生效——拆完才對得出歸屬(ADR-0003)。
    """
    report = _new_report()
    existing_index = _index_existing(existing)
    split_index = _index_splits(splits)
    judgment_index = _index_judgments(judgments)
    matched = set()

    faq_by_password = {e["password"]: e for e in faq_entries
                       if e.get("password") is not None}
    entries = []
    for card in sorted(cards, key=lambda c: c["id"]):
        cid = card["id"]
        ctype = card.get("type", 0)
        desc = card.get("desc") or ""
        report["cards"] += 1

        stripped = FOOTNOTE_RE.sub("", desc)
        if stripped != desc:
            report["footnote_stripped"] += 1

        faq = faq_by_password.get(cid, {})
        ja_by_section = {
            SECTION_MAIN: faq.get("card_text") or "",
            SECTION_PENDULUM: faq.get("pen_effect") or "",
        }
        supplement_by_section = {
            SECTION_MAIN: faq.get("supplement") or "",
            SECTION_PENDULUM: faq.get("pen_supplement") or "",
        }
        name_ja = faq.get("name_ja") or card.get("name_ja") or ""

        sections, flavor_dropped = _zh_sections(stripped)
        if flavor_dropped:
            report["flavor_dropped"] += 1
        has_pendulum_section = any(s == SECTION_PENDULUM for s, _ in sections)
        if has_pendulum_section:
            report["pendulum_sections"] += 1
            if not ctype & TYPE_PENDULUM:
                report["header_without_pendulum_bit"].append(cid)
        elif ctype & TYPE_PENDULUM:
            report["pendulum_bit_without_header"].append(cid)

        # 純通常怪獸:已處理且確實沒有效果,clauses 為空陣列
        pure_normal = (ctype & TYPE_MONSTER and ctype & TYPE_NORMAL
                       and not ctype & TYPE_PENDULUM)
        if pure_normal:
            report["pure_normal"] += 1
            if _cut_points(stripped):
                report["normal_with_numerals"].append(cid)
            entries.append({"id": cid, "clauses": []})
            continue

        clauses = []
        official_optional = set()
        for section, text in sections:
            if _line_start_cut_points(text) != _cut_points(text):
                report["zh_cut_rule_disagree"] += 1
            built, attested_optional = _build_section(
                card, section, text, ja_by_section[section],
                supplement_by_section[section], name_ja,
                split_index.get((cid, section)), judgment_index, report)
            clauses.extend(built)
            official_optional |= attested_optional
        _dedupe_indexes(cid, clauses, report)
        if any(clause["needs_review"] for clause in clauses):
            # 判定與官方明示打架時最可能是拆錯,整張卡都要看而不只是那一行
            for clause in clauses:
                clause["needs_review"] = True
        clauses = _merge_clauses(cid, clauses, existing_index, matched,
                                 official_optional, judgment_index, report)
        _check_substrings(cid, clauses, desc, ja_by_section, report)
        if any(c["confidence"] == CONFIDENCE_LOW for c in clauses):
            report["low_confidence"].append(cid)
        entries.append({"id": cid, "clauses": clauses})

    _report_orphans(existing_index, matched, entries, report)
    _report_judgment_orphans(entries, judgment_index, report)
    _apply_rules(entries, existing_index, report)
    _count_clauses(entries, report)
    report["no_japanese_text"].sort()
    report["low_confidence"].sort()
    return entries, report


def serialize_tag_cards(entries):
    """效果標記表 → JSON 文字(indent=2、不 escape 中文、保留結尾換行)。"""
    return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
