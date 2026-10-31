# -*- coding: utf-8 -*-
"""票 01「索引體積與評估器速度實測」的投影工具:frames.json 的動作框架 → 每句的框架欄位,
算三種編碼的 raw / gzip 增量,並寫出給 Node 評估器(evaluate.js)讀的投影檔。

只讀 .scratch/effect-tokenize/(frames.json、patient.py、places.py、categories.py)與
data/cards.json、web/data.js,不改任何網站資料。輸出到 --out(預設 session scratchpad)。

用法:python .scratch/frame-predicate-search/tools/project.py --out <dir>
"""
import argparse
import gzip
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOKENIZE = os.path.join(ROOT, ".scratch", "effect-tokenize")
sys.path.insert(0, TOKENIZE)
import patient  # noqa: E402
import places  # noqa: E402
from categories import head_nouns  # noqa: E402

FRAMES = os.path.join(TOKENIZE, "frames.json")
CARDS = os.path.join(ROOT, "data", "cards.json")
DATA_JS = os.path.join(ROOT, "web", "data.js")
FACE_FIELDS = ("type", "race", "attribute", "level", "atk", "def", "name_ja")

POSITIONS = ("效果", "代價", "條件")
POLARITIES = ("肯定", "否定", "可能")
VOICES = (None, "受身", "他動", "自動")
PLAYERS = ("無", "自分", "相手", "雙方", "相對")
ZONES = ("手牌", "牌組", "額外牌組", "墓地", "除外", "場上", "靈擺區")
MODES = (None, patient.SELF, patient.NONSELF)
OLD_FIELDS = ("ae", "ac", "aes", "aen", "acs", "acn")
# 外推用的五個小整數欄(片語中心詞類、施事者、方式類、數量類、修飾語類)的值域大小
EXTRA_CARDINALITY = (5, 4, 7, 5, 9)


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def sizes(obj):
    raw = dumps(obj).encode("utf-8")
    return len(raw), len(gzip.compress(raw, 9))


def zone_pairs(literal):
    """地點字面 → [(玩家碼, 區域碼)];認不出或沒字面 → []。"""
    zones = places.parse_zones(literal)
    if not zones:
        return []
    return [(PLAYERS.index(p), ZONES.index(z)) for p, z in zones]


def pair_code(player, zone):
    return player * 8 + zone


def goal_heads(literal):
    """目的補語的中心詞:字面不是地點、不是純玩家時才有。"""
    if not literal or places.parse_zones(literal) or literal in places.BARE_PLAYERS:
        return []
    return [h for h in head_nouns(literal) if h]


def patient_heads(frame):
    for key in ("object", "subject", "topic"):
        if frame.get(key):
            return [h for h in head_nouns(frame[key]) if h]
    return []


def extras(key):
    """外推的五個小整數:由框架鍵決定性地算出(只為估體積,沒有語意)。回兩組——均勻(每個值
    等機率,gzip 幾乎壓不動,是上界)與偏態(七成是 0、其餘集中在小值,接近真實欄位多數為
    空的樣子)。"""
    digest = hashlib.sha1(key.encode("utf-8")).digest()
    uniform = [digest[i] % n for i, n in enumerate(EXTRA_CARDINALITY)]
    skewed = [0 if digest[8 + i] < 179 else 1 + digest[8 + i] % (n - 1)
              for i, n in enumerate(EXTRA_CARDINALITY)]
    return uniform, skewed


def project(sentences, faces):
    """→ {card: [句 → [框架欄位 dict]]}(句依 frames.json 的列序)。"""
    by_card = defaultdict(list)
    stats = Counter()
    for s in sentences:
        verdicts = patient.judge_sentence(s["frames"], faces.get(s["card"]), s["section"])
        row = []
        for fr, verdict in zip(s["frames"], verdicts):
            if fr.get("kind") != "動作":
                continue
            key = "%s/%s/%s/%s" % (s["card"], s["section"], s["index"], fr["order"])
            rec = {
                "lemma": fr["action"],
                "position": POSITIONS.index(fr["position"]),
                "polarity": POLARITIES.index(fr["polarity"]),
                "voice": VOICES.index(fr.get("voice")),
                "source": zone_pairs(fr.get("source")),
                "goal": zone_pairs(fr.get("goal")),
                "place": zone_pairs(fr.get("place")),
                "mode": MODES.index(verdict.mode),
                "heads": patient_heads(fr),
                "goal_heads": goal_heads(fr.get("goal")),
                "extras": extras(key),
            }
            stats["frames"] += 1
            stats["heads_total"] += len(rec["heads"])
            stats["goal_heads_total"] += len(rec["goal_heads"])
            row.append(rec)
        by_card[s["card"]].append(row)
        stats["sentences"] += 1
    return by_card, stats


