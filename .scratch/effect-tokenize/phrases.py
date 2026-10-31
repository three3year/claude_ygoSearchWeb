# -*- coding: utf-8 -*-
"""論元片語(frame-args-v4 票 02 段/中心詞/中心詞類/玩家/區域/指示詞、票 03 修飾語、票 04 數量)。

structure(ctx, tokens, frame):替動作框架加 frame["phrases"] = {"object"|"topic"|"subject"|"goal": Phrase},
只放有字面的欄;推得的目的沒有片語。Phrase/Segment/Modifier/Quantity 的形狀見 enrich.py 與
`.scratch/frame-args-v4/spec.md`;片語讀切區域之前的受事者字面(frame["_raw"],票 02 暫存)。
封閉值域在 closed_values.py。票 01 只建骨架:什麼都不做。
"""


def structure(ctx, tokens, frame):
    """票 02〜04 填。"""
