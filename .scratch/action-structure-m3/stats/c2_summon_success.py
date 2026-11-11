"""第 2 類:「召喚」動作詞與「〜に成功した」語尾。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c2_summon_success.py
讀 data/action_structure.json。
表一:段原文含「に成功」且 述語解析不出 的段,依原述語字面(seg["predicate"])分子型(先中先贏)。
     注意:「に成功した」已在語尾表(synonyms,被動),「特殊召喚に成功した」單獨已解析得出;
     這裡解析不出的是動作詞或句中別的寫法。
表二:不含「に成功」、原述語字面含單獨「召喚」(前面不是 特殊/儀式/融合/S/X/L/P/通常/反転/リンク…)
     且 述語解析不出 的段(補「召喚」動作詞會一起動到的)。
另印:含「に成功」的段各解析狀態。
"""
import collections
import re

from common import all_segments, cards, classify, short

Q = r"「[^」]*」"

SUCCESS_RULES = [
    ("S1 列舉含「召喚」:召喚・特殊召喚/召喚・反転召喚(・特殊召喚)に成功", r"召喚・"),
    ("S2 「Xの(特殊)召喚に成功」:物件後接「の」", r"の(特殊)?召喚に成功"),
    ("S3 原因「この方法で/この効果で/〜によって/〜の効果で」+ 特殊召喚に成功", r"(で|によって|により)(特殊)?召喚に成功"),
    ("S4 單獨「召喚に成功」(通常召喚)", r"(^|[をがは])召喚に成功"),
    ("S5 「アドバンス召喚/生け贄召喚に成功」", r"(アドバンス|生け贄)召喚に成功"),
    ("S6 「反転召喚に成功」", r"反転召喚に成功"),
    ("S7 片假名/字母召喚種類:リンク/シンクロ/エクシーズ/P/ペンデュラム召喚に成功", r"(リンク|シンクロ|エクシーズ|ペンデュラム|P|Ｐ)召喚に成功"),
    ("S8 「素材として〜召喚に成功」", r"素材"),
    ("S9 其他「〜召喚に成功」(字幹已認、卡在別處)", r"召喚に成功"),
]

BARE = re.compile(r"(?<![殊式合ＳＸＬSXLPＰ常ス転ク贄ーA])召喚")
BARE_RULES = [
    ("T1 「召喚・特殊召喚した/された/する/できない」等列舉", r"召喚・"),
    ("T2 「召喚できる/する」(召喚手續・效果)", r"召喚(できる|する|でき)"),
    ("T3 「召喚した/された」", r"召喚(した|された|されている)"),
    ("T4 「〜召喚に使用/の素材」", r"召喚(に|の素材)"),
]


def main():
    status = collections.Counter()
    rows, bare_rows = [], []
    for c in cards():
        for b, s in all_segments(c):
            t = b["text"][s["span"][0]:s["span"][1]]
            reason = (s["unparsed"] or {}).get("reason")
            if "に成功" in t:
                status[reason or "解析出"] += 1
                if reason == "述語解析不出":
                    pred = re.sub(Q, "「」", s["predicate"] or t)
                    rows.append((c["id"], c["name_ja"], s, t, classify(pred, SUCCESS_RULES)))
            elif reason == "述語解析不出" and BARE.search(s["predicate"] or ""):
                pred = re.sub(Q, "「」", s["predicate"])
                bare_rows.append((c["id"], c["name_ja"], s, t, classify(pred, BARE_RULES)))

    print("含「に成功」的段 解析狀態:", dict(status.most_common()))
    print(f"含「に成功」且述語解析不出: {len(rows)} 段 / {len({r[0] for r in rows})} 張")
    print("段類別:", dict(collections.Counter(r[2]['kind'] for r in rows).most_common()))
    trig = collections.Counter()
    for r in rows:
        m = re.search(r"に成功(?:した|する)(時|場合|ターン|際)?", r[3])
        trig[m.group(1) if m else None] += 1
    print("觸發形:", dict(trig.most_common()))
    _table(rows, SUCCESS_RULES)

    print(f"\n表二:不含「に成功」、原述語字面含單獨「召喚」且述語解析不出: {len(bare_rows)} 段 / "
          f"{len({r[0] for r in bare_rows})} 張")
    _table(bare_rows, BARE_RULES)

    print("\n表一各子型的原述語字面前 8(「」換成「」):")
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r[4]][re.sub(Q, "「」", r[2]["predicate"] or "")] += 1
    for k in sorted(by):
        print(f"  {k}: " + ";".join(f"{p}×{n}" for p, n in by[k].most_common(8)))


def _table(rows, rules):
    by = collections.defaultdict(list)
    for r in rows:
        by[r[4]].append(r)
    cum = 0
    print("| 子型 | 段 | 張 | 累計% | 例 1 | 例 2 |")
    print("|---|---|---|---|---|---|")
    for name in sorted(by, key=lambda n: -len(by[n])):
        rs = by[name]
        cum += len(rs)
        ex, seen = [], set()
        for r in rs:
            if r[0] in seen:
                continue
            seen.add(r[0])
            ex.append(f"{r[1]} {r[0]}「{short(r[3], 60)}」")
            if len(ex) == 2:
                break
        print(f"| {name} | {len(rs)} | {len({r[0] for r in rs})} | {cum / len(rows):.1%} | "
              f"{ex[0]} | {ex[1] if len(ex) > 1 else ''} |")


if __name__ == "__main__":
    main()
