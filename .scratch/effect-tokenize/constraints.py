# -*- coding: utf-8 -*-
"""約束框架(規格 .scratch/constraint-frames,票 01〜06):由句型認出、不靠述語錨點
生出的框架,與動作框架並列,記效果或卡片「能怎麼用、什麼時候用、怎麼出場」。

被認成約束的句子或子句不再另出動作框架(取代規則):frames.py 逐句呼叫
ConstraintFinder.find() 拿到約束框架與被吃掉的詞序列範圍,落在範圍內的述語錨點
不出動作框架;兩種框架依原文位置(詞序列範圍起點)混排。

框架共有欄位:kind(約束)、category(限制/時機/素材)、subtype(限制才有:次數/
事件回合禁用/誓約/召喚條件)、sentence、span、clause、option、label;各類專屬欄位
見 FIELDS。describe() 把專屬欄位併成一欄「內容」字串,拆解頁與檢驗批次檔共用。
"""

from report import token_kind

KIND_ACTION, KIND_CONSTRAINT = "動作", "約束"
CAT_LIMIT, CAT_TIMING, CAT_MATERIAL = "限制", "時機", "素材"
SUB_COUNT, SUB_EVENT_TURN, SUB_PLEDGE, SUB_SUMMON = (
    "次數", "事件回合禁用", "誓約", "召喚條件")
LABEL_COUNT = CAT_LIMIT + "·" + SUB_COUNT
LABEL_EVENT_TURN = CAT_LIMIT + "·" + SUB_EVENT_TURN
LABEL_PLEDGE = CAT_LIMIT + "·" + SUB_PLEDGE
LABEL_SUMMON = CAT_LIMIT + "·" + SUB_SUMMON
# 類別·子類 → 專屬欄位(順序即「內容」欄的顯示順序)
FIELDS = {
    LABEL_COUNT: ("period", "count", "target", "sharing"),
    LABEL_EVENT_TURN: ("event", "banned"),
    LABEL_PLEDGE: ("trigger", "action", "form", "scope", "source"),
    LABEL_SUMMON: ("form", "method", "procedure", "source"),
    CAT_TIMING: ("player", "window", "mode", "polarity"),
    CAT_MATERIAL: ("method", "materials"),
}
FIELD_LABEL = {"period": "期間", "count": "次數", "target": "對象", "sharing": "共用",
               "event": "事件", "banned": "禁止", "trigger": "觸發", "action": "動作",
               "form": "形式", "scope": "範圍", "source": "來源", "method": "方式",
               "procedure": "手續", "player": "回合", "window": "窗口", "mode": "型態",
               "polarity": "極性", "materials": "素材"}
PERIOD_TURN, PERIOD_DUEL, PERIOD_CHAIN = "回合", "決鬥", "同一連鎖"
THIS_EFFECT = "この効果"
COUNT_UNITS = {"度", "回", "枚"}
OPTION = "●"


def label_of(frame):
    return frame["category"] + ("·" + frame["subtype"] if frame["subtype"] else "")


def describe(frame):
    """約束框架的專屬欄位 → 「內容」欄字串(欄位名 值・欄位名 值)。"""
    parts = []
    for key in FIELDS[label_of(frame)]:
        value = frame.get(key)
        if value in (None, "", []):
            continue
        if key == "materials":
            value = "、".join("%s×%s" % (m["text"], m["count"]) for m in value)
        elif key == "procedure":
            value = ";".join(_procedure_text(p) for p in value)
        parts.append("%s %s" % (FIELD_LABEL[key], value))
    return "・".join(parts)


def describe_action(frame):
    """動作框架的可選欄位(次數/窗口,票 06)→ 「內容」欄字串;沒有時 None。"""
    parts = []
    if frame.get("count") is not None:
        period = frame.get("period")
        parts.append("次數 %s%s" % (frame["count"], "(%s)" % period if period else ""))
    if frame.get("window"):
        parts.append("窗口 %s" % frame["window"])
    return "・".join(parts) or None


def _procedure_text(step):
    args = [step.get("object"), step.get("source") and step["source"] + "から",
            step.get("goal") and step["goal"] + "へ"]
    return " ".join([step["action"]] + [a for a in args if a])


class ConstraintFinder:
    """逐句找約束框架。x 是 frames.FrameExtractor(借用 token 讀取與論元切分)。"""

    def __init__(self, extractor):
        self.x = extractor

    # ── 片段讀取 ──
    def period_count(self, tokens, i, stop):
        """tokens[i] 起是否為「期間 に/で N 度/回/枚」(１ターンに１度、デュエル中に
        １度、同一チェーン上では１度)→ (期間, 次數, 量詞, 結束位置) 或 None。"""
        x = self.x
        words = []
        k = i
        while k < stop and k - i < 4 and tokens[k] not in ("p:に", "p:で") \
                and token_kind(tokens[k]) in ("num", "lex", "dem"):
            words.append(x.surface(tokens[k]))
            k += 1
        if not words or k >= stop or tokens[k] not in ("p:に", "p:で"):
            return None
        k += 1
        if k < stop and tokens[k] == "p:は":
            k += 1
        if k + 1 >= stop or not tokens[k].startswith("NUM:"):
            return None
        counter = tokens[k + 1]
        if not counter.startswith("c:") or counter[2:] not in COUNT_UNITS:
            return None
        text = "".join(words)
        if "チェーン" in text:
            period = PERIOD_CHAIN
        elif "デュエル" in text:
            period = PERIOD_DUEL
        elif "ターン" in text:
            period = PERIOD_TURN
        else:
            return None
        value = tokens[k][4:]
        return period, int(value) if value.isdigit() else value, counter[2:], k + 2

    # ── 規則 ──
    def count_prefix(self, tokens, sentence, anchors):
        """子句開頭的「期間に N 度、」(票 01/02):發動句、P 區、代破、場地魔法一律
        是限制·次數。回 (框架清單, 吃掉的範圍清單);同時把緊接其後的錨點的子句
        起點推到字首之後(動作框架的子句不含它)。"""
        start, end = sentence
        found, consumed = [], []
        for p in range(start, end):
            if not (p == start or tokens[p - 1] in ("、", "：", OPTION)):
                continue
            hit = self.period_count(tokens, p, end)
            if hit is None:
                continue
            period, value, _unit, j = hit
            if j >= end or tokens[j] != "、":
                continue
            found.append({"category": CAT_LIMIT, "subtype": SUB_COUNT,
                          "period": period, "count": value, "target": THIS_EFFECT,
                          "sharing": None, "span": [p, j + 1]})
            consumed.append((p, j + 1))
            for a in anchors:
                if a["clause_start"] <= p < a["head"]:
                    a["clause_start"] = j + 1
        return found, consumed

    def find(self, tokens, sentence, anchors, marker_idx, depth_at, extra=False,
             card_type=None, text_of=None):
        """一句 → (約束框架清單, 吃掉的詞序列範圍清單)。anchors 是這句的述語錨點
        (frames.py 已算好,clause_start 可被本函式推後)、marker_idx 是發動句收尾
        錨點的序(不是發動句時 None)、depth_at 每個 token 的括弧深度、extra 標效果外
        文本、card_type 卡片子類型、text_of(start, end) 取詞序列範圍的原文字面。
        框架只帶類別/子類/專屬欄位與 span,其餘共有欄位由 frames.py 補。"""
        self.text_of = text_of or (
            lambda a, b: "".join(self.x.surface(t) for t in tokens[a:b]))
        frames, consumed = [], []
        for rule in (self.count_prefix,):
            found, used = rule(tokens, sentence, anchors)
            frames += found
            consumed += used
        return frames, consumed
