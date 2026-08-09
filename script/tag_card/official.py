"""補足情報的官方明示抽取與歸屬判定。

回答三件事:官方寫下的效果類型是什麼、它有沒有寫這個效果必發、它講的是哪一個
效果句。
歸屬的統一原則是**證據唯一且明確才自動套用**——引號對不回本卡、同時命中多個
效果段、明示句只提到別張卡、卡名限定卻是多效果卡,一律不回傳判定,改記進註記
交由後續判定,絕不猜測。

不是對外接縫,對外的只有 tagcard.build_tag_cards 與 masked 那一對。這裡也放兩樣
姊妹模組共用的東西:`NON_EFFECT_RE`(遮蔽測試要遮掉的效果外文本明示,八種變體與
抽取器認同一條才不會漏遮)與 `normalise` / `quotes`(拆句表的引用交叉驗證要與歸屬
對位用同一把尺)。共用的是判準本身,不是判定流程。詞彙見 CONTEXT.md。
"""
import re
import unicodedata

NUMERALS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"
INDEX_PREAMBLE = "0"
# 舊式無編號卡文在依語意拆開之前的整團(拆句骨架給的唯一 index)
INDEX_UNNUMBERED = "1"

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

# 必發/選發的兩個值(CONTEXT.md 定義);官方明示只講得出必發那一邊
OPTIONAL_MANDATORY = "必發"
OPTIONAL_OPTIONAL = "選發"

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
             "non_effect_outside_preamble", "mandatory_deferred")

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
# 效果外文本的官方明示。官方寫過八種變體(實測「効果として扱いません」1,214 行、
# 「効果の扱いではありません」476 行、其餘各 1~9 行),語幹一律是「効果」直接接
# 「扱い」——中間夾了別的詞的(「効果で破壊された扱いにはなりません」「効果ダメージ
# の扱いではありません」)講的是別件事,不得混入。
# 「効果の扱いではありません」與禁用句型「効果ではありません」只差三個字,兩者
# 互不包含,禁令因此不會被這組變體打穿。
NON_EFFECT_RE = re.compile(
    r"効果(?:としては?|としての|の)"
    r"(?:扱いません|扱われません|扱いではありません|扱いにはなりません)")
# 括弧內的否定不算。官方把「不算哪一種效果」的補述寫在句尾括弧裡,那是限定否定
# 而不是「這一段不是效果」——實測只在括弧內出現的 7 行全是這一種,其中兩行的
# 括弧外正是一句貨真價實的類型明示,整行改判會把那個類型吃掉。
_PAREN_OPEN = "（("
_PAREN_CLOSE = "）)"
# 必發的官方明示。實測 1,526 行全是「必ず発動する効果です」「必ず発動します」
# 「必ず発動し、〜」三種肯定寫法,沒有一行是否定,所以認前綴就夠。
_MANDATORY_MARK = "必ず発動"

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


def normalise(text):
    """比對用的正規化。拆句表的引用交叉驗證要與這裡用同一把尺。"""
    return _normalise(text)


def quotes(text):
    """補足情報裡的 『原文』 引用(排除 『①』 這種純序號引用)。"""
    return [q for q in _QUOTE_RE.findall(text or "") if not _is_sequence_ref(q)]


def _is_non_effect_line(line):
    """這一行有沒有在括弧之外寫下效果外文本的明示。"""
    depth = 0
    outside = []
    for ch in line:
        if ch in _PAREN_OPEN:
            depth += 1
        elif ch in _PAREN_CLOSE:
            depth = max(depth - 1, 0)
        elif not depth:
            outside.append(ch)
    return bool(NON_EFFECT_RE.search("".join(outside)))


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


def _line_mandatory(line):
    """一行明示 → 它有沒有寫「必ず発動」(必發)。

    與 _line_kinds 同樣逐句判斷,好讓「必ず発動する効果ではありません」這種
    禁用句型同樣不產生判定。
    """
    return any(_MANDATORY_MARK in sentence and _FORBIDDEN_MARK not in sentence
               for sentence in line.split("。"))


# ---------------------------------------------------------------- 歸屬對位

