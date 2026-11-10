"""傷害與回復:句型、填格(`fill_clause`)與句型模板(`render_clause`)成對放在一起。

- 動作詞傷害:「与える」「受ける」同一個動作詞,`recipient` 是受傷的一方、`predicate` 留字面
  (「与えた」「受ける」);動作詞回復(「回復する」)形狀同傷害。
- 受方是玩家時記 `{"side": 方, "text": 字面}`,字面 = 玩家字面(閉集 `PLAYER_WORDS`)+ 接法
  (依句型的閉集 `DEAL_TAILS`、`RECEIVE_TAILS`、`MODIFY_TAILS`、`RECOVER_TAILS`);寫在傷害名詞前的
  「Xに」另帶 `placement: 名詞前`。「自分は１０００ダメージを受ける」的自分是受方、不是物件。
- 施事:「このカードが相手に戦闘ダメージを与えた」的主語是物件 → 對象線角色「施事」(助詞が);
  主語是玩家(自分/相手)→ `agent`。
- 數量 `amount`:固定值 `{"text", "value", "unit"}`(unit:ダメージ、ポイント、LP、ライフポイント;
  「６００ダメージ」的 ダメージ 是 unit,傷害名詞就不另寫);算式只記字面
  `{"kind": "算式", "text"}`(「〜の数×２００ポイント」「〜分の」「受けたダメージと同じ」;以「だけ」
  收尾的寫在受方前)。
- 原因:動詞型(「戦闘・効果で」「相手のカードの効果によって」)照 `segment_fields.CAUSE_FORMS`,
  寫在受方主語前的另帶 `placement: 主語前`;名詞型(「戦闘ダメージ」「効果ダメージ」)記
  `{"kind", "text": 名詞字面}`,寫在傷害名詞的位置。「このカードの戦闘で発生する」記在原因的
  `source`:`{"text": の戦闘で発生する, "object", "ref"}`(「その戦闘で発生する」沒有物件)。
- 傷害值變更(「〜戦闘ダメージは０/倍/半分になる」「〜ダメージを受けない」)是性質變更:動作詞
  性質變更、`modified` `{"attr": ["傷害"], "form": 數值|倍|半分, "value": 0(數值時)}`,
  「受けない」也是數值 0、`predicate` 留「受けない」;門檻「このカードの攻撃力以下の」記
  `modified.limit` `{"cmp", "text"}`。句中「このターン」(沒有讀點)記期間本回合。
"""
import re

from agent_phrase import render_agent
from block_state import REASON_CLAUSE, REASON_TWICE
from cause_phrase import REASON_CAUSE, parse_cause_phrase
from object_render import render_object
from predicate_literal import check_predicate
from segment_fields import CAUSE_PATTERN, DURATION_TURN, render_cause, resolve_polarity
from structure_shape import AMOUNT_FORMULA, NoTemplate, new_line, unparsed
from synonyms import DAMAGE_OBJECT, MODIFY_ACTION, merged_voice, parse_predicates
from zone_phrase import SIDE_WORDS

DAMAGE_ACTION = "傷害"
RECOVER_ACTION = "回復"
DAMAGE_ATTR = "傷害"
DEAL_STEM, RECEIVE_STEM, RECOVER_STEM = "与え", "受け", "回復"
NEGATED_RECEIVE = "受けない"
MODIFY_DAMAGE_PREDICATE = "になる"

PLAYER_WORDS = (("お互いのプレイヤー", "雙方各自"), ("お互い", "雙方各自"),
                ("相手プレイヤー", "對手"), ("相手ライフ", "對手"),
                ("このカードのコントローラー", "我方"), ("自分", "我方"), ("相手", "對手"))
