import json
import os, sys
from collections import Counter
HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "effect-tokenize")
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import constraints
P="召喚手續"; constraints.POSITIONS += (P,)
import export_common; export_common.FRAMES = sys.argv[1]
import export_frames
faces = export_common.load_faces()
c = Counter(); ex = {}
for s in export_common.load_sentences():
    for fr, row, v in export_frames.frame_rows(s, faces):
        if fr["position"] == P:
            k = (fr["action"], v.mode, v.why, fr.get("agent"), bool(fr.get("topic")))
            c[k] += 1; ex.setdefault(k, (s["card"], fr["clause"][:70], fr.get("topic"), fr.get("object")))
for k, n in sorted(c.items(), key=lambda x: (x[0][0], -x[1])):
    print(n, k, ex[k])
