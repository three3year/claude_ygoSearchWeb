"""第 1 類:物件修飾解析不出。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c1_object_modifier.py [--full]
讀 data/action_structure.json(load_structures)。物件的條件式裡 op=解析不出 原子的 text 是
`segment_extract.parse_modifiers` 從「第一個認不得的位置」到修飾語結尾的剩餘字面,所以照它的
**開頭**分子型(先中先贏,RULES 順序)。印:每子型物件數 / 張數、只差物件修飾就整張通過的卡裡
「該卡全部修飾解析不出物件都屬此子型」的張數(補這一型就整張通過)、兩個例子。
--full 另印每子型前 40 個字面(寫進 c1_object_modifier_detail.txt)。
"""
import collections
import re
import sys

from common import blocks_by_id, cards, classify, sentence, short, unparsed_atoms

sys.setrecursionlimit(10000)

# 「」裡的字不算(避免卡名裡的が、、誤判)
def _strip_quotes(t):
    return re.sub(r"「[^」]*」", "「」", t)


RULES = [
    # A:物件範圍吞進了前文(不是修飾語本身的問題,是物件/子句切點)
    ("A1 吞進前文:含「、」「：」(標籤、時點、前提、〜ように、〜の中から…)", r"[、：]"),
    ("A2 吞進期間/時點字面(〜まで、エンドフェイズに、〜の間…)",
     r"まで|フェイズ|の間|ダメージ計算|ダメージステップ|ターンに|ターン中|時に|毎に|１度"),
    ("A3 吞進主語「Xが/Xは」(このカードが戦闘で相手、装備モンスターが守備表示…)",
     r"(カード|モンスター|自分|相手|プレイヤー|」)[がは]"),
    ("A4 開頭是助詞/連接詞殘片(に、さらに、または…)", r"^(に|さらに|または|及び|か|と|を|で|もう)"),
    ("A5 物件內含從「〜から」(デッキから、手札・墓地から)", r"から"),
    ("B 修飾此卡「〜このカード」(この効果で特殊召喚した/装備されている/Pゾーンの この)", r"この$"),
    ("C 回指前綴(その〜、対象の、選択した、選んだ、上記の…)",
     r"^(その|それら|それ(?!ぞれ)|対象の|選択した|選んだ|上記|確認した|めくった|墓地へ送った|破壊した|除外した|リリースした|特殊召喚した|この効果で|この方法で)"),
    ("D 與此卡的關係(このカードの装備、このカードに装備、このカードを素材として持っている…)",
     r"^このカード(の|に|を|と)"),
    ("E 除外「他の」「〜以外の」", r"^他の|以外"),
    ("F 連體子句:召喚方式/履歴/狀態(特殊召喚された、除外されている、X召喚した、除外状態の、〜を持つ…)",
     r"(した|された|されている|している|ている|られた|られている|状態|を行う|を持つ|を含む|置かれた|持っている|ない)"),
    ("G 數值比較與合計(攻撃力N以下、ランクN以下、レベルの合計…)",
     r"(攻撃力|守備力|レベル|ランク|リンク|元々の).*?([０-９0-9]|以上|以下|合計|同じ|高い|低い)"),
    ("H 卡名/屬性/等級異同(カード名が異なる、同名、同じ縦列…)", r"同名|カード名|異なる|同じ"),
    ("I 列舉「AまたはB」「A及びB」「AかB」(魔法または罠、永続魔法または永続罠…)",
     r"または|及び|[」族性]か|モンスターか|カードか|自分か"),
    ("J 舊式字段「と名のついた」", r"名のついた|という"),
    ("K 原子後接「の」再接字段/子類型(レベル８の「DDD」)", r"^の"),
    ("L 表示形式(攻撃表示、守備表示、表側表示…)", r"表示|^表側|^裏側"),
    ("M 卡片種類/子類型字面不在閉集(効果、スピリット、魔法・罠・、「X」速攻…)",
     r"^(「」)?(効果|魔法|罠|永続|デュアル|リバース|スピリット|トゥーン|速攻|ユニオン|融合|儀式|通常|チューナー|装備|カウンター|フィールド$|「[^」]*」フィールド$|フィールド魔法|Ｓ|Ｘ|Ｌ|Ｐ|S|X|L|P(?!ゾーン)|A|シンクロ|エクシーズ|リンク|ペンデュラム|ドラゴン族|攻撃$|トークン|モンスター)"),
    ("N 區域/方字面(Pゾーンの、魔法＆罠ゾーンの、リンク先の、自分か相手の…)",
     r"ゾーン|リンク先|デッキ|フィールド|墓地|手札|除外|自分|相手|お互い|EX"),
    ("O 數量/範圍(全ての、のみ…)", r"^全て|のみ|^[０-９]"),
]

