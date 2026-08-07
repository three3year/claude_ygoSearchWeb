"""建置卡片總表的 CLI 薄殼:讀來源 cdb → cardlist 管線 → 寫出 cards.json。

用法:
    python build_cards.py --zh sources/cards.cdb -o cards.json
"""
import argparse
import json
import sys

from cardlist import build_card_list, serialize_card_list


def print_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"收錄: {report['included']} 張")
    excluded = report["excluded"]
    p(f"排除: 無正式密碼(先行卡) {excluded['no_password']} 筆、"
      f"衍生物 {excluded['token']} 筆")
    p(f"異圖合併: {report['merged_alt']} 筆")
    for lang, label in (("ja", "日文"), ("en", "英文")):
        cov = report.get("name_coverage", {}).get(lang)
        if cov:
            total = cov["named"] + cov["missing"]
            pct = cov["named"] / total * 100 if total else 0.0
            p(f"{label}卡名覆蓋率: {cov['named']}/{total} ({pct:.1f}%),"
              f" 缺漏 {cov['missing']} 筆")
    changes = report.get("changes")
    if changes is not None:
        p(f"差值更新: 新增 {len(changes['added'])} 張、"
          f"變動 {len(changes['changed'])} 張")
        for cid in changes["added"]:
            p(f"  新增 id={cid}")
        for ch in changes["changed"]:
            p(f"  變動 id={ch['id']} 欄位={','.join(ch['fields'])}")
    if report["alias_exceptions"]:
        p(f"alias 例外(未合併,請人工檢視): {len(report['alias_exceptions'])} 筆")
        for e in report["alias_exceptions"]:
            p(f"  id={e['id']} alias={e['alias']} 原因={e['reason']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置卡片總表")
    parser.add_argument("--zh", required=True, help="繁中 cards.cdb 路徑")
    parser.add_argument("--ja", help="日文卡名 cdb 路徑 (mycard ja-JP)")
    parser.add_argument("--en", help="英文卡名 cdb 路徑 (mycard en-US)")
    parser.add_argument("--existing",
                        help="既有 cards.json 路徑;給定時執行差值更新並輸出變動報告")
    parser.add_argument("-o", "--output", default="cards.json",
                        help="輸出 JSON 路徑 (預設 cards.json)")
    args = parser.parse_args(argv)

    existing = None
    if args.existing:
        with open(args.existing, encoding="utf-8") as f:
            existing = json.load(f)
    cards, report = build_card_list(
        args.zh, ja_path=args.ja, en_path=args.en, existing=existing)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_card_list(cards))
    print_report(report)
    print(f"已寫出 {args.output}")


if __name__ == "__main__":
    main()
