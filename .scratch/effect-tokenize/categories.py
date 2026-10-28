# -*- coding: utf-8 -*-
"""動作類別歸組(.scratch/action-categories 票 01〜):動作框架 → 類別樹的葉。

接在分詞鏈框架抽取之後:讀 frames.json(frames.py 的輸出)與類別樹來源檔
category_tree.json,為每個動作框架寫一列類別紀錄到 frame_categories.json(框架類別檔),
再把每張卡的葉集合分效果組與代價組寫到 card_categories.json(卡層彙總檔,票 04;各自
去重、依樹序,大類與詞元層由樹展開、不另存)。兩份都是決定性建置產物、不入版控。只讀
框架抽取的輸出、不改它;約束框架不歸本樹。

類別樹(格式見 category_tree.json 的「說明」):大類 → 詞元節點 → 葉,分支可不等深;
框架只貼葉、祖先由樹推得。葉可宣告自己掛的大類(category-tree-restart 票 04;值是頂層大類名,
沒宣告時取詞元節點所在的本家大類),葉的路徑是 宣告的大類 › 詞元 › 葉——同一詞元的葉
因此可以在不同大類(にする:守備力 在 數值、にする:ダメージ 在 LP・ダメージ、にする→属性 在 規則改寫)。頂層大類可另列
中類清單(category-middle-class),葉以名字宣告所掛大類的中類,路徑改為 大類 › 中類 › 葉——
詞元層省掉,跨詞元收同一個屬性或來源的葉(數值 › 攻撃力 › アップ:攻撃力、區域移動 › ←墓地 ›
加える:墓地→手札);中類只改路徑,匹配、葉名、大類都不變。
葉名由條件機械組出——來源「詞元←區域」、目的「詞元→區域」、
來源加目的「詞元:來源→目的」、所在「詞元@區域」、關鍵詞「詞元:關鍵詞」(多個關鍵詞以 /
並列)、目的關鍵詞「詞元→字面」(多個以 / 並列;與目的區域同一種箭頭,意思都是「變成/去到」)、
否定「詞元(耐性)」「詞元(限制)」;區域在葉名裡寫日文卡文的區域名(手札/デッキ/墓地…),
條件值是區域七值。區域條件可各帶玩家條件(來源玩家/目的玩家/所在玩家,值 自分/相手/雙方;
category-tree-restart 票 02,2026-10-19 站主裁定不切「無」),葉名以日文前綴連寫在該區域名前
(破壊@相手フィールド、除外←相手墓地、雙方寫 お互いの)。

規則表語意:主鍵是(動作詞元, 極性類)。極性類是 肯定/耐性/限制:可能視同肯定;否定
依述語形分(票 03)——被動否定(態 受身;frame-lemma-unify 票 01 起讀框架的態欄)、にならない、
受けない 為耐性,可能否定(できない、行えない)為限制,其餘一般否定(送らず、戻さず)沒有極性類、
記未歸。被動以外的述語形是唯一讀子句字面的地方(框架抽取只記 否定、沒記述語形);其餘匹配只看
框架欄位(動作、來源、目的、所在、極性、態、位置,關鍵詞讀 對象/主語/主題):
    條件位       → 不適用(條件框架歸觸發事件軸,另開線)
    匹配到葉     → 已歸,記葉清單與大類(第一葉的大類)
    其餘         → 未歸(詞元沒有節點,或條件全不符且沒有預設葉);沒有「其他」類
來源/目的/所在字面各自映成(玩家, 區域清單)(票 02;區域辨識 places.parse_place 在框架線,
frame-args-v3 票 01),各比自己那一欄(category-tree-restart 票 01):移動類動作依來源切葉,
破壊、選ぶ 這類非移動類依所在切葉(受事者區域由框架抽取切出,frame-args-v3 票 04);非移動類
(不在框架線的 MOVE_ACTIONS)所在空著、來源有原文字面時,來源當所在比——「手札・墓地から選ぶ」
的 から 是受事者的所在(類別線票 08,category-round1;2026-10-28 站主裁定保留)。
玩家條件只在宣告的葉上比對該區域欄的玩家(複合字面逐區域取:自分の墓地・相手フィールド
的墓地是自分、フィールドは相手;同一區域兩個玩家各算一段——自分フィールド・相手フィールド 帶
破壊@自分フィールド 與 破壊@相手フィールド,雙方只來自 自分・相手/お互いの 前綴;票 08,2026-10-28
站主裁定;places.parse_zones);沒寫玩家前綴的字面(玩家 無)、
持ち主の/自身の 這類相對前綴(玩家 相對,看主語或持有者是誰;類別線票 06,2026-10-27
站主裁定另記一值)與 null(沒字面、推得、字面不是地點)都不中任何宣告玩家的葉,落沒宣告
玩家的葉——沒宣告玩家的葉不看玩家。不論葉有沒有宣告,
來源/目的的玩家都照記在來源玩家/目的玩家欄(推得的記 null)。
關鍵詞條件(字面子字串清單)依 對象→主語→主題 找第一個有值的欄、只比那一欄(主題含回填
延續的值;三欄都空不中;category-tree-restart 票 03);關鍵詞緊接 した/する/され 的出現是動詞用法、
修飾後面的名詞(特殊召喚したモンスターの効果、発動した効果),不算命中(票 08,2026-10-28 站主
裁定;關鍵詞類條件都適用)。目的關鍵詞條件(字面子字串清單)只比
目的欄(原文字面,推得的值也照字面比),與關鍵詞各自獨立——收補語是值或屬性、留在目的欄的框架
(にする→裏側守備表示、にする→属性;category-lemma-followup 票 02);一葉兩種都宣告時兩者都要中。
關鍵詞與目的關鍵詞合稱關鍵詞類條件。匹配:對每個(來源區域, 目的區域,
所在區域)組合,收集所有區域/玩家條件相符且關鍵詞類條件命中的葉(多關鍵詞多葉:攻撃力・守備力
帶兩葉;裏側守備表示 同時中 →裏側守備表示 與 →守備表示),樹序第一個條件相符、不帶關鍵詞類條件
的葉若帶所在條件也收(「做什麼」與
「在哪裡」兩軸並收:相手フィールドのモンスター 帶 破壊:モンスター 與 破壊@相手フィールド;
來源/目的葉是移動的起訖、不並收——フィールドの表側表示モンスターにカウンターを置く 不帶
置く→フィールド;類別線票 06,2026-10-19 站主裁定);沒有任何關鍵詞類葉命中時就取那一葉(預設葉含在
內)。複合字面(手札・墓地)逐區域各匹配,一個框架因此可帶多個葉;葉清單依樹序去重,
多葉跨大類時框架的大類取第一葉的。

建置期檢查樹的完整性(葉名全樹唯一、每葉有詞元條件、每大類至少一葉、葉宣告的大類
存在、同詞元的葉不被前面較寬、不帶關鍵詞類條件的葉蓋掉;葉宣告的中類在所掛大類的清單裡、
清單裡的中類都有葉、中類不與同大類的詞元節點同名;目的關鍵詞是非空字串清單、不與目的(區域)
疊在一葉),違反時報錯不產出。詞元節點的詞元另要是框架抽取產得出的正規詞元——不是詞元對照表的
輸入端(戻る、無効化),也不是補語不併判準會拆開的「值或屬性 + にする」(裏側守備表示にする);
兩條都直接用框架線的判準,所以建置任何樹都會載入框架抽取(category-lemma-followup 票 05)。類別紀錄另帶每葉的
路徑(與葉清單同序);框架類別檔不存路徑(由樹展開)。

測試接縫是 classify(text, context=""):一句效果句原文(帶同卡同段上文)→ 每個
動作框架的類別紀錄,內部呼叫真的框架抽取與類別樹;卡層彙總經同一接縫多句組裝
(classify_card)。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/categories.py
"""
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import frames  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from frames import MOVE_ACTIONS, POL_AFFIRM, POL_NEG, POS_COND, POS_COST, POS_EFFECT  # noqa: E402
import action_lemmas  # noqa: E402
from action_lemmas import VOICE_PASSIVE  # noqa: E402
from places import PLAYER_BOTH, PLAYER_OPP, PLAYER_SELF, parse_place, parse_zones  # noqa: E402

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
# 否定框架的述語形 → 極性類:態是受身(被動否定,frame-lemma-unify 票 01 起讀框架的態欄)為
# 耐性;其餘取子句裡最後一個否定述語(框架的子句收在它自己的述語);
# 〜ければならない/〜ねばならない 是義務、不是否定述語。
# 受けない 字面是一般否定,但 受ける 的否定就是不受影響,歸耐性;行えない 是五段動詞
# 行う 的可能否定。其餘一般否定(送らず、戻さず、リリースせず)不屬任何一類。
NEGATION_FORMS = (
    (re.compile(r"(?:でき|出来)(?:ない|ず|なく|ませ)|行え(?:ない|ず|なく)"), POL_RESTRICT),
    (re.compile(r"(?:(?<!ば)なら|受け)(?:ない|ず|なく)"), POL_RESIST),
)

