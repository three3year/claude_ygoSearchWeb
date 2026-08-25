"""卡文詞彙表驗證接縫:詞彙表 md 全文+卡句記錄 → 結構化不一致清單。

純函式、不做 IO(接縫 2026-08-24 站主確認,spec .scratch/text-glossary/
spec.md);報告式,回傳清單供殼層排版,不阻擋建置。

樣式 → 機器比對規則(md 只維護人讀樣式,推導定義在此):
    〈n〉  → 連續數字 ``[0-9０-９]+``。中文側卡文依規範用半形、日文側官方
            卡文用全形,比對一律兩者皆容許——寬窄之辨歸《文本格式規範》§2,
            不歸本表。
    〜    → 同句內任意內文 ``[^。\\n]*``(不跨句號、不跨行)。
    〈時點〉→ 階段/時點名,**中日成對替換**(2026-08-24 站主核可):日文側
            匹配 ターン/ドローフェイズ/スタンバイフェイズ/メインフェイズ/
            バトルフェイズ/エンドフェイズ/ダメージステップ 之一,中文側須
            在對應槽位出現**配對**的 回合/抽牌階段/準備階段/主要階段/
            戰鬥階段/結束階段/傷害步驟——日文命中哪個,中文就查哪個,
            錯位(日文主要階段、中文寫成準備階段)因此也查得到。同一句
            多次命中時逐一驗,缺任一配對即報。兩側樣式的〈時點〉槽數必須
            相等,否則解析失敗;禁譯欄內的〈時點〉**不配對**,任一時點名
            命中即算(禁譯要抓的是形,不是哪個階段)。
    其餘字元照字面比對(re.escape)。出現上述以外的 ``〈…〉`` 佔位符或
    落單的 ``〈``/``〉`` 即解析失敗。

檢查兩級,同一套比對機器,只差條目來源與問題名稱:
    譯詞:日文側含「日文」欄樣式 → 中文側須含「規範譯法」樣式(否則報
          「未用規範譯法」),且不得命中「禁譯」欄任一樣式(否則報「用禁譯」,
          規範與禁譯並存時仍報禁譯——句中混用也是不一致)。
    句式:日文側命中「日文樣式」 → 中文側須命中「中文樣式」(否則報
          「未照模板」),禁譯同上。
「規範譯法」「中文樣式」欄可以「;」(半形或全形)分隔**多個規範形**,任一形
命中即照規範(2026-08-25 站主裁示,票03 追記;首例 ドローする 定數形
「抽〈n〉張卡」+變數形「依照〜數量，〜抽牌。」)。帶〈時點〉時每一形的槽數
都須與日文側相等,否則解析失敗。
「日文」「日文樣式」欄可用「≠」附**負向護欄**:`樣式≠排除樣式1;排除樣式2`
——比對前先把排除樣式命中的段落遮掉,命中整段落在裡面就不算命中(2026-08-25
站主指出 Xモンスター 誤中 EXモンスターゾーン;短樣式被長詞包住的誤中走這裡,
單卡的「不用修」走「例外」欄)。排除樣式支援同一套佔位符。
「例外」欄所列卡片密碼對該條目自動跳過;無日文卡文的記錄(ot=2 繁中單側)
整筆跳過——檢查以日文側為門。

解析大聲失敗(GlossaryError):兩節標題(譯詞對照/句式模板)缺一、表格
列欄數不是 7、佔位符不明、例外欄不是「—」或卡片密碼逗號清單。
"""
import re

# 欄位序照 docs/text_glossary.md 體例:譯詞與句式同欄數,前兩欄語意對應
# (日文/日文樣式、規範譯法/中文樣式)
_COLUMNS = 7
_EMPTY = "—"

_LEVEL_TERM = "譯詞"
_LEVEL_PATTERN = "句式"
# (節標題關鍵字, 級別, 中文側未達標時的問題名)
_SECTIONS = (("譯詞對照", _LEVEL_TERM, "未用規範譯法"),
             ("句式模板", _LEVEL_PATTERN, "未照模板"))

_TOKEN_RE = re.compile(r"(〈[^〉]*〉|〜)")
_NUM_RE = "[0-9０-９]+"
_ANY_RE = "[^。\n]*"
_SEPARATOR_RE = re.compile(r"^[-: ]+$")

