"""段抽取:一個區塊的原文 → 段(扁平)+ 段樹 + 物件(寫進整卡共用的物件表)。

規則是句型層級的,不針對任何一張卡:
- 句子以「。」切;「その後、」開頭的句子與前一句連接為「先後」;區塊開頭的「また、」是接著詞。
- 發動句(…発動できる / …発動する):
    (前提)(條件子句)(時|場合|際)(に)、(代價子句)て  → 條件段 + 代價段
  條件段帶觸發形;代價子句以て形結尾才算代價。前提(`premise` 模組:「〜に存在する場合、」
  「相手ターンに」)先剝掉、寫進第一個段的前提格(段的範圍從前提起算);整句只有前提的
  (「自分メインフェイズに発動できる」)開一個沒有動作詞的條件段放它;效果句開頭的前提同樣。
- 舊式的「(條件子句)(時|場合|際)、(效果子句)」(沒有発動できる)→ 條件段 + 效果段。
- 其他句子是效果段;極性由述語語尾判(できない → 不能…);「〜できる」「〜事ができる」是
  可選的效果(可選格 `optional`,極性仍是做,查詢預設算命中;票 08 再分辨永續的「可以」)。
- 簡單子句:[誰が][到に][從から|從の][物件](を|が|は)[數量][原因][形式][從から][到に][受方に]述語
  (物件前的「到に」只在助詞是「が」時:「自分フィールドにモンスターが特殊召喚された」;
  「從」寫在物件後的記 placement 述語前;受方是「相手に見せて」的相手)。
  述語字面經同義表收成動作詞,語尾決定態與極性;て形串接的多個述語(めくられて墓地へ送られた)
  是多個動作詞。從/到保留含助詞的原文字面(`text`:「墓地の」「自分のデッキの上から」「デッキの一番下に」),
  反向檢查據此還原(の/から、に/へ 是字面的選擇,結構上都是明寫的從/到)。
- 存在前提:「(容器)の中に(物件)が(あった|ある|存在する)」→ 條件段,物件是容器的子集。
- 物件:このカード = 物件0;その/それらの モンスター|カード 指回本區塊最近的同大類物件
  (從條件段指回來的不標取對象;回指字面記在對象線 `ref`);「めくったカード」這類動作回指
  也指回;助詞後的數量(「を全て」「を２枚まで」)記在對象線 `count`,屬於這次提及;「残りのX」是
  剩餘物件(容器 − 最近的子集);其餘是新建物件,頭名詞給大類、數量給數量,修飾語從左到右認:
  「X」以外の = 非(卡名∋X);「X」と名のついた、緊接頭名詞的「X」= 字段(依字段表換成 setcode);
  カード名に「X」を含む = 卡名包含;「X」１体 = 卡名∋X;種族、屬性、レベルN = 屬性比較
  (「・」列舉的種族/屬性是「或」,種族接屬性是「且」,`attribute_atoms`);頭名詞 チューナー =
  怪獸 且 子類型 協調。認不得的修飾語整截標「解析不出」;「X」對不到卡名與字段的,
  物件標「不認得的「」名稱」。
- 位置:處理完一段把「到」寫回物件目前位置;「從」沒寫先繼承目前位置(沒動過就是初始位置),
  再查推得表;推得值與繼承自推得值的標 inferred,查詢開關開才算。
  區域的方沒寫(「墓地から」)照慣例歸我方但記 side_source 預設,場上系沒寫方不預設(任一方的
  場上);明寫「自分の」記明寫,反向檢查沒有字面時只在明寫才寫出來。
抽不出的段與物件一律標原因,不丟例外,全庫建置不中斷。
"""
import re

from archetype_table import fold_width
from attribute_atoms import parse_modifier as parse_param_group
from attribute_words import ATTRIBUTE_JA, RACE_JA
from condition_atoms import parse_modifier as parse_atom_modifier
from names_attributes import REASON_NAME_UNKNOWN
from premise import split_premises
from structure_shape import (new_line, new_object, new_segment, position,
                             segment_node, unparsed, zone)

# ── 同義表:述語字面 → 動作詞;第三欄是述語本身寫明的終點(「墓地へ送る」)。
PREDICATE_STEMS = (
    ("特殊召喚", "特殊召喚", None),
    ("融合召喚", "融合召喚", None),
    ("S召喚", "S召喚", None),
    ("X召喚", "X召喚", None),
    ("L召喚", "L召喚", None),
    ("見せ", "展示", None),
    ("破壊", "破壞", None),
    ("捨て", "捨棄", None),
    ("リリース", "解放", None),
    ("除外", "除外", "除外"),
    ("墓地へ送", "送墓", "墓地"),
    ("手札に加え", "加入手牌", "手牌"),
    ("めく", "翻開", None),
    ("戻", "返回", None),
    ("装備", "裝備", None),
)
# 取對象子句的述語字面(「Xを対象として発動できる」):沒有動作詞,只把 X 標成取對象。
TARGET_WORD = "対象として"
# 動作回指(「めくったカード」「特殊召喚したモンスター」)用的過去形。
ACTION_PAST = {"翻開": "めくった", "特殊召喚": "特殊召喚した", "破壞": "破壊した",
               "除外": "除外した", "送墓": "墓地へ送った", "捨棄": "捨てた",
               "解放": "リリースした", "加入手牌": "手札に加えた", "返回": "戻した",
               "融合召喚": "融合召喚した", "S召喚": "S召喚した", "X召喚": "X召喚した",
               "L召喚": "L召喚した", "展示": "見せた"}
