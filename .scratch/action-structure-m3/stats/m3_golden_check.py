"""里程碑三標準卡核對(票 13)。
1. 兩張收尾標準卡(使い捨て学習装置 42149850、竜姫神サフィラ 56350972):跑斷言「整張通過」的測試類,
   記下那幾個模組的 faq() 夾具,與官方 DB 文本(data/sources/faq_info.json)逐字比對。
2. 全庫產物(data/action_structure.json 經 load_structures 讀回)逐張 check_card:
   規格「測試決策」表的候選標準卡與各票 Comments 另挑的替代標準卡;沒通過的列出還卡在哪。
跑法:python -X utf8 .scratch/action-structure-m3/stats/m3_golden_check.py <repo 根>
輸出決定性:照下表順序,不印時間。里程碑一、二的 18 張另跑 .scratch/action-structure-m2/stats/golden_check.py。
"""
import io
import json
import os
import sys
import unittest

ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))
os.chdir(os.path.join(ROOT, "script", "action_structure"))

import test_golden  # noqa: E402

WRAP_UP = {42149850: "使い捨て学習装置", 56350972: "竜姫神サフィラ"}
# 斷言「整張通過」的測試類(票 10、票 12 寫的)
WRAP_UP_TESTS = (("test_leave_field", "DisposableLearnerTest"),
                 ("test_premise_count_enum", "SaffiraSecondTimepointTest"))

# (票, 角色, 卡號):候選 = 規格「測試決策」表;替代 = 各票 Comments 另挑、票檔記整張通過的卡。
GOLDEN = [
    ("13", "收尾", 42149850), ("13", "收尾", 56350972),
    ("03", "候選", 111280), ("03", "候選", 218704), ("03", "候選", 324483),
    ("04", "候選", 109401), ("04", "候選", 276357), ("04", "候選", 674561), ("04", "候選", 41546),
    ("04", "替代", 39276790), ("04", "替代", 17688543),
    ("05", "候選", 59080), ("05", "候選", 122520), ("05", "候選", 10000),
    ("05", "替代", 6285791), ("05", "替代", 59388357), ("05", "替代", 18816758),
    ("05", "替代", 43227), ("05", "替代", 85059922), ("05", "替代", 7541475),
    ("06", "候選", 856784), ("06", "候選", 27821104), ("06", "候選", 10780049),
    ("06", "替代", 11637481), ("06", "替代", 1033312), ("06", "替代", 2994495),
    ("06", "替代", 8608979), ("06", "替代", 16114248),
    ("07", "候選", 75043725), ("07", "候選", 3405259),
    ("07", "替代", 29228529), ("07", "替代", 20663556), ("07", "替代", 77515704),
    ("08", "候選", 387282), ("08", "候選", 645794), ("08", "候選", 2326738),
    ("08", "候選", 4929256), ("08", "候選", 1487805), ("08", "候選", 3486020),
    ("08", "替代", 56804361), ("08", "替代", 2158562), ("08", "替代", 2507443), ("08", "替代", 45894482),
    ("09", "候選", 1688285), ("09", "候選", 1735088), ("09", "候選", 64865),
    ("09", "候選", 734741), ("09", "候選", 875572), ("09", "候選", 1410324),
    ("09", "替代", 96687733), ("09", "替代", 26708437), ("09", "替代", 88413677), ("09", "替代", 4167084),
    ("10", "候選", 286392), ("10", "候選", 27551), ("10", "候選", 1278431), ("10", "候選", 303660),
    ("10", "替代", 86282581), ("10", "替代", 33420078), ("10", "替代", 71453557), ("10", "替代", 10028593),
    ("11", "候選", 3627449), ("11", "候選", 293542),
    ("12", "候選", 336601), ("12", "候選", 1410324), ("12", "替代", 8085950),
]

# 1. 收尾兩張:測試與夾具
recorded = {}
_orig = test_golden.faq


def _recording_faq(password, name_ja, card_text, pen_effect=None):
    if password in WRAP_UP:
        recorded.setdefault(password, set()).add((card_text, pen_effect))
    return _orig(password, name_ja, card_text, pen_effect)


test_golden.faq = _recording_faq
loader = unittest.TestLoader()
print("收尾標準卡「整張通過」的測試:")
for module, cls in WRAP_UP_TESTS:
    suite = loader.loadTestsFromTestCase(getattr(__import__(module), cls))
    result = unittest.TextTestResult(io.StringIO(), True, 0)
    suite.run(result)
    print(f"  {module}.{cls}: 跑 {result.testsRun} 個,失敗 {len(result.failures)}、錯誤 {len(result.errors)}")

with open(os.path.join(ROOT, "data", "sources", "faq_info.json"), encoding="utf-8") as f:
    official = {e["password"]: e for e in json.load(f)}
print("\n夾具卡文 vs 官方 DB 文本:")
for cid, name in WRAP_UP.items():
    entry = official[cid]
    texts = recorded.get(cid, set())
    same = [t for t in texts if t[0] == entry["card_text"] and t[1] == entry.get("pen_effect")]
    print(f"  {cid} {name}: 夾具 {len(texts)} 種,與官方逐字相同 {len(same)} 種")

# 2. 全庫產物逐張反向檢查
from card_structure import load_structures  # noqa: E402
from reverse_check import check_card  # noqa: E402
from structure_shape import iter_segments  # noqa: E402

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = {c["id"]: c for c in load_structures(f.read())}


def short(text, n=70):
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"


print("\n全庫產物 check_card:")
passed = {"候選": 0, "替代": 0, "收尾": 0}
total = {"候選": 0, "替代": 0, "收尾": 0}
for ticket, role, cid in GOLDEN:
    c = cards[cid]
    texts = {(b["id"], s["id"]): s["text"] for block in c["blocks"] for b, s in iter_segments(block)}
    failures = check_card(c)
    total[role] += 1
    passed[role] += not failures
    state = "整張通過" if not failures else f"沒通過({len(failures)} 處)"
    print(f"  票 {ticket} {role} {cid} {c['name_ja']}:段 {len(texts)},{state}")
    for f in failures:
        detail = f["detail"] if f["detail"] is not None else "字面不符"
        where = short(texts.get((f["block"], f["segment"])) or f.get("original"))
        print(f"      - {f['reason']}/{detail}:{where}")
print("\n合計:" + "、".join(f"{role} {passed[role]} / {total[role]} 張整張通過" for role in ("收尾", "候選", "替代")))
