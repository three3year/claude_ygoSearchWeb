"""數量字面:抽取與句型模板成對放在一起。

- 物件的數量(名詞短語結尾的「１体」「２枚まで」):`parse_count`。
- 對象線的數量(助詞後的「全て」「２枚まで」、物件前的算式「〜の数だけ」、述語前的數量):
  `floating_count`;正規式片段 `COUNT_PATTERN`、`FRONT_COUNT_PATTERN` 給句型用。
- 模板:`render_count`。
抽牌的張數另有自己的寫法,在 `draw`。
"""

import re

from structure_shape import AMOUNT_FORMULA, NoTemplate


FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
# 對象線的數量字面:N体/N枚(まで)、全て;「それぞれ」「ずつ」是每一份各 N(`each`);
# 變數數量「任意の数だけ」記算式字面。寫在物件前的變數數量(「破壊した数だけ相手フィールドの
# カードを」)與寫在述語前「從」之後的數量(「自分の墓地から１枚選んで」)另帶 placement。
EACH_PREFIX, EACH_SUFFIX, FORMULA_COUNT_TAIL = "それぞれ", "ずつ", "数だけ"
# 單位「つ」:超量素材、計數器的「１つ」「２つまで」。
COUNT_UNITS = "体|枚|つ"
COUNT_PATTERN = (f"(?:{EACH_PREFIX})?[０-９]+(?:{COUNT_UNITS})(?:まで|{EACH_SUFFIX})?|全て"
                 f"|任意の{FORMULA_COUNT_TAIL}")
_COUNT_RE = re.compile(f"^(?P<each>{EACH_PREFIX})?(?P<digits>[０-９]+)(?P<unit>{COUNT_UNITS})"
                       f"(?P<upto>まで)?(?P<per>{EACH_SUFFIX})?$")
# 物件前的變數數量另收上限「〜の数まで、」(「自分フィールドの「＠イグニスター」モンスターの
# 数まで、相手フィールドの〜を選んで破壊する」),算式帶 cmp ≤。
FORMULA_UPTO_TAIL = "数まで"
FORMULA_COUNT_TAILS = (FORMULA_COUNT_TAIL, FORMULA_UPTO_TAIL)
FRONT_COUNT_PATTERN = f"[^、を]+?(?:{'|'.join(FORMULA_COUNT_TAILS)})、?"
TO_FULLWIDTH_DIGITS = str.maketrans("0123456789", "０１２３４５６７８９")
# 存在前提的數量:寫在「存在する」前(「モンスターが２体以上存在する場合」),記在物件的數量格,
# `placement` 存在前——不接在名詞後,由前提的模板寫。單位另收「種類」(卡名的種類數);
# 比較是 以上(≥)、以下(≤)、沒寫(=)。
BEFORE_EXISTENCE = "存在前"
EXISTENCE_CMP_WORDS = {"以上": "≥", "以下": "≤", "": "="}
EXISTENCE_COUNT_PATTERN = f"[０-９]+(?:{COUNT_UNITS}|種類)(?:{'|'.join(filter(None, EXISTENCE_CMP_WORDS))})?"
_EXISTENCE_COUNT_RE = re.compile(
    f"^(?P<digits>[０-９]+)(?P<unit>{COUNT_UNITS}|種類)(?P<cmp>{'|'.join(filter(None, EXISTENCE_CMP_WORDS))})?$")


def parse_count(m):
    if not m.group("count"):
        return None
    digits = m.group("count")[:-len(m.group("unit")) - len(m.group("upto") or "")]
    return {"text": m.group("count"),
            "value": int(digits.translate(FULLWIDTH_DIGITS)),
            "unit": m.group("unit"), "cmp": "≤" if m.group("upto") else "="}


def floating_count(text, placement=None):
    """對象線的數量(「カードを２枚まで」「それらのモンスターを全て」),記在對象線上;
    變數數量(「任意の数だけ」「破壊した数だけ」)是算式字面;「それぞれ」「ずつ」帶 `each`;
    寫在物件前或述語前的帶 `placement`(有值才寫)。"""
    if text == "全て":
        count = {"text": text, "cmp": "全部"}
    elif text.rstrip("、").endswith(FORMULA_COUNT_TAILS):
        count = {"kind": AMOUNT_FORMULA, "text": text}
        if text.rstrip("、").endswith(FORMULA_UPTO_TAIL):
            count["cmp"] = "≤"
    else:
        m = _COUNT_RE.match(text)
        count = {"text": text, "value": int(m.group("digits").translate(FULLWIDTH_DIGITS)),
                 "unit": m.group("unit"), "cmp": "≤" if m.group("upto") else "="}
        if m.group("each") or m.group("per"):
            count["each"] = True
    if placement:
        count["placement"] = placement
    return count


def parse_existence_count(text):
    """存在前提的數量字面(「２体以上」「３種類以上」「２枚」)→ 物件的數量格。"""
    m = _EXISTENCE_COUNT_RE.match(text)
    return {"text": text, "value": int(m.group("digits").translate(FULLWIDTH_DIGITS)),
            "unit": m.group("unit"), "cmp": EXISTENCE_CMP_WORDS[m.group("cmp") or ""],
            "placement": BEFORE_EXISTENCE}


def is_existence_count(count):
    return bool(count) and count.get("placement") == BEFORE_EXISTENCE


def render_existence_count(count):
    """存在前提的數量 → 字面,由值、單位、比較拼回。"""
    words = {cmp: word for word, cmp in EXISTENCE_CMP_WORDS.items()}
    if (not is_existence_count(count) or count.get("cmp") not in words
            or not re.fullmatch(f"{COUNT_UNITS}|種類", count.get("unit") or "")
            or not isinstance(count.get("value"), int)):
        raise NoTemplate("物件數量無模板:存在前")
    return (str(count["value"]).translate(TO_FULLWIDTH_DIGITS) + count["unit"]
            + words[count["cmp"]])


def render_count(count):
    """數量字面:N体/N枚/Nつ(まで)、全て;變數數量(算式)只記字面、照寫,上限「〜の数まで」
    帶 cmp ≤;
    `each`(「それぞれ」「ずつ」)由數值拼回基本字面,再驗原文字面是它加上這兩個字。"""
    if not count:
        return ""
    if count.get("kind") == AMOUNT_FORMULA:
        text = count.get("text") or ""
        bare = text.rstrip("、")
        if (not bare.endswith(FORMULA_COUNT_TAILS)
                or (count.get("cmp") == "≤") != bare.endswith(FORMULA_UPTO_TAIL)):
            raise NoTemplate("物件數量無模板")
        return text
    if count.get("cmp") == "全部":
        return "全て"
    if count.get("cmp") not in ("=", "≤") or not count.get("unit"):
        raise NoTemplate("物件數量無模板")
    # 官方卡文的數字是全形,照它寫(正規化時兩邊都會折成半形,這裡只為報告好讀)。
    digits = str(count["value"]).translate(TO_FULLWIDTH_DIGITS)
    base = f"{digits}{count['unit']}{'まで' if count['cmp'] == '≤' else ''}"
    if count.get("each"):
        text = count.get("text") or ""
        if text == base or not re.fullmatch(f"(?:{EACH_PREFIX})?{base}(?:{EACH_SUFFIX})?", text):
            raise NoTemplate("物件數量無模板:each")
        return text
    return base
