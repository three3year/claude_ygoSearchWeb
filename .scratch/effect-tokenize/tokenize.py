"""效果文分詞器(票 effect-tokenize#03):領域詞典+最長匹配,純 Python 零依賴。

語料:三級分類的**新格式新卡**層(script/text_format/classify.py 的 TIER_NEW,
與 build_report.py 同一套日期合併邏輯),逐段對上 data/tag_cards.json 的
clauses,取每句 text_ja。效果外文本(kind=效果外文本,素材行/使用次數限制等)
與效果句分開標 stratum,報表端分開統計。

切分慣例(第一版,詳 conventions.md;裁定點清單也在該檔):
- 「卡名」→ NAME token(帶原文);『』非卡名引用,照原文處理(裁定點)
- 數字(半形/全形/漢數字+つ体枚度回組量詞)→ NUM token(帶正規化後的數值);
  NUM 後緊接的量詞(つ/体/枚/度/回/組)→ 量詞 token
- 助詞(に/で/を/は/が/と/の/へ/も/や/か/から/まで/より/など/として/または/
  及び/しか/のみ/だけ/ずつ)→ 獨立 token(封閉類,不占詞典 ID)
- 句讀(。、:・()『』)→ 邊界,不編 ID 但保留在序列裡(模板的結構訊號);
  圈號(①②…)、●、空白 → 靜默邊界(丟棄)
- 詞典最長匹配;匹配不到的連續段合併成 OOV token(前一字是平假名時 OOV 段
  不被助詞切斷——活用殘尾不可誤斷成助詞)

token 編碼(tokens.json 的 tokens 陣列,一律字串):
    "W0123"      詞典詞(lexicon.json 的 ID)
    "d:この:W0123"  指示綁定(R5 裁定:この/その+詞典詞一個 token,
                 模板不收斂;その後 整詞、裸指示詞留 OOV)
    "p:に"       助詞
    "NAME:青眼の白龍"  卡名引用
    "NUM:1000"   數字(數值正規化:全形→半形、漢數字→阿拉伯)
    "c:体"       NUM 後的量詞
    "r:2:5:体"    數字範圍(２～５体,含兩端;量詞可空)
    "s:通常:魔法"  列舉前項省略(通常・速攻魔法 的 通常,顯示 通常(魔法))
    "?:xxx"      OOV 段
    "。"/"、"/…  句讀邊界(照原字)

決定性:卡片依密碼排序、句依 clauses 原序;同一份輸入重跑逐位元組相同。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/tokenize.py
"""
import json
import os
import re
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(_ROOT, "script", "text_format"))
from classify import TIER_NEW, classify_card  # noqa: E402
from ocg_dates import align_ocg_dates, load_ocg_dates  # noqa: E402
from official_dates import merge_aligned_dates  # noqa: E402

CARDS = os.path.join(_ROOT, "data", "cards.json")
TAG_CARDS = os.path.join(_ROOT, "data", "tag_cards.json")
DATES = os.path.join(_ROOT, "data", "sources", "ocg-dates.json")
OFFICIAL_DATES = os.path.join(_ROOT, "data", "sources", "official-dates.json")
LEXICON = os.path.join(_HERE, "lexicon.json")
OUT = os.path.join(_HERE, "tokens.json")

# ── 封閉類(與 extract_seed.py 的切分慣例同一套)──
# R7 裁定(2026-10-07):だけ/ずつ/か 比照 しか 收入;か 排在 から/しか 之後
# (tuple 依序比對,長的先中)
PARTICLES = ("として", "または", "から", "まで", "より", "など", "及び",
             "しか", "のみ", "だけ", "ずつ", "に", "で", "を", "は", "が",
             "と", "の", "へ", "も", "や", "か")
