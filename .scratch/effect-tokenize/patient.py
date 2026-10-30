# -*- coding: utf-8 -*-
"""[[動作對象]]判定(.scratch/action-patient):一句效果句的動作框架 → 每個框架動到的是
不是此卡本身。

接在框架抽取之後、由類別匯出(export_categories.py)呼叫;框架抽取的受事者取法不改,
判定在它的結果上加規則。值是 此卡(SELF)、非此卡(NONSELF),或 None(皆非:兩種模式
都不中)。

受事者依態取:他動(與沒判態的)取對象,自動/受身取主語、沒有時取主題;對象空著而主題
(含句內延續的主題)以此卡收尾時,主題就是受事者,不分動作。
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
WHY_NONE = "沒有受事者"
WHY_OTHER = "其他"

_SPACES = re.compile(r"\s+")
# 此卡的屬性(このカードの攻撃力・守備力、この効果で特殊召喚したこのカードのレベル):
# 屬性跟著此卡走;效果、發動、召喚、攻擊也是屬性(受事者是效果、發動時跟著主人走)。
# 裝備怪獸、X 素材、カウンター、リンク先 不在表上——那是另一張實體卡或別的東西
_ATTRIBUTES = ("攻撃力", "守備力", "レベル", "ランク", "Pスケール", "効果", "発動", "攻撃",
               "召喚", "特殊召喚", "属性", "種族", "カード名", "表示形式", "コントロール", "位置")
_ATTR = "(?:元々の)?(?:%s)" % "|".join(_ATTRIBUTES)
_ATTRIBUTE_OF_SELF = re.compile(
    r"%sの+%s(?:(?:・|と|及び|および)%s)*$" % (THIS_CARD, _ATTR, _ATTR))
# 並列含此卡:このカードと〜、このカード及び〜(〜とこのカード 以此卡收尾,已算);
# このカードと同じ縦列、このカードとは種族が異なる 這類比較不是並列
_LISTED_WITH_SELF = re.compile(r"^%s(?:と|及び|および|や|または|か)(?!同じ|同名|は|相互|リンクし|"
                               r"リンク状態|戦闘|\(共同\)|異なる|元々)" % THIS_CARD)
_INCLUDING_SELF = THIS_CARD + "を含む"


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


def judge(frame):
    """一個動作框架 → (SELF/NONSELF/None, 理由)。"""
    text, by_topic = patient(frame)
    if not text:
        return None, WHY_NONE
    why = self_rule(text)
    if why:
        return SELF, WHY_TOPIC if by_topic and why == WHY_PATIENT else why
    return None, WHY_OTHER


def judge_sentence(frames):
    """一句效果句的框架清單 → 與它對齊的 [(值, 理由)];約束框架是 (None, None)。"""
    return [judge(fr) if fr.get("kind") == KIND_ACTION else (None, None) for fr in frames]
