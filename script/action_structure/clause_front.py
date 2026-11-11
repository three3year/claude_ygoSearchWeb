"""子句前文:物件切點(`object_boundary.find_cut`)切出去的那截,交給既有的規則。

前文照固定順序認,每種至多一次(遊戲狀態可連續多個),要整截認完才算:
  [遊戲狀態前提…][次數限制][期間][時機][誰 | 主語(が|は)][次數限制][期間][原因]
- 遊戲狀態(`premise.parse_game_state`:「相手ターンに」「自分メインフェイズに、」)併進段的前提。
- 次數限制(「１度、」「１ターンに１度、」)不記,進略過文本;寫在誰/主語前後都有。
- 期間(`FRONT_DURATION`:「ダメージステップ終了時まで」「このターン、」)記在段的 `duration`,
  `placement` 子句前;寫在誰/主語之後的(「相手はダメージステップ終了時まで」)是 主語後。
- 時機只收延遲(「このターンのエンドフェイズに」),記在段的 `timing`,`placement` 子句前。
- 誰(玩家字面)記段的 `agent`;主語是物件的(「このカードが」「相手モンスターは」)成一條角色施事的
  對象線,助詞記在線上;「Xは」同時是後面主語省略的子句的主語。
- 原因(「戦闘によって」)記段的 `cause`,`placement` 名詞前;本卡自己的效果(「この効果で」)指的段要看
  子句本體的動作詞,由呼叫端在本體解析完後找(`cause_phrase.point_own_effect`)。
認不得(字面不在這些規則裡、順序不同、同一格已有值)就在段上標 `REASON_FRONT`,段的格不動;子句本體
由呼叫端照常解析(`segment_extract.fill_clause`),物件不帶吞進來的字面,但這一段算解析不出。
模板:期間 `render_front_duration`、時機 `render_front_timing`、主語線 `subject_line`(由簡單子句的
模板與 `reverse_check.render_segment` 放回原位);前提、誰、原因沿用各自的模板。
"""
import re

from agent_phrase import AGENT_PATTERN, fill_agent
from block_state import INTERVAL_REASON, INTERVAL_SCOPE, INTERVAL_TIMES
from cause_phrase import CAUSE_ALT, fill_cause, is_own_effect
from object_boundary import REASON_FRONT
from premise import PHASE_WORDS, parse_game_state
from segment_fields import (BATTLE_DURATION_PATTERN, CLAUSE_DURATION_PATTERN, DELAY, parse_duration,
                            parse_leading_duration, parse_timing, render_timing)
from structure_shape import NoTemplate, new_line, unparsed

PLACEMENT_FRONT, PLACEMENT_AFTER_SUBJECT = "子句前", "主語後"
DURATION_PLACEMENTS = {"期間": PLACEMENT_FRONT, "主語後的期間": PLACEMENT_AFTER_SUBJECT}
ROLE_SUBJECT = "施事"
PHASE_ALT = "|".join(word for word, _ in PHASE_WORDS)
SIDE_ALT = "自分・相手の|自分|相手"
# 不在句首的「このターン、」「このターン中、」(句首的由 `segment_fields.parse_leading_duration` 剝)。
LEADING_THIS_TURN = ("このターン、", "このターン中、")
_INTERVAL = f"{INTERVAL_SCOPE}?{INTERVAL_TIMES}(?:だけ)?、"
_INTERVAL_RE = re.compile(f"^{_INTERVAL}")
# 子句前的期間:某個回合、階段或傷害步驟結束為止,該戰鬥的字面,與不在句首的「このターン、」。
FRONT_DURATION = (
    f"(?:次の|その)?(?:自分の?|相手の?)?(?:ターン|{PHASE_ALT}|ダメージステップ)の?終了時まで、?"
    f"|(?:{CLAUSE_DURATION_PATTERN})、?|{BATTLE_DURATION_PATTERN}|{'|'.join(LEADING_THIS_TURN)}")
_DURATION_RE = re.compile(f"^(?:{FRONT_DURATION})")
# 子句前的時機只收帶「次の/このターンの」的延遲;沒帶的(「自分メインフェイズに」)是遊戲狀態。
_TIMING_RE = re.compile(f"^(?:次の|このターンの)(?:{SIDE_ALT})?(?:{PHASE_ALT})に、?")
_AGENT_RE = re.compile(f"^(?P<word>{AGENT_PATTERN})(?P<marker>が|は|(?<=お互い)に)(?P<pause>、)?")
# 主語:到第一個「が/は」為止(「」裡的字與「または」的は不算),後面只能再接次數限制、期間、原因。
_SUBJECT_RE = re.compile(
    "^(?P<phrase>(?:「[^「」]*」|または|[^、がは「」])+?)(?P<marker>が|は)(?P<pause>、)?"
    f"(?=$|(?:{CAUSE_ALT})$|{_INTERVAL}|(?:{FRONT_DURATION}))")
_CAUSE_RE = re.compile(f"^(?:{CAUSE_ALT})$")


def _parse_front_duration(text):
    """子句前的期間字面 → duration 格:「このターン、」同句首時間狀語,其餘照 `parse_duration`。"""
    if text in LEADING_THIS_TURN:
        return parse_leading_duration(text)[0]
    return parse_duration(text)


