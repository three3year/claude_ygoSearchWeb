# 票 07 收尾:人工驗收清單裡「要看到幾張、哪張在不在」的數字。
# 跑法(repo 根,機器上要有 node):python -X utf8 .scratch/action-search-coverage/stats/acceptance_queries.py
# 讀版控裡的 data/action_structure.json、data/cards.json、web/data.js、web/action-data.js(不重建)。
# 網站那邊借 action-search-web 的 site_queries.js(接縫三的沙箱載入真實前端檔),每條動作條件
# 換成的列查詢交回 run_query,兩邊問同一個問題;比:網站命中 = 全部 ∪ 經引用,網站無法確認 = 未解析。
# 每行印網站張數、無法確認張數、兩邊是否逐張相同,與指定的卡在不在網站清單裡。不帶側欄卡片條件。輸出決定性。
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402

SITE_QUERIES = os.path.join(ROOT, ".scratch", "action-search-web", "stats", "site_queries.js")


def side(end, zone, who=None):
    return {end: {"zone": zone} if who is None else {"zone": zone, "side": who}}


def named(action, text):
    return {"actions": [action], "target": {"condition": {"name": text}}}


# (名稱, 動作條件(玩家介面的形狀,同 web/js/action.js 的 condOf), 要看在不在的卡號)
CASES = [
    ("特殊召喚 從對手的墓地", {"actions": ["特殊召喚"], **side("from", "墓地", "對手")},
     [83764718, 70828912, 14983497]),
    ("特殊召喚 從我方的墓地", {"actions": ["特殊召喚"], **side("from", "墓地", "我方")},
     [83764718, 70828912, 14983497]),
    ("特殊召喚 從墓地", {"actions": ["特殊召喚"], **side("from", "墓地")}, []),
    ("破壞 從對手的場上", {"actions": ["破壞"], **side("from", "場上", "對手")}, [53129443, 12580477]),
    ("破壞 從我方的場上", {"actions": ["破壞"], **side("from", "場上", "我方")}, [53129443, 12580477]),
    ("送墓 到對手的墓地", {"actions": ["送墓"], **side("to", "墓地", "對手")}, [81439173, 36262024]),
    ("送墓 到我方的墓地", {"actions": ["送墓"], **side("to", "墓地", "我方")}, [81439173, 36262024]),
    ("除外 到對手的除外", {"actions": ["除外"], **side("to", "除外", "對手")}, [70342110]),
    ("返回 到對手的手牌", {"actions": ["返回"], **side("to", "手牌", "對手")}, [42703248]),
    ("返回 到我方的手牌", {"actions": ["返回"], **side("to", "手牌", "我方")}, [42703248]),
    ("捨棄 從對手的手牌", {"actions": ["捨棄"], **side("from", "手牌", "對手")}, [7623640]),
    ("捨棄 從我方的手牌", {"actions": ["捨棄"], **side("from", "手牌", "我方")}, [7623640]),
    ("破壞 卡名包含 黑魔導", named("破壞", "黑魔導"), []),
    ("破壞 卡名包含 ブラック・マジシャン", named("破壞", "ブラック・マジシャン"), []),
    ("破壞 卡名包含 Dark Magician", named("破壞", "Dark Magician"), []),
    ("破壞 卡名包含 黑%導", named("破壞", "黑%導"), []),
    ("破壞 卡名包含 黑％導(全形 ％)", named("破壞", "黑％導"), []),
    ("破壞 卡名包含 ＤＲＡＧＯＮ", named("破壞", "ＤＲＡＧＯＮ"), []),
    ("破壞 卡名包含 dragon", named("破壞", "dragon"), []),
    ("破壞 卡名包含 %(只有萬用字元)", named("破壞", "%"), []),
    ("破壞(不給條件)", {"actions": ["破壞"]}, []),
    ("加入手牌 卡名包含 拉比麗斯的狂時鐘", named("加入手牌", "拉比麗斯的狂時鐘"), []),
    ("加入手牌 卡名包含 白銀之城的狂時鐘(別名)", named("加入手牌", "白銀之城的狂時鐘"), []),
    ("特殊召喚 卡名包含 救世龍", named("特殊召喚", "救世龍"), [291414, 21159309]),
    ("特殊召喚 卡名包含 救世竜", named("特殊召喚", "救世竜"), [291414, 21159309]),
]

site = json.loads(subprocess.run(
    ["node", SITE_QUERIES],
    input=json.dumps({"root": ROOT, "conds": [{"name": n, "act": a} for n, a, _ in CASES]}),
    capture_output=True, text=True, encoding="utf-8", check=True).stdout)

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    structures = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    cards = json.load(f)
names = {c["id"]: c.get("name_zh") or c["name_ja"] for c in cards}

print("| 查詢 | 網站 | 無法確認 | 兩邊 | 指定的卡 |")
print("|---|---:|---:|---|---|")
for (name, _, probes), s in zip(CASES, site):
    groups = run_query(structures, cards, s["rowQuery"])["groups"]
    same = (set(groups["全部"]) | set(groups["經引用"])) == set(s["ids"]) \
        and set(groups["未解析"]) == set(s["unsure"])
    hits = set(s["ids"])
    shown = "、".join(f"{names[i]} {'在' if i in hits else '不在'}" for i in probes)
    print(f"| {name} | {len(s['ids']):,} | {len(s['unsure']):,} | {'相同' if same else '不同'} | {shown} |")
