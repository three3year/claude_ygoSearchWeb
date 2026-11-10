"""誰(段的 `agent`):抽取與句型模板成對放在一起。

- 字面:玩家字面 `AGENT_PLAYER_WORDS` 與動作回指「ドローしたプレイヤー」;`AGENT_PATTERN` 給句型用。
- 抽取:`parse_agent`(玩家字面寫成預設接法時是方的字串,其他接法記 `{"side", "text"}`,
  動作回指記 `{"ref", "segment"}`)。
- 模板:`render_agent`。預設接法 `agent_particle`(條件子句「が」、其餘「は」)兩邊共用。
"""

import re

from segment_history import last_segment_doing
from structure_shape import REASON_CLAUSE, REASON_REF, NoTemplate
from synonyms import ACTION_PAST
from zone_phrase import SIDE_WORDS


# 誰:玩家字面「自分/相手/お互い」與動作回指「ドローしたプレイヤー」(指回本區塊最近做過
# 那個動作的段);助詞 が/は(「お互いに」也是誰),後面可帶讀點。
PLAYER_REF_HEAD = "プレイヤー"
AGENT_PLAYER_WORDS = {"お互いのプレイヤー": "雙方各自", "相手プレイヤー": "對手",
                      "自分": "我方", "相手": "對手", "お互い": "雙方各自"}
AGENT_PATTERN = ("|".join(AGENT_PLAYER_WORDS) + "|(?:"
                 + "|".join(sorted(ACTION_PAST.values(), key=len, reverse=True))
                 + f"){PLAYER_REF_HEAD}")
_PLAYER_SIDES = {"我方": "自分", "對手": "相手", "雙方各自": "お互い"}
_AGENT_TEXT_RE = re.compile("^(?P<word>" + "|".join(AGENT_PLAYER_WORDS)
                            + ")(?P<marker>が|は|(?<=お互い)に)、?$")


def agent_particle(kind):
    """誰的預設接法:條件子句是「相手が〜した時」,效果句是「自分は〜する」(全庫 66:0、31:1)。"""
    return "が" if kind in ("條件", "被代替") else "は"


def agent_side(agent):
    """agent 格 → 方(字串或玩家字面的 side);動作回指沒有靜態的方,回 None。"""
    if isinstance(agent, dict):
        return agent.get("side")
    return agent


def parse_agent(state, word, marker, pause, kind):
    """誰的字面 → (agent 格, 原因)。玩家字面寫成預設接法(條件段「相手が」、其餘「自分は」)時
    是方的字串;其他接法(「お互いに」「自分は、」)記 `{"side", "text"}`(同受方的玩家字面);
    「ドローしたプレイヤー」記 `{"ref", "segment"}`,接法要是預設的。"""
    text = word + marker + (pause or "")
    if word not in AGENT_PLAYER_WORDS:
        past = word[:-len(PLAYER_REF_HEAD)]
        action = next(a for a, p in ACTION_PAST.items() if p == past)
        seg_id = state.last_segment_of_action.get(action)
        if seg_id is None:
            return None, REASON_REF
        if marker + (pause or "") != agent_particle(kind):
            return None, REASON_CLAUSE
        return {"ref": word, "segment": seg_id}, None
    side = AGENT_PLAYER_WORDS[word]
    if text == word + agent_particle(kind) and SIDE_WORDS.get(word) == side:
        return side, None
    return {"side": side, "text": text}, None


def render_agent(agent, seg, card):
    """誰:方的字串寫預設接法(條件段「相手が」、其餘「自分は」);玩家字面
    `{"side", "text"}` 驗過玩家字與方一致再照字面;動作回指 `{"ref", "segment"}` 要指回這一段之前
    最後一個做過那個動作的段,接法是預設的。"""
    particle = agent_particle(seg["kind"])
    if isinstance(agent, dict) and "ref" in agent:
        ref = agent["ref"] or ""
        past = ref[:-len(PLAYER_REF_HEAD)] if ref.endswith(PLAYER_REF_HEAD) else None
        action = next((a for a, p in ACTION_PAST.items() if p == past), None)
        if action is None or agent.get("segment") != last_segment_doing(action, seg, card):
            raise NoTemplate("誰的動作回指與先前的段不符")
        return ref + particle
    if isinstance(agent, dict):
        m = _AGENT_TEXT_RE.match(agent.get("text") or "")
        if not m or AGENT_PLAYER_WORDS[m.group("word")] != agent.get("side"):
            raise NoTemplate(f"誰無模板:{agent}")
        return agent["text"]
    if agent not in _PLAYER_SIDES:
        raise NoTemplate(f"誰無模板:{agent}")
    return _PLAYER_SIDES[agent] + particle
