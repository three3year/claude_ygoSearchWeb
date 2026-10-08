# -*- coding: utf-8 -*-
"""動作框架抽取(票 effect-tokenize#04,實作票 05〜07):分詞結果 → 每句的動作框架。

接在分詞鏈之後:讀 tokens.json(tokenize.py 的輸出)逐句抽框架,寫 frames.json
(決定性建置產物,不入版控)。測試接縫是 extract(text, context):一句效果文
原文(帶同卡同段上文)→ 動作框架清單,內部呼叫真的分詞器與詞典。

框架(一個動作一個框架,依原文順序):
    action    動作(詞元):動詞以 lexicon.json 的 lemma 歸詞元;サ変名詞+する
              家族記名詞(破壊|する → 破壊);召喚法+召喚記 法+召喚(特殊召喚);
              「N に する/なる」的單詞補語併入動作(無効にする、対象になる);
              「〜を対象として」記 対象とする
    object    對象(を 前的詞)、source 來源(から 前)、goal 目的(に/へ 前)
              ——述語往前、同一子句內依助詞收;值保留原詞(指示綁定、列舉前項
              補全值、數量約束、卡名佔位);時間語(ターン/フェイズ/時…)的 に 不收
    position  位置:代價/效果/條件——發動句(以 発動できる/発動する 收尾的第一
              句)裡的付出是代價、處理段的動作是效果、觸發句(…場合/…時/…限り)
              與發動條件(対象として、狀態述語、被動)是條件
    polarity  極性:肯定/否定/可能——ない/されない/できない 系否定、できる 系可能
    sentence  句序(。 切開的第幾句,0 起)、span 對應詞序列範圍 [start, end)、
              clause 子句字面(span 內 token 字面相連,供拆解頁對照)

子句切分:一子句至多一個述語錨點——錨點(含活用尾/可能/否定/形式名詞 後綴與
其後的助詞、讀點)結束處即下一子句的起點;定語用法(動詞後直接接名詞:
特殊召喚したモンスター)不當錨點,留在名詞片語裡。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/frames.py
"""
import importlib.util
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from report import token_kind  # noqa: E402

LEXICON = os.path.join(HERE, "lexicon.json")
TOKENS = os.path.join(HERE, "tokens.json")
OUT = os.path.join(HERE, "frames.json")

# ── 封閉類(述語家族與功能詞)──
SURU_ACTIVE = {"する", "した", "して", "し", "すれば"}
SURU_PASSIVE = {"され", "される", "された", "されて"}
SURU_NEG = {"されない", "されず", "せず"}
POTENTIAL = {"できる", "でき"}
POTENTIAL_NEG = {"できない", "できず"}
SURU_FAMILY = SURU_ACTIVE | SURU_PASSIVE | SURU_NEG | POTENTIAL | POTENTIAL_NEG
# 錨點後的否定/補助/活用尾
NEGATORS = {"ない", "なく", "なかった", "ず", "なければ"}
AUXILIARY = {"いる", "いた", "いない", "いれば", "ある", "あった", "あれば"}
TAILS = {"た", "て", "る", "った"}
# 形式名詞:動詞後接這些仍是述語錨點(不算定語);條件類給 條件 位置
NOMINALIZERS = {"場合", "時", "際", "度", "限り", "ターン", "状態", "事", "ため",
                "よう", "まま", "後", "前", "間", "つき", "代わり", "結果"}
CONDITIONAL_NOMINALIZERS = {"場合", "時", "際", "度", "限り", "ターン", "状態"}
CONDITIONAL_FORMS = {"すれば", "あれば", "いれば", "なければ"}
# 「N に する/なる」的補語不吸收這些詞(量化詞/比較詞:全て裏側守備表示にする
# 的 全て 是副詞;レベル以上になる 的 以上 是比較結果,留在目的論元)
FOLD_STOP = {"全て", "それぞれ", "お互い", "両", "元々", "以上", "以下", "未満",
             "同名", "任意", "他", "次", "残り"}
