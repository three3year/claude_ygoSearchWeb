"""段抽取:一個區塊的原文 → 段(扁平)+ 段樹 + 物件(寫進整卡共用的物件表)。

規則是句型層級的,不針對任何一張卡:
- 句子以「。」切;「その後、」開頭的句子與前一句連接為「先後」;區塊開頭的「また、」是接著詞。
- 發動句(…発動できる / …発動する):
    (前提)(條件子句)(時|場合|際)(に)、(代價子句)て  → 條件段 + 代價段
  條件段帶觸發形;代價子句以て形結尾才算代價。前提(`premise` 模組:「〜に存在する場合、」
  「相手ターンに」)先剝掉、寫進第一個段的前提格(段的範圍從前提起算);整句只有前提的
  (「自分メインフェイズに発動できる」)開一個沒有動作詞的條件段放它;效果句開頭的前提同樣。
- 舊式的「(條件子句)(時|場合|際)、(效果子句)」(沒有発動できる)→ 條件段 + 效果段。
- 舊式的「(代價子句)る事で、(效果子句)」(= 新式「〜て発動できる。〜」)→ 代價段 + 效果段。
- 效果子句以「代わりに」開頭的是代替(票 08):條件段改標「被代替」(不更新位置)、效果段記 `replaces`。
- 其他句子是效果段;連用形串接(「〜に戻り、その攻撃力は〜になる」「〜手札に加え、〜に戻す」)切成
  多段、連接「同時」、後段與前段同一時機(`clause_join`);性質變更句「その攻撃力は〜倍になる」
  走 `segment_fields.parse_modify`。極性由述語語尾判(できない → 不能…);「〜を…できる」是可選的
  效果(可選格 `optional`,極性仍是做,查詢預設算命中),「〜は…できる」是永續的許可(極性 可以)
  (`segment_fields.resolve_polarity`)。
- 延遲(票 08):「次のスタンバイフェイズに」記時機延遲;序列中段出現條件段之後的段也算延遲(沒有字面);
  延遲段指回被點名物件的線不標取對象。
- 發動句的代價子句也可連用形串接(「〜を墓地へ送り、〜を対象として発動できる」,票 06),
  同樣切段、連接「同時」;句子以上的結構(● 分歧、內嵌效果、先後連接)在 `segment_tree`。
- 上游切分:整句是場上唯一或次數限制句(`OMITTED_SENTENCES`)的進略過文本、不產生段;
  句首時間狀語(このターン、/この効果の発動後、ターン終了時まで/〜を発動するターン、)剝成期間、
  套到整句的段;前提「〜限り、」整句的段期間持續;「Xしか〜できない」的しか是助詞、極性只能。
- 子句怎麼填格:`fill_clause` 照 `CLAUSE_FORMS` 依序試各句型(存在前提 `existence_clause`、
  傷害與回復 `damage`、戰鬥 `battle_clause`、抽牌 `draw`),都不是就當簡單子句(`simple_clause`);
  效果子句先試性質變更句(`stat_modify`)。素材行在 `material_line`,「〜として扱う」句在 `treat_as`。
  物件短語、位置規則與各句型共用的子句 context 在 `block_state`。
抽不出的段與物件一律標原因,不丟例外,全庫建置不中斷。
"""
import re

import battle_clause
import damage
import draw
import existence_clause
import material_line
import simple_clause
import stat_modify
from block_state import (ClauseContext, INTERVAL_RE, INTERVAL_REASON, KIND_PROCEDURE,
                         KIND_RESTRICTION, segment_at)
from clause_join import JOIN, split_continuative
from names_attributes import parse_treat_as
from premise import is_lasting, split_premises
from segment_fields import (REPLACEMENT_PREFIX, find_battle_duration, inherited_duration, lasting,
                            parse_cause, parse_leading_duration)
from structure_shape import BATTLE_TRIGGERS, unparsed
from synonyms import ACTIVATION_SUFFIXES, COST_GLUE
from treat_as import treat_as_segment
from zone_phrase import parse_from, zone_literal


