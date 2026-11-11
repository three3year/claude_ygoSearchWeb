"""m3b 標準卡核對:各票的候選卡、替代卡與另寫斷言的卡在全庫產物上整張通不通過。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3b/stats/m3b_golden_check.py > .scratch/action-structure-m3b/stats/m3b_golden_check.txt
只讀 data/action_structure.json;用 repo 的 reverse_check.check_card。輸出決定性。
「候選」= 規格「測試決策」表的卡;「替代」= 票改用、斷言整張通過的卡;「其他」= 票另寫斷言的卡。
每列:票、角色、卡號、卡名、段數、整張通過或沒通過的處數與前三處(原因:段原文)。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "action-structure-m3", "stats"))

from common import all_segments, cards, seg_text, short  # noqa: E402
from reverse_check import check_card  # noqa: E402

CARDS = (
    ("01", "候選", (1561110, 1295442, 847217)),
    ("01", "替代", (24508238, 6983839, 33776843, 21056275)),
    ("01", "其他", (24749710, 13744068, 21846145, 21143940)),
    ("02", "候選", (759393, 923596, 1571945, 62121, 1995985)),
    ("02", "其他", (2326738, 14824019, 88650530)),
    ("03", "候選", (293542, 1735088, 35699)),
    ("03", "其他", (31550470,)),
    ("04", "候選", (3825890, 10060427, 218704, 23536866, 45450218, 5253985)),
    ("04", "替代", (76930964, 93211836)),
    ("04", "其他", (38589847, 59951714)),
    ("05", "候選", (2403771, 8775395, 15635751, 13391185)),
    ("05", "替代", (24027078, 60764609)),
    ("06", "候選", (41578483, 30138615, 95911373)),
    ("06", "替代", (28183605, 85545073)),
    ("07", "候選", (22790789, 7617253, 7405310, 3055837, 75198893, 1295111, 21143940, 856784)),
    ("07", "替代", (55289183, 79571449, 6351548, 19027895)),
    ("07", "其他", (84472026,)),
)


def main():
    by_id = {c["id"]: c for c in cards()}
    totals = {}
    for ticket, role, ids in CARDS:
        for cid in ids:
            card = by_id[cid]
            segs = {(b["id"], s["id"]): seg_text(b, s) for b, s in all_segments(card)}
            failures = check_card(card)
            ok, n = totals.get(role, (0, 0))
            totals[role] = (ok + (not failures), n + 1)
            if not failures:
                print(f"{ticket}\t{role}\t{cid}\t{card['name_ja']}\t段 {len(segs)}\t整張通過")
                continue
            where = ";".join(f"{f['detail'] or f['reason']}「{short(segs.get((f['block'], f['segment']), ''), 40)}」"
                             for f in failures[:3])
            print(f"{ticket}\t{role}\t{cid}\t{card['name_ja']}\t段 {len(segs)}\t沒通過({len(failures)} 處)\t{where}")
    print("合計:" + "、".join(f"{role} {ok} / {n} 張整張通過" for role, (ok, n) in totals.items()))


main()
