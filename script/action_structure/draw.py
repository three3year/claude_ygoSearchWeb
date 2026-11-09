"""抽牌(m2 票 10):句型與字面閉集(抽取的填格在 `segment_extract._fill_draw`,模板在
`reverse_check._render_draw`)。

- 抽到的卡是新建物件(條件同頭名詞カード,即 大類 卡);「カードを」有寫時物件字面是它、助詞を,
  沒寫時物件沒有字面與範圍、對象線沒有助詞——兩者除字面外結構相同。
- 張數在對象線 `count`:固定值「N枚」寫在述語前;變數張數(「破壊した数だけ」「その枚数分だけ」)
  只記算式字面 `{"kind": "算式", "text"}`,寫在主語前的帶 `placement: 主語前`、寫在主語後
  「從」前的帶 `placement: 名詞前`。「お互いはそれぞれ」的「それぞれ」是每人各 N 張,記 `each`。
- 從牌組(「デッキから」明寫,沒寫照推得表)到手牌(推得)。
- 誰:「自分は/相手は/お互いは」進 `agent`(`segment_extract.parse_agent`)。
- 原因:「通常のドロー」= `{"kind": "規則", "text": "通常の"}`,寫在述語前;「効果で」照既有閉集。
- 「ドローフェイズ」是階段字面,不是抽牌(述語字面排除它)。
"""
import re

from segment_fields import CAUSE_PATTERN

DRAW_ACTION = "抽牌"
DRAWN_OBJECT = "カード"
DRAWN_MARKER = "を"
COUNT_UNIT = "枚"
EACH_WORD = "それぞれ"
RULE_TEXT = "通常の"
CAUSE_RULE = "規則"
PLACEMENT_BEFORE_SUBJECT = "主語前"
PLACEMENT_BEFORE_NOUN = "名詞前"
# 變數張數的字面收尾(「破壊した数だけ」「その枚数分だけ」)。
FORMULA_TAIL = "(?:数|数分)だけ"
_FORMULA_TAIL_RE = re.compile(f"{FORMULA_TAIL}、?$")
_FIXED_RE = re.compile(f"^(?P<digits>[０-９]+){COUNT_UNIT}$")
_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")


def clause_pattern(agent_pattern):
    """抽牌子句的正規式:[算式(主語前)][誰][それぞれ][原因][算式(名詞前)][從から][カードを][N枚]
    [通常の]述語。誰的字面由呼叫端給(與簡單子句共用)。主語前的算式不能吃到「自分は」這種主語。"""
    return re.compile(
        f"^(?P<count_lead>(?!(?:{agent_pattern})(?:は|が))[^、を]+?{FORMULA_TAIL}、?)?"
        f"(?:(?P<agent>{agent_pattern})(?P<agent_marker>は|が|(?<=お互い)に)"
        "(?P<agent_pause>、)?)?"
        f"(?P<each>{EACH_WORD})?"
        f"(?P<cause>{CAUSE_PATTERN})?"
        f"(?P<count_front>[^、を]+?{FORMULA_TAIL}、?)?"
        "(?:(?P<from>(?:自分の|相手の)?デッキ)から)?"
        f"(?:(?P<object>{DRAWN_OBJECT}){DRAWN_MARKER})?"
        f"(?P<count>[０-９]+{COUNT_UNIT})?"
        f"(?P<rule>{RULE_TEXT})?"
        "(?P<pred>ドロー(?!フェイズ)を?[^、を]*)$")


def parse_count(fixed, front, lead, each):
    """張數字面 → 對象線 count;寫了兩處、或「それぞれ」沒有張數 → None(不猜)。"""
    written = [(text, placement) for text, placement in
               ((fixed, None), (front, PLACEMENT_BEFORE_NOUN), (lead, PLACEMENT_BEFORE_SUBJECT))
               if text]
    if len(written) > 1 or (each and not written):
        return None, bool(written)
    if not written:
        return None, False
    text, placement = written[0]
    if placement is None:
        count = {"text": text, "value": int(text[:-len(COUNT_UNIT)].translate(_FULLWIDTH)),
                 "unit": COUNT_UNIT, "cmp": "="}
    else:
        count = {"kind": "算式", "text": text, "placement": placement}
    if each:
        count["each"] = True
    return count, False


def rule_cause():
    return {"kind": CAUSE_RULE, "text": RULE_TEXT}


def is_rule_cause(cause):
    return cause == rule_cause()


def render_count(count):
    """count → (字面, placement);形狀不對丟 ValueError(呼叫端轉成無模板)。"""
    if not count:
        return "", None
    text = count.get("text") or ""
    if count.get("kind") == "算式":
        placement = count.get("placement")
        if placement not in (PLACEMENT_BEFORE_SUBJECT, PLACEMENT_BEFORE_NOUN) \
                or not _FORMULA_TAIL_RE.search(text):
            raise ValueError("抽牌張數無模板")
        return text, placement
    m = _FIXED_RE.match(text)
    if (not m or count.get("unit") != COUNT_UNIT or count.get("cmp") != "="
            or int(m.group("digits").translate(_FULLWIDTH)) != count.get("value")
            or count.get("placement")):
        raise ValueError("抽牌張數無模板")
    return text, None
