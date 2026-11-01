"""分詞統計報表(票 effect-tokenize#03):三件套 → report.md + wordfreq.json。

讀 tokens.json(tokenize.py 的輸出)與 lexicon.json,產出:
1. 詞頻表(top 100 入報表;全量存 wordfreq.json,效果句/效果外分列)
2. OOV 統計(token 數佔比、字數佔比、零 OOV 句覆蓋、高頻 OOV 段 top 100
   ——補詞迭代的輸入)
3. 正規化後句型模板分佈(NAME/NUM 收斂成佔位、OOV 段保留字面;同一 token
   序列=同一模板;top 50 各附例句+模板大小分佈直方圖)
4. 動作框架覆蓋率(frames.json 存在時;票 05):有抽到框架的句比例、位置/極性
   分佈、動作詞元 top 50——儀表板參考,不是通過門檻
5. 新欄填充率(frame-args-v4)與具名查詢目錄(named-queries 票 09;frame_queries.json
   存在時):節點數、三個位置的命中框數分佈(命中 0/1/2/3+ 個具名查詢的框數)、不留清單

統計單位是效果句(ADR-0015:一個編號效果的全文,連同它的 ● 選項;tokens.json
一筆就是一句,拆開的領起句與子效果句已由 tokenize.py 接回一段)。效果外文本
(stratum=extra,素材行/使用次數限制等)與效果層(effect;含子效果句的效果句
一律算效果層)全程分開統計——素材行句型單一,混著算會稀釋效果句的模板分佈。
模板裡的 ● 以符號顯示(選項邊界 token,不計入內容 token)。

冪等:同一份輸入重跑,輸出逐位元組相同(排序全部固定、不寫時間戳)。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/report.py
"""
import json
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
LEXICON = os.path.join(_HERE, "lexicon.json")
TOKENS = os.path.join(_HERE, "tokens.json")
FRAMES = os.path.join(_HERE, "frames.json")
QUERIES = os.path.join(_HERE, "frame_queries.json")   # catalog_hits.py 的命中中間產物(一框一列)
OUT_MD = os.path.join(_HERE, "report.md")
OUT_FREQ = os.path.join(_HERE, "wordfreq.json")

STRATA = (("effect", "效果句"), ("extra", "效果外文本"))
FREQ_TOP = {"effect": 100, "extra": 50}   # 詞頻表列數(prepare_view.py 共用)
# 模板大小分佈的桶(句數下限,遞減檢查)
BUCKETS = ((100, "≥100 句"), (50, "50–99 句"), (20, "20–49 句"),
           (10, "10–19 句"), (5, "5–9 句"), (2, "2–4 句"), (1, "1 句"))
# 一框命中幾個具名查詢的桶(2026-11-01 規格 2 票 09 定:拆解頁總覽與報告同一把尺)
HIT_BUCKETS = ("0", "1", "2", "3+")


def load():
    with open(LEXICON, encoding="utf-8") as f:
        lexicon = json.load(f)
    with open(TOKENS, encoding="utf-8") as f:
        sentences = json.load(f)
    return lexicon, sentences


def token_kind(token):
    if token.startswith("W"):
        return "lex"
    if token.startswith("d:"):
        return "dem"
    if token.startswith("q:"):
        return "quant"
    if token.startswith("k:"):
        return "cname"
    if token.startswith("a:"):
        return "attr"
    if token.startswith("m:"):
        return "method"
    if token.startswith("s:"):
        return "elided"
    if token.startswith("r:"):
        return "range"
    if token.startswith("p:"):
        return "particle"
    if token.startswith("NAME:"):
        return "name"
    if token.startswith("NUM:"):
        return "num"
    if token.startswith("c:"):
        return "counter"
    if token.startswith("?:"):
        return "oov"
    return "punct"


