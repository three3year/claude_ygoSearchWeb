"""素材句型裡「誰的素材」那一格(m3 票 09):抽取與句型模板成對放在一起。

簡單子句述語前的一格(`OWNER_SLOT`):「XをYの下に重ねてX素材とする」「XをYのX素材とする/にする」
「XをYのL素材とする場合」的 Y。
- 成為超量素材(效果把 X 疊到超量怪獸 Y 下面):X 的對象線的到是 Y 的超量素材物件
  (`{"kind": 超量素材, "of": Y, "of_ref": 回指字面}`),不是區域——
  到 `{"zones": [], "source": 明寫, "text": 這一格的字面(「そのモンスターの下に」「このカードの」「下に」「その」),
  "object": 超量素材物件 id}`。不移動到區域,不進推得表。
- 沒寫 Y(「このカードを下に重ねてX素材とする」)或只寫「その」(「このカードをそのX素材とする」):Y 是同一句
  前面剛特殊召喚出來的那一隻(`BlockState.last_summoned`),沒有就標指回的物件找不到;模板要前一段就是
  召喚它的段才寫得回。
- 作為素材 帶 Y(「自分フィールドのLモンスターをサイバース族LモンスターのL素材とする場合」):Y 是要召喚的怪獸,
  記在段的受方 `{"object": Y, "ref": 回指字面, "particle": "の"}`。
"""

from block_state import OBJECT_MATERIAL, REASON_CLAUSE, REASON_REF, REASON_TWICE, summoned_object
from object_render import render_object
from segment_history import previous_segment
from structure_shape import NoTemplate, new_object, position, unparsed
from synonyms import (MATERIAL_ACTION, MATERIAL_NOUNS, MATERIAL_OWNER_PARTICLE,
                      MATERIAL_SUMMON_KINDS, XYZ_ATTACH_ACTION, XYZ_MATERIAL_WORDS)

STACK_UNDER = "下に"
STACK_VERB = "重ねて"
# 只寫「その」的所屬(「そのX素材とする」「その下に重ねて」):回指,沒有頭名詞。
BARE_OWNER = "その"
# 後面緊接素材名詞 + と/に 的位置(lookahead):所屬的「Yの」只在這種述語前才認。
_MATERIAL_AHEAD = ("(?=(?:" + "|".join(f"{kind}の素材" for kind in MATERIAL_SUMMON_KINDS) + "|"
                   + "|".join(MATERIAL_NOUNS) + ")(?:と|に))")
# 簡單子句述語前的一格:[Yの|その][下に];「下に」後面一定是「重ねて」。
# 「X召喚の素材とする」的「X召喚の」是述語的一部分,不是所屬。
OWNER_SLOT = (f"(?:(?P<material_owner>{BARE_OWNER}|(?:「[^「」]*」|[^を、「」])+?{MATERIAL_OWNER_PARTICLE}"
              f"(?<!召喚{MATERIAL_OWNER_PARTICLE}))?"
              f"(?:(?P<under>{STACK_UNDER})(?={STACK_VERB})|{_MATERIAL_AHEAD}))?")
RECIPIENT_OF = MATERIAL_OWNER_PARTICLE


def is_owned(owner_literal, under):
    """述語前寫了所屬而沒有「下に」:查同義表前要把「の」接回去(`synonyms.parse_material_predicates`)。"""
    return bool(owner_literal) and not under


def attaches_without_owner(parsed, pred, kind):
    """效果段的「このカードをX素材とする」(沒寫所屬、沒有「重ねて」):效果裡拿卡「當超量素材」就是疊到
    超量怪獸下面——成為超量素材,所屬是剛召喚出來的那一隻;條件段的「〜をX素材とする場合」仍是 作為素材。"""
    return (kind == "效果" and [(p.action, p.polarity, p.optional) for p in parsed or ()]
            == [(MATERIAL_ACTION, "做", False)] and pred.startswith(XYZ_MATERIAL_WORDS))


def _resolve_owner(state, literal, sentence_start):
    """所屬字面 → (物件 id, 回指字面, 原因)。沒寫或只寫「その」時是本句剛特殊召喚出來的物件。"""
    if literal in (None, BARE_OWNER):
        if state.last_summoned is None:
            return None, None, REASON_REF
        return state.last_summoned, literal, None
    return state.object_at(literal[:-len(MATERIAL_OWNER_PARTICLE)], sentence_start)


