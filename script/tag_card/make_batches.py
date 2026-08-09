"""判定批次檔的 CLI 薄殼:跑一次管線 → 取出待判的卡 → 寫成一批一檔。

批次**即時產生**:每次都跑當前的規則層與拆句表,判定票因此永遠吃到最新的影子預測
與最新的效果句集合,不會拿著過期的批次去判(spec「批次檔即時產生」)。

分成兩個系列,不混在一起排票——兩種工作的輸出格式與成本差約兩倍,混編會讓每票的
實際負擔不可預測:

- `kind`「只判類型」—— 卡文已經有①②③,效果句集合已定,判定者只填類型與必發/選發。
- `split`「要拆+判」—— 舊式無編號卡文,判定者要先依語意拆句再判類型。批次檔額外附上
  補足情報裡命中整團的 `『原文』` 引用當**拆點提示**;那只是提示,程式不會自動拆
  (理由同 `_split_bullets`:官方沒有明確分項的引用可能只是一句話的片段,ADR-0003)。

補足情報**不裁剪**、原文照抄:批次檔要自足到判定票不必回頭查任何其他來源。

批號由 `--start` 給:待判集合一票比一票小(判完就不再出現),所以「第幾批」不是算得
出來的,每票報自己的批號,檔名才不會互相蓋掉。

用法:
    python script/tag_card/make_batches.py --dry-run        # 只點數,不寫檔
    python script/tag_card/make_batches.py --series split --limit 1 --start 2
"""
import argparse
import os
import sys

import official
from official import INDEX_UNNUMBERED
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_SPLITS,
                   DEFAULT_TAG_CARDS, ROOT, dump_json, load_json,
                   load_optional)
from tagcard import SECTION_PENDULUM, build_tag_cards, card_type_label

DEFAULT_BATCH_DIR = os.path.join(ROOT, ".scratch", "tag-card", "batches")

SERIES_KIND = "kind"
SERIES_SPLIT = "split"
# 每批卡數。「要拆+判」的輸出多一份拆點,單卡成本約兩倍,所以放得少。
BATCH_SIZE = {SERIES_KIND: 300, SERIES_SPLIT: 200}
SERIES_LABEL = {SERIES_KIND: "只判類型", SERIES_SPLIT: "要拆+判"}


def pending_clauses(entry):
    """這張卡仍待判定的效果句。效果外文本段由位置規則填好了,自然不在其中。"""
    return [clause for clause in entry["clauses"] if clause["kind"] is None]


def quote_hints(supplement, text_ja):
    """補足情報裡命中這一團的 `『原文』` 引用——拆點的提示,不是拆點。"""
    body = official.normalise(text_ja)
    hints = []
    for quoted in official.quotes(supplement):
        needle = official.normalise(quoted)
        if needle and needle in body and quoted not in hints:
            hints.append(quoted)
    return hints


def card_payload(entry, card, faq, blobs):
    """一張待判卡的完整上下文:卡文兩側 + 不裁剪的補足情報 + 待判效果句。"""
    clauses = pending_clauses(entry)
    payload = {
        "id": entry["id"],
        "name_zh": card.get("name_zh"),
        "name_ja": card.get("name_ja") or faq.get("name_ja"),
        # 規範 §5.8 的「這張卡本身的發動」由[[卡片種類]]決定,而通常魔法與速攻魔法
        # 的卡文寫法一樣——不附上種類,判定者只讀批次檔就走不完那一節
        "card_type": card_type_label(card.get("type", 0)),
        "card_text_zh": card.get("desc") or "",
        "card_text_ja": faq.get("card_text") or "",
        "supplement": faq.get("supplement") or "",
        "clauses": [{"index": c["index"], "section": c["section"],
                     "text_zh": c["text_zh"], "text_ja": c["text_ja"],
                     "rule_predicted": c["rule_predicted"]}
                    for c in clauses],
    }
    if faq.get("pen_effect") or faq.get("pen_supplement"):
        payload["pendulum"] = {
            "card_text_ja": faq.get("pen_effect") or "",
            "supplement": faq.get("pen_supplement") or "",
        }
    # 拆句標的的原文取自待拆清單那一份**整團**,不取標記表上那一行——● 子效果
    # 可能已經把那一行切掉一塊,照它拆會在雜湊與覆蓋兩道驗證同時失敗(票13)
    targets = []
    for blob in blobs:
        supplement = (faq.get("pen_supplement")
                      if blob["section"] == SECTION_PENDULUM
                      else faq.get("supplement")) or ""
        targets.append({
            "section": blob["section"], "index": INDEX_UNNUMBERED,
            "text_zh": blob["text_zh"], "text_ja": blob["text_ja"],
            "quote_hints": quote_hints(supplement, blob["text_ja"]),
        })
    if targets:
        payload["split_targets"] = targets
    return payload


