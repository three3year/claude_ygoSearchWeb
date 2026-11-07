"""區塊切分:官方 DB 文本 → 區塊列表 + 略過文本。

新式卡依 ①②③ 的編號字元切(筆記 01:①前不一定有換行,所以用字元不用換行);
編號前的前言與舊式無編號卡的全文走同一支(票 09 收成一支):先切成「單位」——句號
(「」『』（）外)與換行處各一句——再把單位分類:素材行(不以句號結尾的開頭行)、
召喚條件句(`_SUMMON_RE`)、次數限制(不記、進略過文本)、效果句;相鄰的效果句依後一句
的開頭決定切不切(spec「區塊切分」的候選清單,照共識集 3,363 張調過:`_NO_CUT_RE`
續前一區塊、`_CUT_RE` 另起區塊、其餘看句首有沒有觸發子句);● 開頭的單位一律續前一區塊
(spec:● 列舉留在區塊內當段樹的分歧)。
硬約束:補足情報的『』引用跨句號時不得切斷——引用跨過的切點一律撤掉。
區塊種類:素材行 → 素材、召喚條件句 → 召喚條件;沒有編號的效果句,魔陷卡的第一個是
卡片發動(舊式魔陷的整段卡文、新式魔陷前言的「このカードを発動するターン、〜」),其餘歸
編號效果——新式怪獸卡前言裡的這種句子(維持コスト、「〜するターン、〜できない」)沒有編號
也不是召喚條件,標「區塊種類判不出」(spec:判不出歸編號效果、標未解析)。
邊界補丁(`data/block_boundaries.json`,站主判過的卡)先讀:一卡一筆、只記官方日文的
區塊子字串、雜湊只算官方日文;雜湊不符(卡文變動)、覆蓋不成立、引用被切斷或格式
不合法時整筆失效、退回規則(同拆句表,ADR-0003)。
靈擺效果取 `pen_effect`,同一套切法、區塊種類固定靈擺效果。
"""
import hashlib
import re

from structure_shape import new_block, unparsed

# 編號字元 ①..⑳ 後一律全形冒號(筆記 01)。
_LABEL_RE = re.compile("[①-⑳]：")
# 次數限制前言:「このカード名の(①②の)効果は１ターンに１度しか使用できない」
# 「このカード名のカードは１ターンに１枚しか発動できない」等;不記(spec)。
_LIMIT_RE = re.compile(
    "^[^。]*?(?:１ターンに[１-９]度|１ターンに[１-９]枚|デュエル中に[１-９]度|デュエル中に[１-９]枚)"
    "[^。]*?(?:しか|まで)(?:使用|発動|適用|特殊召喚)?でき(?:ない|る|ず[^。]*?できない)。?$")
# 「しか/まで」要緊接在「使用/発動/特殊召喚できる」前:「１ターンに１度、融合召喚及び
# 以下の方法でのみ特殊召喚できる」有 １ターンに１度 卻是召喚條件句,不能當次數限制略過。
# 只收單句的行;一行兩句(「X」により降臨。このカード名の…)留給票 09 的句型切。

KIND_UNKNOWN = "區塊種類判不出"
LIMIT_REASON = "次數限制"
CATEGORY_SPELL_TRAP = "魔陷"
KIND_ACTIVATION = "卡片發動"

# ── 舊式無編號卡:單位分類 ──────────────────────────────────
# 召喚條件句:召喚限制、特殊召喚方法、降臨、素材限制、裝備限制、「〜なければならない」。
_SUMMON_RE = re.compile(
    "^(?:このカード|このモンスター)は[^。]*?"
    "(?:通常召喚|特殊召喚|召喚・反転召喚・特殊召喚|召喚・特殊召喚|召喚・セット|通常召喚・セット)"
    "(?:は)?(?:できない|する事ができない|する事はできない|出来ない)。?$"
    "|のみ特殊召喚|でしか特殊召喚|しか特殊召喚できない|でのみ(?:エクストラデッキ|融合デッキ)から"
    "|でのみ[^。]{0,16}?召喚(?:できる|する事ができる|する事が出来る)"
    "|により降臨|降臨させる|降臨する"
    # 票 09 補:「〜場合のみ、EXデッキから特殊召喚できる」「〜の上に重ねてX召喚する事もできる」
    # 「〜場合、このカードは召喚・特殊召喚できない」「〜場合にEXデッキの表側のこのカードはP召喚できる」
    "|のみ、?(?:EXデッキ|エクストラデッキ|手札・墓地|手札|墓地)から特殊召喚できる"
    "|重ねて(?:X|エクシーズ)召喚(?:する事もできる|する事ができる|できる)"
    "|このカードは(?:P|ペンデュラム)召喚できる"
    # 只收 できない:「〜場合、このカードは手札から特殊召喚できる」共識集當效果(票 05/11 的斷言也要它命中)。
    "|場合、このカードは[^。]*?(?:召喚|特殊召喚)できない。?$"
    "|(?:シンクロ|融合|エクシーズ)素材(?:に|とする事は|とする事が|には)できない|素材にできない"
    "|(?:融合|シンクロ)召喚は[^。]*?(?:でしか|のみ)"
    "|装備可能。?$"
    "|(?:召喚|素材|セット|リリース)[^。]*?なければならない。?$"
    "|^このカードは[^。]*?リリースして[^。]*?(?:召喚|特殊召喚)(?:できる|する事ができる)。?$"
    "|素材[^。]*?しか使用できない"
    "|(?:デッキから|墓地から|手札から)の特殊召喚はできない")
