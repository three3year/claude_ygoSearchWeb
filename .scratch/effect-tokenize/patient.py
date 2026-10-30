# -*- coding: utf-8 -*-
"""[[動作對象]]判定(.scratch/action-patient):一句效果句的動作框架 → 每個框架動到的是
不是此卡本身。

接在框架抽取之後、由類別匯出(export_categories.py)呼叫;框架抽取的受事者取法不改,
判定在它的結果上加規則。值是 此卡(SELF)、非此卡(NONSELF),或 None(皆非:兩種模式
都不中)。

受事者依態取:他動(與沒判態的)取對象,自動/受身取主語、沒有時取主題;對象空著而主題
(含句內延續的主題)指名此卡時,主題就是受事者,不分動作。

- 此卡:受事者字面指名此卡(self_rule)。
- 非此卡:受事者是卡、字面不指名此卡,而且是選擇類(帶數量、指示詞)、このカード以外、
  此卡的附屬卡(X 素材、裝備怪獸、リンク先),或主人不是此卡的效果、發動、攻擊。屬性
  (攻撃力、レベル…)跟著它的主人判。
- 皆非:受事者不是卡(封閉名詞表)、表外判不出的,以及會包含此卡的全部類。

受事者是指示詞時讀框架的[[回指]](anaphora.py),沿用目標的判定:目標含此卡 → 此卡;このカード以外、
他の → 非此卡;目標或指示詞自己帶數量 → 非此卡;無數量的群體 → 全部類比對(區域、玩家用回指欄,
事件主語是相手算對手,事件主語是此卡時目標確定是別張,
發動位置用受事者那個框架當時的位置)。效果類(その発動、その効果、その攻撃)
事件主人字面是此卡才算此卡,其餘非此卡。回指留空 → 非此卡。修飾語(そのモンスターより…Xモンスター)
不算指示詞,照受事者自己的字面判。字面指名此卡的規則(そのカードとこのカード)優先於回指。

全部類(沒有數量的群體)依**發動位置**判:一句效果句內依序取 條件/代價寫明的此卡區域、
條件位觸發事件裡此卡的去處、處理中此卡自己移動的起點,都沒有就是場上(此卡在我方)。此卡在
代價或處理中自己移動之後,後面的框架改看移動的目的(手札から特殊召喚 之後 手札全部 不含此卡)。
群體的區域(所在或來源)含發動位置,而且玩家、卡種、種族、屬性、字段、卡片子類型、數值條件
全都對得上此卡的卡面參數,才算會包含此卡;比不了的定語(含區域判不出)一律視為對得上,任一
條件對不上就判非此卡。條件只看群體本身:修飾語(〜を素材とした、〜以外の)裡的種族說的是
別的東西,切掉後記為比不了;か/と 並列的是替代項,任一項全對得上就算包含。
"""
from collections import namedtuple
import os
import re
import sys
import unicodedata

import anaphora
from constraints import KIND_ACTION
from frames import POS_COND, POS_COST, POS_EFFECT
from places import PLAYER_OPP, ZONE_TERMS, parse_zones

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "..", "script", "web"))
import vocab  # noqa: E402

SELF = "此卡"
NONSELF = "非此卡"
NEITHER = "皆非"       # 統計的鍵;Verdict.mode 以 None 表示

THIS_CARD = anaphora.THIS_CARD
INTRANSITIVE = anaphora.INTRANSITIVE

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
# 並列詞(替代項的切分與並列含此卡共用)
_CONJUNCTIONS = "または|か|や|及び|および|と"