# 下位詞:S、X、L、融合召喚是特殊召喚的下位(spec「動作詞」),查「特殊召喚」要含它們;
# 推得表與角色也照上位詞算。
ACTION_PARENT = {"融合召喚": "特殊召喚", "S召喚": "特殊召喚", "X召喚": "特殊召喚",
                 "L召喚": "特殊召喚"}


def action_ancestors(action):
    """動作詞與它的全部上位詞(含自己):融合召喚 → [融合召喚, 特殊召喚]。"""
    out = [action]
    while action in ACTION_PARENT:
        action = ACTION_PARENT[action]
        out.append(action)
    return out
# 述語語尾 → (態, 極性[, 可選])。語尾不在表內的述語標「述語語尾不明」,不猜。
TAILS = {
    "": ("主動", "做"), "る": ("主動", "做"), "する": ("主動", "做"),
    "した": ("主動", "做"), "し": ("主動", "做"), "して": ("主動", "做"),
    "て": ("主動", "做"), "った": ("主動", "做"), "って": ("主動", "做"),
    "す": ("主動", "做"), "り": ("主動", "做"), "え": ("主動", "做"),
    "される": ("被動", "做"), "された": ("被動", "做"), "され": ("被動", "做"),
    "されて": ("被動", "做"),
    "られる": ("被動", "做"), "られた": ("被動", "做"), "られ": ("被動", "做"),
    "られて": ("被動", "做"),
    "に成功した": ("被動", "做"), "に成功する": ("被動", "做"),
    "できる": ("主動", "做", True), "る事ができる": ("主動", "做", True),
    "する事ができる": ("主動", "做", True), "事ができる": ("主動", "做", True),
    "できない": ("主動", "不能"), "できず": ("主動", "不能"),
    "する事ができない": ("主動", "不能"), "る事ができない": ("主動", "不能"),
    "しない": ("主動", "不會"), "されない": ("被動", "不會"),
    "られない": ("被動", "不會"),
}
_TAILS_LONGEST_FIRST = sorted(TAILS, key=len, reverse=True)
# 連用形語尾:子句以它收尾再接「、」,是與下一個子句的「同時」連接(墓地へ送り、/特殊召喚し、/
# 手札に加え、/相手に見せ、);語尾本身的態與極性照 TAILS。
CONNECTIVE_TAILS = ("し", "り", "え", "")
# 推得表:動作詞 → (沒寫「從」時的出發地, 沒寫「到」時的終點)。
INFERENCE_TABLE = {
    "破壞": ("場上", "墓地"),
    "解放": ("場上", "墓地"),
    "捨棄": ("手牌", "墓地"),
    "特殊召喚": (None, "場上"),
    "裝備": (None, "魔陷區"),
}
# 區域字面(長的在前,EXデッキ 不能被 デッキ 先吃掉;同一區域多個字面時後者是反向檢查的預設寫法)。
ZONE_WORDS = (("EXデッキ", "額外牌組"), ("デッキの一番下", "牌組底"),
              ("デッキの一番上", "牌組頂"), ("デッキの上", "牌組頂"),
              ("デッキ", "牌組"), ("手札", "手牌"),
              ("EXモンスターゾーン", "EX怪獸區"), ("モンスターゾーン", "怪獸區"),
              ("魔法＆罠ゾーン", "魔陷區"), ("ペンデュラムゾーン", "P區"),
              ("フィールドゾーン", "場地區"),
              ("フィールド", "場上"), ("墓地", "墓地"))
# 場上系區域:沒寫方時不預設(手札・デッキ・墓地沒寫方照慣例是自己的,場上不是)。
FIELD_ZONES = ("場上", "EX怪獸區", "怪獸區", "魔陷區", "P區", "場地區")
HEAD_CATEGORY = {"モンスター": "怪獸", "魔法カード": "魔法", "罠カード": "陷阱",
                 "魔法・罠カード": ("魔法", "陷阱"), "カード": "卡"}
# 帶子類型的頭名詞:大類 且 屬性比較(卡片子類型 = 協調,與票 07 的 Xモンスター 同一種原子)。
HEAD_SUBTYPE = {"チューナー": ("怪獸", "協調")}
_HEADS = "|".join(sorted(list(HEAD_CATEGORY) + list(HEAD_SUBTYPE), key=len,
                         reverse=True))
SIDE_WORDS = {"自分": "我方", "相手": "對手", "自分か相手": "任一方"}
# 原因:種類 → 允許的字面(反向檢查只認這些)。
CAUSE_TEXTS = {"效果": ("カードの効果によって", "効果によって", "カードの効果で", "効果で"),
               "戰鬥": ("戦闘によって", "戦闘で")}
EXIST_WORDS = ("あった", "ある", "存在する", "存在した")
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

_ZONE_WORDS_ALT = "|".join(w for w, _ in ZONE_WORDS)
# 區域短語:[自分の|相手の|自分か相手の]區域(・區域|か區域)*;「・」與「か」都是列舉
# (自分の手札・フィールド、自分のフィールドか墓地),字面由從/到的 text 還原。
_ZONE_PHRASE = (f"(?:(?:自分か相手|自分|相手)の?)?(?:{_ZONE_WORDS_ALT})"
                f"(?:[・か](?:{_ZONE_WORDS_ALT}))*")