def collect(entries, report, cards, faqs):
    """→ {系列: [卡片酬載, ...]},依卡片密碼升冪。"""
    by_id = {card["id"]: card for card in cards}
    faq_by_id = {e["password"]: e for e in faqs if e.get("password")}
    blobs_by_id = {}
    for row in report["pending_split"]:
        blobs_by_id.setdefault(row["id"], []).append(row)
    series = {SERIES_KIND: [], SERIES_SPLIT: []}
    for entry in sorted(entries, key=lambda e: e["id"]):
        if not pending_clauses(entry):
            continue
        blobs = blobs_by_id.get(entry["id"], [])
        payload = card_payload(entry, by_id.get(entry["id"], {}),
                               faq_by_id.get(entry["id"], {}), blobs)
        series[SERIES_SPLIT if blobs else SERIES_KIND].append(payload)
    return series


def batches_of(payloads, size):
    return [payloads[start:start + size]
            for start in range(0, len(payloads), size)]


# 判定票只讀規範與批次檔,所以結果檔的格式得寫在批次檔裡(spec Story 36)
RESULT_FORMAT = {
    "說明": "一卡一段落一物件。split_targets 的段落要拆句,寫 split: true 與"
            "每段的原文子字串;其餘只填 kind / optional / role。"
            "拆不出來或判不出來的留空並寫 note,不猜。",
    "範例": [
        {"id": 12345, "section": "main", "split": True,
         "clauses": [
             {"index": "0", "text_zh": "（效果外文本段的繁中原文）",
              "text_ja": "（同一段的日文原文）"},
             {"index": "1", "text_zh": "（效果句的繁中原文）",
              "text_ja": "（同一段的日文原文）",
              "kind": "啟動效果", "optional": None, "role": None}]},
        {"id": 67890, "section": "main",
         "clauses": [{"index": "①", "kind": "誘發效果(1速)",
                      "optional": "必發", "role": None, "note": ""}]},
    ],
}


def write_batch(path, name, series, number, remaining, payload):
    # `remaining` 是**產生這一批的當下**這個系列還剩幾批,不是「總共幾批」——
    # 待判集合一票比一票小,總數是個會過期的數字
    body = {
        "batch": name,
        "series": series,
        "series_label": SERIES_LABEL[series],
        "number": number,
        "remaining_batches": remaining,
        "cards": len(payload),
        "clauses": sum(len(c["clauses"]) for c in payload),
        "guide": "docs/effect_kind_guide.md",
        "result_format": RESULT_FORMAT,
        "entries": payload,
    }
    dump_json(path, body)


def main(argv=None):
    parser = argparse.ArgumentParser(description="產生判定批次檔")
    parser.add_argument("--cards", default=DEFAULT_CARDS)
    parser.add_argument("--faq-info", default=DEFAULT_FAQ_INFO)
    parser.add_argument("--sheet", default=DEFAULT_TAG_CARDS,
                        help="既有效果標記表 (預設 data/tag_cards.json)")
    parser.add_argument("--splits", default=DEFAULT_SPLITS)
    parser.add_argument("--out-dir", default=DEFAULT_BATCH_DIR)
    parser.add_argument("--series", choices=(SERIES_KIND, SERIES_SPLIT),
                        action="append", default=[],
                        help="只寫這個系列,可重複;預設兩個都寫")
    parser.add_argument("--limit", type=int,
                        help="每個系列只寫前 N 批(試點用)")
    parser.add_argument("--start", type=int, default=1,
                        help="第一個檔案的批號。每票只生自己那一批,而批次是"
                             "即時產生的(待判集合一票比一票小),所以批號由票"
                             "自己給,檔名才不會互相蓋掉")
    parser.add_argument("--dry-run", action="store_true",
                        help="只點數,不寫檔")
    args = parser.parse_args(argv)

    cards = load_json(args.cards)
    faqs = load_json(args.faq_info)
    entries, report = build_tag_cards(cards, faqs,
                                      existing=load_optional(args.sheet),
                                      splits=load_optional(args.splits))

    series = collect(entries, report, cards, faqs)
    wanted = args.series or [SERIES_SPLIT, SERIES_KIND]
    if not args.dry_run:
        os.makedirs(args.out_dir, exist_ok=True)

    for name in (SERIES_SPLIT, SERIES_KIND):
        payloads = series[name]
        clauses = sum(len(c["clauses"]) for c in payloads)
        groups = batches_of(payloads, BATCH_SIZE[name])
        print(f"{SERIES_LABEL[name]}({name}): {len(payloads)} 張卡 / "
              f"{clauses} 條待判效果句 → {len(groups)} 批,"
              f"每批 {BATCH_SIZE[name]} 張")
        if args.dry_run or name not in wanted:
            continue
        limit = len(groups) if args.limit is None else args.limit
        for offset, group in enumerate(groups[:limit]):
            number = args.start + offset
            batch = f"{name}-{number:02d}"
            path = os.path.join(args.out_dir, f"{batch}.json")
            write_batch(path, batch, name, number, len(groups), group)
            print(f"  已寫出 {path}({len(group)} 張 / "
                  f"{sum(len(c['clauses']) for c in group)} 條)")
        if limit < len(groups):
            print(f"  其餘 {len(groups) - limit} 批未產生"
                  f"(下一票開始時再生,吃得到最新的規則層)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
