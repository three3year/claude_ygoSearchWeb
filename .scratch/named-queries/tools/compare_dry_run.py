# -*- coding: utf-8 -*-
"""票 08「與試跑逐葉比對」:具名查詢目錄的全語料張數(匯出檔 data/action_frames.json 的目錄欄,效果位)
對照編譯試跑 compile-v4.json(.scratch/frame-predicate-search/tools/compile_dry_run.py --heads v4 的結果),
逐葉、逐詞元節點列新舊張數與差異原因,寫 results/compare-v4.md。

三個數字(都是效果位、卡為單位):
    試跑    compile-v4.json 記錄的 new(葉條件對框架**字面**區域、子字串關鍵詞、極性類讀述語形)
    重算    試跑的比法在**現在的 frames.json** 上重跑(compile_dry_run.project/evaluate)——與「試跑」的差是上游框架變了
            (票 02/03 之後的 frames.json),與目錄無關
    現在    目錄欄的張數(predicate.card_sets 對匯出框列算;本工具由匯出檔的句列重算、核對目錄欄)
「重算 → 現在」的差逐卡歸因(同一份 frames.json,只有比法不同;多收 +、少收 −):
    取自來源收回    試跑嚴格所在不中、沿用 から 當所在才中——第四版論元的 取自來源 已把 から 寫進結構化所在
                    (規格「31 葉不同」裡的 から 四葉;使用者故事 5)
    回指回填        結構化區域含回指回填寫進的來源/所在(frames.json 的 region_backfill 記號;規格 1),試跑只讀字面
    取自で          結構化所在含 で 轉欄寫進的(transfer=取自で)
    結構化區域      結構化區域與字面解析不同的其他情形(推得欄的玩家寫 無、字面解析不出的區域)
    尾綴            中心詞含關鍵詞(子字串)但不以它結尾(モンスターカード 對 モンスター、数値 對 数)——規格「中心詞尾綴」(a)
    其他            以上都不是(列卡片密碼,要逐卡看)
預設葉(97)已取消:列舊的預設葉張數與現在詞元節點的張數;詞元節點(100)與試跑的節點述詞相比。

用法(repo 任意位置):PYTHONIOENCODING=utf-8 python .scratch/named-queries/tools/compare_dry_run.py
輸入都要先有:frames.json、data/action_frames.json(run_chain.py)、compile-v4.json(入版控)。
"""
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOKENIZE = os.path.join(ROOT, ".scratch", "effect-tokenize")
DRY_RUN_TOOLS = os.path.join(ROOT, ".scratch", "frame-predicate-search", "tools")
sys.path.insert(0, TOKENIZE)
sys.path.insert(0, DRY_RUN_TOOLS)
import catalog  # noqa: E402
import categories  # noqa: E402
import compile_dry_run as dry  # noqa: E402
import export_frames  # noqa: E402
import predicate  # noqa: E402
from categories import keyword_in  # noqa: E402
from closed_values import TRANSFER_FROM_DE  # noqa: E402
from constraints import KIND_ACTION, POS_EFFECT  # noqa: E402

FRAMES = os.path.join(TOKENIZE, "frames.json")
EXPORT = os.path.join(ROOT, "data", "action_frames.json")
RECORDED = os.path.join(DRY_RUN_TOOLS, "results", "compile-v4.json")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
OUT = os.path.join(RESULTS, "compare-v4.md")

WHY_KARA, WHY_BACKFILL, WHY_DE, WHY_STRUCTURED, WHY_SUFFIX, WHY_OTHER = (
    "取自來源收回", "回指回填", "取自で", "結構化區域", "尾綴", "其他")


def effect_frames(sentences):
    """效果位動作框架 → [(卡, 試跑投影, 匯出框列, 框架)…]。框列由 export_frames.frame_row 轉(動作對象不用判:
    目錄述詞沒有那一欄)。"""
    out = []
    for s in sentences:
        for fr in s["frames"]:
            if fr["kind"] == KIND_ACTION and fr["position"] == POS_EFFECT:
                out.append((s["card"], dry.project(fr, dry.HEADS_V4), export_frames.frame_row(fr, None), fr))
    return out


