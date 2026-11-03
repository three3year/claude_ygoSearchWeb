import json
import os, sys
from collections import Counter
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "effect-tokenize")
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import constraints  # noqa: E402
P = "召喚手續"
constraints.POSITIONS = constraints.POSITIONS + (P,)
import export_common  # noqa: E402
export_common.FRAMES = sys.argv[1]
import export_frames  # noqa: E402
import frames as F  # noqa: E402

cards = {c["id"]: c for c in json.load(open(os.path.join(HERE, "..", "..", "data", "cards.json"), encoding="utf-8"))}
faces = export_common.load_faces()
EXTRA_BITS = 0x40 | 0x2000 | 0x800000 | 0x4000000  # 融合 S X Link
sents = export_common.load_sentences()
agent = Counter(); mode = Counter(); why = Counter(); src = Counter(); zutsu = []; regions = Counter(); noreg = []
for s in sents:
    summon_src = [f.get("source") for f in s["frames"] if f.get("subtype") == "召喚條件" and f.get("procedure")]
    for fr, row, v in export_frames.frame_rows(s, faces):
        if fr["position"] != P:
            continue
        agent[(fr.get("agent"), fr.get("agent_source"))] += 1
        mode[v.mode] += 1
        why[v.why] += 1
        extra = bool(cards[s["card"]]["type"] & EXTRA_BITS)
        src[("有來源" if any(summon_src) else "沒來源", "EX" if extra else "主牌組")] += 1
        if "ずつ" in fr["clause"]:
            q = [seg.get("quantity") for ph in (fr.get("phrases") or {}).values() for seg in ph["segments"]]
            zutsu.append((s["card"], fr["action"], q))
        regions[tuple(sorted((fr.get("regions") or {}).keys()))] += 1
        if not fr.get("regions"):
            noreg.append((s["card"], fr["action"], fr.get("object"), fr.get("source"), fr.get("goal")))
print("施事者", agent.most_common())
print("動作對象", mode.most_common())
print("理由", why.most_common())
print("召喚來源", src.most_common())
print("ずつ", len(zutsu))
for z in zutsu:
    print("  ", json.dumps(z, ensure_ascii=False)[:200])
print("結構化區域鍵", regions.most_common())
print("沒區域", len(noreg))
for n in noreg[:15]:
    print("  ", json.dumps(n, ensure_ascii=False))