_PLAYER_ALT = "|".join(sorted((w for w, _ in PLAYER_WORDS), key=len, reverse=True))
# 受方字面在玩家字面後的接法(閉集,依句型):給予「相手ライフに」;受到「自分は」「自分が」
# 「お互いに」;變更「自分への」「お互いが受ける」「相手に与える」「お互いの」;回復「自分は」
# 「自分のLPを」「自分のLPが」。
DEAL_TAILS = ("に",)
RECEIVE_TAILS = ("は", "が", "に")
MODIFY_TAILS = ("への", "が受ける", "に与える", "の")
RECOVER_TAILS = ("は", "のLPを", "のライフポイントを", "のLPが")
PLACEMENT_BEFORE_NOUN = "名詞前"
CAUSE_BEFORE_SUBJECT = "主語前"
NOUN_CAUSES = {"戦闘・効果ダメージ": "戰鬥或效果", "戦闘ダメージ": "戰鬥",
               "効果ダメージ": "效果", "ダメージ": None}
_NOUN_ALT = "|".join(sorted(NOUN_CAUSES, key=len, reverse=True))
PLAIN_NOUN = "ダメージ"
SOURCE_TAILS = ("の戦闘で発生する", "の戦闘によって発生する")
SOURCE_THAT_BATTLE = ("その戦闘で発生する", "その戦闘によって発生する")
LIMIT_CMP = {"以下の": "≤", "未満の": "<"}
VALUE_FORMS = {"０": ("數值", 0), "倍": ("倍", None), "半分": ("半分", None)}
DURATION_THIS_TURN = "このターン"
_FULLWIDTH = str.maketrans("０１２３４５６７８９", "0123456789")
_TO_FULLWIDTH = str.maketrans("0123456789", "０１２３４５６７８９")

_FIXED = "[０-９]+(?:ポイント)?"
_FORMULA = "[^、]+?(?:×[０-９]+(?:ポイント)?|分の|と同じ)"
_LP_UNIT = "(?:LP|ライフポイント)"
_CAUSE = f"(?:{CAUSE_PATTERN})"

_DEAL_RE = re.compile(
    # 主語「自分が」「相手が」後面接的是關係子句(「自分が受けたダメージと同じ数値分の」是算式),
    # 不是施事:玩家當施事只認「は」。
    "^(?:(?P<subject>(?!(?:自分|相手|お互い)が)[^、を]+?)(?P<subject_marker>が|は))?"
    f"(?P<cause>{_CAUSE})?"
    "(?P<amount_pre>[^、]+?だけ)?"
    f"(?:(?P<recipient_pre>{_PLAYER_ALT})に)?"
    f"(?P<amount>{_FIXED}|{_FORMULA})?"
    f"(?P<noun>{_NOUN_ALT})を"
    f"(?:(?P<recipient>{_PLAYER_ALT})に)?"
    f"(?P<pred>{DEAL_STEM}[^、]*)$")
_RECEIVE_RE = re.compile(
    f"^(?P<cause_pre>{_CAUSE})?"
    f"(?P<recipient>{_PLAYER_ALT})(?P<recipient_tail>{'|'.join(RECEIVE_TAILS)})"
    f"(?P<cause>{_CAUSE})?"
    "(?P<limit>[^、]+?(?:以下の|未満の))?"
    f"(?P<amount>{_FIXED}|{_FORMULA})?"
    f"(?P<noun>{_NOUN_ALT})を"
    f"(?P<pred>{RECEIVE_STEM}[^、]*)$")
_MODIFY_RE = re.compile(
    f"^(?P<duration>{DURATION_THIS_TURN})?"
    "(?:(?P<source_that>" + "|".join(SOURCE_THAT_BATTLE) + ")"
    "|(?P<source_object>[^、]+?)(?P<source_tail>" + "|".join(SOURCE_TAILS) + "))?"
    f"(?:(?P<recipient>{_PLAYER_ALT})(?P<recipient_tail>{'|'.join(MODIFY_TAILS)}))?"
    f"(?P<noun>{_NOUN_ALT})は"
    f"(?P<value>{'|'.join(VALUE_FORMS)}){MODIFY_DAMAGE_PREDICATE}$")
_RECOVER_SUBJECT_RE = re.compile(
    f"^(?P<recipient>{_PLAYER_ALT})(?P<recipient_tail>は)"
    f"(?P<amount>[０-９]+{_LP_UNIT}|[^、]+?×[０-９]+{_LP_UNIT})"
    f"(?P<pred>{RECOVER_STEM}[^、]*)$")
