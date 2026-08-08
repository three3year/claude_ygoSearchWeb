"""遮蔽測試的 CLI 薄殼(票07):抽樣 → 判定者作答 → 對答案。

    # 一、抽樣:從標記表的官方明示分層抽 300 條,遮掉補足情報裡的類型結論
    python script/tag_card/run_masked_test.py sample

    # 二、判定者只讀 sample.json 與 docs/effect_kind_guide.md,把判定寫成
    #     answers.json:[{"id":…, "section":…, "index":…, "kind":…}, …]
    #     判不出來的 kind 填 null(留空,不猜)。

    # 三、對答案:標準答案現場從標記表查回來,樣本檔不帶答案
    python script/tag_card/run_masked_test.py score

`--ambiguous` 指向[[已知歧義清單]](官方文本本身歧義的條目),那些條目不計入分母;
超過 5 條就代表六類邊界的定義本身有問題,直接判不通過(票07)。

判定的邏輯全在 masked.py 的兩個純函式裡,這裡只讀檔、寫檔、印報告。
"""
import argparse
import json
import os
import sys

import masked

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKDIR = os.path.join(ROOT, ".scratch", "tag-card", "masked-test")
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_INFO = os.path.join(ROOT, "data", "sources", "faq_info.json")
DEFAULT_TAG_CARDS = os.path.join(ROOT, "data", "tag_cards.json")
DEFAULT_SAMPLE = os.path.join(WORKDIR, "sample.json")
DEFAULT_ANSWERS = os.path.join(WORKDIR, "answers.json")
DEFAULT_AMBIGUOUS = os.path.join(WORKDIR, "ambiguous.json")

LIST_PREVIEW = 40


def load_json(path, default=None):
    if default is not None and not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def print_sample_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"樣本 {report['size']} 條(種子 {report['seed']})")
    p("逐類別:")
    for kind in masked.KINDS:
        p(f"  {kind:<14} 母體 {report['population'][kind]:>6} "
          f"配額 {report['quota'][kind]:>4} 抽出 {report['taken'][kind]:>4}")
    if report["shortfall"]:
        p(f"母體不足下限、全取的類別: {report['shortfall']}")


def print_score_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"樣本 {report['size']} 條,判定集合自檢: "
      f"對不回標記表 {len(report['stale'])}、"
      f"漏判 {len(report['missing'])}、多判 {len(report['extra'])}、"
      f"值域外 {len(report['invalid'])}、"
      f"歧義不在樣本內 {len(report['ambiguous_unknown'])}")
    for key, label in (("stale", "對不回標記表(樣本過期,請重抽)"),
                       ("missing", "漏判"), ("extra", "多判"),
                       ("invalid", "值域外的類型"),
                       ("ambiguous_unknown", "歧義不在樣本內")):
        for row in report[key][:LIST_PREVIEW]:
            p(f"  {label}: id={row['id']} section={row['section']} "
              f"index={row['index']}")

    ambiguous = report["ambiguous"]
    p(f"已知歧義(不計入分母): {len(ambiguous)} 條 "
      f"[上限 {masked.AMBIGUOUS_CAP}"
      f"{',已超過' if report['ambiguous_over_cap'] else ''}]")
    for row in ambiguous:
        p(f"  id={row['id']} section={row['section']} index={row['index']} "
          f"{row['reason']}")

    p("")
    p(f"逐類別 recall(門檻 {100 * masked.RECALL_THRESHOLD:.0f}%):")
    for kind, stats in sorted(report["per_kind"].items(),
                              key=lambda kv: masked.KINDS.index(kv[0])):
        rate = stats["recall"]
        verdict = "PASS" if rate is not None \
            and rate >= masked.RECALL_THRESHOLD else "FAIL"
        rate_text = "—" if rate is None else f"{100 * rate:.1f}%"
        p(f"  {kind:<14} {stats['correct']:>3}/{stats['scored']:<3} "
          f"= {rate_text:>6} [{verdict}] "
          f"(抽出 {stats['total']}、歧義排除 {stats['ambiguous']})")
    overall = report["overall"]
    accuracy = "—" if overall["accuracy"] is None \
        else f"{100 * overall['accuracy']:.1f}%"
    p(f"總體準確率(不作為門檻): {overall['correct']}/{overall['scored']} "
      f"= {accuracy}")

    p("")
    p(f"錯判 {len(report['errors'])} 條(其中留空 {len(report['blank'])} 條):")
    for row in report["errors"]:
        p(f"  id={row['id']} section={row['section']} index={row['index']} "
          f"{row['name_zh']}")
        p(f"    官方={row['official']} 判定={row['answered'] or '留空'}")
        p(f"    句型={row['text_ja']}")
    p("")
    p(f"→ {'PASS' if report['passed'] else 'FAIL'}")


def cmd_sample(args):
    entries = load_json(args.tag_cards)
    sample, report = masked.sample_masked(
        entries, load_json(args.cards), load_json(args.faq_info),
        size=args.size, per_kind_min=args.per_kind_min, seed=args.seed)
    dump_json(args.sample, sample)
    print_sample_report(report)
    print(f"已寫出 {args.sample}")
    return 0


def cmd_score(args):
    report = masked.score_masked(load_json(args.tag_cards),
                                 load_json(args.sample),
                                 load_json(args.answers),
                                 load_json(args.ambiguous, default=[]))
    print_score_report(report)
    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="\n") as f:
            print_score_report(report, file=f)
        print(f"已寫出 {args.report}")
    return 0 if report["passed"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="效果類型判定的遮蔽測試")
    parser.add_argument("--tag-cards", default=DEFAULT_TAG_CARDS,
                        help="效果標記表 (預設 data/tag_cards.json)")
    parser.add_argument("--sample", default=DEFAULT_SAMPLE,
                        help="遮蔽樣本檔路徑")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("sample", help="抽樣並產出遮蔽樣本檔")
    build.add_argument("--cards", default=DEFAULT_CARDS,
                       help="卡片總表 JSON (預設 data/cards.json)")
    build.add_argument("--faq-info", default=DEFAULT_FAQ_INFO,
                       help="補足情報 JSON (預設 data/sources/faq_info.json)")
    build.add_argument("--size", type=int, default=masked.DEFAULT_SIZE)
    build.add_argument("--per-kind-min", type=int,
                       default=masked.DEFAULT_PER_KIND_MIN)
    build.add_argument("--seed", type=int, default=masked.DEFAULT_SEED)
    build.set_defaults(func=cmd_sample)

    score = sub.add_parser("score", help="對答案並印出逐類別 recall 報告")
    score.add_argument("--answers", default=DEFAULT_ANSWERS,
                       help="判定結果 JSON")
    score.add_argument("--ambiguous", default=DEFAULT_AMBIGUOUS,
                       help="已知歧義清單 JSON(不存在時視為空)")
    score.add_argument("--report", help="把報告另存一份純文字的路徑")
    score.set_defaults(func=cmd_score)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
