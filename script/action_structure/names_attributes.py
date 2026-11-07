"""名稱表與卡片屬性表(純函式):官方 DB 文本的「」引用 → 名稱表;卡片總表的參數與
「〜として扱う」句 → 卡片屬性表(物件0 的來源)。

名稱表(`card["names"]`):每個「」引用的名稱一列(同名只一列,id 取首次出現的偏移),
來源「」引用;對得到卡名或字段的算認得,否則標 `unparsed`(原因「不認得的「」名稱」),
覆蓋報告的「不認得的「」名稱」一節就讀這個。比對前雙方全半形折疊,表裡保留原文字面。
宣言名稱(「カード名を１つ宣言して」)沒有字面,留給之後的票。

卡片屬性表(`card["attributes"]`):每種屬性一張表,每列帶值與位置條件(`where`,None = 任何位置)。
- 卡名表:官方卡名(任何位置);「<位置>に存在する限り(カード名を)「X」として扱う」
  → 「X」只在該位置;「このカード名はルール上「X」として扱う」→ 「X」任何位置。
- 字段表:卡片總表的 setcode 拆成各系列碼(任何位置);「ルール上「X」カードとしても扱う」
  → X 的 setcode 任何位置;「<位置>に存在する限り「X」モンスターとしても扱う」→ 只在該位置。
  「X」同時是卡名又是字段(ブラック・マジシャン)時,後面接「カード/モンスター」的算字段,
  否則算卡名。
- 大類、屬性、種族、等級:取卡片總表的值(來源「卡片總表」),位置條件 None。
  屬性、種族、等級是魔陷時沒有值,不列。
句型規則是整句比對,抽不出的句子不記列(那一句的段仍由段抽取標解析不出)。
"""
import re

from archetype_table import fold_width, split_setcode
from structure_shape import attribute_row, name_row, unparsed, zone

REASON_NAME_UNKNOWN = "不認得的「」名稱"
SOURCE_QUOTE = "「」引用"
SOURCE_OFFICIAL_NAME = "官方卡名"
SOURCE_CARD_LIST = "卡片總表"
CATEGORY_BITS = (("怪獸", 0x1), ("魔法", 0x2), ("陷阱", 0x4))

_QUOTE_RE = re.compile("「([^「」]+)」")
_RANGE_RE = re.compile("「(?P<lo>[^「」]+)」～「(?P<hi>[^「」]+)」のいずれかの")
# 「〜として扱う」句:主語(このカード / このカード名 / このカードのカード名)、
# 範圍(ルール上 / <位置>に存在する限り)、名稱列(「X」カード、「X」カード…)、尾綴(カード/モンスター)。
# 票 09:也認大類與子類型(「このカードは罠カードとしても扱う」「〜限り、通常モンスターとして扱う」);
# 這句本身是「修飾」段(`parse_treat_as` 給段抽取、`render_treat_as` 給反向檢查)。
# 「〜として扱う」的大類/子類型字面 → (屬性名, 值)。
TREAT_KINDS = {"罠カード": ("大類", "陷阱"), "魔法カード": ("大類", "魔法"),
               "通常モンスター": ("卡片子類型", "通常"), "効果モンスター": ("卡片子類型", "效果"),
               "チューナー": ("卡片子類型", "協調")}
_TREAT_RE = re.compile(
    "^(?P<subject>このカード(?:名|のカード名)?(?:は|が)、?)"
    "(?P<scope>ルール上、?|(?P<zones>[^、「]+?)に存在する限り、?)?"
    "(?P<prefix>カード名を|このカードのカード名は)?"
    "(?:(?P<names>「[^」]+」(?:(?:カード|モンスター)?、「[^」]+」)*)"
    "(?P<suffix>カード|モンスター)?"
    f"|(?P<kind>{'|'.join(TREAT_KINDS)}))"
    "として(?P<also>も)?扱う$")
