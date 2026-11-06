"""段抽取:一個區塊的原文 → 段(扁平)+ 段樹 + 物件(寫進整卡共用的物件表)。

規則是句型層級的,不針對任何一張卡:
- 句子以「。」切;「その後、」開頭的句子與前一句連接為「先後」;區塊開頭的「また、」是接著詞。
- 發動句(…発動できる / …発動する):
    (條件子句)(時|場合|際)(に)、(代價子句)て  → 條件段 + 代價段
  條件段帶觸發形;代價子句以て形結尾才算代價。
- 舊式的「(條件子句)(時|場合|際)、(效果子句)」(沒有発動できる)→ 條件段 + 效果段。
- 舊式的「(代價子句)る事で、(效果子句)」(= 新式「〜て発動できる。〜」)→ 代價段 + 效果段。
- 其他句子是效果段;極性由述語語尾判(できない → 不能…);「〜できる」「〜事ができる」是
  可選的效果(可選格 `optional`,極性仍是做,查詢預設算命中;票 08 再分辨永續的「可以」)。
- 簡單子句:[誰が][從から|從の|從に存在する][物件](を|が|は)[數量][取對象][原因][形式][到に]述語。
  述語字面經同義表(`synonyms`)收成動作詞,語尾決定態與極性;て形串接的多個述語
  (めくられて墓地へ送られた)是多個動作詞。從/到保留含助詞的原文字面(`text`:「墓地の」
  「自分のデッキの上から」「デッキの一番下に」「墓地に存在する」),反向檢查據此還原
  (の/から/に存在する、に/へ 是字面的選擇,結構上都是明寫的從/到)。
- 取對象:舊式「Xを選択して(述語)」、新式「Xを対象として(述語)」把 X 的對象線標 `targeting`,
  字面留在原述語字面的開頭(「選択して破壊する」);述語空的(「Xを選択して発動できる」)是
  發動句的取對象宣告,代價段、沒有動作詞。之後效果段裡指回被點名物件的線(そのモンスター、
  舊式 選択したモンスター)也標取對象。「選択」不是動作詞。
- 存在前提:「(容器)の中に(物件)が(あった|ある|存在する)」→ 條件段,物件是容器的子集。
- 物件:このカード = 物件0;その/それらの モンスター|カード 指回本區塊最近的同大類物件
  (從條件段指回來的不標取對象;回指字面記在對象線 `ref`);「めくったカード」這類動作回指
  也指回;助詞後的數量(「を全て」「を２枚まで」)記在對象線 `count`,屬於這次提及;「残りのX」是
  剩餘物件(容器 − 最近的子集);其餘是新建物件,頭名詞給大類、數量給數量,修飾語從左到右認:
  「X」以外の = 非(卡名∋X);「X」と名のついた、緊接頭名詞的「X」= 字段(依字段表換成 setcode);
  カード名に「X」を含む = 卡名包含;「X」１体 = 卡名∋X;種族、屬性、レベルN = 屬性比較
  (「・」分隔)。認不得的修飾語整截標「解析不出」(票 05 起逐步填);「X」對不到卡名與字段的,
  物件標「不認得的「」名稱」。
- 位置:處理完一段把「到」寫回物件目前位置;「從」沒寫先繼承目前位置(沒動過就是初始位置),
  再查推得表;推得值與繼承自推得值的標 inferred,查詢開關開才算。
抽不出的段與物件一律標原因,不丟例外,全庫建置不中斷。
"""
import re

from archetype_table import fold_width
from attribute_words import ATTRIBUTE_JA, RACE_JA
from names_attributes import REASON_NAME_UNKNOWN
from structure_shape import (new_line, new_object, new_segment, position,
                             segment_node, unparsed, zone)
# 同義表(述語字面 → 動作詞、語尾、取對象字面)在 synonyms;這裡再匯出,舊的匯入點不變。
from synonyms import (  # noqa: F401
    ACTION_PAST, ACTIVATION_SUFFIXES, COST_GLUE, PREDICATE_STEMS,
    REASON_PREDICATE, REASON_TAIL, TAILS, TARGET_REF, TARGETING_PREFIXES,
    parse_predicate, parse_predicates, split_targeting)

