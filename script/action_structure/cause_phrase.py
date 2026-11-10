"""原因(段的 `cause`)帶物件或方法的寫法:抽取與句型模板成對放在一起。

閉集字面(戦闘で、相手の効果で…)在 `segment_fields.CAUSE_FORMS`,由 `segment_fields.parse_cause`、
`render_cause` 處理;這裡加上要解物件的寫法:「「X」の効果で」(物件)、「融合召喚及び以下の方法で」
(召喚方式)、「Xとの戦闘では」(戰鬥的對手)、「Xの(効果を受けない)」(誰的效果)、
「ドロー以外の方法で」(方法)。
- 抽取:`parse_cause_phrase`;`CAUSE_ALT` 是各句型共用的原因槽正規式片段。
- 模板:`render_cause_phrase`。
"""

import re

from object_render import render_object
from segment_fields import (CAUSE_PATTERN, OWNER_JOINER, OWNER_PATTERN, OWNER_TEXT, parse_cause,
                            render_cause)
from structure_shape import NoTemplate
from synonyms import parse_predicates


# 原因(票 09 加):「「X」の効果で」= 某張卡的效果(物件);「融合召喚及び以下の方法で」= 召喚方式
# (「以下の方法」指後面的 ● 列舉)。閉集字面(戦闘で…)在 segment_fields.CAUSE_FORMS。
_NAMED_CAUSE = "「[^「」]+」の効果で"
SUMMON_METHODS = ("融合召喚", "S召喚", "X召喚", "L召喚", "儀式召喚", "P召喚", "以下の方法")
_METHOD_CAUSE = (f"(?:{'|'.join(SUMMON_METHODS)})(?:及び(?:{'|'.join(SUMMON_METHODS)}))*で")
# 「Xとの戦闘では」:戰鬥的對手是物件。「〜の(効果を受けない)」:誰的效果(OWNER_PATTERN)。
_BATTLE_CAUSE = "(?:「[^「」]*」|[^を、「」])+?との(?:戦闘では|戦闘で|戦闘によって)"
_BATTLE_CAUSE_RE = re.compile("^(?P<phrase>.+?)との(?P<tail>戦闘では|戦闘で|戦闘によって)$")
# 「ドロー以外の方法で手札に加わった」:原因是方法,`exclude` 記被排除的動作詞;
# 「X以外の」的 X 是同義表的述語字幹(目前只收ドロー,全庫 33 處)。
EXCLUDE_METHOD_TAIL = "以外の方法で"
EXCLUDE_METHOD_PATTERN = f"ドロー{EXCLUDE_METHOD_TAIL}"
CAUSE_EXCLUDE = "方法"
CAUSE_ALT = (f"{CAUSE_PATTERN}|{_NAMED_CAUSE}|{_METHOD_CAUSE}|{_BATTLE_CAUSE}|{OWNER_PATTERN}"
              f"|{EXCLUDE_METHOD_PATTERN}")
_NAMED_CAUSE_RE = re.compile(f"^(?P<name>「[^「」]+」)の効果で$")
_METHOD_CAUSE_RE = re.compile(f"^{_METHOD_CAUSE}$")
CAUSE_EFFECT_OF = "の効果で"
CAUSE_METHOD = "召喚方式"
REASON_CAUSE = "原因解析不出"


def parse_cause_phrase(state, text, sentence_start):
    """原因字面 → (cause 格, 原因):閉集字面(戦闘で…)、「「X」の効果で」(物件)、
    「融合召喚及び以下の方法で」(召喚方式);「Xとの戦闘では」(戰鬥的對手)與
    「Xの(効果を受けない)」(誰的效果,「A及びB」多個),物件記在 `objects`。"""
    cause = parse_cause(text)
    if cause is not None:
        return cause, None
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
    battle = _BATTLE_CAUSE_RE.match(text)
    if battle:
        obj_id, _, reason = state.object_at(battle.group("phrase"), sentence_start)
        if obj_id is None:
            return None, reason
        return {"kind": "戰鬥", "text": "との" + battle.group("tail"),
                "objects": [obj_id]}, None
    if text.endswith(OWNER_TEXT):
        objects = []
        for phrase in text[:-len(OWNER_TEXT)].split(OWNER_JOINER):
            obj_id, _, reason = state.object_at(phrase, sentence_start)
            if obj_id is None:
                return None, reason
            objects.append(obj_id)
        return {"kind": "效果", "text": OWNER_TEXT, "objects": objects}, None
    return None, REASON_CAUSE


def render_cause_phrase(cause, seg, card, objects, names, self_id):
    """原因:閉集字面(戦闘で…);「「X」の効果で」寫物件;召喚方式寫各方式以「及び」連接 + で;
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
    if cause and cause.get("object") is not None:
        obj = objects.get(cause["object"])
        if obj is None or cause.get("kind") != "效果" or cause.get("text") != CAUSE_EFFECT_OF:
            raise NoTemplate("原因無模板:效果的物件")
        return render_object(obj, seg, card, names, self_id=self_id) + CAUSE_EFFECT_OF
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
