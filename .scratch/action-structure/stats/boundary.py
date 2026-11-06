# 舊式卡(官方文本無①②③)效果邊界多來源比對:拆句表(clause_splits)、ja-JP.cdb 的①編號、en-US.cdb 英文分組、官方補足『』引用。
# 跑法:python -X utf8 boundary.py [repo 根,預設目前目錄] [共識集 JSON 輸出路徑,省略則不輸出]
import collections
import json
import os
import re
import sqlite3
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OUT_JSON = sys.argv[2] if len(sys.argv) > 2 else None

NUM = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
TYPE_MONSTER, TYPE_EFFECT = 1, 0x20
TYPE_NORMAL, TYPE_PENDULUM, TYPE_TOKEN = 0x10, 0x1000000, 0x4000
MATERIAL_TYPES = 0x40 | 0x80 | 0x2000 | 0x800000 | 0x4000000
FW = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)}


# ---------- 載入
def load():
    def p(*x):
        return os.path.join(ROOT, *x)

    def cdb(name):
        uri = "file:" + os.path.abspath(p("data", "sources", name)).replace("\\", "/") + "?mode=ro"
        return {r[0]: r[1] for r in sqlite3.connect(uri, uri=True).execute("select id, desc from texts")}

    faq = json.load(open(p("data", "sources", "faq_info.json"), encoding="utf8"))
    cards = json.load(open(p("data", "cards.json"), encoding="utf8"))
    splits = json.load(open(p("data", "clause_splits.json"), encoding="utf8"))
    return faq, {c["id"]: c for c in cards}, splits, cdb("ja-JP.cdb"), cdb("en-US.cdb")


# ---------- 文字工具
def norm(s):
    return re.sub(r"\s", "", s.translate(FW))


def has_num(s):
    return any(ch in NUM for ch in (s or ""))


def is_header(s, i):
    """效果編號當標頭:在行首,或後面接冒號。"""
    return s[i] in NUM and (i == 0 or s[i - 1] in "\n\r" or s[i + 1:i + 2] in ("：", ":"))


def num_count(s):
    if not s:
        return 0
    return len({s[i] for i in range(len(s)) if is_header(s, i)})


def num_blocks(s):
    """依編號標頭切成 [(編號或 None, 區塊文字)]。"""
    if not s:
        return []
    cuts = [i for i in range(len(s)) if is_header(s, i)]
    if not cuts:
        return [(None, s)]
    out = [(None, s[:cuts[0]])] if cuts[0] > 0 else []
    for a, b in zip(cuts, cuts[1:] + [len(s)]):
        out.append((s[a], s[a:b]))
    return out


def ja_cdb_main(desc):
    """ja cdb desc → (怪獸效果/本文, P 效果或 None)。"""
    if desc is None:
        return None, None
    if "【モンスター効果】" in desc or "【Ｐスケール" in desc or "【Pスケール" in desc:
        if "【モンスター効果】" in desc:
            p, m = desc.split("【モンスター効果】", 1)
        elif "【フレーバーテキスト】" in desc:
            p, m = desc.split("【フレーバーテキスト】", 1)
            m = ""
        else:
            p, m = desc, ""
        p = re.sub(r"^.*?【[ＰP]スケール[^】]*】", "", p, flags=re.S)
        return m, p
    return desc, None


def zh_main(desc):
    if "【靈擺效果】" not in desc:
        return desc, None
    st = desc.index("【靈擺效果】") + len("【靈擺效果】")
    m = re.search(r"【怪獸(效果|敘述|描述)】", desc[st:])
    if not m:
        return "", desc[st:]
    p = desc[st:st + m.start()]
    if m.group(1) != "效果":
        return "", p
    return desc[st + m.end():], p


def en_main(desc):
    if desc is None:
        return None, None
    if "[ Pendulum Effect ]" in desc:
        p = desc.split("[ Pendulum Effect ]", 1)[1]
        parts = re.split(r"-{5,}", p, 1)
        m = parts[1] if len(parts) > 1 else ""
        m = m.split("[ Monster Effect ]", 1)[1] if "[ Monster Effect ]" in m else ""
        return m, parts[0]
    return desc, None