# ---- 三種編碼 -------------------------------------------------------------------

def encode_objects(rec, lemma_code, with_extras):
    """A 欄名物件:短欄名、值可讀(列舉值寫字面),null/空欄省略。"""
    out = {"l": rec["lemma"], "p": POSITIONS[rec["position"]]}
    if rec["polarity"]:
        out["g"] = POLARITIES[rec["polarity"]]
    if rec["voice"]:
        out["v"] = VOICES[rec["voice"]]
    for key, name in (("source", "s"), ("goal", "d"), ("place", "a")):
        if rec[key]:
            out[name] = [PLAYERS[p] + ":" + ZONES[z] for p, z in rec[key]]
    if rec["mode"]:
        out["m"] = MODES[rec["mode"]]
    if rec["heads"]:
        out["h"] = rec["heads"]
    if rec["goal_heads"]:
        out["dh"] = rec["goal_heads"]
    if with_extras is not None:
        out["x"] = rec["extras"][with_extras]
    return out


def encode_tuples(rec, lemma_code, with_extras):
    """B 定序小整數元組:固定欄序,列舉值是小整數,區域+玩家一對一個小整數,中心詞保留字面。"""
    out = [lemma_code[rec["lemma"]], rec["position"], rec["polarity"], rec["voice"],
           [pair_code(p, z) for p, z in rec["source"]],
           [pair_code(p, z) for p, z in rec["goal"]],
           [pair_code(p, z) for p, z in rec["place"]],
           rec["mode"], rec["heads"], rec["goal_heads"]]
    if with_extras is not None:
        out.extend(rec["extras"][with_extras])
    return out


def encode_dict(rec, lemma_code, head_code, with_extras):
    """C 欄位對照表+元組:B 之上把中心詞字面也換成對照表碼,尾端的空值截掉。"""
    out = [lemma_code[rec["lemma"]], rec["position"], rec["polarity"], rec["voice"],
           [pair_code(p, z) for p, z in rec["source"]],
           [pair_code(p, z) for p, z in rec["goal"]],
           [pair_code(p, z) for p, z in rec["place"]],
           rec["mode"], [head_code[h] for h in rec["heads"]],
           [head_code[h] for h in rec["goal_heads"]]]
    if with_extras is not None:
        out.extend(rec["extras"][with_extras])
    else:
        while out and out[-1] in (0, []):
            out.pop()
    return out


def load_cards_js():
    with open(DATA_JS, encoding="utf-8") as f:
        raw = f.read()
    i = raw.index("window.VOCAB=")
    j = raw.index("window.META=")
    cards = json.loads(raw[len("window.CARD_DATA="):i].rstrip().rstrip(";"))
    vocab = json.loads(raw[i + len("window.VOCAB="):j].rstrip().rstrip(";"))
    return cards, vocab


