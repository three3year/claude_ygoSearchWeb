"""定版驗收的 CLI 薄殼:跑一次全表 → 逐項驗收 → 印定版報告(票09)。

建置由 `build_tag_cards.py` 負責、這一支**不寫任何檔**:定版要回答的是「repo 裡
現在這一份效果標記表能不能當網站的查詢基礎」,而不是「再建一次會長什麼樣」。兩件
事分開,驗收才不會因為自己順手改了資料而永遠通過。

驗收分兩段:

- **關卡**(`gates`)—— 每一項都是可機器檢查的斷言,全過才給定版。任何一項不過就
  指出是哪一項、缺口多少,退出碼 1。
- **報告**(`sections`)—— 定版報告要涵蓋的數字與清單。不管關卡過不過都印,因為
  沒過的時候更需要看。

「檔案就是管線的定點」那一關順帶把票09 的 JSON 格式檢查一起做掉:拿管線這一次的
輸出與磁碟上那一份逐字元比對,相同就同時證明了一卡一物件、依卡片密碼升冪、
`indent=2` 與結尾換行——那正是 `serialize_tag_cards` 寫出來的形狀。

用法:
    python script/tag_card/seal_report.py
    python script/tag_card/seal_report.py --out .scratch/tag-card/seal.txt
"""
import argparse
import os
import sys

import rules
from build_tag_cards import DIGEST_RE, LIST_PREVIEW
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_RULES_DOC,
                   DEFAULT_SPLITS, DEFAULT_TAG_CARDS, load_json, load_optional)
from tagcard import build_tag_cards, serialize_tag_cards

# 票55 的那批(ADR-0006):無官方日文文本、無[[官方明示]]、無[[影子預測]],
# 是全表可信度最低的一批,定版報告要單獨列出來供優先抽查
ZH_ONLY_NOTE = ("ot=2 的 TCG 限定卡,官方日文卡文與補足情報永遠不會出現,"
                "判定基礎是繁中卡文(ADR-0006)")


def read_digest(path):
    """規則清單文件裡登記的規則定義指紋;文件不在或寫壞時回 None。"""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        match = DIGEST_RE.search(f.read())
    return match.group(1) if match else None


def gate(label, ok, gap=""):
    return {"label": label, "ok": bool(ok), "gap": gap}


def empty_gate(label, rows, sample=lambda row: row["id"]):
    """「這份清單必須是空的」型的關卡,缺口=筆數 + 前幾筆的卡片密碼。"""
    preview = [sample(row) for row in rows[:LIST_PREVIEW]]
    return gate(label, not rows, f"{len(rows)} 筆 {preview}" if rows else "")


def convergence_gates(report, digest_on_disk):
    """收斂條件四項(spec「收斂條件」+ 票12 新增的分母下限)。"""
    below = report["rule_below_threshold"]
    thin = report["rule_below_attested"]
    return [
        gate("收斂一・規則清單本輪無異動",
             digest_on_disk == report["rules_digest"],
             f"{DEFAULT_RULES_DOC} 記的是 {digest_on_disk}、"
             f"本輪算出來的是 {report['rules_digest']}"),
        gate(f"收斂二・每條規則覆蓋 ≥ {rules.MIN_COVERAGE}",
             not below, f"不足的規則 {below}"),
        gate(f"收斂三・每條生效規則的官方明示分母 ≥ {rules.MIN_ATTESTED}",
             not thin, f"不足的規則 {thin}"),
        empty_gate("收斂四・衝突清單(影子預測 vs 判定)為空",
                   report["rule_conflicts"]),
    ]


def integrity_gates(report):
    """完整性檢查:效果句的欄位值域與拆句表的三道驗證。"""
    return [
        empty_gate("全表無殘留的 kind: null", report["kind_missing"]),
        empty_gate("text_zh / text_ja 都是對應卡文的連續子字串",
                   report["substring_violations"]),
        empty_gate("optional 只出現在承載必發/選發的類型上",
                   report["optional_on_wrong_kind"]),
        empty_gate("role 只出現在效果外文本", report["role_on_wrong_kind"]),
        empty_gate("拆句表驗證一・無遺漏覆蓋", report["split_coverage_failed"]),
        empty_gate("拆句表驗證二・官方引用未被拆點切開",
                   report["split_quote_violations"]),
        empty_gate("拆句表驗證三・卡文未變動(無退回整團)",
                   report["split_stale"]),
        empty_gate("拆句表紀錄結構合法", report["split_malformed"]),
        empty_gate("舊式整團全部有拆句表紀錄", report["pending_split"],
                   sample=lambda row: (row["id"], row["section"])),
    ]


