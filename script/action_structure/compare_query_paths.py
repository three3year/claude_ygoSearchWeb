"""全庫新舊比對:一批查詢,讀卡片結構(舊)與攤平成列(新)兩條路徑各跑一次,列出每個查詢、每一組的差異。

    python -X utf8 script/action_structure/compare_query_paths.py [--structures ...] [--cards ...]

全庫只攤平一次,候選卡全部先算好(分開計時),之後每個查詢兩條路徑各跑一次。
比的是直接命中:特定、泛用、全部三組(逐張)與每張卡的命中段;未解析組、經引用、代替還沒搬到新路徑(票 04)。
有任何差異時結束碼 1。
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from action_query import VIA_GROUP, run_query  # noqa: E402
from action_rows import flatten  # noqa: E402
from card_structure import load_structures  # noqa: E402
from row_match import match_rows  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_STRUCTURES = os.path.join(ROOT, "data", "action_structure.json")
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
GROUPS = ("特定", "泛用", "全部")

BLACK_MAGICIAN = 46986414
BLACK_MAGICIAN_ALT = 46986415   # 異圖的卡片密碼
BLUE_EYES = 89631139
ASH_BLOSSOM = 14558127
MONSTER = {"op": "大類", "value": "怪獸"}
SPELL = {"op": "大類", "value": "魔法"}

# (名稱, 查詢);名稱寫這個查詢在測哪個查詢欄。
QUERIES = [
    ("空查詢", {}),
    ("動作詞 破壞", {"actions": ["破壞"]}),
    ("動作詞 特殊召喚(含下位詞)", {"actions": ["特殊召喚"]}),
    ("多個動作詞同一段", {"actions": ["無效", "破壞"]}),
    ("多個動作詞(無同段)", {"actions": ["破壞", "特殊召喚"]}),
    ("從 牌組", {"actions": ["特殊召喚"], "from_zones": ["牌組"]}),
    ("從 對手的墓地", {"actions": ["特殊召喚"], "from_zones": [{"zone": "墓地", "side": "對手"}]}),
    ("從 場上(含子區域)", {"actions": ["破壞"], "from_zones": ["場上"]}),
    ("從 牌組頂", {"actions": ["送墓"], "from_zones": ["牌組頂"]}),
    ("到 牌組", {"actions": ["返回"], "to_zones": ["牌組"]}),
    ("到 我方的場上", {"actions": ["特殊召喚"], "to_zones": [{"zone": "場上", "side": "我方"}]}),
    ("到 墓地(推得終點關)", {"actions": ["解放"], "to_zones": ["墓地"]}),
    ("到 墓地(推得終點開)", {"actions": ["解放"], "to_zones": ["墓地"], "include_inferred": True}),
    ("從+到 推得終點開", {"actions": ["送墓"], "from_zones": ["手牌"], "to_zones": ["墓地"],
                     "include_inferred": True}),
    ("指定卡 ブラック・マジシャン", {"actions": ["特殊召喚"], "card": BLACK_MAGICIAN}),
    ("指定卡 異圖密碼", {"actions": ["特殊召喚"], "card": BLACK_MAGICIAN_ALT}),
    ("指定卡 青眼の白龍 破壞", {"actions": ["破壞"], "card": BLUE_EYES}),
    ("指定卡 灰流うらら 從手牌捨棄", {"actions": ["捨棄"], "card": ASH_BLOSSOM,
                               "from_zones": ["手牌"]}),
    ("指定卡 無動作詞", {"card": BLACK_MAGICIAN}),
    ("給條件 卡名包含", {"actions": ["特殊召喚"],
                    "condition": {"op": "卡名包含", "text": "ブラック・マジシャン"}}),
    ("給條件 字段", {"actions": ["加入手牌"], "condition": {"op": "字段", "setcodes": [0x10a2]}}),
    ("給條件 怪獸且等級≤4 從手牌", {"actions": ["特殊召喚"], "from_zones": ["手牌"], "condition": {
        "op": "且", "args": [MONSTER, {"op": "屬性比較", "attr": "等級", "cmp": "≤", "value": 4}]}}),
    ("給條件 種族 屬性", {"actions": ["除外"], "condition": {"op": "且", "args": [
        {"op": "屬性比較", "attr": "種族", "cmp": "=", "value": "ドラゴン族"},
        {"op": "屬性比較", "attr": "屬性", "cmp": "=", "value": "光"}]}}),
    ("給條件 魔法 破壞", {"actions": ["破壞"], "condition": SPELL}),
    ("取對象 破壞", {"actions": ["破壞"], "targeting": True}),
    ("取對象 裝備(受方是被取對象的物件)", {"actions": ["裝備"], "targeting": True}),
    ("取對象 性質變更", {"actions": ["性質變更"], "targeting": True}),
    ("取對象+從 墓地", {"actions": ["特殊召喚"], "targeting": True, "from_zones": ["墓地"]}),
    ("段類別 代價", {"actions": ["捨棄"], "kinds": ["代價"]}),
    ("段類別 召喚手續", {"actions": ["解放"], "kinds": ["召喚手續"]}),
    ("段類別 限制+極性 不能", {"actions": ["特殊召喚"], "kinds": ["限制"], "polarities": ["不能"]}),
    ("區塊種類 召喚條件", {"actions": ["特殊召喚"], "block_kinds": ["召喚條件"]}),
    ("區塊種類 靈擺效果", {"actions": ["破壞"], "block_kinds": ["靈擺效果"]}),
    ("條件段開關", {"actions": ["特殊召喚"], "include_condition": True}),
    ("條件段開關+段類別 條件", {"actions": ["破壞"], "include_condition": True, "kinds": ["條件"]}),
    ("條件段開關 關+段類別 條件", {"actions": ["破壞"], "kinds": ["條件"]}),
    ("極性 不會", {"actions": ["破壞"], "kinds": ["效果", "限制", "修飾"], "polarities": ["不會"]}),
    ("極性 不能、只能", {"actions": ["發動"], "kinds": ["限制", "效果"], "polarities": ["不能", "只能"]}),
    ("只查泛用 破壞", {"actions": ["破壞"], "generic_only": True}),
    ("只查泛用 從墓地除外", {"actions": ["除外"], "from_zones": ["墓地"], "generic_only": True}),
    ("被改的屬性 攻擊力 增", {"actions": ["性質變更"], "modified": {"attr": "攻擊力", "form": "增"}}),
    ("被改的屬性 傷害 數值 0", {"modified": {"attr": "傷害", "form": "數值", "value": 0},
                         "kinds": ["效果", "修飾"]}),
    ("被改的屬性 卡名", {"modified": {"attr": "卡名"}, "kinds": ["效果", "修飾"]}),
    ("合併:從墓地+給條件+取對象", {"actions": ["特殊召喚"], "from_zones": ["墓地"],
                           "condition": MONSTER, "targeting": True}),
    ("合併:指定卡+到+推得", {"actions": ["送墓"], "card": BLUE_EYES, "to_zones": ["墓地"],
                       "include_inferred": True}),
]


def direct_hits(result):
    """卡號 → (組, 命中段);經引用組不算。"""
    return {hit["id"]: (hit["group"], hit["segments"]) for hit in result["hits"]
            if hit["group"] != VIA_GROUP}


def compare(old, new):
    """兩條路徑的結果 → 每組的差異:{組: (只在舊, 只在新)},外加命中段不同的卡。"""
    diff = {}
    for group in GROUPS:
        a, b = set(old["groups"][group]), set(new["groups"][group])
        diff[group] = (sorted(a - b), sorted(b - a))
    old_hits, new_hits = direct_hits(old), direct_hits(new)
    diff["命中段"] = sorted(cid for cid in old_hits.keys() & new_hits.keys()
                         if old_hits[cid][1] != new_hits[cid][1])
    return diff


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--structures", default=DEFAULT_STRUCTURES)
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    args = parser.parse_args(argv)
    with open(args.structures, encoding="utf-8") as f:
        structures = load_structures(f.read())
    with open(args.cards, encoding="utf-8") as f:
        cards = json.load(f)

    start = time.perf_counter()
    index = flatten(structures, cards)
    flat_seconds = time.perf_counter() - start
    start = time.perf_counter()
    for row in index.rows:
        if row.line is not None and row.line.object is not None:
            row.line.object.candidates.mask
    candidate_seconds = time.perf_counter() - start
    print(f"攤平 {len(index.rows)} 列:{flat_seconds:.1f} 秒;候選卡全部算好:{candidate_seconds:.1f} 秒")

    failed = 0
    total_old = total_new = 0.0
    for name, query in QUERIES:
        start = time.perf_counter()
        old = run_query(structures, cards, query)
        old_seconds = time.perf_counter() - start
        start = time.perf_counter()
        new = match_rows(index, query)
        new_seconds = time.perf_counter() - start
        total_old += old_seconds
        total_new += new_seconds
        diff = compare(old, new)
        same = not diff["命中段"] and all(not a and not b for a, b in
                                         (diff[g] for g in GROUPS))
        failed += not same
        counts = " ".join(f"{g} {len(old['groups'][g])}" for g in GROUPS)
        print(f"{'相同' if same else '不同'} | {name} | {counts} | 舊 {old_seconds:.2f} 秒 新 {new_seconds:.2f} 秒"
              f" | {json.dumps(query, ensure_ascii=False)}")
        if not same:
            for group in GROUPS:
                only_old, only_new = diff[group]
                if only_old or only_new:
                    print(f"    {group}:只在舊 {only_old} 只在新 {only_new}")
            if diff["命中段"]:
                print(f"    命中段不同的卡:{diff['命中段']}")
    print(f"{len(QUERIES)} 個查詢,不同 {failed} 個;查詢合計 舊 {total_old:.1f} 秒 新 {total_new:.1f} 秒")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
