"""建置卡片總表的 CLI 薄殼:讀來源 cdb → cardlist 管線 → 寫出 cards.json。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/card_list/build_cards.py --zh data/sources/cards.cdb
"""
import argparse
import json
import os
import sys

from cardlist import build_card_list, serialize_card_list

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUTPUT = os.path.join(ROOT, "data", "cards.json")
DEFAULT_ERRATA = os.path.join(ROOT, "data", "text_errata.json")


def load_errata(path):
    """讀卡文勘誤表;檔案不存在視為無勘誤(clean checkout 一定有,防的是測試環境)。"""
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_monster_invariant(report, p):
    """大類閘門的成果:清空了幾張,以及不變式兩個方向的檢查結果。

    違反者逐張列出——這道不變式一旦破了,下游拿「有種族」判怪獸就會出錯,
    而那是無聲的錯誤結果。
    """
    inv = report["monster_invariant"]
    p(f"非怪獸清空怪獸參數: {report['cleared_monster_params']} 張"
      "(陷阱怪獸等,cdb 存的是它變成怪獸之後的形態)")
    missing = inv["monster_missing_race_or_attribute"]
    extra = inv["non_monster_with_monster_params"]
    status = "成立" if not missing and not extra else "**不成立**"
    p(f"不變式「大類是怪獸 ⟺ 有種族與屬性」: {status}"
      f"(怪獸 {inv['monsters']} 張、缺種族或屬性 {len(missing)} 張、"
      f"非怪獸殘留參數 {len(extra)} 張)")
    for cid in missing:
        p(f"  怪獸卻缺種族或屬性 id={cid}")
    for cid in extra:
        p(f"  非怪獸卻有怪獸參數 id={cid}")


def print_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"收錄: {report['included']} 張")
    excluded = report["excluded"]
    p(f"排除: 無正式密碼(先行卡) {excluded['no_password']} 筆、"
      f"衍生物 {excluded['token']} 筆")
    p(f"異圖合併: {report['merged_alt']} 筆")
    if report.get("errata_applied"):
        p(f"卡文勘誤: 套用 {report['errata_applied']} 筆")
    print_monster_invariant(report, p)
    for lang, label in (("ja", "日文"), ("en", "英文")):
        cov = report.get("name_coverage", {}).get(lang)
        if cov:
            total = cov["named"] + cov["missing"]
            pct = cov["named"] / total * 100 if total else 0.0
            p(f"{label}卡名覆蓋率: {cov['named']}/{total} ({pct:.1f}%),"
              f" 缺漏 {cov['missing']} 筆")
    md_cov = report.get("md_rarity_coverage")
    if md_cov:
        total = md_cov["rated"] + md_cov["missing"]
        pct = md_cov["rated"] / total * 100 if total else 0.0
        p(f"MD 稀有度覆蓋率: {md_cov['rated']}/{total} ({pct:.1f}%),"
          f" 未實裝 {md_cov['missing']} 筆")
    genesys_listed = report.get("genesys_listed")
    if genesys_listed is not None:
        p(f"Genesys 列點卡: {genesys_listed} 張(其餘為 0 點)")
    for fmt, cov in sorted((report.get("banlist_coverage") or {}).items()):
        p(f"{fmt.upper()} 禁限: 上榜 {cov['listed']} 張、"
          f"對不上總表 {cov['unmatched']} 筆")
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
    parser.add_argument("--md", help="MD 稀有度 JSON 路徑 (masterduelmeta)")
    parser.add_argument("--genesys",
                        help="Genesys 點數 JSON 路徑 (YGOPRODeck 萃取)")
    parser.add_argument("--banlist-ocg",
                        help="OCG 禁限 JSON 路徑 (YGOPRODeck 禁限端點萃取)")
    parser.add_argument("--existing",
                        help="既有 cards.json 路徑;給定時執行差值更新並輸出變動報告")
    parser.add_argument("--errata", default=DEFAULT_ERRATA,
                        help="卡文勘誤表路徑 (預設 data/text_errata.json)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="輸出 JSON 路徑 (預設 data/cards.json)")
    args = parser.parse_args(argv)

    existing = None
    if args.existing:
        with open(args.existing, encoding="utf-8") as f:
            existing = json.load(f)
    banlist_paths = {}
    if args.banlist_ocg:
        banlist_paths["ocg"] = args.banlist_ocg
    cards, report = build_card_list(
        args.zh, ja_path=args.ja, en_path=args.en, md_rarity_path=args.md,
        genesys_path=args.genesys, banlist_paths=banlist_paths or None,
        existing=existing, errata=load_errata(args.errata))
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_card_list(cards))
    print_report(report)
    print(f"已寫出 {args.output}")


if __name__ == "__main__":
    main()
