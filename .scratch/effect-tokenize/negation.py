# -*- coding: utf-8 -*-
"""否定形(frame-args-v4 票 08)。

mark(ctx, tokens, frame):極性 否定 的動作框架加 frame["negation"](closed_values.NEGATION_FORMS 之一):
態 受身 → 受身;否則看子句裡述語自己的否定形(LITERAL_FORMS,取最後一個命中的):にならない/受けない 系
→ 不成不受、できない/出来ない/行えない 系 → 不可能、其餘(ず/ない/なく)→ 一般。〜ければならない 的
ならない 不是否定述語(受身優先於字面;定語裡的 受けない/できない 不改被動否定)。極性 肯定/可能 的框架
不帶此欄。

目錄的耐性/限制(catalog.NEGATION_LABEL)讀這一欄:受身/不成不受 → 耐性、不可能 → 限制。
這裡不 import frames(循環 import)。
"""
import re

from action_lemmas import VOICE_PASSIVE
from closed_values import NEGATION_FORMS
from constraints import POL_NEG
from report import count_by_position, position_table

PASSIVE, NOT_BECOME, CANNOT, GENERAL = NEGATION_FORMS

# 子句字面(去空白)裡的否定述語形 → 否定形;受けない 字面是一般否定,但 受ける 的否定就是不受影響,
# 歸 不成不受;行えない 是五段動詞 行う 的可能否定;(?<!ば)なら 排除 〜ければならない(義務)。
LITERAL_FORMS = (
    (re.compile(r"(?:でき|出来)(?:ない|ず|なく|ませ)|行え(?:ない|ず|なく)"), CANNOT),
    (re.compile(r"(?:(?<!ば)なら|受け)(?:ない|ず|なく)"), NOT_BECOME),
)


def literal_form(clause):
    """子句字面 → 不成不受/不可能/一般:取最後一個命中的否定述語形(框架的子句收在它自己的述語),
    都沒有就是一般否定。"""
    text = clause.replace(" ", "")
    last, found = -1, GENERAL
    for pattern, form in LITERAL_FORMS:
        for m in pattern.finditer(text):
            if m.end() > last:
                last, found = m.end(), form
    return found


def form_of(frame):
    """框架 → 否定形;極性不是否定時 None。"""
    if frame["polarity"] != POL_NEG:
        return None
    if frame.get("voice") == VOICE_PASSIVE:
        return PASSIVE
    return literal_form(frame["clause"])


def mark(ctx, tokens, frame):
    form = form_of(frame)
    if form is not None:
        frame["negation"] = form


def fill_state(frame):
    """報告填充率的狀態:有否定形就是 有值。"""
    return "有值" if frame.get("negation") else None


def count_section(records):
    """報告小節「否定形各值框數」:四值 × 位置(代價/效果/條件)的動作框架數。"""
    lines = ["只在極性 否定 的動作框架上有值(受身=態 受身;不成不受=にならない/受けない;不可能=できない/"
             "行えない;一般=其餘 ず/ない/なく)。", ""]
    return lines + position_table(count_by_position(records, "negation"), NEGATION_FORMS, "否定形")


FILL_RATE_ROWS = [("否定形 negation", fill_state)]
REPORT_SECTIONS = [("否定形各值框數", count_section)]


def batch_cells(frame):
    """批次檔的格(llm_check.py 經 enrich.batch_cells 讀):否定形=X,只在否定框架上有。"""
    return ["否定形=%s" % frame["negation"]] if frame.get("negation") else []
