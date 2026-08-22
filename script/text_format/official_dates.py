"""官方 DB 収録シリーズ後備日期:頁面解析、缺口盤點與合併一致性(純函式)。

YGOPRODeck 查無 OCG 首發日的卡,改抓官方卡片資料庫**日文頁**的「収録シリーズ」
區塊,取最早一筆発売日補缺(票 text-format#06)。來源檔
data/sources/official-dates.json 由 fetch_official_dates.py 補抓寫出,形狀與
ocg-dates.json 相同({密碼字串: 日期}),載入/對齊直接複用 ocg_dates 模組。
合併以 YGOPRODeck 為主、官方後備補缺;兩邊都有日期且不一致的卡列入回報,
不默默以任一邊蓋掉。
"""
import re

# 収録シリーズ標題只出現在日文 locale 的卡片頁:英文頁同一區塊給的是 TCG
# 發售日(例:cid 21639 英文頁 2025-07-04、日文頁 2026-06-27),抓到英文頁
# 必須視為錯誤,絕不能把 TCG 日期當 OCG 首發日入檔。
_UPDATE_LIST_MARK = 'id="update_list"'
_JA_HEADING = "収録シリーズ"
_TIME_RE = re.compile(r'class="time">\s*(\d{4}-\d{2}-\d{2})')
# 區塊邊界:下一個 <div id="…"> 起手(頁面後段的搜尋表單等也有日期欄位)
_NEXT_SECTION_RE = re.compile(r'<div id="(?!update_list)')


def extract_release_dates(html):
    """官方卡片頁 HTML → 収録シリーズ區塊內的発売日字串列表(依頁面順序)。

    區塊不存在(錯誤頁/非卡片頁)或標題不是日文(抓到英文頁)都 raise
    ValueError——呼叫端把該頁視為抓取失敗,不入快取。
    """
    start = html.find(_UPDATE_LIST_MARK)
    if start == -1:
        raise ValueError("頁面沒有収録シリーズ區塊(錯誤頁或非卡片頁)")
    block = html[start:]
    m = _NEXT_SECTION_RE.search(block)
    if m:
        block = block[:m.start()]
    if _JA_HEADING not in block:
        raise ValueError(
            "収録シリーズ標題不在:非日文 locale?英文頁給的是 TCG 日期,"
            "不能入檔")
    return _TIME_RE.findall(block)


def earliest_release_date(html):
    """官方卡片頁 HTML → 収録シリーズ最早一筆発売日;區塊無日期回 None。

    ISO 日期字串字典序即時間序;查無日期不硬猜,None 由呼叫端回報。
    """
    dates = extract_release_dates(html)
    return min(dates) if dates else None


def merge_aligned_dates(primary, fallback):
    """合併兩份對齊後日期 → (merged, conflicts)。

    primary(YGOPRODeck)為主、fallback(官方後備)補缺;鍵集合以 primary
    為準(= 全部主卡)。兩邊都有日期且不同的卡列入 conflicts
    [(密碼, primary 值, fallback 值)] 依密碼排序——回報,不默默蓋掉。
    """
    merged, conflicts = {}, []
    for pid, p_date in primary.items():
        f_date = fallback.get(pid)
        merged[pid] = p_date if p_date is not None else f_date
        if p_date is not None and f_date is not None and p_date != f_date:
            conflicts.append((pid, p_date, f_date))
    conflicts.sort()
    return merged, conflicts


def build_password_to_cid(faq_entries, overrides=None):
    """faq_info 條目 + 人工 cid 覆寫({cid: 密碼})→ {密碼: cid}。

    人工查證優先(它是查來的知識);faq_info 無密碼的條目略過。
    """
    mapping = {e["password"]: e["cid"] for e in faq_entries
               if e.get("password") is not None and e.get("cid") is not None}
    for cid, password in (overrides or {}).items():
        mapping[password] = cid
    return mapping


def build_cid_to_password(faq_entries, overrides=None):
    """faq_info 條目 + 人工 cid 覆寫({cid: 密碼})→ {cid: 密碼}。

    build_password_to_cid 的反向配對:同一個過濾條件、同一個覆寫優先序,
    快取重建端(cid 檔名 → 密碼)用這個方向。
    """
    mapping = {e["cid"]: e["password"] for e in faq_entries
               if e.get("password") is not None and e.get("cid") is not None}
    mapping.update(overrides or {})
    return mapping


def conflict_report_lines(conflicts, cards):
    """兩邊日期不一致的回報行(標題 + 逐卡兩邊的值),更新殼與補抓殼共用。

    顯示以 YGOPRODeck 為主,但不一致必須浮出——回報,不默默以任一邊蓋掉。
    無不一致回空列表,呼叫端不印。
    """
    if not conflicts:
        return []
    names = {card["id"]: card.get("name_zh", "?") for card in cards}
    lines = [f"OCG 首發日不一致: {len(conflicts)} 張"
             "(YGOPRODeck ≠ 官方後備,顯示以 YGOPRODeck 為主,"
             "不默默覆蓋,請人工查證):"]
    lines += [f"  {pid} {names.get(pid, '?')}: "
              f"YGOPRODeck {p_date} / 官方 {f_date}"
              for pid, p_date, f_date in conflicts]
    return lines


def find_gap_targets(cards, primary, password_to_cid):
    """盤點缺口 → (targets, unresolved)。只抓缺口卡,不做全庫抓取。

    targets 為 (cid, 卡片) 依 cid 升冪——YGOPRODeck 查無日期且拿得到 cid;
    主卡密碼優先,退而求其次用異圖密碼(比照 refill 慣例)。拿不到 cid 的
    缺口卡(多為 TCG 限定)進 unresolved,維持「日期不明」。
    """
    targets, unresolved = [], []
    for card in cards:
        if primary.get(card["id"]) is not None:
            continue
        cid = password_to_cid.get(card["id"])
        if cid is None:
            cid = next((password_to_cid[a] for a in card.get("alt_ids", ())
                        if a in password_to_cid), None)
        if cid is None:
            unresolved.append(card)
        else:
            targets.append((cid, card))
    targets.sort(key=lambda t: t[0])
    return targets, unresolved
