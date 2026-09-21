"""tag 貼標期的定版驗收 CLI 薄殼(票10):跑一次全表 → 逐項驗收 → 印報告。

與效果類型的 `seal_report.py` 同構,**不寫任何檔**。關卡(spec 票10):

1. 體系定稿無異動 —— vocab 的 tag_digest 與批次/樣本產出時一致(值域正典自檢
   為空即體系合法;指紋寫在遮蔽樣本旁的 digest 檔,首次 seal 時落檔)。
2. 規則清單自檢為空、規則與 LLM 判定零衝突(tag 與時機各一)。
3. 遮蔽測試門檻 —— 對入版控的樣本與標準答案**現場重算**:逐規則錯標 0、
   框架 recall 達標、分母達標(全表命中不足 8 的規則以全量計)。
4. 當期類別零空缺 —— 已開貼類別粗篩命中的每一句,要嘛有該類 tag、要嘛有判定
   紀錄(tags_checked);觸發時機同理(粗篩命中而值仍空且未判空 = 空缺)。
5. tags / 時機值全在正典;時機只在承載類型上。
6. 冪等 fixpoint —— 磁碟上那一份就是管線的輸出。

用法:
    python script/tag_card/tag_seal_report.py
    python script/tag_card/tag_seal_report.py --out .scratch/effect-tag/seal.txt
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "web"))
import vocab  # noqa: E402

import masked_tags  # noqa: E402
import tag_rules  # noqa: E402
from seal_report import fixpoint_gate, gate, print_gates  # noqa: E402
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_SPLITS,  # noqa: E402
                   DEFAULT_TAG_CARDS, ROOT, load_json, load_modern_ja,
                   load_optional)
from tagcard import build_tag_cards  # noqa: E402

MASKED_DIR = os.path.join(ROOT, ".scratch", "effect-tag", "masked")
DIGEST_FILE = os.path.join(MASKED_DIR, "taxonomy-digest.txt")
# 遮蔽樣本與標準答案(入版控;類別 → 檔名前綴)
MASKED_SETS = {
    tag_rules.CAT_MOVE: ("mv-sample.json", "mv-sample-supplement.json",
                         "mv-sample-supplement2.json"),
    tag_rules.CAT_DESTROY: ("ds-sample.json", "ds-sample-supplement.json"),
    tag_rules.CAT_NEGATE: ("ng-sample.json", "ng-sample-supplement.json"),
    tag_rules.CAT_STAT: ("st-sample.json", "st-sample-supplement.json"),
    tag_rules.CAT_DAMAGE: ("dm-sample.json", "dm-sample-supplement.json"),
    tag_rules.CAT_HEAL: ("hp-sample.json",),
    tag_rules.CAT_LP_PAY: ("lpp-sample.json",),
    tag_rules.CAT_LP_LOSE: ("lpl-sample.json",),
    tag_rules.CAT_RESTRICT: ("rs-sample.json", "rs-sample-supplement.json"),
    tag_rules.CAT_PROTECT: ("pt-sample.json", "pt-sample-supplement.json"),
}
LIST_PREVIEW = 10


def read_recorded_digest():
    if not os.path.exists(DIGEST_FILE):
        return None
    with open(DIGEST_FILE, encoding="utf-8") as f:
        return f.read().strip() or None


def write_recorded_digest():
    os.makedirs(MASKED_DIR, exist_ok=True)
    with open(DIGEST_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(vocab.tag_digest() + "\n")


def masked_gates(entries, report):
    """逐類別現場重算遮蔽測試;回傳 (關卡列, 摘要列)。"""
    gates, summaries = [], []
    coverage = {row["id"]: row["coverage"] for row in report["tag_rules"]}
    for category, files in MASKED_SETS.items():
        sample, truth = [], []
        for name in files:
            sample += load_json(os.path.join(MASKED_DIR, name))
            truth += load_json(os.path.join(
                MASKED_DIR, name.replace("sample", "truth")))
        res = masked_tags.score_tag_masked(entries, sample, truth,
                                           category=category)
        wrong = sum(row["wrong"] for row in res["rules"])
        recall_fail = [row["id"] for row in res["rules"]
                       if row["fired"] and not row["passed"]]
        # 分母:樣本命中要達 8;全表命中本來就不足 8 的規則以全量計
        thin = [row["id"] for row in res["rules"]
                if row["fired"] < min(tag_rules.MASKED_MIN_HITS,
                                      coverage.get(row["id"], 0))]
        consistent = not (res["stale"] or res["missing"] or res["extra"]
                          or res["invalid"])
        gates += [
            gate(f"遮蔽・{category} 樣本一致(無 stale/missing/extra)",
                 consistent,
                 f"stale {len(res['stale'])} missing {len(res['missing'])} "
                 f"extra {len(res['extra'])} invalid {len(res['invalid'])}"),
            gate(f"遮蔽・{category} 逐規則錯標 0", wrong == 0,
                 f"{wrong} 筆"),
            gate(f"遮蔽・{category} 逐規則框架 recall ≥ "
                 f"{tag_rules.MASKED_MIN_RECALL:.0%}",
                 not recall_fail, f"{recall_fail}"),
            gate(f"遮蔽・{category} 逐規則樣本分母 ≥ "
                 f"{tag_rules.MASKED_MIN_HITS}(全表不足者全量計)",
                 not thin, f"{thin}"),
        ]
        summaries.append(
            f"  {category}: 樣本 {res['scored']} 句 / 標準答案 "
            f"{res['truth_tags']} 個 tag / 類別 recall "
            f"{res['category_recall']:.2%}")
    return gates, summaries


def all_gates(entries, report, sheet_path):
    recorded = read_recorded_digest()
    gates = [
        gate("值域正典自檢為空", not report["vocab_problems"],
             f"{report['vocab_problems'][:LIST_PREVIEW]}"),
        gate("體系定稿無異動(tag_digest 與紀錄一致)",
             recorded == vocab.tag_digest(),
             f"紀錄 {recorded}、現行 {vocab.tag_digest()};體系動過要重出"
             f"批次與樣本,或首次 seal 先 --record-digest"),
        gate("tag 規則清單自檢為空", not report["tag_rules_problems"],
             f"{report['tag_rules_problems'][:LIST_PREVIEW]}"),
        gate("規則與 LLM 判定零衝突(tag)",
             not report["tag_rule_vs_llm"],
             f"{len(report['tag_rule_vs_llm'])} 筆"),
        gate("規則與 LLM 判定零衝突(時機)",
             not report["timing_rule_vs_llm"],
             f"{len(report['timing_rule_vs_llm'])} 筆"),
        gate("當期類別零空缺(粗篩命中皆有 tag 或判定紀錄)",
             not report["tag_pending"],
             f"{len(report['tag_pending'])} 條 "
             f"{report['tag_pending'][:LIST_PREVIEW]}"),
        gate("觸發時機零空缺", not report["timing_pending"],
             f"{len(report['timing_pending'])} 條"),
        gate("tags 值全在正典", not report["tag_value_problems"],
             f"{report['tag_value_problems'][:LIST_PREVIEW]}"),
        gate("時機值全在正典且只在承載類型上",
             not (report["timing_value_problems"]
                  or report["timing_on_wrong_kind"]),
             f"值 {report['timing_value_problems'][:LIST_PREVIEW]} 承載 "
             f"{report['timing_on_wrong_kind'][:LIST_PREVIEW]}"),
    ]
    masked, summaries = masked_gates(entries, report)
    gates += masked
    gates.append(fixpoint_gate(entries, sheet_path))
    return gates, summaries


def audit(entries, report):
    """seal 專屬的逐句稽核(值域、承載、時機空缺),塞回 report。"""
    report["vocab_problems"] = vocab.problems()
    tag_value_problems = []
    timing_value_problems = []
    timing_zh = {e["zh"] for e in vocab.entries(vocab.TIMING)}
    for entry in entries:
        for clause in entry["clauses"]:
            for tag in clause["tags"]:
                code, problem = vocab.tag_code(tag)
                if code is None:
                    tag_value_problems.append(
                        {"id": entry["id"], "index": clause["index"],
                         "problem": problem})
            if (clause["timing"] is not None
                    and clause["timing"] not in timing_zh):
                timing_value_problems.append(
                    {"id": entry["id"], "index": clause["index"],
                     "timing": clause["timing"]})
    report["tag_value_problems"] = tag_value_problems
    report["timing_value_problems"] = timing_value_problems


def print_stats(report, summaries, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p("")
    p("## 首期統計")
    p("")
    p(f"  管轄範圍(新式效果句): {report['tag_scope_clauses']:,} 條")
    total = sum(report["tag_counts"].values())
    p(f"  tag 總數: {total:,}(類別分布 {dict(sorted(report['tag_counts'].items()))})")
    p(f"  tag 來源分布: {report['tag_src_counts']}")
    p(f"  判空紀錄(tags_checked): {report['tags_checked_counts']}")
    p(f"  觸發時機: 規則 {report['timing_rule_values']:,} 條 + 判定,"
      f"分布 {dict(sorted(report['timing_counts'].items()))}")
    p("")
    p("## 遮蔽測試(現場重算)")
    p("")
    for line in summaries:
        p(line)


def main(argv=None):
    parser = argparse.ArgumentParser(description="tag 貼標期的定版驗收(票10)")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_TAG_CARDS)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--record-digest", action="store_true",
                        help="把現行體系定稿指紋落檔(首次 seal / 新裁定後)")
    parser.add_argument("--out", help="把報告另存一份")
    args = parser.parse_args(argv)

    if args.record_digest:
        write_recorded_digest()
        print(f"已記錄體系定稿指紋 {vocab.tag_digest()} → {DIGEST_FILE}")

    entries, report = build_tag_cards(load_json(args.cards),
                                      load_json(args.faq_info),
                                      existing=load_optional(args.sheet),
                                      splits=load_optional(args.splits),
                                      modern_ja=load_modern_ja())
    audit(entries, report)
    gates, summaries = all_gates(entries, report, args.sheet)

    def render(file):
        cats = "、".join(sorted(tag_rules.PHASES,
                                key=lambda c: tag_rules.PHASES[c]))
        print(f"# 效果 Tag 定版報告(已開貼:{cats} + 觸發時機)", file=file)
        print("", file=file)
        ok = print_gates(gates, lambda *a: print(*a, file=file))
        print_stats(report, summaries, file=file)
        return ok

    ok = render(sys.stdout)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            render(f)
        print(f"已另存 {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
