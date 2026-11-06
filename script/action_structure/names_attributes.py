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
_TREAT_RE = re.compile(
    "^(?:このカード(?:名|のカード名)?(?:は|が)、?)"
    "(?:(?P<rule>ルール上、?)|(?P<zones>[^、「]+?)に存在する限り、?)"
    "(?:カード名を|このカードのカード名は)?"
    "(?P<names>「[^」]+」(?:(?:カード|モンスター)?、「[^」]+」)*)"
    "(?P<suffix>カード|モンスター)?として(?P<also>も)?扱う$")
_WHERE_WORDS = (("EXデッキ", "額外牌組"), ("デッキ", "牌組"), ("手札", "手牌"),
                ("フィールド上", "場上"), ("フィールドゾーン", "場地區"),
                ("フィールド", "場上"), ("墓地", "墓地"),
                ("モンスターゾーン", "怪獸區"), ("魔法＆罠ゾーン", "魔陷區"),
                ("ペンデュラムゾーン", "P區"))


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


def extract_treat_as(card, texts, lookups):
    """「〜として扱う」句 → 卡名表與字段表的列(帶位置條件、原文範圍與字面)。"""
    tables = card["attributes"]
    for source, text in texts:
        for offset, sent in _sentences(text or ""):
            m = _TREAT_RE.match(sent)
            if not m:
                continue
            where = None
            if m.group("zones"):
                where = _parse_where(m.group("zones"))
                if where is None:
                    continue
            # 名稱列裡每個「X」後面是否接 カード/モンスター:「X」カード、「X」カード としても扱う
            # 的尾綴只寫在最後一個,前面的以頓號前的字判。
            names_text = m.group("names")
            items = [p for p in re.split("、", names_text) if p]
            span = (offset, offset + len(sent))
            for i, item in enumerate(items):
                qm = _QUOTE_RE.match(item)
                if not qm:
                    continue
                name = qm.group(1)
                tail = item[qm.end():]
                if not tail and i == len(items) - 1:
                    tail = m.group("suffix") or ""
                folded = fold_width(name)
                codes = lookups["archetypes"].get(folded, [])
                is_card_name = folded in lookups["card_names"]
                if codes and (tail or not is_card_name):
                    for code in codes:
                        _add_row(tables["archetype"], code, where, source, span, sent)
                elif is_card_name:
                    _add_row(tables["name"], name, where, source, span, sent)


def _add_row(table, value, where, source, span, sent):
    """同值同位置只記一列(卡片總表的 setcode 已含 cdb 寫進去的「ルール上」系列時不重複)。"""
    for row in table:
        if row["value"] == value and row["where"] == where:
            return
    table.append(attribute_row(value, where=where, source=source, span=span,
                               text=sent))
