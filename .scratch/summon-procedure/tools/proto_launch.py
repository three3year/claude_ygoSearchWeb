"""召喚手續框的發動位置:召喚來源(寫了照寫;沒寫時 主牌組→手牌、額外→額外牌組;或沒寫時 預設場上)比較動作對象判定。"""
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
import patient  # noqa: E402
import places  # noqa: E402

cards = {c["id"]: c for c in json.load(open(os.path.join(HERE, "..", "..", "data", "cards.json"), encoding="utf-8"))}
EXTRA_BITS = 0x40 | 0x2000 | 0x800000 | 0x4000000
STATE = {"card": None, "mode": None}
orig_launch = patient.launch


def zones_of(text):
    out = set()
    for term, zone in places.ZONE_TERMS:
        if term in text:
            out.add(zone)
    return out


def launch(frames_, section="main"):
    if STATE["mode"] and any(f.get("position") == P for f in frames_):
        src = next((f.get("source") for f in frames_ if f.get("subtype") == "召喚條件" and f.get("procedure")), None)
        if src and zones_of(src):
            return patient.Launch(zones_of(src), "召喚來源")
        if STATE["mode"] == "bytype":
            extra = cards[STATE["card"]]["type"] & EXTRA_BITS
            return patient.Launch({"額外牌組" if extra else "手牌"}, "召喚來源預設")
    return orig_launch(frames_, section)


patient.launch = launch
faces = export_common.load_faces()
sents = export_common.load_sentences()


def run(mode):
    STATE["mode"] = mode
    out = {}
    for s in sents:
        STATE["card"] = s["card"]
        for fr, row, v in export_frames.frame_rows(s, faces):
            if fr["position"] == P:
                out[(s["card"], s["section"], s["index"], fr["order"])] = (v.mode, v.why, fr["clause"], fr["action"])
    return out


base = run(None)
written = run("written")
bytype = run("bytype")
for name, other in (("只用寫明的來源", written), ("寫明+沒寫依卡種", bytype)):
    ch = [(k, base[k], other[k]) for k in base if base[k][:2] != other[k][:2]]
    print(name, "對預設場上變了", len(ch), "框", Counter((b[0], o[0]) for k, b, o in ch))
    for k, b, o in ch[:12]:
        print("   ", k[0], b[3], b[:2], "→", o[:2], "|", b[2][:70])
ch = [(k, written[k], bytype[k]) for k in base if written[k][:2] != bytype[k][:2]]
print("沒寫依卡種 vs 沒寫照預設場上:差", len(ch), Counter((b[0], o[0]) for k, b, o in ch))
for k, b, o in ch[:15]:
    print("   ", k[0], b[3], b[:2], "→", o[:2], "|", b[2][:80])
print("最終(寫明+依卡種)動作對象", Counter(v[0] for v in bytype.values()).most_common())
fin = Counter("此卡" if v[3] == "重ねる" else v[0] for v in bytype.values())
print("最終再加 重ねる 一律此卡", fin.most_common())
