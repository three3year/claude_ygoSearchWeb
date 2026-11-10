"""抽牌:句型、填格(`fill_clause`)與句型模板(`render_clause`)成對放在一起。

- 抽到的卡是新建物件(條件同頭名詞カード,即 大類 卡);「カードを」有寫時物件字面是它、助詞を,
  沒寫時物件沒有字面與範圍、對象線沒有助詞——兩者除字面外結構相同。
- 張數在對象線 `count`:固定值「N枚」寫在述語前;變數張數(「破壊した数だけ」「その枚数分だけ」)
  只記算式字面 `{"kind": "算式", "text"}`,寫在主語前的帶 `placement: 主語前`、寫在主語後
  「從」前的帶 `placement: 名詞前`。「お互いはそれぞれ」的「それぞれ」是每人各 N 張,記 `each`。
- 從牌組(「デッキから」明寫,沒寫照推得表)到手牌(推得)。
- 誰:「自分は/相手は/お互いは」進 `agent`(`agent_phrase.parse_agent`)。
- 原因:「通常のドロー」= `{"kind": "規則", "text": "通常の"}`,寫在述語前;「効果で」照既有閉集。
- 「ドローフェイズ」是階段字面,不是抽牌(述語字面排除它)。
"""
import re

from agent_phrase import AGENT_PATTERN, agent_side, parse_agent, render_agent
from block_state import INFERENCE_TABLE, REASON_CLAUSE, REASON_TWICE, update_positions
from cause_phrase import parse_cause_phrase, render_cause_phrase
from noun_phrase import category_condition
from object_render import render_object
from predicate_literal import render_predicate
from segment_fields import CAUSE_PATTERN, render_timing, resolve_polarity
from structure_shape import NoTemplate, new_line, new_object, position, unparsed, zone
from synonyms import merged_voice, parse_predicates
from zone_phrase import parse_from, render_zone_text

DRAW_ACTION = "抽牌"
DRAWN_OBJECT = "カード"
DRAWN_MARKER = "を"
COUNT_UNIT = "枚"
EACH_WORD = "それぞれ"
RULE_TEXT = "通常の"
CAUSE_RULE = "規則"
PLACEMENT_BEFORE_SUBJECT = "主語前"
PLACEMENT_BEFORE_NOUN = "名詞前"
FORMULA_TAIL = "(?:数|数分)だけ"
_FORMULA_TAIL_RE = re.compile(f"{FORMULA_TAIL}、?$")
_FIXED_RE = re.compile(f"^(?P<digits>[０-９]+){COUNT_UNIT}$")
_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")


def clause_pattern(agent_pattern):
    """抽牌子句的正規式:[算式(主語前)][誰][それぞれ][原因][算式(名詞前)][從から][カードを][N枚]
    [通常の]述語。誰的字面由呼叫端給(與簡單子句共用)。主語前的算式不能吃到「自分は」這種主語。"""
    return re.compile(
        f"^(?P<count_lead>(?!(?:{agent_pattern})(?:は|が))[^、を]+?{FORMULA_TAIL}、?)?"
        f"(?:(?P<agent>{agent_pattern})(?P<agent_marker>は|が|(?<=お互い)に)"
        "(?P<agent_pause>、)?)?"
        f"(?P<each>{EACH_WORD})?"
        f"(?P<cause>{CAUSE_PATTERN})?"
        f"(?P<count_front>[^、を]+?{FORMULA_TAIL}、?)?"
        "(?:(?P<from>(?:自分の|相手の)?デッキ)から)?"
        f"(?:(?P<object>{DRAWN_OBJECT}){DRAWN_MARKER})?"
        f"(?P<count>[０-９]+{COUNT_UNIT})?"
        f"(?P<rule>{RULE_TEXT})?"
        "(?P<pred>ドロー(?!フェイズ)を?[^、を]*)$")


