# 比兩份 passdump.py 輸出:規則票的「改前通過、改後不通過」張數(spec「反向檢查與報告」、故事 42)。
# 跑法:python -X utf8 .scratch/action-structure-m3/stats/regress.py <前.json> <後.json>
#   前、後各用 passdump.py 產生(見該檔檔頭)。只用標準庫,不讀 repo 的程式。
# 印:全庫合計前後對照(前 / 後 / 差);「改前通過、改後不通過」張數與卡號清單,每張附數字變了的欄
#     (段、段解析出、段通過、未結構化段、物件、解析不出物件)與改後的不通過清單;「改前不通過、改後通過」張數。
# exit code:0 = 沒有回歸;1 = 有「改前通過、改後不通過」的卡;2 = 兩份的卡片集合不同(不比)。
import json
import sys

COUNTS = ("段", "段解析出", "段通過", "未結構化段", "物件", "解析不出物件")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt_delta(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return f"{b - a:+d}" if isinstance(a, int) and isinstance(b, int) else f"{b - a:+g}"
    return "" if a == b else "變"


def main():
    before, after = load(sys.argv[1]), load(sys.argv[2])
    cards_b, cards_a = before["卡"], after["卡"]
    if set(cards_b) != set(cards_a):
        only_b = sorted(set(cards_b) - set(cards_a), key=int)
        only_a = sorted(set(cards_a) - set(cards_b), key=int)
        print(f"錯誤:卡片集合不同(只在前 {len(only_b)} 張、只在後 {len(only_a)} 張)")
        print(f"只在前: {', '.join(only_b[:50])}")
        print(f"只在後: {', '.join(only_a[:50])}")
        return 2

    print("全庫合計(前 / 後 / 差):")
    keys = list(before["合計"]) + [k for k in after["合計"] if k not in before["合計"]]
    for key in keys:
        a, b = before["合計"].get(key, "—"), after["合計"].get(key, "—")
        print(f"  {key}: {a} / {b} / {fmt_delta(a, b)}".rstrip(" /"))

    ids = sorted(cards_b, key=int)
    regressed = [c for c in ids if cards_b[c]["整張通過"] and not cards_a[c]["整張通過"]]
    fixed = [c for c in ids if not cards_b[c]["整張通過"] and cards_a[c]["整張通過"]]

    print(f"\n改前通過、改後不通過 張: {len(regressed)}")
    for cid in regressed:
        b, a = cards_b[cid], cards_a[cid]
        changed = [f"{k} {b[k]}→{a[k]}" for k in COUNTS if b[k] != a[k]]
        print(f"  {cid} {a['卡名']}:{'、'.join(changed) if changed else '段數字沒變'}")
        for block, seg, reason, detail in a["不通過"]:
            print(f"    {block} {seg or '(區塊)'} {reason}:{detail}")
    print(f"\n改前不通過、改後通過 張: {len(fixed)}")
    return 1 if regressed else 0


sys.exit(main())