_SPACES = re.compile(r"\s+")
# 此卡的屬性(このカードの攻撃力・守備力、この効果で特殊召喚したこのカードのレベル):
# 屬性跟著此卡走;效果、發動、召喚、攻擊也是屬性(受事者是效果、發動時跟著主人走)。
# 裝備怪獸、X 素材、カウンター、リンク先 不在表上——那是另一張實體卡或別的東西
_EFFECT_HEADS = ("効果", "発動", "攻撃", "特殊召喚", "召喚")
_VALUE_HEADS = anaphora.VALUE_HEADS
_ATTRIBUTES = _VALUE_HEADS + _EFFECT_HEADS
_ATTR = "(?:元々の)?(?:%s)" % "|".join(_ATTRIBUTES)
_ATTR_LIST = r"%s(?:(?:・|と|及び|および)%s)*" % (_ATTR, _ATTR)
_ATTRIBUTE_OF_SELF = re.compile(r"%sの+%s$" % (THIS_CARD, _ATTR_LIST))
# 並列含此卡:このカードと〜、このカード及び〜(〜とこのカード 以此卡收尾,已算);
# このカードと同じ縦列、このカードとは種族が異なる 這類比較不是並列
_LISTED_WITH_SELF = re.compile(r"%s(?:%s)(?!同じ|同名|は|相互|リンクし|リンク状態|戦闘|\(共同\)|異なる"
                               r"|元々|(?:種族|属性|カード名|レベル|攻撃力|守備力)が)"
                               % (THIS_CARD, _CONJUNCTIONS))
_INCLUDING_SELF = THIS_CARD + "を含む"
# この効果、この効果の発動、この発動とこの効果:主人是此卡(この効果で特殊召喚したモンスターの
# 効果 主人是別張)
_THIS_EFFECT = re.compile(r"^この(?:効果|発動)(?:の発動)?(?:(?:と|・)(?:この)?(?:効果|発動))*$")
# このカード以外;群體前的「他の」(フィールドの他のカード)在卡文裡同樣是此卡以外
_OTHER_THAN_SELF = re.compile(r"%s以外|(?:^|の)他の" % THIS_CARD)
# 此卡的附屬卡:另一張實體卡(このカードのX素材、このカードの装備モンスター、リンク先)
_ATTACHED = re.compile(r"^%sの(?:X素材|装備|リンク先)" % THIS_CARD)

# 受事者的中心詞分類(封閉表;依結尾比):
# 卡——卡片名詞、「卡名」、區域(受事者寫成區域時以那個區域當群體)、指示代名詞
_CARD_HEADS = ("モンスター", "カード", "トークン", "チューナー", "」", "X素材", "素材", "手札",
               "デッキ", "墓地", "フィールド", "それ", "それら", "いずれか", "内", "対象", "残り",
               "魔法", "罠")
# 不是卡——傷害、LP、數值、指示物與遊戲程序
# 選擇類:受事者帶數量(數字+量詞、〜まで)或指示詞。數量只寫在子句裡時要緊接受事者
# (手札を１枚捨てる、カードを３枚まで)或是「〜の數まで/任意の數」——子句裡別的數字不算:
# ターン終了時まで 是期間、レベルは５つ上がる 是升降值。全て 優先於子句裡的數量
_QUANTITY = r"[0-9０-９]+(?:枚|体|つ|種類|ヵ所|箇所|個)"
_COUNT = re.compile(r"%s|まで" % _QUANTITY)
_CLAUSE_COUNT = re.compile(r"を%s|数まで|任意の数|好きな数" % _QUANTITY)
_ALL_OF_THEM = re.compile(r"全て")
_COUNT_TAIL = re.compile(r"(?:%s)?(?:まで|以上)?$" % _QUANTITY)
_CARD_COUNT = re.compile(r"[0-9０-９]+(?:枚|体)")
_PAREN_TAIL = re.compile(r"[（(][^（()）]*[)）]$")
_QUOTED = re.compile(r"「[^」]*」")
_ATTRIBUTE_TAIL = re.compile(r"^(.*?)(?:の)*%s$" % _ATTR_LIST)


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


# 卡種(卡片總表 type 位元)
_KIND_BITS = _bits_by_word({"モンスター": "m", "魔法": "s", "罠": "t"}, vocab.CAT, exhaustive=True)
_KIND_TAIL = {word: re.compile(word + r"(?:\(カード\))?(?:カード)?$") for word in _KIND_BITS}


def _clean(text):
    return _SPACES.sub("", text or "")


def _zones(literal):
    """地點字面 → [(玩家, 區域)];フィールド上 這類尾巴去掉再認,認不出時 []。"""
    literal = _clean(literal)
    if not literal:
        return []
    return parse_zones(literal) or parse_zones(re.sub(r"上$", "", literal)) or []


# 受事者開頭的區域片語(自分フィールドの「天気」魔法・罠カード:框架沒切出所在時)
_LEADING_ZONE = re.compile(r"^((?:自分|相手|お互い)?の?(?:%s))の" % "|".join(
    re.escape(term) for term, _ in ZONE_TERMS))


