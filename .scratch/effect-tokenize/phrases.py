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

修飾語(票 03):中心詞之前的各格依 の 與讀點切段;定語述語的連續格之後也是邊界(特殊召喚した|レベル4以下),
帶格助詞的定語子句把前面的段一起收進去(墓地のモンスターを対象とする|効果)。每段再依 ・/／/並列詞拆成並列項逐項
定類:種族/表示形式(封閉值整詞,含省略寫法 水(族))、屬性(屬性字+属性,光・闇属性 是兩個)、字段(引號段直接接名詞;
接 の 的是卡名、落 其他)、卡片子類型(召喚法格 融合/S/X/P/L/リンク/儀式、省略寫法 通常(モンスター)、直接接名詞的
効果/通常/リバース/…/チューナー/ペンデュラム)、玩家(自分/相手/お互い/持ち主,含 その 綁定的)、區域(區域辨識認得的
一到三格:墓地、自分フィールド、除外状態)、數值(全段只有數值欄位詞/比較詞/數字/連接:每個帶欄位的數字一個,
攻撃力か守備力が2100 共用一個數,レベル4・5 一個、numbers 列兩數,500ダメージ 的裸數欄位空);一項認不出整段落 其他、
只留字面(定語子句、以外/他/元々/残り、このカード、同じ種族…)。
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import places  # noqa: E402
from action_lemmas import MATERIAL_METHODS  # noqa: E402
from closed_values import (HEAD_CARD, HEAD_DEMONSTRATIVE, HEAD_NON_CARD, MODIFIER_KINDS, OTHER,  # noqa: E402
                           PHRASE_KEYS, PLACE_PLAYER, head_kind)
from extract_seed import CLOSED_VALUES  # noqa: E402  封閉值域(種族/卡片子類型/表示形式)的單一來源
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

# ── 修飾語(票 03)的表 ──
MOD_RACE, MOD_ATTRIBUTE, MOD_ARCHETYPE, MOD_SUBTYPE, MOD_NUMERIC, MOD_ZONE, MOD_PLAYER, MOD_POSITION = MODIFIER_KINDS[:8]
MODIFIER_BOUNDARIES = {"p:の", "、"}                           # 修飾語段的邊界(規格:依 の 與讀點切)
ITEM_SEPARATORS = {"・", "／"}                                   # 一段裡並列項的分隔(光・闇属性、融合・S・X)
CASE_PARTICLES = {"p:を", "p:が", "p:に", "p:へ", "p:から", "p:で", "p:と", "p:は", "p:も", "p:より", "p:として"}
ADNOMINAL_COMPARE = {"同じ", "異なる", "違う"}                   # 連體的比較詞:後面的名詞還是同一個修飾語(同じ種族)
NUMERIC_FIELDS = frozenset({"攻撃力", "守備力", "レベル", "ランク", "リンク", "Pスケール", "LP"})
COMPARATORS = frozenset({"以上", "以下", "未満"})
NUMERIC_CONNECTORS = {"・", "／", "p:か", "p:や", "p:または", "p:と", "p:が", "p:で", "p:は", "p:も"}
NUMBER_TOKEN_KINDS = {"num", "quant", "range"}
SUMMON_KIND_PREFIXES = {"通常", "反転", "特殊", "アドバンス"}      # m: 格裡的召喚種類(只出現在 召喚 前),不是卡片子類型
# 指示詞綁住的召喚法名(その融合モンスター 的 融合 是詞典格,不是 m: 格):素材法 + 儀式/P/リンク
SUMMON_METHOD_WORDS = frozenset(MATERIAL_METHODS) | {"儀式", "P", "リンク"}
# 玩家修飾語:自分/相手/お互い 之外,區域辨識當玩家前綴的 持ち主(相對玩家);自身の 指卡片自己,不算
MODIFIER_PLAYER_WORDS = frozenset(prefix[:-1] for prefix, _ in places.PLAYER_PREFIXES
                                  if prefix.endswith("の") and not any(c in prefix[:-1] for c in "か・の")
                                  and "または" not in prefix) - {"自身"}