# か 的護欄:後接 れ/ず/っ 是動詞活用(置かれ/行かず/なかった),不當助詞
_KA_VERB_NEXT = "れずっ"
# 組:R10 裁定(2026-10-07),一組 → NUM:1+c:組;種類:●標籤檢查(2026-10-07),
# ３種類以上 比照 ３体以上 綁成數量約束。長的在前(依序比對)
# ヵ所/個:2026-10-07 站主補詞時併入(１ヵ所、１２個)
COUNTERS = ("種類", "ヵ所", "つ", "体", "枚", "度", "回", "組", "個")
DEMONSTRATIVES = ("この", "その")
COMPARATORS = ("以下", "以上", "未満")
OPERATORS = ("＋", "×")   # 詞典詞(manual),但不當比較詞綁定的前詞
ATTRIBUTES = "闇光地水炎風神"   # 七值封閉集合(屬性裁定)
# 屬性字成詞的前瞻條件:後面(可隔著・列舉)最終接到 属性——
# 擋 墓地/水族 這類含同字的詞被誤切
_ATTR_CHAIN = re.compile(r"[闇光地水炎風神](?:・[闇光地水炎風神])*属性")
# 召喚法七法(R9 裁定):成詞條件=後接 素材/モンスター/召喚,或 ・並列鏈
# (融合・S・X・P・L);並列尾項由「前一格是法+・」回看補救
# A:アドバンス召喚 的縮寫(A召喚,2026-10-07 站主裁定加入,召喚法八法)
_METHOD = r"(?:リンク|融合|儀式|[SXPLAＳＸＰＬＡ])"
# 全形召喚法字母(融合・Ｓ・Ｘ)輸出統一成半形
_FULL_ASCII = {"Ｓ": "S", "Ｘ": "X", "Ｐ": "P", "Ｌ": "L", "Ａ": "A"}
_METHOD_RE = re.compile(_METHOD)
_METHOD_CHAIN = re.compile(
    _METHOD + r"(?:・" + _METHOD + r")*(?:素材|モンスター|召喚|効果)"
    r"|" + _METHOD + r"(?:・" + _METHOD + r")+")
# ～:數字～數字 綁成範圍 token(r:);其餘(「No.101」～「No.107」)當連接符號
PUNCT_KEEP = "。、：・（）『』／～"
# 列舉項的切分邊界(・鏈的一項不跨這些字)
_ITEM_STOP = set("。、：・（）『』／「」●\n 　") | {chr(c) for c in range(0x2460, 0x2500)}
# ●選項標籤「●…：」:標籤裡的值所屬類別寫在前文(2026-10-07 站主裁定)
_LABEL = re.compile(r"●([^●：\n]{1,30})：")
_LABEL_METHOD_CTX = re.compile(r"リンク|融合|儀式|[SXPLAＳＸＰＬＡ]|種類")
# 圈號與列點是段落標號、空白是排版——靜默邊界,不入序列
SILENT = set("● 　\t\n") | {chr(c) for c in range(0x2460, 0x2500)}

_DIGITS = "0123456789０１２３４５６７８９"
_KANJI_NUM = "一二三四五六七八九十"
_KANJI_VAL = {c: v for v, c in enumerate(_KANJI_NUM[:9], start=1)}


def _is_hira(ch):
    return "ぁ" <= ch <= "ゟ"


def _name_char(ch):
    """計數器名可含的字:非平假名、非句讀/靜默邊界/引號/圈號。"""
    return not (_is_hira(ch) or ch in PUNCT_KEEP or ch in SILENT
                or ch in "「」")


def _num_value(run):
    """數字字串 → 正規化數值(全形→半形、漢數字→阿拉伯)。"""
    if run[0] in _DIGITS:
        return int("".join(str(_DIGITS.index(c) % 10) for c in run))
    # 漢數字(語料只有簡單形:一〜十、十二 這類)
    total = 0
    if "十" in run:
        head, _, tail = run.partition("十")
        total = (_KANJI_VAL.get(head, 1) if head else 1) * 10
        if tail:
            total += _KANJI_VAL.get(tail, 0)
        return total
    value = 0
    for c in run:
        value = value * 10 + _KANJI_VAL.get(c, 0)
    return value


