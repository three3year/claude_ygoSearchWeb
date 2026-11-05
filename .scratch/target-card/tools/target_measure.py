# -*- coding: utf-8 -*-
"""原型(target-card 規格調查,2026-11-04):針對卡片要多匯出的值——體積、回指、比得了/比不了的分佈。

讀本機 frames.json(與匯出同一份)、results/anaphora_targets.json(anaphora_targets.py 重跑記下的先行框序與目的片語
回指原型)。全部在記憶體做:匯出檔用 export_frames.export + serialize,網站資料用 webindex.build_index + serialize_index,
各方案只在記憶體改框列/編碼後重建,量 UTF-8 位元組與 gzip(與 build_index.print_size 同法)。不寫 repo 既有檔。

方案:
  基準       現行匯出(應與 data/action_frames.json 相同)
  修飾語(a)  段多帶 values:種族/屬性/子類型存 vocab 碼(與 data.js 卡面 r/at/s 同一套碼)、數值 [欄位, 比較, 數字或數字列]、
             字段存日文;比不了旗標 u
  修飾語(b)  同鍵但值全存日文字面(數值存整段字面,前端自己剖)
  回指(a)    框列多帶 anaphora_segments {patient|goal: [段…]}(目標字面經 patient.segments_of 切段,段同 segment_row + 修飾語(a))
  回指(b)    框列多帶 anaphora_ref {patient|goal: [標記句相對位移, 框在該句框列的序]}(先行框;指不到不帶)
data.js 編碼:段元組尾多一格值物件(短鍵 r/a/s/n/z/u);框元組尾多一格 [受事者目標, 目的目標]。

用法:python -X utf8 .scratch/target-card/tools/target_measure.py   → results/target_measure.txt
"""
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ET = os.path.join(ROOT, ".scratch", "effect-tokenize")
WEB = os.path.join(ROOT, "script", "web")
sys.path.insert(0, ET)
sys.path.insert(0, WEB)
import catalog  # noqa: E402
import export_frames  # noqa: E402
import patient  # noqa: E402
import vocab  # noqa: E402
from closed_values import (HEAD_CARD, MOD_ARCHETYPE, MOD_ATTRIBUTE, MOD_NUMERIC, MOD_PLAYER, MOD_POSITION,  # noqa: E402
                           MOD_RACE, MOD_SUBTYPE, MOD_ZONE, OTHER)
from export_common import load_faces, load_sentences, owner  # noqa: E402
from referent import clean, is_demonstrative  # noqa: E402
import build_index  # noqa: E402
import frameindex  # noqa: E402
import webindex  # noqa: E402

RESULTS = os.path.join(HERE, "results")
OUT = os.path.join(RESULTS, "target_measure.txt")
LINES = []


def p(line=""):
    LINES.append(line)
    print(line, flush=True)


# ── 碼表:卡文日文 → vocab 碼(由 patient 的 日文 → 位元 與 vocab 正典的 碼 → 位元 反推,一份) ──
def _code_of(domain, words):
    by_bits = {e["src"]: e["code"] for e in vocab.DOMAINS[domain]["entries"]}
    return {word: by_bits[bits] for word, bits in words.items()}


RACE_CODE = _code_of(vocab.RACE, patient._RACE_BITS)
ATTR_CODE = _code_of(vocab.ATTR, patient._ATTR_BITS)
SUB_CODE = {"モンスター": _code_of(vocab.SUB["m"], patient._MONSTER_TYPE_BITS),
            "魔法": _code_of(vocab.SUB["s"], patient._SPELL_TRAP_TYPE_BITS["魔法"]),
            "罠": _code_of(vocab.SUB["t"], patient._SPELL_TRAP_TYPE_BITS["罠"])}
MULTI_FIELD_MARKS = ("か", "と", "・", "または")
# 不是卡面參數的條件(狀態、事件、表示形式、指向別張卡):比不了,但不是「卡面條件比不了」
NON_FACE = ("定語子句(狀態/事件)", "表示形式(狀態,非卡面)", "指示詞修飾(そのモンスター…)", "このカード修飾",
            "關係/位置(素材、装備、リンク先、残り…)", "其他修飾語")
RELATIONAL_OTHER = ("素材", "装備", "リンク先", "リンク状態", "正面", "もう片方", "残り", "上記", "一番上", "一番下",
                    "隣", "相互リンク先", "対象", "攻撃対象")


