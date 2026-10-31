# -*- coding: utf-8 -*-
"""否定形(frame-args-v4 票 08)。

mark(ctx, tokens, frame):極性 否定 的框架加 frame["negation"](closed_values.NEGATION_FORMS):態 受身 →
受身,否則看述語自己的否定形(にならない/受けない 系 → 不成不受、できない 系 → 不可能、其餘 →
一般)。字面表從 categories.polarity_class 搬來這裡,categories.py 改成 import、行為不變。
票 01 只建骨架:什麼都不做。
"""


def mark(ctx, tokens, frame):
    """票 08 填。"""
