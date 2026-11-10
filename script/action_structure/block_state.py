"""區塊抽取時的工作狀態 `BlockState` 與物件短語的解析。

- `BlockState`:物件目前位置、本區塊提過/被取對象/被做過動作的物件、本句的主語(`subject` 與
  前一截「Xは」的三態 `topic`)、名稱表;`object_at` 把物件短語解成物件(此卡、回指、動作回指、
  剩餘、超量素材/計數器、新建),`new_object`、`subset_object` 等建物件。
- 物件短語的字面閉集與句型(回指 `REF_RE`、`TARGET_REF_RE`、`ACTION_REF_RE`,超量素材、計數器)
  在這裡;名詞短語的修飾語與頭名詞在 `noun_phrase`。
- 推得表 `INFERENCE_TABLE` 與位置自動規則 `update_positions`;`segment_at` 由區塊原文的範圍開一個段。
- 各模組共用的解析不出原因(`REASON_CLAUSE`、`REASON_OBJECT`、`REASON_REF`、`REASON_TWICE`…)。
- `ClauseContext`:各句型的 `fill_clause` 共用的參數(段、區塊狀態、句子起點、承襲的時機)。
誰、原因、區域、數量各自的字面在 `agent_phrase`、`cause_phrase`、`zone_phrase`、`quantity`。

規則:
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
- 去除:對象是超量素材「(Xの)X素材」(`of` 所屬卡;沒寫時是隱含的新建超量怪獸,初始位置 = 從)
  與計數器「(Xの)魔力カウンター」(`counter` 種類名);數量單位「つ」;舊式代價「〜く事で、」。
  另收:「このカードを対象とする(Xの)効果が発動した」(物件條件 以此卡為對象)、超量素材行「×N」、
  物件前的「〜の数まで、」、片假名子類型(リンク…)、修飾語連接字與預設不同時記 `joiner`。
"""

import re
from dataclasses import dataclass
from typing import NamedTuple

from archetype_table import fold_width
from condition_atoms import TARGETING_THIS_FORMS, targeting_this_atom
from names_attributes import REASON_NAME_UNKNOWN
from noun_phrase import (EFFECT_HEADS, HEAD_CATEGORY, NOUN_RE, category_condition,
                         category_of, noun_condition, parse_modifiers, split_alternatives)
from quantity import parse_count
from segment_fields import implicit_delay
from structure_shape import new_object, new_segment, unparsed
from synonyms import ACTION_PAST, TARGET_REF, XYZ_MATERIAL_WORDS, is_summon


# 推得表:動作詞 → (沒寫「從」時的出發地, 沒寫「到」時的終點)。
INFERENCE_TABLE = {
    "破壞": ("場上", "墓地"),
    "解放": ("場上", "墓地"),
    "捨棄": ("手牌", "墓地"),
    "特殊召喚": (None, "場上"),
    "裝備": (None, "魔陷區"),
    "放置": (None, "魔陷區"),
    "覆蓋": (None, "魔陷區"),
    "抽牌": ("牌組", "手牌"),
}
# 次數限制字面(「１ターンに１度、」):spec 說不記,出現在句中時進略過文本(原因 次數限制),
# 反向檢查比對時扣掉。
INTERVAL_PATTERN = "(?:１ターンに|デュエル中に)[１-９]度、"
INTERVAL_RE = re.compile(INTERVAL_PATTERN)
INTERVAL_REASON = "次數限制"
KIND_PROCEDURE, KIND_RESTRICTION, KIND_MODIFIER = "召喚手續", "限制", "修飾"
_SELF_RE = re.compile("^このカード$")
REF_RE = re.compile("^(?P<ref>その|それらの)(?P<head>モンスター|カード)$")
# 「その発動」:指回本區塊最近被發動的那張卡(「罠カードが発動した時、…その発動を無効にし」,票 09)。
ACTIVATION_REF = "その発動"
_REMAINDER_RE = re.compile("^残りの(?P<head>モンスター|カード)$")
# 去除的對象:超量素材「(Xの)X素材」、計數器「(Xの)魔力カウンター」;「の」前是所屬的物件
# (`of`,このカード/そのモンスター…)。超量素材沒寫所屬卡時(「自分フィールドのX素材」的
# 「自分フィールドの」是從),所屬卡是隱含的新建超量怪獸,初始位置 = 從;字面沒有它(`text` 是 None)。
OBJECT_MATERIAL, OBJECT_COUNTER = "超量素材", "計數器"
OBJECT_CARD, OBJECT_EFFECT = "卡", "效果"
MATERIAL_WORDS = XYZ_MATERIAL_WORDS
_MATERIAL_RE = re.compile(f"^(?:(?P<owner>.+)の)?(?P<word>{'|'.join(MATERIAL_WORDS)})$")
_COUNTER_RE = re.compile("^(?:(?P<owner>.+)の)?(?P<counter>[^「」のをにがは、]*カウンター)$")
# 「選択したモンスター」:指回本區塊最近被取對象的同大類物件(舊式;新式用 そのモンスター)。
TARGET_REF_RE = re.compile(f"^{TARGET_REF}(?P<head>モンスター|カード)$")
TARGET_OF = "対象の"
# 動作回指可帶「この効果で」(この効果で除外したモンスター);字面整個記進對象線 ref(票 08)。
ACTION_REF_RE = re.compile("^(?:この効果で)?(?P<past>.+?)(?P<head>モンスター|カード)$")
# 「X」１体:只有卡名、沒有頭名詞的物件;「A」または「B」是兩個卡名的「或」(票 08)。
_NAMED_RE = re.compile(
    "^(?P<names>「[^「」]+」(?:または「[^「」]+」)*)"
    "(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")
