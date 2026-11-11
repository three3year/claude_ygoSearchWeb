# 票 13 前後對比的總數字(讀 <repo 根> 的卡片結構產物,用同一個根的程式;只印 stdout)。
# 跑法:python -X utf8 .scratch/action-structure-m3/stats/m3_compare.py <repo 根>
#   前 = 里程碑二:git archive 834f518 script/action_structure data/action_structure.json data/cards.json
#        解到一個空資料夾當 <repo 根>(用里程碑二當時的程式讀里程碑二的產物)
#   後 = 本里程碑:repo 根本身
# 定義與 .scratch/action-structure-m2/stats/m2_compare.py、同目錄 passdump.py 相同:
#   段解析出 = 段的 unparsed 為空且不是 unstructured;整張通過 = 有官方日文且 check_card 回空清單。
# 印:段數與段解析出比例、各段類別、段解析不出的原因、物件與解析不出物件、反向檢查通過段、
#     整張通過張數與只差一種原因的張數、查詢(預設開關,只給動作詞;另註的除外):命中(groups 全部)、經引用、未解析組張數。
# 該根的程式不認得的動作詞印「不認得」(里程碑二沒有的動作詞)。輸出決定性:排序固定、不印時間。約 1 分鐘。
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

KNOWN = ({action for _, action, _ in synonyms.PREDICATE_STEMS}
         | set(synonyms.ACTION_PARENT) | set(synonyms.ACTION_PARENT.values()))

# 常用動作詞(里程碑二摘要「查詢實況」的同一批,加 解放、裝備、支付、發動)
COMMON = ("特殊召喚", "破壞", "送墓", "除外", "加入手牌", "捨棄", "返回", "解放",
          "抽牌", "傷害", "回復", "性質變更", "去除", "放置", "覆蓋", "裝備", "支付", "儀式召喚")
# 本輪新動作詞與牽動的既有詞
NEW = ("通常召喚", "召喚", "上級召喚", "反轉召喚", "P召喚", "L召喚", "融合召喚",
       "成為超量素材", "作為素材", "離場", "取對象", "變更表示形式")
POLAR = (("破壞", "不會"), ("受到效果影響", "不會"), ("取對象", "不會"), ("攻擊", "不能"),
         ("攻擊", "可以"), ("特殊召喚", "只能"), ("召喚", "不能"), ("通常召喚", "不能"))
# 開條件段:誘發寫法多在條件段
CONDITION = ("戰鬥", "特殊召喚", "破壞", "送墓", "除外", "通常召喚", "召喚", "上級召喚",
             "反轉召喚", "P召喚", "作為素材", "離場")
# 開代替:自我限制「離れた場合に除外される」照代替記
REPLACEMENT = ("除外", "離場", "返回", "破壞")

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    card_list = json.load(f)

with_text = [c for c in cards if not c["unparsed"]]
segs = [seg for c in cards for block in c["blocks"] for _, seg in iter_segments(block)]
unstructured = sum(1 for s in segs if s.get("unstructured"))
parsed = sum(1 for s in segs if not s["unparsed"] and not s.get("unstructured"))
print(f"卡: {len(cards)}")
print(f"有官方日文 張: {len(with_text)}")
print(f"段: {len(segs)}")
print(f"段解析出: {parsed}")
print(f"段解析不出: {sum(1 for s in segs if s['unparsed'])}")
print(f"段解析出比例: {parsed / len(segs):.1%}")
print(f"未結構化 段: {unstructured}")

kinds, kinds_parsed = Counter(), Counter()
for s in segs:
    kinds[s["kind"]] += 1
    kinds_parsed[s["kind"]] += not s["unparsed"] and not s.get("unstructured")
for kind, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"段類別 {kind}: {n};解析出 {kinds_parsed[kind]}")

reasons, reason_cards = Counter(), {}
for c in cards:
    for block in c["blocks"]:
        for _, s in iter_segments(block):
            if s["unparsed"]:
                reasons[s["unparsed"]["reason"]] += 1
                reason_cards.setdefault(s["unparsed"]["reason"], set()).add(c["id"])
for reason, n in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"段解析不出的原因 {reason}: {n} 段 / {len(reason_cards[reason])} 張")

objects = [(c["id"], o) for c in cards for o in c["objects"]]
bad = [(cid, o) for cid, o in objects if o.get("unparsed")]
print(f"物件: {len(objects)}")
print(f"解析不出物件: {len(bad)}")
object_reasons, object_reason_cards = Counter(), {}
for cid, o in bad:
    object_reasons[o["unparsed"]["reason"]] += 1
    object_reason_cards.setdefault(o["unparsed"]["reason"], set()).add(cid)
for reason, n in sorted(object_reasons.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"解析不出物件 {reason}: {n} 個 / {len(object_reason_cards[reason])} 張")

passed_cards, passed_segs, only_one, mismatch = 0, 0, Counter(), 0
for card in with_text:
    failures = check_card(card)
    failed = {(f["block"], f["segment"]) for f in failures}
    mismatch += sum(1 for f in failures if f["reason"] != REASON_NO_TEMPLATE and f.get("rendered") is not None)
    passed_segs += sum(1 for block in card["blocks"] for b, s in iter_segments(block)
                       if (b["id"], s["id"]) not in failed and not s.get("unstructured"))
    if not failures:
        passed_cards += 1
        continue
    keys = {f["detail"] if f["reason"] == REASON_NO_TEMPLATE else f["reason"] for f in failures}
    if len(keys) == 1:
        only_one[keys.pop()] += 1
print(f"反向檢查通過 段: {passed_segs}")
print(f"反向檢查通過 佔全部段: {passed_segs / len(segs):.1%}")
print(f"反向檢查通過 佔解析出的段: {passed_segs / parsed:.1%}")
print(f"字面不符 段: {mismatch}")
print(f"整張通過 張: {passed_cards}")
print(f"只差一種原因 張: {sum(only_one.values())}")
for key, n in sorted(only_one.items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"只差一種原因 {key} 張: {n}")


def query(q):
    if not set(q["actions"]) <= KNOWN:
        return "不認得"
    groups = run_query(cards, card_list, q)["groups"]
    return (f"{len(groups['全部'])} / {len(groups.get('經引用', []))} / "
            f"{len(groups['未解析'])}")


print("查詢(命中 / 經引用 / 未解析):")
for action in COMMON + NEW:
    print(f"查詢 {action}: {query({'actions': [action]})}")
for action, polarity in POLAR:
    print(f"查詢 {action},極性{polarity}: "
          f"{query({'actions': [action], 'polarities': [polarity]})}")
for action in CONDITION:
    print(f"查詢 {action},條件段開: {query({'actions': [action], 'include_condition': True})}")
for action in REPLACEMENT:
    print(f"查詢 {action},代替開: {query({'actions': [action], 'replacement': True})}")
print(f"查詢 加入手牌,只看取對象: {query({'actions': ['加入手牌'], 'targeting': True})}")
print(f"查詢 破壞,只看取對象: {query({'actions': ['破壞'], 'targeting': True})}")