# サ変名詞直接接 時 也是事件(攻撃宣言時/発動時/成功時);終了時/開始時/
# ダメージ計算時 是時點,不是動作
EVENT_NOUNS = {"宣言", "発動", "成功", "リバース"}
# 狀態/變化述語:在發動句裡是條件、不是代價
STATE_LEMMAS = {"存在", "ある", "いる", "持つ", "なる", "成功", "含む", "異なる",
                "違う", "超える", "揃う", "記す", "当たる", "出る", "離れる",
                "加わる", "戻る", "移る", "上がる", "下がる", "入れ替わる",
                "満たす", "リンク", "相互リンク", "だ", "無い", "多い", "少ない",
                "高い", "低い"}
LIGHT_VERBS = {"する": "する", "なる": "なる"}
# 時間語的 に(ターン/フェイズ/時…)不收成目的論元
TIME_HEADS = {"ターン", "時", "場合", "際", "度", "後", "前", "間", "内", "中",
              "以降", "開始", "終了", "デュエル", "フェイズ"}
CASE_ROLE = {"を": "object", "から": "source", "に": "goal", "へ": "goal"}
# 其他格助詞:切片語但第一版不收(主體/手段/期間);後綴型(にも/には)併入前一格
CASE_OTHER = {"が", "は", "で", "まで", "より", "として", "しか", "のみ", "だけ",
              "ずつ", "も"}
CASE_SUFFIX = {"も", "は", "のみ", "だけ", "しか", "ずつ"}
COORDINATORS = {"と", "や", "または", "及び", "か", "など"}
FUNCTIONAL = (SURU_FAMILY | NEGATORS | AUXILIARY | TAILS
              | {"な", "だった", "さらに", "また", "もう", "既に", "それ", "それら",
                 "いずれ", "よる", "よって", "よらず", "ない", "通常の"})
# 純平假名的詞元只有這幾個是動詞(よう/ため/まま 這類形式名詞詞元也以 う/る 結尾)
HIRAGANA_VERBS = {"なる", "めくる", "なくす"}
# 定語動詞只吸收這些格的片語(其餘動詞:往前吸到讀點或主題 は 為止)——
# 「カード名が記されたモンスター」的 が 屬定語,前面的 から 是主句的來源
RELATIVE_SCOPE = {"記す": {"が"}, "持つ": {"を"}, "含む": {"を"},
                  "異なる": {"が"}, "受ける": {"が"}, "違う": {"が"},
                  "決める": {"に"}, "存在": {"に", "で", "が"}}
# 連用形/て形不當定語(選んで特殊召喚、リリースして発動)
NON_ATTRIBUTIVE_SURU = {"し", "して", "され", "されて", "せず", "されず"}
ADJECTIVE_LEMMAS = {"高い", "低い", "多い", "少ない", "大きい", "小さい", "正しい",
                    "無い", "ない"}
SPECIAL_POTENTIAL = {"出せ", "出せる", "選べ", "行え", "取り除け", "除け"}
# 接 する家族 也不是動作的名詞:に対して(對…)、〜な、通常の
NON_PREDICATE_NOUNS = {"対", "な", "通常の", "際", "後", "前"}
# 「N に する/なる」能併入動作的補語:至多三格、全是名詞類、不含數字
FOLD_MAX = 3
IRREALIS_TAIL = "あかさたなはまやらわがざだばぱ"
NOUN_KINDS = {"name", "dem", "elided", "attr", "method", "cname", "num", "quant",
              "range", "counter"}
PUNCT_IN_PHRASE = set("・／～（）『』")
_PASSIVE_RE = re.compile(r"[らかまさわたばがな]れ")
_TE_GODAN_RE = re.compile(r"(って|いて|んで|して)$")

POS_COST, POS_EFFECT, POS_COND = "代價", "效果", "條件"
POL_AFFIRM, POL_NEG, POL_CAN = "肯定", "否定", "可能"


