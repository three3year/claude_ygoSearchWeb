# -*- coding: utf-8 -*-
"""票 02「具名查詢編譯試跑」:類別樹的每片葉 → 框架述詞,對現有 frames.json 重算張數,
和 data/action_categories.json 現在的張數比。

只讀 .scratch/effect-tokenize/(category_tree.json、frames.json、categories.py、places.py)與
data/action_categories.json,不改任何網站資料、不改樹。輸出 results/compile.json(每葉一列)
與 results/compile.md(三張清單),印摘要。

述詞欄位(GLOSSARY 框架述詞):詞元、位置、極性、態、來源/目的/所在的(玩家, 區域)、受事者
中心詞字面、目的補語中心詞字面。葉條件逐欄對過去:
    來源/目的/所在(+玩家)  → 該欄任一 (玩家, 區域) 段:區域相等,葉有玩家條件時玩家也相等
    關鍵詞                 → 受事者中心詞(對象→主語→主題第一個有值的欄,categories.head_nouns)
                             任一段含關鍵詞(categories.keyword_in,した/する/され 尾不算)
    目的關鍵詞             → 目的欄中心詞任一段含
    極性類(肯定/耐性/限制) → 現有欄位只有 極性(肯定/否定/可能)+態;耐性/限制靠述語形
                             (categories.polarity_class 讀子句字面),述詞沒有這一欄——
                             以它當「假想新欄」算一組,另以 極性+態 近似(耐性=否定+受身、
                             限制=否定+非受身)算一組,差多少就是缺欄的代價
    預設葉 {}               → 取消;詞元節點就是「詞元=X(極性類=Y)」的述詞
張數都只算效果位(現在介面預設:ae 欄,不含代價、動作對象不限)。
所在欄另分兩種:嚴格(只讀框架的所在欄)與沿用 categories.place_literal(非移動類所在空、
來源有字面時來源當所在;2026-10-28 裁定),差額就是規格 1 要不要把 から 搬進所在的代價。

用法:PYTHONIOENCODING=utf-8 python .scratch/frame-predicate-search/tools/compile_dry_run.py [--heads old|v4]
--heads v4(frame-args-v4 票 02):關鍵詞與目的關鍵詞改讀論元片語各段的中心詞(frame["phrases"][欄]
的 segments[].head;欄的取法同舊:對象→主語→主題第一個有值的欄),比對仍用 keyword_in(子字串);
結果另存 results/compile-v4.json / compile-v4.md,不蓋舊結果。預設 old = categories.head_nouns 的
平假名邊界中心詞。
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOKENIZE = os.path.join(ROOT, ".scratch", "effect-tokenize")
sys.path.insert(0, TOKENIZE)
import categories  # noqa: E402
from categories import ZONE_FIELDS, head_nouns, keyword_in, place_literal, polarity_class  # noqa: E402
from frames import POL_AFFIRM, POL_NEG, POS_EFFECT  # noqa: E402
from action_lemmas import VOICE_PASSIVE  # noqa: E402
from places import parse_zones  # noqa: E402

FRAMES = os.path.join(TOKENIZE, "frames.json")
EXPORT = os.path.join(ROOT, "data", "action_categories.json")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

REASON_DEFAULT = "預設葉取消"
REASON_EXCLUSIVE = "不再互斥(較具體的同詞元葉先到)"
REASON_PARALLEL = "並收取消(關鍵詞葉命中時來源/目的葉現在不收)"
REASON_KARA = "非移動類 から 不當所在"
REASON_UNPLACED = "原未歸(預期外)"
REASON_OTHER = "其他(預期外)"
HEADS_OLD, HEADS_V4 = "old", "v4"


def zone_pairs(frame, field, literal=None):
    """框架一欄 → [(玩家, 區域)];推得的欄玩家記 None(與 categories.classify_frame 同)。"""
    literal = frame.get(field) if literal is None else literal
    pairs = parse_zones(literal) or []
    if field in (frame.get("inferred") or ()):
        return [(None, zone) for _, zone in pairs]
    return pairs


def phrase_heads(frame, field):
    """frame-args-v4 的中心詞:該欄論元片語各段的 head(沒有片語、或段沒有中心詞的略過)。"""
    phrase = (frame.get("phrases") or {}).get(field) if field else None
    return [seg["head"] for seg in (phrase or {}).get("segments", ()) if seg.get("head")]


def project(frame, heads=HEADS_OLD):
    """動作框架 → 述詞比對用的欄位;heads 選中心詞的來源(old=平假名邊界、v4=論元片語)。"""
    field = next((f for f in categories.KEYWORD_FIELDS if frame.get(f)), None)
    text = frame.get(field) if field else None
    goal = frame.get("goal")
    neg = frame["polarity"] == POL_NEG
    if heads == HEADS_V4:
        head_list = phrase_heads(frame, field)
        goal_heads = phrase_heads(frame, "goal")
    else:
        head_list = [h for h in head_nouns(text)] if text else []
        goal_heads = [h for h in head_nouns(goal)] if goal else []
    return {
        "lemma": frame["action"],
        "position": frame["position"],
        "class_derived": polarity_class(frame),          # 假想新欄(讀述語形)
        "class_fields": (POL_AFFIRM if not neg                # 只用 極性+態 的近似
                         else categories.POL_RESIST if frame.get("voice") == VOICE_PASSIVE
                         else categories.POL_RESTRICT),
        "source": zone_pairs(frame, "source"),
        "goal": zone_pairs(frame, "goal"),
        "place_strict": zone_pairs(frame, "place"),
        "place_rule": zone_pairs(frame, "place", place_literal(frame)),
        "heads": head_list,
        "goal_heads": goal_heads,
    }


def leaf_predicate(leaf):
    """葉 → 述詞(欄 → 條件);預設葉沒有條件欄。"""
    pred = {"lemma": leaf.lemma, "class": leaf.polarity}
    for field in ZONE_FIELDS:
        zone = getattr(leaf, field)
        if zone:
            pred[field] = (leaf.players.get(field), zone)
    if leaf.keywords:
        pred["keywords"] = list(leaf.keywords)
    if leaf.goal_keywords:
        pred["goal_keywords"] = list(leaf.goal_keywords)
    return pred


def zone_hit(pairs, cond):
    player, zone = cond
    return any(z == zone and (player is None or p == player) for p, z in pairs)


def evaluate(pred, proj, place_key="place_strict", class_key="class_derived"):
    if proj["lemma"] != pred["lemma"] or proj[class_key] != pred["class"]:
        return False
    for field in ("source", "goal"):
        if field in pred and not zone_hit(proj[field], pred[field]):
            return False
    if "place" in pred and not zone_hit(proj[place_key], pred["place"]):
        return False
    if "keywords" in pred and not any(
            keyword_in(k, h) for k in pred["keywords"] for h in proj["heads"]):
        return False
    if "goal_keywords" in pred and not any(
            keyword_in(k, h) for k in pred["goal_keywords"] for h in proj["goal_heads"]):
        return False
    return True


def is_default(leaf):
    return not (leaf.source or leaf.goal or leaf.place or leaf.keyed)


def main(argv=None):
    parser = argparse.ArgumentParser(description="具名查詢編譯試跑")
    parser.add_argument("--heads", choices=(HEADS_OLD, HEADS_V4), default=HEADS_OLD,
                        help="中心詞來源:old=平假名邊界(預設)、v4=論元片語的中心詞(結果另存 compile-v4.*)")
    args = parser.parse_args(argv)
    heads = args.heads
    suffix = "" if heads == HEADS_OLD else "-" + heads
    tree = categories.load_tree()
    with open(FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(EXPORT, encoding="utf-8") as f:
        export = json.load(f)

    # 現在的張數:匯出檔每句效果位的葉 → 葉 → 卡集合
    old_cards = defaultdict(set)
    for row in export["句"]:
        for leaf_name in row.get("effect", ()):
            old_cards[leaf_name].add(row["card"])

    # 效果位動作框架 → 投影 + 現行歸葉紀錄(歸因用)
    effect_frames = []
    for s in sentences:
        for fr in s["frames"]:
            if fr["kind"] != "動作" or fr["position"] != POS_EFFECT:
                continue
            effect_frames.append((s["card"], project(fr, heads), tree.classify_frame(fr), fr))
    # 驗證自己讀出的「現在」與匯出檔一致(同一份 frames.json 重跑 classify_frame)
    check = defaultdict(set)
    for card, _, record, _ in effect_frames:
        for leaf_name in record["leaves"]:
            check[leaf_name].add(card)
    mismatch = [n for n in set(check) | set(old_cards) if check[n] != old_cards[n]]
    assert not mismatch, "classify_frame 重算與匯出檔不一致:%s" % mismatch[:5]

    leaves_out = []
    reason_totals = Counter()
    for leaf in tree.leaves:
        pred = leaf_predicate(leaf)
        default = is_default(leaf)
        sets = {key: set() for key in ("strict", "rule", "fields")}
        reasons = defaultdict(set)         # 原因 → 卡
        reason_frames = Counter()
        for card, proj, record, fr in effect_frames:
            hit_strict = evaluate(pred, proj)
            if hit_strict:
                sets["strict"].add(card)
            if evaluate(pred, proj, place_key="place_rule"):
                sets["rule"].add(card)
            if evaluate(pred, proj, place_key="place_rule", class_key="class_fields"):
                sets["fields"].add(card)
            placed_here = leaf.name in record["leaves"]
            if hit_strict and not placed_here:
                if default:
                    why = REASON_DEFAULT          # 其餘框全進詞元節點
                elif not record["leaves"]:
                    why = REASON_UNPLACED
                elif (leaf.source or leaf.goal) and not leaf.place and any(
                        tree.leaves[tree.leaf_order[n]].keyed for n in record["leaves"]):
                    why = REASON_PARALLEL
                else:
                    why = REASON_EXCLUSIVE
                reasons[why].add(card)
                reason_frames[why] += 1
            elif placed_here and not hit_strict:
                why = REASON_KARA if evaluate(pred, proj, place_key="place_rule") else REASON_OTHER
                reasons[why].add(card)
                reason_frames[why] += 1
        old = old_cards.get(leaf.name, set())
        new = sets["strict"]
        # 卡層差異的歸因:多出的卡裡,每張至少有一個不帶現行葉的命中框;少掉的卡同理
        gained, lost = new - old, old - new
        attributed = {why: len(cards & (gained | lost)) for why, cards in reasons.items()}
        leaves_out.append({
            "leaf": leaf.name, "path": list(leaf.path), "default": default,
            "predicate": {k: v for k, v in pred.items()},
            "needs_negation_field": leaf.polarity != POL_AFFIRM,
            "old": len(old), "new": len(new), "new_rule": len(sets["rule"]),
            "new_fields_only": len(sets["fields"]),
            "gained": len(gained), "lost": len(lost),
            "reasons_cards": dict(sorted(attributed.items())),
            "reasons_frames": dict(sorted(reason_frames.items())),
        })
        for why, n in attributed.items():
            reason_totals[why] += n

    # 詞元節點(含極性類節點)的述詞:詞元=X(極性類=Y);現在 = 底下各葉的聯集
    nodes_out = []
    for (lemma, cls), leaves in tree.by_key.items():
        pred = {"lemma": lemma, "class": cls}
        new = {card for card, proj, _, _ in effect_frames if evaluate(pred, proj)}
        fields = {card for card, proj, _, _ in effect_frames
                  if evaluate(pred, proj, class_key="class_fields")}
        old = set().union(*(old_cards.get(l.name, set()) for l in leaves))
        nodes_out.append({"node": categories.leaf_name(lemma, cls), "leaves": len(leaves),
                          "has_default": any(is_default(l) for l in leaves),
                          "old": len(old), "new": len(new), "new_fields_only": len(fields),
                          "needs_negation_field": cls != POL_AFFIRM})

    # 否定形的分布(缺欄的代價)
    neg = Counter()
    for _, proj, _, fr in effect_frames:
        if fr["polarity"] == POL_NEG:
            neg[(fr.get("voice") or "—", proj["class_derived"] or "一般否定")] += 1

    os.makedirs(RESULTS, exist_ok=True)
    result = {"heads": heads, "leaves": leaves_out, "lemma_nodes": nodes_out,
              "reason_card_totals": dict(reason_totals),
              "negation_forms_effect_position": {"%s/%s" % k: v for k, v in sorted(neg.items())},
              "effect_frames": len(effect_frames),
              "cards_covered": len({c for c, _, _, _ in effect_frames})}
    with open(os.path.join(RESULTS, "compile%s.json" % suffix), "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RESULTS, "compile%s.md" % suffix), "w", encoding="utf-8", newline="\n") as f:
        f.write(report(result))
    print(summary(result))


def report(result):
    same = [l for l in result["leaves"] if l["new"] == l["old"] and not l["default"]]
    diff = [l for l in result["leaves"] if l["new"] != l["old"] and not l["default"]]
    defaults = [l for l in result["leaves"] if l["default"]]
    heads = result.get("heads", HEADS_OLD)
    out = ["# 具名查詢編譯試跑:三張清單(效果位張數;現在 = data/action_categories.json 的 effect 欄)%s"
           % ("——中心詞讀論元片語(frame-args-v4 票 02,--heads v4)" if heads == HEADS_V4 else ""),
           "", "工具:tools/compile_dry_run.py%s;數字原檔 results/compile%s.json。" % (
               " --heads v4" if heads == HEADS_V4 else "", "" if heads == HEADS_OLD else "-" + heads), ""]
    out.append("## 一、可機械編譯且張數相同(%d 葉)" % len(same))
    out.append("")
    out.append("| 葉 | 張數 | 述詞 | 備註 |")
    out.append("|---|---:|---|---|")
    for l in same:
        out.append("| %s | %d | %s | %s |" % (l["leaf"], l["old"], pred_text(l["predicate"]),
                                            notes(l)))
    out.append("")
    out.append("## 二、可編譯但張數不同(%d 葉)" % len(diff))
    out.append("")
    out.append("| 葉 | 現在 | 述詞 | 差 | 原因(卡數) | 備註 |")
    out.append("|---|---:|---:|---:|---|---|")
    for l in sorted(diff, key=lambda l: -(abs(l["new"] - l["old"]))):
        out.append("| %s | %d | %d | %+d | %s | %s |" % (
            l["leaf"], l["old"], l["new"], l["new"] - l["old"],
            "、".join("%s %d" % kv for kv in l["reasons_cards"].items()), notes(l)))
    out.append("")
    out.append("## 三、預設葉(取消,改為詞元節點述詞;%d 葉)" % len(defaults))
    out.append("")
    out.append("| 預設葉 | 現在(只收其餘) | 詞元節點述詞 | 差 | 備註 |")
    out.append("|---|---:|---:|---:|---|")
    for l in defaults:
        out.append("| %s | %d | %d | %+d | %s |" % (l["leaf"], l["old"], l["new"],
                                                 l["new"] - l["old"], notes(l)))
    out.append("")
    out.append("## 詞元節點(詞元=X(極性類=Y) 的述詞;現在 = 底下各葉聯集)")
    out.append("")
    out.append("| 節點 | 葉數 | 有預設葉 | 現在 | 述詞 | 差 | 只用極性+態 |")
    out.append("|---|---:|:-:|---:|---:|---:|---:|")
    for n in result["lemma_nodes"]:
        out.append("| %s | %d | %s | %d | %d | %+d | %d |" % (
            n["node"], n["leaves"], "是" if n["has_default"] else "", n["old"], n["new"],
            n["new"] - n["old"], n["new_fields_only"]))
    out.append("")
    out.append("## 否定框架的述語形(效果位;態/極性類)")
    out.append("")
    for k, v in result["negation_forms_effect_position"].items():
        out.append("- %s:%d 框" % (k, v))
    out.append("")
    return "\n".join(out)


def notes(l):
    parts = []
    if l["new_rule"] != l["new"]:
        parts.append("沿用 から 當所在則 %d" % l["new_rule"])
    if l["needs_negation_field"]:
        parts.append("需要否定形欄;只用極性+態則 %d" % l["new_fields_only"])
    return ";".join(parts)


def pred_text(pred):
    parts = ["詞元=%s" % pred["lemma"]]
    if pred["class"] != POL_AFFIRM:
        parts.append("極性類=%s" % pred["class"])
    names = {"source": "來源", "goal": "目的", "place": "所在"}
    for field in ZONE_FIELDS:
        if field in pred:
            player, zone = pred[field]
            parts.append("%s=%s%s" % (names[field], (player + ":") if player else "", zone))
    if "keywords" in pred:
        parts.append("中心詞含 %s" % "/".join(pred["keywords"]))
    if "goal_keywords" in pred:
        parts.append("目的中心詞含 %s" % "/".join(pred["goal_keywords"]))
    return "、".join(parts)


def summary(result):
    leaves = result["leaves"]
    same = sum(1 for l in leaves if l["new"] == l["old"] and not l["default"])
    diff = sum(1 for l in leaves if l["new"] != l["old"] and not l["default"])
    defaults = sum(1 for l in leaves if l["default"])
    kara = sum(1 for l in leaves if l["new_rule"] != l["new"])
    neg = sum(1 for l in leaves if l["needs_negation_field"])
    lines = ["葉 %d:張數相同 %d、張數不同 %d、預設葉 %d" % (len(leaves), same, diff, defaults),
             "所在葉受 から 規則影響 %d 葉;否定節點的葉 %d 片需要否定形欄" % (kara, neg),
             "差異歸因(卡·葉):%s" % "、".join("%s %d" % kv for kv in
                                             sorted(result["reason_card_totals"].items())),
             "效果位動作框架 %d、卡 %d" % (result["effect_frames"], result["cards_covered"])]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
