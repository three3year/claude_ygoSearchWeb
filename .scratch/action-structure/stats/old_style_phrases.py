# 舊式用語在官方 DB 文本(faq_info.json 的 card_text + pen_effect)上的出現次數,與同義表收表前後的覆蓋對比。
# 跑法:python -X utf8 stats/old_style_phrases.py [repo 根,預設目前目錄] [報告輸出路徑,預設 report/old_style_phrases.md]
# 報告正文不寫時間;同一輸入兩次產出相同。先前(票面)的數字是在 ja-JP.cdb 上量的,不能沿用,這裡一律以官方 DB 文本為準。
# 「收表後」的欄位讀 data/action_structure.json(卡片結構產物)現場算;「收表前」是 BASELINE 常數,
# 由這支腳本在整合分支 action-structure(a2e198a,票 11 收表前)的產物上量得,改同義表後重跑即得對比。
import json
import os
import re
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "report", "old_style_phrases.md")
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from card_structure import load_structures  # noqa: E402
from reverse_check import check_structures  # noqa: E402
from structure_shape import iter_segments  # noqa: E402

# (舊式用語, 正規表示式, 新式對應 / 收法)
PHRASES = [
    ("する事ができる", r"する事ができる", "〜できる(可選,極性做)"),
    ("事ができる", r"事ができる", "〜できる(含上一列)"),
    ("発動する事ができる", r"発動する事ができる", "発動できる(發動句語尾)"),
    ("フィールド上", r"フィールド上", "フィールド(區域 場上)"),
    ("フィールド上の", r"フィールド上の", "フィールドの(從)"),
    ("フィールド上に存在する", r"フィールド上に存在する", "フィールドの(從;舊式連體修飾)"),
    ("フィールド上に表側表示で存在する", r"フィールド上に表側表示で存在する", "表側是狀態,未收(留給位置規則)"),
    ("ゲームから除外", r"ゲームから除外", "除外(動作詞 除外,到 除外)"),
    ("生け贄に捧げ", r"生け贄に捧げ", "リリース(動作詞 解放)"),
    ("生け贄召喚", r"生け贄召喚", "アドバンス召喚(召喚手續,票 09)"),
    ("を選択して", r"を選択して", "を対象として(取對象,標在對象線)"),
    ("〜体/枚を選択して", r"[０-９]+(?:体|枚)(?:まで)?を選択して", "〜体を対象として(取對象)"),
    ("以下の効果から１つを選択して", r"以下(?:の効果)?から１つを選択して", "分歧(票 06),不是取對象"),
    ("選択した(モンスター|カード)", r"選択した(?:モンスター|カード)", "その(モンスター|カード)(指回取對象的物件)"),
    ("を対象として(新式,對照)", r"を対象として", "—"),
    ("墓地に送", r"墓地に送", "墓地へ送(動作詞 送墓)"),
    ("墓地に捨て", r"墓地に捨て", "捨てる(動作詞 捨棄;墓地 是明寫的到)"),
    ("持ち主の手札に戻す", r"持ち主の手札に戻す", "到 = 持ち主的手牌,未收(留給位置規則)"),
    ("なければならない", r"なければならない", "極性 必須"),
]

# 收表前(整合分支 a2e198a 的產物)量得的數字;鍵與下面的 measure() 輸出同形。
BASELINE = {
    "commit": "a2e198a",
    "totals": {"blocks": [28348, 24955], "segments": [60730, 8253], "objects": [20264, 16479],
               "reverse_passed": 4497},
    "segments_by_phrase": {
        "する事ができる": [884, 51, 16], "事ができる": [1629, 242, 97],
        "発動する事ができる": [326, 0, 0], "フィールド上": [3155, 317, 0],
        "フィールド上の": [879, 105, 0], "フィールド上に存在する": [502, 73, 0],
        "フィールド上に表側表示で存在する": [950, 106, 0], "ゲームから除外": [434, 5, 0],
        "生け贄に捧げ": [100, 1, 0], "生け贄召喚": [29, 0, 0], "を選択して": [1089, 0, 0],
        "〜体/枚を選択して": [719, 0, 0], "以下の効果から１つを選択して": [343, 0, 0],
        "選択した(モンスター|カード)": [369, 45, 0], "を対象として(新式,對照)": [4297, 0, 0],
        "墓地に送": [86, 1, 0], "墓地に捨て": [15, 4, 1], "持ち主の手札に戻す": [258, 0, 0],
        "なければならない": [185, 0, 0],
    },
}


def load_texts():
    faq = json.load(open(os.path.join(ROOT, "data", "sources", "faq_info.json"), encoding="utf8"))
    texts = {}
    for e in faq:
        if e.get("password") is None:
            continue
        texts.setdefault(e["password"], (e.get("card_text") or "") + "\n" + (e.get("pen_effect") or ""))
    return texts


def count_phrases(texts):
    rows = []
    for label, pattern, note in PHRASES:
        rx = re.compile(pattern)
        cards, occurrences = [], 0
        for pw in sorted(texts):
            n = len(rx.findall(texts[pw]))
            if n:
                cards.append(pw)
                occurrences += n
        rows.append({"label": label, "note": note, "cards": len(cards),
                     "occurrences": occurrences, "examples": cards[:5]})
    return rows


