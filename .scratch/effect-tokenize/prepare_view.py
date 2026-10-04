# -*- coding: utf-8 -*-
"""產生檢視頁資料 view_data.js(window.VIEW_DATA=...),以及 conventions.md
審閱鏡像的資料塊 JSON(mirror-data/,格式見 review-mirror skill 的「資料塊」)。

重用 report.py 的 token_kind/normalize/scan_stratum,保證與報表同一把尺。
決定性輸出:排序穩定、不讀時鐘。
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report  # noqa: E402

# tokenize.py 與標準庫同名:照檔案路徑載入,免得拿到標準庫的 tokenize
_spec = importlib.util.spec_from_file_location(
    "effect_tokenize", os.path.join(HERE, "tokenize.py"))
effect_tokenize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(effect_tokenize)

MIRROR_DIR = os.path.join(HERE, "mirror-data")

TOP_TEMPLATES = {"effect": 300, "extra": 150}
EXAMPLES_PER_TEMPLATE = 4
TOP_OOV = 100
TOP_FREQ = 100


def split_token(token):
    """token → [kind, payload](payload:詞典詞用 surface 查表後補)。"""
    if token == "NAME":               # 模板鍵的正規化形
        return ["name", "名"]
    if token == "NUM":
        return ["num", "n"]
    kind = report.token_kind(token)
    if kind == "lex":
        return [kind, token]          # 前端用 lexicon 表查 surface
    if kind == "dem":
        return [kind, token[2:]]      # "この:W0067",前端查表拼 surface
    if kind == "quant":
        return [kind, token[2:]]      # "W0139:4::以下",前端查表拼 surface
    if kind == "cname":
        return [kind, token[2:]]      # 計數器名("魔力";模板形為空)
    if kind == "attr":
        return [kind, token[2:]]      # 屬性("闇")
    if kind == "method":
        return [kind, token[2:]]      # 召喚法("融合"/"S")
    if kind == "punct":
        return [kind, token]
    return [kind, token.split(":", 1)[1]]


def main():
    lexicon, sentences = report.load()
    surface_of = {e["id"]: e["surface"] for e in lexicon}
    surface_len = {e["id"]: len(e["surface"]) for e in lexicon}

    with open(os.path.join(HERE, "conventions.md"), encoding="utf-8") as f:
        conventions = f.read()

    out = {"lexicon": surface_of, "strata": {}, "conventions": conventions}
    for key, label in (("effect", "效果句"), ("extra", "效果外文本")):
        subset = [s for s in sentences if s["stratum"] == key]
        stats, freq, oov_freq, templates = report.scan_stratum(
            subset, surface_len)
        ordered = report.template_order(templates)

        tpl_rows = []
        for template_key, positions in ordered[:TOP_TEMPLATES[key]]:
            examples = []
            for pos in positions[:EXAMPLES_PER_TEMPLATE]:
                s = subset[pos]
                examples.append({
                    "card": s["card"],
                    "text": s["text_ja"],
                    "tokens": [split_token(t) for t in s["tokens"]],
                })
            tpl_rows.append({
                "count": len(positions),
                "tokens": [split_token(t) for t in template_key],
                "examples": examples,
            })

        top_cov = sum(len(p) for _, p in ordered[:100]) / max(1, len(subset))
        oov_rows = sorted(oov_freq.items(), key=lambda kv: (-kv[1], kv[0]))

        # 每個 OOV 段的首見例句(語料順序決定性):卡片密碼+效果位置+原句
        oov_example = {}
        for s in subset:
            for t in s["tokens"]:
                if t.startswith("?:"):
                    seg = t[2:]
                    if seg not in oov_example:
                        oov_example[seg] = {
                            "card": s["card"],
                            "section": s["section"],
                            "index": s["index"],
                            "text": s["text_ja"],
                        }
        freq_rows = report.freq_rows(freq, surface_of)[:TOP_FREQ]

        out["strata"][key] = {
            "label": label,
            "sentences": len(subset),
            "cards": len({s["card"] for s in subset}),
            "templates": len(templates),
            "top100_coverage": round(top_cov * 100, 2),
            "oov_token_pct": round(stats["oov_token_pct"], 2)
                if "oov_token_pct" in stats else stats.get("oov_pct"),
            "stats": stats,
            "histogram": [
                {"bucket": b, "templates": t, "sentences": s2}
                for b, t, s2 in report.histogram(ordered)],
            "top_templates": tpl_rows,
            "top_oov": [
                {"seg": k, "count": v, "ex": oov_example.get(k)}
                for k, v in oov_rows[:TOP_OOV]],
            "top_freq": freq_rows,
        }

    # ensure_ascii=True:全檔純 ASCII(\uXXXX 轉義),不受伺服器 charset 影響
    js = "window.VIEW_DATA=" + json.dumps(
        out, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + ";"
    path = os.path.join(HERE, "view_data.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    print("written", path, len(js), "bytes")

    write_mirror_data(lexicon, sentences)


# ── 審閱鏡像的資料塊(conventions.md 引用;一個檔一張表)──

# 詞類別:分詞器的 7 類+句讀(序列裡的結構訊號,不編 ID);OOV 標警示
CLASSES = [
    {"id": "lex", "label": "詞典詞"},
    {"id": "dem", "label": "指示綁定(この/その+詞)"},
    {"id": "p", "label": "助詞"},
    {"id": "name", "label": "卡名/計數器名"},
    {"id": "num", "label": "數字/數量約束"},
    {"id": "ctr", "label": "量詞"},
    {"id": "punct", "label": "句讀"},
    {"id": "oov", "label": "OOV 未收錄", "warn": True},
]
CLASS_OF = {"lex": "lex", "attr": "lex", "method": "lex", "dem": "dem",
            "particle": "p", "name": "name", "cname": "name", "num": "num",
            "quant": "num", "counter": "ctr", "punct": "punct", "oov": "oov"}
# 待裁:全て/同じ 的兩種粒度(conventions.md 決策段)
COMPOUNDS = ("全て破壊", "同じレベル", "同じ数値")
STANDALONE = ("全て", "同じ")
EVIDENCE_EXAMPLES = 5


def token_cell(token, surface_of):
    """token(或模板鍵的正規化形)→ [類別, 字面]。模板鍵的 NAME/NUM/k:/
    q::n: 顯示成佔位(《名》/〈n〉/〈名〉カウンター),例句顯示原值。"""
    if token == "NAME":
        return ["name", "《名》"]
    if token == "NUM":
        return ["num", "〈n〉"]
    kind = report.token_kind(token)
    if kind == "lex":
        surface = surface_of[token]
    elif kind == "dem":
        _, dem, wid = token.split(":", 2)
        surface = dem + surface_of[wid]
    elif kind == "quant":
        _, wid, val, counter, cmp_word = token.split(":", 4)
        surface = ((surface_of[wid] if wid else "")
                   + ("〈n〉" if val == "n" else val) + counter + cmp_word)
    elif kind == "cname":
        surface = "〈%s〉カウンター" % (token[2:] or "名")
    elif kind == "name":
        surface = "「%s」" % token.split(":", 1)[1]
    elif kind == "punct":
        surface = token
    else:                               # attr/method/particle/num/counter/oov
        surface = token.split(":", 1)[1]
    return [CLASS_OF[kind], surface]


def examples_of(candidates, limit):
    """例句:依 candidates 的順序(語料順序)、原文去重,取前 limit 句。"""
    out, seen = [], set()
    for s in candidates:
        if s["text_ja"] in seen:
            continue
        seen.add(s["text_ja"])
        out.append(s)
        if len(out) == limit:
            break
    return out


def column(name, cell_type):
    return {"name": name, "type": cell_type}


def write_mirror_data(lexicon, sentences):
    surface_of = {e["id"]: e["surface"] for e in lexicon}
    surface_len = {e["id"]: len(e["surface"]) for e in lexicon}

    def seq(tokens):
        return [token_cell(t, surface_of) for t in tokens]

    tables = {}
    for key, _label in report.STRATA:
        subset = [s for s in sentences if s["stratum"] == key]
        _stats, freq, oov_freq, templates = report.scan_stratum(
            subset, surface_len)
        ordered = report.template_order(templates)

        tables["templates-%s.json" % key] = {
            "columns": [column("排名", "number"), column("句數", "number"),
                        column("模板", "tokens")],
            "key": "排名",
            "classes": CLASSES,
            "rows": [{
                "cells": [rank, len(positions), seq(template_key)],
                "detail": {
                    "columns": [column("卡號", "text"), column("原文", "text"),
                                column("切分", "tokens")],
                    "rows": [{"cells": [str(s["card"]), s["text_ja"],
                                        seq(s["tokens"])]}
                             for s in examples_of(
                                 (subset[p] for p in positions),
                                 EXAMPLES_PER_TEMPLATE)],
                },
            } for rank, (template_key, positions)
                in enumerate(ordered[:TOP_TEMPLATES[key]], 1)],
        }

        # 例句:原文裡該段出現次數最少、再取最短的句子(同分取語料順序)——
        # 鏡像會標出段的所有出現處,單字段(い/か/た)挑首見句會滿句都是標記
        example = {}
        for s in subset:
            for seg in {t[2:] for t in s["tokens"] if t.startswith("?:")}:
                rank_key = (s["text_ja"].count(seg), len(s["text_ja"]))
                if seg not in example or rank_key < example[seg][0]:
                    example[seg] = (rank_key, s)
        oov_rows = sorted(oov_freq.items(), key=lambda kv: (-kv[1], kv[0]))
        tables["oov-%s.json" % key] = {
            "columns": [column("排名", "number"), column("OOV 段", "text"),
                        column("次數", "number"), column("例句", "quote"),
                        column("卡號", "text")],
            "key": "OOV 段",
            "rows": [{"cells": [
                rank, seg, count,
                {"text": example[seg][1]["text_ja"], "marks": [seg]},
                str(example[seg][1]["card"])]}
                for rank, (seg, count) in enumerate(
                    oov_rows[:TOP_OOV], 1)],
        }

        tables["freq-%s.json" % key] = {
            "columns": [column("排名", "number"), column("詞", "text"),
                        column("類別", "text"), column("次數", "number")],
            "rows": [{"cells": [rank, label, cat, count]}
                     for rank, (count, cat, _surface, label) in enumerate(
                         report.freq_rows(freq, surface_of)[
                             :report.FREQ_TOP[key]], 1)],
        }

    tables["evidence-all-same.json"] = evidence_table(
        lexicon, sentences, surface_of)

    os.makedirs(MIRROR_DIR, exist_ok=True)
    for name, table in sorted(tables.items()):
        path = os.path.join(MIRROR_DIR, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(table, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print("written", path, os.path.getsize(path), "bytes")


def word_uses(tokens, wid):
    """詞 wid 在 token 序列裡出現幾次——含被綁進 d:(指示綁定)與 q:
    (數量約束的前詞)的出現。"""
    count = 0
    for t in tokens:
        kind = report.token_kind(t)
        count += (t == wid
                  or (kind == "dem" and t.split(":", 2)[2] == wid)
                  or (kind == "quant" and t.split(":", 2)[1] == wid))
    return count


def evidence_table(lexicon, sentences, surface_of):
    """決策證據:全て/同じ 的整詞形與獨立形各自的句數與例句。整詞形另附
    「拆開後」的切分——拿掉三個複合詞條重切同一句(其餘詞條不動)。"""
    id_of = {e["surface"]: e["id"] for e in lexicon}
    split = effect_tokenize.Tokenizer(
        [e for e in lexicon if e["surface"] not in COMPOUNDS])

    def seq(tokens):
        return [token_cell(t, surface_of) for t in tokens]

    def split_form(surface):
        """複合詞自身拆開後的形狀,如 同じ|数値(OOV)。"""
        return "|".join(text + ("(OOV)" if cls == "oov" else "")
                        for cls, text in seq(split.tokenize(surface)))

    rows = []
    # 裁定後詞典裡不再有的詞形不列(例如拆掉的複合詞條)
    for surface in [w for w in COMPOUNDS + STANDALONE if w in id_of]:
        wid = id_of[surface]
        uses = [(s, word_uses(s["tokens"], wid)) for s in sentences]
        hits = [s for s, n in uses if n]
        compound = surface in COMPOUNDS
        columns = [column("卡號", "text"), column("原文", "quote")]
        columns += ([column("現行切分", "tokens"), column("拆開後切分", "tokens")]
                    if compound else [column("切分", "tokens")])
        examples = []
        for s in examples_of(hits, EVIDENCE_EXAMPLES):
            cells = [str(s["card"]),
                     {"text": s["text_ja"], "marks": [surface]},
                     seq(s["tokens"])]
            if compound:
                cells.append(seq(split.tokenize(s["text_ja"])))
            examples.append({"cells": cells})
        rows.append({
            "cells": [surface,
                      "整詞(tag_rules 萃出)" if compound else "獨立詞(manual)",
                      len(hits), sum(n for _, n in uses),
                      split_form(surface) if compound else "—"],
            "detail": {"columns": columns, "rows": examples},
        })
    return {
        "columns": [column("詞形", "text"), column("現行切法", "text"),
                    column("句數", "number"), column("出現次數", "number"),
                    column("拆開後", "text")],
        "key": "詞形",
        "classes": CLASSES,
        "rows": rows,
    }


if __name__ == "__main__":
    main()
