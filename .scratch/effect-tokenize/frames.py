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
    sentence  句序(。 與 ● 切開的第幾句,0 起)、span 對應詞序列範圍 [start, end)、
              clause 子句字面(span 內 token 字面相連,供拆解頁對照)
    option    選項(ADR-0015):出自第 n 個 ● 選項的框架記 n,第一個 ● 之前為 None;
              label 是「●自分ターン：」這類標籤冒號前的值(沒有標籤時 None),
              標籤本身不出框架

單位是效果句(一個編號效果的全文,連同它的 ● 選項;tokenize.py 的 assemble 把
拆開的領起句與子效果句接回一段):選項邊界 token「●」與「。」同樣結束一句,
發動句、位置、極性各句照既有規則判定,選項各有自己的發動句。

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
from constraints import KIND_ACTION, KIND_CONSTRAINT, ConstraintFinder  # noqa: E402
from report import frame_stats, token_kind  # noqa: E402

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
                "よう", "まま", "後", "前", "間", "つき"}
CONDITIONAL_NOMINALIZERS = {"場合", "時", "際", "度", "限り", "ターン", "状態",
                            "間"}
CONDITIONAL_FORMS = {"すれば", "あれば", "いれば", "なければ"}
# 「N に する/なる」的補語不吸收這些詞(量化詞/比較詞:全て裏側守備表示にする
# 的 全て 是副詞;レベル以上になる 的 以上 是比較結果,留在目的論元)
FOLD_STOP = {"全て", "それぞれ", "お互い", "両", "元々", "以上", "以下", "未満",
             "同名", "任意", "他", "次", "残り"}
# サ変名詞直接接 時 也是事件(攻撃宣言時/発動時/成功時);終了時/開始時/
# ダメージ計算時 是時點,不是動作
EVENT_NOUNS = {"宣言", "成功", "リバース"}
# 「・」並列的述語名詞(召喚・特殊召喚した/特殊召喚・リバースした):各出一框架
SAHEN_NOUNS = {"発動", "召喚", "破壊", "存在", "除外", "アップ", "リリース", "成功",
               "攻撃", "ドロー", "セット", "装備", "選択", "無効化", "適用", "宣言",
               "ダウン", "回復", "リバース", "確認", "無視", "発生", "使用", "変更",
               "移動", "シャッフル", "合計", "チェーン", "終了", "スキップ", "指定",
               "公開", "勝利", "代用", "相互リンク", "コントロール"}
# 「Xが Yの N」的屬性主語(攻撃力と守備力が０の悪魔族モンスター):併入名詞片語
ATTR_NOUNS = {"レベル", "ランク", "攻撃力", "守備力", "種族", "属性", "カード名", "数",
              "数値", "Pスケール", "リンクマーカー", "名", "合計", "レベル・ランク",
              "攻撃力・守備力", "種族・属性", "元々の攻撃力", "元々の守備力"}
# 片語開頭的副詞/接續詞/時間語不屬論元
LEADING_ADVERBS = {"さらに", "また", "もう", "既に", "その後", "それぞれ"}
# 「〜に」的方式副詞(ランダムに/順に/お互いに/〜の代わりに):不是目的論元
MANNER_NI = {"代わり", "ランダム", "お互い", "順"}
# 狀態/變化述語:在發動句裡是條件、不是代價
STATE_LEMMAS = {"存在", "ある", "いる", "持つ", "なる", "成功", "含む", "異なる",
                "違う", "超える", "揃う", "記す", "当たる", "出る", "離れる",
                "加わる", "戻る", "移る", "上がる", "下がる", "入れ替わる",
                "満たす", "リンク", "相互リンク", "だ", "無い", "多い", "少ない",
                "高い", "低い"}
LIGHT_VERBS = {"する", "なる"}
# 時間語的 に(ターン/フェイズ/時…)不收成目的論元
TIME_HEADS = {"ターン", "時", "場合", "際", "度", "後", "前", "間", "内", "中",
              "以降", "開始", "終了", "デュエル", "フェイズ", "毎"}
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
RELATIVE_SCOPE = {"記す": {"が", "に"}, "持つ": {"を", "として"}, "含む": {"を"},
                  "異なる": {"が"}, "受ける": {"が"}, "違う": {"が"},
                  "決める": {"に"}, "存在": {"に", "で", "が"},
                  "なる": {"と", "に", "が", "で"}, "な": {"に", "が"},
                  "同じ": {"と", "が"}, "高い": {"が", "より", "と"},
                  "低い": {"が", "より", "と"}, "多い": {"が", "より", "と"},
                  "少ない": {"が", "より", "と"}, "無い": {"が", "に"},
                  "ない": {"が", "に"}}