# 區域七值(值域正典的區域,與第一版同一組)與葉名裡的日文區域名
ZONE_LABEL = {"手牌": "手札", "牌組": "デッキ", "額外牌組": "EXデッキ", "墓地": "墓地",
              "除外": "除外", "場上": "フィールド", "靈擺區": "Pゾーン"}

# 樹來源檔的鍵
KEY_MAJOR = "大類"
KEY_MIDDLE = "中類"
KEY_LEMMA = "詞元"
KEY_POLARITY_CLASS = "極性類"
KEY_CHILDREN = "子"
# 可宣告的玩家條件值與它在葉名裡的日文前綴。「無」不能宣告(2026-10-19 站主裁定):
# 它與沒宣告玩家的葉葉名同形,沒寫玩家的框架由沒宣告玩家的葉收
PLAYER_LABEL = {PLAYER_SELF: "自分", PLAYER_OPP: "相手", PLAYER_BOTH: "お互いの"}

# 樹來源檔的葉條件鍵 → 內部欄名;玩家條件欄是「區域欄名_player」,綁在該區域條件上
LEAF_KEYS = {"來源": "source", "目的": "goal", "所在": "place", "關鍵詞": "keywords",
             "目的關鍵詞": "goal_keywords",
             "來源玩家": "source_player", "目的玩家": "goal_player", "所在玩家": "place_player"}
