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
                   "では", "及び", "しか", "のみ")
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
    須 ≥2。「か」不在切分助詞表(〜か〜 的歧義),只在這裡當尾端殘渣剝。"""
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
    # 同じ/全て 入典(2026-10-03 站主裁定)
    for word in ("同じ", "全て"):
        merged.setdefault(word, set()).add("manual")
    # R9 定案(2026-10-02 站主):召喚法七法(リンク/融合/儀式/S/X/P/L)
    # 由分詞器出 m: token,「法+素材/モンスター/召喚」全矩陣統一兩格——
    # 法系複合詞條剝除(恰為 法+名詞 者;X召喚扱い 這類更長複合不動);
    # 性質系子類型(通常/効果/リバース等)維持整詞
    _method_noun = re.compile(
        r"^(?:リンク|融合|儀式|S|X|P|L)(?:素材|モンスター|召喚)$")
    for word in list(merged):
        if _method_noun.match(word):
            merged.pop(word)
    # 詞元(lemma):同詞源活用形的分組鉤子,現階段只標 選ぶ 家族;
    # 全面標注等 R12(活用形窮舉)一併生成
    lemma_of = {"選んで": "選ぶ", "選び": "選ぶ", "選んだ": "選ぶ",
                "選ぶ": "選ぶ"}
    entries = []
    for pos, surface in enumerate(sorted(merged), start=1):
        entry = {"id": "W%04d" % pos, "surface": surface,
                 "sources": sorted(merged[surface])}
        if surface in lemma_of:
            entry["lemma"] = lemma_of[surface]
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
