"""針對卡片 字段「卡名包含」實測(原型,不入產品)。

讀 .scratch/effect-tokenize/frames.json 動作框架 phrases 的 object(受事者)與 goal(目的)片語,
收 kind=字段 的修飾語字面「X」;對 data/cards.json 的 name_ja 做 NFKC 子字串比對(同 patient._segment_blocker)。

對照組:cards.json 的 setcode(EDOPro cdb 的字段碼,4×16 bit 打包;子字段規則同 Card.IsSetCard:
(sc & 0xfff) == (code & 0xfff) and (sc & code) == code)。每個字串推一個字段碼:
- 卡名對得到的:候選碼 = 命中卡的各 sc 與 sc & 0xfff,取「命中卡中屬於該碼的張數」最多者,同分取全庫成員少的(較專一)。
- 卡名對不到的:改從「寫出這個字串的框所在的卡」的字段碼投票(過半才算)。
推得的碼覆蓋卡名命中卡 < 50% 時視為非官方字段(無對照)。

誤中候選兩法:
- A 字段碼:卡名包含但不屬推得的字段碼。
- B 片假名邊界:字串頭/尾是片假名或長音,而卡名裡緊鄰的字也是片假名/長音(詞的一部分)。
漏中:屬字段碼但卡名不含。

另掃 ja-JP.cdb 卡文「このカード名はルール上「X」カード(、「Y」カード)としても扱う」當對照表來源。

用法:python -X utf8 archetype_name_match.py  → results/archetype_name_match.txt
"""
from collections import Counter, defaultdict
import json
import os
import re
import sqlite3
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FRAMES = os.path.join(ROOT, ".scratch", "effect-tokenize", "frames.json")
CARDS = os.path.join(ROOT, "data", "cards.json")
JA_CDB = os.path.join(ROOT, "data", "sources", "ja-JP.cdb")
OUT = os.path.join(HERE, "results", "archetype_name_match.txt")

ROLES = ("object", "goal")
MOD_ARCHETYPE = "字段"
TREATED_AS = re.compile(r"ルール上((?:「[^」]+」(?:カード)?[、・]?)+)カードとしても扱う")
QUOTED = re.compile(r"「([^」]+)」")


def nfkc(text):
    return unicodedata.normalize("NFKC", text or "")


def is_kana(ch):
    return ch == "ー" or "゠" <= ch <= "ヿ" or "ｦ" <= ch <= "ﾟ"


def setcodes(card):
    value = card.get("setcode") or 0
    return [(value >> (16 * i)) & 0xffff for i in range(4) if (value >> (16 * i)) & 0xffff]


def in_set(card, code):
    return any((sc & 0xfff) == (code & 0xfff) and (sc & code) == code for sc in setcodes(card))


def kana_glued(q, name):
    """q 在 name 裡每個出現處都是更長片假名詞的一部分 → True。"""
    starts = [m.start() for m in re.finditer(re.escape(q), name)]
    if not starts:
        return False
    for s in starts:
        e = s + len(q)
        left = s > 0 and is_kana(q[0]) and is_kana(name[s - 1])
        right = e < len(name) and is_kana(q[-1]) and is_kana(name[e])
        if not (left or right):
            return False
    return True


def collect(frames_path):
    frames_by = defaultdict(int)
    cards_by = defaultdict(set)
    heads = defaultdict(int)
    with open(frames_path, encoding="utf-8") as f:
        sentences = json.load(f)
    for s in sentences:
        for fr in s["frames"]:
            seen, seen_head = set(), set()
            for role in ROLES:
                phrase = (fr.get("phrases") or {}).get(role)
                if not phrase:
                    continue
                for seg in phrase["segments"]:
                    for mod in seg["modifiers"]:
                        if mod["kind"] == MOD_ARCHETYPE:
                            for q in QUOTED.findall(mod["text"]) or [mod["text"]]:
                                seen.add(nfkc(q))
                    head = seg.get("head") or ""
                    if head.startswith("「") and head.endswith("」"):
                        seen_head.add(nfkc(head[1:-1]))
            for q in seen:
                frames_by[q] += 1
                cards_by[q].add(s["card"])
            for q in seen_head:
                heads[q] += 1
    return frames_by, cards_by, heads


def infer_code(hit_cards, cards, frame_cards, by_id, members_of):
    """回 (碼, 來源, 覆蓋率)。候選碼 = 卡名命中卡與寫出此字串的框所在卡的各 sc、sc & 0xfff;
    分數 = F1(卡名命中, 碼成員) + F1(框卡, 碼成員),同分取成員少的。覆蓋率 = max(命中卡屬碼比, 框卡屬碼比)。"""
    owners = [by_id[i] for i in frame_cards if i in by_id]
    cand = set()
    for c in list(hit_cards) + owners:
        for sc in setcodes(c):
            cand |= {sc, sc & 0xfff}
    if not cand:
        return None, "-", 0.0

    def f1(group, mem):
        inter = sum(1 for c in group if c["id"] in mem)
        return 2 * inter / (len(group) + len(mem)) if group else 0.0, inter / len(group) if group else 0.0

    scored = []
    for code in cand:
        mem = members_of(code)
        fh, ch = f1(hit_cards, mem)
        fo, co = f1(owners, mem)
        scored.append((fh + fo, -len(mem), code, max(ch, co)))
    _, _, code, cover = max(scored)
    return code, "卡名+框卡" if hit_cards else "框卡", cover


