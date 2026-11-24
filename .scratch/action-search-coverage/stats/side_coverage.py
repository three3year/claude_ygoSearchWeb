# 規格〔區域的方〕的預估表,以重建後的卡片結構重量:幾條指定方的查詢的直接命中張數(run_query 的「全部」)。
# 跑法(repo 根):python -X utf8 .scratch/action-search-coverage/stats/side_coverage.py
# 讀版控裡的 data/action_structure.json(票 01–06 後重建的)、data/cards.json;直接查,不模擬。
# 「本輪前」「規格預估」兩欄抄自規格〔數據出處〕的表(當時用模擬量的,不隨重跑變);
# 沒指定方的兩條抄自票 02 的 Comments。「實際」是這次跑出來的。約半分鐘。
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    structures = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    cards = json.load(f)


def zone(end, name, side=None):
    want = name if side is None else {"zone": name, "side": side}
    return {f"{end}_zones": [want]}


# (名稱, 動作, 從/到條件, 本輪前, 規格預估);規格預估 None 印「不變」
QUERIES = [
    ("特殊召喚 從對手的墓地", "特殊召喚", zone("from", "墓地", "對手"), 29, 76),
    ("特殊召喚 從我方的墓地", "特殊召喚", zone("from", "墓地", "我方"), 1397, 1598),
    ("破壞 從對手的場上", "破壞", zone("from", "場上", "對手"), 597, 1248),
    ("破壞 從我方的場上", "破壞", zone("from", "場上", "我方"), 251, 906),
    ("送墓 到對手的墓地", "送墓", zone("to", "墓地", "對手"), 0, 1192),
    ("送墓 到我方的墓地", "送墓", zone("to", "墓地", "我方"), 0, 1402),
    ("除外 到對手的除外", "除外", zone("to", "除外", "對手"), 0, 1203),
    ("返回 到對手的手牌", "返回", zone("to", "手牌", "對手"), 0, 291),
    ("返回 到我方的手牌", "返回", zone("to", "手牌", "我方"), 259, 549),
    ("特殊召喚 從墓地(沒指定方)", "特殊召喚", zone("from", "墓地"), 1628, None),
    ("破壞 從場上(沒指定方)", "破壞", zone("from", "場上"), 1492, None),
]

print("| 查詢 | 本輪前 | 規格預估 | 實際 | 實際 − 預估 |")
print("|---|---:|---:|---:|---:|")
for name, action, zones, before, estimate in QUERIES:
    actual = len(run_query(structures, cards, {"actions": [action], **zones})["groups"]["全部"])
    target = before if estimate is None else estimate
    shown = "不變" if estimate is None else f"{estimate:,}"
    print(f"| {name} | {before:,} | {shown} | {actual:,} | {actual - target:+,} |")
