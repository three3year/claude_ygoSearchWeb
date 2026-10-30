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

全部類(沒有數量的群體)依**發動位置**判:一句效果句內依序取 條件/代價寫明的此卡區域、
條件位觸發事件裡此卡的去處、處理中此卡自己移動的起點,都沒有就是場上(此卡在我方)。
群體的區域(所在或來源)含發動位置,而且玩家、卡種、種族、屬性、字段、卡片子類型、數值條件
全都對得上此卡的卡面參數,才算會包含此卡;比不了的定語(含區域判不出)一律視為對得上,任一
條件對不上就判非此卡。條件只看群體本身:修飾語(〜を素材とした、〜以外の)裡的種族說的是
別的東西,切掉後記為比不了;か/と 並列的是替代項,任一項全對得上就算包含。
"""
import re
import unicodedata

from constraints import KIND_ACTION
from places import PLAYER_OPP, ZONE_TERMS, parse_zones

SELF = "此卡"
NONSELF = "非此卡"

THIS_CARD = "このカード"
INTRANSITIVE = ("自動", "受身")

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
WHY_ALL = "全部類"
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

_SPACES = re.compile(r"\s+")
# 此卡的屬性(このカードの攻撃力・守備力、この効果で特殊召喚したこのカードのレベル):
# 屬性跟著此卡走;效果、發動、召喚、攻擊也是屬性(受事者是效果、發動時跟著主人走)。
# 裝備怪獸、X 素材、カウンター、リンク先 不在表上——那是另一張實體卡或別的東西
_EFFECT_HEADS = ("効果", "発動", "攻撃", "特殊召喚", "召喚")
_VALUE_HEADS = ("攻撃力", "守備力", "レベル", "ランク", "Pスケール", "属性", "種族", "カード名",
                "表示形式", "コントロール", "位置")
_ATTRIBUTES = _VALUE_HEADS + _EFFECT_HEADS
_ATTR = "(?:元々の)?(?:%s)" % "|".join(_ATTRIBUTES)
_ATTR_LIST = r"%s(?:(?:・|と|及び|および)%s)*" % (_ATTR, _ATTR)
_ATTRIBUTE_OF_SELF = re.compile(r"%sの+%s$" % (THIS_CARD, _ATTR_LIST))
# 並列含此卡:このカードと〜、このカード及び〜(〜とこのカード 以此卡收尾,已算);
# このカードと同じ縦列、このカードとは種族が異なる 這類比較不是並列
_LISTED_WITH_SELF = re.compile(r"^%s(?:と|及び|および|や|または|か)(?!同じ|同名|は|相互|リンクし|"
                               r"リンク状態|戦闘|\(共同\)|異なる|元々)" % THIS_CARD)
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
_NOT_CARD_HEADS = ("ダメージ", "LP", "ライフポイント", "カウンター", "サイコロ", "コイントス",
                   "フェイズ", "ダメージ計算", "召喚条件", "数値", "数", "ターン", "目", "枚数",
                   "合計", "種類")
# 選擇類:受事者帶數量(數字+量詞、〜まで)或指示詞。數量只寫在子句裡時要緊接受事者
# (手札を１枚捨てる、カードを３枚まで)或是「〜の數まで/任意の數」——子句裡別的數字不算:
# ターン終了時まで 是期間、レベルは５つ上がる 是升降值。全て 優先於子句裡的數量
_QUANTITY = r"[0-9０-９]+(?:枚|体|つ|種類|ヵ所|箇所|個)"
_COUNT = re.compile(r"%s|まで" % _QUANTITY)
_CLAUSE_COUNT = re.compile(r"を%s|数まで|任意の数|好きな数" % _QUANTITY)
_ALL_OF_THEM = re.compile(r"全て")
_COUNT_TAIL = re.compile(r"(?:[0-9０-９]+(?:枚|体|つ|種類|ヵ所|箇所|個))?(?:まで|以上)?$")
_CARD_COUNT = re.compile(r"[0-9０-９]+(?:枚|体)")
_DEMONSTRATIVE = re.compile(r"^(?:その|それら?(?:$|の)|対象の|この効果の対象)")
_PAREN_TAIL = re.compile(r"[（(][^（()）]*[)）]$")
_QUOTED = re.compile(r"「[^」]*」")
_ATTRIBUTE_TAIL = re.compile(r"^(.*?)(?:の)*%s$" % _ATTR_LIST)


# 發動位置的來源(建置報告分項)
LAUNCH_WRITTEN = "寫明"
LAUNCH_TRIGGER = "觸發"
LAUNCH_MOVE = "自己移動"
LAUNCH_DEFAULT = "預設場上"
FIELD = "場上"
PENDULUM_ZONE = "靈擺區"
OFF_FIELD = "場外"           # 去處不明的「離開場上」:不在場上,也不知道在哪
STATE_ACTIONS = ("存在", "ある", "いる")
# 觸發事件沒寫去處、但一定是離開場上的動作
LEAVE_FIELD_ACTIONS = ("破壊", "リリース")
POS_CONDITION, POS_COST, POS_EFFECT = "條件", "代價", "效果"

# 卡種(卡片總表 type 位元)
KIND_BITS = (("怪獸", 0x1), ("魔法", 0x2), ("陷阱", 0x4))
_KIND_WORDS = (("モンスター", "怪獸"), ("魔法", "魔法"), ("罠", "陷阱"))
_KIND_TAIL = {word: re.compile(word + r"(?:\(カード\))?(?:カード)?$") for word, _ in _KIND_WORDS}


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


def _is_this_card(text):
    return _clean(text).endswith(THIS_CARD)


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
    """一句效果句的框架 → (此卡可能所在的區域集合, 來源);靈擺段落的效果預設在靈擺區。"""
    written, trigger, move = [], [], []
    for fr in frames:
        if fr.get("kind") != KIND_ACTION:
            continue
        position = fr.get("position")
        agent = fr.get("subject") or fr.get("topic")
        if position == POS_CONDITION and _is_this_card(agent):
            if fr.get("action") in STATE_ACTIONS:
                written = written or _zones(fr.get("goal") or fr.get("place"))
            else:
                trigger = trigger or _trigger_zones(fr)
        elif position == POS_COST and _is_this_card(fr.get("object")):
            written = written or _zones(fr.get("source") or fr.get("place"))
        elif position == POS_EFFECT and _is_this_card(patient(fr)[0]):
            move = move or _zones(fr.get("source"))
    for found, source in ((written, LAUNCH_WRITTEN), (trigger, LAUNCH_TRIGGER),
                          (move, LAUNCH_MOVE)):
        if found:
            return {zone for _, zone in found}, source
    return ({PENDULUM_ZONE} if section == "pendulum" else {FIELD}), LAUNCH_DEFAULT


def face_kinds(face):
    return {name for name, bit in KIND_BITS if face["type"] & bit}


def group_kinds(text):
    """群體字面 → 卡種集合(看並列的每段中心詞;カード、「卡名」、區域是任何卡種 → None)。"""
    core = _core(text)
    kinds = set()
    for part in re.split(r"・|か|または|及び|と|や", core):
        found = [kind for word, kind in _KIND_WORDS if _KIND_TAIL[word].search(part)]
        if not found:
            return None
        kinds.update(found)
    return kinds or None


# 卡面參數:總表的位元(同 script/web/vocab.py 的值域正典)與卡文的日文寫法
_RACE_BITS = {"戦士族": 0x1, "魔法使い族": 0x2, "天使族": 0x4, "悪魔族": 0x8, "アンデット族": 0x10,
              "機械族": 0x20, "水族": 0x40, "炎族": 0x80, "岩石族": 0x100, "鳥獣族": 0x200,
              "植物族": 0x400, "昆虫族": 0x800, "雷族": 0x1000, "ドラゴン族": 0x2000, "獣族": 0x4000,
              "獣戦士族": 0x8000, "恐竜族": 0x10000, "魚族": 0x20000, "海竜族": 0x40000,
              "爬虫類族": 0x80000, "サイキック族": 0x100000, "幻神獣族": 0x200000,
              "創造神族": 0x400000, "幻竜族": 0x800000, "サイバース族": 0x1000000,
              "幻想魔族": 0x2000000}
_RACE = re.compile("|".join(sorted(_RACE_BITS, key=len, reverse=True)))
_ATTR_BITS = {"地": 0x1, "水": 0x2, "炎": 0x4, "風": 0x8, "光": 0x10, "闇": 0x20, "神": 0x40}
_ATTRIBUTE = re.compile(r"((?:[地水炎風光闇神]・)*[地水炎風光闇神])属性")
_MONSTER_TYPE_BITS = {"融合": 0x40, "シンクロ": 0x2000, "S": 0x2000, "エクシーズ": 0x800000,
                      "X": 0x800000, "リンク": 0x4000000, "L": 0x4000000, "儀式": 0x80,
                      "ペンデュラム": 0x1000000, "P": 0x1000000, "通常": 0x10, "効果": 0x20,
                      "トゥーン": 0x400000, "スピリット": 0x200, "ユニオン": 0x400,
                      "デュアル": 0x800, "リバース": 0x200000, "チューナー": 0x1000}
_MONSTER_TYPE_ALT = "|".join(sorted(_MONSTER_TYPE_BITS, key=len, reverse=True))
_MONSTER_TYPES = re.compile(r"((?:(?:%s)・?)+)モンスター|チューナー" % _MONSTER_TYPE_ALT)
_SPELL_TYPE_BITS = {"速攻": 0x10000, "永続": 0x20000, "装備": 0x40000, "フィールド": 0x80000,
                    "儀式": 0x80}
_TRAP_TYPE_BITS = {"永続": 0x20000, "カウンター": 0x100000}
_SPELL_TRAP_TYPES = re.compile(r"(通常|速攻|永続|装備|フィールド|儀式|カウンター)(魔法|罠)")
_NUMERIC = re.compile(r"(レベル|ランク|リンク|攻撃力|守備力)が?([0-9０-９]+)(以上|以下|未満)?")
XYZ_BIT, LINK_BIT = 0x800000, 0x4000000

# 修飾語:最後一個述語或關係詞之前都是別的東西的條件(〜を素材とした、〜以外の、〜と同じ)
_MODIFIER = re.compile(r"^.*(?:した|する|された|される|されて|している|となる|とする|を含む|と同じ"
                       r"|異なる|持つ|以外の|より|いる|ある|ない)")
_ALTERNATIVE = re.compile(r"または|か|や|及び|および|と")
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
            if types & 0x1000:
                return False
            continue
        names = re.findall(_MONSTER_TYPE_ALT, m.group(1))
        if types & 0x1 and any(types & _MONSTER_TYPE_BITS[n] for n in names):
            return False
    for m in spell_trap:
        name, kind = m.groups()
        bits = _SPELL_TYPE_BITS if kind == "魔法" else _TRAP_TYPE_BITS
        kind_bit = 0x2 if kind == "魔法" else 0x4
        if not types & kind_bit:
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
    if kinds is not None and not kinds & face_kinds(face):
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


def _all_class(text, frame, where, face):
    """全部類:→ (值, 理由)。"""
    zones = _group_zones(text, frame)
    possible, _ = where
    # 靈擺區在場上:群體寫場上時含靈擺區的此卡
    near = [(player, zone) for player, zone in zones
            if zone in possible or (OFF_FIELD in possible and zone != FIELD)
            or (zone == FIELD and PENDULUM_ZONE in possible)]
    if zones and not near:
        return NONSELF, WHY_ALL_ZONE
    if near and all(player == PLAYER_OPP for player, _ in near):
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
    if core.endswith(_NOT_CARD_HEADS):
        return "not_card"
    if core.endswith(_VALUE_HEADS):
        return "value"
    if core.endswith(_EFFECT_HEADS):
        return "effect"
    if core.endswith(_CARD_HEADS):
        return "card"
    return "unknown"


def _card_group(text, clause, all_class):
    """受事者是卡(或屬性的主人):→ (值, 理由)。"""
    if _ATTACHED.search(text):
        return NONSELF, WHY_ATTACHED
    if _DEMONSTRATIVE.search(text) or _COUNT.search(text) or (
            _CLAUSE_COUNT.search(clause) and not _ALL_OF_THEM.search(clause)):
        return NONSELF, WHY_SELECTED
    return all_class(text) if all_class else (None, WHY_ALL)


def classify(text, clause="", all_class=None):
    """受事者字面(與它所在子句的字面,數量可能只寫在子句裡)→ (值, 理由);all_class 是
    全部類的判定(群體字面 → (值, 理由)),沒給時全部類一律皆非。"""
    if not text:
        return None, WHY_NONE
    why = self_rule(text)
    if why:
        return SELF, why
    if _OTHER_THAN_SELF.search(text):
        return NONSELF, WHY_OTHER_THAN_SELF
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
        if _DEMONSTRATIVE.search(text):
            return NONSELF, WHY_SELECTED
        found = _ATTRIBUTE_TAIL.match(_core(text))
        owner = found.group(1) if found else ""
        if not owner or head_kind(owner) != "card":
            return None, WHY_NO_OWNER
        return _card_group(owner, clause, all_class)
    return _card_group(text, clause, all_class)


class Verdict:
    """一個框架的判定:值、理由、受事者字面,以及全部類用到的發動位置來源(其餘 None)。"""
    __slots__ = ("mode", "why", "text", "launch")

    def __init__(self, mode, why, text="", launch_source=None):
        self.mode, self.why, self.text, self.launch = mode, why, text, launch_source


def judge(frame, where=None, face=None):
    """一個動作框架(與它所在效果句的發動位置、此卡卡面參數)→ Verdict。"""
    text, by_topic = patient(frame)
    where = where or ({FIELD}, LAUNCH_DEFAULT)
    used = []

    def all_class(group):
        used.append(where[1])
        return _all_class(group, frame, where, face)
    mode, why = classify(text, _clean(frame.get("clause")), all_class)
    if by_topic and why == WHY_PATIENT:
        why = WHY_TOPIC
    return Verdict(mode, why, text, used[0] if used else None)


def judge_sentence(frames, face=None, section="main"):
    """一句效果句的框架清單(與此卡卡面參數,沒有時不比卡面;段落)→ 與它對齊的 [Verdict];
    約束框架是 Verdict(None, None)。"""
    where = launch(frames, section)
    return [judge(fr, where, face) if fr.get("kind") == KIND_ACTION else Verdict(None, None)
            for fr in frames]
