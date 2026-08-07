"""一鍵更新卡片總表:下載三來源 → 管線建置 → 寫出 cards.json 與報告。

用法:
    python update_cards.py            # 下載最新來源後(差值)建置
    python update_cards.py --offline  # 不連網,用 sources/ 既有檔重跑
"""
import argparse
import json
import os
import ssl
import urllib.request

from build_cards import print_report
from cardlist import build_card_list, serialize_card_list

SOURCES = {
    "zh": "https://github.com/salix5/cdb/releases/latest/download/cards.cdb",
    "ja": ("https://raw.githubusercontent.com/mycard/ygopro-database/"
           "master/locales/ja-JP/cards.cdb"),
    "en": ("https://raw.githubusercontent.com/mycard/ygopro-database/"
           "master/locales/en-US/cards.cdb"),
}
FILENAMES = {"zh": "cards.cdb", "ja": "ja-JP.cdb", "en": "en-US.cdb"}


def _fetch_url(url):
    # 本機 curl 對 github.com 有憑證撤銷檢查問題(需 --ssl-no-revoke);
    # Python 預設不做撤銷檢查,維持憑證驗證即可。
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(url, timeout=120, context=ctx) as resp:
        return resp.read()


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


def main(argv=None):
    parser = argparse.ArgumentParser(description="一鍵更新卡片總表")
    parser.add_argument("--offline", action="store_true",
                        help="不連網,使用 sources/ 既有來源檔")
    parser.add_argument("--sources-dir", default="sources",
                        help="來源暫存目錄 (預設 sources/,不入版控)")
    parser.add_argument("-o", "--output", default="cards.json",
                        help="輸出 JSON 路徑 (預設 cards.json)")
    args = parser.parse_args(argv)

    paths = download_sources(args.sources_dir, offline=args.offline)

    existing = None
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)

    cards, report = build_card_list(
        paths["zh"], ja_path=paths["ja"], en_path=paths["en"],
        existing=existing)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_card_list(cards))
    print_report(report)
    print(f"已寫出 {args.output}")


if __name__ == "__main__":
    main()
