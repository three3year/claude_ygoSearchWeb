"""卡文勘誤的下游同步:拆句表與效果標記表的 text_zh / 雜湊跟上勘誤後卡文。

[[卡文勘誤表]](ADR-0011)在建置期改的是 `cards.json` 的卡文;拆句表與標記表
存著同一句的繁中原文子字串與雜湊,不跟著換就觸發拆句紀錄失效(split_stale)
與前端建置的覆蓋檢查失敗。**只動文字欄位,判定欄位(kind / optional / source)
原封不動**——那是判定票的成果,勘誤動的是卡文不是判定(盤問決定:同票一次性
更新,而不是教三個模組在讀入時各自套勘誤)。

可重跑(冪等):已同步的紀錄找不到原文子字串就跳過;新勘誤入表後重跑同一支。
原文子字串橫跨拆點(單一段落找不到、串接後找得到)無法機械處理,吵鬧失敗。

用法(於 repo 任意位置執行皆可,預設路徑以 repo 根為準):
    python script/tag_card/sync_errata_texts.py
    python script/tag_card/sync_errata_texts.py --dry-run
"""
import argparse
import os

from store import (DEFAULT_SPLITS, DEFAULT_TAG_CARDS, ROOT, dump_json,
                   load_json, load_optional)
from tagcard import _ja_order, _text_hash, split_hash

DEFAULT_ERRATA = os.path.join(ROOT, "data", "text_errata.json")


def _sync_split(record, entry, problems):
    """一筆拆句紀錄 × 一筆勘誤 → 是否有改動。雜湊由段落重建後重算。"""
    segments = record.get("segments") or []
    concat_zh = "".join(seg.get("text_zh", "") for seg in segments)
    order = _ja_order(record, len(segments))
    if order is None:
        problems.append(f"id={record['id']} ja_order 不合法,無法同步")
        return False
    concat_ja = "".join(segments[pos].get("text_ja", "") for pos in order)
    # 雜湊必須能由段落重建,改完才敢重算;對不上代表這筆紀錄另有隱情,人工處理
    if record.get("text_hash") != split_hash(concat_zh, concat_ja):
        problems.append(f"id={record['id']} 拆句雜湊無法由段落重建,人工處理")
        return False
    if entry["from"] not in concat_zh:
        return False  # 已同步過,或勘誤落在編號句/故事文,拆句表無事
    hits = [seg for seg in segments if entry["from"] in seg.get("text_zh", "")]
    if len(hits) != 1 or hits[0]["text_zh"].count(entry["from"]) != 1:
        problems.append(f"id={record['id']} 原文子字串橫跨拆點或出現多次,"
                        f"無法機械同步:{entry['from']}")
        return False
    hits[0]["text_zh"] = hits[0]["text_zh"].replace(entry["from"], entry["to"])
    new_zh = "".join(seg.get("text_zh", "") for seg in segments)
    record["text_hash"] = split_hash(new_zh, concat_ja)
    return True


def _sync_tag_row(clause, entry):
    """一行標記表 × 一筆勘誤 → 是否有改動。

    雜湊以判定基礎文本計(絕大多數卡是日文,勘誤不動它,雜湊因此不變;
    ADR-0006 的繁中單側卡以繁中計,跟著換)。
    """
    if entry["from"] not in clause.get("text_zh", ""):
        return False
    clause["text_zh"] = clause["text_zh"].replace(entry["from"], entry["to"])
    clause["text_hash"] = _text_hash(clause["text_ja"], clause["text_zh"])
    return True


def sync_texts(errata, splits, tag_entries):
    """→ report。就地修改 splits 與 tag_entries;有 problems 即不該寫出。"""
    splits_by_id = {}
    for record in splits or []:
        splits_by_id.setdefault(record["id"], []).append(record)
    tags_by_id = {e["id"]: e for e in tag_entries or []}
    report = {"splits_changed": 0, "clauses_changed": 0, "problems": []}
    for entry in errata:
        for record in splits_by_id.get(entry["id"], []):
            if _sync_split(record, entry, report["problems"]):
                report["splits_changed"] += 1
        tag_entry = tags_by_id.get(entry["id"])
        for clause in (tag_entry or {}).get("clauses") or []:
            if _sync_tag_row(clause, entry):
                report["clauses_changed"] += 1
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="卡文勘誤的拆句表/標記表同步")
    parser.add_argument("--errata", default=DEFAULT_ERRATA)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--tag-cards", default=DEFAULT_TAG_CARDS)
    parser.add_argument("--dry-run", action="store_true",
                        help="只報告,不寫檔")
    args = parser.parse_args(argv)

    errata = load_optional(args.errata, missing=[])
    splits = load_optional(args.splits, missing=[])
    tag_entries = load_optional(args.tag_cards, missing=[])
    report = sync_texts(errata, splits, tag_entries)
    for problem in report["problems"]:
        print(f"問題: {problem}")
    print(f"拆句紀錄改動 {report['splits_changed']} 筆、"
          f"標記表效果句改動 {report['clauses_changed']} 行"
          f"{'(dry-run,未寫檔)' if args.dry_run else ''}")
    if report["problems"]:
        return 1
    if not args.dry_run:
        if report["splits_changed"]:
            dump_json(args.splits, splits)
        if report["clauses_changed"]:
            dump_json(args.tag_cards, tag_entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
