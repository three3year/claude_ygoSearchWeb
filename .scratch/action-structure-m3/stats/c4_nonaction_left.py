"""第 4 類:多子句切開後的非動作左半「Xを選択し、」「Xを対象とし、」「〜とはカード名が異なり、」。

跑法(repo 根):python -X utf8 .scratch/action-structure-m3/stats/c4_nonaction_left.py
讀 data/action_structure.json(頂層區塊的相鄰段,同 m2 split_classes.py 的判法:左半段原文去尾讀點
以 を選択し / を対象とし / 異なり 收尾)。印:處數、左右半狀態、右半開頭寫法、左半寫法變體、例外。
"""
import collections
import re

from common import cards, short

CLASSES = [
    ("1 舊式取對象「Xを選択し、」", r"を選択し$"),
    ("2 「Xを対象とし、」", r"を対象とし$"),
    ("4 「〜とは(元々の)カード名が異なり、」及變體", r"異なり$"),
]

def right_kind(text):
    t = re.sub(r"「[^」]*」", "「」", text)
    if t.startswith("以下の効果から"):
        return "右半是分歧引導「以下の効果から１つを選択して」"
    if "宣言" in t[:20]:
        return "右半是宣言「〜を宣言して」"
    if re.match(r"(この|その|それ|対象の|選択した)", t):
        return "右半有明寫物件/回指"
    if re.match(r"(表側|裏側|攻撃|守備)?(攻撃|守備)?表示で|自分フィールド上に|エンドフェイズ|装備カード扱い|表示形式|攻撃力|守備力", t):
        return "右半動作、物件省略"
    return "右半其他開頭"


def main():
    rows = collections.defaultdict(list)
    for c in cards():
        for b in c["blocks"]:
            segs = b["segments"]
            for i, s in enumerate(segs):
                t = b["text"][s["span"][0]:s["span"][1]].rstrip("、")
                for name, pat in CLASSES:
                    if re.search(pat, t):
                        nxt = segs[i + 1] if i + 1 < len(segs) else None
                        nt = b["text"][nxt["span"][0]:nxt["span"][1]] if nxt else ""
                        rows[name].append((c["id"], c["name_ja"], s, t, nxt, nt))
    for name, _ in CLASSES:
        rs = rows[name]
        print(f"\n## {name}:{len(rs)} 處 / {len({r[0] for r in rs})} 張")
        left = collections.Counter(("解析不出:" + r[2]["unparsed"]["reason"]) if r[2]["unparsed"] else "解析出" for r in rs)
        right = collections.Counter("無右半" if not r[4] else (("解析不出:" + r[4]["unparsed"]["reason"]) if r[4]["unparsed"] else "解析出") for r in rs)
        print("左半:", dict(left.most_common()))
        print("右半:", dict(right.most_common()))
        rk = collections.Counter(right_kind(r[5]) for r in rs)
        print("右半開頭:", dict(rk.most_common()))
        print("右半段類別/動作:", dict(collections.Counter((r[4]["kind"] if r[4] else None, ",".join(r[4]["actions"]) if r[4] else "") for r in rs).most_common(8)))
        if name.startswith("1"):
            cnt = collections.Counter(re.search(r"([０-９\d]+(体|枚)(まで)?)?を選択し$", r[3]).group(1) for r in rs)
            print("左半數量:", dict(cnt.most_common()))
        if name.startswith("4"):
            what = collections.Counter(re.search(r"とは?(.*?)が異なり$", r[3]).group(1) if re.search(r"とは?(.*?)が異なり$", r[3]) else r[3][-12:] for r in rs)
            print("異なる的屬性:", dict(what.most_common()))
        print("例:")
        shown = set()
        for r in rs:
            k = right_kind(r[5])
            if (k, bool(r[4] and not r[4]["unparsed"])) in shown:
                continue
            shown.add((k, bool(r[4] and not r[4]["unparsed"])))
            st = "解析出" if r[4] and not r[4]["unparsed"] else ("解析不出:" + r[4]["unparsed"]["reason"] if r[4] else "")
            print(f"  [{k}/{st}] {r[1]} {r[0]}「{short(r[3], 50)}、｜{short(r[5], 45)}」")
    merged_left_halves()


def merged_left_halves():
    """m3 票 06 之後「〜とは〜が異なり(、)」不另成段,併在右半的段裡:數這種段、它的狀態、
    帶這截字面的物件解析出幾個。"""
    rows = []
    for c in cards():
        objects = {o["id"]: o for o in c["objects"]}
        for b in c["blocks"]:
            for s in b["segments"]:
                t = b["text"][s["span"][0]:s["span"][1]]
                if re.search(r"異なり(?!$)", t):
                    objs = [objects[l["object"]] for l in s["lines"]
                            if "異なり" in (objects[l["object"]]["text"] or "")]
                    rows.append((c["id"], c["name_ja"], s, t, objs))
    print(f"\n## 4b 「〜とは〜が異なり(、)」併在右半的段裡:{len(rows)} 處 / {len({r[0] for r in rows})} 張")
    seg = collections.Counter(("解析不出:" + r[2]["unparsed"]["reason"]) if r[2]["unparsed"] else "解析出" for r in rows)
    print("段:", dict(seg.most_common()))
    obj = collections.Counter(
        "沒有建出物件" if not r[4] else
        ("物件解析不出:" + r[4][0]["unparsed"]["reason"]) if r[4][0]["unparsed"] else "物件解析出"
        for r in rows)
    print("帶這截字面的物件:", dict(obj.most_common()))
    for r in rows:
        if r[2]["unparsed"] or not r[4] or r[4][0]["unparsed"]:
            why = (r[2]["unparsed"] or {}).get("reason") or (r[4][0]["unparsed"]["reason"] if r[4] else "")
            print(f"  [{why}] {r[1]} {r[0]}「{short(r[3], 90)}」")


if __name__ == "__main__":
    main()
