"""名詞短語(修飾語 + 頭名詞)↔ 條件式:抽取與句型模板成對放在一起。

- 抽取:`parse_modifiers`(修飾語從左到右認成原子列表;名稱類的句型在 `_MOD_RES`,種族/屬性在
  `parse_modifier`,等級與「・」列舉在 `attribute_atoms`,其餘原子在 `condition_atoms`);
  頭名詞表 `HEAD_CATEGORY`、`HEAD_SUBTYPE`;「AかB」列舉 `split_alternatives`。
- 模板:`render_condition`(條件式 → 名詞短語)。
加一種修飾語多半只動 `condition_atoms`(原子的抽取與模板)或 `attribute_atoms`(屬性比較);
這裡管的是原子之間怎麼接(連接字 `joiner`)與頭名詞。物件短語整體(回指、新建、子集)在
`block_state.BlockState.object_at`。
"""

import re

from attribute_atoms import (EXCEPT, is_param_atom, joiner, parse_modifier as parse_param_group,
                             render_group, render_number)
from attribute_words import ATTRIBUTE_JA, RACE_JA
from condition_atoms import parse_modifier as parse_atom_modifier, quoted_name, render_atom
from structure_shape import NoTemplate


HEAD_CATEGORY = {"モンスター": "怪獸", "魔法カード": "魔法", "罠カード": "陷阱",
                 "魔法・罠カード": ("魔法", "陷阱"), "カード": "卡"}
# 帶子類型的頭名詞:大類 且 屬性比較(卡片子類型 = 協調,與票 07 的 Xモンスター 同一種原子)。
HEAD_SUBTYPE = {"チューナー": ("怪獸", "協調")}
# 「效果」的頭名詞(m3 票 04):被發動、被無效的是效果,不是卡——「魔法・罠・モンスター(の効果)」
# 「魔法・罠・効果モンスター(の効果)」「モンスターの効果・魔法・罠カード」。物件種類記 效果,條件式是
# 「誰的效果」:各項的或,照字面順序;項是大類,或 (大類, 子類型)。
EFFECT_HEADS = {"魔法・罠・モンスター": ("魔法", "陷阱", "怪獸"),
                "魔法・罠・効果モンスター": ("魔法", "陷阱", ("怪獸", "效果")),
                "モンスターの効果・魔法・罠カード": ("怪獸", "魔法", "陷阱")}
# 頭名詞的另一種寫法(m3 票 04):條件式同正規寫法,另帶 `text` 記字面。
HEAD_VARIANTS = {"魔法または罠カード": "魔法・罠カード", "モンスターカード": "モンスター"}
_HEADS = "|".join(sorted(list(HEAD_CATEGORY) + list(HEAD_SUBTYPE) + list(EFFECT_HEADS)
                         + list(HEAD_VARIANTS), key=len, reverse=True))
NOUN_RE = re.compile(
    f"^(?P<mods>.*?)(?P<head>{_HEADS})"
    "(?P<count>[０-９]+(?P<unit>体|枚)(?P<upto>まで)?)?$")
# 名稱修飾語(從左到右逐個認;「X」單獨出現只能緊接頭名詞,所以要在字串尾)。
_MOD_RES = (
    ("以外", re.compile("^「(?P<name>[^「」]+)」以外の")),
    ("と名のついた", re.compile("^「(?P<name>[^「」]+)」と名のついた")),
    ("卡名包含", re.compile("^カード名に「(?P<name>[^「」]+)」を含む")),
    ("字段", re.compile("^「(?P<name>[^「」]+)」$")),
)
# 「<名詞短語>以外の」(「チューナー以外の」「「彼岸」モンスター以外の」「光属性モンスター以外の」,m3 票 04):
# 非(那個名詞短語的條件)。名詞短語從這裡起到頭名詞為止、中間沒有「の」(「自分フィールドのチューナー以外の」
# 的「自分フィールドの」修飾的是外層);裡面只收卡片屬性的原子(`CARD_PROPERTY_OPS`)——狀態原子代入時
# 任何卡都算,包進「非」會變成任何卡都不算。「このカード以外の」「「X」以外の」「水属性以外の」照舊各走各的規則。
_EXCEPT_NOUN_RE = re.compile(
    f"^(?P<inner>(?:「[^「」]+」|[^の「」、])*?(?:{_HEADS}))以外の")
