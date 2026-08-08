"""建置效果標記表的 CLI 薄殼:卡片總表 + 補足情報 → tagcard 管線 → tag_cards.json。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/tag_card/build_tag_cards.py
    python script/tag_card/build_tag_cards.py --out 別處/tag_cards.json
"""
import argparse
import json
import os
import sys

from tagcard import build_tag_cards, serialize_tag_cards

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_INFO = os.path.join(ROOT, "data", "sources", "faq_info.json")
DEFAULT_OUTPUT = os.path.join(ROOT, "data", "tag_cards.json")

LIST_PREVIEW = 20  # 清單過長時只印前幾筆,完整內容看輸出檔


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"卡片: {report['cards']} 張,效果句: {report['clauses']} 條")
    p(f"純通常怪獸(空 clauses): {report['pure_normal']} 張")
    p(f"靈擺段: {report['pendulum_sections']} 張,"
      f"丟棄怪獸敘述段: {report['flavor_dropped']} 張")
    p(f"前言段(效果外文本): {report['preambles']} 條")
    for role, count in report["role_counts"].items():
        p(f"  role={role}: {count}")
    p(f"別名註記(※)已從卡文尾端剝除: {report['footnote_stripped']} 張")
    p(f"無編號待拆: {len(report['pending_split'])} 段")
    p(f"confidence=low(該段無官方補足): {len(report['low_confidence'])} 張")
    p(f"無日文卡文: {len(report['no_japanese_text'])} 張 "
      f"{report['no_japanese_text'][:LIST_PREVIEW]}")

    p(f"繁中/日文編號數量不一致: {len(report['numeral_mismatch'])} 段")
    for row in report["numeral_mismatch"]:
        p(f"  id={row['id']} section={row['section']} "
          f"zh={row['zh'] or '—'} ja={row['ja'] or '—'}")
    p(f"繁中編號重複改採日文編號: {len(report['numeral_relabelled'])} 段")
    for row in report["numeral_relabelled"]:
        p(f"  id={row['id']} section={row['section']} "
          f"zh={row['zh']} ja={row['ja']}")
    p(f"前言段只有單邊有: {len(report['preamble_one_sided'])} 段")
    for row in report["preamble_one_sided"]:
        p(f"  id={row['id']} section={row['section']} 只有 {row['present']}")

    for key, label in (("empty_section_with_japanese", "繁中段落空但日文有文字"),
                       ("pendulum_bit_without_header", "有靈擺位元但卡文無靈擺標頭"),
                       ("header_without_pendulum_bit", "有靈擺標頭但無靈擺位元"),
                       ("normal_with_numerals", "通常怪獸卡文含編號"),
                       ("duplicate_index", "index 撞號(已加尾碼)"),
                       ("substring_violations", "非連續子字串(必須為 0)")):
        rows = report[key]
        p(f"{label}: {len(rows)} 筆 {rows[:LIST_PREVIEW]}")
    p(f"繁中兩條切割規則不一致(必須為 0): {report['zh_cut_rule_disagree']}")
    if report["unsupported_inputs"]:
        p(f"本票尚未支援的輸入(已忽略): {report['unsupported_inputs']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置效果標記表(拆句骨架)")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表 JSON (預設 data/cards.json)")
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO,
                        help="補足情報 JSON (預設 data/sources/faq_info.json)")
    parser.add_argument("--out", default=DEFAULT_OUTPUT,
                        help="輸出 JSON 路徑 (預設 data/tag_cards.json)")
    args = parser.parse_args(argv)

    entries, report = build_tag_cards(load_json(args.cards),
                                      load_json(args.faq_info))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_tag_cards(entries))

    print_report(report)
    print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
