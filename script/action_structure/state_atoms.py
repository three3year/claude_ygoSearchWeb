"""和「指誰」有關的修飾語原子:抽取與句型模板成對放在一起。

`condition_atoms.parse_modifier` 先問這裡的 `parse_modifier`,`condition_atoms.render_atom` 先問這裡的
`render_atom`;只修飾此卡的狀態字面由 `anaphora.self_state_atoms` 問 `parse_self_state`。
查詢判斷的代入規則在 `action_query.STATE_ATOMS`(這裡的原子都是狀態,任何卡都代得進去)。

- 此卡以外的「他の」:一律 非(同一張 此卡)(站主裁定)——與「このカード以外の」同一個結構,只差字面:
  {"op": "非", "arg": {"op": "同一張", "object": 此卡的物件 id}, "text": "他の"}。
- 召喚方式:連體子句「X召喚した/された」(融合召喚した、アドバンス召喚した、通常召喚された…)→
  {"op": "召喚方式", "value": 召喚系的動作詞, "text": 字面}。單獨的「特殊召喚された」不在這裡
  (那是 `曾被特殊召喚`)。
- 只修飾此卡的狀態(帶狀態的此卡,`parse_self_state`):
  - 本卡效果做的召喚:「この効果で/この方法で/このカードの①の効果で 特殊召喚した(された)」→ 召喚方式原子
    另帶 `by`(前綴字面)。
  - 本卡效果做的其他動作:「この効果でセットした」「この効果で除外した」→
    {"op": "曾被動作", "action": 動作詞, "by": 前綴字面, "text": 字面};動詞是動作回指的過去形
    (`synonyms.ACTION_PAST`)。
  - 裝備中:「装備されている」「装備状態の」「モンスターに装備されている」「装備カード扱いの」→
    {"op": "裝備中", "text": 字面}(這張卡正當成裝備卡裝在怪獸上;與 `被裝備者` 是裝備關係的兩端)。
    頭名詞「装備カード」的「装備」也是這個原子(`noun_phrase.HEAD_STATE`)。
"""
import re

from synonyms import ACTION_PAST, PREDICATE_STEMS, SUMMON_STEMS, is_summon

SAME_CARD = "同一張"
OTHER = "他の"
_OTHER_RE = re.compile(f"^{OTHER}")
SUMMON_METHOD = "召喚方式"
ACTED_BY_EFFECT = "曾被動作"
EQUIPPED_ON = "裝備中"
EQUIPPED_ON_FORMS = ("モンスターに装備されている", "装備されている", "装備状態の", "装備カード扱いの")
_EQUIPPED_ON_RE = re.compile("^(?:" + "|".join(EQUIPPED_ON_FORMS) + ")")
_STEM_ACTION = {stem: action for stem, action, _ in PREDICATE_STEMS}
_SUMMON_ALT = "|".join(SUMMON_STEMS)
# 單獨的「特殊召喚された」是 曾被特殊召喚(沒寫出發地),不在召喚方式裡。
PLAIN_SPECIAL_SUMMONED = "特殊召喚された"
_SUMMONED_RE = re.compile(f"^(?P<stem>{_SUMMON_ALT})(?:した|された)")
# 本卡自己的效果(「この効果で」「この方法で」「このカードの①の効果で」「このカードの効果で」)。
BY_OWN_EFFECT = "(?:このカードの(?:[①-⑳]の)?|この)(?:効果|方法)で"
_BY_SUMMONED_RE = re.compile(f"^(?P<by>{BY_OWN_EFFECT})(?P<stem>{_SUMMON_ALT})(?:した|された)")
_PAST_ACTION = {past: action for action, past in ACTION_PAST.items() if not is_summon(action)}
_BY_ACTED_RE = re.compile(
    f"^(?P<by>{BY_OWN_EFFECT})"
    f"(?P<past>{'|'.join(sorted(_PAST_ACTION, key=len, reverse=True))})")


def other_than_this_atom(self_id):
    """「他の」→ 非(同一張 此卡);字面記在 非 原子上(「このカード以外の」的字面在裡面那個原子上)。"""
    return {"op": "非", "arg": {"op": SAME_CARD, "object": self_id}, "text": OTHER}


def _summon_method(text):
    """開頭的「X召喚した/された」→ (召喚方式原子, 長度);不是回 (None, 0)。"""
    m = _SUMMONED_RE.match(text)
    if not m or m.group() == PLAIN_SPECIAL_SUMMONED:
        return None, 0
    return {"op": SUMMON_METHOD, "value": _STEM_ACTION[m.group("stem")], "text": m.group()}, m.end()


def parse_modifier(rest, state):
    """修飾語開頭認得的原子 → (原子列表, 原因, 吃掉的長度);不是這裡管的回 None。"""
    m = _OTHER_RE.match(rest)
    if m:
        return [other_than_this_atom(state.self_id)], None, m.end()
    atom, length = _summon_method(rest)
    if atom is not None:
        return [atom], None, length
    return None


def parse_self_state(text):
    """只修飾此卡的狀態字面(本卡效果做的召喚或動作、裝備中)→ (原子, 長度);不是回 (None, 0)。
    這幾種寫法接在一般名詞前不是同一個意思(「この効果で特殊召喚したモンスター」是動作回指),所以不放進
    `parse_modifier`。"""
    m = _BY_SUMMONED_RE.match(text)
    if m:
        return {"op": SUMMON_METHOD, "value": _STEM_ACTION[m.group("stem")],
                "by": m.group("by"), "text": m.group()}, m.end()
    m = _BY_ACTED_RE.match(text)
    if m:
        return {"op": ACTED_BY_EFFECT, "action": _PAST_ACTION[m.group("past")],
                "by": m.group("by"), "text": m.group()}, m.end()
    m = _EQUIPPED_ON_RE.match(text)
    if m:
        return {"op": EQUIPPED_ON, "text": m.group()}, m.end()
    return None, 0


def render_atom(atom):
    """原子 → 修飾語字面;不是這裡管的原子回 None。字面要照抽取規則拆得回同一個原子才寫。"""
    op, text = atom.get("op"), atom.get("text") or ""
    if (op == "非" and text == OTHER and atom.get("arg", {}).get("op") == SAME_CARD
            and atom["arg"].get("object")):
        return OTHER
    if op in (SUMMON_METHOD, ACTED_BY_EFFECT, EQUIPPED_ON):
        parsed, length = _summon_method(text)
        if parsed is None:
            parsed, length = parse_self_state(text)
        return text if parsed == atom and length == len(text) else None
    return None