def _scan(front):
    """前文 → [(種類, 起點, 比對結果或原子)],照固定順序;沒有整截認完回 None。只看字面,不動段。"""
    found, pos = [], 0

    def take(kind, m):
        nonlocal pos
        if m:
            found.append((kind, pos, m))
            pos += m.end()
        return m

    while True:
        atom, length = parse_game_state(front[pos:])
        if atom is None:
            break
        found.append(("遊戲狀態", pos, atom))
        pos += length
    interval = take("次數限制", _INTERVAL_RE.match(front[pos:]))
    duration = take("期間", _DURATION_RE.match(front[pos:]))
    take("時機", _TIMING_RE.match(front[pos:]))
    if not take("誰", _AGENT_RE.match(front[pos:])):
        take("主語", _SUBJECT_RE.match(front[pos:]))
    # 次數限制與期間也可寫在誰、主語之後(「「X」は１ターンに１度、」「相手はダメージステップ終了時まで」)。
    if not interval:
        take("次數限制", _INTERVAL_RE.match(front[pos:]))
    if not duration:
        take("主語後的期間", _DURATION_RE.match(front[pos:]))
    take("原因", _CAUSE_RE.match(front[pos:]))
    return found if pos == len(front) else None


def fill_front(ctx, front):
    """前文 → 填進段的格;認得回 True。認不得(或同一格已有值)回 False 並在段上標 `REASON_FRONT`,
    這時段的格不動;字面認得、但主語、誰、原因照各自的規則解析不出時標它們的原因(排在前面的格已填)。"""
    seg, state = ctx.seg, ctx.state
    found = _scan(front)
    kinds = {kind for kind, _, _ in found or ()}
    duration = next((_parse_front_duration(m.group()) for kind, _, m in found or ()
                     if kind in DURATION_PLACEMENTS), None)
    # 主語要像個物件短語(「このターン相手」不是)。
    subject_named = all(state.names_object(m.group("phrase")) for kind, _, m in found or ()
                        if kind == "主語")
    if (found is None or not subject_named or ("時機" in kinds and seg["timing"] is not None)
            or ("誰" in kinds and seg["agent"] is not None)
            or ("原因" in kinds and seg["cause"] is not None)
            or (duration is not None and seg["duration"] not in (None, duration))):
        seg["unparsed"] = unparsed(REASON_FRONT)
        return False
    atoms = []
    for kind, offset, m in found:
        start = ctx.sentence_start + offset
        reason = None
        if kind == "遊戲狀態":
            atoms.append(m)
        elif kind == "次數限制":
            state.omit(start, m.group(), INTERVAL_REASON)
        elif kind in DURATION_PLACEMENTS:
            seg["duration"] = {**duration, "placement": DURATION_PLACEMENTS[kind]}
        elif kind == "時機":
            seg["timing"] = {**parse_timing(m.group().rstrip("、")), "text": m.group(),
                             "placement": PLACEMENT_FRONT}
        elif kind == "誰":
            reason = fill_agent(seg, state, m.group("word"), m.group("marker"), m.group("pause"),
                                ctx.kind)
        elif kind == "主語":
            obj_id, ref, reason = state.object_at(m.group("phrase"), start)
            if obj_id is not None:
                marker = m.group("marker") + (m.group("pause") or "")
                seg["lines"].append(new_line(obj_id, ROLE_SUBJECT, marker=marker, ref=ref))
                if obj_id != state.self_id and obj_id not in state.recent:
                    state.recent.append(obj_id)
                if m.group("marker") == "は":
                    state.subject = obj_id
        elif kind == "原因" and is_own_effect(m.group()):
            # 指的段要看本體的動作詞,本體解析完才找(`cause_phrase.point_own_effect`)。
            seg["cause"] = {"kind": "效果", "text": m.group(), "segment": None, "placement": "名詞前"}
        elif kind == "原因":
            reason = fill_cause(seg, state, m.group(), start, placement="名詞前")
        if reason:
            seg["unparsed"] = unparsed(reason)
            return False
    if atoms:
        own = seg["premise"]
        merged = atoms + (own["args"] if own and own.get("op") == "且" else [own] if own else [])
        seg["premise"] = merged[0] if len(merged) == 1 else {"op": "且", "args": merged}
    return True


def front_duration(duration):
    """段的期間是不是物件切點切出來的(`placement` 子句前/主語後),回傳 placement 或 None。"""
    placement = (duration or {}).get("placement")
    return placement if placement in DURATION_PLACEMENTS.values() else None


def render_front_duration(duration):
    """子句前的期間 → 字面;字面不在 `FRONT_DURATION` 或與種類對不上丟 NoTemplate。"""
    bare = {k: v for k, v in duration.items() if k != "placement"}
    text = bare.get("text") or ""
    if not re.fullmatch(FRONT_DURATION, text) or _parse_front_duration(text) != bare:
        raise NoTemplate("期間無模板:子句前")
    return text


def front_timing(timing):
    return bool(timing) and timing.get("placement") == PLACEMENT_FRONT


def render_front_timing(timing):
    """子句前的時機 → 字面(可帶讀點);去掉讀點後要是 `render_timing` 寫得出的延遲。"""
    text = timing.get("text") or ""
    bare = {k: v for k, v in timing.items() if k != "placement"}
    bare["text"] = text.rstrip("、")
    if timing.get("kind") != DELAY or not _TIMING_RE.fullmatch(text) \
            or render_timing(bare) != bare["text"]:
        raise NoTemplate("時機無模板:子句前")
    return text


def subject_line(seg):
    """簡單子句的主語線(角色施事,排在最前面、至多一條);沒有回 None。"""
    subjects = [line for line in seg["lines"] if line["role"] == ROLE_SUBJECT]
    if not subjects:
        return None
    if len(subjects) > 1 or seg["lines"][0] is not subjects[0] or seg["agent"] is not None \
            or (subjects[0]["marker"] or "").rstrip("、") not in ("が", "は") \
            or any(subjects[0][slot] for slot in ("from", "to", "targeting", "count", "pick")):
        raise NoTemplate("主語的對象線無模板")
    return subjects[0]
