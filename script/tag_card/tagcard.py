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
                      OPTIONAL_MANDATORY, OPTIONAL_OPTIONAL)

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
# 這些怪獸的卡文第一行是素材指定(卡文的硬性寫作慣例)
MATERIAL_TYPES = TYPE_FUSION | TYPE_RITUAL | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK

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

HEAD_PENDULUM = "【靈擺效果】"
HEAD_MONSTER_RE = re.compile(r"【怪獸(效果|敘述|描述)】")
# 通常怪獸的敘述段。來源資料有一張寫成「描述」,只認「敘述」會漏掉。
FLAVOR_HEADS = ("敘述", "描述")
# 繁中來源在卡文尾端附的別名註記(如「\n\n※白銀之城的狂時鐘」),不是卡文本體
FOOTNOTE_RE = re.compile(r"\n\n※[^\n]*$")

CLAUSE_FIELDS = ("index", "section", "text_zh", "text_ja", "text_hash", "kind",
                 "optional", "role", "source", "needs_review", "rule_predicted",
                 "confidence", "tags")


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

def _text_hash(text_ja):
    """日文原文的雜湊(身分變動偵測用);無日文原文時為 None。"""
    if not text_ja:
        return None
    return hashlib.sha1(text_ja.encode("utf-8")).hexdigest()[:16]


