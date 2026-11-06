"""建置字段表的 CLI 薄殼:strings.conf + 補丁 + 卡片總表 + 官方 DB 文本 → data/archetypes.json
與報告 .scratch/action-structure/report/archetypes.md。

薄殼只做四件事:讀檔 → 呼叫 archetype_table → 寫檔 → 印摘要。時間與來源雜湊只印到
stdout,不進產物與報告正文,所以兩次建置逐位元組相同。補丁有問題(欄位不認得、
setcode 格式錯)以非 0 結束、不寫檔。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python -X utf8 script/action_structure/build_archetypes.py

上游來源 `data/sources_vendored/strings.conf` 入版控;要更新時用 Python 下載
(本機 curl 對 github.com 有憑證撤銷檢查問題,urllib 沒有,見 update_cards.py):
    python -X utf8 script/action_structure/build_archetypes.py --fetch
"""
import argparse
import datetime
import hashlib
import json
import os
import ssl
import sys
import urllib.request

from archetype_table import (build_archetypes, render_report,
                             parse_setnames, serialize_archetypes)

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STRINGS = os.path.join(ROOT, "data", "sources_vendored", "strings.conf")
DEFAULT_PATCHES = os.path.join(ROOT, "data", "archetype_patches.json")
DEFAULT_CARDS = os.path.join(ROOT, "data", "cards.json")
DEFAULT_FAQ_INFO = os.path.join(ROOT, "data", "sources", "faq_info.json")
DEFAULT_OUTPUT = os.path.join(ROOT, "data", "archetypes.json")
DEFAULT_REPORT = os.path.join(ROOT, ".scratch", "action-structure", "report",
                              "archetypes.md")
STRINGS_URL = ("https://raw.githubusercontent.com/mycard/ygopro-database/"
               "master/locales/ja-JP/strings.conf")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def fetch_strings(path):
    """從上游抓 strings.conf 原檔(帶 BOM 的 UTF-8,照原樣存)。"""
    req = urllib.request.Request(STRINGS_URL,
                                 headers={"User-Agent": "ygoSearchWeb/1.0"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        data = resp.read()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    print(f"已下載 {STRINGS_URL} → {path}({len(data)} bytes)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="建置動作搜尋的字段表")
    parser.add_argument("--strings", default=DEFAULT_STRINGS,
                        help="上游 strings.conf(預設 data/sources_vendored/strings.conf)")
    parser.add_argument("--patches", default=DEFAULT_PATCHES,
                        help="本站補丁(預設 data/archetype_patches.json)")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq", default=DEFAULT_FAQ_INFO,
                        help="官方 DB 文本(預設 data/sources/faq_info.json)")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                        help="字段表產物(預設 data/archetypes.json)")
    parser.add_argument("--report", default=DEFAULT_REPORT,
                        help="報告路徑(預設 .scratch/action-structure/report/archetypes.md)")
    parser.add_argument("--fetch", action="store_true",
                        help="先從上游下載 strings.conf 覆蓋本地副本")
    args = parser.parse_args(argv)
    if args.fetch:
        fetch_strings(args.strings)
    for path in (args.strings, args.faq):
        if not os.path.exists(path):
            print(f"找不到 {path}", file=sys.stderr)
            return 1
    with open(args.strings, encoding="utf-8-sig") as f:
        setnames = parse_setnames(f.read())
    patches = _load_json(args.patches) if os.path.exists(args.patches) else []
    rows, report = build_archetypes(setnames, patches, _load_json(args.cards),
                                    _load_json(args.faq))
    built_at = datetime.datetime.now().astimezone().strftime(
        "%Y-%m-%dT%H:%M:%S%z")
    print(f"建置時間 {built_at}")
    for path in (args.strings, args.cards, args.faq):
        print(f"來源 {os.path.basename(path)} digest={_digest(path)}")
    print(f"字段 {report['total']} 筆、配到中文名 {report['matched']}、"
          f"配不到 {len(report['unmatched'])}、候選不唯一 {len(report['ambiguous'])}、"
          f"套用補丁 {len(report['patches'])}")
    if report["problems"]:
        for problem in report["problems"]:
            print(f"補丁問題:{problem}", file=sys.stderr)
        return 1
    with open(args.output, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize_archetypes(rows))
    os.makedirs(os.path.dirname(os.path.abspath(args.report)), exist_ok=True)
    with open(args.report, "w", encoding="utf-8", newline="\n") as f:
        f.write(render_report(report))
    print(f"已寫出 {args.output} 與 {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