def make_render(surface_of):
    """token → 人讀形(詞典詞原樣、助詞[x]、NAME《名》、NUM〈n〉、量詞原樣、
    OOV ((x))、句讀原樣)。"""
    def render(token):
        kind = token_kind(token)
        if kind == "lex":
            return surface_of[token]
        if kind == "dem":
            _, dem, wid = token.split(":", 2)
            return dem + surface_of[wid]
        if kind == "quant":
            _, wid, _val, counter, cmp_word = token.split(":", 4)
            return (surface_of[wid] if wid else "") + "〈n〉" + counter + cmp_word
        if kind == "cname":
            return "〈%s〉カウンター" % (token[2:] or "名")
        if kind == "attr":
            return token[2:]
        if kind == "method":
            return token[2:]
        if kind == "elided":
            _, head, wid = token.split(":", 2)
            return "%s(%s)" % (head, surface_of[wid][len(head):])
        if kind == "range":
            return "〈n～n〉" + token.split(":", 3)[3]
        if kind == "particle":
            return "[%s]" % token[2:]
        if kind == "name":
            return "《名》"
        if kind == "num":
            return "〈n〉"
        if kind == "counter":
            return token[2:]
        if kind == "oov":
            return "((%s))" % token[2:]
        return token
    return render


def normalize(token):
    """模板鍵:NAME/NUM 收斂(數量約束只收斂數值)、其餘照 token。"""
    kind = token_kind(token)
    if kind == "name":
        return "NAME"
    if kind == "num":
        return "NUM"
    if kind == "quant":
        _, wid, _val, counter, cmp_word = token.split(":", 4)
        return "q:%s:n:%s:%s" % (wid, counter, cmp_word)
    if kind == "cname":
        return "k:"
    if kind == "range":
        return "r:n:n:" + token.split(":", 3)[3]
    return token


def token_chars(token, kind):
    """token 蓋住的原文字數(近似:NAME 算引號內文、NUM 算正規化後位數)。"""
    if kind in ("lex", "punct"):
        return len(token) if kind == "punct" else None   # lex 由呼叫端查表
    if kind == "particle" or kind == "counter":
        return len(token) - 2
    if kind in ("name", "oov"):
        return len(token.split(":", 1)[1])
    if kind == "num":
        return len(token.split(":", 1)[1])
    return len(token)


def scan_stratum(sentences, surface_len):
    """單一 stratum 的句子 → 統計包。"""
    stats = {
        "sentences": len(sentences),
        "cards": len({s["card"] for s in sentences}),
        "content_tokens": 0,
        "oov_tokens": 0,
        "content_chars": 0,
        "oov_chars": 0,
        "zero_oov_sentences": 0,
    }
    freq = Counter()
    oov_freq = Counter()
    templates = defaultdict(list)
    for pos, s in enumerate(sentences):
        has_oov = False
        for token in s["tokens"]:
            kind = token_kind(token)
            if kind == "punct":
                continue
            stats["content_tokens"] += 1
            if kind == "lex":
                chars = surface_len[token]
                freq[("詞典", token)] += 1
            elif kind == "dem":
                _, dem, wid = token.split(":", 2)
                chars = len(dem) + surface_len[wid]
                freq[("指示綁定", token)] += 1
            elif kind == "quant":
                _, wid, val, counter, cmp_word = token.split(":", 4)
                chars = ((surface_len[wid] if wid else 0) + len(val)
                         + len(counter) + len(cmp_word))
                freq[("數量約束", normalize(token))] += 1
            elif kind == "cname":
                chars = len(token) - 2 + len("カウンター")
                freq[("計數器名", "k:")] += 1
            elif kind == "attr":
                chars = len(token) - 2
                freq[("屬性字", token)] += 1
            elif kind == "method":
                chars = len(token) - 2
                freq[("召喚法", token)] += 1
            elif kind == "elided":
                chars = len(token.split(":", 2)[1])
                freq[("列舉前項", token)] += 1
            elif kind == "range":
                _, lo, hi, counter = token.split(":", 3)
                chars = len(lo) + 1 + len(hi) + len(counter)
                freq[("數字範圍", normalize(token))] += 1
            else:
                chars = token_chars(token, kind)
                if kind == "particle":
                    freq[("助詞", token)] += 1
                elif kind == "name":
                    freq[("NAME", "NAME")] += 1
                elif kind == "num":
                    freq[("NUM", "NUM")] += 1
                elif kind == "counter":
                    freq[("量詞", token)] += 1
                else:
                    stats["oov_tokens"] += 1
                    stats["oov_chars"] += chars
                    oov_freq[token[2:]] += 1
                    has_oov = True
            stats["content_chars"] += chars
        if not has_oov:
            stats["zero_oov_sentences"] += 1
        templates[tuple(normalize(t) for t in s["tokens"])].append(pos)
    return stats, freq, oov_freq, templates


