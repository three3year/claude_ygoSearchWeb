"""性質變更句(「その攻撃力は〜倍になる」「Xの攻撃力は〜アップする」)的段:主語的解析、
填格(`fill_clause`)與句型模板(`render_clause`)成對放在一起。

被改的屬性與值的字面在 `segment_fields.parse_modify`、`render_modify`;這裡把主語(回指字面,或
「[區域の][全ての]物件短語の」)解成對象線。裝備段衍生的性質變更段(「攻撃力３００アップの装備カード
扱いで」)也在這裡(`derived_segment`、`render_derived`)。
"""

import re

from block_state import segment_at
from clause_front import front_duration
from object_boundary import find_cut
from object_render import render_object
from segment_fields import (MENTION_FORMS, is_delayed, mention_head, parse_modify,
                            parse_treat_delta, render_modify, render_treat_delta)
from simple_clause import render_from
from structure_shape import (REASON_OBJECT, REASON_REF, REASON_TWICE, NoTemplate, new_line,
                             position, unparsed)
from synonyms import MODIFY_ACTION
from zone_phrase import ZONE_PHRASE, parse_from


# 性質變更句的主語:「[區域の][全ての]物件短語の」;區域照簡單子句記成對象線的從,
# 「全ての」記成對象線的數量(屬於這次提及)。
_MODIFY_SUBJECT_RE = re.compile(
    f"^(?:(?P<from>{ZONE_PHRASE})の)?(?P<all>全ての)?(?P<phrase>.+)の$")
ALL_PREFIX = "全ての"


def _modify_subject(subject, marker, state, sentence_start):
    """性質變更句的主語 → (對象線, None) 或 (None, 原因)。回指字面(その、このカードの、
    そのモンスターの…)照舊記在 `ref`;其餘是「物件短語 + の」,物件照一般規則解析。"""
    if subject in MENTION_FORMS:
        head = mention_head(subject)
        obj_id = state.self_id if head is None else state.recent_of(head)
        if obj_id is None:
            return None, REASON_REF
        return new_line(obj_id, "受事", marker=marker, ref=subject), None
    m = _MODIFY_SUBJECT_RE.match(subject)
    if not m:
        return None, REASON_OBJECT
    from_zones = parse_from(m.group("from")) if m.group("from") else None
    phrase = m.group("phrase")
    if m.group("from") and from_zones is None:
        phrase = subject[:-1]
        if m.group("all"):
            return None, REASON_OBJECT
    obj_id, ref, reason = state.object_at(phrase, sentence_start)
    if obj_id is None:
        return None, reason
    count = {"text": ALL_PREFIX, "cmp": "全部"} if m.group("all") else None
    line = new_line(obj_id, "受事", marker=marker, ref=ref, count=count)
    if from_zones is not None:
        line["from"] = position(from_zones, "明寫", text=m.group("from") + "の")
        obj = state.find(obj_id)
        if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
            obj["initial_position"] = list(from_zones)
    return line, None


def swallowed_front(state, clause):
    """性質變更句的主語往前吞進了多少不屬於它的字面(從子句開頭起算的字數;0 = 沒有),判法同
    `simple_clause.swallowed_front`:「ダメージステップの間このカードの攻撃力は〜」的主語是このカード。"""
    modify = parse_modify(clause)
    subject = modify and modify["subject"]
    if not subject or subject in MENTION_FORMS or not clause.startswith(subject):
        return 0
    mention = next((form for form in sorted(MENTION_FORMS, key=len, reverse=True)
                    if subject.endswith(form)), None)
    if mention:
        # 「ターン終了時までその攻撃力は」:回指字面前面整截要正好在切點結束。
        front = subject[:-len(mention)]
        return len(front) if find_cut(front + "カード") == len(front) else 0
    m = _MODIFY_SUBJECT_RE.match(subject)
    if not m or state.parses_cleanly(m.group("phrase")):
        return 0
    whole = subject[:-1]
    cut = find_cut(whole)
    return cut if cut and state.names_object(whole[cut:]) else 0


