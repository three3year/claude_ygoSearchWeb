# -*- coding: utf-8 -*-
"""LLM 檢驗(票 09/10):分層抽樣固定 300 張卡、切批給子代理「看原文與框架挑錯」,
再把各批回報彙整成錯誤類型報告。

分層(依卡種與效果數):單效果怪獸 100、多效果怪獸 100、魔陷 70、靈擺 30;
種子固定,同一種子重抽得到同一批(複檢沿用);不同種子抽新樣本(過擬合抽驗)。

    sample  --round R --seed S   寫 llm-check/round<R>/sample.json 與 batch-<k>.md
    report  --round R            讀 llm-check/round<R>/findings-<k>.json 寫 report.md
    recheck --round R --from R0  用 round R0 的樣本重出批次檔(同批複檢)

子代理回報格式(findings-<k>.json):[{"card": 卡號, "index": "①", "frame": 框架序或 null,
"type": 錯誤類型, "reason": 理由}];錯誤類型固定五種:漏抽動作/論元抽錯/位置判錯/
極性判錯/多抽(不是動作)。
"""
import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CARDS = os.path.join(ROOT, "data", "cards.json")
TOKENS = os.path.join(HERE, "tokens.json")
FRAMES = os.path.join(HERE, "frames.json")
CHECK_DIR = os.path.join(HERE, "llm-check")

QUOTA = {"mono": 100, "multi": 100, "st": 70, "pendulum": 30}
BATCHES = 8
ERROR_TYPES = ("漏抽動作", "論元抽錯", "位置判錯", "極性判錯", "多抽(不是動作)")
TYPE_PENDULUM, TYPE_SPELL, TYPE_TRAP = 0x1000000, 0x2, 0x4


def load():
    with open(CARDS, encoding="utf-8") as f:
        cards = {c["id"]: c for c in json.load(f)}
    with open(TOKENS, encoding="utf-8") as f:
        tokens = json.load(f)
    with open(FRAMES, encoding="utf-8") as f:
        frames = json.load(f)
    return cards, tokens, frames


def stratum_of(card, effect_count):
    t = card["type"]
    if t & TYPE_PENDULUM:
        return "pendulum"
    if t & (TYPE_SPELL | TYPE_TRAP):
        return "st"
    return "mono" if effect_count <= 1 else "multi"


def sample(seed):
    cards, tokens, _ = load()
    effect_count = Counter(s["card"] for s in tokens if s["stratum"] == "effect")
    pools = defaultdict(list)
    for cid in sorted({s["card"] for s in tokens}):
        pools[stratum_of(cards[cid], effect_count[cid])].append(cid)
    rng = random.Random(seed)
    picked = []
    for key in ("mono", "multi", "st", "pendulum"):
        chosen = sorted(rng.sample(pools[key], QUOTA[key]))
        picked += [{"card": cid, "stratum": key} for cid in chosen]
    return picked


def card_block(cid, cards, recs, frames_by_key):
    c = cards[cid]
    lines = ["## 卡 %d %s(%s)" % (cid, c["name_ja"], c["name_zh"]), ""]
    for s in recs:
        label = ("靈擺 " if s["section"] == "pendulum" else "") + (
            "效果外文本 " + s["index"] if s["stratum"] == "extra" else s["index"])
        lines.append("### 句 %s" % label)
        lines.append("原文:%s" % s["text_ja"].replace("\n", " "))
        fr = frames_by_key[(s["card"], s["section"], s["index"])]
        if not fr:
            lines.append("框架:(無)")
        for k, f in enumerate(fr, 1):
            lines.append("框架 %d:[%s] %s(%s)| 對象=%s | 來源=%s | 目的=%s | 子句=%s"
                         % (k, f["position"], f["action"], f["polarity"],
                            f.get("object") or "", f.get("source") or "",
                            f.get("goal") or "", f["clause"]))
        lines.append("")
    return lines


