"""建置卡片結構的 CLI 薄殼:讀卡片總表與官方 DB 文本 → card_structure 管線 → 寫產物。

薄殼只做四件事:讀檔 → 呼叫 → 寫檔 → 印報告。時間與來源雜湊由這裡算、給進純函式,
只進 report(印在 stdout),不進產物,所以 `data/action_structure.json` 兩次建置
逐位元組相同、入版控後 git diff 讀得出改了什麼。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python -X utf8 script/action_structure/build_structure.py
    python -X utf8 script/action_structure/build_structure.py --no-write   # 只印報告

`data/sources/faq_info.json` 不入版控(由 script/faq_info/build_faq_info.py 建出),
沒有它就建不了結構,這支會以非 0 結束。
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

from card_structure import build_structures, serialize_structures

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_INFO = os.path.join(ROOT, "data", "sources", "faq_info.json")
DEFAULT_OUTPUT = os.path.join(ROOT, "data", "action_structure.json")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _digest(path):
    """來源檔雜湊(sha256 前 16 hex):報告裡看得出結構是哪份輸入生出來的。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def print_report(report, file=None):
    # 預設值不在定義時綁 sys.stdout:測試用 redirect_stdout 時才收得到。
    p = lambda *a: print(*a, file=file or sys.stdout)  # noqa: E731
    p(f"建置時間 {report['built_at']}")
    for name, digest in report["sources"].items():
        p(f"來源 {name} digest={digest}")
    p(f"卡片 {report['cards']} 張、無官方日文 {len(report['no_official_text'])} 張")
    p(f"區塊 {report['blocks']}(解析不出 {report['unparsed_blocks']})、"
      f"段 {report['segments']}(解析不出 {report['unparsed_segments']})、"
      f"物件 {report['objects']}(解析不出 {report['unparsed_objects']})")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置動作搜尋的卡片結構")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表路徑(預設 data/cards.json)")
    parser.add_argument("--faq", default=DEFAULT_FAQ_INFO,
                        help="官方 DB 文本路徑(預設 data/sources/faq_info.json)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="產物路徑(預設 data/action_structure.json)")
    parser.add_argument("--no-write", action="store_true",
                        help="只印報告,不寫產物")
    args = parser.parse_args(argv)
    if not os.path.exists(args.faq):
        print(f"找不到官方 DB 文本 {args.faq}(data/sources/ 不入版控,"
              "先跑 script/faq_info/build_faq_info.py)", file=sys.stderr)
        return 1
    built_at = datetime.datetime.now().astimezone().strftime(
        "%Y-%m-%dT%H:%M:%S%z")
    structures, report = build_structures(
        _load(args.cards), _load(args.faq), built_at=built_at,
        sources={os.path.basename(args.cards): _digest(args.cards),
                 os.path.basename(args.faq): _digest(args.faq)})
    print_report(report)
    if not args.no_write:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(serialize_structures(structures))
        print(f"已寫出 {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
