# -*- coding: utf-8 -*-
"""剝鍵比對(frame-args-v4 票 01):第四版論元只加欄不換值——把新鍵剝掉後,frames.json 要和
修前凍結的基準檔逐紀錄、逐框、逐鍵相同。

- NEW_KEYS:框架的頂層新鍵(規格的全部新欄,票 01 先列齊;這份清單是唯一要維護的東西);
  NEW_ANAPHORA_KEYS:回指欄的新子鍵(票 09 的 moving)。
- strip(frame):剝掉新鍵的框架副本。
- diff(baseline_path, current_path):差異清單 [(卡號, 段落, 句序, 框序, 鍵, 基準值, 現值)];
  框數不同時框序 None、鍵 "frames";紀錄缺少時鍵 "record"。
- underscore_keys(records):底線開頭的內部鍵(票 02 暫存切前字面用,enrich 用完要 pop 掉),
  不得出現在 frames.json。

CLI:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/baseline_diff.py [--baseline P] [--current P]
預設 baseline/frames.json(gitignore)與 frames.json;環境變數 FRAMES_BASELINE 蓋過預設基準。
差異非 0 或有底線鍵時 exit 1。基準檔:session scratchpad 的 v4-baseline/frames.json
(md5 2bcfb772edbdfa53f31885a3c103ce18),每個工作樹自己複製到預設路徑。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.environ.get("FRAMES_BASELINE") or os.path.join(HERE, "baseline", "frames.json")
CURRENT = os.path.join(HERE, "frames.json")

NEW_KEYS = ("phrases", "regions", "transfer", "agent", "agent_source", "agent_inferred",
            "manner", "manner_kind", "manner_value", "negation", "region_backfill")
NEW_ANAPHORA_KEYS = ("moving",)


def strip(frame):
    """剝掉新鍵的框架副本(原框架不動);回指欄也剝它的新子鍵。"""
    out = {k: v for k, v in frame.items() if k not in NEW_KEYS}
    anaphora = out.get("anaphora")
    if isinstance(anaphora, dict):
        out["anaphora"] = {k: v for k, v in anaphora.items() if k not in NEW_ANAPHORA_KEYS}
    return out


def _key(rec):
    return (rec["card"], rec["section"], rec["index"])


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def diff(baseline_path=BASELINE, current_path=CURRENT):
    """兩個框架檔 → 差異清單(剝掉新鍵後)。紀錄依 (卡號, 段落, 句序) 對齊,框依序比。"""
    base = {_key(r): r for r in _load(baseline_path)}
    cur = {_key(r): r for r in _load(current_path)}
    out = []
    for key in sorted(set(base) | set(cur)):
        if key not in cur:
            out.append(key + (None, "record", "基準有", "現在沒有"))
            continue
        if key not in base:
            out.append(key + (None, "record", "基準沒有", "現在有"))
            continue
        b_frames, c_frames = base[key]["frames"], cur[key]["frames"]
        if len(b_frames) != len(c_frames):
            out.append(key + (None, "frames", len(b_frames), len(c_frames)))
        for k, (b, c) in enumerate(zip(b_frames, c_frames)):
            b, c = strip(b), strip(c)
            for field in sorted(set(b) | set(c)):
                if b.get(field) != c.get(field):
                    out.append(key + (k, field, b.get(field), c.get(field)))
    return out


def underscore_keys(records):
    """[(卡號, 段落, 句序, 框序, 鍵)]:框架頂層以底線開頭的鍵。"""
    return [(r["card"], r["section"], r["index"], k, key)
            for r in records for k, fr in enumerate(r["frames"])
            for key in sorted(fr) if key.startswith("_")]


def main(argv=None):
    parser = argparse.ArgumentParser(description="剝掉第四版論元的新鍵後與基準框架檔比對")
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--current", default=CURRENT)
    parser.add_argument("--limit", type=int, default=30, help="最多列幾處差異")
    args = parser.parse_args(argv)
    if not os.path.exists(args.baseline):
        print("沒有基準檔:%s" % args.baseline, file=sys.stderr)
        return 2
    differences = diff(args.baseline, args.current)
    for row in differences[:args.limit]:
        print("差異:卡 %s %s/%s 框 %s 鍵 %s:基準 %r → 現在 %r" % row)
    underscored = underscore_keys(_load(args.current))
    for row in underscored[:args.limit]:
        print("底線鍵:卡 %s %s/%s 框 %s 鍵 %s" % row)
    print("剝鍵比對:差異 %d 處、底線鍵 %d 個(基準 %s)" % (
        len(differences), len(underscored), args.baseline))
    return 1 if differences or underscored else 0


if __name__ == "__main__":
    sys.exit(main())
