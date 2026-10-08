# -*- coding: utf-8 -*-
"""LLM 檢驗(票 09/10/15):分層抽樣固定一批卡、切批給子代理「看原文與框架挑錯」,
再把各批回報彙整成錯誤類型報告。

兩種抽樣:
- 全語料(票 09;round1〜4):依卡種與效果數分層——單效果怪獸 100、多效果怪獸 100、
  魔陷 70、靈擺 30,切 8 批。
- 受影響卡(票 15;round5 起):● 合併(ADR-0015)影響到的卡——有子效果句的卡加上
  含未拆 ● 的卡;依母句家族分層(賦予型/發動時選/處理時選/適用/依條件發動/其他/
  未拆●),抽 100 張、切 4 批。
種子固定,同一種子重抽得到同一批(複檢沿用);不同種子抽新樣本(過擬合抽驗)。

    sample   --round R --seed S   全語料抽樣:寫 llm-check/round<R>/sample.json 與 batch-<k>.md
    affected --round R --seed S   受影響卡抽樣(同上,另寫 meta.json 記分層與批數)
    report   --round R            讀 llm-check/round<R>/findings-<k>.json 寫 report.md
    recheck  --round R --from R0  用 round R0 的樣本重出批次檔(同批複檢)

批次檔一張卡一節、一句效果句一段:整段效果句(含 ● 選項;拆開的領起句與子效果句
各標 index 與效果類型)與它的框架(含選項欄「●n 標籤」)。

子代理回報格式(findings-<k>.json):[{"card": 卡號, "index": "①", "frame": 框架序或 null,
"type": 錯誤類型, "reason": 理由, "merge_related": true/false}];錯誤類型固定五種:
漏抽動作/論元抽錯/位置判錯/極性判錯/多抽(不是動作);merge_related 標這筆是否和
● 合併有關(round5 起)。
"""
import argparse
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CARDS = os.path.join(ROOT, "data", "cards.json")
TOKENS = os.path.join(HERE, "tokens.json")
FRAMES = os.path.join(HERE, "frames.json")
CHECK_DIR = os.path.join(HERE, "llm-check")

QUOTA = {"mono": 100, "multi": 100, "st": 70, "pendulum": 30}
STRATUM_LABEL = {"mono": "單效果怪獸", "multi": "多效果怪獸", "st": "魔陷",
                 "pendulum": "靈擺"}
BATCHES = 8
# 受影響卡(票 15):母句家族 → 配額(合計 100);某家族不足額時缺口補給 未拆●
FAMILIES = ("賦予型", "發動時選", "處理時選", "適用", "依條件發動", "其他", "未拆●")
QUOTA_AFFECTED = {"賦予型": 22, "發動時選": 18, "處理時選": 8, "適用": 15,
                  "依條件發動": 8, "其他": 4, "未拆●": 25}
BATCHES_AFFECTED = 4
ERROR_TYPES = ("漏抽動作", "論元抽錯", "位置判錯", "極性判錯", "多抽(不是動作)")
TYPE_PENDULUM, TYPE_SPELL, TYPE_TRAP = 0x1000000, 0x2, 0x4
OPTION = "●"


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


# ── 受影響卡(票 15)──

def family_of(lead_text):
    """領起句(第一個 ● 之前的文字)→ 母句家族。順序:賦予型 → 發動時選 → 處理時選
    → 適用 → 依條件發動 → 其他。"""
    t = lead_text
    if "効果を得る" in t or "効果を持つ" in t:
        return "賦予型"
    if re.search(r"(選択|選ん)で?(して)?発動", t) or "選択して発動" in t:
        return "發動時選"
    if re.search(r"選択|選ん|選び", t):
        return "處理時選"
    if "適用" in t:
        return "適用"
    if "発動できる" in t or "発動する" in t:
        return "依條件發動"
    return "其他"


