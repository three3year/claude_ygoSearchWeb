# 規格〔區域的方〕的預估:現行判法 vs 站主 2026-11-24 定的規則,幾條查詢的直接命中張數(run_query 的「全部」)。
# 跑法(repo 根):python -X utf8 .scratch/action-search-coverage/stats/side_coverage.py
# 讀版控裡的 data/action_structure.json、data/cards.json。新規則在查詢時模擬(不改結構):
#   查詢給我方/對手時,區域的方是 任一方、雙方各自、持有者、自身 → 命中(自身照段的誰較準,這裡一律當兩邊,
#   全庫 67 個區域條目,影響很小);從的區域沒寫方、但物件條件式明寫了控制方(「自分の墓地の」)→ 照那個方;
#   其餘沒寫方的:場上系區域 → 命中;墓地、除外 → 物件是此卡只算我方、其他物件兩邊。
# 約半分鐘。
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

import row_match  # noqa: E402
from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402
from condition_judge import OBJECT_THIS  # noqa: E402

NOT_FIELD = {"墓地", "除外", "手牌", "牌組", "額外牌組", "牌組頂", "牌組底", "素材"}
BROAD = {"任一方", "雙方各自", "持有者", "自身"}

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    structures = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    cards = json.load(f)

orig_line, orig_zones = row_match._line_matches, row_match._zones_match
with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    OBJECTS = {c["id"]: {o["id"]: o for o in (c.get("objects") or [])} for c in json.load(f)}


def _atoms(cond):
    if isinstance(cond, dict):
        yield cond
        for arg in cond.get("args") or []:
            yield from _atoms(arg)


def written_side(owner, raw_line):
    objects = OBJECTS.get(owner["id"] if isinstance(owner, dict) else owner, {})
    obj, seen = objects.get(raw_line.get("object")), set()
    while obj is not None and obj["id"] not in seen:
        seen.add(obj["id"])
        for atom in _atoms(obj.get("condition")):
            if atom.get("op") == "控制方" and atom.get("value") in ("我方", "對手"):
                return atom["value"]
        source = obj.get("source") or {}
        obj = objects.get(source.get("of")) if source.get("kind") in ("子集", "剩餘") else None
    return None


state = {"new": False, "this": False, "from": None, "written": None}


def zones(query_zones, pos, include_inferred):
    if orig_zones(query_zones, pos, include_inferred):
        return True
    if not state["new"] or pos is None or (pos.inferred and not include_inferred):
        return False
    for want in query_zones:
        if not isinstance(want, dict) or want.get("side") not in ("我方", "對手"):
            continue
        for zone, side in pos.zones:
            if zone != want["zone"]:
                continue
            if side is None and pos is state["from"] and state["written"] is not None:
                if state["written"] == want["side"]:
                    return True
                continue
            if side in BROAD:
                return True
            if side is None and zone in ("墓地", "除外"):
                if want["side"] == "我方" or not state["this"]:
                    return True
            elif side is None and zone not in NOT_FIELD:
                return True
    return False


def line(line_, q, wanted):
    state["this"] = line_.object is not None and line_.object.kind == OBJECT_THIS
    state["from"] = line_.from_
    cands = line_.object.candidates if line_.object is not None else None
    state["written"] = (written_side(cands._owner, cands._line)
                        if cands is not None and hasattr(cands, "_line") else None)
    return orig_line(line_, q, wanted)


row_match._zones_match, row_match._line_matches = zones, line

QUERIES = [
    ("特殊召喚 從對手的墓地", {"actions": ["特殊召喚"], "from_zones": [{"zone": "墓地", "side": "對手"}]}),
    ("特殊召喚 從我方的墓地", {"actions": ["特殊召喚"], "from_zones": [{"zone": "墓地", "side": "我方"}]}),
    ("破壞 從對手的場上", {"actions": ["破壞"], "from_zones": [{"zone": "場上", "side": "對手"}]}),
    ("破壞 從我方的場上", {"actions": ["破壞"], "from_zones": [{"zone": "場上", "side": "我方"}]}),
    ("送墓 到對手的墓地", {"actions": ["送墓"], "to_zones": [{"zone": "墓地", "side": "對手"}]}),
    ("送墓 到我方的墓地", {"actions": ["送墓"], "to_zones": [{"zone": "墓地", "side": "我方"}]}),
    ("除外 到對手的除外", {"actions": ["除外"], "to_zones": [{"zone": "除外", "side": "對手"}]}),
    ("返回 到對手的手牌", {"actions": ["返回"], "to_zones": [{"zone": "手牌", "side": "對手"}]}),
    ("返回 到我方的手牌", {"actions": ["返回"], "to_zones": [{"zone": "手牌", "side": "我方"}]}),
]

print("| 查詢 | 現行 | 新規則(預估) |")
print("|---|---:|---:|")
for name, q in QUERIES:
    counts = []
    for new in (False, True):
        state["new"] = new
        counts.append(len(run_query(structures, cards, q)["groups"]["全部"]))
    print(f"| {name} | {counts[0]:,} | {counts[1]:,} |")
