# -*- coding: utf-8 -*-
"""[[動作對象]]判定(.scratch/action-patient;named-queries 票 04 改讀[[論元片語]]):一句效果句的動作框架
→ 每個框架動到的是不是此卡本身。

接在框架抽取之後、由類別匯出(export_categories.py)呼叫;框架抽取的受事者取法不改,判定在它的結果上
加規則。值是 此卡(SELF)、非此卡(NONSELF),或 None(皆非:兩種模式都不中)。

**讀什麼**(票 04):判定讀框架線已結構化的值,不再自己拆字面——受事者的片語段(frame["phrases"][欄]
.segments:中心詞、中心詞類、指示詞旗標、玩家、區域、修飾語類、數量類)、結構化區域(frame["regions"])、
回指欄(frame["anaphora"])。回指欄的目標字面與事件主語只有字面,交給片語模組同一套切段(phrases.split/
segment,經 frames.context() 的分詞輔助)得到段;目標的所在字面交給 regions.zones_of。本模組沒有正則式。
表的來源:中心詞類/修飾語類/動作對象值在 closed_values、量詞(枚/体)與 全部/指示詞格 在 phrases、玩家拼法在 places,
與回指共用的小表(指示詞起頭、此卡、事件詞、素材、元々、不是回指的名詞、關係詞、via)在 referent.py——這些都只有
那一份;這裡只有卡面參數的日文寫法 → 值域正典的碼(ADR-0008)與判定自己的小表(この効果、此卡的附屬卡、「和此卡」
的關係名詞、指示代名詞的中心詞、發動位置)。

受事者依態取:他動(與沒判態的)取對象,自動/受身取主語、沒有時取主題;對象空著而主題
(含句內延續的主題)指名此卡時,主題就是受事者,不分動作。

- 此卡:受事者指名此卡(self_rule,比段):最後一段中心詞是 カード 且字面以 このカード 收尾;屬性段的最後一個
  修飾語是 このカード(元々 不算);並列裡有一段是此卡;修飾語含 このカードを含む;各段都是 この効果/この発動。
- 非此卡:受事者是卡、不指名此卡,而且是選擇類(任一段有數量且數量類不是 全部,或指示詞)、修飾語含
  このカード以外/他(の)、此卡的附屬卡(第一個修飾語是 このカード 而接著的是 X素材/装備/リンク先),或主人不是
  此卡的效果、發動、攻擊(事件類中心詞)。屬性(攻撃力、レベル…)跟著它的主人判:主人是中心詞前的字面,再切一次段。
- 皆非:受事者不是卡(中心詞類 非卡)、表外(玩家/位置/表示形式/其他 類),以及會包含此卡的全部類。

受事者是指示詞(段的旗標)時讀框架的[[回指]],沿用目標的判定:目標含此卡 → 此卡;このカード以外、他の → 非此卡;
目標或指示詞自己帶數量 → 非此卡;無數量的群體 → 全部類比對(區域、玩家用回指欄,事件主語是相手算對手,
事件主語是此卡時目標確定是別張,發動位置用受事者那個框架當時的位置)。效果類(その発動、その効果、その攻撃)
事件主人字面是此卡才算此卡,其餘非此卡。回指留空 → 非此卡。旗標假而段首仍是指示詞(そのモンスターと同じ
種族のモンスター),或指示詞綁的是 他/時/中/種族 這類不是卡的詞(その他の、その種族の),指示詞只修飾另一張卡:
受事者照自己的段判。字面指名此卡的規則(そのカードとこのカード)優先於回指。

全部類(沒有數量的群體)依**發動位置**判:一句效果句內依序取 條件/代價寫明的此卡區域、條件位觸發事件裡此卡
的去處、處理中此卡自己移動的起點,都沒有就是場上(此卡在我方)。此卡在代價或處理中自己移動之後,後面的框架
改看移動的目的(手札から特殊召喚 之後 手札全部 不含此卡)。群體的區域(結構化所在、沒有時來源;都沒有時
段自己的玩家/區域)含發動位置,而且玩家、卡種(中心詞字面尾 モンスター/魔法/罠)、種族、屬性、字段、卡片子類型
(修飾語類,或中心詞字面裡的 効果モンスター/速攻魔法)、數值(修飾語的欄位/比較/數字)全都對得上此卡的卡面參數,
才算會包含此卡;比不了的(其他類與表示形式類修飾語、認不出的中心詞、含區域判不出)一律視為對得上,任一條件
對不上就判非此卡。か/と/・ 並列的段是替代項,任一段全對得上就算包含。
"""
from collections import namedtuple
from functools import lru_cache
import os
import sys
import unicodedata

from anaphora import INTRANSITIVE
from closed_values import (HEAD_ATTRIBUTE, HEAD_CARD, HEAD_DEMONSTRATIVE, HEAD_NON_CARD, MOD_ARCHETYPE, MOD_ATTRIBUTE,
                           MOD_NUMERIC, MOD_PLAYER, MOD_RACE, MOD_SUBTYPE, MOD_ZONE, OTHER, PATIENT_MODES, PLACE_PLAYER,
                           REGION_GOAL, REGION_PLACE, REGION_SOURCE)
from constraints import KIND_ACTION
import frames
from frames import POS_COND, POS_COST, POS_EFFECT
import phrases
from phrases import CARD_COUNTERS, Q_ALL
import places
from referent import (CARD_SUFFIX, EVENT_WORDS, MATERIAL, NON_REFERENCE_NOUNS, ORIGINAL, PRONOUNS, RELATIONAL_WORDS,
                      TARGETED_PREFIXES, THIS_CARD, VIA_EVENT, WITHIN, clean, opener_of)
import regions

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "..", "script", "web"))
import vocab  # noqa: E402

SELF, NONSELF = PATIENT_MODES
NEITHER = "皆非"       # 統計的鍵;Verdict.mode 以 None 表示

