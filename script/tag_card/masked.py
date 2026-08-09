"""遮蔽測試:量化[[效果類型]]判定的準確率(票07)。

做法是拿[[官方明示]]當標準答案:從已經填好類型的效果句分層抽一批,把補足情報
裡的類型結論句遮掉,判定者只憑卡名、繁中與日文效果句原文、以及剩下的補足情報,
依 `docs/effect_kind_guide.md` 判一次,再對答案。

兩個接縫,都是純函式,不碰網路與檔案系統:

    sample_masked(標記表, 卡片總表, 補足情報[, 條數, 每類下限, 種子, 排除的卡])
        → (樣本, 報告)
    score_masked(標記表, 樣本, 判定[, 已知歧義, 管線缺陷]) → 報告

標準答案**不寫進樣本檔**——對答案時現場從標記表照 (卡片密碼, section, index)
查回來。樣本檔因此不可能夾帶答案,判定者拿到的就是遮蔽過的那一份。

門檻是**逐類別 100%**:難分的類別不該被簡單類別的高分稀釋,所以總體準確率照算
但不作為門檻。未達標時要修的是規範文件而不是重刷分數(見票07 的分流)。

詞彙見 CONTEXT.md。
"""
import random
import re

from official import KINDS, NON_EFFECT_RE

DEFAULT_SIZE = 300
DEFAULT_PER_KIND_MIN = 40
# 抽樣種子。寫死才能「同一份標記表抽出同一份樣本」,換樣本要換這個數字。
DEFAULT_SEED = 20260809

SOURCE_OFFICIAL = "official"
SECTION_PENDULUM = "pendulum"

# 逐類別門檻(票07 由使用者定為 100%)
RECALL_THRESHOLD = 1.0
# 已知歧義的上限。超過代表六類邊界的定義本身有問題,該回頭改 CONTEXT.md 而不是
# 繼續重跑(票07)。
AMBIGUOUS_CAP = 5
# 管線缺陷(錯不在判定而在抽取/歸屬,標準答案本身是錯的)的上限。超過代表該先修
# 管線再測判定(票07 第二期)。與歧義分開記——兩者的成因與修法都不同。
PIPELINE_CAP = 5
# 兩個「排除於分母」的桶。分開記到底:各自的清單、各自的「不在樣本內」、各自的
# 上限——把管線缺陷的超限印成歧義超限,會讓分流的人去改錯地方。
# 上限是**單次執行**的,跨輪次的累計要自己在票裡記。
BUCKET_CAPS = {"ambiguous": AMBIGUOUS_CAP, "pipeline": PIPELINE_CAP}

# 樣本檔的欄位。答案(kind / optional / source / rule_predicted)一律不在其中。
SAMPLE_FIELDS = ("id", "section", "index", "name_zh", "name_ja",
                 "text_zh", "text_ja", "supplement")

# 補足情報裡會直接講出答案的句型,整句遮掉。
# 「効果ではありません」不必單獨列——那個句型裡的類型詞已經被類型詞本身命中。
# 效果外文本的明示不寫在這裡:官方有八種等義變體,共用抽取器的 NON_EFFECT_RE
# 才不會像票07 第二期輪 4 那樣漏遮 18 行的官方答案(當時只認八種裡的一種)。
# 共用的只有那條正規表示式:抽取器還要求明示出現在**括弧之外**才採用,遮蔽這邊
# 不加這個限制——括弧裡的一樣講出了答案,寧可多遮。
_CONCLUSION_MARKS = ("誘発即時効果", "誘発効果", "起動効果", "永続効果",
                     "分類されない", "必ず発動")

_HEADER_PREFIX_RE = re.compile(r"^【[^】]*】")
_SENTENCE_RE = re.compile(r"[^。]*。|[^。]+$")
# 遮蔽後只剩標點、括號或「■」的行等於沒有內容
_RESIDUE_RE = re.compile(r"^[\s。、，,・…（）()「」『』■\-—]*$")


# ---------------------------------------------------------------- 遮蔽

