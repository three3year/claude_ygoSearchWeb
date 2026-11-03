"""現行 frames.json 的召喚條件手續步驟統計(動作種類、來源有無、數字怪值、ずつ)。"""
import json, os, sys, re
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "effect-tokenize", "frames.json"), encoding="utf-8"))
sc = 0; sc_cards = set(); proc_frames = 0; proc_cards = set(); steps = 0
acts = Counter(); act_cards = defaultdict(set); act_ex = {}
nosource = Counter(); nosource_ex = defaultdict(list)
zuts = []
weird = []
for r in d:
    for f in r["frames"]:
        if f.get("subtype") != "召喚條件":
            continue
        sc += 1; sc_cards.add(r["card"])
        p = f.get("procedure") or []
        if not p:
            continue
        proc_frames += 1; proc_cards.add(r["card"])
        src = f.get("source")
        nosource["有來源" if src else "沒來源"] += 1
        if not src and len(nosource_ex["沒來源"]) < 400:
            nosource_ex["沒來源"].append((r["card"], f["form"], f["clause"]))
        if "ずつ" in f["clause"]:
            zuts.append((r["card"], f["clause"], p))
        for s in p:
            steps += 1
            a = s["action"]; acts[a] += 1; act_cards[a].add(r["card"])
            act_ex.setdefault(a, (r["card"], f["clause"], s))
            if re.search(r"\d{4,}", json.dumps(s, ensure_ascii=False)) or re.fullmatch(r"[\d０-９]+", a):
                weird.append((r["card"], s, f["clause"]))
print("召喚條件框", sc, "卡", len(sc_cards), "手續非空框", proc_frames, "卡", len(proc_cards), "步", steps)
print("來源", dict(nosource))
for a, n in acts.most_common():
    c, cl, s = act_ex[a]
    print(f"{n:4d} {len(act_cards[a]):4d}張 {a} | 例 {c}: {json.dumps(s, ensure_ascii=False)} | {cl[:90]}")
print("== 數字怪值", len(weird))
for w in weird[:20]:
    print(w[0], json.dumps(w[1], ensure_ascii=False), "|", w[2][:100])
print("== ずつ", len(zuts))
for z in zuts[:20]:
    print(z[0], z[1][:110], json.dumps(z[2], ensure_ascii=False)[:200])