# 判定的理由(建置報告依它分項計數)
WHY_PATIENT = "受事者是此卡"
WHY_TOPIC = "主題是此卡"
WHY_ATTRIBUTE = "此卡的屬性"
WHY_LISTED = "並列含此卡"
WHY_INCLUDING = "包含此卡"
WHY_OTHER_THAN_SELF = "此卡以外"
WHY_ATTACHED = "此卡的附屬卡"
WHY_SELECTED = "選擇類"
WHY_OTHERS_EFFECT = "主人不是此卡的效果"
WHY_THIS_EFFECT = "この効果"
WHY_THIS_NAME = "このカード名の效果"
WHY_ALL_INCLUDES = "全部類含此卡"
WHY_ALL_NO_ZONE = "全部類區域不明"
WHY_ALL_ZONE = "全部類區域對不上"
WHY_ALL_PLAYER = "全部類玩家對不上"
WHY_ALL_KIND = "全部類卡種對不上"
WHY_ALL_RACE = "全部類種族對不上"
WHY_ALL_ATTR = "全部類屬性對不上"
WHY_ALL_ARCHETYPE = "全部類字段對不上"
WHY_ALL_SUBTYPE = "全部類子類型對不上"
WHY_ALL_NUMERIC = "全部類數值對不上"
WHY_ALL_UNCOMPARABLE = "全部類比不了"
WHY_NO_OWNER = "屬性沒有主人"
WHY_NOT_CARD = "不是卡"
WHY_UNKNOWN = "表外"
WHY_NONE = "沒有受事者"
# 回指(全部類的結果另以「回指」為前綴記,例 回指全部類含此卡)
WHY_ANAPHORA_SELECTED = "回指選擇類"
WHY_ANAPHORA_SELF = "回指含此卡"
WHY_ANAPHORA_OTHER_THAN_SELF = "回指此卡以外"
WHY_ANAPHORA_ATTACHED = "回指此卡的附屬卡"
WHY_ANAPHORA_SELF_AGENT = "回指此卡是事件主語"
WHY_ANAPHORA_OWNER_SELF = "回指事件主人是此卡"
WHY_ANAPHORA_OWNER_OTHER = "回指事件主人不是此卡"
WHY_ANAPHORA_BLANK = "回指留空"
WHY_MODIFIER_SELECTED = "修飾語選擇類"
ANAPHORA_PREFIX = "回指"
MODIFIER_PREFIX = "修飾語"
# 全部類的判定(用到發動位置的框架)
_WHY_ALL_CLASS = {WHY_ALL_INCLUDES, WHY_ALL_NO_ZONE, WHY_ALL_ZONE, WHY_ALL_PLAYER, WHY_ALL_KIND,
                  WHY_ALL_RACE, WHY_ALL_ATTR, WHY_ALL_ARCHETYPE, WHY_ALL_SUBTYPE, WHY_ALL_NUMERIC,
                  WHY_ALL_UNCOMPARABLE}
# 動作本身就沒有卡片受事者:デッキに戻した数＋１枚をドローする 的「１枚」是張數
_NOT_CARD_ACTIONS = ("ドロー",)

OPPONENT = PLACE_PLAYER[places.PLAYER_OPP]
# 判定自己的小表(2026-11-01 規格 2 票 04 裁定改讀片語時從正則式收成表;來源 action-patient 的判定規則):
# この効果、この効果の発動、この発動とこの効果:主人是此卡(この効果で特殊召喚したモンスターの効果 主人是別張)
THIS_EFFECT = ("この効果", "この発動")
THIS_EFFECT_FIRST = THIS_EFFECT + ("この効果の発動", "この発動の発動")
THIS_EFFECT_REST = THIS_EFFECT + ("効果", "発動")
# 此卡的附屬卡:另一張實體卡(このカードのX素材、このカードの装備モンスター、リンク先);指示詞綁的卡的附屬卡
# (そのモンスターのX素材、装備カード、攻撃対象)不是回指那張卡本身
ATTACHED_TO_SELF = ("X素材", "装備", "リンク先")
ATTACHED_TO_OTHER = ("X素材", "装備", "攻撃対象")
# このカードと|リンク状態のモンスター、このカードと|戦闘を行うモンスター:片語在 と 後切了段,但這個 と 是「和此卡」,
# 後一段以這些關係名詞起頭時不是並列含此卡
WITH_THIS_CARD = ("リンク状態", "相互", "戦闘")
# 指示代名詞自己就是被指的卡(それ、それら、その内の…);其餘指示詞類中心詞(いずれか、残り)照卡判
REFERENCE_HEADS = PRONOUNS + (WITHIN,)
PAREN_OPEN, PAREN_CLOSE = "（", "）"
# 中心詞類 → 判定用的粗類
CARD, EFFECT, VALUE, NOT_CARD, UNKNOWN = "card", "effect", "value", "not_card", "unknown"
# 指示詞在段裡扮演的角色
REFERENCE, MODIFIER = "reference", "modifier"


# 發動位置的來源(建置報告分項)
LAUNCH_WRITTEN = "寫明"
LAUNCH_TRIGGER = "觸發"
LAUNCH_MOVE = "自己移動"
LAUNCH_DEFAULT = "預設場上"
LAUNCH_AFTER_MOVE = "移動後"
FIELD = "場上"
PENDULUM_ZONE = "靈擺區"
OFF_FIELD = "場外"           # 去處不明的「離開場上」:不在場上,也不知道在哪
STATE_ACTIONS = ("存在", "ある", "いる")
# 觸發事件沒寫去處、但一定是離開場上的動作
LEAVE_FIELD_ACTIONS = ("破壊", "リリース")

# 發動位置:此卡可能所在的區域集合與判定來源
Launch = namedtuple("Launch", "zones source")


def _source_bits(domain):
    """值域正典的 碼 → 來源位元(ADR-0008:位元只在 script/web/vocab.py 宣告一次)。"""
    return {e["code"]: e["src"] for e in vocab.DOMAINS[domain]["entries"]}