def _is_conclusion(sentence):
    """這一句有沒有直接講出答案。"""
    return (any(mark in sentence for mark in _CONCLUSION_MARKS)
            or bool(NON_EFFECT_RE.search(sentence)))


def _tidy(text):
    """句子被遮掉後可能留下沒有開頭的右括號(官方把補述寫在括號裡)。"""
    while text and text[-1] in "）)":
        if text.count("（") + text.count("(") >= text.count("）") + text.count(")"):
            break
        text = text[:-1]
    return text.strip()


def _mask_line(line):
    """一行補足情報 → 遮掉類型結論句之後的樣子(整行沒內容了就回空字串)。

    標頭 `【①の効果について】` 是歸屬標記而不是結論,保留——它告訴判定者官方在
    講哪一個效果句,不告訴他是哪一種。
    """
    match = _HEADER_PREFIX_RE.match(line)
    header, body = (match.group(0), line[match.end():]) if match else ("", line)
    kept = "".join(sentence for sentence in _SENTENCE_RE.findall(body)
                   if not _is_conclusion(sentence))
    kept = _tidy(kept)
    if _RESIDUE_RE.match(kept):
        kept = ""
    return header + kept


def mask_supplement(text):
    """補足情報 → 不含類型結論的補足情報。"""
    lines = [_mask_line(raw.strip()) for raw in (text or "").split("\n")]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------- 抽樣

def _quotas(population, size, per_kind_min):
    """六類的母體大小 → 各抽幾條。

    先給每一類抽滿下限(母體不足就全取),多出來的名額再依母體比例分配(最大餘數
    法),配額不得超過母體。這樣難分的小類別有保底條數,大類別也不會被壓成陪襯。
    """
    quota = {kind: min(per_kind_min, population[kind]) for kind in population}
    extra = size - sum(quota.values())
    while extra > 0:
        room = {kind: population[kind] - quota[kind] for kind in population}
        room = {kind: n for kind, n in room.items() if n > 0}
        if not room:
            break
        total = sum(population[kind] for kind in room)
        exact = {kind: extra * population[kind] / total for kind in room}
        add = {kind: min(room[kind], int(exact[kind])) for kind in room}
        left = extra - sum(add.values())
        for kind in sorted(room, key=lambda k: (-(exact[k] % 1),
                                                -population[k], k)):
            if left <= 0:
                break
            if add[kind] < room[kind]:
                add[kind] += 1
                left -= 1
        for kind, count in add.items():
            quota[kind] += count
        extra -= sum(add.values())
    return quota


def _candidates(entries, exclude_ids=()):
    """標記表 → 可以當標準答案的效果句(官方明示且類型在值域內)。

    exclude_ids 整張卡排掉:先前輪次抽過的卡,以及判定者在別處看過官方答案的卡。
    排除的粒度是**卡**而不是效果句——同一張卡的[[補足情報]]是共用的,判過 ① 之後
    再抽到 ② 等於帶著看過的情報作答。
    """
    excluded = set(exclude_ids)
    return [(entry["id"], clause) for entry in sorted(entries,
                                                      key=lambda e: e["id"])
            if entry["id"] not in excluded
            for clause in entry["clauses"]
            if clause["source"] == SOURCE_OFFICIAL and clause["kind"] in KINDS]


def _row(cid, clause, card, faq):
    supplement = faq.get("pen_supplement" if clause["section"]
                         == SECTION_PENDULUM else "supplement")
    return {
        "id": cid,
        "section": clause["section"],
        "index": clause["index"],
        "name_zh": card.get("name_zh") or "",
        "name_ja": faq.get("name_ja") or card.get("name_ja") or "",
        "text_zh": clause["text_zh"],
        "text_ja": clause["text_ja"],
        "supplement": mask_supplement(supplement),
    }


