"""tag 判定結果的合併 CLI 薄殼(票09):一份結果檔 → 效果標記表。

與效果類型的 `merge_judgments.py` 同構,三道關卡,任何一道不過就整批不寫入:

1. **集合一致性自檢** —— 結果檔涵蓋的效果句必須與批次檔完全相同,少一筆或
   多一筆都指名道姓。
2. **值全在正典** —— tag 系列:每個 tag 的類別必須是批次的類別、槽位鍵與值
   照 `vocab.tag_code` 解得動;timing 系列:值在觸發時機值域、句子的效果類型
   是承載者。改判旗標兩個方向都要對得上批次(漏寫=改判沒做卻看起來成功,
   多寫=一般票偷覆寫)。
3. **對得回效果句** —— 鍵對不到標記表、或日文原文與批次時不同(卡文已變動,
   批次過期)即失敗。

寫入語意:tag 系列把該句**該類別**的既有 `llm` tag 換成結果檔那一組(空陣列=
判空),類別記進 `tags_checked`;timing 系列寫 `timing`/`timing_src: "llm"`,
判 null 時把「觸發時機」記進 `tags_checked`。寫完重跑管線定版(規則層 tag 與
merge 的保留邏輯照常生效),磁碟上那一份因此仍是管線的定點。

用法:
    python script/tag_card/merge_tag_judgments.py \\
        --result .scratch/effect-tag/judgments/tag-mv-01.json \\
        --batch .scratch/effect-tag/batches/tag-mv-01.json --ticket 票09
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "web"))
import vocab  # noqa: E402

import tag_rules  # noqa: E402
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_SPLITS,  # noqa: E402
                   DEFAULT_TAG_CARDS, load_json, load_modern_ja,
                   load_optional)
from tagcard import (_tag_sort_key, build_tag_cards,  # noqa: E402
                     serialize_tag_cards)

TIMING_ZH = {e["zh"] for e in vocab.entries(vocab.TIMING)}
TIMING_SENTINEL = "觸發時機"


def key_of(row):
    return (row["id"], row["section"], row["index"])


def set_problems(batch, result):
    want = {key_of(row) for row in batch["entries"]}
    got = {key_of(row) for row in result}
    problems = [f"待判效果句少了 {key}" for key in sorted(want - got)]
    problems += [f"待判效果句多了 {key}" for key in sorted(got - want)]
    return problems


def rejudge_problems(batch, result):
    want = {key_of(row) for row in batch["entries"] if row.get("rejudge")}
    got = {key_of(row) for row in result if row.get("rejudge")}
    return ([f"改判標的 {key} 的結果沒寫 rejudge: true"
             for key in sorted(want - got)]
            + [f"{key} 不是這一批的改判標的,結果卻寫了 rejudge: true"
               for key in sorted(got - want)])


def value_problems(batch, result):
    problems = []
    category = batch["category"]
    timing = batch["series"] == "timing"
    for row in result:
        key = key_of(row)
        if timing:
            value = row.get("timing")
            if value is not None and value not in TIMING_ZH:
                problems.append(f"{key} 的時機值 {value!r} 不在值域")
            continue
        for tag in row.get("tags", ()):
            if tag.get("cat") != category:
                problems.append(f"{key} 的 tag 類別 {tag.get('cat')!r} "
                                f"不是本批的 {category!r}")
                continue
            code, problem = vocab.tag_code(tag)
            if code is None:
                problems.append(f"{key} 的 tag 解不進正典:{problem}")
    return problems


def apply_rows(sheet, batch, result, ticket):
    """結果寫進標記表(dict 就地改);對不回效果句的列成問題清單。"""
    problems = []
    clauses = {(entry["id"], c["section"], c["index"]): c
               for entry in sheet for c in entry["clauses"]}
    batch_text = {key_of(row): row["text_ja"] for row in batch["entries"]}
    batch_kind = {key_of(row): row["kind"] for row in batch["entries"]}
    category = batch["category"]
    timing = batch["series"] == "timing"
    for row in result:
        key = key_of(row)
        clause = clauses.get(key)
        if clause is None:
            problems.append(f"{key} 不是標記表上的效果句")
            continue
        if clause["text_ja"] != batch_text.get(key):
            problems.append(f"{key} 的卡文已變動,批次過期(重出批次)")
            continue
        if timing:
            value = row.get("timing")
            if value is None:
                checked = set(clause["tags_checked"])
                checked.add(TIMING_SENTINEL)
                clause["tags_checked"] = sorted(checked)
                clause["timing"] = None
                clause["timing_src"] = None
            else:
                if batch_kind.get(key) != clause["kind"]:
                    problems.append(f"{key} 的效果類型已變動,批次過期")
                    continue
                clause["timing"] = value
                clause["timing_src"] = tag_rules.TAG_SRC_LLM
            continue
        kept = [tag for tag in clause["tags"]
                if tag.get("cat") != category
                or tag.get("src") == tag_rules.TAG_SRC_RULE]
        for tag in row.get("tags", ()):
            kept.append({**{k: v for k, v in tag.items() if v is not None},
                         "src": tag_rules.TAG_SRC_LLM, "ticket": ticket})
        clause["tags"] = sorted(kept, key=_tag_sort_key)
        checked = set(clause["tags_checked"])
        checked.add(category)
        clause["tags_checked"] = sorted(checked)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description="合併 tag 判定票的結果檔")
    parser.add_argument("--result", required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_TAG_CARDS)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="關卡沒過也照寫(會把失敗藏起來,慎用)")
    args = parser.parse_args(argv)

    result = load_json(args.result)
    batch = load_json(args.batch)
    if batch.get("taxonomy_digest") != vocab.tag_digest():
        print(f"批次的體系定稿指紋 {batch.get('taxonomy_digest')} 與現行 "
              f"{vocab.tag_digest()} 不符——體系動過,整批重出")
        if not args.force:
            return 1

    problems = (set_problems(batch, result) + rejudge_problems(batch, result)
                + value_problems(batch, result))
    sheet = load_json(args.sheet)
    problems += apply_rows(sheet, batch, result, args.ticket)

    written = sum(len(r.get("tags", ())) for r in result)
    blank = sum(1 for r in result
                if not r.get("tags") and not r.get("timing"))
    print(f"結果檔 {len(result)} 條:tag 寫入 {written} 個、判空 {blank} 條")
    print(f"關卡: {len(problems)} 個問題")
    for problem in problems:
        print(f"  {problem}")
    if problems and not args.force:
        print("整批不寫入。修好結果檔再跑一次(或 --force 強行寫入)。")
        return 1
    if args.dry_run:
        print("--dry-run:未寫入任何檔案。")
        return 0

    cards = load_json(args.cards)
    faqs = load_json(args.faq_info)
    entries, report = build_tag_cards(cards, faqs, existing=sheet,
                                      splits=load_optional(args.splits),
                                      modern_ja=load_modern_ja())
    conflicts = report["tag_rule_vs_llm"] + report["timing_rule_vs_llm"]
    if conflicts:
        # 第四道關卡:規則層與本批判定寫入後打架,下場與前三道相同——整批
        # 不寫入。默默寫入的話 seal 的零衝突關卡會在下一輪才炸,那時已分不出
        # 是哪一票帶進來的
        print(f"規則層與本批判定衝突 {len(conflicts)} 筆(規則要收緊,"
              f"或判定要覆核):")
        for row in conflicts[:20]:
            print(f"  {row}")
        if not args.force:
            print("整批不寫入。")
            return 1
    with open(args.sheet, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_tag_cards(entries))
    print(f"已寫出 {args.sheet}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
