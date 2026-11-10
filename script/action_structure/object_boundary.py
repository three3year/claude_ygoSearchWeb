"""物件切點:物件短語前面不屬於它的字面(時點、前提、期間、主語、原因、「〜から」…)從哪裡切。

簡單子句的句型把助詞「を/が/は」前面整截都當物件短語,前文沒有被別的規則剝掉時會被吞進來
(「このカードが戦闘によって相手モンスター」「自分・相手ターンに、このカード」)。`find_cut` 只看字面,
回傳真正的物件短語從哪裡開始;切出去的前文由 `clause_front` 交給既有的規則,認不得的那一段標
`REASON_FRONT`。

只在整截照現有規則認不全時才切(呼叫端先問 `BlockState.parses_cleanly`),所以認得的修飾語裡
有同樣的字(「EXデッキから特殊召喚されたモンスター」)不受影響。

切點(都要在「」『』（）外;取最後一個):
- 「：」之後。
- 讀點之後——除非讀點前是修飾語的停頓(「〜の、」「〜と、」「「A」、「B」」「〜を持つ、」「〜高い、」
  與連體形「〜た、」「〜る、」「〜な、」):那是物件短語內部的讀點,留給物件修飾的規則。
- 沒有讀點的前文收尾(`_ENDINGS`):主語「Xが/Xは」、原因字面、時點與期間(〜まで、〜に、〜の間)、
  「〜から」、條件(〜場合、〜限り、〜ずに、代わりに)。後面剩下的若是連體子句就不算(`_VERBAL`:
  「戦闘で破壊されたモンスター」的「戦闘で」是修飾語的一部分);以「は」收尾的不看這一條,
  連體子句裡的主語不用は。
- 開頭的殘片(`_LEADING`):さらに、また、に。
"""
import re

from segment_fields import CAUSE_PATTERN
from structure_shape import DISPLAY_WORD
from zone_phrase import ZONE_PHRASE

REASON_FRONT = "物件前的字面認不得"
_OPEN, _CLOSE = "「『（", "」』）"
# 讀點前是這些收尾時,讀點是物件短語內部的停頓,不是前文的結束。
_PAUSE_ENDINGS = ("の", "と", "」", "持つ", "含む", "高い", "低い", "高く", "低く", "ない",
                  "た", "る", "な", "及び", "または", "か")
# 剩下的字面裡有這些就是連體子句(動詞、形容詞接名詞),前面的「が/から/で」屬於修飾語。
_VERBAL = re.compile(
    "した|された|されている|している|していない|されていない|ていない|ている|られた|なった|"
    "異なる|同じ|高い|低い|を持つ|持たない|を含む|含まない|存在する|存在しない|できる|できない|"
    "のない|が無い|がない|である|となる|に必要|可能な|されなかった|しなかった|いない|出た|"
    "置かれた|乗っている|持っている|受けた|行った|なっている|よって決められた|^いる|ない"
    # 過去形接名詞(「この効果で墓地へ送ったモンスター」);「と名のついた」是字段的寫法,不算。
    "|(?<!名のつ)[っいしんえけせれげめてきり](?:た|だ)(?!め)")
# 沒有讀點的前文收尾(位置取比對的結尾)。
_ENDINGS = re.compile(
    # 主語:名詞短語 + が/は(「または」的は不算)。
    "(?:カード|モンスター|自分|相手|プレイヤー|お互い|」|トークン)(?:が|(?<!また)は)"
    f"|{CAUSE_PATTERN}"
    # 時點與期間。
    "|まで|(?:ターン|フェイズ|ステップ|時|中|毎|前|後|間)に|の間(?:だけ)?"
    "|[０-９]度(?:だけ)?"
    "|から"
    "|場合(?:には|に|は)?|限り|ずに|代わりに")
_OLD_FROM = re.compile(f"^(?:{ZONE_PHRASE})に(?:{DISPLAY_WORD}で)?存在する")
# 開頭的殘片(前一截沒被剝乾淨留下的助詞、接續詞)。
_LEADING = re.compile("^(?:さらに|また(?!は)|に(?!よ))")


def _depth_zero(text):
    """「」『』（）外的位置。"""
    depth, out = 0, []
    for i, ch in enumerate(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        elif depth == 0:
            out.append(i)
    return set(out)


def find_cut(text):
    """物件短語的字面 → 真正的物件短語從哪裡開始(0 = 沒有吞進前文)。"""
    outside = _depth_zero(text)
    cut = 0
    for i in sorted(outside):
        ch = text[i]
        if ch == "：" or (ch == "、" and not text[:i].endswith(_PAUSE_ENDINGS)):
            cut = i + 1
    for m in _ENDINGS.finditer(text):
        end = m.end()
        if end <= cut or m.start() not in outside or end - 1 not in outside:
            continue
        rest = text[end:]
        if not rest or rest.startswith(("、", "の")):
            continue
        # 「は」不會是連體子句裡的主語(連體子句用が/の),後面有動詞也照切;其餘收尾後面剩下的若是
        # 連體子句就不是切點。物件前的舊式「從」(「フィールド上に表側表示で存在する」)不算連體子句。
        if not m.group().endswith("は") and _VERBAL.search(_OLD_FROM.sub("", rest)):
            continue
        cut = end
    lead = _LEADING.match(text)
    if lead and lead.end() > cut and text[lead.end():]:
        cut = lead.end()
    return cut