def _bits_by_word(words, domain, exhaustive=False):
    """卡文的日文寫法 → 碼 的對照 + 值域正典 → 日文寫法 → 位元。exhaustive 的值域多一個成員
    而這裡沒有寫法時就吵:漏了的話那個條件會安靜地比不到(ADR-0008 的無聲失效)。"""
    bits = _source_bits(domain)
    missing = set(bits) - set(words.values()) if exhaustive else set()
    if missing:
        raise ValueError("%s 有值域成員沒有日文寫法:%s" % (domain, sorted(missing)))
    return {word: bits[code] for word, code in words.items()}


# 卡種(卡片總表 type 位元):中心詞字面尾
_KIND_BITS = _bits_by_word({"モンスター": "m", "魔法": "s", "罠": "t"}, vocab.CAT, exhaustive=True)
# 卡面參數:卡文的日文寫法 → 值域正典的碼(位元由正典來)
_RACE_BITS = _bits_by_word(
    {"戦士族": "warrior", "魔法使い族": "spellcaster", "天使族": "fairy", "悪魔族": "fiend",
     "アンデット族": "zombie", "機械族": "machine", "水族": "aqua", "炎族": "pyro", "岩石族": "rock",
     "鳥獣族": "winged_beast", "植物族": "plant", "昆虫族": "insect", "雷族": "thunder",
     "ドラゴン族": "dragon", "獣族": "beast", "獣戦士族": "beast_warrior", "恐竜族": "dinosaur",
     "魚族": "fish", "海竜族": "sea_serpent", "爬虫類族": "reptile", "サイキック族": "psychic",
     "幻神獣族": "divine_beast", "創造神族": "creator_god", "幻竜族": "wyrm",
     "サイバース族": "cyberse", "幻想魔族": "illusion"}, vocab.RACE, exhaustive=True)
_ATTR_BITS = _bits_by_word({"地": "earth", "水": "water", "炎": "fire", "風": "wind", "光": "light",
                            "闇": "dark", "神": "divine"}, vocab.ATTR, exhaustive=True)
_MONSTER_TYPE_BITS = _bits_by_word(
    {"融合": "fusion", "シンクロ": "synchro", "S": "synchro", "エクシーズ": "xyz", "X": "xyz",
     "リンク": "link", "L": "link", "儀式": "ritual", "ペンデュラム": "pendulum", "P": "pendulum",
     "通常": "normal", "効果": "effect", "トゥーン": "toon", "スピリット": "spirit", "ユニオン": "union",
     "デュアル": "dual", "リバース": "flip", "チューナー": "tuner"}, vocab.SUB["m"])
_SPELL_TRAP_TYPE_BITS = {
    "魔法": _bits_by_word({"速攻": "quick", "永続": "continuous", "装備": "equip",
                           "フィールド": "field", "儀式": "ritual"}, vocab.SUB["s"]),
    "罠": _bits_by_word({"永続": "continuous", "カウンター": "counter"}, vocab.SUB["t"])}
NORMAL = "通常"
XYZ_BIT, LINK_BIT = _MONSTER_TYPE_BITS["X"], _MONSTER_TYPE_BITS["L"]
TUNER_BIT = _MONSTER_TYPE_BITS["チューナー"]
# 數值條件比得了的欄位(レベル/ランク/リンク 共用總表的 level 欄,依卡片子類型分)
NUMERIC_FIELDS = ("レベル", "ランク", "リンク", "攻撃力", "守備力")
# 卡面能比的中心詞(卡種詞之外):任何卡種;X素材 這類不是卡面能比的
ANY_KIND_HEADS = ("カード", "トークン")


def _nfkc(text):
    return unicodedata.normalize("NFKC", text or "")


def _unelide(text):
    """分詞的省略寫法 水(族)、通常(モンスター) → 認得的詞;補全的詞尾只在括號裡。"""
    if "(" not in text:
        return text
    head, _, rest = text.partition("(")
    return head + rest.partition(")")[2]


# ── 片語段 ──
_CTX = None


def _ctx():
    global _CTX
    if _CTX is None:
        _CTX = frames.context()
    return _CTX


@lru_cache(maxsize=None)
def segments_of(text):
    """一段字面(回指欄的目標、事件主語、屬性的主人)→ 片語段:和片語模組切受事者同一套(分詞 → 切段 → 定段)。"""
    text = clean(text)
    if not text:
        return ()
    run = _ctx().tokenize(text)
    if "、" not in text:
        run = [t for t in run if t != "、"]
    return tuple(phrases.segment(_ctx(), chunk) for chunk in phrases.split(_ctx(), run))


def _segments(frame, key):
    """框架某欄的片語段(框架沒有片語時把字面自己切段)。片語讀的是切區域前的字面,欄位是切後的:切掉的開頭含指示詞(その墓地の|モンスター)、
    或切掉之後才以指示詞起頭(墓地の|そのモンスター2体)時,段的指示詞旗標說的不是這一欄,把切後的字面重新切段
    (取自子句的數量帶過去);其餘照用片語的段。"""
    phrase = (frame.get("phrases") or {}).get(key)
    if not phrase:
        # 沒跑過片語步驟的框架(手寫的測試框架):字面自己切段
        return segments_of(frame.get(key)) if frame.get(key) else ()
    segments = tuple(phrase["segments"])
    field, raw = clean(phrase["text"]), segments[0]["text"]
    if raw != field and not field.startswith(raw):
        k = next((k for k in range(1, len(raw)) if field.startswith(raw[k:])), None)
        if k is not None and (opener_of(raw[:k]) or opener_of(raw[k:])):
            found = segments_of(field)
            last = segments[-1]["quantity"]
            if found and last and last["from_clause"] and not found[-1]["quantity"]:
                found = found[:-1] + (dict(found[-1], quantity=last),)
            return found
    return segments


def _is_this_card(seg):
    return seg["head_kind"] == HEAD_CARD and seg["text"].endswith(THIS_CARD)


def _is_clause(text):
    """字面是定語子句(破壊された、効果を発動した):有述語格。"""
    return any(_ctx().is_predicate(t) for t in _ctx().tokenize(text))


