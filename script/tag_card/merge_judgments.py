"""判定結果的合併 CLI 薄殼:一份結果檔 → 拆句表 + 效果標記表。

判定票只寫**一個**結果檔,兩份來源檔的一致性由這支程式保證(票13 的工作契約):
拆點路由進[[拆句表]] `data/clause_splits.json`,類型與必發/選發路由進[[效果標記表]]
`data/tag_cards.json`。判定者不維護兩個檔。

結果檔一卡一段落一物件:

    [
      {"id": 12345, "section": "main", "split": true,
       "clauses": [
         {"index": "0", "text_zh": "…", "text_ja": "…"},
         {"index": "1", "text_zh": "…", "text_ja": "…",
          "kind": "啟動效果", "optional": "選發"}]},
      {"id": 67890, "section": "main",
       "clauses": [{"index": "①", "kind": "誘發效果(1速)", "optional": "必發"}]}
    ]

`split: true` 的段落會拿 `text_zh` / `text_ja` 去拆句表;沒有這個旗標的只吃
`kind` / `optional` / `role`。拆不出來或判不出來的留空並寫 `note`,不猜。

三道關卡,任何一道不過就整批不寫入(`--force` 可強行寫,但那等於把失敗藏起來):

1. **集合一致性自檢** —— 結果檔涵蓋的效果句與拆句標的必須與批次檔完全相同,
   少一筆或多一筆即失敗。
2. **拆句表三道驗證** —— 無遺漏覆蓋、官方 `『原文』` 引用交叉驗證、卡文變動即失效,
   由管線在套用時檢查(ADR-0003)。
3. **判定對得回效果句** —— 結果檔的 index 對不到任何一行即失敗。

用法:
    python script/tag_card/merge_judgments.py \\
        --result .scratch/tag-card/judgments/split-01.json \\
        --batch .scratch/tag-card/batches/split-01.json --ticket 票13
"""
import argparse
import json
import os
import sys

from build_tag_cards import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_OUTPUT,
                             DEFAULT_RULES_DOC, DEFAULT_SPLITS, load_json,
                             load_optional, print_report, write_rules_doc)
from official import INDEX_UNNUMBERED
from tagcard import build_tag_cards, serialize_tag_cards, split_hash

# 套用時被管線擋下來的理由;新加的拆句紀錄一筆都不該落在這些清單裡
SPLIT_FAILURES = ("split_malformed", "split_stale", "split_coverage_failed",
                  "split_quote_violations", "split_unused")


def key_of(record):
    return record["id"], record["section"]


def batch_expectations(batch):
    """批次檔 → (該拆的段落集合, 該判的效果句集合)。"""
    targets = set()
    clauses = set()
    for entry in batch["entries"]:
        split_sections = {t["section"]
                          for t in entry.get("split_targets", ())}
        targets.update((entry["id"], section) for section in split_sections)
        clauses.update((entry["id"], c["section"], c["index"])
                       for c in entry["clauses"]
                       if c["section"] not in split_sections)
    return targets, clauses


def result_coverage(result):
    """結果檔 → (拆了哪些段落, 判了哪些效果句)。"""
    targets = set()
    clauses = set()
    for record in result:
        if record.get("split"):
            targets.add(key_of(record))
            continue
        clauses.update((record["id"], record["section"], row["index"])
                       for row in record.get("clauses", ()))
    return targets, clauses


def set_problems(batch, result):
    """集合一致性自檢:少一筆或多一筆都要指名道姓。"""
    want_targets, want_clauses = batch_expectations(batch)
    got_targets, got_clauses = result_coverage(result)
    problems = []
    for label, want, got in (("拆句標的", want_targets, got_targets),
                             ("待判效果句", want_clauses, got_clauses)):
        for missing in sorted(want - got):
            problems.append(f"{label}少了 {missing}")
        for extra in sorted(got - want):
            problems.append(f"{label}多了 {extra}")
    return problems


def blob_index(entries, report):
    """{(卡片密碼, section): 未拆整團的那一行},拆句表的雜湊對著它算。"""
    unsplit = {(row["id"], row["section"]) for row in report["pending_split"]}
    blobs = {}
    for entry in entries:
        for clause in entry["clauses"]:
            key = (entry["id"], clause["section"])
            if key in unsplit and clause["index"] == INDEX_UNNUMBERED:
                blobs[key] = clause
    return blobs


