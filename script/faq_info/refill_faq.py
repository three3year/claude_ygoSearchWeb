"""補齊缺漏卡官方 Q&A 快取的 CLI 薄殼。

流程:盤點缺口 → 下載新的 ygoprodeck dump → 新舊 cid 對應表 diff(只增不減)
→ 取得缺漏卡的 cid → 以固定間隔補爬並寫入快取 → 全量重建 faq_info.json
→ 驗收每張待補卡都拿得到 card_text 且對得上卡片密碼。

只增不減檢查不通過時停下回報並以非零碼結束,不自動繼續(需 --force 才覆寫判斷)。
薄殼不納入自動測試。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/faq_info/refill_faq.py --dry-run   # 只盤點缺口,不連網
    python script/faq_info/refill_faq.py             # 完整補爬
"""
import argparse
import json
import os
import sys
import time

import build_faq_info
from build_faq_info import load_cid_to_password
from faqfetch import fetch_faq_page, fetch_ygopro_dump, sleep_between
from faqgap import (DEFAULT_CACHE, build_cid_to_password, diff_cid_mapping,
                    extract_konami_ids, find_missing_cards, format_gap_report,
                    split_alt_artwork_changes)

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_JSON = os.path.join(ROOT, "data", "sources", "faq_info.json")
# 新 dump 存成獨立檔,檔名排序在既有 ygopro_<密碼>_<密碼>.json 之後,
# 使 build_cid_to_password 的「先出現者優先」保留既有對應不被覆寫。
NEW_DUMP_NAME = "ygopro_full_{stamp}.json"


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_dump(cache_dir, dump, stamp):
    """把新 dump 寫進快取目錄;先寫 .tmp 再原子替換。"""
    path = os.path.join(cache_dir, NEW_DUMP_NAME.format(stamp=stamp))
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(dump, f, ensure_ascii=False)
    os.replace(tmp_path, path)
    return path


def resolve_targets(missing, password_to_cid):
    """把待補卡對應到 cid。回傳 (targets, unresolved)。

    targets 為 (cid, 卡片) 序列,依 cid 升冪;主卡密碼優先,退而求其次用異圖密碼。
    """
    targets, unresolved = [], []
    for card in missing:
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


def crawl(targets, cache_dir, delay, overwrite=False):
    """補爬 targets 的官方 Q&A 頁寫入快取。回傳 (已寫入 cid, 失敗清單)。"""
    written, failed = [], []
    for i, (cid, card) in enumerate(targets):
        path = os.path.join(cache_dir, f"faq_{cid}.html")
        if os.path.exists(path) and not overwrite:
            print(f"  cid={cid} 已有快取,略過({card['id']} {card['name_ja']})")
            continue
        sleep_between(i, delay)
        try:
            html = fetch_faq_page(cid)
        except Exception as e:  # noqa: BLE001 — 單張失敗不中斷其餘補爬
            failed.append((cid, card, repr(e)))
            print(f"  cid={cid} 抓取失敗: {e}")
            continue
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(html)
        written.append(cid)
        print(f"  cid={cid} 已寫入({card['id']} {card['name_ja']})")
    return written, failed


def verify(faq_path, missing):
    """驗收:每張待補卡都在 faq_info.json 有 card_text 且對得上卡片密碼。"""
    entries = _load_json(faq_path, [])
    by_password = {e["password"]: e for e in entries
                   if e.get("password") is not None}
    ok, bad = [], []
    for card in missing:
        entry = by_password.get(card["id"]) or next(
            (by_password[a] for a in card.get("alt_ids", ())
             if a in by_password), None)
        if entry is not None and entry.get("card_text"):
            ok.append(card)
        else:
            bad.append(card)
    return ok, bad