def sample_masked(entries, cards, faq_entries, size=DEFAULT_SIZE,
                  per_kind_min=DEFAULT_PER_KIND_MIN, seed=DEFAULT_SEED,
                  exclude_ids=()):
    """標記表 + 卡片總表 + 補足情報 → (遮蔽樣本, 抽樣報告)。

    只抽 `source: "official"` 的效果句——標準答案是官方寫的,不是推論來的。
    六種類型分層,每類至少 per_kind_min 條,母體不足的類別全取並列進 shortfall。

    exclude_ids 的那些卡整張不抽(見 `_candidates`)。多輪測試靠它讓各輪樣本互斥
    ——重疊的行在後面幾輪等於送分,曲線會虛高。

    每類下限優先於 size:`per_kind_min * 6 > size` 時抽出來的會比 size 多,報告的
    `requested_size` 與 `size` 因此不相等。門檻是逐類別 recall,小類別的分母不能為了
    湊總數被砍掉。
    """
    by_kind = {kind: [] for kind in KINDS}
    for cid, clause in _candidates(entries, exclude_ids):
        by_kind[clause["kind"]].append((cid, clause))
    population = {kind: len(rows) for kind, rows in by_kind.items()}
    quota = _quotas(population, size, per_kind_min)

    cards_by_id = {card["id"]: card for card in cards}
    faq_by_id = {faq["password"]: faq for faq in faq_entries
                 if faq.get("password") is not None}
    rng = random.Random(seed)
    picked = []
    for kind in KINDS:
        picked += rng.sample(by_kind[kind], quota[kind])
    picked.sort(key=lambda row: (row[0], row[1]["section"], row[1]["index"]))

    sample = [_row(cid, clause, cards_by_id.get(cid, {}),
                   faq_by_id.get(cid, {})) for cid, clause in picked]
    report = {
        "size": len(sample),
        "requested_size": size,
        "per_kind_min": per_kind_min,
        "population": population,
        "quota": quota,
        "taken": {kind: sum(1 for cid, clause in picked
                            if clause["kind"] == kind) for kind in KINDS},
        "shortfall": [kind for kind in KINDS
                      if population[kind] < per_kind_min],
        "seed": seed,
        "excluded_ids": len(set(exclude_ids)),
    }
    return sample, report


# ---------------------------------------------------------------- 對答案

def _key(row):
    return (row["id"], row["section"], row["index"])


def _answer_key(entries):
    """標記表 → {(卡片密碼, section, index): 官方類型 or None}。

    鍵收全部的行,值只認 `source: "official"`。兩件事因此分得開:鍵不在裡面代表
    那一行整個不見了(樣本過期),鍵在但值是 None 代表那一行**現在沒有官方答案**
    ——可能是官方明示被撤回,也可能是判定票後來把類型填了上去。後者尤其不能當
    標準答案:那是判定者自己的產出,拿它對答案等於讓判定者跟自己對。
    """
    return {(entry["id"], clause["section"], clause["index"]):
            clause["kind"] if clause["source"] == SOURCE_OFFICIAL else None
            for entry in entries for clause in entry["clauses"]}


def _identity(key):
    cid, section, index = key
    return {"id": cid, "section": section, "index": index}


