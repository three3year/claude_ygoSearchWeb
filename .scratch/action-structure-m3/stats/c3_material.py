"""第 3 類:「X素材とする/としている」與「〜を融合素材とし、」切開後的左半。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c3_material.py
讀 data/action_structure.json。母體同 m2_residue.py 的「X素材とする/としている/融合素材とし」類:
述語解析不出 且段原文(去尾「。、」)含 素材(と|に)(する|し|して|している)。子型照段原文(「」內換成「」)
先中先贏。另印:段原文以「素材とし」收尾的左半(m2 split_classes 第 3 類)處數與右半狀態。
"""
import collections
import re

from common import all_segments, cards, classify, short

P = re.compile(r"素材(と|に)(する|し|して|している)")

RULES = [
    ("M1 左半「〜を融合素材とし、」(多子句切開,右半是融合召喚)", r"素材とし$"),
    ("M2 疊放「Xを(Yの下に)重ねてX素材とする」", r"重ねて"),
    ("M3 附加「XをYのX素材とする/にする」(效果把卡變成超量素材)", r"(の|その)(X|エクシーズ)素材(と|に)する$|を(全て)?(この|その)?(カードの)?(X|エクシーズ)素材(と|に)する"),
    ("M4 狀態「Xが「Y」/YをX素材としている(場合/限り)」", r"素材としている"),
    ("M5 原因「〜の(S/L/X/融合)素材として墓地へ送られた/除外された」", r"素材として(墓地|除外|リリース|フィールド|手札)"),
    ("M6 條件「(このカードを)〜素材とする場合」(素材限制/作為素材時)", r"素材とする場合"),
    ("M7 許可「〜も(融合)素材とする事ができる/にできる」", r"素材(と|に)(する|して)?事(が|も)でき|素材にできる|素材として使用"),
    ("M8 連體「〜を素材としたXモンスター」「素材とした数」", r"素材とした"),
    ("M10 「〜を素材として(このカードが)〜召喚(に成功)した」(素材寫在召喚條件段)", r"素材として.*召喚"),
    ("M9 「〜召喚の素材とする」「〜の素材とし」(召喚手續)", r"召喚の素材"),
]


def main():
    rows = []
    for c in cards():
        for b, s in all_segments(c):
            t = b["text"][s["span"][0]:s["span"][1]]
            if (s["unparsed"] or {}).get("reason") != "述語解析不出":
                continue
            core = re.sub(r"[。、]+$", "", t)
            if not P.search(core):
                continue
            rows.append((c["id"], c["name_ja"], s, t, classify(re.sub(r"「[^」]*」", "「」", core), RULES)))
    print(f"述語解析不出且含 素材(と|に)(する|し|して|している): {len(rows)} 段 / {len({r[0] for r in rows})} 張")
    print("段類別:", dict(collections.Counter(r[2]["kind"] for r in rows).most_common()))
    by = collections.defaultdict(list)
    for r in rows:
        by[r[4]].append(r)
    cum = 0
    print("| 子型 | 段 | 張 | 累計% | 段類別 | 例 1 | 例 2 |")
    print("|---|---|---|---|---|---|---|")
    for name in sorted(by, key=lambda n: -len(by[n])):
        rs = by[name]
        cum += len(rs)
        kinds = ",".join(f"{k}{n}" for k, n in collections.Counter(r[2]["kind"] for r in rs).most_common())
        ex, seen = [], set()
        for r in rs:
            if r[0] in seen:
                continue
            seen.add(r[0])
            ex.append(f"{r[1]} {r[0]}「{short(r[3], 60)}」")
            if len(ex) == 2:
                break
        print(f"| {name} | {len(rs)} | {len({r[0] for r in rs})} | {cum / len(rows):.1%} | {kinds} | {ex[0]} | {ex[1] if len(ex) > 1 else ''} |")

    print("\n其他 的段原文:")
    for r in by.get("其他", [])[:40]:
        print(f"  {r[0]} {short(r[3], 70)}")

    # 多子句切開的左半「〜素材とし、」(同 m2 split_classes.py 第 3 類,只看頂層區塊的相鄰段)
    left, right = collections.Counter(), collections.Counter()
    for c in cards():
        for b in c["blocks"]:
            segs = b["segments"]
            for i, s in enumerate(segs):
                t = b["text"][s["span"][0]:s["span"][1]].rstrip("、")
                if not re.search("素材とし$", t):
                    continue
                left["解析不出:" + s["unparsed"]["reason"] if s["unparsed"] else "解析出"] += 1
                nxt = segs[i + 1] if i + 1 < len(segs) else None
                right["無" if not nxt else ("解析不出:" + nxt["unparsed"]["reason"] if nxt["unparsed"] else "解析出")] += 1
                right["右半動作 " + ",".join(nxt["actions"]) if nxt and nxt["actions"] else "右半動作 無"] += 0
    print(f"\n左半以「素材とし」收尾(頂層區塊): {sum(left.values())} 處;左半 {dict(left)};右半 {dict((k, v) for k, v in right.items() if v)}")


if __name__ == "__main__":
    main()
