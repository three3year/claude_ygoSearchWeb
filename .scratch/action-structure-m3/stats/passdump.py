# 每張卡的反向檢查結果與全庫合計(JSON 到 stdout),給 regress.py 比前後。
# 跑法:python -X utf8 .scratch/action-structure-m3/stats/passdump.py <repo 根> [產物路徑] > 輸出.json
#   用 <repo 根>/script/action_structure 的程式讀產物;產物預設 <repo 根>/data/action_structure.json。
#   規則票:改前在工作樹根跑一次存「前」,改完重建產物(可建到暫存檔,當 [產物路徑] 傳入)再跑一次存「後」,
#   然後 python -X utf8 .scratch/action-structure-m3/stats/regress.py 前.json 後.json。
# 定義與 .scratch/action-structure-m2/stats/m2_compare.py 一致(里程碑二摘要數字的出處):
#   段 = 每張卡 blocks 經 structure_shape.iter_segments 走出的段(含內嵌效果裡的段)。
#   段解析出 = 段的 unparsed 為空且不是 unstructured。
#   段通過 = 段不在 reverse_check.check_card 的不通過清單(以 (區塊, 段) 對)且不是 unstructured。
#   整張通過 = 有官方日文(卡的 unparsed 為空)且 check_card 回空清單;無官方日文的卡記不通過。
#   物件 = 卡的 objects 全部(含 o0「このカード」);解析不出物件 = unparsed 不為空的物件。
# 輸出:{"合計": {...}, "卡": {"<卡號>": {...}, ...}},卡號依數值排序、一張卡一行;
#   每張卡附「不通過」= check_card 的 [區塊, 段, 原因, 細節] 清單(照 check_card 的順序;
#   字面不符的細節是「寫回「…」≠原文「…」」)。
# 輸出決定性:排序固定、不印時間與路徑。全庫跑一次約 6 秒(輸出約 6 MB)。
import json
import os
import sys
from collections import Counter

ROOT = sys.argv[1]
PRODUCT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "data", "action_structure.json")
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from card_structure import load_structures  # noqa: E402
from reverse_check import check_card  # noqa: E402
from structure_shape import iter_segments  # noqa: E402


def card_row(card):
    segs = [(b, s) for block in card["blocks"] for b, s in iter_segments(block)]
    has_text = not card["unparsed"]
    failures = check_card(card) if has_text else []
    failed = {(f["block"], f["segment"]) for f in failures}
    bad_objects = [o for o in card["objects"] if o.get("unparsed")]
    return {
        "卡名": card["name_ja"],
        "有官方日文": has_text,
        "整張通過": has_text and not failures,
        "段": len(segs),
        "段解析出": sum(1 for _, s in segs if not s["unparsed"] and not s.get("unstructured")),
        "段通過": sum(1 for b, s in segs
                    if has_text and (b["id"], s["id"]) not in failed and not s.get("unstructured")),
        "未結構化段": sum(1 for _, s in segs if s.get("unstructured")),
        "物件": len(card["objects"]),
        "解析不出物件": len(bad_objects),
        "不通過": [[f["block"], f["segment"], f["reason"], failure_detail(f)] for f in failures],
    }, Counter(o["unparsed"]["reason"] for o in bad_objects)


def failure_detail(f):
    """check_card 的細節;字面不符沒有細節,改附寫回與原文。"""
    if f["detail"] is None and f["rendered"] is not None:
        return f"寫回「{f['rendered']}」≠原文「{f['original']}」"
    return f["detail"]


def main():
    with open(PRODUCT, encoding="utf-8") as f:
        cards = load_structures(f.read())
    rows, object_reasons = {}, Counter()
    for card in sorted(cards, key=lambda c: int(c["id"])):
        row, reasons = card_row(card)
        rows[str(card["id"])] = row
        object_reasons.update(reasons)

    def total(key):
        return sum(r[key] for r in rows.values())

    segs, parsed = total("段"), total("段解析出")
    totals = {
        "卡": len(rows),
        "有官方日文 張": sum(1 for r in rows.values() if r["有官方日文"]),
        "段": segs,
        "段解析出": parsed,
        "段解析出比例": f"{parsed / segs:.1%}",
        "未結構化 段": total("未結構化段"),
        "反向檢查通過 段": total("段通過"),
        "整張通過 張": sum(1 for r in rows.values() if r["整張通過"]),
        "物件": total("物件"),
        "解析不出物件": total("解析不出物件"),
    }
    for reason, n in sorted(object_reasons.items(), key=lambda kv: (-kv[1], kv[0])):
        totals[f"解析不出物件 {reason}"] = n

    out = sys.stdout
    out.write('{"合計": ' + json.dumps(totals, ensure_ascii=False, indent=1) + ',\n"卡": {\n')
    out.write(",\n".join(json.dumps(cid, ensure_ascii=False) + ": " + json.dumps(row, ensure_ascii=False)
                         for cid, row in rows.items()))
    out.write("\n}}\n")


main()
