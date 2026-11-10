"""反向檢查用的「這一段之前」:同一區塊裡先前的段對某物件做過什麼。

回指字面要對得上先前的段才寫得回去:動作回指(「めくったカード」)看 `last_action_on`,
「選択したモンスター」看 `targeted_earlier`,「ドローしたプレイヤー」看 `last_segment_doing`。
`all_blocks` 走過區塊與內嵌效果的區塊。
"""

from predicate_literal import split_predicate_literal
from structure_shape import iter_nodes


def all_blocks(card):
    """區塊與內嵌效果的區塊(票 06)。"""
    stack = list(card["blocks"])
    while stack:
        block = stack.pop()
        yield block
        for node in iter_nodes(block["tree"]["items"]):
            if node.get("node") == "內嵌效果" and node.get("block"):
                stack.append(node["block"])


def last_action_on(obj_id, seg, card):
    """同一區塊裡、這一段之前最後一個作用在該物件上的動作詞(動作回指「めくったカード」用)。"""
    block_id = seg["id"].split(".")[0]
    for block in all_blocks(card):
        if block["id"] != block_id:
            continue
        found = None
        for other in block["segments"]:
            if other["id"] == seg["id"]:
                break
            if other["actions"] and any(l["object"] == obj_id for l in other["lines"]):
                found = other["actions"][-1]
        return found
    return None


def targeted_earlier(obj_id, seg, card):
    """這一段之前,同一區塊裡有沒有一段以取對象字面(選択して/対象として)點名過該物件。"""
    block_id = seg["id"].split(".")[0]
    for block in all_blocks(card):
        if block["id"] != block_id:
            continue
        for other in block["segments"]:
            if other["id"] == seg["id"]:
                return False
            prefix = split_predicate_literal(other["predicate"] or "").targeting
            if prefix and any(l["object"] == obj_id and l["targeting"]
                              for l in other["lines"]):
                return True
    return False


def last_segment_doing(action, seg, card):
    """同一區塊裡、這一段之前最後一個做過該動作詞的段 id(「ドローしたプレイヤー」的回指)。"""
    block_id = seg["id"].split(".")[0]
    for block in all_blocks(card):
        if block["id"] != block_id:
            continue
        found = None
        for other in block["segments"]:
            if other["id"] == seg["id"]:
                break
            if action in other["actions"]:
                found = other["id"]
        return found
    return None
