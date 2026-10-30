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
WHY_NONE = "沒有受事者"
WHY_OTHER = "其他"

_SPACES = re.compile(r"\s+")


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
    if topic.endswith(THIS_CARD):
        return topic, True
    return "", False


def judge(frame):
    """一個動作框架 → (SELF/NONSELF/None, 理由)。"""
    text, by_topic = patient(frame)
    if not text:
        return None, WHY_NONE
    if text.endswith(THIS_CARD):
        return SELF, WHY_TOPIC if by_topic else WHY_PATIENT
    return None, WHY_OTHER


def judge_sentence(frames):
    """一句效果句的框架清單 → 與它對齊的 [(值, 理由)];約束框架是 (None, None)。"""
    return [judge(fr) if fr.get("kind") == KIND_ACTION else (None, None) for fr in frames]
