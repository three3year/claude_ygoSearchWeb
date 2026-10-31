# -*- coding: utf-8 -*-
"""論元片語(frame-args-v4 票 02 段/中心詞/中心詞類/玩家/區域/指示詞、票 03 修飾語、票 04 數量)。

structure(ctx, tokens, frame):替動作框架加 frame["phrases"] = {"object"|"topic"|"subject"|"goal": Phrase},
只放有字面的欄;推得的目的沒有片語。Phrase/Segment/Modifier/Quantity 的形狀見 enrich.py 與
`.scratch/frame-args-v4/spec.md`;封閉值域在 closed_values.py。

片語讀**切區域之前**的受事者字面(frame["_raw"],frames.py 切出來源/所在時暫存;enrich 用完 pop),
所以切走的區域在片語裡仍留一份;Phrase 的 text 是該欄現在的值(切後),不改。

字面 → 詞序列:在句子的詞序列裡找字面相連的一段(先子句範圍、再整句——延續來的主題與回填的對象
在別的子句),找不到時(讀點接起來的多格、省略寫法)把字面重新分詞。

切段:受事者並列詞(ctx.coordinates:と/か/や/及び/または,と同じ 的 と 不算)與「・」。並列詞前一格是數量
(1体と…)或類是卡的名詞(「X」か「Y」、このカードと…)時切;前一格是屬性/非卡/其他類的詞時只在後面到下一個
並列為止沒有 の/が 時切(攻撃力と守備力 切;攻撃力か守備力が2100のモンスター、ドラゴン族か植物族のチューナー
是並列的修飾語,不切);夾在兩個區域/玩家詞之間的(自分か相手の、手札かフィールドの)是區域內部的並列、不切。
「・」要求前一格是名詞格且類不是其他,而且不論類都看後面有沒有 の/が(魔法・罠カード、攻撃力・守備力 切;
融合・S・Xモンスター、光・闇属性、魔法使い族・ドラゴン族モンスター、レベル4・5、魔法・罠カードの効果、
自分フィールド・墓地のモンスター 不切)。

中心詞:段去掉尾端的括號註記(含卡片的數值註記「（…族・…・攻／守0）」)、助詞、數量尾(數字/量詞/範圍/まで/
運算符、任意の数/好きな数/全て)後的最後一格;
指示詞格(そのモンスター)與省略寫法(魔法(カード))取被指/補全的詞;分詞拆成兩格的 特殊|召喚、X|素材、
カード|名 合記一格。只剩數量的段(1枚、2体以上)中心詞就是那段數量、類 指示詞(名詞省略);純數值(0、1000)
類 非卡。

指示詞:段以 その/それ/それら/対象の/この効果の対象 起頭(この 不算)。玩家與區域:段裡最後一個定語述語之後
的字面交給區域辨識(places.parse_place;除外されている… 的狀態寫法例外看整段);沒認出玩家而段以玩家詞
起頭、段裡沒有述語或 の 以外的助詞時,玩家就是段首那個(相手モンスター、自分のLP)。玩家拼法走
closed_values.PLACE_PLAYER。
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import places  # noqa: E402
from closed_values import (HEAD_CARD, HEAD_DEMONSTRATIVE, HEAD_NON_CARD, OTHER,  # noqa: E402
                           PHRASE_KEYS, PLACE_PLAYER, QUANTITY_KINDS, head_kind)
from report import token_kind  # noqa: E402

PHRASE_LABELS = (("object", "對象"), ("topic", "主題"), ("subject", "主語"), ("goal", "目的"))
# 數量尾的格(票 04 在這裡接手數量本身)
QUANTITY_TOKEN_KINDS = {"num", "counter", "range"}
QUANTITY_WORD_TAIL = {"全て"}                             # 段尾單格的量化詞
QUANTITY_PHRASE_TAIL = (("任意", "p:の", "数"), ("好きな", "p:の", "数"))
PLAYER_WORDS = {"自分", "相手", "お互い"}
DEMONSTRATIVE_WORDS = {"それ", "それら", "その"}         # その 單獨一格:その3枚、その「X」
# 分詞拆開的複合中心詞:前一格是召喚法前綴(m:)時 召喚/素材 合記(特殊召喚、X素材);カード|名 合記 カード名
METHOD_JOIN_HEADS = {"召喚", "素材"}
OPERATORS = {"×", "＋", "－"}                              # 數值運算(…の数×300):數量尾的一部分
NOUN_ITEM_KINDS = {"lex", "dem", "elided", "name", "cname"}   # 「・」前能當並列項的格
LINK_PARTICLES = {"p:の", "p:が"}                            # 並列詞之後還有這些:並列的是修飾語
PAREN_OPEN, PAREN_CLOSE = "（", "）"
SKIP_IN_CORE = {"、", PAREN_OPEN, PAREN_CLOSE, "・"}
COUNT_HEADS = {"数", "合計"}                                 # 中心詞是數:區域修飾的是數,不是受事者
# 數量(票 04)
Q_FIXED, Q_UPPER, Q_LOWER, Q_ANY, Q_ALL = QUANTITY_KINDS
QUANTITY_COUNTERS = {"枚", "体", "つ", "種類", "個", "組", "回"}      # 規格列的量詞;ヵ所/度 不算
QUANTITY_COMPARE_KIND = {"以上": Q_LOWER, "以下": Q_UPPER}            # N体以上 下限、N体以下 上限
QUANTITY_ANY_PHRASES = (("任意", "の", "数"), ("任意", "の", "枚", "数"), ("任意", "の", "個", "数"),
                        ("好き", "な", "数"))                         # 任意の数/任意の枚数/好きな数(字面比)
QUANTITY_TAIL_PARTICLES = {"p:まで", "p:の", "p:ずつ"}                  # 段尾數量裡會出現的助詞
CLAUSE_QUANTITY_SKIP = (("ランダム", "に"), ("それぞれ",))             # を 與數量之間可夾的副詞(不進字面)
CLAUSE_QUANTITY_STOP = {"。", "、", "p:を"}                            # 引用量往後找的邊界
CLAUSE_QUANTITY_REACH = 12                                             # 引用量最多往後看幾格


def structure(ctx, tokens, frame):
    """票 02:段、中心詞、中心詞類、指示詞、玩家、區域(修飾語與數量由票 03/04 補進 Segment)。"""
    raw = frame.get("_raw") or {}
    inferred = frame.get("inferred") or ()
    surfaces = None
    phrases = {}
    for key in PHRASE_KEYS:
        text = frame.get(key)
        if not text or key in inferred:
            continue
        if surfaces is None:
            surfaces = [ctx.surface(t) for t in tokens]
        span = frame.get("span")
        found = locate(ctx, tokens, surfaces, raw.get(key) or text, span)
        run = tokens[found[0]:found[1]] if found else ctx.tokenize(raw.get(key) or text)
        segments = [segment(ctx, chunk) for chunk in split(ctx, run)]
        if key == "object" and found and not any(seg["quantity"] for seg in segments):
            quantity = clause_quantity(ctx, tokens, surfaces, found[1], span,
                                       "object" in (frame.get("backfill") or ()))
            if quantity:
                segments[-1]["quantity"] = quantity
        phrases[key] = {"text": text, "segments": segments}
    if phrases:
        frame["phrases"] = phrases


def locate(ctx, tokens, surfaces, literal, span):
    """字面 → 句子詞序列裡字面相連的一段的位置 (起, 迄)(先子句範圍、再整句);對不回時 None
    (呼叫端重新分詞)。"""
    windows = ([(span[0], span[1])] if span else []) + [(0, len(tokens))]
    for lo, hi in windows:
        hi = min(hi, len(tokens))
        for i in range(lo, hi):
            if not literal.startswith(surfaces[i]):
                continue
            acc = ""
            for j in range(i, hi):
                acc += surfaces[j]
                if acc == literal:
                    return i, j + 1
                if not literal.startswith(acc):
                    break
    return None


# ── 切段 ──
def split(ctx, run):
    """詞序列 → 段的詞序列清單(並列詞本身不屬任何段)。"""
    chunks, current = [], []
    for k in range(len(run)):
        if current and _is_boundary(ctx, run, k):
            chunks.append(current)
            current = []
            continue
        current.append(run[k])
    if current:
        chunks.append(current)
    return chunks


def _is_boundary(ctx, run, k):
    is_dot = run[k] == "・"
    if not (is_dot or ctx.coordinates(run, k)) or k + 1 >= len(run):
        return False
    prev = run[k - 1]
    if not is_dot and _is_region_word(ctx, prev) and _is_region_word(ctx, run[k + 1]):
        return False                      # 自分か相手の、手札かフィールドの:區域內部的並列
    prev_kind = token_kind(prev)
    if prev_kind in QUANTITY_TOKEN_KINDS or (prev_kind == "quant" and prev.split(":")[1] == ""):
        return not is_dot                 # 1体と…:完整的受事者;レベル4・5 是一個數值修飾語
    if prev_kind not in NOUN_ITEM_KINDS and prev_kind != "quant":
        return not is_dot                 # 融合・S・X、光・闇:前綴的並列;並列詞之後照切
    kind = head_kind(_head_text(ctx, run, k - 1))
    if is_dot:
        if kind == OTHER:
            return False                  # 魔法使い族・ドラゴン族モンスター:修飾語的並列
    elif kind == HEAD_CARD:
        return True                       # このカードと…のモンスター:兩個受事者
    rest = run[k + 1:]
    stop = next((m for m in range(len(rest)) if rest[m] == "・" or ctx.coordinates(rest, m)), len(rest))
    return not any(u in LINK_PARTICLES for u in rest[:stop])


def _is_region_word(ctx, token):
    base = _base(ctx, token)
    return bool(base) and (base in PLAYER_WORDS or bool(places.parse_place(base)[1]))


def _base(ctx, token):
    """格的「詞」:詞典詞的字面、指示詞格與省略寫法被指/補全的詞;其餘 None。"""
    kind = token_kind(token)
    if kind == "lex":
        return ctx.word(token)
    if kind in ("dem", "elided"):
        return ctx.surface(token.split(":", 2)[2])
    return None


# ── 一段 ──
def segment(ctx, chunk):
    text = "".join(ctx.surface(t) for t in chunk)
    core = _strip_tail(ctx, chunk)
    head_at = _head_index(ctx, core)
    if head_at is not None:
        head = _head_text(ctx, core, head_at)
        kind = head_kind(head)
    else:
        # 只剩數量(1枚、2体以上:名詞省略)或純數值(0、1000)的段
        tail = [t for t in chunk[len(core):] if token_kind(t) != "particle" or t == "p:まで"]
        head = "".join(ctx.surface(t) for t in tail) or None
        kind = head_kind(head)
        if head and kind == OTHER:
            kind = HEAD_DEMONSTRATIVE if any(token_kind(t) == "counter" for t in tail) else HEAD_NON_CARD
    player, zones = _place_of(ctx, chunk, text, head)
    return {"text": text, "head": head, "head_kind": kind, "demonstrative": _demonstrative(ctx, chunk),
            "player": player, "zones": zones, "quantity": _tail_quantity(ctx, chunk, core)}


def _is_quantity_tail(ctx, core):
    """core 的尾端是不是數量尾的一格或一組 → 要去掉的格數(0 = 不是)。"""
    last = core[-1]
    kind = token_kind(last)
    if kind in QUANTITY_TOKEN_KINDS or last == "p:まで" or (kind == "quant" and last.split(":")[1] == "") \
            or ctx.surface(last) in OPERATORS:
        return 1
    if len(core) > 1 and ctx.word(last) in QUANTITY_WORD_TAIL:
        return 1
    for pattern in QUANTITY_PHRASE_TAIL:
        n = len(pattern)
        if len(core) > n and all(
                core[-n + i] == p if p.startswith("p:") else ctx.word(core[-n + i]) == p
                for i, p in enumerate(pattern)):
            return n
    return 0


def _strip_tail(ctx, chunk):
    """去掉段尾的括號註記、助詞與數量尾 → 中心詞所在的前段。"""
    core = list(chunk)
    while core:
        if core[-1] == PAREN_CLOSE and PAREN_OPEN in core:
            core = core[:len(core) - 1 - core[::-1].index(PAREN_OPEN)]   # 括號註記整組去掉
            continue
        if token_kind(core[-1]) == "particle" or core[-1] in SKIP_IN_CORE:
            core.pop()
            continue
        n = _is_quantity_tail(ctx, core)
        if not n:
            break
        del core[-n:]
    return core


def _head_index(ctx, core):
    """中心詞的格:去尾後最後一個不是助詞/讀點的格(名詞格;不是名詞時也取它,類會落 其他 進報告);
    單獨一格的 その 是連體詞,不是中心詞(その3枚)。"""
    for i in range(len(core) - 1, -1, -1):
        if token_kind(core[i]) != "particle" and core[i] not in SKIP_IN_CORE:
            return None if ctx.word(core[i]) == "その" else i
    return None


def _head_text(ctx, core, i):
    token = core[i]
    kind = token_kind(token)
    if kind in ("dem", "elided"):
        return ctx.surface(token.split(":", 2)[2])
    if kind == "quant":
        wid = token.split(":")[1]
        return ctx.surface(wid) if wid else ctx.surface(token)
    if kind != "lex":
        return ctx.surface(token)
    word = ctx.word(token)
    if i > 0:
        prev = core[i - 1]
        if word in METHOD_JOIN_HEADS and token_kind(prev) == "method":
            return ctx.surface(prev) + word
        if word == "名" and (_base(ctx, prev) or "").endswith("カード"):
            return _base(ctx, prev) + "名"          # カード|名、モンスターカード|名
        if word == "方" and ctx.word(prev) == "両":
            return "両方"
    return word


def _demonstrative(ctx, chunk):
    first = chunk[0]
    if token_kind(first) == "dem":
        dem = first.split(":", 2)[1]
        if dem == "その":
            return True
        return (dem == "この" and _base(ctx, first) == "効果" and len(chunk) > 2
                and chunk[1] == "p:の" and ctx.word(chunk[2]) == "対象")
    word = ctx.word(first)
    if word in DEMONSTRATIVE_WORDS:
        return True
    return word == "対象" and len(chunk) > 1 and chunk[1] == "p:の"


def _place_of(ctx, chunk, text, head):
    """段的玩家與區域(沿用區域辨識):最後一個定語述語之後的字面;整段認不出時退到它收在 の 前的最長前段
    (自分の墓地の|攻撃力2500の悪魔族・レベル6モンスター:描述裡有 ・ 時區域辨識認不出整段);中心詞是 数/合計
    時不退(區域修飾的是數);狀態寫法 除外されている… 看整段。"""
    last_predicate = max((i for i, t in enumerate(chunk) if ctx.is_predicate(t)), default=-1)
    tail = chunk[last_predicate + 1:]
    player, zones = places.parse_place("".join(ctx.surface(t) for t in tail))
    if not zones and head not in COUNT_HEADS:
        for i in reversed([i for i, t in enumerate(tail) if t == "p:の"]):
            found = places.parse_place("".join(ctx.surface(t) for t in tail[:i]))
            if found[1]:
                player, zones = found
                break
    if not zones and text.startswith("除外されて"):
        player, zones = places.parse_place(text)
    if player is None and not zones and last_predicate < 0 \
            and _base(ctx, chunk[0]) in PLAYER_WORDS \
            and all(token_kind(t) != "particle" or t == "p:の" for t in chunk):
        player = places.BARE_PLAYERS[_base(ctx, chunk[0])]
    return (PLACE_PLAYER[player] if player else None), list(zones)


# ── 數量(票 04)──
def _quantity(text, kind, number, from_clause=False):
    return {"text": text, "kind": kind, "number": number, "from_clause": from_clause}


def _number(token):
    value = token.split(":", 1)[1]
    return int(value) if value.isdigit() else None


def match_quantity(ctx, run, i):
    """run[i:] 起頭是不是一個數量 → (Quantity, 結束位置) 或 None。數字+量詞(+まで → 上限;+ずつ 一併記進字面)、
    數量約束格 N体以上/以下(下限/上限)、範圍 ２～５体(只記字面、類空)、全て(全部)、任意の数/好きな数(任意)。"""
    token = run[i]
    kind = token_kind(token)
    if kind == "num":
        if i + 1 < len(run) and token_kind(run[i + 1]) == "counter" and run[i + 1][2:] in QUANTITY_COUNTERS:
            text, end, qkind = ctx.surface(token) + run[i + 1][2:], i + 2, Q_FIXED
            if end < len(run) and run[end] == "p:まで":
                text, end, qkind = text + "まで", end + 1, Q_UPPER
            elif end < len(run) and run[end] == "p:ずつ":
                text, end = text + "ずつ", end + 1
            return _quantity(text, qkind, _number(token)), end
        return None
    if kind == "quant":
        _, wid, value, counter, compare = token.split(":", 4)
        if wid == "" and counter in QUANTITY_COUNTERS:
            return _quantity(ctx.surface(token), QUANTITY_COMPARE_KIND.get(compare),
                             int(value) if value.isdigit() else None), i + 1
        return None
    if kind == "range":
        return (_quantity(ctx.surface(token), None, None), i + 1) if token.split(":")[3] in QUANTITY_COUNTERS else None
    if kind == "lex" and ctx.word(token) == "全て":
        return _quantity("全て", Q_ALL, None), i + 1
    for pattern in QUANTITY_ANY_PHRASES:
        n = len(pattern)
        if i + n <= len(run) and all(ctx.surface(run[i + k]) == p for k, p in enumerate(pattern)):
            return _quantity("".join(pattern), Q_ANY, None), i + n
    return None


def _tail_quantity(ctx, chunk, core):
    """段尾(中心詞之後)的數量:去掉括號註記、讀點與無關助詞後,整個尾巴要剛好是一個數量。"""
    tail = []
    depth = 0
    for t in chunk[len(core):]:
        if t == PAREN_OPEN:
            depth += 1
        elif t == PAREN_CLOSE:
            depth = max(0, depth - 1)
        elif depth == 0 and t not in SKIP_IN_CORE and (token_kind(t) != "particle" or t in QUANTITY_TAIL_PARTICLES):
            tail.append(t)
    if not tail:
        return None
    found = match_quantity(ctx, tail, 0)
    return found[0] if found and found[1] == len(tail) else None


def clause_quantity(ctx, tokens, surfaces, end, span, backfilled):
    """受事者字面沒有數量時,子句裡緊接受事者的 を+數量(手札を１枚捨てる)→ Quantity(from_clause),沒有 None。
    を 要在本框的子句範圍內;對象是回填來的時 を 在提供它的前面子句(子句範圍之前)。を 與數量之間可夾
    ランダムに/それぞれ。數量不是定形時往後找引用量(…の数まで、同じ数だけ、…の数の分だけ):只記字面、類空。"""
    if end >= len(tokens) or tokens[end] != "p:を" or not span:
        return None
    if span[0] <= end < span[1]:
        bound = min(span[1], len(tokens))
    elif backfilled and end < span[0]:
        bound = span[0]
    else:
        return None
    j = end + 1
    for prefix in CLAUSE_QUANTITY_SKIP:
        n = len(prefix)
        if j + n <= bound and all(surfaces[j + k] == p for k, p in enumerate(prefix)):
            j += n
    if j >= bound:
        return None
    found = match_quantity(ctx, tokens, j)
    if found:
        return dict(found[0], from_clause=True)
    return _later_quantity(ctx, tokens, surfaces, j, min(bound, j + CLAUSE_QUANTITY_REACH))


def _later_quantity(ctx, tokens, surfaces, start, bound):
    """を 後不是定形數量時往後找:任意の数/好きな数 隔著來源片語(をEXデッキから任意の数だけ)仍是 任意;
    引用量(…の数まで、同じ数(だけ)、…の数の分だけ、…の数だけ)只記 を 後到它為止的字面、類空。沒有 None。"""
    for k in range(start, bound):
        if tokens[k] in CLAUSE_QUANTITY_STOP:
            return None
        found = match_quantity(ctx, tokens, k)
        if found and found[0]["kind"] == Q_ANY:
            return dict(found[0], from_clause=True)
        if _base(ctx, tokens[k]) != "数":
            continue
        rest = tokens[k + 1:bound]
        if rest[:1] == ["p:まで"] or rest[:1] == ["p:だけ"]:
            end = k + 2
        elif rest[:1] == ["p:の"] and len(rest) > 2 and ctx.word(rest[1]) == "分" and rest[2] == "p:だけ":
            end = k + 4
        elif k > start and ctx.word(tokens[k - 1]) == "同じ":
            end = k + 1
        else:
            continue
        return _quantity("".join(surfaces[start:end]), None, None, True)
    return None


# ── 報告 ──
def _fill_state(key):
    def state(frame):
        phrase = (frame.get("phrases") or {}).get(key)
        if phrase:
            return OTHER if any(s["head_kind"] == OTHER for s in phrase["segments"]) else "有值"
        if frame.get(key) and key in (frame.get("inferred") or ()):
            return "推得"                   # 推得的目的沒有片語
        return None
    return state


def _segment_quantities(frame):
    for phrase in (frame.get("phrases") or {}).values():
        for seg in phrase["segments"]:
            if seg.get("quantity"):
                yield seg["quantity"]


def quantity_fill_state(frame):
    """填充率的列「片語·數量」(票 04):任一段的數量取自子句 → 取自子句;否則有數量 → 有值;沒有 None。"""
    found = list(_segment_quantities(frame))
    if not found:
        return None
    return "取自子句" if any(q["from_clause"] for q in found) else "有值"


FILL_RATE_ROWS = [("片語·" + label, _fill_state(key)) for key, label in PHRASE_LABELS]
FILL_RATE_ROWS.append(("片語·數量", quantity_fill_state))

QUANTITY_REFERENCE_LABEL = "引用量(類空)"


def quantity_section(records):
    """「數量各類框數」(票 04):帶各類數量的動作框架數,分 段尾字面/取自子句,另列位置分佈。"""
    counts, positions = Counter(), Counter()
    for rec in records:
        for fr in rec["frames"]:
            seen = set()
            for q in _segment_quantities(fr):
                seen.add((q["kind"] or QUANTITY_REFERENCE_LABEL, q["from_clause"]))
            for kind, from_clause in seen:
                counts[(kind, from_clause)] += 1
            if seen:
                positions[fr["position"]] += 1
    total = sum(positions.values())
    lines = ["帶數量的動作框架 {:,}(代價 {:,}、效果 {:,}、條件 {:,});一框同時帶幾類時各類都計。段尾字面=數量寫在受事者"
             "字面的段尾(モンスター１体、２枚まで、全て);取自子句=受事者字面沒有數量、子句裡緊接受事者的 を+數量"
             "(手札を１枚捨てる、カードを全て破壊する、任意の数);引用量(数まで/同じ数/数の分だけ)只記字面、類空。"
             .format(total, positions["代價"], positions["效果"], positions["條件"]), "",
             "| 數量類 | 段尾字面 | 取自子句 | 合計 |", "|---|---:|---:|---:|"]
    for kind in (*QUANTITY_KINDS, QUANTITY_REFERENCE_LABEL):
        tail, clause = counts[(kind, False)], counts[(kind, True)]
        lines.append("| %s | %s | %s | %s |" % (kind, format(tail, ","), format(clause, ","), format(tail + clause, ",")))
    return lines


def other_heads_section(records):
    """「其他類的中心詞 top 100」:各類段數,與落 其他 的中心詞依段數排序(附出現在哪些欄)。"""
    kinds, others, fields = Counter(), Counter(), defaultdict(Counter)
    labels = dict(PHRASE_LABELS)
    for rec in records:
        for fr in rec["frames"]:
            for key, phrase in (fr.get("phrases") or {}).items():
                for seg in phrase["segments"]:
                    kinds[seg["head_kind"]] += 1
                    if seg["head_kind"] == OTHER:
                        others[seg["head"]] += 1
                        fields[seg["head"]][labels.get(key, key)] += 1
    total = sum(kinds.values()) or 1
    lines = ["片語段 {:,};中心詞類:".format(total) + "、".join(
        "%s %s(%.1f%%)" % (kind, format(kinds[kind], ","), 100.0 * kinds[kind] / total)
        for kind in ("卡", "屬性", "非卡", "指示詞", OTHER)),
        "其他類的中心詞 {:,} 種;下表依段數排序。".format(len(others)), "",
        "| # | 中心詞 | 段數 | 欄 |", "|---:|---|---:|---|"]
    ranked = sorted(others.items(), key=lambda kv: (-kv[1], kv[0] or ""))[:100]
    for n, (head, count) in enumerate(ranked, 1):
        lines.append("| %d | %s | %s | %s |" % (
            n, head if head is not None else "(無)", format(count, ","),
            "、".join("%s %d" % kv for kv in fields[head].most_common())))
    return lines


REPORT_SECTIONS = [("其他類的中心詞 top 100", other_heads_section), ("數量各類框數", quantity_section)]
