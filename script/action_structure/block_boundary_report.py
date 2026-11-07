"""區塊邊界比對報告(純函式):舊式卡的規則切法對三方共識集比,一致幾張、不一致逐張列出。

接縫三(spec「測試決策」):共識集是 `stats/boundary_consensus.json` 的 `full_agree`
(拆句表、cdb 的①、英文三者效果數與邊界一致的 3,363 張),正解邊界直接取拆句表
`data/clause_splits.json` 該卡各段的 `text_ja`(照 `ja_order` 串接後與官方 DB 文本去空白全等,
docs/data_sources.md)。比的是**效果區塊的起點**(去空白後的字元位移):規則側取種類為編號效果的區塊,
共識側取 `index` 不以 0 開頭的段;素材、召喚條件、次數限制這些前言兩側都不算起點。
無共識的卡(`no_consensus`)規則照切,但沒有正解可比,清單交站主判、判完寫進邊界補丁。
邊界補丁的結果(生效 / 卡文已變動 / 覆蓋不成立 / 引用被切斷 / 格式不合法)一併列出。
"""
import re

from block_split import LIMIT_REASON, split_blocks

_WS_RE = re.compile(r"[\s　]+")
EFFECT_KIND = "編號效果"
NO_RECORD = "拆句表無紀錄"
COVERAGE_FAILED = "拆句表覆蓋不成立"


def _condense(text):
    return _WS_RE.sub("", text)


def consensus_units(record, text):
    """拆句表一筆 → [(index, text_ja, 壓縮位移)](照 ja_order);串接後與卡文不等回 None。"""
    segments = record.get("segments") or []
    order = record.get("ja_order") or list(range(len(segments)))
    if sorted(order) != list(range(len(segments))):
        return None
    units, pos = [], 0
    for k in order:
        piece = _condense(segments[k].get("text_ja") or "")
        units.append((segments[k]["index"], segments[k].get("text_ja") or "", pos))
        pos += len(piece)
    if "".join(_condense(u[1]) for u in units) != _condense(text):
        return None
    return units


def consensus_effect_starts(units):
    return {pos for index, _, pos in units if not index.startswith("0")}


def rule_units(text, blocks, omitted):
    """規則切出的單位(區塊與略過文本,依原文順序)→ [(種類, 字面, 壓縮位移)]。"""
    items = [(b["span"][0], b["kind"], b["text"]) for b in blocks
             if b["source"] == "card_text"]
    items += [(o["span"][0], LIMIT_REASON, o["text"]) for o in omitted
              if o["source"] == "card_text"]
    items.sort()
    return [(kind, piece, len(_condense(text[:start])))
            for start, kind, piece in items]


def rule_effect_starts(units):
    return {pos for kind, _, pos in units if kind == EFFECT_KIND}


def compare_card(faq_entry, record, patch=None):
    """一張卡:規則切法對拆句表 → {"agree", "reason", "rule", "consensus", "patch"}。"""
    text = faq_entry.get("card_text") or ""
    status = {}
    blocks, omitted = split_blocks(text, None, faq_entry.get("supplement"),
                                   {"card_text": patch} if patch else None,
                                   status)
    rule = rule_units(text, blocks, omitted)
    result = {"id": faq_entry["password"], "name_ja": faq_entry["name_ja"],
              "rule": rule, "consensus": None, "patch": status.get("card_text"),
              "agree": False, "reason": None}
    if record is None:
        result["reason"] = NO_RECORD
        return result
    units = consensus_units(record, text)
    if units is None:
        result["reason"] = COVERAGE_FAILED
        return result
    result["consensus"] = units
    result["agree"] = rule_effect_starts(rule) == consensus_effect_starts(units)
    return result