# ── 區域 ──
def _region_pairs(frame, *keys):
    """框架的來源/目的/所在:第一個有字面的欄的結構化值 [(玩家, 區域)…];字面認不出區域時 []。"""
    found = frame.get("regions") or {}
    for key in keys:
        if frame.get(key):
            return [tuple(pair) for pair in found.get(key, ())]
    return []


def _segment_zones(segments):
    """段自己帶的玩家/區域(手札を全て捨てる 的受事者本身是區域;框架沒切出所在時段開頭的區域)。"""
    out = []
    for seg in segments:
        for zone in seg["zones"]:
            pair = (seg["player"], zone)
            if pair not in out:
                out.append(pair)
    return out


def _names_this_card(segments):
    """段把此卡本身算進去:以此卡收尾、並列含此卡、包含此卡(此卡的屬性不算移動此卡)。"""
    return self_rule(segments) in (WHY_PATIENT, WHY_LISTED, WHY_INCLUDING)


def _trigger_zones(frame):
    """條件位以此卡為主語的事件 → 此卡的去處。此卡是施事者(對象另有其物、破壊した)時此卡
    沒有移動。"""
    if frame.get("object"):
        return []
    zones = _region_pairs(frame, REGION_GOAL)
    if zones:
        return zones
    leaves = frame.get("action") == "離れる" or FIELD in {z for _, z in _region_pairs(frame, REGION_SOURCE)}
    if leaves or (frame.get("action") in LEAVE_FIELD_ACTIONS and frame.get("voice") == "受身"):
        return [(None, OFF_FIELD)]
    return []


def launch(frames_, section="main"):
    """一句效果句的框架 → Launch;靈擺段落的效果預設在靈擺區。"""
    written, trigger, move = [], [], []
    for fr in frames_:
        if fr.get("kind") != KIND_ACTION:
            continue
        position = fr.get("position")
        agent = _segments(fr, "subject") if fr.get("subject") else _segments(fr, "topic")
        if position == POS_COND and _names_this_card(agent):
            if fr.get("action") in STATE_ACTIONS:
                written = written or _region_pairs(fr, REGION_GOAL, REGION_PLACE)
            else:
                trigger = trigger or _trigger_zones(fr)
        elif position == POS_COST and _names_this_card(_segments(fr, "object")):
            written = written or _region_pairs(fr, REGION_SOURCE, REGION_PLACE)
        elif position == POS_EFFECT and _names_this_card(patient(fr)[1]):
            move = move or _region_pairs(fr, REGION_SOURCE)
    for found, source in ((written, LAUNCH_WRITTEN), (trigger, LAUNCH_TRIGGER),
                          (move, LAUNCH_MOVE)):
        if found:
            return Launch({zone for _, zone in found}, source)
    return Launch({PENDULUM_ZONE} if section == "pendulum" else {FIELD}, LAUNCH_DEFAULT)


def _self_move_zones(frame):
    """代價或處理中此卡自己移動 → 去處;不是移動時 []。否定的不算(戦闘では破壊されない),
    沒有去處的 破壊/リリース 當離開場上。"""
    if (frame.get("position") not in (POS_COST, POS_EFFECT) or frame.get("polarity") == "否定"
            or not _names_this_card(patient(frame)[1])):
        return []
    zones = _region_pairs(frame, REGION_GOAL)
    if zones:
        return zones
    return [(None, OFF_FIELD)] if frame.get("action") in LEAVE_FIELD_ACTIONS else []


def _positions(frames_, launched):
    """一句效果句 → 與框架對齊的 Launch:此卡自己移動之前是發動位置,之後看目的。● 選項是
    替代關係,移動只影響共同部分與同一選項的框架。"""
    moved = {}
    out = []
    for fr in frames_:
        option = fr.get("option")
        latest = moved.get(option) or moved.get(None)
        out.append(latest or launched)
        if fr.get("kind") == KIND_ACTION:
            zones = _self_move_zones(fr)
            if zones:
                moved[option] = Launch({zone for _, zone in zones}, LAUNCH_AFTER_MOVE)
    return out


# ── 全部類的卡面比對 ──
def _head_face(head):
    """中心詞字面 → (卡種詞或 None, 字面裡的子類型前綴, 比不比得了)。モンスターカード/魔法(カード) 去 カード 再看尾;
    効果モンスター、速攻魔法 的子類型在詞裡;カード/トークン/「卡名」/區域 是任何卡種;X素材 這類比不了。"""
    core = _unelide(head or "")
    if core.endswith(CARD_SUFFIX) and core != CARD_SUFFIX:
        core = core[:-len(CARD_SUFFIX)]
    for word in _KIND_BITS:
        if core.endswith(word):
            return word, core[:-len(word)], True
    if core == "チューナー":
        return "モンスター", core, True
    comparable = core in ANY_KIND_HEADS or (core.startswith("「") and core.endswith("」")) \
        or not core.endswith(MATERIAL)
    return None, "", comparable


def _subtype_block(kind, names, face):
    """子類型條件:群體寫了卻對不上 → True;名字不是這個卡種的子類型 → None(比不了)。"""
    types = face["type"]
    if not names:
        return False
    if kind == "モンスター":
        if any(name not in _MONSTER_TYPE_BITS for name in names):
            return None
        if "チューナー" in names and types & TUNER_BIT:
            return False
        others = [n for n in names if n != "チューナー"]
        return not (others and types & _KIND_BITS[kind] and any(types & _MONSTER_TYPE_BITS[n] for n in others))
    bits = _SPELL_TRAP_TYPE_BITS[kind]
    if any(name != NORMAL and name not in bits for name in names):
        return None
    if not types & _KIND_BITS[kind]:
        return False
    for name in names:
        if name == NORMAL and not any(types & bit for bit in bits.values()):
            return False
        if bits.get(name, 0) & types:
            return False
    return True


