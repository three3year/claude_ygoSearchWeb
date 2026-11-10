"""反向檢查用的「這一段之前」:同一區塊裡先前的段對某物件做過什麼。

回指字面要對得上先前的段才寫得回去:動作回指(「めくったカード」)看 `last_action_on`,
「選択したモンスター」看 `targeted_earlier`,「ドローしたプレイヤー」看 `last_segment_doing`。
`all_blocks` 走過區塊與內嵌效果的區塊;「この効果で(〜召喚に成功した)」指的段從 `segments_before` 的範圍找。
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


def _with_embedded(block):
    yield block
    for node in iter_nodes(block["tree"]["items"]):
        if node.get("node") == "內嵌效果" and node.get("block"):
            yield from _with_embedded(node["block"])


def segments_before(seg, card):
    """(這一段所在的頂層區塊之前的各頂層區塊, 同一區塊裡這一段之前的段);段找不到回兩個空列表。
    與抽取當下看得到的範圍相同:前面的區塊已抽完,自己的區塊只抽到這一段之前。"""
    block_id = seg["id"].split(".")[0]
    for index, top in enumerate(card["blocks"]):
        for block in _with_embedded(top):
            if block["id"] != block_id:
                continue
            own = []
            for other in block["segments"]:
                if other["id"] == seg["id"]:
                    break
                own.append(other)
            return card["blocks"][:index], own
    return [], []


def previous_segment(seg, card):
    """同一區塊裡緊接在這一段前面的段;這一段是區塊的第一段、或找不到時回 None。"""
    _, own = segments_before(seg, card)
    return own[-1] if own else None


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


def declared_earlier(obj_id, seg, card):
    """這一段之前,同一區塊裡有沒有一個沒有動作詞的宣告段(「Xを対象とし、」「Xを選択し、」)點名過該物件:
    省略的受方(沒寫出來的裝備對象)要對得上它(m3 票 07)。"""
    block_id = seg["id"].split(".")[0]
    for block in all_blocks(card):
        if block["id"] != block_id:
            continue
        for other in block["segments"]:
            if other["id"] == seg["id"]:
                return False
            literal = split_predicate_literal(other["predicate"] or "")
            if (literal.targeting and not literal.predicate and not other["actions"]
                    and any(l["object"] == obj_id for l in other["lines"])):
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