def ja_sentences(text):
    """在「」『』（）外的 。 切句;● 前也切;括號外換行也切。"""
    out, buf, depth = [], "", 0
    for ch in text:
        if ch in "「『（(":
            depth += 1
        elif ch in "」』）)":
            depth = max(0, depth - 1)
        if ch == "●" and buf.strip():
            out.append(buf)
            buf = ""
        buf += ch
        if ch == "。" and depth == 0:
            out.append(buf)
            buf = ""
        elif ch in "\n\r" and depth == 0 and buf.strip():
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return [s.strip() for s in out if s.strip()]


SUMMON_JA = re.compile(r"通常召喚できない|特殊召喚できない|特殊召喚する事ができない|特殊召喚する事はできない"
                       r"|場合のみ特殊召喚|でのみ特殊召喚|によってのみ特殊召喚|方法でのみ|でしか特殊召喚"
                       r"|儀式召喚でのみ|融合召喚でのみ|でのみ.{0,20}召喚|しか特殊召喚できない|召喚・反転召喚・特殊召喚できない"
                       r"|降臨させる事ができる|降臨させる|特殊召喚する事ができる。?$|特殊召喚できる。?$|リリースして.{0,20}召喚")


# ---------- 英文分組(en-US.cdb)
def en_sentences(text):
    out, buf, q, par = [], "", False, 0
    i = 0
    while i < len(text):
        ch = text[i]
        buf += ch
        if ch == '"':
            q = not q
        elif ch == "(":
            par += 1
        elif ch == ")":
            par = max(0, par - 1)
            if par == 0 and not q and buf.rstrip(")").endswith("."):
                out.append(buf)
                buf = ""
                i += 1
                continue
        if not q and par == 0 and ch == "." and (i + 1 == len(text) or text[i + 1] in " \r\n"):
            out.append(buf)
            buf = ""
        elif ch == "\n" and not q and par == 0:
            if buf.strip():
                out.append(buf)
            buf = ""
        i += 1
    if buf.strip():
        out.append(buf)
    return [s.strip() for s in out if s.strip()]


PREAMBLE = re.compile(
    r"^(Cannot be (Normal|Special) Summoned|Must (first )?be (Special|Ritual|Fusion|Synchro|Xyz|Link|Normal) Summoned"
    r"|Must be Special Summoned|This card cannot be (Normal |Special )?Summoned"
    r"|This card can only be (Special )?Summoned|Can only be Special Summoned|Cannot be Special Summoned"
    r"|You can Ritual Summon this card|This card is used to Ritual Summon|You can only (use|activate|Special Summon|control|Normal Summon|Set)"
    r"|You can only use each|You can use the effect of .* per turn|Equip only to|This card('s name)? is (also )?always treated|\(This card is (also )?always treated"
    r"|There can only be 1|Only 1 .* can be|You can Normal Summon this card without Tributing|This card requires \d|Requires \d"
    r"|This card cannot be used as|You cannot Special Summon .* the turn|.*Must be Special Summoned)")
CONT_START = re.compile(
    r"^(Then|Also|Otherwise|If you do|In addition|Afterwards|After that|That |Those |Its |It |They |Their |These |Them |Each of them"
    r"|Both |\(|For the rest of this turn|During the End Phase of this turn|At the end of|Shuffle the rest|Place the rest|Send the rest"
    r"|If not|If it|If they|If that|If the (Special Summoned|targeted|selected|returned|declared|discarded|sent|revealed|destroyed|banished|chosen|card|cards|monster|monsters) "
    r"|You cannot .* the turn you activate|You cannot .* the turn you|While (it|that|this card is) equipped|●|•)")
VERB_PRON = re.compile(r"^\w+ (it|them|that|those|the targets?|the target|the rest)\b")
CONT_IN = re.compile(r"by this effect|this way|by this card's effect|in response to this|the turn you activate this|affected by this effect|with this effect|this effect's activation|You cannot activate this card")
OPENER = re.compile(r"^(Activate only|You can only activate this card|Activate this card only|Discard \d+ cards?\.$|Pay \d+ (Life Points|LP)\.$)")


def en_groups(text, ctype):
    """英文效果分組(每組一串句子),前言丟掉。"""
    text = text.replace("\r", "")
    lines = text.split("\n")
    if ctype & TYPE_MONSTER and ctype & MATERIAL_TYPES and lines and not lines[0].strip().endswith("."):
        text = "\n".join(lines[1:])
    groups, pending = [], []
    for s in en_sentences(text):
        if PREAMBLE.search(s):
            continue
        if OPENER.search(s):
            pending.append(s)
            continue
        if not pending and groups and (CONT_START.search(s) or VERB_PRON.search(s) or CONT_IN.search(s)):
            groups[-1].append(s)
        else:
            groups.append(pending + [s])
            pending = []
    if pending:
        groups.append(pending)
    return groups


