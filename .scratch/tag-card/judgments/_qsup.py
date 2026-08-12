# -*- coding: utf-8 -*-
"""全表查詢(補足情報側):拿一條正則掃 `data/sources/faq_info.json` 的每一行明示,
回報命中的卡與那一行,並附上該卡在[[效果標記表]]上的現有判定,供判定票量全表用。

用法:
  python _qsup.py "装備カードとなった"
  python _qsup.py "永続魔法カード扱いの効果" --clauses
"""
import argparse
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
FAQ = os.path.join(ROOT, "data", "sources", "faq_info.json")
CARDS = os.path.join(ROOT, "data", "tag_cards.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern")
    ap.add_argument("--clauses", action="store_true", help="一併列出該卡的效果句判定")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    rx = re.compile(args.pattern)
    faq = json.load(io.open(FAQ, encoding="utf-8"))
    tagged = {c["id"]: c for c in json.load(io.open(CARDS, encoding="utf-8"))}

    hits = 0
    for entry in faq:
        sup = entry.get("supplement") or ""
        lines = [ln for ln in sup.split("\n") if rx.search(ln)]
        if not lines:
            continue
        hits += 1
        if hits > args.limit:
            continue
        pid = entry.get("password")
        print("=" * 60)
        print("%s %s" % (pid, entry.get("name_ja")))
        for ln in lines:
            print("  ", ln.strip()[:220])
        if args.clauses and pid in tagged:
            for cl in tagged[pid]["clauses"]:
                print("   -> %s/%s kind=%s optional=%s source=%s"
                      % (cl.get("section"), cl.get("index"), cl.get("kind"),
                         cl.get("optional"), cl.get("source")))
    print("命中 %d 張" % hits)


if __name__ == "__main__":
    main()
