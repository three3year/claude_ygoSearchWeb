# 規格〔區域的方〕:對象線的從、到上各種方的條數(含「自身」「持有者」與沒寫方的區域)。
# 跑法(repo 根):python -X utf8 .scratch/action-search-coverage/stats/side_values.py
# 讀版控裡的 data/action_structure.json;只走區塊的段(內嵌效果的段不算),數的是區域條目。
import json
import os
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    structures = json.load(f)

counts = Counter()
for card in structures:
    for block in card.get("blocks") or []:
        for seg in block.get("segments", []):
            for line in seg.get("lines") or []:
                for end in ("from", "to"):
                    for zone in ((line.get(end) or {}).get("zones") or []):
                        counts[zone.get("side") or "沒寫方"] += 1

for side, n in counts.most_common():
    print(f"{side} {n:,}")
