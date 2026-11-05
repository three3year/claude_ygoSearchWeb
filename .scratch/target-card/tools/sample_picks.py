# -*- coding: utf-8 -*-
"""針對卡片抽驗卡候選的細表(口徑同 sample_target_card.py):每張卡「只看有寫條件的」命中(分他卡框/自己框、
命中段有「卡名/字段」條件的專門支援框、部分條件未比對)、預設模式命中、擋下(被非 このカード 的寫出條件擋)。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sample_target_card as T  # noqa: E402

PICKS = (("黑魔導", (46986414,)),
         ("同步", (50954680, 84815190, 80666118, 27548199)),
         ("超量", (90448279, 56832966, 28346136)),
         ("連結", (86066372, 65741786, 63288573, 5043010)),
         ("魔法", (44362883, 17236839, 63166095, 24224830)))


def named(seg):
    head = seg["head"] or ""
    return head.startswith("「") or any(m["kind"] == T.P.MOD_ARCHETYPE for m in seg["modifiers"])


def main():
    _, cards, table = T.load()
    lines = ["欄:他卡框命中 框/張 | 其中卡名·字段條件 框 | 部分未比對 框 | 自己框命中 | 預設(非空泛)框 | 擋下 框/張"]
    for cls, ids in PICKS:
        lines.append("== " + cls)
        for cid in ids:
            face = T.card_face(cards[cid])
            hit, hit_cards, name_hit, partial, own, dflt, blk, blk_cards = 0, set(), 0, 0, 0, 0, 0, set()
            for card, pos, gs, fr, s in table:
                r = T.judge(gs, face, card == cid)
                if r["default"] and not r["empty"]:
                    dflt += 1
                if r["blocked_cond"]:
                    blk += 1
                    blk_cards.add(card)
                if not r["strict"]:
                    continue
                if card == cid:
                    own += 1
                    continue
                hit += 1
                hit_cards.add(card)
                partial += r["partial_s"]
                segs = [seg for _, g in gs if g for seg in g
                        if T.seg_eval(seg, face, False)[0] and T.seg_eval(seg, face, False)[1] > 0]
                name_hit += any(named(seg) for seg in segs)
            c = cards[cid]
            lines.append("  %s %s / %s:%d/%d | %d | %d | %d | %d | %d/%d" % (
                cid, c["name_ja"], c["name_zh"], hit, len(hit_cards), name_hit, partial, own, dflt, blk, len(blk_cards)))
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "results", "sample_picks.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
