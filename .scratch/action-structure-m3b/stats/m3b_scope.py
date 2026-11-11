"""m3b 規格的範圍統計:各項寫法在現在的產物裡有幾段、幾個物件。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3b/stats/m3b_scope.py
只讀 data/action_structure.json 與 data/cards.json;共用 m3 的 stats/common.py。
輸出存成同目錄的 m3b_scope.txt。
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "action-structure-m3", "stats"))

from common import ROOT, all_segments, cards, seg_text  # noqa: E402

SUMMONS = {"召喚", "上級召喚", "通常召喚", "反轉召喚", "特殊召喚", "P召喚", "融合召喚", "儀式召喚", "S召喚", "X召喚", "L召喚"}
MOVERS = {"解放", "除外", "送墓", "捨棄", "返回", "破壞"}
NO_TARGET_ZONES = {"牌組", "手牌", "額外牌組"}


def reason(seg):
    u = seg.get("unparsed")
    return u.get("reason") if u else None


def objects(card):
    out = {}

    def collect(o):
        if isinstance(o, dict):
            if "id" in o and "source" in o and "condition" in o:
                out[o["id"]] = o
            for v in o.values():
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)

    collect(card)
    return out


def atoms(cond, op):
    if isinstance(cond, dict):
        if cond.get("op") == op:
            yield cond
        for v in cond.values():
            yield from atoms(v, op)
    elif isinstance(cond, list):
        for v in cond:
            yield from atoms(v, op)


def has_unparsed(cond):
    return any(True for _ in atoms(cond, "解析不出"))


def card_text(card):
    return "".join(b.get("text") or "" for b in card["blocks"])


class Tally:

    def __init__(self, name):
        self.name = name
        self.parsed = 0
        self.unparsed = 0
        self.ids = set()
        self.unparsed_ids = set()
        self.reasons = collections.Counter()
        self.example = None

    def add(self, card, seg, text):
        self.ids.add(card["id"])
        r = reason(seg)
        if r:
            self.unparsed += 1
            self.unparsed_ids.add(card["id"])
            self.reasons[r] += 1
            if self.example is None:
                self.example = f"{card['id']} {card['name_ja']}「{text[:60]}」"
        else:
            self.parsed += 1

    def show(self):
        print(f"{self.name}: {self.parsed + self.unparsed} 段 / {len(self.ids)} 張;"
              f"解析出 {self.parsed}、解析不出 {self.unparsed} 段 / {len(self.unparsed_ids)} 張")
        if self.reasons:
            print("  原因:" + "、".join(f"{k} {v}" for k, v in self.reasons.most_common()))
        if self.example:
            print("  例:" + self.example)


SEGMENT_PATTERNS = [
    ("「自分・相手ターンに」", r"自分・相手ターンに"),
    ("「自分・相手ターンに、」", r"自分・相手ターンに、"),
    ("「自分・相手ターンに１度、」", r"自分・相手ターンに１度、"),
    ("「リバース：」", r"リバース："),
    ("「リバースした/する/し、」", r"リバース(した|する|し、)"),
    ("「召喚・リバース」", r"召喚・リバース"),
    ("「され/られ墓地へ送られ」", r"(され|られ)墓地へ送られ"),
    ("「取り除けない」", r"取り除けない"),
    ("「このカードに(１体のみ)装備」", r"このカードに(１体のみ)?装備(する|できる|し、|して)"),
]


def main():
    tallies = [(Tally(name), re.compile(pat)) for name, pat in SEGMENT_PATTERNS]
    no_to = Tally("原因 表示形式沒有到")
    chains = collections.Counter()
    chain_example = {}
    pick_te = 0
    pick_te_ids = set()
    obj_counts = collections.Counter()
    equipped_on = 0
    equippee_non_monster = 0
    same_no_ref = same_no_ref_one = 0
    same_one_ids = set()
    same_one_examples = []

    for card in cards():
        for blk, seg in all_segments(card):
            text = seg_text(blk, seg)
            for tally, pat in tallies:
                if pat.search(text):
                    tally.add(card, seg, text)
            if reason(seg) == "表示形式沒有到":
                no_to.add(card, seg, text)
            actions = seg.get("actions") or []
            if not reason(seg) and len(actions) >= 2 and actions[-1] in SUMMONS:
                left = [a for a in actions if a not in SUMMONS]
                if left:
                    key = (tuple(left), actions[-1])
                    chains[key] += 1
                    chain_example.setdefault(key, f"{card['id']} {card['name_ja']}「{text[:50]}」")
            if "選択して" in text and not reason(seg):
                for line in seg.get("lines") or []:
                    zones = {z["zone"] for z in ((line.get("from") or {}).get("zones") or [])}
                    if line.get("targeting") and zones & NO_TARGET_ZONES:
                        pick_te += 1
                        pick_te_ids.add(card["id"])
        for obj in objects(card).values():
            text = obj.get("text") or ""
            cond = obj.get("condition")
            state = "解析不出" if has_unparsed(cond) else "解析出"
            if "装備魔法カード" in text:
                obj_counts[("「装備魔法カード」", state)] += 1
            elif "装備カード" in text:
                obj_counts[("「装備カード」", state)] += 1
            equipped_on += sum(1 for _ in atoms(cond, "裝備中"))
            if "装備モンスター" not in text:
                equippee_non_monster += sum(1 for a in atoms(cond, "被裝備者") if a.get("text") == "装備")
            for atom in atoms(cond, "異同"):
                if "ref" in atom:
                    continue
                same_no_ref += 1
                count = obj.get("count") or {}
                if count.get("value") == 1 and count.get("cmp") == "=":
                    same_no_ref_one += 1
                    same_one_ids.add(card["id"])
                    if len(same_one_examples) < 20:
                        same_one_examples.append(f"{card['id']} {card['name_ja']}「{text}」")

    print("## 段的寫法")
    for tally, _ in tallies:
        tally.show()
    no_to.show()

    print("\n## て形串接:解析出、兩個以上動作詞、最後一個是召喚系、左邊有非召喚系的段")
    for (left, right), n in sorted(chains.items(), key=lambda kv: -kv[1]):
        kind = "移走" if set(left) <= MOVERS else "不移走"
        print(f"{'+'.join(left)} + {right}: {n} 段({kind})  例:{chain_example[(left, right)]}")
    print("左半全是移走的動作詞:", sum(n for (left, _), n in chains.items() if set(left) <= MOVERS), "段")

    print("\n## 選択して:解析出、對象線標取對象、明寫的出發地含牌組/手牌/額外牌組")
    print(f"{pick_te} 條線 / {len(pick_te_ids)} 張")

    print("\n## 物件字面含「装備」")
    for key in sorted(obj_counts):
        print(f"{key[0]} {key[1]}: {obj_counts[key]} 個")
    print("條件式原子 裝備中:", equipped_on, "個")
    print("條件式原子 被裝備者(字面「装備」、物件字面不含「装備モンスター」):", equippee_non_monster, "個")

    print("\n## 異同原子沒寫比較對象")
    print(f"全部 {same_no_ref} 個;物件數量恰好一張的 {same_no_ref_one} 個 / {len(same_one_ids)} 張")
    for line in same_one_examples:
        print("  " + line)

    print("\n## 指定卡有沒有可能成為裝備卡(卡片總表的 type 位元;官方日文取自區塊原文)")
    with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
        types = {c["id"]: c["type"] for c in json.load(f)}
    kinds = collections.Counter()
    for card in cards():
        t = types.get(card["id"], 0)
        if t & 0x1:
            kind = "怪獸"
        elif t & 0x2:
            kind = "魔法(子類型 裝備)" if t & 0x40000 else "魔法(非裝備)"
        elif t & 0x4:
            kind = "陷阱"
        else:
            kind = "其他"
        kinds[kind] += 1
        if "装備" in card_text(card):
            kinds[kind + ",官方日文含「装備」"] += 1
    for key in sorted(kinds):
        print(f"{key}: {kinds[key]} 張")


if __name__ == "__main__":
    main()
