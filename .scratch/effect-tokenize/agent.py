# -*- coding: utf-8 -*-
"""施事者(frame-args-v4 票 07)。

mark(ctx, tokens, frame):frame["agent"](closed_values.AGENTS)、frame["agent_source"](AGENT_SOURCES,與
agent 同進退)、frame["agent_inferred"] = True(只在來源是 預設 時)。順序照規格 Implementation
Decisions 的 (1)〜(4)。票 01 只建骨架:什麼都不做。
"""


def mark(ctx, tokens, frame):
    """票 07 填。"""