def values_of(seg, scheme):
    """段 → 修飾語值物件(沒有值回 None)。scheme 'a' 碼/結構、'b' 日文字面。"""
    kind, _, _ = patient._head_face(seg["head"])
    out = defaultdict(list)
    for mod in seg["modifiers"]:
        mk, text = mod["kind"], patient._unelide(mod["text"])
        if mk == MOD_RACE:
            out["r"].append(RACE_CODE.get(text, text) if scheme == "a" else mod["text"])
        elif mk == MOD_ATTRIBUTE:
            out["a"].append(ATTR_CODE.get(text[:1], text) if scheme == "a" else mod["text"])
        elif mk == MOD_SUBTYPE:
            table = SUB_CODE.get(kind or "モンスター", {})
            out["s"].append(table.get(text, text) if scheme == "a" else mod["text"])
        elif mk == MOD_ARCHETYPE:
            out["z"].append(text[1:-1] if scheme == "a" else mod["text"])
        elif mk == MOD_NUMERIC:
            if scheme == "a":
                numbers = mod.get("numbers") or ([mod["number"]] if mod.get("number") is not None else [])
                out["n"].append([mod.get("field"), mod.get("compare"),
                                 numbers[0] if len(numbers) == 1 else numbers])
            else:
                out["n"].append(mod["text"])
    if reasons_of(seg):
        out["u"] = 1
    return dict(out) or None


# ── 比得了/比不了 ──
def reasons_of(seg):
    """段 → 比不了的原因清單(與 patient._segment_blocker 判 uncomparable 同一套情形,不看卡面)。"""
    found = []
    kind, prefix, comparable = patient._head_face(seg["head"])
    if not comparable:
        found.append("中心詞不是卡面能比的(X素材…)")
    mods = seg["modifiers"]
    subtypes = []
    for i, mod in enumerate(mods):
        mk, text = mod["kind"], patient._unelide(mod["text"])
        if mk == MOD_SUBTYPE and i + 1 < len(mods) and mods[i + 1]["text"].startswith(patient.MATERIAL):
            found.append("融合素材(召喚法不是子類型)")
        elif mk == MOD_SUBTYPE:
            subtypes.append(text)
        elif mk == MOD_RACE and text not in patient._RACE_BITS:
            found.append("種族表外")
        elif mk == MOD_ATTRIBUTE and text[:1] not in patient._ATTR_BITS:
            found.append("屬性表外")
        elif mk == MOD_NUMERIC:
            field = mod.get("field")
            if field not in patient.NUMERIC_FIELDS:
                if field and any(m in field for m in MULTI_FIELD_MARKS):
                    found.append("多欄數值(%s)" % field)
                else:
                    found.append("數值欄位不可比(%s)" % field)
            elif not (mod.get("numbers") or mod.get("number") is not None):
                found.append("數值沒有數字")
        elif mk == MOD_POSITION:
            found.append("表示形式(狀態,非卡面)")
        elif mk == OTHER:
            found.append(other_reason(mod["text"]))
    if prefix:
        subtypes += prefix.split("・")
    if subtypes:
        blocked = patient._subtype_block(kind, subtypes, {"type": 0}) if kind else None
        if blocked is None:
            found.append("子類型對不到卡種/表外")
    if "合計" in seg["text"] and not any(r.startswith("合計") for r in found):
        found.append("合計")
    return found


@lru_cache(maxsize=None)
def _is_clause(text):
    try:
        return patient._is_clause(text)
    except IndexError:          # 分詞器在少數字面尾巴越界(tokenize._lex_match);當不是子句
        return False


@lru_cache(maxsize=None)
def other_reason(text):
    if "合計" in text:
        return "合計"
    if "以外" in text or text in ("他", "その他"):
        return "以外/他(このカード以外、他の…)"
    if any(w in text for w in ("同じ", "同名", "異なる", "違う")):
        return "同じ/同名/異なる(關係)"
    if "元々" in text:
        return "元々の"
    if is_demonstrative(text):
        return "指示詞修飾(そのモンスター…)"
    if text.startswith("このカード") or text == "自身":
        return "このカード修飾"
    if patient._unelide(text) in ("魔法", "罠", "モンスター", "魔法カード", "罠カード", "モンスターカード"):
        return "卡種並列(魔法(カード)・罠カード…)"
    if text in RELATIONAL_OTHER:
        return "關係/位置(素材、装備、リンク先、残り…)"
    if _is_clause(text):
        return "定語子句(狀態/事件)"
    return "其他修飾語"


