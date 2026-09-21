"""tag 判定批次檔的 CLI 薄殼(票09):跑一次管線 → 取當期待判 → 一批一檔。

與效果類型的 `make_batches.py` 同構,批次**即時產生**:每次都跑當前的規則層,
判定票永遠吃到最新的直貼結果與待判集合。兩個系列:

- `tag-<類別碼>` —— 動作 tag 的長尾判定。入選條件(ADR-0013):新式效果句、
  kind 已定、命中類別粗篩、無該類 tag、該類不在 tags_checked。判定者對每句給
  出該類**全部** tag(含空 = 判空,收票時記進 tags_checked)。
- `timing` —— 觸發時機的長尾判定。入選條件:誘發系承載類型、發動子句帶觸發
  事件、timing 仍空、「觸發時機」不在 tags_checked。

批次檔自帶體系定稿指紋、規則指紋與結果格式(spec Story 21:判定票只讀規範與
批次檔就能作答)。改判(rejudge)由旗標逐行標記:標的已有該類 llm tag(或已
判空)時,批次自動標 `rejudge: true`,結果檔必須回寫同一旗標。

用法:
    python script/tag_card/make_tag_batches.py --dry-run
    python script/tag_card/make_tag_batches.py --series tag-mv --start 1
    python script/tag_card/make_tag_batches.py --series timing --limit 1
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "web"))
import vocab  # noqa: E402

import tag_rules  # noqa: E402
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_SPLITS,  # noqa: E402
                   DEFAULT_TAG_CARDS, ROOT, dump_json, load_json,
                   load_modern_ja, load_optional)
from tagcard import _tag_scope_clauses, build_tag_cards  # noqa: E402

DEFAULT_BATCH_DIR = os.path.join(ROOT, ".scratch", "effect-tag", "batches")
BATCH_SIZE = 200

CAT_BY_CODE = {code: vocab.zh(vocab.TAG, code)
               for code in vocab.codes(vocab.TAG)}

RESULT_FORMAT = {
    "說明": "一效果句一物件,鍵 id / section / index 照批次檔抄。tag 系列:"
            "tags 給該句**該類別的全部** tag(槽位值照 docs/effect_tag_guide.md"
            " 的中文值域);該句沒有該類動作時 tags 給空陣列(= 判空,收票會記"
            "進 tags_checked)。timing 系列:timing 給觸發時機單值,判不進具名"
            "值時給「其他」;該句其實沒有觸發事件時 timing 給 null(收票記"
            "判空)。判不出時 tags/timing 留空並寫 note,不猜。",
    "改判": "批次檔標了 rejudge 的行,結果檔也要寫 rejudge: true,否則整批"
          "不寫入;批次沒標的行不准自己寫。",
    "範例": [
        {"id": 12345, "section": "main", "index": "①",
         "tags": [{"cat": "區域移動", "from": "牌組", "to": "手牌",
                   "side": "我方", "pos": "效果"}]},
        {"id": 12345, "section": "main", "index": "②", "tags": [],
         "note": ""},
        {"id": 67890, "section": "main", "index": "①",
         "timing": "召喚成功時"},
    ],
}


def pending_tag_rows(entries, report):
    """→ {類別: [待判效果句列, ...]}(沿用管線報告的待判清單)。"""
    by_key = {(cid, clause["section"], clause["index"]): clause
              for cid, clause in _tag_scope_clauses(entries)}
    series = {}
    for row in report["tag_pending"]:
        clause = by_key[(row["id"], row["section"], row["index"])]
        series.setdefault(row["cat"], []).append((row["id"], clause))
    return series


def pending_timing_rows(entries, report):
    """觸發時機的待判效果句(母體由管線報告給,與 seal 同一份)。"""
    by_key = {(cid, clause["section"], clause["index"]): clause
              for cid, clause in _tag_scope_clauses(entries)}
    return [(row["id"], by_key[(row["id"], row["section"], row["index"])])
            for row in report["timing_pending"]]


def clause_row(cid, clause, card, series):
    row = {
        "id": cid,
        "section": clause["section"],
        "index": clause["index"],
        "name_zh": card.get("name_zh") or "",
        "kind": clause["kind"],
        "text_zh": clause["text_zh"],
        "text_ja": clause["text_ja"],
    }
    if series != "timing":
        cat = CAT_BY_CODE.get(series.replace("tag-", ""))
        if (any(t.get("cat") == cat and t.get("src") != "rule"
                for t in clause["tags"]) or cat in clause["tags_checked"]):
            row["rejudge"] = True
    elif clause["timing_src"] not in (None, "rule"):
        row["rejudge"] = True
    return row


def taxonomy_block(series, category):
    """批次檔自帶的體系定稿本體(Story 21:只讀規範與批次檔就能作答)。

    值域照正典現場導出——抄一份死的進來,體系一動批次就帶著過期定稿出門
    (指紋擋得住收票,擋不住判定者白做工)。"""
    if series == "timing":
        return {
            "軸": "觸發時機(句層單值,僅誘發系承載類型)",
            "值域": [e["zh"] for e in vocab.entries(vocab.TIMING)],
            "通則": "同句多時機取最先寫出的;判不進具名值給「其他」;"
                  "該句沒有觸發事件時給 null(判空)。",
        }
    code = series.replace("tag-", "")
    return {
        "類別": category,
        "槽位": {key: [e["zh"] for e in vocab.entries(domain_name)]
               for key, domain_name in vocab.TAG_SLOTS[code]},
        "通則": "位置=成本只標發動子句內的代價,其餘一律效果;對象方判得準"
              "才填;複合起點逐起點各貼一個 tag;槽位不確定就留空。",
    }


def write_batch(path, name, series, category, number, remaining, rows):
    dump_json(path, {
        "batch": name,
        "series": series,
        "category": category,
        "number": number,
        "remaining_batches": remaining,
        "clauses": len(rows),
        "guide": "docs/effect_tag_guide.md",
        "taxonomy": taxonomy_block(series, category),
        "taxonomy_digest": vocab.tag_digest(),
        "tag_rules_digest": tag_rules.digest(),
        "result_format": RESULT_FORMAT,
        "entries": rows,
    })


def main(argv=None):
    parser = argparse.ArgumentParser(description="產生 tag 判定批次檔")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_TAG_CARDS)
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--out-dir", default=DEFAULT_BATCH_DIR)
    parser.add_argument("--series", action="append", default=[],
                        help="tag-<類別碼>(如 tag-mv)或 timing;可重複,"
                             "預設全部")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--name", help="檔名(單檔時)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    cards = load_json(args.cards)
    faqs = load_json(args.faq_info)
    entries, report = build_tag_cards(cards, faqs,
                                      existing=load_optional(args.sheet),
                                      splits=load_optional(args.splits),
                                      modern_ja=load_modern_ja())
    by_id = {card["id"]: card for card in cards}

    series = {}
    code_by_cat = {zh_name: code for code, zh_name in CAT_BY_CODE.items()}
    for cat, rows in pending_tag_rows(entries, report).items():
        series[f"tag-{code_by_cat[cat]}"] = (cat, rows)
    series["timing"] = ("觸發時機", pending_timing_rows(entries, report))

    wanted = args.series or sorted(series)
    for name in wanted:
        if name not in series:
            print(f"沒有 {name} 這個系列(現有:{sorted(series)})")
            return 1
    total_files = 0
    for name in wanted:
        rows = series[name][1]
        groups = [rows[i:i + BATCH_SIZE]
                  for i in range(0, len(rows), BATCH_SIZE)]
        total_files += (len(groups) if args.limit is None
                        else min(args.limit, len(groups)))
    if args.name and total_files > 1:
        print("--name 只能用在只寫出一個檔案的時候")
        return 1
    if not args.dry_run:
        os.makedirs(args.out_dir, exist_ok=True)

    for name in wanted:
        category, rows = series[name]
        groups = [rows[i:i + BATCH_SIZE]
                  for i in range(0, len(rows), BATCH_SIZE)]
        print(f"{name}({category}): {len(rows)} 條待判 → {len(groups)} 批")
        if args.dry_run:
            continue
        limit = len(groups) if args.limit is None else args.limit
        for offset, group in enumerate(groups[:limit]):
            number = args.start + offset
            batch = args.name or f"{name}-{number:02d}"
            path = os.path.join(args.out_dir, f"{batch}.json")
            payload = [clause_row(cid, clause, by_id.get(cid, {}), name)
                       for cid, clause in group]
            write_batch(path, batch, name, category, number, len(groups),
                        payload)
            print(f"  已寫出 {path}({len(group)} 條)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