# 封閉值 → 修飾語類(值從 extract_seed.CLOSED_VALUES 取,不另抄):種族、表示形式整詞;卡片子類型的整詞只在
# 省略寫法(通常(モンスター)・効果モンスター)裡當修飾語,詞典一格的 効果モンスター 本身是中心詞或 の 前的名詞
_CLOSED_MODIFIER = {value: kind for kind, values in (
    (MOD_RACE, CLOSED_VALUES["種族"]), (MOD_SUBTYPE, CLOSED_VALUES["卡片子類型"]),
    (MOD_POSITION, CLOSED_VALUES["表示形式"])) for value in values}
# 子類型前綴(効果/通常/リバース/デュアル/スピリット/ユニオン/トゥーン,從 卡片子類型 的 〜モンスター 值去尾取)
# 與規格另列的 チューナー/ペンデュラム:分詞裡是單獨一格、直接接中心詞(チューナーモンスター、ペンデュラムモンスター)
SUBTYPE_PREFIXES = frozenset({v[:-len("モンスター")] for v in CLOSED_VALUES["卡片子類型"] if v.endswith("モンスター")}
                             | {"チューナー", "ペンデュラム"})


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
        run = locate(ctx, tokens, surfaces, raw.get(key) or text, frame.get("span"))
        phrases[key] = {"text": text,
                        "segments": [segment(ctx, chunk) for chunk in split(ctx, run)]}
    if phrases:
        frame["phrases"] = phrases


def locate(ctx, tokens, surfaces, literal, span):
    """字面 → 句子詞序列裡字面相連的一段(先子句範圍、再整句);對不回時重新分詞。"""
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
                    return tokens[i:j + 1]
                if not literal.startswith(acc):
                    break
    return ctx.tokenize(literal)


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
            "player": player, "zones": zones,
            "modifiers": modifiers(ctx, core, head_at, head) if head_at is not None else []}


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


# ── 修飾語(票 03)──
def modifiers(ctx, core, head_at, head):
    """中心詞之前的各格 → [Modifier]:依 の 與讀點切段(定語述語的連續格之後也是一個邊界:特殊召喚した|レベル4以下;
    帶格助詞的定語子句把前面的段一起收進去:墓地のモンスターを対象とする),每段再依 ・/／/並列詞拆成並列項,
    逐項定類;一項認不出時整段落 其他、只留字面。數值段(欄位+比較+數字)另帶 field/compare/number。"""
    pre = core[:_head_start(ctx, core, head_at, head)]
    out = []
    for lo, hi in _modifier_chunks(ctx, pre):
        adjacent = hi == len(pre) or pre[hi] not in MODIFIER_BOUNDARIES
        out.extend(_classify_chunk(ctx, pre[lo:hi], adjacent))
    return out


def _head_start(ctx, core, head_at, head):
    """合記的中心詞(特殊|召喚、カード|名、両|方)佔兩格:修飾語到前一格為止。"""
    if head_at > 0 and token_kind(core[head_at]) == "lex" and head != ctx.word(core[head_at]):
        return head_at - 1
    return head_at


def _modifier_chunks(ctx, pre):
    """pre 的 [lo, hi) 段清單:の/、 是邊界(本身不屬任何段);定語述語的連續格(した、された、持つ)之後也是邊界,
    連體比較詞(同じ/異なる)例外;帶格助詞(を/が/に/で…)的述語段把它前面(上一個述語段之後)的段併成一段。"""
    chunks, start, i = [], 0, 0
    while i < len(pre):
        if pre[i] in MODIFIER_BOUNDARIES:
            if i > start:
                chunks.append([start, i])
            start = i = i + 1
            continue
        if ctx.is_predicate(pre[i]) and ctx.word(pre[i]) not in ADNOMINAL_COMPARE:
            j = i
            while j < len(pre) and ctx.is_predicate(pre[j]):
                j += 1
            chunks.append([start, j])
            start = i = j
            continue
        i += 1
    if start < len(pre):
        chunks.append([start, len(pre)])
    merged, since = [], 0
    for lo, hi in chunks:
        toks = pre[lo:hi]
        if any(ctx.is_predicate(t) for t in toks):
            if any(t in CASE_PARTICLES for t in toks) and len(merged) > since:
                lo = merged[since][0]
                del merged[since:]
            merged.append([lo, hi])
            since = len(merged)
        else:
            merged.append([lo, hi])
    return merged


