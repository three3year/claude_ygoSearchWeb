"""官方 DB 収録シリーズ後備日期的補抓 CLI 薄殼(票 text-format#06)。

流程:盤點缺口(YGOPRODeck 查無日期且有官方 cid 的卡)→ 以固定間隔抓官方
卡片頁**日文版**寫入快取 → 由全部快取頁重建 data/sources/official-dates.json
→ 與 YGOPRODeck 對照,回報後備補到幾張與兩邊不一致的卡。

只抓缺口卡,不做全庫抓取;網路存取比照 faq_info 線的既有慣例(節流、
快取沿用、--offline 不連網)。快取是這份來源檔的事實來源:重跑一律由快取
重建,YGOPRODeck 日後跟上的卡也留在檔內,交給合併端做一致性對照。
薄殼不納入自動測試(合併與解析的純函式在 official_dates.py,有測試)。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/text_format/fetch_official_dates.py --dry-run   # 只盤點,不連網
    python script/text_format/fetch_official_dates.py             # 補抓
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

from ocg_dates import align_ocg_dates, load_ocg_dates
from official_dates import (build_cid_to_password, build_password_to_cid,
                            conflict_report_lines, earliest_release_date,
                            extract_release_dates, find_gap_targets,
                            merge_aligned_dates)

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 官方站抓取與 cid 對應復用 faq_info 線;資料更新時間記錄復用 card_list 的殼
# (跨資料夾,需手動加入搜尋路徑)。append 不 insert:不遮蔽標準庫。
sys.path.append(os.path.join(ROOT, "script", "faq_info"))
sys.path.append(os.path.join(ROOT, "script", "card_list"))
from build_faq_info import load_cid_overrides  # noqa: E402
from faqfetch import fetch_card_page, sleep_between  # noqa: E402
from faqgap import DEFAULT_CACHE, DEFAULT_CID_OVERRIDES  # noqa: E402
from update_cards import record_downloaded_at  # noqa: E402

DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_SOURCES_DIR = os.path.join(ROOT, "data", "sources")
DEFAULT_YGO_DATES = os.path.join(DEFAULT_SOURCES_DIR, "ocg-dates.json")
DEFAULT_FAQ_JSON = os.path.join(DEFAULT_SOURCES_DIR, "faq_info.json")
DEFAULT_OUT = os.path.join(DEFAULT_SOURCES_DIR, "official-dates.json")

# 快取與 faq_*.html 同目錄、不同前綴,兩邊的掃描互不相見
CARD_CACHE_NAME = "card_{cid}.html"
CARD_CACHE_RE = re.compile(r"card_(\d+)\.html$")


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def crawl(targets, cache_dir, delay, overwrite=False):
    """補抓 targets 的官方卡片頁寫入快取。回傳 (已寫入 cid, 失敗清單)。

    寫入前先解析驗證(収録シリーズ標題必須在):錯誤頁或非日文 locale 的
    回應不入快取,計為失敗——快取只收確定可用的頁。
    """
    written, failed = [], []
    for i, (cid, card) in enumerate(targets):
        path = os.path.join(cache_dir, CARD_CACHE_NAME.format(cid=cid))
        if os.path.exists(path) and not overwrite:
            print(f"  cid={cid} 已有快取,略過({card['id']} {card['name_ja']})")
            continue
        sleep_between(i, delay)
        try:
            html = fetch_card_page(cid)
            extract_release_dates(html)
        except Exception as e:  # noqa: BLE001 — 單張失敗不中斷其餘補抓
            failed.append((cid, card, repr(e)))
            print(f"  cid={cid} 抓取失敗: {e}")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(html)
        written.append(cid)
        print(f"  cid={cid} 已寫入({card['id']} {card['name_ja']})")
    return written, failed


def rebuild_from_cache(cache_dir, cid_to_password):
    """全部快取卡片頁 → ({密碼: 最早発売日}, 問題行)。

    對不到密碼、解析失敗、頁上無発売日的頁都列問題行回報,不入檔。
    """
    dates, problems = {}, []
    for path in sorted(glob.glob(os.path.join(cache_dir, "card_*.html"))):
        m = CARD_CACHE_RE.search(os.path.basename(path))
        if not m:
            continue
        cid = int(m.group(1))
        password = cid_to_password.get(cid)
        if password is None:
            problems.append(f"  cid={cid} 對不到卡片密碼,略過")
            continue
        with open(path, encoding="utf-8") as f:
            try:
                date = earliest_release_date(f.read())
            except ValueError as e:
                problems.append(f"  cid={cid} 快取頁解析失敗({e}),略過")
                continue
        if date is None:
            problems.append(f"  cid={cid} 収録シリーズ無発売日,維持日期不明")
            continue
        dates[password] = date
    return dates, problems


def write_dates(path, dates):
    """寫出後備來源檔,形狀與 ocg-dates.json 相同;先寫 .tmp 再原子替換。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({str(k): v for k, v in sorted(dates.items())}, f,
                  ensure_ascii=False, indent=0)
    os.replace(tmp_path, path)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="補抓官方 DB 収録シリーズ後備日期")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表路徑 (預設 data/cards.json)")
    parser.add_argument("--ygo-dates", default=DEFAULT_YGO_DATES,
                        help="YGOPRODeck 首發日來源 "
                             "(預設 data/sources/ocg-dates.json)")
    parser.add_argument("--faq-json", default=DEFAULT_FAQ_JSON,
                        help="官方 Q&A 整合檔,取 password→cid 對應 "
                             "(預設 data/sources/faq_info.json)")
    parser.add_argument("--cid-overrides", default=DEFAULT_CID_OVERRIDES,
                        help="人工查證的 cid→卡片密碼 覆寫檔 "
                             "(預設 data/cid_overrides.json)")
    parser.add_argument("--cache", default=DEFAULT_CACHE,
                        help=f"官方頁快取目錄 (預設 {DEFAULT_CACHE})")
    parser.add_argument("--out", default=DEFAULT_OUT,
                        help="後備來源檔輸出路徑 "
                             "(預設 data/sources/official-dates.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只盤點缺口並列出,不連網、不寫檔")
    parser.add_argument("--offline", action="store_true",
                        help="不連網,只用快取既有頁重建來源檔")
    parser.add_argument("--overwrite", action="store_true",
                        help="已有快取的 cid 也重抓")
    parser.add_argument("--limit", type=int, default=0,
                        help="最多補抓幾張 (0 表示不限,用於試跑)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="請求間隔秒數 (預設 1.5)")
    args = parser.parse_args(argv)

    cards = _load_json(args.cards)
    if cards is None:
        print(f"找不到卡片總表: {args.cards}", file=sys.stderr)
        return 2
    if not os.path.exists(args.ygo_dates):
        print(f"找不到 YGOPRODeck 首發日來源: {args.ygo_dates};"
              "請先跑 update_cards.py", file=sys.stderr)
        return 2
    primary = align_ocg_dates(cards, load_ocg_dates(args.ygo_dates))

    faq_entries = _load_json(args.faq_json, [])
    overrides = load_cid_overrides(args.cid_overrides)
    password_to_cid = build_password_to_cid(faq_entries, overrides)
    targets, unresolved = find_gap_targets(cards, primary, password_to_cid)
    print(f"缺口盤點: YGOPRODeck 查無日期 {len(targets) + len(unresolved)} 張;"
          f"有 cid 可抓 {len(targets)} 張、無 cid {len(unresolved)} 張")
    for card in unresolved:
        print(f"  {card['id']} {card['name_ja']}(無官方 cid,維持日期不明)")
    if args.dry_run:
        for cid, card in targets:
            cached = os.path.exists(
                os.path.join(args.cache, CARD_CACHE_NAME.format(cid=cid)))
            mark = "已有快取" if cached else "待抓"
            print(f"  cid={cid} {card['id']} {card['name_ja']}({mark})")
        return 0

    written, failed = [], []
    if args.offline:
        print("離線模式:不連網,只用快取既有頁重建")
    else:
        to_crawl = targets
        if args.limit:
            to_crawl = targets[:args.limit]
            print(f"--limit {args.limit}:本次最多補抓 {len(to_crawl)} 張")
        print(f"補抓 {len(to_crawl)} 張的官方卡片頁(間隔 {args.delay}s)…")
        os.makedirs(args.cache, exist_ok=True)
        written, failed = crawl(to_crawl, args.cache, args.delay,
                                args.overwrite)
        print(f"補抓完成: 寫入 {len(written)} 頁、失敗 {len(failed)} 頁")

    dates, problems = rebuild_from_cache(
        args.cache, build_cid_to_password(faq_entries, overrides))
    for line in problems:
        print(line)
    write_dates(args.out, dates)
    print(f"已寫出 {args.out}({len(dates)} 張)")

    fallback = align_ocg_dates(cards, dates)
    merged, conflicts = merge_aligned_dates(primary, fallback)
    filled = sum(1 for pid, v in merged.items()
                 if v is not None and primary[pid] is None)
    still_missing = sum(1 for v in merged.values() if v is None)
    print(f"合併結果: 官方後備補到 {filled} 張;仍查無日期 {still_missing} 張"
          f"(其中無 cid {len(unresolved)} 張)")
    for line in conflict_report_lines(conflicts, cards):
        print(line)

    # 納入資料更新時間機制:真的有下載且全數成功才記(比照 download_all
    # 「任一失敗即不記」;offline/沒東西要抓時時間不動)
    if written and not failed:
        record_downloaded_at(
            os.path.dirname(args.out),
            datetime.datetime.now().astimezone().strftime(
                "%Y-%m-%dT%H:%M:%S%z"))
        print("已記錄資料更新時間")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
