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

第三種批次不排票、由票逐條指名:`--rejudge` 的**改判批次**(票52)。規範改版後回頭
修既有判定時,標的是已經判過的效果句,`collect()` 那條路(只認 `kind` 為 null 的待判
行)看不到它們,所以另走 `write_rejudge_batch()`。

用法:
    python script/tag_card/make_batches.py --dry-run        # 只點數,不寫檔
    python script/tag_card/make_batches.py --series split --limit 1 --start 2
    python script/tag_card/make_batches.py --rejudge 1200843:main:2 \\
        --name fix-52
"""
import argparse
import os
import re
import sys

import official
from official import INDEX_UNNUMBERED
from store import (DEFAULT_CARDS, DEFAULT_FAQ_INFO, DEFAULT_SPLITS,
                   DEFAULT_TAG_CARDS, ROOT, dump_json, load_json,
                   load_optional)
from tagcard import (FOOTNOTE_RE, SECTION_PENDULUM, build_tag_cards,
                     card_type_label)

DEFAULT_BATCH_DIR = os.path.join(ROOT, ".scratch", "tag-card", "batches")

SERIES_KIND = "kind"
SERIES_SPLIT = "split"
# 「改判」不是排票排得到的系列:它的標的是**已經判過**的效果句,由規範改版後的
# 一張改判票逐條指名(票52)。因此沒有批量、沒有批號,一次一個檔。
SERIES_FIX = "fix"
_ONLY_RE = re.compile(r"^\d+(,\d+)*$")
_REJUDGE_RE = re.compile(r"^(\d+):(main|pendulum):([^,:]+)$")
# 每批卡數。「要拆+判」的輸出多一份拆點,單卡成本約兩倍,所以放得少。
BATCH_SIZE = {SERIES_KIND: 300, SERIES_SPLIT: 200}
SERIES_LABEL = {SERIES_KIND: "只判類型", SERIES_SPLIT: "要拆+判",
                SERIES_FIX: "改判"}


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


def clause_row(clause):
    return {"index": clause["index"], "section": clause["section"],
            "text_zh": clause["text_zh"], "text_ja": clause["text_ja"],
            "rule_predicted": clause["rule_predicted"]}


def card_context(entry, card, faq):
    """一張卡的完整上下文:卡文兩側 + 不裁剪的補足情報。效果句由呼叫端填。"""
    payload = {
        "id": entry["id"],
        "name_zh": card.get("name_zh"),
        "name_ja": card.get("name_ja") or faq.get("name_ja"),
        # 規範 §5.8 的「這張卡本身的發動」由[[卡片種類]]決定,而通常魔法與速攻魔法
        # 的卡文寫法一樣——不附上種類,判定者只讀批次檔就走不完那一節
        "card_type": card_type_label(card.get("type", 0)),
        # 尾端的 ※ 別名譯註照管線剝除:card_text_zh 必須與拆句標的的整團原文
        # 一致,否則判定者照它抄段落會在覆蓋驗證上失敗(票21 的 20349913)
        "card_text_zh": FOOTNOTE_RE.sub("", card.get("desc") or ""),
        "card_text_ja": faq.get("card_text") or "",
        "supplement": faq.get("supplement") or "",
        "clauses": [],
    }
    if faq.get("pen_effect") or faq.get("pen_supplement"):
        payload["pendulum"] = {
            "card_text_ja": faq.get("pen_effect") or "",
            "supplement": faq.get("pen_supplement") or "",
        }
    return payload


def card_payload(entry, card, faq, blobs):
    """一張待判卡的上下文 + 待判效果句(+ 要拆的整團)。"""
    payload = card_context(entry, card, faq)
    payload["clauses"] = [clause_row(c) for c in pending_clauses(entry)]
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


def parse_rejudge(spec):
    """`密碼:section:index,…` → [(密碼, section, index), …];寫壞時回 None。"""
    keys = []
    for item in spec.split(","):
        match = _REJUDGE_RE.match(item.strip())
        if match is None:
            return None
        keys.append((int(match.group(1)), match.group(2), match.group(3)))
    return keys


def rejudge_payloads(entries, cards, faqs, keys):
    """指名的效果句 → 改判批次的卡片酬載;對不上時回 (None, 理由)。

    標的必須是**已經判過**的效果句:改判是換掉一個判定,還沒判的那一行走的是
    正常排票(判了才有東西可換)。批次帶上這一行現在的判定與來源,改判票才知道
    自己要動的是什麼、以及那一行動不動得了(官方明示與人工修正動不了,票52)。
    """
    by_id = {card["id"]: card for card in cards}
    faq_by_id = {e["password"]: e for e in faqs if e.get("password")}
    clause_index = {(entry["id"], clause["section"], clause["index"]):
                    (entry, clause)
                    for entry in entries for clause in entry["clauses"]}
    payloads = {}
    for key in keys:
        found = clause_index.get(key)
        if found is None:
            return None, f"{key} 不是標記表上的效果句"
        entry, clause = found
        if clause["kind"] is None:
            return None, f"{key} 還沒判過,改判無從換起(走正常排票)"
        payload = payloads.get(entry["id"])
        if payload is None:
            payload = card_context(entry, by_id.get(entry["id"], {}),
                                   faq_by_id.get(entry["id"], {}))
            payloads[entry["id"]] = payload
        payload["clauses"].append({
            **clause_row(clause), "rejudge": True,
            "current": {"kind": clause["kind"], "optional": clause["optional"],
                        "role": clause["role"], "source": clause["source"]},
        })
    return [payloads[cid] for cid in sorted(payloads)], None


def collect(entries, report, cards, faqs):
    """→ {系列: [卡片酬載, ...]},依卡片密碼升冪。

    「有沒有待判的效果句」不是唯一的入選條件:**未拆的整團就算類型已經有了也要排**
    ——官方以 `『①』` 指名整團時它會拿到 `official` 的類型(spec 的階梯二對未拆整團
    照樣開火),`pending_clauses` 因此看不到它,那張卡就再也進不了拆句批次(票09 在
    23927567 幸運を告げるフクロウ 上發現這個缺口,全表僅此一張)。拆句與判類型是
    兩件事,入選條件要各問各的。
    """
    by_id = {card["id"]: card for card in cards}
    faq_by_id = {e["password"]: e for e in faqs if e.get("password")}
    blobs_by_id = {}
    for row in report["pending_split"]:
        blobs_by_id.setdefault(row["id"], []).append(row)
    series = {SERIES_KIND: [], SERIES_SPLIT: []}
    for entry in sorted(entries, key=lambda e: e["id"]):
        blobs = blobs_by_id.get(entry["id"], [])
        if not pending_clauses(entry) and not blobs:
            continue
        payload = card_payload(entry, by_id.get(entry["id"], {}),
                               faq_by_id.get(entry["id"], {}), blobs)
        series[SERIES_SPLIT if blobs else SERIES_KIND].append(payload)
    return series


def batches_of(payloads, size):
    return [payloads[start:start + size]
            for start in range(0, len(payloads), size)]


def _file_count(series, wanted, limit):
    """這一次會寫出幾個檔案。`--name` 只能用在剛好一個的時候。"""
    total = 0
    for name in wanted:
        groups = batches_of(series[name], BATCH_SIZE[name])
        total += len(groups) if limit is None else min(limit, len(groups))
    return total


# 判定票只讀規範與批次檔,所以結果檔的格式得寫在批次檔裡(spec Story 36)
RESULT_FORMAT = {
    "說明": "一卡一段落一物件。split_targets 的段落要拆句,寫 split: true 與"
            "每段的原文子字串;其餘只填 kind / optional / role。"
            "拆不出來或判不出來的留空並寫 note,不猜。"
            "note 只在 kind 留空時被合併程序讀取;寫在已判行上的 note 只留在"
            "結果檔當稽核軌跡,不進標記表與報告。",
    "兩側語序不一致": "繁中與日文把同一批句子排成不同順序時,clauses 照繁中順序"
                "列、另給 ja_order(段落位置的排列)說明日文怎麼讀;index 仍照"
                "日文的序號給,官方的『①』對的是日文那一側(規範 §8 判準11)。",
    "改判": "批次檔的效果句寫了 rejudge 的(改判批次),結果檔那一行也要寫 "
          "rejudge: true,否則既有判定會照 ADR-0002 擋下來、改判等於沒做;"
          "反過來,批次沒標的效果句不准自己寫這個旗標。current 是那一行現在的"
          "判定,改判後仍相同也照樣寫回來(空操作,不報錯)。",
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
        {"id": 24680, "section": "main", "split": True, "ja_order": [1, 2, 0],
         "_說明": "日文讀 ①②③,繁中把 ③ 搬到最前面。clauses 照繁中順序列,"
                "ja_order 說明日文從第 2 段讀起(=[1, 2, 0]);"
                "index 照日文的序號給,所以是 3、1、2——這一例的日文③剛好是"
                "效果外文本,index 因此寫 0(判準5:效果外文本段一律 0)。",
         "clauses": [
             {"index": "0", "text_zh": "（繁中第一段 = 日文③,效果外文本）",
              "text_ja": "（日文第三句）"},
             {"index": "1", "text_zh": "（繁中第二段 = 日文①）",
              "text_ja": "（日文第一句）",
              "kind": "誘發即時效果(2速)", "optional": "選發", "role": None},
             {"index": "2", "text_zh": "（繁中第三段 = 日文②）",
              "text_ja": "（日文第二句）",
              "kind": "永續效果", "optional": None, "role": None}]},
    ],
}


def write_batch(path, name, series, number, remaining, payload):
    # `remaining` 是**產生這一批的當下**這個系列還剩幾批,不是「總共幾批」——
    # 待判集合一票比一票小,總數是個會過期的數字。改判批次兩者皆為 None:
    # 它由票逐條指名,沒有批量也沒有下一批
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


def write_rejudge_batch(entries, cards, faqs, args):
    """`--rejudge` 那條路:一張改判票、一個檔,標的由票逐條指名。

    不走 `collect()`——那一支只認**待判**的效果句(`kind` 為 null),而改判的標的
    恰恰是已經判過的那些行。
    """
    if not args.name:
        print("--rejudge 要配 --name:改判批次不屬於任何一個排票系列,"
              "沒有算得出來的檔名")
        return 1
    if args.only or args.series or args.limit is not None:
        # 排票用的旗標在這條路上一個都不生效,靜靜忽略會讓人以為篩過了
        print("--rejudge 是逐條指名的,不能配 --only / --series / --limit")
        return 1
    keys = parse_rejudge(args.rejudge)
    if keys is None:
        print("--rejudge 只吃逗號分隔的 <卡片密碼>:<section>:<index>")
        return 1
    payload, problem = rejudge_payloads(entries, cards, faqs, keys)
    if problem is not None:
        print(problem)
        return 1
    clauses = sum(len(c["clauses"]) for c in payload)
    print(f"{SERIES_LABEL[SERIES_FIX]}({SERIES_FIX}): {len(payload)} 張卡 / "
          f"{clauses} 條改判標的")
    if args.dry_run:
        return 0
    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f"{args.name}.json")
    write_batch(path, args.name, SERIES_FIX, None, None, payload)
    print(f"  已寫出 {path}")
    return 0


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
    parser.add_argument("--only", help="只放這幾張卡(逗號分隔的卡片密碼)。"
                                       "回頭補判先前留空的卡用——正式排票要的是"
                                       "無遺漏地判完全部,不要拿它來挑卡")
    parser.add_argument("--name", help="檔名(預設 <系列>-<批號>)。"
                                       "補判批次取個自己的名字,才不會蓋掉正式排票的檔")
    parser.add_argument("--rejudge",
                        help="改判批次:逗號分隔的 <卡片密碼>:<section>:<index>,"
                             "標的必須是已經判過的效果句。規範改版後回頭修既有"
                             "判定用,要配 --name 自己取檔名")
    parser.add_argument("--dry-run", action="store_true",
                        help="只點數,不寫檔")
    args = parser.parse_args(argv)

    cards = load_json(args.cards)
    faqs = load_json(args.faq_info)
    entries, report = build_tag_cards(cards, faqs,
                                      existing=load_optional(args.sheet),
                                      splits=load_optional(args.splits))

    if args.rejudge is not None:
        return write_rejudge_batch(entries, cards, faqs, args)

    series = collect(entries, report, cards, faqs)
    wanted = args.series or [SERIES_SPLIT, SERIES_KIND]
    if args.only is not None:
        if not _ONLY_RE.match(args.only):
            print("--only 只吃逗號分隔的卡片密碼")
            return 1
        only = {int(cid) for cid in args.only.split(",")}
        series = {name: [p for p in payloads if p["id"] in only]
                  for name, payloads in series.items()}
        found = {p["id"] for name in wanted for p in series[name]}
        if only - found:
            print(f"--only 指名的 {sorted(only - found)} 不在待判集合裡"
                  f"(或不屬於 {wanted})")
            return 1
    if args.name and _file_count(series, wanted, args.limit) > 1:
        # `--name` 是給補判批次取名用的,一次只寫一檔;會寫出多檔時取同一個名字
        # 等於自己蓋掉自己,那正是這個旗標要避免的事
        print("--name 只能用在只寫出一個檔案的時候,請加上 --only 或 --limit 1")
        return 1
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
            batch = args.name or f"{name}-{number:02d}"
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