def _modifier(text, kind):
    return {"text": text, "kind": kind}


def _classify_chunk(ctx, toks, adjacent):
    while toks and toks[-1] in ITEM_SEPARATORS:
        toks = toks[:-1]                                 # 魔法(カード)・|罠カード:緊接中心詞的分隔不是修飾語的字面
    if not toks:
        return []
    text = "".join(ctx.surface(t) for t in toks)
    if any(ctx.is_predicate(t) for t in toks):
        return [_modifier(text, OTHER)]              # 定語子句:只留字面
    numeric = _numeric_items(ctx, toks)
    if numeric is not None:
        return numeric
    items = _items(ctx, toks, adjacent)
    return items if items is not None else [_modifier(text, OTHER)]


def _numeric_items(ctx, toks):
    """數值段:全段只有數值欄位詞(攻撃力/守備力/レベル/ランク/リンク/Pスケール/LP)、比較詞、數字與連接(・／か が で…)
    → 每個帶欄位的數字一個 Modifier(攻撃力1000／守備力1000 兩個;攻撃力か守備力が2100 一個、欄位 攻撃力か守備力;
    レベル4・5 一個、number 空、numbers [4, 5]);不是數值段回 None。"""
    if not any(token_kind(t) in NUMBER_TOKEN_KINDS for t in toks):
        return None
    for t in toks:
        kind = token_kind(t)
        if kind == "lex":
            if ctx.word(t) not in NUMERIC_FIELDS and ctx.word(t) not in COMPARATORS:
                return None
        elif kind == "quant":
            wid, _, counter, _ = t.split(":", 4)[1:]
            if counter or (wid and ctx.surface(wid) not in NUMERIC_FIELDS):
                return None
        elif kind == "range":
            if t.split(":", 3)[3]:
                return None                           # 量詞的範圍(2～5体)是數量,不是數值
        elif kind != "num" and t not in NUMERIC_CONNECTORS:
            return None
    spans, lo = [], 0
    for i, t in enumerate(toks):
        if t in NUMERIC_CONNECTORS:
            if i > lo:
                spans.append([lo, i])
            lo = i + 1
    if lo < len(toks):
        spans.append([lo, len(toks)])
    # 沒有數字的項併進下一項(攻撃力|か|守備力が2100);沒有欄位的項併進上一項(レベル4|・|5)
    k = 0
    while k < len(spans) - 1:
        if not any(token_kind(t) in NUMBER_TOKEN_KINDS for t in toks[spans[k][0]:spans[k][1]]):
            spans[k + 1][0] = spans[k][0]
            del spans[k]
        else:
            k += 1
    k = 1
    while k < len(spans):
        if not any(_numeric_field(ctx, t) for t in toks[spans[k][0]:spans[k][1]]):
            spans[k - 1][1] = spans[k][1]
            del spans[k]
        else:
            k += 1
    return [_numeric_modifier(ctx, toks[lo:hi]) for lo, hi in spans]


def _numeric_field(ctx, token):
    kind = token_kind(token)
    if kind == "lex" and ctx.word(token) in NUMERIC_FIELDS:
        return ctx.word(token)
    if kind == "quant":
        wid = token.split(":")[1]
        return ctx.surface(wid) if wid else None
    return None


