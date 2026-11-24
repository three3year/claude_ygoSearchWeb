"""建置的「補方」:卡文沒寫方、但照遊戲規則推得出方的區域,把方寫進對象線的從、到,
方的來源記「規則」(spec「規則推得的方」、GLOSSARY「方的來源」)。
"""
from typing import NamedTuple

from action_rows import IMPLIED_SELF, agent_of
from condition_judge import is_this_card
from structure_shape import SIDE_SOURCE_RULE, iter_segments
from zone_phrase import FIELD_ZONES

_CONTROLLER_OP = "控制方"
_OWNER_ZONES = ("墓地", "除外")   # 卡一定進持有者的墓地、除外
_SELF = "自身"


class RuleInput(NamedTuple):
    zone: dict
    end: str
    line: dict
    seg: dict
    block: dict
    card: dict
    objects: dict


def _written_controller(given):
    if given.end != "from" or given.zone["side"] is not None:
        return None
    return _controller_of(given.objects.get(given.line["object"]), given.objects)


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
    _written_controller,
    _field_any_side,
    _graveyard_banished_owner,
    _self_is_segment_agent,
)


def _controller_of(obj, objects):
    seen = set()
    while obj is not None and obj["id"] not in seen:
        seen.add(obj["id"])
        sides = {atom["value"] for atom in _conjuncts(obj["condition"])
                 if atom.get("op") == _CONTROLLER_OP}
        if len(sides) == 1:
            return sides.pop()
        if sides:
            return None
        source = obj["source"]
        if source.get("kind") not in ("子集", "剩餘"):
            return None
        obj = objects.get(source.get("of"))
    return None


def _conjuncts(condition):
    if not isinstance(condition, dict):
        return
    if condition.get("op") == "且":
        for arg in condition.get("args") or ():
            yield from _conjuncts(arg)
    else:
        yield condition


def fill_rule_sides(card):
    """就地把一張卡的對象線換成補過方的從、到(見模組說明)。"""
    objects = {obj["id"]: obj for obj in card["objects"]}
    for block in card["blocks"]:
        for owner, seg in iter_segments(block):
            for line in seg["lines"]:
                for end in ("from", "to"):
                    pos = line[end]
                    if not pos:
                        continue
                    zones = [_filled(RuleInput(z, end, line, seg, owner, card, objects))
                             for z in pos["zones"]]
                    if zones != pos["zones"]:
                        line[end] = {**pos, "zones": zones}


def _filled(given):
    for rule in RULES:
        side = rule(given)
        if side is not None:
            return {**given.zone, "side": side, "side_source": SIDE_SOURCE_RULE}
    return given.zone
