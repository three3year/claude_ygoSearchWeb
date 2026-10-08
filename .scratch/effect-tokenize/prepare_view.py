# -*- coding: utf-8 -*-
"""產生檢視頁資料 view_data.js(window.VIEW_DATA=...)、卡片拆解分頁的分片
view_frames_<k>.js(window.VIEW_FRAMES[k]=...,依卡號分片、按需載入),以及
conventions.md 審閱鏡像的資料塊 JSON(mirror-data/,格式見 review-mirror skill
的「資料塊」)。

重用 report.py 的 token_kind/normalize/scan_stratum,保證與報表同一把尺;
框架資料讀 frames.json(frames.py 的輸出)。
決定性輸出:排序穩定、不讀時鐘;全部純 ASCII(\\uXXXX 轉義)避開伺服器 charset。
"""
import importlib.util
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report  # noqa: E402

# tokenize.py 與標準庫同名:照檔案路徑載入,免得拿到標準庫的 tokenize
_spec = importlib.util.spec_from_file_location(
    "effect_tokenize", os.path.join(HERE, "tokenize.py"))
effect_tokenize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(effect_tokenize)
import extract_seed  # noqa: E402

MIRROR_DIR = os.path.join(HERE, "mirror-data")
FRAMES = os.path.join(HERE, "frames.json")
CARDS = os.path.join(HERE, "..", "..", "data", "cards.json")
FRAME_SHARDS = 12
TOP_ACTIONS = 80

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
    if kind == "elided":
        return [kind, token[2:]]      # 列舉前項("通常:W0123",前端查表)
    if kind == "range":
        return [kind, token[2:]]      # 數字範圍("2:5:体";模板形 n:n:体)
    if kind == "punct":
        return [kind, token]
    return [kind, token.split(":", 1)[1]]


