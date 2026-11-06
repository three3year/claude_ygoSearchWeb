# 官方 DB 文本(faq_info.json 的 card_text + pen_effect)中含「」と名のついた / カード名に「X」を含む / カード名が異なる 的卡數。
# 跑法:python -X utf8 phrases.py [repo 根,預設目前目錄]
import json
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
faq = json.load(open(os.path.join(ROOT, "data", "sources", "faq_info.json"), encoding="utf8"))

PHRASES = [
    ("「」と名のついた", re.compile(r"」と名のついた")),
    ("カード名に「X」を含む", re.compile(r"カード名に「[^」]+」を含む|名に「[^」]+」を含む")),
    ("カード名が異なる", re.compile(r"カード名が異なる")),
]

# 同一 password 有多筆時只算一張
texts = {}
for e in faq:
    if e.get("password") is None:
        continue
    texts.setdefault(e["password"], (e.get("card_text") or "") + "\n" + (e.get("pen_effect") or ""))

print(f"官方文本 {len(texts)} 張(依 password 去重)")
for label, rx in PHRASES:
    hit = [pw for pw, t in texts.items() if rx.search(t)]
    print(f"  {label}:{len(hit)} 張  例 {hit[:5]}")
