"""查詢側的卡名包含:打的字先換成一組卡片編號(GLOSSARY「卡名包含」的查詢用法)。

一張卡的名字是中文名、日文名、英文名與別名(中文卡文「※ 別名」,抽法同前端索引),
加上它「〜として扱う」當作的卡名:先換成指的那張卡、用那張卡的這四種名字,對不到卡的用日文字面;
不看位置條件。
比法同網站:打的字去頭尾空白,打的字與名字都做全形英數、全形空白當半形與小寫的折疊;
以 `%` 切段、去掉空段,各段依序出現在名字裡就算;沒有非空的段時等於沒給。
"""
import os
import sys

from archetype_table import fold_width
from condition_judge import CARD_IDS

_WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
if _WEB not in sys.path:
    sys.path.append(_WEB)
from webindex import split_alias  # noqa: E402

NAME_CONTAINS = "卡名包含"


def fold_name(text):
    return fold_width(text).lower()


def like_parts(text):
    return [part for part in fold_name(text.strip()).split("%") if part]


def like_match(name, parts):
    pos = 0
    for part in parts:
        at = name.find(part, pos)
        if at < 0:
            return False
        pos = at + len(part)
    return True


def _own_names(entry):
    return (entry["name_zh"], entry["name_ja"], entry["name_en"], split_alias(entry["desc"])[1])


def _loose(text):
    # 卡文與卡名只差全半形或空白的(卡文「N・グロー・モス」、卡名「Ｎ・グロー・モス」)也算同一張卡。
    return fold_width(text).replace(" ", "")


def treated_names(structures, cards):
    """卡片結構 + 卡片總表 → {卡號: (對到的卡號, 對不到卡的日文字面)},只列有當作卡名的卡。"""
    exact = {entry["name_ja"]: entry["id"] for entry in cards if entry["name_ja"]}
    loose = {_loose(name): cid for name, cid in exact.items()}
    out = {}
    for structure in structures:
        ids, literals = [], []
        for row in ((structure.get("attributes") or {}).get("name") or [])[1:]:
            value = row["value"]
            cid = exact.get(value, loose.get(_loose(value)))
            found, item = (ids, cid) if cid is not None else (literals, value)
            if item not in found:
                found.append(item)
        if ids or literals:
            out[structure["id"]] = (ids, literals)
    return out


class CardNames:
    def __init__(self, cards, treated):
        own = {entry["id"]: _own_names(entry) for entry in cards}

        def names(cid):
            ids, literals = treated.get(cid, ((), ()))
            return own[cid] + tuple(n for t in ids for n in own[t]) + tuple(literals)
        self._names = [(entry["id"], tuple(fold_name(n) for n in names(entry["id"]) if n))
                       for entry in cards]

    def ids_containing(self, parts):
        return frozenset(cid for cid, names in self._names
                         if any(like_match(name, parts) for name in names))


def drop_blank_names(condition):
    """查詢條件式裡沒有非空段的卡名包含等於沒給:從頂層與「且」拿掉,拿光了回 None。"""
    if condition is None:
        return None
    if condition["op"] == NAME_CONTAINS:
        return condition if like_parts(condition["text"]) else None
    if condition["op"] == "且":
        args = [arg for arg in map(drop_blank_names, condition["args"]) if arg is not None]
        return {**condition, "args": args} if args else None
    return condition


def resolve_names(condition, cards, structures):
    """查詢條件式 → 卡名包含原子換成卡號集合原子的條件式;其他原子原樣。"""
    names = None

    def walk(node):
        nonlocal names
        if node["op"] == NAME_CONTAINS:
            names = names or CardNames(cards, treated_names(structures, cards))
            return {"op": CARD_IDS, "ids": names.ids_containing(like_parts(node["text"]))}
        if node["op"] in ("且", "或"):
            return {**node, "args": [walk(arg) for arg in node["args"]]}
        if node["op"] == "非":
            return {**node, "arg": walk(node["arg"])}
        return node
    return walk(condition)