_ACTIVATION_RE = re.compile("^(?P<body>.*?)(?P<suffix>" + "|".join(ACTIVATION_SUFFIXES) + ")$")
# 整句不記、進略過文本的句子:場上唯一「Xは自分フィールドに１体しか表側表示で存在
# できない」;次數限制「この効果は１ターンに１度しか使用できない」型(區塊切分只在它自成一句、
# 沒被補足情報的『』引用黏進效果區塊時才略過,黏進去的由這裡收)。
UNIQUE_REASON = "場上唯一"
_UNIQUE_RE = re.compile(
    "^[^、。]+?は、?(?:自分フィールド上|自分フィールド|フィールド上|フィールド|自分のモンスターゾーン)"
    "に１(?:体|枚)しか表側表示で存在できない$")
_LIMIT_SENTENCE_RE = re.compile(
    "^(?:「[^「」]+」の|このカード名の)?(?:この)?効果は(?:お互いに)?"
    "(?:１ターンに|デュエル中に)[１-９]度しか(?:使用|適用)できない$")
OMITTED_SENTENCES = ((_UNIQUE_RE, UNIQUE_REASON), (_LIMIT_SENTENCE_RE, INTERVAL_REASON))
# 同一句次數限制寫成句尾括號注記(「〜発動できる（このカード名のこの効果は１ターンに１度しか使用できない）」)。
_LIMIT_NOTE_RE = re.compile("（(?P<note>[^（）]+)）$")
# 句首的「Xは」(「「A」または「B」は」的「または」屬於 X)。
_TOPIC_RE = re.compile("^(?P<topic>(?:または|[^をがは、])+?)は")
# 觸發形:戰鬥時點排在「時」前面,「〜戦闘を行うダメージ計算時」的觸發形是整個時點字面;
# 後接「(、)または」的是「A時點、またはB時」兩個觸發的或,維持切在後面的「時」。
_TRIGGERS = f"(?:{'|'.join(BATTLE_TRIGGERS)})(?!、?または)|時|場合|際"
# 條件子句不在「」中間結束:「「時械神」モンスター」的「時」不是觸發形。
_COND = "(?P<cond>(?:「[^「」]*」|[^「」])+?)"
_TRIGGER_RE = re.compile(f"^{_COND}(?P<trig>{_TRIGGERS})に?、?(?P<rest>.*)$")
# 發動句裡單獨的戰鬥時點:「そのダメージ計算前に発動する」「ダメージ計算時に、〜て発動できる」
# 開一個沒有動作詞的條件段;「その」指回同一句前一個條件段(前提 段已執行)。後面要接「に」「、」或句尾,
# 「ダメージステップ終了時まで」不是。
BATTLE_TIMING_REF = "その"
_BATTLE_TIMING_RE = re.compile(
    f"^(?P<ref>{BATTLE_TIMING_REF})?(?P<trig>{'|'.join(BATTLE_TRIGGERS)})(?=に|、|$)に?、?(?P<rest>.*)$")
PREMISE_DONE = "段已執行"
# 舊式的條件句:觸發形後一定有「、」才算,免得「終了時に」這類句中的時被當觸發。
_OLD_TRIGGER_RE = re.compile(f"^{_COND}(?P<trig>{_TRIGGERS})(?:に)?、(?P<rest>.+)$")
# 召喚條件區塊的召喚手續句(票 09):「〜をリリースした場合に特殊召喚できる」「〜を除外した場合のみ
# EXデッキから特殊召喚できる」,觸發形後可接「に」、「、」或直接接「のみ」。
_SUMMON_TRIGGER_RE = re.compile(f"^{_COND}(?P<trig>時|場合)(?:に、|に|、)?(?P<rest>.+)$")
BLOCK_SUMMON, BLOCK_MATERIAL = "召喚條件", "素材"
# 「〜したターン、」(票 09):句首的動作子句 + ターン 是條件段(觸發形 ターン),後面的段的前提引用它
# (`本回合發生過`);「相手ターンに」是遊戲狀態前提,不走這裡(前面要有 した/成功した)。
TURN_TRIGGER = "ターン"
_TURN_RE = re.compile("^(?P<cond>[^、]+?(?:した|に成功した))ターン、(?P<rest>.+)$")
PREMISE_HAPPENED = "本回合發生過"
# 重複到停為止(spec 故事 28、GLOSSARY「未結構化」):「「〜」処理を繰り返す」「〜までこの効果を
# (最大で７回)繰り返す」「〜処理を〜の数だけ繰り返す」。要有「処理を」或「この効果を」才算,
# 通常怪獸的故事文「攻撃を繰り返す」不是效果。句尾可帶「（最大４回）」。
REPEAT_RE = re.compile("^(?=.*(?:処理|この効果)を).*繰り返す(?:（[^）]*）)?$")
# 舊式的代價句:「(代價子句)る事で、(效果子句)」= 新式「(代價子句)て発動できる。(效果子句)」。
# 代價子句以非過去形收尾(る/う/す/く;く 是「取り除く事で」)才算,「〜された事で」是條件意味、不切。
_OLD_COST_RE = re.compile("^(?P<cost>.+?[るうすく])" + COST_GLUE + "、?(?P<rest>.+)$")