# ---------- cdb 無編號前言裡的「このカードを発動できる」行
ACT = re.compile(r"このカードを発動(できる|する)。$|このカードの発動")
SELF = re.compile(r"(このカードを破壊する|このカードは破壊される|破壊される|墓地へ送られる|このカードを墓地へ送る)）?。$")


def cdb_info(desc):
    """→ (①編號數, 前言有無發動行, 前言自壞/維持行數)"""
    bl = num_blocks(ja_cdb_main(desc)[0])
    numbered = len({h for h, _ in bl if h})
    act = selfl = 0
    if bl and bl[0][0] is None:
        for line in re.split(r"\r?\n", bl[0][1]):
            line = line.strip()
            if not line:
                continue
            if ACT.search(line):
                act = 1
            elif SELF.search(line) and "のみ" not in line:
                selfl += 1
    return numbered, act, selfl


# ---------- 對位工具
def bigrams(s):
    s = re.sub(r"[、。・「」『』（）\(\)]", "", norm(s))
    return collections.Counter(s[i:i + 2] for i in range(len(s) - 1))


def sim(a, b):
    return sum((a & b).values()) / max(1, sum(a.values()))


def cdb_units(desc):
    """cdb 本文切成 [(標籤, 文字)];標籤是編號、ACT(發動行)或 PRE(其他前言行)。"""
    out = []
    for h, t in num_blocks(ja_cdb_main(desc)[0]):
        if h:
            out.append((h, t[2:] if t[1:2] in "：:" else t[1:]))
        else:
            for line in re.split(r"\r?\n", t):
                if line.strip():
                    out.append(("ACT" if ACT.search(line.strip()) else "PRE", line))
    return out


def sent_offsets(text):
    sents = ja_sentences(text)
    offs, pos = [], 0
    for s in sents:
        pos += len(norm(s))
        offs.append(pos)
    return sents, offs


def quote_spans(supplement, body):
    """官方補足『』引用(正規化、去句點、長度 ≥ 8)在本文裡的 (起, 迄)。"""
    qs = []
    for q in re.findall(r"『([^『』]+)』", supplement or ""):
        nq = norm(q).rstrip("。")
        if len(nq) >= 8:
            i = body.find(nq)
            if i >= 0:
                qs.append((i, i + len(nq)))
    return qs


def cuts(bounds, qs):
    return sum(1 for a, b in qs for x in bounds if a < x < b)


# ================= 1. 母體(原 pop.py + analyze.py)
faq, cm, splits, jcdb, ecdb = load()
alt = {a: c["id"] for c in cm.values() for a in (c.get("alt_ids") or [])}
pop_stats = collections.Counter()
pop0, seen = [], set()
for x in faq:
    p = x["password"]
    if p is None:
        pop_stats["no_pw"] += 1
        continue
    cid = p if p in cm else alt.get(p)
    if cid is None:
        pop_stats["no_card"] += 1
        continue
    if cid in seen:
        pop_stats["dup"] += 1
        continue
    seen.add(cid)
    ct, pe = x.get("card_text") or "", x.get("pen_effect") or ""
    ctype = cm[cid]["type"]
    if not ct and not pe:
        pop_stats["no_text"] += 1
    elif ctype & TYPE_TOKEN:
        pop_stats["token"] += 1
    elif ctype & TYPE_MONSTER and ctype & TYPE_NORMAL and not ctype & TYPE_PENDULUM:
        pop_stats["pure_normal"] += 1
    elif has_num(ct) or has_num(pe):
        pop_stats["numbered"] += 1
    else:
        pop_stats["old"] += 1
        pop0.append(cid)


def no_effect_monster(c):
    t = cm[c]["type"]
    return t & TYPE_MONSTER and not t & TYPE_EFFECT and not t & TYPE_PENDULUM


pop = [c for c in pop0 if not no_effect_monster(c)]
pend = [c for c in pop if cm[c]["type"] & TYPE_PENDULUM]
main = [c for c in pop if not cm[c]["type"] & TYPE_PENDULUM]

# 官方文本:依 password 取(多筆時後者為準),沒有再走 alt_ids
fm = {x["password"]: x for x in faq}
faqtext = {c: fm.get(c) or next(y for y in faq if alt.get(y["password"]) == c) for c in pop}