_RECOVER_OBJECT_RE = re.compile(
    "^(?P<amount_pre>[^、]+?だけ)"
    f"(?P<recipient>{_PLAYER_ALT})(?P<recipient_tail>のLPを|のライフポイントを)"
    f"(?P<pred>{RECOVER_STEM}[^、]*)$")
_RECOVER_CONDITION_RE = re.compile(
    f"^(?P<recipient>{_PLAYER_ALT})(?P<recipient_tail>のLPが)"
    f"(?P<pred>{RECOVER_STEM}[^、]*)$")
_FIXED_RE = re.compile(f"^(?P<digits>[０-９]+)(?P<unit>ポイント|{_LP_UNIT})?$")

DEAL, RECEIVE, MODIFY, RECOVER = "給予", "受到", "變更", "回復"
FURTHER = "さらに"


def match_clause(clause):
    """子句 → (句型, match) 或 None。句型:給予、受到(含「受けない」的變更)、變更、回復。
    子句開頭的「さらに」(「〜場合、さらに〜」)沒有寫回的格,不收(否則會被吃進算式字面);
    句首的「さらに、」由段樹當接著詞剝掉。"""
    if clause.startswith(FURTHER):
        return None
    for form, pattern in ((DEAL, _DEAL_RE), (RECEIVE, _RECEIVE_RE), (MODIFY, _MODIFY_RE),
                          (RECOVER, _RECOVER_SUBJECT_RE), (RECOVER, _RECOVER_OBJECT_RE),
                          (RECOVER, _RECOVER_CONDITION_RE)):
        m = pattern.match(clause)
        if m:
            return form, m
    return None


def player(word, tail, placement=None):
    """玩家受方 → {"side", "text"(含接法)[, "placement"]}。"""
    recipient = {"side": dict(PLAYER_WORDS)[word], "text": word + tail}
    if placement:
        recipient["placement"] = placement
    return recipient


def parse_amount(text, noun):
    """數量字面 → amount 格。「６００」接名詞「ダメージ」時 unit 就是 ダメージ(字面含它)。"""
    m = _FIXED_RE.match(text)
    if not m:
        return {"kind": AMOUNT_FORMULA, "text": text}
    unit = m.group("unit")
    if unit is None:
        if noun != PLAIN_NOUN:
            return None   # 「１０００戦闘ダメージ」沒有這種寫法,不猜
        unit = noun
        text += noun
    return {"text": text, "value": int(m.group("digits").translate(_FULLWIDTH)), "unit": unit}


def noun_cause(noun):
    """傷害名詞 → 名詞型原因(沒寫種類回 None)。"""
    kind = NOUN_CAUSES[noun]
    return {"kind": kind, "text": noun} if kind else None


def parse_limit(text):
    for tail, cmp in LIMIT_CMP.items():
        if text.endswith(tail):
            return {"cmp": cmp, "text": text}
    return None


def parse_value(text):
    form, value = VALUE_FORMS[text]
    modified = {"attr": [DAMAGE_ATTR], "form": form}
    if value is not None:
        modified["value"] = value
    return modified


def is_damage_segment(seg):
    """傷害、回復段與傷害值變更段走這裡的模板。"""
    if seg["actions"] in ([DAMAGE_ACTION], [RECOVER_ACTION]):
        return True
    modified = seg.get("modified") or {}
    return DAMAGE_ATTR in (modified.get("attr") or []) and seg["predicate"] != "として扱う"


def render_recipient(recipient, tails):
    """玩家受方 → 字面;字面要是 玩家字面 + 允許的接法,且玩家字面與方對得上。"""
    if not isinstance(recipient, dict) or "side" not in recipient:
        raise NoTemplate("受方無模板")
    text = recipient.get("text") or ""
    for word, side in PLAYER_WORDS:
        if text.startswith(word) and text[len(word):] in tails:
            if side != recipient["side"]:
                raise NoTemplate("受方字面與方不一致")
            return text
    raise NoTemplate("受方無模板")