LEAF_LABELS = {field: key for key, field in LEAF_KEYS.items()}
# 區域條件欄(樹序也是葉名裡區域段的順序)
ZONE_FIELDS = ("source", "goal", "place")
# 關鍵詞的比對欄,依序取第一個有值的(category-tree-restart 票 03)
KEYWORD_FIELDS = ("object", "subject", "topic")
# 關鍵詞緊接這些字時是動詞用法、修飾後面的名詞(特殊召喚したモンスター、発動した効果、召喚された),
# 不算命中(票 08,2026-10-28 站主裁定);召喚・特殊召喚を無効 的 召喚 照中
KEYWORD_VERB_TAILS = ("した", "する", "され")


class TreeError(ValueError):
    """類別樹完整性檢查失敗(訊息逐條列出違反處)。"""


def unplaced_label(frame):
    """未歸框架的聚合標籤與它的 (詞元, 極性類) 鍵(類別總覽與草案的未歸類清單共用):
    肯定記詞元、耐性/限制記 詞元(耐性)/(限制)、一般否定(沒有極性類)記 詞元(否定)、
    鍵為 None。"""
    cls = polarity_class(frame)
    if cls is None:
        return frame["action"] + "(否定)", None
    return leaf_name(frame["action"], cls), (frame["action"], cls)


def polarity_class(frame):
    """框架的極性 → 極性類:可能視同肯定;被動否定(態 受身)是耐性;其餘否定依子句裡最後一個
    否定述語分耐性/限制,一般否定回 None(沒有節點)。"""
    if frame["polarity"] != POL_NEG:
        return POL_AFFIRM
    if frame.get("voice") == VOICE_PASSIVE:
        return POL_RESIST
    clause = frame["clause"].replace(" ", "")
    last, found = -1, None
    for pattern, cls in NEGATION_FORMS:
        for m in pattern.finditer(clause):
            if m.end() > last:
                last, found = m.end(), cls
    return found


def keyword_in(keyword, text):
    """關鍵詞是否出現在字面裡(子字串),但緊接 した/する/され 的出現不算——那是動詞用法、修飾
    後面的名詞(特殊召喚したモンスターの効果 的 召喚、発動した効果 的 発動),不是動作的標的。"""
    start = 0
    while True:
        i = text.find(keyword, start)
        if i < 0:
            return False
        tail = text[i + len(keyword):]
        if not tail.startswith(KEYWORD_VERB_TAILS):
            return True
        start = i + 1