def split_heads(pred):
    """目錄述詞 → (不含中心詞欄的述詞, [(片語鍵, 關鍵詞清單)…])。"""
    rest = {k: v for k, v in pred.items() if k not in predicate.HEAD_FIELDS}
    heads = [(predicate.EXPORT_PATH[field][1], predicate.values_of(pred, field))
             for field in predicate.HEAD_FIELDS if field in pred]
    return rest, heads


def heads_of(row, phrase):
    return [seg["head"] for seg in (row.get("phrases") or {}).get(phrase) or ()]


class Variants:
    """一片葉的各種比法在全語料的卡集合:strict/rule(試跑)、structured(結構化區域 + 子字串)、now(目錄述詞);
    hits 記每張卡在 now 或 structured 命中的框架(歸因用)。"""

    def __init__(self, leaf, pred, frames_):
        dry_pred = dry.leaf_predicate(leaf)
        rest, heads = split_heads(pred)
        base = predicate.matcher(rest)
        full = predicate.matcher(pred)
        self.strict, self.rule, self.structured, self.now = set(), set(), set(), set()
        self.frames = defaultdict(list)
        for card, proj, row, fr in frames_:
            if dry.evaluate(dry_pred, proj):
                self.strict.add(card)
            if dry.evaluate(dry_pred, proj, place_key="place_rule"):
                self.rule.add(card)
            if base(row):
                if all(any(keyword_in(k, h) for k in keywords for h in heads_of(row, phrase)) for phrase, keywords in heads):
                    self.structured.add(card)
                    self.frames[card].append(fr)
            if full(row):
                self.now.add(card)

    def attribute(self):
        out = defaultdict(list)
        for card in sorted(self.now - self.strict):
            if card in self.rule:
                why = WHY_KARA
            elif card in self.structured:
                markers = {m for fr in self.frames[card] for m in (
                    (WHY_BACKFILL if fr.get("region_backfill") else None),
                    (WHY_DE if fr.get("transfer") == TRANSFER_FROM_DE else None)) if m}
                why = sorted(markers)[0] if markers else WHY_STRUCTURED
            else:
                why = WHY_OTHER
            out["+" + why].append(card)
        for card in sorted(self.strict - self.now):
            out["-" + (WHY_SUFFIX if card in self.structured else WHY_OTHER)].append(card)
        return out


def why_text(reasons):
    parts = []
    for key, cards in reasons.items():
        shown = "、".join(str(c) for c in cards[:5]) + ("…" if len(cards) > 5 else "")
        parts.append("%s %d(%s)" % (key, len(cards), shown))
    return ";".join(parts)


