# -*- coding: utf-8 -*-
"""具名查詢目錄(named-queries 票 07,ADR-0018):目錄檔 catalog.json 的載入、檢查、命名。

動作類別第三版:類別樹退成一本具名查詢的目錄,每個節點直接是一個框架述詞(predicate.py 的字彙),框架可同時
命中好幾個、不互斥、沒有預設葉。本模組只做載入、檢查、命名與樹的推得(路徑、大類/中類的聯集);命中與張數
在票 08(predicate.matcher/card_sets)。不 import 舊歸葉程式 categories.py——舊樹檔 category_tree.json 凍結、
只給過渡期的舊歸葉用,規格 3 一起刪。

目錄檔(catalog.json,頂層 {"說明", "樹"})的節點三種:
    大類      {"大類": 名, "中類"?: [中類名…], "子": [節點…]}——只有頂層大類可列中類
    中類      只在大類的清單宣告(名字),具名查詢以 "中類" 掛上去;路徑 大類 › 中類 › 具名查詢(詞元層省掉)
    具名查詢  {"述詞": {欄: 值…}, "子"?: [具名查詢…], "大類"?: 頂層大類名, "中類"?: 中類名}
              述詞只有 詞元/極性/否定形 的具名查詢是詞元節點(Node.lemma_node;帶不帶子無關——召喚 這類詞元節點沒有子,
              真目錄 236 個具名查詢裡詞元節點 100、帶子的 35);頂層的具名查詢自成大類(破壊)
述詞的欄用 predicate.FIELDS 的字;本規格目錄只開 詞元(單值,必填)、極性、否定形、來源/目的/所在
([玩家或 null, 區域七值] 的清單,null 不看玩家)、受事者中心詞、目的中心詞(字串清單,尾綴比對)。
極性省略是目錄的預設(評估器對沒寫的欄一律不看,票 06 假設 2):載入時補成明文清單——沒寫否定形 → [肯定, 可能]
(規格「詞元節點極性」(a)),寫了否定形 → [否定](否定形只在否定框架上,這是唯一不空的選擇)。

命名(節點名由述詞機械組出,寫法沿用第二版):詞元;區域段 ←來源、→目的、:來源→目的、@所在(區域寫日文卡文
ZONE_LABEL;玩家前綴連寫 自分/相手/お互いの);:受事者中心詞(多個以 / 並列);→目的中心詞(同);否定形集合等於
耐性集合 {受身, 不成不受} 寫 (耐性)、等於 {不可能} 寫 (限制);詞元節點就是詞元名。組不出名字的述詞——用了本規格
沒給命名規則的欄(NAMED_FIELDS 以外)、區域欄多值、玩家 相對/無、其他否定形集合、極性不是預設——建置失敗。

檢查(違反即 CatalogError,訊息列全部違反處):每個值在值域(predicate.problems,含詞元是正規詞元)、名字唯一的
口徑(2026-11-01 code review 修正時寫明,不改行為):具名查詢之間唯一、頂層節點(大類與自成大類的具名查詢)之間唯一;
大類與它底下的同名具名查詢合法(大類 召喚 底下的詞元節點 召喚——路徑 召喚 › 召喚 收合成 召喚,網址與總覽都收合;
test_07_catalog 守)、宣告的大類存在(頂層大類)、宣告的中類在所掛大類的清單裡、清單裡的中類都有具名
查詢、中類不與同大類的具名查詢或大類同名、每個大類至少一個具名查詢(掛在它底下或宣告到它的)、節點名不含網址
路徑分隔符 PATH_SEP、不認得的鍵。「每個具名查詢在全語料至少命中一張」在票 08。

接縫:load(path) → Catalog。Catalog.queries 是全部具名查詢(目錄序),每個 Node 帶 name、predicate(明文)、
path(大類 › 中類或詞元節點 › 名;宣告的大類取代本家、中類取代詞元層;相鄰同名只留一個——與舊路徑同形)、
major、home、middle、children;majors/middles 是頂層大類序與中類表;members(大類, 中類=None) 是底下具名
查詢名的聯集(票 08:大類/中類的命中由此推得、不另存)。
"""
import json
import os