def _group_zones(text, frame):
    """群體的區域:框架的所在或來源;都沒有時看受事者本身(手札を全て捨てる)或它開頭的
    區域片語。"""
    zones = _zones(frame.get("place") or frame.get("source"))
    if zones:
        return zones
    zones = _zones(text) if head_kind(text) == "card" else []
    if zones:
        return zones
    lead = _LEADING_ZONE.match(_clean(text))
    return _zones(lead.group(1)) if lead else []


def _names_this_card(text):
    """字面把此卡本身算進去:以此卡收尾、並列含此卡、包含此卡(此卡的屬性不算移動此卡)。"""
    return self_rule(_clean(text)) in (WHY_PATIENT, WHY_LISTED, WHY_INCLUDING)


def _trigger_zones(frame):
    """條件位以此卡為主語的事件 → 此卡的去處。此卡是施事者(對象另有其物、破壊した)時此卡
    沒有移動。"""
    if frame.get("object"):
        return []
    zones = _zones(frame.get("goal"))
    if zones:
        return zones
    leaves = frame.get("action") == "離れる" or FIELD in {z for _, z in _zones(frame.get("source"))}
    if leaves or (frame.get("action") in LEAVE_FIELD_ACTIONS and frame.get("voice") == "受身"):
        return [(None, OFF_FIELD)]
    return []


def launch(frames, section="main"):
    """一句效果句的框架 → Launch;靈擺段落的效果預設在靈擺區。"""
    written, trigger, move = [], [], []
    for fr in frames:
        if fr.get("kind") != KIND_ACTION:
            continue
        position = fr.get("position")
        agent = fr.get("subject") or fr.get("topic")
        if position == POS_COND and _names_this_card(agent):
            if fr.get("action") in STATE_ACTIONS:
                written = written or _zones(fr.get("goal") or fr.get("place"))
            else:
                trigger = trigger or _trigger_zones(fr)
        elif position == POS_COST and _names_this_card(fr.get("object")):
            written = written or _zones(fr.get("source") or fr.get("place"))
        elif position == POS_EFFECT and _names_this_card(patient(fr)[0]):
            move = move or _zones(fr.get("source"))
    for found, source in ((written, LAUNCH_WRITTEN), (trigger, LAUNCH_TRIGGER),
                          (move, LAUNCH_MOVE)):
        if found:
            return Launch({zone for _, zone in found}, source)
    return Launch({PENDULUM_ZONE} if section == "pendulum" else {FIELD}, LAUNCH_DEFAULT)


def _self_move_zones(frame):
    """代價或處理中此卡自己移動 → 去處;不是移動時 []。否定的不算(戦闘では破壊されない),
    沒有去處的 破壊/リリース 當離開場上。"""
    if (frame.get("position") not in (POS_COST, POS_EFFECT) or frame.get("polarity") == "否定"
            or not _names_this_card(patient(frame)[0])):
        return []
    zones = _zones(frame.get("goal"))
    if zones:
        return zones
    return [(None, OFF_FIELD)] if frame.get("action") in LEAVE_FIELD_ACTIONS else []


def _positions(frames, launched):
    """一句效果句 → 與框架對齊的 Launch:此卡自己移動之前是發動位置,之後看目的。● 選項是
    替代關係,移動只影響共同部分與同一選項的框架。"""
    moved = {}
    out = []
    for fr in frames:
        option = fr.get("option")
        latest = moved.get(option) or moved.get(None)
        out.append(latest or launched)
        if fr.get("kind") == KIND_ACTION:
            zones = _self_move_zones(fr)
            if zones:
                moved[option] = Launch({zone for _, zone in zones}, LAUNCH_AFTER_MOVE)
    return out


def group_kinds(text):
    """群體字面 → 卡種位元的集合(看並列的每段中心詞;カード、「卡名」、區域是任何卡種 →
    None)。"""
    kinds = set()
    for part in re.split("・|" + _CONJUNCTIONS, _core(text)):
        found = [bit for word, bit in _KIND_BITS.items() if _KIND_TAIL[word].search(part)]
        if not found:
            return None
        kinds.update(found)
    return kinds or None


