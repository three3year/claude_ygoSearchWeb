"""補足情報的官方明示抽取與歸屬判定。

回答兩件事:官方寫下的效果類型是什麼、它講的是哪一個效果句。
歸屬的統一原則是**證據唯一且明確才自動套用**——引號對不回本卡、同時命中多個
效果段、明示句只提到別張卡、卡名限定卻是多效果卡,一律不回傳判定,改記進註記
交由後續判定,絕不猜測。

給 tagcard.build_tag_cards 用,不是對外接縫。詞彙見 CONTEXT.md。
"""
import re
import unicodedata

NUMERALS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
INDEX_PREAMBLE = "0"

# 效果類型的六種固定值(CONTEXT.md 定義,「(2速)」「(1速)」是名稱的一部分)
KIND_NON_EFFECT = "效果外文本"
KIND_UNCLASSIFIED = "無種類效果"
KIND_CONTINUOUS = "永續效果"
KIND_QUICK = "誘發即時效果(2速)"
KIND_TRIGGER = "誘發效果(1速)"
KIND_IGNITION = "啟動效果"
KINDS = (KIND_NON_EFFECT, KIND_UNCLASSIFIED, KIND_CONTINUOUS, KIND_QUICK,
         KIND_TRIGGER, KIND_IGNITION)

SOURCE_OFFICIAL = "official"

# 五種對位方式(spec 的階梯一~五)加上效果外文本的官方明示
LADDER_HEADER = "header"
LADDER_SEQ = "seq"
LADDER_QUOTE = "quote"
LADDER_NAME_SINGLE = "name_single"
LADDER_SINGLE = "single"
LADDER_NON_EFFECT = "non_effect"
LADDERS = (LADDER_HEADER, LADDER_SEQ, LADDER_QUOTE, LADDER_NAME_SINGLE,
           LADDER_SINGLE, LADDER_NON_EFFECT)

NOTE_KEYS = ("seq_missing", "header_index_missing", "quote_unmatched",
             "quote_ambiguous", "attribution_deferred", "other_card_only",
             "kind_conflicts", "kind_ambiguous",
             "non_effect_outside_preamble")

# 官方類型詞。「誘発即時効果」必須排在「誘発効果」之前才不會被前綴吃掉。
_KIND_BY_WORD = {
    "誘発即時効果": KIND_QUICK,
    "誘発効果": KIND_TRIGGER,
    "起動効果": KIND_IGNITION,
    "永続効果": KIND_CONTINUOUS,
}
_KIND_WORD_RE = re.compile("(" + "|".join(_KIND_BY_WORD) + ")")
_KIND_RE = re.compile("(" + "|".join(_KIND_BY_WORD) + ")です")
# 否定句優先:這句話會列舉其他四個類型詞,不得因此多重命中。
# 官方寫過「いずれにも」與「どれにも」兩種,都是同一件事。
_UNCLASSIFIED_MARK = "分類されない"
# 「対象を取る効果ではありません」這類限定否定與效果分類無關,絕不可作為判定依據
_FORBIDDEN_MARK = "効果ではありません"
_NON_EFFECT_MARK = "効果として扱いません"

_HEADER_RE = re.compile(r"^【([^】]*)】", re.M)
_INDEX_HEADER_RE = re.compile(
    rf"^([{NUMERALS}])[のに]?(?:モンスター|ペンデュラム)?の?効果について$")
_BULLET_HEADER_RE = re.compile(
    r"^(?:(?P<ordinal>[１-９1-9①-⑩])つ目の)?"
    r"(?:『(?P<label>●[^』]*)』|(?P<bare>●))"
    r"[のな]?(?:効果|処理)?について$")
_SEQ_QUOTE_RE = re.compile(rf"『([{NUMERALS}])』")
_QUOTE_RE = re.compile(r"『([^』]*)』")
_NAME_RE = re.compile(r"「([^」]*)」")

_ORDINALS = {c: i + 1 for i, c in enumerate("１２３４５６７８９")}
_ORDINALS.update({c: i + 1 for i, c in enumerate("123456789")})
_ORDINALS.update({c: i + 1 for i, c in enumerate(NUMERALS)})

# 比對前的正規化。官方在補足情報裡重打卡名與卡文,寬窄形、長音記號與中黑點常與
# 來源資料不同(「バグマンＹ」「ユニオン・キャリア―」),不正規化會把本卡誤判成別卡。
_DASH_MAP = {ord(dash): ord("ー") for dash in "-―‐−–—"}
_NOISE_RE = re.compile(r"[\s…‥]+")


def _normalise(text):
    folded = unicodedata.normalize("NFKC", text or "")
    return _NOISE_RE.sub("", folded.translate(_DASH_MAP))


def _is_sequence_ref(quoted):
    return bool(quoted) and all(ch in NUMERALS for ch in quoted)


