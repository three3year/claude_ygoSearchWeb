"""種子詞典萃取(票 effect-tokenize#02)。

從兩個既有資產萃取日文領域詞彙,合併去重成 lexicon.json:

1. `script/tag_card/tag_rules.py` 的 regex(RULES 274 條 + TIMING_RULES 19 條,
   pattern / exclude / action 三欄):解析 pattern 字串,收集字面日文片段。
   regex 元字符(`(|)[]{}?!<=*+.^$\\`)是片段邊界;另做兩種「前綴接合」還原
   動詞活用形:
   - 群組交替 `送(る|り|って)` → 送る/送り/送って(負向環視 `(?!...)` 不接合
     ——那是排除語境,不是詞彙)
   - 字元類 `戻[すし]` → 戻す/戻し
2. `docs/text_glossary.md` 的日→中對照表日文側(譯詞+句式模板兩表的第一欄):
   剝掉佔位符(〈n〉/〈時點〉/〜)與 ≠ 護欄後取字面段。

後處理(兩源同一套):
- **助詞切分**:片段內、前一字非平假名處,依最長匹配切開複合助詞
  (として/から/まで/より/など)與單字助詞(に/で/を/は/が/と/の/へ/も/や),
  助詞本身不入詞典(分詞器的封閉類)。前一字為平假名不切(できる 的 で、
  この 的 の 都是詞中音,不是助詞)。
- **過濾**:
  - 純平假名片段只留功能詞白名單(する/した/され/される/されない/されず/
    できる/できない/できず/なる/ない)——其餘是活用殘渣(し、って、られ…)
  - tag_rules 來源片段長度 < 2 丟棄(單字殘渣);glossary 來源放寬到單一漢字
    (払/戻 這類站主親核的動詞詞條)
  - 純 ASCII 片段只留白名單 {LP}(EX 這類 regex 殘渣丟棄)
  - 片段本身是助詞者丟棄
- 尾端單字助詞剝除(墓地か→墓地;前一字非平假名才剝)

輸出 `.scratch/effect-tokenize/lexicon.json`:
    [{"id": "W0001", "surface": "...", "sources": ["tag_rules","glossary"]}]
ID 依 surface 的 Unicode 碼位排序後編號——同一份輸入重跑,輸出逐位元組相同。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/extract_seed.py
"""
import json
import os
import re
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(os.path.join(_ROOT, "script", "tag_card"))
import tag_rules  # noqa: E402

GLOSSARY = os.path.join(_ROOT, "docs", "text_glossary.md")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicon.json")

# ── 字面字元(片段的合法成分)──
# 平假名/片假名(含ー)/漢字/々/ASCII 大寫(EX・S召喚 的 S)/全形英文字母/＆。
# 數字(半形全形)、・、〜 都是邊界:數字歸 NUM 正規化、・ 是並列分隔。
def _is_literal(ch):
    o = ord(ch)
    return (0x3041 <= o <= 0x309F          # 平假名
            or (0x30A0 <= o <= 0x30FF and ch != "・")   # 片假名(含ー,排・)
            or 0x4E00 <= o <= 0x9FFF or ch == "々"       # 漢字
            or "A" <= ch <= "Z"                            # ASCII 大寫
            or 0xFF21 <= o <= 0xFF3A                       # 全形大寫
            or ch == "＆")


def _is_hira(ch):
    return "ぁ" <= ch <= "ゟ"


def _all_jp(text):
    return all(_is_literal(ch) and not ("A" <= ch <= "Z") for ch in text)


# ── 助詞/接續詞(切分用;分詞器端另有同一份封閉類)──
# または/及び 是並列接續詞、しか/では 是係助詞與複合形:regex 片段裡它們把
# 兩個內容詞黏成一團(手札または自分、デッキ及び相手),比照助詞切開。
PARTICLES_MULTI = ("として", "または", "から", "まで", "より", "など",
                   "では", "及び", "しか", "のみ", "だけ", "ずつ")
PARTICLES_SINGLE = "にでをはがとのへもや"
PARTICLES = set(PARTICLES_MULTI) | set(PARTICLES_SINGLE)

# regex 殘渣黑名單:活用尾+名詞的斷頭片段(う事/る場合)、群組接合的
# 跨字殘片(り直す 之於 振り直す)、更長詞形已在表內的斷尾(半分払、選択す)
# 與側別錨的詞組殘片——留著會在最長匹配時搶走正確切分。
BLOCKLIST = {"う事", "く事", "る事", "る効果", "る場合", "り直す",
             "選択す", "半分払", "見て相手", "つしか使用"}

# 純平假名功能詞白名單(可能形/サ変尾/受身形——分詞器靠它們把活用尾
# 從 OOV 裡撈出來)
HIRA_WHITELIST = {"する", "した", "され", "される", "されない", "されず",
                  "できる", "できない", "できず", "なる", "ない"}
ASCII_WHITELIST = {"LP"}


