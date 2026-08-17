"""建置前端索引的 CLI 薄殼:讀總表與標記表 → webindex 管線 → 寫 web/data.js。

薄殼只做四件事:讀檔 → 呼叫 → 寫檔 → 印報告,並依 report 的 problems 決定
exit code。驗收條件全部長在 `build_index` 的 report 裡(與 tag_card 的
`seal_report.py` 同一個結構),所以這支不納入自動測試。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/web/build_index.py
    python script/web/build_index.py --no-write   # 只驗證,不動 data.js
"""
import argparse
import datetime
import hashlib
import json
import os
import sys

from webindex import build_index, serialize_index

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_TAGS = os.path.join(ROOT, "data", "tag_cards.json")
DEFAULT_ERRATA = os.path.join(ROOT, "data", "text_errata.json")
DEFAULT_OUTPUT = os.path.join(ROOT, "web", "data.js")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _digest(path):
    """來源檔雜湊:索引是誰生出來的,看 META 就知道。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def print_census(report, p):
    """每一個值域的成員數與對應卡數:某個值突然掉到 0 就在這裡看得見。"""
    census = report["census"]
    p(f"值域正典 digest={report['vocab']['digest']}")
    for name, counts in census["counts"].items():
        cells = " ".join(f"{code}={n}" for code, n in counts.items())
        empty = census["no_value"][name]
        tail = f" 無值={empty}" if empty else ""
        p(f"  {name}({len(counts)}): {cells}{tail}")
    cross = report["kind_cross"]
    cells = " ".join(f"{code}={n}" for code, n in cross["cards"].items())
    dropped = ("(拿掉按鈕: " + " ".join(cross["dropped"]) + ")"
               if cross["dropped"] else "")
    p(f"  跨類型魔陷卡數: {cells} {dropped}")


def print_checks(report, p, limit=20):
    """四道一致性檢查加兩道同族的。逐筆列出前 limit 筆,夠找到現場就好。"""
    checks = report["checks"]
    labels = (
        ("missing_cards", "卡片總表有卡而索引沒有"),
        ("duplicate_ids", "卡片密碼重複"),
        ("cards_without_clause_entry", "卡片沒有效果標記表條目"),
        ("unknown_values", "索引出現值域正典沒有的值"),
        ("clauses_without_kind", "效果句缺效果類型"),
        ("optional_on_non_carrier", "必發/選發出現在不承載的效果類型上"),
        ("coverage_gaps", "覆蓋缺口(已知兩種以外)"),
        ("clauses_not_in_desc", "效果句在卡文裡找不到"),
        ("unexplained_type_bits", "type 有值域正典沒解釋的位元"),
        ("alias_gap_not_extracted", "※ 別名的缺口與抽取結果對不上"),
        ("errata_not_reversible", "卡文勘誤逆推不回原文"),
    )
    gaps = report["known_gaps"]
    p(f"已知缺口: 段落標頭 {gaps['header']} 處、※ 別名 {gaps['alias']} 處")
    for key, label in labels:
        items = checks[key]
        p(f"{label}: {len(items)} 筆" + ("" if items else " ✓"))
        for item in items[:limit]:
            p(f"  {item}")
        if len(items) > limit:
            p(f"  …其餘 {len(items) - limit} 筆略")


def print_invariant(report, p):
    inv = report["monster_invariant"]
    missing = inv["monster_missing_race_or_attribute"]
    extra = inv["non_monster_with_monster_params"]
    status = "成立" if not missing and not extra else "**不成立**"
    p(f"不變式「大類是怪獸 ⟺ 有種族與屬性」: {status}"
      f"(怪獸 {inv['monsters']} 張、缺種族或屬性 {len(missing)} 張、"
      f"非怪獸殘留參數 {len(extra)} 張)")
    for cid in missing[:20]:
        p(f"  怪獸卻缺種族或屬性 id={cid}")
    for cid in extra[:20]:
        p(f"  非怪獸卻有怪獸參數 id={cid}")


def print_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"索引: {report['cards']} 張卡、{report['clauses']} 個效果句")
    print_census(report, p)
    print_invariant(report, p)
    print_checks(report, p)
    problems = report["problems"]
    if problems:
        p(f"**建置失敗**,{len(problems)} 個問題:")
        for problem in problems:
            p(f"  {problem}")
    else:
        p("全部檢查通過")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置查卡網站的前端索引")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表路徑 (預設 data/cards.json)")
    parser.add_argument("--tags", default=DEFAULT_TAGS,
                        help="效果標記表路徑 (預設 data/tag_cards.json)")
    parser.add_argument("--errata", default=DEFAULT_ERRATA,
                        help="卡文勘誤表路徑 (預設 data/text_errata.json)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="輸出路徑 (預設 web/data.js)")
    parser.add_argument("--no-write", action="store_true",
                        help="只跑檢查與報告,不寫出索引")
    args = parser.parse_args(argv)

    built_at = datetime.datetime.now().astimezone().strftime(
        "%Y-%m-%dT%H:%M:%S%z")
    errata = _load(args.errata) if os.path.exists(args.errata) else []
    index, report = build_index(
        _load(args.cards), _load(args.tags), built_at=built_at,
        sources={os.path.basename(args.cards): _digest(args.cards),
                 os.path.basename(args.tags): _digest(args.tags)},
        errata=errata)
    print_report(report)
    if report["problems"]:
        return 1
    if not args.no_write:
        with open(args.output, "w", encoding="utf-8", newline="\n") as f:
            f.write(serialize_index(index))
        print(f"已寫出 {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