def render_amount(amount, noun):
    """amount → 寫在傷害名詞前的字面(含名詞);以「だけ」收尾的算式另回傳(寫在受方前)。
    回傳 (受方前的字面, 名詞短語)。"""
    if not amount:
        return "", noun
    if amount.get("kind") == AMOUNT_FORMULA:
        text = amount.get("text") or ""
        if not text:
            raise NoTemplate("數量無模板")
        if text.endswith("だけ"):
            return text, noun
        return "", text + noun
    value, unit = amount.get("value"), amount.get("unit")
    if not isinstance(value, int):
        raise NoTemplate("數量無模板")
    digits = str(value).translate(_TO_FULLWIDTH)
    if unit == PLAIN_NOUN and noun == PLAIN_NOUN:
        written = digits + unit
        return "", _checked(written, amount)
    if unit == "ポイント":
        return "", _checked(digits + unit, amount) + noun
    raise NoTemplate("數量無模板")


def _checked(written, amount):
    if written != amount.get("text"):
        raise NoTemplate("數量字面與數值不一致")
    return written


def render_lp_amount(amount):
    """回復的數量:固定值 NLP / Nライフポイント,或以 LP 單位收尾的算式字面。"""
    if amount.get("kind") == AMOUNT_FORMULA:
        text = amount.get("text") or ""
        if not text:
            raise NoTemplate("數量無模板")
        return text
    value, unit = amount.get("value"), amount.get("unit")
    if not isinstance(value, int) or unit not in ("LP", "ライフポイント"):
        raise NoTemplate("數量無模板")
    return _checked(str(value).translate(_TO_FULLWIDTH) + unit, amount)


def split_cause(cause):
    """段的原因 → (動詞型原因字面, 是否寫在主語前, 名詞字面)。名詞型原因的字面就是傷害名詞。"""
    if not cause:
        return "", False, PLAIN_NOUN
    if cause.get("text") in NOUN_CAUSES:
        if NOUN_CAUSES[cause["text"]] != cause.get("kind") or cause.get("side"):
            raise NoTemplate(f"原因無模板:{cause.get('kind')}")
        return "", False, cause["text"]
    plain = {k: v for k, v in cause.items() if k != "placement"}
    return render_cause(plain), cause.get("placement") == CAUSE_BEFORE_SUBJECT, PLAIN_NOUN


def render_source(source, render_object):
    """傷害來源「このカードの戦闘で発生する」/「その戦闘で発生する」。"""
    if not source:
        return ""
    text = source.get("text")
    if source.get("object") is None:
        if text not in SOURCE_THAT_BATTLE:
            raise NoTemplate("傷害來源無模板")
        return text
    if text not in SOURCE_TAILS:
        raise NoTemplate("傷害來源無模板")
    return render_object(source["object"], source.get("ref")) + text


def render_modified(modified, predicate):
    """傷害值變更 → 述語前的字面「０になる」「倍になる」,或「受けない」(只配數值 0)。"""
    form, value = modified.get("form"), modified.get("value")
    if modified.get("attr") != [DAMAGE_ATTR]:
        raise NoTemplate("被改的屬性無模板")
    if predicate == NEGATED_RECEIVE:
        if (form, value) != ("數值", 0):
            raise NoTemplate("被改的屬性無模板")
        return None
    for text, (want_form, want_value) in VALUE_FORMS.items():
        if (form, value) == (want_form, want_value) and predicate == MODIFY_DAMAGE_PREDICATE:
            return text + predicate
    raise NoTemplate("被改的屬性無模板")


def render_limit(limit):
    if not limit:
        return ""
    if parse_limit(limit.get("text") or "") != limit:
        raise NoTemplate("門檻無模板")
    return limit["text"]


def parse_damage_predicates(pred, recover):
    """傷害、回復句型的原述語字面(「与えた」「受ける」「回復する」)→ 同義表的查表結果。
    傷害的字幹在同義表裡連受詞「ダメージを」一起寫,句型卻把它切在述語外(見 `synonyms.DAMAGE_OBJECT`):
    查表前在這裡接回去,抽取(`fill_clause`)與模板(`render_clause`)都走這一支。回復的字幹不帶受詞。"""
    return parse_predicates(pred if recover else DAMAGE_OBJECT + pred)