def extract_fragments(pattern):
    """regex 字串 → 字面片段清單(含群組/字元類的前綴接合變體)。"""
    frags = []
    stack = []   # [{"prefix": str, "joinable": bool, "expect": bool}]
    cur = ""

    def flush():
        nonlocal cur
        if cur:
            frags.append(cur)
            if stack and stack[-1]["expect"] and stack[-1]["prefix"]:
                frags.append(stack[-1]["prefix"] + cur)
            if stack:
                stack[-1]["expect"] = False
        cur = ""

    i = 0
    n = len(pattern)
    while i < n:
        ch = pattern[i]
        if ch == "\\":          # 跳脫序列:邊界,連跳脫字元一起略過
            flush()
            if stack:
                stack[-1]["expect"] = False
            i += 2
            continue
        if ch == "(":
            # 負向/正向環視不接合(排除語境);捕獲群組與 (?:) 接合
            joinable = not (i + 1 < n and pattern[i + 1] == "?"
                            and pattern[i + 2:i + 3] != ":")
            prefix = cur if joinable else ""
            flush()
            stack.append({"prefix": prefix, "joinable": joinable,
                          "expect": joinable})
            i += 1
            continue
        if ch == "|":
            flush()
            if stack:
                stack[-1]["expect"] = stack[-1]["joinable"]
            i += 1
            continue
        if ch == ")":
            flush()
            if stack:
                stack.pop()
            i += 1
            continue
        if ch == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                flush()
                i += 1
                continue
            content = pattern[i + 1:end]
            prefix = cur
            flush()
            if (prefix and "^" not in content and len(content) <= 4
                    and all(_is_literal(c) for c in content)):
                for c in content:
                    frags.append(prefix + c)
            if stack:
                stack[-1]["expect"] = False
            i = end + 1
            continue
        if _is_literal(ch):
            cur += ch
        else:
            # 字面中斷(・、量詞、數字、元字符):同一交替支內的前綴接合
            # 作廢——「召喚(・反転召喚)?」不得接成 召喚反転召喚
            flush()
            if stack:
                stack[-1]["expect"] = False
        i += 1
    flush()
    return frags


def split_particles(fragment):
    """片段依助詞切開,回傳內容詞片段清單。

    切分位置兩款:(a) 前一字非平假名(或前面剛切過助詞)——助詞接在名詞後;
    (b) 片段起點、且助詞後一字非平假名——「に戻す」的 regex 片段以助詞開頭
    (前面的受詞在 regex 裡是變數)。できる 的 で 後面是平假名き,兩款都
    擋得住。"""
    pieces = []
    cur = ""
    prev_is_boundary = True
    i = 0
    n = len(fragment)

    def _try(pos, at_start):
        for p in PARTICLES_MULTI:
            if fragment.startswith(p, pos):
                nxt = fragment[pos + len(p):pos + len(p) + 1]
                if not at_start or (nxt and not _is_hira(nxt)):
                    return p
        if fragment[pos] in PARTICLES_SINGLE:
            nxt = fragment[pos + 1:pos + 2]
            if not at_start or (nxt and not _is_hira(nxt)):
                return fragment[pos]
        return None

    while i < n:
        prev = fragment[i - 1] if i > 0 else None
        matched = None
        if i == 0:
            matched = _try(i, at_start=True)
        elif not _is_hira(prev) or prev_is_boundary:
            matched = _try(i, at_start=False)
        if matched:
            if cur:
                pieces.append(cur)
                cur = ""
            prev_is_boundary = True
            i += len(matched)
            continue
        cur += fragment[i]
        prev_is_boundary = False
        i += 1
    if cur:
        pieces.append(cur)
    return pieces


def _strip_trailing_particle(piece):
    """尾端單字助詞剝除:墓地か→墓地、永続罠カード扱いで→永続罠カード扱い。
    無條件剝(不看前一字)——這個領域沒有以單字助詞收尾的內容詞;剝後長度
    須 ≥2。「か」不在萃取端切分助詞表(〜か〜 的歧義,regex
    片段無上下文可判),只在這裡當尾端殘渣剝;分詞器端 R7 裁定(2026-10-07)
    已收為助詞。"""
    tail_chars = PARTICLES_SINGLE + "か"
    if len(piece) >= 3 and piece[-1] in tail_chars:
        return piece[:-1]
    return piece


def clean_pieces(fragment, min_len):
    """片段 → 助詞切分+過濾後的詞條清單。min_len 依來源(tag_rules 2 /
    glossary 1)。"""
    out = []
    for piece in split_particles(fragment):
        piece = _strip_trailing_particle(piece)
        if not piece or piece in PARTICLES or piece in BLOCKLIST:
            continue
        if all("A" <= c <= "Z" for c in piece):
            if piece in ASCII_WHITELIST:
                out.append(piece)
            continue
        if all(_is_hira(c) for c in piece):
            if piece in HIRA_WHITELIST:
                out.append(piece)
            continue
        if len(piece) < min_len:
            continue
        out.append(piece)
    return out


def from_tag_rules():
    """RULES + TIMING_RULES 的 pattern/exclude/action → 詞條集合。"""
    sources = []
    for rule in tag_rules.RULES:
        for key in ("pattern", "exclude", "action"):
            compiled = rule.get(key)
            if compiled is not None:
                sources.append(compiled.pattern)
    for rule in tag_rules.TIMING_RULES:
        for key in ("pattern", "exclude"):
            compiled = rule.get(key)
            if compiled is not None:
                sources.append(compiled.pattern)
    words = set()
    for pat in sources:
        for frag in extract_fragments(pat):
            words.update(clean_pieces(frag, min_len=2))
    return words