def main():
    tree = categories.load_tree()
    cat = catalog.load()
    with open(FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(EXPORT, encoding="utf-8") as f:
        doc = json.load(f)
    with open(RECORDED, encoding="utf-8") as f:
        recorded = json.load(f)
    frames_ = effect_frames(sentences)
    column = {row["name"]: row["cards"][POS_EFFECT] for row in doc["目錄"]}
    rec_leaf = {l["leaf"]: l for l in recorded["leaves"]}
    rec_node = {n["node"]: n for n in recorded["lemma_nodes"]}
    old_leaves = {leaf.name: leaf for leaf in tree.leaves}
    old_nodes = {categories.leaf_name(lemma, cls): (lemma, cls) for (lemma, cls) in tree.by_key}

    summary = defaultdict(int)
    reason_totals = defaultdict(int)
    variants = {}
    for q in cat.queries:
        leaf = old_leaves.get(q.name)
        if leaf is None:                      # 詞元節點:試跑的節點述詞 {lemma, class}
            lemma, cls = old_nodes[q.name]
            leaf = type("Node", (), {"lemma": lemma, "polarity": cls, "source": None, "goal": None, "place": None,
                                     "players": {}, "keywords": (), "goal_keywords": ()})()
        v = Variants(leaf, q.predicate, frames_)
        assert len(v.now) == column[q.name], (q.name, len(v.now), column[q.name])
        variants[q.name] = v

    lines = ["# 票 08 逐葉比對:具名查詢目錄的張數(效果位)對照編譯試跑 compile-v4", "",
             "工具:.scratch/named-queries/tools/compare_dry_run.py(原因的定義在檔頭)。欄:試跑 = compile-v4.json 記錄的 new;"
             "重算 = 試跑的比法在現在的 frames.json 重跑;現在 = 目錄欄(predicate.card_sets 對匯出框列);差 = 現在 − 試跑;"
             "原因 = 重算 → 現在 的逐卡歸因(+ 多收、− 少收,括號列前 5 張);備註的「上游」= 重算 − 試跑。", ""]

    def leaf_row(name):
        rec, v = rec_leaf[name], variants[name]
        reasons = v.attribute()
        for key, cards in reasons.items():
            reason_totals[key] += len(cards)
        upstream = len(v.strict) - rec["new"]
        return "| %s | %d | %d | %d | %+d | %s | %s |" % (
            name, rec["new"], len(v.strict), len(v.now), len(v.now) - rec["new"], why_text(reasons),
            ("上游 %+d" % upstream) if upstream else "")

    groups = (("一、試跑可編譯且張數相同的葉", lambda l: not l["default"] and l["new"] == l["old"]),
              ("二、試跑可編譯但張數不同的葉", lambda l: not l["default"] and l["new"] != l["old"]))
    for title, pick in groups:
        names = [l["leaf"] for l in recorded["leaves"] if pick(l)]
        lines += ["## %s(%d 葉)" % (title, len(names)), "",
                  "| 葉 | 試跑 | 重算 | 現在 | 差 | 原因(卡) | 備註 |", "|---|---:|---:|---:|---:|---|---|"]
        for name in names:
            lines.append(leaf_row(name))
            summary[title + (":張數相同" if len(variants[name].now) == rec_leaf[name]["new"] else ":張數不同")] += 1
        lines.append("")

    defaults = [l for l in recorded["leaves"] if l["default"]]
    lines += ["## 三、預設葉(取消;%d 葉)——詞元節點就是「詞元=X」的述詞" % len(defaults), "",
              "| 預設葉 | 舊(只收其餘) | 試跑的詞元節點 | 現在的詞元節點 | 差(現在 − 試跑) |", "|---|---:|---:|---:|---:|"]
    for l in defaults:
        current = len(variants[l["leaf"]].now)
        lines.append("| %s | %d | %d | %d | %+d |" % (l["leaf"], l["old"], l["new"], current, current - l["new"]))
        summary["三、預設葉" + (":詞元節點張數相同" if current == l["new"] else ":詞元節點張數不同")] += 1
    lines.append("")

    lines += ["## 詞元節點(%d 個;極性類節點是 否定形 述詞)" % len(recorded["lemma_nodes"]), "",
              "| 節點 | 試跑 | 重算 | 現在 | 差 |", "|---|---:|---:|---:|---:|"]
    for n in recorded["lemma_nodes"]:
        v = variants[n["node"]]
        lines.append("| %s | %d | %d | %d | %+d |" % (n["node"], n["new"], len(v.strict), len(v.now), len(v.now) - n["new"]))
        summary["詞元節點" + (":張數相同" if len(v.now) == n["new"] else ":張數不同")] += 1
    lines.append("")

    head = ["## 摘要", ""] + ["- %s:%d" % (key, summary[key]) for key in sorted(summary)]
    head.append("- 重算 → 現在 的歸因合計(卡·葉):" + "、".join("%s %d" % kv for kv in sorted(reason_totals.items())))
    head.append("")
    lines[3:3] = head
    os.makedirs(RESULTS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(head))
    print("已寫出 %s" % OUT)


if __name__ == "__main__":
    main()