def _numeric_block(mod, face):
    """數值條件:對不上 → True;攻守未知(?)比不了,不擋;欄位不是能比的五個 → None(比不了)。"""
    field = mod.get("field")
    if field not in NUMERIC_FIELDS:
        return None
    types = face["type"]
    if field == "レベル":
        value = None if types & (XYZ_BIT | LINK_BIT) else face.get("level")
    elif field == "ランク":
        value = face.get("level") if types & XYZ_BIT else None
    elif field == "リンク":
        value = face.get("level") if types & LINK_BIT else None
    else:
        value = face.get("atk" if field == "攻撃力" else "def")
        if value is not None and value < 0:
            return False
    if value is None:
        return True
    numbers = mod.get("numbers") or ([mod["number"]] if mod.get("number") is not None else [])
    if not numbers:
        return None
    op = mod.get("compare")
    if op is None:
        return value not in numbers
    wanted = numbers[0]
    return op == "以上" and value < wanted or op == "以下" and value > wanted or op == "未満" and value >= wanted


def _segment_blocker(seg, face):
    """一個替代項(段)對此卡卡面參數 → (第一個擋下的條件(理由)或 None, 有沒有比不了的定語)。"""
    kind, prefix, comparable = _head_face(seg["head"])
    uncomparable = not comparable
    races, attrs, quoted, subtypes, numerics = [], [], [], [], []
    mods = seg["modifiers"]
    for i, mod in enumerate(mods):
        text, mkind = _unelide(mod["text"]), mod["kind"]
        if mkind == MOD_SUBTYPE and i + 1 < len(mods) and mods[i + 1]["text"].startswith(MATERIAL):
            uncomparable = True                      # 融合素材モンスター:融合 說的是素材法,不是子類型
        elif mkind == MOD_RACE and text in _RACE_BITS:
            races.append(text)
        elif mkind == MOD_ATTRIBUTE and text[:1] in _ATTR_BITS:
            attrs.append(text[:1])
        elif mkind == MOD_ARCHETYPE:
            quoted.append(text[1:-1])
        elif mkind == MOD_SUBTYPE:
            subtypes.append(text)
        elif mkind == MOD_NUMERIC:
            numerics.append(mod)
        elif mkind not in (MOD_ZONE, MOD_PLAYER):
            uncomparable = True
    if prefix:
        subtypes += prefix.split("・")
    head = seg["head"] or ""
    if head.startswith("「") and head.endswith("」"):
        quoted.append(head[1:-1])
    if kind is not None and not face["type"] & _KIND_BITS[kind]:
        return WHY_ALL_KIND, uncomparable
    if races and not any(face["race"] & _RACE_BITS[r] for r in races):
        return WHY_ALL_RACE, uncomparable
    if attrs and not any(face["attribute"] & _ATTR_BITS[a] for a in attrs):
        return WHY_ALL_ATTR, uncomparable
    if quoted and not any(_nfkc(q) in _nfkc(face.get("name_ja")) for q in quoted):
        return WHY_ALL_ARCHETYPE, uncomparable
    blocked = _subtype_block(kind, subtypes, face) if kind else (None if subtypes else False)
    if blocked is None:
        uncomparable = True
    elif blocked:
        return WHY_ALL_SUBTYPE, uncomparable
    for mod in numerics:
        blocked = _numeric_block(mod, face)
        if blocked is None:
            uncomparable = True
        elif blocked:
            return WHY_ALL_NUMERIC, uncomparable
    return None, uncomparable


def _compare_face(segments, face):
    """群體的段 × 此卡卡面參數 → (擋下的理由或 None, 有沒有比不了的定語);任一段全對得上就算包含。
    替代項只算中心詞是卡的段(レベル・ランクを持つ融合・Xモンスター 切出的 屬性 段不是替代項)。"""
    cards = [seg for seg in segments if head_class(seg) == CARD] or segments
    results = [_segment_blocker(seg, face) for seg in cards]
    uncomparable = any(u for _, u in results)
    blockers = [b for b, _ in results]
    if not blockers or None in blockers:
        return None, uncomparable
    return blockers[0], uncomparable


def _all_class(segments, frame_zones, launched, face):
    """全部類:(群體的段, 框架的結構化所在/來源, 發動位置, 卡面)→ (值, 理由)。"""
    zones = frame_zones or _segment_zones(segments)
    possible = launched.zones
    # 靈擺區在場上:群體寫場上時含靈擺區的此卡
    reachable = [(player, zone) for player, zone in zones
                 if zone in possible or (OFF_FIELD in possible and zone != FIELD)
                 or (zone == FIELD and PENDULUM_ZONE in possible)]
    if zones and not reachable:
        return NONSELF, WHY_ALL_ZONE
    if reachable and all(player == OPPONENT for player, _ in reachable):
        return NONSELF, WHY_ALL_PLAYER
    uncomparable = False
    if face is not None:
        blocker, uncomparable = _compare_face(segments, face)
        if blocker:
            return NONSELF, blocker
    if not zones:
        return None, WHY_ALL_NO_ZONE
    return None, WHY_ALL_UNCOMPARABLE if uncomparable else WHY_ALL_INCLUDES


# ── 受事者 ──
def patient(frame):
    """→ (受事者字面, 受事者的段, 是否由主題規則取得);沒有受事者時字面是空字串、段是空的。"""
    if frame.get("voice") in INTRANSITIVE:
        key = "subject" if frame.get("subject") else "topic"
        return clean(frame.get(key)), _segments(frame, key), False
    obj = clean(frame.get("object"))
    if obj:
        return obj, _segments(frame, "object"), False
    topic = _segments(frame, "topic")
    if self_rule(topic):
        return clean(frame.get("topic")), topic, True
    return "", (), False


def _attribute_run(segments):
    """字面尾端的屬性段:最後一段是屬性,往前收光禿的屬性段(並列的 攻撃力・守備力)→ 起點 k;不是屬性收尾時 None。"""
    k = len(segments) - 1
    if segments[k]["head_kind"] != HEAD_ATTRIBUTE:
        return None
    while k > 0 and segments[k]["head_kind"] == HEAD_ATTRIBUTE and not segments[k]["modifiers"]:
        k -= 1
    return k if segments[k]["head_kind"] == HEAD_ATTRIBUTE else k + 1