REASON_ACTIVATION = "發動句解析不出"


def sentences(text, body_start, end=None):
    """以「。」切句,回傳 (start, end) 且去掉頭尾空白換行;句號不含在範圍內。
    `end` 限定只切到這個偏移(● 分支的範圍,票 06)。"""
    limit = len(text) if end is None else end
    spans = []
    pos = body_start
    while pos < limit:
        stop = text.find("。", pos, limit)
        if stop < 0:
            stop = limit
        start, stop_at = pos, stop
        while start < stop_at and text[start] in "\n ":
            start += 1
        while stop_at > start and text[stop_at - 1] in "\n ":
            stop_at -= 1
        if start < stop_at:
            spans.append((start, stop_at))
        pos = stop + 1
    return spans


# 子句句型:依序試,第一個認得的句型負責填格(認得但解析不出的也算,它會在段上標原因);
# 都不是就當簡單子句。加一種句型 = 加一個模組(`fill_clause(ctx, 子句) -> bool`)再排進這張表。
CLAUSE_FORMS = (existence_clause.fill_clause, damage.fill_clause, battle_clause.fill_clause,
                draw.fill_clause)


def fill_clause(ctx, clause_text):
    """子句 → 填進 `ctx.seg`;失敗就在段上標原因。"""
    for fill in CLAUSE_FORMS:
        if fill(ctx, clause_text):
            return
    simple_clause.fill_clause(ctx, clause_text)


def _fill_effect(ctx, clause):
    """效果子句:性質變更句(「その攻撃力は〜倍になる」)走它的句型,其餘照一般的子句句型。"""
    if stat_modify.fill_clause(ctx, clause):
        return
    ctx.seg["duration"] = find_battle_duration(clause)
    fill_clause(ctx, clause)


def _condition_and_rest(state, seg_start, clause_start, body, trig, segs, kind="條件"):
    """觸發子句 → 條件段(範圍從 seg_start 起算:前面可能有前提;「〜場合、代わりに」的是被代替段,
    不更新位置);回傳 (剩下的子句, 它的起點)。"""
    cond_end = clause_start + len(trig.group("cond"))
    seg = segment_at(state, kind, seg_start, cond_end + len(trig.group("trig")))
    seg["trigger"] = trig.group("trig")
    fill_clause(ClauseContext(seg, state, clause_start), trig.group("cond"))
    segs.append(seg)
    rest = trig.group("rest")
    return rest, clause_start + body.rfind(rest) if rest else None


def _battle_timing(state, body, body_start, seg_start, segs):
    """發動句子句開頭的戰鬥時點 → 條件段(觸發形是時點字面、沒有動作詞),append 進 segs;
    回傳 (剩下的子句, 它的起點),不是就回 None。「その」沒有同一句的前一個條件段可指時不認。"""
    m = _BATTLE_TIMING_RE.match(body)
    if not m or (m.group("ref") and not segs):
        return None
    seg = segment_at(state, "條件", seg_start, body_start + m.end("trig"))
    seg["trigger"] = m.group("trig")
    if m.group("ref"):
        seg["premise"] = {"op": PREMISE_DONE, "segment": segs[-1]["id"]}
    segs.append(seg)
    return m.group("rest"), body_start + m.start("rest")


def _attach_premise(seg, premise):
    """前提寫進段;段已有前提(存在前提的條件段)時依字面順序組成「且」。"""
    if seg["premise"] is None:
        seg["premise"] = premise
        return
    atoms = premise["args"] if premise.get("op") == "且" else [premise]
    seg["premise"] = {"op": "且", "args": atoms + [seg["premise"]]}


