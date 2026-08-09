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
BULLET = "●"

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
# 賦予型領起句:「〜は以下の効果を得る。●…」。領起句只是把一組效果賦予別的東西,
# 自己不發動也不形成連鎖(官方對 89355716 寫得很白:「『②：…以下の効果を得る』
# 効果はチェーンブロックの作られない効果です」),`●` 才是被賦予的效果。
_GRANT_LEAD_RE = re.compile(r"以下の効果を得る。?\s*$")

_HEADER_RE = re.compile(r"^【([^】]*)】", re.M)
# 黏在行尾的標頭:官方偶爾把下一段的標頭接在前一行的尾巴,先切成獨立的一行再走
# 歸屬階梯。不切的話那一行之後的明示會繼續算在**上一個**編號底下(CNo.104 仮面
# 魔踏士アンブラル 49456901:官方在同一行裡先說②的領起句不是效果,再切到 `●`,
# `●` 的 2 速因此掛給了②)。
# 只認**行尾**:行中間的【…】是強調而不是標頭(オーディンの眼 88069166
# 「効果の発動を伴わない【カードの発動】だけであれば〜」),切開它會把一句話
# 劈成兩半又多生一個對不到標的的段。實測行尾 15 行、行中 1 行。
_TRAILING_HEADER_RE = re.compile(r"(?<=.)(【[^】]*】)[ 　\t]*$", re.M)
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


def _outside_parens(line):
    """一行明示 → 括弧之外的部分。

    官方把補述寫在句尾括弧裡,那裡面的話是限定否定或解說時的指代,不是這一句
    在講的事——效果外文本的明示與 `『●』` 指名都靠這一點分辨主語。
    """
    depth = 0
    outside = []
    for ch in line:
        if ch in _PAREN_OPEN:
            depth += 1
        elif ch in _PAREN_CLOSE:
            depth = max(depth - 1, 0)
        elif not depth:
            outside.append(ch)
    return "".join(outside)


def _is_non_effect_line(line):
    """這一行有沒有在括弧之外寫下效果外文本的明示。"""
    return bool(NON_EFFECT_RE.search(_outside_parens(line)))


def _bullet_subject(line):
    """這一行是不是在講某個 `●` 子效果 → 那個 `『●…』` 引用;不是則 None。

    官方寫 `『②』の『●…』は永続効果です` 時,序號只說了在哪一個編號效果底下,
    真正的標的是 `●`——把它套回編號效果的領起句就是票14 治的那個病。

    兩道限制,兩種不是主語的 `●` 因此都不算數:
    只認括弧之外的引用——`『②』は…です。（…『●』の効果を得ます。）` 的主語是②,
    括弧裡的 `●` 只是解說時的指代(實測這兩種形狀各佔一半);而且只認**第一個**
    非序號引用,與 attribute() 的歸屬規則同一條——後面的引用是為了解說而提到的
    另一個效果。
    """
    for quoted in _QUOTE_RE.findall(_outside_parens(line)):
        if _is_sequence_ref(quoted):
            continue
        return quoted if _normalise(quoted).startswith(BULLET) else None
    return None


def _is_sequence_ref(quoted):
    return bool(quoted) and all(ch in NUMERALS for ch in quoted)


# ---------------------------------------------------------------- 補足情報結構

def _blocks(text):
    """補足情報 → [(標頭內文 or None, 區塊內文), ...]。第一個標頭之前為 None。

    標頭一律是新段的開始,黏在行尾的先切成獨立的一行才數。
    """
    text = _TRAILING_HEADER_RE.sub(r"\n\1", text or "")
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
    for header, _ in _blocks(text):
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


def grant_lead(text_ja):
    """「〜は以下の効果を得る。●…」→ (領起句, 整段) 正規化後;不是這一族回 None。

    兩份文字都已正規化,拿來回答「官方這一句講的是領起句還是 `●`」——`●` 拆成
    獨立效果句之後領起句那一行就不含 `●`,這裡自然收不到它,判定隨即恢復正常。
    拆句要不要認行內 `『●…』` 引用看的是同一族(票16),所以兩邊共用這一支。
    """
    text = text_ja or ""
    if BULLET not in text:
        return None
    head = text.split(BULLET)[0]
    if not _GRANT_LEAD_RE.search(head.strip()):
        return None
    return _normalise(head), _normalise(text)


