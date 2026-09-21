"""效果 Tag 規則層的遮蔽測試(ADR-0013 的敘用門檻)。

效果類型的遮蔽測試拿[[官方明示]]當標準答案;tag 沒有這種免費對照,標準答案
改由**獨立判定**產生:從類別候選句(粗篩命中)抽固定種子樣本,判定者**看不到
規則輸出**、只依判定規範(docs/effect_tag_guide.md)逐句標注全部該類 tag,
存成標準答案檔;規則層再對著標準答案計分。

兩個接縫,純函式、不碰檔案系統:

    sample_tag_masked(標記表, 卡片總表, 類別[, 條數, 種子]) → (樣本, 報告)
    score_tag_masked(標記表, 樣本, 標準答案[, 規則]) → 報告

門檻(rulings.md 批4):逐規則**錯標 0**(規則發出而判定者沒給,一筆都不容——
直貼的錯標會靜靜進資料)、**框架 recall ≥ 90%**(標準答案裡屬於該規則框架
——內容與規則樣板相同——的 tag,規則群要復現九成)、**分母 ≥ 8**(樣本內
命中不足 8 句的規則,補抽其命中句判定後才算數)。

樣本檔與標準答案檔入版控(.scratch/effect-tag/masked/),tag seal 每輪對著
它們**現場重算**規則輸出——規則改了,成績就跟著變,不會留著一張過期的及格單。

詞彙見 CONTEXT.md:效果 Tag、動作類別、遮蔽測試。
"""
import random

import tag_rules
from tagcard import _tag_scope_clauses, rule_tags_for

DEFAULT_SIZE = 200
DEFAULT_SEED = 20260920

SAMPLE_FIELDS = ("id", "section", "index", "name_zh", "text_zh", "text_ja")


# 內容鍵(剝 src/rule/ticket 後排序)的單一來源在 tag_rules
_content = tag_rules._content


def _rule_emits(clause_ja, rules):
    """一句的規則層輸出(內容 → 發出它的規則編號集合)。"""
    emitted = {}
    for tag in rule_tags_for(clause_ja, rules):
        emitted.setdefault(_content(tag), set()).add(tag["rule"])
    return emitted


def sample_tag_masked(entries, cards, category, size=DEFAULT_SIZE,
                      seed=DEFAULT_SEED, extra_ids=()):
    """類別候選句的固定種子樣本(判定者拿去標注的那一份,不含規則輸出)。

    extra_ids 是補抽清單((id, section, index) 的集合):樣本內命中不足 8 句的
    規則,由呼叫端把該規則命中句補進來(分母下限,rulings.md 批4)。
    """
    cards_by_id = {card["id"]: card for card in cards}
    pool = [(cid, clause) for cid, clause in _tag_scope_clauses(entries)
            if tag_rules.screen_hit(category, clause["text_ja"])]
    rng = random.Random(seed)
    picked = rng.sample(pool, min(size, len(pool)))
    keys = {(cid, clause["section"], clause["index"])
            for cid, clause in picked}
    for cid, clause in pool:
        if (cid, clause["section"], clause["index"]) in set(extra_ids) - keys:
            picked.append((cid, clause))
            keys.add((cid, clause["section"], clause["index"]))
    picked.sort(key=lambda row: (row[0], row[1]["section"], row[1]["index"]))
    sample = [{
        "id": cid,
        "section": clause["section"],
        "index": clause["index"],
        "name_zh": cards_by_id.get(cid, {}).get("name_zh", ""),
        "text_zh": clause["text_zh"],
        "text_ja": clause["text_ja"],
    } for cid, clause in picked]
    report = {"category": category, "size": len(sample),
              "population": len(pool), "seed": seed}
    return sample, report


def _key(row):
    return (row["id"], row["section"], row["index"])