REASON_NOT_ARCHETYPE = "「」名稱不是字段"
REASON_CLAUSE = "子句解析不出"
REASON_OBJECT = "物件解析不出"
REASON_REF = "指回的物件找不到"
# 同一格(原因、期間、數量)在句中寫了兩處:不猜哪一處算數。
REASON_TWICE = "同一格寫了兩處"
# 物件的目前位置:{"zones": [區域], "inferred": bool}(推得的或繼承自推得的才是 True)。
CurrentPosition = dict[str, object]
# 主語省略的子句向前一截要主語時,前一截句首「Xは」的三態(`BlockState.topic`):
#   沒有:本句剛開始,或前一截解析得出——主語是 `BlockState.subject`,沒有就是此卡。
#   待建:前一截解析不出、句首有「Xは」——物件還沒建,用到時才建(建不出就轉成判不了)。
#   判不了:前一截解析不出、句首沒有「Xは」,或那個物件建不出來——不退回此卡。
# 三態只由 `BlockState.start_sentence`、`hold_topic`、`lose_topic` 寫,由 `elided_subject` 讀。
TOPIC_NONE, TOPIC_PENDING, TOPIC_UNKNOWN = "沒有", "待建", "判不了"


class Topic(NamedTuple):
    """前一截句首「Xは」的狀態;短語與句子起點只在「待建」時有值。"""
    state: str
    phrase: str | None = None
    sentence_start: int | None = None


def xyz_monster_condition():
    """超量怪獸的條件式(與「Xモンスター」解析出的相同)。"""
    return {"op": "且", "args": [
        {"op": "屬性比較", "attr": "卡片子類型", "cmp": "=", "value": "超量"},
        {"op": "大類", "value": "怪獸"}]}


