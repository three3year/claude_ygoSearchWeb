# -*- coding: utf-8 -*-
"""方式(frame-args-v4 票 06)。

mark(ctx, tokens, frame):述語前同一子句內的 で 片語 → frame["manner"](字面,含 で、不含 は/も 後綴)、
frame["manner_kind"](closed_values.MANNER_KINDS)、frame["manner_value"](只在 表示形式 時);區域+で
不是方式,進 regions["place"] 並 transfer="取自で"。一框至多一個。票 01 只建骨架:什麼都不做。
"""


def mark(ctx, tokens, frame):
    """票 06 填。"""