def leaf_name(lemma, polarity, conditions=None):
    """葉的條件(內部欄名 → 值)→ 葉名(機械組出):詞元、區域段(←來源、→目的、
    :來源→目的、@所在;玩家前綴連寫在區域名前)、:關鍵詞、→目的關鍵詞、(極性類)。"""
    conditions = conditions or {}

    def zone(field):
        player = conditions.get(field + "_player")
        return (PLAYER_LABEL[player] if player else "") + ZONE_LABEL[conditions[field]]

    name = lemma
    source, goal = conditions.get("source"), conditions.get("goal")
    if source and goal:
        name += ":%s→%s" % (zone("source"), zone("goal"))
    elif source:
        name += "←" + zone("source")
    elif goal:
        name += "→" + zone("goal")
    if conditions.get("place"):
        name += "@" + zone("place")
    keywords = conditions.get("keywords")
    if keywords:
        name += ":" + "/".join(keywords)
    goal_keywords = conditions.get("goal_keywords")
    if goal_keywords:
        name += "→" + "/".join(goal_keywords)
    if polarity != POL_AFFIRM:
        name += "(%s)" % polarity
    return name


class Leaf:
    """一個葉:所屬詞元節點的(詞元, 極性)加上自己的條件欄;名字由條件組出。
    path 是大類到葉的節點名(詞元節點自己就是葉時、或頂層詞元節點自成大類時,相鄰同名
    只留一個),major 是 path 的頭、home 是本家大類(詞元節點所在的頂層節點)、node 是
    詞元節點名;葉宣告了本家以外的大類(declared)時 path 是 宣告的大類 › 詞元 › 葉,
    宣告了中類(middle)時是 大類 › 中類 › 葉——詞元層省掉(category-middle-class)。"""

    def __init__(self, lemma, polarity, conditions, ancestors, declared=None, middle=None):
        self.lemma = lemma
        self.polarity = polarity
        self.source = conditions.get("source")
        self.goal = conditions.get("goal")
        self.place = conditions.get("place")
        # 區域欄 → 宣告的玩家(沒宣告的區域不在表裡)
        self.players = {field: conditions[field + "_player"] for field in ZONE_FIELDS
                        if field + "_player" in conditions}
        self.keywords = tuple(conditions.get("keywords") or ())
        self.goal_keywords = tuple(conditions.get("goal_keywords") or ())
        self.name = leaf_name(lemma, polarity, conditions)
        self.declared = declared
        self.middle = middle
        self.home = ancestors[0]
        self.node = ancestors[-1]
        major = self.home if declared is None else declared
        if middle is not None:
            # 中類取代詞元層:大類 › 中類 › 葉
            ancestors = (major, middle)
        elif major != self.home:
            # 借到別的大類:直接掛在宣告的大類下,本家路徑上的中間節點不帶過去
            ancestors = (major, self.node)
        path = []
        for name in ancestors + (self.name,):
            if not path or path[-1] != name:
                path.append(name)
        self.path = tuple(path)
        self.major = self.path[0]

    @property
    def borrowed(self):
        """葉掛在本家以外的大類(總覽頁的詞元節點因此出現在幾個大類下)。"""
        return self.major != self.home

    @property
    def keyed(self):
        """帶關鍵詞類條件(關鍵詞或目的關鍵詞)的葉:命中全收、不互蓋。"""
        return bool(self.keywords or self.goal_keywords)

    def covers(self, other):
        """本葉寫在 other 前面時是否蓋住它:只有不帶關鍵詞類條件的葉蓋得住(關鍵詞類葉之間
        多葉、不互蓋),條件是本葉的區域與玩家條件涵蓋 other 的全部情形——other 是不帶
        關鍵詞類條件的葉時它永遠匹配不到;是關鍵詞類葉時較具體者要寫在前。other 的條件當成
        一個框架來比,沒宣告的欄是 None。"""
        return not self.keyed and self.places_match(
            {field: (other.players.get(field), getattr(other, field)) for field in ZONE_FIELDS})

    def places_match(self, places):
        """{來源/目的/所在欄: (玩家或 None, 區域或 None)} 是否符合本葉的區域與玩家條件。"""
        for field in ZONE_FIELDS:
            player, zone = places[field]
            mine = getattr(self, field)
            if mine and mine != zone:
                return False
            if field in self.players and self.players[field] != player:
                return False
        return True

    def hits(self, text, goal):
        """關鍵詞類葉是否命中:宣告了關鍵詞時,關鍵詞比對欄的字面(或 None)要含其中一個;宣告了
        目的關鍵詞時,目的欄的字面(或 None)要含其中一個;兩者都宣告時都要中。不帶關鍵詞類條件
        的葉恆為假。"""
        return self.keyed and all(
            bool(value) and any(keyword_in(k, value) for k in keys)
            for keys, value in ((self.keywords, text), (self.goal_keywords, goal)) if keys)


