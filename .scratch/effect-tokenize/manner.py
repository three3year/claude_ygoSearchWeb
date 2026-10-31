# -*- coding: utf-8 -*-
"""方式(frame-args-v4 票 06)。

mark(ctx, tokens, frame):述語前同一子句內(frame["span"])的 で 片語 → frame["manner"](字面,含 で、
不含 は/も/のみ/しか 後綴)、frame["manner_kind"](closed_values.MANNER_KINDS)、frame["manner_value"]
(只在 表示形式 時,帶表示形式的值)。一框至多一個:從離述語最近的 で 往前找,第一個不是定語/繫詞的
就定案——它接的是區域(Pゾーンで、フィールドで)時不是方式,交給 regions.place_from_de 進結構化所在
並標 取自で(2026-10-31 定案);否則記方式。

不收的 で(規格「定語裡的 で 沿用既有判準不收、〜でなければならない 不收」):
- 定語子句裡的 で:で 與述語之間有定語述語(動詞/形容詞/する家族後接名詞,この効果で特殊召喚した|
  モンスター、その戦闘で発生する|戦闘ダメージ),で 屬那個定語述語,不是本述語的方式。
- 並列修飾的 で:片語頭是數值(攻撃力2400以上で、レベル4以下で、800で;數值從不是方式),或頭是
  種族/屬性/以外/同じ… 且 で 後只隔名詞就接 の(戦士族・ドラゴン族で光属性の、同じ属性で攻撃力1500の)。
- 繫詞 で:後面(越過 は/も)接 ある/ない/なければ 系(〜である、〜ではない、〜でなければならない)。
- 中止形的繫詞 で(LPが2000以下で、…):で 後接讀點而片語落 其他 時不收;落得進類的(「X」の効果で、
  リリースされた;装備カード扱いで、…に装備)照收。
片語字面:往前收名詞格、の、並列(・/または/か/及び/や)到格助詞、讀點或述語為止;開頭的數量
(１枚、全て、それぞれ)與時間語(このターン)屬對象或句子,不進方式字面;なし(な+し)併入(リリースなしで)。

方式類(closed_values.MANNER_KINDS):片語依並列切成幾段,各段依尾詞歸類——効果 → 手段:效果;戦闘/攻撃 →
手段:戰鬥;方法 → 手段:方法;表示形式字面(守備表示/表側表示/…)→ 表示形式;扱い → 視同;順番 → 順序;
其餘 → 其他。各段同一類才是那一類(表側守備表示または裏側守備表示で → 表示形式,值是整段字面),
不同類(戦闘・効果で)落 其他、只留字面。這裡不 import frames(循環 import);定語述語的判準由
frames.py 經 ctx.is_predicate 傳進來。
"""
import places
import regions
from closed_values import MANNER_KINDS, OTHER
from report import token_kind

MEANS_EFFECT, MEANS_BATTLE, MEANS_METHOD, DISPLAY_FORM, REGARDED, ORDER = MANNER_KINDS[:6]

DE, SUFFIXES = "p:で", ("p:は", "p:も", "p:のみ", "p:しか")
# 片語內的並列與連接(字面照原文接起來:戦闘・効果、表側守備表示または裏側守備表示):
# 擇一並列(または/か/及び/や)各段要同類;・ 並列可以是修飾語的並列(魔法・罠カードの効果),類看最後一段
ALT_JOINERS = {"p:または", "p:か", "p:及び", "p:や"}
JOINERS = ALT_JOINERS | {"・"}
PHRASE_PUNCT = {"・", "／", "～"}
# 形式名詞/連用形當片語尾的(表側守備表示のままで、装備カード扱いで;frames.py 也不把 扱い 當動作)
PHRASE_TAIL_WORDS = frozenset(("まま", "扱い"))
# 表示形式的字面(規格列的九個)
DISPLAY_FORMS = frozenset(("守備表示", "表側表示", "裏側守備表示", "攻撃表示", "表側", "裏側", "裏側表示",
                           "表側攻撃表示", "表側守備表示"))
# 尾詞 → 方式類(表示形式另看整段字面)
TAIL_KINDS = (("効果", MEANS_EFFECT), ("戦闘", MEANS_BATTLE), ("攻撃", MEANS_BATTLE),
              ("方法", MEANS_METHOD), ("扱い", REGARDED), ("順番", ORDER))
