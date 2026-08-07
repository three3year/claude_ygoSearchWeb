"""抽樣重爬官方 Q&A 頁的 CLI 薄殼:確認「無補足情報」是否為快取過舊。

重爬指定/抽樣的 cid → 新頁覆蓋快取舊檔 → 重新抽取比對前後補足情報。
發現線上新增補足情報時明確回報並以非零碼結束,不自動全量重爬。
薄殼不納入自動測試。

用法:
    python script/faq_info/recrawl_faq.py --cache F:/AiProject/_cache \
        --sample 20 --cids 19359,20691
"""
import argparse
import json
import os
import sys
import time
import urllib.request

from faqinfo import parse_faq_page

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_FAQ_JSON = os.path.join(ROOT, "data", "sources", "faq_info.json")

URL = ("https://www.db.yugioh-card.com/yugiohdb/faq_search.action"
       "?ope=4&cid={cid}&request_locale=ja")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def fetch(cid):
    req = urllib.request.Request(
        URL.format(cid=cid), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def sample_evenly(items, n):
    """由排序清單等距取 n 個,涵蓋頭尾,結果可重現。"""
    if len(items) <= n:
        return list(items)
    step = (len(items) - 1) / (n - 1) if n > 1 else 0
    return [items[round(i * step)] for i in range(n)]


def supplement_keys(fields):
    return {k for k in ("supplement", "pen_supplement") if k in fields}


def main(argv=None):
    parser = argparse.ArgumentParser(description="抽樣重爬官方 Q&A 頁並比對補足情報")
    parser.add_argument("--cache", required=True, help="官方 Q&A 快取目錄")
    parser.add_argument("--faq-json", default=DEFAULT_FAQ_JSON,
                        help="整合 JSON 路徑,用來挑出無補足情報的卡")
    parser.add_argument("--sample", type=int, default=20,
                        help="無補足情報卡的抽樣數 (預設 20,0 表示不抽)")
    parser.add_argument("--cids", default="",
                        help="額外指定重爬的 cid,逗號分隔")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="請求間隔秒數 (預設 1.5)")
    args = parser.parse_args(argv)

    targets = []
    if args.sample > 0:
        with open(args.faq_json, encoding="utf-8") as f:
            entries = json.load(f)
        no_supp = sorted(e["cid"] for e in entries if "supplement" not in e)
        targets += sample_evenly(no_supp, args.sample)
    for part in args.cids.split(","):
        part = part.strip()
        if part:
            targets.append(int(part))

    gained = []
    for i, cid in enumerate(targets):
        if i:
            time.sleep(args.delay)
        path = os.path.join(args.cache, f"faq_{cid}.html")
        old_fields = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old_fields, _, _ = parse_faq_page(f.read())
        html = fetch(cid)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(html)
        new_fields, _, _ = parse_faq_page(html)

        new_keys = supplement_keys(new_fields) - supplement_keys(old_fields)
        if new_keys:
            gained.append(cid)
            status = f"線上新增補足情報 ({', '.join(sorted(new_keys))})"
        elif "card_text" not in new_fields:
            status = "線上仍無 card_info(疑似無此卡頁)"
        elif supplement_keys(new_fields):
            status = "維持有補足情報"
        else:
            status = "確認無補足情報"
        print(f"cid={cid} {status}")

    print(f"重爬完成: {len(targets)} 頁")
    if gained:
        print(f"注意: {len(gained)} 張卡的線上頁面出現原快取沒有的補足情報: {gained}")
        print("請決定是否全量重爬其餘無補足情報的快取。")
        return 1
    print("抽樣結論: 線上與快取一致,未發現新增的補足情報。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
