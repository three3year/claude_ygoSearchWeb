"""摘要裁定併成一張票的小型寫法 4 項:現在產物上的解析不出段數(核對摘要「依 573e758 產物重算」的數字)。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c0_small_items.py
讀 data/action_structure.json;段解析不出(任何原因)且段原文中該字面。
"""
import re

from common import all_segments, cards

ITEMS = [
    ("括號注記(句尾括號版次數限制)", r"（[^）]*(１ターンに１度|しか(選択|使用|発動|適用)できない)[^）]*）"),
    ("ライフポイントを払", r"ライフポイントを払"),
    ("〜表示に変更/〜表示にならない", r"表示に変更|表示にならない"),
    ("ダメージステップ時/戦闘ダメージ計算時", r"ダメージステップ時|戦闘ダメージ計算時"),
]

for name, pat in ITEMS:
    segs, ids = 0, set()
    for c in cards():
        for b, s in all_segments(c):
            if s["unparsed"] and re.search(pat, b["text"][s["span"][0]:s["span"][1]]):
                segs += 1
                ids.add(c["id"])
    print(f"{name}: {segs} 段 / {len(ids)} 張")