# 推得表:動作詞 → (沒寫「從」時的出發地, 沒寫「到」時的終點)。
INFERENCE_TABLE = {
    "破壞": ("場上", "墓地"),
    "解放": ("場上", "墓地"),
    "捨棄": ("手牌", "墓地"),
    "特殊召喚": (None, "場上"),
}
# 區域字面(長的在前,EXデッキ 不能被 デッキ 先吃掉;同一區域多個字面時後者是反向檢查的預設寫法)。
ZONE_WORDS = (("EXデッキ", "額外牌組"), ("デッキの一番下", "牌組底"),
              ("デッキの一番上", "牌組頂"), ("デッキの上", "牌組頂"),
              ("デッキ", "牌組"), ("手札", "手牌"),
              ("フィールド上", "場上"),  # 舊式:フィールド上の = フィールドの
              ("フィールド", "場上"), ("墓地", "墓地"))
# 從的助詞:新式「墓地の」「墓地から」;舊式連體修飾「墓地に存在するX」(= 墓地のX)。
FROM_PARTICLES = ("から", "の", "に存在する")
HEAD_CATEGORY = {"モンスター": "怪獸", "魔法カード": "魔法", "罠カード": "陷阱",
                 "魔法・罠カード": ("魔法", "陷阱"), "カード": "卡"}
SIDE_WORDS = {"自分": "我方", "相手": "對手"}
# 原因:種類 → 允許的字面(反向檢查只認這些)。
CAUSE_TEXTS = {"效果": ("カードの効果によって", "効果によって", "カードの効果で", "効果で"),
               "戰鬥": ("戦闘によって", "戦闘で")}
EXIST_WORDS = ("あった", "ある", "存在する", "存在した")
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

_ZONE_PHRASE = ("(?:(?:自分|相手)の?)?(?:" + "|".join(w for w, _ in ZONE_WORDS) + ")"
                "(?:・(?:" + "|".join(w for w, _ in ZONE_WORDS) + "))*")
_ACTIVATION_RE = re.compile("^(?P<body>.*?)(?P<suffix>" + "|".join(ACTIVATION_SUFFIXES) + ")$")
_TRIGGER_RE = re.compile("^(?P<cond>.+?)(?P<trig>時|場合|際)に?、?(?P<rest>.*)$")
# 舊式的條件句:觸發形後一定有「、」才算,免得「終了時に」這類句中的時被當觸發。
_OLD_TRIGGER_RE = re.compile("^(?P<cond>.+?)(?P<trig>時|場合|際)(?:に)?、(?P<rest>.+)$")
# 舊式的代價句:「(代價子句)る事で、(效果子句)」= 新式「(代價子句)て発動できる。(效果子句)」。
# 代價子句以非過去形收尾(る/う/す)才算,「〜された事で」是條件意味、不切。
_OLD_COST_RE = re.compile("^(?P<cost>.+?[るうす])" + COST_GLUE + "、?(?P<rest>.+)$")
_CLAUSE_RE = re.compile(
    "^(?:(?P<agent>自分|相手)(?:が|は))?"
    f"(?:(?P<from>{_ZONE_PHRASE})(?P<from_particle>{'|'.join(FROM_PARTICLES)}))?"
    # 物件短語裡的「を含む」(カード名に「X」を含む)不是受詞助詞;述語裡沒有を,
    # 所以切錯時會回頭把「を含む」吃進物件短語。
    "(?P<objects>(?:を含む|[^を])+?)(?P<marker>を|が|は)"
    "(?P<count>[０-９]+(?:体|枚)(?:まで)?|全て)?"
    # 取對象字面(舊式 選択して、新式 対象として):單獨出現(述語空)是發動句的取對象宣告。
    f"(?P<targeting>{'|'.join(TARGETING_PREFIXES)})?"
    "(?P<cause>(?:カードの効果|効果|戦闘)(?:によって|で))?"
    "(?P<form>好きな順番で)?"
    f"(?:(?P<to>{_ZONE_PHRASE})(?P<to_particle>に|へ))?"
    "(?P<pred>[^を]*)$")