def treated_as(by_id):
    db = sqlite3.connect("file:%s?mode=ro" % JA_CDB.replace("\\", "/"), uri=True)
    pairs = []
    for cid, name, desc in db.execute("select id, name, desc from texts"):
        for m in TREATED_AS.finditer(desc or ""):
            for q in QUOTED.findall(m.group(1)):
                pairs.append((cid, name, nfkc(q)))
    db.close()
    return pairs


def main():
    with open(CARDS, encoding="utf-8") as f:
        cards = json.load(f)
    by_id = {c["id"]: c for c in cards}
    names = {c["id"]: nfkc(c["name_ja"]) for c in cards}
    frames_by, cards_by, heads = collect(FRAMES)
    cache = {}

    def members_of(code):
        if code not in cache:
            cache[code] = {c["id"] for c in cards if in_set(c, code)}
        return cache[code]
    out = []
    p = out.append
    p("# 字段「卡名包含」實測(受事者 object + 目的 goal 片語,kind=字段 修飾語)")
    p("卡片總表 %d 張;字段字串 %d 種、%d 框(一框多個同字串算一次)、%d 張卡寫到"
      % (len(cards), len(frames_by), sum(frames_by.values()), len(set().union(*cards_by.values()))))
    rows = []
    for q in sorted(frames_by, key=lambda k: -frames_by[k]):
        hits = [c for c in cards if q in names[c["id"]]]
        code, src, cover = infer_code(hits, cards, cards_by[q], by_id, members_of)
        official = code is not None and cover >= 0.5
        members = [by_id[i] for i in sorted(members_of(code))] if official else []
        mids = {c["id"] for c in members}
        hids = {c["id"] for c in hits}
        false_a = [c for c in hits if official and c["id"] not in mids]
        false_b = [c for c in hits if kana_glued(q, names[c["id"]])]
        miss = [c for c in members if c["id"] not in hids]
        rows.append(dict(q=q, frames=frames_by[q], hits=hits, code=code, src=src, cover=cover, official=official,
                         members=members, false_a=false_a, false_b=false_b, miss=miss))

    best = {}
    for r in rows:
        if r["official"]:
            inter = len({c["id"] for c in r["hits"]} & {c["id"] for c in r["members"]})
            r["f1"] = 2 * inter / max(len(r["hits"]) + len(r["members"]), 1)
            if r["code"] not in best or r["f1"] > best[r["code"]]["f1"]:
                best[r["code"]] = r
    for r in rows:
        r["owner"] = r["official"] and best[r["code"]] is r
    zero = [r for r in rows if not r["hits"]]
    p("")
    p("## 1. 卡名命中張數分布")
    dist = Counter("0" if not r["hits"] else "1" if len(r["hits"]) == 1 else "2-9" if len(r["hits"]) < 10
                   else "10+" for r in rows)
    p("  " + "、".join("%s 張:%d 種" % (k, dist[k]) for k in ("0", "1", "2-9", "10+")))
    p("  有官方字段碼(覆蓋 ≥50%%):%d 種;無:%d 種" % (sum(r["official"] for r in rows),
                                                 sum(not r["official"] for r in rows)))

    p("")
    p("## 2. 卡名對到 0 張(%d 種、%d 框)" % (len(zero), sum(r["frames"] for r in zero)))
    p("  字串\t框數\t框卡推得字段碼(過半)\t碼成員數\t成員例")
    for r in zero:
        ex = "、".join(c["name_ja"] for c in r["members"][:3])
        p("  「%s」\t%d\t%s\t%d\t%s" % (r["q"], r["frames"], ("0x%x(%.0f%%)" % (r["code"], 100 * r["cover"]))
                                       if r["official"] else "-", len(r["members"]), ex))

    p("")
    p("## 3. 誤中候選")
    off = [r for r in rows if r["official"]]
    tot_hits = sum(len(r["hits"]) for r in off)
    tot_a = sum(len(r["false_a"]) for r in off)
    tot_b = sum(len(r["false_b"]) for r in rows)
    tot_b_all = sum(len(r["hits"]) for r in rows)
    both = sum(len({c["id"] for c in r["false_a"]} & {c["id"] for c in r["false_b"]}) for r in off)
    p("  A 字段碼法(只算有官方碼的 %d 種):卡名命中 %d 卡次,不屬字段碼 %d(%.1f%%)"
      % (len(off), tot_hits, tot_a, 100 * tot_a / max(tot_hits, 1)))
    p("  B 片假名邊界法(全 %d 種):卡名命中 %d 卡次,黏在更長片假名詞裡 %d(%.1f%%);A∩B %d"
      % (len(rows), tot_b_all, tot_b, 100 * tot_b / max(tot_b_all, 1), both))
    fa_frames = sum(r["frames"] for r in off if r["false_a"])
    p("  有 A 誤中的字串 %d 種(占框 %d)" % (sum(1 for r in off if r["false_a"]), fa_frames))
    p("")
    p("  A 誤中最多的前 25 種:字串\t框數\t卡名命中\tA 誤中\tB 誤中\t例卡(A)")
    for r in sorted(off, key=lambda r: -len(r["false_a"]))[:25]:
        if not r["false_a"]:
            break
        p("  「%s」\t%d\t%d\t%d\t%d\t%s" % (r["q"], r["frames"], len(r["hits"]), len(r["false_a"]), len(r["false_b"]),
                                         "、".join(c["name_ja"] for c in r["false_a"][:4])))
    p("")
    p("  B 誤中最多的前 15 種:字串\t卡名命中\tB 誤中\t例卡")
    for r in sorted(rows, key=lambda r: -len(r["false_b"]))[:15]:
        if not r["false_b"]:
            break
        p("  「%s」\t%d\t%d\t%s" % (r["q"], len(r["hits"]), len(r["false_b"]),
                                 "、".join(c["name_ja"] for c in r["false_b"][:4])))
    p("")
    owners = [r for r in off if r["hits"] and r["owner"]]
    tot_miss = sum(len(r["miss"]) for r in owners)
    p("## 3b. 漏中(屬字段碼、卡名不含;只算卡名有命中、且是該碼 F1 最高字串的 %d 種):%d 卡次、%d 種有漏"
      % (len(owners), tot_miss, sum(1 for r in owners if r["miss"])))
    p("  (同碼的其他 %d 種字串借用上位碼,不算漏中,例:%s)" % (sum(1 for r in off if not r["owner"]),
      "、".join("「%s」→「%s」" % (r["q"], best[r["code"]]["q"]) for r in off if not r["owner"])[:300]))
    for r in sorted(owners, key=lambda r: -len(r["miss"]))[:20]:
        if not r["miss"]:
            break
        p("  「%s」\t成員 %d\t漏 %d\t%s" % (r["q"], len(r["members"]), len(r["miss"]),
                                        "、".join(c["name_ja"] for c in r["miss"][:4])))

    pairs = treated_as(by_id)
    p("")
    p("## 3c. 卡文「このカード名はルール上「X」カードとしても扱う」")
    pc = {(cid, q) for cid, _, q in pairs}
    p("  %d 張卡、%d 組(卡, 字段);不同字段 %d 種" % (len({c for c, _ in pc}), len(pc), len({q for _, q in pc})))
    qs = set(frames_by)
    in_corpus = [(c, q) for c, q in pc if q in qs]
    covered = [(c, q) for c, q in in_corpus if c in names and q in names[c]]
    zero_q = {r["q"] for r in zero}
    p("  其中字段字串出現在受事者/目的片語的 %d 組;卡名已含該字串 %d 組;補到「卡名 0 張」字串 %d 組"
      % (len(in_corpus), len(covered), sum(1 for _, q in in_corpus if q in zero_q)))
    in_code = sum(1 for c, q in in_corpus for r in rows if r["q"] == q and r["official"] and c in by_id
                  and in_set(by_id[c], r["code"]))
    p("  這些組裡卡片 setcode 也含該字段碼:%d / %d" % (in_code, len(in_corpus)))
    extra = sorted({q for _, q in in_corpus if q not in {q2 for c, q2 in covered}})
    p("  需靠這句補的字段(卡名不含):" + "、".join("「%s」" % q for q in extra))
    miss_pairs = {(c["id"], r["q"]) for r in owners for c in r["miss"]}
    p("  漏中卡次(3b)裡有這句的:%d / %d" % (len(miss_pairs & pc), len(miss_pairs)))
    p("  卡名對到 0 張的字段中,靠這句能補到的:" + "、".join(sorted("「%s」" % q for _, q in in_corpus if q in zero_q)))

    p("")
    p("## 附:中心詞「…」(卡名)")
    hz = [q for q in heads if not any(q in names[i] for i in names)]
    multi = [q for q in heads if sum(1 for i in names if q in names[i]) > 1]
    p("  %d 種、%d 框;卡名包含對到 0 張 %d 種;對到 >1 張(子字串比全名寬)%d 種"
      % (len(heads), sum(heads.values()), len(hz), len(multi)))
    p("  0 張:" + "、".join("「%s」" % q for q in hz[:60]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    sys.exit(main())