_SCOPE_RE = re.compile("^(?:ルール上、?|(?P<zones>[^、「]+?)に存在する限り、?)?$")
_TREAT_KIND_TEXT = {value: text for text, value in TREAT_KINDS.items()}
_WHERE_WORDS = (("EXデッキ", "額外牌組"), ("デッキ", "牌組"), ("手札", "手牌"),
                ("フィールド上", "場上"), ("フィールドゾーン", "場地區"),
                ("フィールド", "場上"), ("墓地", "墓地"),
                ("モンスターゾーン", "怪獸區"), ("魔法＆罠ゾーン", "魔陷區"),
                ("ペンデュラムゾーン", "P區"))
TREAT_PREDICATE = "として扱う"


def _sentences(text):
    """(偏移, 句子)列表:以「。」切、去掉編號「①：」與 ● 等開頭標記、頭尾空白。"""
    out = []
    pos = 0
    for raw in text.split("。"):
        start = pos
        pos += len(raw) + 1
        sent = raw
        offset = start
        while sent and sent[0] in "\n ●":
            sent, offset = sent[1:], offset + 1
        m = re.match("^[①-⑳]：", sent)
        if m:
            sent, offset = sent[2:], offset + 2
        sent = sent.rstrip("\n ")
        if sent:
            out.append((offset, sent))
    return out


def _parse_where(phrase):
    zones = []
    for part in phrase.split("・"):
        for word, name in _WHERE_WORDS:
            if part == word:
                zones.append(zone(name))
                break
        else:
            return None
    return zones


def extract_names(card, texts, lookups):
    """texts = [(來源 "card_text"/"pen_effect", 文本)];名稱表寫進 card["names"],
    回傳 {名稱字面: 名稱列}。"""
    rows = {}
    for source, text in texts:
        prefix = "pn" if source == "pen_effect" else "n"
        for m in _QUOTE_RE.finditer(text or ""):
            name = m.group(1)
            if name in rows:
                continue
            row = name_row(f"{prefix}{m.start()}", name, SOURCE_QUOTE)
            folded = fold_width(name)
            if folded not in lookups["card_names"] and folded not in lookups["archetypes"]:
                row["unparsed"] = unparsed(REASON_NAME_UNKNOWN)
            rows[name] = row
        # 範圍端點(「No.101」～「No.107」)不是卡名也不是字段,但範圍規則認得它:不算不認得。
        for m in _RANGE_RE.finditer(text or ""):
            for name in (m.group("lo"), m.group("hi")):
                rows[name]["unparsed"] = None
    card["names"] = list(rows.values())
    return rows


def fill_from_card_list(card, entry):
    """卡片總表的參數 → 大類、屬性、種族、等級列(任何位置)。"""
    tables = card["attributes"]
    for name, bit in CATEGORY_BITS:
        if entry["type"] & bit:
            tables["category"].append(attribute_row(name, source=SOURCE_CARD_LIST))
    for key in ("attribute", "race", "level"):
        if entry.get(key):
            tables[key].append(attribute_row(entry[key], source=SOURCE_CARD_LIST))
    for code in split_setcode(entry.get("setcode") or 0):
        tables["archetype"].append(attribute_row(code, source=SOURCE_CARD_LIST))


def parse_treat_as(sent):
    """「〜として扱う」句 → 修飾段的 `modified` 格(名稱仍是字面,段抽取換成名稱列 id)或 None:
    {"subject": 主語字面, "scope": 範圍字面(ルール上、/ <位置>に存在する限り、), "where": 區域列表或 None,
     "prefix": カード名を/None, "items": [{"text": X, "tail": カード/モンスター/None}], "suffix",
     "also": 「も」有無;大類/子類型時沒有 items 而是 "attr"/"value"}。"""
    m = _TREAT_RE.match(sent)
    if not m:
        return None
    where = None
    if m.group("zones"):
        where = _parse_where(m.group("zones"))
        if where is None:
            return None
    modified = {"subject": m.group("subject"), "scope": m.group("scope") or "",
                "where": where, "prefix": m.group("prefix"), "also": bool(m.group("also"))}
    if m.group("kind"):
        modified["attr"], modified["value"] = TREAT_KINDS[m.group("kind")]
        return modified
    # 名稱列裡每個「X」後面是否接 カード/モンスター:「X」カード、「X」カード としても扱う
    # 的尾綴只寫在最後一個,前面的以頓號前的字判。
    items = []
    for item in [p for p in re.split("、", m.group("names")) if p]:
        qm = _QUOTE_RE.match(item)
        if not qm:
            return None
        items.append({"text": qm.group(1), "tail": item[qm.end():] or None})
    modified["items"], modified["suffix"] = items, m.group("suffix")
    return modified


