"""抽取官方 Q&A 快取的 CLI 薄殼:掃描快取目錄 → faqinfo 管線 → 寫出 faq_info.json。

用法(於 repo 任意位置執行皆可):
    python script/faq_info/build_faq_info.py --cache F:/AiProject/_cache
"""
import argparse
import glob
import json
import os
import re
import sys

from faqinfo import extract_faq_info

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUTPUT = os.path.join(ROOT, "data", "sources", "faq_info.json")

FAQ_NAME = re.compile(r"faq_(\d+)\.html$")


def iter_cache_pages(cache_dir):
    """掃描快取目錄,依序產出 (cid, html 字串)。"""
    paths = glob.glob(os.path.join(cache_dir, "faq_*.html"))
    for path in sorted(paths):
        m = FAQ_NAME.search(os.path.basename(path))
        if not m:
            continue
        with open(path, encoding="utf-8") as f:
            yield int(m.group(1)), f.read()


def load_cid_to_password(cache_dir):
    """由快取目錄的 ygoprodeck 資料檔建 cid(konami_id)→卡片密碼 對應表。"""
    mapping = {}
    for path in sorted(glob.glob(os.path.join(cache_dir, "ygopro_*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for card in data.get("data", []):
            for misc in card.get("misc_info", []):
                kid = misc.get("konami_id")
                if kid is not None:
                    mapping.setdefault(kid, card["id"])
    return mapping


def print_report(report, file=sys.stdout):
    p = lambda *a: print(*a, file=file)  # noqa: E731
    p(f"收錄: {report['included']} 張")
    p(f"無補足情報: {len(report['no_supplement'])} 張")
    p(f"靈擺卡: {report['pendulum']} 張")
    missing = report.get("password_missing")
    if missing is not None:
        p(f"對不到卡片密碼的 cid: {len(missing)} 筆")
        for cid in missing:
            p(f"  cid={cid}")
    p(f"無 card_info(不收錄): {len(report['no_card_info'])} 筆")
    for cid in report["no_card_info"]:
        p(f"  cid={cid}")
    hits = report["outside_supplement"]
    p(f"場外「補足情報」: {len(hits)} 處")
    for h in hits:
        p(f"  cid={h['cid']} 前後文={h['context']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="抽取官方 Q&A 快取為補足情報 JSON")
    parser.add_argument("--cache", required=True, help="官方 Q&A 快取目錄")
    parser.add_argument("--out", default=DEFAULT_OUTPUT,
                        help="輸出 JSON 路徑 (預設 data/sources/faq_info.json)")
    args = parser.parse_args(argv)

    cid_to_password = load_cid_to_password(args.cache)
    entries, report = extract_faq_info(
        iter_cache_pages(args.cache), cid_to_password=cid_to_password)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n")
        f.write(",\n".join(
            json.dumps(e, ensure_ascii=False) for e in entries))
        f.write("\n]\n")

    print_report(report)
    print(f"已寫出 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