# 繫詞 で 後面接的(越過 は/も):〜である、〜ではない、〜でなければならない
COPULA_NEXT = frozenset(("ある", "あり", "あった", "あれば", "あって", "ない", "なく", "なかった",
                         "なければ", "なら", "ならない"))
# 並列修飾的 で:片語頭是這些(數值另算)且 で 後只隔名詞就接 の
ATTRIBUTE_TAILS = ("族", "属性", "以上", "以下", "未満")   # X以外で 多半是「以 X 以外的方式」,不算
NUMERIC_KINDS = frozenset(("num", "quant", "counter", "range"))
# 片語開頭不收的:對象的數量(１枚、全て、それぞれ)與時間語(このターン)
LEADING_ADVERBS = frozenset(("全て", "それぞれ"))
LEADING_TIME_TAILS = ("ターン", "フェイズ", "フェイズ中")
ZONE_SURFACES = tuple(term for term, _ in places.ZONE_TERMS)


def _noun_like(ctx, token):
    return ctx.is_noun_like(token) or token_kind(token) == "method"


def phrase_before(ctx, tokens, start, i):
    """で(索引 i)前的片語起點 lo(片語是 tokens[lo:i]):往前收名詞格、の、並列;なし(な+し)併入。"""
    lo = i
    if lo - 2 >= start and (ctx.surface(tokens[lo - 2]), ctx.surface(tokens[lo - 1])) == ("な", "し"):
        lo -= 2
    while lo - 1 >= start:
        t = tokens[lo - 1]
        if (_noun_like(ctx, t) or t == "p:の" or t in JOINERS or t in PHRASE_PUNCT
                or ctx.surface(t) in PHRASE_TAIL_WORDS):
            lo -= 1
        else:
            break
    # 開頭不能是 の/並列
    while lo < i and (tokens[lo] == "p:の" or tokens[lo] in JOINERS or tokens[lo] in PHRASE_PUNCT):
        lo += 1
    return lo


def strip_leading(ctx, tokens, lo, i):
    """片語開頭的數量、全て/それぞれ、時間語不進方式字面。"""
    while lo < i:
        t = tokens[lo]
        s = ctx.surface(t)
        if token_kind(t) in NUMERIC_KINDS or s in LEADING_ADVERBS or (
                token_kind(t) == "dem" and s.endswith(LEADING_TIME_TAILS)):
            lo += 1
        else:
            break
    return lo


def _in_relative_clause(ctx, tokens, i, end):
    """で 與述語之間有定語述語(述語後直接接名詞)→ で 屬那個定語;讀點之後是別的論元(装備魔法カード
    扱いで、この効果で特殊召喚したモンスターに装備),不再往後看。"""
    for m in range(i + 1, end - 1):
        if tokens[m] == "、":
            return False
        if ctx.is_predicate(tokens[m]) and _noun_like(ctx, tokens[m + 1]):
            return True
    return False


def _attributive_coordination(ctx, tokens, lo, i, end):
    """並列修飾的 で:片語頭是數值 → 一律不是方式;頭是 種族/屬性/以外/同じ… 且 で 後只隔名詞就接 の。"""
    head = tokens[i - 1]
    if token_kind(head) in NUMERIC_KINDS:
        return True
    head_text = ctx.surface(head)
    first = ctx.surface(tokens[lo]) if lo < i else ""
    if not (head_text.endswith(ATTRIBUTE_TAILS) or first.startswith("同じ")):
        return False
    for m in range(i + 1, end):
        t = tokens[m]
        if t == "p:の":
            return True
        if not (_noun_like(ctx, t) or t in PHRASE_PUNCT):
            return False
    return False


def _after_suffixes(tokens, i, end):
    """で 後越過 は/も/のみ/しか 的下一個 token 索引。"""
    m = i + 1
    while m < end and tokens[m] in SUFFIXES:
        m += 1
    return m


def kind_of(ctx, tokens, literal):
    """方式片語的 token(不含 で)→ (方式類, 表示形式值|None)。擇一並列(または/か/及び/や)各段要同一類;
    ・ 並列的各段同一類,或只有最後一段落得進類、其餘是裸修飾語(魔法・罠カードの効果 → 手段:效果);
    不同類(戦闘・効果、戦闘または相手の効果)落 其他。"""
    kinds = {_alternative_kind(ctx, alt) for alt in _split(tokens, ALT_JOINERS)}
    if len(kinds) != 1:
        return OTHER, None
    kind = kinds.pop()
    return kind, (literal if kind == DISPLAY_FORM else None)