def _attribute_of_self(segments):
    """このカードの攻撃力(・守備力)、この効果で特殊召喚したこのカードの元々の攻撃力、そのモンスターとこのカードのレベル:
    尾端屬性段的最後一個修飾語(元々 不算)以 このカード 收尾。"""
    k = _attribute_run(segments)
    if k is None:
        return False
    mods = [m["text"] for m in segments[k]["modifiers"]]
    while mods and mods[-1] == ORIGINAL:
        mods.pop()
    return bool(mods) and mods[-1].endswith(THIS_CARD)


def _this_effect(segments):
    return segments[0]["text"] in THIS_EFFECT_FIRST and all(seg["text"] in THIS_EFFECT_REST for seg in segments[1:])


def _listed_in_modifier(mod):
    """このカード及びこのカードと同じ縦列のモンスター:並列詞在定語子句裡,片語沒切段,此卡留在修飾語字面開頭——
    此卡後面是 と 以外的並列詞(このカードと戦闘を行う、このカードとリンク状態の 的 と 是「和此卡」,不是並列)。"""
    if not mod["text"].startswith(THIS_CARD):
        return False
    run = _ctx().tokenize(mod["text"])
    return len(run) > 2 and _ctx().surface(run[0]) == THIS_CARD and run[1] != "p:と" and _ctx().coordinates(run, 1)


def self_rule(segments):
    """受事者的段指名此卡時回命中的規則(理由),否則 None。"""
    if not segments:
        return None
    if _is_this_card(segments[-1]):
        return WHY_PATIENT
    if _attribute_of_self(segments):
        return WHY_ATTRIBUTE
    if any(_is_this_card(seg) and not segments[i + 1]["text"].startswith(WITH_THIS_CARD)
           for i, seg in enumerate(segments[:-1])) \
            or any(_listed_in_modifier(m) for seg in segments for m in seg["modifiers"]):
        return WHY_LISTED
    if any(m["text"].endswith(THIS_CARD + "を含む") for seg in segments for m in seg["modifiers"]):
        return WHY_INCLUDING
    if _this_effect(segments):
        return WHY_THIS_EFFECT
    return None


def _other_than_self(segments):
    """このカード以外;群體前的「他の」(フィールドの他の、その他の)在卡文裡同樣是此卡以外。"""
    for seg in segments:
        for mod in seg["modifiers"]:
            text = mod["text"]
            if THIS_CARD + "以外" in text or text == "他" or text.endswith("の他"):
                return True
    return False


def _attached(seg, following):
    """第一個修飾語之後(後面的修飾語或中心詞)有 X素材/装備/… 這類另一張實體卡。"""
    after = [m["text"] for m in seg["modifiers"][1:]] + [seg["head"] or ""]
    return any(text.startswith(following) for text in after)


def _attached_to_self(seg):
    """このカードのX素材、このカードのリンク先のモンスター;定語子句把前面的段併進去時(このカードのリンク先のEXデッキから
    特殊召喚された|モンスター)看修飾語字面的開頭。"""
    mods = seg["modifiers"]
    if not mods:
        return False
    if mods[0]["text"] == THIS_CARD:
        return _attached(seg, ATTACHED_TO_SELF)
    return mods[0]["text"].startswith(tuple(THIS_CARD + "の" + word for word in ATTACHED_TO_SELF))


def _pure_count(seg):
    """只剩量詞的段(１枚、その２体、3体以上):中心詞就是那個數量。"""
    return bool(seg["quantity"]) and seg["head"] == seg["quantity"]["text"]


def _counts_cards(seg):
    """段的數量是 枚/体 數的:數的一定是卡(相手が選んだ4枚 的中心詞落 其他,仍是卡)。"""
    return bool(seg["quantity"]) and any(c in seg["quantity"]["text"] for c in CARD_COUNTERS)


def head_class(seg):
    """段 → 判定用的粗類 card/effect/value/not_card/unknown(中心詞類加事件類小表)。"""
    kind, head = seg["head_kind"], seg["head"] or ""
    if kind == HEAD_NON_CARD:
        # 合計3枚を対象として:段尾自己的 枚/体 數量說的是卡;数を2体にできる 的 2体 取自子句,是值
        return CARD if _counts_cards(seg) and not seg["quantity"]["from_clause"] else NOT_CARD
    if kind == HEAD_ATTRIBUTE:
        return EFFECT if head.endswith(EVENT_WORDS) else VALUE
    if kind == HEAD_CARD:
        return CARD
    if kind == HEAD_DEMONSTRATIVE:
        if _pure_count(seg):
            return CARD if _counts_cards(seg) else UNKNOWN
        return CARD
    return CARD if _counts_cards(seg) else UNKNOWN


def _quantity_of(seg, own=False):
    """段的數量(全部 不算;own 時取自子句的也不算——回指時只看指示詞自己帶的)。"""
    quantity = seg["quantity"]
    return bool(quantity) and quantity["kind"] != Q_ALL and not (own and quantity["from_clause"])


def _trailing_count(seg):
    """指示詞類中心詞後 の 接的數量(その内の1体、残りの1体、その2体の内の1体):片語沒收進數量尾,再切一次段看。"""
    text, head = seg["text"], seg["head"] or ""
    if seg["head_kind"] != HEAD_DEMONSTRATIVE or not head or head not in text:
        return False
    tail = text[text.index(head) + len(head):]
    if not tail.startswith("の"):
        return False
    return any(_quantity_of(found) for found in segments_of(tail[1:]))


def _has_count(segments, own=False):
    """任一段有數量且數量類不是 全部(取自子句的已在段裡;own 時不算):段尾的、指示詞類中心詞後 の 接的,
    或連體的數量(3体以上の|モンスター、合計8枚の|カード:落在其他類修飾語裡,再切一次段看)。"""
    for seg in segments:
        if _quantity_of(seg, own) or _trailing_count(seg):
            return True
        if any(m["kind"] == OTHER and any(_quantity_of(found) for found in segments_of(m["text"]))
               for seg_mod in (seg,) for m in seg_mod["modifiers"]):
            return True
    return False