def compare_boundaries(faq_entries, consensus, splits, patches=None, cards=None):
    """全部共識集與無共識卡 → 報告資料。

    `consensus` 是 `boundary_consensus.json`(`full_agree`、`no_consensus`);`splits` 是拆句表
    列表;`patches` 是邊界補丁列表;`cards` 是卡片總表(無共識清單附卡名用)。
    """
    by_password = {entry["password"]: entry for entry in faq_entries}
    by_split = {(r["id"], r.get("section", "main")): r for r in splits or ()}
    by_patch = {(p["id"], p.get("source", "card_text")): p for p in patches or ()}
    names = {c["id"]: c for c in cards or ()}
    results, missing = [], []
    for cid in sorted(consensus.get("full_agree", ())):
        entry = by_password.get(cid)
        if entry is None:
            missing.append(cid)
            continue
        results.append(compare_card(entry, by_split.get((cid, "main")),
                                    by_patch.get((cid, "card_text"))))
    patch_status = {}
    for (cid, source), patch in sorted(by_patch.items()):
        entry = by_password.get(cid)
        if entry is None:
            patch_status.setdefault("無官方日文", []).append(cid)
            continue
        text = entry.get(source) or ""
        status = {}
        split_blocks(text if source == "card_text" else "",
                     text if source == "pen_effect" else None,
                     entry.get("supplement"), {source: patch}, status)
        patch_status.setdefault(status[source], []).append(cid)
    no_consensus = []
    for cid in sorted(consensus.get("no_consensus", ())):
        entry = by_password.get(cid)
        card = names.get(cid, {})
        no_consensus.append({
            "id": cid,
            "name_ja": entry["name_ja"] if entry else card.get("name_ja", ""),
            "name_zh": card.get("name_zh", "")})
    return {
        "consensus_total": len(consensus.get("full_agree", ())),
        "compared": len(results),
        "missing_text": missing,
        "agree": sum(1 for r in results if r["agree"]),
        "disagree": [r for r in results if not r["agree"]],
        "patches": patch_status,
        "no_consensus": no_consensus,
    }


def _unit_lines(units, label):
    return [f"  - {label}:`[{kind}]` {piece}" for kind, piece, _ in units]


def render_block_boundaries(report):
    """報告 md:不寫時間(同一輸入兩次產出相同),排序全部固定、列全部不截斷。"""
    agree, compared = report["agree"], report["compared"]
    rate = f"{agree / compared:.1%}" if compared else "—"
    lines = [
        "# 區塊邊界比對報告",
        "",
        "<!-- 由 script/action_structure/build_block_boundaries.py 產生,不要手改;"
        "改切分規則或邊界補丁後重跑即刷新。 -->",
        "",
        "舊式無編號卡的區塊切法(script/action_structure/block_split.py)對三方共識集比:"
        "共識集是 stats/boundary_consensus.json 的 full_agree(拆句表、cdb 的①、英文三者效果數與"
        "邊界一致的卡),正解邊界取 data/clause_splits.json 該卡各段的 text_ja。"
        "比的是效果區塊的起點;素材、召喚條件、次數限制這些前言兩側都不算起點。",
        "",
        "## 總覽",
        "",
        "| 項目 | 數 |",
        "|---|---|",
        f"| 共識集 | {report['consensus_total']} |",
        f"| 可比(有官方日文) | {compared} |",
        f"| 一致 | {agree} |",
        f"| 不一致 | {len(report['disagree'])} |",
        f"| 一致率 | {rate} |",
        f"| 無共識(交站主判) | {len(report['no_consensus'])} |",
        "",
    ]
    if report["missing_text"]:
        lines.append("共識集裡沒有官方日文的卡:" + ", ".join(map(str, report["missing_text"])))
        lines.append("")
    lines += ["## 邊界補丁", ""]
    if not report["patches"]:
        lines.append("沒有邊界補丁(data/block_boundaries.json 不存在或為空)。")
    for status, ids in sorted(report["patches"].items()):
        lines.append(f"- {status}({len(ids)} 張):{', '.join(map(str, ids))}")
    lines.append("")
    lines += [f"## 不一致({len(report['disagree'])} 張)", "",
              "每張列規則側與共識側的單位(依原文順序;`[編號效果]` 與 `[1]` `[2]`… 是效果區塊,"
              "其餘是前言);拆句表沒有紀錄或串接後與卡文不等的另註原因。", ""]
    for r in report["disagree"]:
        lines.append(f"- `{r['id']}` {r['name_ja']}" + (f"({r['reason']})" if r["reason"] else ""))
        lines += _unit_lines(r["rule"], "規則")
        if r["consensus"]:
            lines += _unit_lines(r["consensus"], "共識")
    lines.append("")
    lines += [f"## 無共識({len(report['no_consensus'])} 張,交站主判)", "",
              "拆句表與 cdb 的①效果數或邊界不同、英文與補足引用也沒站到一邊的卡。"
              "判完寫進 data/block_boundaries.json(一卡一筆:id、text_hash、blocks),規則先讀補丁。", "",
              "| 卡片密碼 | 日文卡名 | 中文卡名 |", "|---|---|---|"]
    for item in report["no_consensus"]:
        lines.append(f"| {item['id']} | {item['name_ja']} | {item['name_zh']} |")
    lines.append("")
    return "\n".join(lines)
