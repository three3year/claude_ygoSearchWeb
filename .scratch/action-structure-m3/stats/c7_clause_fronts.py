"""物件切點切出去的子句前文(m3 票 03):哪些認得、哪些認不得。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c7_clause_fronts.py [--top N]
前文不存在產物裡(認得的已填進段的格,認不得的只留原因),所以這支用 repo 的程式把全庫重建一次
(約 15 秒,不寫檔),在 `clause_front.fill_front` 被呼叫時記下前文字面與結果。
印:切出前文的子句數、認得/認不得、認不得的原因;認不得與認得的前文各依字面計數
(「」裡的字與數字折掉,附第一張卡的卡號與那一段的原文)。
段最後標成什麼原因要看產物:子句本體自己解析不出時留本體的原因,不是這裡印的前文原因。
"""
import collections
import json
import os
import re
import sys

from common import ROOT, short

import clause_front  # noqa: E402
from card_structure import build_structures  # noqa: E402


def _load(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return json.load(f)


def _fold(front):
    return re.sub("[０-９]+", "N", re.sub("「[^」]*」", "「」", front))


def main(top):
    log = []
    original = clause_front.fill_front

    def spy(ctx, front):
        ok = original(ctx, front)
        reason = None if ok else ctx.seg["unparsed"]["reason"]
        log.append((front, reason, ctx.state.card["id"], ctx.seg["text"]))
        return ok

    clause_front.fill_front = spy
    patches = os.path.join(ROOT, "data", "block_boundaries.json")
    build_structures(_load("data", "cards.json"), _load("data", "sources", "faq_info.json"),
                     _load("data", "archetypes.json"),
                     boundary_patches=_load("data", "block_boundaries.json")
                     if os.path.exists(patches) else None)
    clause_front.fill_front = original
    known = [row for row in log if row[1] is None]
    unknown = [row for row in log if row[1] is not None]
    print(f"切出前文的子句: {len(log)};前文認得 {len(known)}、認不得 {len(unknown)}")
    for reason, n in collections.Counter(row[1] for row in unknown).most_common():
        print(f"  認不得的原因 {reason}: {n}")
    for title, rows in (("認不得的前文", unknown), ("認得的前文", known)):
        count = collections.Counter(_fold(row[0]) for row in rows)
        first = {}
        for front, _, cid, text in rows:
            first.setdefault(_fold(front), (cid, text))
        print(f"\n## {title}:{len(rows)} 處,相異字面 {len(count)}(列前 {top})")
        for front, n in count.most_common(top):
            cid, text = first[front]
            print(f"  {n}\t{front}\t{cid}「{short(text, 60)}」")


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 60)