# 裝備限制句(「〜モンスターにのみ装備できる」);效果裡的「装備カード扱いとして〜に装備できる」不算。
_EQUIP_RE = re.compile("(?:モンスター|カード)(?:に|には)(?:のみ|だけ)?装備(?:可能|できる|する事ができる)。?$")
_EQUIP_EFFECT_RE = re.compile("扱い|時、|場合、|時に|１ターンに")
# 召喚條件後接的召喚手續句(「このカードは通常召喚できない。〜をリリースして特殊召喚する。」)。
_SUMMON_TAIL_RE = re.compile("(?:特殊召喚|召喚)(?:する|できる|する事ができる)。$")

# 效果句開頭:續前一區塊(不切)。「この(効果|方法)で〜に成功した時」是新效果,先於此判。
_RESULT_CUT_RE = re.compile("^この(?:効果|方法)で(?:特殊召喚|召喚)に成功した(?:時|場合)")
_NO_CUT_RE = re.compile(
    "^(?:選択した|この効果は|この効果の|このターン|その後|デッキから|手札から|その|それ"
    "|この効果を(?:発動|適用)(?:する|した)|「[^」]*」のこの効果|ターン終了時まで|（|●|または"
    "|さらに|この効果で|この方法で|お互い|この効果によって|次の(?:自分|相手)?ターン|この時"
    "|こうして|墓地へ送|墓地に送|破壊し|確認し|宣言し|残りの|めくっ|違った|当たっ|ハズレ"
    "|同一チェーン|発動後|また、この効果|[^、。]*?(?:なかった|だった)場合|(?:自分|相手)の出た目"
    "|この効果|このカードを発動(?:した|する)ターン"
    "|このカードは[^。]*?(?:発動後|フェイズ)[^。]*?(?:破壊される|墓地へ送られる|墓地に送られる)。$)")
# 效果句開頭:另起區塊。
_CUT_RE = re.compile(
    "^(?:また、|このカードが|このカードは|このカードと|このカードに|１ターンに１度|装備モンスター"
    "|召喚・反転召喚・特殊召喚|魔法＆罠|相手は[^。]*?できない。$|このカードのコントローラー)")
# 「このカードの攻撃力は〜アップする」是獨立的持續效果;帶「まで」「この効果」的是前一效果的結果。
_SELF_STAT_RE = re.compile("^このカードの[^、。を]*?は")
# 句首觸發子句(「〜時、」「〜場合、」「〜限り、」「〜毎に」…)是新效果。
_TRIGGER_OPEN_RE = re.compile(
    "^[^、。]*?(?:時|場合|限り|毎に|度に|際|ターン|フェイズ|ステップ)(?:、|に、|に|この|自分|相手)"
    "|^[^。]*?(?:時|場合|限り)(?:、|に、)")

UNIT_MATERIAL, UNIT_SUMMON, UNIT_LIMIT, UNIT_EFFECT = "素材", "召喚條件", "次數限制", "效果"
_UNIT_KIND = {UNIT_MATERIAL: "素材", UNIT_SUMMON: "召喚條件", UNIT_EFFECT: "編號效果"}
_PRIORITY = (UNIT_EFFECT, UNIT_SUMMON, UNIT_MATERIAL, UNIT_LIMIT)

_WS_RE = re.compile(r"[\s　]+")
_QUOTE_RE = re.compile("『([^』]*)』")
_SEQUENCE_CHARS = set("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳●１２３４５６７８９")

# ── 邊界補丁 ────────────────────────────────────────────────
PATCH_APPLIED = "生效"
PATCH_STALE = "卡文已變動"
PATCH_MALFORMED = "格式不合法"
PATCH_COVERAGE = "覆蓋不成立"
PATCH_QUOTE = "引用被切斷"