def main():
    lexicon, sentences = report.load()
    surface_of = {e["id"]: e["surface"] for e in lexicon}
    surface_len = {e["id"]: len(e["surface"]) for e in lexicon}

    with open(os.path.join(HERE, "conventions.md"), encoding="utf-8") as f:
        conventions = f.read()

    # 檢驗摘要(票 11):llm-check/summary.md 打包成「檢驗摘要」分頁
    summary_path = os.path.join(HERE, "llm-check", "summary.md")
    check_summary = ""
    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            check_summary = f.read()

    out = {"lexicon": surface_of, "strata": {}, "conventions": conventions,
           "check_summary": check_summary}
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

    out["frames"] = write_frame_shards(sentences, surface_of)
    print("框架字元範圍對齊失敗 %d 句" % out["frames"]["unaligned"])

    # ensure_ascii=True:全檔純 ASCII(\uXXXX 轉義),不受伺服器 charset 影響
    js = "window.VIEW_DATA=" + json.dumps(
        out, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + ";"
    path = os.path.join(HERE, "view_data.js")
    with open(path, "w", encoding="utf-8") as f:
        f.write(js)
    print("written", path, len(js), "bytes")

    write_mirror_data(lexicon, sentences)


# ── 卡片拆解(票 05/08/13/14):frames.json → 分片 + 索引/覆蓋率/盲區 ──

_SILENT = effect_tokenize.SILENT      # ● 不是靜默字元(選項邊界 token,ADR-0015)
_FULL = str.maketrans("０１２３４５６７８９ＳＸＰＬＡ？", "0123456789SXPLA?")
_KANJI_NUM = set("一二三四五六七八九十")


def _token_pattern(token, surface_of):
    """token → (原文字面, 是否放寬比對)。放寬:數字可是全形/漢數字、字母可是全形。"""
    kind = report.token_kind(token)
    if kind == "lex":
        return surface_of[token], False
    if kind == "dem":
        _, dem, wid = token.split(":", 2)
        return dem + surface_of[wid], False
    if kind == "name":
        return "「" + token.split(":", 1)[1] + "」", False
    if kind == "num":
        return token.split(":", 1)[1], True
    if kind == "quant":
        _, wid, val, counter, cmp_word = token.split(":", 4)
        return (surface_of[wid] if wid else "") + val + counter + cmp_word, True
    if kind == "range":
        _, lo, hi, counter = token.split(":", 3)
        return lo + "～" + hi + counter, True
    if kind == "cname":
        return token[2:] + "カウンター", False
    if kind == "elided":
        return token.split(":", 2)[1], False
    if kind == "method":
        return token[2:], True
    if kind == "punct":
        return token, False
    return token.split(":", 1)[1], False          # particle/attr/counter/oov


def _match(text, pos, pattern, flexible):
    """pattern 從 text[pos] 起比對;回結束位置,對不上回 -1。"""
    i, j = pos, 0
    while j < len(pattern):
        if i >= len(text):
            return -1
        ch = pattern[j]
        if flexible and ch.isdigit():
            while j < len(pattern) and pattern[j].isdigit():
                j += 1
            k = i
            while k < len(text) and (text[k].translate(_FULL).isdigit()
                                     or text[k] in _KANJI_NUM):
                k += 1
            if k == i:
                return -1
            i = k
            continue
        if text[i] == ch or (flexible and text[i].translate(_FULL) == ch):
            i, j = i + 1, j + 1
            continue
        return -1
    return i


def char_offsets(text, tokens):
    """每個 token 在原文的 [起,迄);整句對不上回 None(頁面就不高亮)。"""
    pos, out = 0, []
    for token in tokens:
        while pos < len(text) and text[pos] in _SILENT:
            pos += 1
        if not out and pos < len(text) and text[pos] == "：" and token != "：":
            pos += 1                      # 段首「①：」的冒號(分詞器剝掉)
            while pos < len(text) and text[pos] in _SILENT:
                pos += 1
        pattern, flexible = _token_pattern(token, _SURFACES)
        end = _match(text, pos, pattern, flexible)
        if end < 0:
            return None
        out.append((pos, end))
        pos = end
    return out


_SURFACES = {}


def span_chars(offsets, span):
    if offsets is None:
        return None
    start, end = span
    if start >= len(offsets) or end > len(offsets) or start >= end:
        return None
    return [offsets[start][0], offsets[end - 1][1]]

def write_frame_shards(sentences, surface_of):
    """frames.json 逐卡打包成 FRAME_SHARDS 個 view_frames_<k>.js;回傳要放進
    view_data.js 的索引(卡號/卡名/分片號)、覆蓋率與「抽不到框架的句子」。
    一筆是一句效果句(含 ● 選項);回傳值另附字元範圍對齊失敗的句數。"""
    _SURFACES.update(surface_of)
    with open(FRAMES, encoding="utf-8") as f:
        frames = json.load(f)
    with open(CARDS, encoding="utf-8") as f:
        names = {c["id"]: (c["name_ja"], c["name_zh"]) for c in json.load(f)}
    by_key = {(s["card"], s["section"], s["index"]): s for s in sentences}

    per_card = {}
    stats, position, polarity, actions = report.frame_stats(frames)
    uncovered = []
    unaligned = 0
    for r in frames:
        s = by_key[(r["card"], r["section"], r["index"])]
        # 原文字元範圍:框架的詞序列範圍對回 text_ja(對不上時為 null,頁面不高亮)
        offsets = char_offsets(s["text_ja"], s["tokens"])
        unaligned += offsets is None
        # 欄位:句序、位置、動作、極性、對象、來源、目的、子句、原文 [起,迄)、
        # 選項(第幾個 ●)、標籤;p=各段(標記句)的 index、效果類型、字元範圍
        rec = {"s": r["section"], "i": r["index"], "k": s["kind"],
               "st": r["stratum"], "t": s["text_ja"],
               "p": [[p["index"], p["kind"], p["start"], p["end"]]
                     for p in s["parts"]],
               "f": [[fr["sentence"], fr["position"], fr["action"],
                      fr["polarity"], fr.get("object"), fr.get("source"),
                      fr.get("goal"), fr["clause"],
                      span_chars(offsets, fr["span"]),
                      fr.get("option"), fr.get("label")] for fr in r["frames"]]}
        per_card.setdefault(r["card"], []).append(rec)
        if not r["frames"]:
            uncovered.append({"card": r["card"], "section": r["section"],
                              "index": r["index"], "stratum": r["stratum"],
                              "text": s["text_ja"]})

    card_ids = sorted(per_card)
    per_shard = -(-len(card_ids) // FRAME_SHARDS)
    index = []
    for k in range(FRAME_SHARDS):
        chunk = card_ids[k * per_shard:(k + 1) * per_shard]
        shard = {str(cid): per_card[cid] for cid in chunk}
        js = ("window.VIEW_FRAMES=window.VIEW_FRAMES||{};window.VIEW_FRAMES[%d]="
              % k) + json.dumps(shard, ensure_ascii=True,
                                separators=(",", ":"), sort_keys=True) + ";"
        path = os.path.join(HERE, "view_frames_%d.js" % k)
        with open(path, "w", encoding="utf-8") as f:
            f.write(js)
        print("written", path, len(js), "bytes")
        for cid in chunk:
            recs = per_card[cid]
            ja, zh = names.get(cid, ("", ""))
            index.append([cid, ja, zh, k, len(recs),
                          sum(len(r["f"]) for r in recs),
                          sum(1 for r in recs if not r["f"])])
    return {
        "shards": FRAME_SHARDS,
        "cards": index,
        "stats": stats,
        "position": [[k, v] for k, v in sorted(position.items())],
        "polarity": [[k, v] for k, v in sorted(polarity.items())],
        "top_actions": [[a, c] for a, c in sorted(
            actions.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_ACTIONS]],
        "distinct_actions": len(actions),
        "uncovered": uncovered,
        "unaligned": unaligned,
    }


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
CLASS_OF = {"lex": "lex", "attr": "lex", "method": "lex", "elided": "lex",
            "range": "num",
            "dem": "dem",
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
    elif kind == "elided":
        _, head, wid = token.split(":", 2)
        surface = "%s(%s)" % (head, surface_of[wid][len(head):])
    elif kind == "range":
        _, lo, hi, counter = token.split(":", 3)
        surface = ("〈n～n〉" if lo == "n" else "%s～%s" % (lo, hi)) + counter
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
    tables["r12-words.json"] = r12_words_table(
        extract_seed.R12B_WORDS, lexicon, sentences, surface_of)
    tables["r12a-words.json"] = r12_words_table(
        extract_seed.R12A_WORDS, lexicon, sentences, surface_of)

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


# R12 收錄表(2026-10-07 站主核可 (b)、(a) 兩份清單全收):清單在
# extract_seed.py 的 R12B_WORDS/R12A_WORDS,這裡依詞元列落地後的次數與例句;
# 「剝除」類不列(已不在詞典)
R12_EXAMPLES = 5


def r12_words_table(words, lexicon, sentences, surface_of):
    """R12 落地後:每個詞元一列——詞形(含只補 lemma 的既有詞形)、
    次數(含指示綁定裡的出現)、句數;展開看例句切分。"""
    id_of = {e["surface"]: e["id"] for e in lexicon}
    lemma_of = {e["id"]: e["lemma"] for e in lexicon if "lemma" in e}

    def seq(tokens):
        return [token_cell(t, surface_of) for t in tokens]

    per = {}
    for i, s in enumerate(sentences):
        for t in s["tokens"]:
            wid = t.split(":", 2)[2] if t.startswith("d:") else t
            lemma = lemma_of.get(wid)
            if lemma is None:
                continue
            p = per.setdefault(lemma, {"count": 0, "hits": []})
            p["count"] += 1
            if not p["hits"] or p["hits"][-1] != i:
                p["hits"].append(i)

    rows = []
    for lemma, cat, forms in words:
        if cat == "剝除":
            continue
        family = [e["surface"] for e in lexicon if e.get("lemma") == lemma]
        p = per.get(lemma, {"count": 0, "hits": []})
        examples = []
        for i in examples_of_idx(p["hits"], sentences, R12_EXAMPLES):
            s = sentences[i]
            examples.append({"cells": [
                str(s["card"]),
                {"text": s["text_ja"],
                 "marks": [f for f in family if f in s["text_ja"]]},
                seq(s["tokens"])]})
        # ADR-0014 拆掉的詞形(両隣/倍数 等)不在詞典了,標「已拆」
        shown = "/".join(f if f in id_of else f + "(已拆)" for f in forms)
        rows.append({
            "cells": [lemma, cat, shown,
                      "/".join(f for f in family if f not in forms) or None,
                      p["count"], len(p["hits"])],
            "detail": {"columns": [column("卡號", "text"),
                                   column("原文", "quote"),
                                   column("切分", "tokens")],
                       "rows": examples},
        })
    return {
        "columns": [column("詞元", "text"), column("類別", "text"),
                    column("新增詞形", "text"), column("既有詞形(補 lemma)", "text"),
                    column("次數", "number"), column("句數", "number")],
        "key": "詞元",
        "classes": CLASSES,
        "rows": rows,
    }


def examples_of_idx(indices, sentences, limit):
    """examples_of 的索引版:依給定順序、原文去重,取前 limit 句的索引。"""
    out, seen = [], set()
    for i in indices:
        text = sentences[i]["text_ja"]
        if text in seen:
            continue
        seen.add(text)
        out.append(i)
        if len(out) == limit:
            break
    return out


if __name__ == "__main__":
    main()