_EXIST_RE = re.compile(
    "^(?P<container>.+?)の中に(?P<objects>.+?)が(?P<pred>" + "|".join(EXIST_WORDS) + ")$")
_FROM_RE = re.compile("^(?:(?P<side>自分|相手)の?)?(?P<zones>.+)$")
_SELF_RE = re.compile("^このカード$")
_REF_RE = re.compile("^(?P<ref>その|それらの)(?P<head>モンスター|カード)$")
_REMAINDER_RE = re.compile("^残りの(?P<head>モンスター|カード)$")
# 「選択したモンスター」:指回本區塊最近被取對象的同大類物件(舊式;新式用 そのモンスター)。
_TARGET_REF_RE = re.compile(f"^{TARGET_REF}(?P<head>モンスター|カード)$")
_ACTION_REF_RE = re.compile("^(?P<past>.+?)(?P<head>モンスター|カード)$")
_NOUN_RE = re.compile(
    "^(?P<mods>.*?)(?P<head>モンスター|魔法・罠カード|魔法カード|罠カード|カード)"
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

REASON_NOT_ARCHETYPE = "「」名稱不是字段"
REASON_CLAUSE = "子句解析不出"
REASON_FROM = "從解析不出"
REASON_TO = "到解析不出"
REASON_OBJECT = "物件解析不出"
REASON_MODS = "物件修飾解析不出"
REASON_REF = "指回的物件找不到"
REASON_ACTIVATION = "發動句解析不出"
REASON_CAUSE = "原因解析不出"


def parse_from(phrase):
    """「自分の手札・フィールド」→ 區域列表;任何一截不是區域字面就回 None。"""
    m = _FROM_RE.match(phrase)
    if not m:
        return None
    side = SIDE_WORDS.get(m.group("side"), "我方")
    zones = []
    for part in m.group("zones").split("・"):
        for word, name in ZONE_WORDS:
            if part == word:
                zones.append(zone(name, side))
                break
        else:
            return None
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
        if ch == "と" and depth == 0 and not phrase.startswith("と名のついた", i):
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p for p in parts if p]