def freq_rows(freq, surface_of):
    """Counter[(類別, token)] → 排序後的列(count 降冪、同數依表面)。"""
    rows = []
    for (cat, token), count in freq.items():
        if cat == "詞典":
            surface = surface_of[token]
            label = "%s(%s)" % (surface, token)
        elif cat == "指示綁定":
            _, dem, wid = token.split(":", 2)
            surface = dem + surface_of[wid]
            label = "%s(%s+%s)" % (surface, dem, wid)
        elif cat == "數量約束":
            _, wid, _val, counter, cmp_word = token.split(":", 4)
            surface = ((surface_of[wid] if wid else "")
                       + "〈n〉" + counter + cmp_word)
            label = surface
        elif cat == "計數器名":
            surface = "〈名〉カウンター"
            label = surface
        elif cat == "屬性字":
            surface = token[2:]
            label = surface
        elif cat == "召喚法":
            surface = token[2:]
            label = surface
        elif cat == "數字範圍":
            surface = "〈n～n〉" + token.split(":", 3)[3]
            label = surface
        elif cat == "列舉前項":
            _, head, wid = token.split(":", 2)
            surface = "%s(%s)" % (head, surface_of[wid][len(head):])
            label = surface
        elif cat == "助詞":
            surface = token[2:]
            label = surface
        elif cat == "量詞":
            surface = token[2:]
            label = surface
        else:
            surface = cat
            label = "〈%s〉" % ("卡名" if cat == "NAME" else "數字")
        rows.append((count, cat, surface, label))
    rows.sort(key=lambda r: (-r[0], r[1], r[2]))
    return rows


