"""「〜として扱う」句的修飾段:抽取與句型模板成對放在一起。

句子本身的解析與字面在 `names_attributes`(同一句也寫進卡片屬性表);這裡把它記成對象線是此卡的修飾段。
"""

from block_state import KIND_MODIFIER, segment_at
from names_attributes import REASON_NAME_UNKNOWN, TREAT_PREDICATE, render_treat_as
from structure_shape import NoTemplate, new_line, unparsed


def treat_as_segment(state, start, end, treat):
    """「〜として扱う」句 → 修飾段(卡片屬性表的列由 names_attributes 另記):被改的屬性是卡名/字段
    (名稱換成名稱列 id)或大類/子類型,述語字面 として扱う,對象線是此卡。"""
    seg = segment_at(state, KIND_MODIFIER, start, end)
    seg["predicate"], seg["voice"] = TREAT_PREDICATE, "主動"
    seg["lines"] = [new_line(state.self_id, "受事", marker="は")]
    modified = dict(treat)
    if "items" in modified:
        items = []
        for item in modified["items"]:
            row = state.names.get(item["text"])
            if row is None:
                seg["unparsed"] = unparsed(REASON_NAME_UNKNOWN)
                return seg
            items.append({"name": row["id"], "tail": item["tail"]})
        modified["items"] = items
        # 「X」後接 カード/モンスター 的是字段,否則是卡名(與 names_attributes 同一把尺)。
        tails = [i["tail"] for i in items[:-1]] + [items[-1]["tail"] or modified.get("suffix")]
        modified["attr"] = "字段" if any(tails) else "卡名"
    seg["modified"] = modified
    return seg


def render_treat_as_segment(seg, names, objects, self_id):
    """修飾段(票 09):「〜として扱う」句由 names_attributes.render_treat_as 從被改的屬性拼回;
    對象線只能是此卡、沒有動作詞。"""
    if (seg["actions"] or seg["predicate"] != TREAT_PREDICATE or not seg["modified"]
            or len(seg["lines"]) != 1 or seg["lines"][0]["object"] != self_id):
        raise NoTemplate("修飾段的格不齊")

    def name_text(name_id):
        row = names.get(name_id)
        if row is None or row["unparsed"]:
            raise NoTemplate("修飾段引用的名稱列找不到或不認得")
        return row["text"]

    return render_treat_as(seg["modified"], name_text)