CARD_PROPERTY_OPS = ("大類", "屬性比較", "字段", "卡名", "卡名包含", "記載", "卡名範圍")
REASON_MODS = "物件修飾解析不出"
# 名詞短語的列舉「AかB」「AまたはB」:或,`form` 記連接的字面。
OR_FORM = "か"
OR_FORMS = ("または", OR_FORM)
_HEAD_TEXT = {v: k for k, v in HEAD_CATEGORY.items() if isinstance(v, str)}
_HEAD_TEXT[("魔法", "陷阱")] = "魔法・罠カード"
_SUBTYPE_HEAD_TEXT = {v: k for k, v in HEAD_SUBTYPE.items()}
JOINER_WORDS = ("", "・", "の")


def split_alternatives(mods, head):
    """物件短語的修飾語裡,頂層(「」外)的「か」「または」左邊是完整名詞短語(帶頭名詞、沒有數量)時才算
    列舉:回傳 (連接的字面, 各截名詞短語)(最後一截接回頭名詞);不是列舉回 None(「自分か相手の」
    「自分または相手の」是方,不在此列)。兩種連接字混用的不收。"""
    for form in OR_FORMS:
        pieces = _split_on(mods, form)
        if pieces:
            return form, pieces + [mods[sum(len(p) + len(form) for p in pieces):] + head]
    return None


def _split_on(mods, form):
    pieces, depth, last = [], 0, 0
    for i, ch in enumerate(mods):
        if ch == "「":
            depth += 1
        elif ch == "」":
            depth -= 1
        elif depth == 0 and i >= last and mods.startswith(form, i):
            left = NOUN_RE.match(mods[last:i])
            if left and not left.group("count"):
                pieces.append(mods[last:i])
                last = i + len(form)
    return pieces


def noun_condition(atoms, head):
    condition = category_condition(head)
    return {"op": "且", "args": atoms + [condition]} if atoms else condition


def _subtype_condition(category, subtype):
    return {"op": "且", "args": [{"op": "大類", "value": category},
                                {"op": "屬性比較", "attr": "卡片子類型",
                                 "cmp": "=", "value": subtype}]}


def _effect_condition(head):
    return {"op": "或", "args": [
        {"op": "大類", "value": item} if isinstance(item, str) else _subtype_condition(*item)
        for item in EFFECT_HEADS[head]]}


def category_condition(head):
    if head in HEAD_VARIANTS:
        return {**category_condition(HEAD_VARIANTS[head]), "text": head}
    if head in HEAD_SUBTYPE:
        return _subtype_condition(*HEAD_SUBTYPE[head])
    if head in EFFECT_HEADS:
        return _effect_condition(head)
    value = HEAD_CATEGORY[head]
    if isinstance(value, tuple):
        return {"op": "或", "args": [{"op": "大類", "value": v} for v in value]}
    return {"op": "大類", "value": value}


# ── 條件式:屬性比較的修飾語(種族、屬性);等級(レベルN、N以上/以下)與「・」列舉在
# attribute_atoms,名稱類的在 parse_modifiers ──
def parse_modifier(part):
    """一截修飾語 → 屬性比較原子;認不得回 None。"""
    if part in RACE_JA:
        return {"op": "屬性比較", "attr": "種族", "cmp": "=", "value": part}
    if part.endswith("属性") and part[:-2] in ATTRIBUTE_JA:
        return {"op": "屬性比較", "attr": "屬性", "cmp": "=", "value": part[:-2]}
    return None


def category_of(condition):
    if not condition:
        return None
    if condition.get("op") == "大類":
        return condition["value"]
    if condition.get("op") == "且":
        for arg in condition["args"]:
            found = category_of(arg)
            if found:
                return found
    if condition.get("op") == "或" and all(a.get("op") == "大類" for a in condition["args"]):
        return tuple(a["value"] for a in condition["args"])
    if condition.get("op") == "或" and condition.get("form") in OR_FORMS:
        found = {category_of(arg) for arg in condition["args"]}
        return found.pop() if len(found) == 1 else None
    return None