# 定語吸收不越過的片語(方式/手段副詞、●標籤)
NON_ABSORB_ROLES = {"に(方式)", "によって", "に対して", "に加えて", "：", "は"}
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
OPTION = "●"                  # 選項邊界 token(tokenize.OPTION)
LABEL_MAX_CHARS = 30          # ●標籤「●…：」冒號前的最大字數(與 tokenize._LABEL 同)


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
    if surface.endswith("ず"):
        return "stem"
    if surface.endswith(("ない", "なく", "なかった")):
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
    def __init__(self, lexicon_entries):
        self.lex = Lexicon(lexicon_entries)
        tokenize = _load_tokenizer_module()
        self.tokenizer = tokenize.Tokenizer(lexicon_entries)
        self.char_offsets = tokenize.char_offsets
        self.finder = ConstraintFinder(self)

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

    @staticmethod
    def _method_prefix(tokens, m, start):
        """tokens[m] 往前連續的召喚法 token(法・法…)→ (字串前綴, 第一個法的位置)。
        沒有召喚法時回 ("", m + 1)。"""
        parts = []
        while m >= start and token_kind(tokens[m]) == "method":
            parts.insert(0, tokens[m][2:])
            m -= 1
        return "・".join(parts), m + 1

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

        if w == "対象" and j < n and tokens[j] == "p:として":
            return self._finish(tokens, i, i, j + 1, "対象とする", POL_AFFIRM,
                                "te", False, 0, clause_start)
        # 〜を素材として/〜をX素材として:當作素材(動作 素材とする)
        if w is not None and w.endswith("素材") and j < n \
                and tokens[j] == "p:として":
            prefix, head = self._method_prefix(tokens, head - 1, clause_start)
            return self._finish(tokens, head, i, j + 1, prefix + w + "とする",
                                POL_AFFIRM, "te", False, 0, clause_start)
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
            # 〜でなければならない:繫詞「必須是」,不是動作 なる
            if lemma == "なる" and i - 1 >= clause_start and tokens[i - 1] == "p:で":
                return None
            # 〜扱いで/〜扱いとして:「當作…」的修飾語,不是動作
            if w == "扱い" and j < n and token_kind(tokens[j]) == "particle":
                return None
            # 続けて攻撃できる 的 続けて 是副詞;通常召喚に加えて 的 加えて 是慣用
            if w == "続けて" and j < n and token_kind(tokens[j]) != "punct":
                return None
            if w == "加えて" and i - 2 >= clause_start and tokens[i - 1] == "p:に" \
                    and self.word(tokens[i - 2]) == "召喚":
                return None
            passive = bool(_PASSIVE_RE.search(w)) and lemma not in ("離れる",)
            action = lemma
            if form == "neg" or w.endswith("ず"):
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
            # 対象にもできない:後綴助詞(も/は)夾在 に 與 する 之間
            skip = 0
            if (prev in ("p:も", "p:は") and i - 2 >= clause_start
                    and tokens[i - 2] in ("p:に", "p:と")):
                prev, skip = tokens[i - 2], 1
            if prev in ("p:に", "p:と"):
                action, fold = self._fold_complement(tokens, i - skip,
                                                     clause_start, "する")
                fold += skip
            elif prev == "p:を" and w in SURU_ACTIVE:
                action = "する"        # 通常のドローをした
            elif w in POTENTIAL | POTENTIAL_NEG:
                # 「〜の特殊召喚は１ターンに１度しかできない」:主題是動作名詞時
                # 動作就是它(効果は…できない 視為 使用)
                action = self._topic_action(tokens, i, clause_start)
                if action is None:
                    return None
            else:
                return None
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
                    "せず": "stem", "されず": "stem",
                    "できず": "stem", "でき": "stem"}.get(suru_form, "dict")
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
            elif self.word(tokens[j]) in ("ない", "なかった"):
                form = "neg"           # 存在しない+名詞 是定語
            elif self.word(tokens[j]) == "ず":
                form = "stem"          # 戻さず手札に加える:連用否定
            j += 1
            # 〜しなければならない:義務,不是否定
            if (j + 1 < n and self.word(tokens[j - 1]) == "なければ"
                    and self.word(tokens[j]) == "なら"
                    and self.word(tokens[j + 1]) == "ない"):
                polarity = POL_AFFIRM
                form = "dict"
                j += 2
        aux_cond = False
        if j < n and self.word(tokens[j]) in AUXILIARY:
            # 〜している/〜されている:補助動詞後直接接名詞仍是定語;
            # 〜ていれば/〜てあれば 是条件形
            if self.word(tokens[j]) == "いない":
                polarity = POL_NEG
            aux_cond = self.word(tokens[j]) in CONDITIONAL_FORMS
            form = "cond" if aux_cond else "dict"
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
        conditional = suru_form in CONDITIONAL_FORMS or form == "cond" \
            or aux_cond or (w is not None and w in CONDITIONAL_FORMS)
        return self._finish(tokens, head, i, j, action, polarity, form, passive,
                            fold, clause_start, conditional)

    def _topic_action(self, tokens, i, clause_start):
        """裸 できる/できない 的主題(は 前的名詞)是動作名詞時回它的動作名。"""
        for k in range(i - 1, clause_start, -1):
            if tokens[k] != "p:は":
                continue
            head = self.word(tokens[k - 1])
            if head == "発動" and k - 3 >= clause_start and tokens[k - 2] == "p:の" \
                    and tokens[k - 3].startswith("d:この:"):
                return None           # このカードの発動は手札からもできる
            if head == "召喚":
                return self._method_prefix(tokens, k - 2, clause_start)[0] + "召喚"
            if head == "効果":
                return "できる"       # 効果は１ターンに１度しかできない:述語就是 できる
            if head in SAHEN_NOUNS:
                return head
            break
        # 攻撃宣言もできない/特殊召喚ができない:も/が 前的動作名詞
        if i - 2 >= clause_start and tokens[i - 1] in ("p:も", "p:しか", "p:が"):
            head = self.word(tokens[i - 2])
            if head == "宣言" and i - 3 >= clause_start \
                    and self.word(tokens[i - 3]) == "攻撃":
                return "攻撃宣言"
            if head == "召喚":
                return self._method_prefix(tokens, i - 3, clause_start)[0] + "召喚"
            if head in SAHEN_NOUNS:
                return head
        return None

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
        if j < n and self.word(tokens[j]) in AUXILIARY and j + 1 < n \
                and self.word(tokens[j + 1]) in NOMINALIZERS:
            j += 1                    # 〜としている場合
            form = "dict"
        if j < n and self.word(tokens[j]) in NOMINALIZERS:
            nominalizer = self.word(tokens[j])
            j += 1
        elif form not in ("te", "stem", "cond") and j < n \
                and self.is_noun_like(tokens[j]):
            return None               # 定語:動詞直接修飾後面的名詞
        elif form in ("dict", "past", "neg") and j + 1 < n and tokens[j] == "、" \
                and self.is_noun_like(tokens[j + 1]):
            return None               # 「X」を除く、…モンスター:隔讀點的定語
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
                # 助詞後接 の(への戦闘ダメージ/EXデッキからの特殊召喚/１～６までの)
                # 是修飾,留在片語裡;に対して(對…)整組不是論元
                if p != "の" and k + 1 < stop and tokens[k + 1] == "p:の":
                    cur.append(t)
                    continue
                # 後綴助詞後接格助詞(１体のみを):不切;〜とは(そのモンスターとは
                # 種族が異なる)的 は 是定語子句的主題,不切
                if p in CASE_SUFFIX and k + 1 < stop and token_kind(
                        tokens[k + 1]) == "particle" and tokens[k + 1][2:] in CASE_ROLE:
                    continue
                if p == "は" and cur and cur[-1] == "p:と":
                    cur.append(t)
                    continue
                # 〜としている:として+補助動詞 是一個述語(定語用法留在片語裡)
                if (p == "として" and k + 1 < stop
                        and self.word(tokens[k + 1]) in AUXILIARY):
                    cur.append(t)
                    continue
                if p in CASE_ROLE and not cur:
                    continue              # 開頭副詞被剝掉後的裸助詞(このターンに)
                # 通常召喚に加えて:慣用,整組不是論元
                if (p == "に" and k + 1 < stop and self.word(tokens[k + 1]) == "加えて"
                        and cur and self.word(cur[-1]) == "召喚"):
                    out.append(["に加えて", cur, hard])
                    cur, hard = [], False
                    k += 1
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
                if p == "で" and cur and (token_kind(cur[-1]) == "quant" or (
                        token_kind(cur[-1]) == "lex"
                        and self.lex.closed_of[cur[-1]] == "種族")) and any(
                            tokens[m] == "p:の" for m in range(k + 1, min(stop, k + 4))):
                    cur.append(t)         # 種族で属性の:並列修飾
                    continue
                if p == "に" and cur and self.word(cur[-1]) in MANNER_NI:
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
                    # 裸數字後面不是量詞(１ターンに 的 １)不算數量
                    if lead and token_kind(cur[lead - 1]) == "num":
                        lead = 0
                    if 0 < lead < len(cur) and out and out[-1][0] == "を":
                        out[-1][1] = out[-1][1] + [
                            t for t in cur[:lead]
                            if self.word(t) not in ("全て", "それぞれ")]
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
                elif p == "と" and k + 1 < stop and self.word(tokens[k + 1]) == "戦闘":
                    out.append(["と(共同)", cur, hard])   # モンスターと戦闘を行う
                    cur, hard = [], False
                elif p in COORDINATORS or p == "の":
                    cur.append(t)
                continue
            if kind == "punct":
                if t == "、":
                    # 定語動詞後的讀點(「X」を除く、…モンスター)在名詞片語裡;
                    # 卡名列舉的讀點(「A」、「B」、「C」モンスター)也是
                    if cur and self._predicate_lemma(cur, len(cur) - 1) is not None:
                        continue
                    if (cur and token_kind(cur[-1]) == "name" and k + 1 < stop
                            and token_kind(tokens[k + 1]) == "name"):
                        continue
                    if k + 1 < stop and tokens[k + 1] in ("p:または", "p:及び"):
                        continue
                    if cur and cur[-1] == "p:の":
                        continue          # そのモンスター以外の、…
                    if cur:
                        out.append([None, cur, hard])
                    cur, hard = [], True
                elif t == "：":
                    # ●選項標籤「●…：」:標籤不是論元,也是硬邊界
                    out.append(["：", cur, hard])
                    cur, hard = [], True
                elif t in PUNCT_IN_PHRASE:
                    cur.append(t)
                continue
            # 片語開頭的副詞/接續詞/このターン 不屬論元
            if not cur and (self.word(t) in LEADING_ADVERBS or (
                    t.startswith("d:") and self.word(t.split(":", 2)[2]) == "ターン")):
                continue
            cur.append(t)
        if cur:
            out.append([None, cur, hard])
        return out

    def _predicate_lemma(self, chunk, k):
        """chunk[k] 是定語位置的述語時回它的詞元(含 た/いる 尾往前找動詞)。"""
        w = self.word(chunk[k])
        if w is None:
            return None
        if w in TAILS or w in AUXILIARY:
            for m in range(k - 1, -1, -1):
                v = self.word(chunk[m])
                if v is None:
                    # 〜としている+名詞:として+いる 是定語(X素材としているモンスター)
                    return "とする" if chunk[m] == "p:として" and w in AUXILIARY \
                        else None
                if v in TAILS or v in AUXILIARY or v in NEGATORS:
                    continue
                if v in SURU_FAMILY:
                    prev = self.word(chunk[m - 1]) if m else None
                    return prev or v
                return self.lex.lemma_of[chunk[m]] if self.lex.is_verb(
                    chunk[m]) else None
            return None
        if w in SURU_FAMILY and w not in NON_ATTRIBUTIVE_SURU:
            prev = self.word(chunk[k - 1]) if k else None
            return prev or w
        if w in NEGATORS and k >= 1 and self.lex.is_verb(chunk[k - 1]):
            return self.lex.lemma_of[chunk[k - 1]]      # レベルを持たない
        if w in NEGATORS or w == "な" or w == "同じ":
            return w
        if self.lex.lemma_of[chunk[k]] in ADJECTIVE_LEMMAS:
            return self.lex.lemma_of[chunk[k]]    # レベルが高いモンスター
        if self.lex.is_verb(chunk[k]) and verb_form(
                w, self.lex.lemma_of[chunk[k]]) not in ("te", "stem", "irrealis"):
            return self.lex.lemma_of[chunk[k]]
        return None

    def _relative_verb(self, chunk, trailing=False):
        """片語含定語動詞(動詞/する家族後直接接名詞)→ 回該定語的詞元;
        前面的片語屬同一名詞片語。連用形/て形不算。trailing:片語尾的動詞也算
        (後面接的是併入動作的名詞:戦闘を行う|攻撃宣言時)。"""
        for k, (a, b) in enumerate(zip(chunk, chunk[1:])):
            if not self.is_noun_like(b):
                continue
            lemma = self._predicate_lemma(chunk, k)
            if lemma is not None:
                return lemma
        if trailing and chunk:
            return self._predicate_lemma(chunk, len(chunk) - 1)
        return None

    def arguments(self, tokens, start, stop, trailing=False):
        """[start, stop) 的論元 → (args, carry):args 是本述語的對象/來源/目的,
        carry 是多個 を 時留給下一個述語的論元(そのモンスターを効果を無効にして
        特殊召喚し:無効にする 只拿最後一個 を,前面的 を 與 から 給 特殊召喚)。"""
        parts = self.chunks(tokens, start, stop)
        merged = []
        for idx, (role, chunk, hard) in enumerate(parts):
            rel = self._relative_verb(chunk, trailing and idx == len(parts) - 1)
            if rel is None and merged and merged[-1][0] == "が" and merged[-1][1] \
                    and self.word(merged[-1][1][-1]) in ATTR_NOUNS \
                    and "p:の" in chunk[:3] and role in ("を", None):
                rel = "が"              # 攻撃力と守備力が|０の悪魔族モンスター
            if rel is not None and merged and not hard:
                # 往前併到讀點或主題(は)為止;特定動詞只吸收自己的格
                scope = RELATIVE_SCOPE.get(rel)
                absorbed = []
                verb_rel = rel not in ("が", "な", "同じ") \
                    and rel not in ADJECTIVE_LEMMAS and rel not in NEGATORS \
                    and rel not in RELATIVE_SCOPE
                taken = set()
                while merged and merged[-1][0] not in NON_ABSORB_ROLES:
                    r, c, h = merged.pop()
                    if scope is not None and (r not in scope or r in taken) or (
                            verb_rel and r == "が" and c
                            and self.word(c[-1]) in ATTR_NOUNS):
                        merged.append([r, c, h])
                        break
                    taken.add(r)
                    absorbed.insert(0, c + (["p:" + r] if r else []))
                    if h or rel == "が":
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
        # 多個 を:只有最後一個屬本述語,前面的(連同其前的 から)留給下一個述語
        carry = {}
        wo_at = [k for k, (role, chunk, _h) in enumerate(joined) if role == "を"]
        if len(wo_at) >= 2:
            cut = wo_at[-2] + 1
            carried, joined = joined[:cut], joined[cut:]
            for role, chunk, _h in carried:
                key = CASE_ROLE.get(role)
                if key and chunk and key not in carry:
                    carry[key] = "".join(self.surface(t) for t in self._trim(chunk))
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
            chunk = self._trim(chunk)
            if not chunk:
                continue
            text = "".join(self.surface(t) for t in chunk)
            args[key] = text if key not in args else args[key] + "、" + text
            last_key = key
        return args, carry

    @staticmethod
    def _trim(chunk):
        """片語兩端不成對的括弧是註記邊界,不屬論元字面。"""
        while chunk and chunk[0] in ("（", "）") and (
                chunk[0] == "）" or chunk.count("（") > chunk.count("）")):
            chunk = chunk[1:]
        while chunk and chunk[-1] in ("（", "）") and (
                chunk[-1] == "（" or chunk.count("）") > chunk.count("（")):
            chunk = chunk[:-1]
        return chunk

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
    def _option_of_sentence(self, tokens, sentence):
        """句子以 ● 開頭時回它的標籤值(「●自分ターン：」冒號前的字面;沒有標籤時
        "");不是選項句回 None。"""
        start, end = sentence
        if start >= end or tokens[start] != OPTION:
            return None
        label = []
        for k in range(start + 1, end):
            t = tokens[k]
            if t == "：":
                text = "".join(label)
                return text if 0 < len(text) <= LABEL_MAX_CHARS else ""
            if t in ("。", OPTION):
                break
            label.append(self.surface(t))
        return ""

    def frames_of_tokens(self, tokens, text=None, extra=False, card_type=None):
        """一句效果句的詞序列 → 框架清單(動作框架與約束框架混排、依原文位置排序)。
        text 是原文(約束框架的對象欄用它取回 ①② 這類分詞器丟掉的字);extra 標
        效果外文本(召喚條件、素材行只在效果外文本認);card_type 是卡片子類型
        (素材框架的召喚法)。"""
        n = len(tokens)
        offsets = self.char_offsets(text, tokens, self.lex.surface_of) \
            if text is not None else None

        def text_of(start, end):
            """詞序列範圍的原文字面(對不回原文時退回 token 字面相連)。從前一個 token
            的結尾起算,分詞器丟掉的圈號(②の効果 的 ②)才留得住;呼叫端自己去頭尾。"""
            if offsets is not None and start < end <= len(offsets):
                lead = offsets[start - 1][1] if start else offsets[0][0]
                return text[lead:offsets[end - 1][1]]
            return "".join(self.surface(t) for t in tokens[start:end])
        sentences = []
        start = 0
        for k, t in enumerate(tokens):
            if t == "。":
                sentences.append((start, k + 1))
                start = k + 1
            elif t == OPTION and k > start:      # 選項邊界:● 開新的一句
                sentences.append((start, k))
                start = k
        if start < n:
            sentences.append((start, n))

        # 選項:第 n 個 ● 起的句子都屬選項 n,標籤取自 ● 句自己
        option_of, label_of = {}, {}
        option, label = None, None
        for s_idx, sentence in enumerate(sentences):
            found = self._option_of_sentence(tokens, sentence)
            if found is not None:
                option = (option or 0) + 1
                label = found or None
            option_of[s_idx], label_of[s_idx] = option, label

        anchors_by_sentence = []
        for s_start, s_end in sentences:
            anchors = []
            clause_start = s_start
            i = s_start
            while i < s_end:
                a = self.anchor_at(tokens, i, clause_start) \
                    if tokens[i] not in ("。", OPTION) else None
                if a is None:
                    i += 1
                    continue
                a["clause_start"] = clause_start
                # て形/連用形子句後面緊接定語動詞+名詞(〜を素材としてX召喚した
                # モンスター):整段是名詞片語,不是動作
                if a["form"] in ("te", "stem") and self._inside_relative(
                        tokens, a["end"], s_end):
                    i = a["tail"]
                    continue
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

        # 發動句:以 発動できる/発動する 收尾(括弧外、後接 。/（ 或句尾)的句子都是
        # (●選項各有自己的發動句);この効果は…発動できる 的速度註記除外
        marker_of = {}
        for s_idx, anchors in enumerate(anchors_by_sentence):
            s_start, s_end = sentences[s_idx]
            if self._topic_is_this_effect(tokens, sentences[s_idx]):
                continue
            for k, a in enumerate(anchors):
                if (a["action"] == "発動" and a["polarity"] != POL_NEG
                        and a["nominalizer"] is None
                        and depth_at[a["verb_at"]] == 0
                        and (a["end"] >= s_end - 1
                             or tokens[a["end"]] in ("。", "（"))):
                    m_args, _c = self.arguments(tokens, a["clause_start"],
                                                a["head"])
                    if "goal" in m_args:
                        continue
                    marker_of[s_idx] = k
                    break

        frames = []
        for s_idx, anchors in enumerate(anchors_by_sentence):
            marker_idx = marker_of.get(s_idx)
            in_activation = marker_idx is not None
            # 約束框架(constraints.py):由句型認出;被吃掉範圍內的錨點不出動作框架
            found, consumed = self.finder.find(
                tokens, sentences[s_idx], anchors, marker_idx, depth_at,
                extra=extra, card_type=card_type, text_of=text_of)
            for fr in found:
                span = fr["span"]
                fr.update({"kind": KIND_CONSTRAINT, "sentence": s_idx,
                           "option": option_of[s_idx], "label": label_of[s_idx],
                           "clause": " ".join(self.surface(t)
                                              for t in tokens[span[0]:span[1]])})
                frames.append(fr)
            # 「この効果は…発動できない/発動できる」整句是效果本身的註記(速度/
            # 時機限制),句內的條件子句也不是這張卡的動作
            if self._topic_is_this_effect(tokens, sentences[s_idx]) and any(
                    self.word(t) == "発動"
                    for t in tokens[sentences[s_idx][0]:sentences[s_idx][1]]):
                continue
            # 條件鏈:發動句裡條件子句之前的子句都是條件;處理句裡緊接條件子句的
            # 連用/て形子句(存在し、…場合)也是條件
            cond_after = [False] * len(anchors)
            seen = False
            limit = marker_idx - 1 if in_activation else len(anchors) - 1
            s_end = sentences[s_idx][1]
            for k in range(limit, -1, -1):
                nxt_head = anchors[k + 1]["head"] if k + 1 < len(anchors) else s_end
                baai_ahead = anchors[k]["action"] in STATE_LEMMAS and any(
                    self.word(t) in ("場合", "時")
                    for t in tokens[anchors[k]["tail"]:nxt_head])
                cond_after[k] = seen if in_activation else baai_ahead or (
                    k + 1 < len(anchors) and anchors[k + 1]["conditional"]
                    and (anchors[k]["action"] in STATE_LEMMAS
                         or anchors[k]["form"] == "te"
                         and anchors[k]["polarity"] == POL_AFFIRM
                         and "、" not in tokens[anchors[k]["end"]:anchors[k]["tail"]]))
                if anchors[k]["conditional"]:
                    seen = True
            carry = {}
            for k, a in enumerate(anchors):
                if any(lo <= a["verb_at"] < hi for lo, hi in consumed):
                    continue
                is_marker = in_activation and k == marker_idx
                before_marker = in_activation and k < marker_idx \
                    and depth_at[a["verb_at"]] == 0
                args, next_carry = self.arguments(
                    tokens, a["clause_start"], a["head"] - a["fold"],
                    trailing=a["form"] == "noun" or a["fold"] > 0)
                for key, value in carry.items():
                    args.setdefault(key, value)
                carry = next_carry
                if a["action"].endswith("なる") and "source" in args:
                    carry["source"] = args.pop("source")   # 〜からリリースし
                # 発動 本身:發動句的收尾(このカードを発動できる)、速度註記、
                # 〜するために 都不是動作;有別的對象/來源(〜を発動できない、
                # デッキから「X」を発動できる)才成框架
                if a["action"] == "発動" and a["polarity"] != POL_NEG and (
                        a["nominalizer"] in (None, "ため")
                        and not ("object" in args or "source" in args
                                 or "goal" in args)
                        or a["nominalizer"] == "ため"
                        or args.get("object") in ("このカード", "この効果")
                        or a["nominalizer"] is None
                        and (args.get("object") or "").endswith("効果")):
                    continue
                if a["conditional"] or a["action"] == "対象とする":
                    position = POS_COND
                elif is_marker:
                    position = POS_EFFECT
                elif before_marker:
                    if (a["passive"] or a["action"] in STATE_LEMMAS
                            or cond_after[k]
                            or a["form"] in ("dict", "past", "neg")
                            and a["nominalizer"] != "事"
                            or a["action"] in ("選択", "選ぶ")
                            and args.get("source", "").startswith("以下")):
                        position = POS_COND
                    else:
                        position = POS_COST
                elif cond_after[k]:
                    position = POS_COND
                else:
                    position = POS_EFFECT
                span = (a["clause_start"], a["end"])
                clause = " ".join(self.surface(t) for t in tokens[span[0]:span[1]])
                # 「・」並列的述語名詞(召喚・特殊召喚した)與召喚法鏈(儀式・融合・
                # S・X召喚):各出一框架,共用後綴
                coordinated = self._coordinated_actions(tokens, a)
                if "・" in a["action"] and a["action"].endswith("召喚"):
                    methods = a["action"][:-2].split("・")
                    coordinated += [m + "召喚" for m in methods[:-1]]
                    a["action"] = methods[-1] + "召喚"
                for action in coordinated + [a["action"]]:
                    frames.append({"kind": KIND_ACTION, "sentence": s_idx,
                                   "action": action,
                                   "object": args.get("object"),
                                   "source": args.get("source"),
                                   "goal": args.get("goal"),
                                   "position": position,
                                   "polarity": a["polarity"],
                                   "option": option_of[s_idx],
                                   "label": label_of[s_idx],
                                   "span": list(span), "clause": clause})
        # 依原文位置混排;同起點時約束框架在前(穩定排序保住並列述語的順序)
        frames.sort(key=lambda f: (f["sentence"], f["span"][0],
                                   f["kind"] != KIND_CONSTRAINT))
        return frames

    def _topic_is_this_effect(self, tokens, sentence):
        """句子以「この効果は」為主題(この効果は相手ターンでも発動できる);括弧裡的
        註記(…発動できる（この効果は相手ターンでも発動できる）)不算本句的主題。"""
        start, end = sentence
        depth = 0
        for k in range(start, end):
            t = tokens[k]
            if t == "（":
                depth += 1
            elif t == "）":
                depth = max(0, depth - 1)
            elif (depth == 0 and t.startswith("d:この:")
                  and self.word(t.split(":", 2)[2]) == "効果"
                  and k + 1 < end and tokens[k + 1] == "p:は"):
                return True
        return False

    def _inside_relative(self, tokens, start, stop):
        """start 起到下一個助詞/句讀前,出現「定語動詞+名詞」→ 前面的子句在
        名詞片語裡。"""
        for k in range(start, min(stop, start + 8) - 1):
            t = tokens[k]
            if token_kind(t) in ("particle", "punct"):
                return False
            w = self.word(t)
            if w is None:
                continue
            # 〜を素材として持っている、元々の種族が…のXモンスター:いる 後隔讀點
            # 接名詞片語也是定語(round6)
            if w in ("いる", "いた", "いない") and tokens[k + 1] == "、" \
                    and k + 2 < stop and self.is_noun_like(tokens[k + 2]):
                return True
            # 補助動詞 いる/いた 收尾也是定語(〜を素材として持っているXモンスター、
            # 〜X素材としているモンスター;round5)
            attributive = (w in SURU_FAMILY and w not in NON_ATTRIBUTIVE_SURU) \
                or (w in AUXILIARY and w not in CONDITIONAL_FORMS) \
                or (self.lex.is_verb(t) and verb_form(
                    w, self.lex.lemma_of[t]) in ("dict", "past"))
            if attributive and self.is_noun_like(tokens[k + 1]):
                return True
        return False

    def _coordinated_actions(self, tokens, a):
        """錨點前以 ・ 並列的述語名詞(召喚・|特殊召喚、特殊召喚・|リバース),
        與 または 並列的素材(融合素材または|リンク素材として)。"""
        out = []
        k = a["head"] - 1
        if a["action"].endswith("素材とする"):
            while k - 1 >= a["clause_start"] and tokens[k] in ("p:または", "・") \
                    and (self.word(tokens[k - 1]) or "").endswith("素材"):
                prefix, m = self._method_prefix(tokens, k - 2, a["clause_start"])
                out.insert(0, prefix + self.word(tokens[k - 1]) + "とする")
                k = m - 1
            return out
        while k - 1 >= a["clause_start"] and tokens[k] == "・":
            w = self.word(tokens[k - 1])
            if w == "召喚":
                prefix, m = self._method_prefix(tokens, k - 2, a["clause_start"])
                out.insert(0, prefix + "召喚")
                k = m - 1
            elif w in SAHEN_NOUNS:
                out.insert(0, w)
                k -= 2
            else:
                break
        return out

    def extract(self, text, context="", extra=None, card_type=None):
        if extra is None:
            # 沒說是不是效果外文本時看字首:編號效果(①：/●)是效果,其餘當效果外
            extra = not (text[:1] in (OPTION,) or 0x2460 <= ord(text[:1] or " ") < 0x2500)
        return self.frames_of_tokens(self.tokenizer.tokenize(text, context),
                                     text=text, extra=extra, card_type=card_type)


