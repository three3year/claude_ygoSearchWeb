"""建置效果標記表的 CLI 薄殼:卡片總表 + 補足情報 → tagcard 管線 → tag_cards.json。

效果標記表是**來源檔而非建置產物**(ADR-0001):輸出檔若已存在就當作既有標記表
餵回管線,人工修正與已判定的行因此活過每一次重跑。要完全重建請加
`--ignore-existing`——那會丟掉檔案裡所有 manual / official / llm 的判定。

[[拆句表]] `data/clause_splits.json` 同樣是來源檔(ADR-0003),存在就自動讀進來把
舊式無編號的整團切開。`--judgments` 可再餵一份判定結果檔,把類型合併進標記表——
兩者由 `merge_judgments.py` 依判定票的結果檔產生,這裡只負責讀。

順帶把效果類型規則清單回寫 `docs/effect_kind_rules.md`:規則的定義寫在
`script/tag_card/rules.py`,但覆蓋條數與對官方明示的一致率一律由這一次的全表
統計算出來後填進去,不靠人工計數(票06)。`--rules-doc` 可改路徑。

`--attribution-lists` 會把報告的三份人工清單(歸屬由判定決定、引號對不上、
明示句只提別卡名)完整寫成 JSON,方便逐條抽查。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/tag_card/build_tag_cards.py
    python script/tag_card/build_tag_cards.py --out 別處/tag_cards.json
"""
import argparse
import json
import os
import re
import sys

import rules
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_RULES_DOC,
                   DEFAULT_SPLITS, DEFAULT_TAG_CARDS, load_json, load_optional)
from tagcard import build_tag_cards, serialize_tag_cards

LIST_PREVIEW = 20  # 清單過長時只印前幾筆,完整內容看輸出檔
OPTIONAL_THRESHOLD = 0.98  # 必發/選發規則層的獨立驗證門檻(票04)
DIGEST_RE = re.compile(r"規則定義指紋:`([0-9a-f]+)`")

# 五種對位方式(spec 的階梯一~五)加上效果外文本的官方明示
LADDER_LABELS = (
    ("header", "標頭對位【①の効果について】"),
    ("seq", "序號引用對位『①』"),
    ("quote", "原文引用對位『效果原文』"),
    ("name_single", "卡名限定 + 單效果卡"),
    ("single", "無歸屬標記 + 單效果卡"),
    ("non_effect", "效果外文本(効果として扱いません 系列)"),
)
# 需要人工看的三份清單(票03 驗收項目)
ATTRIBUTION_LISTS = (
    ("attribution_deferred", "歸屬由判定決定"),
    ("quote_unmatched", "引號對不回本卡卡文"),
    ("other_card_only", "明示句只提到別張卡名"),
)


def print_splits(report, file=sys.stdout):
    """拆句表:套用了幾筆、拆出多少條,以及三道驗證各自的失敗筆數。"""
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p("")
    p(f"拆句表: 套用 {report['split_records']} 筆,"
      f"拆出效果句 {report['split_clauses']} 條,"
      f"因拆句新取得官方明示 {report['split_new_official']} 條")
    for key, label in (
            ("split_coverage_failed", "驗證一・無遺漏覆蓋不成立"),
            ("split_quote_violations", "驗證二・官方引用被拆點切開(必須為 0)"),
            ("split_stale", "驗證三・卡文已變動,退回整團"),
            ("split_malformed", "紀錄結構不合法(index 或雜湊)"),
            ("split_unused", "有紀錄但該段不是未拆的整團")):
        rows = report[key]
        p(f"  {label}: {len(rows)} 筆 {[r['id'] for r in rows[:LIST_PREVIEW]]}")


def print_judgments(report, file=sys.stdout):
    """判定結果合併:寫進去幾條、官方接手幾條,以及每一種沒寫進去的理由。"""
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p("")
    p(f"判定結果: 寫入 {report['judgment_clauses']} 條,"
      f"與官方明示一致而留 official {report['judgment_confirmed_by_official']} 條,"
      f"判定給的必發/選發 {report['optional_llm']} 條")
    for key, label in (
            ("judgment_blank", "判定者留空未判"),
            ("judgment_vs_rule", "與位置規則結論不同(未覆蓋)"),
            ("judgment_optional_dropped", "類型不承載必發/選發(已丟棄)"),
            ("judgment_overridden", "既有判定擋下本次判定(判定一次就算數)"),
            ("judgment_orphans", "結果檔對不到任何一行(必須為 0)")):
        rows = report[key]
        p(f"  {label}: {len(rows)} 筆")
        for row in rows[:LIST_PREVIEW]:
            extra = " ".join(f"{k}={v}" for k, v in row.items()
                             if k not in ("id", "section", "index"))
            p(clause_line(row, extra, indent="    "))


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


