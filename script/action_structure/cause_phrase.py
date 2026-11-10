"""原因(段的 `cause`)帶物件或方法的寫法:抽取與句型模板成對放在一起。

閉集字面(戦闘で、相手の効果で…)在 `segment_fields.CAUSE_FORMS`,由 `segment_fields.parse_cause`、
`render_cause` 處理;這裡加上要解物件的寫法:「「X」の効果で」(物件)、「融合召喚及び以下の方法で」
(召喚方式)、「Xとの戦闘では」(戰鬥的對手)、「Xの(効果を受けない)」(誰的效果)、
「ドロー以外の方法で」(方法)、「「X」により(降臨)」(物件)。
也收:「「X」モンスターの効果で/によって」(物件是名詞短語)、
「この効果で/この方法で/このカードの①の効果で(〜召喚に成功した)」(本卡自己的效果,指向做那次召喚的段)。
- 抽取:`parse_cause_phrase`;`CAUSE_ALT` 是各句型共用的原因槽正規式片段。
- 模板:`render_cause_phrase`。
"""

import re

from block_state import REASON_REF
from object_render import render_object
from segment_fields import (CAUSE_MATERIAL, CAUSE_PATTERN, MATERIAL_FORMS, OWNER_JOINER,
                            OWNER_PATTERN, OWNER_TEXT, parse_cause, render_cause)
from segment_history import segments_before
from structure_shape import NoTemplate
from synonyms import action_ancestors, is_summon, parse_predicates


# 原因:「「X」の効果で」= 某張卡的效果(物件);「融合召喚及び以下の方法で」= 召喚方式
# (「以下の方法」指後面的 ● 列舉)。閉集字面(戦闘で…)在 segment_fields.CAUSE_FORMS。
_NAMED_CAUSE = "「[^「」]+」の効果で"
SUMMON_METHODS = ("融合召喚", "S召喚", "X召喚", "L召喚", "儀式召喚", "P召喚", "以下の方法")
# 「P召喚できる」「融合召喚できない」的「で」是述語語尾「できる」的一部分,不是「〜召喚で」。
_METHOD_CAUSE = (f"(?:{'|'.join(SUMMON_METHODS)})(?:及び(?:{'|'.join(SUMMON_METHODS)}))*で(?!き)")
# 「Xとの戦闘では」:戰鬥的對手是物件。「〜の(効果を受けない)」:誰的效果(OWNER_PATTERN)。
_BATTLE_CAUSE = "(?:「[^「」]*」|[^を、「」])+?との(?:戦闘では|戦闘で|戦闘によって)"
_BATTLE_CAUSE_RE = re.compile("^(?P<phrase>.+?)との(?P<tail>戦闘では|戦闘で|戦闘によって)$")
# 「ドロー以外の方法で手札に加わった」:原因是方法,`exclude` 記被排除的動作詞;
# 「X以外の」的 X 是同義表的述語字幹(只收ドロー,全庫 33 處)。
EXCLUDE_METHOD_TAIL = "以外の方法で"
EXCLUDE_METHOD_PATTERN = f"ドロー{EXCLUDE_METHOD_TAIL}"
CAUSE_EXCLUDE = "方法"
# 「「剣闘獣」と名のついたモンスターの効果によって」「「夢魔鏡」モンスターの効果で」:
# 某(類)卡的效果,物件是以 モンスター/カード 收尾的名詞短語。短語裡不收主語的助詞(が、は;「または」除外),
# 免得把「このカードがモンスターの効果で」整截吃成物件,也不收「から」(「手札またはデッキからカードの効果によって」
# 的前半是從);「戦闘またはXの効果で」是戰鬥與效果的或,現有的格記不了,不認。
EFFECT_OF_TAILS = ("の効果によって", "の効果で")
_OBJECT_EFFECT_CAUSE = ("(?!戦闘)(?:「[^「」]*」|または|(?!から)[^を、「」がは])*?(?:モンスター|カード)"
                        "の効果(?:によって|で)")
