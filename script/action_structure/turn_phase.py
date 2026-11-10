"""時點「Xした/されたターンの〈階段〉に」(m3 票 11):抽取。模板在 `premise.render_premise`。

「このカードが墓地へ送られたターンのエンドフェイズに発動できる」這類發動或適用的時點,用現有的格、
不加新觸發形:

- 動作子句「Xした」是條件段(觸發形 ターン,範圍到「ターン」為止),和「〜したターン、」同一種段。
- 「の〈階段〉に」是後面那一段的前提:`本回合發生過`(指向那個條件段,`form` 記「の」)且
  `遊戲狀態` 階段(`form` 記助詞:に、時に、時,後面有讀點就帶讀點;舊式「エンドフェイズ時」同一個讀法)。
  後面沒有子句(「〜ターンのエンドフェイズに発動できる」)時由只有前提的條件段裝。
- 時點列舉「T1及び、T2に」:兩個時點的或——`{"op": "或", "form": "及び、", "args": [且(本回合發生過, 階段)…]}`。
  助詞只寫在最後一個時點後,各支的階段原子都記它。最後一支的字面「の〈階段〉に」在帶前提的那一段裡,
  前面各支的「の〈階段〉及び、」在段外(夾在兩個條件段之間),反向檢查由 `premise.timepoint_glue` 產生後扣掉。
  第二個以後的時點可帶自己的句首前提(「このカードがモンスターゾーンに存在し、〜が墓地へ送られたターン」),
  掛在那個時點的條件段上。

第一個時點的動作子句不含讀點(同「〜したターン、」):前面有主題或別的子句的句子不認。
不收:「次のターンのエンドフェイズ」「このターンのエンドフェイズに」(動作子句不是過去形)、
「〜エンドフェイズ時まで」(期間)、「〜した相手ターンのエンドフェイズに」(回合另帶方)。

接縫:`match_timepoints(body)` 只比字面、沒有副作用;`build_timepoints` 才開段、建物件。
"""
import re
from typing import NamedTuple

from block_state import ClauseContext, segment_at
from premise import (GAME_STATE_PHASE, PHASE_WORDS, SIDE_PREFIX, TIMEPOINT_OR_FORMS, TURN_OF,
                     split_premises)

# 「〜したターン」的條件段:觸發形、後面的段引用它的前提原子。
TURN_TRIGGER = "ターン"
PREMISE_HAPPENED = "本回合發生過"
_POINT_RE = re.compile(
    "(?P<clause>.+?た)" + TURN_TRIGGER + TURN_OF
    + "(?P<side>" + "|".join(SIDE_PREFIX) + ")?"
    + "(?P<what>" + "|".join(word for word, _ in PHASE_WORDS) + ")"
    # 「時」單獨當助詞時後面要接讀點或句尾(「エンドフェイズ時まで」是期間)。
    + "(?:(?P<enum>" + "|".join(TIMEPOINT_OR_FORMS) + ")|(?P<form>時に|時(?=、|$)|に)(?P<pause>、)?)")


class TimepointMatch(NamedTuple):
    """一個時點的字面位置(相對於句子主體):動作子句、階段原子的值、列舉的連接字(最後一個是 None)。"""
    clause: tuple
    side: str | None
    phase: str
    enum: str | None
    of_start: int      # 「の」的位置
    end: int


class Timepoints(NamedTuple):
    """時點解析的結果:各時點的條件段、要掛在後面那一段的前提原子、那一段的起點(最後一個「の」)、
    前提字面的結束(不含讀點)、其餘子句的起點。偏移都相對於區塊原文。"""
    segs: list
    atoms: list
    carrier_start: int
    text_end: int
    rest_start: int


def match_timepoints(body):
    """句子主體開頭的時點(可列舉)→ ([TimepointMatch], 助詞, 前提字面結束, 其餘子句起點);不是就回 None。"""
    points, pos = [], 0
    while True:
        m = _POINT_RE.match(body, pos)
        if not m or (not points and "、" in m.group("clause")):
            return None
        points.append(TimepointMatch(m.span("clause"), SIDE_PREFIX.get(m.group("side")),
                                     dict(PHASE_WORDS)[m.group("what")], m.group("enum"),
                                     m.end("clause") + len(TURN_TRIGGER), m.end()))
        if not m.group("enum"):
            break
        pos = m.end()
    if len({p.enum for p in points[:-1]}) > 1:
        return None
    form = m.group("form") + (m.group("pause") or "")
    return points, form, m.end("form"), m.end()


def build_timepoints(state, body, start, matched, fill_clause, parse_zones, zone_literal):
    """`match_timepoints` 的結果 → `Timepoints`:每個時點開一個條件段(觸發形 ターン)並填格。
    `start` 是 body 在區塊原文的位置;`fill_clause(ctx, 子句)` 是子句的填格函式。"""
    points, form, text_end, rest_start = matched
    segs, alternatives = [], []
    for i, point in enumerate(points):
        clause_start, clause_end = start + point.clause[0], start + point.clause[1]
        premise, cond_start = None, clause_start
        if i:
            premise, _, cond_start = split_premises(body[point.clause[0]:point.clause[1]], state,
                                                    clause_start, parse_zones, zone_literal)
        seg = segment_at(state, "條件", clause_start, clause_end + len(TURN_TRIGGER))
        seg["trigger"] = TURN_TRIGGER
        fill_clause(ClauseContext(seg, state, cond_start),
                    state.block["text"][cond_start:clause_end])
        if premise is not None:
            # 時點自己的句首前提排在子句填進去的前提(存在前提)前面,同 segment_extract 的句首前提。
            own = [seg["premise"]] if seg["premise"] is not None else []
            leading = premise["args"] if premise.get("op") == "且" else [premise]
            seg["premise"] = premise if not own else {"op": "且", "args": leading + own}
        segs.append(seg)
        alternatives.append([
            {"op": PREMISE_HAPPENED, "segment": seg["id"], "form": TURN_OF},
            {"op": "遊戲狀態", "state": GAME_STATE_PHASE, "value": point.phase,
             "side": point.side, "form": form}])
    atoms = alternatives[0]
    if len(alternatives) > 1:
        atoms = [{"op": "或", "form": points[0].enum,
                  "args": [{"op": "且", "args": pair} for pair in alternatives]}]
    return Timepoints(segs, atoms, start + points[-1].of_start, start + text_end,
                      start + rest_start)