class CategoryTree:
    """類別樹:載入時做完整性檢查,classify_frame 把一個動作框架貼到葉上。"""

    def __init__(self, data):
        self.leaves = []            # 樹序
        self.by_key = {}            # (詞元, 極性類) → 該詞元節點的葉(樹序)
        self.majors = []            # 頂層節點名(大類名),樹序
        self.major_nodes = set()    # 頂層大類節點名(葉可宣告的值;不含自成大類的詞元節點)
        self.middles = {}           # 頂層大類名 → 中類清單(總覽頁順序)
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
        for leaf in self.leaves:
            if leaf.declared is not None and leaf.declared not in self.major_nodes:
                errors.append("葉 %s 宣告的大類 %s 不是頂層大類" % (leaf.name, leaf.declared))
        homes, majors = {leaf.home for leaf in self.leaves}, {leaf.major for leaf in self.leaves}
        for name in self.majors:
            if name in homes and name not in majors:
                errors.append("大類 %s 底下的葉都宣告到別的大類" % name)
        errors.extend(self._middle_errors())
        # 同詞元的葉只擋「後面的葉被前面不帶關鍵詞的葉整個蓋住」;部分重疊
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

    def _middle_errors(self):
        """中類的完整性:葉宣告的中類要在所掛大類的清單裡、清單裡的中類要有葉、中類不與
        同大類底下的詞元節點(本家的與借來的都算,葉全進了中類的也算)或大類本身同名。"""
        errors = []
        used = {(leaf.major, leaf.middle) for leaf in self.leaves if leaf.middle is not None}
        for leaf in self.leaves:
            if leaf.middle is None or leaf.middle in self.middles.get(leaf.major, ()):
                continue
            owners = [m for m, names in self.middles.items() if leaf.middle in names]
            if owners:
                errors.append("葉 %s 宣告的中類 %s 屬於大類 %s,不在它所掛的大類 %s"
                              % (leaf.name, leaf.middle, "、".join(owners), leaf.major))
            else:
                errors.append("葉 %s 宣告的中類 %s 不在大類 %s 的中類清單"
                              % (leaf.name, leaf.middle, leaf.major))
        nodes = {(major, leaf.node) for leaf in self.leaves for major in (leaf.home, leaf.major)}
        for major, names in self.middles.items():
            for name in names:
                if (major, name) not in used:
                    errors.append("大類 %s 的中類 %s 沒有葉" % (major, name))
                if (major, name) in nodes:
                    errors.append("大類 %s 的中類 %s 與詞元節點同名" % (major, name))
                if name == major:   # 相鄰同名收合會把中類那一層吃掉
                    errors.append("大類 %s 的中類 %s 與大類同名" % (major, name))
        return errors

    def _middle_list(self, node, name, major, errors):
        """大類節點的中類清單(只有頂層大類可列;字串清單、不重複)。"""
        if KEY_MIDDLE not in node:
            return
        middles = node[KEY_MIDDLE]
        if major is not None:
            errors.append("大類 %s 不是頂層大類,不能列中類" % name)
        elif not (isinstance(middles, list) and middles
                  and all(isinstance(m, str) and m for m in middles)):
            errors.append("大類 %s 的中類清單要是非空字串清單:%r" % (name, middles))
        else:
            for dup in sorted({m for m in middles if middles.count(m) > 1}):
                errors.append("大類 %s 的中類清單重複:%s" % (name, dup))
            self.middles[name] = middles

    def _walk(self, node, path, major, errors):
        """回傳此節點底下的葉數。"""
        if not isinstance(node, dict):
            errors.append("%s 底下有不是物件的節點:%r" % ("/".join(path) or "樹", node))
            return 0
        if KEY_MAJOR in node:
            name = node[KEY_MAJOR]
            self._middle_list(node, name, major, errors)
            if major is None:
                self.majors.append(name)
                self.major_nodes.add(name)
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
        errors.extend(lemma_errors(lemma))
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
            parsed = self._conditions(spec, lemma, errors)
            if parsed is not None:
                conditions, declared, middle = parsed
                leaves.append(Leaf(lemma, polarity, conditions, path + (node_name,), declared,
                                   middle))
        self.by_key[key] = leaves
        self.leaves.extend(leaves)
        return len(leaves)

    @staticmethod
    def _conditions(spec, lemma, errors):
        """葉的物件 → (條件 {內部欄名: 值}, 宣告的大類或 None, 宣告的中類或 None);不合法時
        記錯、回 None。"""
        if not isinstance(spec, dict) or KEY_CHILDREN in spec or KEY_LEMMA in spec:
            errors.append("詞元節點 %s 底下只能掛葉:%s"
                          % (lemma, json.dumps(spec, ensure_ascii=False)))
            return None
        unknown = set(spec) - set(LEAF_KEYS) - {KEY_MAJOR, KEY_MIDDLE}
        if unknown:
            errors.append("詞元 %s 的葉有不認得的條件欄:%s" % (lemma, "、".join(sorted(unknown))))
            return None
        conditions = {LEAF_KEYS[k]: v for k, v in spec.items() if k in LEAF_KEYS}
        for field in ZONE_FIELDS:
            if field in conditions and conditions[field] not in ZONE_LABEL:
                errors.append("詞元 %s 的葉區域 %r 不在區域七值" % (lemma, conditions[field]))
                return None
            player = conditions.get(field + "_player")
            if player is None:
                continue
            if field not in conditions:
                errors.append("詞元 %s 的葉 %s 綁在葉沒有的區域條件(%s)上"
                              % (lemma, LEAF_LABELS[field + "_player"], LEAF_LABELS[field]))
                return None
            if player not in PLAYER_LABEL:
                errors.append("詞元 %s 的葉 %s %r 不在 %s" % (
                    lemma, LEAF_LABELS[field + "_player"], player, "/".join(PLAYER_LABEL)))
                return None
        for field in ("keywords", "goal_keywords"):
            keywords = conditions.get(field)
            if keywords is not None and (not isinstance(keywords, list) or not keywords
                                         or not all(isinstance(k, str) and k for k in keywords)):
                errors.append("詞元 %s 的葉%s要是非空字串清單:%r"
                              % (lemma, LEAF_LABELS[field], keywords))
                return None
        if "goal" in conditions and "goal_keywords" in conditions:
            # 目的區域葉 戻す→デッキ 與目的關鍵詞葉 にする→守備表示 葉名同一種箭頭,不能疊在一葉
            errors.append("詞元 %s 的葉不能同時宣告 目的 與 目的關鍵詞" % lemma)
            return None
        declared = spec.get(KEY_MAJOR)
        if declared is not None and not (isinstance(declared, str) and declared):
            errors.append("詞元 %s 的葉宣告的大類 %r 不是頂層大類" % (lemma, declared))
            return None
        middle = spec.get(KEY_MIDDLE)
        if middle is not None and not (isinstance(middle, str) and middle):
            errors.append("詞元 %s 的葉宣告的中類 %r 不是字串" % (lemma, middle))
            return None
        return conditions, declared, middle

    def classify_frame(self, frame):
        """一個動作框架 → 類別紀錄(動作、狀態、葉清單、大類、來源玩家、目的玩家、路徑)。

        複合來源/目的/所在逐(來源區域, 目的區域, 所在區域)組合各匹配:命中的關鍵詞類葉
        (關鍵詞、目的關鍵詞)全收,沒有時取第一個條件相符、不帶關鍵詞類條件的葉;葉清單
        依樹序去重,路徑與葉清單同序(每葉一條大類到葉的節點名清單)。認不出區域的一欄以 None 參與匹配。條件位不適用,
        玩家欄也不填。"""
        record = {"action": frame["action"], "status": STATUS_UNPLACED, "leaves": [],
                  "major": None, "source_player": None, "goal_player": None, "paths": []}
        if frame["position"] == POS_COND:
            record["status"] = STATUS_NA
            return record
        # 推得的來源/目的(frame-args-v3 票 05)參與區域匹配,但沒有原文字面:玩家照 null,
        # 不中任何宣告玩家的葉,玩家欄也記 null
        inferred = frame.get("inferred") or ()
        literals = {"source": frame.get("source"), "goal": frame.get("goal"),
                    "place": place_literal(frame)}
        options = []                # 每欄的 [(玩家, 區域)…];沒有區域的欄以 (None, None) 參與
        for field in ZONE_FIELDS:
            zones = parse_zones(literals[field]) or [(None, None)]
            options.append([(None, zone) for _, zone in zones] if field in inferred else zones)
        for field in ("source", "goal"):     # 玩家欄:各段的玩家合起來(與葉的條件無關)
            record[field + "_player"] = (None if field in inferred
                                         else parse_place(frame.get(field))[0])
        text = next((frame[f] for f in KEYWORD_FIELDS if frame.get(f)), None)
        goal = frame.get("goal")    # 目的關鍵詞只比目的欄(推得的值也照字面比)
        candidates = self.by_key.get((frame["action"], polarity_class(frame)), ())
        matched = set()
        for combo in itertools.product(*options):
            places = dict(zip(ZONE_FIELDS, combo))
            fitting = [leaf for leaf in candidates if leaf.places_match(places)]
            hits = [leaf for leaf in fitting if leaf.hits(text, goal)]
            plain = [leaf for leaf in fitting if not leaf.keyed][:1]
            if hits:
                # 關鍵詞類葉命中時,帶所在條件的葉照收(兩軸並收);來源/目的葉與預設葉不收
                matched.update(hits + [leaf for leaf in plain if leaf.place])
            else:
                matched.update(plain)
        matched = [leaf for leaf in candidates if leaf in matched]     # 樹序
        if matched:
            # 多葉跨大類時取第一葉(樹序)的
            record.update(status=STATUS_PLACED, leaves=[leaf.name for leaf in matched],
                          major=matched[0].major, paths=[list(leaf.path) for leaf in matched])
        return record