def fill_clause(ctx, clause_text):
    """傷害、回復與傷害值變更的句型 → 填格回 True;不是這些句型回 False。
    玩家主語/受方進 `agent`/`recipient`、不建物件;物件主語(「このカードが」)是角色施事的對象線。"""
    seg, state, sentence_start = ctx.seg, ctx.state, ctx.sentence_start
    found = match_clause(clause_text)
    if found is None:
        return False
    form, m = found
    g = m.groupdict().get
    pred = g("pred") or MODIFY_DAMAGE_PREDICATE
    seg["predicate"], seg["voice"] = pred, "主動"
    if form == MODIFY or pred == NEGATED_RECEIVE:
        seg["actions"] = [MODIFY_ACTION]
        seg["modified"] = (parse_value(g("value")) if form == MODIFY
                           else parse_value("０"))
        if g("limit"):
            seg["modified"]["limit"] = parse_limit(g("limit"))
    else:
        parsed, reason = parse_damage_predicates(pred, recover=form == RECOVER)
        if parsed is None:
            seg["unparsed"] = unparsed(reason)
            return True
        seg["actions"] = [p.action for p in parsed]
        seg["voice"] = merged_voice(parsed)
        seg["polarity"], seg["optional"] = resolve_polarity(parsed, None)
    if g("recipient"):
        seg["recipient"] = player(g("recipient"), g("recipient_tail") or "に")
    elif g("recipient_pre"):
        seg["recipient"] = player(g("recipient_pre"), "に", PLACEMENT_BEFORE_NOUN)
    noun = g("noun") or PLAIN_NOUN
    cause = noun_cause(noun) if g("noun") else None
    verbal = g("cause") or g("cause_pre")
    if verbal:
        if cause is not None:
            seg["unparsed"] = unparsed(REASON_TWICE)
            return True
        cause, reason = parse_cause_phrase(state, verbal, sentence_start)
        if cause is None:
            seg["unparsed"] = unparsed(reason)
            return True
        if g("cause_pre"):
            cause["placement"] = CAUSE_BEFORE_SUBJECT
    if g("source_that") or g("source_object"):
        if cause is None:
            seg["unparsed"] = unparsed(REASON_CAUSE)
            return True
        source = {"text": g("source_that") or g("source_tail")}
        if g("source_object"):
            obj_id, ref, reason = state.object_at(g("source_object"), sentence_start)
            if obj_id is None:
                seg["unparsed"] = unparsed(reason)
                return True
            source["object"] = obj_id
            if ref:
                source["ref"] = ref
        cause["source"] = source
    seg["cause"] = cause
    if g("amount_pre") and g("amount"):
        seg["unparsed"] = unparsed(REASON_TWICE)
        return True
    amount_text = g("amount_pre") or g("amount")
    if amount_text:
        seg["amount"] = parse_amount(amount_text, noun)
        if seg["amount"] is None:
            seg["unparsed"] = unparsed(REASON_CLAUSE)
            return True
    if g("duration"):
        seg["duration"] = {"kind": DURATION_TURN, "text": g("duration")}
    ctx.inherit_timing()
    subject = g("subject")
    if subject in SIDE_WORDS and g("subject_marker"):
        seg["agent"] = SIDE_WORDS[subject]
    elif subject:
        obj_id, ref, reason = state.object_at(subject, sentence_start)
        if obj_id is None:
            seg["unparsed"] = unparsed(reason)
            return True
        seg["lines"] = [new_line(obj_id, "施事", marker=g("subject_marker"), ref=ref)]
        if obj_id != state.self_id and obj_id not in state.recent:
            state.recent.append(obj_id)
    return True