def percentile(counter, q):
    total = sum(counter.values())
    target = int(total * q)
    seen = 0
    for k in sorted(counter):
        seen += counter[k]
        if seen > target:
            return k
    return max(counter)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    with open(FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(CARDS, encoding="utf-8") as f:
        faces = {c["id"]: {k: c.get(k) for k in FACE_FIELDS} for c in json.load(f)}
    by_card, stats = project(sentences, faces)

    lemmas = sorted({r["lemma"] for rows in by_card.values() for row in rows for r in row})
    lemma_code = {l: i for i, l in enumerate(lemmas)}
    head_counter = Counter(h for rows in by_card.values() for row in rows for r in row
                           for h in r["heads"] + r["goal_heads"])
    heads = [h for h, _ in head_counter.most_common()]
    head_code = {h: i for i, h in enumerate(heads)}
    pair_counter = Counter(pair_code(p, z) for rows in by_card.values() for row in rows
                           for r in row for key in ("source", "goal", "place") for p, z in r[key])

    cards, vocab = load_cards_js()
    by_id = {c["id"]: c for c in cards}
    covered = [cid for cid in by_card if cid in by_id]
    stats["covered_cards"] = len(covered)
    stats["cards_in_index"] = len(cards)
    stats["lemmas"] = len(lemmas)
    stats["distinct_heads"] = len(heads)
    stats["distinct_zone_pairs"] = len(pair_counter)
    per_card = Counter(sum(len(row) for row in by_card[cid]) for cid in covered)

    def attach(encoder, with_extras):
        out = []
        for c in cards:
            base = {k: v for k, v in c.items() if k not in OLD_FIELDS}
            rows = by_card.get(c["id"])
            if rows is not None:
                base["fr"] = [[encoder(r, with_extras) for r in row] for row in rows]
            out.append(base)
        return out

    base_cards = [{k: v for k, v in c.items() if k not in OLD_FIELDS} for c in cards]
    results = {"baseline": {}, "encodings": {}}
    results["baseline"]["with_old_fields"] = sizes(cards)
    results["baseline"]["without_old_fields"] = sizes(base_cards)
    results["baseline"]["old_fields_standalone"] = sizes(
        [{k: c[k] for k in OLD_FIELDS if k in c} for c in cards])
    results["baseline"]["acat_vocab"] = sizes(vocab["acat"])

    encoders = {
        "A_objects": lambda r, x: encode_objects(r, lemma_code, x),
        "B_tuples": lambda r, x: encode_tuples(r, lemma_code, x),
        "C_dict": lambda r, x: encode_dict(r, lemma_code, head_code, x),
    }
    table_sizes = {"lemmas": sizes(lemmas), "heads": sizes(heads)}
    suffix = {None: "", 0: "+5均勻", 1: "+5偏態"}
    for name, enc in encoders.items():
        for with_extras in (None, 0, 1):
            full = attach(enc, with_extras)
            raw, gz = sizes(full)
            # C 的中心詞與詞元對照表要跟著進 VOCAB;B 只有詞元表;A 什麼表都不用
            tables = {"A_objects": (0, 0), "B_tuples": table_sizes["lemmas"],
                      "C_dict": tuple(map(sum, zip(table_sizes["lemmas"], table_sizes["heads"])))}[name]
            raw += tables[0]
            gz += tables[1]
            only = [c.get("fr", []) for c in full]
            key = name + suffix[with_extras]
            results["encodings"][key] = {
                "whole_with_tables": (raw, gz),
                "increment_vs_without_old": (raw - results["baseline"]["without_old_fields"][0],
                                             gz - results["baseline"]["without_old_fields"][1]),
                "increment_vs_with_old": (raw - results["baseline"]["with_old_fields"][0],
                                          gz - results["baseline"]["with_old_fields"][1]),
                "fr_standalone": sizes(only),
            }
            if with_extras is None:
                with open(os.path.join(args.out, "proj_%s.json" % name), "w", encoding="utf-8") as f:
                    f.write(dumps({"cards": [{"id": c["id"], "tx": len(c.get("tx", [])),
                                              "fr": c.get("fr")} for c in full],
                                   "lemmas": lemmas, "heads": heads}))
    results["tables"] = table_sizes
    results["stats"] = dict(stats)
    results["frames_per_covered_card"] = {
        "max": max(per_card),
        "mean": round(sum(k * v for k, v in per_card.items()) / sum(per_card.values()), 2),
        "p50": percentile(per_card, 0.5), "p95": percentile(per_card, 0.95),
    }
    results["top_heads"] = head_counter.most_common(25)
    results["top_zone_pairs"] = [("%s:%s" % (PLAYERS[c // 8], ZONES[c % 8]), n)
                                 for c, n in pair_counter.most_common(12)]
    results["head_tail"] = {"singletons": sum(1 for _, n in head_counter.items() if n == 1),
                            "<=3": sum(1 for _, n in head_counter.items() if n <= 3)}
    with open(os.path.join(args.out, "sizes.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(results, ensure_ascii=False, indent=1))
    print(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