def _split(tokens, joiners):
    parts, cur = [], []
    for t in tokens:
        if t in joiners:
            parts.append(cur)
            cur = []
        else:
            cur.append(t)
    parts.append(cur)
    return [p for p in parts if p]


def _alternative_kind(ctx, tokens):
    groups = _split(tokens, {"・"})
    kinds = [_part_kind("".join(ctx.surface(t) for t in g)) for g in groups]
    if len(set(kinds)) == 1:
        return kinds[0]
    if all(k == OTHER for k in kinds[:-1]):
        return kinds[-1]
    return OTHER


def _part_kind(part):
    if part in DISPLAY_FORMS:
        return DISPLAY_FORM
    for tail, kind in TAIL_KINDS:
        if part.endswith(tail):
            return kind
    return OTHER


def is_zone_phrase(literal, last_surface):
    """片語整個是區域(可帶玩家):Pゾーン、自分フィールド、相手のモンスターゾーン;同じ縦列 不是。"""
    return last_surface.endswith(ZONE_SURFACES) and bool(places.parse_zones(literal))


def find(ctx, tokens, frame):
    """子句裡定案的 で 片語 → ("manner", 字面不含 で, 方式類, 表示形式值) | ("zone", 字面, None, None) | None。"""
    start, end = frame["span"]
    for i in range(end - 1, start, -1):
        if tokens[i] != DE:
            continue
        lo = phrase_before(ctx, tokens, start, i)
        if lo >= i:
            continue                                   # 助詞/讀點後的裸 で
        if _in_relative_clause(ctx, tokens, i, end):
            continue
        if _attributive_coordination(ctx, tokens, lo, i, end):
            continue
        nxt = _after_suffixes(tokens, i, end)
        if nxt < end and ctx.surface(tokens[nxt]) in COPULA_NEXT:
            continue
        lo2 = strip_leading(ctx, tokens, lo, i)
        if lo2 >= i:
            continue
        literal = "".join(ctx.surface(t) for t in tokens[lo2:i])
        if is_zone_phrase(literal, ctx.surface(tokens[i - 1])):
            return "zone", literal, None, None
        kind, value = kind_of(ctx, tokens[lo2:i], literal)
        if nxt < end and tokens[nxt] == "、" and kind == OTHER:
            continue                                   # 中止形的繫詞 で(LPが2000以下で、)
        return "manner", literal, kind, value
    return None


def mark(ctx, tokens, frame):
    found = find(ctx, tokens, frame)
    if found is None:
        return
    what, literal, kind, value = found
    if what == "zone":
        regions.place_from_de(frame, literal)
        return
    frame["manner"] = literal + "で"
    frame["manner_kind"] = kind
    if value is not None:
        frame["manner_value"] = value


def fill_state(frame):
    """填充率的列:方式 → 有值(落得進類)/其他/None。"""
    kind = frame.get("manner_kind")
    if kind is None:
        return None
    return OTHER if kind == OTHER else "有值"


def count_section(records):
    """報告小節「方式各類框數」:七類 × 位置(代價/效果/條件)的動作框架數,與 其他 類的字面 top 30。"""
    from collections import Counter
    positions = ("代價", "效果", "條件")
    counts, others = Counter(), Counter()
    for rec in records:
        for fr in rec["frames"]:
            if fr.get("manner_kind"):
                counts[(fr["manner_kind"], fr["position"])] += 1
                if fr["manner_kind"] == OTHER:
                    others[fr["manner"]] += 1
    lines = ["方式=述語前同一子句內的 で 片語(字面含 で);方式類依片語尾詞歸類,並列不同類(戦闘・効果で)"
             "落 其他。定語裡的 で、繫詞 で 不收;で 接區域不是方式,進結構化所在、標 取自で。", "",
             "| 方式類 | " + " | ".join(positions) + " | 合計 |", "|---|" + "---|" * (len(positions) + 1)]
    for kind in MANNER_KINDS:
        row = [counts[(kind, pos)] for pos in positions]
        lines.append("| %s | %s | %s |" % (kind, " | ".join(format(c, ",") for c in row),
                                           format(sum(row), ",")))
    lines += ["", "其他類的方式字面 top 30:", ""]
    lines += ["- %s %s" % (literal, format(n, ",")) for literal, n in others.most_common(30)]
    return lines
