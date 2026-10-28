# -*- coding: utf-8 -*-
"""類別樹草案的資料塊(.scratch/action-categories 票 06;category-tree-restart 票 05 改版):
從框架類別檔決定性產出審核關卡 md(.scratch/action-categories/tree-draft.md)引用的 JSON 表,
格式見 review-mirror skill 的「資料塊」。計數與例句都由這裡產出,草案不手抄。

    summary.json       儀表板:已歸/未歸/不適用、已歸比例、有所在的框架數、葉數、
                       頂層節點數
    majors.json        頂層節點(大類):成員(中類在前、再列留有葉的詞元節點,含借來的)、
                       葉數、框架數、卡數
    middles.json       中類(category-middle-class):所屬大類、葉數、框架數、卡數、收的葉;
                       展開看每葉的詞元與計數
    leaves.json        每葉(樹序):所屬大類與詞元節點、條件欄逐欄(詞元、極性類、來源、
                       目的、所在、各區域的玩家、關鍵詞、目的關鍵詞、宣告大類、中類)、框架數(效果位/
                       代價位分列)、卡數;展開看三條例句
    unplaced.json      未歸類依(詞元, 極性類)聚合:詞元有沒有節點、框架數、卡數;展開看例句
    places.json        非移動類詞元的所在分佈:每個非條件位有所在的非移動類詞元節點(含否定
                       極性類)一列,展開看 所在區域×玩家 的框架數、卡數、≥10 框可開的擬葉名
                       與現在落的葉;沒有所在的框架數另列
    keywords-naru.json になる 系、keywords-up.json アップ 系:依「第一個有值的欄」(對象→
                       主語→主題)的關鍵詞聚合,列該欄是對象/主語/主題與詞元分佈;第一列是
                       家族合計;展開看例句,(其他)展開看欄值的頻次

計數口徑:複合所在(手札・フィールド)在 places.json 逐區域各算一次、一個欄值含幾個關鍵詞
在關鍵詞表就算進幾列(與多葉同理),所以展開列/關鍵詞列加總可以超過外層的框架數。

例句以葉名(未歸類以標籤、關鍵詞表以表名+關鍵詞)當種子隨機抽,種子固定、重跑相同。讀
frames.json、frame_categories.json、category_tree.json 與 data/cards.json;先跑
categories.py。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/category_draft.py
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import categories  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from frames import MOVE_ACTIONS, POS_COND, POS_COST, POS_EFFECT  # noqa: E402
from places import (PLAYER_BOTH, PLAYER_NONE, PLAYER_OPP,  # noqa: E402
                    PLAYER_RELATIVE, PLAYER_SELF, parse_zones)

OUT_DIR = os.path.join(HERE, "..", "action-categories", "draft-data")
CARDS = os.path.join(HERE, "..", "..", "data", "cards.json")
EXAMPLES_PER_LEAF = 3
EXAMPLES_PER_UNPLACED = 5
EXAMPLES_PER_KEYWORD = 5
OTHER_VALUES = 30           # 關鍵詞表(其他)展開列的欄值數
# 開葉門檻:葉 ≥10 框才開,與詞元節點同(category-tree-restart 規格)
LEAF_THRESHOLD = 10

# 關鍵詞分佈的詞元家族(票 06 的裁定項:になる 的關鍵詞→大類對照表、アップ/ダウン 的關鍵詞集);
# 詞元統一(frame-lemma-unify,ADR-0016)後 なる 形併入 する 形、上げる/上がる 併入 アップ
NARU_FAMILY = ("にする", "とする", "倍にする", "半分にする", "同じにする")
UP_FAMILY = ("アップ", "ダウン")
# 各家族聚合用的候選關鍵詞(字面子字串;一個欄值含幾個就算進幾列,與多關鍵詞多葉同理)。
# アップ 系照規格只看 攻撃力/守備力/レベル/ランク/Pスケール,其餘字面進(其他)——
# 免得「闇属性モンスターの攻撃力」多算一列 属性
NUMERIC_KEYWORDS = ("攻撃力", "守備力", "レベル", "ランク", "Pスケール")
NARU_KEYWORDS = NUMERIC_KEYWORDS + ("ダメージ", "LP", "ドロー", "枚数", "合計", "数値", "回数",
                                    "種族", "属性")
KEYWORD_LABELS = {"object": "對象", "subject": "主語", "topic": "主題"}
TOTAL, OTHER, EMPTY = "(家族合計)", "(其他)", "(三欄都空)"

# 所在分佈的玩家列序;區域合計列不分玩家(擬葉名不帶玩家前綴)
PLAYER_ORDER = (PLAYER_SELF, PLAYER_OPP, PLAYER_BOTH, PLAYER_RELATIVE, PLAYER_NONE)
ALL_PLAYERS = "(不分)"
UNKNOWN_ZONE = "(認不出區域)"
ZONE_ORDER = list(categories.ZONE_LABEL)


def column(name, cell_type):
    return {"name": name, "type": cell_type}


EXAMPLE_COLUMNS = [column("卡號", "text"), column("卡名", "text"), column("位置", "text"),
                   column("子句", "text"), column("對象", "text"), column("主語", "text"),
                   column("主題", "text"), column("來源", "text"), column("目的", "text"),
                   column("所在", "text")]


def examples(items, seed, limit, names):
    picked = random.Random(seed).sample(items, min(limit, len(items)))
    picked.sort(key=lambda it: it[0])            # 依語料順序列
    return {"columns": EXAMPLE_COLUMNS, "rows": [{"cells": [
        str(card), names.get(card), fr["position"], fr["clause"].replace(" ", ""),
        fr.get("object"), fr.get("subject"), fr.get("topic"), fr.get("source"), fr.get("goal"),
        fr.get("place")]}
        for _, card, fr in picked]}


def tally(counter):
    """Counter → 「名 數、名 數」,依數由大到小(同數依名)。"""
    return "、".join("%s %d" % kv for kv in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


def summary_table(counts, with_place, tree, unplaced):
    placed, missing = counts[categories.STATUS_PLACED], counts[categories.STATUS_UNPLACED]
    return {
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
            ["中類", "{:,}".format(sum(len(names) for names in tree.middles.values()))],
            ["未歸類組(詞元+極性類)", "{:,}".format(len(unplaced))],
        )]}


def majors_table(tree, per_major):
    """成員欄:中類(樹來源檔的清單順序)在前,再列還留有葉(沒宣告中類)的詞元節點,
    與類別總覽同一棵樹。"""
    leaves_of_major = defaultdict(list)
    for leaf in tree.leaves:
        leaves_of_major[leaf.major].append(leaf)
    rows = []
    for major in tree.majors:
        leaves = leaves_of_major[major]
        lemma_nodes = []
        for leaf in leaves:
            if leaf.middle is None and leaf.node not in lemma_nodes:
                lemma_nodes.append(leaf.node)
        members = []
        if tree.middles.get(major):
            members.append("中類:" + "、".join(tree.middles[major]))
        if lemma_nodes:
            members.append("詞元節點:" + "、".join(lemma_nodes))
        frames = per_major[major]
        rows.append({"cells": [major, ";".join(members), len(leaves), len(frames),
                               len({key[0] for key in frames})]})
    return {"columns": [column("大類", "text"), column("成員", "text"),
                        column("葉數", "number"), column("框架數", "number"),
                        column("卡數", "number")],
            "key": "大類",
            "rows": rows}


def middles_table(tree, per_leaf):
    """每個中類一列(大類依樹序、中類依清單順序):框架數是帶該中類任一葉的框架(多葉框架
    只算一次),展開列每葉的詞元節點與計數(樹序)。"""
    rows = []
    for major in tree.majors:
        for middle in tree.middles.get(major, ()):
            leaves = [leaf for leaf in tree.leaves
                      if leaf.major == major and leaf.middle == middle]
            frames = {(seq, card) for leaf in leaves for seq, card, _ in per_leaf[leaf.name]}
            rows.append({
                "cells": [middle, major, len(leaves), len(frames),
                          len({card for _, card in frames}),
                          "、".join(leaf.name for leaf in leaves)],
                "detail": {"columns": [column("葉", "text"), column("詞元節點", "text"),
                                       column("框架數", "number"), column("卡數", "number")],
                           "rows": [{"cells": [leaf.name, leaf.node, len(per_leaf[leaf.name]),
                                               len({c for _, c, _ in per_leaf[leaf.name]})]}
                                    for leaf in leaves]}})
    return {"columns": [column("中類", "text"), column("大類", "text"), column("葉數", "number"),
                        column("框架數", "number"), column("卡數", "number"),
                        column("收的葉", "text")],
            "key": "中類",
            "rows": rows}


def leaves_table(tree, per_leaf, names):
    zone_columns = []
    for field in categories.ZONE_FIELDS:
        label = categories.LEAF_LABELS[field]
        zone_columns += [column(label, "text"), column(label + "玩家", "text")]
    rows = []
    for leaf in tree.leaves:
        items = per_leaf[leaf.name]
        zones = []
        for field in categories.ZONE_FIELDS:
            zones += [getattr(leaf, field), leaf.players.get(field)]
        rows.append({
            "cells": [leaf.name, leaf.major, leaf.node,
                      leaf.lemma, leaf.polarity] + zones + [
                      "/".join(leaf.keywords) or None, "/".join(leaf.goal_keywords) or None,
                      leaf.declared, leaf.middle, len(items),
                      sum(fr["position"] == POS_EFFECT for _, _, fr in items),
                      sum(fr["position"] == POS_COST for _, _, fr in items),
                      len({card for _, card, _ in items})],
            "detail": examples(items, leaf.name, EXAMPLES_PER_LEAF, names)})
    return {"columns": [column("葉", "text"), column("大類", "text"), column("詞元節點", "text"),
                        column("詞元", "text"), column("極性類", "text")] + zone_columns + [
                        column("關鍵詞", "text"), column("目的關鍵詞", "text"),
                        column("宣告大類", "text"),
                        column("中類", "text"), column("框架數", "number"), column("效果位", "number"),
                        column("代價位", "number"), column("卡數", "number")],
            "key": "葉",
            "rows": rows}


def unplaced_table(unplaced, has_node, names):
    groups = sorted(unplaced.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return {"columns": [column("標籤", "text"), column("詞元節點", "text"),
                        column("框架數", "number"), column("卡數", "number")],
            "key": "標籤",
            "rows": [{"cells": [label, "有(條件全不符)" if has_node[label] else "無",
                                len(items), len({card for _, card, _ in items})],
                      "detail": examples(items, label, EXAMPLES_PER_UNPLACED, names)}
                     for label, items in groups]}


def counted(entries):
    """[(卡號, 葉名清單)…] → (框架數, 卡數, 現落葉的文字:葉名 框架數,依框架數排)。"""
    leaves = Counter(name for _, leaf_names in entries for name in leaf_names)
    text = tally(leaves)
    unplaced = sum(not leaf_names for _, leaf_names in entries)
    if unplaced:
        text += ("、" if text else "") + "(未歸) %d" % unplaced
    return len(entries), len({card for card, _ in entries}), text


def places_table(actions, tree):
    """非移動類詞元的 所在區域×玩家 分佈(非條件位;所在空著時讀來源,categories.place_literal)。
    一個框架的複合所在逐區域各算一次
    (玩家逐區域取,places.parse_zones;所在不會推得),每個區域先列不分玩家的合計列、再列
    玩家各列。≥10 框標可開並給擬葉名(詞元節點存在時):玩家列是 詞元@相手フィールド 這類,
    無(沒寫玩家)不能宣告、沒有自己的葉;合計列是不帶玩家的 詞元@區域,門檻看扣掉同區域
    可開玩家葉之後剩下的框架數(玩家葉開了以後它收的就是這些)。"""
    by_node = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))  # 節點→區域→玩家→框架
    placed_cards = defaultdict(list)    # 詞元節點 → 有所在框架的卡號(一框一筆)
    without = Counter()
    keys = {}
    for _, card, fr, rec in actions:
        if fr["position"] == POS_COND or fr["action"] in MOVE_ACTIONS:
            continue
        label, key = categories.unplaced_label(fr)
        keys[label] = key
        place = categories.place_literal(fr)      # 所在空著時讀來源(票 08),與歸組同一個字面
        if not place:
            without[label] += 1
            continue
        placed_cards[label].append(card)
        entry = (card, rec["leaves"])
        zones = parse_zones(place)
        if not zones:
            by_node[label][UNKNOWN_ZONE][None].append(entry)
        for player, zone in zones:
            by_node[label][zone][player].append(entry)

    rows = []
    for label, by_zone in by_node.items():
        key = keys[label]
        detail, openable = [], []

        def proposal(n, conditions):
            """≥10 框且詞元節點存在時的擬葉名(加進可開清單),否則 None。"""
            if key is None or n < LEAF_THRESHOLD:
                return None
            name = categories.leaf_name(key[0], key[1], conditions)
            openable.append(name)
            return name

        zone_order = sorted(by_zone, key=lambda z: (
            z == UNKNOWN_ZONE, -sum(len(v) for v in by_zone[z].values()),
            ZONE_ORDER.index(z) if z in ZONE_ORDER else 0))
        for zone in zone_order:
            by_player = by_zone[zone]
            n, c, now = counted([e for entries in by_player.values() for e in entries])
            if zone == UNKNOWN_ZONE:
                detail.append([zone, None, n, c, None, None, None, now])
                continue
            zone_label = categories.ZONE_LABEL[zone]
            remaining, player_rows = n, []
            for player in sorted(by_player, key=lambda p: (-len(by_player[p]),
                                                           PLAYER_ORDER.index(p))):
                pn, pc, pnow = counted(by_player[player])
                name = None
                if player in categories.PLAYER_LABEL:
                    name = proposal(pn, {"place": zone, "place_player": player})
                if name:
                    remaining -= pn
                player_rows.append([zone_label, player, pn, pc, None,
                                    "可開" if name else None, name, pnow])
            name = proposal(remaining, {"place": zone})
            detail.append([zone_label, ALL_PLAYERS, n, c, remaining, "可開" if name else None,
                           name, now])
            detail.extend(player_rows)
        rows.append((len(placed_cards[label]), label, {
            "cells": [label, "有" if key in tree.by_key else "無", len(placed_cards[label]),
                      len(set(placed_cards[label])), without[label],
                      "、".join(openable) or None],
            "detail": {"columns": [column("所在", "text"), column("玩家", "text"),
                                   column("框架數", "number"), column("卡數", "number"),
                                   column("扣可開玩家葉後", "number"),
                                   column("≥%d" % LEAF_THRESHOLD, "text"),
                                   column("擬葉名", "text"), column("現落葉", "text")],
                       "rows": [{"cells": cells} for cells in detail]}}))
    rows.sort(key=lambda r: (-r[0], r[1]))
    return {"columns": [column("詞元節點", "text"), column("節點", "text"),
                        column("有所在", "number"), column("卡數", "number"),
                        column("沒有所在", "number"), column("可開的擬葉", "text")],
            "key": "詞元節點",
            "rows": [row for _, _, row in rows]}


def keywords_table(actions, family, keywords, seed, names):
    """詞元家族(非條件位)依關鍵詞比對欄(對象→主語→主題 第一個有值的)聚合:一個欄值含
    幾個候選關鍵詞就算進幾列;都不含的進(其他)、三欄都空的進(三欄都空);第一列是家族
    合計(每框一次)。"""
    groups = defaultdict(list)          # 列名 → [(語料序, 卡號, 框架, 比對欄)]
    for seq, card, fr, _ in actions:
        if fr["position"] == POS_COND or fr["action"] not in family:
            continue
        field = next((f for f in categories.KEYWORD_FIELDS if fr.get(f)), None)
        item = (seq, card, fr, field)
        groups[TOTAL].append(item)
        if field is None:
            groups[EMPTY].append(item)
            continue
        hits = [k for k in keywords if k in fr[field]]
        for k in hits or [OTHER]:
            groups[k].append(item)
    order = [TOTAL] + list(keywords) + [OTHER, EMPTY]
    rows = []
    for name in sorted(groups, key=lambda k: (k != TOTAL, k in (OTHER, EMPTY),
                                              -len(groups[k]), order.index(k))):
        items = groups[name]
        by_field = Counter(field for _, _, _, field in items)
        lemmas = Counter(categories.unplaced_label(fr)[0] for _, _, fr, _ in items)
        if name == TOTAL:
            detail = None
        elif name == OTHER:
            values = Counter((fr[field], field) for _, _, fr, field in items)
            detail = {"columns": [column("欄值", "text"), column("欄", "text"),
                                  column("框架數", "number")],
                      "rows": [{"cells": [value, KEYWORD_LABELS[field], n]} for (value, field), n
                               in sorted(values.items(),
                                         key=lambda kv: (-kv[1], kv[0]))[:OTHER_VALUES]]}
        else:
            detail = examples([(seq, card, fr) for seq, card, fr, _ in items],
                              seed + name, EXAMPLES_PER_KEYWORD, names)
        row = {"cells": [name, len(items), len({card for _, card, _, _ in items})]
               + [by_field[f] for f in categories.KEYWORD_FIELDS] + [tally(lemmas)]}
        if detail:
            row["detail"] = detail
        rows.append(row)
    return {"columns": [column("關鍵詞", "text"), column("框架數", "number"),
                        column("卡數", "number")]
            + [column(KEYWORD_LABELS[f], "number") for f in categories.KEYWORD_FIELDS]
            + [column("詞元", "text")],
            "key": "關鍵詞",
            "rows": rows}


def main():
    tree = categories.load_tree()
    with open(categories.FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(categories.OUT, encoding="utf-8") as f:
        records = {(r["card"], r["section"], r["index"], r["order"]): r for r in json.load(f)}
    with open(CARDS, encoding="utf-8") as f:
        names = {c["id"]: c["name_ja"] for c in json.load(f)}

    actions = []                        # [(語料序, 卡號, 框架, 類別紀錄)]
    per_leaf = defaultdict(list)        # 葉名 → [(語料序, 卡號, 框架)]
    per_major = defaultdict(set)        # 大類 → {框架鍵}
    unplaced = defaultdict(list)        # 標籤 → [(語料序, 卡號, 框架)]
    has_node = {}
    counts = dict.fromkeys(categories.STATUSES, 0)
    with_place = 0                      # 有所在字面的框架(所在只比葉的所在條件)
    for s in sentences:
        for fr in s["frames"]:
            if fr["kind"] != KIND_ACTION:
                continue
            key = (s["card"], s["section"], s["index"], fr["order"])
            rec = records[key]
            counts[rec["status"]] += 1
            if rec["status"] != categories.STATUS_NA and fr.get("place"):
                with_place += 1
            item = (len(actions), s["card"], fr)
            actions.append(item + (rec,))
            if rec["status"] == categories.STATUS_PLACED:
                per_major[rec["major"]].add(key)
                for name in rec["leaves"]:
                    per_leaf[name].append(item)
            elif rec["status"] == categories.STATUS_UNPLACED:
                label, node_key = categories.unplaced_label(fr)
                unplaced[label].append(item)
                has_node[label] = node_key in tree.by_key

    tables = {
        "summary.json": summary_table(counts, with_place, tree, unplaced),
        "majors.json": majors_table(tree, per_major),
        "leaves.json": leaves_table(tree, per_leaf, names),
        "middles.json": middles_table(tree, per_leaf),
        "unplaced.json": unplaced_table(unplaced, has_node, names),
        "places.json": places_table(actions, tree),
        "keywords-naru.json": keywords_table(actions, NARU_FAMILY, NARU_KEYWORDS, "naru:",
                                             names),
        "keywords-up.json": keywords_table(actions, UP_FAMILY, NUMERIC_KEYWORDS, "up:", names),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, table in sorted(tables.items()):
        path = os.path.join(OUT_DIR, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(table, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print("written", os.path.normpath(path), os.path.getsize(path), "bytes",
              len(table["rows"]), "rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
