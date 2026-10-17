# -*- coding: utf-8 -*-
"""動作類別歸組(.scratch/action-categories 票 01〜):動作框架 → 類別樹的葉。

接在分詞鏈框架抽取之後:讀 frames.json(frames.py 的輸出)與類別樹來源檔
category_tree.json,為每個動作框架寫一列類別紀錄到 frame_categories.json(框架類別檔),
再把每張卡的葉集合分效果組與代價組寫到 card_categories.json(卡層彙總檔,票 04;各自
去重、依樹序,大類與詞元層由樹展開、不另存)。兩份都是決定性建置產物、不入版控。只讀
框架抽取的輸出、不改它;約束框架不歸本樹。

類別樹(格式見 category_tree.json 的「說明」):大類 → 詞元節點 → 葉,分支可不等深;
框架只貼葉、祖先由樹推得。葉名由條件機械組出——來源「詞元←區域」、目的「詞元→區域」、
來源加目的「詞元:來源→目的」、對象關鍵詞「詞元:關鍵詞」(多個關鍵詞以 / 並列)、
否定「詞元(耐性)」「詞元(限制)」;區域在葉名裡寫日文卡文的區域名(手札/デッキ/墓地…),
條件值是區域七值。

規則表語意:主鍵是(動作詞元, 極性類)。極性類是 肯定/耐性/限制:可能視同肯定;否定
依述語形分(票 03)——被動否定(されない)、にならない、受けない 為耐性,可能否定
(できない、行えない)為限制,其餘一般否定(送らず、戻さず)沒有極性類、記未歸。述語形
是唯一讀子句字面的地方(框架抽取只記 否定、沒記述語形);其餘匹配只看框架欄位(動作、
來源、目的、極性、位置、對象):
    條件位       → 不適用(條件框架歸觸發事件軸,另開線)
    匹配到葉     → 已歸,記葉清單與大類(葉所在的頂層節點)
    其餘         → 未歸(詞元沒有節點,或條件全不符且沒有預設葉);沒有「其他」類
來源/目的字面先映成(玩家, 區域清單)(票 02;區域辨識 places.parse_place 在框架線,
frame-args-v3 票 01):玩家 自分/相手/雙方/無 不進葉、記在來源玩家/目的玩家欄;來源字面空著時改讀對象欄開頭的區域(墓地のこのカード、
相手フィールドのカード;票 06);複合字面(手札・墓地)逐區域各匹配一葉,一個框架因此可帶
多個葉(依字面順序、去重),同詞元的葉同大類。同詞元的葉依樹序先到先得。

建置期檢查樹的完整性(葉名全樹唯一、每葉有詞元條件、每大類至少一葉、同詞元的葉
不被前面較寬的葉蓋掉),違反時報錯不產出。

測試接縫是 classify(text, context=""):一句效果句原文(帶同卡同段上文)→ 每個
動作框架的類別紀錄,內部呼叫真的框架抽取與類別樹;卡層彙總經同一接縫多句組裝
(classify_card)。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/categories.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from frames import POL_AFFIRM, POL_NEG, POS_COND, POS_COST, POS_EFFECT  # noqa: E402
from places import parse_place  # noqa: E402

TREE = os.path.join(HERE, "category_tree.json")
FRAMES = os.path.join(HERE, "frames.json")
OUT = os.path.join(HERE, "frame_categories.json")
CARDS_OUT = os.path.join(HERE, "card_categories.json")

STATUS_PLACED = "已歸"
STATUS_UNPLACED = "未歸"
STATUS_NA = "不適用"
STATUSES = (STATUS_PLACED, STATUS_UNPLACED, STATUS_NA)

# 極性類(規則表的主鍵之一;樹的詞元節點以 極性類 宣告,預設肯定)
POL_RESIST = "耐性"
POL_RESTRICT = "限制"
POLARITY_CLASSES = (POL_AFFIRM, POL_RESIST, POL_RESTRICT)
# 否定框架的述語形 → 極性類:取子句裡最後一個否定述語(框架的子句收在它自己的述語);
# 〜ければならない/〜ねばならない 是義務、不是否定述語。
# 受けない 字面是一般否定,但 受ける 的否定就是不受影響,歸耐性;行えない 是五段動詞
# 行う 的可能否定。其餘一般否定(送らず、戻さず、リリースせず)不屬任何一類。
NEGATION_FORMS = (
    (re.compile(r"(?:でき|出来)(?:ない|ず|なく|ませ)|行え(?:ない|ず|なく)"), POL_RESTRICT),
    (re.compile(r"(?:され|(?<!ば)なら|受け)(?:ない|ず|なく)"), POL_RESIST),
)

# 區域七值(值域正典的區域,與第一版同一組)與葉名裡的日文區域名
ZONE_LABEL = {"手牌": "手札", "牌組": "デッキ", "額外牌組": "EXデッキ", "墓地": "墓地",
              "除外": "除外", "場上": "フィールド", "靈擺區": "Pゾーン"}

# 樹來源檔的鍵
KEY_MAJOR = "大類"
KEY_LEMMA = "詞元"
KEY_POLARITY_CLASS = "極性類"
KEY_CHILDREN = "子"
LEAF_KEYS = {"來源": "source", "目的": "goal", "對象": "keywords"}


class TreeError(ValueError):
    """類別樹完整性檢查失敗(訊息逐條列出違反處)。"""


def object_place(literal):
    """對象字面開頭的地點 → (玩家, 區域清單):取第一個認得出區域的「…の」前綴(墓地の
    このカード、相手フィールドの魔法・罠カード、自分の墓地のモンスター),都認不出時整個
    字面再認一次(手札、除外状態のこのカード);認不出回 (None, [])。"""
    if not literal:
        return None, []
    for i, ch in enumerate(literal):
        if ch == "の":
            player, zones = parse_place(literal[:i])
            if zones:
                return player, zones
    return parse_place(literal)


def source_place(frame):
    """框架的來源 → (玩家, 區域清單, 是否取自對象欄)。來源字面空著時,對象欄開頭的區域
    就是來源(墓地のこのカードを除外する、相手フィールドのカードを破壊する;票 06)。"""
    player, zones = parse_place(frame.get("source"))
    if not frame.get("source"):
        object_player, object_zones = object_place(frame.get("object"))
        if object_zones:
            return object_player, object_zones, True
    return player, zones, False


def unplaced_label(frame):
    """未歸框架的聚合標籤與它的 (詞元, 極性類) 鍵(類別總覽與草案的未歸類清單共用):
    肯定記詞元、耐性/限制記 詞元(耐性)/(限制)、一般否定(沒有極性類)記 詞元(否定)、
    鍵為 None。"""
    cls = polarity_class(frame)
    if cls is None:
        return frame["action"] + "(否定)", None
    return leaf_name(frame["action"], cls), (frame["action"], cls)


def polarity_class(frame):
    """框架的極性 → 極性類:可能視同肯定;否定依子句裡最後一個否定述語分耐性/限制,
    一般否定回 None(沒有節點)。"""
    if frame["polarity"] != POL_NEG:
        return POL_AFFIRM
    clause = frame["clause"].replace(" ", "")
    last, found = -1, None
    for pattern, cls in NEGATION_FORMS:
        for m in pattern.finditer(clause):
            if m.end() > last:
                last, found = m.end(), cls
    return found


def leaf_name(lemma, polarity, source=None, goal=None, keywords=()):
    """葉的條件 → 葉名(機械組出)。"""
    name = lemma
    if source and goal:
        name += ":%s→%s" % (ZONE_LABEL[source], ZONE_LABEL[goal])
    elif source:
        name += "←" + ZONE_LABEL[source]
    elif goal:
        name += "→" + ZONE_LABEL[goal]
    if keywords:
        name += ":" + "/".join(keywords)
    if polarity != POL_AFFIRM:
        name += "(%s)" % polarity
    return name


class Leaf:
    """一個葉:所屬詞元節點的(詞元, 極性)加上自己的條件欄;名字由條件組出。
    path 是大類到葉的節點名(詞元節點自己就是葉時、或頂層詞元節點自成大類時,相鄰同名
    只留一個),major 是 path 的頭。"""

    def __init__(self, lemma, polarity, conditions, ancestors):
        self.lemma = lemma
        self.polarity = polarity
        self.source = conditions.get("source")
        self.goal = conditions.get("goal")
        self.keywords = tuple(conditions.get("keywords") or ())
        self.name = leaf_name(lemma, polarity, self.source, self.goal, self.keywords)
        path = []
        for name in ancestors + (self.name,):
            if not path or path[-1] != name:
                path.append(name)
        self.path = tuple(path)
        self.major = self.path[0]

    def covers(self, other):
        """本葉的條件是否涵蓋 other 的全部情形(other 寫在後面就永遠匹配不到)。"""
        if self.source and self.source != other.source:
            return False
        if self.goal and self.goal != other.goal:
            return False
        # 關鍵詞是子字串比對:other 的每個關鍵詞都含本葉某個關鍵詞時,命中 other 的
        # 對象必然也命中本葉(本葉 魔法 蓋掉後面的 魔法・罠)
        if self.keywords and not (other.keywords and all(
                any(mine in theirs for mine in self.keywords)
                for theirs in other.keywords)):
            return False
        return True

    def matches(self, source_zone, goal_zone, obj):
        """框架的(來源區域, 目的區域, 對象字面)是否符合本葉全部條件。"""
        if self.source and self.source != source_zone:
            return False
        if self.goal and self.goal != goal_zone:
            return False
        if self.keywords and not (obj and any(k in obj for k in self.keywords)):
            return False
        return True


class CategoryTree:
    """類別樹:載入時做完整性檢查,classify_frame 把一個動作框架貼到葉上。"""

    def __init__(self, data):
        self.leaves = []            # 樹序
        self.by_key = {}            # (詞元, 極性類) → 該詞元節點的葉(樹序)
        self.majors = []            # 頂層節點名(大類名),樹序
        errors = []
        for node in data["樹"]:
            self._walk(node, (), None, errors)
        seen = set()
        for leaf in self.leaves:
            if leaf.name in seen:
                errors.append("葉名重複:%s" % leaf.name)
            seen.add(leaf.name)
        for name in sorted({m for m in self.majors if self.majors.count(m) > 1}):
            errors.append("大類名重複(頂層節點同名):%s" % name)
        # 同詞元的葉只擋「後面的葉被前面的葉整個蓋住」(永遠匹配不到);部分重疊
        # (來源=墓地 與 目的=手札)合法,依樹序先到先得
        for leaves in self.by_key.values():
            for i, earlier in enumerate(leaves):
                for later in leaves[i + 1:]:
                    if earlier.covers(later):
                        errors.append("葉 %s 被前面的 %s 蓋掉(較具體的葉要寫在前)"
                                      % (later.name, earlier.name))
        if errors:
            raise TreeError("類別樹完整性檢查失敗:\n" + "\n".join(errors))
        self.leaf_order = {leaf.name: i for i, leaf in enumerate(self.leaves)}

    def _walk(self, node, path, major, errors):
        """回傳此節點底下的葉數。"""
        if not isinstance(node, dict):
            errors.append("%s 底下有不是物件的節點:%r" % ("/".join(path) or "樹", node))
            return 0
        if KEY_MAJOR in node:
            name = node[KEY_MAJOR]
            if major is None:
                self.majors.append(name)
            children = node.get(KEY_CHILDREN) or []
            count = sum(self._walk(child, path + (name,), major or name, errors)
                        for child in children)
            if not count:
                errors.append("大類 %s 底下沒有葉" % name)
            return count
        if KEY_LEMMA in node:
            return self._lemma_node(node, path, major, errors)
        errors.append("葉沒有詞元條件(葉要掛在詞元節點底下):%s 底下的 %s"
                      % ("/".join(path) or "樹", json.dumps(node, ensure_ascii=False)))
        return 0

    def _lemma_node(self, node, path, major, errors):
        lemma = node[KEY_LEMMA]
        polarity = node.get(KEY_POLARITY_CLASS, POL_AFFIRM)
        if polarity not in POLARITY_CLASSES:
            errors.append("詞元節點 %s 的極性類 %r 不是 %s"
                          % (lemma, polarity, "/".join(POLARITY_CLASSES)))
            return 0
        key = (lemma, polarity)
        if key in self.by_key:
            errors.append("詞元節點重複:%s(%s)" % (lemma, polarity))
            return 0
        unknown = set(node) - {KEY_LEMMA, KEY_POLARITY_CLASS, KEY_CHILDREN}
        if unknown:
            errors.append("詞元節點 %s 有不認得的鍵:%s" % (lemma, "、".join(sorted(unknown))))
        node_name = leaf_name(lemma, polarity)
        if major is None:           # 頂層詞元節點自成大類
            self.majors.append(node_name)
        children = node.get(KEY_CHILDREN)
        specs = children if children else [{}]
        leaves = []
        for spec in specs:
            conditions = self._conditions(spec, lemma, errors)
            if conditions is not None:
                leaves.append(Leaf(lemma, polarity, conditions, path + (node_name,)))
        self.by_key[key] = leaves
        self.leaves.extend(leaves)
        return len(leaves)

    @staticmethod
    def _conditions(spec, lemma, errors):
        if not isinstance(spec, dict) or KEY_MAJOR in spec or KEY_LEMMA in spec:
            errors.append("詞元節點 %s 底下只能掛葉:%s"
                          % (lemma, json.dumps(spec, ensure_ascii=False)))
            return None
        unknown = set(spec) - set(LEAF_KEYS)
        if unknown:
            errors.append("詞元 %s 的葉有不認得的條件欄:%s" % (lemma, "、".join(sorted(unknown))))
            return None
        conditions = {LEAF_KEYS[k]: v for k, v in spec.items()}
        for field in ("source", "goal"):
            if field in conditions and conditions[field] not in ZONE_LABEL:
                errors.append("詞元 %s 的葉區域 %r 不在區域七值" % (lemma, conditions[field]))
                return None
        keywords = conditions.get("keywords")
        if keywords is not None and (not isinstance(keywords, list) or not keywords
                                     or not all(isinstance(k, str) and k for k in keywords)):
            errors.append("詞元 %s 的葉對象關鍵詞要是非空字串清單:%r" % (lemma, keywords))
            return None
        return conditions

    def classify_frame(self, frame):
        """一個動作框架 → 類別紀錄(動作、狀態、葉清單、大類、來源玩家、目的玩家)。

        複合來源/目的逐(來源區域, 目的區域)組合各匹配一葉(依字面順序、去重);認不出
        區域的一邊以 None 參與匹配。條件位不適用,玩家欄也不填。"""
        record = {"action": frame["action"], "status": STATUS_UNPLACED, "leaves": [],
                  "major": None, "source_player": None, "goal_player": None}
        if frame["position"] == POS_COND:
            record["status"] = STATUS_NA
            return record
        source_player, source_zones, _ = source_place(frame)
        goal_player, goal_zones = parse_place(frame.get("goal"))
        record.update(source_player=source_player, goal_player=goal_player)
        candidates = self.by_key.get((frame["action"], polarity_class(frame)), ())
        matched = []
        for source_zone in source_zones or [None]:
            for goal_zone in goal_zones or [None]:
                for leaf in candidates:
                    if leaf.matches(source_zone, goal_zone, frame.get("object")):
                        if leaf not in matched:
                            matched.append(leaf)
                        break
        if matched:
            # 同一詞元節點的葉同大類(樹的設計保證),取第一葉的
            record.update(status=STATUS_PLACED, leaves=[leaf.name for leaf in matched],
                          major=matched[0].major)
        return record


def load_tree(path=TREE):
    with open(path, encoding="utf-8") as f:
        return CategoryTree(json.load(f))


_DEFAULT = None


def default_tree():
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = load_tree()
    return _DEFAULT


def classified(tree, sentence_frames):
    """一句的框架清單 → 動作框架與它的類別紀錄 (框架, 紀錄),依原文順序;約束框架略過。"""
    return [(f, tree.classify_frame(f)) for f in sentence_frames if f["kind"] == KIND_ACTION]


def classify(text, context=""):
    """接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄(依原文順序)。"""
    return [record for _, record in classified(default_tree(), frames.extract(text, context))]


def rollup(pairs, tree):
    """一張卡的(位置, 類別紀錄)→ 卡層彙總 {"effect": 葉名清單, "cost": 葉名清單}:
    只收已歸的效果位與代價位,各自去重、依樹序排。"""
    groups = {POS_EFFECT: set(), POS_COST: set()}
    for position, record in pairs:
        if record["status"] == STATUS_PLACED and position in groups:
            groups[position].update(record["leaves"])
    order = tree.leaf_order
    return {"effect": sorted(groups[POS_EFFECT], key=order.__getitem__),
            "cost": sorted(groups[POS_COST], key=order.__getitem__)}


def classify_card(sentences):
    """接縫的多句組裝:一張卡的幾句效果句原文(字串,或 (原文, 上文))→ 卡層彙總。"""
    tree = default_tree()
    pairs = []
    for sentence in sentences:
        text, context = (sentence, "") if isinstance(sentence, str) else sentence
        pairs.extend((f["position"], record)
                     for f, record in classified(tree, frames.extract(text, context)))
    return rollup(pairs, tree)


def main():
    try:
        tree = load_tree()
    except TreeError as e:
        print(e, file=sys.stderr)
        return 1
    with open(FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    out = []
    per_card = {}
    for s in sentences:
        pairs = per_card.setdefault(s["card"], [])
        for fr, record in classified(tree, s["frames"]):
            row = {"card": s["card"], "section": s["section"], "index": s["index"],
                   "order": fr["order"]}
            row.update(record)
            out.append(row)
            pairs.append((fr["position"], record))
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
        f.write("\n")
    cards = [dict({"card": card}, **rollup(per_card[card], tree)) for card in sorted(per_card)]
    with open(CARDS_OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cards, f, ensure_ascii=False, indent=0)
        f.write("\n")
    counts = {status: sum(r["status"] == status for r in out) for status in STATUSES}
    placed = counts[STATUS_PLACED] + counts[STATUS_UNPLACED]
    print("動作框架 %d:已歸 %d、未歸 %d、不適用 %d;已歸比例 %.2f%%(已歸/(已歸+未歸))" % (
        len(out), counts[STATUS_PLACED], counts[STATUS_UNPLACED], counts[STATUS_NA],
        100.0 * counts[STATUS_PLACED] / max(1, placed)))
    print("類別樹葉 %d;已寫出 %s" % (len(tree.leaves), OUT))
    print("卡 %d(效果組有葉 %d、代價組有葉 %d);已寫出 %s" % (
        len(cards), sum(bool(c["effect"]) for c in cards),
        sum(bool(c["cost"]) for c in cards), CARDS_OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
