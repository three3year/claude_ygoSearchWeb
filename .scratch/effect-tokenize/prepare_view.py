# -*- coding: utf-8 -*-
"""產生檢視頁資料 view_data.js(window.VIEW_DATA=...)。

重用 report.py 的 token_kind/normalize/scan_stratum,保證與報表同一把尺。
決定性輸出:排序穩定、不讀時鐘。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report  # noqa: E402

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


if __name__ == "__main__":
    main()
