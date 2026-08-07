"""建置卡片總表的 CLI 薄殼:讀來源 cdb → cardlist 管線 → 寫出 cards.json。

用法:
    python build_cards.py --zh sources/cards.cdb -o cards.json
"""
import argparse
import sys

from cardlist import build_card_list, serialize_card_list


def print_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"收錄: {report['included']} 張")
    excluded = report["excluded"]
    p(f"排除: 無正式密碼(先行卡) {excluded['no_password']} 筆、"
      f"衍生物 {excluded['token']} 筆")
    p(f"異圖合併: {report['merged_alt']} 筆")
    if report["alias_exceptions"]:
        p(f"alias 例外(未合併,請人工檢視): {len(report['alias_exceptions'])} 筆")
        for e in report["alias_exceptions"]:
            p(f"  id={e['id']} alias={e['alias']} 原因={e['reason']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置卡片總表")
    parser.add_argument("--zh", required=True, help="繁中 cards.cdb 路徑")
    parser.add_argument("-o", "--output", default="cards.json",
                        help="輸出 JSON 路徑 (預設 cards.json)")
    args = parser.parse_args(argv)

    cards, report = build_card_list(args.zh)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_card_list(cards))
    print_report(report)
    print(f"已寫出 {args.output}")


if __name__ == "__main__":
    main()