def main(argv=None):
    parser = argparse.ArgumentParser(description="補齊缺漏卡的官方 Q&A 快取")
    parser.add_argument("--cache", default=DEFAULT_CACHE,
                        help=f"官方 Q&A 快取目錄 (預設 {DEFAULT_CACHE})")
    parser.add_argument("--cards", default=DEFAULT_CARDS,
                        help="卡片總表路徑 (預設 data/cards.json)")
    parser.add_argument("--faq-json", default=DEFAULT_FAQ_JSON,
                        help="整合 JSON 路徑 (預設 data/sources/faq_info.json)")
    parser.add_argument("--dry-run", action="store_true",
                        help="只盤點缺口並列出,不連網、不寫檔")
    parser.add_argument("--offline", action="store_true",
                        help="不下載新 dump,只用快取既有的 ygopro_*.json")
    parser.add_argument("--force", action="store_true",
                        help="即使新舊對應表不是只增不減也繼續")
    parser.add_argument("--overwrite", action="store_true",
                        help="已有快取的 cid 也重抓")
    parser.add_argument("--limit", type=int, default=0,
                        help="最多補爬幾張 (0 表示不限,用於試跑)")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="請求間隔秒數 (預設 1.5)")
    args = parser.parse_args(argv)

    cards = _load_json(args.cards)
    if cards is None:
        print(f"找不到卡片總表: {args.cards}", file=sys.stderr)
        return 2
    faq_entries = _load_json(args.faq_json, [])

    missing, excluded = find_missing_cards(cards, faq_entries,
                                           with_excluded=True)
    for line in format_gap_report(missing, excluded,
                                  sample=len(missing) if args.dry_run else 10):
        print(line)
    if not missing:
        return 0
    if args.dry_run:
        return 0

    old_mapping = load_cid_to_password(args.cache)
    password_to_cid = {}
    if args.offline:
        print("離線模式:沿用快取既有的 ygoprodeck 資料檔")
        # 與 build_cid_to_password 一致:依檔名排序,先出現者優先
        for dump in build_faq_info.iter_dumps(args.cache):
            for password, cid in extract_konami_ids(dump).items():
                password_to_cid.setdefault(password, cid)
    else:
        print("下載 ygoprodeck 完整 dump …")
        try:
            dump = fetch_ygopro_dump()
        except Exception as e:  # noqa: BLE001
            print(f"dump 下載失敗: {e}", file=sys.stderr)
            return 2
        new_mapping = build_cid_to_password([dump])
        d = diff_cid_mapping(old_mapping, new_mapping)
        benign, real_changes = split_alt_artwork_changes(d["changed"], cards)
        print(f"cid 對應表 diff: 新增 {len(d['added'])}、"
              f"消失 {len(d['removed'])}、改指 {len(d['changed'])}"
              f"(其中同卡異圖 {len(benign)}、真的改指 {len(real_changes)})")
        if d["removed"] or real_changes:
            for cid in d["removed"][:10]:
                print(f"  消失 cid={cid}(舊對應密碼 {old_mapping[cid]})")
            for cid, old_pw, new_pw in real_changes[:10]:
                print(f"  改指 cid={cid}: {old_pw} → {new_pw}")
            if not args.force:
                print("新 dump 並非只增不減,停下回報。"
                      "確認無誤後可加 --force 繼續。", file=sys.stderr)
                return 1
            print("--force:已知不是只增不減,仍繼續")
        path = save_dump(args.cache, dump, time.strftime("%Y%m%d"))
        print(f"新 dump 已存為 {path}(不覆蓋既有檔)")
        password_to_cid = extract_konami_ids(dump)

    targets, unresolved = resolve_targets(missing, password_to_cid)
    print(f"取得 cid: {len(targets)} 張;取不到 konami_id: {len(unresolved)} 張")
    for card in unresolved:
        print(f"  {card['id']} {card['name_ja']}(無 konami_id,略過)")
    if args.limit:
        targets = targets[:args.limit]
        print(f"--limit {args.limit}:本次只補爬 {len(targets)} 張")

    print(f"補爬 {len(targets)} 頁(間隔 {args.delay}s)…")
    written, failed = crawl(targets, args.cache, args.delay, args.overwrite)
    print(f"補爬完成: 寫入 {len(written)} 頁、失敗 {len(failed)} 頁")

    print("重建 faq_info.json …")
    build_faq_info.main(["--cache", args.cache, "--out", args.faq_json])

    ok, bad = verify(args.faq_json, missing)
    print(f"驗收: {len(ok)}/{len(missing)} 張待補卡拿得到 card_text 且對得上密碼")
    for card in bad:
        print(f"  未補齊: {card['id']} {card['name_ja']}")
    return 1 if bad or failed else 0


if __name__ == "__main__":
    sys.exit(main())
