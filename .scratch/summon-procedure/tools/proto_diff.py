import json, sys
from collections import Counter
sys.stdout.reconfigure(encoding="utf-8")
import os
real = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "effect-tokenize", "frames.json"), encoding="utf-8"))
proto = json.load(open(sys.argv[1], encoding="utf-8"))
P = "召喚手續"
diff_keys = Counter(); order_shift = 0; ex = []
recs_with = 0
for r, p in zip(real, proto):
    assert (r["card"], r["section"], r["index"]) == (p["card"], p["section"], p["index"])
    pf = [f for f in p["frames"] if f.get("position") != P]
    if len(pf) != len(p["frames"]):
        recs_with += 1
    if len(pf) != len(r["frames"]):
        diff_keys["框數"] += 1; ex.append((r["card"], "框數", len(r["frames"]), len(pf))); continue
    for a, b in zip(r["frames"], pf):
        for k in set(a) | set(b):
            if a.get(k) != b.get(k):
                if k == "order":
                    order_shift += 1
                else:
                    diff_keys[k] += 1
                    if len(ex) < 15:
                        ex.append((r["card"], k, a.get(k), b.get(k)))
print("含召喚手續框的句", recs_with, "既有框只差 order:", order_shift, "其他差異", dict(diff_keys))
for e in ex:
    print(json.dumps(e, ensure_ascii=False)[:400])