_DEFAULT = None


def default_extractor():
    global _DEFAULT
    if _DEFAULT is None:
        with open(LEXICON, encoding="utf-8") as f:
            _DEFAULT = FrameExtractor(json.load(f))
    return _DEFAULT


def extract(text, context="", extra=None, card_type=None):
    """接縫:一句效果句原文(整段,含 ● 選項;帶同卡同段上文;可選 效果外文本 旗標與
    卡片子類型)→ 框架清單(動作框架與約束框架混排)。"""
    return default_extractor().extract(text, context, extra, card_type)


def main():
    extractor = default_extractor()
    with open(TOKENS, encoding="utf-8") as f:
        sentences = json.load(f)
    out = []
    for s in sentences:
        # 效果外文本看效果類型(含子效果句的領起句雖算效果層,仍是效果外文本的句型)
        frames = extractor.frames_of_tokens(
            s["tokens"], text=s["text_ja"], extra=s["kind"] == "效果外文本")
        for k, fr in enumerate(frames):
            fr["order"] = k
        out.append({"card": s["card"], "section": s["section"],
                    "index": s["index"], "stratum": s["stratum"],
                    "parts": s["parts"], "frames": frames})
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
        f.write("\n")
    stats, _position, _polarity, _actions, constraints = frame_stats(out)
    for key in ("effect", "extra"):
        st = stats[key]
        print("%s: 有框架的句 %d / %d(%.2f%%);動作框架 %d、約束框架 %d" % (
            key, st["covered"], st["records"],
            100.0 * st["covered"] / max(1, st["records"]),
            st["frames"] - st["constraints"], st["constraints"]))
    print("約束框架分佈:" + "、".join(
        "%s %d" % (k, v) for k, v in sorted(constraints.items())))
    print("框架總數 %d;已寫出 %s" % (
        sum(st["frames"] for st in stats.values()), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
