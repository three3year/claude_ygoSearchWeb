"""第 5 類補充(票 11):「Xした/されたターンの〈階段〉に」以句子為單位的前後對比。

c5 的表二比的是「段原文含『ターンのエンドフェイズ』」;票 11 之後這種句子切成條件段(到「ターン」為止)
與帶前提的段(從「の〈階段〉」起),兩段的原文都不再含整串字面,表二的數字會掉得比實際多。
這支改以句子為單位:找出原文含該寫法的句子,分別看蓋住「ターン」的段(動作子句)與蓋住階段字面的段
(時點)有沒有解析出、有沒有通過反向檢查。階段字面由分歧引導句(段樹)認走時,時點那一欄算「引導句」。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c5b_timepoint_sentences.py
讀 data/action_structure.json。
"""
import collections
import re

from common import all_segments, cards, short

from reverse_check import check_card  # noqa: E402  (common 已把 script/action_structure 放進 sys.path)

PHASE = "(?:エンドフェイズ|メインフェイズ[１２]?|バトルフェイズ|スタンバイフェイズ|ドローフェイズ)"
FORMS = [
    ("E1 「Xした/されたターンのエンドフェイズに」", r"たターンのエンドフェイズに"),
    ("E5 舊式「Xしたターンのエンドフェイズ時(、|に)」", r"たターンのエンドフェイズ時(?:、|に)"),
    ("其他階段「Xしたターンの(自分)〈階段〉(時)に」",
     r"たターンの(?:自分・相手の|自分|相手)?(?!エンドフェイズ)" + PHASE + r"(?:時、|時に|に)"),
    ("不收:「〜ターンのエンドフェイズ時まで/まで」", r"たターンのエンドフェイズ(?:時)?まで"),
    ("不收:「Xした相手/自分ターンのエンドフェイズ」", r"た(?:相手|自分|自分の|相手の)ターンのエンドフェイズ"),
]


def status(seg, failed):
    if seg is None:
        return "沒有段"
    if seg["unparsed"]:
        return "解析不出:" + seg["unparsed"]["reason"]
    return "通過" if seg["id"] not in failed else "解析出、反向檢查沒過"


def covering(segs, pos):
    return next((s for s in segs if s["span"][0] <= pos < s["span"][1]), None)


def main():
    rows = collections.defaultdict(list)
    for c in cards():
        failed = None
        by_block = collections.defaultdict(list)
        for b, s in all_segments(c):
            by_block[id(b)].append((b, s))
        for pairs in by_block.values():
            block = pairs[0][0]
            segs = [s for _, s in pairs]
            for name, pattern in FORMS:
                for m in re.finditer(pattern, block["text"]):
                    if failed is None:
                        failed = {f["segment"] for f in check_card(c)}
                    turn_pos = m.start() + 1                      # 「ターン」的第一個字
                    phase_pos = block["text"].index("フェイズ", m.start())
                    clause = covering(segs, turn_pos)
                    point = covering(segs, phase_pos)
                    point_status = status(point, failed) if point is not None else "引導句(段樹)"
                    same = point is not None and clause is not None and point["id"] == clause["id"]
                    rows[name].append((c["id"], c["name_ja"], status(clause, failed),
                                       "同一段" if same else point_status,
                                       short(block["text"][max(0, m.start() - 20):m.end()], 60)))
    for name, _ in FORMS:
        items = rows.get(name, [])
        print(f"\n{name}: {len(items)} 處 / {len({r[0] for r in items})} 張")
        print("| 動作子句(蓋住「ターン」的段) | 時點(蓋住階段字面的段) | 處 | 例 |")
        print("|---|---|---|---|")
        groups = collections.Counter((r[2], r[3]) for r in items)
        for (clause, point), n in groups.most_common():
            ex = next(r for r in items if (r[2], r[3]) == (clause, point))
            print(f"| {clause} | {point} | {n} | {ex[1]} {ex[0]}「{ex[4]}」 |")


if __name__ == "__main__":
    main()