def boundary_patch_hash(text):
    """邊界補丁的卡文雜湊:只算官方日文(與拆句表不同,不含中文)。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _condense(text):
    """去掉全部空白 → (壓縮後的文字, 每個字元在原文的位移)。"""
    kept = [(ch, pos) for pos, ch in enumerate(text) if not ch.isspace() and ch != "　"]
    return "".join(ch for ch, _ in kept), [pos for _, pos in kept]


def quote_spans(supplement, condensed):
    """補足情報的『原文』引用在壓縮文本裡的 (起, 迄);序號引用(『①』『●』)不算。"""
    spans = []
    for quoted in _QUOTE_RE.findall(supplement or ""):
        if not quoted or all(ch in _SEQUENCE_CHARS for ch in quoted):
            continue
        needle = _WS_RE.sub("", quoted).rstrip("。")
        if not needle:
            continue
        start = condensed.find(needle)
        if start >= 0:
            spans.append((start, start + len(needle)))
    return spans


def _quote_crosses(spans, cut):
    return any(a < cut < b for a, b in spans)


def _strip_span(text, start, end):
    """去掉頭尾換行與空白,回傳收緊後的 (start, end)。"""
    while start < end and text[start] in "\n ":
        start += 1
    while end > start and text[end - 1] in "\n ":
        end -= 1
    return start, end


def _units(text):
    """舊式卡文的單位:「。」(「」『』（）外)與換行處各切一句;回傳收緊後的 (start, end)。"""
    spans, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "「『（":
            depth += 1
        elif ch in "」』）":
            depth = max(0, depth - 1)
        if depth == 0 and ch == "。":
            spans.append((start, i + 1))
            start = i + 1
        elif depth == 0 and ch == "\n":
            spans.append((start, i))
            start = i + 1
    spans.append((start, len(text)))
    out = []
    for s, e in spans:
        s, e = _strip_span(text, s, e)
        if s < e:
            out.append((s, e))
    return out


def classify_unit(sentence, first, previous):
    """一句的單位種類:素材行、召喚條件、次數限制或效果。"""
    if _LIMIT_RE.match(sentence):
        return UNIT_LIMIT
    if not sentence.endswith("。") and (first or previous == UNIT_MATERIAL):
        return UNIT_MATERIAL
    if _SUMMON_RE.search(sentence):
        return UNIT_SUMMON
    if _EQUIP_RE.search(sentence) and not _EQUIP_EFFECT_RE.search(sentence):
        return UNIT_SUMMON
    if previous == UNIT_SUMMON and _SUMMON_TAIL_RE.search(sentence) \
            and not sentence.startswith("このカードが"):
        return UNIT_SUMMON
    return UNIT_EFFECT


def starts_new_block(sentence):
    """效果句接在效果句後面時,依開頭決定另起區塊(True)或續前一區塊(False)。"""
    if _RESULT_CUT_RE.match(sentence):
        return True
    if _NO_CUT_RE.match(sentence):
        return False
    if _CUT_RE.match(sentence):
        return True
    if _SELF_STAT_RE.match(sentence):
        return "まで" not in sentence and "この効果" not in sentence
    return bool(_TRIGGER_OPEN_RE.match(sentence))


def _group_units(text, units, spans):
    """單位 → 區塊群 [(種類, 起, 迄)];切點被引用跨過就與前一群合併。"""
    condensed_starts = []
    pos = 0
    for s, e in units:
        condensed_starts.append(pos)
        pos += len(_WS_RE.sub("", text[s:e]))
    groups = []
    previous = None
    for i, (s, e) in enumerate(units):
        sentence = text[s:e]
        kind = classify_unit(sentence, i == 0, previous)
        cut = (not groups or kind != previous or kind != UNIT_EFFECT
               or starts_new_block(sentence))
        if cut and groups and (sentence.startswith("●")
                               or _quote_crosses(spans, condensed_starts[i])):
            cut = False
        if cut:
            groups.append([kind, s, e])
        else:
            group = groups[-1]
            group[0] = min(group[0], kind, key=_PRIORITY.index)
            group[2] = e
        previous = kind
    return groups


def _emit_groups(text, groups, source, prefix, kind_fixed, category, numbered):
    """單位群 → 區塊與略過文本。`numbered` = 這段文本後面還有 ①②③(新式卡的前言):
    沒有編號的效果句歸編號效果就標「區塊種類判不出」;魔陷卡的第一個無編號效果群是卡片發動。"""
    blocks, omitted = [], []
    activation_used = False
    for kind, start, end in groups:
        if kind == UNIT_LIMIT:
            omitted.append({"source": source, "span": [start, end],
                            "text": text[start:end], "reason": LIMIT_REASON})
            continue
        block_kind = kind_fixed or _UNIT_KIND[kind]
        block = new_block(f"{prefix}{start}", block_kind, None, source,
                          (start, end), text[start:end])
        if kind == UNIT_EFFECT and not kind_fixed:
            if category == CATEGORY_SPELL_TRAP and not activation_used:
                block["kind"] = KIND_ACTIVATION
                activation_used = True
            elif numbered:
                block["unparsed"] = unparsed(KIND_UNKNOWN)
        blocks.append(block)
    return blocks, omitted


def check_boundary_patch(record, text, supplement):
    """補丁一筆對官方日文 → (各區塊的 (起, 迄), None) 或 (None, 不能用的理由)。

    順序即優先序:格式不合法 → 卡文已變動(雜湊不符)→ 覆蓋不成立 → 引用被切斷。
    任一道不過整筆退回規則,不保留舊切點(同拆句表)。
    """
    pieces = record.get("blocks")
    if (not isinstance(pieces, list) or not pieces
            or any(not isinstance(p, str) or not _WS_RE.sub("", p) for p in pieces)
            or not isinstance(record.get("text_hash"), str)):
        return None, PATCH_MALFORMED
    if record["text_hash"] != boundary_patch_hash(text):
        return None, PATCH_STALE
    condensed, offsets = _condense(text)
    parts = [_WS_RE.sub("", p) for p in pieces]
    if "".join(parts) != condensed:
        return None, PATCH_COVERAGE
    spans, start = [], 0
    for part in parts:
        spans.append((offsets[start], offsets[start + len(part) - 1] + 1))
        start += len(part)
    cuts = []
    pos = 0
    for part in parts[:-1]:
        pos += len(part)
        cuts.append(pos)
    if any(_quote_crosses(quote_spans(supplement, condensed), cut) for cut in cuts):
        return None, PATCH_QUOTE
    return spans, None


def _split_unnumbered(text, end, source, kind_fixed, prefix, supplement, patch,
                      patch_status, category):
    """沒有編號的文字(舊式卡的全文,或新式卡編號前的前言 `text[:end]`)→ 區塊與略過文本。
    邊界補丁只對舊式卡的全文生效(`end` 是全文長度時)。"""
    condensed, _ = _condense(text)
    spans = quote_spans(supplement, condensed)
    numbered = end < len(text)
    if patch is not None and not numbered:
        pieces, reason = check_boundary_patch(patch, text, supplement)
        if patch_status is not None:
            patch_status[source] = reason or PATCH_APPLIED
        if pieces:
            groups = []
            for s, e in pieces:
                kinds, previous = [], None
                for i, (us, ue) in enumerate(_units(text[s:e])):
                    previous = classify_unit(text[s + us:s + ue], i == 0, previous)
                    kinds.append(previous)
                groups.append([min(kinds, key=_PRIORITY.index), s, e])
            return _emit_groups(text, groups, source, prefix, kind_fixed,
                                category, numbered)
    units = _units(text[:end])
    groups = _group_units(text, units, spans)
    return _emit_groups(text, groups, source, prefix, kind_fixed, category,
                        numbered)


def _split_text(text, source, kind_numbered, prefix, supplement, patch,
                patch_status, category):
    if not text:
        return [], []
    labels = list(_LABEL_RE.finditer(text))
    kind_fixed = None if kind_numbered == "編號效果" else kind_numbered
    preamble_end = labels[0].start() if labels else len(text)
    blocks, omitted = _split_unnumbered(text, preamble_end, source, kind_fixed,
                                        prefix, supplement, patch, patch_status,
                                        category)
    # 編號區塊:從這個編號到下一個編號前。
    for i, m in enumerate(labels):
        stop = labels[i + 1].start() if i + 1 < len(labels) else len(text)
        start, end = _strip_span(text, m.start(), stop)
        blocks.append(new_block(f"{prefix}{start}", kind_numbered,
                                m.group()[0], source, (start, end),
                                text[start:end]))
    return blocks, omitted


def split_blocks(card_text, pen_effect=None, supplement=None,
                 boundary_patch=None, patch_status=None, category=None):
    """→ (區塊列表, 略過文本列表);每個區塊帶原文範圍(相對於各自的來源文本)。

    `supplement` 是補足情報(『』引用跨句號不得切斷);`boundary_patch` 是這張卡的邊界補丁
    {"card_text": 紀錄, "pen_effect": 紀錄};`patch_status`(dict)給呼叫端收補丁結果:
    {來源: 生效 / 卡文已變動 / 覆蓋不成立 / 引用被切斷 / 格式不合法};`category` 是卡片大類
    (「魔陷」時沒有編號的第一個效果區塊是卡片發動,其餘值不影響切法)。
    """
    patches = boundary_patch or {}
    blocks, omitted = _split_text(card_text or "", "card_text", "編號效果", "b",
                                  supplement, patches.get("card_text"),
                                  patch_status, category)
    if pen_effect:
        pen_blocks, pen_omitted = _split_text(pen_effect, "pen_effect",
                                              "靈擺效果", "p", supplement,
                                              patches.get("pen_effect"),
                                              patch_status, category)
        blocks.extend(pen_blocks)
        omitted.extend(pen_omitted)
    return blocks, omitted
