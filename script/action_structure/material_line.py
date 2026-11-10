"""素材行(素材區塊的「「ブラック・マジシャン」＋光・闇属性モンスター」):抽取與句型模板成對放在一起。

一行是一個召喚手續段,沒有動作詞,每個素材一條角色「素材」的對象線;超量素材數「×N」記在對象線的數量。
"""

import re

from block_state import KIND_PROCEDURE, segment_at
from object_render import render_object
from quantity import FULLWIDTH_DIGITS, TO_FULLWIDTH_DIGITS
from structure_shape import NoTemplate, new_line, unparsed


ROLE_MATERIAL = "素材"
MATERIAL_JOINER = "＋"
MATERIAL_TIMES = "×"
_MATERIAL_TIMES_RE = re.compile(f"^(?P<phrase>.+?)(?P<times>{MATERIAL_TIMES}(?P<digits>[０-９]+))$")


def material_segment(state, start, end):
    """素材行(「「ブラック・マジシャン」＋光・闇属性モンスター」)→ 召喚手續段:沒有動作詞,
    每個素材一條角色「素材」的對象線(以「＋」分);素材短語認不得的整段標原因。"""
    seg = segment_at(state, KIND_PROCEDURE, start, end)
    phrase_start = start
    for phrase in seg["text"].split(MATERIAL_JOINER):
        times = _MATERIAL_TIMES_RE.match(phrase)
        count = None
        if times:
            phrase = times.group("phrase")
            count = {"text": times.group("times"), "unit": MATERIAL_TIMES,
                     "value": int(times.group("digits").translate(FULLWIDTH_DIGITS)), "cmp": "="}
        obj_id, ref, reason = state.object_at(phrase, phrase_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return seg
        seg["lines"].append(new_line(obj_id, ROLE_MATERIAL, ref=ref, count=count))
        written = phrase + (times.group("times") if times else "")
        phrase_start += len(written) + len(MATERIAL_JOINER)
    return seg


def render_line(seg, card, names, objects, self_id):
    """素材行:每條角色「素材」的線寫物件全名(超量素材數「×N」接在後面),以「＋」連;
    沒有述語。"""
    if seg["actions"] or seg["predicate"] or seg["kind"] != "召喚手續":
        raise NoTemplate("素材段的格不齊")
    return MATERIAL_JOINER.join(
        render_object(objects[line["object"]], seg, card, names, line, self_id=self_id)
        + _render_material_times(line["count"])
        for line in seg["lines"])


def _render_material_times(count):
    """超量素材數「×N」:對象線 count 單位 ×;沒有就是空字串。"""
    if not count:
        return ""
    if (count.get("unit") != MATERIAL_TIMES or count.get("cmp") != "="
            or not isinstance(count.get("value"), int)):
        raise NoTemplate("素材數量無模板")
    return MATERIAL_TIMES + str(count["value"]).translate(TO_FULLWIDTH_DIGITS)