class Tokenizer:
    def __init__(self, lexicon_entries):
        self.id_of = {e["surface"]: e["id"] for e in lexicon_entries}
        self.surface_of = {e["id"]: e["surface"] for e in lexicon_entries}
        self.by_first = {}
        for e in lexicon_entries:
            self.by_first.setdefault(e["surface"][0], []).append(e["surface"])
        for first in self.by_first:
            # 長的在前(最長匹配);同長依碼位,決定性
            self.by_first[first].sort(key=lambda s: (-len(s), s))

    def _lex_match(self, text, i):
        for surface in self.by_first.get(text[i], ()):
            if text.startswith(surface, i):
                return surface
        return None

    def _plain_surface(self, token):
        """可併進計數器名的 token 的原文字面(詞典詞/OOV/屬性字/召喚法);
        其餘類別回 None。"""
        if token.startswith("W"):
            return self.surface_of[token]
        if token[:2] in ("?:", "a:", "m:"):
            return token[2:]
        return None

    @staticmethod
    def _counter_at(text, j):
        return next((c for c in COUNTERS if text.startswith(c, j)), "")

    def _emit_num(self, tokens, text, i, value, counter):
        """數字(+量詞)落 token;後接比較詞時綁成數量約束 q: token。

        比較詞裁定(2026-10-01 站主):無量詞且前一 token 是詞典詞時前詞
        一併綁入(レベル〈n〉以下 屬性約束);有量詞則前詞不綁
        (モンスター|〈n〉体以上 個數約束)。回位置 i(已消耗的下一格)。
        """
        cmp_word = next((c for c in COMPARATORS
                         if text.startswith(c, i)), None)
        if cmp_word:
            word = ""
            # 運算符號(＋/×)不是屬性名:Pスケール×〈n〉以上 的 × 不綁入
            if (not counter and tokens and tokens[-1].startswith("W")
                    and self.surface_of[tokens[-1]] not in OPERATORS):
                word = tokens.pop()
            tokens.append("q:%s:%d:%s:%s" % (word, value, counter, cmp_word))
            return i + len(cmp_word)
        tokens.append("NUM:%d" % value)
        if counter:
            tokens.append("c:" + counter)
        return i

    def _elided_head(self, text, i):
        """列舉前項省略(2026-10-07 站主裁定):・鏈的一項 X 不是詞典詞,但補上
        鏈尾詞 W 的尾巴 T 能組成詞典詞(通常・速攻魔法 的 通常+魔法=通常魔法)
        → 回 (X, T);否則 None。鏈尾詞取最後一項開頭的最長匹配。呼叫端只在
        token 邊界(OOV 段未開)呼叫;X 從 i 起算到下一個列舉邊界。"""
        j = i
        while j < len(text) and text[j] not in _ITEM_STOP:
            j += 1
        head = text[i:j]
        if not head or j >= len(text) or text[j] != "・" or head in self.id_of:
            return None
        k = j + 1
        while True:                       # 跳過中段各項,停在最後一項開頭
            m = k
            while m < len(text) and text[m] not in _ITEM_STOP:
                m += 1
            if m < len(text) and text[m] == "・":
                k = m + 1
                continue
            break
        last = self._lex_match(text, k) if k < len(text) else None
        if not last:
            return None
        for cut in range(1, len(last)):
            if head + last[cut:] in self.id_of:
                return head, last[cut:]
        return None

    def tokenize(self, text, context=""):
        """一句 text_ja → token 字串陣列。context 是同卡同段前幾句的原文,
        ●選項標籤據此判斷標籤值所屬類別。"""
        # ●選項標籤的內容範圍(原文座標;下面剝段首時一併平移)
        labels = []
        for m in _LABEL.finditer(text):
            before = context + text[:m.start()]
            labels.append((m.start(1), m.end(1), "属性" in before,
                           bool(_LABEL_METHOD_CTX.search(before))))
        shift = 0
        # 段首圈號標號(「①：」)剝除——那是段落索引,不是句子內容
        while text and (text[0] in SILENT or 0x2460 <= ord(text[0]) < 0x2500):
            text = text[1:]
            shift += 1
        if text.startswith("："):
            text = text[1:]
            shift += 1
        labels = [(a - shift, b - shift, attr, meth)
                  for a, b, attr, meth in labels]
        tokens = []
        oov = ""

        def close_oov():
            nonlocal oov
            if oov:
                tokens.append("?:" + oov)
                oov = ""

        i = 0
        n = len(text)
        w_end = -1          # 最後一個詞典詞 token 的結束位置(計數器名回折用)
        while i < n:
            ch = text[i]
            # 1. 卡名引用「…」(配對含巢狀)
            if ch == "「":
                depth, j = 1, i + 1
                while j < n and depth:
                    if text[j] == "「":
                        depth += 1
                    elif text[j] == "」":
                        depth -= 1
                    j += 1
                if depth == 0:
                    close_oov()
                    tokens.append("NAME:" + text[i + 1:j - 1])
                    i = j
                    continue
            # 2. 邊界
            if ch in SILENT:
                close_oov()
                i += 1
                continue
            if ch in PUNCT_KEEP:
                close_oov()
                tokens.append(ch)
                i += 1
                continue
            # 3. 數字 → NUM(+量詞)(+比較詞綁定,見 _emit_num)
            if ch in _DIGITS:
                j = i
                while j < n and text[j] in _DIGITS:
                    j += 1
                close_oov()
                # 數字範圍(2026-10-07 裁定):２～５ → r:2:5:(量詞),含兩端
                if j + 1 < n and text[j] == "～" and text[j + 1] in _DIGITS:
                    k = j + 1
                    while k < n and text[k] in _DIGITS:
                        k += 1
                    counter = self._counter_at(text, k)
                    tokens.append("r:%d:%d:%s" % (
                        _num_value(text[i:j]), _num_value(text[j + 1:k]),
                        counter))
                    i = k + len(counter)
                    continue
                counter = self._counter_at(text, j)
                i = self._emit_num(tokens, text, j + len(counter),
                                   _num_value(text[i:j]), counter)
                continue
            # ？:攻撃力/守備力 的未定值(攻？/守０、攻撃力が？以外;2026-10-07
            # 站主裁定)→ NUM:?(語料 18 處全是這個用法)
            if ch == "？":
                close_oov()
                tokens.append("NUM:?")
                i += 1
                continue
            if ch in _KANJI_NUM:
                j = i
                while j < n and text[j] in _KANJI_NUM:
                    j += 1
                counter = self._counter_at(text, j)
                if counter:
                    close_oov()
                    i = self._emit_num(tokens, text, j + len(counter),
                                       _num_value(text[i:j]), counter)
                    continue
                # 漢數字後無量詞:不當數字(一番上 的 一),落回詞典/OOV
            # 3.9 計數器名綁定(2026-10-01 裁定):〈名〉+カウンター 一格,
            # 名收斂比照〈卡名〉;カウンター罠(反擊陷阱)除外;無名字的
            # 裸 カウンター 落回詞典詞
            if (text.startswith("カウンター", i)
                    and not text.startswith("カウンター罠", i)):
                name = ""
                if oov:
                    # 名=OOV 段尾端的非平假名連續段(活用殘尾不綁進名字)
                    j = len(oov)
                    while j > 0 and not _is_hira(oov[j - 1]):
                        j -= 1
                    name, oov = oov[j:], oov[:j]
                    close_oov()
                # 名的全長=原文 カウンター 前緊鄰的非平假名連續段(2026-10-07
                # 站主裁定):名字被詞典切開時(方|界、万|倍)往前把整段併回;
                # 平假名結尾的詞典詞是活用形(する/いた),不併
                run = i
                while run > 0 and _name_char(text[run - 1]):
                    run -= 1
                popped = []
                while len(name) < i - run and tokens:
                    piece = self._plain_surface(tokens[-1])
                    if (piece is None or any(_is_hira(c) for c in piece)
                            or len(name) + len(piece) > i - run):
                        break
                    popped.append(tokens.pop())
                    name = piece + name
                if name != text[i - len(name):i] or len(name) != i - run:
                    # 拼不回原文整段:還原,只留 OOV 側取到的名
                    for t in reversed(popped):
                        tokens.append(t)
                        name = name[len(self._plain_surface(t)):]
                    if (not name and w_end == i and tokens
                            and tokens[-1].startswith("W")
                            and not _is_hira(self.surface_of[tokens[-1]][-1])):
                        name = self.surface_of[tokens.pop()]
                if name:
                    tokens.append("k:" + name)
                    i += len("カウンター")
                    continue
            # 3.9x ●選項標籤(2026-10-07 裁定):標籤「●…：」裡以・分隔的值,
            # 單一屬性字(前文提到 属性)→ a:、召喚法名(前文提到召喚法或
            # 種類)→ m:——炎・炎/闇・地/S/融合 這類值所屬類別寫在前文
            label = next((lb for lb in labels if lb[0] <= i < lb[1]), None)
            # 屬性字後接連接詞也算(闇以外/光のみ/光と闇/地または風):
            # 屬性字前是標籤起點、・或助詞,後是標籤終點、・、助詞或 以外
            if label and label[2] and ch in ATTRIBUTES and (
                    i == label[0] or text[i - 1] == "・"
                    or (tokens and tokens[-1].startswith("p:"))):
                rest = text[i + 1:label[1]]
                if (not rest or rest[0] == "・" or rest.startswith("以外")
                        or any(rest.startswith(p) for p in PARTICLES)):
                    close_oov()
                    tokens.append("a:" + ch)
                    i += 1
                    continue
            if label and (i == label[0] or text[i - 1] == "・"):
                end = i
                while end < label[1] and text[end] != "・":
                    end += 1
                item = text[i:end]
                if label[2] and len(item) == 1 and item in ATTRIBUTES:
                    close_oov()
                    tokens.append("a:" + item)
                    i = end
                    continue
                if label[3] and _METHOD_RE.fullmatch(item):
                    close_oov()
                    tokens.append("m:" + _FULL_ASCII.get(item, item))
                    i = end
                    continue
            # 3.95 屬性字(2026-10-01 裁定修訂):屬性字與 属性 拆成兩詞,
            # 列舉形 光・闇属性 → 光|・|闇|属性;属性 歸詞典詞。
            # 衍生物規格括弧(種族・闇・星１)的屬性字也算:後接 ・星 成詞
            # 規格括弧沒有星級的寫法(アンデット族・闇・攻／守０)後接 ・攻 也算
            # (2026-10-07 站主裁定)
            if ch in ATTRIBUTES and (_ATTR_CHAIN.match(text, i)
                                     or text.startswith("・星", i + 1)
                                     or (i and text[i - 1] == "・"
                                         and text.startswith("・攻", i + 1))):
                close_oov()
                tokens.append("a:" + ch)
                i += 1
                continue
            # 3.97 召喚法(R9 裁定):七法 token,法+素材/モンスター/召喚
            # 兩格結構;並列鏈(融合・S・X・P・L)逐法成詞
            m = _METHOD_RE.match(text, i)
            if m and (_METHOD_CHAIN.match(text, i)
                      or (len(tokens) >= 2 and tokens[-1] == "・"
                          and tokens[-2].startswith("m:"))):
                close_oov()
                tokens.append("m:" + _FULL_ASCII.get(m.group(), m.group()))
                i = m.end()
                continue
            # 3.98 列舉前項省略(2026-10-07 裁定):通常・速攻魔法カード 的
            # 通常 → s:通常:魔法(顯示 通常(魔法)),模板不收斂
            elided = self._elided_head(text, i) if not oov else None
            if elided:
                tokens.append("s:%s:%s" % elided)
                i += len(elided[0])
                continue
            # 4. 詞典與助詞跨類最長匹配(R2 後 し 入典,不可吃掉 しか——
            # 助詞較長時助詞優先;OOV 開著且尾字是平假名時助詞照舊不切)
            surface = self._lex_match(text, i)
            # 裸 その 入典(2026-10-07 站主裁定):詞典命中的只是指示詞本身、
            # 後面又接得上詞典詞時,讓給 4.5 的指示綁定(R5 第一款不變)
            if (surface in DEMONSTRATIVES
                    and self._lex_match(text, i + len(surface))):
                surface = None
            particle = None
            if not (oov and _is_hira(oov[-1])):
                particle = next((p for p in PARTICLES
                                 if text.startswith(p, i)), None)
                if (particle == "か" and i + 1 < n
                        and text[i + 1] in _KA_VERB_NEXT):
                    particle = None
            if particle and len(particle) > len(surface or ""):
                close_oov()
                tokens.append("p:" + particle)
                i += len(particle)
                continue
            if surface:
                close_oov()
                tokens.append(self.id_of[surface])
                i += len(surface)
                w_end = i
                continue
            # 4.5 指示綁定(R5):この/その+詞典詞 → 一個 d: token;
            # 接不上詞典詞的裸指示詞照舊落 OOV
            dem = next((d for d in DEMONSTRATIVES
                        if text.startswith(d, i)), None)
            if dem:
                surface = self._lex_match(text, i + len(dem))
                if surface:
                    close_oov()
                    tokens.append("d:%s:%s" % (dem, self.id_of[surface]))
                    i += len(dem) + len(surface)
                    continue
            # 5. 助詞(詞典沒中時)
            if particle:
                close_oov()
                tokens.append("p:" + particle)
                i += len(particle)
                continue
            # 6. OOV 累積
            oov += ch
            i += 1
        close_oov()
        return tokens


