# 票 14 前後對比的總數字(讀 <repo 根> 的卡片結構產物,用同一個根的程式;只印 stdout)。
# 跑法:python -X utf8 .scratch/action-structure-m2/stats/m2_compare.py <repo 根>
#   前 = 里程碑一:git archive c349dc1 script/action_structure data/action_structure.json data/cards.json
#        解到一個空資料夾當 <repo 根>(用里程碑一當時的程式讀里程碑一的產物)
#   後 = 本里程碑:repo 根本身
# 印:段數與段解析出比例、反向檢查通過段、整張通過張數與只差一種原因的張數、
#     常用與新動作詞的查詢(預設開關,只給動作詞):命中(groups 全部)、經引用、未解析組張數。
# 該根的程式不認得的動作詞印「不認得」(里程碑一沒有的動作詞)。輸出決定性:排序固定、不印時間。
import json
import os
import sys
from collections import Counter

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402
from reverse_check import REASON_NO_TEMPLATE, check_card  # noqa: E402
from structure_shape import iter_segments  # noqa: E402
import synonyms  # noqa: E402

# 該根的程式認得的動作詞:同義表字幹的動作詞與下位詞表的兩端
KNOWN = ({action for _, action, _ in synonyms.PREDICATE_STEMS}
         | set(synonyms.ACTION_PARENT) | set(synonyms.ACTION_PARENT.values()))

ACTIONS = ("特殊召喚", "破壞", "送墓", "除外", "加入手牌", "捨棄", "返回",
           "抽牌", "傷害", "回復", "性質變更", "去除", "放置", "覆蓋", "儀式召喚")
# 極性查詢(抗性/限制類):動作詞 + 極性;這幾個動作詞只出現在非「做」的段,預設極性查不到
POLAR = (("破壞", "不會"), ("受到效果影響", "不會"), ("取對象", "不會"), ("攻擊", "不能"),
         ("攻擊", "可以"), ("特殊召喚", "只能"))
# 只出現在條件段的動作詞:開條件段
CONDITION = ("戰鬥",)

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    card_list = json.load(f)

with_text = [c for c in cards if not c["unparsed"]]
segs = [seg for c in cards for block in c["blocks"] for _, seg in iter_segments(block)]
unstructured = sum(1 for s in segs if s.get("unstructured"))
parsed = sum(1 for s in segs if not s["unparsed"] and not s.get("unstructured"))
print(f"有官方日文 張: {len(with_text)}")
print(f"段: {len(segs)}")
print(f"段解析出: {parsed}")
print(f"段解析出比例: {parsed / len(segs):.1%}")
print(f"未結構化 段: {unstructured}")

passed_cards, passed_segs, only_one = 0, 0, Counter()
for card in with_text:
    failures = check_card(card)
    failed = {(f["block"], f["segment"]) for f in failures}
    passed_segs += sum(1 for block in card["blocks"] for b, s in iter_segments(block)
                       if (b["id"], s["id"]) not in failed and not s.get("unstructured"))
    if not failures:
        passed_cards += 1
        continue
    keys = {f["detail"] if f["reason"] == REASON_NO_TEMPLATE else f["reason"] for f in failures}
    if len(keys) == 1:
        only_one[keys.pop()] += 1
print(f"反向檢查通過 段: {passed_segs}")
print(f"整張通過 張: {passed_cards}")
print(f"只差一種原因 張: {sum(only_one.values())}")
for key, n in sorted(only_one.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"只差一種原因 {key} 張: {n}")


def query(q):
    if not set(q["actions"]) <= KNOWN:
        return "不認得"
    result = run_query(cards, card_list, q)
    groups = result["groups"]
    return (f"{len(groups['全部'])} / {len(groups.get('經引用', []))} / "
            f"{len(groups['未解析'])}")


print("查詢(命中 / 經引用 / 未解析):")
for action in ACTIONS:
    print(f"查詢 {action}: {query({'actions': [action]})}")
for action, polarity in POLAR:
    print(f"查詢 {action},極性{polarity}: "
          f"{query({'actions': [action], 'polarities': [polarity]})}")
for action in CONDITION:
    print(f"查詢 {action},條件段開: {query({'actions': [action], 'include_condition': True})}")
