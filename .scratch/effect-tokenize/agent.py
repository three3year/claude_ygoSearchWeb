# -*- coding: utf-8 -*-
"""施事者(frame-args-v4 票 07):誰做這個動作。

mark(ctx, tokens, frame):frame["agent"](closed_values.AGENTS 之一)、frame["agent_source"](AGENT_SOURCES,與
agent 同進退)、frame["agent_inferred"] = True(只在來源是 預設 時)。順序照規格 Implementation Decisions:

(1)受事者位:主語(が)、再來主題(は;延續來的照用)。是玩家(自分/相手/お互い;玩家名詞 プレイヤー/コントローラー
   帶玩家的也算)→ 該玩家,態 受身 除外(受身的玩家主題是承受方);是 このカード(含帶定語:墓地のこのカード、
   S召喚したこのカード)→ 此卡、是卡片片語(票 02 片語最後一段的中心詞類 卡)→ 其他卡,兩者只在框架自己帶對象
   (他動,或態空但有 object)時——受身、自動、沒對象的 このカード 是受事者。受事者位有字面但認不出是誰
   (ターンプレイヤー、そのコントローラー、その間)時留空、也不補預設:原文寫了誰做,只是規則讀不出。
(2)によって:受身框架,或態空/自動且沒對象的框架(相手によってフィールドから離れた),子句裡述語前最近的
   「X に よって/よる/より」——X 是玩家或玩家起頭(相手の効果によって)→ 該玩家;指名此卡(このカードの効果に
   よって)→ 此卡;卡片片語(融合モンスターカードによって、「X」カードの効果によって)→ 其他卡;其他(数によって、
   表示形式によって)不記。によって 之後還有 が/は/を 的是定語裡的(Xによって決められたYを…),不讀。
(3)事件主語:框架自己是效果類事件(動作 発動/攻撃/各召喚)而回指欄的找法是 事件、記了主人(subject)→ 主人映成
   玩家/此卡/其他卡。一般受事者的回指事件主語(相手がモンスターを特殊召喚した時…そのモンスターを破壊する 的
   破壊、その発動を無効にする 的 無効にする)說的是目標的來歷,不是本框架的施事者,不用。
(4)預設:位置 代價/效果、態不是 受身/自動、帶 object、以上都沒有 → 自分,來源 預設、agent_inferred;條件位、
   受身、自動、沒對象的留空。

不 import frames(循環 import);分詞輔助走 ctx,片語的段/中心詞類走 phrases.segment。
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import phrases  # noqa: E402
from closed_values import AGENTS, AGENT_SOURCES, HEAD_CARD  # noqa: E402

AGENT_SELF, AGENT_OPP, AGENT_BOTH, AGENT_THIS_CARD, AGENT_OTHER_CARD = AGENTS
SRC_TOPIC, SRC_SUBJECT, SRC_EVENT, SRC_NIYOTTE, SRC_DEFAULT = AGENT_SOURCES
PLAYER_AGENTS = {AGENT_SELF: AGENT_SELF, AGENT_OPP: AGENT_OPP, AGENT_BOTH: AGENT_BOTH}
PLAYER_NOUN_HEADS = {"プレイヤー", "コントローラー", "持ち主"}   # 玩家名詞:段的玩家就是施事者
THIS_CARD = "このカード"
VOICE_PASSIVE, VOICE_INTRANSITIVE, VOICE_TRANSITIVE = "受身", "自動", "他動"
POSITIONS_DEFAULT = ("代價", "效果")
NIYOTTE_WORDS = {"よって", "よる", "より"}        # 「に」之後的詞(frames.py 收 によって 論元的同一判準)
EFFECT_TAIL_WORDS = {"効果"}                      # Xの効果によって:施事者看 X
EVENT_ACTIONS = {"発動", "攻撃"}                  # 效果類事件的動作(各召喚以尾字比)
EVENT_ACTION_SUFFIX = "召喚"
VIA_EVENT = "事件"                                # anaphora.VIA_EVENT(只讀,不 import)
# 認不出是誰的受事者位字面:留空、不補預設(與「沒有字面」的 None 區別)
UNRESOLVED = object()


def mark(ctx, tokens, frame):
    found = _from_patient_slot(frame)
    if found is UNRESOLVED:
        return
    if found is None and (frame.get("voice") == VOICE_PASSIVE or not _has_object(frame)):
        found = _from_niyotte(ctx, tokens, frame)
    if found is None and _is_event_action(frame.get("action")):
        found = _from_event_subject(ctx, frame)
    if found is None and _has_object(frame) and frame.get("voice") in (None, VOICE_TRANSITIVE) \
            and frame.get("position") in POSITIONS_DEFAULT:
        found = (AGENT_SELF, SRC_DEFAULT)
    if found is None:
        return
    frame["agent"], frame["agent_source"] = found
    if found[1] == SRC_DEFAULT:
        frame["agent_inferred"] = True


def _has_object(frame):
    return bool(frame.get("object")) and "object" not in (frame.get("inferred") or ())


# ── (1)受事者位 ──
def _from_patient_slot(frame):
    """主語、再來主題 → (施事者, 來源) | UNRESOLVED(有字面但認不出) | None(兩欄都空)。"""
    passive = frame.get("voice") == VOICE_PASSIVE
    takes_card = _has_object(frame) and frame.get("voice") in (None, VOICE_TRANSITIVE)
    for key, source in (("subject", SRC_SUBJECT), ("topic", SRC_TOPIC)):
        text = frame.get(key)
        if not text:
            continue
        segments = ((frame.get("phrases") or {}).get(key) or {}).get("segments") or ()
        kinds = {_classify_segment(seg) for seg in segments} if segments else {_classify_text(text)}
        if len(kinds) != 1:
            return UNRESOLVED
        agent = kinds.pop()
        if agent is None:
            return UNRESOLVED
        if agent in PLAYER_AGENTS:
            return (agent, source) if not passive else None
        # 此卡/其他卡:受身、自動、沒對象時這一欄是受事者,不是施事者 → 交給 (2)〜(4)
        return (agent, source) if takes_card else None
    return None


def _classify_segment(seg):
    """片語的一段 → 施事者值或 None:玩家詞、帶玩家的玩家名詞、此卡(段尾 このカード)、卡片片語(中心詞類 卡)。"""
    text = seg["text"]
    if text in PLAYER_AGENTS:
        return PLAYER_AGENTS[text]
    if seg.get("head") in PLAYER_NOUN_HEADS:
        return PLAYER_AGENTS.get(seg.get("player"))
    if _is_this_card(text):
        return AGENT_THIS_CARD
    if seg.get("head_kind") == HEAD_CARD:
        return AGENT_OTHER_CARD
    return None


def _classify_text(text):
    """沒有片語可讀時只看字面(玩家詞、此卡)。"""
    if text in PLAYER_AGENTS:
        return PLAYER_AGENTS[text]
    if _is_this_card(text):
        return AGENT_THIS_CARD
    return None


def _is_this_card(text):
    return text.rstrip("の").endswith(THIS_CARD)


# ── (2)によって ──
def _from_niyotte(ctx, tokens, frame):
    """子句裡述語前最近的「X に よって/よる/より」→ (施事者, によって) | None。"""
    start, end = frame.get("span") or (0, 0)
    end = min(end, len(tokens))
    hits = [k for k in range(start, end - 1)
            if tokens[k] == "p:に" and ctx.word(tokens[k + 1]) in NIYOTTE_WORDS]
    if not hits:
        return None
    k = hits[-1]
    if _attributive_after(ctx, tokens, k + 2, end):
        return None
    j = k
    while j > start and (ctx.is_noun_like(tokens[j - 1]) or tokens[j - 1] == "p:の"):
        j -= 1
    agent = _classify_run(ctx, tokens[j:k])
    return (agent, SRC_NIYOTTE) if agent else None


def _attributive_after(ctx, tokens, start, end):
    """によって 之後先出現述語、述語後面還有名詞格 → によって 修飾的是定語裡的述語(Xによって決められたYを),
    不是本框架的述語。"""
    seen_predicate = False
    for t in tokens[start:end]:
        if seen_predicate and ctx.is_noun_like(t):
            return True
        if ctx.is_predicate(t):
            seen_predicate = True
    return False


def _classify_run(ctx, run):
    """によって 前的名詞段 → 施事者值或 None:尾巴的「の効果」去掉後,玩家起頭 → 該玩家、含 このカード → 此卡、
    中心詞類 卡 → 其他卡。"""
    if len(run) >= 2 and run[-2] == "p:の" and ctx.word(run[-1]) in EFFECT_TAIL_WORDS:
        run = run[:-2]
    if not run:
        return None
    if ctx.word(run[0]) in PLAYER_AGENTS:
        return PLAYER_AGENTS[ctx.word(run[0])]
    if any(ctx.surface(t) == THIS_CARD for t in run):
        return AGENT_THIS_CARD
    if phrases.segment(ctx, list(run))["head_kind"] == HEAD_CARD:
        return AGENT_OTHER_CARD
    return None


# ── (3)事件主語 ──
def _is_event_action(action):
    return bool(action) and (action in EVENT_ACTIONS or action.endswith(EVENT_ACTION_SUFFIX))


def _from_event_subject(ctx, frame):
    """效果類事件框架的回指欄(找法 事件)記了主人 → (主人映成的施事者, 事件主語) | None。"""
    anaphora = frame.get("anaphora") or {}
    owner = anaphora.get("subject")
    if anaphora.get("via") != VIA_EVENT or not owner:
        return None
    agent = _classify_text(owner)
    if agent is None:
        for word in PLAYER_AGENTS:
            if owner.startswith(word) and owner[len(word):len(word) + 1] in ("", "の"):
                agent = PLAYER_AGENTS[word]
                break
    if agent is None and phrases.segment(ctx, ctx.tokenize(owner))["head_kind"] == HEAD_CARD:
        agent = AGENT_OTHER_CARD
    return (agent, SRC_EVENT) if agent else None


# ── 報告 ──
def fill_state(frame):
    """填充率的列(report.py 經 enrich.FILL_RATE_ROWS 讀):施事者 → 有值/推得/None。"""
    if not frame.get("agent"):
        return None
    return "推得" if frame.get("agent_inferred") else "有值"


POSITIONS = ("代價", "效果", "條件")


def count_section(records):
    """報告小節「施事者各值 × 來源」:動作框架數,值一列、來源一欄;另一張表各來源分位置。"""
    by_source = Counter()
    by_position = Counter()
    for rec in records:
        for fr in rec["frames"]:
            if fr.get("agent"):
                by_source[(fr["agent"], fr["agent_source"])] += 1
                by_position[(fr["agent_source"], fr["position"])] += 1
    lines = ["值 自分/相手/お互い/此卡/其他卡;來源 主題/主語(受事者位的字面)、によって(受身與沒對象的框架)、"
             "事件主語(效果類事件框架的回指主人)、預設(代價/效果位、他動、帶對象、沒寫誰做 → 自分,標推得)。", "",
             "| 施事者 | " + " | ".join(AGENT_SOURCES) + " | 合計 |", "|---|" + "---|" * (len(AGENT_SOURCES) + 1)]
    for agent in AGENTS:
        row = [by_source[(agent, src)] for src in AGENT_SOURCES]
        lines.append("| %s | %s | %s |" % (agent, " | ".join(format(c, ",") for c in row), format(sum(row), ",")))
    total = [sum(by_source[(agent, src)] for agent in AGENTS) for src in AGENT_SOURCES]
    lines.append("| 合計 | %s | %s |" % (" | ".join(format(c, ",") for c in total), format(sum(total), ",")))
    lines += ["", "| 來源 | " + " | ".join(POSITIONS) + " |", "|---|" + "---|" * len(POSITIONS)]
    for src in AGENT_SOURCES:
        lines.append("| %s | %s |" % (src, " | ".join(format(by_position[(src, pos)], ",") for pos in POSITIONS)))
    return lines
