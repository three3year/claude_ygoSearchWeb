"""存在前提的條件子句:句型、填格與句型模板成對放在一起。

- 存在前提:「(容器)の中に(物件)が(あった|ある|存在する)」→ 條件段,物件是容器的子集。
句首的前提(「〜に存在する場合、」「相手ターンに」)是另一回事,在 `premise`。
"""

import re

from object_render import render_object
from structure_shape import NoTemplate, new_line, unparsed


EXIST_WORDS = ("あった", "ある", "存在する", "存在した")
_EXIST_RE = re.compile(
    "^(?P<container>.+?)の中に(?P<objects>.+?)が(?P<pred>" + "|".join(EXIST_WORDS) + ")$")


def fill_clause(ctx, clause_text):
    """存在前提:「(容器)の中に(物件)があった」→ 容器回指線 + 子集物件;不是這個句型回 False。"""
    m = _EXIST_RE.match(clause_text)
    if not m:
        return False
    seg, state, sentence_start = ctx.seg, ctx.state, ctx.sentence_start
    container_id, ref, reason = state.object_at(m.group("container"), sentence_start)
    if container_id is None:
        seg["unparsed"] = unparsed(reason)
        return True
    subset_id, _, reason = state.subset_object(m.group("objects"), container_id,
                                               sentence_start)
    if subset_id is None:
        seg["unparsed"] = unparsed(reason)
        return True
    seg["predicate"] = m.group("pred")
    seg["lines"] = [new_line(container_id, "受事", ref=ref),
                    new_line(subset_id, "受事")]
    seg["premise"] = {"op": "存在", "object": subset_id, "in": container_id}
    return True


def render_clause(seg, premise, card, objects):
    """存在前提(帶容器 `in`):「(容器回指)の中に(子集全名)が(あった)」。"""
    if premise.get("op") != "存在" or seg["actions"] or seg["kind"] != "條件":
        raise NoTemplate(f"前提無模板:{premise.get('op')}")
    if seg["predicate"] not in EXIST_WORDS:
        raise NoTemplate("存在述語無模板")
    container = next((l for l in seg["lines"] if l["object"] == premise.get("in")), None)
    if container is None or premise.get("object") not in objects:
        raise NoTemplate("存在前提缺容器或子集")
    inner = objects[premise["object"]]
    names = {row["id"]: row for row in card["names"]}
    return (render_object(objects[container["object"]], seg, card, names, container)
            + "の中に" + render_object(inner, seg, card, names, with_count=False)
            + "が" + seg["predicate"])