def render_clause(t):
    """傷害、回復、傷害值變更段的模板:
    給予 [主語][原因][算式だけ][受方に(名詞前)][數量]名詞を[受方に]与え〜;
    受到 [原因(主語前)][受方は|が][原因][門檻][數量]名詞を受け〜(受けない 是數值 0 的變更);
    變更 [このターン][來源][受方への|が受ける|に与える]名詞は(０|倍|半分)になる;
    回復 受方は數量回復〜 / 算式だけ受方のLPを回復〜 / 受方のLPが回復〜。"""
    seg, card, objects, names, self_id = t.seg, t.card, t.objects, t.names, t.self_id
    inner_duration = t.inner_duration
    predicate = seg["predicate"] or ""
    verbal, cause_first, noun = split_cause(seg["cause"])
    source = ""
    if seg["cause"] and seg["cause"].get("source"):
        source = render_source(
            seg["cause"]["source"],
            lambda obj_id, ref: render_object(objects[obj_id], seg, card, names,
                                              {"ref": ref} if ref else None,
                                              self_id=self_id))
    if seg["actions"] == [MODIFY_ACTION]:
        tail = render_modified(seg["modified"], predicate)
        if seg["lines"] or seg["agent"]:
            raise NoTemplate("傷害值變更段不該有對象線")
        if tail is not None:
            period = ""
            if inner_duration is not None:
                if inner_duration != {"kind": "本回合", "text": DURATION_THIS_TURN}:
                    raise NoTemplate("期間無模板:句中")
                period = inner_duration["text"]
            if verbal or seg["amount"] or seg["modified"].get("limit"):
                raise NoTemplate("傷害值變更段的格不齊")
            recipient = (render_recipient(seg["recipient"], MODIFY_TAILS)
                         if seg["recipient"] is not None else "")
            return period + source + recipient + noun + "は" + tail
        if inner_duration is not None or source:
            raise NoTemplate("傷害值變更段的格不齊")
    elif seg["actions"] == [RECOVER_ACTION]:
        check_predicate(seg, parse_damage_predicates(predicate, recover=True)[0])
        if seg["lines"] or verbal or noun != PLAIN_NOUN or seg["agent"] or source:
            raise NoTemplate("回復段的格不齊")
        recipient = render_recipient(seg["recipient"], RECOVER_TAILS)
        amount = seg["amount"]
        if recipient.endswith("は") and amount:
            return recipient + render_lp_amount(amount) + predicate
        if (recipient.endswith("を") and amount and amount.get("kind") == "算式"
                and amount.get("text", "").endswith("だけ")):
            return amount["text"] + recipient + predicate
        if recipient.endswith("が") and not amount:
            return recipient + predicate
        raise NoTemplate("回復段的格不齊")
    else:
        check_predicate(seg, parse_damage_predicates(predicate, recover=False)[0])
    if source:
        raise NoTemplate("傷害來源無模板")
    before_recipient, noun_phrase = render_amount(seg["amount"], noun)
    if predicate.startswith(DEAL_STEM):
        parts = []
        for line in seg["lines"]:
            if line["role"] != "施事" or line["marker"] not in ("が", "は"):
                raise NoTemplate(f"角色無模板:{line['role']}")
            parts.append(render_object(objects[line["object"]], seg, card, names, line,
                                       self_id=self_id) + line["marker"])
        if seg["agent"] is not None:
            if seg["lines"]:
                raise NoTemplate(f"誰無模板:{seg['agent']}")
            parts.append(render_agent(seg["agent"], seg, card))
        if cause_first or seg["modified"]:
            raise NoTemplate("傷害段的格不齊")
        recipient = (render_recipient(seg["recipient"], DEAL_TAILS)
                     if seg["recipient"] is not None else "")
        front = bool(recipient) and seg["recipient"].get("placement") == PLACEMENT_BEFORE_NOUN
        parts += [verbal, before_recipient, recipient if front else "", noun_phrase, "を",
                  "" if front else recipient, predicate]
        return "".join(parts)
    if seg["lines"] or seg["agent"] or before_recipient:
        raise NoTemplate("傷害段的格不齊")
    recipient = render_recipient(seg["recipient"], RECEIVE_TAILS)
    limit = render_limit((seg["modified"] or {}).get("limit"))
    return ((verbal if cause_first else "") + recipient + ("" if cause_first else verbal)
            + limit + noun_phrase + "を" + predicate)
