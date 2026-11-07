"""連用形串接的子句:「〜フィールドに戻り、その攻撃力は〜になる」「〜を手札に加え、このカードをデッキに戻す」
以「、」切成兩個段,連接記「同時」(spec 段樹:序列帶連接)。

只在「、」前面那截是完整的簡單子句、且述語語尾是連用形(`JOIN_TAILS`:戻り、戻し、加え)時才切;
「自分フィールドの、「A」または「B」が」這種讀點前不成子句的不切。「」『』（）內的「、」不算。
判「是不是可切的子句」由呼叫端(`segment_extract`)給,這裡不 import 它,免得互相 import。
票 06 的「し、」同時連接(含發動句的代價子句「〜を墓地へ送り、〜を対象として発動できる」)
也走這裡;句子以上的結構(● 分歧、內嵌效果)在 `segment_tree`。
"""

JOIN_TAILS = ("", "り", "し", "え", "い", "できず")   # できず:「通常召喚できず、〜」(票 09)
JOIN = "同時"
_OPEN = "「『（"
_CLOSE = "」』）"


def split_continuative(text, is_joinable):
    """子句原文 → [(相對起點, 子句字面)];`is_joinable(左半)` 回 True 才在那個「、」切。"""
    pieces, depth, last = [], 0, 0
    for i, ch in enumerate(text):
        if ch in _OPEN:
            depth += 1
        elif ch in _CLOSE:
            depth -= 1
        elif ch == "、" and depth == 0 and is_joinable(text[last:i]):
            pieces.append((last, text[last:i]))
            last = i + 1
    pieces.append((last, text[last:]))
    return pieces
