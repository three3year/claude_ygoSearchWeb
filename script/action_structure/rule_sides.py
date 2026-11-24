"""建置的「補方」:卡文沒寫方、但照遊戲規則推得出方的區域,把方寫進對象線的從、到,
方的來源記「規則」(spec「規則推得的方」、GLOSSARY「方的來源」)。

段與對象線抽完後,`fill_rule_sides(card)` 走過每條對象線的從、到的每個區域,照 `RULES` 的順序
問每條規則;第一條給出方的就用它,都不給的區域原樣。每條規則自己判要不要管這個區域
(「沒寫方」= 區域條目沒有方,不看來源;已經有方的不論來源都不動,只有自身照段的誰換掉),所以加一條規則只要
寫一個函式、插進 `RULES` 的位置。

前提、條件式的位置原子、卡片屬性表的位置條件不補。結構裡的區域 dict 可能被幾條線共用
(繼承的從),補方一律換成新的 dict、不就地改,共用的線各自照自己的物件補。
"""
from typing import NamedTuple

from action_rows import IMPLIED_SELF, agent_of
from structure_shape import SIDE_SOURCE_RULE, iter_segments
from zone_phrase import FIELD_ZONES

_CONTROLLER_OP = "控制方"
_SELF = "自身"


class RuleInput(NamedTuple):
    """一條規則看得到的東西:這個區域、它在從還是到(`end` 是 "from" / "to")、
    這條對象線、所在的段與區塊、卡片結構與物件表(id → 物件)。"""
    zone: dict
    end: str
    line: dict
    seg: dict
    block: dict
    card: dict
    objects: dict


def _written_controller(given):
    """從的區域沒寫方、物件的條件式寫了控制方(「相手の表側表示モンスター」;物件是子集或剩餘時
    往上找來源物件)→ 照寫的方。到不用:控制方說的是物件出發時在哪一方,不是去處。"""
    if given.end != "from" or given.zone["side"] is not None:
        return None
    return _controller_of(given.objects.get(given.line["object"]), given.objects)


def _field_any_side(given):
    """場上系區域沒寫方 → 任一方(「フィールドのカードを全て破壊する」)。"""
    if given.zone["side"] is None and given.zone["zone"] in FIELD_ZONES:
        return "任一方"
    return None


def _self_is_segment_agent(given):
    """方是自身(「ドローしたプレイヤーは自身の手札を」)→ 這一段的誰,解法同查詢判斷(`agent_of`):
    我方、對手照填,主動句沒寫誰算我方,動作回指解回它指的那一段;雙方各自、不限定 → 任一方。"""
    if given.zone["side"] != _SELF:
        return None
    segments = {seg["id"]: seg for block in given.card["blocks"]
                for _, seg in iter_segments(block)}
    agent = agent_of(given.seg, segments)
    if agent == IMPLIED_SELF:
        return "我方"
    return agent if agent in ("我方", "對手") else "任一方"


# 依序套用:前面的規則先給方。
RULES = (
    _written_controller,
    _field_any_side,
    _self_is_segment_agent,
)


def _controller_of(obj, objects):
    """物件條件式寫的控制方(只看最外層與「且」裡的原子;寫了兩種不同的方就不算);
    物件是子集或剩餘、自己沒寫時往上找來源物件。沒寫回 None。"""
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