def _cost_and_effect(state, clause, start, seg_start, replaces=None):
    """效果子句 → [(效果段, 連接)],或舊式代價句「(代價)る事で、(效果)」→ 代價段 + 效果段。
    效果子句若是連用形串接(「〜に戻り、その攻撃力は〜になる」)切成多段、連接「同時」(票 08);
    第一個段的範圍從 seg_start 起算(前面可能有前提)。`replaces` 是做代替的段要記的被代替段 id。"""
    segs = []
    cost = _OLD_COST_RE.match(clause)
    if cost:
        cost_text = cost.group("cost")
        cost_seg = segment_at(state, "代價", seg_start, start + len(cost_text))
        fill_clause(ClauseContext(cost_seg, state, start), cost_text)
        segs.append((cost_seg, None))
        # 效果子句接在「事で、」後面,它的段範圍從自己起算(前提已在代價段上)。
        start += len(clause) - len(cost.group("rest"))
        clause, seg_start = cost.group("rest"), None
    for i, (offset, piece) in enumerate(split_continuative(clause)):
        piece_start = start + offset
        join = JOIN if i else None
        then = _THEN_RE.match(piece) if i else None
        if then:
            piece_start += then.end()
            piece = piece[then.end():]
            join = SEQUENCE_JOIN
        seg = segment_at(state, "效果", seg_start if (i == 0 and seg_start is not None)
                       else piece_start, piece_start + len(piece))
        if replaces:
            seg["replaces"] = replaces
        _fill_effect(ClauseContext(seg, state, piece_start,
                                   segs[-1][0]["timing"] if i and not then else None), piece)
        _hold_topic(seg, piece, state, piece_start)
        segs.append((seg, join))
        derived = stat_modify.derived_segment(seg, state)
        if derived is not None:
            segs.append((derived, JOIN))
    return segs


SEQUENCE_JOIN = "先後"
_THEN_RE = re.compile("^その後、?")


def _hold_topic(seg, piece, state, piece_start):
    """左半解不出時,它句首的「Xは」仍是後面主語省略的子句的主語(「装備モンスターは相手の効果の
    対象にならず、戦闘では破壊されない」);物件等用到時才建(`BlockState.elided_subject`)。"""
    if not seg["unparsed"]:
        return
    m = _TOPIC_RE.match(piece)
    if m and not parse_cause(m.group()):
        state.hold_topic(m.group("topic"), piece_start)
    else:
        state.lose_topic()


def _apply_duration(segs, duration):
    for seg, _ in segs:
        if seg["duration"] is None:
            seg["duration"] = dict(duration)


