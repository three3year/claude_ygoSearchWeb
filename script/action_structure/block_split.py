"""區塊切分:官方 DB 文本 → 區塊列表 + 略過文本。

新式卡依 ①②③ 的編號字元切(筆記 01:①前不一定有換行,所以用字元不用換行);
編號前的前言依官方換行逐行處理:次數限制(「１ターンに１度しか使用できない」等)
不記、進略過文本;其他行(素材行、召喚條件句、卡片發動句…)先各成一個區塊、
種類暫歸編號效果並標「區塊種類判不出」,由票 09 的句型接手。
舊式無編號卡整段一個區塊,標「舊式無編號卡未切分」,票 10 接手。
靈擺效果取 `pen_effect`,同一套切法、區塊種類固定靈擺效果。
"""
import re

from structure_shape import new_block, unparsed

# 編號字元 ①..⑳ 後一律全形冒號(筆記 01)。
_LABEL_RE = re.compile("[①-⑳]：")
# 次數限制前言:「このカード名の(①②の)効果は１ターンに１度しか使用できない」
# 「このカード名のカードは１ターンに１枚しか発動できない」等;不記(spec)。
_LIMIT_RE = re.compile(
    "^[^。]*?(?:１ターンに[１-９]度|１ターンに[１-９]枚|デュエル中に[１-９]度|デュエル中に[１-９]枚)"
    "[^。]*?(?:しか|まで)(?:使用|発動|適用|特殊召喚)?でき(?:ない|る|ず[^。]*?できない)。?$")
# 「しか/まで」要緊接在「使用/発動/特殊召喚できる」前:「１ターンに１度、融合召喚及び
# 以下の方法でのみ特殊召喚できる」有 １ターンに１度 卻是召喚條件句,不能當次數限制略過。
# 只收單句的行;一行兩句(「X」により降臨。このカード名の…)留給票 09 的句型切。

KIND_UNKNOWN = "區塊種類判不出"
OLD_STYLE_UNSPLIT = "舊式無編號卡未切分"
LIMIT_REASON = "次數限制"


def _strip_span(text, start, end):
    """去掉頭尾換行與空白,回傳收緊後的 (start, end)。"""
    while start < end and text[start] in "\n ":
        start += 1
    while end > start and text[end - 1] in "\n ":
        end -= 1
    return start, end


def _split_text(text, source, kind_numbered, prefix):
    blocks, omitted = [], []
    if not text:
        return blocks, omitted
    labels = list(_LABEL_RE.finditer(text))
    if not labels:
        start, end = _strip_span(text, 0, len(text))
        block = new_block(f"{prefix}{start}", kind_numbered, None, source,
                          (start, end), text[start:end])
        block["unparsed"] = unparsed(OLD_STYLE_UNSPLIT)
        return [block], omitted
    # 前言:編號前的文字,依官方換行逐行。
    preamble_end = labels[0].start()
    pos = 0
    for line in text[:preamble_end].split("\n"):
        start, end = _strip_span(text, pos, pos + len(line))
        pos += len(line) + 1
        if start == end:
            continue
        if _LIMIT_RE.match(text[start:end]):
            omitted.append({"source": source, "span": [start, end],
                            "text": text[start:end], "reason": LIMIT_REASON})
            continue
        block = new_block(f"{prefix}{start}", kind_numbered, None, source,
                          (start, end), text[start:end])
        if kind_numbered == "編號效果":
            block["unparsed"] = unparsed(KIND_UNKNOWN)
        blocks.append(block)
    # 編號區塊:從這個編號到下一個編號前。
    for i, m in enumerate(labels):
        stop = labels[i + 1].start() if i + 1 < len(labels) else len(text)
        start, end = _strip_span(text, m.start(), stop)
        blocks.append(new_block(f"{prefix}{start}", kind_numbered,
                                m.group()[0], source, (start, end),
                                text[start:end]))
    return blocks, omitted


def split_blocks(card_text, pen_effect=None):
    """→ (區塊列表, 略過文本列表);每個區塊帶原文範圍(相對於各自的來源文本)。"""
    blocks, omitted = _split_text(card_text or "", "card_text", "編號效果", "b")
    if pen_effect:
        pen_blocks, pen_omitted = _split_text(pen_effect, "pen_effect",
                                              "靈擺效果", "p")
        blocks.extend(pen_blocks)
        omitted.extend(pen_omitted)
    return blocks, omitted
