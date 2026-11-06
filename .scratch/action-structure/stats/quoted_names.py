# 官方 DB 文本(card_text + pen_effect)裡最外層「」引用的名稱,去重後有幾個精確對到卡片總表 name_ja、全半形折疊後累計對到幾個。
# 跑法:python -X utf8 quoted_names.py [repo 根,預設目前目錄]
import collections
import json
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
faq = json.load(open(os.path.join(ROOT, "data", "sources", "faq_info.json"), encoding="utf8"))
cards = json.load(open(os.path.join(ROOT, "data", "cards.json"), encoding="utf8"))


def fw2hw(s):
    return "".join(chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in s)


def quotes(text):
    """最外層「…」的內容,內層巢狀「」保留在內容裡。"""
    out, depth, buf = [], 0, ""
    for ch in text:
        if ch == "「":
            if depth > 0:
                buf += ch
            depth += 1
        elif ch == "」" and depth > 0:
            depth -= 1
            if depth == 0:
                out.append(buf)
                buf = ""
            else:
                buf += ch
        elif depth > 0:
            buf += ch
    return out


names = {c["name_ja"] for c in cards if c.get("name_ja")}
names_hw = {fw2hw(n) for n in names}

# 每筆官方文本都算(原腳本不依 password 去重)
occ = collections.Counter()
for e in faq:
    for q in quotes((e.get("card_text") or "") + "\n" + (e.get("pen_effect") or "")):
        occ[q] += 1

uniq = set(occ)
exact = {q for q in uniq if q in names}
folded = {q for q in uniq - exact if fw2hw(q) in names_hw}
unmatched = uniq - exact - folded
cum = len(exact) + len(folded)
print(f"引用出現 {sum(occ.values())} 次,去重 {len(uniq)} 個")
print(f"  精確對到 name_ja:{len(exact)}({len(exact) / len(uniq):.1%})")
print(f"  全半形折疊後才對到:{len(folded)}  例 {sorted(folded, key=lambda q: -occ[q])[:5]}")
print(f"  累計對到:{cum}({cum / len(uniq):.1%})")
print(f"  對不到:{len(unmatched)}  高頻例 {sorted(unmatched, key=lambda q: -occ[q])[:8]}")