def print_merge(report, file=sys.stdout):
    """與既有標記表合併的結果:哪些判定被保留、哪些需要人工回頭看。"""
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p("")
    p("判定來源分布(本次寫出的標記表):")
    for source, count in report["source_counts"].items():
        p(f"  {source}: {count}")
    p(f"沿用既有判定: {report['preserved_judgments']} 條")
    p(f"遲到的官方明示升為 official: {report['late_official_upgrades']} 條")

    for key, label in (("needs_review", "待複查(雜湊變動或尚未清旗標)"),
                       ("late_official_conflicts", "遲到的官方明示與既有判定不一致"),
                       ("orphaned_judgments", "既有判定對不到任何一行"),
                       ("official_changed", "官方改了自己的裁定(已採新值)"),
                       ("rule_changed", "規則層重算後與既有不同")):
        rows = report[key]
        p(f"{label}: {len(rows)} 筆")
        for row in rows[:LIST_PREVIEW]:
            extra = " ".join(f"{k}={v}" for k, v in row.items()
                             if k not in ("id", "section", "index"))
            p(f"  id={row['id']} section={row['section']} "
              f"index={row['index']} {extra}")


def verdict_of(rate, threshold):
    return "PASS" if rate >= threshold else "FAIL"


def rule_verdict(row):
    """一條規則對官方明示的一致率與判讀。沒有官方明示可對照時不給判讀。"""
    if not row["attested"]:
        return None, "—"
    rate = row["agree"] / row["attested"]
    return rate, verdict_of(rate, rules.AGREEMENT_THRESHOLD)


def rule_status(row):
    if row["merged_into"]:
        return f"已併入 {row['merged_into']}"
    if row["applied"]:
        return "生效"
    return f"覆蓋不足 {rules.MIN_COVERAGE} 條,未上工"


def clause_line(row, tail, indent="  "):
    """報告裡指向單一效果句的一行,前綴一律是那三個穩定鍵。"""
    return (f"{indent}id={row['id']} section={row['section']} "
            f"index={row['index']} {tail}")


def print_rules(report, digest_changed, file=sys.stdout):
    """效果類型規則層:影子預測、獨立驗證,以及收斂條件的三個問題。"""
    p = lambda *a: print(*a, file=file)  # noqa: E731
    applied = [row for row in report["rules"] if row["applied"]]
    attested = sum(row["attested"] for row in applied)
    agree = sum(row["agree"] for row in applied)
    rate = agree / max(attested, 1)
    p("")
    p(f"效果類型規則層(只寫影子預測,不寫 kind):"
      f"{len(applied)} 條生效 / {len(report['rules'])} 條登記,"
      f"指紋 {report['rules_digest']}")
    p(f"規則清單自身的毛病(必須為 0): {len(report['rules_problems'])} 筆 "
      f"{report['rules_problems'][:LIST_PREVIEW]}")
    p(f"影子預測: {report['rule_predictions']} 條"
      f"(其中尚未判定、留給判定票對照的 {report['rule_predictions_pending']} 條)")
    p(f"與既有判定一致升為 llm_then_rule: {report['rule_upgrades']} 條")
    p(f"判別條件重疊且結論不同(必須為 0): {len(report['rule_overlaps'])} 筆")
    for row in report["rule_overlaps"][:LIST_PREVIEW]:
        p(clause_line(row, f"規則={'+'.join(row['rules'])} 結論={row['kinds']}"))

    p(f"獨立驗證(官方明示的 {attested} 條遮答案跑規則): {agree}/{attested} = "
      f"{100 * rate:.1f}% [{verdict_of(rate, rules.AGREEMENT_THRESHOLD)} "
      f"門檻 {100 * rules.AGREEMENT_THRESHOLD:.0f}%]")
    for row in report["rules"]:
        row_rate, row_verdict = rule_verdict(row)
        rate_text = "—" if row_rate is None else f"{100 * row_rate:.1f}%"
        p(f"  {row['id']:>4} {row['kind']:<12} 覆蓋 {row['coverage']:>5} "
          f"官方 {row['attested']:>5} 一致 {rate_text:>6} [{row_verdict}] "
          f"{rule_status(row)}")
    disagree = report["rule_official_disagree"]
    p(f"  與官方明示不一致(規則要收緊的線索): {len(disagree)} 筆")
    for row in disagree[:LIST_PREVIEW]:
        p(clause_line(row, f"規則={'+'.join(row['rules'])} "
                           f"官方={row['official']} 預測={row['predicted']}",
                      indent="    "))

    changed = report["rule_prediction_changed"]
    p(f"影子預測與既有標記表不同(規則改動的影響範圍): {len(changed)} 筆")
    for row in changed[:LIST_PREVIEW]:
        p(clause_line(row, f"{row['before'] or '—'} → {row['after'] or '—'}"))

    conflicts = report["rule_conflicts"]
    p(f"衝突清單(影子預測與判定不一致,資料未動): {len(conflicts)} 筆")
    for row in conflicts[:LIST_PREVIEW]:
        p(clause_line(row, f"規則={'+'.join(row['rules'])} "
                           f"既有={row['existing']} 預測={row['predicted']} "
                           f"source={row['source']}"))

    below = report["rule_below_threshold"]
    p("收斂條件:")
    p(f"  規則清單本輪有異動: {'是' if digest_changed else '否'}")
    p(f"  每條規則覆蓋 ≥ {rules.MIN_COVERAGE}: "
      f"{'否 ' + str(below) if below else '是'}")
    p(f"  衝突清單為空: {'是' if not conflicts else '否'}")
    converged = not digest_changed and not below and not conflicts
    p(f"  → {'已收斂' if converged else '未收斂'}")