def split_records(result, blobs, ticket):
    """結果檔的拆點 → 拆句表紀錄;對不到未拆整團的段落列成問題。"""
    records = []
    problems = []
    for record in result:
        if not record.get("split"):
            continue
        blob = blobs.get(key_of(record))
        if blob is None:
            problems.append(f"{key_of(record)} 不是未拆的整團,無從套用拆點")
            continue
        segments = [{"index": row["index"], "text_zh": row.get("text_zh", ""),
                     "text_ja": row.get("text_ja", "")}
                    for row in record.get("clauses", ())]
        records.append({
            "id": record["id"], "section": record["section"],
            "ticket": ticket,
            "text_hash": split_hash(blob["text_zh"], blob["text_ja"]),
            "segments": segments,
        })
    return records, problems


def merged_splits(existing, records):
    """既有拆句表 + 本票新增 → 依 (卡片密碼, section) 升冪的整份拆句表。"""
    by_key = {key_of(record): record for record in existing}
    by_key.update({key_of(record): record for record in records})
    return [by_key[key] for key in sorted(by_key)]


def applied_problems(report, records):
    """本票新增的拆句紀錄有沒有被三道驗證擋下來,以及判定對不對得回效果句。"""
    added = {key_of(record) for record in records}
    problems = []
    for key in SPLIT_FAILURES:
        for row in report[key]:
            if (row["id"], row["section"]) in added:
                problems.append(f"{key}: {row}")
    for row in report["judgment_orphans"]:
        problems.append(f"judgment_orphans: {row}")
    return problems


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description="合併判定票的結果檔")
    parser.add_argument("--result", required=True, help="判定票的結果檔")
    parser.add_argument("--batch", required=True, help="對應的批次檔")
    parser.add_argument("--ticket", required=True,
                        help="判定票號,寫進拆句表的每一筆")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_OUTPUT)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--rules-doc", default=DEFAULT_RULES_DOC)
    parser.add_argument("--dry-run", action="store_true",
                        help="跑完三道關卡與報告,不寫任何檔")
    parser.add_argument("--force", action="store_true",
                        help="關卡沒過也照寫(會把失敗藏起來,慎用)")
    args = parser.parse_args(argv)

    result = load_json(args.result)
    batch = load_json(args.batch)
    cards = load_json(args.cards)
    faqs = load_json(args.faq_info)
    existing = load_optional(args.sheet)
    splits = load_optional(args.splits, missing=[])

    problems = set_problems(batch, result)

    # 先照既有的拆句表跑一次,好拿到整團現在的原文——拆句表的雜湊對著它算,
    # 判定票寫結果檔時看到的也是它
    entries, report = build_tag_cards(cards, faqs, existing=existing,
                                      splits=splits)
    records, blob_problems = split_records(result, blob_index(entries, report),
                                           args.ticket)
    problems += blob_problems
    updated = merged_splits(splits, records)

    entries, report = build_tag_cards(cards, faqs, existing=existing,
                                      judgments=result, splits=updated)
    problems += applied_problems(report, records)

    print(f"結果檔 {len(result)} 段落:拆句 {len(records)} 筆、"
          f"判定 {report['judgment_clauses']} 條寫入、"
          f"官方接手 {report['judgment_confirmed_by_official']} 條")
    print(f"關卡: {len(problems)} 個問題")
    for problem in problems:
        print(f"  {problem}")

    if problems and not args.force:
        print("整批不寫入。修好結果檔再跑一次(或 --force 強行寫入)。")
        return 1
    if args.dry_run:
        print_report(report)
        print("--dry-run:未寫入任何檔案。")
        return 0

    write_json(args.splits, updated)
    os.makedirs(os.path.dirname(args.sheet), exist_ok=True)
    with open(args.sheet, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_tag_cards(entries))
    digest_changed = write_rules_doc(args.rules_doc, report)
    print_report(report, digest_changed=digest_changed)
    print(f"已寫出 {args.splits}、{args.sheet} 與 {args.rules_doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