def _grant_leads(effects):
    """效果句清單 → {index: (領起句, 整段)},只收「賦予型領起句 + 未拆的 ●」。"""
    leads = {}
    for clause in effects:
        lead = grant_lead(clause["text_ja"])
        if lead is not None:
            leads[clause["index"]] = lead
    return leads


def quoted_bullets(supplement, text_ja):
    """官方以行內 `『●…』` 引用這一段的 ● 子效果 → 那些引用。

    引用**從 `●` 起頭**才算數:官方是拿整個 `●` 當一個東西在講,與
    `【●…について】` 標頭是同一種依據,只是不開標頭(實測 150 / 156 條賦予型
    領起句有這種引用)。從句中截斷的引用只是一句話的片段、不是子效果的邊界
    (ADR-0003),不得當作拆句的授權。
    """
    body = _normalise(text_ja)
    if not body:
        return []
    hits = []
    for quoted in quotes(supplement):
        needle = _normalise(quoted)
        if needle.startswith(BULLET) and needle in body:
            hits.append(quoted)
    return hits


def _quotes_the_lead(lead, quoted):
    """官方的 『原文』 引用是不是從領起句開始。

    是,才代表這一句講的是領起句(或連 `●` 一起講的整段);從 `●` 開始的引用
    講的是那個子效果,而子效果還不是效果句,套到領起句上就是把只描述其中一段的
    明示放大成整段的判定(晴れの天気模様 89355716:領起句不形成連鎖,官方給的
    2 速是 `●` 的)。
    """
    if not quoted:
        return False
    head, body = lead
    position = body.find(_normalise(quoted))
    return 0 <= position < len(head)


# 引用常常從編號之後才開始(官方寫『このカードは〜』而卡文是『②：このカードは〜』)。
# 正規化把「②：」折成半形的「2:」,⑩ 折成兩位數,所以編號前綴最長是三個字元。
_INDEX_PREFIX_RE = re.compile(r"^\d{0,2}[:：]?$")


