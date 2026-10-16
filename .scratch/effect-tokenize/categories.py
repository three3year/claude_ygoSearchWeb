# -*- coding: utf-8 -*-
"""動作類別歸組(.scratch/action-categories 票 01〜):動作框架 → 類別樹的葉。

接在分詞鏈框架抽取之後:讀 frames.json(frames.py 的輸出)與類別樹來源檔
category_tree.json,為每個動作框架寫一列類別紀錄到 frame_categories.json(決定性
建置產物,不入版控)。只讀框架抽取的輸出、不改它;約束框架不歸本樹。

類別樹(格式見 category_tree.json 的「說明」):大類 → 詞元節點 → 葉,分支可不等深;
框架只貼葉、祖先由樹推得。葉名由條件機械組出——來源「詞元←區域」、目的「詞元→區域」、
來源加目的「詞元:來源→目的」、對象關鍵詞「詞元:關鍵詞」、否定「詞元(否定)」;區域在
葉名裡寫日文卡文的區域名(手札/デッキ/墓地…),條件值是區域七值。

規則表語意:主鍵是(動作詞元, 極性)——可能視同肯定;同詞元的葉依樹序先到先得。
匹配只看框架欄位(動作、來源、目的、極性、位置、對象),不看子句字面:
    條件位       → 不適用(條件框架歸觸發事件軸,另開線)
    匹配到葉     → 已歸,記葉清單與大類(葉所在的頂層節點)
    其餘         → 未歸(詞元沒有節點,或條件全不符且沒有預設葉);沒有「其他」類

建置期檢查樹的完整性(葉名全樹唯一、每葉有詞元條件、每大類至少一葉、同詞元的葉
不被前面較寬的葉蓋掉),違反時報錯不產出。

測試接縫是 classify(text, context=""):一句效果句原文(帶同卡同段上文)→ 每個
動作框架的類別紀錄,內部呼叫真的框架抽取與類別樹。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/categories.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from frames import POL_AFFIRM, POL_NEG, POS_COND  # noqa: E402

TREE = os.path.join(HERE, "category_tree.json")
FRAMES = os.path.join(HERE, "frames.json")
OUT = os.path.join(HERE, "frame_categories.json")

STATUS_PLACED = "已歸"
STATUS_UNPLACED = "未歸"
STATUS_NA = "不適用"
STATUSES = (STATUS_PLACED, STATUS_UNPLACED, STATUS_NA)

# 區域七值(值域正典的區域,與第一版同一組)與葉名裡的日文區域名
ZONE_LABEL = {"手牌": "手札", "牌組": "デッキ", "額外牌組": "EXデッキ", "墓地": "墓地",
              "除外": "除外", "場上": "フィールド", "靈擺區": "Pゾーン"}
# 來源/目的字面 → 區域:票 01 只認單一區域的整詞(去掉玩家前綴);玩家欄、複合字面
# 與其餘寫法在票 02
ZONE_OF = {label: zone for zone, label in ZONE_LABEL.items()}
ZONE_OF["エクストラデッキ"] = "額外牌組"
PLAYER_PREFIXES = ("自分の", "相手の", "自分", "相手")

# 樹來源檔的鍵
KEY_MAJOR = "大類"
KEY_LEMMA = "詞元"
KEY_POLARITY = "極性"
KEY_CHILDREN = "子"
LEAF_KEYS = {"來源": "source", "目的": "goal", "對象": "keywords"}


class TreeError(ValueError):
    """類別樹完整性檢查失敗(訊息逐條列出違反處)。"""


def zone_of(literal):
    """來源/目的字面 → 區域七值;對不上時 None。"""
    if not literal:
        return None
    for prefix in PLAYER_PREFIXES:
        if literal.startswith(prefix) and literal[len(prefix):] in ZONE_OF:
            return ZONE_OF[literal[len(prefix):]]
    return ZONE_OF.get(literal)


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
    if polarity == POL_NEG:
        name += "(否定)"
    return name


class Leaf:
    """一個葉:所屬詞元節點的(詞元, 極性)加上自己的條件欄;名字由條件組出。"""

    def __init__(self, lemma, polarity, conditions, major):
        self.lemma = lemma
        self.polarity = polarity
        self.source = conditions.get("source")
        self.goal = conditions.get("goal")
        self.keywords = tuple(conditions.get("keywords") or ())
        self.name = leaf_name(lemma, polarity, self.source, self.goal, self.keywords)
        self.major = major

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
        self.by_key = {}            # (詞元, 極性) → 該詞元節點的葉(樹序)
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
        polarity = node.get(KEY_POLARITY, POL_AFFIRM)
        if polarity not in (POL_AFFIRM, POL_NEG):
            errors.append("詞元節點 %s 的極性 %r 不是 肯定/否定" % (lemma, polarity))
            return 0
        key = (lemma, polarity)
        if key in self.by_key:
            errors.append("詞元節點重複:%s(%s)" % (lemma, polarity))
            return 0
        unknown = set(node) - {KEY_LEMMA, KEY_POLARITY, KEY_CHILDREN}
        if unknown:
            errors.append("詞元節點 %s 有不認得的鍵:%s" % (lemma, "、".join(sorted(unknown))))
        if major is None:           # 頂層詞元節點自成大類
            major = leaf_name(lemma, polarity)
            self.majors.append(major)
        children = node.get(KEY_CHILDREN)
        specs = children if children else [{}]
        leaves = []
        for spec in specs:
            conditions = self._conditions(spec, lemma, errors)
            if conditions is not None:
                leaves.append(Leaf(lemma, polarity, conditions, major))
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
        """一個動作框架 → 類別紀錄(動作、狀態、葉清單、大類、來源玩家、目的玩家)。"""
        record = {"action": frame["action"], "status": STATUS_UNPLACED, "leaves": [],
                  "major": None, "source_player": None, "goal_player": None}
        if frame["position"] == POS_COND:
            record["status"] = STATUS_NA
            return record
        polarity = POL_NEG if frame["polarity"] == POL_NEG else POL_AFFIRM
        source_zone, goal_zone = zone_of(frame.get("source")), zone_of(frame.get("goal"))
        for leaf in self.by_key.get((frame["action"], polarity), ()):
            if leaf.matches(source_zone, goal_zone, frame.get("object")):
                record.update(status=STATUS_PLACED, leaves=[leaf.name], major=leaf.major)
                break
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


def classify(text, context=""):
    """接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄(依原文順序)。"""
    tree = default_tree()
    return [tree.classify_frame(f) for f in frames.extract(text, context)
            if f["kind"] == KIND_ACTION]


def main():
    try:
        tree = load_tree()
    except TreeError as e:
        print(e, file=sys.stderr)
        return 1
    with open(FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    out = []
    for s in sentences:
        for fr in s["frames"]:
            if fr["kind"] != KIND_ACTION:
                continue
            row = {"card": s["card"], "section": s["section"], "index": s["index"],
                   "order": fr["order"]}
            row.update(tree.classify_frame(fr))
            out.append(row)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
        f.write("\n")
    counts = {status: sum(r["status"] == status for r in out) for status in STATUSES}
    placed = counts[STATUS_PLACED] + counts[STATUS_UNPLACED]
    print("動作框架 %d:已歸 %d、未歸 %d、不適用 %d;已歸比例 %.2f%%(已歸/(已歸+未歸))" % (
        len(out), counts[STATUS_PLACED], counts[STATUS_UNPLACED], counts[STATUS_NA],
        100.0 * counts[STATUS_PLACED] / max(1, placed)))
    print("類別樹葉 %d;已寫出 %s" % (len(tree.leaves), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