def _relational(seg):
    """段裡有關係詞:以外/同名(其他類修飾語的詞)或帶比較的數值(攻撃力1500以上)——指示詞只修飾另一張卡。"""
    for mod in seg["modifiers"]:
        if mod["kind"] == MOD_NUMERIC and mod.get("compare"):
            return True
        if mod["kind"] == OTHER and mod["text"] \
                and any(_ctx().surface(t) in RELATIONAL_WORDS for t in _ctx().tokenize(mod["text"])):
            return True
    return False


def _demonstrative_role(segments):
    """第一段的指示詞是回指(REFERENCE)、只修飾另一張卡(MODIFIER),或都不是(None:照中心詞判)。
    旗標假而段首仍是指示詞(そのモンスターと同じ種族のモンスター):只修飾。旗標真:中心詞不是卡/屬性/指示詞類
    (その数)照中心詞判;綁的卡的附屬卡(そのモンスターのX素材、その相手モンスターの攻撃対象)照卡判;段裡有關係詞
    只修飾;指示詞綁在第一個修飾語上時看那個詞——修飾語類是卡的限定(その相手、その融合、その表側表示)或綁的是卡/
    數量/定語子句(そのモンスターの効果、その2体の内、その破壊された)是回指,綁的是屬性/非卡/時間程度名詞
    (その種族の、その時の、その中の)只修飾;沒有修飾語時 卡/屬性 類是回指,指示詞類只有 それ/それら/内/只剩數量是回指。"""
    seg = segments[0]
    text, kind, mods = seg["text"], seg["head_kind"], seg["modifiers"]
    if head_class(segments[-1]) in (NOT_CARD, UNKNOWN):
        return None                       # その攻撃モンスターと対象のモンスターの攻撃力の差分のダメージ:受事者不是卡
    if not seg["demonstrative"]:
        if not opener_of(text):
            return None
        cls = head_class(seg)
        if cls == CARD:
            return MODIFIER
        if cls in (VALUE, EFFECT):
            # 屬性/效果跟著主人:主人是卡才是只修飾(そのモンスターと同じ種族のモンスターの攻撃力);
            # そのモンスターがフィールドで発動した効果 的主人不是卡,仍是回指
            owner = _owner(seg)
            return MODIFIER if owner and head_class(owner[-1]) == CARD else REFERENCE
        return None
    if kind not in (HEAD_CARD, HEAD_ATTRIBUTE, HEAD_DEMONSTRATIVE):
        return None
    if mods and _attached(seg, ATTACHED_TO_OTHER):
        return None
    if _relational(seg):
        return MODIFIER if head_class(seg) in (CARD, VALUE, EFFECT) else None
    if opener_of(text) in TARGETED_PREFIXES:
        return REFERENCE
    opener = opener_of(mods[0]["text"]) if mods else None
    if opener and mods[0]["kind"] == OTHER:
        bound = mods[0]["text"][len(opener):]
        if _is_clause(bound):
            return REFERENCE
        found = segments_of(bound)
        if bound in NON_REFERENCE_NOUNS or (found and head_class(found[-1]) in (VALUE, NOT_CARD)):
            return MODIFIER if head_class(seg) in (CARD, VALUE, EFFECT) else None
        return REFERENCE
    if kind == HEAD_DEMONSTRATIVE:
        return REFERENCE if seg["head"] in REFERENCE_HEADS or _pure_count(seg) else None
    return REFERENCE


def _card_group(segments, all_class, counted=False):
    """受事者是卡(或屬性的主人):→ (值, 理由);counted 是段之外已知的數量(屬性段的、回填對象的提供框架的)。"""
    if _attached_to_self(segments[0]):
        return NONSELF, WHY_ATTACHED
    if segments[0]["demonstrative"] or counted or _has_count(segments):
        return NONSELF, WHY_SELECTED
    return all_class(segments)


def _only_this_card(segments):
    """字面只是此卡(帶定語的也算:S召喚したこのカード);並列含此卡的不算。"""
    return len(segments) == 1 and _is_this_card(segments[0])


def _follow_target(segments, target, target_class):
    """受事者是指示詞、帶回指:→ (值, 理由);target_class 是目標的全部類判定((回指欄, 目標的段) → (值, 理由))。"""
    subject = segments_of(target.get("subject"))
    if target["via"] == VIA_EVENT:
        if subject and _only_this_card(subject):
            return SELF, WHY_ANAPHORA_OWNER_SELF
        return NONSELF, WHY_ANAPHORA_OWNER_OTHER
    found = segments_of(target["text"])
    if _names_this_card(found):
        return SELF, WHY_ANAPHORA_SELF
    if _other_than_self(found):
        return NONSELF, WHY_ANAPHORA_OTHER_THAN_SELF
    if found and _attached_to_self(found[0]):
        return NONSELF, WHY_ANAPHORA_ATTACHED
    # このカードが戦闘でモンスターを破壊し…そのモンスター:此卡是施事者,目標確定是別張
    if subject and _only_this_card(subject):
        return NONSELF, WHY_ANAPHORA_SELF_AGENT
    if target.get("count") or _has_count(found) or _has_count(segments[:1], own=True):
        return NONSELF, WHY_ANAPHORA_SELECTED
    mode, why = target_class(target, found)
    return mode, ANAPHORA_PREFIX + why


def _modifier_group(segments, all_class, counted=False):
    """指示詞只修飾另一張卡:受事者照自己的段判,帶數量是選擇類,沒有數量走全部類。"""
    if counted or _has_count(segments):
        return NONSELF, WHY_MODIFIER_SELECTED
    mode, why = all_class(segments)
    return mode, MODIFIER_PREFIX + why