def fill_clause(ctx, clause):
    """性質變更句(「その攻撃力は〜倍になる」)→ 填格回 True;不是這個句型回 False。
    段上可能已有子句前文填好的期間、時機(`clause_front`),句中沒寫才沿用。"""
    modify = parse_modify(clause)
    if modify is None:
        return False
    seg, state = ctx.seg, ctx.state
    line, reason = _modify_subject(modify["subject"], modify["marker"], state, ctx.sentence_start)
    if line is None:
        seg["unparsed"] = unparsed(reason)
        return True
    seg["actions"] = [MODIFY_ACTION]
    seg["predicate"], seg["voice"] = modify["predicate"], "主動"
    seg["modified"] = modify["modified"]
    if modify["duration"] and front_duration(seg["duration"]):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return True
    seg["duration"] = modify["duration"] or seg["duration"]
    if seg["timing"] is None:
        ctx.inherit_timing()
    line["targeting"] = line["object"] in state.targeted and not is_delayed(seg)
    seg["lines"] = [line]
    return True


def derived_segment(seg, state):
    """「攻撃力３００アップの装備カード扱いで〜に装備する」的裝備段 → 衍生的性質變更段:
    範圍是 treat 字面裡的「攻撃力３００アップ」、記 `derived_from` = 裝備段、對象線是裝備的對象
    (裝備段的受方物件);與裝備段同時。沒有增減前綴、或受方不是物件時回 None。"""
    recipient = seg["recipient"]
    if seg["unparsed"] or not isinstance(recipient, dict) or "object" not in recipient:
        return None
    treats = [((line["to"] or {}).get("form") or {}).get("treat") for line in seg["lines"]]
    delta = next((parse_treat_delta(t["text"]) for t in treats if t), None)
    if delta is None:
        return None
    literal, modified, predicate = delta
    start = seg["span"][0] + seg["text"].index(literal)
    derived = segment_at(state, "效果", start, start + len(literal))
    derived.update(actions=[MODIFY_ACTION], predicate=predicate, voice="主動",
                   modified=modified, derived_from=seg["id"],
                   lines=[new_line(recipient["object"], "受事")])
    return derived


def render_clause(t):
    """性質變更句:[主語][屬性]は[期間][值]述語(期間是段的句中期間 `t.inner_duration`);
    主語是回指字面(對象線的 ref,物件0 是「このカードの」),或「[從の][全ての]物件の」。"""
    seg, card, objects, names, self_id = t.seg, t.card, t.objects, t.names, t.self_id
    if len(seg["lines"]) != 1 or seg["actions"] != [MODIFY_ACTION] or not seg["modified"]:
        raise NoTemplate("性質變更段的格不齊")
    line = seg["lines"][0]
    obj = objects.get(line["object"])
    if obj is None or line["role"] != "受事" or line["to"]:
        raise NoTemplate("性質變更段的格不齊")
    mention = line["ref"]
    if mention in MENTION_FORMS:
        if (line["object"] == self_id) != (mention == "このカードの") or line["from"] \
                or line["count"]:
            raise NoTemplate("性質變更段的提及與物件不符")
        subject = mention
    else:
        count = line["count"]
        if count and count != {"text": ALL_PREFIX, "cmp": "全部"}:
            raise NoTemplate("性質變更段的數量無模板")
        from_text, _ = render_from([line])
        subject = (from_text + (ALL_PREFIX if count else "")
                   + render_object(obj, seg, card, names, line, self_id=self_id) + "の")
    return render_modify(subject, line["marker"], seg["modified"],
                         t.inner_duration, seg["predicate"])


def render_derived(t):
    """衍生的性質變更段(「攻撃力３００アップの装備カード扱いで」):不另寫一句,
    只寫回它在 treat 字面裡的範圍「[屬性][差量]アップ」;其餘格要空。"""
    seg = t.seg
    if (seg["actions"] != [MODIFY_ACTION] or not seg["modified"] or len(seg["lines"]) != 1
            or seg["lines"][0]["role"] != "受事" or seg["lines"][0]["ref"]
            or any(seg[slot] for slot in ("agent", "recipient", "cause", "duration", "timing",
                                          "trigger", "premise", "amount", "replaces"))):
        raise NoTemplate("衍生的性質變更段的格不齊")
    return render_treat_delta(seg["modified"], seg["predicate"])
