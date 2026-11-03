"""原型匯出:讀 proto frames 檔,算目錄四個位置的張數,與現行 data/action_frames.json 比。"""
import json
import os
import sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "effect-tokenize")
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import constraints  # noqa: E402

P = "召喚手續"
constraints.POSITIONS = constraints.POSITIONS + (P,)
import export_common  # noqa: E402

export_common.FRAMES = sys.argv[1]
import export_frames  # noqa: E402
import catalog  # noqa: E402

doc, problems = export_frames.export(export_common.load_sentences(), export_common.load_faces(), catalog.load())
print("problems", len(problems), problems[:3])
old = json.load(open(os.path.join(HERE, "..", "..", "data", "action_frames.json"), encoding="utf-8"))
oldrows = {(tuple(r["path"]), r["predicate"] is None): r for r in old["目錄"]}
print("統計.位置", doc["統計"]["位置"])
sets = export_frames.query_sets(catalog.load(), doc["句"])
cat = catalog.load()
changed = []
for q in cat.queries:
    s = sets[q.name]
    three = set().union(*(s[p] for p in constraints.POSITIONS[:3]))
    four = three | s[P]
    if s[P]:
        changed.append((q.name, len(s[P]), len(four - three), len(three), s["效果"] and len(s["效果"])))
print("具名查詢有召喚手續張數的列", len(changed), "/", len(cat.queries))
for c in sorted(changed, key=lambda c: -c[1]):
    print("  %s:召喚手續 %d 張;只在召喚手續的 %d 張;三位置合計 %d;效果 %s" % c)
zero_eff = [(q.name, {p: len(sets[q.name][p]) for p in constraints.POSITIONS}) for q in cat.queries
            if not sets[q.name]["效果"] and sets[q.name][P]]
print("效果位 0 張而召喚手續有張數的列", zero_eff)
mism = [r["name"] for r in doc["目錄"] if any(r["cards"][p] != oldrows[(tuple(r["path"]), r["predicate"] is None)]["cards"][p]
                                               or r["hash"][p] != oldrows[(tuple(r["path"]), r["predicate"] is None)]["hash"][p]
                                               for p in constraints.POSITIONS[:3])]
print("三個位置張數或雜湊有變的目錄列", mism)
for r in doc["目錄"]:
    if r["predicate"] is None and r["cards"][P]:
        print("  節點 %s 召喚手續 %d" % ("/".join(r["path"]), r["cards"][P]))
