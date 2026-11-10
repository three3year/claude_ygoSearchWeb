"""戰鬥子句「Xが(Yと)戦闘を行う」:句型、填格與句型模板成對放在一起。

X 是角色施事的對象線、Y 是受事;戰鬥不移動卡片,線沒有從/到。戰鬥時點的觸發形(ダメージ計算時…)
在 `segment_extract`。
"""

import re

from object_render import render_object
from predicate_literal import render_predicate
from segment_fields import resolve_polarity
from structure_shape import NoTemplate, new_line, unparsed
from synonyms import merged_voice, parse_predicates


# 戰鬥子句:述語「戦闘を行う」含「を」,一般句型的述語槽吃不到,另開句型。
# 施事寫在前、受事(「Yと」)可省;物件短語裡沒有讀點(「自分のモンスターが、〜と」不收)。
BATTLE_AGENT_MARKER, BATTLE_PARTNER_MARKER = "が", "と"
BATTLE_PREDICATE = "戦闘を行"
_BATTLE_RE = re.compile(
    f"^(?P<agent>[^、]+?){BATTLE_AGENT_MARKER}"
    f"(?:(?P<partner>[^、]+?){BATTLE_PARTNER_MARKER})?(?P<pred>{BATTLE_PREDICATE}[^を、]*)$")


def fill_clause(ctx, clause_text):
    """戰鬥子句「Xが(Yと)戦闘を行う」:X 是施事(助詞 が)、Y 是受事(助詞 と),兩者都是物件;
    戰鬥不移動卡片,線沒有從/到。不是這個句型回 False。"""
    m = _BATTLE_RE.match(clause_text)
    if not m:
        return False
    seg, state, sentence_start = ctx.seg, ctx.state, ctx.sentence_start
    parsed, reason = parse_predicates(m.group("pred"))
    seg["predicate"] = m.group("pred")
    if parsed is None:
        seg["unparsed"] = unparsed(reason)
        return True
    seg["actions"] = [p.action for p in parsed]
    seg["voice"] = merged_voice(parsed)
    seg["polarity"], seg["optional"] = resolve_polarity(parsed, BATTLE_AGENT_MARKER)
    mentions = [(m.group("agent"), "施事", BATTLE_AGENT_MARKER)]
    if m.group("partner"):
        mentions.append((m.group("partner"), "受事", BATTLE_PARTNER_MARKER))
    for phrase, role, marker in mentions:
        obj_id, ref, reason = state.object_at(phrase, sentence_start)
        if obj_id is None:
            seg["lines"] = []
            seg["unparsed"] = unparsed(reason)
            return True
        seg["lines"].append(new_line(obj_id, role, marker=marker, ref=ref))
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
        state.acted.setdefault(obj_id, []).extend(seg["actions"])
    return True


def render_clause(seg, card, objects, names, self_id):
    """戰鬥子句:[施事]が[受事と]述語;施事一條、受事至多一條,線不帶從/到/取對象/數量,
    段不帶誰、受方、原因、時機、數量。"""
    lines = seg["lines"]
    roles = [(line["role"], line["marker"]) for line in lines]
    if roles not in ([("施事", BATTLE_AGENT_MARKER)],
                     [("施事", BATTLE_AGENT_MARKER), ("受事", BATTLE_PARTNER_MARKER)]):
        raise NoTemplate("戰鬥的對象線無模板")
    if (any(line["from"] or line["to"] or line["targeting"] or line["count"] for line in lines)
            or any(seg[slot] for slot in ("agent", "recipient", "cause", "timing", "amount"))):
        raise NoTemplate("戰鬥段的格無模板")
    _, select, predicate, _ = render_predicate(seg, BATTLE_AGENT_MARKER)
    if select:
        raise NoTemplate("戰鬥段的格無模板")
    return "".join(render_object(objects[line["object"]], seg, card, names, line,
                                  self_id=self_id) + line["marker"]
                   for line in lines) + predicate