# 卡面參數:卡文的日文寫法 → 值域正典的碼(位元由正典來)
_RACE_BITS = _bits_by_word(
    {"戦士族": "warrior", "魔法使い族": "spellcaster", "天使族": "fairy", "悪魔族": "fiend",
     "アンデット族": "zombie", "機械族": "machine", "水族": "aqua", "炎族": "pyro", "岩石族": "rock",
     "鳥獣族": "winged_beast", "植物族": "plant", "昆虫族": "insect", "雷族": "thunder",
     "ドラゴン族": "dragon", "獣族": "beast", "獣戦士族": "beast_warrior", "恐竜族": "dinosaur",
     "魚族": "fish", "海竜族": "sea_serpent", "爬虫類族": "reptile", "サイキック族": "psychic",
     "幻神獣族": "divine_beast", "創造神族": "creator_god", "幻竜族": "wyrm",
     "サイバース族": "cyberse", "幻想魔族": "illusion"}, vocab.RACE, exhaustive=True)
_RACE = re.compile("|".join(sorted(_RACE_BITS, key=len, reverse=True)))
_ATTR_BITS = _bits_by_word({"地": "earth", "水": "water", "炎": "fire", "風": "wind", "光": "light",
                            "闇": "dark", "神": "divine"}, vocab.ATTR, exhaustive=True)
_ATTR_CHARS = "".join(_ATTR_BITS)
_ATTRIBUTE = re.compile(r"((?:[%s]・)*[%s])属性" % (_ATTR_CHARS, _ATTR_CHARS))
_MONSTER_TYPE_BITS = _bits_by_word(
    {"融合": "fusion", "シンクロ": "synchro", "S": "synchro", "エクシーズ": "xyz", "X": "xyz",
     "リンク": "link", "L": "link", "儀式": "ritual", "ペンデュラム": "pendulum", "P": "pendulum",
     "通常": "normal", "効果": "effect", "トゥーン": "toon", "スピリット": "spirit", "ユニオン": "union",
     "デュアル": "dual", "リバース": "flip", "チューナー": "tuner"}, vocab.SUB["m"])
_MONSTER_TYPE_ALT = "|".join(sorted(_MONSTER_TYPE_BITS, key=len, reverse=True))
_MONSTER_TYPES = re.compile(r"((?:(?:%s)・?)+)モンスター|チューナー" % _MONSTER_TYPE_ALT)
_SPELL_TRAP_TYPE_BITS = {
    "魔法": _bits_by_word({"速攻": "quick", "永続": "continuous", "装備": "equip",
                           "フィールド": "field", "儀式": "ritual"}, vocab.SUB["s"]),
    "罠": _bits_by_word({"永続": "continuous", "カウンター": "counter"}, vocab.SUB["t"])}
_SPELL_TRAP_TYPES = re.compile(r"(通常|速攻|永続|装備|フィールド|儀式|カウンター)(魔法|罠)")
_NUMERIC = re.compile(r"(レベル|ランク|リンク|攻撃力|守備力)が?([0-9０-９]+)(以上|以下|未満)?")
XYZ_BIT, LINK_BIT = _MONSTER_TYPE_BITS["X"], _MONSTER_TYPE_BITS["L"]
TUNER_BIT = _MONSTER_TYPE_BITS["チューナー"]

# 修飾語:最後一個述語或關係詞之前都是別的東西的條件(〜を素材とした、〜以外の、〜と同じ)
_MODIFIER = re.compile(r"^.*(?:した|する|された|される|されて|している|となる|とする|を含む|と同じ"
                       r"|異なる|持つ|以外の|より|いる|ある|ない)")
_ALTERNATIVE = re.compile(_CONJUNCTIONS)
_KNOWN_TOKENS = re.compile("|".join(
    [r"「\d+」", _RACE.pattern, _ATTRIBUTE.pattern, _NUMERIC.pattern, _MONSTER_TYPES.pattern,
     _SPELL_TRAP_TYPES.pattern]
    + [re.escape(term) for term, _ in ZONE_TERMS]
    + ["モンスター", r"\(カード\)", "カード", "魔法", "罠", "トークン", "全ての", "全て", "自分",
       "相手", "お互い", "上", "の", "・", "または", "か", "や", "及び", "および", "と"]))


def _nfkc(text):
    return unicodedata.normalize("NFKC", text or "")


