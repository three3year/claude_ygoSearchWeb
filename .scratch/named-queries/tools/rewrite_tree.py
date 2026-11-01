# -*- coding: utf-8 -*-
"""一次性編譯器(named-queries 票 07):舊類別樹檔 category_tree.json → 具名查詢目錄檔 catalog.json。

**改寫後不再跑。** 跑過一次、目錄檔入版控後,站主直接用述詞字彙改目錄檔;舊樹檔凍結、只給過渡期的舊歸葉
(categories.py)讀,規格 4 一起刪。留著本檔只為了對照「目錄檔怎麼來的」。

機械改寫(規格「來源檔形狀」(a)):
    葉的 來源/目的/所在(+來源玩家/目的玩家/所在玩家) → 述詞同名欄 [[玩家或 null, 區域]](玩家沒宣告就 null = 不限;
                                                       舊拼法 雙方 → お互い,closed_values.PLAYERS 的字)
    關鍵詞                                            → 受事者中心詞(票 08 起尾綴比對,不再是子字串)
    目的關鍵詞                                        → 目的中心詞
    詞元節點 極性類 耐性 / 限制                        → 底下每個述詞 否定形 [受身, 不成不受] / [不可能];
                                                       肯定(省略)→ 不寫極性(目錄預設 肯定與可能,載入時補明文)
    詞元節點                                          → 帶子的具名查詢 {述詞: {詞元: X}, 子: […]};沒有子的就是不帶子的具名查詢
    預設葉 {}                                         → 刪(詞元節點本身就是「詞元=X」的述詞);預設葉宣告的中類搬到詞元節點上
    葉宣告的 大類/中類                                → 具名查詢同名鍵照抄
每個葉都帶自己的 詞元(述詞要完整,不從父節點繼承)。改寫完用 catalog.load 載入檢查,並逐一核對新節點名與舊葉名
/舊節點名(categories.load_tree 的 Leaf.name 與詞元節點名)相同;編不出來(舊葉有不認得的鍵、名字對不上)的
列清單、exit 1。對應表寫到 catalog-mapping.json(舊名、種類 葉/預設葉/詞元節點、新名;test_07_catalog 讀它守
真目錄的節點名)。

用法:PYTHONIOENCODING=utf-8 python .scratch/named-queries/tools/rewrite_tree.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
TOKENIZE = os.path.join(ROOT, ".scratch", "effect-tokenize")
sys.path.insert(0, TOKENIZE)
import catalog  # noqa: E402
import categories  # noqa: E402
from closed_values import PLACE_PLAYER, PLAYERS  # noqa: E402
from predicate import (FIELD_GOAL, FIELD_GOAL_HEAD, FIELD_LEMMA, FIELD_NEGATION, FIELD_PATIENT_HEAD,  # noqa: E402
                       FIELD_PLACE, FIELD_SOURCE)

OLD = os.path.join(TOKENIZE, "category_tree.json")
NEW = catalog.CATALOG
MAPPING = os.path.join(TOKENIZE, "catalog-mapping.json")

# 舊葉條件鍵 → (述詞欄, 玩家鍵)
REGION_OF = {"來源": (FIELD_SOURCE, "來源玩家"), "目的": (FIELD_GOAL, "目的玩家"), "所在": (FIELD_PLACE, "所在玩家")}
HEAD_OF = {"關鍵詞": FIELD_PATIENT_HEAD, "目的關鍵詞": FIELD_GOAL_HEAD}
# 舊極性類 → 否定形集合(規格裁定)
NEGATION_OF = {"耐性": [catalog.PASSIVE, catalog.NOT_BECOME], "限制": [catalog.CANNOT]}
# 舊玩家拼法 → closed_values 的字(雙方 → お互い)
PLAYER_OF = {old: PLACE_PLAYER[old] for old in PLACE_PLAYER if PLACE_PLAYER[old] in PLAYERS[:3]}
KIND_LEAF, KIND_DEFAULT, KIND_LEMMA = "葉", "預設葉", "詞元節點"

DOC = ("具名查詢目錄(named-queries 規格,ADR-0018;入版控,改節點只改本檔、重跑 run_chain.py 即生效)。由 "
       ".scratch/named-queries/tools/rewrite_tree.py 從第二版類別樹 category_tree.json 一次機械改寫而來(2026-11-01),"
       "之後直接改本檔;舊樹檔凍結、只給過渡期的舊歸葉用。節點三種:{\"大類\": 名, \"中類\"?: [名…], \"子\": [節點…]} 是"
       "大類(只有頂層大類可列中類;中類只在這裡宣告);{\"述詞\": {欄: 值…}, \"子\"?: [具名查詢…], \"大類\"?: 頂層大類名, "
       "\"中類\"?: 中類名} 是具名查詢——每個節點直接是一個框架述詞,帶子的就是詞元節點,頂層的自成大類;沒有預設葉,"
       "詞元節點本身就是「詞元=X」的述詞,具名查詢彼此不互斥、沒有樹序 first-match、沒有並收。述詞的欄用 predicate.py "
       "的字(FIELDS):詞元(單值、必填;要是框架抽取產得出的正規詞元)、極性(值清單;省略 = 預設——沒寫否定形時"
       " 肯定與可能、寫了否定形時 否定,載入時補成明文)、否定形(值清單;耐性 = [受身, 不成不受]、限制 = [不可能])、"
       "來源/目的/所在(各一清單,每項 [玩家或 null, 區域七值 手牌/牌組/額外牌組/墓地/除外/場上/靈擺區];null 不看玩家;"
       "玩家 自分/相手/お互い——相對/無 留給使用者述詞;任一項命中即中)、受事者中心詞(字串清單,任一段中心詞以任一值"
       "結尾即中:モンスター 中 効果モンスター、不中 モンスターカード)、目的中心詞(同,比目的片語);欄間 AND。"
       "其餘述詞欄(位置/態/施事者/方式類/動作對象/中心詞類/數量類/修飾語類)評估器支援,但本目錄沒有命名規則、"
       "要用時先補。節點名不另存、由述詞機械組出(catalog.py name_of):詞元;←來源、→目的、:來源→目的、@所在"
       "(區域寫日文 手札/デッキ/EXデッキ/墓地/除外/フィールド/Pゾーン,玩家前綴連寫 自分/相手/お互いの);"
       ":受事者中心詞(多個以 / 並列);→目的中心詞;(耐性)/(限制)。宣告 大類 的具名查詢路徑是 宣告的大類 › 詞元節點 › 名,"
       "宣告 中類 的是 大類 › 中類 › 名(詞元層省掉);大類/中類的命中是底下具名查詢的聯集,由樹推得。建置期檢查"
       "(catalog.py):值在值域、名字全目錄唯一、宣告的大類/中類存在、清單裡的中類都有具名查詢且不與同大類的具名"
       "查詢同名、每個大類至少一個具名查詢、節點名不含 ›、用了沒有命名規則的欄;每個具名查詢在全語料三個位置合計至少"
       "命中一張(票 08)。")


def rewrite_leaf(spec, lemma, negation, problems):
    """舊葉物件 → 具名查詢節點(預設葉回 None)。"""
    pred = {FIELD_LEMMA: lemma}
    if negation:
        pred[FIELD_NEGATION] = list(negation)
    node = {}
    for key, value in spec.items():
        if key in REGION_OF:
            field, player_key = REGION_OF[key]
            player = spec.get(player_key)
            pred[field] = [[PLAYER_OF[player] if player else None, value]]
        elif key in HEAD_OF:
            pred[HEAD_OF[key]] = list(value)
        elif key in ("來源玩家", "目的玩家", "所在玩家"):
            if key[:2] not in spec:
                problems.append("詞元 %s 的葉 %s 綁在沒有的區域上:%s" % (lemma, key, json.dumps(spec, ensure_ascii=False)))
        elif key in (catalog.KEY_MAJOR, catalog.KEY_MIDDLE):
            node[key] = value
        else:
            problems.append("詞元 %s 的葉有不認得的鍵 %s:%s" % (lemma, key, json.dumps(spec, ensure_ascii=False)))
    if len(pred) == 1 + bool(negation):
        return None, node           # 預設葉:刪,宣告的大類/中類交給詞元節點
    return dict({catalog.KEY_PREDICATE: pred}, **node), None


def rewrite_lemma(node, problems):
    lemma = node["詞元"]
    negation = NEGATION_OF.get(node.get("極性類"))
    out = {catalog.KEY_PREDICATE: dict({FIELD_LEMMA: lemma}, **({FIELD_NEGATION: negation} if negation else {}))}
    children = []
    for spec in node.get("子") or []:
        query, inherited = rewrite_leaf(spec, lemma, negation, problems)
        if query is not None:
            children.append(query)
        else:
            out.update(inherited)
    unknown = set(node) - {"詞元", "極性類", "子"}
    if unknown:
        problems.append("詞元節點 %s 有不認得的鍵:%s" % (lemma, "、".join(sorted(unknown))))
    if children:
        out[catalog.KEY_CHILDREN] = children
    return out


def rewrite(node, problems):
    if "大類" in node:
        out = {catalog.KEY_MAJOR: node["大類"]}
        if "中類" in node:
            out[catalog.KEY_MIDDLE] = list(node["中類"])
        out[catalog.KEY_CHILDREN] = [rewrite(child, problems) for child in node.get("子") or []]
        return out
    return rewrite_lemma(node, problems)


def dump_node(node, indent):
    """一個節點一行;帶子的節點把 子 攤開成多行(與舊樹檔同形,diff 好讀)。"""
    pad = "  " * indent
    if catalog.KEY_CHILDREN not in node:
        return pad + json.dumps(node, ensure_ascii=False)
    head = json.dumps({k: v for k, v in node.items() if k != catalog.KEY_CHILDREN}, ensure_ascii=False)
    lines = [pad + head[:-1] + ', "%s": [' % catalog.KEY_CHILDREN]
    lines.append(",\n".join(dump_node(child, indent + 1) for child in node[catalog.KEY_CHILDREN]))
    lines.append(pad + "]}")
    return "\n".join(lines)


def serialize(doc):
    return ('{\n"說明": %s,\n"樹": [\n%s\n]\n}\n'
            % (json.dumps(doc["說明"], ensure_ascii=False), ",\n".join(dump_node(n, 1) for n in doc["樹"])))


def old_names(tree):
    """舊樹的 (舊名, 種類) 清單,樹序:每個詞元節點一筆,底下每片葉一筆(預設葉的名字就是詞元節點名)。"""
    out = []
    for leaves in tree.by_key.values():
        if not leaves:
            continue
        node = leaves[0].node
        out.append((node, KIND_LEMMA))
        out.extend((leaf.name, KIND_DEFAULT if leaf.name == node else KIND_LEAF) for leaf in leaves)
    return out


def main(argv=None):
    with open(OLD, encoding="utf-8") as f:
        old = json.load(f)
    problems = []
    doc = {"說明": DOC, "樹": [rewrite(node, problems) for node in old["樹"]]}
    text = serialize(doc)
    try:
        new = catalog.Catalog(json.loads(text))
    except catalog.CatalogError as e:
        problems.append(str(e))
        new = None
    mapping = []
    if new is not None:
        new_names = {q.name for q in new.queries}
        for old_name, kind in old_names(categories.load_tree(OLD)):
            if old_name in new_names:
                mapping.append([old_name, kind, old_name])
            else:
                problems.append("舊%s %s 在新目錄裡找不到同名節點" % (kind, old_name))
        extra = sorted(new_names - {old_name for old_name, _ in old_names(categories.load_tree(OLD))})
        problems.extend("新節點 %s 沒有對應的舊葉/舊節點" % name for name in extra)
    if problems:
        print("編不出來 %d 項:" % len(problems))
        print("\n".join(problems))
        return 1
    with open(NEW, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    with open(MAPPING, "w", encoding="utf-8", newline="\n") as f:
        doc = ("舊類別樹 category_tree.json 的葉與詞元節點 → 具名查詢目錄 catalog.json 的節點名(一次性改寫的對應表,"
               "rewrite_tree.py 產生;每筆 [舊名, 種類 葉/預設葉/詞元節點, 新名];預設葉刪掉、對到詞元節點;"
               "test_07_catalog 用它守真目錄的節點名——目錄改了節點時同步改本表)。")
        rows = ",\n".join(json.dumps(row, ensure_ascii=False) for row in mapping)
        f.write('{\n"說明": %s,\n"對應": [\n%s\n]\n}\n' % (json.dumps(doc, ensure_ascii=False), rows))
    kinds = {}
    for _, kind, _ in mapping:
        kinds[kind] = kinds.get(kind, 0) + 1
    print("寫出 %s:具名查詢 %d、大類 %d" % (NEW, len(new.queries), len(new.majors)))
    print("對應表 %s:%d 筆(%s);編不出來 0" % (MAPPING, len(mapping), "、".join("%s %d" % kv for kv in kinds.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