def affected_pools(tokens):
    """{家族: [卡號]}:有子效果句的卡依它第一句含子效果句的效果句分家族;只含
    未拆 ● 的卡歸 未拆●。"""
    family_by_card = {}
    unsplit_cards = set()
    for s in tokens:
        if len(s["parts"]) > 1:
            if s["card"] not in family_by_card:
                lead = s["text_ja"][:s["parts"][1]["start"]]
                family_by_card[s["card"]] = family_of(lead)
        elif OPTION in s["tokens"]:
            unsplit_cards.add(s["card"])
    pools = defaultdict(list)
    for cid, fam in family_by_card.items():
        pools[fam].append(cid)
    for cid in unsplit_cards - set(family_by_card):
        pools["未拆●"].append(cid)
    return {k: sorted(v) for k, v in pools.items()}


def sample_affected(seed):
    _cards, tokens, _ = load()
    pools = affected_pools(tokens)
    rng = random.Random(seed)
    quota = dict(QUOTA_AFFECTED)
    short = sum(max(0, quota[k] - len(pools.get(k, []))) for k in FAMILIES)
    quota["未拆●"] += short                   # 不足額的家族,缺口補給 未拆●
    picked = []
    for key in FAMILIES:
        pool = pools.get(key, [])
        chosen = sorted(rng.sample(pool, min(quota[key], len(pool))))
        picked += [{"card": cid, "stratum": key} for cid in chosen]
    print("母體:" + "、".join("%s %d" % (k, len(pools.get(k, []))) for k in FAMILIES))
    return picked


# ── 批次檔 ──

def record_lines(s, fr):
    """一句效果句 → 批次檔的一段:整段原文(拆開的各段標 index・效果類型)+ 框架。"""
    label = ("靈擺 " if s["section"] == "pendulum" else "") + (
        "效果外文本 " + s["index"] if s["stratum"] == "extra" else s["index"])
    lines = ["### 句 %s" % label]
    if len(s["parts"]) > 1:
        lines.append("原文(效果句含 %d 個 ● 子效果句,各段的效果類型如標):"
                     % (len(s["parts"]) - 1))
        for p in s["parts"]:
            lines.append("  [%s・%s] %s" % (
                p["index"], p["kind"],
                s["text_ja"][p["start"]:p["end"]].replace("\n", " ")))
    else:
        lines.append("原文:%s" % s["text_ja"].replace("\n", " "))
    if not fr:
        lines.append("框架:(無)")
    for k, f in enumerate(fr, 1):
        opt = ""
        if f.get("option") is not None:
            opt = " | 選項=●%d%s" % (f["option"],
                                    " " + f["label"] if f.get("label") else "")
        lines.append("框架 %d:[%s] %s(%s)| 對象=%s | 來源=%s | 目的=%s%s | 子句=%s"
                     % (k, f["position"], f["action"], f["polarity"],
                        f.get("object") or "", f.get("source") or "",
                        f.get("goal") or "", opt, f["clause"]))
    lines.append("")
    return lines


def card_block(cid, cards, recs, frames_by_key):
    c = cards[cid]
    lines = ["## 卡 %d %s(%s)" % (cid, c["name_ja"], c["name_zh"]), ""]
    for s in recs:
        lines += record_lines(s, frames_by_key[(s["card"], s["section"], s["index"])])
    return lines


