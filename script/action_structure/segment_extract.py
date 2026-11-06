"""段抽取:一個區塊的原文 → 段(扁平)+ 段樹 + 物件(寫進整卡共用的物件表)。

規則是句型層級的,不針對任何一張卡:
- 句子以「。」切;「その後、」開頭的句子與前一句連接為「先後」。
- 發動句(…発動できる / …発動する):
    (條件子句)(時|場合|際)(に)、(代價子句)て  → 條件段 + 代價段
  條件段帶觸發形;代價子句以て形結尾才算代價。
- 其他句子是效果段;極性由述語語尾判(できる → 可以、できない → 不能…)。
- 簡單子句:[誰が][從から][物件を]述語。述語字面經同義表收成動作詞,語尾決定態與極性。
- 物件:このカード = 物件0;その/それらの モンスター|カード 指回本區塊最近的同大類物件
  (從條件段指回來的不標取對象);其餘是新建物件,頭名詞給大類、數量給數量,
  前面的修飾語先整段標「解析不出」(票 04 起逐步填)。
- 位置:處理完一段把「到」寫回物件目前位置;「從」沒寫先繼承目前位置,
  再查推得表;推得值與繼承自推得值的標 inferred,查詢開關開才算。
抽不出的段與物件一律標原因,不丟例外,全庫建置不中斷。
"""
import re

from structure_shape import (new_line, new_object, new_segment, position,
                             segment_node, unparsed, zone)

# ── 同義表:述語字面 → 動作詞;第三欄是述語本身寫明的終點(「墓地へ送る」)。
PREDICATE_STEMS = (
    ("特殊召喚", "特殊召喚", None),
    ("破壊", "破壞", None),
    ("捨て", "捨棄", None),
    ("リリース", "解放", None),
    ("除外", "除外", "除外"),
    ("墓地へ送", "送墓", "墓地"),
    ("手札に加え", "加入手牌", "手牌"),
)
# 述語語尾 → (態, 極性)。語尾不在表內的述語標「述語語尾不明」,不猜。
TAILS = {
    "": ("主動", "做"), "る": ("主動", "做"), "する": ("主動", "做"),
    "した": ("主動", "做"), "し": ("主動", "做"), "して": ("主動", "做"),
    "て": ("主動", "做"),
    "される": ("被動", "做"), "された": ("被動", "做"), "され": ("被動", "做"),
    "されて": ("被動", "做"),
    "られる": ("被動", "做"), "られた": ("被動", "做"), "られ": ("被動", "做"),
    "られて": ("被動", "做"),
    "できる": ("主動", "可以"), "できない": ("主動", "不能"),
    "できず": ("主動", "不能"),
    "しない": ("主動", "不會"), "されない": ("被動", "不會"),
    "られない": ("被動", "不會"),
}
# 推得表:動作詞 → (沒寫「從」時的出發地, 沒寫「到」時的終點)。
INFERENCE_TABLE = {
    "破壞": ("場上", "墓地"),
    "解放": ("場上", "墓地"),
    "捨棄": ("手牌", "墓地"),
    "特殊召喚": (None, "場上"),
}
# 區域字面(長的在前,EXデッキ 不能被 デッキ 先吃掉)。
ZONE_WORDS = (("EXデッキ", "額外牌組"), ("デッキ", "牌組"), ("手札", "手牌"),
              ("フィールド", "場上"), ("墓地", "墓地"))
HEAD_CATEGORY = {"モンスター": "怪獸", "魔法カード": "魔法", "罠カード": "陷阱",
                 "魔法・罠カード": ("魔法", "陷阱"), "カード": "卡"}
SIDE_WORDS = {"自分": "我方", "相手": "對手"}
FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")

_ACTIVATION_RE = re.compile("^(?P<body>.*?)(?P<suffix>発動できる|発動する)$")
_TRIGGER_RE = re.compile("^(?P<cond>.+?)(?P<trig>時|場合|際)に?、?(?P<rest>.*)$")
_CLAUSE_RE = re.compile(
    "^(?:(?P<agent>自分|相手)が)?(?:(?P<from>[^を]+?)から)?"
    "(?P<objects>[^を]+?)を(?P<pred>[^を]+)$")
_FROM_RE = re.compile("^(?:(?P<side>自分|相手)の?)?(?P<zones>.+)$")
_SELF_RE = re.compile("^このカード$")
_REF_RE = re.compile("^(?:その|それらの)(?P<head>モンスター|カード)$")
_NOUN_RE = re.compile(
    "^(?P<mods>.*?)(?P<head>モンスター|魔法・罠カード|魔法カード|罠カード|カード)"
    "(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")

REASON_PREDICATE = "述語解析不出"
REASON_TAIL = "述語語尾不明"
REASON_CLAUSE = "子句解析不出"
REASON_FROM = "從解析不出"
REASON_OBJECT = "物件解析不出"
REASON_MODS = "物件修飾解析不出"
REASON_REF = "指回的物件找不到"
REASON_ACTIVATION = "發動句解析不出"


def parse_predicate(pred):
    """述語字面 → (動作詞, 態, 極性, 寫明的終點) 或 (None, 原因)。"""
    for stem, action, to in PREDICATE_STEMS:
        if pred.startswith(stem):
            tail = pred[len(stem):]
            if tail not in TAILS:
                return None, REASON_TAIL
            voice, polarity = TAILS[tail]
            return (action, voice, polarity, to), None
    return None, REASON_PREDICATE


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


def category_condition(head):
    value = HEAD_CATEGORY[head]
    if isinstance(value, tuple):
        return {"op": "或", "args": [{"op": "大類", "value": v} for v in value]}
    return {"op": "大類", "value": value}


