"""素材寫在召喚的句子裡(m3 票 09):句型、填格(`fill_clause`)與句型模板(`render_clause`)成對放在一起。

- 「Xを融合素材とし、Yを融合召喚する」(融合魔法的標準寫法)、「Xを素材として(このカードが)融合召喚に成功した」
  「このカードがXを素材としてX召喚した」「Xのみを素材としてS召喚する」→ 一個召喚段:X 是角色 素材 的對象線,
  被召喚的那一方(寫了才有)是角色 被召喚 的線;不另成 作為素材 的段。
- 素材字面(「融合素材とし、」「素材として」「S素材として」)記在段的原因 `{"kind": 作為素材, "text", "summon"}`;
  「Xのみを」的「のみ」記進素材線的助詞字面。
- 對象線照原文順序排:素材線在前是「Xを素材として…」,被召喚的線在前是「このカードがXを素材として…」。
- 素材那一截以外的字面就是一個完整的子句,交給簡單子句;只剩述語的(「…を素材としてS召喚する」)沒有被召喚的線
  ——叫出來的不是此卡,文面沒寫是誰。
"""

import re

import simple_clause
from block_state import ClauseContext, REASON_CLAUSE, REASON_TWICE
from material_line import ROLE_MATERIAL
from object_render import render_object
from predicate_literal import check_predicate
from segment_fields import (CAUSE_MATERIAL, MATERIAL_FORMS, is_delayed, parse_cause,
                            resolve_polarity)
from segment_history import targeted_earlier
from structure_shape import NoTemplate, new_line, position, unparsed
from synonyms import BARE_SUMMON_STEM, is_summon, merged_voice, parse_predicates
from zone_phrase import ZONE_PHRASE, parse_from

# 連用形的素材字面(融合魔法的「〜を融合素材とし、」):字面含讀點,後面接召喚的子句。
# `clause_join` 不在這個讀點切(`NOT_CONTINUATIVE`),整句才會到這裡。
LEFT_HALF_FORMS = {"融合素材とし、": "融合"}
_AS_ALT = "|".join(sorted(map(re.escape, [*MATERIAL_FORMS, *LEFT_HALF_FORMS]), key=len,
                          reverse=True))
ONLY = "のみ"
MATERIAL_MARKER = "を"
SELF_SUBJECT = "このカード"
SUBJECT_MARKER = "が"
# [このカードが、]素材(のみ)を 素材字面 其餘;素材短語裡的「を含む」不是受詞助詞。
_CLAUSE_RE = re.compile(
    f"^(?:(?P<subject>{SELF_SUBJECT}){SUBJECT_MARKER}(?P<pause>、)?)?"
    f"(?P<materials>(?:「[^「」]*」|を含む|[^を「」])+?)(?P<only>{ONLY})?{MATERIAL_MARKER}"
    f"(?P<literal>{_AS_ALT})(?P<rest>.+)$")
# 素材短語開頭的從(「自分の手札・フィールドのモンスター」);讀點記進從的字面。
_FROM_RE = re.compile(f"^(?P<from>{ZONE_PHRASE})(?P<particle>の|から)(?P<pause>、)?(?P<objects>.+)$")


def _material_cause(literal):
    """素材字面 → 原因格 {"kind": 作為素材, "text", "summon"}。"""
    if literal in MATERIAL_FORMS:
        return parse_cause(literal)
    return {"kind": CAUSE_MATERIAL, "text": literal, "summon": LEFT_HALF_FORMS[literal]}


def _material_lines(state, phrase, only, sentence_start):
    """素材短語 → ([角色 素材 的對象線], None) 或 (None, 原因);「AとB」是兩條線,開頭的區域是每條線明寫的從。"""
    from_zones, from_text, owner_from = None, None, None
    located = _FROM_RE.match(phrase)
    if located and parse_from(located.group("from")):
        from_zones = parse_from(located.group("from"))
        from_text = located.group("from") + located.group("particle") + (located.group("pause") or "")
        owner_from = (located.group("from"), from_zones)
        phrase = located.group("objects")
    lines = []
    for piece in simple_clause.split_objects(phrase):
        obj_id, ref, reason = state.object_at(piece, sentence_start, owner_from)
        if obj_id is None:
            return None, reason
        line = new_line(obj_id, ROLE_MATERIAL, marker=(only or "") + MATERIAL_MARKER, ref=ref)
        if from_zones is not None:
            line["from"] = position(from_zones, "明寫", text=from_text)
            obj = state.find(obj_id)
            if obj["source"]["kind"] == "新建" and obj["initial_position"] is None:
                obj["initial_position"] = list(from_zones)
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
        lines.append(line)
    return lines, None