def has_condition(seg):
    """窄口徑:寫了卡面條件(種族/屬性/字段/子類型/數值/卡名/中心詞帶子類型)或是 このカード。"""
    if patient._is_this_card(seg):
        return True
    _, prefix, _ = patient._head_face(seg["head"])
    head = seg["head"] or ""
    if prefix or (head.startswith("「") and head.endswith("」")):
        return True
    return any(m["kind"] in (MOD_RACE, MOD_ATTRIBUTE, MOD_ARCHETYPE, MOD_SUBTYPE, MOD_NUMERIC) for m in seg["modifiers"])


def has_any(seg):
    """寬口徑:窄口徑或有任何 區域/玩家 以外的修飾語、中心詞比不了。"""
    return has_condition(seg) or bool(reasons_of(seg)) or any(
        m["kind"] not in (MOD_ZONE, MOD_PLAYER) for m in seg["modifiers"])


# ── 匯出對應 ──
def links(sentences, doc):
    """(效果句, 框架, 框列, 標記句序, 框在該句框列的序) 依原文順序;順便回 {(卡,段,句): {order: (標記句序, 框序)}}。"""
    out, where = [], {}
    k = 0
    rows = doc["句"]
    for s in sentences:
        parts = rows[k:k + len(s["parts"])]
        k += len(s["parts"])
        part_no = {r["index"]: n for n, r in enumerate(parts)}
        used = Counter()
        place = {}
        for fr in s["frames"]:
            if fr["kind"] != "動作":
                continue
            n = part_no[owner(s, fr)]
            pos = used[n]
            used[n] += 1
            row = parts[n]["frames"][pos]
            assert row.get("action") == fr.get("action")
            out.append((s, fr, row, n, pos))
            place[fr["order"]] = (n, pos)
        where[(s["card"], s["section"], s["index"])] = place
    return out, where


def export_source(fr):
    phrases = fr.get("phrases") or {}
    return next((key for key in export_frames.PATIENT_SOURCES if phrases.get(key)), None)


def seg_row(seg, scheme):
    row = export_frames.segment_row(seg)
    values = values_of(seg, scheme)
    if values:
        row["values"] = values
    return row


# ── 大小 ──
def sizes(text):
    raw = text.encode("utf-8")
    return len(raw), len(gzip.compress(raw, mtime=0))


def build_web(doc, cards, tags, errata, rewrites, ext):
    """在記憶體建 data.js 文字;ext 為 True 時段元組尾帶 values、框元組尾帶 anaphora 欄。"""
    orig = webindex.encode_frame

    def seg_tuple(seg, tables):
        if seg["head"] not in tables.head_code:
            tables.heads.append(seg["head"])
            tables.head_code[seg["head"]] = len(tables.heads) - 1
        items = [tables.head_code[seg["head"]],
                 *(frameindex._enum(tables, field, seg.get(key)) for key, field in frameindex.SEGMENT_ENUM_KEYS),
                 sum(tables.modifier_bit[kind] for kind in seg.get("modifiers") or ())]
        return items + [seg["values"]] if seg.get("values") else frameindex._cut(items)

    def encode(frame, tables):
        regions = frame.get("regions") or {}
        items = [tables.lemma_code[frame["action"]],
                 *(frameindex._enum(tables, field, frame.get(key)) for key, field in frameindex.SCALAR_KEYS),
                 *([tables.pair_code[tuple(pair)] for pair in regions.get(key) or ()] for key, _ in frameindex.REGION_KEYS),
                 *([seg_tuple(seg, tables) for seg in frameindex._segments(frame, phrase)]
                   for phrase, _ in frameindex.PHRASE_KEYS)]
        extra = None
        if frame.get("anaphora_segments"):
            a = frame["anaphora_segments"]
            extra = [[seg_tuple(s, tables) for s in a.get("patient") or ()],
                     [seg_tuple(s, tables) for s in a.get("goal") or ()]]
        elif frame.get("anaphora_ref"):
            a = frame["anaphora_ref"]
            extra = [a.get("patient") or 0, a.get("goal") or 0]
        return items + [extra] if extra else frameindex._cut(items)

    webindex.encode_frame = encode if ext else orig
    try:
        index, report = webindex.build_index(cards, tags, built_at="2026-11-04T00:00:00+0800", sources={},
                                             errata=errata, rewrites=rewrites, data_updated_at=None,
                                             frame_export=doc)
    finally:
        webindex.encode_frame = orig
    assert not report["problems"], report["problems"][:5]
    return webindex.serialize_index(index), len(index.get("frames") or ()) if isinstance(index, dict) else None