def split_objects(phrase):
    """以「と」切物件,但「」裡的と不算(「X」と名のついた 是字段寫法,票 04)。"""
    parts, depth, buf = [], 0, ""
    for ch in phrase:
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        if ch == "と" and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    return [p for p in parts if p]


class BlockState:
    """一個區塊抽取時的工作狀態:物件目前位置、本區塊提過的物件(給その指回)。"""

    def __init__(self, block, card):
        self.block = block
        self.card = card
        self.positions = {}   # 物件 id → {"zones", "inferred"}
        self.recent = []      # 本區塊建立或引用過的物件 id(其後者優先)
        self.targeted = set()  # 「を対象として」點名的物件(票 08 填)

    def object_at(self, phrase, sentence_start):
        """物件短語 → (物件 id, 由條件段指回來的?) 或 (None, 原因)。"""
        if _SELF_RE.match(phrase):
            return "o0", None
        ref = _REF_RE.match(phrase)
        if ref:
            want = HEAD_CATEGORY[ref.group("head")]
            for obj_id in reversed(self.recent):
                obj = self.find(obj_id)
                if want == "卡" or _category_of(obj["condition"]) == want:
                    return obj_id, None
            return None, REASON_REF
        m = _NOUN_RE.match(phrase)
        if not m:
            return None, REASON_OBJECT
        text = self.block["text"]
        offset = text.find(phrase, sentence_start)
        if offset < 0:
            offset = sentence_start
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"],
                         condition=category_condition(m.group("head")),
                         count=parse_count(m))
        if m.group("mods"):
            obj["condition"] = {"op": "且", "args": [
                obj["condition"],
                {"op": "解析不出", "text": m.group("mods")}]}
            obj["unparsed"] = unparsed(REASON_MODS)
        self.card["objects"].append(obj)
        self.recent.append(obj["id"])
        return obj["id"], None

    def find(self, obj_id):
        for obj in self.card["objects"]:
            if obj["id"] == obj_id:
                return obj
        return None


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


def _fill_clause(seg, clause_text, kind, state, sentence_start):
    """把簡單子句解析進段;失敗就在段上標原因。"""
    m = _CLAUSE_RE.match(clause_text)
    if not m:
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return
    parsed, reason = parse_predicate(m.group("pred"))
    seg["predicate"] = m.group("pred")
    if parsed is None:
        seg["unparsed"] = unparsed(reason)
        return
    action, voice, polarity, written_to = parsed
    seg["actions"] = [action]
    seg["voice"] = voice
    seg["polarity"] = polarity
    agent = SIDE_WORDS.get(m.group("agent")) if m.group("agent") else None
    seg["agent"] = agent
    from_zones = None
    if m.group("from"):
        from_zones = parse_from(m.group("from"))
        if from_zones is None:
            seg["unparsed"] = unparsed(REASON_FROM)
            return
    inferred_from, inferred_to = INFERENCE_TABLE.get(action, (None, None))
    # 推得的場上/墓地歸誰:特殊召喚到施事者的場上;其餘不知道就不標方。
    inferred_side = (agent or "我方") if action == "特殊召喚" else None
    for phrase in split_objects(m.group("objects")):
        obj_id, reason = state.object_at(phrase, sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return
        role = "被召喚" if action == "特殊召喚" else "受事"
        line = new_line(obj_id, role,
                        targeting=(kind == "效果" and obj_id in state.targeted))
        if from_zones is not None:
            line["from"] = position(from_zones, "明寫")
            obj = state.find(obj_id)
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = list(from_zones)
        elif obj_id in state.positions:
            current = state.positions[obj_id]
            line["from"] = position(current["zones"], "繼承",
                                    inferred=current["inferred"])
        elif inferred_from:
            side = "我方" if inferred_from == "手牌" else None
            line["from"] = position([zone(inferred_from, side)], "推得",
                                    inferred=True)
        if written_to:
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


def _parse_sentence(state, start, end):
    """一句 → 段列表(發動句可產生條件段 + 代價段)。"""
    text = state.block["text"]
    sent = text[start:end]
    act = _ACTIVATION_RE.match(sent)
    if not act:
        seg = _segment(state, "效果", start, end)
        _fill_clause(seg, sent, "效果", state, start)
        return [seg]
    body = act.group("body")
    segs = []
    trig = _TRIGGER_RE.match(body)
    rest = body
    if trig:
        cond_end = start + len(trig.group("cond"))
        seg = _segment(state, "條件", start, cond_end + len(trig.group("trig")))
        seg["trigger"] = trig.group("trig")
        _fill_clause(seg, trig.group("cond"), "條件", state, start)
        segs.append(seg)
        rest = trig.group("rest")
    if rest:
        rest_start = start + body.rfind(rest)
        seg = _segment(state, "代價", rest_start, rest_start + len(rest))
        if rest.endswith(("て", "で")):
            _fill_clause(seg, rest, "代價", state, rest_start)
        else:
            seg["unparsed"] = unparsed(REASON_ACTIVATION)
        segs.append(seg)
    return segs


def extract_block(block, card):
    """就地把段、段樹寫進 block,物件寫進 card["objects"]。"""
    state = BlockState(block, card)
    body_start = 2 if block["label"] else 0  # 「①：」兩個字元
    join = None
    for start, end in _sentences(block["text"], body_start):
        if block["text"].startswith("その後、", start):
            join, start = "先後", start + 4
        for seg in _parse_sentence(state, start, end):
            block["segments"].append(seg)
            block["tree"]["items"].append(segment_node(seg["id"], join))
            join = None
    return block