sp = {(r["id"], r["section"]): r for r in splits}
res = {}
for c in main:
    ctype = cm[c]["type"]
    x = faqtext[c]
    ct = x.get("card_text") or ""
    r = {}
    jm = ja_cdb_main(jcdb[c])[0] if jcdb.get(c) else None
    r["cdb"] = num_count(jm) if jm else 0
    if r["cdb"]:
        # 對齊口徑:永續/裝備魔陷前言的「〜を対象としてこのカードを発動できる。」補算一個效果
        n, act, selfl = cdb_info(jcdb[c])
        r["cdb1"] = n + act
        r["cdb_self"] = selfl
    em = en_main(ecdb[c])[0] if ecdb.get(c) else None
    r["en"] = len(en_groups(em, ctype)) if em else 0
    body = norm(ct)
    r["q"] = [q for q in (norm(q).rstrip("。") for q in re.findall(r"『([^『』]+)』", x.get("supplement") or ""))
              if len(q) >= 8 and q in body]
    rec = sp.get((c, "main"))
    r["cs"] = None
    if rec:
        r["cs"] = len([g for g in rec["segments"] if not (g["index"] == "0" or g["index"].startswith("0-"))])
        r["cs_segs"] = rec["segments"]
        r["cs_order"] = rec.get("ja_order") or list(range(len(rec["segments"])))
    res[c] = r

# ================= 2. 句子對位(原 align.py):官方文本每句配到 cdb 最相似的單元
out = {}
for c in main:
    r = res[c]
    if not (r.get("cdb1") and r["cs"]):
        continue
    ct = faqtext[c]["card_text"]
    sents, offs = sent_offsets(ct)
    ub = [(lab, bigrams(t)) for lab, t in cdb_units(jcdb[c])]
    labels = []
    for s in sents:
        sb = bigrams(s)
        best = max(ub, key=lambda u: sim(sb, u[1]))
        labels.append(best[0] if sim(sb, best[1]) > 0.2 else None)
    for i in range(len(labels)):
        if labels[i] is None:
            labels[i] = labels[i - 1] if i else "PRE"
    cdb_b = {offs[i] for i in range(len(sents) - 1) if labels[i] != labels[i + 1]}
    # cs 效果邊界:相鄰兩段標籤不同才算(前言段 index 0 開頭都標 PRE)
    segs, order = r["cs_segs"], r["cs_order"]
    labs = ["PRE" if segs[k]["index"].startswith("0") else segs[k]["index"] for k in order]
    pos, cs_eb = 0, set()
    for i, k in enumerate(order[:-1]):
        pos += len(norm(segs[k]["text_ja"]))
        if labs[i] != labs[i + 1]:
            cs_eb.add(pos)
    out[c] = dict(sents=sents, offs=offs, labels=labels, cdb_b=cdb_b, cs_eb=cs_eb,
                  qs=quote_spans(faqtext[c].get("supplement"), norm(ct)))

# ================= 3. 補足引用完整切分(原 final.py 的 supp_full)
PRE_RX = re.compile(SUMMON_JA.pattern + "|" + r"しか使用できない|しか発動できない|のみ装備可能|装備可能|降臨|に必要")
supp_full = {}
for c in main:
    ct = faqtext[c]["card_text"]
    qs = quote_spans(faqtext[c].get("supplement"), norm(ct))
    if not qs:
        continue
    sents, offs = sent_offsets(ct)
    starts = [0] + offs[:-1]
    aligned = set()
    for a, b in qs:
        if a in starts and (b in offs or b + 1 in offs):
            aligned.add((a, b + 1 if b + 1 in offs else b))
    aligned = sorted(aligned)
    maximal = [q for q in aligned if not any(o != q and o[0] <= q[0] and q[1] <= o[1] for o in aligned)]
    if not maximal or any(maximal[i][1] > maximal[i + 1][0] for i in range(len(maximal) - 1)):
        continue
    if all(any(a <= st and en <= b for a, b in maximal) or PRE_RX.search(norm(s))
           for st, en, s in zip(starts, offs, sents)):
        supp_full[c] = len(maximal)

