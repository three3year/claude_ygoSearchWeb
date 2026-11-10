"""票 10(離場)之後的盤點:離場段有幾段、寫不寫得回;含「離れ」而仍解析不出的段依原因列出。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c5c_leave_after.py [--full]
讀 data/action_structure.json(要看「改後」就先就地重建產物,看完還原)。
`c5_leave_and_golden.py` 表一只數原因是「述語解析不出」的段;規則補上後,剩下的段多半換了原因
(述語語尾不明、指回的物件找不到…),這裡不分原因全部列。預設每種原因列 5 句,`--full` 全列。
"""
import collections
import sys

from common import all_segments, cards, short
from reverse_check import check_card

LEAVE = "離場"


def main():
    full = "--full" in sys.argv
    kinds = collections.Counter()          # 離場段:段類別
    destinations = 0                       # 自我限制的去處段(做代替的段)
    passed = collections.Counter()         # 離場段與去處段:反向檢查通過/不通過
    failed = collections.defaultdict(list)
    unparsed = collections.defaultdict(list)
    for card in cards():
        if card["unparsed"]:
            continue
        failures = None
        leaving = {seg["id"] for _, seg in all_segments(card)
                   if LEAVE in seg["actions"] and not seg["unparsed"]}
        for _, seg in all_segments(card):
            destination = seg["replaces"] in leaving and not seg["unparsed"]
            if seg["unparsed"]:
                if "離れ" in seg["text"]:
                    unparsed[seg["unparsed"]["reason"]].append((card, seg))
                continue
            if seg["id"] not in leaving and not destination:
                continue
            if seg["id"] in leaving:
                kinds[seg["kind"]] += 1
            destinations += destination
            if failures is None:
                failures = {f["segment"]: f for f in check_card(card)}
            failure = failures.get(seg["id"])
            passed["通過" if failure is None else "不通過"] += 1
            if failure is not None:
                failed[failure["detail"] or failure["reason"]].append((card, seg))
    print(f"離場段(解析得出): {sum(kinds.values())} 段;"
          + "、".join(f"{kind} {n}" for kind, n in kinds.most_common()))
    print(f"自我限制的去處段(做代替的段,解析得出): {destinations} 段")
    print(f"以上兩種段的反向檢查: 通過 {passed['通過']}、不通過 {passed['不通過']}")
    for title, groups in (("反向檢查不通過", failed), ("含「離れ」而解析不出的段", unparsed)):
        print(f"\n{title}: {sum(map(len, groups.values()))} 段")
        for reason, rows in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            print(f"- {reason}: {len(rows)} 段 / {len({card['id'] for card, _ in rows})} 張")
            for card, seg in rows if full else rows[:5]:
                print(f"    {card['name_ja']} {card['id']}「{short(seg['text'], 80)}」")


if __name__ == "__main__":
    main()
