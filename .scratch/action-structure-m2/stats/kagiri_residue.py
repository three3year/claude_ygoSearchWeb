"""m2 票 03:全庫「限り」的去向(交站主)。

用法(repo 根):python -X utf8 .scratch/action-structure-m2/stats/kagiri_residue.py <產物路徑> [每類列幾段]
只讀產物、只用標準庫。段原文含「限り」的段依先中先贏歸一類:
  1 剝成前提:段的前提裡有 form 以「限り」開頭的位置/存在原子
  2 留在述語:段的原述語字面含「限り」
  3 留在物件:段的對象線物件(在本段新建)的條件式裡有「解析不出」原子、字面含「限り」
  4 可能な限り:「可能な限り」是數量副詞,不是前提
  5 其他:段解析不出(子句解析不出等)而沒有述語字面,或「限り」在別的格
每類印段數、張數與前幾段的卡號與原文。
"""
import json
import sys
from collections import defaultdict


def premise_atoms(premise):
    if not premise:
        return []
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    return [a.get("arg", a) if a.get("op") == "非" else a for a in atoms]


def unparsed_texts(condition):
    if not isinstance(condition, dict):
        return []
    if condition.get("op") == "解析不出":
        return [condition.get("text") or ""]
    out = []
    for arg in condition.get("args", []):
        out += unparsed_texts(arg)
    if "arg" in condition:
        out += unparsed_texts(condition["arg"])
    return out


def classify(seg, text, objects):
    if any((a.get("form") or "").startswith("限り") for a in premise_atoms(seg.get("premise"))):
        return "1 剝成前提"
    if "限り" in (seg.get("predicate") or ""):
        return "2 留在述語"
    for line in seg.get("lines", []):
        obj = objects.get(line["object"])
        if obj and any("限り" in t for t in unparsed_texts(obj.get("condition"))):
            return "3 留在物件"
    if "可能な限り" in text:
        return "4 可能な限り"
    return "5 其他"


def main():
    path = sys.argv[1]
    show = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    groups = defaultdict(list)
    for raw in open(path, encoding="utf-8"):
        raw = raw.strip().rstrip(",")
        if not raw.startswith('{"id"'):
            continue
        card = json.loads(raw)
        objects = {o["id"]: o for o in card.get("objects", [])}
        for block in card.get("blocks", []):
            for seg in block.get("segments", []):
                text = block["text"][seg["span"][0]:seg["span"][1]]
                if "限り" in text:
                    groups[classify(seg, text, objects)].append((card["id"], text))
    total = sum(len(v) for v in groups.values())
    print(f"段原文含「限り」:{total} 段 / {len({c for v in groups.values() for c, _ in v})} 張")
    for label in sorted(groups):
        items = groups[label]
        print(f"\n{label}:{len(items)} 段 / {len({c for c, _ in items})} 張")
        for cid, text in items[:show]:
            print(f"  {cid} {text}")


if __name__ == "__main__":
    main()
