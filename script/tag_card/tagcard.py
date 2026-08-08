"""效果標記表管線:卡片總表 + 補足情報 → 效果標記表(拆句骨架)。

單一接縫:build_tag_cards(卡片總表條目, 補足情報條目[, 既有標記表, 判定結果])
    → (entries, report)
純函式,不碰網路與檔案系統。詞彙見 CONTEXT.md:效果標記表、效果句、效果類型、
效果外文本、必發/選發。

拆句與官方明示(票02/03)已實作;必發/選發(票04)、既有標記表與判定結果的合併
(票05/08)另票處理。
"""
import hashlib
import json
import re

import official
from official import INDEX_PREAMBLE, KIND_NON_EFFECT, NUMERALS

# NUMERALS:效果編號字元。官方目前最多用到⑤,official 多留幾個位以防新卡。
FULLWIDTH_COLON = "："
BULLET = "●"

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
CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"

SECTION_MAIN = "main"
SECTION_PENDULUM = "pendulum"
INDEX_UNNUMBERED = "1"

HEAD_PENDULUM = "【靈擺效果】"
HEAD_MONSTER_RE = re.compile(r"【怪獸(效果|敘述|描述)】")
# 通常怪獸的敘述段。來源資料有一張寫成「描述」,只認「敘述」會漏掉。
FLAVOR_HEADS = ("敘述", "描述")
# 繁中來源在卡文尾端附的別名註記(如「\n\n※白銀之城的狂時鐘」),不是卡文本體
FOOTNOTE_RE = re.compile(r"\n\n※[^\n]*$")

CLAUSE_FIELDS = ("index", "section", "text_zh", "text_ja", "text_hash", "kind",
                 "optional", "role", "source", "rule_predicted", "confidence",
                 "tags")


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
        "rule_predicted": None,
        "confidence": confidence,
        "tags": [],
    }


def _slice(text, span):
    return "" if span is None else text[span[0]:span[1]]


# ---------------------------------------------------------------- ● 子效果

def _bullet_parts(text):
    """文字 → (第一個 ● 之前的段落, [● 分項, ...]);兩者都已去首尾空白。"""
    positions = [i for i, ch in enumerate(text) if ch == BULLET]
    if not positions:
        return text.strip(), []
    bounds = list(zip(positions, positions[1:] + [len(text)]))
    return text[:positions[0]].strip(), [text[s:e].strip() for s, e in bounds]


def _split_bullets(cid, section, clauses, supplement, report):
    """官方以【●…について】解說子效果時,把 ● 分項拆成獨立效果句。

    只在官方確實這樣解說時才拆——沒有官方標頭的 ● 只是同一個效果的選項列舉,
    拆了反而製造出官方沒有認可的效果句。繁中與日文的 ● 數量不一致時不拆。
    """
    if not official.bullet_specs(supplement):
        return clauses
    split = []
    for clause in clauses:
        both = clause["text_zh"] + clause["text_ja"]
        if clause["index"] == INDEX_PREAMBLE or BULLET not in both:
            split.append(clause)
            continue
        zh_head, zh_bullets = _bullet_parts(clause["text_zh"])
        if clause["text_ja"]:
            ja_head, ja_bullets = _bullet_parts(clause["text_ja"])
        else:
            ja_head, ja_bullets = "", [""] * len(zh_bullets)
        if len(ja_bullets) != len(zh_bullets):
            report["bullet_split_mismatch"].append(
                {"id": cid, "section": section, "index": clause["index"]})
            split.append(clause)
            continue
        confidence = clause["confidence"]
        if zh_head or ja_head:
            split.append(_clause(clause["index"], section, zh_head, ja_head,
                                 confidence))
        for pos, (zh, ja) in enumerate(zip(zh_bullets, ja_bullets), start=1):
            split.append(_clause(f"{clause['index']}-{BULLET}{pos}", section,
                                 zh, ja, confidence))
        report["bullet_clauses"] += len(zh_bullets)
    return split


# ---------------------------------------------------------------- 官方明示

def _apply_attestations(cid, section, clauses, name_ja, supplement, report):
    """官方明示的效果類型寫進效果句;歸屬不確定的只進報告,不猜測。"""
    assignments, notes = official.attest(name_ja, supplement, clauses)
    by_index = {clause["index"]: clause for clause in clauses}
    for index, (kind, ladder) in assignments.items():
        clause = by_index[index]
        clause["kind"] = kind
        clause["source"] = official.SOURCE_OFFICIAL
        report["official_clauses"] += 1
        report["official_coverage"][ladder] += 1
    for key, rows in notes.items():
        for row in rows:
            report[key].append({"id": cid, "section": section, **row})


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
        "unsupported_inputs": [],
        "official_clauses": 0,
        "official_coverage": {ladder: 0 for ladder in official.LADDERS},
        "kind_counts": {kind: 0 for kind in official.KINDS},
        "bullet_clauses": 0,
        "bullet_split_mismatch": [],
        **{key: [] for key in official.NOTE_KEYS},
    }


def _build_section(card, section, zh_text, ja_text, supplement, name_ja,
                   report):
    """單一段落 → 效果句清單。繁中負責拆句,日文靠編號序列對位。"""
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

    if zh_all is not None:
        # 無編號舊式卡文:先當單一效果句,語意拆分留給判定票(票08)
        clauses.append(_clause(
            INDEX_UNNUMBERED, section, _slice(zh_text, zh_all),
            _slice(ja_text, ja_all) if aligned else "", confidence))
        report["pending_split"].append({"id": cid, "section": section})

    clauses = _split_bullets(cid, section, clauses, supplement, report)
    _apply_attestations(cid, section, clauses, name_ja, supplement, report)
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


def build_tag_cards(cards, faq_entries, existing=None, judgments=None):
    """卡片總表 + 補足情報 → (效果標記表條目, 報告)。

    cards: 卡片總表條目(需 id / desc / type)。
    faq_entries: 補足情報條目(需 password,取 card_text / supplement /
        pen_effect / pen_supplement)。
    existing / judgments: 既有標記表與判定結果。本票尚未實作合併(票05/08),
        傳入時列進報告的 unsupported_inputs 而不靜靜忽略。
    """
    report = _new_report()
    if existing is not None:
        report["unsupported_inputs"].append("existing")
    if judgments is not None:
        report["unsupported_inputs"].append("judgments")

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
                supplement_by_section[section], name_ja, report))
        _dedupe_indexes(cid, clauses, report)
        _check_substrings(cid, clauses, desc, ja_by_section, report)
        if any(c["confidence"] == CONFIDENCE_LOW for c in clauses):
            report["low_confidence"].append(cid)
        for clause in clauses:
            if clause["kind"] is not None:
                report["kind_counts"][clause["kind"]] += 1
        report["clauses"] += len(clauses)
        entries.append({"id": cid, "clauses": clauses})

    report["no_japanese_text"].sort()
    report["low_confidence"].sort()
    return entries, report


def serialize_tag_cards(entries):
    """效果標記表 → JSON 文字(indent=2、不 escape 中文、保留結尾換行)。"""
    return json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
