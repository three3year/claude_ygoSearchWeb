"""卡文詞彙表驗證接縫:詞彙表 md 全文+卡句記錄 → 結構化不一致清單。

純函式、不做 IO(接縫 2026-08-24 站主確認,spec .scratch/text-glossary/
spec.md);報告式,回傳清單供殼層排版,不阻擋建置。

樣式 → 機器比對規則(md 只維護人讀樣式,推導定義在此):
    〈n〉  → 連續數字 ``[0-9０-９]+``。中文側卡文依規範用半形、日文側官方
            卡文用全形,比對一律兩者皆容許——寬窄之辨歸《文本格式規範》§2,
            不歸本表。
    〜    → 同句內任意內文 ``[^。\\n]*``(不跨句號、不跨行)。
    其餘字元照字面比對(re.escape)。出現上述以外的 ``〈…〉`` 佔位符或
    落單的 ``〈``/``〉`` 即解析失敗。

檢查兩級,同一套比對機器,只差條目來源與問題名稱:
    譯詞:日文側含「日文」欄樣式 → 中文側須含「規範譯法」樣式(否則報
          「未用規範譯法」),且不得命中「禁譯」欄任一樣式(否則報「用禁譯」,
          規範與禁譯並存時仍報禁譯——句中混用也是不一致)。
    句式:日文側命中「日文樣式」 → 中文側須命中「中文樣式」(否則報
          「未照模板」),禁譯同上。
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


class GlossaryError(ValueError):
    """詞彙表解析失敗:格式壞了要立即發現,不靜默漏檢。"""


def _compile_style(style, row):
    """人讀樣式 → regex(佔位符推導規則見模組 docstring)。"""
    parts = []
    for token in _TOKEN_RE.split(style):
        if token == "〜":
            parts.append(_ANY_RE)
        elif token.startswith("〈"):
            if token != "〈n〉":
                raise GlossaryError(f"佔位符不明:{token}(列:{row})")
            parts.append(_NUM_RE)
        else:
            if "〈" in token or "〉" in token:
                raise GlossaryError(f"佔位符括號落單:{style}(列:{row})")
            parts.append(re.escape(token))
    return re.compile("".join(parts))


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
    ja, zh, banned_cell, _, _, exception_cell, _ = cells
    banned = ([] if banned_cell == _EMPTY else
              [part.strip() for part in re.split(r"[;;]", banned_cell)])
    return {
        "level": level, "ja": ja, "zh": zh, "miss_problem": miss_problem,
        "ja_re": _compile_style(ja, line), "zh_re": _compile_style(zh, line),
        "banned": [(style, _compile_style(style, line)) for style in banned],
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
            if not entry["ja_re"].search(ja):
                continue
            banned = [style for style, banned_re in entry["banned"]
                      if banned_re.search(zh)]
            if banned:
                problem = "用禁譯"
            elif not entry["zh_re"].search(zh):
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
