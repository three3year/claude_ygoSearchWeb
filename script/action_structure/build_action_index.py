"""建置動作索引:讀卡片結構、卡片總表、前端索引、字段表、效果標記表 → 寫 web/action-data.js。
建置失敗(前端索引對不上、超過體積門檻)時不寫檔、結束碼非 0。

用法:
    python -X utf8 script/action_structure/build_action_index.py
    python -X utf8 script/action_structure/build_action_index.py --no-write   # 只驗證,不寫檔
"""
import argparse
import json
import os
import sys
import time

from action_index import DEFAULT_SIZE_LIMIT, build_action_index
from card_structure import load_structures
from digest import file_digest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STRUCTURES = os.path.join(ROOT, "data", "action_structure.json")
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FRONTEND = os.path.join(ROOT, "web", "data.js")
DEFAULT_ARCHETYPES = os.path.join(ROOT, "data", "archetypes.json")
DEFAULT_TAGS = os.path.join(ROOT, "data", "tag_cards.json")
DEFAULT_OUTPUT = os.path.join(ROOT, "web", "action-data.js")
FRONTEND_HEAD = "window.CARD_DATA=[\n"
FRONTEND_TAIL = "\n];\n"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontend_cards(text):
    if not text.startswith(FRONTEND_HEAD) or FRONTEND_TAIL not in text:
        raise ValueError("前端索引開頭不是 window.CARD_DATA=[")
    return json.loads(text[len(FRONTEND_HEAD) - 2:text.index(FRONTEND_TAIL) + 2])


def print_report(report, file=None):
    p = lambda *a: print(*a, file=file or sys.stdout)  # noqa: E731
    if "rows" in report:
        p(f"列 {report['rows']:,}(段 {report['segments']:,},有對象線的 {report['line_rows']:,}、"
          f"線上有物件的 {report['object_lines']:,})")
        p(f"未解析的來源 {report['unresolved']:,}(寫進索引的 {report['unresolved_written']:,},"
          f"字面不含動作詞的不寫;其中引用節點 {report['unresolved_references']})")
        p(f"引用列 {report['references']}、指定的部分不是整張的 {report['part_entries']:,} 筆、"
          f"無官方日文的卡 {report['no_text']}、有當作卡名的卡 {report['treated_names']}")
        p(f"有列的卡 {report['cards']:,}、字段 {report['archetypes']}"
          f"(沒有成員不寫 {report['empty_archetypes']})")
        p(f"候選卡集合 {report['sets']:,}(清單 {report['list_sets']:,}、位元集 "
          f"{report['bitset_sets']:,};成員合計 {report['set_members']:,},最大 "
          f"{report['largest_set']:,})")
        p("值的清單 " + "、".join(f"{k} {v}" for k, v in report["vocab"].items()))
        p(f"產物 {report['bytes']:,} 位元組(gzip {report['gzip_bytes']:,});門檻 "
          f"{report['size_limit']:,}")
        p("各部分 " + "、".join(f"{k} {v:,}" for k, v in report["section_bytes"].items()))
        m = report["clause_mapping"]
        share = lambda n: f"{n:,}({n / m['segments']:.1%})" if m["segments"] else "0"  # noqa: E731
        p(f"效果對應 段 {m['segments']:,}:靠編號 {share(m['by_number'])}、靠位置 "
          f"{share(m['by_position'])}、留空 {share(m['unmapped'])};引用列 {m['references']}"
          f"(留空 {m['unmapped_references']})")
        p(f"留空的卡 {len(m['unmapped_cards']):,} 張:"
          + ", ".join(map(str, m["unmapped_cards"])))
    p("時間 " + "、".join(f"{k} {v:.1f} 秒" for k, v in report["timings"].items()))
    if report["problems"]:
        p(f"**建置失敗**,{len(report['problems'])} 個問題:")
        for problem in report["problems"]:
            p(f"  {problem}")
    else:
        p("全部檢查通過")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置動作搜尋的動作索引")
    parser.add_argument("--structures", default=DEFAULT_STRUCTURES,
                        help="卡片結構路徑(預設 data/action_structure.json)")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表路徑(預設 data/cards.json)")
    parser.add_argument("--frontend", default=DEFAULT_FRONTEND,
                        help="前端索引路徑(預設 web/data.js)")
    parser.add_argument("--archetypes", default=DEFAULT_ARCHETYPES,
                        help="字段表路徑(預設 data/archetypes.json)")
    parser.add_argument("--tags", default=DEFAULT_TAGS,
                        help="效果標記表路徑(預設 data/tag_cards.json)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="輸出路徑(預設 web/action-data.js)")
    parser.add_argument("--size-limit", type=int, default=DEFAULT_SIZE_LIMIT,
                        help=f"體積門檻,位元組(預設 {DEFAULT_SIZE_LIMIT:,})")
    parser.add_argument("--no-write", action="store_true",
                        help="只跑檢查與報告,不寫出索引")
    args = parser.parse_args(argv)

    paths = (args.structures, args.cards, args.frontend, args.archetypes, args.tags)
    for path in paths:
        print(f"來源 {os.path.basename(path)} digest={file_digest(path)}")
    started = time.perf_counter()
    structures = load_structures(_read(args.structures))
    cards = json.loads(_read(args.cards))
    frontend = frontend_cards(_read(args.frontend))
    archetypes = json.loads(_read(args.archetypes))
    tag_cards = json.loads(_read(args.tags))
    loading = time.perf_counter() - started
    text, report = build_action_index(structures, cards, frontend, archetypes,
                                      tag_cards=tag_cards, size_limit=args.size_limit)
    report["timings"] = {"讀檔": loading, **report["timings"]}
    print_report(report)
    if report["problems"]:
        return 1
    if not args.no_write:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"已寫出 {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
