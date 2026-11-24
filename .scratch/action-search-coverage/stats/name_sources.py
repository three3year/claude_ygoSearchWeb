# 規格〔卡名包含〕的數字:「〜として扱う」當作的卡名有幾個、對得到卡的有幾個;幾個字在各語言名字裡命中幾張。
# 跑法(repo 根):python -X utf8 .scratch/action-search-coverage/stats/name_sources.py
# 讀版控裡的 data/action_structure.json、data/cards.json。當作的卡名 = 卡片屬性表 name 的第 2 列起。
# 對卡:先比日文卡名原字;再比全半形折疊、去空白後的字。各語言命中只比卡片總表的中日英名(不含別名)。
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from archetype_table import fold_width  # noqa: E402

with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
    structures = json.load(f)
with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
    cards = json.load(f)


def loose(s):
    return fold_width(s).replace(" ", "").replace("　", "")


exact = {c["name_ja"]: c for c in cards if c.get("name_ja")}
folded = {loose(c["name_ja"]): c for c in cards if c.get("name_ja")}

total = anywhere = positional = hit_exact = hit_folded = 0
missing = []
for card in structures:
    for row in ((card.get("attributes") or {}).get("name") or [])[1:]:
        total += 1
        if row.get("where"):
            positional += 1
        else:
            anywhere += 1
        if row["value"] in exact:
            hit_exact += 1
        elif loose(row["value"]) in folded:
            hit_folded += 1
        else:
            missing.append((card["name_ja"], row["value"]))

print(f"當作的卡名 {total}:任何位置 {anywhere}、帶位置條件 {positional}")
print(f"對得到卡:原字 {hit_exact}、折疊後 {hit_folded};對不到 {len(missing)}")
for owner, value in missing:
    print(f"- {owner} → {value}")
print()
print("| 字 | 中文名 | 日文名 | 英文名 | 三種合計 |")
print("|---|---:|---:|---:|---:|")
for word in ["神", "魔導", "天使", "龍", "竜", "黑魔導", "ブラック", "Dragon"]:
    zh = {c["id"] for c in cards if word in (c.get("name_zh") or "")}
    ja = {c["id"] for c in cards if word in (c.get("name_ja") or "")}
    en = {c["id"] for c in cards if word.lower() in (c.get("name_en") or "").lower()}
    print(f"| {word} | {len(zh):,} | {len(ja):,} | {len(en):,} | {len(zh | ja | en):,} |")