def parse_count(fixed, front, lead, each):
    """張數字面 → 對象線 count;寫了兩處、或「それぞれ」沒有張數 → None(不猜)。"""
    written = [(text, placement) for text, placement in
               ((fixed, None), (front, PLACEMENT_BEFORE_NOUN), (lead, PLACEMENT_BEFORE_SUBJECT))
               if text]
    if len(written) > 1 or (each and not written):
        return None, bool(written)
    if not written:
        return None, False
    text, placement = written[0]
    if placement is None:
        count = {"text": text, "value": int(text[:-len(COUNT_UNIT)].translate(_FULLWIDTH)),
                 "unit": COUNT_UNIT, "cmp": "="}
    else:
        count = {"kind": "算式", "text": text, "placement": placement}
    if each:
        count["each"] = True
    return count, False


def drawer_deck(zones, drawer):
    """沒寫方的牌組(「デッキから」)是抽牌者的:「相手はデッキから」是對手的牌組、「お互いは」是雙方各自
    (站主 2026-11-10)。抽牌者靜態判不了(動作回指)或沒寫(預設我方)時照區域預設。"""
    if drawer is None:
        return zones
    return [{**z, "side": drawer} if z["side_source"] == "預設" else z for z in zones]


def undo_drawer_deck(zones, drawer):
    """`drawer_deck` 的反向(反向檢查由字面拼回區域時比對用):抽牌者的牌組換回區域預設的我方。"""
    return [{**z, "side": "我方"} if z["side_source"] == "預設" and z["side"] == drawer else z
            for z in zones]


def rule_cause():
    return {"kind": CAUSE_RULE, "text": RULE_TEXT}


def is_rule_cause(cause):
    return cause == rule_cause()


def render_count(count):
    """count → (字面, placement);形狀不對丟 ValueError(呼叫端轉成無模板)。"""
    if not count:
        return "", None
    text = count.get("text") or ""
    if count.get("kind") == "算式":
        placement = count.get("placement")
        if placement not in (PLACEMENT_BEFORE_SUBJECT, PLACEMENT_BEFORE_NOUN) \
                or not _FORMULA_TAIL_RE.search(text):
            raise ValueError("抽牌張數無模板")
        return text, placement
    m = _FIXED_RE.match(text)
    if (not m or count.get("unit") != COUNT_UNIT or count.get("cmp") != "="
            or int(m.group("digits").translate(_FULLWIDTH)) != count.get("value")
            or count.get("placement")):
        raise ValueError("抽牌張數無模板")
    return text, None


_DRAW_RE = clause_pattern(AGENT_PATTERN)
_DRAWN_CONDITION = {"op": "大類", "value": "卡"}


def fill_clause(ctx, clause_text):
    """抽牌子句 → 填格回 True;不是這個句型回 False。抽到的卡是新建物件(「カードを」沒寫時物件沒有字面)、張數在對象線、
    從牌組(明寫或推得)到手牌(推得);玩家主語進 `agent`。"""
    m = _DRAW_RE.match(clause_text)
    if not m:
        return False
    seg, state, sentence_start = ctx.seg, ctx.state, ctx.sentence_start
    g = m.groupdict().get
    parsed, reason = parse_predicates(g("pred"))
    seg["predicate"] = g("pred")
    if parsed is None or [p.action for p in parsed] != [DRAW_ACTION]:
        seg["unparsed"] = unparsed(reason or REASON_CLAUSE)
        return True
    seg["actions"] = [DRAW_ACTION]
    seg["voice"] = merged_voice(parsed)
    seg["polarity"], seg["optional"] = resolve_polarity(parsed, None)
    if g("agent"):
        seg["agent"], reason = parse_agent(state, g("agent"), g("agent_marker"),
                                           g("agent_pause"), ctx.kind)
        if seg["agent"] is None:
            seg["unparsed"] = unparsed(reason)
            return True
    count, ambiguous = parse_count(g("count"), g("count_front"), g("count_lead"), g("each"))
    if ambiguous or (g("cause") and g("rule")):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return True
    if g("each") and count is None:
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return True
    if g("cause"):
        seg["cause"], reason = parse_cause_phrase(state, g("cause"), sentence_start)
        if seg["cause"] is None:
            seg["unparsed"] = unparsed(reason)
            return True
    elif g("rule"):
        seg["cause"] = rule_cause()
    ctx.inherit_timing()
    if g("object"):
        obj_id, _, _ = state.new_object(g("object"), sentence_start, {"kind": "新建"})
    else:
        offset = state.offset_of(g("pred"), sentence_start)
        obj_id = state.add_object(new_object(
            f"{state.block['id']}.o{offset}", {"kind": "新建"}, block=state.block["id"],
            condition=category_condition(DRAWN_OBJECT)))
    if g("from"):
        from_ = position(drawer_deck(parse_from(g("from")), agent_side(seg["agent"])),
                         "明寫", text=g("from") + "から")
        state.find(obj_id)["initial_position"] = list(from_["zones"])
    else:
        from_ = position([zone(INFERENCE_TABLE[DRAW_ACTION][0], None)], "推得",
                         inferred=True)
    line = new_line(obj_id, "受事", marker=DRAWN_MARKER if g("object") else None,
                    count=count)
    line["from"] = from_
    line["to"] = position([zone(INFERENCE_TABLE[DRAW_ACTION][1], None)], "推得",
                          inferred=True)
    seg["lines"] = [line]
    state.acted.setdefault(obj_id, []).extend(seg["actions"])
    update_positions(seg, state)
    state.note_actions(seg)
    return True


