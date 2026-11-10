"""第 6 類:前提的數量與列舉(m2_residue「存在(しない)場合」類,903 段)。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c6_premise_count_enum.py
讀 data/action_structure.json。母體照 m2_residue.py 重現:述語解析不出、段原文(去尾「。、」)不中它排在
前面的 11 類、且含 存在(する|しない)(場合|時)。
先分兩群:原述語字面(seg["predicate"])已不含「存在」= 前提已剝成、卡在後半(不是前提的問題);
仍含「存在」= 前提沒剝成,再照寫法分子型(先中先贏,看原述語字面裡含「存在」的那截)。
"""
import collections
import re

from common import all_segments, cards, classify, short

Q = r"「[^」]*」"
# m2_residue.py CATEGORIES 排在「存在(しない)場合」之前的 11 類(先中先贏)
EARLIER = [r"素材(と|に)(する|し|して|している)", r"に成功(した|する)", r"を得る|を得て|を得た",
           r"適用(する|できる|し)", r"として扱|扱いとな", r"なければならない|ならず", r"攻撃宣言",
           r"離れ", r"装備可能|降臨", r"(され|られ)た(場合|時)", r"(し|っ|い|け|せ|べ|め)た(場合|時)"]
P = r"存在(する|しない)(場合|時)"

RULES = [
    ("P1 兩個前提以連用形串接「Aが存在し/存在せず、Bが存在(しない)場合」(含「LPが少なく、」)",
     r"存在(し|せず)、.*存在|(少なく|多く|なく|以下で|以上で)、.*存在"),
    ("P8 前提的或「〜場合、または〜場合」", r"場合、?または|^または"),
    ("P2 數量「Xが２体以上/３枚以上/２種類以上/のみ 存在する」", r"[０-９0-9]+(体|枚|種類|つ|ヵ所|個)(以上|以下|のみ|だけ)?(が)?(表側表示で)?存在|以上存在"),
    ("P3 物件列舉「A及びB」「AとB」「AかB」「「A」「B」「C」のいずれか」", r"及び|」と「|モンスターと|」か「|モンスターか|カードか|」「|いずれか|または「|」または"),
    ("P4 區域不在閉集(Pゾーン、フィールドゾーン、魔法＆罠ゾーン、メインモンスターゾーン、同じ縦列、または列舉的區域)",
     r"Pゾーン|フィールドゾーン|魔法＆罠|お互いのフィールド|エクストラデッキ|EXデッキ|正面|メインモンスターゾーン|EXモンスターゾーン|縦列|リンク先|墓地または|または墓地|フィールドまたは|手札・|・墓地|・フィールド"),
    ("P5 「Xにのみ」「〜のみが存在」", r"のみ"),
    ("P6 前提後接「に」不帶讀點/後接動作(〜存在しない場合に特殊召喚できる)", r"存在(する|しない)(場合|時)に"),
    ("P7 前提前有主題或別的子句(この効果は〜、〜効果を〜場合、効果処理として、)", r"^(この効果は|.*効果を|.*は、|.*として、)"),
    ("P11 前面是「自分・相手ターンに、」(回合方任一方不在遊戲狀態閉集)", r"^自分・相手ターンに"),
    ("P12 「自分フィールドのモンスターが、存在しない」(區域寫成修飾、讀點在中間)", r"が、存在"),
    ("P9 沒寫區域「フィールド魔法カードが表側表示で存在する場合」", r"^[^に]*が(表側表示で|表側守備表示で|裏側表示で)?存在"),
    ("P10 表示形式寫在區域前「表側守備表示でフィールド上に存在」", r"表示でフィールド|表示で(自分|相手)?の?(フィールド|モンスターゾーン)"),
]

AFTER_RULES = [
    ("後半含單獨「召喚」(召喚・特殊召喚できない…)", r"(?<![殊式合SXLP])召喚"),
    ("後半是抗性/限制(できない/されない/受けない)", r"(できない|されない|受けない)$"),
    ("後半是「〜事ができる」", r"事(が|も)できる$"),
    ("後半是「〜扱い/として」", r"扱|として"),
]


def main():
    rows = []
    for c in cards():
        for b, s in all_segments(c):
            if (s["unparsed"] or {}).get("reason") != "述語解析不出":
                continue
            t = b["text"][s["span"][0]:s["span"][1]]
            core = re.sub(r"[。、]+$", "", t)
            if any(re.search(p, core) for p in EARLIER) or not re.search(P, core):
                continue
            pred = re.sub(Q, "「」", s["predicate"] or "")
            if "存在" not in pred:
                name = "Q 前提已剝成、卡在後半:" + classify(pred, AFTER_RULES)
            else:
                name = classify(re.sub(Q, "「」", core), RULES)
            rows.append((c["id"], c["name_ja"], s, t, name))
    print(f"母體: {len(rows)} 段 / {len({r[0] for r in rows})} 張")
    stripped = [r for r in rows if r[4].startswith("Q")]
    print(f"前提已剝成(原述語字面不含「存在」): {len(stripped)} 段;前提沒剝成: {len(rows) - len(stripped)} 段")
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
    print("\n「其他」(前提沒剝成)前 30 段原文:")
    for r in by.get("其他", [])[:30]:
        print(f"  {r[0]} {short(r[3], 80)}")


if __name__ == "__main__":
    main()