# 受方可以是物件的回指(「この効果で特殊召喚したモンスターに装備できる」)。
_RECIPIENT_REF = ("(?:この効果で)?(?:その|それらの|" + "|".join(ACTION_PAST.values())
                  + ")(?:モンスター|カード)")
_ACTIVATION_RE = re.compile("^(?P<body>.*?)(?P<suffix>発動できる|発動する)$")
_TRIGGER_RE = re.compile("^(?P<cond>.+?)(?P<trig>時|場合|際)に?、?(?P<rest>.*)$")
# 舊式的條件句:觸發形後一定有「、」才算,免得「終了時に」這類句中的時被當觸發。
_OLD_TRIGGER_RE = re.compile("^(?P<cond>.+?)(?P<trig>時|場合|際)(?:に)?、(?P<rest>.+)$")
_CLAUSE_RE = re.compile(
    "^(?:(?P<agent>自分|相手)(?:が|は))?"
    # 物件前的「到に」:主語形「自分フィールドにモンスターが特殊召喚された」(助詞が時才有)。
    f"(?:(?P<to_front>{_ZONE_PHRASE})に)?"
    f"(?:(?P<from>{_ZONE_PHRASE})(?P<from_particle>から|の))?"
    # 物件短語裡的「を含む」(カード名に「X」を含む)、「を持つ」(…と同じ数値のレベルを持つ)
    # 不是受詞助詞;述語裡沒有を,所以切錯時會回頭把「を含む」吃進物件短語。
    "(?P<objects>(?:を含む|を持つ|[^を])+?)(?P<marker>を|が|は)"
    "(?P<count>[０-９]+(?:体|枚)(?:まで)?|全て)?"
    "(?P<cause>(?:カードの効果|効果|戦闘)(?:によって|で))?"
    # 到的放置形式:「好きな順番で」;「装備魔法カード扱いで、」是裝備時到的形式(到本身推得)。
    "(?P<form>好きな順番で|装備(?:魔法)?カード扱いで、?)?"
    # 「從」也可寫在物件後(XをデッキからYに加える);受方(相手に見せて、〜したモンスターに装備)
    # 緊接述語前。
    f"(?:(?P<from2>{_ZONE_PHRASE})から)?"
    f"(?:(?P<to>{_ZONE_PHRASE})(?P<to_particle>に|へ))?"
    f"(?:(?P<recipient>自分|相手|{_RECIPIENT_REF})に)?"
    "(?P<pred>[^を]+)$")
_EXIST_RE = re.compile(
    "^(?P<container>.+?)の中に(?P<objects>.+?)が(?P<pred>" + "|".join(EXIST_WORDS) + ")$")
_FROM_RE = re.compile("^(?:(?P<side>自分か相手|自分|相手)の?)?(?P<zones>.+)$")
_SELF_RE = re.compile("^このカード$")
_REF_RE = re.compile("^(?P<ref>その|それらの)(?P<head>モンスター|カード)$")
_REMAINDER_RE = re.compile("^残りの(?P<head>モンスター|カード)$")
# 動作回指:「めくったカード」「この効果で特殊召喚したモンスター」= 本區塊裡最近被做過那個動作的物件。
_ACTION_REF_RE = re.compile("^(?:この効果で)?(?P<past>.+?)(?P<head>モンスター|カード)$")
_NOUN_RE = re.compile(
    f"^(?P<mods>.*?)(?P<head>{_HEADS})"
    "(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")
# 「X」１体:只有卡名、沒有頭名詞的物件。
_NAMED_RE = re.compile(
    "^「(?P<name>[^「」]+)」(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")
# 名稱修飾語(從左到右逐個認;「X」單獨出現只能緊接頭名詞,所以要在字串尾)。
_MOD_RES = (
    ("以外", re.compile("^「(?P<name>[^「」]+)」以外の")),
    ("と名のついた", re.compile("^「(?P<name>[^「」]+)」と名のついた")),
    ("卡名包含", re.compile("^カード名に「(?P<name>[^「」]+)」を含む")),
    ("字段", re.compile("^「(?P<name>[^「」]+)」$")),
)
_LEVEL_RE = re.compile("^レベル(?P<n>[０-９]+)$")

REASON_PREDICATE = "述語解析不出"
REASON_NOT_ARCHETYPE = "「」名稱不是字段"
REASON_TAIL = "述語語尾不明"
REASON_CLAUSE = "子句解析不出"
REASON_FROM = "從解析不出"
REASON_TO = "到解析不出"
REASON_OBJECT = "物件解析不出"
REASON_MODS = "物件修飾解析不出"
REASON_REF = "指回的物件找不到"
REASON_ACTIVATION = "發動句解析不出"
REASON_CAUSE = "原因解析不出"


def parse_predicate(pred):
    """述語字面 → (動作詞, 態, 極性, 寫明的終點, 可選) 或 (None, 原因)。"""
    for stem, action, to in PREDICATE_STEMS:
        if pred.startswith(stem):
            tail = pred[len(stem):]
            if tail not in TAILS:
                return None, REASON_TAIL
            voice, polarity, *optional = TAILS[tail]
            return (action, voice, polarity, to, bool(optional and optional[0])), None
    return None, REASON_PREDICATE