import predicate
from closed_values import PLAYERS
from constraints import POL_AFFIRM, POL_CAN, POL_NEG
from negation import CANNOT, NOT_BECOME, PASSIVE
from predicate import (FIELD_GOAL, FIELD_GOAL_HEAD, FIELD_LEMMA, FIELD_NEGATION, FIELD_PATIENT_HEAD, FIELD_PLACE,
                       FIELD_POLARITY, FIELD_SOURCE)

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "catalog.json")

# 網址以 › 連寫節點路徑(category-search spec「網址 hash」),節點名不能含它;舊匯出 export_categories 從這裡 import
PATH_SEP = "›"

# 目錄檔的鍵
KEY_MAJOR, KEY_MIDDLE, KEY_CHILDREN, KEY_PREDICATE = "大類", "中類", "子", "述詞"
KIND_MAJOR, KIND_QUERY = "大類", "具名查詢"

# 區域七值 → 節點名裡的日文卡文區域名(第二版葉名的寫法,2026-10-16 定案;2026-11-01 規格 2 裁定命名沿用第二版;
# 舊歸葉 categories.py 從這裡 import)
ZONE_LABEL = {"手牌": "手札", "牌組": "デッキ", "額外牌組": "EXデッキ", "墓地": "墓地",
              "除外": "除外", "場上": "フィールド", "靈擺區": "Pゾーン"}
# 節點名裡可寫的玩家與它的前綴(2026-10-19 類別線裁定「無」不切;2026-11-01 規格 2「玩家相對與無」(a):相對/無 留在
# 值域、目錄不宣告——沒有命名規則;舊歸葉 categories.py 從這裡推它的 places 拼法對照)
PLAYER_LABEL = {PLAYERS[0]: "自分", PLAYERS[1]: "相手", PLAYERS[2]: "お互いの"}
# 否定形集合 → 名字的尾綴(2026-11-01 規格 2 裁定:耐性 = {受身, 不成不受}、限制 = {不可能});其他集合沒有命名規則
NEGATION_LABEL = ((frozenset((PASSIVE, NOT_BECOME)), "耐性"), (frozenset((CANNOT,)), "限制"))
# 極性的預設(2026-11-01 規格 2「詞元節點極性」(a):省略時補 肯定與可能);寫了否定形的述詞極性只能是 否定
DEFAULT_POLARITY = [POL_AFFIRM, POL_CAN]
NEGATIVE_POLARITY = [POL_NEG]
# 本規格給了命名規則的欄(2026-11-01 規格 2 命名規則段);其餘欄要進目錄時先補命名規則
REGION_ARROWS = ((FIELD_SOURCE, "←"), (FIELD_GOAL, "→"), (FIELD_PLACE, "@"))
NAMED_FIELDS = (FIELD_LEMMA, FIELD_POLARITY, FIELD_NEGATION, FIELD_SOURCE, FIELD_GOAL, FIELD_PLACE,
                FIELD_PATIENT_HEAD, FIELD_GOAL_HEAD)
# 詞元節點的判準(2026-11-01 票 09 裁定、GLOSSARY 第三版段):述詞只有這三欄(極性是預設、否定形是耐性/限制的極性類
# 節點);report.py 與 prepare_view.py 的節點數讀 Node.lemma_node
LEMMA_NODE_FIELDS = frozenset((FIELD_LEMMA, FIELD_POLARITY, FIELD_NEGATION))


class CatalogError(ValueError):
    """目錄檢查失敗(訊息逐條列出違反處)。"""