def _mask_names(text):
    """「卡名」換成編號佔位(名字裡的字不干擾切分)→ (字面, 名字清單)。"""
    names = []

    def mask(match):
        names.append(match.group(1))
        return "「%d」" % (len(names) - 1)
    return re.sub(r"「([^」]*)」", mask, text), names


def _subtype_block(segment, face):
    """子類型條件:群體寫了卻對不上 → True。同一替代項有沒帶子類型的卡種名詞時不算條件
    (融合モンスター・魔法カード)。"""
    types = face["type"]
    wanted = [m for m in _MONSTER_TYPES.finditer(segment)]
    spell_trap = list(_SPELL_TRAP_TYPES.finditer(segment))
    if not wanted and not spell_trap:
        return False
    nouns = len(re.findall(r"モンスター|魔法|罠|チューナー", segment))
    if nouns > len(wanted) + len(spell_trap):
        return False
    for m in wanted:
        if m.group(0) == "チューナー":
            if types & TUNER_BIT:
                return False
            continue
        names = re.findall(_MONSTER_TYPE_ALT, m.group(1))
        if types & _KIND_BITS["モンスター"] and any(types & _MONSTER_TYPE_BITS[n] for n in names):
            return False
    for m in spell_trap:
        name, kind = m.groups()
        bits = _SPELL_TRAP_TYPE_BITS[kind]
        if not types & _KIND_BITS[kind]:
            continue
        if name == "通常" and not any(types & bit for bit in bits.values()):
            return False
        if bits.get(name, 0) & types:
            return False
    return True


def _numeric_block(segment, face):
    """數值條件:對不上 → True;攻守未知(?)比不了,不擋。"""
    types = face["type"]
    for field, digits, op in _NUMERIC.findall(segment):
        wanted = int(digits)
        if field == "レベル":
            value = None if types & (XYZ_BIT | LINK_BIT) else face.get("level")
        elif field == "ランク":
            value = face.get("level") if types & XYZ_BIT else None
        elif field == "リンク":
            value = face.get("level") if types & LINK_BIT else None
        else:
            value = face.get("atk" if field == "攻撃力" else "def")
            if value is not None and value < 0:
                continue
        if value is None:
            return True
        if op == "以上" and value < wanted or op == "以下" and value > wanted \
                or op == "未満" and value >= wanted or not op and value != wanted:
            return True
    return False


def _segment_blocker(segment, names, face):
    """一個替代項對此卡卡面參數的第一個擋下的條件(理由),全對得上時 None。"""
    kinds = group_kinds(segment)
    if kinds is not None and not any(face["type"] & bit for bit in kinds):
        return WHY_ALL_KIND
    races = _RACE.findall(segment)
    if races and not any(face["race"] & _RACE_BITS[r] for r in races):
        return WHY_ALL_RACE
    attrs = [a for found in _ATTRIBUTE.findall(segment) for a in found.split("・")]
    if attrs and not any(face["attribute"] & _ATTR_BITS[a] for a in attrs):
        return WHY_ALL_ATTR
    quoted = [names[int(i)] for i in re.findall(r"「(\d+)」", segment)]
    if quoted and not any(_nfkc(q) in _nfkc(face.get("name_ja")) for q in quoted):
        return WHY_ALL_ARCHETYPE
    if _subtype_block(segment, face):
        return WHY_ALL_SUBTYPE
    if _numeric_block(segment, face):
        return WHY_ALL_NUMERIC
    return None


def _compare_face(text, face):
    """群體字面 × 此卡卡面參數 → (擋下的理由或 None, 有沒有比不了的定語)。"""
    masked, names = _mask_names(_nfkc(text))
    body = _MODIFIER.sub("", masked)
    uncomparable = body != masked or bool(_KNOWN_TOKENS.sub("", body))
    blockers = [_segment_blocker(segment, names, face)
                for segment in _ALTERNATIVE.split(body) if segment]
    if not blockers or None in blockers:
        return None, uncomparable
    return blockers[0], uncomparable