def parse_predicates(pred):
    """て形串接的述語字面(めくられて墓地へ送られた)→ [parse_predicate 的結果] 或 (None, 原因)。
    單一述語也走這裡;串接時前面的語尾必須以て/で收尾。"""
    parsed, reason = parse_predicate(pred)
    if parsed is not None:
        return [parsed], None
    for stem, action, to in PREDICATE_STEMS:
        if not pred.startswith(stem):
            continue
        rest = pred[len(stem):]
        for tail in _TAILS_LONGEST_FIRST:
            if tail and tail.endswith(("て", "で")) and rest.startswith(tail) \
                    and len(rest) > len(tail):
                following, reason = parse_predicates(rest[len(tail):])
                if following is not None:
                    voice, polarity, *optional = TAILS[tail]
                    head = (action, voice, polarity, to, bool(optional and optional[0]))
                    return [head] + following, None
        return None, REASON_TAIL
    return None, reason


def parse_from(phrase):
    """「自分の手札・フィールド」→ 區域列表;任何一截不是區域字面就回 None。"""
    m = _FROM_RE.match(phrase)
    if not m:
        return None
    zones = []
    for part in re.split("[・か]", m.group("zones")):
        for word, name in ZONE_WORDS:
            if part == word:
                break
        else:
            return None
        if m.group("side"):
            side, side_source = SIDE_WORDS[m.group("side")], "明寫"
        elif name in FIELD_ZONES:
            # 「フィールドに「海」が存在する場合」是任一方的場上:場上系沒寫方就不預設。
            side, side_source = None, None
        else:
            side, side_source = "我方", "預設"
        zones.append(zone(name, side, side_source))
    return zones


def parse_count(m):
    if not m.group("count"):
        return None
    digits = m.group("count")[:-len(m.group("unit")) - len(m.group("upto") or "")]
    return {"text": m.group("count"),
            "value": int(digits.translate(FULLWIDTH_DIGITS)),
            "unit": m.group("unit"), "cmp": "≤" if m.group("upto") else "="}


def floating_count(text):
    """助詞後的數量(「カードを２枚まで」「それらのモンスターを全て」),記在對象線上。"""
    if text == "全て":
        return {"text": text, "cmp": "全部"}
    m = re.match("^(?P<count>(?P<digits>[０-９]+)(?P<unit>体|枚)(?P<upto>まで)?)$", text)
    return {"text": text, "value": int(m.group("digits").translate(FULLWIDTH_DIGITS)),
            "unit": m.group("unit"), "cmp": "≤" if m.group("upto") else "="}


def category_condition(head):
    if head in HEAD_SUBTYPE:
        category, subtype = HEAD_SUBTYPE[head]
        return {"op": "且", "args": [{"op": "大類", "value": category},
                                    {"op": "屬性比較", "attr": "卡片子類型",
                                     "cmp": "=", "value": subtype}]}
    value = HEAD_CATEGORY[head]
    if isinstance(value, tuple):
        return {"op": "或", "args": [{"op": "大類", "value": v} for v in value]}
    return {"op": "大類", "value": value}


# ── 條件式:屬性比較的修飾語(種族、屬性、レベルN);名稱類的在 BlockState.parse_modifiers ──
def parse_modifier(part):
    """一截修飾語 → 屬性比較原子;認不得回 None。"""
    if part in RACE_JA:
        return {"op": "屬性比較", "attr": "種族", "cmp": "=", "value": part}
    if part.endswith("属性") and part[:-2] in ATTRIBUTE_JA:
        return {"op": "屬性比較", "attr": "屬性", "cmp": "=", "value": part[:-2]}
    m = _LEVEL_RE.match(part)
    if m:
        return {"op": "屬性比較", "attr": "等級", "cmp": "=",
                "value": int(m.group("n").translate(FULLWIDTH_DIGITS))}
    return None


def split_objects(phrase):
    """以「と」切物件,但「」裡的と、「X」と名のついた 的と(字段的舊式寫法)不算。"""
    parts, depth, buf = [], 0, ""
    for i, ch in enumerate(phrase):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        if (ch == "と" and depth == 0
                and not phrase.startswith(("と名のついた", "と同じ"), i)):
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p for p in parts if p]