def escape_cell(text):
    """表格欄位裡的 `|` 會把 markdown 的欄位切開,判別條件裡就有。"""
    return text.replace("|", "\\|")


def rules_doc_preamble(report):
    return [
        "# 效果類型規則清單",
        "",
        "<!-- 這份文件由 script/tag_card/build_tag_cards.py 產生,不要手改。 -->",
        "<!-- 規則定義寫在 script/tag_card/rules.py;覆蓋條數與一致率由建置流程"
        "統計後回寫。 -->",
        "",
        f"規則定義指紋:`{report['rules_digest']}`"
        "(定義有異動時才會變,覆蓋條數變動不算)",
        "",
        f"統計基準:{report['cards']:,} 張卡 / {report['rule_targets']:,} 條"
        "有日文原文的效果句(規則層的管轄範圍,前言段不在其中),"
        f"產出影子預測 {report['rule_predictions']:,} 條"
        f"(其中尚未判定 {report['rule_predictions_pending']:,} 條)。",
        "",
        "規則只寫 `rule_predicted` 影子預測,**不寫 `kind`**——每條規則都必須有一次"
        "獨立判定作對照(ADR-0002)。",
        f"覆蓋不足 {rules.MIN_COVERAGE} 條的規則視為過擬合的單卡特例,不進規則層。",
    ]


def rules_doc_registry(report):
    lines = [
        "## 規則清單",
        "",
        "| 編號 | 對應類型 | 掃描範圍 | 判別條件 | 覆蓋條數 | 新增票號 | 狀態 |",
        "|---|---|---|---|---|---|---|",
    ]
    return lines + [
        f"| {row['id']} | {row['kind']} | {row['scope']} | "
        f"{escape_cell(row['condition'])} | {row['coverage']} | "
        f"{row['ticket']} | {rule_status(row)} |"
        for row in report["rules"]]


def rules_doc_validation(report):
    lines = [
        "## 獨立驗證(以[[官方明示]]的效果句遮答案跑規則)",
        "",
        f"門檻 {100 * rules.AGREEMENT_THRESHOLD:.0f}%。未達門檻的規則不自動停用"
        "——那會把問題藏起來;它會一直標成 FAIL,直到判別條件收緊或使用者判定"
        "官方那一行是特例。",
        "",
        "| 編號 | 官方明示條數 | 一致 | 不一致 | 一致率 | 判讀 |",
        "|---|---|---|---|---|---|",
    ]
    for row in report["rules"]:
        rate, verdict = rule_verdict(row)
        rate_text = "—" if rate is None else f"{100 * rate:.1f}%"
        lines.append(f"| {row['id']} | {row['attested']} | {row['agree']} | "
                     f"{row['disagree']} | {rate_text} | {verdict} |")
    lines += ["", "不一致的逐條清單(規則要不要收緊,看的就是這幾行):", ""]
    return lines + ([f"- {'+'.join(row['rules'])} `{row['id']}` "
                     f"section={row['section']} index={row['index']} "
                     f"官方={row['official']} 規則={row['predicted']}"
                     for row in report["rule_official_disagree"]] or ["(無)"])