def parse_modifiers(state, mods):
    """修飾語 → (原子列表, 原因):名稱類的句型逐個認,其餘以「・」切成一截截給
    `parse_modifier`(種族、屬性、レベルN);認不得的那截以「解析不出」原子收尾。
    種族/屬性/等級原子與下一個修飾語之間實際寫的字(「・」「の」或沒有)與模板的預設寫法
    (`attribute_atoms.joiner`)不同時,記進該原子的 `joiner`(素材行「水属性レベル４」、
    「ドラゴン族のシンクロモンスター」)。"""
    atoms, reason, rest = [], None, mods
    dot_before, written_after = [], []
    dot = False

    def add(new_atoms, tail=""):
        nonlocal dot
        atoms.extend(new_atoms)
        dot_before.extend([dot] + [False] * (len(new_atoms) - 1))
        written_after.extend([tail] + [""] * (len(new_atoms) - 1))
        dot = False

    while rest:
        excepted = _parse_except_noun(state, rest)
        if excepted is not None:
            atom, why, length = excepted
            add([atom])
            reason = reason or why
            rest = rest[length:]
            continue
        # 種族/屬性的「・」列舉(含後面的「の」)整組先認:「ドラゴン族・鳥獣族」是或、
        # 「光・闇属性」逐截切會把「光」認不出。
        atom, length = parse_param_group(rest)
        if atom is not None:
            literal = rest[:length]
            dot = dot or literal.startswith("・")
            add([atom], "の" if is_param_atom(atom) and literal.endswith("の") else "")
            rest = rest[length:]
            continue
        if rest.startswith("・"):  # 列舉後接的其他修飾語(植物族・レベル１)
            dot = True
            rest = rest[1:]
        for kind, pattern in _MOD_RES:
            m = pattern.match(rest)
            if m:
                break
        else:
            piece, sep, remainder = rest.partition("・")
            atom = parse_modifier(piece)
            if atom is not None:
                add([atom])
                dot = bool(sep)
                rest = remainder
                continue
            extra = parse_atom_modifier(rest, state)   # 票 07 的原子(condition_atoms)
            if extra is None:
                atoms.append({"op": "解析不出", "text": rest})
                return atoms, reason or REASON_MODS
            new_atoms, why, end = extra
            if not new_atoms:
                atoms.append({"op": "解析不出", "text": rest})
                return atoms, reason or why
            add(new_atoms)
            reason = reason or why
            rest = rest[end:]
            continue
        if kind == "以外":
            atom, why = state.name_atom("卡名", m.group("name"))
            if atom:
                atom = {"op": "非", "arg": atom}
        elif kind == "卡名包含":
            atom, why = state.name_atom("卡名包含", m.group("name"))
        else:
            atom, why = state.name_atom(
                "字段", m.group("name"),
                form=kind if kind == "と名のついた" else None)
        if atom is None:
            atoms.append({"op": "解析不出", "text": rest})
            return atoms, reason or why
        add([atom])
        reason = reason or why
        rest = rest[m.end():]
    for i, atom in enumerate(atoms):
        if not is_param_atom(atom):
            continue
        following = atoms[i + 1] if i + 1 < len(atoms) else None
        written = written_after[i] + (
            "・" if following is not None and dot_before[i + 1] else "")
        if written != joiner(atom, following):
            atom["joiner"] = written
    return atoms, reason


def _parse_except_noun(state, rest):
    """開頭的「<名詞短語>以外の」→ (非 原子, 原因, 字面長度);不是、或裡面的名詞短語認不全就回 None。"""
    m = _EXCEPT_NOUN_RE.match(rest)
    inner = m and NOUN_RE.match(m.group("inner"))
    if not inner or inner.group("count"):
        return None
    atoms, why = parse_modifiers(state, inner.group("mods"))
    condition = noun_condition(atoms, inner.group("head"))
    if not _only_card_properties(condition):
        return None
    return {"op": "非", "arg": condition}, why, m.end()


def _only_card_properties(condition):
    op = condition.get("op")
    if op in ("且", "或"):
        return all(_only_card_properties(arg) for arg in condition["args"])
    if op == "非":
        return _only_card_properties(condition["arg"])
    return op in CARD_PROPERTY_OPS and "ref" not in condition


def _is_noun_condition(condition):
    """條件式是不是一個名詞短語(以頭名詞收尾)。"""
    if _render_head(condition):
        return True
    return condition.get("op") == "且" and bool(_render_head(condition["args"][-1]))


def _quoted(atom, names):
    """名稱原子 → 「X」;名稱列找不到就是無模板。"""
    text = quoted_name(atom, names)
    if text is None:
        raise NoTemplate("名稱原子引用的名稱列找不到")
    return text