class BlockState:
    """一個區塊抽取時的工作狀態:物件目前位置、本區塊提過的物件(給その指回)、
    名稱表(「X」→ 名稱列)與字段對照。"""

    def __init__(self, block, card, lookups=None, self_id="o0"):
        self.block = block
        self.card = card
        self.lookups = lookups or {"card_names": set(), "archetypes": {}}
        self.names = {row["text"]: row for row in card["names"]}
        self.positions = {}   # 物件 id → {"zones", "inferred"}
        self.recent = []      # 本區塊建立或引用過的物件 id(其後者優先)
        self.targeted = set()  # 「を対象として」點名的物件(取對象標記的來源)
        self.acted = {}       # 物件 id → 本區塊對它做過的動作詞(動作回指「〜したモンスター」用)
        self.self_id = self_id  # 「このカード」指誰:內嵌效果裡綁定成被賦予效果的物件

    def name_atom(self, op, name, form=None):
        """「X」→ (條件式原子, 原因):名稱列對不到卡名與字段 → 不認得的「」名稱;
        字段原子的 X 不是字段(只是卡名)→ 「」名稱不是字段。原子只引用名稱列的 id,
        字段原子另帶換好的 setcode(查詢不必再查字段表)。"""
        row = self.names.get(name)
        if row is None:
            return None, REASON_NAME_UNKNOWN
        atom = {"op": op, "name": row["id"]}
        reason = REASON_NAME_UNKNOWN if row["unparsed"] else None
        if op == "字段":
            atom["setcodes"] = self.lookups["archetypes"].get(fold_width(name), [])
            if form:
                atom["form"] = form
            if reason is None and not atom["setcodes"]:
                reason = REASON_NOT_ARCHETYPE
        return atom, reason

    def parse_modifiers(self, mods):
        """修飾語 → (原子列表, 原因):名稱類的句型逐個認,其餘以「・」切成一截截給
        `parse_modifier`(種族、屬性、レベルN);認不得的那截以「解析不出」原子收尾。"""
        atoms, reason, rest = [], None, mods
        while rest:
            # 種族/屬性的「・」列舉(含後面的「の」)整組先認:「ドラゴン族・鳥獣族」是或、
            # 「光・闇属性」逐截切會把「光」認不出。
            atom, length = parse_param_group(rest)
            if atom is not None:
                atoms.append(atom)
                rest = rest[length:]
                continue
            if rest.startswith("・"):  # 列舉後接的其他修飾語(植物族・レベル１)
                rest = rest[1:]
            for kind, pattern in _MOD_RES:
                m = pattern.match(rest)
                if m:
                    break
            else:
                piece, _, remainder = rest.partition("・")
                atom = parse_modifier(piece)
                if atom is not None:
                    atoms.append(atom)
                    rest = remainder
                    continue
                extra = parse_atom_modifier(rest, self)   # 票 07 的原子(condition_atoms)
                if extra is None:
                    atoms.append({"op": "解析不出", "text": rest})
                    return atoms, reason or REASON_MODS
                new_atoms, why, end = extra
                if not new_atoms:
                    atoms.append({"op": "解析不出", "text": rest})
                    return atoms, reason or why
                atoms.extend(new_atoms)
                reason = reason or why
                rest = rest[end:]
                continue
            if kind == "以外":
                atom, why = self.name_atom("卡名", m.group("name"))
                if atom:
                    atom = {"op": "非", "arg": atom}
            elif kind == "卡名包含":
                atom, why = self.name_atom("卡名包含", m.group("name"))
            else:
                atom, why = self.name_atom(
                    "字段", m.group("name"),
                    form=kind if kind == "と名のついた" else None)
            if atom is None:
                atoms.append({"op": "解析不出", "text": rest})
                return atoms, reason or why
            atoms.append(atom)
            reason = reason or why
            rest = rest[m.end():]
        return atoms, reason

    def find(self, obj_id):
        for obj in self.card["objects"]:
            if obj["id"] == obj_id:
                return obj
        return None

    def current_position(self, obj_id):
        """物件目前位置:動過就是最後的「到」,沒動過就是初始位置;都沒有回 None。"""
        if obj_id in self.positions:
            return self.positions[obj_id]
        obj = self.find(obj_id)
        if obj and obj["initial_position"]:
            return {"zones": list(obj["initial_position"]), "inferred": False}
        return None

    def recent_of(self, head, action=None):
        """最近的同大類物件;給了動作詞就只找本區塊被做過那個動作的(動作回指)。"""
        want = HEAD_CATEGORY[head]
        # 「このカード」不進 recent(その 不會指它),但動作回指可以:「このカードを特殊召喚する。
        # 〜この効果で特殊召喚したモンスターに装備」;它的大類看卡片屬性表。
        candidates = list(reversed(self.recent)) + ([self.self_id] if action else [])
        for obj_id in candidates:
            if action is not None and action not in self.acted.get(obj_id, ()):
                continue
            obj = self.find(obj_id)
            category = (_category_of(obj["condition"]) if obj_id != self.self_id
                        or obj["source"]["kind"] != "自己" else self._self_category())
            if want == "卡" or category == want:
                return obj_id
        return None

    def _self_category(self):
        rows = self.card["attributes"]["category"]
        return rows[0]["value"] if rows else None

    def action_reference(self, phrase):
        """動作回指短語 → 物件 id;不是動作回指回 None(區分不開「找不到」時呼叫端自己判)。"""
        m = _ACTION_REF_RE.match(phrase)
        if not m or m.group("past") not in ACTION_PAST.values():
            return None
        action = next(a for a, past in ACTION_PAST.items() if past == m.group("past"))
        return self.recent_of(m.group("head"), action)

    def is_action_reference(self, phrase):
        m = _ACTION_REF_RE.match(phrase)
        return bool(m and m.group("past") in ACTION_PAST.values())

    def resolve_reference(self, phrase):
        """修飾語裡指回的物件短語(「そのモンスターのランク」「見せたモンスターと同じ」的
        その/それらの+頭名詞、動作回指)→ 物件 id 或 None;與 object_at 同一把尺。"""
        ref = _REF_RE.match(phrase)
        if ref:
            return self.recent_of(ref.group("head"))
        if self.is_action_reference(phrase):
            return self.action_reference(phrase)
        return None

    def add_object(self, obj):
        self.card["objects"].append(obj)
        self.recent.append(obj["id"])
        return obj["id"]

    def _offset(self, phrase, sentence_start):
        offset = self.block["text"].find(phrase, sentence_start)
        return offset if offset >= 0 else sentence_start

    def object_at(self, phrase, sentence_start):
        """物件短語 → (物件 id, 回指字面, 原因);回指字面 None = 本段首次出現。"""
        if _SELF_RE.match(phrase):
            return self.self_id, None, None
        ref = _REF_RE.match(phrase)
        if ref:
            obj_id = self.recent_of(ref.group("head"))
            return obj_id, phrase, (None if obj_id else REASON_REF)
        remainder = _REMAINDER_RE.match(phrase)
        if remainder:
            return self.remainder_object(phrase, remainder.group("head"),
                                         sentence_start)
        if self.is_action_reference(phrase):
            obj_id = self.action_reference(phrase)
            return obj_id, phrase, (None if obj_id else REASON_REF)
        return self.new_object(phrase, sentence_start, {"kind": "新建"})

    def new_object(self, phrase, sentence_start, source, initial_position=None):
        named = _NAMED_RE.match(phrase)
        m = named or _NOUN_RE.match(phrase)
        if not m:
            return None, None, REASON_OBJECT
        if named:
            condition, reason = self.name_atom("卡名", named.group("name"))
            if condition is None:
                condition = {"op": "解析不出", "text": phrase}
        else:
            atoms, reason = self.parse_modifiers(m.group("mods"))
            condition = category_condition(m.group("head"))
            if atoms:
                # 且 的順序 = 字面順序(修飾語在前、大類頭名詞在後),反向檢查照此組回。
                condition = {"op": "且", "args": atoms + [condition]}
            # 名詞修飾的位置(「墓地のモンスター」「EXデッキの「No.」Xモンスター」)就是
            # 物件的初始位置:後續段「從」沒寫時由此繼承(spec「初始位置」)。
            if initial_position is None:
                located = [z for a in atoms if a.get("op") == "位置" for z in a["zones"]]
                initial_position = [dict(z) for z in located] or None
        offset = self._offset(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", source,
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=condition,
                         count=parse_count(m), initial_position=initial_position)
        if reason:
            obj["unparsed"] = unparsed(reason)
        return self.add_object(obj), None, None

    # ── 物件來源:子集、剩餘(票 10;集中在這裡,票 04 不動) ──
    def subset_object(self, phrase, container_id, sentence_start):
        """容器的子集:條件是子集自己的條件,初始位置繼承容器目前位置;
        來源的 select(全部/選)、chooser、random 有值才寫(產物省略空格)。"""
        current = self.current_position(container_id)
        obj_id, _, reason = self.new_object(
            phrase, sentence_start,
            {"kind": "子集", "of": container_id},
            initial_position=current["zones"] if current else None)
        return obj_id, None, reason

    def remainder_object(self, phrase, head, sentence_start):
        """「残りのX」= 最近的子集的容器 − 那個子集;子集是「全部」時剩餘 = 容器條件且非子集條件。"""
        subset = next((self.find(i) for i in reversed(self.recent)
                       if self.find(i)["source"]["kind"] == "子集"), None)
        if subset is None:
            return None, None, REASON_REF
        container = self.find(subset["source"]["of"])
        current = self.current_position(container["id"])
        condition = container["condition"]
        if subset["source"].get("select") == "全部":
            condition = {"op": "且", "args": [condition,
                                              {"op": "非", "arg": subset["condition"]}]}
        offset = self._offset(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}",
                         {"kind": "剩餘", "of": container["id"], "minus": subset["id"]},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=condition,
                         initial_position=current["zones"] if current else None)
        return self.add_object(obj), None, None


