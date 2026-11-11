"""票 13:各票點名要在全部票合入後重查的事(讀 <repo 根> 的產物,用同一個根的程式)。
跑法:python -X utf8 .scratch/action-structure-m3/stats/m3_rechecks.py <repo 根>
  後 = repo 根本身;要看里程碑二的狀態,把 git archive 834f518 解出來的資料夾當 <repo 根>(不認得的動作詞印「不認得」)。
印三節:
1. 逐卡的查詢:那張卡落在命中組、經引用組、未解析組,還是都不在;在未解析組時附列出的段與原因。
2. 取對象的錯標(票 07):那張卡每一條標取對象的對象線所在的段、段的狀態。
3. 「Xをリリースして(アドバンス)召喚できる」(票 08 記的已知不對):段的動作詞同時有 解放 與 召喚/上級召喚、
   且有一條不是此卡的線標 被召喚(被解放的怪獸被標成被召喚);印段數、解析出、通過反向檢查的段數與卡號。
各卡整張還卡在哪,見 m3_golden_check.py。輸出決定性:順序固定、不印時間。
"""
import json
import os
import sys

ROOT = sys.argv[1]
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from action_query import run_query  # noqa: E402
from card_structure import load_structures  # noqa: E402
from reverse_check import check_card  # noqa: E402
from structure_shape import iter_segments  # noqa: E402
import synonyms  # noqa: E402

KNOWN = ({action for _, action, _ in synonyms.PREDICATE_STEMS}
         | set(synonyms.ACTION_PARENT) | set(synonyms.ACTION_PARENT.values()))

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    cards = load_structures(f.read())
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    card_list = json.load(f)
by_id = {c["id"]: c for c in cards}

# (出處, 卡號, 查詢說明, 查詢)
CARD_QUERIES = (
    ("票 09", 1688285, "成為超量素材", dict(actions=["成為超量素材"])),
    ("票 09", 1688285, "作為素材", dict(actions=["作為素材"])),
    ("票 09", 1735088, "成為超量素材", dict(actions=["成為超量素材"])),
    ("票 09", 7511613, "成為超量素材", dict(actions=["成為超量素材"])),
    ("票 07", 75043725, "加入手牌,只看取對象", dict(actions=["加入手牌"], targeting=True)),
    ("票 07", 75043725, "加入手牌", dict(actions=["加入手牌"])),
    ("票 07", 23927567, "加入手牌,只看取對象", dict(actions=["加入手牌"], targeting=True)),
    ("票 07", 34236961, "送墓,只看取對象", dict(actions=["送墓"], targeting=True)),
    ("票 10", 75198893, "除外", dict(actions=["除外"])),
    ("票 10", 75198893, "除外,開代替", dict(actions=["除外"], replacement=True)),
    ("票 10", 94079037, "除外", dict(actions=["除外"])),
    ("票 10", 94079037, "除外,開代替", dict(actions=["除外"], replacement=True)),
    ("票 10", 96930127, "除外", dict(actions=["除外"])),
    ("票 10", 96930127, "除外,開代替", dict(actions=["除外"], replacement=True)),
    ("票 12", 59374259, "除外,開代替", dict(actions=["除外"], replacement=True)),
    ("票 12", 90290572, "加入手牌,開代替", dict(actions=["加入手牌"], replacement=True)),
    ("票 12", 57111661, "特殊召喚,開代替", dict(actions=["特殊召喚"], replacement=True)),
    ("票 12", 82970905, "特殊召喚,開代替", dict(actions=["特殊召喚"], replacement=True)),
    ("票 04", 674561, "加入手牌", dict(actions=["加入手牌"])),
)


def short(text, n=60):
    text = (text or "").replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"


print("1. 逐卡的查詢:")
results = {}
for source, cid, label, query in CARD_QUERIES:
    name = by_id[cid]["name_ja"]
    if not set(query["actions"]) <= KNOWN:
        print(f"  {source} {cid} {name} 查「{label}」: 不認得")
        continue
    key = json.dumps(query, sort_keys=True, ensure_ascii=False)
    if key not in results:
        results[key] = run_query(cards, card_list, query)
    result = results[key]
    groups = result["groups"]
    where = next((g for g in ("全部", "經引用", "未解析") if cid in groups.get(g, ())), None)
    print(f"  {source} {cid} {name} 查「{label}」: "
          f"{ {'全部': '命中', '經引用': '經引用', '未解析': '未解析組', None: '不命中、也不在未解析組'}[where] }")
    if where == "未解析":
        entry = next(u for u in result["unparsed"] if u["id"] == cid)
        for seg in entry["segments"]:
            print(f"      - {seg['reason']}:{short(seg['text'])}")

print("\n2. 取對象的錯標(票 07):")
for cid in (23927567, 34236961):
    card = by_id[cid]
    print(f"  {cid} {card['name_ja']}")
    found = False
    for block in card["blocks"]:
        for _, seg in iter_segments(block):
            if any(line.get("targeting") for line in seg["lines"]):
                found = True
                state = seg["unparsed"]["reason"] if seg["unparsed"] else "解析出"
                print(f"      - 標取對象的段({state};動作詞 {'、'.join(seg['actions']) or '無'}):{short(seg['text'])}")
    if not found:
        print("      - 沒有標取對象的對象線")

print("\n3. 被解放的怪獸標成被召喚(票 08):")
SUMMON = {"召喚", "上級召喚"}
rows = []
for card in cards:
    if card["unparsed"]:
        continue
    objects = {o["id"]: o for o in card["objects"]}
    failed = None
    for block in card["blocks"]:
        for b, seg in iter_segments(block):
            actions = set(seg["actions"])
            if "解放" not in actions or not actions & SUMMON:
                continue
            if not any(line["role"] == "被召喚" and objects[line["object"]]["source"]["kind"] != "自己"
                       for line in seg["lines"]):
                continue
            if failed is None:
                failed = {(f["block"], f["segment"]) for f in check_card(card)}
            rows.append((card["id"], card["name_ja"], seg, (b["id"], seg["id"]) not in failed))
parsed = [r for r in rows if not r[2]["unparsed"]]
passing = [r for r in rows if r[3]]
print(f"  段: {len(rows)};解析出: {len(parsed)};通過反向檢查: {len(passing)}")
for cid, name, seg, ok in sorted(rows, key=lambda r: (r[0], r[2]["id"])):
    state = "通過" if ok else (seg["unparsed"]["reason"] if seg["unparsed"] else "解析出但不通過")
    print(f"      - {cid} {name}({state}):{short(seg['text'])}")