# glossary 日文欄的佔位符與護欄:剝掉後以邊界切段
_PLACEHOLDER_RE = re.compile(r"〈[^〉]*〉|〜|≠|[0-9０-９]+")


def from_glossary():
    """text_glossary.md 兩張表的日文欄(第一欄)→ 詞條集合。

    只收表頭第一欄是「日文/日文樣式」的表——體例說明表(「欄/說明」)的
    第一欄是中文欄名(禁譯、備註、庫內計數…),不是日文詞彙。"""
    words = set()
    in_target_table = False
    with open(GLOSSARY, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line.startswith("|"):
                # 表中夾雜的空行不重置(譯詞表在 E3 後有一個空行,表還沒完);
                # 體例表由「欄/說明」表頭關閉
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells or not cells[0]:
                continue
            head = cells[0]
            # 表頭須是多欄表(譯詞表 7 欄/模板表 6 欄);體例表「| 日文 |
            # 官方日文卡文的原詞 |」只有兩欄,不算表頭
            if head in ("日文", "日文樣式") and len(cells) >= 3:
                in_target_table = True
                continue
            if head in ("欄", "說明"):
                in_target_table = False
                continue
            if set(head) <= set("-: ") or not in_target_table:
                continue
            # 佔位符/護欄/數字 → 邊界;再依字面字元切出片段
            text = _PLACEHOLDER_RE.sub(" ", head)
            frag = ""
            frags = []
            for ch in text:
                if _is_literal(ch):
                    frag += ch
                else:
                    if frag:
                        frags.append(frag)
                    frag = ""
            if frag:
                frags.append(frag)
            for piece in frags:
                words.update(clean_pieces(piece, min_len=1))
    return words


# R12(b) 定案(2026-10-07 站主核可全收):高頻原生詞以活用形補詞典——
# (詞元, 類別, 詞形)。清單由語料 OOV 表產出(R1/R7/R10 落地後),動詞照
# 送る/選ぶ 先例收整個活用形(含 て/た),後接的 いる/ない 等歸 (a);
# 單字漢字名詞與 ルール上/同一/目/方/両隣 一併收,壓掉切開後的殘段。
# prepare_view.py 讀這份清單產審閱表
R12B_WORDS = (
    ("後", "名詞", ("後",)), ("他", "名詞", ("他",)),
    ("中", "名詞", ("中",)), ("上", "名詞", ("上",)),
    ("ルール上", "名詞", ("ルール上",)), ("同一", "名詞", ("同一",)),
    ("目", "名詞", ("目",)), ("方", "名詞", ("方",)),
    ("両隣", "名詞", ("両隣",)),
    ("下", "名詞", ("下",)), ("前", "名詞", ("前",)),
    ("内", "名詞", ("内",)), ("分", "名詞", ("分",)),
    ("差", "名詞", ("差",)), ("倍", "名詞", ("倍",)),
    ("隣", "名詞", ("隣",)), ("事", "名詞", ("事",)),
    ("際", "名詞", ("際",)), ("罠", "名詞", ("罠",)),
    ("終了", "名詞", ("終了",)), ("種類", "名詞", ("種類",)),
    ("合計", "名詞", ("合計",)), ("同名", "名詞", ("同名",)),
    ("自身", "名詞", ("自身",)), ("任意", "名詞", ("任意",)),
    ("開始", "名詞", ("開始",)), ("発生", "名詞", ("発生",)),
    ("状態", "名詞", ("状態",)), ("移動", "名詞", ("移動",)),
    ("方法", "名詞", ("方法",)), ("最大", "名詞", ("最大",)),
    ("位置", "名詞", ("位置",)), ("正面", "名詞", ("正面",)),
    ("中央", "名詞", ("中央",)), ("同士", "名詞", ("同士",)),
    ("処理", "名詞", ("処理",)), ("チェーン", "名詞", ("チェーン",)),
    ("残り", "名詞", ("残り",)), ("もう片方", "名詞", ("もう片方",)),
    ("メインモンスターゾーン", "名詞", ("メインモンスターゾーン",)),
    ("奇数", "名詞", ("奇数",)), ("偶数", "名詞", ("偶数",)),
    ("倍数", "名詞", ("倍数",)), ("回数", "名詞", ("回数",)),
    ("複数", "名詞", ("複数",)), ("数字", "名詞", ("数字",)),
    ("上記", "名詞", ("上記",)), ("可能", "名詞", ("可能",)),
    ("必要", "名詞", ("必要",)), ("既に", "副詞", ("既に",)),
    ("星", "規格記法", ("星",)), ("攻", "規格記法", ("攻",)),
    ("守", "規格記法", ("守",)),
    ("持つ", "動詞", ("持つ", "持って", "持った", "持た")),
    ("含む", "動詞", ("含む", "含まれる")),
    ("除く", "動詞", ("除く", "除き", "除かれ", "除かれた", "除け")),
    ("行う", "動詞", ("行った", "行って", "行わず", "行え")),
    ("行く", "動詞", ("行かず",)),
    ("置く", "動詞", ("置いた", "置かれ", "置かれた",
                      "置かれて", "置かれる")),
    ("上げる", "動詞", ("上げる", "上げ", "上げた")),
    ("下げる", "動詞", ("下げる", "下げ", "下げた")),
    ("異なる", "動詞", ("異なる", "異なり")),
    ("違う", "動詞", ("違う", "違った")),
    ("加わる", "動詞", ("加わる", "加わった")),
    ("出る", "動詞", ("出る", "出た")),
    ("出す", "動詞", ("出す", "出せる", "出せ")),
    ("続ける", "動詞", ("続ける", "続けて", "続け")),
    ("得る", "動詞", ("得た",)),
    ("離れる", "動詞", ("離れ", "離れる")),
    ("当てる", "動詞", ("当てる",)),
    ("当たる", "動詞", ("当たった",)),
    ("見る", "動詞", ("見て",)),
    ("積む", "動詞", ("積まれ", "積まれて")),
    ("決める", "動詞", ("決められた",)),
    ("めくる", "動詞", ("めくる", "めくり", "めくった", "めくって",
                        "めくられ", "めくられた", "めくられて")),
    ("記す", "動詞", ("記された", "記されて")),
    ("扱う", "動詞", ("扱わ",)),
    ("高い", "形容詞", ("高い", "高く")),
    ("低い", "形容詞", ("低い", "低く")),
    ("多い", "形容詞", ("多い", "多く", "多けれ")),
    ("少ない", "形容詞", ("少ない", "少なく")),
    ("無い", "形容詞", ("無い", "無かった")),
)
# 第三批殘餘 OOV 補詞(2026-10-08 站主裁定 B~E 全入):(詞元, 類別, 詞形),
# 處理方式同 R12B_WORDS(manual 來源+lemma)
R12C_WORDS = (
    ("最小", "名詞", ("最小",)), ("ハズレ", "名詞", ("ハズレ",)),
    ("順番", "名詞", ("順番",)), ("順", "名詞", ("順",)),
    ("テキスト", "名詞", ("テキスト",)), ("条件", "名詞", ("条件",)),
    ("以降", "名詞", ("以降",)), ("正規", "名詞", ("正規",)),
    ("ジャンケン", "名詞", ("ジャンケン",)), ("制限", "名詞", ("制限",)),
    ("結果", "名詞", ("結果",)), ("値", "名詞", ("値",)),
    ("左", "名詞", ("左",)), ("名", "名詞", ("名",)),
    ("複数回", "名詞", ("複数回",)),
    ("どこ", "疑問詞", ("どこ",)), ("どちらか", "疑問詞", ("どちらか",)),
    ("いつでも", "副詞", ("いつでも",)),
    ("下がる", "動詞", ("下がり", "下がる")),
    ("上がる", "動詞", ("上がり", "上がる")), ("小さい", "形容詞", ("小さい",)),
    ("正しい", "形容詞", ("正しい",)),
    ("する", "動詞", ("すれば",)),
    ("払う", "動詞", ("払わ",)),
    ("ない", "助動詞", ("なく",)),
    ("取り除く", "動詞", ("取り除か",)),
    ("選ぶ", "動詞", ("選べ",)),
    ("渡す", "動詞", ("渡して", "渡さ")),
    ("加える", "動詞", ("加えられ",)),
    ("振る", "動詞", ("振ら",)),
    ("揃う", "動詞", ("揃った",)),
    ("超える", "動詞", ("超え",)),
    ("近づく", "動詞", ("近づく",)),
    ("繰り返す", "動詞", ("繰り返す",)),
    ("持つ", "動詞", ("持ち",)),
    ("多い", "形容詞", ("多ければ",)),
    ("引き分け", "名詞", ("引き分け",)), ("負ける", "動詞", ("負け",)),
    ("やり直す", "動詞", ("やり直す",)),
    ("－", "符號", ("－",)), ("EXリンク", "名詞", ("EXリンク",)),
    ("時計回り", "名詞", ("時計回り",)),
)
# ADR-0014 重複覆蓋總整理(2026-10-08 站主核可審閱表全照提案)
# 封閉值域:卡文中官方枚舉值的字面,整詞不拆;lexicon.json 以 closed 欄標類別,
# 分詞器據此做列舉前項擴大(魔法・罠カード 的 魔法 → 魔法(カード))
_RACES = ("戦士族", "魔法使い族", "天使族", "悪魔族", "アンデット族", "機械族",
          "水族", "炎族", "岩石族", "鳥獣族", "植物族", "昆虫族", "雷族",
          "ドラゴン族", "獣族", "獣戦士族", "恐竜族", "魚族", "海竜族",
          "爬虫類族", "サイキック族", "幻神獣族", "創造神族", "幻竜族",
          "サイバース族", "幻想魔族")
_SUBTYPES = ("通常魔法", "速攻魔法", "永続魔法", "装備魔法", "フィールド魔法",
             "儀式魔法", "通常罠", "永続罠", "カウンター罠", "通常モンスター",
             "効果モンスター", "リバースモンスター", "デュアルモンスター",
             "スピリットモンスター", "ユニオンモンスター", "トゥーンモンスター",
             "トゥーン")
CLOSED_VALUES = {
    "種族": _RACES,
    "卡片子類型": _SUBTYPES,
    "階段名": ("ドローフェイズ", "スタンバイフェイズ", "メインフェイズ",
              "メインフェイズ１", "メインフェイズ２", "バトルフェイズ",
              "エンドフェイズ", "バトルステップ", "ダメージステップ"),
    "區域名": ("モンスターゾーン", "魔法＆罠ゾーン", "フィールドゾーン", "Pゾーン",
              "EXモンスターゾーン", "エクストラモンスターゾーン",
              "メインモンスターゾーン", "エクストラデッキ", "EXデッキ"),
    "表示形式": ("攻撃表示", "守備表示", "表側表示", "裏側表示", "表側攻撃表示",
              "表側守備表示", "裏側守備表示"),
    "卡種+カード": ("魔法カード", "罠カード", "モンスターカード", "装備カード")
                 + tuple(st + "カード" for st in _SUBTYPES),
    "玩家+區域": ("自分フィールド", "相手フィールド"),
    "傷害種類": ("戦闘ダメージ", "効果ダメージ"),
}

# 可拆詞條:拆成其他詞條(含 R1 家族推翻改拆),從詞典拿掉
OVERLAP_SPLIT = (
    "墓地へ送られた", "墓地へ送る", "墓地へ送って", "墓地へ送り", "デッキに戻す", "手札に戻す", "墓地へ送った",
    "デッキに戻し", "手札に戻し", "墓地へ送られる", "EXデッキに戻す", "墓地へ送られて", "EXデッキに戻し",
    "デッキに戻して", "手札に戻る", "墓地へ送らず", "墓地へ送らなければ", "デッキに戻した", "手札に戻った", "デッキに戻る",
    "手札に戻して", "EXデッキに戻して", "手札に戻した", "EXデッキに戻る", "EXデッキに戻した", "EXデッキに戻った",
    "デッキに戻さず", "デッキに戻った", "墓地へ送られ", "デッキに戻さなければ", "手札に戻らず", "墓地へ送らなかった",
    "手札に戻さなければ", "カード名", "ターン終了", "存在する限り", "チューナー以外", "除外状態", "攻撃宣言", "リンク先",
    "存在する状態", "除外されている", "直接攻撃", "攻撃対象", "装備カード扱い", "素材モンスター", "召喚条件", "効果処理",
    "数値分", "超えた分", "召喚する事", "する度", "する事", "永続魔法カード扱い", "デュエル中", "お互いのプレイヤー",
    "リリースなしで召喚", "置く事", "扱う事", "リンク状態", "する際", "永続罠カード扱い", "ドロー以外", "したレベル",
    "取り除く事", "攻撃しなければならない", "宣言した種類", "戻した数", "魔法カード扱い", "倍数", "公開し続け", "両隣",
    "リリースして表側表示", "リリースして召喚", "必要なくなる", "破壊する効果", "払うLP", "見せる事", "払う事",
    "破壊されるカード", "破壊されるモンスター", "リリースする事", "し続け", "する状態", "カード扱い", "セットする事",
    "リンク召喚扱い", "体分", "儀式召喚扱い", "変更する事", "罠ゾーン", "融合召喚扱い", "裏側守備",
)

# 拆後零命中詞條:刪除(封閉值與比較詞規則用的不在此)
OVERLAP_ZERO_DELETE = (
    "S召喚扱い", "X召喚扱い", "エクストラ", "スケール", "ライフポイント", "体", "入れ替", "入れ替え",
    "入れ替わった", "取り除", "取り除ける", "多けれ", "守備", "得て", "戻された", "戻せない", "払", "払えば",
    "捨てられ", "満たさ", "満たした", "特殊召喚する事", "特殊召喚する際", "積まれ", "表示", "複数", "除かれ",
    "除かれた", "除け", "ＬＰ",
)

# R1 推翻後缺的動詞活用形(活用形不拆):(詞元, 詞形)
R1_VERB_FORMS = (
    ("送る", ("送る", "送り", "送って", "送った", "送ら", "送らず",
              "送られ", "送られた")),
    ("戻す", ("戻す", "戻し", "戻して", "戻さ")),
    ("戻る", ("戻る", "戻り", "戻った", "戻ら")),
)
# 封閉值清單上、語料零出現且原不在詞典的值:不入典
_CLOSED_UNSEEN = (
    "エクストラモンスターゾーン", "通常モンスターカード", "効果モンスターカード", "リバースモンスターカード",
    "デュアルモンスターカード", "スピリットモンスターカード", "トゥーンモンスターカード", "トゥーンカード",
)


# 已在表的同家族詞形:不新增詞條,只補 lemma
R12B_EXISTING = {"行い": "行う", "行う": "行う", "置き": "置く", "置く": "置く",
                 "置いて": "置く",
                 "得て": "得る", "得る": "得る", "離れた": "離れる",
                 "扱い": "扱う", "扱う": "扱う"}

# R12(a) 定案(2026-10-07 站主核可全收):功能詞封閉類與殘片清理——
# (詞, 類別, 詞形)。活用尾/補助動詞/なる・ない 活用/繫詞/形式名詞/副詞/
# 代名詞/複合格整詞入典(manual,lemma 記「詞」欄);「剝除」類是 regex
# 斷尾殘片(破壊されな 把 破壊されない 切成 破壊されな|い),從詞典拿掉;
# 詞幹補形是風險樣本暴露的缺形。prepare_view.py 讀這份清單產審閱表
R12A_WORDS = (
    ("破壊されな", "剝除", ("破壊されな", "破壊されなくな")),
    ("受けなくな", "剝除", ("受けなくな",)),
    ("必要なくな", "剝除", ("必要なくな", "必要なくなり")),
    ("て", "活用尾", ("て",)), ("た", "活用尾", ("た",)),
    ("る", "活用尾", ("る",)), ("ず", "活用尾", ("ず",)),
    ("った", "活用尾", ("った",)),
    ("いる", "補助動詞", ("いる", "いた", "いない", "いれば")),
    ("ある", "補助動詞", ("ある", "あった", "あれば")),
    ("なる", "なる/ない活用", ("なり", "なった", "なって", "なら",
                                "なかった", "なければ")),
    ("だ", "繫詞", ("だった",)), ("な", "繫詞", ("な",)),
    ("せず", "サ変否定", ("せず",)), ("でき", "可能形", ("でき",)),
    ("ため", "形式名詞", ("ため",)), ("よう", "形式名詞", ("よう",)),
    ("まま", "形式名詞", ("まま",)), ("つき", "形式名詞", ("つき",)),
    ("もう", "副詞", ("もう",)), ("さらに", "副詞", ("さらに",)),
    ("また", "副詞", ("また",)),
    ("それ", "代名詞", ("それ", "それら")),
    ("なくす", "動詞", ("なくす",)),
    ("取り除く", "詞幹補形", ("取り除かれ", "取り除かれた", "取り除いた",
                              "取り除け")),
    ("戻る", "詞幹補形", ("戻る", "戻り", "戻った")),
    ("払う", "詞幹補形", ("払った", "払わず")),
    ("選ぶ", "詞幹補形", ("選ば",)),
    ("満たす", "詞幹補形", ("満たす", "満たして", "満たした", "満たさ")),
    ("揃う", "詞幹補形", ("揃って",)),
    ("数える", "詞幹補形", ("数えて",)),
    ("振る", "詞幹補形", ("振った",)),
    ("移る", "詞幹補形", ("移った",)),
    ("入れ替わる", "詞幹補形", ("入れ替わる", "入れ替わった")),
    ("よる", "複合格", ("よる", "よって", "よらず")),
    ("いずれ", "代名詞", ("いずれ",)),
    ("表", "名詞", ("表",)), ("裏", "名詞", ("裏",)),
    ("組み合わせ", "名詞", ("組み合わせ",)),
)


def main():
    rule_words = from_tag_rules()
    glossary_words = from_glossary()
    merged = {}
    for word in rule_words:
        merged.setdefault(word, set()).add("tag_rules")
    for word in glossary_words:
        merged.setdefault(word, set()).add("glossary")
    # 終篩:「〜でき(る)」複合形若其詞幹已獨立在表,丟棄複合形——切分慣例
    # 定可能形獨立成 token(conventions.md),留複合形會讓最長匹配把 できる
    # 黏回去,同一個句型切出兩種樣子
    for word in list(merged):
        for suffix in ("できない", "できず", "できる", "でき"):
            if word != suffix and word.endswith(suffix):
                stem = _strip_trailing_particle(word[:-len(suffix)])
                if stem in merged:
                    del merged[word]
                break
    # R5 裁定(2026-10-01 站主):この/その+已收入詞 → 指示綁定 token,
    # 複合詞條剝除;その後 例外整詞保留(「後」單字不在表)。餘詞不在表內
    # 時保留複合,避免剝了反而製造 OOV。
    for word in list(merged):
        if word == "その後":
            continue
        for dem in ("この", "その"):
            if word.startswith(dem) and len(word) > len(dem):
                if word[len(dem):] in merged:
                    del merged[word]
                break
    # 比較詞裁定(2026-10-01 站主):接不上數量的 以下/以上/未満(回指
    # 「以下の効果」等)獨立成詞;數量後的比較用法由分詞器綁進 q: token
    for word in ("以下", "以上", "未満"):
        merged.setdefault(word, set()).add("manual")
    # 計數器名裁定(2026-10-01):カウンター罠(反擊陷阱)整詞入典,
    # 擋計數器名綁定誤觸;〈名〉カウンター由分詞器綁 k: token
    merged.setdefault("カウンター罠", set()).add("manual")
    # 屬性綁定裁定(2026-10-01):〇属性 由分詞器綁 a: token,
    # 属性モンスター 複合詞條拆除(属性 歸綁定、モンスター 歸詞典)
    merged.pop("属性モンスター", None)
    # 種族裁定(2026-10-01):26 種族整詞入典——清單以值域正典為準
    # (script/web/vocab.py 的 _RACE,26 值),日文名對照 OCG 官方種族名;
    # 魔法使い族 整詞以最長匹配壓過「魔法」,修誤切
    races_ja = (
        "戦士族", "魔法使い族", "天使族", "悪魔族", "アンデット族",
        "機械族", "水族", "炎族", "岩石族", "鳥獣族", "植物族", "昆虫族",
        "雷族", "ドラゴン族", "獣族", "獣戦士族", "恐竜族", "魚族",
        "海竜族", "爬虫類族", "サイキック族", "幻神獣族", "創造神族",
        "幻竜族", "サイバース族", "幻想魔族",
    )
    for word in races_ja:
        merged.setdefault(word, set()).add("manual")
    # 時/同時入典+R4 定案(2026-10-01 站主):場合/時 結尾的複合全拆,
    # 場合/時 獨立成時機標記(時 可能錯過時點、場合 不會——差異落在單一
    # token 位);同時 整詞擋歧義(〜と同時に)。剝除後的殘幹:非純平假名
    # 自動補進詞典(ターン終了/攻撃宣言等),純平假名留給白名單與 R12。
    for word in ("時", "同時"):
        merged.setdefault(word, set()).add("manual")
    # 選んで進詞(2026-10-01 站主裁定);選び/選ぶ/選んだ 同日補齊全家族,
    # 並以 lemma 欄記同詞源(選ぶ)——詞條各自獨立、模板不收斂,lemma 只是
    # 給後續推導「按詞元分組」的鉤子
    for word in ("選んで", "選び", "選ぶ", "選んだ"):
        merged.setdefault(word, set()).add("manual")
    # R2 定案(2026-10-01 站主):サ変+する家族一律拆——する/した/して/し/
    # され系 結尾的複合詞條剝除,動作名詞與時態正交(與 R3 できる、R4
    # 場合/時 同一邏輯)。殘幹非純平假名且 ≥2 字才拆(擋 残して 這類原生
    # 動詞被斬首);連用形 し/して 補進功能詞。
    for word in ("し", "して", "される", "された", "されて",
                 "されない", "されず"):
        merged.setdefault(word, set()).add("manual")
    # 剝除順序:R4(場合/時)先、R2(サ変)後——R4 剝出的殘幹
    # (破壊される/特殊召喚した)要再經 R2 剝一次
    for word in list(merged):
        if word in ("場合", "時", "同時"):
            continue
        for suf in ("場合", "時"):
            if word.endswith(suf):
                stem = word[:-len(suf)]
                srcs = merged.pop(word)
                if stem and not all(_is_hira(c) for c in stem):
                    merged.setdefault(stem, set()).update(srcs)
                break
    _SAHEN_SUF = ("されない", "されず", "された", "される", "されて",
                  "され", "して", "した", "する", "し")
    for word in list(merged):
        if word in _SAHEN_SUF:
            continue
        for suf in _SAHEN_SUF:
            if word.endswith(suf):
                stem = word[:-len(suf)]
                if len(stem) >= 2 and not all(_is_hira(c) for c in stem):
                    srcs = merged.pop(word)
                    merged.setdefault(stem, set()).update(srcs)
                break
    # 卡片子類型裁定(2026-10-01 站主:全收):封閉值域整詞入典,補齊
    # 已在詞典的 効果モンスター/Sモンスター/カウンター罠 等的家族——
    # 粒度一致;魔陷側是卡片種類的字面(速攻魔法カードの効果)
    subtypes = (
        "リバースモンスター",
        "デュアルモンスター", "スピリットモンスター", "ユニオンモンスター",
        "トゥーンモンスター", "トゥーン",
        "通常魔法", "速攻魔法", "永続魔法", "装備魔法",
        "フィールド魔法", "儀式魔法", "通常罠", "永続罠",
    )
    for word in subtypes:
        merged.setdefault(word, set()).add("manual")
    # 效果外文本檢視裁定(2026-10-03 站主):それぞれ/いずれか(使用次數
    # 限制句骨架)與 ＋/×(素材行的加號、數值運算的乘號)整詞入典——
    # 符號不屬字面字元,只能走 manual;のみ 歸助詞封閉類(分詞器端)
    for word in ("それぞれ", "いずれか", "＋", "×"):
        merged.setdefault(word, set()).add("manual")
    # ●選項標籤檢查補詞(2026-10-07 站主裁定):位置詞與 中央 同組、
    # 大きい 比照 R12(b) 的 高い/多い
    for word in ("左端", "右端", "左側", "右側", "大きい"):
        merged.setdefault(word, set()).add("manual")
    # 殘餘 OOV 補詞(2026-10-07 站主裁定):個 另進量詞集合(分詞器端),
    # ヵ所 只當量詞(語料全接數字)
    for word in ("対", "降臨", "毎", "デュエル", "勝利", "どちらも", "個",
                 "先", "合わせ"):
        merged.setdefault(word, set()).add("manual")
    # 第二批殘餘 OOV 補詞(2026-10-07 站主裁定):裸 この 比照 その(分詞器
    # 照舊優先指示綁定);階段名補 メインフェイズ１/２ 與 バトルステップ
    # (ドロー/スタンバイ/メイン/バトル/エンドフェイズ 原已在表)
    for word in ("この", "両", "失い", "元", "代用",
                 "メインフェイズ１", "メインフェイズ２", "バトルステップ"):
        merged.setdefault(word, set()).add("manual")
    # 通常 的形容詞用法整詞入典;通常召喚 改走召喚法兩格(分詞器 m:通常|
    # 召喚),複合詞條剝除(2026-10-08 站主裁定)
    # 同日改裁:通常の攻撃/通常のドロー 兩條整詞改為 通常の 一條
    # (通常の|攻撃、通常の|ドロー、通常の|P|召喚)
    merged.setdefault("通常の", set()).add("manual")
    merged.pop("通常召喚", None)
    # 反転/特殊/アドバンス 同日加入召喚法(後接 召喚 才成立),整詞剝除;
    # 單獨的 特殊 是零命中殘片,留著會讓 その特殊召喚 綁成 その特殊
    for word in ("反転召喚", "特殊召喚", "アドバンス召喚", "特殊"):
        merged.pop(word, None)
    # 裸 その 入典(2026-10-07 站主裁定,改 R5 第三款):接不上詞典詞的
    # その 不再落 OOV;接得上時分詞器照舊出指示綁定
    merged.setdefault("その", set()).add("manual")
    # 同じ/全て 入典(2026-10-03 站主裁定)
    for word in ("同じ", "全て"):
        merged.setdefault(word, set()).add("manual")
    # 複合詞條拆除(2026-10-06 站主裁定):全て破壊/同じレベル/同じ数値
    # 剝除,全て/同じ 只剩一種粒度(與 R5/R4/R2/R9 剝除複合同向);数値
    # 同輪入典(剝後餘詞不落 OOV)。餘詞不在表內時保留複合,同 R5 保險。
    merged.setdefault("数値", set()).add("manual")
    for word in list(merged):
        for head in ("同じ", "全て"):
            if word.startswith(head) and len(word) > len(head):
                if word[len(head):] in merged:
                    del merged[word]
                break
    # R9 定案(2026-10-02 站主):召喚法七法(リンク/融合/儀式/S/X/P/L)
    # 由分詞器出 m: token,「法+素材/モンスター/召喚」全矩陣統一兩格——
    # 法系複合詞條剝除(恰為 法+名詞 者;X召喚扱い 這類更長複合不動);
    # 性質系子類型(通常/効果/リバース等)維持整詞
    _method_noun = re.compile(
        r"^(?:リンク|融合|儀式|S|X|P|L|A)(?:素材|モンスター|召喚)$")
    for word in list(merged):
        if _method_noun.match(word):
            merged.pop(word)
    # R1(2026-10-07 複合移動動詞整詞)由 ADR-0014(2026-10-08)推翻:
    # 墓地へ送る → 墓地|へ|送る,動詞活用形整詞補齊並記 lemma
    lemma_of = {}
    for lemma, forms in R1_VERB_FORMS:
        for form in forms:
            merged.setdefault(form, set()).add("manual")
            lemma_of[form] = lemma
    for lemma, _cat, forms in R12B_WORDS:
        for form in forms:
            merged.setdefault(form, set()).add("manual")
            lemma_of[form] = lemma
    lemma_of.update(R12B_EXISTING)
    for lemma, _cat, forms in R12C_WORDS:
        for form in forms:
            merged.setdefault(form, set()).add("manual")
            lemma_of.setdefault(form, lemma)
    for word, cat, forms in R12A_WORDS:
        for form in forms:
            if cat == "剝除":
                merged.pop(form, None)
            else:
                merged.setdefault(form, set()).add("manual")
                lemma_of.setdefault(form, word)
    # 詞元(lemma):同詞源活用形的分組鉤子——選ぶ 家族、R1 複合移動動詞、
    # R12(b) 補詞;詞條各自獨立、模板不收斂
    lemma_of.update({"選んで": "選ぶ", "選び": "選ぶ", "選んだ": "選ぶ",
                     "選ぶ": "選ぶ"})
    # ADR-0014:可拆詞條與零命中詞條剝除;封閉值全數入典並標類別
    for word in OVERLAP_SPLIT + OVERLAP_ZERO_DELETE:
        merged.pop(word, None)
    closed_of = {}
    for kind, values in CLOSED_VALUES.items():
        for value in values:
            closed_of[value] = kind
            if value not in merged and value not in _CLOSED_UNSEEN:
                merged.setdefault(value, set()).add("manual")
    entries = []
    for pos, surface in enumerate(sorted(merged), start=1):
        entry = {"id": "W%04d" % pos, "surface": surface,
                 "sources": sorted(merged[surface])}
        if surface in lemma_of:
            entry["lemma"] = lemma_of[surface]
        if surface in closed_of:
            entry["closed"] = closed_of[surface]
        entries.append(entry)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(entries, f, ensure_ascii=False, indent=1)
        f.write("\n")
    both = sum(1 for e in entries if len(e["sources"]) == 2)
    print("tag_rules 詞條: %d" % len(rule_words))
    print("glossary 詞條: %d" % len(glossary_words))
    print("合併去重: %d(兩源皆有 %d)" % (len(entries), both))
    print("已寫出 %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
