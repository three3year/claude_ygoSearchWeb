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
# 時機窗口片語允許的詞:玩家、階段名(封閉值域)、ターン、時點與連接
PLAYERS = {"自分": "自分", "相手": "相手", "お互い": "雙方"}
WINDOW_WORDS = {"ターン", "開始", "終了", "時", "中", "次"}
WINDOW_PARTICLES = {"p:の", "p:及び"}
MODE_LIMIT, MODE_ADD = "限定", "追加"
BOTH = "雙方"
POL_AFFIRM, POL_NEG = "肯定", "否定"
THIS_EFFECT = "この効果"
COUNT_UNITS = {"度", "回", "枚"}
POTENTIAL_ALL = {"できる", "でき", "できない", "できず"}
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
        是限制·次數(對象 この効果);同時把緊接其後的錨點的子句起點推到字首之後
        (動作框架的子句不含它)。"""
        start, end = sentence
        found = []
        for p in range(start, end):
            if not (p == start or tokens[p - 1] in ("、", "：", OPTION))                     or not self._free(p):
                continue
            hit = self.period_count(tokens, p, end)
            if hit is None:
                continue
            period, value, _unit, j = hit
            if j >= end or tokens[j] != "、":
                continue
            found.append(self._take(
                {"category": CAT_LIMIT, "subtype": SUB_COUNT, "period": period,
                 "count": value, "target": THIS_EFFECT, "sharing": None},
                p, j + 1))
            for a in anchors:
                if a["clause_start"] <= p < a["head"]:
                    a["clause_start"] = j + 1
        return found

    def find(self, tokens, sentence, anchors, marker_idx, depth_at, extra=False,
             card_type=None, text_of=None):
        """一句 → (約束框架清單, 吃掉的詞序列範圍清單)。anchors 是這句的述語錨點
        (frames.py 已算好,clause_start 可被本函式推後)、marker_idx 是發動句收尾
        錨點的序(不是發動句時 None)、depth_at 每個 token 的括弧深度、extra 標效果外
        文本、card_type 卡片子類型、text_of(start, end) 取詞序列範圍的原文字面。
        框架只帶類別/子類/專屬欄位與 span,其餘共有欄位由 frames.py 補。"""
        self.text_of = text_of or (
            lambda a, b: "".join(self.x.surface(t) for t in tokens[a:b]))
        self.consumed = []
        frames = []
        self.depth_at = depth_at
        for rule in (self.count_notes, self.count_prefix):
            frames += rule(tokens, sentence, anchors)
        frames += self.this_effect_notes(tokens, sentence, anchors)
        if marker_idx is not None:
            frames += self.activation_windows(tokens, sentence,
                                              anchors[marker_idx]["head"])
        return frames, self.consumed

    def _free(self, p):
        return not any(lo <= p < hi for lo, hi in self.consumed)

    def _take(self, frame, start, end):
        """登記框架的範圍(span)並把它吃掉(範圍內的錨點不出動作框架)。"""
        frame["span"] = [start, end]
        self.consumed.append((start, end))
        return frame

    def _text(self, start, end):
        """詞序列範圍的原文字面,去掉兩端的讀點與空白。"""
        return self.text_of(start, end).strip("、 　\n")

    # ── 時機 ──
    def window_at(self, tokens, i, stop):
        """tokens[i] 起是否為窗口片語「(玩家)(の)(次の)階段名/ターン(開始時/終了時)+に/でも/
        にも/には/では/にのみ」→ (玩家, 窗口字面, 型態, 片語結束位置) 或 None。片語前一格
        須是邊界(句首/句讀/●/助詞),定語動詞後的 ターン(破壊された自分・相手ターン)不算。"""
        x = self.x
        if i > 0 and (token_kind(tokens[i - 1]) not in ("particle", "punct")
                      or tokens[i - 1] in ("・", "p:の")) \
                and tokens[i - 1] != OPTION:
            return None                   # 定語後/並列中段/〜ターンの 的片語不是窗口
        players, rest, has_window = set(), [], False
        k = i
        while k < stop:
            t = tokens[k]
            w = x.word(t)
            if w in PLAYERS:
                players.add(PLAYERS[w])
            elif t == "・" and players:
                if x.word(tokens[k - 1]) not in PLAYERS:
                    rest.append(t)        # メインフェイズ１・メインフェイズ２ 的並列
            elif t in WINDOW_PARTICLES:
                if not (players and tokens[k - 1] not in WINDOW_PARTICLES
                        and x.word(tokens[k - 1]) in PLAYERS):
                    rest.append(t)
            elif w is not None and (w in WINDOW_WORDS or (
                    t.startswith("W") and x.lex.closed_of[t] == "階段名")):
                rest.append(t)
                has_window = has_window or w == "ターン" or (
                    t.startswith("W") and x.lex.closed_of[t] == "階段名")
            else:
                break
            k += 1
        if not has_window or k >= stop or k == i:
            return None
        particle = tokens[k]
        if particle not in ("p:に", "p:で"):
            return None
        mode = MODE_LIMIT
        end = k + 1
        if end < stop and tokens[end] in ("p:も", "p:は", "p:のみ", "p:しか"):
            mode = MODE_ADD if tokens[end] == "p:も" else MODE_LIMIT
            end += 1
        elif particle == "p:で":
            return None
        window = "".join(x.surface(t) for t in rest)
        player = BOTH if len(players) == 2 or BOTH in players else (
            next(iter(players)) if players else None)
        return player, window, mode, end

    def activation_windows(self, tokens, sentence, marker_head):
        """發動句(票 03):收尾錨點之前、括弧外的窗口片語各出一個時機框架(型態 限定,
        でも/にも 為 追加)。"""
        start, _end = sentence
        found = []
        i = start
        while i < marker_head:
            if self.depth_at[i] or not self._free(i):
                i += 1
                continue
            hit = self.window_at(tokens, i, marker_head)
            if hit is None:
                i += 1
                continue
            player, window, mode, end = hit
            found.append(self._take(
                {"category": CAT_TIMING, "subtype": None, "player": player,
                 "window": window, "mode": mode, "polarity": POL_AFFIRM}, i, end))
            i = end
        return found

    def this_effect_notes(self, tokens, sentence, anchors):
        """「この効果は…」註記句(票 03;整句或括弧裡):窗口片語+発動できる/できない 出
        時機(でも/にも 追加、否定看 できない);「〜したターンには発動できない/使用できない」
        出限制·事件回合禁用(事件=は 後到 ターン 的原文、禁止=発動/使用)。認得出任一種時整段
        吃掉(句內的條件子句不是這張卡的動作);次數註記已由 count_notes 處理。"""
        x = self.x
        start, end = sentence
        found = []
        for i in range(start, end - 1):
            if not (tokens[i].startswith("d:この:") and x.word(tokens[i].split(":", 2)[2])
                    == "効果" and tokens[i + 1] == "p:は") or not self._free(i):
                continue
            seg_end = i + 2
            while seg_end < end and tokens[seg_end] not in ("。", "）", OPTION):
                seg_end += 1
            seg_frames = []
            # 事件回合禁用:錨點帶形式名詞 ターン,其後 に(は) + 発動/使用 + できない
            for a in anchors:
                if not (i + 2 <= a["head"] < seg_end and a["nominalizer"] == "ターン"):
                    continue
                k = a["end"]
                while k < seg_end and tokens[k] in ("p:に", "p:は"):
                    k += 1
                banned = x.word(tokens[k]) if k < seg_end else None
                if banned in ("発動", "使用") and k + 1 < seg_end \
                        and x.word(tokens[k + 1]) in ("できない", "できず"):
                    seg_frames.append({"category": CAT_LIMIT, "subtype": SUB_EVENT_TURN,
                                       "event": self._text(i + 2, a["end"]),
                                       "banned": banned, "span": [i, k + 2]})
            # 時機:窗口片語(前一格是 は/、)+ 発動 + できる/できない
            k = i + 2
            while k < seg_end:
                hit = self.window_at(tokens, k, seg_end)
                if hit is None:
                    k += 1
                    continue
                player, window, mode, w_end = hit
                if w_end < seg_end and x.word(tokens[w_end]) == "発動" \
                        and w_end + 1 < seg_end + 1 \
                        and x.word(tokens[w_end + 1]) in POTENTIAL_ALL:
                    polarity = POL_NEG if x.word(tokens[w_end + 1]) in (
                        "できない", "できず") else POL_AFFIRM
                    seg_frames.append({"category": CAT_TIMING, "subtype": None,
                                       "player": player, "window": window,
                                       "mode": mode, "polarity": polarity,
                                       "span": [k, w_end + 2]})
                    k = w_end + 2
                else:
                    k = w_end
            if seg_frames:
                self.consumed.append((i, seg_end))
                found += seg_frames
        return found

    def count_notes(self, tokens, sentence, anchors):
        """使用次數/發動次數註記(票 02):「X は (それぞれ) 期間に N 度 (、いずれか１つ)
        しか/まで (動作) できない/できず/できる」、「自分は X を 期間に N 度しか 特殊召喚
        できない」(對象 X の特殊召喚)、「同一チェーン上では発動できない」(同一連鎖 1 次),
        與括弧註記「（期間に N 度 まで/のみ）」(對象 この効果)。一句可有多個(できず、相連),
        主題從上一個註記結束處(或句首、括弧、●標籤)起算到 は。"""
        x = self.x
        start, end = sentence
        found = []
        seg_start = start
        i = start
        while i < end:
            t = tokens[i]
            if t in ("（", "：", OPTION):
                seg_start = i + 1
            hit = self.period_count(tokens, i, end)
            chain_only = hit is None and x.word(t) == "同一" and i + 4 < end                 and x.word(tokens[i + 1]) == "チェーン" and tokens[i + 3] == "p:で"
            if hit is None and not chain_only:
                i += 1
                continue
            if hit:
                period, value, _unit, j = hit
            else:
                period, value, j = PERIOD_CHAIN, 1, i + 4
                if j < end and tokens[j] == "p:は":
                    j += 1
            sharing = None
            k = j
            if k + 1 < end and tokens[k] == "、" and x.word(tokens[k + 1]) == "いずれか":
                sharing = "いずれか１つ"
                while k < end and tokens[k] not in ("p:しか", "p:まで", "p:のみ"):
                    k += 1
            if hit:
                if k >= end or tokens[k] not in ("p:しか", "p:まで", "p:のみ"):
                    i = j                         # 「期間に N 度、」字首 → count_prefix
                    continue
                k += 1
            # 括弧註記:（期間に N 度 まで/のみ）
            if k < end and tokens[k] == "）" and seg_start == i and tokens[i - 1] == "（":
                found.append(self._take(
                    {"category": CAT_LIMIT, "subtype": SUB_COUNT, "period": period,
                     "count": value, "target": THIS_EFFECT, "sharing": None},
                    i - 1, k + 1))
                seg_start = i = k + 1
                continue
            verbs, m = [], k
            while m < end and m - k < 5 and tokens[m] not in ("。", "）", "（")                     and x.word(tokens[m]) not in POTENTIAL_ALL:
                verbs.append(tokens[m])
                m += 1
            if m >= end or x.word(tokens[m]) not in POTENTIAL_ALL:
                i = j
                continue
            m += 1
            # 主題(は 前)與對象(自分は X を 形)
            topic_end = next((h for h in range(i - 1, seg_start - 1, -1)
                              if tokens[h] == "p:は"), None)
            topic = self._text(seg_start, topic_end) if topic_end is not None else ""
            action = "".join(x.surface(v) for v in verbs)
            if topic in ("", "自分", "お互い") and "p:を" in tokens[seg_start:i]:
                obj_start = topic_end + 1 if topic_end is not None else seg_start
                obj_end = tokens.index("p:を", obj_start, i)
                target = self._text(obj_start, obj_end) + "の" + (action or "できる")
            elif topic:
                target = topic
            elif found and found[-1]["span"][1] == seg_start:
                # 〜しか使用できず、同一チェーン上では発動できない:承接前一個註記的主題
                target, sharing = found[-1]["target"], found[-1]["sharing"]
            else:
                target = THIS_EFFECT
            if sharing is None and any(x.word(v) == "それぞれ"
                                       for v in tokens[seg_start:m]):
                sharing = "それぞれ"
            stop = m + 1 if m < end and tokens[m] == "、" else m
            found.append(self._take(
                {"category": CAT_LIMIT, "subtype": SUB_COUNT, "period": period,
                 "count": value, "target": target, "sharing": sharing},
                seg_start, stop))
            seg_start = i = stop
        return found