def new_tier_sections():
    """TIER_NEW 的 (卡片密碼, section) 集合(與 build_report 同一套日期)。"""
    with open(CARDS, encoding="utf-8") as f:
        cards = json.load(f)
    dates = align_ocg_dates(cards, load_ocg_dates(DATES))
    if os.path.exists(OFFICIAL_DATES):
        fallback = align_ocg_dates(cards, load_ocg_dates(OFFICIAL_DATES))
        dates, _ = merge_aligned_dates(dates, fallback)
    picked = set()
    for card in cards:
        for seg in classify_card(card, dates.get(card["id"])):
            if seg["tier"] == TIER_NEW:
                picked.add((card["id"], seg["section"]))
    return picked


def main():
    with open(LEXICON, encoding="utf-8") as f:
        tokenizer = Tokenizer(json.load(f))
    picked = new_tier_sections()
    with open(TAG_CARDS, encoding="utf-8") as f:
        tag_cards = json.load(f)

    sentences = []
    skipped_no_ja = 0
    for card in sorted(tag_cards, key=lambda c: c["id"]):
        context, context_key = "", None
        for clause in card["clauses"]:
            if (card["id"], clause["section"]) not in picked:
                continue
            if clause["section"] != context_key:   # 上文只取同卡同段
                context, context_key = "", clause["section"]
            text_ja = clause.get("text_ja")
            if not text_ja:
                skipped_no_ja += 1
                continue
            stratum = ("extra" if clause["kind"] == "效果外文本" else "effect")
            sentences.append({
                "card": card["id"],
                "section": clause["section"],
                "index": clause["index"],
                "kind": clause["kind"],
                "stratum": stratum,
                "text_ja": text_ja,
                "tokens": tokenizer.tokenize(text_ja, context),
            })
            context += text_ja

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sentences, f, ensure_ascii=False, indent=0)
        f.write("\n")

    cards_seen = len({s["card"] for s in sentences})
    by_stratum = {"effect": 0, "extra": 0}
    for s in sentences:
        by_stratum[s["stratum"]] += 1
    print("TIER_NEW 段: %d(卡 %d 張)" % (len(picked),
                                           len({c for c, _ in picked})))
    print("分詞句數: %d(效果句 %d / 效果外 %d;卡 %d 張;無 text_ja 略過 %d)"
          % (len(sentences), by_stratum["effect"], by_stratum["extra"],
             cards_seen, skipped_no_ja))
    print("已寫出 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
