"""交件數字(summon-procedure 票 06):從入版控的框列匯出檔 data/action_frames.json 數召喚手續框。

接縫:匯出檔(句列的框、目錄列的召喚手續格、統計.位置)→ 文字報表。列:召喚手續框數與張數、詞元分佈、
施事者與動作對象分佈、結構化區域有值的框數、統計.位置四格、目錄在召喚手續有張數的列(照召喚手續張數排,
附效果位張數),以及效果位 0 張而召喚手續有張數的列數。
用法:python -X utf8 .scratch/summon-procedure/tools/handoff_stats.py(結果寫 tools/results/handoff_stats.txt 也印 stdout)
"""
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "effect-tokenize"))
from constraints import POS_EFFECT as EFFECT, POS_PROCEDURE as PROCEDURE  # noqa: E402

EXPORT = os.path.join(HERE, "..", "..", "..", "data", "action_frames.json")
OUT = os.path.join(HERE, "results", "handoff_stats.txt")


def counter_text(counter):
    return "、".join(f"{k} {v}" for k, v in counter.most_common())


def main():
    data = json.load(open(EXPORT, encoding="utf-8"))
    frames = [(s["card"], f) for s in data["句"] for f in s["frames"] if f["position"] == PROCEDURE]
    cards = {card for card, _ in frames}
    lines = [
        f"匯出檔 data/action_frames.json 版本 {data['版本']}",
        f"召喚手續框 {len(frames)} 框、{len(cards)} 張",
        f"詞元:{counter_text(Counter(f['action'] for _, f in frames))}",
        f"施事者:{counter_text(Counter(f.get('agent') or '空' for _, f in frames))}",
        f"動作對象:{counter_text(Counter(f.get('patient_mode') or '皆非' for _, f in frames))}",
        f"結構化區域有值 {sum(1 for _, f in frames if f.get('regions'))} 框、空 {sum(1 for _, f in frames if not f.get('regions'))} 框",
        "統計.位置:" + "、".join(f"{k} {v:,}" for k, v in data["統計"]["位置"].items()),
    ]
    rows = [r for r in data["目錄"] if r["predicate"] and r["cards"][PROCEDURE]]
    rows.sort(key=lambda r: (-r["cards"][PROCEDURE], r["path"]))
    lines.append(f"目錄具名查詢 {sum(1 for r in data['目錄'] if r['predicate'])} 列,在召喚手續有張數的 {len(rows)} 列"
                 f"(效果位 0 張的 {sum(1 for r in rows if not r['cards'][EFFECT])} 列):")
    lines += [f"  {r['name']}:召喚手續 {r['cards'][PROCEDURE]}、效果 {r['cards'][EFFECT]}" for r in rows]
    groups = [r for r in data["目錄"] if not r["predicate"] and r["cards"][PROCEDURE]]
    lines.append("大類、中類有召喚手續張數的:" + "、".join(f"{r['name']} {r['cards'][PROCEDURE]}" for r in groups))
    text = "\n".join(lines) + "\n"
    sys.stdout.reconfigure(encoding="utf-8")
    print(text, end="")
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    main()
