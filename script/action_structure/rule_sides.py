"""建置時寫進規則推得的方:卡文沒寫方、但照遊戲規則推得出方的區域,把方寫進對象線的從、到,
方的來源記「規則」(spec「規則推得的方」、GLOSSARY「方的來源」)。
"""
from typing import Literal, NamedTuple

from action_rows import IMPLIED_SELF, agent_of
from condition_judge import is_this_card
from structure_shape import SIDE_SOURCE_RULE, iter_segments
from zone_phrase import FIELD_ZONES, SIDE_WORDS

_CONTROLLER_OP = "控制方"
_OWNER_ZONES = ("墓地", "除外")   # 卡一定進持有者的墓地、除外
_SELF = SIDE_WORDS["自身"]


class RuleInput(NamedTuple):
    zone: dict
    end: Literal["from", "to"]
    line: dict
    seg: dict
    block: dict
    card: dict
    objects: dict


def _from_written_controller(given):
    if given.end != "from" or given.zone["side"] is not None:
        return None
    obj = given.objects.get(given.line["object"])
    if obj is None:
        return None
    sides = {atom["value"] for atom in _conjuncts(obj["condition"])
             if atom.get("op") == _CONTROLLER_OP}
    return sides.pop() if len(sides) == 1 else None


def _field_any_side(given):
    if given.zone["side"] is None and given.zone["zone"] in FIELD_ZONES:
        return "任一方"
    return None


def _graveyard_banished_owner(given):
    if given.zone["side"] is not None or given.zone["zone"] not in _OWNER_ZONES:
        return None
    obj = given.objects.get(given.line["object"])
    return "我方" if obj is not None and is_this_card(obj, given.objects) else "持有者"


def _self_is_segment_agent(given):
    if given.zone["side"] != _SELF:
        return None
    segments = {seg["id"]: seg for block in given.card["blocks"]
                for _, seg in iter_segments(block)}
    agent = agent_of(given.seg, segments)
    if agent == IMPLIED_SELF:
        return "我方"
    return agent if agent in ("我方", "對手") else "任一方"


RULES = (
    _from_written_controller,
    _field_any_side,
    _graveyard_banished_owner,
    _self_is_segment_agent,
)


def _conjuncts(condition):
    if not isinstance(condition, dict):
        return
    if condition.get("op") == "且":
        for arg in condition.get("args") or ():
            yield from _conjuncts(arg)
    else:
        yield condition


def fill_rule_sides(card):
    """就地把一張卡對象線的從、到補上規則推得的方(見模組說明)。"""
    objects = {obj["id"]: obj for obj in card["objects"]}
    for block in card["blocks"]:
        for owner, seg in iter_segments(block):
            for line in seg["lines"]:
                for end in ("from", "to"):
                    if line[end]:
                        for zone in line[end]["zones"]:
                            _fill(RuleInput(zone, end, line, seg, owner, card, objects))


def _fill(given):
    for rule in RULES:
        side = rule(given)
        if side is not None:
            given.zone.update(side=side, side_source=SIDE_SOURCE_RULE)
            return