_OBJECT_EFFECT_RE = re.compile(
    f"^(?P<phrase>.+?(?:モンスター|カード))(?P<tail>{'|'.join(EFFECT_OF_TAILS)})$")
# 本卡自己的效果當原因:「この効果で/この方法で/このカードの①の効果で 特殊召喚に成功した」。
# 只在後面是「〜召喚に成功」時認(「この効果で特殊召喚したモンスター」是動作回指,不走這裡)。
_SELF_EFFECT_CAUSE = ("(?:このカードの[①-⑳]の|この)(?:効果|方法)(?:によって|で)"
                      "(?=[^、。]*召喚に成功)")
_SELF_EFFECT_RE = re.compile(
    "^(?:このカードの(?P<label>[①-⑳])の|この)(?:効果|方法)(?:によって|で)$")
# 「「トリックスター」LモンスターのL素材として(墓地へ送られた)」:作為素材,帶被召喚怪獸的物件。
# 物件是以 モンスター 收尾的名詞短語,不收主語的助詞與「から」(同 `_OBJECT_EFFECT_CAUSE`)。
_MATERIAL_ALT = "|".join(sorted(map(re.escape, MATERIAL_FORMS), key=len, reverse=True))
MATERIAL_OF = "の"
_MATERIAL_OF_CAUSE = ("(?:「[^「」]*」|または|(?!から)[^を、「」がは])*?モンスター"
                      f"{MATERIAL_OF}(?:{_MATERIAL_ALT})")
_MATERIAL_OF_RE = re.compile(
    f"^(?P<phrase>.+?モンスター){MATERIAL_OF}(?P<form>{_MATERIAL_ALT})$")
# 「「X」により降臨」:X(儀式魔法的物件短語)的效果;只認後面緊接「降臨」的,
# 「により」單獨不是原因字面。
CAUSE_BY = "により"
DESCENT_STEM = "降臨"
DESCENT_TAIL = CAUSE_BY + DESCENT_STEM
_DESCENT_CAUSE = f"(?:「[^「」]*」|[^を、「」])+?{CAUSE_BY}(?={DESCENT_STEM})"
CAUSE_ALT = (f"{CAUSE_PATTERN}|{_NAMED_CAUSE}|{_METHOD_CAUSE}|{_BATTLE_CAUSE}|{OWNER_PATTERN}"
             f"|{EXCLUDE_METHOD_PATTERN}|{_SELF_EFFECT_CAUSE}|{_OBJECT_EFFECT_CAUSE}"
             f"|{_DESCENT_CAUSE}|{_MATERIAL_OF_CAUSE}")
_NAMED_CAUSE_RE = re.compile(f"^(?P<name>「[^「」]+」)の効果で$")
_METHOD_CAUSE_RE = re.compile(f"^{_METHOD_CAUSE}$")
CAUSE_EFFECT_OF = "の効果で"
CAUSE_METHOD = "召喚方式"
REASON_CAUSE = "原因解析不出"


def _related(action, other):
    """兩個動作詞有上下位關係(含相同):特殊召喚 與 融合召喚、召喚 與 上級召喚。"""
    return action in action_ancestors(other) or other in action_ancestors(action)


def source_segment(earlier_blocks, earlier_segments, label, actions):
    """「この効果/この方法/このカードの①の効果(で〜召喚に成功した)」指的那一段:寫了編號就在那個編號的
    區塊裡找,沒寫就從這一段往前找(同區塊先前的段,再往前面的區塊);取最近一個做了那種召喚的段
    (動作詞與 `actions` 有上下位關係;條件段與不能/不會的段不是「做了」)。找不到回 None。
    抽取與模板共用這一把尺。"""
    if label:
        candidates = [seg for block in earlier_blocks if block["label"] == label
                      for seg in block["segments"]]
    else:
        candidates = [seg for block in earlier_blocks for seg in block["segments"]]
        candidates.extend(earlier_segments)
    for seg in reversed(candidates):
        if (seg["kind"] not in ("條件", "被代替") and seg["polarity"] not in ("不能", "不會")
                and any(is_summon(a) and _related(a, wanted)
                        for a in seg["actions"] for wanted in actions)):
            return seg
    return None


