"""一鍵更新卡片總表:下載三來源 → 管線建置 → 寫出 cards.json 與報告。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/update_cards.py            # 下載最新來源後(差值)建置
    python script/update_cards.py --offline  # 不連網,用既有來源檔重跑
"""
import argparse
import json
import os
import ssl
import urllib.request

from build_cards import DEFAULT_OUTPUT, print_report
from cardlist import build_card_list, serialize_card_list

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCES_DIR = os.path.join(ROOT, "data", "sources")

SOURCES = {
    "zh": "https://github.com/salix5/cdb/releases/latest/download/cards.cdb",
    "ja": ("https://raw.githubusercontent.com/mycard/ygopro-database/"
           "master/locales/ja-JP/cards.cdb"),
    "en": ("https://raw.githubusercontent.com/mycard/ygopro-database/"
           "master/locales/en-US/cards.cdb"),
}
FILENAMES = {"zh": "cards.cdb", "ja": "ja-JP.cdb", "en": "en-US.cdb"}
MD_RARITY_URL = ("https://www.masterduelmeta.com/api/v1/cards"
                 "?limit=3000&page={page}&fields=konamiID,rarity")
MD_RARITY_FILENAME = "md-rarity.json"
# genesys_points 只在帶 format=genesys 時才出現於 misc_info
GENESYS_URL = ("https://db.ygoprodeck.com/api/v7/cardinfo.php"
               "?misc=yes&format=genesys")
GENESYS_FILENAME = "genesys.json"


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
    """自 masterduelmeta API 分頁抓取 {卡片密碼: MD稀有度} → md-rarity.json。

    分頁抓到空頁為止;konamiID 非純數字或缺稀有度的條目略過。
    先寫 .tmp 再原子替換,失敗時既有檔不受影響。
    """
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, MD_RARITY_FILENAME)
    if offline:
        if not os.path.exists(path):
            raise RuntimeError(
                f"離線模式但缺少來源 md({path});請先連網下載一次")
        return path
    rarity = {}
    page = 1
    try:
        while True:
            rows = fetch_json(MD_RARITY_URL.format(page=page))
            if not rows:
                break
            for row in rows:
                kid = row.get("konamiID")
                value = row.get("rarity")
                if kid and value and str(kid).isdigit():
                    rarity[int(kid)] = value
            page += 1
    except Exception as e:
        raise RuntimeError(f"來源 md 下載失敗(第 {page} 頁): {e}") from e
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({str(k): v for k, v in sorted(rarity.items())}, f,
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="一鍵更新卡片總表")
    parser.add_argument("--offline", action="store_true",
                        help="不連網,使用 sources/ 既有來源檔")
    parser.add_argument("--sources-dir", default=DEFAULT_SOURCES_DIR,
                        help="來源暫存目錄 (預設 data/sources/,不入版控)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="輸出 JSON 路徑 (預設 data/cards.json)")
    args = parser.parse_args(argv)

    paths = download_sources(args.sources_dir, offline=args.offline)
    md_path = download_md_rarity(args.sources_dir, offline=args.offline)
    genesys_path = download_genesys(args.sources_dir, offline=args.offline)

    existing = None
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)

    cards, report = build_card_list(
        paths["zh"], ja_path=paths["ja"], en_path=paths["en"],
        md_rarity_path=md_path, genesys_path=genesys_path, existing=existing)
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_card_list(cards))
    print_report(report)
    print(f"已寫出 {args.output}")


if __name__ == "__main__":
    main()