def explicit(pred):
    """目錄檔寫的述詞 → 明文述詞:極性省略時補成清單(沒寫否定形 → 肯定與可能;寫了 → 否定);其餘照抄。"""
    out = dict(pred)
    if FIELD_POLARITY not in out:
        out[FIELD_POLARITY] = list(NEGATIVE_POLARITY if FIELD_NEGATION in out else DEFAULT_POLARITY)
    return out


def _zone_label(pred, field, problems):
    """區域欄 → 名字裡的段(玩家前綴 + 區域名);多值、相對/無、表外區域沒有命名規則。"""
    items = predicate.values_of(pred, field)
    if len(items) != 1:
        problems.append("%s 多值沒有命名規則(本規格每欄一項)" % field)
        return "?"
    item = items[0]
    if not (isinstance(item, (list, tuple)) and len(item) == 2):
        return "?"                      # 形狀錯誤由 predicate.problems 報
    player, zone = item
    if player is not None and player not in PLAYER_LABEL:
        problems.append("%s 的玩家 %s 沒有命名規則(目錄只寫 %s 或不寫玩家)"
                        % (field, player, "/".join(PLAYER_LABEL)))
    return (PLAYER_LABEL.get(player, "") if player else "") + ZONE_LABEL.get(zone, "?")


def name_of(pred):
    """明文述詞 → (節點名, 命名問題清單);組不出名字的部分以 ? 佔位、問題逐條列。"""
    problems = ["沒有命名規則的欄:%s" % field for field in pred if field not in NAMED_FIELDS]
    lemma = pred.get(FIELD_LEMMA)
    if not (isinstance(lemma, str) and lemma):
        problems.append("述詞要有單值的詞元:%s" % json.dumps(pred, ensure_ascii=False))
        lemma = "?"
    zones = {field: _zone_label(pred, field, problems) for field, _ in REGION_ARROWS if field in pred}
    name = lemma
    if FIELD_SOURCE in zones and FIELD_GOAL in zones:
        name += ":%s→%s" % (zones[FIELD_SOURCE], zones[FIELD_GOAL])
    else:
        for field, arrow in REGION_ARROWS[:2]:
            if field in zones:
                name += arrow + zones[field]
    if FIELD_PLACE in zones:
        name += "@" + zones[FIELD_PLACE]
    for field, mark in ((FIELD_PATIENT_HEAD, ":"), (FIELD_GOAL_HEAD, "→")):
        if field in pred:
            name += mark + "/".join(str(v) for v in predicate.values_of(pred, field))
    polarity = set(predicate.values_of(pred, FIELD_POLARITY)) if FIELD_POLARITY in pred else set()
    if FIELD_NEGATION in pred:
        forms = frozenset(predicate.values_of(pred, FIELD_NEGATION))
        label = next((label for wanted, label in NEGATION_LABEL if forms == wanted), None)
        if label is None:
            problems.append("否定形集合沒有命名規則:{%s}(耐性是 {%s}、限制是 {%s})"
                            % ("、".join(sorted(forms)), "、".join(NEGATION_LABEL[0][0]), "、".join(NEGATION_LABEL[1][0])))
            label = "?"
        name += "(%s)" % label
        if polarity != set(NEGATIVE_POLARITY):
            problems.append("極性沒有命名規則:{%s}(寫了否定形的述詞極性只能是 %s)"
                            % ("、".join(sorted(polarity)), POL_NEG))
    elif polarity != set(DEFAULT_POLARITY):
        problems.append("極性沒有命名規則:{%s}(沒寫否定形的述詞極性只能是預設的 %s)"
                        % ("、".join(sorted(polarity)), "、".join(DEFAULT_POLARITY)))
    return name, problems