def fill_owner(seg, state, literal, under, predicate_offset, sentence_start):
    """述語前的所屬格 → 成為超量素材時回傳每條對象線要用的到(工廠函式),作為素材時寫段的受方並回 None;
    解析不出就在段上標原因並回 None。`predicate_offset` 是述語在區塊原文的位置,超量素材物件的 id 取述語裡
    素材名詞(X素材)的位置。要在這一句的物件建立之前呼叫:「手札のXを、そのモンスターの下に重ねて」的
    「そのモンスター」指的是前文的怪獸,不是 X。"""
    attaching = seg["actions"] == [XYZ_ATTACH_ACTION]
    if not attaching and (under or literal == BARE_OWNER
                          or seg["actions"] != [MATERIAL_ACTION]):
        seg["unparsed"] = unparsed(REASON_CLAUSE)
        return None
    owner_id, ref, reason = _resolve_owner(state, literal, sentence_start)
    if owner_id is None:
        seg["unparsed"] = unparsed(reason)
        return None
    if not attaching:
        if seg["recipient"] is not None:
            seg["unparsed"] = unparsed(REASON_TWICE)
            return None
        seg["recipient"] = {"object": owner_id, "ref": ref, "particle": RECIPIENT_OF}
        return None
    block_text = state.block["text"]
    word_offset, word = min((block_text.find(w, predicate_offset), w) for w in XYZ_MATERIAL_WORDS
                            if block_text.find(w, predicate_offset) >= 0)
    material = new_object(f"{state.block['id']}.o{word_offset}", {"kind": "新建"}, text=word,
                          span=(word_offset, word_offset + len(word)), block=state.block["id"],
                          kind=OBJECT_MATERIAL)
    material["of"] = owner_id
    if ref is not None:
        material["of_ref"] = ref
    state.card["objects"].append(material)
    text = (literal or "") + (under or "")

    def attached():
        to = position([], "明寫", text=text)
        to["object"] = material["id"]
        return to
    return attached


def is_attached(line):
    """這條線的到是超量素材物件(成為超量素材),不是區域。"""
    return bool(line["to"]) and line["to"].get("object") is not None


def render_owner(seg, lines, card, objects, names, self_id):
    """成為超量素材的所屬格 → 字面(「そのモンスターの下に」「このカードの」「下に」「その」);段沒有這一格回空字串。
    `lines` 是物件槽的對象線(主語的線不算)。字面由超量素材物件的所屬重寫,要與到的 `text` 相符;
    沒寫所屬(或只寫「その」)時,所屬要是前一段召喚的物件。"""
    attached = [line for line in lines if is_attached(line)]
    if not attached:
        return ""
    to = attached[0]["to"]
    material = objects.get(to["object"])
    if (len(attached) != len(lines) or any(line["to"] != to for line in attached)
            or seg["actions"] != [XYZ_ATTACH_ACTION] or to["zones"] or to["form"]
            or to["source"] != "明寫" or material is None
            or material["kind"] != OBJECT_MATERIAL or material["condition"] is not None
            or material.get("of") not in objects):
        raise NoTemplate("成為超量素材的到無模板")
    owner = objects[material["of"]]
    if any(line["object"] == owner["id"] for line in seg["lines"]):
        raise NoTemplate("超量素材的所屬卡就是被疊的卡")
    text = to["text"] or ""
    under = STACK_UNDER if text.endswith(STACK_UNDER) else ""
    literal = text[:len(text) - len(under)]
    ref = material.get("of_ref")
    if literal in ("", BARE_OWNER):
        earlier = previous_segment(seg, card)
        if (ref or "") != literal or earlier is None or summoned_object(earlier) != owner["id"]:
            raise NoTemplate("沒寫所屬卡的超量素材無模板")
        return text
    written = (render_object(owner, seg, card, names, {"ref": ref}, self_id=self_id)
               + MATERIAL_OWNER_PARTICLE)
    if written != literal:
        raise NoTemplate("成為超量素材的所屬字面無模板")
    return written + under


def render_recipient_of(recipient, seg, card, objects, names, self_id):
    """作為素材 的受方(「サイバース族LモンスターのL素材とする」的 Y)→ 物件字面 +「の」。"""
    obj = objects.get(recipient.get("object"))
    if obj is None or recipient.get("particle") != RECIPIENT_OF or seg["actions"] != [MATERIAL_ACTION]:
        raise NoTemplate("素材的受方無模板")
    return (render_object(obj, seg, card, names, {"ref": recipient.get("ref")}, self_id=self_id)
            + RECIPIENT_OF)