def summoned_by(source):
    """那一段召喚的物件(主語省略的「この効果で特殊召喚に成功した」的被召喚者)。不是恰好一條線、
    或那一段還串著別的動作(「Xをリリースして召喚する」的線是被解放的 X)就判不了。"""
    if len(source["lines"]) != 1 or not all(is_summon(a) for a in source["actions"]):
        return None
    return source["lines"][0]["object"]


def parse_cause_phrase(state, text, sentence_start, actions=()):
    """原因字面 → (cause 格, 原因):閉集字面(戦闘で…)、「「X」の効果で」(物件)、
    「融合召喚及び以下の方法で」(召喚方式);「Xとの戦闘では」(戰鬥的對手)與
    「Xの(効果を受けない)」(誰的效果,「A及びB」多個),物件記在 `objects`。
    `actions` 是這一段的動作詞:「この効果で(〜召喚に成功した)」靠它找做那次召喚的段,
    原因記 {"kind": 效果, "text": 字面, "segment": 那一段的 id}。"""
    cause = parse_cause(text)
    if cause is not None:
        return cause, None
    own = _SELF_EFFECT_RE.match(text)
    if own:
        source = source_segment(state.card["blocks"], state.block["segments"],
                                own.group("label"), actions)
        if source is None:
            return None, REASON_REF
        return {"kind": "效果", "text": text, "segment": source["id"]}, None
    if text.endswith(EXCLUDE_METHOD_TAIL):
        parsed, reason = parse_predicates(text[:-len(EXCLUDE_METHOD_TAIL)])
        if parsed is None:
            return None, REASON_CAUSE
        return {"kind": CAUSE_EXCLUDE, "exclude": [p.action for p in parsed],
                "text": text}, None
    named = _NAMED_CAUSE_RE.match(text)
    if named:
        obj_id, _, reason = state.object_at(named.group("name"), sentence_start)
        if obj_id is None:
            return None, reason
        return {"kind": "效果", "text": CAUSE_EFFECT_OF, "object": obj_id}, None
    if _METHOD_CAUSE_RE.match(text):
        return {"kind": CAUSE_METHOD, "text": text,
                "methods": text[:-1].split("及び")}, None
    material_of = _MATERIAL_OF_RE.match(text)
    if material_of:
        obj_id, _, reason = state.object_at(material_of.group("phrase"), sentence_start)
        if obj_id is None:
            return None, reason
        return {**parse_cause(material_of.group("form")), "object": obj_id}, None
    effect_of = _OBJECT_EFFECT_RE.match(text)
    if effect_of:
        obj_id, _, reason = state.object_at(effect_of.group("phrase"), sentence_start)
        if obj_id is None:
            return None, reason
        return {"kind": "效果", "text": effect_of.group("tail"), "object": obj_id}, None
    battle = _BATTLE_CAUSE_RE.match(text)
    if battle:
        obj_id, _, reason = state.object_at(battle.group("phrase"), sentence_start)
        if obj_id is None:
            return None, reason
        return {"kind": "戰鬥", "text": "との" + battle.group("tail"),
                "objects": [obj_id]}, None
    if text.endswith(CAUSE_BY):
        obj_id, ref, reason = state.object_at(text[:-len(CAUSE_BY)], sentence_start)
        if obj_id is None:
            return None, reason
        cause = {"kind": "效果", "text": CAUSE_BY, "object": obj_id}
        if ref is not None:
            # 以自己的卡名寫的(P 效果讓自己降臨的儀式怪獸):物件0,回指字面是卡名。
            cause["ref"] = ref
        return cause, None
    if text.endswith(OWNER_TEXT):
        objects = []
        for phrase in text[:-len(OWNER_TEXT)].split(OWNER_JOINER):
            obj_id, _, reason = state.object_at(phrase, sentence_start)
            if obj_id is None:
                return None, reason
            objects.append(obj_id)
        return {"kind": "效果", "text": OWNER_TEXT, "objects": objects}, None
    return None, REASON_CAUSE


