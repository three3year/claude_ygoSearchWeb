# 規格 3 用:真實匯出檔 → 候選編碼的 data.js 增量(raw/gz);寫出給 measure_eval.js 讀的投影。
import collections, gzip, json, os, sys

ROOT, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(ROOT, ".scratch", "effect-tokenize"))
import predicate as P
from closed_values import PLAYERS, ZONES

doc = json.load(open(os.path.join(ROOT, "data", "action_frames.json"), encoding="utf-8"))
raw = open(os.path.join(ROOT, "web", "data.js"), encoding="utf-8").read()
i = raw.index("window.VOCAB=")
cards = json.loads(raw[len("window.CARD_DATA="):i].rstrip().rstrip(";"))
base = raw

def size(text):
    b = text.encode("utf-8")
    return len(b), len(gzip.compress(b, 9))

heads = collections.Counter()
lemmas = collections.Counter()
for r in doc["句"]:
    for f in r["frames"]:
        lemmas[f["action"]] += 1
        for segs in (f.get("phrases") or {}).values():
            for s in segs:
                heads[s["head"]] += 1
freq = lambda c: [k for k, _ in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))]
HEADS = {h: n for n, h in enumerate(freq(heads))}
HEADS_ALPHA = {h: n for n, h in enumerate(sorted(heads))}
LEMMAS = {h: n for n, h in enumerate(sorted(lemmas))}
def code(table):
    return {v: n + 1 for n, v in enumerate(table)}  # 0 = 沒有
POS, POL, VOI, NEG, AGT, MAN, PM = map(code, (P.POSITIONS if hasattr(P, "POSITIONS") else P.DOMAIN["位置"],
                                             P.DOMAIN["極性"], P.DOMAIN["態"], P.DOMAIN["否定形"], P.DOMAIN["施事者"],
                                             P.DOMAIN["方式類"], P.DOMAIN["動作對象"]))
HK, QK = code(P.DOMAIN["中心詞類"]), code(P.DOMAIN["數量類"])
MOD = {v: 1 << n for n, v in enumerate(P.DOMAIN["修飾語類"])}
PL = {v: n for n, v in enumerate(PLAYERS)}
ZN = {v: n for n, v in enumerate(ZONES)}
pair = lambda p, z: PL[p] * len(ZONES) + ZN[z]

def seg(s, table):
    t = [table[s["head"]], HK.get(s.get("head_kind"), 0), QK.get(s.get("quantity"), 0),
         sum(MOD[m] for m in s.get("modifiers") or ())]
    while len(t) > 1 and not t[-1]:
        t.pop()
    return t

def frame(f, table, heads_on=True):
    rg = f.get("regions") or {}
    ph = f.get("phrases") or {}
    t = [LEMMAS[f["action"]], POS[f["position"]], POL.get(f.get("polarity"), 0), VOI.get(f.get("voice"), 0),
         NEG.get(f.get("negation"), 0), AGT.get(f.get("agent"), 0), MAN.get(f.get("manner_kind"), 0),
         PM.get(f.get("patient_mode"), 0),
         [pair(*x) for x in rg.get("source") or ()], [pair(*x) for x in rg.get("goal") or ()],
         [pair(*x) for x in rg.get("place") or ()],
         [seg(s, table) for s in ph.get("patient") or ()], [seg(s, table) for s in ph.get("goal") or ()]]
    while len(t) > 2 and (t[-1] == 0 or t[-1] == []):
        t.pop()
    return t

tag = json.load(open(os.path.join(ROOT, "data", "tag_cards.json"), encoding="utf-8"))
clauses = {t["id"]: t.get("clauses") or [] for t in tag}
rows = {(r["card"], r["section"], r["index"]): r for r in doc["句"]}
covered = {c for c, _, _ in rows}

def compact(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))

def build(table, dedupe=False):
    uniq, out = {}, []
    lines = []
    for c in cards:
        cid = c["id"]
        e = dict(c)
        for k in ("ae", "ac", "aes", "aen", "acs", "acn"):
            e.pop(k, None)
        if cid in covered:
            fr = []
            for cl in clauses.get(cid, ()):
                row = rows.get((cid, cl.get("section"), cl.get("index")))
                frames = [frame(f, table) for f in row["frames"]] if row else []
                if dedupe:
                    frames = [uniq.setdefault(compact(x), len(uniq)) for x in frames]
                fr.append(frames)
            e["fr"] = fr
        lines.append(compact(e))
    return lines, uniq

def old_lines():
    return [compact(c) for c in cards]

base_cards = ",\n".join(old_lines())
print("現在卡片段", size(base_cards), "整檔", size(raw))
no_old = ",\n".join(compact({k: v for k, v in c.items() if k not in ("ae", "ac", "aes", "aen", "acs", "acn")}) for c in cards)
print("拿掉舊六欄", size(no_old))
heads_table = compact(freq(heads))
print("中心詞表(頻率序)", len(heads), size(heads_table), "詞元表", len(lemmas), size(compact(sorted(lemmas))))
lines, _ = build(HEADS)
s = size(",\n".join(lines))
print("C 頻率序:卡片段", s, "相對拿掉舊欄", s[0] - size(no_old)[0], s[1] - size(no_old)[1],
      "相對現在", s[0] - size(base_cards)[0], s[1] - size(base_cards)[1])