def score_masked(entries, sample, answers, ambiguous=(), pipeline=()):
    """標記表 + 樣本 + 判定 → 逐類別 recall 報告。

    標準答案現場從標記表查回來,樣本檔不帶答案。判定的集合必須與樣本完全一致
    (漏判進 missing、多判進 extra、值域外的類型進 invalid),三者任一非空即不通過
    ——分母對不上的準確率沒有意義。

    ambiguous 是[[已知歧義清單]]:官方文本本身歧義的條目不計入分母,但超過
    AMBIGUOUS_CAP 條就代表六類邊界的定義有問題,直接判不通過。

    pipeline 是[[管線缺陷]]:標準答案本身是錯的(抽取器或歸屬階梯把別的效果句的
    類型套了上來),同樣不計入分母。與歧義分兩個桶,因為修法完全不同——歧義改的是
    六類的定義,管線缺陷改的是程式。超過 PIPELINE_CAP 條就該先修管線再測判定。
    兩個桶的清單、「不在樣本內」與上限都各報各的,見 BUCKET_CAPS。

    樣本檔是先產出、後判定的,中間標記表可能已經重跑過。漂移分兩種,都排除於分母
    之外但下場不同:

      stale     —— `(卡片密碼, section, index)` 在標記表裡整個不見了。結構對不上,
                   判不通過,該重抽。
      withdrawn —— key 還在,但那一行**現在沒有官方答案**:官方明示被撤回(票11 撤掉
                   未拆整團的就撤了 1,146 條),或判定票後來把類型填了上去。都是資料
                   的正常演進,不判不通過,只是那一條沒有標準答案可對。

    判定者仍然可以對 withdrawn 的行作答——那些行當初確實在樣本裡,答了不算多判、
    不答也不算漏判。
    """
    official = _answer_key(entries)
    stale = [_identity(_key(row)) for row in sample
             if _key(row) not in official]
    present = [_key(row) for row in sample if _key(row) in official]
    withdrawn = [_identity(key) for key in present
                 if official[key] not in KINDS]
    sample_keys = [key for key in present if official[key] in KINDS]
    in_sample = set(present)
    text_by_key = {_key(row): row for row in sample}

    answered, extra, invalid = {}, [], []
    for row in answers:
        key = _key(row)
        if key not in in_sample:
            extra.append(_identity(key))
            continue
        kind = row.get("kind")
        if kind is not None and kind not in KINDS:
            invalid.append({**_identity(key), "kind": kind})
            kind = None
        answered[key] = kind
    invalid_keys = {(row["id"], row["section"], row["index"]) for row in invalid}
    missing = [_identity(key) for key in sample_keys if key not in answered]

    excluded = {name: {} for name in BUCKET_CAPS}
    unknown = {name: [] for name in BUCKET_CAPS}
    for name, rows_in in (("ambiguous", ambiguous), ("pipeline", pipeline)):
        for row in rows_in:
            key = _key(row)
            if key in in_sample:
                excluded[name][key] = row.get("reason", "")
            else:
                unknown[name].append(_identity(key))
    skipped, defective = excluded["ambiguous"], excluded["pipeline"]

    per_kind = {}
    errors, blank = [], []
    correct = scored = 0
    for key in sample_keys:
        kind = official[key]
        stats = per_kind.setdefault(kind, {"total": 0, "ambiguous": 0,
                                           "pipeline": 0,
                                           "scored": 0, "correct": 0})
        stats["total"] += 1
        if key in skipped:
            stats["ambiguous"] += 1
            continue
        if key in defective:
            stats["pipeline"] += 1
            continue
        given = answered.get(key)
        stats["scored"] += 1
        scored += 1
        if given == kind:
            stats["correct"] += 1
            correct += 1
            continue
        row = text_by_key[key]
        errors.append({**_identity(key), "official": kind, "answered": given,
                       "name_zh": row["name_zh"], "text_zh": row["text_zh"],
                       "text_ja": row["text_ja"]})
        if given is None and key not in invalid_keys:
            blank.append(_identity(key))
    for stats in per_kind.values():
        stats["recall"] = stats["correct"] / stats["scored"] \
            if stats["scored"] else None

    over_cap = {name: len(excluded[name]) > cap
                for name, cap in BUCKET_CAPS.items()}
    consistent = not (missing or extra or invalid or stale
                      or any(unknown.values()))
    passed = (consistent and not any(over_cap.values()) and bool(per_kind)
              and all(stats["recall"] is not None
                      and stats["recall"] >= RECALL_THRESHOLD
                      for stats in per_kind.values()))
    return {
        "size": len(sample),
        "stale": stale,
        "withdrawn": withdrawn,
        "missing": missing,
        "extra": extra,
        "invalid": invalid,
        **{name: [{**_identity(key), "reason": reason}
                  for key, reason in sorted(rows.items())]
           for name, rows in excluded.items()},
        "unknown": unknown,
        "over_cap": over_cap,
        "per_kind": per_kind,
        "overall": {"scored": scored, "correct": correct,
                    "accuracy": correct / scored if scored else None},
        "errors": errors,
        "blank": blank,
        "passed": passed,
    }
