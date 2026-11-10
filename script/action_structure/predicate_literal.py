"""原述語字面(段的 `predicate`):串接與拆開成對放在一起。

簡單子句的原述語字面 = 取對象字面 + 選取字面 + 述語本身,抽取端用 `join_predicate_literal` 串、
反向檢查端用 `split_predicate_literal` 拆;兩邊只走這一對函式,順序才不會各寫各的。
`render_predicate` 驗述語那一截拆得回段的動作詞、態、極性;`check_predicate` 是不帶前綴的版本。
"""
from typing import NamedTuple

from segment_fields import resolve_polarity
from structure_shape import NoTemplate
from synonyms import SELECT_PREFIX, TARGETING_PREFIXES, attack_times, merged_voice, parse_predicates


class PredicateLiteral(NamedTuple):
    """原述語字面(段的 `predicate`)拆開的三截。"""
    targeting: str | None   # 取對象字面(「選択して」「対象として」)
    select: str | None      # 選取字面(「選んで」)
    predicate: str          # 述語本身:查同義表、驗態與極性的那一截


def join_predicate_literal(targeting, select, predicate):
    """抽取端:句型切出的取對象字面、選取字面、述語 → 原述語字面(照原文順序串接)。"""
    return (targeting or "") + (select or "") + predicate


def split_predicate_literal(text):
    """反向檢查端:原述語字面 → 三截,是 `join_predicate_literal` 的反向。
    取對象字面與「選んで」都寫的句子抽取端照樣串接,但這裡只拆得回取對象字面(「選んで」留在述語那一截、
    查不到同義表),那種段沒有模板。"""
    targeting, rest = _split_targeting(text)
    select, rest = _split_select(rest) if targeting is None else (None, rest)
    return PredicateLiteral(targeting, select, rest)


def _split_select(pred):
    """述語字面 → (選取字面或 None, 其餘述語)。「選んで破壊する」→ ("選んで", "破壊する")。"""
    if pred.startswith(SELECT_PREFIX):
        return SELECT_PREFIX, pred[len(SELECT_PREFIX):]
    return None, pred


def _split_targeting(pred):
    """述語字面 → (取對象字面或 None, 其餘述語)。「選択して破壊する」→ ("選択して", "破壊する");
    單獨的「選択して」(發動句的取對象宣告)→ ("選択して", "")。"""
    for prefix in TARGETING_PREFIXES:
        if pred.startswith(prefix):
            return prefix, pred[len(prefix):]
    return None, pred


def render_predicate(seg, marker):
    """述語字面必須能拆回段的動作詞、態、極性(多動作詞是て形串接;「Xは〜できる」的極性是可以,
    與抽取端同一把尺 resolve_polarity);開頭的取對象字面(「選択して」「対象として」)拆出來、
    單獨出現時是沒有動作詞的取對象宣告;「選んで」同一個位置、同樣拆法,但不標取對象。
    回傳 (取對象字面或 None, 選取字面或 None, 述語字面, 述語寫明的終點)。"""
    if not seg["predicate"]:
        raise NoTemplate("段無動作詞")
    prefix, select, rest = split_predicate_literal(seg["predicate"])
    if not rest:
        if seg["actions"] or (seg["voice"], seg["polarity"], seg["optional"]) != (None, "做", None):
            raise NoTemplate("取對象宣告帶了動作詞")
        return prefix, select, "", None
    if not seg["actions"]:
        raise NoTemplate("段無動作詞")
    parsed, _ = parse_predicates(rest)
    if parsed is None or [p.action for p in parsed] != seg["actions"]:
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
    polarity, optional = resolve_polarity(parsed, marker)
    if (merged_voice(parsed), polarity, optional) != (seg["voice"], seg["polarity"],
                                                      seg["optional"]):
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
    if attack_times(rest) != seg["times"]:
        raise NoTemplate("攻擊次數與述語字面不一致")
    return prefix, select, rest, next((p.to for p in parsed if p.to), None)


def check_predicate(seg, parsed):
    if parsed is None or [p.action for p in parsed] != seg["actions"]:
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
    polarity, optional = resolve_polarity(parsed, None)
    if (merged_voice(parsed), polarity, optional) != (seg["voice"], seg["polarity"],
                                                      seg["optional"]):
        raise NoTemplate("述語字面與動作詞、態、極性不一致")