def _render_self_effect(cause, seg, card, objects):
    """本卡自己的效果:字面照寫,但指的段要與 `source_segment` 重算的相同;主語省略的線的物件要是
    那一段召喚的物件,而且那個物件解析得出(省略的線沒有字面可驗,物件解析不出就不算寫得回)。"""
    own = _SELF_EFFECT_RE.match(cause.get("text") or "")
    source = own and source_segment(*segments_before(seg, card), own.group("label"),
                                    seg["actions"])
    if not source or cause.get("kind") != "效果" or source["id"] != cause["segment"]:
        raise NoTemplate("原因無模板:本卡的效果")
    for line in seg["lines"]:
        if line.get("elided") and (line["object"] != summoned_by(source)
                                   or objects[line["object"]]["unparsed"]):
            raise NoTemplate("原因無模板:本卡的效果召喚的不是主語")
    return cause["text"]


def render_cause_phrase(cause, seg, card, objects, names, self_id):
    """原因:閉集字面(戦闘で…);「「X」の効果で」「「X」により」寫物件 + 字面;召喚方式寫各方式以「及び」連接 + で;
    帶 `objects` 的寫各物件以「及び」連接 + 字面(「との戦闘では」「の」)。"""
    if cause and cause.get("objects"):
        expected = {"戰鬥": ("との戦闘では", "との戦闘で", "との戦闘によって"),
                    "效果": (OWNER_TEXT,)}.get(cause.get("kind"), ())
        if (cause.get("text") not in expected
                or any(o not in objects for o in cause["objects"])
                or (cause["kind"] == "戰鬥" and len(cause["objects"]) != 1)):
            raise NoTemplate("原因無模板:物件")
        return OWNER_JOINER.join(render_object(objects[o], seg, card, names, self_id=self_id)
                                 for o in cause["objects"]) + cause["text"]
    if cause and cause.get("object") is not None and cause.get("kind") == CAUSE_MATERIAL:
        # 作為素材 帶被召喚怪獸:[物件]の[素材として]。
        obj = objects.get(cause["object"])
        if obj is None:
            raise NoTemplate("原因無模板:素材的物件")
        return (render_object(obj, seg, card, names, self_id=self_id) + MATERIAL_OF
                + render_cause({k: v for k, v in cause.items() if k != "object"}))
    if cause and cause.get("object") is not None:
        obj = objects.get(cause["object"])
        if (obj is None or cause.get("kind") != "效果"
                or cause.get("text") not in EFFECT_OF_TAILS + (CAUSE_BY,)):
            raise NoTemplate("原因無模板:效果的物件")
        line = {"ref": cause["ref"]} if cause.get("ref") else None
        return render_object(obj, seg, card, names, line, self_id=self_id) + cause["text"]
    if cause and cause.get("segment") is not None:
        return _render_self_effect(cause, seg, card, objects)
    if cause and cause.get("kind") == CAUSE_EXCLUDE:
        text = cause.get("text") or ""
        parsed, _ = (parse_predicates(text[:-len(EXCLUDE_METHOD_TAIL)])
                     if text.endswith(EXCLUDE_METHOD_TAIL) else (None, None))
        if parsed is None or [p.action for p in parsed] != cause.get("exclude"):
            raise NoTemplate("原因無模板:方法")
        return text
    if cause and cause.get("kind") == CAUSE_METHOD:
        methods = cause.get("methods") or []
        if any(m not in SUMMON_METHODS for m in methods) \
                or "及び".join(methods) + "で" != cause.get("text"):
            raise NoTemplate("原因無模板:召喚方式")
        return cause["text"]
    return render_cause(cause)
