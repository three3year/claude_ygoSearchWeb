"""反向檢查的 CLI 薄殼:讀 data/action_structure.json → reverse_check → 寫報告 md。

薄殼只做三件事:讀產物(一律走 `card_structure.load_structures`)→ 呼叫 → 寫檔。
報告正文不寫時間與雜湊(同一輸入兩次產出逐位元組相同、入版控);執行時間與
產物雜湊只印到 stdout。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python -X utf8 script/action_structure/build_reverse_check.py
    python -X utf8 script/action_structure/build_reverse_check.py --no-write   # 只印總覽
"""
import argparse
import datetime
import os
import sys

from card_structure import load_structures
from digest import file_digest
from reverse_check import check_structures, render_report

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STRUCTURES = os.path.join(ROOT, "data", "action_structure.json")
DEFAULT_OUT = os.path.join(ROOT, ".scratch", "action-structure", "report",
                           "reverse_check.md")



def main(argv=None):
    parser = argparse.ArgumentParser(description="對全庫卡片結構跑反向檢查、產報告")
    parser.add_argument("--structures", default=DEFAULT_STRUCTURES,
                        help="卡片結構產物路徑(預設 data/action_structure.json)")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="報告路徑(預設 .scratch/action-structure/report/reverse_check.md)")
    parser.add_argument("--no-write", action="store_true", help="只印總覽,不寫報告")
    args = parser.parse_args(argv)
    if not os.path.exists(args.structures):
        print(f"找不到卡片結構 {args.structures}(先跑 "
              "script/action_structure/build_structure.py)", file=sys.stderr)
        return 1
    with open(args.structures, encoding="utf-8") as f:
        structures = load_structures(f.read())
    report = check_structures(structures)
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"執行時間 {now}")
    print(f"來源 {os.path.basename(args.structures)} digest={file_digest(args.structures)}")
    print(f"卡片 {report['cards']} 張、無官方日文 {report['no_official_text']} 張、"
          f"段 {report['segments']}:通過 {report['passed']}、不通過 {report['failed']}、"
          f"未結構化 {report['unstructured']}")
    by_reason = {}
    for failure in report["failures"]:
        by_reason[failure["reason"]] = by_reason.get(failure["reason"], 0) + 1
    for reason, count in sorted(by_reason.items()):
        print(f"  {reason} {count}")
    if not args.no_write:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_report(report))
        print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
