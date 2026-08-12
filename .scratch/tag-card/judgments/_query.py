# -*- coding: utf-8 -*-
"""全表查詢:拿一條日文正則掃 `data/tag_cards.json` 的所有效果句,
回報現有的[[效果類型]]分布,並區分 source(official / llm / rule)。

判定票要「量全表」時用它:先看官方給過答案的那一半怎麼判,再決定本票怎麼填。

用法:
  python _query.py "装備モンスター.*代わりにこのカードを破壊"
  python _query.py "しか表側表示で存在できない" --show 5
  python _query.py "永続魔法カード扱い" --field sup     # 改掃補足情報
"""
import argparse
import collections
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CARDS = os.path.join(ROOT, "data", "tag_cards.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pattern")
    ap.add_argument("--field", default="ja", choices=("ja", "zh", "sup"))
    ap.add_argument("--show", type=int, default=0, help="列出前 N 條命中的原文")
    ap.add_argument("--kind", default=None, help="只列這個類型的命中")
    ap.add_argument("--source", default=None, help="只列這個 source 的命中")
    args = ap.parse_args()

    rx = re.compile(args.pattern)
    cards = json.load(io.open(CARDS, encoding="utf-8"))
    key = {"ja": "text_ja", "zh": "text_zh", "sup": "supplement"}[args.field]

    hits = []
    for card in cards:
        for clause in card.get("clauses", []):
            text = clause.get(key) or ""
            if args.field == "sup":
                text = card.get("supplement") or ""
            if not rx.search(text):
                continue
            hits.append((card["id"], clause))

    by_kind = collections.Counter()
    by_source = collections.Counter()
    official = collections.Counter()
    for cid, clause in hits:
        by_kind[clause.get("kind") or "(留空)"] += 1
        by_source[clause.get("source") or "(無)"] += 1
        if clause.get("source") == "official":
            official[clause.get("kind") or "(留空)"] += 1

    print("命中 %d 條 / %d 張" % (len(hits), len({c for c, _ in hits})))
    print("類型分布:", dict(by_kind.most_common()))
    print("source :", dict(by_source.most_common()))
    print("官方明示:", dict(official.most_common()))

    shown = 0
    for cid, clause in hits:
        if shown >= args.show:
            break
        if args.kind and (clause.get("kind") or "") != args.kind:
            continue
        if args.source and (clause.get("source") or "") != args.source:
            continue
        print("-" * 60)
        print("%s %s/%s  kind=%s optional=%s source=%s"
              % (cid, clause.get("section"), clause.get("index"),
                 clause.get("kind"), clause.get("optional"), clause.get("source")))
        print("  JA:", (clause.get("text_ja") or "").replace("\n", " /N "))
        shown += 1


if __name__ == "__main__":
    main()
