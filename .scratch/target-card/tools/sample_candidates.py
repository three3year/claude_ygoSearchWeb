# -*- coding: utf-8 -*-
"""針對卡片抽驗卡候選:涵蓋範圍內(frames.json 有框的卡 = 新格式新卡層)的同步/超量/連結/魔法卡,
逐張算「只看有寫條件的」命中框與「被寫出條件擋下」框(口徑同 sample_target_card.py),各類列前 N。
用法:python -X utf8 sample_candidates.py [每類列幾張]"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sample_target_card as T  # noqa: E402

SYNCHRO, XYZ, LINK, SPELL, QUICK, FIELD = 0x2000, 0x800000, 0x4000000, 0x2, 0x10000, 0x80000
CLASSES = (("同步", lambda t: t & SYNCHRO), ("超量", lambda t: t & XYZ), ("連結", lambda t: t & LINK),
           ("魔法", lambda t: t & SPELL))


def interesting(gs):
    """框裡有沒有任一段寫了條件(修飾語、中心詞前綴、「卡名」)或是 このカード:沒有的框對每張卡都一樣,略過。"""
    for _, g in gs:
        for seg in g or ():
            head = seg["head"] or ""
            if seg["modifiers"] or T.P._head_face(head)[1] or head.startswith("「") or T.P._is_this_card(seg):
                return True
    return False


def main():
    top = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    t0 = time.time()
    sentences, cards, table = T.load()
    sub = [row for row in table if interesting(row[2])]
    covered = {s["card"] for s in sentences}
    lines = ["動作框 %d,有寫條件的框 %d;涵蓋範圍內卡 %d" % (len(table), len(sub), len(covered))]
    for name, pred in CLASSES:
        pool = [cid for cid in covered if cid in cards and pred(cards[cid]["type"] or 0)]
        scored = []
        for cid in pool:
            face = T.card_face(cards[cid])
            hit = hit_other = blk = 0
            hit_cards = set()
            for card, pos, gs, fr, s in sub:
                r = T.judge(gs, face, card == cid)
                if r["strict"]:
                    hit += 1
                    hit_cards.add(card)
                    if card != cid:
                        hit_other += 1
                if r["blocked_cond"]:
                    blk += 1
            scored.append((hit_other, hit, len(hit_cards), blk, cid))
        scored.sort(reverse=True)
        lines.append("\n== %s:涵蓋範圍內 %d 張,依「只看有寫」命中(不含自己的框)排序前 %d" % (name, len(pool), top))
        lines.append("  命中(他卡框) 命中框 命中張 擋下框 密碼 日文名 / 中文名 type")
        for hit_other, hit, hc, blk, cid in scored[:top]:
            c = cards[cid]
            lines.append("  %5d %5d %5d %6d  %s %s / %s 0x%x" % (hit_other, hit, hc, blk, cid, c["name_ja"],
                                                               c["name_zh"], c["type"]))
        print(name, "done %.0fs" % (time.time() - t0), flush=True)
    lines.append("耗時 %.0fs" % (time.time() - t0))
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "results", "sample_candidates.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