def render_treat_as(modified, name_text):
    """修飾段的模板:主語 + 範圍 + [カード名を] + 「X」(尾綴)、… + 尾綴 + として(も)扱う;
    `name_text(名稱 id) → 字面`。格與閉集對不上回 None。"""
    scope = _SCOPE_RE.match(modified.get("scope") or "")
    if scope is None:
        return None
    where = modified.get("where")
    if (scope.group("zones") is None) != (where is None):
        return None
    if where is not None and _parse_where(scope.group("zones")) != where:
        return None
    text = modified["subject"] + modified["scope"] + (modified.get("prefix") or "")
    if modified.get("items") is None:
        kind = _TREAT_KIND_TEXT.get((modified.get("attr"), modified.get("value")))
        if kind is None:
            return None
        text += kind
    else:
        pieces = []
        for item in modified.get("items") or ():
            name = name_text(item["name"]) if "name" in item else item.get("text")
            if name is None or item.get("tail") not in (None, "カード", "モンスター"):
                return None
            pieces.append(f"「{name}」" + (item.get("tail") or ""))
        if not pieces or modified.get("suffix") not in (None, "カード", "モンスター"):
            return None
        text += "、".join(pieces) + (modified.get("suffix") or "")
    return text + "として" + ("も" if modified.get("also") else "") + "扱う"


def extract_treat_as(card, texts, lookups):
    """「〜として扱う」句 → 卡名表、字段表與大類表的列(帶位置條件、原文範圍與字面)。"""
    tables = card["attributes"]
    for source, text in texts:
        for offset, sent in _sentences(text or ""):
            modified = parse_treat_as(sent)
            if modified is None:
                continue
            where = modified["where"]
            span = (offset, offset + len(sent))
            if modified.get("items") is None:
                if modified["attr"] == "大類":
                    _add_row(tables["category"], modified["value"], where, source, span, sent)
                continue   # 卡片子類型沒有屬性表,只在修飾段上
            items = modified["items"]
            for i, item in enumerate(items):
                name, tail = item["text"], item["tail"] or ""
                if not tail and i == len(items) - 1:
                    tail = modified["suffix"] or ""
                folded = fold_width(name)
                codes = lookups["archetypes"].get(folded, [])
                is_card_name = folded in lookups["card_names"]
                if codes and (tail or not is_card_name):
                    for code in codes:
                        _add_row(tables["archetype"], code, where, source, span, sent)
                elif is_card_name:
                    _add_row(tables["name"], name, where, source, span, sent)


def treat_as_sentences(texts):
    """「〜として扱う」句的 (來源, 原文範圍) 集合:句型認得就算,不管名稱對不對得到
    (卡片總表的 setcode 已含那個系列時列不會新增,但那句仍不是效果)。"""
    found = set()
    for source, text in texts:
        for offset, sent in _sentences(text or ""):
            if parse_treat_as(sent) is not None:
                found.add((source, (offset, offset + len(sent))))
    return found


def _add_row(table, value, where, source, span, sent):
    """同值同位置只記一列(卡片總表的 setcode 已含 cdb 寫進去的「ルール上」系列時不重複)。"""
    for row in table:
        if row["value"] == value and row["where"] == where:
            return
    table.append(attribute_row(value, where=where, source=source, span=span,
                               text=sent))
