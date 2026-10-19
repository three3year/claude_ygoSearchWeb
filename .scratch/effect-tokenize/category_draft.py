# -*- coding: utf-8 -*-
"""類別樹草案的資料塊(.scratch/action-categories 票 06):從框架類別檔決定性產出審核關卡
md(.scratch/action-categories/tree-draft.md)引用的 JSON 表,格式見 review-mirror skill 的
「資料塊」。計數與例句都由這裡產出,草案不手抄。

    summary.json   儀表板:已歸/未歸/不適用、已歸比例、有所在的框架數、葉數、
                   頂層節點數
    majors.json    頂層節點(大類):成員詞元節點、葉數、框架數、卡數
    leaves.json    每葉(樹序):所屬大類與詞元節點、條件、效果位/代價位框架數、卡數;展開看三條例句
    unplaced.json  未歸類依(詞元, 極性類)聚合:詞元有沒有節點、框架數、卡數;展開看例句

例句以葉名(未歸類以標籤)當種子隨機抽,種子固定、重跑相同。讀 frames.json、
frame_categories.json、category_tree.json 與 data/cards.json;先跑 categories.py。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/category_draft.py
"""
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import categories  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from frames import POS_COST, POS_EFFECT  # noqa: E402

OUT_DIR = os.path.join(HERE, "..", "action-categories", "draft-data")
CARDS = os.path.join(HERE, "..", "..", "data", "cards.json")
EXAMPLES_PER_LEAF = 3
EXAMPLES_PER_UNPLACED = 5


def column(name, cell_type):
    return {"name": name, "type": cell_type}


EXAMPLE_COLUMNS = [column("卡號", "text"), column("卡名", "text"), column("位置", "text"),
                   column("子句", "text"), column("對象", "text"), column("來源", "text"),
                   column("目的", "text")]


def leaf_conditions(leaf):
    parts = ["詞元=" + leaf.lemma]
    if leaf.polarity != categories.POL_AFFIRM:
        parts.append("極性類=" + leaf.polarity)
    for field in categories.ZONE_FIELDS:
        if getattr(leaf, field):
            parts.append("%s=%s" % (categories.LEAF_LABELS[field], getattr(leaf, field)))
        if field in leaf.players:
            parts.append("%s=%s" % (categories.LEAF_LABELS[field + "_player"],
                                    leaf.players[field]))
    if leaf.keywords:
        parts.append("對象含 " + "/".join(leaf.keywords))
    return ";".join(parts)


def examples(items, seed, limit, names):
    picked = random.Random(seed).sample(items, min(limit, len(items)))
    picked.sort(key=lambda it: it[0])            # 依語料順序列
    return {"columns": EXAMPLE_COLUMNS, "rows": [{"cells": [
        str(card), names.get(card), fr["position"], fr["clause"].replace(" ", ""),
        fr.get("object"), fr.get("source"), fr.get("goal")]}
        for _, card, fr in picked]}


