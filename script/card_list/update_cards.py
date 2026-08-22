"""一鍵更新卡片總表:下載三來源 → 管線建置 → 寫出 cards.json 與報告
→ 官方 Q&A 對帳(回報缺口,不自動補爬)。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/card_list/update_cards.py            # 下載最新來源後(差值)建置
    python script/card_list/update_cards.py --offline  # 不連網,用既有來源檔重跑
"""
import argparse
import datetime
import json
import os
import ssl
import sys
import urllib.request

from build_cards import (DEFAULT_ERRATA, DEFAULT_OUTPUT, DEFAULT_REWRITES,
                         load_table, print_report)
from cardlist import build_card_list, serialize_card_list

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_SOURCES_DIR = os.path.join(ROOT, "data", "sources")
DEFAULT_FAQ_JSON = os.path.join(ROOT, "data", "sources", "faq_info.json")

# 官方 Q&A 對帳復用 faq_info、首發日對齊復用 text_format 的純函式模組
# (跨資料夾,需手動加入搜尋路徑)。
# 用 append 而非 insert:不讓這個目錄有機會遮蔽標準庫或既有模組。
sys.path.append(os.path.join(ROOT, "script", "faq_info"))
sys.path.append(os.path.join(ROOT, "script", "text_format"))
from faqgap import find_missing_cards, format_gap_report  # noqa: E402
from ocg_dates import align_ocg_dates, load_ocg_dates  # noqa: E402
from official_dates import (conflict_report_lines,  # noqa: E402
                            merge_aligned_dates)

SOURCES = {
    "zh": "https://github.com/salix5/cdb/releases/latest/download/cards.cdb",
    "ja": ("https://raw.githubusercontent.com/mycard/ygopro-database/"
           "master/locales/ja-JP/cards.cdb"),
    "en": ("https://raw.githubusercontent.com/mycard/ygopro-database/"
           "master/locales/en-US/cards.cdb"),
}
FILENAMES = {"zh": "cards.cdb", "ja": "ja-JP.cdb", "en": "en-US.cdb"}
MD_RARITY_URL = ("https://www.masterduelmeta.com/api/v1/cards"
                 "?limit=3000&page={page}&fields=konamiID,rarity,banStatus")
# 檔名不再叫 md-rarity:同一份來源同時承載稀有度與 MD [[禁限狀態]]。
# 換名讓舊形狀的快取在離線模式下直接報「缺來源」,而不是餵舊形狀給建置端。
MD_RARITY_FILENAME = "md.json"
DOWNLOADED_AT_FILENAME = "downloaded_at.json"
# genesys_points 只在帶 format=genesys 時才出現於 misc_info
GENESYS_URL = ("https://db.ygoprodeck.com/api/v7/cardinfo.php"
               "?misc=yes&format=genesys")
GENESYS_FILENAME = "genesys.json"
# 禁限來源([[禁限狀態]]):同一個端點以 banlist=<fmt> 只回上榜卡,
# banlist_info.ban_<fmt> 是原始禁限值;正規化(→ 禁止/限制/準限制)在建置端做,
# 這裡只存原樣——來源冒出新字串時該由建置吵出來,不是下載時靜靜濾掉。
BANLIST_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php?banlist={fmt}"
BANLIST_FORMATS = ("ocg", "tcg")
BANLIST_FILENAME = "banlist-{fmt}.json"
# OCG 首發日([[文本格式規範]]的三級分類用):必須是不帶 format= 卡池篩選的
# 全量 dump——genesys 端點那種 format=genesys 會漏卡,首發日要全庫都對得到。
OCG_DATE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php?misc=yes"
OCG_DATE_FILENAME = "ocg-dates.json"
# 官方 DB 収録シリーズ後備日期:由 fetch_official_dates.py 補抓,不在
# download_all 之列(對官方站發數十次請求,由人決定何時執行,比照 refill)
OFFICIAL_DATE_FILENAME = "official-dates.json"