def write_batches(round_dir, picked):
    cards, tokens, frames = load()
    frames_by_key = {(r["card"], r["section"], r["index"]): r["frames"]
                     for r in frames}
    recs_by_card = defaultdict(list)
    for s in tokens:
        recs_by_card[s["card"]].append(s)
    os.makedirs(round_dir, exist_ok=True)
    with open(os.path.join(round_dir, "sample.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(picked, f, ensure_ascii=False, indent=0)
        f.write("\n")
    per = -(-len(picked) // BATCHES)
    for k in range(BATCHES):
        chunk = picked[k * per:(k + 1) * per]
        lines = ["# 批次 %d(%d 張卡)" % (k, len(chunk)), ""]
        for p in chunk:
            lines += card_block(p["card"], cards, recs_by_card[p["card"]],
                                frames_by_key)
        with open(os.path.join(round_dir, "batch-%d.md" % k), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
        print("written batch-%d.md (%d cards)" % (k, len(chunk)))


def report(round_dir):
    findings = []
    for k in range(BATCHES):
        path = os.path.join(round_dir, "findings-%d.json" % k)
        if not os.path.exists(path):
            print("missing", path)
            continue
        with open(path, encoding="utf-8") as f:
            for item in json.load(f):
                item["batch"] = k
                findings.append(item)
    with open(os.path.join(round_dir, "sample.json"), encoding="utf-8") as f:
        picked = json.load(f)
    stratum_of_card = {p["card"]: p["stratum"] for p in picked}
    by_type = Counter(f["type"] for f in findings)
    by_type_stratum = Counter((f["type"], stratum_of_card.get(f["card"], "?"))
                              for f in findings)
    cards_with = len({f["card"] for f in findings})
    lines = [
        "# LLM 檢驗報告:%s" % os.path.basename(round_dir),
        "",
        "樣本 %d 張卡(單效果怪獸 %d/多效果 %d/魔陷 %d/靈擺 %d);回報 %d 筆,"
        "涉及 %d 張卡(%.1f%%)。" % (
            len(picked), QUOTA["mono"], QUOTA["multi"], QUOTA["st"],
            QUOTA["pendulum"], len(findings), cards_with,
            100.0 * cards_with / max(1, len(picked))),
        "",
        "| 錯誤類型 | 筆數 | 單效果 | 多效果 | 魔陷 | 靈擺 |",
        "|---|---|---|---|---|---|",
    ]
    for t in ERROR_TYPES:
        lines.append("| %s | %d | %d | %d | %d | %d |" % (
            t, by_type.get(t, 0), by_type_stratum.get((t, "mono"), 0),
            by_type_stratum.get((t, "multi"), 0),
            by_type_stratum.get((t, "st"), 0),
            by_type_stratum.get((t, "pendulum"), 0)))
    other = [f for f in findings if f["type"] not in ERROR_TYPES]
    if other:
        lines.append("| (其他) | %d | | | | |" % len(other))
    lines.append("")
    for t in ERROR_TYPES + ("其他",):
        items = [f for f in findings
                 if (f["type"] == t if t != "其他" else f["type"] not in ERROR_TYPES)]
        if not items:
            continue
        lines += ["## %s(%d 筆)" % (t, len(items)), ""]
        for f in items:
            lines.append("- `%s` %s 框架 %s:%s" % (
                f["card"], f.get("index", ""), f.get("frame", "—"),
                f.get("reason", "").replace("\n", " ")))
        lines.append("")
    path = os.path.join(round_dir, "report.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("written", path, "findings", len(findings))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("sample", "report", "recheck"))
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--from", dest="from_round", type=int)
    args = ap.parse_args()
    round_dir = os.path.join(CHECK_DIR, "round%d" % args.round)
    if args.command == "sample":
        write_batches(round_dir, sample(args.seed))
    elif args.command == "recheck":
        with open(os.path.join(CHECK_DIR, "round%d" % args.from_round,
                               "sample.json"), encoding="utf-8") as f:
            write_batches(round_dir, json.load(f))
    else:
        report(round_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
