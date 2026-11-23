"""全庫新舊比對:一批查詢,讀卡片結構(舊)與攤平成列(新)兩條路徑各跑一次,列出每個查詢、每一組的差異。

    python -X utf8 script/action_structure/compare_query_paths.py [--structures ...] [--cards ...]

全庫只攤平一次,候選卡全部先算好(分開計時),之後每個查詢兩條路徑各跑一次。
比的是:特定、泛用、全部、經引用、未解析五組(逐張),每張命中卡的明細(命中段、組、`via`、`mark`、
`replaced_by`),每張未解析卡的明細(原因、段、原文),最後整份結果(含順序)逐項相同。
有任何差異時結束碼 1。
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from action_query import PATH_STRUCTURE, VIA_GROUP, run_query  # noqa: E402
from action_rows import flatten  # noqa: E402
from card_structure import load_structures  # noqa: E402
from row_match import match_rows  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
DEFAULT_STRUCTURES = os.path.join(ROOT, "data", "action_structure.json")
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
GROUPS = ("特定", "泛用", "全部", VIA_GROUP, "未解析")

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
    # 票 04:未解析組(解析不出的段、物件判不了、異同判不了、解析不出的引用節點、區塊種類判不出)
    ("未解析 動作詞 召喚", {"actions": ["召喚"]}),
    ("未解析 動作詞 無效", {"actions": ["無效"]}),
    ("未解析 動作詞 加入手牌", {"actions": ["加入手牌"]}),
    ("未解析 認不得的動作詞", {"actions": ["不存在的動作詞"]}),
    ("未解析 指定卡代入(異同判不了)", {"actions": ["特殊召喚"], "card": BLUE_EYES}),
    ("未解析 給條件代入", {"actions": ["除外"], "condition": MONSTER}),
    ("未解析 區塊種類篩掉(種類判不出)", {"actions": ["發動"], "block_kinds": ["召喚條件"]}),
    ("未解析 區塊種類篩掉 特殊召喚", {"actions": ["特殊召喚"], "block_kinds": ["素材"]}),
    ("未解析 段類別與極性篩選", {"actions": ["特殊召喚"], "kinds": ["限制"], "polarities": ["不能"]}),
    ("未解析 只查泛用", {"actions": ["破壞"], "generic_only": True, "from_zones": ["場上"]}),
    # 票 04:經引用(via、mark、泛用引用開關)
    ("經引用 儀式召喚", {"actions": ["儀式召喚"]}),
    ("經引用 儀式召喚 泛用引用開", {"actions": ["儀式召喚"], "generic_reference": True}),
    ("經引用 破壞 泛用引用開", {"actions": ["破壞"], "generic_reference": True}),
    ("經引用 除外 泛用引用開+區塊種類", {"actions": ["除外"], "generic_reference": True,
                                  "block_kinds": ["編號效果"]}),
    ("經引用 指定卡 泛用引用開", {"actions": ["破壞"], "card": BLUE_EYES,
                           "generic_reference": True}),
    # 票 04:代替(被代替段、做代替的段、replaced_by)
    ("代替 破壞", {"actions": ["破壞"], "replacement": True}),
    ("代替 除外", {"actions": ["除外"], "replacement": True}),
    ("代替 送墓", {"actions": ["送墓"], "replacement": True}),
    ("代替 段類別 被代替", {"actions": ["破壞"], "replacement": True, "kinds": ["被代替"]}),
    ("代替 條件段開關", {"actions": ["破壞"], "replacement": True, "include_condition": True}),
    ("代替 空查詢", {"replacement": True}),
]


def compare(old, new):
    """兩條路徑的結果 → 每組的差異 {組: (只在舊, 只在新)},外加明細不同的卡
    (命中明細:命中段、組、via、mark、replaced_by;未解析明細:原因、段、原文)與整份結果是否相同。"""
    diff = {}
    for group in GROUPS:
        a, b = set(old["groups"][group]), set(new["groups"][group])
        diff[group] = (sorted(a - b), sorted(b - a))
    for key, label in (("hits", "命中明細"), ("unparsed", "未解析明細")):
        a = {item["id"]: item for item in old[key]}
        b = {item["id"]: item for item in new[key]}
        diff[label] = sorted(cid for cid in a.keys() & b.keys() if a[cid] != b[cid])
    diff["整份"] = old == new
    return diff


def same(diff):
    return (diff["整份"] and not diff["命中明細"] and not diff["未解析明細"]
            and all(not a and not b for a, b in (diff[g] for g in GROUPS)))


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
        old = run_query(structures, cards, query, path=PATH_STRUCTURE)
        old_seconds = time.perf_counter() - start
        start = time.perf_counter()
        new = match_rows(index, query)
        new_seconds = time.perf_counter() - start
        total_old += old_seconds
        total_new += new_seconds
        diff = compare(old, new)
        ok = same(diff)
        failed += not ok
        counts = " ".join(f"{g} {len(old['groups'][g])}" for g in GROUPS)
        counts += (f" 未解析段 {sum(len(u['segments']) for u in old['unparsed'])}"
                   f" mark {sum('mark' in h for h in old['hits'])}"
                   f" replaced_by {sum('replaced_by' in h for h in old['hits'])}")
        print(f"{'相同' if ok else '不同'} | {name} | {counts} | 舊 {old_seconds:.2f} 秒 新 {new_seconds:.2f} 秒"
              f" | {json.dumps(query, ensure_ascii=False)}")
        if not ok:
            for group in GROUPS:
                only_old, only_new = diff[group]
                if only_old or only_new:
                    print(f"    {group}:只在舊 {only_old} 只在新 {only_new}")
            for label in ("命中明細", "未解析明細"):
                if diff[label]:
                    print(f"    {label}不同的卡:{diff[label]}")
            if not diff["整份"]:
                print("    整份結果不同(含順序)")
    print(f"{len(QUERIES)} 個查詢,不同 {failed} 個;查詢合計 舊 {total_old:.1f} 秒 新 {total_new:.1f} 秒")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