def place_literal(frame):
    """框架比所在葉用的字面:所在欄;非移動類動作(不在框架線的 MOVE_ACTIONS)所在空著、來源有
    原文字面時讀來源欄——「手札・墓地から選ぶ」的 から 是受事者的所在(票 08,category-round1;
    2026-10-28 站主裁定保留)。移動類的來源仍只比來源葉。草案的所在分佈用同一個字面。"""
    if frame.get("place") or frame["action"] in MOVE_ACTIONS:
        return frame.get("place")
    if "source" in (frame.get("inferred") or ()):
        return None
    return frame.get("source")


def lemma_errors(lemma):
    """詞元節點的詞元要是框架抽取產得出的正規詞元(category-lemma-followup 票 05):不能是詞元
    對照表的輸入端(戻る、無効化、上げる、アドバンス召喚),也不能是補語不併判準會拆開的「值或
    屬性 + にする/とする」(裏側守備表示にする、属性にする)。兩條都直接用框架線的判準。"""
    canonical = action_lemmas.normalize(lemma)[0]
    if canonical != lemma:
        return ["詞元節點 %s 不是框架抽取產得出的詞元(正規詞元是 %s)" % (lemma, canonical)]
    if frames.default_extractor().splits_complement(lemma):
        return ["詞元節點 %s 的補語是值或屬性,框架抽取不併入詞元(詞元寫 にする/とする、"
                "依目的分葉用目的關鍵詞)" % lemma]
    return []


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


def classify(text, context="", tree=None):
    """接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架的類別紀錄(依原文順序)。
    tree 預設是類別樹來源檔;測試可傳小樹驗真樹還沒開的葉條件。"""
    return [record for _, record in
            classified(tree or default_tree(), frames.extract(text, context))]


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
            del row["paths"]        # 框架類別檔不存路徑(由樹展開)
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