def _all_class(text, frame, launched, face):
    """全部類:→ (值, 理由)。"""
    zones = _group_zones(text, frame)
    possible = launched.zones
    # 靈擺區在場上:群體寫場上時含靈擺區的此卡
    reachable = [(player, zone) for player, zone in zones
                 if zone in possible or (OFF_FIELD in possible and zone != FIELD)
                 or (zone == FIELD and PENDULUM_ZONE in possible)]
    if zones and not reachable:
        return NONSELF, WHY_ALL_ZONE
    if reachable and all(player == PLAYER_OPP for player, _ in reachable):
        return NONSELF, WHY_ALL_PLAYER
    uncomparable = False
    if face is not None:
        blocker, uncomparable = _compare_face(text, face)
        if blocker:
            return NONSELF, blocker
    if not zones:
        return None, WHY_ALL_NO_ZONE
    return None, WHY_ALL_UNCOMPARABLE if uncomparable else WHY_ALL_INCLUDES


def patient(frame):
    """→ (受事者字面, 是否由主題規則取得);沒有受事者時字面是空字串。"""
    if frame.get("voice") in INTRANSITIVE:
        return _clean(frame.get("subject") or frame.get("topic")), False
    obj = _clean(frame.get("object"))
    if obj:
        return obj, False
    topic = _clean(frame.get("topic"))
    if self_rule(topic):
        return topic, True
    return "", False


def self_rule(text):
    """受事者字面指名此卡時回命中的規則(理由),否則 None。"""
    if not text:
        return None
    if text.endswith(THIS_CARD):
        return WHY_PATIENT
    if _ATTRIBUTE_OF_SELF.search(text):
        return WHY_ATTRIBUTE
    if _LISTED_WITH_SELF.search(text):
        return WHY_LISTED
    if _INCLUDING_SELF in text:
        return WHY_INCLUDING
    if _THIS_EFFECT.search(text):
        return WHY_THIS_EFFECT
    return None


def _core(text):
    """去掉數量尾、括號尾,「卡名」縮成「」:比中心詞用。"""
    core = _QUOTED.sub("「」", _PAREN_TAIL.sub("", _COUNT_TAIL.sub("", text)))
    return _COUNT_TAIL.sub("", core)


def head_kind(text):
    """受事者字面 → 中心詞類別 card/effect/value/not_card/unknown。"""
    core = _core(text)
    if core.endswith(anaphora.NOT_CARD_HEADS):
        return "not_card"
    if core.endswith(_VALUE_HEADS):
        return "value"
    if core.endswith(_EFFECT_HEADS):
        return "effect"
    if core.endswith(_CARD_HEADS):
        return "card"
    return "unknown"


def _has_count(text, clause):
    """受事者帶數量,或數量寫在子句裡(全て 優先)。"""
    return bool(_COUNT.search(text) or (
        _CLAUSE_COUNT.search(clause) and not _ALL_OF_THEM.search(clause)))


def _card_group(text, clause, all_class):
    """受事者是卡(或屬性的主人):→ (值, 理由)。"""
    if _ATTACHED.search(text):
        return NONSELF, WHY_ATTACHED
    if anaphora.is_demonstrative(text) or _has_count(text, clause):
        return NONSELF, WHY_SELECTED
    return all_class(text)


def _follow_target(text, target, target_class):
    """受事者是指示詞、帶回指:→ (值, 理由);target_class 是目標的全部類判定(回指欄 → (值, 理由))。"""
    if target["via"] == anaphora.VIA_EVENT:
        if target.get("subject") and anaphora.only_this_card(target["subject"]):
            return SELF, WHY_ANAPHORA_OWNER_SELF
        return NONSELF, WHY_ANAPHORA_OWNER_OTHER
    if _names_this_card(target["text"]):
        return SELF, WHY_ANAPHORA_SELF
    if _OTHER_THAN_SELF.search(target["text"]):
        return NONSELF, WHY_ANAPHORA_OTHER_THAN_SELF
    if _ATTACHED.search(target["text"]):
        return NONSELF, WHY_ANAPHORA_ATTACHED
    # このカードが戦闘でモンスターを破壊し…そのモンスター:此卡是施事者,目標確定是別張
    if target.get("subject") and anaphora.only_this_card(target["subject"]):
        return NONSELF, WHY_ANAPHORA_SELF_AGENT
    if target.get("count") or _COUNT.search(target["text"]) or anaphora.reference(text).counted:
        return NONSELF, WHY_ANAPHORA_SELECTED
    mode, why = target_class(target)
    return mode, ANAPHORA_PREFIX + why