def _covers_whole_clause(text_ja, quoted):
    """官方的 `『原文』` 引用涵蓋整個效果句嗎?前面最多剩編號、後面最多剩句號。

    涵蓋一部分時不算數——官方常常只說**領起句**不是效果(符文眼靈擺龍
    1516510),那一句涵蓋不到整段,套上去會把 `●` 的效果一起吃掉。
    """
    body = _normalise(text_ja)
    needle = _normalise(quoted)
    if not body or not needle:
        return False
    position = body.find(needle)
    if position < 0:
        return False
    return (bool(_INDEX_PREFIX_RE.match(body[:position]))
            and body[position + len(needle):] in ("", "。"))


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
    """標頭 → (效果句 index, 狀態, 對位用的引用)。

    狀態 `missing` 表示標頭指名了一個卡文沒有的編號;`unresolved` 表示標頭存在
    但對不出唯一標的——兩者都不產生判定。第三個回傳值只有引號標頭有,底下的
    明示句要靠它才分得出官方講的是領起句還是 `●`。
    """
    match = _INDEX_HEADER_RE.match(header)
    if match is not None:
        index = match.group(1)
        if any(c["index"] == index for c in effects):
            return index, "index", None
        return index, "missing", None

    spec = _bullet_spec(header)
    if spec is not None:
        index = _resolve_bullet(spec, effects)
        return ((index, "index", None) if index is not None
                else (None, "unresolved", None))

    # 引號標頭本身就是歸屬標記,比照階梯三對位回效果句
    for quoted in quotes(header):
        hits = _match_quote(quoted, attributable)
        if len(hits) == 1:
            return hits[0], "index", quoted
    return None, "unresolved", None


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
    unattributable = [c for c in effects if c["index"] in unsplit]
    grant_leads = _grant_leads(effects)
    own_name = _normalise(name_ja)
    conflicting = set()
    # 只寫必發而沒寫類型的明示句另立一份清單,不去動票03 那幾份類型清單的筆數
    kindless = False

    def note(key, row):
        if kindless:
            notes["mandatory_deferred"].append({"note": key, **row})
        else:
            notes[key].append(row)

    def assign(index, kind, ladder, line, is_mandatory=False, quoted=None):
        lead = grant_leads.get(index)
        if lead is not None and not _quotes_the_lead(lead, quoted):
            # 領起句不發動,而 `●` 還沒拆開:官方講的是哪一邊沒有證據可分
            note("attribution_deferred",
                 {"kind": kind, "reason": "● 子效果待拆", "line": line})
            return
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
            if target is None:
                note("seq_missing", {"index": sequence[0]})
                return
            assign_to_index(target, kind, LADDER_SEQ, line, is_mandatory)
            return
        quoted_lines = quotes(line)
        if quoted_lines:
            if not attributable:
                # 舊式無編號卡文還沒依語意拆開,引用指向的是這一團的某一部分
                note("attribution_deferred",
                     {"kind": kind, "reason": "無編號卡文待拆", "line": line})
                return
            quoted = quoted_lines[0]
            if not _match_quote(quoted, attributable) \
                    and _match_quote(quoted, unattributable):
                # 引用落在還沒拆開的那一團裡:是待拆,不是官方引用了別張卡
                note("attribution_deferred",
                     {"kind": kind, "reason": "無編號卡文待拆", "line": line})
                return
            assign_to_match(quoted, attributable, kind, LADDER_QUOTE, line,
                            is_mandatory)
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

    def assign_to_index(target, kind, ladder, line, is_mandatory,
                        header_quote=None):
        """標頭或序號指名了一個編號效果 → 套用;那一行另外指名 `●` 時改指子效果。

        標頭與序號都只說得出「哪一個編號效果」,`●` 拆開之後光靠它就不夠了
        (`■『②』の『●』は永続効果です`:標的是那個 `●`,套回領起句就是票14 治的
        那個病)。`●` 還沒拆開時標的仍是整個編號效果,交給 assign 那道閘門處理:
        賦予型領起句會擋下來,領起句自己就寫了發動的那一族則照常套用——那一族的
        `●` 只是同一個發動的選項列舉,官方的類型本來就是整段的。
        """
        quoted = _bullet_subject(line)
        if quoted is None:
            assign(target, kind, ladder, line, is_mandatory, header_quote)
            return
        bullets = [c for c in attributable
                   if c["index"].startswith(f"{target}-{BULLET}")]
        if bullets:
            assign_to_match(quoted, bullets, kind, ladder, line, is_mandatory)
        else:
            assign(target, kind, ladder, line, is_mandatory, quoted)

    def assign_to_match(quoted, candidates, kind, ladder, line, is_mandatory):
        """`『原文』` 引用 → 命中的那一個效果句;命中不唯一時只記註記,不猜測。"""
        hits = _match_quote(quoted, candidates)
        if len(hits) == 1:
            assign(hits[0], kind, ladder, line, is_mandatory, quoted)
        elif hits:
            note("quote_ambiguous",
                 {"kind": kind, "quote": quoted, "hits": hits})
        else:
            note("quote_unmatched", {"kind": kind, "quote": quoted})

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
        """效果外文本的明示:指到一整段才自動套用,否則只進報告。

        八種變體走的是同一條路徑——寫法不同不代表證據更強。兩種標的的門檻不同,
        因為「指到一整段」這件事在兩邊長得不一樣:前言段整段都是效果外文本,
        引用命中它的任何一句都指得回同一段(票10);效果句則要求引用**涵蓋整句**
        ——官方常常只說領起句不是效果,而領起句是效果句的一部分。
        """
        targets = quotes(line) or (quotes(header) if header else [])
        for segment in preambles:
            body = _normalise(segment["text_ja"])
            if body and any(_normalise(t) in body for t in targets):
                assign(segment["index"], KIND_NON_EFFECT, LADDER_NON_EFFECT,
                       line)
                return
        for clause in attributable:
            covering = next((t for t in targets
                             if _covers_whole_clause(clause["text_ja"], t)),
                            None)
            if covering is not None:
                assign(clause["index"], KIND_NON_EFFECT, LADDER_NON_EFFECT,
                       line, quoted=covering)
                return
        notes["non_effect_outside_preamble"].append(
            {"line": line, "header": header})

    for header, body in _blocks(supplement):
        target, status, header_quote = (None, "none", None) if not header \
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
                assign_to_index(target, kind, LADDER_HEADER, line,
                                is_mandatory, header_quote)
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