def _is_preamble(index):
    """效果外文本段?舊式卡拆出第二段以上的效果外文本是 "0-2" / "0-3"。"""
    return index == INDEX_PREAMBLE or index.startswith(INDEX_PREAMBLE + "-")


def _numbered(effects):
    """有編號的效果句(含 ● 子效果)。用來分辨新式卡文與舊式無編號卡文。"""
    return [c for c in effects if c["index"][:1] in NUMERALS]


def _seq_target(index, effects, unsplit):
    """『①』→ 效果句 index;對不到時回 None。

    官方對舊式無編號卡文仍以①②稱呼,[[拆句表]]拆出來的段就是它指的那幾段
    (index 規則:效果句為 "1" / "2" / "3")。整團還沒拆時整團就是官方口中的那一個。
    """
    if any(c["index"] == index for c in effects):
        return index
    if _numbered(effects):
        return None  # 有編號卡文卻指名不存在的編號:對不到就是對不到
    if len(effects) == 1 and effects[0]["index"] in unsplit:
        return effects[0]["index"]
    ordinal = str(NUMERALS.index(index) + 1)
    return ordinal if any(c["index"] == ordinal for c in effects) else None


def _match_quote(quoted, effects):
    """『效果原文』→ 命中的效果句 index 清單(正規化後的子字串比對)。

    引號可能是原文的截斷,因此用子字串而非全等;命中多個即為歧義,由呼叫端處理。
    """
    needle = _normalise(quoted)
    if not needle:
        return []
    return [clause["index"] for clause in effects
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


def _resolve_header(header, effects, attributable):
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

    # 引號標頭本身就是歸屬標記,比照階梯三對位回效果句
    for quoted in quotes(header):
        hits = _match_quote(quoted, attributable)
        if len(hits) == 1:
            return hits[0], "index"
    return None, "unresolved"


# ---------------------------------------------------------------- 接縫

def attest(name_ja, supplement, clauses, unsplit=()):
    """補足情報 + 某段落的效果句 → (類型判定, 必發判定, 註記)。

    類型判定為 {index: (效果類型, 對位方式)},必發判定為 {index: 對位方式}——
    官方寫下「必ず発動」的效果句。兩者共用同一套歸屬對位。

    clauses 需含 index / text_ja;index 為 "0" / "0-2" 者視為效果外文本段。
    unsplit 是骨架算出來的「還沒依語意拆開的舊式整團」index 集合:它們不是已經
    成立的效果句,不得作為歸屬對位的標的(票11)。
    註記的每一項都是「官方寫了判定但歸屬不確定」或「明示句不可採用」的理由,
    由呼叫端補上卡片密碼後放進報告。
    """
    notes = {key: [] for key in NOTE_KEYS}
    assignments = {}
    mandatory = {}
    if not supplement:
        return assignments, mandatory, notes

    effects = [c for c in clauses if not _is_preamble(c["index"])]
    preambles = [c for c in clauses if _is_preamble(c["index"])]
    # 對得出歸屬的效果句:未拆的整團只是骨架的暫代值,不算數
    attributable = [c for c in effects if c["index"] not in unsplit]
    own_name = _normalise(name_ja)
    conflicting = set()
    # 只寫必發而沒寫類型的明示句另立一份清單,不去動票03 那幾份類型清單的筆數
    kindless = False

    def note(key, row):
        if kindless:
            notes["mandatory_deferred"].append({"note": key, **row})
        else:
            notes[key].append(row)

    def assign(index, kind, ladder, line, is_mandatory=False):
        if is_mandatory:
            mandatory.setdefault(index, ladder)
        if kind is None or index in conflicting:
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

    def attribute(line, kind, is_mandatory):
        """無標頭的明示句 → 依階梯二~五對位;任何歧義都只記註記。

        一行只由**第一個**『』引用決定歸屬。日文的硬性寫作慣例是主語在前
        (「『②』は…誘発効果です。(自身の『①』の効果で…必ず発動する効果です。)」),
        後面的引用是為了解說而提到的另一個效果;逐一套用會把主語的判定複製到
        被提及的效果上(實測 92 行,無一例外)。
        """
        sequence = _SEQ_QUOTE_RE.findall(line)
        if sequence:
            target = _seq_target(sequence[0], effects, unsplit)
            if target is not None:
                assign(target, kind, LADDER_SEQ, line, is_mandatory)
            else:
                note("seq_missing", {"index": sequence[0]})
            return
        quoted_lines = quotes(line)
        if quoted_lines:
            if not attributable:
                # 舊式無編號卡文還沒依語意拆開,引用指向的是這一團的某一部分
                note("attribution_deferred",
                     {"kind": kind, "reason": "無編號卡文待拆", "line": line})
                return
            quoted = quoted_lines[0]
            hits = _match_quote(quoted, attributable)
            if len(hits) == 1:
                assign(hits[0], kind, LADDER_QUOTE, line, is_mandatory)
            elif not hits:
                note("quote_unmatched", {"kind": kind, "quote": quoted})
            else:
                note("quote_ambiguous",
                     {"kind": kind, "quote": quoted, "hits": hits})
            return
        names = _NAME_RE.findall(line)
        if names:
            if own_name and any(_normalise(n) == own_name for n in names):
                apply_to_sole_effect(kind, LADDER_NAME_SINGLE, line, "卡名限定",
                                     is_mandatory)
            else:
                # 補足情報為了解說而引用他卡效果文,不得污染本卡的判定
                note("other_card_only", {"kind": kind, "line": line})
            return
        apply_to_sole_effect(kind, LADDER_SINGLE, line, "無歸屬標記",
                             is_mandatory)

    def apply_to_sole_effect(kind, ladder, line, reason, is_mandatory):
        """階梯四、五:這張卡只有一個效果句時整卡套用。

        「只有一個效果句」必須是已經成立的事實。舊式無編號卡文在依語意拆開之前
        整團只算一個效果句,那是拆句骨架的暫代值而不是證據——整團套上一個類型
        會把只描述其中一段的明示放大成整團的判定(機海竜プレシオン 40160226:
        第一段無種類、第二段啟動,官方講的是第一段),而且整團從此 `kind` 不再是
        null,再也進不了拆句用的判定批次,連自癒的機會都沒有。
        """
        if len(effects) != 1:
            note("attribution_deferred",
                 {"kind": kind, "reason": reason, "line": line})
        elif effects[0]["index"] in unsplit:
            note("attribution_deferred",
                 {"kind": kind, "reason": "無編號卡文待拆", "line": line})
        else:
            assign(effects[0]["index"], kind, ladder, line, is_mandatory)

    def non_effect(line, header):
        """效果外文本的明示:指向效果外文本段才自動套用,否則只進報告。

        八種變體走的是同一條路徑——寫法不同不代表證據更強。
        """
        targets = quotes(line) or (quotes(header) if header else [])
        for segment in preambles:
            body = _normalise(segment["text_ja"])
            if body and any(_normalise(t) in body for t in targets):
                assign(segment["index"], KIND_NON_EFFECT, LADDER_NON_EFFECT,
                       line)
                return
        notes["non_effect_outside_preamble"].append(
            {"line": line, "header": header})

    for header, body in _blocks(supplement):
        target, status = (None, "none") if not header \
            else _resolve_header(header, effects, attributable)
        for raw in body.split("\n"):
            line = raw.strip()
            if not line:
                continue
            if _is_non_effect_line(line):
                non_effect(line, header)
                continue
            kinds = _line_kinds(line)
            if len(kinds) > 1:
                # 一句話交代兩個子效果時,必發講的是哪一個同樣無從得知
                notes["kind_ambiguous"].append(
                    {"kinds": sorted(kinds), "line": line})
                continue
            is_mandatory = _line_mandatory(line)
            if not kinds and not is_mandatory:
                continue
            kind = kinds.pop() if kinds else None
            kindless = kind is None
            if status == "index":
                assign(target, kind, LADDER_HEADER, line, is_mandatory)
            elif status == "missing":
                note("header_index_missing", {"index": target})
            elif status == "unresolved":
                note("attribution_deferred",
                     {"kind": kind, "line": line,
                      "reason": "無編號卡文待拆" if not attributable
                      else "標頭對不出標的"})
            else:
                attribute(line, kind, is_mandatory)
    return assignments, mandatory, notes