def _modifier_group(text, clause, all_class):
    """指示詞只修飾另一張卡:受事者照自己的字面判,帶數量是選擇類,沒有數量走全部類。"""
    if _has_count(text, clause):
        return NONSELF, WHY_MODIFIER_SELECTED
    mode, why = all_class(text)
    return mode, MODIFIER_PREFIX + why


def classify(text, clause, all_class, target=None, target_class=None):
    """受事者字面(與它所在子句的字面,數量可能只寫在子句裡)→ (值, 理由);all_class 是
    全部類的判定(群體字面 → (值, 理由));target 是框架的回指欄,target_class 是目標的全部類判定。"""
    if not text:
        return None, WHY_NONE
    why = self_rule(text)
    if why:
        return SELF, why
    if _OTHER_THAN_SELF.search(text):
        return NONSELF, WHY_OTHER_THAN_SELF
    if anaphora.modifier(text):
        return _modifier_group(text, clause, all_class)
    if anaphora.reference(text):
        return _follow_target(text, target, target_class) if target \
            else (NONSELF, WHY_ANAPHORA_BLANK)
    kind = head_kind(text)
    if kind == "not_card":
        return None, WHY_NOT_CARD
    if kind == "unknown":
        # 只剩量詞(その2体、その内の1枚):枚/体 數的一定是卡
        if _CARD_COUNT.search(text):
            return NONSELF, WHY_SELECTED
        return None, WHY_UNKNOWN
    if kind == "effect":
        if text.startswith(THIS_CARD + "名"):
            return None, WHY_THIS_NAME
        return NONSELF, WHY_OTHERS_EFFECT
    if kind == "value":
        if anaphora.is_demonstrative(text):
            return NONSELF, WHY_SELECTED
        found = _ATTRIBUTE_TAIL.match(_core(text))
        owner = found.group(1) if found else ""
        if not owner or head_kind(owner) != "card":
            return None, WHY_NO_OWNER
        return _card_group(owner, clause, all_class)
    return _card_group(text, clause, all_class)


def _target_class(target, launched, face):
    """回指目標是無數量的群體:全部類比對;區域用回指欄,玩家或事件主語是相手時確定不是此卡。"""
    # 目標自己寫的玩家優先:相手が自分のモンスターを破壊した時 的目標是自分的
    if target.get("player", PLAYER_OPP if _clean(target.get("subject")).startswith(PLAYER_OPP)
                  else None) == PLAYER_OPP:
        return NONSELF, WHY_ALL_PLAYER
    return _all_class(target["text"], {"place": target.get("place")}, launched, face)


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


def _count_clause(frames, k):
    """第 k 個框架比對數量用的子句字面:對象是回填來的(１枚選んで破壊する),數量寫在提供
    對象的那個框架的子句裡,一起看。"""
    frame = frames[k]
    clause = _clean(frame.get("clause"))
    if "object" not in (frame.get("backfill") or ()):
        return clause
    for earlier in reversed(frames[:k]):
        if earlier.get("kind") == KIND_ACTION and earlier.get("object") == frame.get("object"):
            return _clean(earlier.get("clause")) + clause
    return clause


def judge(frame, clause, launched, face):
    """一個動作框架(比對數量用的子句字面、所在效果句的發動位置、此卡卡面參數)→ Verdict。"""
    text, by_topic = patient(frame)
    if frame.get("action") in _NOT_CARD_ACTIONS:
        return Verdict(None, WHY_NOT_CARD, text)
    mode, why = classify(text, clause, lambda group: _all_class(group, frame, launched, face),
                         frame.get("anaphora"), lambda target: _target_class(target, launched, face))
    if by_topic and why == WHY_PATIENT:
        why = WHY_TOPIC
    return Verdict(mode, why, text, launched.source if _is_all_class(why) else None)


def judge_sentence(frames, face=None, section="main"):
    """一句效果句的框架清單(與此卡卡面參數,沒有時不比卡面;段落)→ 與它對齊的 [Verdict];
    約束框架是 Verdict(None, None)。"""
    positions = _positions(frames, launch(frames, section))
    return [judge(fr, _count_clause(frames, k), positions[k], face)
            if fr.get("kind") == KIND_ACTION else Verdict(None, None)
            for k, fr in enumerate(frames)]
