"""舊式反轉效果的標示「リバース：X」(站主裁定)。

「リバース：」等於新式的「このカードがリバースした場合、」:標示自己切成一個條件段——動作詞 反轉、
物件是此卡(原文沒寫,對象線標省略)、觸發形 場合(照官方再錄的寫法)、原述語字面記「リバース：」;
X 照一般的句子解析。標示後面的效果段就是這個效果本身,不因前面有條件段而算延遲:標示段在
`segment_extract.parse_sentence` 判延遲之前就切走,取對象等標記照一般效果段。
觸發形記「場合」但原文沒有這兩個字,所以反向檢查看到這個原述語字面就寫回「リバース：」(`render_label`)。
"""
from block_state import segment_at
from structure_shape import NoTemplate, new_line
from synonyms import FLIP_ACTION, FLIP_STEM

FLIP_LABEL = FLIP_STEM + "："
FLIP_TRIGGER = "場合"


def label_segment(state, start, end):
    if not state.block["text"].startswith(FLIP_LABEL, start, end):
        return None
    seg = segment_at(state, "條件", start, start + len(FLIP_LABEL))
    seg.update(actions=[FLIP_ACTION], trigger=FLIP_TRIGGER, predicate=FLIP_LABEL, voice="主動")
    line = new_line(state.self_id, "受事")
    line["elided"] = True
    seg["lines"] = [line]
    return seg


def is_label(seg):
    return seg["predicate"] == FLIP_LABEL


def render_label(t):
    seg = t.seg
    if ((seg["kind"], seg["actions"], seg["trigger"], seg["voice"])
            != ("條件", [FLIP_ACTION], FLIP_TRIGGER, "主動")
            or [(line["object"], line.get("elided")) for line in seg["lines"]] != [(t.self_id, True)]):
        raise NoTemplate("反轉標示的格無模板")
    return FLIP_LABEL