def fixpoint_gate(entries, path):
    """磁碟上那一份就是管線的輸出(順帶做掉 JSON 格式檢查)。"""
    if not os.path.exists(path):
        return gate("tag_cards.json 是管線的定點", False, f"{path} 不存在")
    with open(path, encoding="utf-8", newline="") as f:
        on_disk = f.read()
    expected = serialize_tag_cards(entries)
    if on_disk == expected:
        return gate("tag_cards.json 是管線的定點(一卡一物件 / 依卡片密碼升冪 / "
                    "indent=2 / 結尾換行)", True)
    return gate("tag_cards.json 是管線的定點", False,
                f"與本輪輸出不同({len(on_disk)} vs {len(expected)} 字元),"
                "先跑一次 build_tag_cards.py 再驗收")


def all_gates(entries, report, digest_on_disk, sheet_path):
    ids = [entry["id"] for entry in entries]
    return (convergence_gates(report, digest_on_disk)
            + integrity_gates(report)
            + [gate("效果標記表依卡片密碼升冪且不重複",
                    ids == sorted(set(ids)), "排序或唯一性壞了"),
               fixpoint_gate(entries, sheet_path)])


def print_gates(gates, p):
    p("## 驗收關卡")
    p("")
    for row in gates:
        p(f"  [{'PASS' if row['ok'] else 'FAIL'}] {row['label']}"
          f"{'' if row['ok'] else ' —— ' + row['gap']}")
    failed = [row for row in gates if not row["ok"]]
    p("")
    p(f"→ {'全數成立,可以定版' if not failed else '未成立,不定版'}"
      f"({len(gates) - len(failed)}/{len(gates)})")
    return not failed


def print_totals(report, p):
    clauses = report["clauses"]
    p("## 規模")
    p("")
    p(f"  卡片 {report['cards']:,} 張,效果句 {clauses:,} 條")
    p(f"  純通常怪獸(空 clauses) {report['pure_normal']:,} 張,"
      f"靈擺段 {report['pendulum_sections']:,} 張")
    p(f"  前言段(效果外文本) {report['preambles']:,} 條,"
      f"● 子效果 {report['bullet_clauses']:,} 條,"
      f"拆句表拆出 {report['split_clauses']:,} 條")
    p("")
    p("## 判定來源分布")
    p("")
    for source, count in report["source_counts"].items():
        if source == "null" and not count:
            continue
        p(f"  {source:<14} {count:>7,}  {100 * count / max(clauses, 1):5.1f}%")
    p("")
    p("## 效果類型分布(十六種,ADR-0004 / ADR-0005)")
    p("")
    for kind, count in report["kind_counts"].items():
        p(f"  {kind:<16} {count:>7,}  {100 * count / max(clauses, 1):5.1f}%")


def print_review_lists(report, p):
    p("## 待審清單")
    p("")
    p(f"  confidence=low(該段無官方補足): {len(report['low_confidence'])} 張")
    p(f"    {report['low_confidence']}")
    p(f"  待複查 needs_review(旗標未清): {len(report['needs_review'])} 筆")
    for row in report["needs_review"]:
        p(f"    id={row['id']} section={row['section']} index={row['index']} "
          + " ".join(f"{k}={v}" for k, v in row.items()
                     if k not in ("id", "section", "index")))
    p("")
    p("## 官方明示的三份待審清單(最終狀態)")
    p("")
    for key, label in (("attribution_deferred", "歸屬由判定決定"),
                       ("quote_unmatched", "引號對不回本卡卡文"),
                       ("other_card_only", "明示句只提到別張卡名")):
        rows = report[key]
        p(f"  {label}: {len(rows)} 筆")
        for row in rows[:LIST_PREVIEW]:
            p(f"    id={row['id']} section={row.get('section')} "
              f"{row.get('reason') or row.get('kind') or ''}")


def print_zh_only(report, p):
    """票55 的 17 張:全表可信度最低的一批,單獨列出來供優先抽查(ADR-0006)。"""
    p("## 繁中判定卡(票55 / ADR-0006)")
    p("")
    p(f"  {len(report['no_japanese_text'])} 張 / "
      f"{report['zh_judged_clauses']} 條效果句 —— {ZH_ONLY_NOTE}")
    p(f"  {report['no_japanese_text']}")


def print_report(entries, report, gates, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p("# 效果標記表定版報告")
    p("")
    ok = print_gates(gates, p)
    p("")
    print_totals(report, p)
    p("")
    print_review_lists(report, p)
    p("")
    print_zh_only(report, p)
    return ok


def main(argv=None):
    parser = argparse.ArgumentParser(description="效果標記表的定版驗收(票09)")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_TAG_CARDS)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--rules-doc", default=DEFAULT_RULES_DOC)
    parser.add_argument("--out", help="把報告另存一份(預設只印到 stdout)")
    args = parser.parse_args(argv)

    existing = load_optional(args.sheet)
    entries, report = build_tag_cards(load_json(args.cards),
                                      load_json(args.faq_info),
                                      existing=existing,
                                      splits=load_optional(args.splits))
    gates = all_gates(entries, report, read_digest(args.rules_doc), args.sheet)
    ok = print_report(entries, report, gates)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            print_report(entries, report, gates, file=f)
        print(f"已另存 {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