def _render_atom(atom, names):
    """修飾語原子 → 字面:字段(「X」/「X」と名のついた)、「X」以外の、カード名に「X」を含む、
    屬性比較(種族名、「レベル１」、「光属性」);票 07 的原子(記載、卡名範圍、位置、
    卡片子類型、引用)的模板在 condition_atoms.render_atom,先問它。"""
    rendered = render_atom(atom, names)
    if rendered is not None:
        return rendered
    op = atom.get("op")
    if op == "字段":
        form = atom.get("form")
        if form not in (None, "と名のついた"):
            raise NoTemplate(f"字段寫法無模板:{form}")
        return _quoted(atom, names) + (form or "")
    if op == "非" and atom.get("arg", {}).get("op") == "卡名":
        return _quoted(atom["arg"], names) + "以外の"
    if op == "非" and is_param_atom(atom.get("arg", {})):
        arg = atom["arg"]
        text = render_group(arg) if arg.get("op") == "或" else _render_atom(arg, names)
        if text is None:
            raise NoTemplate("屬性比較無模板")
        return text + EXCEPT
    if op == "非" and _is_noun_condition(atom.get("arg", {})):
        return render_condition(atom["arg"], names) + EXCEPT
    if op == "卡名包含":
        return "カード名に" + _quoted(atom, names) + "を含む"
    number = render_number(atom)   # レベル１、レベル４以下、攻撃力１５００以下
    if number is not None:
        return number
    if op == "屬性比較" and atom.get("cmp") == "=":
        if atom["attr"] == "種族":
            return atom["value"]
        if atom["attr"] == "屬性":
            return atom["value"] + "属性"
        raise NoTemplate(f"屬性比較無模板:{atom['attr']}")
    if op == "解析不出":
        raise NoTemplate("物件條件無模板:解析不出")
    raise NoTemplate(f"物件條件無模板:{op}")


def _render_head(condition):
    """大類(與 魔法・罠 的或)、大類 且 子類型(チューナー)、效果的頭名詞 → 頭名詞;不是頭名詞回 None。"""
    op = condition.get("op")
    if "text" in condition:
        variant = condition["text"]
        return variant if (variant in HEAD_VARIANTS
                           and condition == category_condition(variant)) else None
    for head in EFFECT_HEADS:
        if condition == _effect_condition(head):
            return head
    if op == "大類":
        return _HEAD_TEXT[condition["value"]]
    if op == "或":
        values = tuple(a.get("value") for a in condition["args"]
                       if a.get("op") == "大類")
        if len(values) == len(condition["args"]) and values in _HEAD_TEXT:
            return _HEAD_TEXT[values]
    if op == "且" and len(condition["args"]) == 2:
        category, subtype = condition["args"]
        if (category.get("op") == "大類" and subtype.get("op") == "屬性比較"
                and subtype.get("attr") == "卡片子類型" and subtype.get("cmp") == "="):
            return _SUBTYPE_HEAD_TEXT.get((category["value"], subtype.get("value")))
    return None


def _render_modifiers(mods, names):
    """修飾語列表 → 字面:屬性比較之間與後面的「・」「の」照 attribute_atoms.joiner
    (魔法使い族・光属性、獣族・獣戦士族の炎属性、ドラゴン族の「ドラグニティ」)。"""
    out = []
    for i, atom in enumerate(mods):
        if not is_param_atom(atom):
            out.append(_render_atom(atom, names))
            continue
        text = render_group(atom) if atom.get("op") == "或" else _render_atom(atom, names)
        if text is None:
            raise NoTemplate("屬性比較無模板")
        written = atom.get("joiner")
        if written is not None and written not in JOINER_WORDS:
            raise NoTemplate("修飾語連接字無模板")
        out.append(text + (written if written is not None
                           else joiner(atom, mods[i + 1] if i + 1 < len(mods) else None)))
    return "".join(out)


def render_condition(condition, names):
    """條件式 → 名詞短語:且 = 修飾語(照字面順序,相鄰的屬性比較以「・」連)+ 頭名詞(且 的末項);
    單獨的卡名 = 「X」。"""
    if condition is None:
        raise NoTemplate("物件條件無模板:空")
    if condition.get("op") == "或" and condition.get("form") in OR_FORMS:
        return condition["form"].join(render_condition(arg, names) for arg in condition["args"])
    head = _render_head(condition)
    if head:
        return head
    op = condition.get("op")
    if op == "卡名":
        return _quoted(condition, names)
    if op == "或" and all(a.get("op") == "卡名" for a in condition["args"]):
        return "または".join(_quoted(a, names) for a in condition["args"])
    if op == "且":
        *mods, last = condition["args"]
        head = _render_head(last)
        if head is None:
            raise NoTemplate("物件條件無模板:且 的末項不是大類")
        return _render_modifiers(mods, names) + head
    return _render_atom(condition, names)
