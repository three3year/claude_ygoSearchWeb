"""第 6 類的收尾統計(m3 票 12):新寫法的前提用了多少段、還沒剝成的前提依寫法計數。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c6b_premise_new_forms.py
讀 data/action_structure.json(要看「改後」就先就地重建產物,跑完用 git checkout 還原)。
1. 全庫各段的前提裡用到票 12 新寫法的段數,與其中那一段寫回原文相符的段數(一段用到幾種各算一次)。
2. `c6_premise_count_enum.py` 的母體裡前提沒剝成的段(原述語字面仍含「存在」),依寫法先中先贏計數。
"""
import collections
import re

import c6_premise_count_enum as c6
from common import all_segments, cards

from reverse_check import check_card  # noqa: E402  (common 已把 script/action_structure 放進 sys.path)

LEFTOVER_RULES = [
    ("「自分・相手ターンに、」開頭或夾在前面(回合方任一方不在遊戲狀態閉集)", r"自分・相手ターンに"),
    ("相對位置:もう片方の自分のPゾーン", r"もう片方"),
    ("相對位置:リンク先、縦列、正面、隣のゾーン", r"リンク先|縦列|正面|隣"),
    ("「Xが、存在しない場合」(區域寫成物件修飾、讀點在中間),含後接「または〜のみの場合」", r"が、存在"),
    ("「〜のみ」(にのみ存在、場合のみ、時のみ、〜のみの場合)", r"のみ"),
    ("主題在前(「この効果は〜場合に発動と処理ができる」「このカードは〜場合」「この効果でセットしたカードは、〜場合には」)",
     r"^(この効果|このカードは|このモンスターは)"),
    ("「〜場合には発動できない」", r"場合には"),
    ("並列卡名「A」「B」「C」(のいずれか/全て/沒有標記)", r"」「|」、「"),
    ("名詞短語與卡名混合、或帶讀點的列舉(「X」モンスターか「Y」、「〜以外の、AかB」)、後一個前提省略區域的「または」",
     r"または|モンスターか|カードか|」か"),
    ("「合計N」「〜の内N種類以上」「いずれも」「全て」「それぞれ」(物件帶と/及び)", r"合計|の内|いずれも|全て|それぞれ"),
    ("區域的寫法不在規則裡(「〜及び〜に」「お互いの〜」「自分または相手の〜」「〜（表側）」「そのゾーン」)",
     r"及び|お互い|自分または相手|（表側|そのゾーン|と自分の"),
    ("「〜しか存在しない」", r"しか存在"),
    ("表示形式寫在區域前(「表側守備表示でフィールド上に存在」「表側表示でモンスターが存在」)",
     r"表示で(フィールド|自分|相手|モンスター|カード|「)"),
    ("承前省略的「存在する場合」「存在しない場合」(不在分歧引導句)", r"^存在(する|しない)場合"),
    ("沒寫區域也沒寫表示形式(「対象のモンスターが存在しない場合」「S召喚したこのカードが存在する場合」)",
     r"^[^に、]*が([０-９]+[体枚]以上)?存在"),
    ("前面有別的時點或子句(「自分のスタンバイフェイズ時に」「〜の発動時に」「〜を確認し、」「相手ターンに１度、」)",
     r"フェイズ時に|発動時に|開始時に|確認し、|ターンに１度、|メインフェイズで|バトルフェイズに|効果処理として"),
    ("物件含「が」(攻撃力が一番高い、元々の持ち主が〜)", r"[^、]*が[^、]*が"),
    ("區域後有讀點(「自分フィールドに、モンスターが存在しない場合」)", r"に、"),
]
OTHER = "其他(前提的寫法認得,物件修飾解析不出或長尾)"


def premise_atoms(premise):
    """前提條件式裡的原子(且、非展開;前提的或本身也算一個)。"""
    if not premise:
        return
    if premise.get("op") == "或":
        yield premise
    if premise.get("op") in ("且", "或"):
        for arg in premise.get("args", ()):
            yield from premise_atoms(arg)
    elif premise.get("op") == "非":
        yield from premise_atoms(premise["arg"])
    else:
        yield premise


def new_forms(atom, objects):
    """一個前提原子用到的票 12 新寫法。"""
    form = (atom.get("form") or "").rstrip("、")
    if atom.get("op") == "或":
        if atom.get("form") == "または":
            yield "「〜場合、または〜場合」(前提的或)"
        return
    if atom.get("state") == "LP比較":
        yield "LP 比較"
    if atom.get("op") not in ("位置", "存在"):
        return
    if form in ("し", "せず"):
        yield "連用形「存在し、/存在せず、」"
    if form in ("場合に", "時に"):
        yield "「場合に」「時に」後面直接接子句"
    if form in ("及び", "と"):
        yield "列舉「A及びB」「AとB」(且)"
    if atom.get("any"):
        yield "「〜のいずれか」(或)"
    if atom.get("each"):
        yield "「それぞれ存在」(每種各一)"
    if atom.get("inferred"):
        yield "沒寫區域、預設場上"
    count = objects[atom["object"]].get("count") or {}
    if count.get("placement") == "存在前":
        yield "數量(單位 種類)" if count["unit"] == "種類" else "數量(体/枚/つ)"
    if "または" in (atom.get("text") or ""):
        yield "區域的或「AまたはBに」"


def main():
    used, passed = collections.Counter(), collections.Counter()
    leftover, examples = collections.Counter(), {}
    for card in cards():
        objects = {o["id"]: o for o in card["objects"]}
        failed = None
        for block, seg in all_segments(card):
            forms = {f for atom in premise_atoms(seg["premise"]) for f in new_forms(atom, objects)}
            if forms:
                if failed is None:
                    failed = {(f["block"], f["segment"]) for f in check_card(card)}
                for form in forms:
                    used[form] += 1
                    passed[form] += (block["id"], seg["id"]) not in failed
            if (seg["unparsed"] or {}).get("reason") != "述語解析不出":
                continue
            text = block["text"][seg["span"][0]:seg["span"][1]]
            core = re.sub(r"[。、]+$", "", text)
            if (any(re.search(p, core) for p in c6.EARLIER) or not re.search(c6.P, core)
                    or "存在" not in (seg["predicate"] or "")):
                continue
            name = next((n for n, p in LEFTOVER_RULES if re.search(p, core)), OTHER)
            leftover[name] += 1
            examples.setdefault(name, f"{card['name_ja']} {card['id']}")
    print("| 新寫法 | 段 | 那一段寫回原文相符 |")
    print("|---|---|---|")
    for form, n in used.most_common():
        print(f"| {form} | {n} | {passed[form]} |")
    print(f"\n前提沒剝成: {sum(leftover.values())} 段")
    print("| 寫法 | 段 | 例 |")
    print("|---|---|---|")
    for name, n in leftover.most_common():
        print(f"| {name} | {n} | {examples[name]} |")


if __name__ == "__main__":
    main()