def _fill_bare_predicate(seg, state, pred):
    """只剩述語(「S召喚する」「リンク召喚した」):填動作詞、態、極性;不是召喚的述語回 False。"""
    parsed, _ = parse_predicates(pred)
    if parsed is None or not all(is_summon(p.action) for p in parsed):
        return False
    seg["predicate"] = pred
    seg["actions"] = [p.action for p in parsed]
    seg["voice"] = merged_voice(parsed)
    seg["polarity"], seg["optional"] = resolve_polarity(parsed, None)
    state.note_actions(seg)
    return True


def fill_clause(ctx, clause_text):
    """「Xを(融合)素材とし、/として 〜召喚〜」→ 召喚段加角色 素材 的線;不是這個句型回 False。"""
    m = _CLAUSE_RE.match(clause_text)
    if not m or BARE_SUMMON_STEM not in m.group("rest"):
        return False
    seg, state = ctx.seg, ctx.state
    materials, reason = _material_lines(state, m.group("materials"), m.group("only"),
                                        ctx.sentence_start)
    if materials is None:
        seg["unparsed"] = unparsed(reason)
        return True
    rest = m.group("rest")
    if m.group("subject"):
        # 「このカードが X を素材として 融合召喚した」:主語接回其餘的字面,就是一個完整的子句。
        simple_clause.fill_clause(ctx, m.group("subject") + SUBJECT_MARKER + (m.group("pause") or "")
                                  + rest)
    elif not _fill_bare_predicate(seg, state, rest):
        simple_clause.fill_clause(
            ClauseContext(seg, state, ctx.sentence_start + m.start("rest"), ctx.inherited_timing),
            rest)
    if seg["unparsed"]:
        return True
    if not seg["actions"] or not all(is_summon(a) for a in seg["actions"]):
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return True
    if seg["cause"] is not None:
        seg["unparsed"] = unparsed(REASON_TWICE)
        return True
    seg["cause"] = _material_cause(m.group("literal"))
    targetable = ctx.kind == "效果" and not is_delayed(seg)
    for line in materials:
        line["targeting"] = targetable and line["object"] in state.targeted
    if m.group("subject"):
        seg["lines"] = seg["lines"][:1] + materials + seg["lines"][1:]
    else:
        seg["lines"] = materials + seg["lines"]
    return True


def is_material_summon(seg):
    """召喚段帶角色 素材 的線(素材行沒有動作詞,不算)。"""
    return bool(seg["actions"]) and any(line["role"] == ROLE_MATERIAL for line in seg["lines"])


def _render_materials(materials, seg, card, objects, names, self_id):
    """素材那一截:[從]素材(と素材…)[のみ]を。"""
    markers = {line["marker"] for line in materials}
    if len(markers) != 1 or markers & {MATERIAL_MARKER, ONLY + MATERIAL_MARKER} != markers:
        raise NoTemplate("素材線的助詞無模板")
    words = []
    for line in materials:
        if line["to"] or line["count"] or line.get("pick"):
            raise NoTemplate("素材線的格無模板")
        if line["targeting"] and not (line["ref"]
                                      and targeted_earlier(line["object"], seg, card)):
            raise NoTemplate("取對象線無模板")
        words.append(render_object(objects[line["object"]], seg, card, names, line,
                                   self_id=self_id))
    from_text, from_placement = simple_clause.render_from(materials)
    if from_placement != "名詞前":
        raise NoTemplate("素材線的從無模板")
    return from_text + "と".join(words) + markers.pop()


def render_clause(seg, card, objects, names, self_id, clause_duration):
    """召喚段帶素材線的模板:素材那一截 + 素材字面,插在其餘子句(簡單子句模板)的前面;
    被召喚的線排在素材線前面時(「このカードが X を素材として〜」)插在主語後面。"""
    materials = [line for line in seg["lines"] if line["role"] == ROLE_MATERIAL]
    others = [line for line in seg["lines"] if line["role"] != ROLE_MATERIAL]
    cause = seg["cause"] or {}
    literal = cause.get("text")
    if (literal not in MATERIAL_FORMS and literal not in LEFT_HALF_FORMS) \
            or cause != _material_cause(literal):
        raise NoTemplate("素材字面無模板")
    material_text = _render_materials(materials, seg, card, objects, names, self_id) + literal
    if not others:
        if any(seg[slot] for slot in ("agent", "recipient", "timing", "amount", "times",
                                      "per_turn")) or clause_duration:
            raise NoTemplate("只寫素材的召喚段有模板不寫的格")
        check_predicate(seg, parse_predicates(seg["predicate"] or "")[0])
        return material_text + seg["predicate"]
    rest = simple_clause.render_clause({**seg, "lines": others, "cause": None}, card, objects,
                                       names, self_id, clause_duration)
    if seg["lines"][0]["role"] == ROLE_MATERIAL:
        return material_text + rest
    subject = others[0]
    lead = (render_object(objects[subject["object"]], seg, card, names, subject, self_id=self_id)
            + (subject["marker"] or ""))
    if not (subject["marker"] or "").startswith(SUBJECT_MARKER) or not rest.startswith(lead):
        raise NoTemplate("素材前的主語無模板")
    return lead + material_text + rest[len(lead):]