# 〈時點〉的中日配對表(單一來源;順序=alternation 順序,無互為前綴之虞)
_TIME_TOKEN = "〈時點〉"
_TIME_UNITS = (("ダメージステップ", "傷害步驟"),
               ("ドローフェイズ", "抽牌階段"),
               ("スタンバイフェイズ", "準備階段"),
               ("メインフェイズ", "主要階段"),
               ("バトルフェイズ", "戰鬥階段"),
               ("エンドフェイズ", "結束階段"),
               ("ターン", "回合"))
_TIME_JA2ZH = dict(_TIME_UNITS)
_TIME_JA_GROUP = "(" + "|".join(ja for ja, _ in _TIME_UNITS) + ")"
_TIME_ZH_ANY = "(?:" + "|".join(zh for _, zh in _TIME_UNITS) + ")"
_TIME_SLOT = "\x00"  # 中文模板的槽位標記(卡文不可能出現此字元)
# 日文樣式的負向護欄:「樣式≠排除樣式1;排除樣式2」。比對前先把排除樣式命中的
# 段落遮成不可能匹配的字元(等長,不動其餘位置),命中落在裡面就自然消失。
# 用途是短樣式被長詞包住的誤中(2026-08-25 站主指出:Xモンスター 誤中
# EXモンスターゾーン),不是給條目寫例外——例外走「例外」欄。
_EXCLUDE_SEP = "≠"
_MASK_CHAR = "\x01"


class GlossaryError(ValueError):
    """詞彙表解析失敗:格式壞了要立即發現,不靜默漏檢。"""


def _compile_style(style, row, time_mode="none"):
    """人讀樣式 → (regex 或模板 parts, 〈時點〉槽數)。

    time_mode 決定 〈時點〉 的推導(推導規則見模組 docstring):
        "ja"    → 日文側 alternation 捕捉群(供跨側配對取值)
        "zh"    → 中文側槽位標記,回傳模板 parts 由 _fill_time_slots 現場填
        "plain" → 不配對的中文 alternation(禁譯欄用)
        "none"  → 不接受 〈時點〉(出現即解析失敗)
    回傳 (compiled_regex, 0) 或——time_mode=="zh" 且有槽時——(parts, 槽數)。
    """
    parts, slots = [], 0
    for token in _TOKEN_RE.split(style):
        if token == "〜":
            parts.append(_ANY_RE)
        elif token == _TIME_TOKEN and time_mode != "none":
            slots += 1
            if time_mode == "ja":
                parts.append(_TIME_JA_GROUP)
            elif time_mode == "plain":
                parts.append(_TIME_ZH_ANY)
            else:
                parts.append(_TIME_SLOT)
        elif token.startswith("〈"):
            if token != "〈n〉":
                raise GlossaryError(f"佔位符不明:{token}(列:{row})")
            parts.append(_NUM_RE)
        else:
            if "〈" in token or "〉" in token:
                raise GlossaryError(f"佔位符括號落單:{style}(列:{row})")
            parts.append(re.escape(token))
    if time_mode == "zh" and slots:
        return parts, slots
    return re.compile("".join(parts)), (slots if time_mode == "ja" else 0)


def _fill_time_slots(zh_parts, units):
    """中文模板 parts+日文側命中的時點 → 該次配對的具體 regex。"""
    it = iter(units)
    filled = [re.escape(_TIME_JA2ZH[next(it)]) if part == _TIME_SLOT else part
              for part in zh_parts]
    return re.compile("".join(filled))


def _parse_ja_style(cell, row):
    """日文欄 → (主樣式, 排除樣式清單)。無「≠」時排除清單為空。"""
    style, _, excluded = cell.partition(_EXCLUDE_SEP)
    excludes = [_compile_style(part.strip(), row)[0]
                for part in re.split(r"[;；]", excluded) if part.strip()]
    return style.strip(), excludes


def _mask_excluded(ja, excludes):
    """把排除樣式命中的段落遮掉(等長替換),供主樣式比對用。"""
    for rx in excludes:
        ja = rx.sub(lambda m: _MASK_CHAR * len(m.group(0)), ja)
    return ja


def _parse_exceptions(cell, row):
    """例外欄 → 卡片密碼集合;「—」為空,其餘必須是逗號分隔的數字。"""
    if cell == _EMPTY:
        return frozenset()
    ids = [part.strip() for part in re.split(r"[,，]", cell)]
    if not all(part.isdigit() for part in ids):
        raise GlossaryError(f"例外欄不是「—」或卡片密碼逗號清單:{cell}"
                            f"(列:{row})")
    return frozenset(int(part) for part in ids)