def _load_tokenizer_module():
    """tokenize.py 與標準庫同名:照路徑載入。"""
    spec = importlib.util.spec_from_file_location(
        "effect_tokenize", os.path.join(HERE, "tokenize.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Lexicon:
    def __init__(self, entries):
        self.entries = entries
        self.surface_of = {e["id"]: e["surface"] for e in entries}
        self.lemma_of = {e["id"]: e.get("lemma", e["surface"]) for e in entries}
        self.closed_of = {e["id"]: e.get("closed") for e in entries}

    def is_verb(self, wid):
        lemma = self.lemma_of[wid]
        surface = self.surface_of[wid]
        if surface in FUNCTIONAL or lemma in ADJECTIVE_LEMMAS:
            return False
        if lemma in ("する", "される", "できる", "ある", "いる", "だ"):
            return False
        if all("ぁ" <= ch <= "ゟ" for ch in lemma):
            return lemma in HIRAGANA_VERBS
        return lemma[-1] in "うくぐすつぬぶむる"


def verb_form(surface, lemma):
    """動詞詞形分類:te/stem/past/neg/cond/dict/irrealis/potential。"""
    if surface in SPECIAL_POTENTIAL:
        return "potential"
    if surface.endswith(("ない", "なく", "ず", "なかった")):
        return "neg"
    if surface.endswith("ば"):
        return "cond"
    if surface == lemma:
        return "dict"
    if surface.endswith(("た", "だ")):
        return "past"
    if surface.endswith(("て", "で")) and (
            surface[:-1] + "る" == lemma or _TE_GODAN_RE.search(surface)):
        return "te"
    if surface[-1] in IRREALIS_TAIL:
        return "irrealis"
    return "stem"


class FrameExtractor:
    def __init__(self, lexicon_entries, tokenizer=None):
        self.lex = Lexicon(lexicon_entries)
        if tokenizer is None:
            tokenizer = _load_tokenizer_module().Tokenizer(lexicon_entries)
        self.tokenizer = tokenizer

    # ── token 讀取 ──
    def surface(self, token):
        kind = token_kind(token)
        if kind == "lex":
            return self.lex.surface_of[token]
        if kind == "dem":
            _, dem, wid = token.split(":", 2)
            return dem + self.lex.surface_of[wid]
        if kind == "quant":
            _, wid, val, counter, cmp_word = token.split(":", 4)
            return ((self.lex.surface_of[wid] if wid else "") + val + counter
                    + cmp_word)
        if kind == "cname":
            return "〈%s〉カウンター" % token[2:]
        if kind == "name":
            return "「%s」" % token.split(":", 1)[1]
        if kind == "elided":
            _, head, wid = token.split(":", 2)
            return "%s(%s)" % (head, self.lex.surface_of[wid][len(head):])
        if kind == "range":
            _, lo, hi, counter = token.split(":", 3)
            return "%s～%s%s" % (lo, hi, counter)
        if kind == "punct":
            return token
        return token.split(":", 1)[1]

    def word(self, token):
        """詞典詞的字面;非詞典詞回 None。"""
        return self.lex.surface_of[token] if token.startswith("W") else None

    def is_noun_like(self, token):
        kind = token_kind(token)
        if kind in NOUN_KINDS:
            return True
        if kind != "lex":
            return False
        surface = self.lex.surface_of[token]
        if surface in FUNCTIONAL or surface in NOMINALIZERS:
            return False
        if self.lex.is_verb(token) or self.lex.lemma_of[token] in ADJECTIVE_LEMMAS:
            return False
        return True

    # ── 錨點辨識 ──
    def anchor_at(self, tokens, i, clause_start):
        """tokens[i] 起是否為述語錨點。回 dict(head, end, action, polarity,
        form, passive, nominalizer, fold) 或 None。end 是後綴鏈結束位置。"""
        t = tokens[i]
        n = len(tokens)
        w = self.word(t)
        head, action, form, passive = i, None, None, False
        j = i + 1
        polarity = POL_AFFIRM
        fold = 0                      # 併入動作的前置 token 數(N に する)

        def nxt(k):
            return self.word(tokens[k]) if k < n else None

        if w == "対象" and nxt(j) is None and j < n and tokens[j] == "p:として":
            return self._finish(tokens, i, i, j + 1, "対象とする", POL_AFFIRM,
                                "te", False, 0, clause_start)
        if w == "対象" and j < n and tokens[j] == "p:と" and nxt(j + 1) in SURU_FAMILY:
            action, j, form = "対象とする", j + 1, None
        elif token_kind(t) == "method" or w == "召喚":
            # 召喚法鏈 法(・法)*+召喚(+する家族)
            k = i
            parts = []
            while k < n and token_kind(tokens[k]) == "method":
                parts.append(tokens[k][2:])
                if k + 1 < n and tokens[k + 1] == "・" and k + 2 < n \
                        and token_kind(tokens[k + 2]) == "method":
                    k += 2
                else:
                    k += 1
                    break
            if nxt(k) != "召喚":
                return None
            after = nxt(k + 1)
            if after in SURU_FAMILY:
                action, j, form = "・".join(parts) + "召喚", k + 1, None
            elif after == "時" and not parts:
                return None
            elif after == "時":
                action, j, form = "・".join(parts) + "召喚", k + 1, "noun"
            else:
                return None
        elif w is not None and self.lex.is_verb(t):
            lemma = self.lex.lemma_of[t]
            form = verb_form(w, lemma)
            # 〜扱いで/〜扱いとして:「當作…」的修飾語,不是動作
            if w == "扱い" and j < n and token_kind(tokens[j]) == "particle":
                return None
            passive = bool(_PASSIVE_RE.search(w)) and lemma not in ("離れる",)
            action = lemma
            if lemma in LIGHT_VERBS or lemma in ("ある", "いる"):
                pass
            if form == "neg":
                polarity = POL_NEG
            elif form == "potential":
                polarity = POL_CAN
            if lemma in LIGHT_VERBS:
                # N に/と なる:補語併入動作(無効になる/対象になる/同じになる)
                action, fold = self._fold_complement(tokens, i, clause_start,
                                                     lemma)
        elif w is not None and w in SURU_FAMILY:
            # 裸 する家族(前面不是サ変名詞):N に/と する → 併入動作
            # (無効にする/裏側守備表示にする/リンク素材とする);補語是數字時
            # 動作記 にする、數字留在目的論元(攻撃力を０にする)
            prev = tokens[i - 1] if i - 1 >= clause_start else None
            if prev not in ("p:に", "p:と"):
                return None
            action, fold = self._fold_complement(tokens, i, clause_start, "する")
            form = None
            j = i                      # 本 token 就是 する家族,下面統一吃
        elif w is not None and w not in FUNCTIONAL and w not in NOMINALIZERS \
                and w not in NON_PREDICATE_NOUNS and not self.lex.is_verb(t) \
                and self.lex.lemma_of[t] not in ADJECTIVE_LEMMAS:
            after = nxt(j)
            if after in SURU_FAMILY:
                action, form = w, None
            elif after == "時" and w in EVENT_NOUNS:
                action, form = w, "noun"
                if w == "宣言" and i - 1 >= clause_start \
                        and self.word(tokens[i - 1]) == "攻撃":
                    action, head = "攻撃宣言", i - 1
            else:
                return None
        else:
            return None

        # ── 後綴鏈:する家族 → 否定 → 補助 → 事ができる → 形式名詞 ──
        suru_form = None
        if j < n and self.word(tokens[j]) in SURU_FAMILY and form != "noun":
            s = self.word(tokens[j])
            suru_form = s
            if s in SURU_NEG or s in POTENTIAL_NEG:
                polarity = POL_NEG
            elif s in POTENTIAL:
                polarity = POL_CAN
            if s in SURU_PASSIVE or s in SURU_NEG - {"せず"}:
                passive = True
            j += 1
        if form is None:
            form = {"し": "stem", "して": "te", "され": "stem", "されて": "te",
                    "せず": "neg", "されず": "neg"}.get(suru_form, "dict")
            if suru_form in ("した", "された"):
                form = "past"
        if j < n and self.word(tokens[j]) in TAILS:
            tail = self.word(tokens[j])
            if tail in ("て", "った"):
                form = "te"
            elif tail == "た":
                form = "past"
            j += 1
        if j < n and self.word(tokens[j]) in NEGATORS:
            polarity = POL_NEG
            if self.word(tokens[j]) == "なく":
                form = "te"
            j += 1
            # 〜しなければならない:義務,不是否定
            if (j + 1 < n and self.word(tokens[j - 1]) == "なければ"
                    and self.word(tokens[j]) == "なら"
                    and self.word(tokens[j + 1]) == "ない"):
                polarity = POL_AFFIRM
                form = "dict"
                j += 2
        if j < n and self.word(tokens[j]) in AUXILIARY:
            # 〜している/〜されている:補助動詞後直接接名詞仍是定語
            if self.word(tokens[j]) == "いない":
                polarity = POL_NEG
            form = "dict"
            j += 1
            if j < n and self.word(tokens[j]) in NEGATORS:
                polarity = POL_NEG
                j += 1
        if (j + 2 < n and self.word(tokens[j]) == "事"
                and tokens[j + 1] in ("p:が", "p:も", "p:は")
                and self.word(tokens[j + 2]) in POTENTIAL | POTENTIAL_NEG):
            polarity = (POL_NEG if self.word(tokens[j + 2]) in POTENTIAL_NEG
                        else POL_CAN)
            j += 3
        conditional = suru_form in CONDITIONAL_FORMS or (
            w is not None and w in CONDITIONAL_FORMS)
        return self._finish(tokens, head, i, j, action, polarity, form, passive,
                            fold, clause_start, conditional)

    def _fold_complement(self, tokens, i, clause_start, lemma):
        """tokens[i] 是 する/なる,前一格是 に/と:補語全是名詞類且不含數字時
        併入動作(補語+助詞+詞元),回 (動作, 併入格數);否則 (助詞+詞元, 0)。"""
        if i - 1 < clause_start or tokens[i - 1] not in ("p:に", "p:と"):
            return lemma, 0
        particle = tokens[i - 1][2:]
        k = i - 1
        while (k - 1 >= clause_start and (i - 1) - (k - 1) <= FOLD_MAX
               and token_kind(tokens[k - 1]) in ("lex", "elided", "method", "attr")
               and self.is_noun_like(tokens[k - 1])
               and self.word(tokens[k - 1]) not in FOLD_STOP):
            k -= 1
        if k == i - 1:
            return particle + lemma, 0
        text = "".join(self.surface(t) for t in tokens[k:i - 1])
        return text + particle + lemma, i - k

    def _finish(self, tokens, head, verb_at, j, action, polarity, form, passive,
                fold, clause_start, conditional=False):
        n = len(tokens)
        nominalizer = None
        if j < n and self.word(tokens[j]) in NOMINALIZERS:
            nominalizer = self.word(tokens[j])
            j += 1
        elif form not in ("te", "stem", "neg") and j < n \
                and self.is_noun_like(tokens[j]):
            return None               # 定語:動詞直接修飾後面的名詞
        if form == "noun" and nominalizer is None:
            return None
        end = j
        # 子句尾:形式名詞/述語後的助詞與讀點一併收進本子句
        while j < n and (token_kind(tokens[j]) == "particle" or tokens[j] == "、"):
            j += 1
        return {"head": head, "verb_at": verb_at, "end": end, "tail": j,
                "action": action, "polarity": polarity, "form": form,
                "passive": passive, "nominalizer": nominalizer,
                "fold": fold, "conditional": conditional
                or nominalizer in CONDITIONAL_NOMINALIZERS}

    # ── 論元 ──
    def chunks(self, tokens, start, stop):
        """[start, stop) 依格助詞切片語 → [(role, [tokens], hard_before)]。"""
        out, cur, hard = [], [], False
        k = start - 1
        while k + 1 < stop:
            k += 1
            t = tokens[k]
            kind = token_kind(t)
            if kind == "particle":
                p = t[2:]
                # 格助詞後接 の(への戦闘ダメージ/EXデッキからの特殊召喚)是修飾,
                # 留在片語裡;に対して(對…)整組不是論元
                if p in CASE_ROLE and k + 1 < stop and tokens[k + 1] == "p:の":
                    cur.append(t)
                    continue
                if (p == "に" and k + 2 < stop and self.word(tokens[k + 1]) == "対"
                        and self.word(tokens[k + 2]) in ("して", "し")):
                    out.append(["に対して", cur, hard])
                    cur, hard = [], False
                    k += 2
                    continue
                # によって/による(依…)、〜の代わりに(代替)、ランダムに:手段/
                # 方式,不是目的論元
                if (p == "に" and k + 1 < stop
                        and self.word(tokens[k + 1]) in ("よって", "よる", "より")):
                    out.append(["によって", cur, hard])
                    cur, hard = [], False
                    k += 1
                    continue
                if p == "に" and cur and self.word(cur[-1]) in ("代わり", "ランダム"):
                    out.append(["に(方式)", cur, hard])
                    cur, hard = [], False
                    continue
                if p in CASE_ROLE or (p in CASE_OTHER and p not in CASE_SUFFIX):
                    # 片語開頭的裸數量/全て(カードを３枚墓地へ、モンスターを全て
                    # 墓地へ)屬前一個 を 片語
                    lead = 0
                    while lead < len(cur) and (
                            token_kind(cur[lead]) in ("num", "counter", "quant",
                                                      "range")
                            or self.word(cur[lead]) in ("全て", "それぞれ")):
                        lead += 1
                    if 0 < lead < len(cur) and out and out[-1][0] == "を":
                        out[-1][1] = out[-1][1] + cur[:lead]
                        cur = cur[lead:]
                    out.append([p, cur, hard])
                    cur, hard = [], False
                elif p in CASE_SUFFIX:
                    if cur:
                        out.append([p, cur, hard])
                        cur, hard = [], False
                    # 後綴型(にも/には):前一格照舊
                elif p == "と" and k == stop - 1:
                    # 述語緊前的 と(〜となる/〜とする 的補語)當目的論元
                    out.append(["と", cur, hard])
                    cur, hard = [], False
                elif p in COORDINATORS or p == "の":
                    cur.append(t)
                continue
            if kind == "punct":
                if t == "、":
                    if cur:
                        out.append([None, cur, hard])
                    cur, hard = [], True
                elif t in PUNCT_IN_PHRASE:
                    cur.append(t)
                continue
            cur.append(t)
        if cur:
            out.append([None, cur, hard])
        return out

    def _relative_verb(self, chunk):
        """片語含定語動詞(動詞/する家族後直接接名詞)→ 回該定語的詞元;
        前面的片語屬同一名詞片語。連用形/て形不算。"""
        for k, (a, b) in enumerate(zip(chunk, chunk[1:])):
            w = self.word(a)
            if w is None or not self.is_noun_like(b):
                continue
            if w in SURU_FAMILY and w not in NON_ATTRIBUTIVE_SURU:
                prev = self.word(chunk[k - 1]) if k else None
                return prev or w
            if w in NEGATORS:
                return w
            if self.lex.is_verb(a) and verb_form(
                    w, self.lex.lemma_of[a]) not in ("te", "stem", "irrealis"):
                return self.lex.lemma_of[a]
        return None

    def arguments(self, tokens, start, stop):
        parts = self.chunks(tokens, start, stop)
        merged = []
        for role, chunk, hard in parts:
            rel = self._relative_verb(chunk)
            if rel is not None and merged and not hard:
                # 往前併到讀點或主題(は)為止;特定動詞只吸收自己的格
                scope = RELATIVE_SCOPE.get(rel)
                absorbed = []
                while merged and merged[-1][0] != "は":
                    r, c, h = merged.pop()
                    if scope is not None and r not in scope:
                        merged.append([r, c, h])
                        break
                    absorbed.insert(0, c + (["p:" + r] if r else []))
                    if h:
                        break
                chunk = [t for c in absorbed for t in c] + chunk
            merged.append([role, chunk, hard])
        # 並列(と/や/または/及び/か 結尾)併入下一格
        joined = []
        for role, chunk, hard in merged:
            if (joined and joined[-1][0] is None and joined[-1][1]
                    and token_kind(joined[-1][1][-1]) == "particle"):
                prev = joined.pop()
                chunk = prev[1] + chunk
            joined.append([role, chunk, hard])
        args = {}
        last_key = None
        for role, chunk, _hard in joined:
            if role == "まで" and last_key == "object" and chunk and all(
                    token_kind(t) in ("num", "counter", "quant", "range")
                    for t in chunk):
                # 「〜を２枚まで」:上限數量併回對象
                args[last_key] += "".join(self.surface(t) for t in chunk) + "まで"
                continue
            key = CASE_ROLE.get(role, "goal" if role == "と" else None)
            if key is None or not chunk:
                last_key = None
                continue
            if key == "goal" and self._is_time(chunk):
                last_key = None
                continue
            # 片語兩端的括弧是註記邊界,不屬論元字面
            while chunk and chunk[0] in ("（", "）"):
                chunk = chunk[1:]
            while chunk and chunk[-1] in ("（", "）"):
                chunk = chunk[:-1]
            if not chunk:
                continue
            text = "".join(self.surface(t) for t in chunk)
            args[key] = text if key not in args else args[key] + "、" + text
            last_key = key
        return args

    def _is_time(self, chunk):
        last = chunk[-1]
        w = self.word(last)
        if w in TIME_HEADS or (last.startswith("W")
                               and self.lex.closed_of[last] == "階段名"):
            return True
        if token_kind(last) == "counter" and last[2:] in ("度", "回"):
            return True
        return False

    # ── 整句 ──
    def frames_of_tokens(self, tokens):
        n = len(tokens)
        sentences = []
        start = 0
        for k, t in enumerate(tokens):
            if t == "。":
                sentences.append((start, k + 1))
                start = k + 1
        if start < n:
            sentences.append((start, n))

        anchors_by_sentence = []
        for s_start, s_end in sentences:
            anchors = []
            clause_start = s_start
            i = s_start
            while i < s_end:
                a = self.anchor_at(tokens, i, clause_start) if tokens[i] != "。" \
                    else None
                if a is None:
                    i += 1
                    continue
                a["clause_start"] = clause_start
                anchors.append(a)
                clause_start = a["tail"]
                i = a["tail"]
            anchors_by_sentence.append(anchors)

        # 括弧深度:（…）裡的註記(この効果は相手ターンでも発動できる)不算
        # 發動句的收尾,也不參與代價/條件判定
        depth, depth_at = 0, []
        for t in tokens:
            if t == "（":
                depth += 1
            depth_at.append(depth)
            if t == "）":
                depth = max(0, depth - 1)

        # 發動句:第一個以 発動できる/発動する 收尾(括弧外、後接 。或句尾)的句子
        # (この効果は…発動できる 的速度註記除外)
        act, marker_idx = None, None
        for s_idx, anchors in enumerate(anchors_by_sentence):
            s_start, s_end = sentences[s_idx]
            if (tokens[s_start].startswith("d:この:")
                    and self.word(tokens[s_start].split(":", 2)[2]) == "効果"
                    and s_start + 1 < n and tokens[s_start + 1] == "p:は"):
                continue
            for k, a in enumerate(anchors):
                if (a["action"] == "発動" and a["polarity"] != POL_NEG
                        and a["nominalizer"] is None
                        and depth_at[a["verb_at"]] == 0
                        and (a["end"] >= s_end - 1
                             or tokens[a["end"]] in ("。", "（"))):
                    act, marker_idx = s_idx, k
                    break
            if act is not None:
                break

        frames = []
        for s_idx, anchors in enumerate(anchors_by_sentence):
            in_activation = (s_idx == act)
            cond_after = [False] * len(anchors)
            if in_activation:
                seen = False
                for k in range(marker_idx - 1, -1, -1):
                    cond_after[k] = seen
                    if anchors[k]["conditional"]:
                        seen = True
            for k, a in enumerate(anchors):
                is_marker = in_activation and k == marker_idx
                before_marker = in_activation and k < marker_idx                     and depth_at[a["verb_at"]] == 0
                args = self.arguments(tokens, a["clause_start"],
                                      a["head"] - a["fold"])
                # 発動 本身:發動句的收尾、「相手ターンでも発動できる」這類速度
                # 註記都不是動作;有直接對象/來源(〜を発動できない)才成框架
                if (a["action"] == "発動" and a["polarity"] != POL_NEG
                        and a["nominalizer"] is None
                        and not ("object" in args or "source" in args)):
                    continue
                if a["conditional"]:
                    position = POS_COND
                elif is_marker:
                    position = POS_COND
                elif before_marker:
                    if (a["action"] == "対象とする" or a["passive"]
                            or a["action"] in STATE_LEMMAS or cond_after[k]
                            or a["form"] in ("dict", "past", "neg")
                            and a["nominalizer"] != "事"):
                        position = POS_COND
                    else:
                        position = POS_COST
                else:
                    position = POS_EFFECT
                span = (a["clause_start"], a["end"])
                frame = {"sentence": s_idx, "action": a["action"],
                         "object": args.get("object"),
                         "source": args.get("source"),
                         "goal": args.get("goal"),
                         "position": position, "polarity": a["polarity"],
                         "span": list(span),
                         "clause": " ".join(self.surface(t)
                                            for t in tokens[span[0]:span[1]])}
                frames.append(frame)
        return frames

    def extract(self, text, context=""):
        return self.frames_of_tokens(self.tokenizer.tokenize(text, context))


_DEFAULT = None


def default_extractor():
    global _DEFAULT
    if _DEFAULT is None:
        with open(LEXICON, encoding="utf-8") as f:
            _DEFAULT = FrameExtractor(json.load(f))
    return _DEFAULT


def extract(text, context=""):
    """接縫:一句效果文原文(帶同卡同段上文)→ 動作框架清單。"""
    return default_extractor().extract(text, context)


def main():
    extractor = default_extractor()
    with open(TOKENS, encoding="utf-8") as f:
        sentences = json.load(f)
    out = []
    covered = {"effect": 0, "extra": 0}
    total = {"effect": 0, "extra": 0}
    n_frames = 0
    for s in sentences:
        frames = extractor.frames_of_tokens(s["tokens"])
        for k, fr in enumerate(frames):
            fr["order"] = k
        out.append({"card": s["card"], "section": s["section"],
                    "index": s["index"], "stratum": s["stratum"],
                    "frames": frames})
        total[s["stratum"]] += 1
        covered[s["stratum"]] += bool(frames)
        n_frames += len(frames)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
        f.write("\n")
    for key in ("effect", "extra"):
        print("%s: 有框架的句 %d / %d(%.2f%%)" % (
            key, covered[key], total[key], 100.0 * covered[key] / total[key]))
    print("框架總數 %d;已寫出 %s" % (n_frames, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