# ---------------------------------------------------------------- 補足情報結構

def _blocks(text):
    """補足情報 → [(標頭內文 or None, 區塊內文), ...]。第一個標頭之前為 None。"""
    blocks = []
    header = None
    pos = 0
    for match in _HEADER_RE.finditer(text):
        body = text[pos:match.start()]
        if header is not None or body.strip():
            blocks.append((header, body))
        header, pos = match.group(1), match.end()
    body = text[pos:]
    if header is not None or body.strip():
        blocks.append((header, body))
    return blocks


def bullet_specs(text):
    """補足情報 → 官方用【●…について】系列標頭描述的子效果標的清單。

    有標的才代表官方把 ● 當成獨立的子效果來解說,拆句才有依據(spec 的
    「官方以●分項描述的子效果拆成獨立效果句」)。
    """
    specs = []
    for header, _ in _blocks(text or ""):
        spec = _bullet_spec(header)
        if spec is not None:
            specs.append(spec)
    return specs


def _bullet_spec(header):
    if not header:
        return None
    match = _BULLET_HEADER_RE.match(header)
    if match is None:
        return None
    if match.group("ordinal"):
        return ("ordinal", _ORDINALS[match.group("ordinal")])
    if match.group("label"):
        return ("label", match.group("label"))
    return ("bare", None)


def _line_kinds(line):
    """一行明示 → 它寫出的效果類型集合(空集合代表沒有明示)。

    逐句判斷:含「分類されない」者只算無種類效果(否定句優先),含
    「効果ではありません」的句子直接跳過(禁用句型),同一句列舉兩個以上類型詞的
    也跳過——官方在一句裡分別交代兩個子效果時,無從得知「です」收尾的是哪一個。
    """
    kinds = set()
    for sentence in line.split("。"):
        if _FORBIDDEN_MARK in sentence:
            continue
        if _UNCLASSIFIED_MARK in sentence:
            kinds.add(KIND_UNCLASSIFIED)
            continue
        if len({m.group(1) for m in _KIND_WORD_RE.finditer(sentence)}) > 1:
            continue
        for match in _KIND_RE.finditer(sentence):
            kinds.add(_KIND_BY_WORD[match.group(1)])
    return kinds


# ---------------------------------------------------------------- 歸屬對位

def _numbered(effects):
    """有編號的效果句(含 ● 子效果)。原文引用只對位得到「編號區段」。"""
    return [c for c in effects if c["index"][:1] in NUMERALS]


def _match_quote(quoted, effects):
    """『效果原文』→ 命中的編號效果句 index 清單(正規化後的子字串比對)。

    引號可能是原文的截斷,因此用子字串而非全等;命中多個即為歧義,由呼叫端處理。
    """
    needle = _normalise(quoted)
    if not needle:
        return []
    return [clause["index"] for clause in _numbered(effects)
            if needle in _normalise(clause["text_ja"])]


def _resolve_bullet(spec, effects):
    """【●…について】標頭 → 子效果句的 index;對不出唯一標的時回 None。"""
    bullets = [c for c in effects if "-●" in c["index"]]
    if not bullets:
        return None
    if len({c["index"].split("-●")[0] for c in bullets}) > 1:
        # ● 散落在多個編號效果裡,序數標頭無從得知是哪一組
        return None
    form, value = spec
    if form == "ordinal":
        return bullets[value - 1]["index"] if value <= len(bullets) else None
    if form == "label":
        label = _normalise(value)
        hits = [c["index"] for c in bullets
                if _normalise(c["text_ja"]).startswith(label)]
        return hits[0] if len(hits) == 1 else None
    return bullets[0]["index"] if len(bullets) == 1 else None


def _resolve_header(header, effects):
    """標頭 → (效果句 index, 狀態)。

    狀態 `missing` 表示標頭指名了一個卡文沒有的編號;`unresolved` 表示標頭存在
    但對不出唯一標的——兩者都不產生判定。
    """
    match = _INDEX_HEADER_RE.match(header)
    if match is not None:
        index = match.group(1)
        if any(c["index"] == index for c in effects):
            return index, "index"
        return index, "missing"

    spec = _bullet_spec(header)
    if spec is not None:
        index = _resolve_bullet(spec, effects)
        return (index, "index") if index is not None else (None, "unresolved")

    # 引號標頭本身就是歸屬標記,比照階梯三對位回編號區段
    for quoted in _QUOTE_RE.findall(header):
        if _is_sequence_ref(quoted):
            continue
        hits = _match_quote(quoted, effects)
        if len(hits) == 1:
            return hits[0], "index"
    return None, "unresolved"


# ---------------------------------------------------------------- 接縫

