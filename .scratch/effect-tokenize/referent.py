# -*- coding: utf-8 -*-
"""受事者字面的共用小表(named-queries code review 修正,2026-11-01):[[回指]](anaphora.py)與[[動作對象]]
(patient.py)原本各抄一份的指示詞起頭、此卡、事件詞、素材、元々、不是回指的名詞、關係詞,與回指欄 via 的四個值,
收成這一份;兩邊(與讀 via 的 regions/agent)import。

值的來源:action-patient-anaphora 票 01〜04 與 action-patient 的判定規則;2026-11-01 規格 2(named-queries 票 03/04)
改讀片語時從正則式收成表。量詞在 phrases.py(QUANTITY_COUNTERS 那一張)、玩家/區域在 places.py、中心詞類與修飾語類
在 closed_values.py,這裡不抄。沒有正則式;兩邊各自的判定規則(主人、候選、全部類)留在各自的模組。

接縫:clean(字面) 去空白;opener_of(字面) → 段首的指示詞字面 | None;is_demonstrative(字面) → 是不是指示詞起頭
(それ/それら 只在單獨或接 の 時算;それぞれ 不是)。
"""
import phrases

THIS_CARD = "このカード"
# 回指欄的 via:找到目標的方法(対象とする 框架、往前的框架欄位、字面備援片語、事件框架)
VIA_TARGET, VIA_FIELD, VIA_LITERAL, VIA_EVENT = "対象", "欄位", "字面", "事件"
# 指示詞字面(2026-11-01 規格 2 裁定收表):段首的 それら/それ/その 是片語模組認的那三個(phrases.DEMONSTRATIVE_WORDS),
# 加 対象の/この効果の対象(找該效果的 対象とする 框架);長的在前,逐一比起頭
TARGETED_PREFIXES = ("対象の", "この効果の対象")
DEMONSTRATIVE_OPENERS = tuple(sorted(phrases.DEMONSTRATIVE_WORDS, key=lambda w: (-len(w), w))) + TARGETED_PREFIXES
PRONOUNS = ("それ", "それら")                              # 指示代名詞:自己就是被指的卡;それら 複數
PRONOUN_PLURAL = PRONOUNS[1]
TARGET_WORD = "対象"                                      # この効果の対象 的中心詞;対象のモンスター 的第一個修飾語
WITHIN = "内"                                             # その内の1枚:目標是前面確認的區域/群,複數
ORIGINAL = "元々"                                         # 元々の攻撃力 的 元々 不是主人、也是屬性的一部分
CARD_SUFFIX = "カード"                                    # 魔法カード 的 魔法 是卡種
MATERIAL = "素材"                                         # X素材 的中心詞;融合素材 的 融合 不算卡片子類型
# 跟主人走的事件詞:屬性類中心詞裡的 発動/効果/攻撃/〜召喚;不當限定語
EVENT_WORDS = ("発動", "効果", "攻撃", "召喚")
# 指示詞綁的是時間、程度、數值的名詞(その時の、その中の、その同名カード):指示詞只修飾另一張卡,不是回指
NON_REFERENCE_NOUNS = ("時", "中", "後", "度", "まま", "差", "同名")
RELATIONAL_WORDS = ("以外", "同名")                        # 段裡的關係詞:そのモンスター以外の、その同名カード


def clean(text):
    """去掉字面裡的空白(frames.json 的字面欄與子句帶分詞空白)。"""
    return "".join((text or "").split())


def opener_of(text):
    """字面(段、修飾語、切區域後的欄位)起頭的指示詞字面;沒有就 None。"""
    for opener in DEMONSTRATIVE_OPENERS:
        if text.startswith(opener):
            return opener
    return None


def is_demonstrative(text):
    """字面是不是指示詞起頭:その/対象の/この効果の対象 起頭,或 それ/それら 單獨、接 の(それぞれ、それと 不算)。"""
    text = clean(text)
    opener = opener_of(text)
    if opener in PRONOUNS:
        return text == opener or text.startswith(opener + "の")
    return opener is not None