class BlockState:
    """一個區塊抽取時的工作狀態:物件目前位置、本區塊提過的物件(給その指回)、
    名稱表(「X」→ 名稱列)與字段對照。"""

    def __init__(self, block, card, lookups=None):
        self.block = block
        self.card = card
        self.lookups = lookups or {"card_names": set(), "archetypes": {}}
        self.names = {row["text"]: row for row in card["names"]}
        self.positions = {}   # 物件 id → {"zones", "inferred"}
        self.recent = []      # 本區塊建立或引用過的物件 id(其後者優先)
        self.targeted = []     # 被取對象的物件 id(「を選択して」「を対象として」點名的,後者優先)

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
            for kind, pattern in _MOD_RES:
                m = pattern.match(rest)
                if m:
                    break
            else:
                piece, _, remainder = rest.partition("・")
                atom = parse_modifier(piece)
                if atom is None:
                    atoms.append({"op": "解析不出", "text": rest})
                    return atoms, reason or REASON_MODS
                atoms.append(atom)
                rest = remainder
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

    def recent_of(self, head, among=None):
        """本區塊最近提過的同大類物件(頭名詞 カード 任何大類都算);`among` 可改成別的候選列。"""
        want = HEAD_CATEGORY[head]
        for obj_id in reversed(self.recent if among is None else among):
            obj = self.find(obj_id)
            if want == "卡" or _category_of(obj["condition"]) == want:
                return obj_id
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
            return "o0", None, None
        ref = _REF_RE.match(phrase)
        if ref:
            obj_id = self.recent_of(ref.group("head"))
            return obj_id, phrase, (None if obj_id else REASON_REF)
        remainder = _REMAINDER_RE.match(phrase)
        if remainder:
            return self.remainder_object(phrase, remainder.group("head"),
                                         sentence_start)
        target_ref = _TARGET_REF_RE.match(phrase)
        if target_ref:
            obj_id = self.recent_of(target_ref.group("head"), among=self.targeted)
            return obj_id, phrase, (None if obj_id else REASON_REF)
        action_ref = _ACTION_REF_RE.match(phrase)
        if action_ref and action_ref.group("past") in ACTION_PAST.values():
            obj_id = self.recent_of(action_ref.group("head"))
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
    if not m or not (m.group("pred") or m.group("targeting")):
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return
    pred, to_phrase, targeting = m.group("pred"), m.group("to"), m.group("targeting")
    parsed = None
    if to_phrase:
        # 「墓地へ送る」「手札に加える」的到在述語裡:先試整串當述語。
        parsed, _ = parse_predicates(to_phrase + m.group("to_particle") + pred)
        if parsed is not None:
            pred, to_phrase = to_phrase + m.group("to_particle") + pred, None
    if parsed is None and pred:
        parsed, reason = parse_predicates(pred)
    # 原述語字面含取對象字面(「選択して破壊する」);反向檢查以 split_targeting 拆回。
    seg["predicate"] = (targeting or "") + pred
    if parsed is None and pred:
        seg["unparsed"] = unparsed(reason)
        return
    if parsed is None:
        # 發動句的取對象宣告(「Xを選択して発動できる」):沒有動作詞,只把物件標成取對象。
        parsed = []
    seg["actions"] = [p[0] for p in parsed]
    voices = {p[1] for p in parsed}
    seg["voice"] = voices.pop() if len(voices) == 1 else ("混合" if voices else None)
    seg["polarity"] = parsed[-1][2] if parsed else "做"
    seg["optional"] = True if any(p[4] for p in parsed) else None
    written_to = next((p[3] for p in reversed(parsed) if p[3]), None)
    agent = SIDE_WORDS.get(m.group("agent")) if m.group("agent") else None
    seg["agent"] = agent
    if m.group("cause"):
        kind_of = "戰鬥" if m.group("cause").startswith("戦闘") else "效果"
        seg["cause"] = {"kind": kind_of, "text": m.group("cause")}
    from_zones = None
    if m.group("from"):
        from_zones = parse_from(m.group("from"))
        if from_zones is None:
            seg["unparsed"] = unparsed(REASON_FROM)
            return
    to_zones = None
    if to_phrase:
        to_zones = parse_from(to_phrase)
        if to_zones is None:
            seg["unparsed"] = unparsed(REASON_TO)
            return
    inferred_from, inferred_to = (None, None)
    if len(parsed) == 1:
        inferred_from, inferred_to = INFERENCE_TABLE.get(seg["actions"][0], (None, None))
    # 推得的場上/墓地歸誰:特殊召喚到施事者的場上;其餘不知道就不標方。
    inferred_side = (agent or "我方") if "特殊召喚" in seg["actions"] else None
    count = floating_count(m.group("count")) if m.group("count") else None
    for phrase in split_objects(m.group("objects")):
        obj_id, ref, reason = state.object_at(phrase, sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        obj = state.find(obj_id)
        if count is not None and count["cmp"] == "全部" and obj["source"]["kind"] == "子集":
            obj["source"]["select"] = "全部"
        role = "被召喚" if "特殊召喚" in seg["actions"] else "受事"
        if targeting:
            state.targeted.append(obj_id)
        # 取對象標記:這一句點名的,或效果段裡指回先前被點名的物件(そのモンスター、選択したモンスター)。
        line = new_line(obj_id, role,
                        targeting=bool(targeting) or (kind == "效果"
                                                      and obj_id in state.targeted),
                        marker=m.group("marker"), ref=ref, count=count)
        if from_zones is not None:
            line["from"] = position(from_zones, "明寫",
                                    text=m.group("from") + m.group("from_particle"))
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = list(from_zones)
        else:
            current = state.current_position(obj_id)
            if current is not None:
                line["from"] = position(current["zones"], "繼承",
                                        inferred=current["inferred"])
            elif inferred_from:
                side = "我方" if inferred_from == "手牌" else None
                line["from"] = position([zone(inferred_from, side)], "推得",
                                        inferred=True)
        if to_zones is not None:
            line["to"] = position(to_zones, "明寫",
                                  text=to_phrase + m.group("to_particle"),
                                  form=m.group("form"))
        elif written_to:
            line["to"] = position([zone(written_to, None)], "明寫")
        elif inferred_to:
            line["to"] = position([zone(inferred_to, inferred_side)], "推得",
                                  inferred=True)
        seg["lines"].append(line)
        if obj_id != "o0" and obj_id not in state.recent:
            state.recent.append(obj_id)
    _update_positions(seg, state)


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


def _sentences(text, body_start):
    """以「。」切句,回傳 (start, end) 且去掉頭尾空白換行;句號不含在範圍內。"""
    spans = []
    pos = body_start
    while pos < len(text):
        stop = text.find("。", pos)
        if stop < 0:
            stop = len(text)
        start, end = pos, stop
        while start < end and text[start] in "\n ":
            start += 1
        while end > start and text[end - 1] in "\n ":
            end -= 1
        if start < end:
            spans.append((start, end))
        pos = stop + 1
    return spans


def _condition_and_rest(state, start, body, trig, segs):
    """觸發子句 → 條件段;回傳 (剩下的子句, 它的起點)。"""
    cond_end = start + len(trig.group("cond"))
    seg = _segment(state, "條件", start, cond_end + len(trig.group("trig")))
    seg["trigger"] = trig.group("trig")
    _fill_clause(seg, trig.group("cond"), "條件", state, start)
    segs.append(seg)
    rest = trig.group("rest")
    return rest, start + body.rfind(rest) if rest else None


def _cost_and_effect(state, clause, start):
    """效果子句 → [效果段],或舊式代價句「(代價)る事で、(效果)」→ [代價段, 效果段]。"""
    cost = _OLD_COST_RE.match(clause)
    if not cost:
        seg = _segment(state, "效果", start, start + len(clause))
        _fill_clause(seg, clause, "效果", state, start)
        return [seg]
    cost_text, rest = cost.group("cost"), cost.group("rest")
    cost_seg = _segment(state, "代價", start, start + len(cost_text))
    _fill_clause(cost_seg, cost_text, "代價", state, start)
    rest_start = start + len(clause) - len(rest)
    effect_seg = _segment(state, "效果", rest_start, rest_start + len(rest))
    _fill_clause(effect_seg, rest, "效果", state, rest_start)
    return [cost_seg, effect_seg]


def _parse_sentence(state, start, end):
    """一句 → 段列表(發動句可產生條件段 + 代價段;舊式條件句產生條件段 + 效果段;
    舊式代價句產生代價段 + 效果段)。"""
    text = state.block["text"]
    sent = text[start:end]
    act = _ACTIVATION_RE.match(sent)
    if not act:
        trig = _OLD_TRIGGER_RE.match(sent)
        if trig:
            segs = []
            rest, rest_start = _condition_and_rest(state, start, sent, trig, segs)
            return segs + _cost_and_effect(state, rest, rest_start)
        return _cost_and_effect(state, sent, start)
    body = act.group("body")
    segs = []
    trig = _TRIGGER_RE.match(body)
    rest, rest_start = body, start
    if trig:
        rest, rest_start = _condition_and_rest(state, start, body, trig, segs)
    if rest:
        seg = _segment(state, "代價", rest_start, rest_start + len(rest))
        if rest.endswith(("て", "で")):
            _fill_clause(seg, rest, "代價", state, rest_start)
        else:
            seg["unparsed"] = unparsed(REASON_ACTIVATION)
        segs.append(seg)
    return segs


def extract_block(block, card, lookups=None):
    """就地把段、段樹寫進 block,物件寫進 card["objects"];lookups 見 card_structure.build_lookups。"""
    state = BlockState(block, card, lookups)
    body_start = 2 if block["label"] else 0  # 「①：」兩個字元
    if block["text"].startswith("また、", body_start):
        body_start += 3  # 區塊開頭的接著詞
    join = None
    for start, end in _sentences(block["text"], body_start):
        if block["text"].startswith("その後、", start):
            join, start = "先後", start + 4
        for seg in _parse_sentence(state, start, end):
            block["segments"].append(seg)
            block["tree"]["items"].append(segment_node(seg["id"], join))
            join = None
    return block