def attest(name_ja, supplement, clauses):
    """補足情報 + 某段落的效果句 → ({index: (效果類型, 對位方式)}, 註記)。

    clauses 需含 index / text_ja;index 為 "0" 者視為前言段(效果外文本)。
    註記的每一項都是「官方寫了類型但歸屬不確定」或「明示句不可採用」的理由,
    由呼叫端補上卡片密碼後放進報告。
    """
    notes = {key: [] for key in NOTE_KEYS}
    assignments = {}
    if not supplement:
        return assignments, notes

    effects = [c for c in clauses if c["index"] != INDEX_PREAMBLE]
    preamble = next((c for c in clauses if c["index"] == INDEX_PREAMBLE), None)
    own_name = _normalise(name_ja)
    conflicting = set()

    def assign(index, kind, ladder, line):
        if index in conflicting:
            return
        current = assignments.get(index)
        if current is None:
            assignments[index] = (kind, ladder)
        elif current[0] != kind:
            del assignments[index]
            conflicting.add(index)
            notes["kind_conflicts"].append(
                {"index": index, "kinds": sorted([current[0], kind]),
                 "line": line})

    def attribute(line, kind):
        """無標頭的明示句 → 依階梯二~五對位;任何歧義都只記註記。"""
        sequence = list(dict.fromkeys(_SEQ_QUOTE_RE.findall(line)))
        if sequence:
            for index in sequence:
                if any(c["index"] == index for c in effects):
                    assign(index, kind, LADDER_SEQ, line)
                elif len(effects) == 1 and not _numbered(effects):
                    # 舊式無編號卡文,官方仍以『①』稱呼那唯一的效果
                    assign(effects[0]["index"], kind, LADDER_SEQ, line)
                else:
                    notes["seq_missing"].append({"index": index})
            return
        quotes = [q for q in _QUOTE_RE.findall(line)
                  if not _is_sequence_ref(q)]
        if quotes:
            if not _numbered(effects):
                # 舊式無編號卡文還沒依語意拆開,引用指向的是這一團的某一部分
                notes["attribution_deferred"].append(
                    {"kind": kind, "reason": "無編號卡文待拆", "line": line})
                return
            for quoted in quotes:
                hits = _match_quote(quoted, effects)
                if len(hits) == 1:
                    assign(hits[0], kind, LADDER_QUOTE, line)
                elif not hits:
                    notes["quote_unmatched"].append(
                        {"kind": kind, "quote": quoted})
                else:
                    notes["quote_ambiguous"].append(
                        {"kind": kind, "quote": quoted, "hits": hits})
            return
        names = _NAME_RE.findall(line)
        if names:
            if own_name and any(_normalise(n) == own_name for n in names):
                apply_to_sole_effect(kind, LADDER_NAME_SINGLE, line, "卡名限定")
            else:
                # 補足情報為了解說而引用他卡效果文,不得污染本卡的判定
                notes["other_card_only"].append({"kind": kind, "line": line})
            return
        apply_to_sole_effect(kind, LADDER_SINGLE, line, "無歸屬標記")

    def apply_to_sole_effect(kind, ladder, line, reason):
        if len(effects) == 1:
            assign(effects[0]["index"], kind, ladder, line)
        else:
            notes["attribution_deferred"].append(
                {"kind": kind, "reason": reason, "line": line})

    def non_effect(line, header):
        """「〜は効果として扱いません」:指向前言段才自動套用,否則只進報告。"""
        targets = [q for q in _QUOTE_RE.findall(line)
                   if not _is_sequence_ref(q)]
        if not targets and header:
            targets = [q for q in _QUOTE_RE.findall(header)
                       if not _is_sequence_ref(q)]
        if preamble is not None:
            body = _normalise(preamble["text_ja"])
            if body and any(_normalise(t) in body for t in targets):
                assign(INDEX_PREAMBLE, KIND_NON_EFFECT, LADDER_NON_EFFECT,
                       line)
                return
        notes["non_effect_outside_preamble"].append(
            {"line": line, "header": header})

    for header, body in _blocks(supplement):
        target, status = (None, "none") if not header \
            else _resolve_header(header, effects)
        for raw in body.split("\n"):
            line = raw.strip()
            if not line:
                continue
            if _NON_EFFECT_MARK in line:
                non_effect(line, header)
                continue
            kinds = _line_kinds(line)
            if not kinds:
                continue
            if len(kinds) > 1:
                notes["kind_ambiguous"].append(
                    {"kinds": sorted(kinds), "line": line})
                continue
            kind = kinds.pop()
            if status == "index":
                assign(target, kind, LADDER_HEADER, line)
            elif status == "missing":
                notes["header_index_missing"].append({"index": target})
            elif status == "unresolved":
                notes["attribution_deferred"].append(
                    {"kind": kind, "line": line,
                     "reason": "無編號卡文待拆" if not _numbered(effects)
                     else "標頭對不出標的"})
            else:
                attribute(line, kind)
    return assignments, notes