def score_tag_masked(entries, sample, answers, rules=None,
                     category=tag_rules.CAT_MOVE):
    """樣本 + 標準答案 → 逐規則成績報告。

    規則輸出**現場重算**(對著標記表裡這一句現在的日文原文):樣本產出之後規則
    改過的話,成績反映的是**現在的**規則層——這正是 seal 要問的問題。句子本身
    變了(text_ja 與樣本不符)列 stale,該重抽。
    """
    rules = tag_rules.active() if rules is None else rules
    rules = [rule for rule in rules if rule["cat"] == category]
    clauses = {(entry_id, clause["section"], clause["index"]): clause
               for entry_id, clause in _tag_scope_clauses(entries)}
    truth_by_key = {}
    extra, invalid = [], []
    sample_keys = {_key(row) for row in sample}
    for row in answers:
        key = _key(row)
        if key not in sample_keys:
            extra.append(key)
            continue
        tags = []
        for tag in row.get("tags", ()):
            if tag.get("cat") != category:
                invalid.append({"key": key, "tag": tag,
                                "reason": "類別不是本次遮蔽測試的類別"})
                continue
            tags.append(tag)
        truth_by_key[key] = tags
    stale, missing = [], []
    scored_keys = []
    for row in sample:
        key = _key(row)
        clause = clauses.get(key)
        if clause is None or clause["text_ja"] != row["text_ja"]:
            stale.append(key)
            continue
        if key not in truth_by_key:
            missing.append(key)
            continue
        scored_keys.append(key)

    # 比對走**子集語意**:判定者依規範會把 side 等規則層不猜的槽位也填上,
    # 規則 tag 是標準答案某 tag 的子集(全部槽位一致、只是少填)即正確;
    # 標準答案的 tag 被「內容是它子集」的規則輸出命中即算復現。
    def subset(inner, outer):
        return all(item in outer for item in inner)

    per_rule = {rule["id"]: {"fired": 0, "wrong": 0, "wrong_rows": []}
                for rule in rules}
    template_of = {rule["id"]: [_content({"cat": rule["cat"], **template,
                                          "pos": _rule_pos(rule)})
                                for template in rule["tags"]]
                   for rule in rules}
    truth_total = 0
    truth_matched = 0
    frame = {rule["id"]: {"total": 0, "matched": 0} for rule in rules}
    for key in scored_keys:
        clause = clauses[key]
        emitted = _rule_emits(clause["text_ja"], rules)
        truth = [_content(tag) for tag in truth_by_key[key]]
        for content, rule_ids in emitted.items():
            for rule_id in rule_ids:
                if rule_id not in per_rule:
                    continue
                per_rule[rule_id]["fired"] += 1
                if not any(subset(content, t) for t in truth):
                    per_rule[rule_id]["wrong"] += 1
                    per_rule[rule_id]["wrong_rows"].append(
                        {"key": key, "tag": dict(content)})
        truth_total += len(truth)
        truth_matched += sum(1 for t in truth
                             if any(subset(c, t) for c in emitted))
        for rule_id, templates in template_of.items():
            for t in truth:
                if any(subset(template, t) for template in templates):
                    frame[rule_id]["total"] += 1
                    if any(subset(c, t) for c in emitted):
                        frame[rule_id]["matched"] += 1

    rows = []
    for rule in rules:
        stats = per_rule[rule["id"]]
        fr = frame[rule["id"]]
        recall = fr["matched"] / fr["total"] if fr["total"] else None
        rows.append({
            "id": rule["id"], "condition": rule["condition"],
            "fired": stats["fired"], "wrong": stats["wrong"],
            "wrong_rows": stats["wrong_rows"],
            "frame_total": fr["total"], "frame_matched": fr["matched"],
            "recall": recall,
            "thin": 0 < stats["fired"] < tag_rules.MASKED_MIN_HITS,
            "passed": (stats["wrong"] <= tag_rules.MASKED_MAX_WRONG
                       and (recall is None
                            or recall >= tag_rules.MASKED_MIN_RECALL)),
        })
    consistent = not (stale or missing or extra or invalid)
    passed = (consistent and bool(scored_keys)
              and all(row["passed"] and not row["thin"]
                      for row in rows if row["fired"]))
    return {
        "category": category,
        "scored": len(scored_keys),
        "stale": stale, "missing": missing, "extra": extra,
        "invalid": invalid,
        "rules": rows,
        "truth_tags": truth_total,
        "truth_matched": truth_matched,
        "category_recall": truth_matched / truth_total if truth_total
        else None,
        "passed": passed,
    }


def _rule_pos(rule):
    return (tag_rules.POS_COST if rule["scope"] == tag_rules.SCOPE_COST
            else tag_rules.POS_EFFECT)