def _fetch_url(url):
    # 本機 curl 對 github.com 有憑證撤銷檢查問題(需 --ssl-no-revoke);
    # Python 預設不做撤銷檢查,維持憑證驗證即可。
    # MDM API 會擋無 User-Agent 的請求(403)。
    ctx = ssl.create_default_context()
    req = urllib.request.Request(
        url, headers={"User-Agent": "ygoSearchWeb/1.0"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        return resp.read()


def _fetch_json(url):
    return json.loads(_fetch_url(url))


def download_md_rarity(dest_dir, fetch_json=_fetch_json, offline=False):
    """自 masterduelmeta API 分頁抓取 {卡片密碼: {稀有度, 禁限}} → md.json。

    分頁抓到空頁為止;konamiID 非純數字、或稀有度與 banStatus 皆缺的條目略過。
    只有 banStatus 的筆(未收錄卡的預掛)也入檔——採不採計是建置端的決定
    (spec banlist:無稀有度不採計並進報告),下載端保留原貌讓報告數得到。
    先寫 .tmp 再原子替換,失敗時既有檔不受影響。
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, MD_RARITY_FILENAME)
    if offline:
        if not os.path.exists(path):
            raise RuntimeError(
                f"離線模式但缺少來源 md({path});請先連網下載一次")
        return path
    entries = {}
    page = 1
    try:
        while True:
            rows = fetch_json(MD_RARITY_URL.format(page=page))
            if not rows:
                break
            for row in rows:
                kid = row.get("konamiID")
                if not kid or not str(kid).isdigit():
                    continue
                # 同一密碼可能多列(異圖/預掛):逐欄位合併,整筆覆蓋會讓
                # 只有 banStatus 的後列吃掉先列的稀有度(實測掉 9 張)
                update = {k: row[k] for k in ("rarity", "banStatus")
                          if row.get(k)}
                if update:
                    entries.setdefault(int(kid), {}).update(update)
            page += 1
    except Exception as e:
        raise RuntimeError(f"來源 md 下載失敗(第 {page} 頁): {e}") from e
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({str(k): v for k, v in sorted(entries.items())}, f,
                  ensure_ascii=False, indent=0)
    os.replace(tmp_path, path)
    return path


def download_sources(dest_dir, fetch=_fetch_url, offline=False):
    """下載(或離線沿用)三個來源檔 → {zh/ja/en: 路徑}。

    先寫 .tmp 再原子替換,單一來源失敗時既有暫存檔不受影響。
    """
    os.makedirs(dest_dir, exist_ok=True)
    paths = {}
    for key, url in SOURCES.items():
        path = os.path.join(dest_dir, FILENAMES[key])
        if offline:
            if not os.path.exists(path):
                raise RuntimeError(
                    f"離線模式但缺少來源 {key}({path});請先連網下載一次")
            paths[key] = path
            continue
        try:
            data = fetch(url)
        except Exception as e:
            raise RuntimeError(f"來源 {key} 下載失敗({url}): {e}") from e
        tmp_path = path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
        paths[key] = path
    return paths


def download_genesys(dest_dir, fetch_json=_fetch_json, offline=False):
    """自 YGOPRODeck 全量 dump 萃取 {卡片密碼: Genesys點數} → genesys.json。

    只保留 misc_info 帶 genesys_points 的卡(官方點數表);未列點的卡不入檔,
    管線端預設 0。先寫 .tmp 再原子替換,失敗時既有檔不受影響。
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, GENESYS_FILENAME)
    if offline:
        if not os.path.exists(path):
            raise RuntimeError(
                f"離線模式但缺少來源 genesys({path});請先連網下載一次")
        return path
    try:
        dump = fetch_json(GENESYS_URL)
        points = {}
        for card in dump["data"]:
            misc = (card.get("misc_info") or [{}])[0]
            value = misc.get("genesys_points")
            if value is not None:
                points[int(card["id"])] = value
    except Exception as e:
        raise RuntimeError(f"來源 genesys 下載失敗: {e}") from e
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({str(k): v for k, v in sorted(points.items())}, f,
                  ensure_ascii=False, indent=0)
    os.replace(tmp_path, path)
    return path


def download_banlists(dest_dir, fetch_json=_fetch_json, offline=False):
    """自 YGOPRODeck 禁限端點抓取各賽制的 {卡片密碼: 原始禁限值} → banlist-*.json。

    缺 banlist_info 或缺該賽制欄位的條目略過(banlist=goat 之類的別榜資料)。
    先寫 .tmp 再原子替換,失敗時既有檔不受影響。
    """
    os.makedirs(dest_dir, exist_ok=True)
    paths = {}
    for fmt in BANLIST_FORMATS:
        path = os.path.join(dest_dir, BANLIST_FILENAME.format(fmt=fmt))
        if offline:
            if not os.path.exists(path):
                raise RuntimeError(
                    f"離線模式但缺少來源 banlist-{fmt}({path});"
                    "請先連網下載一次")
            paths[fmt] = path
            continue
        try:
            dump = fetch_json(BANLIST_URL.format(fmt=fmt))
            statuses = {}
            for card in dump["data"]:
                value = (card.get("banlist_info") or {}).get(f"ban_{fmt}")
                if value:
                    statuses[int(card["id"])] = value
        except Exception as e:
            raise RuntimeError(f"來源 banlist-{fmt} 下載失敗: {e}") from e
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump({str(k): v for k, v in sorted(statuses.items())}, f,
                      ensure_ascii=False, indent=0)
        os.replace(tmp_path, path)
        paths[fmt] = path
    return paths


def download_ocg_dates(dest_dir, fetch_json=_fetch_json, offline=False):
    """自 YGOPRODeck 全量 dump 萃取 {卡片密碼: OCG 首發日} → ocg-dates.json。

    只保留 misc_info 帶 ocg_date 的卡;查無日期的卡(TCG 限定等)不入檔、
    不硬猜——對齊卡片總表後可辨識為「日期不明」(script/text_format/)。
    先寫 .tmp 再原子替換,失敗時既有檔不受影響。
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, OCG_DATE_FILENAME)
    if offline:
        if not os.path.exists(path):
            raise RuntimeError(
                f"離線模式但缺少來源 ocg-dates({path});請先連網下載一次")
        return path
    try:
        dump = fetch_json(OCG_DATE_URL)
        dates = {}
        for card in dump["data"]:
            misc = (card.get("misc_info") or [{}])[0]
            value = misc.get("ocg_date")
            if value is not None:
                dates[int(card["id"])] = value
    except Exception as e:
        raise RuntimeError(f"來源 ocg-dates 下載失敗: {e}") from e
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({str(k): v for k, v in sorted(dates.items())}, f,
                  ensure_ascii=False, indent=0)
    os.replace(tmp_path, path)
    return path


def record_downloaded_at(dest_dir, now, offline=False):
    """全部來源下載成功後記下資料更新時間,一次執行一個時間(九個來源檔
    不分開;官方後備首發日由獨立補抓腳本 fetch_official_dates.py 下載,
    成功補抓同樣呼叫這裡記錄)。

    offline 沿用既有記錄——時間反映「下載」而不是「重跑」;從未記錄過也不報錯,
    footer 那一行省略即可。時刻由呼叫端注入,這裡不讀時鐘。
    """
    path = os.path.join(dest_dir, DOWNLOADED_AT_FILENAME)
    if offline:
        return path
    os.makedirs(dest_dir, exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"downloaded_at": now}, f, ensure_ascii=False)
    os.replace(tmp_path, path)
    return path


def download_all(sources_dir, now, offline=False,
                 fetch=_fetch_url, fetch_json=_fetch_json):
    """全部來源(中/日/英 cdb、MD 稀有度、Genesys、禁限、OCG 首發日)→
    全部成功才記資料更新時間。

    任一下載失敗即 raise,記錄不被動到——「全部成功才寫」由呼叫順序保證,
    收在同一個函式裡讓這件事測得到。
    """
    paths = download_sources(sources_dir, fetch=fetch, offline=offline)
    md_path = download_md_rarity(sources_dir, fetch_json=fetch_json,
                                 offline=offline)
    genesys_path = download_genesys(sources_dir, fetch_json=fetch_json,
                                    offline=offline)
    banlist_paths = download_banlists(sources_dir, fetch_json=fetch_json,
                                      offline=offline)
    ocg_dates_path = download_ocg_dates(sources_dir, fetch_json=fetch_json,
                                        offline=offline)
    record_downloaded_at(sources_dir, now, offline=offline)
    return paths, md_path, genesys_path, banlist_paths, ocg_dates_path


def check_faq_gap(cards, faq_json_path=DEFAULT_FAQ_JSON):
    """對帳:卡片總表對官方 Q&A 整合檔,回傳可列印的報告行。

    純本地比對、不連網。只回報缺口,不自動補爬——補爬要下載 dump 並對官方站
    發數十次請求,那是 refill_faq.py 的工作,由人決定何時執行。
    """
    if not os.path.exists(faq_json_path):
        return [f"官方 Q&A 對帳: 尚無 {os.path.basename(faq_json_path)},略過"]
    with open(faq_json_path, encoding="utf-8") as f:
        faq_entries = json.load(f)
    missing, excluded = find_missing_cards(cards, faq_entries,
                                           with_excluded=True)
    lines = format_gap_report(missing, excluded)
    if missing:
        lines.append("  補齊方式: python script/faq_info/refill_faq.py")
    return lines


def check_ocg_date_coverage(cards, dates_path, official_path=None):
    """首發日覆蓋率:卡片總表對 ocg-dates(主)+ 官方後備,回傳可列印的報告行。

    純本地比對、不連網;對齊與合併復用 script/text_format/ 的純函式,
    YGOPRODeck 為主、官方後備補缺。只報張數——查無日期的卡在三級分類報表
    歸「日期不明」單獨列出;但兩邊都有日期且不一致的卡逐卡列出兩邊的值,
    不默默以任一邊蓋掉。
    """
    if not os.path.exists(dates_path):
        return [f"OCG 首發日覆蓋: 尚無 {os.path.basename(dates_path)},略過"]
    primary = align_ocg_dates(cards, load_ocg_dates(dates_path))
    filled, conflicts = 0, []
    merged = primary
    if official_path and os.path.exists(official_path):
        fallback = align_ocg_dates(cards, load_ocg_dates(official_path))
        merged, conflicts = merge_aligned_dates(primary, fallback)
        filled = sum(1 for pid, v in merged.items()
                     if v is not None and primary[pid] is None)
    dated = sum(1 for v in merged.values() if v is not None)
    missing = len(merged) - dated
    line = f"OCG 首發日覆蓋: 有日期 {dated} 張"
    if filled:
        line += f"(官方後備補 {filled} 張)"
    line += f" / 查無日期 {missing} 張"
    if missing:
        line += "(查無日期的卡在三級分類報表歸「日期不明」;"\
                "有 cid 者可用 script/text_format/fetch_official_dates.py 補)"
    return [line] + conflict_report_lines(conflicts, cards)


def main(argv=None):
    parser = argparse.ArgumentParser(description="一鍵更新卡片總表")
    parser.add_argument("--offline", action="store_true",
                        help="不連網,使用 sources/ 既有來源檔")
    parser.add_argument("--sources-dir", default=DEFAULT_SOURCES_DIR,
                        help="來源暫存目錄 (預設 data/sources/,不入版控)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="輸出 JSON 路徑 (預設 data/cards.json)")
    parser.add_argument("--faq-json", default=DEFAULT_FAQ_JSON,
                        help="官方 Q&A 整合檔路徑,用於更新後對帳")
    parser.add_argument("--errata", default=DEFAULT_ERRATA,
                        help="卡文勘誤表路徑 (預設 data/text_errata.json)")
    parser.add_argument("--rewrites", default=DEFAULT_REWRITES,
                        help="文本改寫表路徑 (預設 data/text_rewrites.json)")
    args = parser.parse_args(argv)

    paths, md_path, genesys_path, banlist_paths, ocg_dates_path = download_all(
        args.sources_dir,
        datetime.datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
        offline=args.offline)

    existing = None
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)

    cards, report = build_card_list(
        paths["zh"], ja_path=paths["ja"], en_path=paths["en"],
        md_rarity_path=md_path, genesys_path=genesys_path,
        banlist_paths=banlist_paths, existing=existing,
        errata=load_table(args.errata), rewrites=load_table(args.rewrites))
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_card_list(cards))
    print_report(report)
    print(f"已寫出 {args.output}")

    for line in check_faq_gap(cards, args.faq_json):
        print(line)
    for line in check_ocg_date_coverage(
            cards, ocg_dates_path,
            official_path=os.path.join(args.sources_dir,
                                       OFFICIAL_DATE_FILENAME)):
        print(line)


if __name__ == "__main__":
    main()