# A1 細分(讀點/冒號前那截的寫法)
A1_RULES = [
    ("「：」選項或標籤(自分：、２体以上：、手札：)", r"："),
    ("「〜になるように、」(儀式/合計)", r"ように、"),
    ("期間「〜の発動後、ターン終了時まで」", r"発動後|終了時まで"),
    ("時點「自分・相手ターンに、」「１度、」「〜フェイズに、」", r"ターンに|１度|フェイズ|ターン中|までに|時に"),
    ("容器「〜の中から、」", r"中から"),
    ("前提/條件「〜限り、」「〜場合、」「〜存在し、」", r"限り|場合|存在し|ていれば|以下で"),
    ("「〜に対して、」", r"対して"),
    ("「または、」「さらに、」等連接", r"^(または|さらに|及び)、|^、"),
]


def main(full=False):
    objs = []  # (卡號, 卡名, 物件, 原子字面, 子型)
    for c in cards():
        for o in c["objects"]:
            if (o["unparsed"] or {}).get("reason") != "物件修飾解析不出":
                continue
            atom = next(unparsed_atoms(o["condition"]), None)
            t = atom["text"] if atom else ""
            blk = blocks_by_id(c).get(o["block"])
            sent = sentence(blk["text"], o["span"]) if blk and o["span"] else o["text"]
            objs.append((c["id"], c["name_ja"], o, t, classify(_strip_quotes(t), RULES), sent))
    total_cards = {r[0] for r in objs}
    print(f"物件修飾解析不出 物件: {len(objs)} / 張: {len(total_cards)}")

    # 只差物件修飾就整張通過的卡(用 reverse_check.check_card 實跑)
    from reverse_check import REASON_NO_TEMPLATE, check_card
    only_mod = set()
    for c in cards():
        if c["unparsed"] or c["id"] not in total_cards:
            continue
        fails = check_card(c)
        keys = {f["detail"] if f["reason"] == REASON_NO_TEMPLATE else f["reason"] for f in fails}
        if keys == {"物件無模板:物件修飾解析不出"}:
            only_mod.add(c["id"])
    print(f"只差物件修飾解析不出就整張通過 張: {len(only_mod)}")
    types_of = collections.defaultdict(set)
    for cid, _, _, _, k, _ in objs:
        types_of[cid].add(k)

    by = collections.defaultdict(list)
    for r in objs:
        by[r[4]].append(r)
    names = [n for n, _ in RULES] + ["其他"]
    cum = 0
    print()
    print("| 子型 | 物件 | 張 | 累計物件% | 補這一型就整張通過(張) | 例 1 | 例 2 |")
    print("|---|---|---|---|---|---|---|")
    for n in sorted(names, key=lambda n: -len(by[n])):
        rows = by[n]
        if not rows:
            continue
        cum += len(rows)
        cids = {r[0] for r in rows}
        unlock = sum(1 for cid in only_mod if types_of[cid] == {n})
        ex = []
        seen = set()
        for r in rows:
            if r[0] in seen:
                continue
            seen.add(r[0])
            ex.append(f"{r[1]} {r[0]}「{short(r[5], 80)}」(物件「{short(r[2]['text'], 30)}」,卡住:{short(r[3], 20)})")
            if len(ex) == 2:
                break
        print(f"| {n} | {len(rows)} | {len(cids)} | {cum / len(objs):.1%} | {unlock} | {ex[0]} | {ex[1] if len(ex) > 1 else ''} |")
    multi = sum(1 for cid in only_mod if len(types_of[cid]) > 1)
    print(f"\n只差物件修飾的卡裡跨兩個以上子型: {multi} 張")
    a_total = sum(len(rows) for n, rows in by.items() if n.startswith("A"))
    a_unlock = sum(1 for cid in only_mod if all(k.startswith("A") for k in types_of[cid]))
    print(f"A 類合計(物件範圍問題,非修飾語本身): {a_total} 物件 / "
          f"{len({r[0] for n, rows in by.items() if n.startswith('A') for r in rows})} 張;"
          f"補完 A 類就整張通過 {a_unlock} 張")

    a1 = [r for r in objs if r[4].startswith("A1")]
    sub = collections.Counter(classify(_strip_quotes(r[3]), A1_RULES) for r in a1)
    print("\nA1 細分(物件數):")
    for k, n in sub.most_common():
        print(f"  {n}\t{k}")

    if full:
        for n in names:
            cnt = collections.Counter(r[3] for r in by[n])
            print(f"\n## {n}:{len(by[n])} 物件,相異字面 {len(cnt)}")
            for t, k in cnt.most_common(40):
                print(f"  {k}\t{t}")


if __name__ == "__main__":
    main("--full" in sys.argv)
