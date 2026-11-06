# 卡片總表(data/cards.json)逐張比官方 DB 文本(faq_info.json 的 card_text)與 ja-JP.cdb 的 desc:兩邊有無、去空白後同異、差異分類。
# 跑法:python -X utf8 source_diff.py [repo 根,預設目前目錄]
import collections
import json
import os
import re
import sqlite3
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."


def path(*p):
    return os.path.join(ROOT, *p)


def ro_db(name):
    uri = "file:" + os.path.abspath(path("data", "sources", name)).replace("\\", "/") + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


cards = json.load(open(path("data", "cards.json"), encoding="utf8"))
faq = json.load(open(path("data", "sources", "faq_info.json"), encoding="utf8"))
cdb = {i: (n, d or "") for i, n, d in ro_db("ja-JP.cdb").execute("select id,name,desc from texts")}

# 同一 password 有多筆時取第一筆
faq_by_pw = {}
for e in faq:
    if e.get("password") is not None:
        faq_by_pw.setdefault(e["password"], e)

WS = re.compile(r"\s+")
NUM = re.compile(r"[①②③④⑤⑥⑦⑧⑨⑩]")
JA = re.compile(r"[぀-ヿ一-鿿]")
PEN_HEAD = re.compile(r"【Ｐスケール：[^】]*】")
SYM = str.maketrans({"・": "", "･": "", "「": "", "」": "", "『": "", "』": "", "，": "", "、": "", "。": "", "（": "(", "）": ")"})


def norm(s):
    return WS.sub("", s or "")


def fw2hw(s):
    return "".join(chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in s)


def loose(s):
    return fw2hw(norm(s)).translate(SYM)


def cdb_parts(desc):
    """靈擺卡 → (P 效果, 怪獸效果);非靈擺 → (None, desc)。"""
    if "【Ｐスケール" not in desc:
        return None, desc
    rest = PEN_HEAD.sub("", desc, count=1)
    m = re.search(r"【(モンスター効果|モンスター情報|フレーバーテキスト)】", rest)
    if not m:
        return rest, ""
    return rest[:m.start()], rest[m.end():]


def classify(ft, fp, ct):
    """分類順序照原腳本 q2.py:先判非日文、靈擺,再判符號/全半形,最後判編號。"""
    pen, main = cdb_parts(ct)
    if len(JA.findall(ct)) / max(1, len(norm(ct))) < 0.3:
        return "cdb非日文(英文回譯)"
    if pen is not None:
        if norm(main) == norm(ft) and norm(pen) == norm(fp):
            return "靈擺分段格式(僅標頭)"
        if loose(main) == loose(ft) and loose(pen) == loose(fp):
            return "靈擺分段+符號/全半形"
        if norm(main) == norm(ft):
            return "靈擺:主效果同、P效果不同"
        if NUM.search(main) and not NUM.search(ft):
            return "靈擺:舊版文(faq無編號)"
        return "靈擺:主效果文字差異"
    if loose(ft) == loose(ct):
        return "僅符號/全半形"
    if NUM.search(ct) and not NUM.search(ft):
        return OLD_STYLE
    if NUM.search(ft) and not NUM.search(ct):
        return "faq有編號cdb無(cdb舊)"
    return "文字差異(勘誤/改版/其他)"


OLD_STYLE = "舊版文(官方文本無①編號,cdb有)"

both = only_faq = only_cdb = neither = same = diff = 0
cats = collections.Counter()
ex = collections.defaultdict(list)
no_faq_ot = collections.Counter()
no_faq_ex = []
for c in cards:
    pw = c["id"]
    f = faq_by_pw.get(pw)
    d = cdb.get(pw)
    hf = bool(f and f.get("card_text"))
    hc = bool(d and d[1])
    if not hf:
        no_faq_ot[c.get("ot")] += 1
        no_faq_ex.append(pw)
    if hf and hc:
        both += 1
    elif hf:
        only_faq += 1
        continue
    elif hc:
        only_cdb += 1
        continue
    else:
        neither += 1
        continue
    ft, fp, ct = f["card_text"], f.get("pen_effect") or "", d[1]
    if norm(ft) == norm(ct):
        same += 1
        continue
    diff += 1
    k = classify(ft, fp, ct)
    cats[k] += 1
    ex[k].append(pw)

print(f"卡片總表 {len(cards)} 張")
print(f"  兩邊都有(官方文本 card_text 非空且 cdb desc 非空) {both}")
print(f"  只有官方文本 {only_faq}、只有 cdb {only_cdb}、兩邊都沒有 {neither}")
print(f"  兩邊都有者去空白換行後:相同 {same}、不同 {diff}")
print("  不同者分類(依序判定,先判中者為準):")
for k, v in cats.most_common():
    print(f"    {v:5d} {k}  例 {ex[k][:5]}")
print(f"官方文本無①②③而 cdb 有①(非靈擺,排除 cdb 非日文與僅符號/全半形差異):{cats[OLD_STYLE]}")
print(f"卡片總表中無官方 DB 文本(faq 無該 password 或 card_text 空):{len(no_faq_ex)} 張,"
      f"ot 分布 {dict(sorted(no_faq_ot.items()))}  例 {no_faq_ex[:6]}")