def is_draw_segment(seg, objects):
    if seg["actions"] != [DRAW_ACTION] or len(seg["lines"]) != 1:
        return False
    line = seg["lines"][0]
    obj = objects.get(line["object"])
    return (obj is not None and obj["source"] == {"kind": "新建"}
            and obj["condition"] == _DRAWN_CONDITION and line["ref"] is None
            and line["marker"] in (None, DRAWN_MARKER))


def render_clause(seg, card, objects, names):
    """抽牌子句:[算式(主語前)][誰][それぞれ][原因][算式(名詞前)][從から][カードを][N枚][通常の]述語。
    物件沒寫時(助詞 None)物件不能有字面;從是明寫或推得的牌組、到是推得的手牌。"""
    line = seg["lines"][0]
    obj = objects[line["object"]]
    if (line["role"] != "受事" or line["targeting"] or line.get("pick") or line.get("elided")
            or obj["count"] or obj["unparsed"]
            or any(seg[slot] for slot in ("recipient", "amount", "modified", "per_turn", "times"))
            or render_timing(seg["timing"])):
        raise NoTemplate("抽牌段的格無模板")
    to = line["to"]
    if not to or to["source"] != "推得" or [z["zone"] for z in to["zones"]] != ["手牌"]:
        raise NoTemplate("抽牌段的到無模板")
    from_ = line["from"]
    if from_ and from_["source"] == "明寫" and not from_.get("placement"):
        drawer = agent_side(seg["agent"])
        from_text = render_zone_text(
            {**from_, "zones": undo_drawer_deck(from_["zones"], drawer)}, "から")
    elif from_ and from_["source"] == "推得" and [z["zone"] for z in from_["zones"]] == ["牌組"]:
        from_text = ""
    else:
        raise NoTemplate("抽牌段的從無模板")
    if line["marker"] is None:
        if obj["text"] is not None or obj["span"] is not None:
            raise NoTemplate("抽牌段的物件無模板")
        object_text = ""
    else:
        object_text = render_object(obj, seg, card, names, line, with_count=False) + line["marker"]
    try:
        count_text, count_placement = render_count(line["count"])
    except ValueError as e:
        raise NoTemplate(str(e)) from None
    each = EACH_WORD if (line["count"] or {}).get("each") else ""
    cause, rule = "", ""
    if is_rule_cause(seg["cause"]):
        rule = RULE_TEXT
    elif seg["cause"]:
        cause = render_cause_phrase(seg["cause"], seg, card, objects, names, "o0")
    targeting, select, predicate, predicate_to = render_predicate(seg, None)
    if targeting or select or predicate_to:
        raise NoTemplate("抽牌段的述語無模板")
    agent = render_agent(seg["agent"], seg, card) if seg["agent"] is not None else ""
    return "".join([
        count_text if count_placement == PLACEMENT_BEFORE_SUBJECT else "",
        agent, each, cause,
        count_text if count_placement == PLACEMENT_BEFORE_NOUN else "",
        from_text, object_text,
        count_text if count_placement is None else "",
        rule, predicate])