class BlockState:
    """一個區塊抽取時的工作狀態:物件目前位置、本區塊提過的物件(給その指回)、
    名稱表(「X」→ 名稱列)與字段對照。"""

    def __init__(self, block, card, lookups=None, self_id="o0"):
        self.block = block
        self.card = card
        self.lookups = lookups or {"card_names": set(), "archetypes": {}}
        self.names = {row["text"]: row for row in card["names"]}
        # 物件目前位置:{物件 id: {"zones": [區域], "inferred": 是不是推得的}},與 current_position 同形。
        self.positions: dict[str, CurrentPosition] = {}
        self.recent = []      # 本區塊建立或引用過的物件 id(其後者優先)
        self.targeted = []     # 被取對象的物件 id(「を選択して」「を対象として」點名的,後者優先)
        self.delayed = False  # 序列中段出現條件段之後:後面的段算延遲、不標取對象(票 08)
        self.acted = {}       # 物件 id → 本區塊對它做過的動作詞(動作回指「〜したモンスター」用;票 06)
        self.self_id = self_id  # 「このカード」指誰:內嵌效果裡綁定成被賦予效果的物件(票 06)
        self.subject = None   # 本句「Xは」的物件:後面主語省略的子句(「〜できず、〜できる」)沿用(票 09)
        self.topic = Topic(TOPIC_NONE)
        # 本句左半的宣告(「Xを選択し、」「Xを対象とし、」)點名的物件:右半省略的物件指回它(m3 票 07)。
        self.declared = None
        self.last_segment_of_action = {}
        # 本句前面的效果段剛特殊召喚出來的物件:「〜を特殊召喚し、このカードを下に重ねてX素材とする」沒寫的
        # 所屬卡是它(m3 票 09)。
        self.last_summoned = None

    def note_actions(self, seg):
        """段解析完後記下它做過的動作詞,給之後的「〜したプレイヤー」指回。"""
        for action in seg["actions"]:
            self.last_segment_of_action[action] = seg["id"]
        summoned = summoned_object(seg)
        if summoned is not None:
            self.last_summoned = summoned

    def start_sentence(self):
        """新的一句:主語、前一截的「Xは」、左半宣告的物件與剛召喚出來的物件都歸零。"""
        self.subject, self.topic, self.declared = None, Topic(TOPIC_NONE), None
        self.last_summoned = None

    def declare(self, obj_ids):
        """沒有動作詞的宣告子句(取對象宣告、選擇)點名了這些物件:同一句後面省略的物件指回它。
        點名兩個以上時省略的是哪一個判不了,不退回此卡。"""
        if len(obj_ids) == 1:
            self.declared = obj_ids[0]
        else:
            self.lose_topic()

    def declared_object(self):
        """同一句左半宣告的物件;後面的子句已經有自己的「Xは」、或有一截解析不出時不算(None)。"""
        if self.subject is None and self.topic.state == TOPIC_NONE:
            return self.declared
        return None

    def hold_topic(self, phrase, sentence_start):
        """前一截解析不出、句首有「Xは」:記下短語,物件等主語省略的子句用到時才建。"""
        self.subject, self.topic = None, Topic(TOPIC_PENDING, phrase, sentence_start)

    def lose_topic(self):
        """前一截解析不出、句首沒有「Xは」:後面主語省略的子句判不了。"""
        self.subject, self.topic = None, Topic(TOPIC_UNKNOWN)

    def elided_subject(self):
        """主語省略的子句的物件:本句「Xは」的物件,沒有就是此卡;前一截解析不出時是它的「Xは」,
        它沒有「Xは」或認不出物件就判不了(None),不退回此卡。左半是宣告(「Xを選択し、」)時是它點名的物件。"""
        if self.declared_object() is not None:
            return self.declared
        if self.subject is None and self.topic.state != TOPIC_NONE:
            if self.topic.state == TOPIC_UNKNOWN:
                return None
            self.subject, _, _ = self.object_at(self.topic.phrase, self.topic.sentence_start)
            self.topic = Topic(TOPIC_NONE if self.subject else TOPIC_UNKNOWN)
            return self.subject
        return self.subject or self.self_id

    def omit(self, offset, text, reason):
        """句中不記的字面(次數限制)進整卡的略過文本;範圍相對於來源文本。"""
        start = self.block["span"][0] + offset
        self.card["omitted"].append({"source": self.block["source"],
                                     "span": [start, start + len(text)],
                                     "text": text, "reason": reason})


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

    def recent_of(self, head, among=None, action=None):
        """本區塊最近提過的同大類物件(頭名詞 カード 任何大類都算);`among` 可改成別的候選列;
        給了 `action` 就只找本區塊被做過那個動作的(動作回指,票 06)。「このカード」不進 recent
        (その 不會指它),但動作回指可以:「このカードを特殊召喚する。〜この効果で特殊召喚した
        モンスターに装備」;它的大類看卡片屬性表。"""
        want = HEAD_CATEGORY[head]
        candidates = list(reversed(self.recent if among is None else among))
        if action is not None and among is None:
            candidates.append(self.self_id)
        for obj_id in candidates:
            if action is not None and action not in self.acted.get(obj_id, ()):
                continue
            obj = self.find(obj_id)
            category = (self._self_category() if obj["source"]["kind"] == "自己"
                        else category_of(obj["condition"]))
            if want == "卡" or category == want:
                return obj_id
        return None

    def _self_category(self):
        rows = self.card["attributes"]["category"]
        return rows[0]["value"] if rows else None

    def is_action_reference(self, phrase):
        m = ACTION_REF_RE.match(phrase)
        return bool(m and m.group("past") in ACTION_PAST.values())

    def action_reference(self, phrase):
        """動作回指短語 → 物件 id 或 None(找不到)。"""
        m = ACTION_REF_RE.match(phrase)
        action = next(a for a, past in ACTION_PAST.items() if past == m.group("past"))
        return self.recent_of(m.group("head"), action=action)

    def resolve_reference(self, phrase):
        """修飾語裡指回的物件短語(「そのモンスターのランク」「見せたモンスターと同じ」的
        その/それらの+頭名詞、動作回指)→ 物件 id 或 None;與 object_at 同一把尺。"""
        ref = REF_RE.match(phrase)
        if ref:
            return self.recent_of(ref.group("head"))
        if self.is_action_reference(phrase):
            return self.action_reference(phrase)
        return None

    def add_object(self, obj):
        self.card["objects"].append(obj)
        self.recent.append(obj["id"])
        return obj["id"]

    def offset_of(self, phrase, sentence_start):
        """短語在區塊原文的起點(從句子起點往後找;找不到就是句子起點):新建物件的 id 用它。"""
        offset = self.block["text"].find(phrase, sentence_start)
        return offset if offset >= 0 else sentence_start

    def object_at(self, phrase, sentence_start, owner_from=None):
        """物件短語 → (物件 id, 回指字面, 原因);回指字面 None = 本段首次出現。
        `owner_from` 是寫在物件前的從 (字面, 區域):超量素材沒寫所屬卡時用它建隱含的所屬卡。"""
        if _MATERIAL_RE.match(phrase) or _COUNTER_RE.match(phrase):
            return self.detach_object(phrase, sentence_start, owner_from)
        if _SELF_RE.match(phrase):
            return self.self_id, None, None
        if phrase == f"「{self.card['name_ja']}」":
            # 本卡以自己的卡名當主語(「「滅びの黒魔術師」は〜でのみ特殊召喚できる」,票 09):物件0,
            # 回指字面是卡名。
            return self.self_id, phrase, None
        ref = REF_RE.match(phrase)
        if ref:
            obj_id = self.recent_of(ref.group("head"))
            return obj_id, phrase, (None if obj_id else REASON_REF)
        if phrase == ACTIVATION_REF:
            obj_id = self.recent_of("カード", action="發動")
            return obj_id, phrase, (None if obj_id else REASON_REF)
        remainder = _REMAINDER_RE.match(phrase)
        if remainder:
            return self.remainder_object(phrase, remainder.group("head"),
                                         sentence_start)
        target_ref = TARGET_REF_RE.match(phrase)
        if target_ref:
            obj_id = self.recent_of(target_ref.group("head"), among=self.targeted)
            if obj_id is not None or not phrase.startswith(TARGET_OF):
                return obj_id, phrase, (None if obj_id else REASON_REF)
        if self.is_action_reference(phrase):
            obj_id = self.action_reference(phrase)
            return obj_id, phrase, (None if obj_id else REASON_REF)
        return self.new_object(phrase, sentence_start, {"kind": "新建"})

    def names_object(self, phrase):
        """字面像不像物件短語(只看、不建物件):以頭名詞收尾(修飾語認不認得不管),或是
        `parses_cleanly` 認得的那幾種(此卡、回指、只有卡名);超量素材、計數器看所屬的物件。"""
        detach = _MATERIAL_RE.match(phrase) or _COUNTER_RE.match(phrase)
        if detach:
            return not detach.group("owner") or self.names_object(detach.group("owner"))
        return bool(NOUN_RE.match(phrase)) or self.parses_cleanly(phrase)

    def parses_cleanly(self, phrase):
        """物件短語照現有規則認不認得全(只看、不建物件):此卡、回指、超量素材、計數器、只有卡名的
        都算認得;名詞短語要修飾語沒有「解析不出」的那截。物件切點(`object_boundary`)只在這裡
        回 False 時才去找吞進來的前文。"""
        detach = _MATERIAL_RE.match(phrase) or _COUNTER_RE.match(phrase)
        if detach:
            return not detach.group("owner") or self.parses_cleanly(detach.group("owner"))
        if (_SELF_RE.match(phrase) or phrase == f"「{self.card['name_ja']}」"
                or REF_RE.match(phrase) or phrase == ACTIVATION_REF or _REMAINDER_RE.match(phrase)
                or TARGET_REF_RE.match(phrase) or self.is_action_reference(phrase)
                or _NAMED_RE.match(phrase) or phrase in TARGETING_THIS_FORMS):
            return True
        m = NOUN_RE.match(phrase)
        if not m:
            return False
        split = split_alternatives(m.group("mods"), m.group("head"))
        mods = ([NOUN_RE.match(piece).group("mods") for piece in split[1]] if split
                else [m.group("mods")])
        return not any(atom.get("op") == "解析不出"
                       for piece in mods for atom in parse_modifiers(self, piece)[0])

    def new_object(self, phrase, sentence_start, source, initial_position=None):
        named = _NAMED_RE.match(phrase)
        m = named or NOUN_RE.match(phrase)
        if not m and phrase in TARGETING_THIS_FORMS:
            offset = self.offset_of(phrase, sentence_start)
            obj = new_object(f"{self.block['id']}.o{offset}", source, text=phrase,
                             span=(offset, offset + len(phrase)), block=self.block["id"],
                             condition=targeting_this_atom(self, phrase))
            return self.add_object(obj), None, None
        if not m:
            return None, None, REASON_OBJECT
        # 頭名詞是「效果」的(「魔法・罠・モンスター(の効果)」):物件種類 效果,條件式是誰的效果。
        is_effect = not named and m.group("head") in EFFECT_HEADS
        if named:
            # 「A」または「B」= 或(卡名∋A, 卡名∋B);任一個對不到就整個標解析不出。
            atoms, reason = [], None
            for name in re.findall("「([^「」]+)」", named.group("names")):
                atom, why = self.name_atom("卡名", name)
                atoms.append(atom)
                reason = reason or why
            if None in atoms:
                condition = {"op": "解析不出", "text": phrase}
            else:
                condition = atoms[0] if len(atoms) == 1 else {"op": "或", "args": atoms}
        elif split_alternatives(m.group("mods"), m.group("head")):
            atoms, reason, alternatives = [], None, []
            form, pieces = split_alternatives(m.group("mods"), m.group("head"))
            for piece in pieces:
                piece_m = NOUN_RE.match(piece)
                piece_atoms, why = parse_modifiers(self, piece_m.group("mods"))
                alternatives.append(noun_condition(piece_atoms, piece_m.group("head")))
                atoms.extend(piece_atoms)
                reason = reason or why
            condition = {"op": "或", "args": alternatives, "form": form}
        else:
            atoms, reason = parse_modifiers(self, m.group("mods"))
            condition = noun_condition(atoms, m.group("head"))
            # 名詞修飾的位置(「墓地のモンスター」「EXデッキの「No.」Xモンスター」)就是
            # 物件的初始位置:後續段「從」沒寫時由此繼承(spec「初始位置」;票 06)。
            if initial_position is None:
                located = [z for a in atoms if a.get("op") == "位置" for z in a["zones"]]
                initial_position = [dict(z) for z in located] or None
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", source,
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=condition,
                         count=parse_count(m), initial_position=initial_position,
                         kind=OBJECT_EFFECT if is_effect else OBJECT_CARD)
        if reason:
            obj["unparsed"] = unparsed(reason)
        return self.add_object(obj), None, None

    def detach_object(self, phrase, sentence_start, owner_from=None):
        """超量素材或計數器→ (物件 id, None, 原因):`of` 是所屬的物件(有寫才有,回指字面記
        `of_ref`);超量素材沒寫所屬卡要靠 `owner_from` 建隱含的所屬卡,沒有就解析不出;
        計數器另帶種類名 `counter`。這幾個鍵有值才寫(接在工廠的格後面)。"""
        material = _MATERIAL_RE.match(phrase)
        m = material or _COUNTER_RE.match(phrase)
        of, of_ref = None, None
        if m.group("owner"):
            of, of_ref, reason = self.object_at(m.group("owner"), sentence_start)
            if of is None:
                return None, None, reason
        elif material:
            if owner_from is None:
                return None, None, REASON_OBJECT
            of = self.implicit_owner(*owner_from, sentence_start)
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"],
                         kind=OBJECT_MATERIAL if material else OBJECT_COUNTER)
        if not material:
            obj["counter"] = m.group("counter")
        if of is not None:
            obj["of"] = of
        if of_ref is not None:
            obj["of_ref"] = of_ref
        return self.add_object(obj), None, None

    def held_material(self, holder_phrase, material_phrase, sentence_start):
        """「Xが「Y」をX素材としている」的超量素材物件(m3 票 09)→ 物件 id,X 或 Y 認不出物件回 None。
        Y 照一般的名詞短語解析,解出的條件式與數量留在物件上;物件種類改成超量素材、所屬 `of` = X
        (X 是回指時字面記 `of_ref`)。超量素材物件可以帶條件式只有這一種寫法,去除的對象(`detach_object`)沒有。"""
        holder_id, holder_ref, _ = self.object_at(holder_phrase, sentence_start)
        if holder_id is None:
            return None
        material_id, _, _ = self.new_object(material_phrase, sentence_start, {"kind": "新建"})
        if material_id is None:
            return None
        material = self.find(material_id)
        material["kind"] = OBJECT_MATERIAL
        material["of"] = holder_id
        if holder_ref is not None:
            material["of_ref"] = holder_ref
        return material_id

    def implicit_owner(self, from_phrase, zones, sentence_start):
        """超量素材隱含的所屬卡:新建的超量怪獸,初始位置 = 寫在物件前的從;id 取從的字面位置。"""
        offset = self.offset_of(from_phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         block=self.block["id"], condition=xyz_monster_condition(),
                         initial_position=[dict(z) for z in zones])
        self.card["objects"].append(obj)
        return obj["id"]

    def zone_object(self, phrase, sentence_start):
        """區域當物件(「自分の手札を１枚選んで捨てる」):新建、沒有條件的卡(條件同頭名詞
        カード),初始位置由呼叫端以對象線的「從」寫入;與「手札からカードを１枚捨てる」同一結構。"""
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}", {"kind": "新建"},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=category_condition("カード"))
        return self.add_object(obj)

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
        offset = self.offset_of(phrase, sentence_start)
        obj = new_object(f"{self.block['id']}.o{offset}",
                         {"kind": "剩餘", "of": container["id"], "minus": subset["id"]},
                         text=phrase, span=(offset, offset + len(phrase)),
                         block=self.block["id"], condition=condition,
                         initial_position=current["zones"] if current else None)
        return self.add_object(obj), None, None


