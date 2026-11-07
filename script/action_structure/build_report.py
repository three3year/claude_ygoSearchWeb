"""覆蓋報告的 CLI 薄殼:讀卡片結構產物與卡片總表 → coverage_report → 寫 md。

薄殼只做四件事:讀檔 → 呼叫 → 寫檔 → 印摘要。時間與來源雜湊只印到 stdout,
不進報告正文,所以 `.scratch/action-structure/report/coverage.md` 兩次產出逐位元組相同。
產物張數與卡片總表張數不符時以非 0 結束、不寫檔:報告的「張數加總等於卡片總表張數」
就靠這一道關卡,產物過期時不會寫出一份對不上的報告。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python -X utf8 script/action_structure/build_report.py
    python -X utf8 script/action_structure/build_report.py --out 另一個路徑

與 build_structure.py 分開一支,是讓建置與報告各自可跑:重建產物不必重算報告,
看報告也不必有 data/sources/(產物入版控,clean checkout 就能跑這支)。
"""
import argparse
import datetime
import json
import os
import sys

from card_structure import load_structures
from coverage_report import build_coverage, render_coverage
from digest import file_digest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STRUCTURES = os.path.join(ROOT, "data", "action_structure.json")
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_OUT = os.path.join(ROOT, ".scratch", "action-structure", "report",
                           "coverage.md")



def main(argv=None):
    parser = argparse.ArgumentParser(description="產出動作搜尋卡片結構的覆蓋報告")
    parser.add_argument("--structures", default=DEFAULT_STRUCTURES,
                        help="卡片結構產物路徑(預設 data/action_structure.json)")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表路徑(預設 data/cards.json)")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="報告路徑(預設 .scratch/action-structure/report/coverage.md)")
    args = parser.parse_args(argv)
    with open(args.structures, encoding="utf-8") as f:
        structures = load_structures(f.read())
    with open(args.cards, encoding="utf-8") as f:
        card_count = len(json.load(f))
    coverage = build_coverage(structures)
    built_at = datetime.datetime.now().astimezone().strftime(
        "%Y-%m-%dT%H:%M:%S%z")
    print(f"產出時間 {built_at}")
    for path in (args.structures, args.cards):
        print(f"來源 {os.path.basename(path)} digest={file_digest(path)}")
    print(f"卡片總表 {card_count} 張;產物 {coverage['cards']} 張 = 有卡片結構 "
          f"{coverage['with_structure']} + 無官方日文 {len(coverage['no_official_text'])}")
    if coverage["cards"] != card_count:
        print(f"產物張數 {coverage['cards']} 與卡片總表 {card_count} 不符:"
              "先重跑 build_structure.py", file=sys.stderr)
        return 1
    print(f"區塊 {coverage['blocks']['total']}(解析不出 {coverage['blocks']['unparsed']})、"
          f"段 {coverage['segments']['total']}(解析不出 {coverage['segments']['unparsed']})、"
          f"物件 {coverage['objects']['total']}(解析不出 {coverage['objects']['unparsed']})")
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_coverage(coverage))
    print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
