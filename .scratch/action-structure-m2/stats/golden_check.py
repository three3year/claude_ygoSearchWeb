"""里程碑二 18 張標準卡核對(票 14):
1. 跑掛標準卡的測試模組,記下每個 faq() 夾具;各標準卡測試類的測試數與結果。
2. 夾具卡文與官方 DB 文本(data/sources/faq_info.json)逐字比對。
3. 全庫產物(data/action_structure.json 經 load_structures 讀回)逐張 check_card;
   ディーナ 只看 ③ 後半那一段。
跑法:python -X utf8 golden_check.py <repo 根>
"""
import io
import json
import os
import sys
import unittest
from collections import Counter

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))
os.chdir(os.path.join(ROOT, "script", "action_structure"))

import test_golden  # noqa: E402

GOLDEN = [
    (75416738, "キノの蟲惑魔", "04", "test_resistance_restriction", "KinoTest"),
    (29047353, "水舞台", "04", "test_resistance_restriction", "WaterStageTest"),
    (31557782, "古代の歯車", "05", "test_display_placement", None),
    (46044841, "ガスタ・ファルコ", "05", "test_display_placement", None),
    (91711547, "フレムベル・デビル", "06", "test_damage_recover", "FlamvellDevilTest"),
    (4192696, "森の聖霊 エーコ", "06", "test_damage_recover", "EcoForestSpiritTest"),
    (47077697, "呪念の化身ウルボヌス", "08", "test_stat_modify", None),
    (79853073, "サイファー・スカウター", "08", "test_stat_modify", None),
    (42149850, "使い捨て学習装置", "08", "test_stat_modify", None),
    (68540058, "メタル化・魔法反射装甲", "08", "test_stat_modify", None),
    (39733924, "フル・アーマード・エクシーズ", "12", "test_embedded_effects", "FullArmoredXyzTest"),
    (65872270, "イグナイト・バースト", "09", "test_select_and_do", "IgniteBurstTest"),
    (56350972, "竜姫神サフィラ", "09", "test_select_and_do", "SaffiraTest"),
    (59581480, "耀聖の波詩ディーナ", "09", "test_select_and_do", "DinaTest"),
    (74117290, "暗黒界の取引", "10", "test_draw", "DarkWorldDealingsTest"),
    (20216608, "ツッパリーチ", "10", "test_draw", "TsuppaReachTest"),
    (69655484, "Em影絵師シャドー・メイカー", "11", "test_detach", "ShadowMakerTest"),
    (61399402, "ライトドラゴン＠イグニスター", "11", "test_detach", "LightDragonTest"),
]
IDS = {g[0] for g in GOLDEN}
DINA = 59581480

recorded = {}
_orig = test_golden.faq


def _recording_faq(password, name_ja, card_text, pen_effect=None):
    if password in IDS:
        recorded.setdefault(password, set()).add((card_text, pen_effect))
    return _orig(password, name_ja, card_text, pen_effect)


test_golden.faq = _recording_faq

modules = sorted({g[3] for g in GOLDEN})
mods = {m: __import__(m) for m in modules}

# 每個測試類的測試數與結果
loader = unittest.TestLoader()
suite = unittest.TestSuite(loader.loadTestsFromModule(mods[m]) for m in modules)
result = unittest.TextTestResult(io.StringIO(), True, 0)
suite.run(result)
bad = {t.id() for t, _ in result.failures + result.errors}
per_class, per_class_bad = Counter(), Counter()


def walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite):
            yield from walk(t)
        else:
            yield t


for t in walk(unittest.TestSuite(loader.loadTestsFromModule(mods[m]) for m in modules)):
    cls = t.id().rsplit(".", 1)[0]
    per_class[cls] += 1
    if t.id() in bad:
        per_class_bad[cls] += 1
print(f"模組 {', '.join(modules)}:跑 {result.testsRun} 個,失敗 {len(result.failures)}、錯誤 {len(result.errors)}")
for name in sorted(per_class):
    print(f"  {name}: {per_class[name]} 個,不過 {per_class_bad[name]}")

# 夾具卡文 vs 官方 DB 文本
with open(os.path.join(ROOT, "data", "sources", "faq_info.json"), encoding="utf-8") as f:
    official = {e["password"]: e for e in json.load(f)}
print("\n夾具卡文 vs 官方 DB 文本:")
for cid, name, *_ in GOLDEN:
    entry = official[cid]
    texts = recorded.get(cid, set())
    same = [t for t in texts if t[0] == entry["card_text"] and t[1] == entry.get("pen_effect")]
    print(f"  {cid} {name}: 夾具 {len(texts)} 種,與官方逐字相同 {len(same)} 種")

# 全庫產物逐張反向檢查
from card_structure import load_structures  # noqa: E402
from reverse_check import check_card  # noqa: E402
from structure_shape import iter_segments  # noqa: E402

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = {c["id"]: c for c in load_structures(f.read())}
print("\n全庫產物 check_card:")
for cid, name, ticket, *_ in GOLDEN:
    c = cards[cid]
    segs = [seg for block in c["blocks"] for _, seg in iter_segments(block)]
    failures = check_card(c)
    if cid == DINA:
        target = [s["id"] for s in segs if s["text"] == mods["test_select_and_do"].DINA_BANISH]
        failures = [f for f in failures if f["segment"] in target]
        print(f"  {cid} {name}(票 {ticket},只驗 ③ 後半段 {target}):段 {len(segs)},"
              f"{'通過' if not failures else '不通過'}")
    else:
        print(f"  {cid} {name}(票 {ticket}):段 {len(segs)},{'通過' if not failures else '不通過'}")
    for f in failures:
        print(f"      - {f['reason']} {f.get('detail')} 段 {f['segment']}:"
              f"{(f.get('original') or '')[:60]}")
    if failures:
        for s in segs:
            if s["id"] in {f["segment"] for f in failures}:
                print(f"        段 {s['id']} 原文:{s['text']}")
