# -*- coding: utf-8 -*-
"""論元片語(frame-args-v4 票 02 段/中心詞/中心詞類/玩家/區域/指示詞、票 03 修飾語、票 04 數量)。

mark(ctx, tokens, frame):替動作框架加 frame["phrases"] = {"object"|"topic"|"subject"|"goal": Phrase},
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

指示詞:段以 その/それ/それら/対象の/この効果の対象 起頭(この 不算);指示詞綁的格之後先有格助詞(と/が/は/より/
を/で/も/として;に/へ/から 只在綁的格不是區域也不是 する名詞時算)再有定語述語或比較詞時,指示詞綁在定語子句裡
的另一張卡(そのモンスターと同じ種族のモンスター、そのカード名が記されたモンスター、そのモンスターよりランクが
２つ高いXモンスター),旗標假(2026-11-01 站主裁定,語意判定取代段首字面);その破壊されたモンスター、その無効にした
カード、その手札に加えたカード 仍為真。玩家與區域:段裡最後一個定語述語之後
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
import re
from collections import Counter, defaultdict

import places
from action_lemmas import MATERIAL_METHODS
from closed_values import (HEAD_ATTRIBUTE, HEAD_CARD, HEAD_DEMONSTRATIVE, HEAD_DISPLAY_FORM, HEAD_KINDS, HEAD_NON_CARD,
                           HEAD_PLAYER, HEAD_POSITION, MODIFIER_KINDS, OTHER, PHRASE_KEYS, PLACE_PLAYER, QUANTITY_KINDS)
from constraints import POS_COND, POS_COST, POS_EFFECT
from extract_seed import CLOSED_VALUES  # 封閉值域(種族/卡片子類型/表示形式)的單一來源
from report import token_kind

PHRASE_LABELS = (("object", "對象"), ("topic", "主題"), ("subject", "主語"), ("goal", "目的"))
# 數量尾的格(票 04 在這裡接手數量本身)
QUANTITY_TOKEN_KINDS = {"num", "counter", "range"}
QUANTITY_WORD_TAIL = {"全て"}                             # 段尾單格的量化詞
PLAYER_WORDS = frozenset(places.BARE_PLAYERS)             # 自分/相手/お互い(區域辨識的裸玩家詞是單一來源)
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
                        ("好き", "な", "数"))                         # 任意の数/任意の枚数/好きな数(字面比;段尾與 を 後共用)
QUANTITY_TAIL_PARTICLES = {"p:まで", "p:の", "p:ずつ"}                  # 段尾數量裡會出現的助詞
CLAUSE_QUANTITY_SKIP = (("ランダム", "に"), ("それぞれ",))             # を 與數量之間可夾的副詞(不進字面)
CLAUSE_QUANTITY_STOP = {"。", "、", "p:を"}                            # 引用量往後找的邊界
CLAUSE_QUANTITY_REACH = 12                                             # 引用量最多往後看幾格
CLAUSE_QUANTITY_PARTICLES = {"object": "p:を", "subject": "p:が"}       # 哪些欄從子句取數量、接在哪個格之後
# 受事者之前的引用量(2026-11-01 裁定):…の数まで/数だけ/数の分だけ/枚数まで 的字面從 数 往前收到讀點/主題的 は 為止;
# 其他助詞只在它後面(数 之前)還有定語述語時才收(この効果で特殊召喚したモンスターの数まで 的 で 屬定語子句;
# 手札から|相手フィールドのモンスターの数まで 的 から 屬主句,不收)
REFERENCE_PHRASE_STOP = {"。", "、", "p:は"}
# 主語位 が 後的數量(「DD」カードが２枚存在する;2026-11-01 裁定):數量後接這些助詞的是值(X素材が３つになった),不收
SUBJECT_QUANTITY_NOT_BEFORE = {"p:に", "p:を", "p:と", "p:へ"}
ADNOMINAL_QUANTITY = {"全て": Q_ALL, "任意": Q_ANY}   # 全ての/任意の 連體寫法(2026-11-01 裁定):該段的數量,修飾語不留

# ── 修飾語(票 03)的表 ──
MOD_RACE, MOD_ATTRIBUTE, MOD_ARCHETYPE, MOD_SUBTYPE, MOD_NUMERIC, MOD_ZONE, MOD_PLAYER, MOD_POSITION = MODIFIER_KINDS[:8]
MODIFIER_BOUNDARIES = {"p:の", "、"}                           # 修飾語段的邊界(規格:依 の 與讀點切)
ITEM_SEPARATORS = {"・", "／"}                                   # 一段裡並列項的分隔(光・闇属性、融合・S・X)
CASE_PARTICLES = {"p:を", "p:が", "p:に", "p:へ", "p:から", "p:で", "p:と", "p:は", "p:も", "p:より", "p:として"}
# 指示詞綁的格之後、把它關進定語子句的格助詞(2026-11-01 裁定):方向格 に/へ/から 只在綁的格是可移動的東西
# (不是區域 その手札に加えた、不是 する名詞 その無効にした)時算
DEMONSTRATIVE_CLAUSE_PARTICLES = CASE_PARTICLES - {"p:に", "p:へ", "p:から"}
DEMONSTRATIVE_DIRECTION_PARTICLES = {"p:に", "p:へ", "p:から"}
ADNOMINAL_COMPARE = {"同じ", "異なる", "違う"}                   # 連體的比較詞:後面的名詞還是同一個修飾語(同じ種族);
#                                                                 前面有格助詞(数値が同じ|機械族)時是子句的述語、之後是邊界
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

# ── 中心詞類(票 02)的判定表(值域在 closed_values.HEAD_KINDS) ──
# 規格 Implementation Decisions 的中心詞類段;依中心詞字面比,表外落 其他:
# 卡——モンスター/カード/トークン/チューナー/素材、卡名「…」、卡種+カード 與 子類型+モンスター 這類封閉值域
# 複合詞(以尾字比)、受事者本身是區域(手札、デッキ、墓地、自分フィールド…,交給 places 認);
# 屬性——數值與性質欄位,與跟主人走的事件類(効果/発動/攻撃/各召喚);非卡——傷害/LP/指示物/數/擲幣/
# 戰鬥/ゾーン 與純數值;指示詞——沒有名詞中心的段(それ/それら/いずれか/内/対象/残り,與只剩數量的段
# 「1枚」「2体以上」:名詞省略了,指的是上文的卡;量詞就是 QUANTITY_COUNTERS 那一張表);
# 玩家/位置/表示形式(2026-11-01 站主裁定加)——玩家詞(區域辨識的裸玩家詞 自分/相手/お互い 加 プレイヤー/
# コントローラー/持ち主:ダメージを与える 的對象、主題/主語的執行者)、牌組位置(デッキの一番下に戻す 的
# 一番上/一番下/上/下)、表示形式的值(裏側守備表示にする 的目的;分詞封閉值域 表示形式 七值——表示形式 這個詞
# 本身仍是 屬性)
_HEAD_CARD_WORDS = frozenset({"モンスター", "カード", "トークン", "チューナー", "素材", "魔法", "罠"})
_HEAD_CARD_SUFFIXES = ("カード", "モンスター", "素材", "トークン", "魔法", "罠")
_HEAD_ATTRIBUTE_WORDS = frozenset({
    "攻撃力", "守備力", "レベル", "ランク", "Pスケール", "属性", "種族", "カード名", "表示形式", "コントロール",
    "位置", "効果", "発動", "攻撃", "召喚"})
_HEAD_ATTRIBUTE_SUFFIXES = ("召喚", "カード名")
_HEAD_NON_CARD_WORDS = frozenset({"ダメージ", "LP", "カウンター", "数", "コイントス", "戦闘", "ゾーン"})
_HEAD_NON_CARD_SUFFIXES = ("ダメージ", "カウンター")
_HEAD_DEMONSTRATIVE_WORDS = frozenset({"それ", "それら", "いずれか", "内", "対象", "残り", "両方", "どちらか"})
_HEAD_PLAYER_WORDS = PLAYER_WORDS | {"プレイヤー", "コントローラー", "持ち主"}
# 票 02 的四類:「・」切段與從修飾語補玩家/區域的判準照舊只看這四類,2026-11-01 加的 玩家/位置/表示形式 在這兩處
# 與 其他 同待遇(自分・相手 不切成兩段;自分または相手、対象の自分のモンスターの上 不從前面的玩家修飾語補玩家)
CORE_HEAD_KINDS = frozenset((HEAD_CARD, HEAD_ATTRIBUTE, HEAD_NON_CARD, HEAD_DEMONSTRATIVE))
_HEAD_POSITION_WORDS = frozenset({"一番上", "一番下", "上", "下"})
_HEAD_DISPLAY_FORMS = frozenset(CLOSED_VALUES["表示形式"])
_NUMERIC = re.compile(r"[0-9]+")
_QUANTITY_ONLY = re.compile(r"[0-9]+(?:%s)(?:まで|以上|以下|未満)?" % "|".join(sorted(QUANTITY_COUNTERS)))


def head_kind(head):
    """中心詞字面 → 中心詞類(HEAD_KINDS 之一);None 與表外的落 其他。"""
    if not head:
        return OTHER
    if head.startswith("「") and head.endswith("」"):
        return HEAD_CARD
    if head in _HEAD_CARD_WORDS or head.endswith(_HEAD_CARD_SUFFIXES):
        return HEAD_CARD
    if head in _HEAD_ATTRIBUTE_WORDS or head.endswith(_HEAD_ATTRIBUTE_SUFFIXES):
        return HEAD_ATTRIBUTE
    if head in _HEAD_NON_CARD_WORDS or head.endswith(_HEAD_NON_CARD_SUFFIXES) or _NUMERIC.fullmatch(head):
        return HEAD_NON_CARD
    if head in _HEAD_DEMONSTRATIVE_WORDS or _QUANTITY_ONLY.fullmatch(head):
        return HEAD_DEMONSTRATIVE
    if head in _HEAD_PLAYER_WORDS:
        return HEAD_PLAYER
    if head in _HEAD_POSITION_WORDS:
        return HEAD_POSITION
    if head in _HEAD_DISPLAY_FORMS:
        return HEAD_DISPLAY_FORM
    if places.parse_place(head)[1]:
        return HEAD_CARD
    return OTHER


def mark(ctx, tokens, frame):
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
        if found and "、" not in (raw.get(key) or text):
            run = [t for t in run if t != "、"]
        segments = [segment(ctx, chunk) for chunk in split(ctx, run)]
        if key in CLAUSE_QUANTITY_PARTICLES and found and not any(seg["quantity"] for seg in segments):
            quantity = clause_quantity(ctx, tokens, surfaces, found, span, key,
                                       key in (frame.get("backfill") or ()))
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
                if surfaces[j] == "、" and not literal.startswith(acc + "、"):
                    continue                  # 上游去掉的讀點(存在する、このカード)跳過(票 10)
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
    if run[:k].count(PAREN_OPEN) > run[:k].count(PAREN_CLOSE):
        return False                      # 種類（モンスター・魔法・罠）が異なる:括號註記裡的並列(票 10)
    if not is_dot and _inside_attributive_clause(ctx, run, k):
        return False                      # 「A」と「B」となるモンスター:並列詞在定語子句裡面(票 10)
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
        if kind not in CORE_HEAD_KINDS:
            return False                  # 魔法使い族・ドラゴン族モンスター、自分・相手:修飾語/玩家的並列
    elif kind == HEAD_CARD:
        return True                       # このカードと…のモンスター:兩個受事者
    rest = run[k + 1:]
    # 「・」串(魔法・罠・モンスターの効果)看整串之後有沒有 の/が,不是下一個 ・ 之前(票 10 v4-round1)
    stop = next((m for m in range(len(rest)) if (rest[m] == "・" and not is_dot) or ctx.coordinates(rest, m)),
                len(rest))
    return not any(u in LINK_PARTICLES for u in rest[:stop])


def _inside_attributive_clause(ctx, run, k):
    """並列詞 run[k] 在定語子句裡面、不是受事者的並列(票 10 v4-round1):到下一個並列詞為止,
    (a)並列詞自己是 と 而後面有比較詞(そのモンスターと元々のカード名が異なる|「フォトン」モンスター:と 是比較的對象);
    (b)後面有一個不是並列的 と(と+は/同じ/なる:「B」と|なる、カードとは種類が異なる、モンスターゾーンと同じ)再接述語、
    述語後還接名詞。「X」またはそのカード名が記されたカード 這種各自帶定語的替代項沒有這樣的 と,照切。"""
    rest = run[k + 1:]
    stop = next((m for m in range(len(rest)) if ctx.coordinates(rest, m)), len(rest))
    rest = rest[:stop]
    if run[k] == "p:と" and any(ctx.word(t) in ADNOMINAL_COMPARE for t in rest):
        return True
    bound = next((m for m in range(len(rest)) if rest[m] == "p:と" and not ctx.coordinates(rest, m)), None)
    if bound is None:
        return False
    for m in range(bound + 1, len(rest)):
        if ctx.is_predicate(rest[m]) or ctx.word(rest[m]) in ADNOMINAL_COMPARE:
            after = next((u for u in rest[m + 1:] if u != "、" and not ctx.is_predicate(u)), None)
            return after is not None and token_kind(after) != "particle"
    return False


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
    mods = modifiers(ctx, core, head_at, head) if head_at is not None else []
    player, zones = _place_of(ctx, chunk, text, head, kind, mods, len(core))
    quantity = _tail_quantity(ctx, chunk, core)
    if quantity is None and head_at is not None:
        quantity = _adnominal_quantity(ctx, core, head_at, mods)
    return {"text": text, "head": head, "head_kind": kind, "demonstrative": _demonstrative(ctx, chunk),
            "player": player, "zones": zones, "modifiers": mods, "quantity": quantity}


def _adnominal_quantity(ctx, core, head_at, mods):
    """中心詞前的 全ての/任意の(2026-11-01 裁定)→ 該段的數量(全部/任意,字面 全ての/任意の,不是取自子句),
    對應的 其他 類修飾語拿掉;段尾已有數量時不動(呼叫端)。沒有 None。"""
    for i in range(head_at):
        word = ctx.word(core[i])
        if word in ADNOMINAL_QUANTITY and core[i + 1] == "p:の":
            surface = ctx.surface(core[i])
            mod = next((m for m in mods if m["text"] == surface and m["kind"] == OTHER), None)
            if mod is None:
                continue
            mods.remove(mod)
            return _quantity(surface + "の", ADNOMINAL_QUANTITY[word], None)
    return None


def _is_quantity_tail(ctx, core):
    """core 的尾端是不是數量尾的一格或一組 → 要去掉的格數(0 = 不是)。"""
    last = core[-1]
    kind = token_kind(last)
    if kind in QUANTITY_TOKEN_KINDS or last == "p:まで" or (kind == "quant" and last.split(":")[1] == "") \
            or ctx.surface(last) in OPERATORS:
        return 1
    if len(core) > 1 and ctx.word(last) in QUANTITY_WORD_TAIL:
        return 1
    for pattern in QUANTITY_ANY_PHRASES:
        n = len(pattern)
        if len(core) > n and all(ctx.surface(core[-n + i]) == p for i, p in enumerate(pattern)):
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
    """段的指示詞旗標:段首是 その/それ/それら/対象の/この効果の対象,且指示詞綁的格沒被關進定語子句
    (2026-11-01 裁定的語意判定,見 _bound_in_relative_clause)。"""
    first = chunk[0]
    if token_kind(first) == "dem":
        dem = first.split(":", 2)[1]
        if dem == "その":
            bound_at, rest_at = 0, 1
        elif dem == "この" and _base(ctx, first) == "効果" and len(chunk) > 2 \
                and chunk[1] == "p:の" and ctx.word(chunk[2]) == "対象":
            bound_at, rest_at = 2, 3
        else:
            return False
    else:
        word = ctx.word(first)
        if word in DEMONSTRATIVE_WORDS:
            bound_at, rest_at = (1, 2) if word == "その" and len(chunk) > 1 else (0, 1)   # その3枚、その「X」
        elif word == "対象" and len(chunk) > 1 and chunk[1] == "p:の":
            bound_at, rest_at = 0, 2
        else:
            return False
    return not _bound_in_relative_clause(ctx, chunk, bound_at, rest_at)


def _bound_in_relative_clause(ctx, chunk, bound_at, rest_at):
    """指示詞綁的格(chunk[bound_at])之後先有格助詞、再有定語述語或比較詞:指示詞說的是定語子句裡的另一張卡
    (そのモンスターと同じ種族の|モンスター、そのカード名が記された|モンスター、そのモンスターより…高い|Xモンスター),
    不是這一段的中心詞。方向格 に/へ/から 只在綁的格是可移動的東西時算:區域(その手札に加えたカード)與
    する名詞(その無効にしたカード)的 に 是述語自己的格,指示詞仍綁中心詞。"""
    bound = _head_text(ctx, chunk, bound_at)
    movable = head_kind(bound) != OTHER and not places.parse_place(bound)[1]
    for i in range(rest_at, len(chunk)):
        t = chunk[i]
        if t in DEMONSTRATIVE_CLAUSE_PARTICLES or (movable and t in DEMONSTRATIVE_DIRECTION_PARTICLES):
            return any(ctx.is_predicate(u) or ctx.word(u) in ADNOMINAL_COMPARE for u in chunk[i + 1:])
    return False


def _place_of(ctx, chunk, text, head, kind, mods, core_len):
    """段的玩家與區域(沿用區域辨識):最後一個定語述語之後的字面;整段認不出時退到它收在 の 前的最長前段
    (自分の墓地の|攻撃力2500の悪魔族・レベル6モンスター:描述裡有 ・ 時區域辨識認不出整段);中心詞是 数/合計
    時不退(區域修飾的是數);狀態寫法 除外されている… 看整段。都認不出時再從玩家/區域類的修飾語補
    (相手フィールドの特殊召喚されたモンスター:區域在定語述語之前、但子句沒有自己的格,修飾的是中心詞;票 10)。"""
    last_predicate = max((i for i, t in enumerate(chunk) if ctx.is_predicate(t)), default=-1)
    tail = chunk[last_predicate + 1:max(core_len, last_predicate + 1)]   # 數量尾不擋區域辨識(手札1枚;票 10)
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
    if player is None and not zones and head not in COUNT_HEADS and kind in CORE_HEAD_KINDS:
        texts = [m["text"] for m in mods if m["kind"] in (MOD_PLAYER, MOD_ZONE)]
        if texts and texts[0] in text and texts[-1] in text:
            lo, hi = text.index(texts[0]), text.index(texts[-1]) + len(texts[-1])
            if lo < hi:
                player, zones = places.parse_place(text[lo:hi])     # 自分及び相手フィールド:照原文的字面連起來
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


def clause_quantity(ctx, tokens, surfaces, found, span, key, backfilled):
    """受事者字面沒有數量時,子句裡緊接受事者的 を+數量(手札を１枚捨てる)→ Quantity(from_clause),沒有 None。
    を 要在本框的子句範圍內;對象是回填來的時 を 在提供它的前面子句(子句範圍之前)。を 與數量之間可夾
    ランダムに/それぞれ。數量不是定形時往後找引用量(…の数まで、同じ数だけ、…の数の分だけ):只記字面、類空;
    を 後都沒有時再找受事者**之前**、同一子句裡的引用量(相手フィールドのモンスターの数まで、手札から…を特殊召喚する;
    2026-11-01 裁定)。主語位(「DD」カードが２枚存在する)只收 が 後緊接的定形數量,數量後接 に/を/と/へ 的是值,不收。"""
    end = found[1]
    if end >= len(tokens) or tokens[end] != CLAUSE_QUANTITY_PARTICLES[key] or not span:
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
    matched = match_quantity(ctx, tokens, j)
    if key == "subject":
        if matched and not (matched[1] < bound and tokens[matched[1]] in SUBJECT_QUANTITY_NOT_BEFORE):
            return dict(matched[0], from_clause=True)
        return None
    if matched:
        return dict(matched[0], from_clause=True)
    later = _later_quantity(ctx, tokens, surfaces, j, min(bound, j + CLAUSE_QUANTITY_REACH))
    if later or found[0] < span[0]:
        return later
    return _earlier_quantity(ctx, tokens, surfaces, span[0], found[0])


def _reference_end(ctx, tokens, k, bound):
    """tokens[k] 是 数 時引用量的結束位置(数まで/数だけ/数の分だけ);不是這幾型時 None。"""
    rest = tokens[k + 1:bound]
    if rest[:1] == ["p:まで"] or rest[:1] == ["p:だけ"]:
        return k + 2
    if rest[:1] == ["p:の"] and len(rest) > 2 and ctx.word(rest[1]) == "分" and rest[2] == "p:だけ":
        return k + 4
    return None


def _earlier_quantity(ctx, tokens, surfaces, start, end):
    """受事者之前(同一子句裡 tokens[start:end])的引用量:最後一個 …の数まで/数だけ/数の分だけ/枚数まで,字面從 数
    往前收到讀點、は、或主句的助詞為止(除外した数だけ、相手フィールドのモンスターの数まで、この効果で特殊召喚した
    モンスターの数まで——定語子句裡的助詞照收);只記字面、類空。沒有 None。"""
    for k in range(end - 1, start - 1, -1):
        if _base(ctx, tokens[k]) != "数":
            continue
        stop = _reference_end(ctx, tokens, k, end)
        if stop is None:
            continue
        lo = k
        while lo - 1 >= start and tokens[lo - 1] not in REFERENCE_PHRASE_STOP:
            t = tokens[lo - 1]
            if token_kind(t) == "particle" and t != "p:の" and not any(ctx.is_predicate(u) for u in tokens[lo:k]):
                break
            lo -= 1
        return _quantity("".join(surfaces[lo:stop]), None, None, True)
    return None


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
        end = _reference_end(ctx, tokens, k, bound)
        if end is None:
            if not (k > start and ctx.word(tokens[k - 1]) == "同じ"):
                continue
            end = k + 1
        return _quantity("".join(surfaces[start:end]), None, None, True)
    return None


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
        if ctx.word(pre[i]) in ADNOMINAL_COMPARE and _closes_clause(pre[start:i]):
            chunks.append([start, i + 1])         # 数値が同じ|機械族:帶格助詞的比較詞是子句的述語(票 10)
            start = i = i + 1
            continue
        i += 1
    if start < len(pre):
        chunks.append([start, len(pre)])
    merged, since = [], 0
    for lo, hi in chunks:
        toks = pre[lo:hi]
        if any(ctx.is_predicate(t) for t in toks) or ctx.word(toks[-1]) in ADNOMINAL_COMPARE:
            if any(t in CASE_PARTICLES for t in toks) and len(merged) > since:
                lo = merged[since][0]
                del merged[since:]
            merged.append([lo, hi])
            since = len(merged)
        else:
            merged.append([lo, hi])
    return merged


def _closes_clause(before):
    """比較詞(同じ/異なる)前的格裡有格助詞 → 它是定語子句的述語(数値が同じ|機械族);緊接在它前面的 と 是
    比較的對象(そのモンスターと同じ種族),不算。"""
    return any(t in CASE_PARTICLES for t in before[:-1]) or (bool(before) and before[-1] in CASE_PARTICLES - {"p:と"})


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
        if kind in NUMBER_TOKEN_KINDS or (kind == "lex" and ctx.word(t) in NUMERIC_FIELDS
                                           and i + 1 < n and token_kind(toks[i + 1]) in NUMBER_TOKEN_KINDS):
            j = _numeric_run(ctx, toks, i)                     # ドラゴン族・レベル8:並列項裡的數值(票 10)
            numeric = _numeric_items(ctx, toks[i:j])
            if numeric is None:
                return None
            out.extend(numeric)
            i = j
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
                    rest = toks[i:]
                    if all(token_kind(u) == "lex" for u in rest) \
                            and head_kind("".join(ctx.surface(u) for u in rest)) == HEAD_CARD:
                        # 「X」モンスターの攻撃力、攻撃表示モンスターの攻撃力:認得的項之後剩所有者名詞(モンスター),
                        # 落 其他、只留字面(票 10;前面什麼都沒認出時結果和整段落其他相同)
                        out.append(_modifier("".join(ctx.surface(u) for u in rest), OTHER))
                        return out
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


def _numeric_run(ctx, toks, i):
    """從 i 起連續的數值字面(欄位詞/比較詞/數字,連接符只在後面還接得上時算)→ 結尾位置。"""
    def is_numeric(u):
        kind = token_kind(u)
        return kind in NUMBER_TOKEN_KINDS or (kind == "lex" and (ctx.word(u) in NUMERIC_FIELDS
                                                                 or ctx.word(u) in COMPARATORS))
    j = i
    while j < len(toks):
        if is_numeric(toks[j]):
            j += 1
        elif toks[j] in NUMERIC_CONNECTORS and j + 1 < len(toks) and is_numeric(toks[j + 1]):
            j += 1
        else:
            break
    return j


def _zone_run(ctx, toks, i):
    """從 i 起的區域字面:一格(墓地)或分詞拆成兩三格的(除外|状態),長的先試,交給區域辨識認得就回結尾位置。"""
    for j in range(min(i + 3, len(toks)), i, -1):
        if all(token_kind(u) == "lex" for u in toks[i:j]) \
                and places.parse_place("".join(ctx.surface(u) for u in toks[i:j]))[1]:
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


FILL_RATE_ROWS = [("片語·%s phrases.%s" % (label, key), _fill_state(key)) for key, label in PHRASE_LABELS]
FILL_RATE_ROWS.append(("片語·數量 segments.quantity", quantity_fill_state))

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
             .format(total, positions[POS_COST], positions[POS_EFFECT], positions[POS_COND]), "",
             "| 數量類 | 段尾字面 | 取自子句 | 合計 |", "|---|---:|---:|---:|"]
    for kind in (*QUANTITY_KINDS, QUANTITY_REFERENCE_LABEL):
        tail, clause = counts[(kind, False)], counts[(kind, True)]
        lines.append("| %s | %s | %s | %s |" % (kind, format(tail, ","), format(clause, ","), format(tail + clause, ",")))
    return lines


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


FILL_RATE_ROWS.append(("修飾語 segments.modifiers", _modifiers_state))
FILL_RATE_ROWS += [("修飾語·%s modifiers.kind" % kind, _modifier_state(kind)) for kind in MODIFIER_KINDS]


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
        for kind in HEAD_KINDS),
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
                   ("其他類的修飾語 top 100", other_modifiers_section),
                   ("數量各類框數", quantity_section)]


# ── 批次檔的格(llm_check.py 經 enrich.batch_cells 讀) ──
def batch_cells(frame):
    """票 02:每欄一格「片語·對象=段 … 中心詞 X(類) 指示詞 玩家 Y 區域 Z | 段 …」;segment_bits 後面接
    修飾語(票 03:修飾語 字面(類)、…)與數量(票 04)。"""
    cells = []
    for key, label in PHRASE_LABELS:
        phrase = (frame.get("phrases") or {}).get(key)
        if not phrase:
            continue
        cells.append("片語·%s=%s" % (label, " | ".join(
            " ".join(segment_bits(seg)) for seg in phrase["segments"])))
    return cells


def segment_bits(seg):
    bits = ["段 %s" % seg["text"],
            "中心詞 %s(%s)" % (seg["head"] if seg["head"] is not None else "—", seg["head_kind"])]
    if seg.get("demonstrative"):
        bits.append("指示詞")
    if seg.get("player"):
        bits.append("玩家 %s" % seg["player"])
    if seg.get("zones"):
        bits.append("區域 %s" % "・".join(seg["zones"]))
    if seg.get("modifiers"):
        bits.append("修飾語 " + "、".join(modifier_bit(m) for m in seg["modifiers"]))
    return bits + quantity_bits(seg)


def quantity_bits(seg):
    """票 04:「數量 2枚まで(上限 2)」;引用量類空記 (引用量);取自子句的標 (取自子句)。"""
    q = seg.get("quantity")
    if not q:
        return []
    kind = "引用量" if q["kind"] is None else q["kind"] + ("" if q["number"] is None else " %d" % q["number"])
    return ["數量 %s(%s)%s" % (q["text"], kind, "(取自子句)" if q["from_clause"] else "")]


def modifier_bit(m):
    """票 03:字面(類);數值類列 欄位/比較/數字——レベル4以下(數值:レベル 以下 4)。"""
    if m["kind"] != MOD_NUMERIC:
        return "%s(%s)" % (m["text"], m["kind"])
    numbers = "・".join(str(n) for n in m["numbers"]) if m.get("numbers") else m["number"]
    detail = " ".join(str(x) for x in (m["field"], m["compare"], numbers) if x is not None)
    return "%s(數值:%s)" % (m["text"], detail)
