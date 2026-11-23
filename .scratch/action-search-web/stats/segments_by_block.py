"""段落在哪一種區塊、那個區塊有沒有①②③編號:量「用編號就能對回效果句」的段佔多少。

在 repo 根執行:python -X utf8 .scratch/action-search-web/stats/segments_by_block.py
段含內嵌效果裡的段(`iter_segments`),算在最外層區塊上。區塊本身標解析不出的沒有段,另外計數。
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from structure_shape import iter_segments  # noqa: E402


def main():
    with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
        raw = json.load(f)
    cards = raw["cards"] if isinstance(raw, dict) else raw
    by_kind = Counter()
    blocks_without_segments = 0
    for card in cards:
        for block in card.get("blocks") or []:
            if "segments" not in block:        # 區塊本身標解析不出,沒有段
                blocks_without_segments += 1
                continue
            n = sum(1 for _ in iter_segments(block))
            label = "有編號" if block.get("label") else "沒有編號"
            by_kind[(block.get("kind") or "(種類判不出)", label)] += n
    total = sum(by_kind.values())
    print(f"段總數 {total:,}")
    for (kind, label), n in by_kind.most_common():
        print(f"{kind}\t{label}\t{n:,}\t{n / total:.1%}")
    labelled = sum(n for (_, label), n in by_kind.items() if label == "有編號")
    print(f"有編號的區塊裡的段 {labelled:,}({labelled / total:.1%})")
    print(f"沒有段的區塊(區塊標解析不出){blocks_without_segments:,}")


if __name__ == "__main__":
    main()
