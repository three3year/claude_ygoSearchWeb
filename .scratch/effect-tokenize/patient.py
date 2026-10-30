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
- 皆非:受事者不是卡(封閉名詞表)、表外判不出的,以及沒有數量的全部類(本版保守當皆非)。
"""
import re

from constraints import KIND_ACTION

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
WHY_ALL = "全部類"
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
_OTHER_THAN_SELF = THIS_CARD + "以外"
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
# 選擇類:數量(數字+量詞、〜まで)或指示詞
_COUNT = re.compile(r"[0-9０-９]+(?:枚|体|つ|種類|ヵ所|箇所|個)|まで")
_COUNT_TAIL = re.compile(r"(?:[0-9０-９]+(?:枚|体|つ|種類|ヵ所|箇所|個))?(?:まで|以上)?$")
_CARD_COUNT = re.compile(r"[0-9０-９]+(?:枚|体)")
_DEMONSTRATIVE = re.compile(r"^(?:その|それ|対象の|この効果の対象)")
_PAREN_TAIL = re.compile(r"[（(][^（()）]*[)）]$")
_QUOTED = re.compile(r"「[^」]*」")
_ATTRIBUTE_TAIL = re.compile(r"^(.*?)(?:の)*%s$" % _ATTR_LIST)


def _clean(text):
    return _SPACES.sub("", text or "")


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


def _card_group(text, clause):
    """受事者是卡(或屬性的主人):→ (值, 理由)。"""
    if _ATTACHED.search(text):
        return NONSELF, WHY_ATTACHED
    if _DEMONSTRATIVE.search(text) or _COUNT.search(text) or _COUNT.search(clause):
        return NONSELF, WHY_SELECTED
    return None, WHY_ALL


def classify(text, clause=""):
    """受事者字面(與它所在子句的字面,數量可能只寫在子句裡)→ (值, 理由)。"""
    if not text:
        return None, WHY_NONE
    why = self_rule(text)
    if why:
        return SELF, why
    if _OTHER_THAN_SELF in text:
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
        if text.startswith("この"):
            return None, WHY_THIS_EFFECT
        return NONSELF, WHY_OTHERS_EFFECT
    if kind == "value":
        if _DEMONSTRATIVE.search(text):
            return NONSELF, WHY_SELECTED
        found = _ATTRIBUTE_TAIL.match(_core(text))
        owner = found.group(1) if found else ""
        if not owner or head_kind(owner) != "card":
            return None, WHY_NO_OWNER
        return _card_group(owner, clause)
    return _card_group(text, clause)


def judge(frame):
    """一個動作框架 → (SELF/NONSELF/None, 理由, 受事者字面)。"""
    text, by_topic = patient(frame)
    mode, why = classify(text, _clean(frame.get("clause")))
    if by_topic and why == WHY_PATIENT:
        why = WHY_TOPIC
    return mode, why, text


def judge_sentence(frames):
    """一句效果句的框架清單 → 與它對齊的 [(值, 理由, 受事者字面)];約束框架是
    (None, None, "")。"""
    return [judge(fr) if fr.get("kind") == KIND_ACTION else (None, None, "")
            for fr in frames]
