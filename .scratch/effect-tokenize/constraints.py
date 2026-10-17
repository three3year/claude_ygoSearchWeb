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
    LABEL_PLEDGE: ("trigger", "subject", "action", "form", "scope", "source"),
    LABEL_SUMMON: ("form", "method", "procedure", "source"),
    CAT_TIMING: ("player", "window", "turn", "mode", "polarity"),
    CAT_MATERIAL: ("method", "materials"),
}
FIELD_LABEL = {"period": "期間", "count": "次數", "target": "對象", "sharing": "共用",
               "subject": "主體",
               "event": "事件", "banned": "禁止", "trigger": "觸發", "action": "動作",
               "form": "形式", "scope": "範圍", "source": "來源", "method": "方式",
               "procedure": "手續", "player": "回合", "window": "窗口", "mode": "型態",
               "polarity": "極性", "materials": "素材",
               # frame-args-v2:回合條件(時機與動作框架共用)、動作框架的列舉/連接/群組/回填
               "turn": "回合條件", "enumeration": "列舉", "link": "連接", "group": "群組",
               "backfill": "回填", "object": "對象",
               # frame-args-v3:動作框架的主題/所在/目的(回填與推得的欄名)
               "topic": "主題", "place": "所在", "goal": "目的", "inferred": "推得"}
# 動作框架的 subject 是主語(約束框架的 subject 是主體)
ACTION_FIELD_LABEL = dict(FIELD_LABEL, subject="主語")
# 回填欄的值是被填的欄名(topic/subject/object/source/place,frame-args-v3 起多主題、主語
# 與所在);
# 推得欄是 source/goal;「內容」欄顯示成 主題/對象/來源/所在/目的
# 群組號的顯示(或①/或②…);超出時退回 或(n)
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
PERIOD_TURN, PERIOD_DUEL, PERIOD_CHAIN = "回合", "決鬥", "同一連鎖"
# 時機窗口片語允許的詞:玩家、階段名(封閉值域)、ターン、時點與連接
PLAYERS = {"自分": "自分", "相手": "相手", "お互い": "雙方"}
# ドロー/前 給「自分ドローフェイズのドロー前に」(票 11);片語仍須含階段名或 ターン
WINDOW_WORDS = {"ターン", "開始", "終了", "時", "中", "次", "ドロー", "前"}
WINDOW_PARTICLES = {"p:の", "p:及び"}
MODE_LIMIT, MODE_ADD = "限定", "追加"
FORM_ONLY, FORM_CANNOT = "只能", "不能"
SUMMON_ONLY, SUMMON_CAN, SUMMON_CANNOT, SUMMON_MUST = (
    "只能以某方式", "可以某方式", "不能", "必須以某方式")
# 誓約的主體:自分(預設,不記)、このカード、自分の…;相手は…できない 是效果內容
PLEDGE_SUBJECTS = ("自分", "このカード")
SEG_END = ("。", "）", "●")
# 召喚條件主題的區域定語(EXデッキの表側のこのカードは P召喚できる)記成來源(票 11)
ZONE_WORDS = {"EXデッキ", "エクストラデッキ", "手札", "墓地", "デッキ"}
BOTH = "雙方"
POL_AFFIRM, POL_NEG, POL_CAN = "肯定", "否定", "可能"
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
    parts += _v2_parts(frame)
    return "・".join(parts)


def describe_action(frame):
    """動作框架的可選欄位(次數/窗口,票 06;回合條件/連接·群組/回填/列舉,frame-args-v2)
    → 「內容」欄字串;沒有時 None。"""
    parts = []
    if frame.get("count") is not None:
        period = frame.get("period")
        parts.append("次數 %s%s" % (frame["count"], "(%s)" % period if period else ""))
    if frame.get("window"):
        parts.append("窗口 %s" % frame["window"])
    if frame.get("turn"):
        parts.append("回合條件 %s" % frame["turn"])
    parts += _v2_parts(frame)
    return "・".join(parts) or None


def group_text(frame):
    """連接·群組的顯示(或①);沒有群組時 None。"""
    if frame.get("group") is None:
        return None
    n = frame["group"]
    mark = CIRCLED[n - 1] if 1 <= n <= len(CIRCLED) else "(%d)" % n
    return "%s%s" % (frame.get("link") or "", mark)


def _v2_parts(frame):
    """兩種框架共用的顯示段:連接·群組、回填、列舉(frame-args-v2)。"""
    parts = []
    if frame.get("group") is not None:
        parts.append(group_text(frame))
    if frame.get("backfill"):
        parts.append("回填 %s" % "・".join(ACTION_FIELD_LABEL[k] for k in frame["backfill"]))
    if frame.get("inferred"):
        parts.append("推得 %s" % "・".join(ACTION_FIELD_LABEL[k] for k in frame["inferred"]))
    if frame.get("enumeration"):
        parts.append("列舉 %s" % "／".join(frame["enumeration"]))
    return parts