def template_order(templates):
    """模板 → (句數降冪, 模板鍵) 排序的 (key, positions) 清單。"""
    return sorted(templates.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def coverage(ordered, top_n, total):
    covered = sum(len(positions) for _, positions in ordered[:top_n])
    return covered, (covered / total if total else 0.0)


def histogram(ordered):
    rows = []
    sizes = [len(positions) for _, positions in ordered]
    for floor, label in BUCKETS:
        upper = [s for s in sizes if s >= floor]
        sizes = [s for s in sizes if s < floor]
        if not upper and not rows:
            continue
        rows.append((label, len(upper), sum(upper)))
    return rows


def pct(x):
    return "%.2f%%" % (x * 100)


def frame_stats(frames):
    """frames.json 的紀錄 → (每 stratum 的 records/covered/frames/constraints,
    位置 Counter, 極性 Counter, 動作 Counter, 約束框架 類別·子類 Counter)。
    覆蓋=有任一種框架(動作或約束);位置/極性/動作只數動作框架。
    frames.py/prepare_view.py/report.py 共用,同一把尺。"""
    stats = {k: {"records": 0, "covered": 0, "frames": 0, "constraints": 0}
             for k, _ in STRATA}
    position, polarity, actions = Counter(), Counter(), Counter()
    constraints = Counter()
    for r in frames:
        st = stats[r["stratum"]]
        st["records"] += 1
        st["covered"] += bool(r["frames"])
        st["frames"] += len(r["frames"])
        for fr in r["frames"]:
            if fr.get("kind") == "約束":
                st["constraints"] += 1
                constraints[fr["category"] + (
                    "·" + fr["subtype"] if fr["subtype"] else "")] += 1
                continue
            position[fr["position"]] += 1
            polarity[fr["polarity"]] += 1
            actions[fr["action"]] += 1
    return stats, position, polarity, actions, constraints


def frames_section():
    """動作框架覆蓋率(票 05):frames.json 不存在時略過。"""
    if not os.path.exists(FRAMES):
        return []
    with open(FRAMES, encoding="utf-8") as f:
        frames = json.load(f)
    stats, position, polarity, actions, constraints = frame_stats(frames)
    lines = [
        "## 框架覆蓋率(票 05、約束框架票 01;儀表板參考)",
        "",
        "框架抽取 `frames.py` 讀 tokens.json 逐句抽述語錨點與論元(動作框架),並由"
        "句型認出約束框架(限制/時機/素材,`constraints.py`);覆蓋率=有抽到至少一個"
        "框架(任一種)的效果句比例(一句效果句含它的 ● 選項,ADR-0015)。",
        "",
        "| 項目 | 效果句 | 效果外文本 |",
        "|---|---|---|",
        "| 有框架的句 | {:,} / {:,}({}) | {:,} / {:,}({}) |".format(
            stats["effect"]["covered"], stats["effect"]["records"],
            pct(stats["effect"]["covered"] / max(1, stats["effect"]["records"])),
            stats["extra"]["covered"], stats["extra"]["records"],
            pct(stats["extra"]["covered"] / max(1, stats["extra"]["records"]))),
        "| 框架數 | {:,} | {:,} |".format(stats["effect"]["frames"],
                                          stats["extra"]["frames"]),
        "| 其中約束框架 | {:,} | {:,} |".format(stats["effect"]["constraints"],
                                               stats["extra"]["constraints"]),
        "",
        "位置分佈(動作框架):" + "、".join("%s %s" % (k, format(v, ","))
                                        for k, v in sorted(position.items())),
        "",
        "極性分佈(動作框架):" + "、".join("%s %s" % (k, format(v, ","))
                                        for k, v in sorted(polarity.items())),
        "",
        "約束框架分佈:" + ("、".join("%s %s" % (k, format(v, ","))
                                   for k, v in sorted(constraints.items()))
                          or "無"),
        "",
        "動作詞元 top 50(相異 %d 種):" % len(actions),
        "",
        "| # | 動作 | 框架數 |",
        "|---|---|---|",
    ]
    ordered = sorted(actions.items(), key=lambda kv: (-kv[1], kv[0]))
    for pos, (action, count) in enumerate(ordered[:50], 1):
        lines.append("| %d | %s | %s |" % (pos, action, format(count, ",")))
    lines.append("")
    return lines


def count_by_position(records, key):
    """frames.json 的紀錄 → Counter((框架[key] 的值, 位置)):只數有值的框架。第四版論元各模組的報告
    小節(否定形/方式/施事者來源)共用。"""
    counts = Counter()
    for rec in records:
        for fr in rec["frames"]:
            if fr.get(key):
                counts[(fr[key], fr["position"])] += 1
    return counts


def position_table(counts, rows, label):
    """Counter((值, 位置)) → markdown 表的行:值一列(依 rows 的順序)、位置一欄(代價/效果/條件)、合計一欄;
    label 是第一欄的欄名。constraints 在這裡才 import(constraints 載入時 import report,模組層級會循環)。"""
    from constraints import POSITIONS
    lines = ["| %s | %s | 合計 |" % (label, " | ".join(POSITIONS)), "|---|" + "---|" * (len(POSITIONS) + 1)]
    for value in rows:
        row = [counts[(value, pos)] for pos in POSITIONS]
        lines.append("| %s | %s | %s |" % (value, " | ".join(format(c, ",") for c in row), format(sum(row), ",")))
    return lines


def fill_rate_section(frames):
    """新欄填充率(frame-args-v4 票 01):一張表,列是各新欄×位置,欄是 enrich.FILL_STATES 與 空;
    列由 enrich.FILL_RATE_ROWS(各票註冊自己的新欄)決定。另附 enrich.REPORT_SECTIONS 的小節
    (其他類的中心詞/修飾語 top 100、回指回填 填/拒)。enrich 在這裡才 import:constraints 載入時
    import report,enrich 又 import constraints,模組層級會循環。"""
    import enrich
    from constraints import POSITIONS
    actions = [fr for r in frames for fr in r["frames"] if fr.get("kind") != "約束"]
    lines = [
        "## 新欄填充率(frame-args-v4)",
        "",
        "第四版論元(`enrich.py`,全部是新鍵、字面欄不動)各新欄在動作框架 {:,} 框裡的狀態數,分位置:"
        "有值=規則從字面算得;推得=依動作補的(原文沒寫);轉欄=所在的結構化值取自來源/取自で;"
        "取自子句=數量取自子句裡的 を+數量;回填=回指回填寫進的結構化值(目標的區域;字面欄不動);"
        "其他=落在封閉表「其他」類;空=沒有值。".format(len(actions)),
        "",
        "| 新欄 | 位置 | " + " | ".join(enrich.FILL_STATES) + " | 空 |",
        "|---|---|" + "---|" * (len(enrich.FILL_STATES) + 1),
    ]
    if not enrich.FILL_RATE_ROWS:
        lines.append("| (尚無列;各票在 enrich.FILL_RATE_ROWS 註冊自己的新欄) | | " + " | " * len(enrich.FILL_STATES) + " |")
    for name, state_of in enrich.FILL_RATE_ROWS:
        counts = {pos: Counter() for pos in POSITIONS}
        for fr in actions:
            counts[fr["position"]][state_of(fr) or "空"] += 1
        for pos in POSITIONS:
            c = counts[pos]
            lines.append("| %s | %s | %s | %s |" % (
                name, pos, " | ".join(format(c[state], ",") for state in enrich.FILL_STATES),
                format(c["空"], ",")))
    lines.append("")
    for title, section_of in enrich.REPORT_SECTIONS:
        lines += ["### " + title, ""] + list(section_of(frames)) + [""]
    return lines


def hit_distribution(hits):
    """命中紀錄(frame_queries.json 的列:position、queries)→ {位置: Counter(HIT_BUCKETS 的桶)}:
    一框命中 0/1/2/3+ 個具名查詢的框數,分位置。constraints 在這裡才 import(模組層級會循環)。"""
    from constraints import POSITIONS
    out = {position: Counter() for position in POSITIONS}
    for hit in hits:
        n = len(hit["queries"])
        out[hit["position"]][HIT_BUCKETS[min(n, len(HIT_BUCKETS) - 1)]] += 1
    return out


def patient_mode_section(hits):
    """動作對象(named-queries 票 04/05;code review 修正補的報告列):命中紀錄的 patient 欄(此卡/非此卡;皆非是
    null)→ 三值 × 位置的框數表。constraints 在這裡才 import(模組層級會循環)。"""
    from constraints import POSITIONS
    import patient
    counts = Counter((hit.get("patient") or patient.NEITHER, hit["position"]) for hit in hits)
    rows = (patient.SELF, patient.NONSELF, patient.NEITHER)
    return ["### 動作對象(此卡/非此卡/皆非)框數分位置", "",
            "每個動作框架動到的是不是此卡本身(`patient.py`,判定讀論元片語;匯出框列的 patient_mode 同一個判定,"
            "皆非不帶鍵)。", ""] + position_table(counts, rows, "動作對象") + [""]


def queries_section(cat, hits):
    """具名查詢目錄(named-queries 票 09):目錄(catalog.Catalog)與命中紀錄 → 小節的行——節點數(大類/中類/
    具名查詢,具名查詢再分詞元節點與葉)、三個位置的命中框數分佈、每框平均命中、不留清單(三個位置都沒命中的
    具名查詢;匯出步驟會擋下,這裡登的是中間產物的現況)、動作對象的框數分位置。"""
    from constraints import POSITIONS
    major_nodes = sum(1 for node in cat.roots if node.predicate is None)
    middles = sum(len(m) for m in cat.middles.values())
    lemma_nodes = sum(1 for q in cat.queries if q.lemma_node)
    distribution = hit_distribution(hits)
    hit_names = {name for hit in hits for name in hit["queries"]}
    unmatched = [q.name for q in cat.queries if q.name not in hit_names]
    total = sum(len(hit["queries"]) for hit in hits)
    lines = [
        "## 具名查詢目錄(named-queries)",
        "",
        "動作類別第三版:類別樹退成具名查詢的目錄(`catalog.json`),每個節點是一個框架述詞,動作框架可同時命中"
        "幾個、不互斥、沒有預設葉;三個位置都算。命中由 `catalog_hits.py` 對匯出框列用參考評估器算"
        "(`frame_queries.json`);大類/中類是底下具名查詢的聯集。沒有「未歸」——沒命中任何具名查詢的框"
        "只是目錄還沒開那個述詞。",
        "",
        "節點數:頂層 %d(大類 %d、自成大類的具名查詢 %d)、中類 %d、具名查詢 %d(詞元節點 %d、葉 %d)。" % (
            len(cat.roots), major_nodes, len(cat.roots) - major_nodes, middles, len(cat.queries), lemma_nodes,
            len(cat.queries) - lemma_nodes),
        "",
        "一框命中幾個具名查詢(動作框架 {:,};合計 {:,} 框·查詢,每框平均 {:.2f}):".format(
            len(hits), total, total / max(1, len(hits))),
        "",
        "| 命中數 | " + " | ".join(POSITIONS) + " | 合計 |",
        "|---|" + "---|" * (len(POSITIONS) + 1),
    ]
    for bucket in HIT_BUCKETS:
        row = [distribution[position][bucket] for position in POSITIONS]
        lines.append("| %s | %s | %s |" % (bucket, " | ".join(format(c, ",") for c in row), format(sum(row), ",")))
    lines += ["",
              "不留(三個位置都沒命中)%s" % (
                  "%d 個:%s" % (len(unmatched), "、".join(unmatched)) if unmatched else ":無"),
              ""]
    return lines + patient_mode_section(hits)


def main():
    lexicon, sentences = load()
    surface_of = {e["id"]: e["surface"] for e in lexicon}
    surface_len = {e["id"]: len(e["surface"]) for e in lexicon}
    render = make_render(surface_of)

    packs = {}
    for key, _ in STRATA:
        subset = [s for s in sentences if s["stratum"] == key]
        packs[key] = (subset,) + scan_stratum(subset, surface_len)

    # ── wordfreq.json(全量詞頻,兩 stratum 分列)──
    freq_out = {}
    for key, _ in STRATA:
        _, _, freq, _, _ = packs[key]
        freq_out[key] = [
            {"surface": surface, "type": cat, "count": count}
            for count, cat, surface, _ in freq_rows(freq, surface_of)]
    with open(OUT_FREQ, "w", encoding="utf-8", newline="\n") as f:
        json.dump(freq_out, f, ensure_ascii=False, indent=1)
        f.write("\n")

    # ── report.md ──
    lines = [
        "# 效果文分詞統計報表(新格式新卡層)",
        "",
        "<!-- 由 .scratch/effect-tokenize/report.py 產生,不要手改;"
        "詞典或語料更新後重跑 tokenize.py + report.py 即刷新。 -->",
        "",
        "語料:三級分類 TIER_NEW(新格式新卡)各段對上 `data/tag_cards.json` "
        "的逐句 `text_ja`,拆開的 ● 子效果句接回領起句成一句效果句(ADR-0015);"
        "分詞器 `tokenize.py`(詞典最長匹配+NAME/NUM/助詞正規化,切分慣例見 "
        "`conventions.md`)。效果外文本(素材行/使用次數限制等)與效果層(含子效果句"
        "的效果句一律算效果層)分開統計;「句」一律指效果句。",
        "",
    ]

    # 摘要
    eff = packs["effect"][1]
    ext = packs["extra"][1]
    eff_ordered = template_order(packs["effect"][4])
    ext_ordered = template_order(packs["extra"][4])
    eff_cov100 = coverage(eff_ordered, 100, eff["sentences"])
    lines += [
        "## 關鍵數字",
        "",
        "| 項目 | 效果句 | 效果外文本 |",
        "|---|---|---|",
        "| 句數 | {:,}({:,} 張卡) | {:,}({:,} 張卡) |".format(
            eff["sentences"], eff["cards"], ext["sentences"], ext["cards"]),
        "| 詞典詞數 | {:,}(lexicon.json,兩 stratum 共用) | 同左 |".format(
            len(lexicon)),
        "| OOV token 佔比 | {} | {} |".format(
            pct(eff["oov_tokens"] / eff["content_tokens"]),
            pct(ext["oov_tokens"] / ext["content_tokens"])),
        "| OOV 字數佔比 | {} | {} |".format(
            pct(eff["oov_chars"] / eff["content_chars"]),
            pct(ext["oov_chars"] / ext["content_chars"])),
        "| 零 OOV 句覆蓋 | {} | {} |".format(
            pct(eff["zero_oov_sentences"] / eff["sentences"]),
            pct(ext["zero_oov_sentences"] / ext["sentences"])),
        "| 模板總數 | {:,} | {:,} |".format(
            len(eff_ordered), len(ext_ordered)),
        "| top-100 模板覆蓋率 | {}({:,} 句) | {}({:,} 句) |".format(
            pct(eff_cov100[1]), eff_cov100[0],
            pct(coverage(ext_ordered, 100, ext["sentences"])[1]),
            coverage(ext_ordered, 100, ext["sentences"])[0]),
        "",
        "token 佔比的分母是內容 token(詞典詞+助詞+NAME+NUM+量詞+OOV,"
        "句讀邊界不計);字數佔比的分母是內容 token 蓋住的原文字數。",
        "",
    ]

    for key, label in STRATA:
        subset, stats, freq, oov_freq, templates = packs[key]
        ordered = template_order(templates)
        top_n = 50 if key == "effect" else 20
        freq_top = FREQ_TOP[key]
        lines += ["## %s" % label, ""]

        # 1. 詞頻表
        rows = freq_rows(freq, surface_of)
        lines += [
            "### 詞頻表(top %d;全量見 wordfreq.json)" % freq_top,
            "",
            "| # | 詞 | 類別 | 次數 |",
            "|---|---|---|---|",
        ]
        for pos, (count, cat, _, disp) in enumerate(rows[:freq_top], 1):
            lines.append("| %d | %s | %s | %s |"
                         % (pos, disp, cat, format(count, ",")))
        lines.append("")

        # 2. OOV
        oov_top = oov_freq.most_common()
        oov_top.sort(key=lambda kv: (-kv[1], kv[0]))
        lines += [
            "### OOV 統計",
            "",
            "- OOV token:{:,} / {:,}({})".format(
                stats["oov_tokens"], stats["content_tokens"],
                pct(stats["oov_tokens"] / stats["content_tokens"])),
            "- OOV 字數:{:,} / {:,}({})".format(
                stats["oov_chars"], stats["content_chars"],
                pct(stats["oov_chars"] / stats["content_chars"])),
            "- 零 OOV 句:{:,} / {:,}({})".format(
                stats["zero_oov_sentences"], stats["sentences"],
                pct(stats["zero_oov_sentences"] / stats["sentences"])),
            "- 相異 OOV 段:{:,} 種".format(len(oov_freq)),
            "",
            "高頻 OOV 段 top 100(補詞迭代的輸入):",
            "",
            "| # | OOV 段 | 次數 |",
            "|---|---|---|",
        ]
        for pos, (segment, count) in enumerate(oov_top[:100], 1):
            lines.append("| %d | `%s` | %s |"
                         % (pos, segment, format(count, ",")))
        lines.append("")

        # 3. 模板分佈
        cov_top = coverage(ordered, top_n, stats["sentences"])
        lines += [
            "### 句型模板分佈(top %d)" % top_n,
            "",
            "同一正規化 token 序列=同一模板(NAME/NUM 收斂成佔位,OOV 段保留"
            "字面)。top %d 覆蓋 %s 句(%s)。渲染:詞典詞原樣、`[x]`=助詞、"
            "`《名》`=卡名、`〈n〉`=數字、`((x))`=OOV 段。" % (
                top_n, format(cov_top[0], ","), pct(cov_top[1])),
            "",
        ]
        for pos, (template_key, positions) in enumerate(ordered[:top_n], 1):
            rendered = " ".join(
                render(t if t not in ("NAME", "NUM") else
                       ("NAME:" if t == "NAME" else "NUM:"))
                for t in template_key)
            lines.append("**#%d**(%s 句)`%s`"
                         % (pos, format(len(positions), ","), rendered))
            lines.append("")
            examples = []
            seen_text = set()
            for p in positions:
                s = subset[p]
                if s["text_ja"] in seen_text:
                    continue
                seen_text.add(s["text_ja"])
                examples.append(s)
                if len(examples) == 3:
                    break
            for s in examples:
                lines.append("- `%s` %s" % (s["card"], s["text_ja"]))
            lines.append("")

        # 長尾形狀
        lines += [
            "### 模板大小分佈(長尾形狀)",
            "",
            "| 模板大小 | 模板數 | 句數 |",
            "|---|---|---|",
        ]
        for bucket_label, n_templates, n_sentences in histogram(ordered):
            lines.append("| %s | %s | %s |" % (
                bucket_label, format(n_templates, ","),
                format(n_sentences, ",")))
        lines.append("")

    lines += frames_section()
    if os.path.exists(FRAMES):
        with open(FRAMES, encoding="utf-8") as f:
            lines += fill_rate_section(json.load(f))
    if os.path.exists(QUERIES):
        import catalog     # catalog → predicate → constraints → report:模組層級會循環,在這裡才 import
        with open(QUERIES, encoding="utf-8") as f:
            lines += queries_section(catalog.load(), json.load(f))

    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        f.write("\n")
    print("效果句 OOV token %s / 零OOV句 %s;效果外 OOV token %s"
          % (pct(eff["oov_tokens"] / eff["content_tokens"]),
             pct(eff["zero_oov_sentences"] / eff["sentences"]),
             pct(ext["oov_tokens"] / ext["content_tokens"])))
    print("效果句模板 %d 種(top50 覆蓋 %s)、效果外模板 %d 種"
          % (len(eff_ordered), pct(coverage(eff_ordered, 50,
                                            eff["sentences"])[1]),
             len(ext_ordered)))
    print("已寫出 %s 與 %s" % (OUT_MD, OUT_FREQ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
