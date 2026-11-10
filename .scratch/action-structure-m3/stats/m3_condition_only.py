# 票 13:「只給條件」的查詢(不指定卡,只給物件條件)幾個代表查詢的命中張數(讀 <repo 根> 的產物,用同一個根的程式)。
# 跑法:python -X utf8 .scratch/action-structure-m3/stats/m3_condition_only.py <repo 根>
#   修正前 = git archive 67b15a3 script/action_structure data/action_structure.json data/cards.json 解到空資料夾當 <repo 根>
#   修正後 = 同樣解出 ef47731(票 13 的程式,產物同 67b15a3,只差查詢程式);repo 根本身會混進之後的產物改動
# 票 13 修的錯:物件是此卡的線,存在性快取鍵每張卡都一樣,第一張卡的結果被所有卡沿用。
# 每個查詢印:命中(groups 全部)/ 未解析組張數。加 --ids 另印每個查詢命中的卡號(一行,給前後逐張比)。
# 輸出決定性:查詢順序固定、不印時間。全部跑完約 2 分鐘。
import json
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402

MONSTER = {"op": "大類", "value": "怪獸"}
SPELL = {"op": "大類", "value": "魔法"}
TRAP = {"op": "大類", "value": "陷阱"}


def attr(name, cmp, value):
    return {"op": "屬性比較", "attr": name, "cmp": cmp, "value": value}


def both(*conditions):
    return {"op": "且", "args": list(conditions)}


QUERIES = (
    ("特殊召喚,怪獸", dict(actions=["特殊召喚"], condition=MONSTER)),
    ("特殊召喚,魔法", dict(actions=["特殊召喚"], condition=SPELL)),
    ("特殊召喚,陷阱", dict(actions=["特殊召喚"], condition=TRAP)),
    ("特殊召喚,攻擊力 ≤ 1500", dict(actions=["特殊召喚"], condition=attr("攻擊力", "≤", 1500))),
    ("特殊召喚,攻擊力 ≥ 3000", dict(actions=["特殊召喚"], condition=attr("攻擊力", "≥", 3000))),
    ("特殊召喚,等級 ≥ 10", dict(actions=["特殊召喚"], condition=attr("等級", "≥", 10))),
    ("特殊召喚,闇屬性怪獸", dict(actions=["特殊召喚"], condition=both(MONSTER, attr("屬性", "=", "闇")))),
    ("特殊召喚,從墓地,怪獸", dict(actions=["特殊召喚"], from_zones=["墓地"], condition=MONSTER)),
    ("破壞,怪獸", dict(actions=["破壞"], condition=MONSTER)),
    ("破壞,魔法", dict(actions=["破壞"], condition=SPELL)),
    ("破壞,陷阱", dict(actions=["破壞"], condition=TRAP)),
    ("送墓,魔法", dict(actions=["送墓"], condition=SPELL)),
    ("送墓,陷阱", dict(actions=["送墓"], condition=TRAP)),
    ("除外,魔法", dict(actions=["除外"], condition=SPELL)),
    ("除外,攻擊力 ≥ 3000", dict(actions=["除外"], condition=attr("攻擊力", "≥", 3000))),
    ("加入手牌,陷阱", dict(actions=["加入手牌"], condition=TRAP)),
    ("解放,魔法", dict(actions=["解放"], condition=SPELL)),
    ("解放,攻擊力 ≥ 3000", dict(actions=["解放"], condition=attr("攻擊力", "≥", 3000))),
    ("裝備,怪獸", dict(actions=["裝備"], condition=MONSTER)),
    ("性質變更,魔法", dict(actions=["性質變更"], condition=SPELL)),
)

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    card_list = json.load(f)
SHOW_IDS = "--ids" in sys.argv[2:]

print("查詢(命中 / 未解析):")
for label, query in QUERIES:
    groups = run_query(cards, card_list, query)["groups"]
    print(f"查詢 {label}: {len(groups['全部'])} / {len(groups['未解析'])}")
    if SHOW_IDS:
        print("  " + " ".join(str(i) for i in sorted(groups["全部"])))