def _procedure_text(step):
    args = [step.get("object"), step.get("source") and step["source"] + "から",
            step.get("goal") and step["goal"] + "へ"]
    head = ([step["subject"] + "が"] if step.get("subject") else []) + [step["action"]]
    return " ".join(head + [a for a in args if a])


class ConstraintFinder:
    """逐句找約束框架。x 是 frames.FrameExtractor(借用 token 讀取與論元切分)。"""

    def __init__(self, extractor):
        self.x = extractor

    # ── 片段讀取 ──
    def period_count(self, tokens, i, stop):
        """tokens[i] 起是否為「期間 に/で N 度/回/枚」(１ターンに１度、デュエル中に
        １度、同一チェーン上では１度、自分・相手のメインフェイズ１に１度)→ (期間, 次數,
        結束位置) 或 None。"""
        x = self.x
        words = []
        k = i
        while k < stop and k - i < 6 and tokens[k] not in ("p:に", "p:で") \
                and (token_kind(tokens[k]) in ("num", "lex", "dem")
                     or tokens[k] in ("・", "p:の")):
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
        elif "ターン" in text or any(
                t.startswith("W") and x.lex.closed_of[t] == "階段名" for t in tokens[i:k]):
            period = PERIOD_TURN          # 自分・相手のメインフェイズ１に１度:每回合那個階段
        else:
            return None
        value = tokens[k][4:]
        return period, int(value) if value.isdigit() else value, k + 2

    # ── 規則 ──
    def count_prefix(self, tokens, sentence, anchors):
        """子句開頭的「期間に N 度、」(票 01/02):發動句、P 區、代破、場地魔法一律
        是限制·次數(對象 この効果);同時把緊接其後的錨點的子句起點推到字首之後
        (動作框架的子句不含它)。"""
        start, end = sentence
        found = []
        for p in range(start, end):
            if not (p == start or tokens[p - 1] in ("、", "：", OPTION)
                    or tokens[p - 1] == "p:は" and self.extra) or not self._free(p):
                continue
            hit = self.period_count(tokens, p, end)
            if hit is None:
                continue
            period, value, j = hit
            if j < end and tokens[j] == "p:まで":
                j += 1                    # １ターンに３度まで、
            if j >= end or tokens[j] != "、":
                continue
            # 「名」は１ターンに１度、…:對象是主題(召喚條件句再補上 の特殊召喚)
            topic = self._text(start, p - 1) if tokens[p - 1] == "p:は" else None
            frame = self._count(period, value, topic or THIS_EFFECT)
            frame["topic"] = topic
            found.append(self._take(frame, p, j + 1))
            # 「相手ターンに１度、」「自分・相手のメインフェイズ１に１度、」:玩家/階段另出
            # 時機框架(限定)
            window = self.window_at(tokens, p, j)
            if window is not None and (window["player"] is not None
                                       or window["window"] != "ターン"):
                found.append(dict(self._timing(window["player"], window["window"],
                                               MODE_LIMIT, turn=window["turn"]),
                                  span=[p, j]))
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
        self.extra = extra
        # 誓約先於次數註記:「〜まで自分は…を１ターンに１度しか発動できない」是帶次數的誓約
        frames += self.pledges(tokens, sentence, anchors)
        frames += self.count_notes(tokens, sentence, anchors)
        frames += self.this_effect_notes(tokens, sentence, anchors)
        frames += self.paren_timing_notes(tokens, sentence)
        prefixes = self.count_prefix(tokens, sentence, anchors)
        frames += prefixes
        if extra:
            frames += self.summon_conditions(tokens, sentence, anchors, prefixes)
            frames += self.materials(tokens, sentence, anchors, card_type)
        if marker_idx is not None:
            frames += self.activation_windows(tokens, sentence, anchors,
                                              anchors[marker_idx]["head"])
        for fr in frames:
            fr.pop("topic", None)         # 字首規則給召喚條件規則看的內部欄位,不入產物
        return frames, self.consumed

    def _free(self, p):
        return not any(lo <= p < hi for lo, hi in self.consumed)

    def _take(self, frame, start, end):
        """登記框架的範圍(span)並把它吃掉(範圍內的錨點不出動作框架)。"""
        frame["span"] = [start, end]
        self.consumed.append((start, end))
        return frame

    @staticmethod
    def _timing(player, window, mode, polarity=POL_AFFIRM, turn=None):
        return {"category": CAT_TIMING, "subtype": None, "player": player,
                "window": window, "turn": turn, "mode": mode, "polarity": polarity}

    @staticmethod
    def _count(period, value, target, sharing=None):
        return {"category": CAT_LIMIT, "subtype": SUB_COUNT, "period": period,
                "count": value, "target": target, "sharing": sharing}

    def _text(self, start, end):
        """詞序列範圍的原文字面,去掉兩端的讀點與空白。"""
        return self.text_of(start, end).strip("、 　\n")

    # ── 時機 ──
    def _is_boundary(self, tokens, i):
        """片語前一格是邊界(句首/句讀/●/助詞;・ 與 の 不算)。"""
        return i == 0 or tokens[i - 1] == OPTION or (
            token_kind(tokens[i - 1]) in ("particle", "punct")
            and tokens[i - 1] not in ("・", "p:の"))

    def _is_verbish(self, token):
        """定語位置的動詞/する家族/否定・補助尾(除外された、していない)。"""
        from frames import AUXILIARY, NEGATORS, SURU_FAMILY, TAILS
        w = self.x.word(token)
        return w is not None and (w in SURU_FAMILY or w in NEGATORS or w in AUXILIARY
                                  or w in TAILS or self.x.lex.is_verb(token))

    def _relative_start(self, tokens, i, anchors):
        """限定詞前緊接定語動詞(このカードが除外された次のターン)時,顯示起點往前到子句
        邊界(句讀/●/：/（ 或上一個錨點的子句尾);否則就是 i。"""
        if i == 0 or not self._is_verbish(tokens[i - 1]):
            return i
        tails = {a["tail"] for a in anchors} if anchors else set()
        q = i
        while q > 0 and tokens[q - 1] not in ("、", "。", OPTION, "：", "（") \
                and q not in tails:
            q -= 1
        return q

    def turn_qualifier_at(self, tokens, i, stop, anchors=None):
        """tokens[i] 起是否為回合限定詞+の(frame-args-v2 票 04):そのターン/このターン、
        次の(自分・相手)ターン、(自分・相手)ターン、或以事件子句收尾的「〜したターン」
        (錨點帶形式名詞 ターン,須給 anchors)→ {text 限定詞原文, players, start 顯示起點,
        next の 之後的位置} 或 None。〜したターン 的原文從子句起點(主題 は 之後)到 ターン;
        次/玩家 前緊接定語動詞(このカードが除外された次のターン)時原文連同定語子句。"""
        x = self.x
        t = tokens[i]
        w = x.word(t)
        players = set()
        q_start = i

        def take_players(k):
            while k < stop and (x.word(tokens[k]) in PLAYERS or tokens[k] == "・"):
                if x.word(tokens[k]) in PLAYERS:
                    players.add(PLAYERS[x.word(tokens[k])])
                k += 1
            return k

        if t.startswith("d:") and x.word(t.split(":", 2)[2]) == "ターン":
            k = i + 1                                       # そのターン/このターン
        elif w == "次" and i + 1 < stop and tokens[i + 1] == "p:の":
            k = take_players(i + 2)
            if k >= stop or x.word(tokens[k]) != "ターン":
                return None
            k += 1
        elif w in PLAYERS:
            k = take_players(i)
            if k < stop and tokens[k] == "p:の" and k + 1 < stop \
                    and x.word(tokens[k + 1]) == "ターン":
                k += 1                                      # お互いのターン
            if k >= stop or x.word(tokens[k]) != "ターン":
                return None
            k += 1
        elif w == "ターン" and anchors:
            a = next((a for a in anchors
                      if a["nominalizer"] == "ターン" and a["end"] - 1 == i), None)
            if a is None:
                return None
            # 事件子句連同前面緊接的連用/て形子句(破壊され墓地へ送られたターン;v2-round1)
            q_start = a["clause_start"]
            prev = [b for b in anchors if b["tail"] == q_start and b is not a]
            while prev and prev[0]["form"] in ("te", "stem") \
                    and "、" not in tokens[prev[0]["end"]:prev[0]["tail"]]:
                q_start = prev[0]["clause_start"]
                prev = [b for b in anchors if b["tail"] == q_start and b is not prev[0]]
            topic = [h for h in range(q_start, a["head"]) if tokens[h] == "p:は"]
            if topic:
                q_start = topic[-1] + 1
            # 〜した自分・相手ターン:事件與 ターン 之間的玩家是回合欄
            for h in range(a["head"], i):
                if x.word(tokens[h]) in PLAYERS:
                    players.add(PLAYERS[x.word(tokens[h])])
            k = i + 1
        else:
            return None
        if k >= stop or tokens[k] != "p:の":
            return None
        if q_start == i:
            if not self._is_boundary(tokens, i) and not self._is_verbish(tokens[i - 1]):
                return None
            q_start = self._relative_start(tokens, i, anchors)
        return {"text": self._text(q_start, k), "players": players, "start": q_start,
                "next": k + 1}

    def _phase_at(self, tokens, j, stop):
        """tokens[j] 起的階段片語「(玩家)(の)(次の)階段名/ターン(開始時/終了時)」→
        (玩家集合, 窗口 token 清單, 是否含階段名或 ターン, 片語結束位置)。"""
        x = self.x
        players, rest, has_window = set(), [], False
        k = j
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
        return players, rest, has_window, k

    def window_at(self, tokens, i, stop, anchors=None):
        """tokens[i] 起是否為窗口片語「(回合限定詞の)(玩家)(の)(次の)階段名/ターン(開始時/
        終了時)+に/でも/にも/には/では/にのみ」→ dict(player 玩家, window 窗口字面, mode
        型態, end 片語結束位置, turn 回合條件, start 顯示起點, phase_player 階段部分的
        玩家) 或 None。有回合限定詞(そのターンの/〜したターンの/次のターンの)時窗口只記
        階段、限定詞記 turn;沒有時片語前一格須是邊界(句首/句讀/●/助詞),定語動詞後的
        ターン(破壊された自分・相手ターン)不算。"""
        x = self.x
        q = self.turn_qualifier_at(tokens, i, stop, anchors)
        j = q["next"] if q is not None else i
        if q is None and not self._is_boundary(tokens, i):
            return None                   # 定語後/並列中段/〜ターンの 的片語不是窗口
        players, rest, has_window, k = self._phase_at(tokens, j, stop)
        if (not has_window or k >= stop or k == j) and q is not None:
            # 限定詞後不是階段(そのターンの２回目…):退回不帶限定詞的解讀
            q, j = None, i
            if not self._is_boundary(tokens, i):
                return None
            players, rest, has_window, k = self._phase_at(tokens, j, stop)
        if not has_window or k >= stop or k == j:
            return None
        particle = tokens[k]
        window = "".join(x.surface(t) for t in rest)
        phase_player = BOTH if len(players) >= 2 or BOTH in players else (
            next(iter(players)) if players else None)
        merged = players | (q["players"] if q else set())
        player = BOTH if len(merged) >= 2 or BOTH in merged else (
            next(iter(merged)) if merged else None)
        hit = {"player": player, "window": window, "mode": MODE_LIMIT, "end": k + 1,
               "turn": q["text"] if q else None, "start": q["start"] if q else i,
               "phase_player": phase_player}
        if particle == "、" and x.word(tokens[k - 1]) == "時":
            return hit                    # 〜終了時、…発動できる
        if particle not in ("p:に", "p:で"):
            return None
        end = k + 1
        if end < stop and tokens[end] in ("p:も", "p:は", "p:のみ", "p:しか"):
            hit["mode"] = MODE_ADD if tokens[end] == "p:も" else MODE_LIMIT
            hit["end"] = end + 1
        elif particle == "p:で":
            return None
        return hit

    def activation_windows(self, tokens, sentence, anchors, marker_head):
        """發動句(票 03):收尾錨點之前、括弧外的窗口片語各出一個時機框架(型態 限定,
        でも/にも 為 追加)。觸發子句裡的窗口(相手がバトルフェイズに…発動した時)修飾的是
        事件,不是時機(round1)。"""
        start, _end = sentence
        found = []
        i = start
        while i < marker_head:
            if self.depth_at[i] or not self._free(i):
                i += 1
                continue
            hit = self.window_at(tokens, i, marker_head, anchors)
            # 觸發子句裡的窗口(相手がバトルフェイズに…発動した時)不是時機;以讀點收尾的
            # 窗口(バトルフェイズ終了時、…場合に)自成一段,仍是時機
            standalone = hit is not None and (
                tokens[hit["end"] - 1] == "、"
                or hit["end"] < marker_head and tokens[hit["end"]] == "、")
            # 看窗口收尾的 に 落在哪個子句:「〜したターンのエンドフェイズに相手が…した
            # 場合」的階段也在觸發子句裡(code review)
            if hit is None or (not standalone and any(
                    a["clause_start"] <= hit["end"] - 1 < a["head"] and a["conditional"]
                    for a in anchors)):
                i += 1
                continue
            if not standalone and self._window_in_relative(tokens, hit["end"],
                                                           marker_head):
                i += 1
                continue
            # 「〜したターンのエンドフェイズに」:吃掉的範圍從 ターン 起(事件子句照舊出
            # 條件框架),顯示範圍(span)連同事件子句
            frame = self._take(self._timing(hit["player"], hit["window"], hit["mode"],
                                            turn=hit["turn"]), i, hit["end"])
            frame["span"] = [hit["start"], hit["end"]]
            found.append(frame)
            i = hit["end"]
        return found

    def _window_in_relative(self, tokens, start, stop):
        """窗口片語之後、同一讀點段內出現「主動過去形的事件定語動詞+名詞」(自分ドロー
        フェイズに通常のドローをしたこのカード)→ 時間語黏在最近的事件述語上,窗口修飾的是
        那個定語動詞,不是發動窗口(票 11)。狀態不帶走窗口:〜ている(次のターンのスタンバイ
        フェイズに除外されているこのカードを…戻して発動できる)、被動結果(エンドフェイズに
        相手フィールドにセットされた魔法・罠カードを対象として)、狀態動詞(エンドフェイズに
        X素材を持ったXモンスターを対象として)的窗口仍是時機。"""
        from frames import STATE_LEMMAS, SURU_FAMILY, _PASSIVE_RE, verb_form
        x = self.x
        for k in range(start, stop - 1):
            t = tokens[k]
            if t == "、":
                return False
            w = x.word(t)
            if w is None:
                continue
            if w in SURU_FAMILY:
                event_past = w.endswith("した") and not w.endswith("された")
            else:
                event_past = x.lex.is_verb(t) \
                    and verb_form(w, x.lex.lemma_of[t]) == "past" \
                    and x.lex.lemma_of[t] not in STATE_LEMMAS \
                    and not _PASSIVE_RE.search(w)
            if event_past and x.is_noun_like(tokens[k + 1]):
                return True
        return False

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
                hit = self.window_at(tokens, k, seg_end, anchors)
                if hit is None:
                    k += 1
                    continue
                w_end = hit["end"]
                if w_end < seg_end and x.word(tokens[w_end]) == "発動" \
                        and x.word(tokens[w_end + 1]) in POTENTIAL_ALL:
                    polarity = POL_NEG if x.word(tokens[w_end + 1]) in (
                        "できない", "できず") else POL_AFFIRM
                    seg_frames.append(dict(self._timing(hit["player"], hit["window"],
                                                        hit["mode"], polarity,
                                                        turn=hit["turn"]),
                                           span=[hit["start"], w_end + 2]))
                    k = w_end + 2
                else:
                    k = w_end
            if seg_frames:
                self.consumed.append((i, seg_end))
                found += seg_frames
        return found

    # ── 誓約 ──
    def _anchor_args(self, tokens, a, clause_start):
        """錨點的論元(對象/來源/目的,只留有值的;主題/主語是動作框架的欄位,不入約束框架)。"""
        args, _carry = self.x.arguments(tokens, clause_start, a["head"] - a["fold"],
                                        trailing=a["form"] == "noun" or a["fold"] > 0)
        return {k: v for k, v in args.items() if v and k in ("object", "source", "goal")}

    def _action_name(self, tokens, a):
        """錨點的動作名,「・」並列(召喚・特殊召喚)串成一個;攻撃宣言 連 攻撃 一起記。"""
        a = dict(a)
        prev = self.x.word(tokens[a["head"] - 1]) \
            if a["head"] - 1 >= a["clause_start"] else None
        if a["action"] == "宣言" and prev == "攻撃":
            a["action"] = "攻撃宣言"
        elif a["action"] == "攻撃" and prev == "直接":
            a["action"] = "直接攻撃"
        return "・".join(self.x._coordinated_actions(tokens, a) + [a["action"]])

    def pledges(self, tokens, sentence, anchors):
        """誓約(票 04):「〜を発動する/したターン、自分は…」「このターン、自分は…」「この効果の
        発動後、ターン終了時まで自分は…」接一個以上 できない/できず 述語——每個否定述語出一個
        限制·誓約:動作、形式(しか → 只能,否則 不能)、範圍(しか 前的片語或對象)、來源(から);
        整段(觸發到句尾/括弧)吃掉。"""
        x = self.x
        start, end = sentence
        found = []
        for k in range(start + 2, end - 1):
            if not self._free(k):
                continue
            prev = tokens[k - 1]
            if prev == "、" and x.surface(tokens[k - 2]).endswith("ターン"):
                turn_at = k - 2
                trig_start = turn_at
                while trig_start > start and self._free(trig_start - 1) \
                        and tokens[trig_start - 1] not in SEG_END + ("、", "（", "："):
                    trig_start -= 1
                trigger = self._text(trig_start, turn_at + 1)
                # 觸發得是發動/召喚、這一回合,或以事件界定的回合(〜したターン)
                if not ("発動" in trigger or "召喚" in trigger
                        or trigger in ("このターン", "そのターン")
                        or trigger.endswith(("したターン", "するターン", "されたターン"))):
                    continue
            elif prev == "p:まで" and any(x.word(t) == "ターン"
                                         for t in tokens[max(start, k - 5):k]):
                trig_start = k - 1
                while trig_start > start and self._free(trig_start - 1) \
                        and tokens[trig_start - 1] not in SEG_END + ("（",):
                    trig_start -= 1
                trigger = self._text(trig_start, k)
                if "発動" not in trigger:
                    continue
            else:
                continue
            seg_end = k
            while seg_end < end and tokens[seg_end] not in SEG_END:
                seg_end += 1
            # 述語得是可能形否定(攻撃できない/発動ができない);被動否定(破壊されない)是
            # 保護效果,不是誓約
            preds = [a for a in anchors if k <= a["head"] < seg_end
                     and a["polarity"] == POL_NEG and a["nominalizer"] is None
                     and any(x.word(t) in ("できない", "できず")
                             for t in tokens[a["head"]:a["end"]])]
            if not preds:
                continue
            # 觸發裡有主題(この効果で特殊召喚したモンスターはこのターン、)是效果內容
            if "p:は" in tokens[trig_start:k]:
                continue
            # 主體:述語之前的「X は」;自分 不記,このカード/自分の… 記在主體欄,
            # 其他(相手は…できない)或條件子句(〜場合には)不是誓約
            subject, clause_start = self._pledge_subject(tokens, k, preds[0]["head"])
            if subject is False:
                continue
            for a in preds:
                if a is not preds[0]:
                    # 〜できず、自分のモンスターは攻撃できない:每個述語各自的主體
                    nxt, nxt_start = self._pledge_subject(tokens, clause_start, a["head"])
                    if nxt is not False:
                        subject, clause_start = nxt, nxt_start
                args = self._anchor_args(tokens, a, clause_start)
                head = a["head"] - a["fold"]
                shika = next((h for h in range(clause_start, head)
                              if tokens[h] == "p:しか"), None)
                wo = next((h for h in range(head - 1, clause_start - 1, -1)
                           if tokens[h] == "p:を"), None)
                if shika is not None:
                    # しか 前的原文是範圍(定語子句整段保留);對象在 しか 前(〜を１度しか)
                    # 或 しか 後(〜でしかモンスターを)時把對象放前面、片語括在後面
                    scope = self._text(clause_start, shika)
                    if args.get("object") and wo is not None and wo < shika:
                        scope = "%s(%s)" % (args["object"], self._text(wo + 1, shika))
                    elif args.get("object") and (wo is not None or scope.endswith("で")):
                        scope = "%s(%s)" % (args["object"], scope)
                elif args.get("object"):
                    scope = args["object"]
                else:
                    # 〜の効果の発動ができない:が 前的片語(去掉尾端的 の動作)是範圍;
                    # 什麼都沒有時主體就是範圍(このカードは攻撃できない)
                    ga = next((h for h in range(head - 1, clause_start - 1, -1)
                               if tokens[h] == "p:が"), None)
                    scope = self._text(clause_start, ga) if ga is not None else None
                    if scope and scope.endswith("の" + a["action"]):
                        scope = scope[:-len(a["action"]) - 1]
                found.append({"category": CAT_LIMIT, "subtype": SUB_PLEDGE,
                              "trigger": trigger, "subject": subject,
                              "action": self._action_name(tokens, a),
                              "form": FORM_ONLY if shika is not None else FORM_CANNOT,
                              "scope": scope, "source": args.get("source"),
                              "span": [trig_start if a is preds[0] else clause_start,
                                       a["tail"]]})
                clause_start = a["tail"]
            # 吃到最後一個否定述語為止;其後的肯定述語(戦闘ダメージは０になる)照舊是動作
            self.consumed.append((trig_start, preds[-1]["tail"]))
        return found

    def _pledge_subject(self, tokens, start, head):
        """[start, head) 裡的「X は」→ (主體, 述語子句起點);自分 回 None;沒有 は 回
        (None, start);主體不是 自分/このカード/自分の… 或含讀點/條件子句時回 (False, start)。"""
        wa = next((h for h in range(start, head) if tokens[h] == "p:は"), None)
        if wa is None:
            return None, start
        subject = self._text(start, wa)
        if not subject.startswith(PLEDGE_SUBJECTS) or "、" in subject \
                or subject.endswith(("場合に", "場合", "時に", "時")):
            return False, start
        return (None if subject == "自分" else subject), wa + 1

    def paren_timing_notes(self, tokens, sentence):
        """括弧註記「（ダメージステップでも発動可能/できる）」(round3):出追加/限定時機。"""
        x = self.x
        start, end = sentence
        found = []
        for i in range(start, end - 3):
            if tokens[i] != "（" or not self._free(i):
                continue
            hit = self.window_at(tokens, i + 1, end)
            if hit is None:
                continue
            w_end = hit["end"]
            if w_end + 2 < end and x.word(tokens[w_end]) == "発動" \
                    and x.word(tokens[w_end + 1]) in ("可能", "できる") \
                    and tokens[w_end + 2] == "）":
                found.append(self._take(
                    self._timing(hit["player"], hit["window"], hit["mode"],
                                 turn=hit["turn"]), i, w_end + 3))
        return found

    # ── 召喚條件 ──
    def summon_conditions(self, tokens, sentence, anchors, prefixes):
        """召喚條件(票 04,只在效果外文本):以召喚法收尾、極性 可能/否定、主題不是玩家的
        述語各出一個限制·召喚條件——形式(不能/只能以某方式/可以某方式 + 動作)、方式(でのみ/
        でしか 前的片語)、手續(它之前的錨點:動作與論元)、來源(から)。整段(上一個召喚條件之後
        到述語尾)吃掉;同句有「は期間に N 度、」字首時,字首框架的對象改記 主題の動作。"""
        x = self.x
        start, end = sentence
        found = []
        seg_start = start
        pending = []
        for a in anchors:
            if not self._free(a["head"]):
                seg_start, pending = a["tail"], []
                continue
            summon = a["action"].endswith("召喚") and a["nominalizer"] is None \
                and (a["polarity"] != POL_AFFIRM or a.get("obligation"))
            if summon and any(x.word(t) == "もう" or tokens[h] == "p:だけ"
                              for h, t in enumerate(tokens[a["clause_start"]:a["head"]],
                                                    a["clause_start"])):
                summon = False            # 通常召喚としてもう１度召喚できる:效果內容
            if not summon:
                if a["nominalizer"] == "ターン":
                    # 〜が発動したターン、…した場合に特殊召喚できる:事件回合是條件,
                    # 不是手續,照舊出條件動作框架
                    seg_start, pending = a["tail"], []
                elif not (a["action"].endswith("召喚") and a["nominalizer"] == "場合"):
                    pending.append(a)     # このカードを通常召喚する場合:是前提,不是手續
                continue
            topic_at = next((h for h in range(a["head"] - 1, a["clause_start"] - 1, -1)
                             if tokens[h] == "p:は"), None)
            if topic_at is not None and x.word(tokens[topic_at - 1]) in PLAYERS:
                seg_start, pending = a["tail"], []
                continue
            args = self._anchor_args(tokens, a, a["clause_start"])
            action = self._action_name(tokens, a)
            only = any(tokens[h] in ("p:のみ", "p:しか") and (
                tokens[h - 1] == "p:で" or x.word(tokens[h - 1]) in ("場合", "時"))
                for h in range(seg_start + 1, a["head"]))
            form = (SUMMON_MUST if a.get("obligation") else SUMMON_ONLY if only
                    else SUMMON_CAN if a["polarity"] == POL_CAN else SUMMON_CANNOT) + action
            method = None
            for d in range(a["head"] - 1, a["clause_start"], -1):
                if tokens[d] == "p:で" and tokens[d + 1] in ("p:のみ", "p:しか"):
                    m_start = topic_at + 1 if topic_at is not None and topic_at < d \
                        else a["clause_start"]
                    method = self._text(m_start, d)
                    break
            steps = []
            pre_end = self._possible_case(tokens, seg_start, a["head"], steps)
            for b in pending:
                step = {"action": self._action_name(tokens, b)}
                step.update(self._anchor_args(tokens, b, b["clause_start"]))
                steps.append((b["head"], step))
            procedure = [step for _pos, step in sorted(steps, key=lambda s: s[0])]
            if "source" not in args and topic_at is not None:
                # 主題的區域定語(EXデッキの表側のこのカードは)是召喚來源(票 11)
                t0 = max(pre_end, a["clause_start"])
                if t0 + 1 < topic_at and x.word(tokens[t0]) in ZONE_WORDS \
                        and tokens[t0 + 1] == "p:の":
                    args["source"] = x.surface(tokens[t0])
            span_start = seg_start
            for pf in prefixes:
                if seg_start <= pf["span"][0] < a["head"] and pf.get("topic"):
                    pf["target"] = pf["topic"] + "の" + action
                    span_start = max(span_start, pf["span"][1])
            found.append(self._take(
                {"category": CAT_LIMIT, "subtype": SUB_SUMMON, "form": form,
                 "action": action, "method": method, "procedure": procedure,
                 "source": args.get("source")}, span_start, a["tail"]))
            seg_start, pending = a["tail"], []
        return found

    def _possible_case(self, tokens, start, stop, steps):
        """「〜が X召喚可能な場合に」(レベル４がP召喚可能な場合にEXデッキの表側のこの
        カードはP召喚できる):可能 不是述語、沒有錨點,召喚法本身的前提記成手續第一步
        (動作 X召喚可能、主體 が 前到上一個讀點為止的片語;票 11)。步驟連同位置加進 steps,
        回傳片語結束位置(沒有時 start)。"""
        x = self.x
        for c in range(start + 2, stop - 3):
            if x.word(tokens[c]) != "可能" or x.word(tokens[c - 1]) != "召喚" \
                    or x.word(tokens[c + 1]) != "な" \
                    or x.word(tokens[c + 2]) != "場合" or tokens[c + 3] != "p:に":
                continue
            prefix, m0 = x._method_prefix(tokens, c - 2, start)
            step = {"action": prefix + "召喚可能"}
            if m0 - 1 > start and tokens[m0 - 1] == "p:が":
                s0 = max([start] + [h + 1 for h in range(start, m0 - 1)
                                    if tokens[h] == "、"])
                step["subject"] = self._text(s0, m0 - 1)
            steps.append((c, step))
            return c + 4
        return start

    # ── 素材 ──
    def materials(self, tokens, sentence, anchors, card_type):
        """素材(票 05,只在效果外文本):降臨句「〜により降臨」出一個素材框架(召喚法 儀式、
        清單是那張儀式魔法);沒有述語、沒有句號的素材行(含 ＋/× 或以數量收尾)出一個,
        ＋ 切項、每項尾端的 ×N/N体/N体以上 是數量(沒寫記 1),召喚法由卡片子類型帶入。"""
        x = self.x
        start, end = sentence
        if any(self._free(a["head"]) for a in anchors):
            return []
        descent = next((k for k in range(start + 1, end - 2)
                        if tokens[k] == "p:に" and tokens[k + 1] == "p:より"
                        and x.word(tokens[k + 2]) == "降臨"), None)
        if descent is not None:
            # 「A」「B」により降臨:連續的卡名各一項
            names = [k for k in range(start, descent) if token_kind(tokens[k]) == "name"]
            if len(names) >= 2 and names == list(range(start, descent)):
                items = [{"text": self._text(k, k + 1), "count": 1} for k in names]
            else:
                items = [{"text": self._text(start, descent), "count": 1}]
            return [self._take(
                {"category": CAT_MATERIAL, "subtype": None, "method": "儀式",
                 "materials": items}, start, end)]
        body = [k for k in range(start, end) if tokens[k] not in ("。", OPTION)]
        if not body or "。" in tokens[start:end] or "p:は" in tokens[start:end]:
            return []
        plus = [k for k in body if x.word(tokens[k]) == "＋"]
        last = tokens[body[-1]]
        quantified = token_kind(last) in ("quant", "counter") or (
            last.startswith("NUM:") and len(body) >= 2
            and x.word(tokens[body[-2]]) == "×")
        if not plus and not quantified:
            return []
        items, item_start = [], start
        for cut in plus + [body[-1] + 1]:
            items.append(self._material_item(tokens, item_start, cut))
            item_start = cut + 1
        return [self._take(
            {"category": CAT_MATERIAL, "subtype": None, "method": card_type,
             "materials": items}, start, end)]

    def _material_item(self, tokens, start, end):
        """素材清單的一項:尾端的 ×N / ×N体以上 / N体 / N体以上 是數量,其餘是素材字面。"""
        x = self.x
        count, k = 1, end
        last = tokens[k - 1]
        if token_kind(last) == "quant":                      # q::2:体:以上
            _, _wid, val, _counter, cmp_word = last.split(":", 4)
            count, k = val + cmp_word, k - 1
        elif token_kind(last) == "counter" and tokens[k - 2].startswith("NUM:"):
            count, k = int(tokens[k - 2][4:]), k - 2
        elif last.startswith("NUM:"):
            count, k = int(last[4:]), k - 1
        if k - 1 >= start and x.word(tokens[k - 1]) == "×":
            k -= 1
        # 〜モンスター１体ずつ合計４体:數量記 4(1体ずつ)
        if k - 4 >= start and x.word(tokens[k - 1]) == "合計" and tokens[k - 2] == "p:ずつ" \
                and tokens[k - 3] == "c:体" and tokens[k - 4].startswith("NUM:"):
            count = "%s(%s体ずつ)" % (count, tokens[k - 4][4:])
            k -= 4
        return {"text": self._text(start, k), "count": count}

    # ── 動作框架的可選欄位(票 06)──
    def action_fields(self, tokens, clause_start, head, in_activation, prev_anchor=None):
        """子句裡的「(期間に)N度だけ」記次數(與期間),非發動句的窗口片語記窗口(有回合
        限定詞時另記 turn:特殊召喚したターンのエンドフェイズに破壊される → 窗口 エンド
        フェイズ、回合條件 特殊召喚したターン;frame-args-v2 票 04);回要併進動作框架的
        欄位 dict(沒有時空 dict)。prev_anchor 是同句的上一個錨點(〜したターン 是它的形式
        名詞時,窗口片語從那個 ターン 起算)。"""
        x = self.x
        out = {}
        for k in range(clause_start, head - 1):
            # １度だけ / もう１度(召喚できる)
            if tokens[k].startswith("NUM:") and tokens[k + 1] == "c:度" and (
                    k + 2 < head and tokens[k + 2] == "p:だけ"
                    or k - 1 >= clause_start and x.word(tokens[k - 1]) == "もう"
                    or k + 2 < head and tokens[k + 2] == "、"
                    and "p:は" in tokens[clause_start:k]):
                out["count"] = int(tokens[k][4:])
                hit = self.period_count(tokens, k - 3, head) if k - 3 >= clause_start \
                    else None
                out["period"] = hit[0] if hit else None
                break
        if not in_activation:
            scan_from = clause_start
            anchors = None
            if (prev_anchor is not None and prev_anchor["nominalizer"] == "ターン"
                    and prev_anchor["tail"] == clause_start
                    and prev_anchor["end"] < clause_start
                    and tokens[prev_anchor["end"]] == "p:の"):
                scan_from = prev_anchor["end"] - 1        # 〜したターン|の|エンドフェイズに
                anchors = [prev_anchor]
            for k in range(scan_from, head):
                if self.depth_at[k]:
                    continue
                hit = self.window_at(tokens, k, head, anchors)
                if hit is not None:
                    player = hit["phase_player"]
                    out["window"] = (player if player not in (None, BOTH) else
                                     "自分・相手の" if player == BOTH else "") + hit["window"]
                    if hit["turn"]:
                        out["turn"] = hit["turn"]
                    break
        return out

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
            if not self._free(i):
                seg_start = i + 1         # 誓約吃掉的範圍(帶次數的誓約)不再當註記
                i += 1
                continue
            hit = self.period_count(tokens, i, end)
            chain_only = hit is None and x.word(t) == "同一" and i + 4 < end \
                and x.word(tokens[i + 1]) == "チェーン" and tokens[i + 3] == "p:で"
            if hit is None and not chain_only:
                i += 1
                continue
            if hit:
                period, value, j = hit
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
                found.append(self._take(self._count(period, value, THIS_EFFECT),
                                        i - 1, k + 1))
                seg_start = i = k + 1
                continue
            verbs, m = [], k
            while m < end and m - k < 5 and tokens[m] not in ("。", "）", "（") \
                    and x.word(tokens[m]) not in POTENTIAL_ALL:
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
            found.append(self._take(self._count(period, value, target, sharing),
                                    seg_start, stop))
            seg_start = i = stop
        return found
