"""m3 統計共用:讀產物(card_structure.load_structures)、走段、解析不出原子、反向檢查快取。

只讀 data/;所有腳本在 repo 根跑:python -X utf8 .scratch/action-structure-m3/stats/<腳本>.py
"""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "script", "action_structure"))

from card_structure import load_structures  # noqa: E402
from structure_shape import iter_segments  # noqa: E402

_CARDS = None


def cards():
    global _CARDS
    if _CARDS is None:
        with open(os.path.join(ROOT, "data", "action_structure.json"), encoding="utf-8") as f:
            _CARDS = load_structures(f.read())
    return _CARDS


def all_segments(card):
    """(區塊, 段),含內嵌效果裡的段。"""
    for top in card["blocks"]:
        yield from iter_segments(top)


def seg_text(block, seg):
    s, e = seg["span"]
    return block["text"][s:e]


def unparsed_atoms(cond):
    """條件式裡 op = 解析不出 的原子(遞迴)。"""
    if not isinstance(cond, dict):
        return
    if cond.get("op") == "解析不出":
        yield cond
    for a in cond.get("args", []) or []:
        yield from unparsed_atoms(a)
    if isinstance(cond.get("arg"), dict):
        yield from unparsed_atoms(cond["arg"])


def classify(text, rules):
    """先中先贏:rules = [(名稱, regex)];沒中回「其他」。"""
    for name, pat in rules:
        if re.search(pat, text):
            return name
    return "其他"


def blocks_by_id(card):
    """區塊 id → 區塊,含內嵌效果的內容區塊。"""
    out = {}

    def walk(block):
        out[block["id"]] = block
        stack = list(block["tree"]["items"])
        while stack:
            node = stack.pop()
            if node.get("node") == "內嵌效果" and node.get("block"):
                walk(node["block"])
            for br in node.get("branches") or []:
                stack.extend(br["items"])
    for b in card["blocks"]:
        walk(b)
    return out


def sentence(text, span):
    """原文裡包含 span 的那一句(以「。」與換行為界)。"""
    s, e = span
    a = max(text.rfind("。", 0, s), text.rfind("\n", 0, s)) + 1
    ends = [i for i in (text.find("。", e), text.find("\n", e)) if i != -1]
    b = (min(ends) + 1) if ends else len(text)
    return text[a:b].strip()


def short(text, n=70):
    text = text.replace("\n", " ")
    return text if len(text) <= n else text[:n] + "…"