def _parse_row(line, level, miss_problem):
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) != _COLUMNS:
        raise GlossaryError(f"表格列欄數 {len(cells)} != {_COLUMNS}:{line}")
    if _SEPARATOR_RE.match("".join(cells)):
        return None  # 表頭下的分隔列
    ja_cell, zh, banned_cell, _, _, exception_cell, _ = cells
    banned = ([] if banned_cell == _EMPTY else
              [part.strip() for part in re.split(r"[;;]", banned_cell)])
    ja, ja_excludes = _parse_ja_style(ja_cell, line)
    ja_re, ja_slots = _compile_style(ja, line, time_mode="ja")
    zh_forms = []  # 多形:任一形命中即照規範(2026-08-25 站主裁示)
    for style in re.split(r"[;;]", zh):
        zh_compiled, zh_slots = _compile_style(style.strip(), line,
                                               time_mode="zh")
        if ja_slots != zh_slots:
            raise GlossaryError(f"〈時點〉槽數兩側不對稱({ja_slots} vs "
                                f"{zh_slots}):{line}")
        zh_forms.append(zh_compiled)  # 有槽=模板 parts,無槽=regex
    return {
        "level": level, "ja": ja, "zh": zh, "miss_problem": miss_problem,
        "ja_re": ja_re, "ja_excludes": ja_excludes,
        "time_slots": ja_slots, "zh_forms": zh_forms,
        "banned": [(style, _compile_style(style, line, time_mode="plain")[0])
                   for style in banned],
        "exceptions": _parse_exceptions(exception_cell, line),
    }


def parse_glossary(md_text):
    """詞彙表 md 全文 → 條目清單(順序照文件;殼層拿它報條目數)。"""
    entries = []
    seen = set()
    level = miss_problem = None
    header_pending = False
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            level = miss_problem = None
            for keyword, section_level, problem in _SECTIONS:
                if keyword in stripped:
                    level, miss_problem = section_level, problem
                    seen.add(section_level)
                    header_pending = True  # 該節表格的第一列是表頭,跳過
            continue
        if level is None or not stripped.startswith("|"):
            continue
        if header_pending:
            header_pending = False
            continue
        entry = _parse_row(stripped, level, miss_problem)
        if entry is not None:
            entries.append(entry)
    missing = [lv for _, lv, _ in _SECTIONS if lv not in seen]
    if missing:
        raise GlossaryError(f"找不到節標題:{'、'.join(missing)}"
                            "(表格挪動或改名了?)")
    return entries


def check_texts(md_text, records):
    """單一高接縫:詞彙表 md 全文+卡句記錄 → 結構化不一致清單。

    records 每筆需 id / name / text_ja / text_zh(合成或取自效果標記表)。
    回傳的每筆不一致:level(譯詞/句式)、entry(日文側樣式)、expected
    (中文側規範樣式)、problem(未用規範譯法/未照模板/用禁譯)、banned
    (命中的禁譯樣式清單,無則空)加記錄的 id / name / text_ja / text_zh。
    順序:記錄序為主、條目序為次,同一份輸入輸出恆同。
    """
    entries = parse_glossary(md_text)
    findings = []
    for record in records:
        ja = record.get("text_ja") or ""
        zh = record.get("text_zh") or ""
        if not ja:
            continue
        for entry in entries:
            if record.get("id") in entry["exceptions"]:
                continue
            ja_scan = _mask_excluded(ja, entry["ja_excludes"])
            if entry["time_slots"]:
                # 跨側配對:日文側每種命中的時點組合,中文側都要有對應形
                unit_sets = {m.groups()
                             for m in entry["ja_re"].finditer(ja_scan)}
                if not unit_sets:
                    continue
                zh_ok = all(
                    any(_fill_time_slots(parts, units).search(zh)
                        for parts in entry["zh_forms"])
                    for units in unit_sets)
            else:
                if not entry["ja_re"].search(ja_scan):
                    continue
                zh_ok = any(form.search(zh)
                            for form in entry["zh_forms"])
            banned = [style for style, banned_re in entry["banned"]
                      if banned_re.search(zh)]
            if banned:
                problem = "用禁譯"
            elif not zh_ok:
                problem = entry["miss_problem"]
            else:
                continue
            findings.append({
                "level": entry["level"], "entry": entry["ja"],
                "expected": entry["zh"], "problem": problem, "banned": banned,
                "id": record.get("id"), "name": record.get("name"),
                "text_ja": ja, "text_zh": zh,
            })
    return findings