def _owner(seg):
    """屬性段的主人(中心詞之前的字面,元々の 不算;尾端的括號註記去掉;モンスターカード名 的主人在合記的中心詞裡)
    → 它的段;沒有主人時空。"""
    text, head = seg["text"], seg["head"] or ""
    if text.endswith(PAREN_CLOSE) and PAREN_OPEN in text:
        text = text[:text.rindex(PAREN_OPEN)]
    if not head or not text.endswith(head):
        return ()
    owner = text[:-len(head)].rstrip("の")
    if not owner and head.endswith("カード名") and head != "カード名":
        owner = head[:-len("カード名")]
    if owner.endswith(ORIGINAL):
        owner = owner[:-len(ORIGINAL)].rstrip("の")
    return segments_of(owner)


def classify(segments, all_class, target=None, target_class=None, counted=False):
    """受事者的段 → (值, 理由);all_class 是全部類的判定(段 → (值, 理由));target 是框架的回指欄,
    target_class 是目標的全部類判定;counted 是回填對象從提供它的框架帶來的數量。中心詞類看最後一段
    (並列的 攻撃力・守備力、モンスター・魔法・罠カード)。"""
    if not segments:
        return None, WHY_NONE
    why = self_rule(segments)
    if why:
        return SELF, why
    if _other_than_self(segments):
        return NONSELF, WHY_OTHER_THAN_SELF
    if target:
        # 回指欄在就是回指(框架線解回指時已判定受事者是指示詞、找到目標),不再看段的旗標
        return _follow_target(segments, target, target_class)
    role = _demonstrative_role(segments)
    kind = head_class(segments[-1])
    if role == MODIFIER:
        group = segments
        if kind == VALUE:
            k = _attribute_run(segments)
            group = (tuple(segments[:k]) + _owner(segments[k])) or segments
        return _modifier_group(group, all_class, counted)
    if role == REFERENCE:
        return NONSELF, WHY_ANAPHORA_BLANK
    if kind == NOT_CARD:
        return None, WHY_NOT_CARD
    if kind == UNKNOWN:
        return None, WHY_UNKNOWN
    if kind == EFFECT:
        if segments[0]["text"].startswith(THIS_CARD + "名"):
            return None, WHY_THIS_NAME
        return NONSELF, WHY_OTHERS_EFFECT
    if kind == VALUE:
        if segments[0]["demonstrative"]:
            return NONSELF, WHY_SELECTED
        k = _attribute_run(segments)
        owner = tuple(segments[:k]) + _owner(segments[k])
        if not owner or head_class(owner[-1]) != CARD:
            return None, WHY_NO_OWNER
        return _card_group(owner, all_class, counted or _has_count(segments))
    return _card_group(segments, all_class, counted)


def _target_class(target, found, launched, face):
    """回指目標是無數量的群體:全部類比對;區域用回指欄,玩家或事件主語是相手時確定不是此卡。"""
    # 目標自己寫的玩家優先:相手が自分のモンスターを破壊した時 的目標是自分的
    subject = segments_of(target.get("subject"))
    player = PLACE_PLAYER.get(target.get("player"), target.get("player"))
    if player is None and subject and subject[0]["player"] == OPPONENT:
        player = OPPONENT
    if player == OPPONENT:
        return NONSELF, WHY_ALL_PLAYER
    zones = [tuple(pair) for pair in regions.zones_of(target.get("place"))]
    return _all_class(found, zones, launched, face)


def _plain_why(why):
    """去掉回指、修飾語前綴 → 全部類的理由本身。"""
    for prefix in (ANAPHORA_PREFIX, MODIFIER_PREFIX):
        if why and why.startswith(prefix):
            return why[len(prefix):]
    return why


def _is_all_class(why):
    """理由是全部類比對的結果(含回指、修飾語前綴):用到發動位置。"""
    return _plain_why(why) in _WHY_ALL_CLASS


def is_uncomparable(why):
    """全部類因為比不了或區域不明而視為可能包含此卡。"""
    return _plain_why(why) in (WHY_ALL_UNCOMPARABLE, WHY_ALL_NO_ZONE)


class Verdict:
    """一個框架的判定:值、理由、受事者字面,以及全部類用到的發動位置來源(其餘 None)。"""
    __slots__ = ("mode", "why", "text", "launch")

    def __init__(self, mode, why, text="", launch_source=None):
        self.mode, self.why, self.text, self.launch = mode, why, text, launch_source


def _donor_count(frames_, k):
    """第 k 個框架的對象是回填來的(１枚選んで破壊する)時,數量寫在提供對象的那個框架的子句裡:看它的對象段。"""
    frame = frames_[k]
    if "object" not in (frame.get("backfill") or ()):
        return False
    for earlier in reversed(frames_[:k]):
        if earlier.get("kind") == KIND_ACTION and earlier.get("object") == frame.get("object"):
            return _has_count(_segments(earlier, "object"))
    return False


def judge(frame, launched, face, counted=False):
    """一個動作框架(所在效果句的發動位置、此卡卡面參數、回填對象從提供框架帶來的數量)→ Verdict。"""
    text, segments, by_topic = patient(frame)
    if frame.get("action") in _NOT_CARD_ACTIONS:
        return Verdict(None, WHY_NOT_CARD, text)
    frame_zones = _region_pairs(frame, REGION_PLACE, REGION_SOURCE)
    mode, why = classify(segments, lambda group: _all_class(group, frame_zones, launched, face),
                         frame.get("anaphora"), lambda target, found: _target_class(target, found, launched, face),
                         counted)
    if by_topic and why == WHY_PATIENT:
        why = WHY_TOPIC
    return Verdict(mode, why, text, launched.source if _is_all_class(why) else None)


def judge_sentence(frames_, face=None, section="main"):
    """一句效果句的框架清單(與此卡卡面參數,沒有時不比卡面;段落)→ 與它對齊的 [Verdict];
    約束框架是 Verdict(None, None)。"""
    positions = _positions(frames_, launch(frames_, section))
    return [judge(fr, positions[k], face, _donor_count(frames_, k)) if fr.get("kind") == KIND_ACTION
            else Verdict(None, None) for k, fr in enumerate(frames_)]
