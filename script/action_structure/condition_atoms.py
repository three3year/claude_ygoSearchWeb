"""條件式原子(票 07):記載、卡名範圍、屬性比較(引用)、位置、卡片子類型的抽取與句型模板。

放獨立模組是為了把一個原子的「抽取」與「模板」放在一起:`segment_extract.parse_modifiers`
認不得修飾語時交給 `parse_modifier`,`reverse_check._render_atom` 沒模板時交給 `render_atom`;
加一個原子只改這裡。原子的查詢判斷在 `action_query.eval_condition`。

- 記載(名稱):「X」のカード名が記された → {"op": "記載", "name": 名稱列 id};
  「X」またはそのカード名が記された → 或(卡名∋X, 記載 X)。查詢時掃卡文含「X」(含括號)。
"""
import re

_MENTION_OR_RE = re.compile("^「(?P<name>[^「」]+)」またはそのカード名が記された")
_MENTION_RE = re.compile("^「(?P<name>[^「」]+)」のカード名が記された")


def parse_modifier(rest, state):
    """修飾語開頭認得的原子 → (原子列表, 原因, 吃掉的長度);認不得回 None。
    原子列表為空時表示名稱對不到(原因帶著),呼叫端把那截標解析不出。"""
    m = _MENTION_OR_RE.match(rest)
    if m:
        named, why = state.name_atom("卡名", m.group("name"))
        mention, _ = state.name_atom("記載", m.group("name"))
        atoms = [{"op": "或", "args": [named, mention]}] if named else []
        return atoms, why, m.end()
    m = _MENTION_RE.match(rest)
    if m:
        atom, why = state.name_atom("記載", m.group("name"))
        return ([atom] if atom else []), why, m.end()
    return None


def _quoted(atom, names):
    row = names.get(atom.get("name"))
    return None if row is None else f"「{row['text']}」"


def render_atom(atom, names):
    """原子 → 修飾語字面;這裡沒模板的回 None(呼叫端記「無模板」)。"""
    op = atom.get("op")
    if op == "記載":
        quoted = _quoted(atom, names)
        return None if quoted is None else quoted + "のカード名が記された"
    if op == "或" and _is_name_or_mention(atom):
        quoted = _quoted(atom["args"][0], names)
        return None if quoted is None else quoted + "またはそのカード名が記された"
    return None


def _is_name_or_mention(atom):
    """或(卡名∋X, 記載 X) 且兩個引用同一個名稱列。"""
    args = atom.get("args", [])
    return (len(args) == 2 and args[0].get("op") == "卡名"
            and args[1].get("op") == "記載"
            and args[0].get("name") == args[1].get("name"))