class Node:
    """目錄的一個節點:大類(predicate 是 None)或具名查詢(predicate 是明文述詞)。ancestors 是樹位置上
    從頂層到父節點的名字;home 是本家(頂層節點名,頂層節點自己就是本家);declared/middle 是宣告的大類/中類;
    major 是宣告的大類或本家;path 是 大類 › 中類或詞元節點 › 名(宣告的大類取代本家、中類取代詞元層;相鄰
    同名只留一個);lemma_node 是「述詞只有詞元/極性/否定形」的詞元節點(大類節點 False)。"""

    def __init__(self, kind, name, ancestors, pred=None, declared=None, middle=None):
        self.kind = kind
        self.name = name
        self.predicate = pred
        self.lemma_node = pred is not None and set(pred) <= LEMMA_NODE_FIELDS
        self.children = []
        self.declared = declared
        self.middle = middle
        self.home = ancestors[0] if ancestors else name
        self.major = declared if declared is not None else self.home
        if middle is not None:
            steps = (self.major, middle)
        elif declared is not None and declared != self.home:
            steps = (self.major,) + ancestors[-1:]
        else:
            steps = ancestors
        path = []
        for step in steps + (name,):
            if not path or path[-1] != step:
                path.append(step)
        self.path = tuple(path)


class Catalog:
    """目錄:載入即檢查,違反 raise CatalogError。"""

    def __init__(self, data):
        self.majors = []            # 頂層節點名(大類與自成大類的具名查詢),目錄序
        self.middles = {}           # 頂層大類名 → 中類清單
        self.queries = []           # 全部具名查詢,目錄序
        self.by_name = {}           # 具名查詢名 → Node
        self.roots = []
        self._major_nodes = set()   # 頂層大類節點名(宣告的大類只能是這些)
        errors = []
        for node in data["樹"]:
            self.roots.append(self._parse(node, (), errors))
        self._check_names(errors)
        self._check_majors(errors)
        self._check_middles(errors)
        if errors:
            raise CatalogError("具名查詢目錄檢查失敗:\n" + "\n".join(errors))

    # ── 載入 ──

    def _parse(self, node, ancestors, errors):
        """節點 dict → Node(子節點遞迴);錯誤記進 errors、仍回一個 Node 讓後面的檢查能列完。"""
        where = PATH_SEP.join(ancestors) or "樹"
        if not isinstance(node, dict) or not (KEY_MAJOR in node or KEY_PREDICATE in node):
            errors.append("%s 底下的節點不是大類也不是具名查詢:%s" % (where, json.dumps(node, ensure_ascii=False)))
            return Node(KIND_MAJOR, "?", ancestors)
        if KEY_PREDICATE not in node:        # 具名查詢的 大類 鍵是宣告;沒有述詞的才是大類節點
            return self._parse_major(node, ancestors, errors)
        unknown = sorted(set(node) - {KEY_PREDICATE, KEY_CHILDREN, KEY_MAJOR, KEY_MIDDLE})
        if unknown:
            errors.append("%s 底下的具名查詢有不認得的鍵:%s" % (where, "、".join(unknown)))
        pred = node[KEY_PREDICATE]
        if not isinstance(pred, dict):
            errors.append("%s 底下的述詞要是物件:%r" % (where, pred))
            pred = {}
        pred = explicit(pred)
        name, naming = name_of(pred)
        errors.extend("具名查詢 %s:%s" % (name, p) for p in predicate.problems(pred) + naming)
        if PATH_SEP in name:
            errors.append("節點名含網址路徑分隔符 %s:%s" % (PATH_SEP, name))
        declared, middle = node.get(KEY_MAJOR), node.get(KEY_MIDDLE)
        for key, value in ((KEY_MAJOR, declared), (KEY_MIDDLE, middle)):
            if value is not None and not (isinstance(value, str) and value):
                errors.append("具名查詢 %s 宣告的%s要是名字:%r" % (name, key, value))
        query = Node(KIND_QUERY, name, ancestors, pred, declared, middle)
        if not ancestors:
            self.majors.append(name)
        self.queries.append(query)
        self.by_name.setdefault(name, query)
        children = node.get(KEY_CHILDREN) or []
        for child in children:
            query.children.append(self._parse(child, ancestors + (name,), errors))
        return query

    def _parse_major(self, node, ancestors, errors):
        name = node[KEY_MAJOR]
        if not (isinstance(name, str) and name):
            errors.append("大類名要是字串:%r" % (name,))
            name = "?"
        if PATH_SEP in name:
            errors.append("節點名含網址路徑分隔符 %s:%s" % (PATH_SEP, name))
        unknown = sorted(set(node) - {KEY_MAJOR, KEY_MIDDLE, KEY_CHILDREN})
        if unknown:
            errors.append("大類 %s 有不認得的鍵:%s" % (name, "、".join(unknown)))
        if KEY_MIDDLE in node:
            middles = node[KEY_MIDDLE]
            if ancestors:
                errors.append("大類 %s 不是頂層大類,不能列中類" % name)
            elif not (isinstance(middles, list) and middles and all(isinstance(m, str) and m for m in middles)):
                errors.append("大類 %s 的中類清單要是非空字串清單:%r" % (name, middles))
            else:
                errors.extend("大類 %s 的中類清單重複:%s" % (name, m) for m in sorted({m for m in middles if middles.count(m) > 1}))
                self.middles[name] = list(middles)
        if not ancestors:
            self.majors.append(name)
            self._major_nodes.add(name)
        out = Node(KIND_MAJOR, name, ancestors)
        for child in node.get(KEY_CHILDREN) or []:
            out.children.append(self._parse(child, ancestors + (name,), errors))
        return out

    # ── 檢查 ──

    def _check_names(self, errors):
        seen = set()
        for query in self.queries:
            if query.name in seen:
                errors.append("名字重複:%s" % query.name)
            seen.add(query.name)
        errors.extend("大類名重複:%s" % m for m in sorted({m for m in self.majors if self.majors.count(m) > 1}))

    def _check_majors(self, errors):
        for query in self.queries:
            if query.declared is not None and query.declared not in self._major_nodes:
                errors.append("具名查詢 %s 宣告的大類 %s 不是頂層大類" % (query.name, query.declared))
        majors = {query.major for query in self.queries}
        for root in self.roots:
            if root.kind != KIND_MAJOR:
                continue
            if not any(q.home == root.name for q in self.queries):
                errors.append("大類 %s 底下沒有具名查詢" % root.name)
            elif root.name not in majors:
                errors.append("大類 %s 底下的具名查詢都宣告到別的大類" % root.name)

    def _check_middles(self, errors):
        used = {(q.major, q.middle) for q in self.queries if q.middle is not None}
        for query in self.queries:
            if query.middle is None or query.middle in self.middles.get(query.major, ()):
                continue
            errors.append("具名查詢 %s 宣告的中類 %s 不在大類 %s 的中類清單" % (query.name, query.middle, query.major))
        names = {(major, q.name) for q in self.queries for major in (q.home, q.major)}
        for major, middles in self.middles.items():
            for middle in middles:
                if (major, middle) not in used:
                    errors.append("大類 %s 的中類 %s 沒有具名查詢" % (major, middle))
                if (major, middle) in names:
                    errors.append("大類 %s 的中類 %s 與具名查詢同名" % (major, middle))
                if middle == major:
                    errors.append("大類 %s 的中類 %s 與大類同名" % (major, middle))

    # ── 樹的推得 ──

    def members(self, major, middle=None):
        """大類(或大類的中類)底下具名查詢名的聯集,目錄序:掛在它底下或宣告到它的。"""
        return [q.name for q in self.queries
                if q.major == major and (middle is None or q.middle == middle)]

    def walk(self):
        """全部節點深度優先、目錄序:(節點, 深度)。"""
        def visit(node, depth):
            yield node, depth
            for child in node.children:
                yield from visit(child, depth + 1)
        for root in self.roots:
            yield from visit(root, 0)


def load(path=CATALOG):
    with open(path, encoding="utf-8") as f:
        return Catalog(json.load(f))