# ================= 4. 共識統計(原 final.py)
T = collections.Counter()
ex = collections.defaultdict(list)
for c in main:
    r, o = res[c], out.get(c)
    cs, cd, en = r["cs"], r.get("cdb1"), r["en"]
    if cs and cd:
        if cs == cd and o and o["cs_eb"] == o["cdb_b"]:
            k = "A_en" if en == cs else "A"
        elif cs == cd:
            k = "B"
        elif en == cs or en == cd or (c in supp_full and supp_full[c] in (cs, cd)):
            k = "C"
        else:
            k = "D"
    elif cs and not cd:
        k = "E_en" if en == cs else "E"
    elif cd and not cs:
        k = "F"
    else:
        k = "G"
    T[k] += 1
    ex[k].append(c)

pairs = [(r["cdb1"], r["cs"]) for r in res.values() if r.get("cdb1") and r["cs"]]
agree = sum(a == b for a, b in pairs)
no_cs = [c for c in main if res[c]["cs"] is None]


def multi_stats(groups_by_card):
    blocks = sum(len(g) for g in groups_by_card.values())
    multi = sum(1 for g in groups_by_card.values() for x in g if len(x) >= 2)
    return len(groups_by_card), blocks, multi


gb = {}
for c, o in out.items():
    groups, prev = [], None
    for lab, s in zip(o["labels"], o["sents"]):
        if lab != "PRE":
            if lab == prev and groups:
                groups[-1].append(s)
            else:
                groups.append([s])
        prev = lab
    gb[c] = groups
gc = {}
for c in main:
    r = res[c]
    if r["cs"] is None:
        continue
    gc[c] = [ss for g in r["cs_segs"] if not g["index"].startswith("0") for ss in [ja_sentences(g["text_ja"])] if ss]

print(f"舊式卡:官方文本無①編號、排除衍生物/通常怪獸/無效果怪獸 {len(pop)} 張(靈擺 {len(pend)} 張只有 P 效果、不比),"
      f"母體(本文){len(main)} 張")
print(f"拆句表(cs)與 cdb①效果數一致率(cdb 前言發動行補算一個效果):{agree}/{len(pairs)} = {agree / len(pairs):.1%}")
print(f"cs、cdb 效果數與邊界都一致:{T['A'] + T['A_en']} 張,其中英文也一致 {T['A_en']}  例 {ex['A_en'][:4]}")
print(f"cs≠cdb 但英文或補足引用站一邊(2 對 1 有共識):{T['C']} 張  例 {ex['C'][:4]}")
nocons = T["B"] + T["D"] + T["E"]
print(f"仍無共識:{nocons} 張 = cs≠cdb 且無第三方 {T['D']} + 數同邊界不同 {T['B']} + 無 cdb① 僅 cs 且英文不同 {T['E']}"
      f"  例 D {ex['D'][:3]} B {ex['B'][:3]} E {ex['E'][:3]}")
print(f"  其餘:無 cdb① 僅 cs 且英文同 {T['E_en']}、cs 無效果段而 cdb 有① {T['F']}、兩者皆無 {T['G']};"
      f"cs 無紀錄 {len(no_cs)} 張 {no_cs}")
n, b, m = multi_stats(gc)
print(f"舊卡效果有 2 句以上(依 cs 分段):{m}/{b} 個效果區塊 = {m / b:.1%}({n} 張)")
n, b, m = multi_stats(gb)
print(f"舊卡效果有 2 句以上(依 cdb 對位):{m}/{b} 個效果區塊 = {m / b:.1%}({n} 張)")

if OUT_JSON:
    data = {
        "description": "舊式卡效果邊界共識集(boundary.py 產出)。full_agree:拆句表與 ja-JP.cdb①效果數與邊界都一致;"
                       "full_agree_en:其中英文分組數也一致;two_to_one:兩者效果數不同,英文或官方補足引用支持其中一方;"
                       "no_consensus:仍無共識(cs≠cdb 且無第三方、數同邊界不同、無 cdb① 僅 cs 且英文不同),交站主判。",
        "full_agree": sorted(ex["A"] + ex["A_en"]),
        "full_agree_en": sorted(ex["A_en"]),
        "two_to_one": sorted(
            ({"id": c, "cs": res[c]["cs"], "cdb": res[c]["cdb1"], "en": res[c]["en"], "supp": supp_full.get(c)}
             for c in ex["C"]), key=lambda d: d["id"]),
        "no_consensus": sorted(ex["B"] + ex["D"] + ex["E"]),
    }
    with open(OUT_JSON, "w", encoding="utf8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"共識集寫到 {OUT_JSON}:full_agree {len(data['full_agree'])}、two_to_one {len(data['two_to_one'])}、"
          f"no_consensus {len(data['no_consensus'])}")