def variant(doc, edit):
    """複製句列(只複製到框列層),對每個 (框列複本, 連結) 套 edit。"""
    new = dict(doc)
    new["句"] = [dict(r, frames=[dict(f) for f in r["frames"]]) for r in doc["句"]]
    return new


def main():
    sentences = load_sentences()
    faces = load_faces()
    doc, problems = export_frames.export(sentences, faces, catalog.load())
    assert not problems
    with open(os.path.join(RESULTS, "anaphora_targets.json"), encoding="utf-8") as f:
        proto = json.load(f)
    linked, where = links(sentences, doc)
    by_id = {}
    k = 0
    for s in sentences:
        for n in range(len(s["parts"])):
            by_id[(id(s), n)] = k + n
        k += len(s["parts"])

    load = build_index._load
    cards, tags = load(build_index.DEFAULT_CARDS), load(build_index.DEFAULT_TAGS)
    errata = load(build_index.DEFAULT_ERRATA) if os.path.exists(build_index.DEFAULT_ERRATA) else []
    rewrites = load(build_index.DEFAULT_REWRITES) if os.path.exists(build_index.DEFAULT_REWRITES) else []

    # ── 回指:受事者與目的片語是指示詞的框、能不能解、先行框指不指得到 ──
    pat_demo, goal_demo = Counter(), Counter()
    pat_resolved, goal_ref, goal_resolved = Counter(), Counter(), Counter()
    goal_actions, goal_actions_resolved = Counter(), Counter()
    ref_stats = Counter()
    samples = defaultdict(list)
    goal_none = Counter()
    goal_via = Counter()
    anaphora_seg = {}   # id(row) → {"patient": [seg…], "goal": [seg…]}
    anaphora_ref = {}
    for s, fr, row, n, pos in linked:
        key = (s["card"], s["section"], s["index"])
        info = proto.get("%s|%s|%s" % key, {}).get(str(fr["order"]), {})
        position = fr["position"]
        src = export_source(fr)
        phrases = fr.get("phrases") or {}
        if src and phrases[src]["segments"] and phrases[src]["segments"][0]["demonstrative"]:
            pat_demo[position] += 1
            if fr.get("anaphora"):
                pat_resolved[position] += 1
        if fr.get("anaphora") and not (src and phrases[src]["segments"][0]["demonstrative"]):
            ref_stats["受事者:有回指但匯出的受事者片語第一段不是指示詞"] += 1
        goal = phrases.get("goal")
        if goal and goal["segments"] and goal["segments"][0]["demonstrative"]:
            goal_demo[position] += 1
            goal_actions[fr["action"]] += 1
            g = info.get("goal")
            if g is not None and not g.get("modifier"):
                goal_ref[position] += 1
            if g and not g.get("modifier") and not g.get("blank"):
                goal_resolved[position] += 1
                goal_actions_resolved[fr["action"]] += 1
                goal_via[g["via"]] += 1
            elif g and g.get("modifier"):
                goal_via["(指示詞只修飾另一張卡)"] += 1
            elif g and g.get("blank"):
                goal_via["(找不到)"] += 1
            else:
                goal_via["(field_reference 為 None:不是卡/切區域後非指示詞)"] += 1
                goal_none["%s:%s" % (fr["action"], goal["text"])] += 1
        # 回指(a):目標字面切段
        segs = {}
        if fr.get("anaphora"):
            segs["patient"] = [seg_row(x, "a") for x in patient.segments_of(fr["anaphora"]["text"])]
        g = info.get("goal")
        if g and g.get("text"):
            segs["goal"] = [seg_row(x, "a") for x in patient.segments_of(g["text"])]
        if segs:
            anaphora_seg[id(row)] = segs
        # 回指(b):先行框
        refs = {}
        for label, item in (("patient", info if fr.get("anaphora") else None), ("goal", g if g and g.get("text") else None)):
            if item is None:
                continue
            targets = item.get("targets") or []
            tag = "受事者" if label == "patient" else "目的"
            if not targets or targets[0] is None:
                ref_stats["%s:指不到(via %s,沒有目標框)" % (tag, item.get("via"))] += 1
                continue
            tn, tpos = where[key][targets[0]]
            target_fr = s["frames"][targets[0]]
            refs[label] = [tn - n, tpos]
            ref_stats["%s:指得到" % tag] += 1
            ref_stats["%s:先行框在%s" % (tag, "同一標記句" if tn == n else "同效果句另一標記句(● 共同部分)")] += 1
            if target_fr["sentence"] != fr["sentence"]:
                ref_stats["%s:先行框跨句號" % tag] += 1
            ref_stats["%s:先行框位置 %s" % (tag, target_fr["position"])] += 1
            text = clean((item if label == "goal" else fr["anaphora"])["text"])
            tsrc = export_source(target_fr)
            exported = clean((target_fr.get("phrases") or {}).get(tsrc, {}).get("text")) if tsrc else ""
            if not (exported and (text in exported or exported in text)):
                tphr = target_fr.get("phrases") or {}
                if tsrc and tphr[tsrc]["segments"] and tphr[tsrc]["segments"][0]["demonstrative"]:
                    why = "先行框自己也是指示詞(鏈,前端沿鏈走)"
                else:
                    other = next((k2 for k2 in ("object", "subject", "topic", "goal") if k2 != tsrc and target_fr.get(k2)
                                  and (text in clean(target_fr[k2]) or clean(target_fr[k2]) in text)), None)
                    why = ("目標在先行框的 %s 欄(匯出只帶 %s)" % (other, tsrc)) if other else "目標字面經改寫/取主人,對不上欄位"
                ref_stats["%s:目標字面 ≠ 先行框匯出的受事者片語:%s" % (tag, why)] += 1
                if why.startswith("目標字面經改寫") and len(samples[tag]) < 8:
                    samples[tag].append("%s %s 目標「%s」先行框受事者「%s」" % (s["card"], fr["action"], text, exported))
        if refs:
            anaphora_ref[id(row)] = refs

    # ── 比得了/比不了 ──
    seg_count = Counter()
    reason_any, reason_only = Counter(), Counter()
    numeric_fields, numeric_cmp, numeric_shape = Counter(), Counter(), Counter()
    other_texts = defaultdict(Counter)
    for s, fr, row, n, pos in linked:
        src = export_source(fr)
        phrases = fr.get("phrases") or {}
        groups = [(lab, phrases[k]["segments"]) for lab, k in (("受事者", src), ("目的", "goal")) if k and phrases.get(k)]
        if fr.get("anaphora"):
            groups.append(("受事者回指目標", patient.segments_of(fr["anaphora"]["text"])))
        for label, segs in groups:
            for seg in segs:
                for mod in seg["modifiers"]:
                    if mod["kind"] == MOD_NUMERIC:
                        numeric_fields[mod.get("field")] += 1
                        numeric_cmp[mod.get("compare")] += 1
                        numeric_shape["數字列(numbers 多個)" if mod.get("numbers") else
                                      "單一數字" if mod.get("number") is not None else "沒有數字"] += 1
                if seg["head_kind"] != HEAD_CARD or seg["demonstrative"]:
                    continue
                seg_count[label, "卡段"] += 1
                narrow, broad = has_condition(seg), has_any(seg)
                rs = sorted(set(reasons_of(seg)))
                if broad:
                    seg_count[label, "寬:有寫條件"] += 1
                    seg_count[label, "寬:乾淨可比"] += not rs
                face_rs = [r for r in rs if r not in NON_FACE]
                if narrow:
                    seg_count[label, "窄:有寫條件"] += 1
                    seg_count[label, "窄:乾淨可比"] += not rs
                    seg_count[label, "窄:卡面條件全比得了"] += not face_rs
                    if patient._is_this_card(seg):
                        seg_count[label, "窄:其中 このカード"] += 1
                    else:
                        seg_count[label, "窄2:有寫條件"] += 1
                        seg_count[label, "窄2:乾淨可比"] += not rs
                        seg_count[label, "窄2:卡面條件全比得了"] += not face_rs
                if broad:
                    for r in rs:
                        reason_any[label, r] += 1
                    if len(rs) == 1:
                        reason_only[label, rs[0]] += 1
                    for mod in seg["modifiers"]:
                        if mod["kind"] == OTHER:
                            why = other_reason(mod["text"])
                            if why in ("其他修飾語", "定語子句(狀態/事件)"):
                                other_texts[why][mod["text"]] += 1

    # ── 體積 ──
    def mods_variant(scheme):
        new = variant(doc, None)
        flat = [f for r in new["句"] for f in r["frames"]]
        assert len(flat) == len(linked)
        for f, (s, fr, row, n, pos) in zip(flat, linked):
            phrases = fr.get("phrases") or {}
            src = export_source(fr)
            out = {}
            if src:
                out["patient"] = [seg_row(x, scheme) for x in phrases[src]["segments"]]
            if phrases.get("goal"):
                out["goal"] = [seg_row(x, scheme) for x in phrases["goal"]["segments"]]
            if out:
                f["phrases"] = out
        return new

    def anaphora_variant(kind):
        new = variant(doc, None)
        flat = [f for r in new["句"] for f in r["frames"]]
        for f, (s, fr, row, n, pos) in zip(flat, linked):
            if kind == "a" and id(row) in anaphora_seg:
                f["anaphora_segments"] = anaphora_seg[id(row)]
            if kind == "b" and id(row) in anaphora_ref:
                f["anaphora_ref"] = anaphora_ref[id(row)]
        return new

    base_text = export_frames.serialize(doc)
    with open(export_frames.OUT, encoding="utf-8") as f:
        same = f.read() == base_text
    rows_size = []
    base_web, base_frames = build_web(doc, cards, tags, errata, rewrites, ext=False)
    web_on_disk = open(os.path.join(ROOT, "web", "data.js"), encoding="utf-8").read()
    for name, new in (("基準", doc), ("修飾語(a) 碼/結構", mods_variant("a")), ("修飾語(b) 日文字面", mods_variant("b")),
                      ("回指(a) 目標的段", anaphora_variant("a")), ("回指(b) 先行框索引", anaphora_variant("b"))):
        ex = sizes(export_frames.serialize(new))
        web_text, uniq = build_web(new, cards, tags, errata, rewrites, ext=name != "基準")
        rows_size.append((name, ex, sizes(web_text), uniq))
    # 修飾語(a) + 回指(a) 合計
    combo = mods_variant("a")
    for f, (s, fr, row, n, pos) in zip([f for r in combo["句"] for f in r["frames"]], linked):
        if id(row) in anaphora_seg:
            f["anaphora_segments"] = anaphora_seg[id(row)]
    web_text, uniq = build_web(combo, cards, tags, errata, rewrites, ext=True)
    rows_size.append(("修飾語(a)+回指(a)", sizes(export_frames.serialize(combo)), sizes(web_text), uniq))
    combo = mods_variant("a")
    for f, (s, fr, row, n, pos) in zip([f for r in combo["句"] for f in r["frames"]], linked):
        if id(row) in anaphora_ref:
            f["anaphora_ref"] = anaphora_ref[id(row)]
    web_text, uniq = build_web(combo, cards, tags, errata, rewrites, ext=True)
    rows_size.append(("修飾語(a)+回指(b)", sizes(export_frames.serialize(combo)), sizes(web_text), uniq))

    # ── 報告 ──
    p("# target_measure(.scratch/target-card/tools/target_measure.py,2026-11-04;frames.json 本機 2026-11-04 01:00)")
    p("基準匯出與 data/action_frames.json 逐位元組相同:%s;記憶體建的 data.js 與 web/data.js 長度差 %d 字元(built_at/sources 不同)" % (
        same, len(base_web) - len(web_on_disk)))
    p("匯出動作框 %d" % len(linked))
    p()
    p("## 1. 體積(UTF-8 位元組;gzip 同 build_index.print_size)")
    p("| 方案 | action_frames.json | 增量 | gzip | gzip 增量 | data.js | 增量 | gzip | gzip 增量 | data.js 唯一框 |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    (_, (eb, ebz), (wb, wbz), ub) = rows_size[0]
    for name, (e, ez), (w, wz), u in rows_size:
        p("| %s | %.1f KB | %+.1f KB (%+.2f%%) | %.1f KB | %+.1f KB (%+.2f%%) | %.1f KB | %+.1f KB (%+.2f%%) | %.1f KB | %+.1f KB (%+.2f%%) | %s |" % (
            name, e / 1e3, (e - eb) / 1e3, 100.0 * (e - eb) / eb, ez / 1e3, (ez - ebz) / 1e3, 100.0 * (ez - ebz) / ebz,
            w / 1e3, (w - wb) / 1e3, 100.0 * (w - wb) / wb, wz / 1e3, (wz - wbz) / 1e3, 100.0 * (wz - wbz) / wbz, u))
    p()
    p("## 1b. 數值修飾語(受事者/目的片語段與受事者回指目標的段,全部中心詞類)")
    p("欄位:" + "、".join("%s %d" % kv for kv in numeric_fields.most_common()))
    p("比較:" + "、".join("%s %d" % kv for kv in numeric_cmp.most_common()))
    p("數字形狀:" + "、".join("%s %d" % kv for kv in numeric_shape.most_common()))
    p()
    p("## 2. 回指")
    p("受事者片語(匯出取的 對象→主語→主題)第一段是指示詞的框,分位置:" + "、".join("%s %d" % kv for kv in pat_demo.items())
      + ";合計 %d,其中有回指目標 %d(%s)" % (sum(pat_demo.values()), sum(pat_resolved.values()),
                                       "、".join("%s %d" % kv for kv in pat_resolved.items())))
    p("目的片語第一段是指示詞的框,分位置:" + "、".join("%s %d" % kv for kv in goal_demo.items())
      + ";合計 %d;field_reference 認成回指 %d;原型解出目標 %d(%.1f%%,佔認成回指的 %.1f%%)" % (
          sum(goal_demo.values()), sum(goal_ref.values()), sum(goal_resolved.values()),
          100.0 * sum(goal_resolved.values()) / max(1, sum(goal_demo.values())),
          100.0 * sum(goal_resolved.values()) / max(1, sum(goal_ref.values()))))
    p("  目的指示詞依詞元(前 10):" + "、".join("%s %d/解出 %d" % (a, c, goal_actions_resolved[a])
                                             for a, c in goal_actions.most_common(10)))
    p("  目的回指結果:" + "、".join("%s %d" % kv for kv in goal_via.most_common()))
    p("  目的 field_reference 為 None 的字面(前 12):" + "、".join("%s %d" % kv for kv in goal_none.most_common(12)))
    for k in sorted(ref_stats):
        p("  %s %d" % (k, ref_stats[k]))
    for tag, rows in samples.items():
        p("  %s 改寫例:" % tag + ";".join(rows))
    p()
    p("## 3. 卡段比得了/比不了(中心詞類 卡、不是指示詞的段;受事者=匯出取的受事者片語)")
    for label in ("受事者", "目的", "受事者回指目標"):
        c = {k[1]: v for k, v in seg_count.items() if k[0] == label}
        if not c:
            continue
        p("%s:卡段 %d;窄口徑有寫條件 %d、乾淨可比 %d(%.1f%%;其中 このカード %d);寬口徑有寫條件 %d、乾淨可比 %d(%.1f%%)" % (
            label, c.get("卡段", 0), c.get("窄:有寫條件", 0), c.get("窄:乾淨可比", 0),
            100.0 * c.get("窄:乾淨可比", 0) / max(1, c.get("窄:有寫條件", 0)), c.get("窄:其中 このカード", 0),
            c.get("寬:有寫條件", 0), c.get("寬:乾淨可比", 0), 100.0 * c.get("寬:乾淨可比", 0) / max(1, c.get("寬:有寫條件", 0))))
        p("  窄口徑扣掉 このカード:有寫條件 %d、乾淨可比 %d(%.1f%%)、卡面條件全比得了(狀態/事件類另標) %d(%.1f%%)" % (
            c.get("窄2:有寫條件", 0), c.get("窄2:乾淨可比", 0),
            100.0 * c.get("窄2:乾淨可比", 0) / max(1, c.get("窄2:有寫條件", 0)), c.get("窄2:卡面條件全比得了", 0),
            100.0 * c.get("窄2:卡面條件全比得了", 0) / max(1, c.get("窄2:有寫條件", 0))))
        rows = sorted(((r, v) for (lab, r), v in reason_any.items() if lab == label), key=lambda kv: -kv[1])
        p("  比不了的原因(寬口徑的段;一段可多個;括號是唯一原因的段數):")
        for r, v in rows:
            p("    %s%s %d(%d)" % ("[非卡面] " if r in NON_FACE else "", r, v, reason_only[label, r]))
    for why, c in other_texts.items():
        p("%s 字面(前 15):" % why + "、".join("%s %d" % kv for kv in c.most_common(15)))
    os.makedirs(RESULTS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    sys.exit(main())