def write_batches(round_dir, picked, meta):
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
    with open(os.path.join(round_dir, "meta.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # 輪流分配:每批混合各分層(連續切會一批幾乎同一分層)
    batches = meta["batches"]
    for k in range(batches):
        chunk = picked[k::batches]
        lines = ["# 批次 %d(%d 張卡)" % (k, len(chunk)), ""]
        for p in chunk:
            lines += card_block(p["card"], cards, recs_by_card[p["card"]],
                                frames_by_key)
        with open(os.path.join(round_dir, "batch-%d.md" % k), "w",
                  encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines))
        print("written batch-%d.md (%d cards)" % (k, len(chunk)))


def read_meta(round_dir):
    path = os.path.join(round_dir, "meta.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"mode": "sample", "batches": BATCHES, "strata": list(QUOTA)}


# ── 報告 ──

def report(round_dir):
    meta = read_meta(round_dir)
    findings = []
    for k in range(meta["batches"]):
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
    strata = meta["strata"]
    label = {k: STRATUM_LABEL.get(k, k) for k in strata}
    stratum_of_card = {p["card"]: p["stratum"] for p in picked}
    quota = Counter(p["stratum"] for p in picked)
    by_type = Counter(f["type"] for f in findings)
    by_type_stratum = Counter((f["type"], stratum_of_card.get(f["card"], "?"))
                              for f in findings)
    cards_with = len({f["card"] for f in findings})
    merge_related = [f for f in findings if f.get("merge_related")]
    lines = [
        "# LLM 檢驗報告:%s" % os.path.basename(round_dir),
        "",
        "樣本 %d 張卡(%s);回報 %d 筆,涉及 %d 張卡(%.1f%%)。" % (
            len(picked), "/".join("%s %d" % (label[k], quota[k]) for k in strata),
            len(findings), cards_with, 100.0 * cards_with / max(1, len(picked))),
        "",
        "| 錯誤類型 | 筆數 | " + " | ".join(label[k] for k in strata) + " |",
        "|---|---|" + "---|" * len(strata),
    ]
    for t in ERROR_TYPES:
        lines.append("| %s | %d | %s |" % (
            t, by_type.get(t, 0),
            " | ".join(str(by_type_stratum.get((t, k), 0)) for k in strata)))
    other = [f for f in findings if f["type"] not in ERROR_TYPES]
    if other:
        lines.append("| (其他) | %d | %s |" % (len(other), " | ".join(
            str(sum(1 for f in other if stratum_of_card.get(f["card"]) == k))
            for k in strata)))
    cards_per = Counter(stratum_of_card[c] for c in {f["card"] for f in findings}
                        if c in stratum_of_card)
    lines.append("| 涉及卡 | %d | %s |" % (
        cards_with, " | ".join("%d/%d" % (cards_per.get(k, 0), quota[k])
                               for k in strata)))
    lines.append("")
    if meta.get("mode") == "affected":
        by_type_merge = Counter(f["type"] for f in merge_related)
        lines += [
            "和 ● 合併有關的回報 %d 筆(%s);其餘 %d 筆是合併前就有的規則問題。" % (
                len(merge_related),
                "、".join("%s %d" % (t, by_type_merge[t]) for t in ERROR_TYPES
                          if by_type_merge[t]) or "無",
                len(findings) - len(merge_related)),
            "",
        ]
    for t in ERROR_TYPES + ("其他",):
        items = [f for f in findings
                 if (f["type"] == t if t != "其他" else f["type"] not in ERROR_TYPES)]
        if not items:
            continue
        lines += ["## %s(%d 筆)" % (t, len(items)), ""]
        for f in items:
            tag = "【合併】" if f.get("merge_related") else ""
            lines.append("- `%s` %s 框架 %s:%s%s" % (
                f["card"], f.get("index", ""), f.get("frame", "—"), tag,
                f.get("reason", "").replace("\n", " ")))
        lines.append("")
    path = os.path.join(round_dir, "report.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("written", path, "findings", len(findings))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("sample", "affected", "report", "recheck"))
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--seed", type=int, default=20261009)
    ap.add_argument("--from", dest="from_round", type=int)
    args = ap.parse_args()
    round_dir = os.path.join(CHECK_DIR, "round%d" % args.round)
    if args.command == "sample":
        write_batches(round_dir, sample(args.seed),
                      {"mode": "sample", "seed": args.seed, "batches": BATCHES,
                       "strata": list(QUOTA)})
    elif args.command == "affected":
        write_batches(round_dir, sample_affected(args.seed),
                      {"mode": "affected", "seed": args.seed,
                       "batches": BATCHES_AFFECTED, "strata": list(FAMILIES)})
    elif args.command == "recheck":
        src = os.path.join(CHECK_DIR, "round%d" % args.from_round)
        with open(os.path.join(src, "sample.json"), encoding="utf-8") as f:
            picked = json.load(f)
        meta = dict(read_meta(src), recheck_of=args.from_round)
        write_batches(round_dir, picked, meta)
    else:
        report(round_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