def rules_doc_changes(report):
    lines = ["## 變更記錄", "",
             "規則變更僅限三種情況,每次都要記理由與票號:"]
    lines += [f"- `{key}` —— {label}"
              for key, label in rules.CHANGE_REASONS.items()]
    changes = [(row, change) for row in report["rules"]
               for change in row["changes"]]
    lines += [""]
    lines += [f"- {row['id']} {change['ticket']} "
              f"`{change['reason']}` {change['note']}"
              for row, change in changes] or ["(尚無變更)"]
    lines += ["", "合併記錄(舊條標記合併去向而不刪行):", ""]
    return lines + ([f"- {' + '.join(sorted(sources))} → {target}"
                     for target, sources
                     in sorted(rules.merged_groups().items())]
                    or ["(尚無合併)"])


def render_rules_doc(report):
    """報告 → docs/effect_kind_rules.md 的內容。

    規則的定義來自 `rules.py`,數字全部來自這一次的全表統計——覆蓋條數不靠人工
    計數是 票06 的驗收項目,所以這份文件是產出物而不是手寫檔。
    """
    sections = (rules_doc_preamble(report), rules_doc_registry(report),
                rules_doc_validation(report), rules_doc_changes(report))
    # 每一節後面補一個空行,最後那個空行就是檔案結尾的換行
    return "\n".join(line for section in sections
                     for line in [*section, ""])


def write_rules_doc(path, report):
    """回寫規則清單;回傳規則定義本輪是否有異動(收斂條件的第一問)。"""
    previous = None
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            match = DIGEST_RE.search(f.read())
        previous = match.group(1) if match else None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_rules_doc(report))
    return previous != report["rules_digest"]


def print_report(report, digest_changed=False, file=sys.stdout):
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
    p(f"● 子效果拆出: {report['bullet_clauses']} 條"
      f",拆開的母句 {report['bullet_quote_splits']} 段由行內『●…』引用授權、"
      f"其餘由【●…について】標頭")
    for key, label in (
            ("bullet_split_mismatch", "繁中/日文 ● 數量不一致,未拆"),
            ("bullet_coverage_failed", "驗證一・● 分項串接不等於原文(必須為 0)"),
            ("bullet_quote_violations", "驗證二・官方引用橫跨 ● 拆點,未拆")):
        rows = report[key]
        p(f"  {label}: {len(rows)} 段 "
          f"{[r['id'] for r in rows[:LIST_PREVIEW]]}")

    print_splits(report, file=file)

    print_optional(report, file=file)

    print_rules(report, digest_changed, file=file)

    print_judgments(report, file=file)

    print_merge(report, file=file)

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


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置效果標記表(拆句骨架)")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表 JSON (預設 data/cards.json)")
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO,
                        help="補足情報 JSON (預設 data/sources/faq_info.json)")
    parser.add_argument("--out", default=DEFAULT_TAG_CARDS,
                        help="輸出 JSON 路徑 (預設 data/tag_cards.json)")
    parser.add_argument("--splits", default=DEFAULT_SPLITS,
                        help="拆句表 JSON (預設 data/clause_splits.json;"
                             "檔案不存在就當作全部未拆)")
    parser.add_argument("--judgments", action="append", default=[],
                        help="判定結果 JSON,可重複指定")
    parser.add_argument("--rules-doc", default=DEFAULT_RULES_DOC,
                        help="效果類型規則清單的回寫路徑 "
                             "(預設 docs/effect_kind_rules.md)")
    parser.add_argument("--attribution-lists",
                        help="把三份人工清單完整寫成 JSON 的路徑")
    parser.add_argument("--ignore-existing", action="store_true",
                        help="不讀既有標記表,從零重建(會丟掉既有判定)")
    args = parser.parse_args(argv)

    existing = None
    if not args.ignore_existing and os.path.exists(args.out):
        existing = load_json(args.out)
        print(f"既有標記表: {args.out}({len(existing)} 張卡)")

    splits = load_optional(args.splits)
    if splits:
        print(f"拆句表: {args.splits}({len(splits)} 筆)")
    judgments = [record for path in args.judgments
                 for record in load_json(path)]
    if judgments:
        print(f"判定結果: {len(args.judgments)} 檔 / {len(judgments)} 張卡")

    entries, report = build_tag_cards(load_json(args.cards),
                                      load_json(args.faq_info),
                                      existing=existing, judgments=judgments,
                                      splits=splits)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_tag_cards(entries))

    if args.attribution_lists:
        lists = {key: report[key] for key, _ in ATTRIBUTION_LISTS}
        with open(args.attribution_lists, "w", encoding="utf-8",
                  newline="\n") as f:
            json.dump(lists, f, ensure_ascii=False, indent=2)
            f.write("\n")

    rules_changed = write_rules_doc(args.rules_doc, report)
    print_report(report, digest_changed=rules_changed)
    print(f"已寫出 {args.out} 與 {args.rules_doc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