la, _ = build(HEADS_ALPHA)
s2 = size(",\n".join(la))
print("C 字典序:卡片段", s2, "相對現在", s2[0] - size(base_cards)[0], s2[1] - size(base_cards)[1])
ld, uniq = build(HEADS, dedupe=True)
s3 = size(",\n".join(ld))
ut = "[" + ",".join(uniq) + "]"
print("D 框表:唯一框", len(uniq), "卡片段", s3, "框表", size(ut), "合計相對現在",
      s3[0] + size(ut)[0] - size(base_cards)[0], s3[1] + size(ut)[1] - size(base_cards)[1])
# 新舊並存(舊欄留著)
both = []
for line, c in zip(lines, cards):
    e = json.loads(line)
    for k in ("ae", "ac", "aes", "aen", "acs", "acn"):
        if k in c:
            e[k] = c[k]
    both.append(compact(e))
s4 = size(",\n".join(both))
print("並存:卡片段", s4, "相對現在", s4[0] - size(base_cards)[0], s4[1] - size(base_cards)[1])
cat = [{k: r[k] for k in ("name", "path", "predicate", "cards")} for r in doc["目錄"]]
print("VOCAB 目錄(無雜湊)", size(compact(cat)))
print("句與 tx 對不上:", sum(1 for c in cards if c["id"] in covered and len(clauses.get(c["id"], ())) != len(c.get("tx", ()))))
print("卡面在索引外:", len(covered - {c["id"] for c in cards}))
print("frame per clause max", max(len(r["frames"]) for r in doc["句"]))
json.dump({"heads": freq(heads), "lemmas": sorted(lemmas), "pos": list(POS), "pol": list(POL), "voi": list(VOI),
           "neg": list(NEG), "agt": list(AGT), "man": list(MAN), "pm": list(PM), "hk": list(HK), "qk": list(QK),
           "mod": list(MOD), "players": list(PLAYERS), "zones": list(ZONES),
           "cards": [json.loads(l) for l in lines]},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
# D 並存:舊六欄留著
both_d = []
for line, c in zip(ld, cards):
    e = json.loads(line)
    for k in ("ae", "ac", "aes", "aen", "acs", "acn"):
        if k in c:
            e[k] = c[k]
    both_d.append(compact(e))
s5 = size(",\n".join(both_d))
print("D 並存:卡片段", s5, "框表另計;合計相對現在", s5[0] + size(ut)[0] - size(base_cards)[0], s5[1] + size(ut)[1] - size(base_cards)[1])
# 領起句與 ● 子句的效果類型
kinds = collections.Counter()
by = {(t["id"], cl.get("section"), cl.get("index")): cl.get("kind") for t in tag for cl in t.get("clauses") or []}
for (cid, sec, idx), kind in by.items():
    if "-●" in str(idx):
        lead = by.get((cid, sec, str(idx).split("-")[0]))
        kinds["同" if lead == kind else "不同" if lead else "無領起句"] += 1
print("● 子句對領起句的效果類型", dict(kinds))
print("動作框架", sum(len(r["frames"]) for r in doc["句"]), "句", len(doc["句"]), "空框句", sum(1 for r in doc["句"] if not r["frames"]), "卡", len(covered))
# 領起句題 (b):涵蓋卡的 ● 子句與領起句(領起句 = index 去掉最後一段 -●n)
st = collections.Counter()
fl_cards = {}
for c in cards:
    cid = c["id"]
    if cid not in covered:
        continue
    cls = clauses.get(cid, ())
    pos = {(cl.get("section"), cl.get("index")): n for n, cl in enumerate(cls)}
    arr = [-1] * len(cls)
    for n, cl in enumerate(cls):
        idx = str(cl.get("index"))
        if "-●" in idx:
            st["●"] += 1
            lead_key = (cl.get("section"), idx.rsplit("-●", 1)[0])
            if "-●" in lead_key[1] or "-" in lead_key[1]:
                st["領起句本身帶連字號"] += 1
            if lead_key not in pos:
                st["找不到領起句"] += 1
                continue
            arr[n] = pos[lead_key]
            lead = cls[pos[lead_key]]
            st["效果類型同" if lead.get("kind") == cl.get("kind") else "效果類型不同"] += 1
    if any(x >= 0 for x in arr):
        fl_cards[cid] = arr
print("涵蓋卡 ● 子句", dict(st), "帶 ● 的卡", len(fl_cards), "領起句", len({(k, v) for k, a in fl_cards.items() for v in a if v >= 0}))
print("fl 欄", size(",".join(compact(a) for a in fl_cards.values())))
lf = collections.Counter()
for cid, a in fl_cards.items():
    cls = clauses[cid]
    for v in {x for x in a if x >= 0}:
        r = rows.get((cid, cls[v].get("section"), cls[v].get("index")))
        for f in (r["frames"] if r else ()):
            lf[f["position"]] += 1
print("領起句框", dict(lf), sum(lf.values()))
