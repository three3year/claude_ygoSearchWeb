# -*- coding: utf-8 -*-
"""把「只判類型」批次檔倒成可讀的純文字,供判定時逐卡閱讀。

用法:python _dumpkind.py 01  → .scratch/tag-card/batches/_dumpkind01.txt
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def nl(s):
    return (s or "").replace("\n", " /N ")


def main():
    n = sys.argv[1]
    batch = os.path.join(ROOT, ".scratch", "tag-card", "batches", "kind-%s.json" % n)
    out = os.path.join(ROOT, ".scratch", "tag-card", "batches", "_dumpkind%s.txt" % n)
    b = json.load(io.open(batch, encoding="utf-8"))
    fh = io.open(out, "w", encoding="utf-8")
    for i, e in enumerate(b["entries"]):
        fh.write("=" * 70 + "\n")
        fh.write("[%d] %s / %s (%s) %s\n" % (i, e["id"], e["name_zh"], e["name_ja"], e["card_type"]))
        fh.write("ZH: %s\n" % nl(e["card_text_zh"]))
        fh.write("JA: %s\n" % nl(e["card_text_ja"]))
        if e.get("supplement"):
            fh.write("SUP: %s\n" % nl(e["supplement"]))
        if e.get("pendulum"):
            p = e["pendulum"]
            fh.write("P-JA: %s\n" % nl(p.get("card_text_ja")))
            if p.get("supplement"):
                fh.write("P-SUP: %s\n" % nl(p.get("supplement")))
        for c in e["clauses"]:
            fh.write("  CLAUSE %s/%s rule=%s\n" % (c["section"], c["index"], c.get("rule_predicted")))
            fh.write("    ZH: %s\n" % nl(c["text_zh"]))
            fh.write("    JA: %s\n" % nl(c["text_ja"]))
    fh.close()
    print("wrote", out, len(b["entries"]))


if __name__ == "__main__":
    main()
