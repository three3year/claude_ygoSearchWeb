"""建置效果標記表的 CLI 薄殼:卡片總表 + 補足情報 → tagcard 管線 → tag_cards.json。

`--attribution-lists` 會把報告的三份人工清單(歸屬由判定決定、引號對不上、
明示句只提別卡名)完整寫成 JSON,方便逐條抽查。

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
OPTIONAL_THRESHOLD = 0.98  # 必發/選發規則層的獨立驗證門檻(票04)

# 五種對位方式(spec 的階梯一~五)加上效果外文本的官方明示
LADDER_LABELS = (
    ("header", "標頭對位【①の効果について】"),
    ("seq", "序號引用對位『①』"),
    ("quote", "原文引用對位『效果原文』"),
    ("name_single", "卡名限定 + 單效果卡"),
    ("single", "無歸屬標記 + 單效果卡"),
    ("non_effect", "效果外文本(効果として扱いません)"),
)
# 需要人工看的三份清單(票03 驗收項目)
ATTRIBUTION_LISTS = (
    ("attribution_deferred", "歸屬由判定決定"),
    ("quote_unmatched", "引號對不回本卡卡文"),
    ("other_card_only", "明示句只提到別張卡名"),
)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def print_optional(report, file=sys.stdout):
    """必發/選發那一層與它的獨立驗證。"""
    p = lambda *a: print(*a, file=file)  # noqa: E731
    validation = report["optional_validation"]
    p("")
    p(f"必發/選發: 官方明示 {report['optional_official']} 條、"
      f"規則 {report['optional_rule']} 條、"
      f"留待判定 {len(report['optional_pending'])} 條")
    for value, count in report["optional_counts"].items():
        p(f"  {value}: {count}")
    p(f"官方說必發但類型未定(不寫值): {report['mandatory_kind_unknown']} 條")
    p(f"官方說必發但類型不發動(必須為 0): "
      f"{len(report['mandatory_other_kind'])} 條")
    p(f"optional 落在不該有值的類型上(必須為 0): "
      f"{len(report['optional_on_wrong_kind'])} 條")
    p(f"歸屬不確定的必發明示: {len(report['mandatory_deferred'])} 筆")

    rate = validation["agree"] / max(validation["predicted"], 1)
    verdict = "PASS" if rate >= OPTIONAL_THRESHOLD else "FAIL"
    p(f"獨立驗證(官方明示的必發 {validation['attested']} 條遮答案跑規則): "
      f"{validation['agree']}/{validation['predicted']} = {100 * rate:.1f}% "
      f"[{verdict} 門檻 {100 * OPTIONAL_THRESHOLD:.0f}%]")
    p(f"  規則無法預測而排除於分母: 未拆句 {validation['unsplit']}、"
      f"無日文卡文 {validation['no_text']}、"
      f"找不到發動子句 {validation['no_activation']}")
    disagree = validation["disagree"]
    # 未達門檻時列出全部,達標時只留樣本——不一致的句型是修規則的唯一線索
    full = verdict == "FAIL"
    shown = disagree if full else disagree[:LIST_PREVIEW]
    p(f"  不一致 {len(disagree)} 條"
      f"{'(全列)' if full else f'(前 {len(shown)} 條)'}:")
    for row in shown:
        p(f"    id={row['id']} section={row['section']} index={row['index']} "
          f"規則={row['predicted']} 發動子句={row['activation']}")


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

    coverage = report["official_coverage"]
    effects = report["clauses"] - report["preambles"]
    kinds = report["official_clauses"] - coverage["non_effect"]
    p("")
    p(f"官方明示: {report['official_clauses']} 條 "
      f"(效果類型 {kinds} / {effects} = {100 * kinds / max(effects, 1):.1f}%)")
    for key, label in LADDER_LABELS:
        p(f"  {label}: {coverage[key]}")
    p("效果類型分布:")
    for kind, count in report["kind_counts"].items():
        p(f"  {kind}: {count}")
    p(f"● 子效果拆出: {report['bullet_clauses']} 條,"
      f"繁中/日文 ● 數量不一致未拆: {len(report['bullet_split_mismatch'])} 段")

    print_optional(report, file=file)

    for key, label in ATTRIBUTION_LISTS:
        p(f"{label}: {len(report[key])} 筆")
    for key, label in (("seq_missing", "序號引用對不到編號(必須為 0)"),
                       ("header_index_missing", "標頭指名的編號卡文沒有"),
                       ("quote_ambiguous", "引號同時命中多個編號區段"),
                       ("kind_conflicts", "同一效果句被官方寫成兩種類型"),
                       ("kind_ambiguous", "同一行寫出多種類型"),
                       ("non_effect_outside_preamble", "效果外明示不在前言段")):
        rows = report[key]
        p(f"{label}: {len(rows)} 筆 {[r['id'] for r in rows[:LIST_PREVIEW]]}")

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
    parser.add_argument("--attribution-lists",
                        help="把三份人工清單完整寫成 JSON 的路徑")
    args = parser.parse_args(argv)

    entries, report = build_tag_cards(load_json(args.cards),
                                      load_json(args.faq_info))

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_tag_cards(entries))

    if args.attribution_lists:
        lists = {key: report[key] for key, _ in ATTRIBUTION_LISTS}
        with open(args.attribution_lists, "w", encoding="utf-8",
                  newline="\n") as f:
            json.dump(lists, f, ensure_ascii=False, indent=2)
            f.write("\n")

    print_report(report)
    print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