def _numeric_modifier(ctx, toks):
    field_at = [i for i, t in enumerate(toks) if _numeric_field(ctx, t)]
    pieces = []
    for i in range(field_at[0], field_at[-1] + 1) if field_at else ():
        pieces.append(_numeric_field(ctx, toks[i]) or ctx.surface(toks[i]))
    compare, numbers = None, []
    for t in toks:
        kind = token_kind(t)
        if kind == "num":
            numbers.append(t.split(":", 1)[1])
        elif kind == "quant":
            _, _, val, _, cmp_word = t.split(":", 4)
            numbers.append(val)
            compare = cmp_word or compare
        elif kind == "range":
            _, low, high, _ = t.split(":", 3)
            numbers += [low, high]
        elif kind == "lex" and ctx.word(t) in COMPARATORS:
            compare = ctx.word(t)
    numbers = [int(v) for v in numbers if v.isdigit()]        # 攻撃力？ 的 ？ 不是數
    out = {"text": "".join(ctx.surface(t) for t in toks), "kind": MOD_NUMERIC,
           "field": "".join(pieces) or None, "compare": compare,
           "number": numbers[0] if len(numbers) == 1 else None}
    if len(numbers) > 1:
        out["numbers"] = numbers
    return out


def _items(ctx, toks, adjacent):
    """一段的並列項逐項定類(・/／/並列詞是分隔);某一項認不出 → None(整段落 其他)。"""
    out, i, n = [], 0, len(toks)

    def next_is_noun(j):
        return (j + 1 < n and token_kind(toks[j + 1]) not in ("particle", "punct")) or (j + 1 == n and adjacent)

    while i < n:
        t = toks[i]
        kind = token_kind(t)
        if t in ITEM_SEPARATORS or ctx.coordinates(toks, i):
            i += 1
            continue
        if kind == "attr":                                     # 闇属性、光(・闇属性)
            j = i + 1
            if j < n and ctx.word(toks[j]) == "属性":
                j += 1
            out.append(_modifier("".join(ctx.surface(u) for u in toks[i:j]), MOD_ATTRIBUTE))
            i = j
            continue
        surface = ctx.surface(t)
        if kind == "name":                                     # 「DD」モンスター 是字段;「青眼の白龍」の攻撃力 是卡名
            out.append(_modifier(surface, MOD_ARCHETYPE if next_is_noun(i) else OTHER))
        elif kind == "method":
            if surface in SUMMON_KIND_PREFIXES:
                return None
            out.append(_modifier(surface, MOD_SUBTYPE))
        elif kind == "elided":                                 # 通常(モンスター)・効果モンスター、自分(フィールド)・相手フィールド
            target = ctx.surface(t.split(":", 2)[2])
            closed = _CLOSED_MODIFIER.get(target)
            if closed:
                out.append(_modifier(surface, closed))
            elif places.parse_place(target)[1]:
                out.append(_modifier(surface, MOD_ZONE))
            else:
                return None
        elif kind in ("lex", "oov"):
            word = ctx.word(t) or surface
            closed = _CLOSED_MODIFIER.get(word)
            if i == 0 and word in DEMONSTRATIVE_WORDS:
                i += 1                                         # その特殊召喚:段首單獨一格的 その 是段的指示詞旗標,不是修飾語
                continue
            if closed and closed != MOD_SUBTYPE:
                out.append(_modifier(surface, closed))
            elif word in SUBTYPE_PREFIXES and next_is_noun(i):
                out.append(_modifier(surface, MOD_SUBTYPE))
            elif word in PLAYER_WORDS or word in MODIFIER_PLAYER_WORDS:
                out.append(_modifier(surface, MOD_PLAYER))
            else:
                j = _zone_run(ctx, toks, i)
                if j is None:
                    return None
                out.append(_modifier("".join(ctx.surface(u) for u in toks[i:j]), MOD_ZONE))
                i = j
                continue
        elif kind == "dem":                                    # その自分/その表側表示/その融合モンスター:指示詞綁在詞上
            base = ctx.surface(t.split(":", 2)[2])
            closed = _CLOSED_MODIFIER.get(base)
            if closed and closed != MOD_SUBTYPE:
                out.append(_modifier(surface, closed))
            elif (base in SUBTYPE_PREFIXES or base in SUMMON_METHOD_WORDS) and next_is_noun(i):
                out.append(_modifier(surface, MOD_SUBTYPE))
            elif base in PLAYER_WORDS or base in MODIFIER_PLAYER_WORDS:
                out.append(_modifier(surface, MOD_PLAYER))
            elif places.parse_place(base)[1]:
                out.append(_modifier(surface, MOD_ZONE))
            else:
                return None
        else:
            return None
        i += 1
    return out