def measure(structures):
    """產物上的覆蓋:總覽(總數, 解析出)、反向檢查通過段數、
    各舊式用語所在段的(段數, 解析出, 反向檢查通過)。"""
    totals = {"blocks": [0, 0], "segments": [0, 0], "objects": [0, 0]}
    by_phrase = {label: [0, 0, 0] for label, _, _ in PHRASES}
    compiled = [(label, re.compile(p)) for label, p, _ in PHRASES]
    reverse = check_structures(structures)
    failed = {(f["card"], f["segment"]) for f in reverse["failures"] if f["segment"]}
    for card in structures:
        if card["unparsed"]:
            continue
        for obj in card["objects"]:
            totals["objects"][0] += 1
            totals["objects"][1] += 0 if obj["unparsed"] else 1
        for block in card["blocks"]:
            totals["blocks"][0] += 1
            totals["blocks"][1] += 0 if block["unparsed"] else 1
            for _, seg in iter_segments(block):
                totals["segments"][0] += 1
                parsed = 0 if seg["unparsed"] or seg["unstructured"] else 1   # 未結構化不算解析出(與 coverage.md 同)
                passed = 0 if (card["id"], seg["id"]) in failed else 1
                totals["segments"][1] += parsed
                for label, rx in compiled:
                    if rx.search(seg["text"]):
                        by_phrase[label][0] += 1
                        by_phrase[label][1] += parsed
                        by_phrase[label][2] += passed
    totals["reverse_passed"] = reverse["passed"]
    return {"totals": totals, "segments_by_phrase": by_phrase}


def pct(n, d):
    return f"{n / d * 100:.1f}%" if d else "—"


def render(texts, rows, after):
    before = BASELINE
    lines = [
        "# 舊式用語出現次數與同義表收表前後對比",
        "",
        "<!-- 由 .scratch/action-structure/stats/old_style_phrases.py 產生,不要手改;"
        "重建卡片結構後重跑即刷新。 -->",
        "",
        f"文本是官方 DB 文本(`faq_info.json` 的 `card_text` + `pen_effect`,依 password 去重 {len(texts):,} 張);"
        "先前票面的數字是在 ja-JP.cdb 上量的,不沿用。「張數」是含該用語的卡數,「次數」是出現次數。",
        "",
        "## 各舊式用語的出現次數",
        "",
        "| 舊式用語 | 張數 | 次數 | 新式對應 / 收法 | 例(卡號) |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        ex = ", ".join(f"`{pw}`" for pw in r["examples"])
        lines.append(f"| {r['label']} | {r['cards']:,} | {r['occurrences']:,} | {r['note']} | {ex} |")
    lines += [
        "",
        f"## 覆蓋對比:收表前(整合分支 `{before['commit']}`)→ 收表後(現在的產物)",
        "",
        "總覽的「解析出」與 `report/coverage.md` 同一算法;「反向檢查通過」與 `report/reverse_check.md` 同一算法。",
        "",
        "| 層次 | 總數(前 → 後) | 解析出(前 → 後) |",
        "|---|---|---|",
    ]
    for key, name in (("blocks", "區塊"), ("segments", "段"), ("objects", "物件")):
        b, a = before["totals"][key], after["totals"][key]
        lines.append(f"| {name} | {b[0]:,} → {a[0]:,} | {b[1]:,} → {a[1]:,} |")
    lines.append(f"| 反向檢查通過段 | — | {before['totals']['reverse_passed']:,} → "
                 f"{after['totals']['reverse_passed']:,} |")
    lines += [
        "",
        "### 含各舊式用語的段:段數、解析出、反向檢查通過(前 → 後)",
        "",
        "段的原文(含條件段、代價段)含該用語才計;一段可含多個用語。「解析出」是段本身沒標解析不出"
        "(物件可能仍解析不出);「反向檢查通過」是段由結構產生的日文與原文全等,物件、從/到都對了才算。",
        "",
        "| 舊式用語 | 段數(前 → 後) | 解析出(前 → 後) | 反向檢查通過(前 → 後) | 通過比例(後) |",
        "|---|---|---|---|---|",
    ]
    for label, _, _ in PHRASES:
        b = before["segments_by_phrase"].get(label, [None, None, None])
        a = after["segments_by_phrase"][label]
        fmt = lambda v: "—" if v is None else f"{v:,}"  # noqa: E731
        lines.append(f"| {label} | {fmt(b[0])} → {a[0]:,} | {fmt(b[1])} → {a[1]:,} | "
                     f"{fmt(b[2])} → {a[2]:,} | {pct(a[2], a[0])} |")
    lines.append("")
    return "\n".join(lines)


def main():
    texts = load_texts()
    rows = count_phrases(texts)
    print(f"官方文本 {len(texts)} 張(依 password 去重)")
    for r in rows:
        print(f"  {r['label']}:{r['cards']} 張、{r['occurrences']} 次  例 {r['examples']}")
    with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf8") as f:
        structures = load_structures(f.read())
    after = measure(structures)
    print("產物覆蓋:", json.dumps(after["totals"], ensure_ascii=False))
    print("各用語所在段 [段數, 解析出, 反向檢查通過]:", json.dumps(after["segments_by_phrase"], ensure_ascii=False))
    with open(OUT, "w", encoding="utf8", newline="\n") as f:
        f.write(render(texts, rows, after))
    print(f"已寫出 {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
