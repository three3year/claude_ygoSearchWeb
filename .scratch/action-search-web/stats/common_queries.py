# 票 17 收尾:幾個常用的動作搜尋,在 Python(run_query)與網站(前端引擎)上各查一次,比張數與卡號。
# 跑法(repo 根,機器上要有 node):python -X utf8 .scratch/action-search-web/stats/common_queries.py
# 讀版控裡的 data/action_structure.json、data/cards.json、web/data.js、web/action-data.js(不重建)。
# 動作條件寫成玩家介面的形狀(web/js/action.js 的 condOf);網站那邊同目錄 site_queries.js
# 用接縫三的沙箱載入真實前端檔,把每條動作條件換成的列查詢(rowQuery)交回來給 run_query,
# 兩邊問的是同一個問題(同 script/action_structure/test_web_parity.py 的做法)。
# 比:網站命中的卡 = run_query 的 全部 ∪ 經引用;網站無法確認的卡 = run_query 的 未解析。
# 卡片條件(側欄的其他軸)一律不給。輸出決定性:不印時間。約 1 分鐘。
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402

ALL_KINDS = ["eff", "cost", "cond"]
CONDS = [
    ("破壞", {"actions": ["破壞"]}),
    ("特殊召喚", {"actions": ["特殊召喚"]}),
    ("特殊召喚 從墓地", {"actions": ["特殊召喚"], "from": {"zone": "墓地"}}),
    ("特殊召喚 從對手的墓地", {"actions": ["特殊召喚"], "from": {"zone": "墓地", "side": "對手"}}),
    ("加入手牌 從牌組", {"actions": ["加入手牌"], "from": {"zone": "牌組"}}),
    ("除外 從墓地", {"actions": ["除外"], "from": {"zone": "墓地"}}),
    ("破壞 抗性", {"actions": ["破壞"], "pol": "resist"}),
    ("破壞 抗性 這張卡自己", {"actions": ["破壞"], "pol": "resist", "target": "this_card"}),
    ("通常召喚 限制", {"actions": ["通常召喚"], "pol": "limit"}),
    ("特殊召喚 誰對手 勾觸發條件", {"actions": ["特殊召喚"], "agent": "對手", "kinds": ALL_KINDS}),
    ("特殊召喚 誰對手 勾觸發條件 含不限定的",
     {"actions": ["特殊召喚"], "agent": "對手", "kinds": ALL_KINDS, "include_unrestricted": True}),
    ("傷害 受方對手", {"actions": ["傷害"], "recipient": "對手"}),
    ("傷害 受方我方", {"actions": ["傷害"], "recipient": "我方"}),
    ("破壞 勾觸發條件 原因戰鬥", {"actions": ["破壞"], "kinds": ALL_KINDS, "cause": {"kind": "戰鬥"}}),
    ("破壞 勾觸發條件 原因戰鬥 含不限定的",
     {"actions": ["破壞"], "kinds": ALL_KINDS, "cause": {"kind": "戰鬥"}, "include_unrestricted": True}),
    ("破壞 抗性 原因對手的效果",
     {"actions": ["破壞"], "pol": "resist", "cause": {"kind": "效果", "side": "對手"}}),
    ("破壞 指定 ブラック・マジシャン", {"actions": ["破壞"], "target": {"card": 46986414}}),
    ("特殊召喚 給條件 龍族", {"actions": ["特殊召喚"], "target": {"condition": {"race": "dragon"}}}),
    ("破壞 給條件 卡名包含 ブラック・マジシャン",
     {"actions": ["破壞"], "target": {"condition": {"name": "ブラック・マジシャン"}}}),
    # action-search-coverage 票 05 起兩邊都先換成卡片編號(中日英名與別名);這一條預期兩邊相同
    ("破壞 給條件 卡名包含 黑魔導(中文)",
     {"actions": ["破壞"], "target": {"condition": {"name": "黑魔導"}}}),
]

site = json.loads(subprocess.run(
    ["node", os.path.join(os.path.dirname(__file__), "site_queries.js")],
    input=json.dumps({"root": ROOT, "conds": [{"name": n, "act": a} for n, a in CONDS]}),
    capture_output=True, text=True, encoding="utf-8", check=True).stdout)

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    structures = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    cards = json.load(f)

print("| 查詢 | Python 全部 | Python 經引用 | Python 合計 | 網站 | Python 未解析 | 網站無法確認 | 兩邊 |")
print("|---|---:|---:|---:|---:|---:|---:|---|")
for (name, _), s in zip(CONDS, site):
    groups = run_query(structures, cards, s["rowQuery"])["groups"]
    py_hit = set(groups["全部"]) | set(groups["經引用"])
    same = py_hit == set(s["ids"]) and set(groups["未解析"]) == set(s["unsure"])
    print(f"| {name} | {len(groups['全部']):,} | {len(groups['經引用']):,} | {len(py_hit):,} "
          f"| {len(s['ids']):,} | {len(groups['未解析']):,} | {len(s['unsure']):,} "
          f"| {'相同' if same else '不同'} |")
print()
print("列查詢(網站把動作條件換成的 run_query 查詢):")
for (name, _), s in zip(CONDS, site):
    print(f"- {name}:`{json.dumps(s['rowQuery'], ensure_ascii=False, sort_keys=True)}`")