def _zone_run(ctx, toks, i):
    """從 i 起的區域字面:一格(墓地)或分詞拆成兩三格的(除外|状態),長的先試,交給區域辨識認得就回結尾位置。"""
    for j in range(min(i + 3, len(toks)), i, -1):
        if all(token_kind(u) == "lex" for u in toks[i:j])                 and places.parse_place("".join(ctx.surface(u) for u in toks[i:j]))[1]:
            return j
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


FILL_RATE_ROWS = [("片語·" + label, _fill_state(key)) for key, label in PHRASE_LABELS]


def _modifier_state(kind):
    """票 03:框架的片語(四欄合計)有沒有這一類的修飾語 → 有值(其他類記 其他);沒有時 None。"""
    def state(frame):
        for phrase in (frame.get("phrases") or {}).values():
            for seg in phrase["segments"]:
                if any(m["kind"] == kind for m in seg.get("modifiers") or ()):
                    return OTHER if kind == OTHER else "有值"
        return None
    return state


def _modifiers_state(frame):
    """票 03:框架有任何修飾語 → 有值;只要有一個落 其他 → 其他;一個都沒有 → None。"""
    kinds = {m["kind"] for phrase in (frame.get("phrases") or {}).values()
             for seg in phrase["segments"] for m in seg.get("modifiers") or ()}
    if not kinds:
        return None
    return OTHER if OTHER in kinds else "有值"


FILL_RATE_ROWS.append(("修飾語", _modifiers_state))
FILL_RATE_ROWS += [("修飾語·" + kind, _modifier_state(kind)) for kind in MODIFIER_KINDS]


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


def other_modifiers_section(records):
    """「其他類的修飾語 top 100」:各類修飾語數,與落 其他 的修飾語字面依次數排序(附出現在哪些欄)。"""
    kinds, others, fields = Counter(), Counter(), defaultdict(Counter)
    labels = dict(PHRASE_LABELS)
    for rec in records:
        for fr in rec["frames"]:
            for key, phrase in (fr.get("phrases") or {}).items():
                for seg in phrase["segments"]:
                    for mod in seg.get("modifiers") or ():
                        kinds[mod["kind"]] += 1
                        if mod["kind"] == OTHER:
                            others[mod["text"]] += 1
                            fields[mod["text"]][labels.get(key, key)] += 1
    total = sum(kinds.values()) or 1
    lines = ["修飾語 {:,};修飾語類:".format(total) + "、".join(
        "%s %s(%.1f%%)" % (kind, format(kinds[kind], ","), 100.0 * kinds[kind] / total)
        for kind in MODIFIER_KINDS),
        "其他類的修飾語 {:,} 種;下表依次數排序。".format(len(others)), "",
        "| # | 修飾語 | 次數 | 欄 |", "|---:|---|---:|---|"]
    ranked = sorted(others.items(), key=lambda kv: (-kv[1], kv[0]))[:100]
    for n, (text, count) in enumerate(ranked, 1):
        lines.append("| %d | %s | %s | %s |" % (
            n, text, format(count, ","), "、".join("%s %d" % kv for kv in fields[text].most_common())))
    return lines


REPORT_SECTIONS = [("其他類的中心詞 top 100", other_heads_section),
                   ("其他類的修飾語 top 100", other_modifiers_section)]
