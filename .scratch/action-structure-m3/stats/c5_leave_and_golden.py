"""第 5 類:「離れた」「離れた場合に除外される」,與兩張標準卡剩下的寫法
(「〜ターンのエンドフェイズに」發動時點、「により降臨」、讀點前的「エンドフェイズ及び、」)。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c5_leave_and_golden.py
讀 data/action_structure.json。
表一:述語解析不出 且段原文含「離れ」(m2_residue 的「〜から離れた/離れる」類是先中先贏後的 519)。
表二:段原文含「ターンのエンドフェイズ」且段解析不出(任何原因)。
表三:段原文含「降臨」且段解析不出。
表四:「エンドフェイズ及び」。最後印兩張標準卡目前的反向檢查不通過項。
"""
import collections
import re

from common import all_segments, cards, classify, short

Q = r"「[^」]*」"

LEAVE_RULES = [
    ("R1 「(X)は、フィールドから離れた場合に除外される」(含「場合ゲームから除外される」)", r"離れた場合(に|、)?(ゲームから)?除外され"),
    ("R2 「〜離れた場合に(持ち主の)デッキの一番下に戻る/デッキに戻る」", r"離れた場合(に|、)?.*(戻る|戻す)"),
    ("R3 連動「Xがフィールドから離れた時/場合に(そのモンスター/このカード/装備モンスター)は破壊される」", r"離れ(た|る)(時|場合)(に|、)?.*破壊され"),
    ("R4 條件「Xが(相手の効果で/相手によって)フィールドから離れた場合/時」(帶原因)", r"(効果|によって|相手|戦闘|以外の方法)で?.*離れ(た|る)(場合|時)?$"),
    ("R5 條件「Xがフィールドから離れた場合/時」", r"(フィールド|ゾーン)(上)?から離れ(た|る)(場合|時)?$"),
    ("R6 「墓地/EXデッキから離れた」", r"(墓地|デッキ|除外)から離れ"),
    ("R7 「フィールドから離れ、墓地へ送られた」等串接", r"離れ、"),
]

EP_RULES = [
    ("E1 「Xした/されたターンのエンドフェイズに」(條件子句 + 階段:發動時點)", r"(した|された|成功した|送られた|リバースした)ターンのエンドフェイズ(時)?に"),
    ("E2 「次の(自分)ターンのエンドフェイズ」(延遲)", r"次の(自分の|相手の|自分|相手)?ターンのエンドフェイズ"),
    ("E3 「この/そのターンのエンドフェイズ時まで」(期間)", r"(この|その)ターンのエンドフェイズ(時)?まで"),
    ("E4 「この/そのターンのエンドフェイズ(時)に」(延遲)", r"(この|その)ターンのエンドフェイズ(時)?に"),
    ("E5 「Xしたターンのエンドフェイズ時」(無に,舊式)", r"ターンのエンドフェイズ時"),
]

DESCENT_RULES = [
    ("D1 召喚條件「「X」(儀式魔法カード/カード)により降臨」", r"により降臨"),
    ("D2 「「X」/儀式モンスターの降臨に必要(なレベル分のリリース)」", r"降臨に(必要|使用)"),
    ("D3 「〜は降臨できない」", r"降臨できな"),
]


def table(rows, title):
    by = collections.defaultdict(list)
    for r in rows:
        by[r[4]].append(r)
    print(f"\n{title}: {len(rows)} 段 / {len({r[0] for r in rows})} 張")
    print("| 子型 | 段 | 張 | 累計% | 段類別 | 解析不出原因 | 例 1 | 例 2 |")
    print("|---|---|---|---|---|---|---|---|")
    cum = 0
    for name in sorted(by, key=lambda n: -len(by[n])):
        rs = by[name]
        cum += len(rs)
        kinds = ",".join(f"{k}{n}" for k, n in collections.Counter(r[2]["kind"] for r in rs).most_common())
        reasons = ",".join(f"{k}{n}" for k, n in collections.Counter(r[2]["unparsed"]["reason"] for r in rs).most_common(3))
        ex, seen = [], set()
        for r in rs:
            if r[0] in seen:
                continue
            seen.add(r[0])
            ex.append(f"{r[1]} {r[0]}「{short(r[3], 60)}」")
            if len(ex) == 2:
                break
        print(f"| {name} | {len(rs)} | {len({r[0] for r in rs})} | {cum / len(rows):.1%} | {kinds} | {reasons} | {ex[0]} | {ex[1] if len(ex) > 1 else ''} |")


def main():
    leave, ep, descent, epand = [], [], [], []
    for c in cards():
        for b, s in all_segments(c):
            t = b["text"][s["span"][0]:s["span"][1]]
            u = s["unparsed"]
            if not u:
                continue
            core = re.sub(Q, "「」", re.sub(r"[。、]+$", "", t))
            if "離れ" in t and u["reason"] == "述語解析不出":
                leave.append((c["id"], c["name_ja"], s, t, classify(core, LEAVE_RULES)))
            if "ターンのエンドフェイズ" in t:
                ep.append((c["id"], c["name_ja"], s, t, classify(core, EP_RULES)))
            if "降臨" in t:
                descent.append((c["id"], c["name_ja"], s, t, classify(core, DESCENT_RULES)))
            if "エンドフェイズ及び" in t:
                epand.append((c["id"], c["name_ja"], s, t, "「エンドフェイズ及び、」"))
    table(leave, "表一 述語解析不出且含「離れ」")
    table(ep, "表二 段解析不出且含「ターンのエンドフェイズ」")
    table(descent, "表三 段解析不出且含「降臨」")
    table(epand, "表四 段解析不出且含「エンドフェイズ及び」")
    allep = sum(1 for c in cards() for b, s in all_segments(c)
                if "エンドフェイズ及び" in b["text"][s["span"][0]:s["span"][1]])
    print(f"全庫段含「エンドフェイズ及び」: {allep}")

    from reverse_check import check_card
    print("\n兩張標準卡目前的不通過項:")
    for c in cards():
        if c["id"] in (42149850, 56350972):
            segs = {s["id"]: (b, s) for b, s in all_segments(c)}
            for f in check_card(c):
                bs = segs.get(f["segment"])
                text = bs[0]["text"][bs[1]["span"][0]:bs[1]["span"][1]] if bs else ""
                print(f"  {c['name_ja']} {c['id']} {f['segment']} {f['detail']}「{text}」")


if __name__ == "__main__":
    main()
