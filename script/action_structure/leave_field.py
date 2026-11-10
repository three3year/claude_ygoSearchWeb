"""離場的兩個句型:抽取端的切點與反向檢查的模板成對放在一起。

動作詞 離場(「フィールド(上)から離れた」)本身是簡單子句:字幹在 `synonyms`(連「フィールドから」一起寫,
出發地 場上 由述語寫明)。這裡管的是觸發形後面直接接另一截(多半沒有讀點)、一句要切成兩段的寫法:
- 連動「Xがフィールドから離れた時に Yは破壊される」:在「時に」切成條件段(離場)加效果段。主語用「が」、
  觸發形是 時/場合、「離れた」「離れる」都收。有讀點的「〜離れた時、Yを破壊する」本來就是舊式條件句。
- 自我限制「(Xは、)フィールドから離れた場合に除外される」「〜デッキの一番下に戻る」:去處被換掉,照代替記——
  離場是被代替段,後面那截(沒有自己的主語)是做代替的段、記 `replaces`。文面沒有「代わりに」,
  做代替的段另有模板(`render_destination`)。主語省略時(「〜し、フィールドから離れた場合に除外される」)
  要有本句的「Xは」可承,沒有就不切、不退回此卡。
"""
import re
from typing import NamedTuple

import simple_clause
from block_state import TOPIC_NONE
from segment_fields import split_duration
from segment_history import previous_segment
from structure_shape import NoTemplate
from synonyms import ACTIVATION_SUFFIXES, LEAVE_ACTION, LEAVE_STEMS

KIND_CONDITION, KIND_REPLACED = "條件", "被代替"
_LEAVE = f"(?:{'|'.join(LEAVE_STEMS)})"
RESTRICTION_TRIGGER = "場合"
# 觸發形與後一截之間的字面(段外的接著詞):「場合に」「時に」的「に」、讀點。
_GLUE = "(?:に、?|、)?"
# 連動:「Xが(原因)フィールドから離れた/離れる 時|場合(に)」+ 後面的子句。條件子句裡沒有讀點。
_LINKED_RE = re.compile(
    f"^(?P<cond>[^、。]+が[^はが、。]*{_LEAVE}(?:た|る))(?P<trig>時|場合){_GLUE}(?P<rest>.+)$")
# 自我限制:「(Xは、?)(原因)フィールドから離れた」;「は」是離場子句前最後一個主題助詞。
_RESTRICTION_COND_RE = re.compile(
    f"^(?:(?P<topic>.+は)、?)?[^はが、。]*{_LEAVE}た$")
# 去處那一截沒有自己的主語與受詞(「除外される」「ゲームから除外される」「持ち主のデッキの一番下に戻る」)。
_DESTINATION_RE = re.compile("^[^はがを、。]+$")
_RESTRICTION_RE = re.compile(
    f"^(?P<cond>.*?{_LEAVE}た)(?P<trig>{RESTRICTION_TRIGGER}){_GLUE}(?P<rest>.+)$")


class LeaveSplit(NamedTuple):
    """離場子句後面直接接另一截的切法:條件子句、觸發形、後一截的起點(相對於子句)、是不是自我限制。"""
    cond: str
    trigger: str
    rest_start: int
    replaced: bool

    @property
    def kind(self):
        return KIND_REPLACED if self.replaced else KIND_CONDITION


def is_self_restriction(state, cond, trigger, rest):
    """「(Xは、)フィールドから離れた」+ 場合 + 沒有自己主語的去處:去處被換掉(照代替記)。
    有讀點的「〜離れた場合、ゲームから除外される」由舊式條件句切開後也用這一把尺。
    離場子句的主語省略、而本句沒有「Xは」可承時不算(主語省略的子句會退回此卡,這裡不猜)。"""
    leaving = _RESTRICTION_COND_RE.match(cond)
    if trigger != RESTRICTION_TRIGGER or not leaving or not _DESTINATION_RE.match(rest):
        return False
    return (leaving.group("topic") is not None or state.subject is not None
            or state.topic.state != TOPIC_NONE)


def split_clause(state, clause):
    """效果子句以離場子句開頭、觸發形後直接接另一截 → `LeaveSplit`;不是回 None。"""
    m = _RESTRICTION_RE.match(clause)
    if m and is_self_restriction(state, m.group("cond"), m.group("trig"), m.group("rest")):
        return LeaveSplit(m.group("cond"), m.group("trig"), m.start("rest"), True)
    m = _LINKED_RE.match(clause)
    # 句尾帶括號注記的發動句(「〜離れた場合に発動できる（ダメージステップでも発動可能）」)不是這個句型。
    if m and not m.group("rest").startswith(ACTIVATION_SUFFIXES):
        return LeaveSplit(m.group("cond"), m.group("trig"), m.start("rest"), False)
    return None


def replaced_leave(seg, card):
    """這一段是自我限制句裡做代替的段(去處)時,回它代替的離場段;不是回 None。
    只看結構:它代替的是緊接在前面、動作詞只有離場的被代替段。"""
    if not seg["replaces"]:
        return None
    replaced = previous_segment(seg, card)
    if (replaced is None or replaced["id"] != seg["replaces"]
            or replaced["kind"] != KIND_REPLACED or replaced["actions"] != [LEAVE_ACTION]):
        return None
    return replaced


def render_destination(seg, card, objects, names, self_id):
    """做代替的段(去處)的模板:沒有「代わりに」,只有主語省略的子句本體(「除外される」「デッキの一番下に戻る」)。
    省略的主語要是被代替段裡離場的那個物件;這個句型沒有寫前提、期間的位置(前提與句首期間的字面都在
    被代替段上,這一段只能有沒有字面的期間:承襲的本回合、「〜限り、」的持續)。"""
    replaced = replaced_leave(seg, card)
    if replaced["trigger"] != RESTRICTION_TRIGGER or replaced["unparsed"]:
        raise NoTemplate("離場的去處無模板:被代替段")
    if seg["premise"] is not None or split_duration(seg["duration"]) != ("", None):
        raise NoTemplate("離場的去處無模板:前提或期間")
    leaving = [line["object"] for line in replaced["lines"]]
    if (len(leaving) != 1 or len(seg["lines"]) != 1 or not seg["lines"][0].get("elided")
            or seg["lines"][0]["object"] != leaving[0]):
        raise NoTemplate("離場的去處無模板:主語不是離場的物件")
    return simple_clause.render_clause(seg, card, objects, names, self_id, None)