def _clause(index, section, text_zh, text_ja, confidence,
            kind=None, role=None, source=None):
    return {
        "index": index,
        "section": section,
        "text_zh": text_zh,
        "text_ja": text_ja,
        "text_hash": _text_hash(text_ja),
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


# ---------------------------------------------------------------- ● 子效果

def _bullet_parts(text):
    """文字 → (第一個 ● 之前的段落, [● 分項, ...]);兩者都已去首尾空白。"""
    positions = [i for i, ch in enumerate(text) if ch == BULLET]
    if not positions:
        return text.strip(), []
    bounds = list(zip(positions, positions[1:] + [len(text)]))
    return text[:positions[0]].strip(), [text[s:e].strip() for s, e in bounds]


def _bullet_authorised(clause, supplement, headers):
    """官方認可這一段的 ● 是獨立子效果嗎?兩種依據,證據強度相同。

    官方都是拿整個 `●` 當一個東西在講:`【●…について】` 標頭(票03),或行內
    `『●…』` 引用逐項給裁定(票16)。後者只對**賦予型領起句**開火——領起句自己
    就寫了發動時 `●` 只是同一個發動的選項列舉,拆了反而製造出官方沒有認可的
    效果句,而票14 實測那一族的官方類型本來就是對的。
    """
    if headers:
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
    if clause["index"] == INDEX_PREAMBLE or BULLET not in both:
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


def _validate_split(record, blob, supplement):
    """拆句表的一筆 → ({側: 各段 span}, None) 或 (None, 不能用的理由)。

    順序即優先序:結構不合法 → 卡文已變動 → 覆蓋不成立 → 引用被切開。**驗證三・
    卡文變動即失效**走的是前兩道,一律退回整團而不保留舊拆點——保留失效的斷言會讓
    歸屬階梯在假前提上開火,那正是票11 的錯誤。
    """
    segments = record.get("segments") or ()
    indexes = [segment.get("index") for segment in segments]
    if (not segments or not record.get("text_hash")
            or len(set(indexes)) != len(indexes)
            or any(not _SPLIT_INDEX_RE.match(index or "")
                   for index in indexes)):
        return None, ("split_malformed", {})
    if record["text_hash"] != split_hash(blob["text_zh"], blob["text_ja"]):
        return None, ("split_stale", {})
    spans = {}
    for side in ("zh", "ja"):
        spans[side] = _cover_spans(
            blob[f"text_{side}"],
            [segment.get(f"text_{side}", "") for segment in segments])
        if spans[side] is None:
            return None, ("split_coverage_failed", {"side": side})
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
    if _ACTIVATION_MARK not in activation:
        return None, "找不到發動子句"
    return OPTIONAL_MANDATORY, activation


def _apply_optional(cid, section, clauses, attested, unsplit, judged, report):
    """必發/選發四層:官方明示 → 判定結果 → 日文發動子句規則 → 留 null 待判。

    官方明示的那批同時當獨立驗證集:遮住答案跑一次規則,一致率進報告。
    """
    for clause in clauses:
        predicted, detail = _optional_by_rule(clause, unsplit)
        is_attested = clause["index"] in attested
        if is_attested:
            _validate_optional(cid, section, clause, predicted, detail, report)
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
                judged[clause["index"]] = row.get("optional")
            else:
                report["judgment_confirmed_by_official"] += 1
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


def _merge_clause(cid, fresh, prior, report):
    """本次重跑的效果句 + 既有標記表的同一行 → 寫進標記表的那一行。

    首次建置時 prior 一律是 None,與重跑走同一條路徑。文本欄位(text_zh /
    text_ja / text_hash)與規則層欄位(rule_predicted / confidence)永遠取本次
    的值——它們是來源資料的投影,不是判定。
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
        # 官方改了自己的裁定:兩邊同權威,以最新的來源資料為準
        if _judgment(fresh) != _judgment(prior):
            report["official_changed"].append(_merge_row(
                cid, fresh, existing=_judgment_text(prior),
                official=_judgment_text(fresh)))
        return fresh

    if fresh["source"] == SOURCE_LLM and _judgment(fresh) != _judgment(prior):
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


def _merge_clauses(cid, clauses, existing_index, matched, report):
    merged = []
    for clause in clauses:
        key = (cid, clause["section"], clause["index"])
        if key in existing_index:
            matched.add(key)
        merged.append(_merge_clause(cid, clause, existing_index.get(key),
                                    report))
    return merged


def _report_orphans(existing_index, matched, report):
    """既有標記表裡對不到任何一行的判定——拆句法變動時使用者的修正會落在這裡。"""
    for key, clause in existing_index.items():
        if key in matched or clause.get("source") not in PRESERVED_SOURCES:
            continue
        cid, section, index = key
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
            if clause["index"] != INDEX_PREAMBLE and clause["text_ja"]:
                yield entry["id"], clause


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
    targets = []
    for cid, clause in _rule_targets(entries):
        prior = existing_index.get((cid, clause["section"], clause["index"]))
        targets.append((cid, clause, prior, rules.matching(
            clause["text_ja"], _activation_clause(clause["text_ja"]),
            registry)))

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
        "pending_split": [],
        "numeral_mismatch": [],
        "numeral_relabelled": [],
        "preamble_one_sided": [],
        "no_japanese_text": [],
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
        "judgment_orphans": [],
        "official_clauses": 0,
        "official_coverage": {ladder: 0 for ladder in official.LADDERS},
        "kind_counts": {kind: 0 for kind in official.KINDS},
        "optional_counts": {OPTIONAL_MANDATORY: 0, OPTIONAL_OPTIONAL: 0,
                            "null": 0},
        "optional_official": 0,
        "optional_llm": 0,
        "optional_rule": 0,
        "optional_pending": [],
        "optional_on_wrong_kind": [],
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
        return []

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

    clauses = []
    if zh_pre is not None:
        if aligned and ja_pre is None:
            report["preamble_one_sided"].append(
                {"id": cid, "section": section, "present": "zh"})
        text_zh = _slice(zh_text, zh_pre)
        role = _preamble_role(text_zh, ctype)
        clauses.append(_clause(
            INDEX_PREAMBLE, section, text_zh,
            _slice(ja_text, ja_pre) if aligned else "",
            confidence, kind=KIND_NON_EFFECT, role=role, source=SOURCE_RULE))
        report["preambles"] += 1
        report["role_counts"][role or "null"] += 1
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
            # 無編號舊式卡文還沒拆:整團先當單一效果句,語意拆分交給判定者
            clauses.append(blob)
            report["pending_split"].append({"id": cid, "section": section})
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
    _apply_optional(cid, section, clauses, attested, unsplit, judged, report)
    return clauses


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
    for entry in entries:
        for clause in entry["clauses"]:
            if clause["kind"] is not None:
                report["kind_counts"][clause["kind"]] += 1
            report["optional_counts"][clause["optional"] or "null"] += 1
            report["source_counts"][clause["source"] or "null"] += 1
            if (clause["optional"] is not None
                    and clause["kind"] not in ACTIVATED_KINDS):
                report["optional_on_wrong_kind"].append(
                    {"id": entry["id"], "section": clause["section"],
                     "index": clause["index"]})
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
        for section, text in sections:
            if _line_start_cut_points(text) != _cut_points(text):
                report["zh_cut_rule_disagree"] += 1
            clauses.extend(_build_section(
                card, section, text, ja_by_section[section],
                supplement_by_section[section], name_ja,
                split_index.get((cid, section)), judgment_index, report))
        _dedupe_indexes(cid, clauses, report)
        if any(clause["needs_review"] for clause in clauses):
            # 判定與官方明示打架時最可能是拆錯,整張卡都要看而不只是那一行
            for clause in clauses:
                clause["needs_review"] = True
        clauses = _merge_clauses(cid, clauses, existing_index, matched, report)
        _check_substrings(cid, clauses, desc, ja_by_section, report)
        if any(c["confidence"] == CONFIDENCE_LOW for c in clauses):
            report["low_confidence"].append(cid)
        entries.append({"id": cid, "clauses": clauses})

    _report_orphans(existing_index, matched, report)
    _report_judgment_orphans(entries, judgment_index, report)
    _apply_rules(entries, existing_index, report)
    _count_clauses(entries, report)
    report["no_japanese_text"].sort()
    report["low_confidence"].sort()
    return entries, report


def serialize_tag_cards(entries):
    """效果標記表 → JSON 文字(indent=2、不 escape 中文、保留結尾換行)。"""
    return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