def _category_of(condition):
    if not condition:
        return None
    if condition.get("op") == "大類":
        return condition["value"]
    if condition.get("op") == "且":
        for arg in condition["args"]:
            found = _category_of(arg)
            if found:
                return found
    return None


def _fill_existence(seg, m, state, sentence_start):
    """存在前提:「(容器)の中に(物件)があった」→ 容器回指線 + 子集物件。"""
    container_id, ref, reason = state.object_at(m.group("container"), sentence_start)
    if container_id is None:
        seg["unparsed"] = unparsed(reason)
        return
    subset_id, _, reason = state.subset_object(m.group("objects"), container_id,
                                               sentence_start)
    if subset_id is None:
        seg["unparsed"] = unparsed(reason)
        return
    seg["predicate"] = m.group("pred")
    seg["lines"] = [new_line(container_id, "受事", ref=ref),
                    new_line(subset_id, "受事")]
    seg["premise"] = {"op": "存在", "object": subset_id, "in": container_id}


def _fill_clause(seg, clause_text, kind, state, sentence_start):
    """把簡單子句解析進段;失敗就在段上標原因。"""
    exist = _EXIST_RE.match(clause_text)
    if exist:
        _fill_existence(seg, exist, state, sentence_start)
        return
    m = _CLAUSE_RE.match(clause_text)
    if not m:
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return
    pred, to_phrase = m.group("pred"), m.group("to")
    if pred == TARGET_WORD and not to_phrase and not m.group("recipient"):
        _fill_targeting(seg, m, state, sentence_start)
        return
    parsed = None
    if to_phrase:
        # 「墓地へ送る」「手札に加える」的到在述語裡:先試整串當述語。
        parsed, _ = parse_predicates(to_phrase + m.group("to_particle") + pred)
        if parsed is not None:
            pred, to_phrase = to_phrase + m.group("to_particle") + pred, None
    if parsed is None:
        parsed, reason = parse_predicates(pred)
    seg["predicate"] = pred
    if parsed is None:
        seg["unparsed"] = unparsed(reason)
        return
    seg["actions"] = [p[0] for p in parsed]
    voices = {p[1] for p in parsed}
    seg["voice"] = voices.pop() if len(voices) == 1 else "混合"
    seg["polarity"] = parsed[-1][2]
    seg["optional"] = True if any(p[4] for p in parsed) else None
    written_to = next((p[3] for p in reversed(parsed) if p[3]), None)
    agent = SIDE_WORDS.get(m.group("agent")) if m.group("agent") else None
    seg["agent"] = agent
    if m.group("recipient") in SIDE_WORDS:
        seg["recipient"] = SIDE_WORDS[m.group("recipient")]
    elif m.group("recipient"):
        # 受方是物件的回指(裝備的對象):{"object", "ref"},找不到就整段標原因。
        obj_id, ref, reason = state.object_at(m.group("recipient"), sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        seg["recipient"] = {"object": obj_id, "ref": ref}
    if m.group("cause"):
        kind_of = "戰鬥" if m.group("cause").startswith("戦闘") else "效果"
        seg["cause"] = {"kind": kind_of, "text": m.group("cause")}
    from_zones = None
    # 「從」寫在物件後(XをデッキからYに加える)記 placement 述語前,模板放回原位。
    from_text, from_placement = None, "名詞前"
    if m.group("from"):
        from_text = m.group("from") + m.group("from_particle")
    elif m.group("from2"):
        from_text, from_placement = m.group("from2") + "から", "述語前"
    if from_text:
        from_zones = parse_from(m.group("from") or m.group("from2"))
        if from_zones is None:
            seg["unparsed"] = unparsed(REASON_FROM)
            return
    to_zones, to_text = None, None
    if to_phrase:
        to_zones, to_text = parse_from(to_phrase), to_phrase + m.group("to_particle")
    elif m.group("to_front"):
        if m.group("marker") != "が":
            seg["unparsed"] = unparsed(REASON_CLAUSE)
            return
        to_zones, to_text = parse_from(m.group("to_front")), m.group("to_front") + "に"
    if to_text and to_zones is None:
        seg["unparsed"] = unparsed(REASON_TO)
        return
    inferred_from, inferred_to = (None, None)
    if len(parsed) == 1:
        # 推得表照上位詞查:融合召喚沒寫「到」也是場上。
        inferred_from, inferred_to = next(
            (INFERENCE_TABLE[a] for a in action_ancestors(seg["actions"][0])
             if a in INFERENCE_TABLE), (None, None))
    # 推得的場上/墓地歸誰:特殊召喚(含下位詞)到施事者的場上;其餘不知道就不標方。
    summoning = any("特殊召喚" in action_ancestors(a) for a in seg["actions"])
    inferred_side = (agent or "我方") if summoning else None
    count = floating_count(m.group("count")) if m.group("count") else None
    for phrase in split_objects(m.group("objects")):
        obj_id, ref, reason = state.object_at(phrase, sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        obj = state.find(obj_id)
        if count is not None and count["cmp"] == "全部" and obj["source"]["kind"] == "子集":
            obj["source"]["select"] = "全部"
        role = "被召喚" if summoning else "受事"
        line = new_line(obj_id, role,
                        targeting=(kind == "效果" and obj_id in state.targeted),
                        marker=m.group("marker"), ref=ref, count=count)
        if from_zones is not None:
            line["from"] = position(from_zones, "明寫", text=from_text)
            if from_placement == "述語前":
                line["from"]["placement"] = from_placement
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = list(from_zones)
        else:
            current = state.current_position(obj_id)
            if current is not None:
                line["from"] = position(current["zones"], "繼承",
                                        inferred=current["inferred"])
            elif inferred_from:
                side = "我方" if inferred_from == "手牌" else None
                line["from"] = position([zone(inferred_from, side, side and "預設")],
                                        "推得", inferred=True)
        if to_zones is not None:
            line["to"] = position(to_zones, "明寫", text=to_text,
                                  form=m.group("form"))
            if m.group("to_front"):
                line["to"]["placement"] = "名詞前"
        elif written_to:
            line["to"] = position([zone(written_to, None)], "明寫")
        elif inferred_to:
            line["to"] = position([zone(inferred_to, inferred_side,
                                        inferred_side and "預設")], "推得",
                                  inferred=True, form=m.group("form"))
        seg["lines"].append(line)
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
        state.acted.setdefault(obj_id, []).extend(seg["actions"])
    _update_positions(seg, state)


def _fill_targeting(seg, m, state, sentence_start):
    """取對象子句「[從の]Xを対象として」:沒有動作詞,X 標成取對象(本區塊後文指回 X 的
    效果段對象線也標);從照簡單子句的規則。"""
    seg["predicate"] = TARGET_WORD
    from_zones, from_text = None, None
    if m.group("from"):
        from_text = m.group("from") + m.group("from_particle")
        from_zones = parse_from(m.group("from"))
        if from_zones is None:
            seg["unparsed"] = unparsed(REASON_FROM)
            return
    count = floating_count(m.group("count")) if m.group("count") else None
    for phrase in split_objects(m.group("objects")):
        obj_id, ref, reason = state.object_at(phrase, sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        obj = state.find(obj_id)
        line = new_line(obj_id, "受事", targeting=True, marker=m.group("marker"),
                        ref=ref, count=count)
        if from_zones is not None:
            line["from"] = position(from_zones, "明寫", text=from_text)
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = list(from_zones)
        else:
            current = state.current_position(obj_id)
            if current is not None:
                line["from"] = position(current["zones"], "繼承",
                                        inferred=current["inferred"])
        seg["lines"].append(line)
        state.targeted.add(obj_id)
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)


def _update_positions(seg, state):
    """位置自動規則:極性「做」的條件/代價/效果/召喚手續段,把「到」寫回目前位置。"""
    if seg["polarity"] != "做" or seg["kind"] not in ("條件", "代價", "效果",
                                                      "召喚手續"):
        return
    for line in seg["lines"]:
        if line["to"]:
            state.positions[line["object"]] = {
                "zones": line["to"]["zones"], "inferred": line["to"]["inferred"]}


def _segment(state, kind, start, end):
    text = state.block["text"]
    return new_segment(f"{state.block['id']}.s{start}", kind, (start, end),
                       text[start:end])




def sentences(text, body_start, end=None):
    """以「。」切句,回傳 (start, end) 且去掉頭尾空白換行;句號不含在範圍內。
    `end` 限定只切到這個偏移(● 分支的範圍)。"""
    limit = len(text) if end is None else end
    spans = []
    pos = body_start
    while pos < limit:
        stop = text.find("。", pos, limit)
        if stop < 0:
            stop = limit
        start, stop_at = pos, stop
        while start < stop_at and text[start] in "\n ":
            start += 1
        while stop_at > start and text[stop_at - 1] in "\n ":
            stop_at -= 1
        if start < stop_at:
            spans.append((start, stop_at))
        pos = stop + 1
    return spans


def _condition_and_rest(state, seg_start, clause_start, body, trig, segs):
    """觸發子句 → 條件段(範圍從 seg_start 起算:前面可能有前提);回傳 (剩下的子句, 它的起點)。"""
    cond_end = clause_start + len(trig.group("cond"))
    seg = _segment(state, "條件", seg_start, cond_end + len(trig.group("trig")))
    seg["trigger"] = trig.group("trig")
    _fill_clause(seg, trig.group("cond"), "條件", state, clause_start)
    segs.append((seg, None))
    rest = trig.group("rest")
    return rest, clause_start + body.rfind(rest) if rest else None


def _attach_premise(seg, premise):
    """前提寫進段;段已有前提(存在前提的條件段)時依字面順序組成「且」。"""
    if seg["premise"] is None:
        seg["premise"] = premise
        return
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    seg["premise"] = {"op": "且", "args": atoms + [seg["premise"]]}


def _ends_connective(chunk):
    """子句以「述語字面 + 連用形語尾」收尾(墓地へ送り、特殊召喚し、相手に見せ)才是同時連接的切點。"""
    for stem, _, _ in PREDICATE_STEMS:
        for tail in CONNECTIVE_TAILS:
            if chunk.endswith(stem + tail) and _CLAUSE_RE.match(chunk):
                return True
    return False


def split_joined(text):
    """「〜し、〜」「〜り、〜」的同時連接:在「」外的「、」處切,前一截要以連用形的述語收尾;
    回傳 [(子句, 相對偏移)]。切不出就是整句一截。"""
    chunks, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        elif ch == "、" and depth == 0 and _ends_connective(text[start:i]):
            chunks.append((text[start:i], start))
            start = i + 1
    chunks.append((text[start:], start))
    return chunks


def parse_sentence(state, start, end):
    """一句 → [(段, 與前一節點的連接)](發動句可產生條件段 + 代價段;舊式條件句產生條件段 + 效果段;
    「〜し、〜」串接的子句各自成段、以「同時」連接)。句首的前提先剝掉,掛在第一個段上、
    段的範圍從前提起算。"""
    text = state.block["text"]
    sent = text[start:end]
    act = _ACTIVATION_RE.match(sent)
    body = act.group("body") if act else sent
    premise, premise_end, clause_start = split_premises(body, state, start,
                                                        parse_from)
    body = text[clause_start:start + len(body)]
    if act and premise and body in ("", "に"):
        seg = _segment(state, "條件", start, premise_end)
        seg["premise"] = premise
        return [(seg, None)]
    segs = []
    trig = (_TRIGGER_RE if act else _OLD_TRIGGER_RE).match(body)
    rest, rest_start, seg_start = body, clause_start, start
    if trig:
        rest, rest_start = _condition_and_rest(state, start, clause_start, body,
                                               trig, segs)
        seg_start = rest_start
    if rest:
        kind = "代價" if act else "效果"
        chunks = split_joined(rest)
        for i, (chunk, offset) in enumerate(chunks):
            chunk_start = rest_start + offset
            seg = _segment(state, kind, seg_start if i == 0 else chunk_start,
                           chunk_start + len(chunk))
            last = i == len(chunks) - 1
            if act and last and not chunk.endswith(("て", "で")):
                seg["unparsed"] = unparsed(REASON_ACTIVATION)
            else:
                _fill_clause(seg, chunk, kind, state, chunk_start)
            segs.append((seg, "同時" if i else None))
    if premise and segs:
        _attach_premise(segs[0][0], premise)
    return segs