def summoned_object(seg):
    """效果段做了召喚、只有一條被召喚的線時,被叫出來的那個物件;其餘回 None。
    抽取(`BlockState.last_summoned`)與模板(沒寫所屬卡的「下に重ねてX素材とする」)共用這一把尺。"""
    if (seg["kind"] != "效果" or seg["polarity"] != "做" or seg["unparsed"] or not seg["actions"]
            or not all(is_summon(a) for a in seg["actions"]) or len(seg["lines"]) != 1
            or seg["lines"][0]["role"] != "被召喚"):
        return None
    return seg["lines"][0]["object"]


def update_positions(seg, state):
    """位置自動規則:極性「做」的條件/代價/效果/召喚手續段,把「到」寫回目前位置。"""
    if seg["polarity"] != "做" or seg["kind"] not in ("條件", "代價", "效果",
                                                      "召喚手續"):
        return
    for line in seg["lines"]:
        if line["to"]:
            state.positions[line["object"]] = {
                "zones": line["to"]["zones"], "inferred": line["to"]["inferred"]}


def segment_at(state, kind, start, end):
    text = state.block["text"]
    return new_segment(f"{state.block['id']}.s{start}", kind, (start, end),
                       text[start:end])


@dataclass
class ClauseContext:
    """一個子句填格時共用的參數:要填的段、區塊狀態、子句所在句子的起點(新建物件的 id、略過文本的
    範圍從它起算)、連用形串接(同時)的前一段的時機。各句型的 `fill_clause(ctx, 子句)` 都吃這一包。"""
    seg: dict
    state: BlockState
    sentence_start: int
    inherited_timing: dict | None = None
    # 句型的回話:這個子句其實該在這個位置(相對於子句)切成兩段——左半已標解析不出,右半請呼叫端另成一段
    # (`material_summon`:「Xを融合素材とし、〜」的 X 解不出時)。只有效果子句的串接(`_cost_and_effect`)理會。
    split_at: int | None = None

    @property
    def kind(self):
        """填格當下段的類別(條件/代價/效果);召喚條件區塊的召喚手續、限制是整句解析完才改寫的。"""
        return self.seg["kind"]

    def inherit_timing(self):
        """沒寫時機的段:連用形串接(同時)的後一段與前一段同一時點(時機照抄、字面只在前一段);
        延遲序列裡的效果段是隱含的延遲。"""
        if self.inherited_timing:
            self.seg["timing"] = {k: v for k, v in self.inherited_timing.items()
                                  if k not in ("text", "placement")}
        elif self.state.delayed and self.kind == "效果":
            self.seg["timing"] = implicit_delay()
