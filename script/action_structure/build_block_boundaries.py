"""區塊邊界比對報告的 CLI 薄殼:讀官方 DB 文本、拆句表、共識集、邊界補丁 → 寫報告 md。

薄殼只做三件事:讀檔 → 呼叫 `block_boundary_report` → 寫檔。報告正文不寫時間與雜湊
(同一輸入兩次產出逐位元組相同、入版控);執行時間與來源雜湊只印到 stdout。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python -X utf8 script/action_structure/build_block_boundaries.py
    python -X utf8 script/action_structure/build_block_boundaries.py --no-write   # 只印總覽

`data/sources/faq_info.json` 不入版控,沒有它就比不了,這支會以非 0 結束;
邊界補丁 `data/block_boundaries.json` 不存在不是錯(還沒有站主判過的卡)。
"""
import argparse
import datetime
import json
import os
import sys

from block_boundary_report import compare_boundaries, render_block_boundaries
from digest import file_digest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_INFO = os.path.join(ROOT, "data", "sources", "faq_info.json")
DEFAULT_SPLITS = os.path.join(ROOT, "data", "clause_splits.json")
DEFAULT_CONSENSUS = os.path.join(ROOT, ".scratch", "action-structure", "stats",
                                 "boundary_consensus.json")
DEFAULT_BOUNDARIES = os.path.join(ROOT, "data", "block_boundaries.json")
DEFAULT_OUT = os.path.join(ROOT, ".scratch", "action-structure", "report",
                           "block_boundaries.md")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_optional(path):
    return _load(path) if os.path.exists(path) else []



def main(argv=None):
    parser = argparse.ArgumentParser(description="舊式卡區塊邊界對共識集比對、產報告")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--splits", default=DEFAULT_SPLITS, help="拆句表")
    parser.add_argument("--consensus", default=DEFAULT_CONSENSUS,
                        help="共識集 JSON(stats/boundary.py 產出)")
    parser.add_argument("--boundaries", default=DEFAULT_BOUNDARIES,
                        help="邊界補丁來源檔(不存在不是錯)")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--no-write", action="store_true", help="只印總覽,不寫報告")
    args = parser.parse_args(argv)
    for path in (args.faq, args.splits, args.consensus):
        if not os.path.exists(path):
            print(f"找不到 {path}", file=sys.stderr)
            return 1
    report = compare_boundaries(_load(args.faq), _load(args.consensus),
                                _load(args.splits), _load_optional(args.boundaries),
                                _load(args.cards))
    now = datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"執行時間 {now}")
    for path in (args.faq, args.splits, args.consensus, args.boundaries):
        if os.path.exists(path):
            print(f"來源 {os.path.basename(path)} digest={file_digest(path)}")
    print(f"共識集 {report['consensus_total']} 張、可比 {report['compared']} 張、"
          f"一致 {report['agree']}、不一致 {len(report['disagree'])}、"
          f"無共識 {len(report['no_consensus'])} 張")
    for status, ids in sorted(report["patches"].items()):
        print(f"  邊界補丁 {status} {len(ids)}")
    if not args.no_write:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_block_boundaries(report))
        print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