def parse_sentence(state, start, end):
    """一句 → [(段, 與前一段的連接)](發動句可產生條件段 + 代價段;舊式條件句產生條件段 + 效果段;
    舊式代價句產生代價段 + 效果段;連用形串接的效果句、代價子句切成多段、連接「同時」)。
    句首的前提先剝掉,掛在第一個段上、段的範圍從前提起算;「〜場合、代わりに〜」的條件段改標
    被代替、後面的段記代替誰(「代わりに」留在它的範圍內)。"""
    text = state.block["text"]
    sent = text[start:end]
    state.start_sentence()
    summon_block = state.block["kind"] == BLOCK_SUMMON
    if state.block["kind"] == BLOCK_MATERIAL:
        return [(material_line.material_segment(state, start, end), None)]
    treat = parse_treat_as(sent)
    if treat is not None:
        return [(treat_as_segment(state, start, end, treat), None)]
    for pattern, reason in OMITTED_SENTENCES:
        if pattern.match(sent):
            state.omit(start, sent, reason)
            return []
    note = _LIMIT_NOTE_RE.search(sent)
    if note and _LIMIT_SENTENCE_RE.match(note.group("note")):
        state.omit(start + note.start(), note.group(), INTERVAL_REASON)
        end = start + note.start()
        sent = text[start:end]
    if REPEAT_RE.match(sent):
        # 重複到停為止(spec 故事 28):第一輪已由前面的句子(或「」裡的字面)寫出,這一句只標未結構化,
        # 不抽動作詞、不更新位置;反向檢查與覆蓋報告各另列一類。
        seg = segment_at(state, "效果", start, end)
        seg["unstructured"] = True
        return [(seg, None)]
    act = _ACTIVATION_RE.match(sent)
    body = act.group("body") if act else sent
    turn_seg = None
    turn = _TURN_RE.match(body)
    if turn:
        # 「〜したターン、」:動作子句是條件段(觸發形 ターン),後面的第一個段以前提引用它。
        turn_seg = segment_at(state, "條件", start, start + len(turn.group("cond")) + len(TURN_TRIGGER))
        turn_seg["trigger"] = TURN_TRIGGER
        fill_clause(ClauseContext(turn_seg, state, start), turn.group("cond"))
        start += turn.start("rest")
        body = turn.group("rest")
    interval = INTERVAL_RE.match(body)
    if interval:
        # 句首的「１ターンに１度、」(①：１ターンに１度、〜):次數限制不記,進略過文本。
        state.omit(start, interval.group(), INTERVAL_REASON)
        start += interval.end()
        body = body[interval.end():]
    seg_from = start
    lead, lead_length = parse_leading_duration(body)
    if lead is not None:
        start += lead_length
        body = body[lead_length:]
    premise, premise_end, clause_start = split_premises(body, state, start,
                                                        parse_from, zone_literal)
    body = text[clause_start:start + len(body)]
    if act and premise and body in ("", "に"):
        seg = segment_at(state, "條件", seg_from, premise_end)
        seg["premise"] = premise
        if lead is not None:
            seg["duration"] = lead
        return [(seg, None)]
    segs = []
    trigger_re = _TRIGGER_RE if act else (_SUMMON_TRIGGER_RE if summon_block
                                         else _OLD_TRIGGER_RE)
    rest, rest_start, seg_start = body, clause_start, seg_from
    timing = _battle_timing(state, body, clause_start, seg_from, segs) if act else None
    trig = None if timing else trigger_re.match(body)
    replaced = trig is not None and trig.group("rest").startswith(REPLACEMENT_PREFIX)
    if trig:
        rest, rest_start = _condition_and_rest(state, seg_from, clause_start, body,
                                               trig, segs,
                                               "被代替" if replaced else "條件")
        seg_start = rest_start
        timing = (_battle_timing(state, rest, rest_start, rest_start, segs)
                  if act and rest else None)
    if timing:
        rest, rest_start = timing
        seg_start = rest_start
    if segs and state.block["segments"] and not summon_block:
        state.delayed = True
    segs = [(seg, None) for seg in segs]
    if rest and not act:
        if replaced:
            rest_start += len(REPLACEMENT_PREFIX)
            rest = rest[len(REPLACEMENT_PREFIX):]
        segs += _cost_and_effect(state, rest, rest_start, seg_start,
                                 replaces=segs[0][0]["id"] if replaced else None)
    elif rest:
        # 代價子句也可連用形串接(「〜を墓地へ送り、〜を対象として発動できる」,票 06):
        # 最後一截要以て形收尾才算代價。
        pieces = split_continuative(rest)
        for i, (offset, piece) in enumerate(pieces):
            piece_start = rest_start + offset
            seg = segment_at(state, "代價", seg_start if i == 0 else piece_start,
                           piece_start + len(piece))
            if i < len(pieces) - 1 or piece.endswith(("て", "で")):
                fill_clause(ClauseContext(seg, state, piece_start), piece)
                _hold_topic(seg, piece, state, piece_start)
            else:
                seg["unparsed"] = unparsed(REASON_ACTIVATION)
            segs.append((seg, JOIN if i else None))
    if premise and segs:
        _attach_premise(segs[0][0], premise)
    if lead is not None:
        _apply_duration(segs[:1], lead)
        _apply_duration(segs[1:], inherited_duration(lead))
    if is_lasting(premise):
        _apply_duration(segs, lasting())
    if turn_seg is not None:
        if segs:
            _attach_premise(segs[0][0], {"op": PREMISE_HAPPENED, "segment": turn_seg["id"]})
        segs.insert(0, (turn_seg, None))
    if summon_block:
        # 召喚條件區塊的段類別(spec):做的是召喚手續(含「〜した場合」的手續子句),
        # 不能/只能/必須的是限制。
        for seg, _ in segs:
            if seg["kind"] in ("條件", "代價", "效果") and seg["trigger"] != TURN_TRIGGER:
                seg["kind"] = (KIND_PROCEDURE if seg["polarity"] == "做"
                               else KIND_RESTRICTION)
    return segs