def main():
    tree = categories.load_tree()
    with open(categories.FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(categories.OUT, encoding="utf-8") as f:
        records = {(r["card"], r["section"], r["index"], r["order"]): r for r in json.load(f)}
    with open(CARDS, encoding="utf-8") as f:
        names = {c["id"]: c["name_ja"] for c in json.load(f)}

    per_leaf = defaultdict(list)        # 葉名 → [(語料序, 卡號, 框架)]
    per_major = defaultdict(set)        # 大類 → {框架鍵}
    unplaced = defaultdict(list)        # 標籤 → [(語料序, 卡號, 框架)]
    has_node = {}
    counts = dict.fromkeys(categories.STATUSES, 0)
    with_place = 0                      # 有所在字面的框架(所在只比葉的所在條件)
    seq = 0
    for s in sentences:
        for fr in s["frames"]:
            if fr["kind"] != KIND_ACTION:
                continue
            key = (s["card"], s["section"], s["index"], fr["order"])
            rec = records[key]
            counts[rec["status"]] += 1
            if rec["status"] != categories.STATUS_NA and fr.get("place"):
                with_place += 1
            item = (seq, s["card"], fr)
            seq += 1
            if rec["status"] == categories.STATUS_PLACED:
                per_major[rec["major"]].add(key)
                for name in rec["leaves"]:
                    per_leaf[name].append(item)
            elif rec["status"] == categories.STATUS_UNPLACED:
                label, node_key = categories.unplaced_label(fr)
                unplaced[label].append(item)
                has_node[label] = node_key in tree.by_key

    placed, missing = counts[categories.STATUS_PLACED], counts[categories.STATUS_UNPLACED]
    tables = {}
    tables["summary.json"] = {
        "columns": [column("項目", "text"), column("數", "text")],
        "rows": [{"cells": cells} for cells in (
            ["動作框架", "{:,}".format(sum(counts.values()))],
            ["已歸", "{:,}".format(placed)],
            ["未歸", "{:,}".format(missing)],
            ["不適用(條件位)", "{:,}".format(counts[categories.STATUS_NA])],
            ["已歸比例(已歸/(已歸+未歸))", "%.2f%%" % (100.0 * placed / max(1, placed + missing))],
            ["有所在(非條件位)", "{:,}".format(with_place)],
            ["葉", "{:,}".format(len(tree.leaves))],
            ["頂層節點(大類)", "{:,}".format(len(tree.majors))],
            ["未歸類組(詞元+極性類)", "{:,}".format(len(unplaced))],
        )]}

    leaves_of_major = defaultdict(list)
    for leaf in tree.leaves:
        leaves_of_major[leaf.major].append(leaf)
    major_rows = []
    for major in tree.majors:
        leaves = leaves_of_major[major]
        lemma_nodes = []
        for leaf in leaves:
            node = categories.leaf_name(leaf.lemma, leaf.polarity)
            if node not in lemma_nodes:
                lemma_nodes.append(node)
        frames = per_major[major]
        major_rows.append({"cells": [
            major, "、".join(lemma_nodes), len(leaves), len(frames),
            len({key[0] for key in frames})]})
    tables["majors.json"] = {
        "columns": [column("大類", "text"), column("詞元節點", "text"), column("葉數", "number"),
                    column("框架數", "number"), column("卡數", "number")],
        "key": "大類",
        "rows": major_rows}

    leaf_rows = []
    for leaf in tree.leaves:
        items = per_leaf[leaf.name]
        leaf_rows.append({
            "cells": [leaf.name, leaf.major, categories.leaf_name(leaf.lemma, leaf.polarity),
                      leaf_conditions(leaf),
                      sum(fr["position"] == POS_EFFECT for _, _, fr in items),
                      sum(fr["position"] == POS_COST for _, _, fr in items),
                      len({card for _, card, _ in items})],
            "detail": examples(items, leaf.name, EXAMPLES_PER_LEAF, names)})
    tables["leaves.json"] = {
        "columns": [column("葉", "text"), column("大類", "text"), column("詞元節點", "text"),
                    column("條件", "text"),
                    column("效果位", "number"), column("代價位", "number"),
                    column("卡數", "number")],
        "key": "葉",
        "rows": leaf_rows}

    groups = sorted(unplaced.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    tables["unplaced.json"] = {
        "columns": [column("標籤", "text"), column("詞元節點", "text"), column("框架數", "number"),
                    column("卡數", "number")],
        "key": "標籤",
        "rows": [{"cells": [label, "有(條件全不符)" if has_node[label] else "無",
                            len(items), len({card for _, card, _ in items})],
                  "detail": examples(items, label, EXAMPLES_PER_UNPLACED, names)}
                 for label, items in groups]}

    os.makedirs(OUT_DIR, exist_ok=True)
    for name, table in sorted(tables.items()):
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(table, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print("written", os.path.normpath(path), os.path.getsize(path), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
