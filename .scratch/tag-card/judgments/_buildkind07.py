# -*- coding: utf-8 -*-
"""票43 — kind-07 判定結果產生器。

「只判類型」系列不拆句:效果句集合已由批次檔決定,本腳本只把逐條判定
(kind / optional / role / note)對回批次檔的 (section, index),並在寫檔前
自檢集合一致——少一條或多一條當場失敗,不等合併程序的關卡一。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BATCH = os.path.join(ROOT, ".scratch", "tag-card", "batches", "kind-07.json")
OUT = os.path.join(ROOT, ".scratch", "tag-card", "judgments", "kind-07.json")

# id -> [(section, index, kind, optional, note), ...]
SPEC = {}


def add(cid, rows):
    if cid in SPEC:
        raise SystemExit("重複判定: %s" % cid)
    SPEC[cid] = [tuple(r) for r in rows]


from _speckind07 import fill  # noqa: E402

fill(add)


def main():
    batch = json.load(io.open(BATCH, encoding="utf-8"))
    want = {}
    for e in batch["entries"]:
        want[e["id"]] = [(c["section"], c["index"]) for c in e["clauses"]]

    missing = [i for i in want if i not in SPEC]
    if missing and os.environ.get("PARTIAL"):
        print("PARTIAL: 略過未判 %d 張" % len(missing))
        want = {i: v for i, v in want.items() if i in SPEC}
        missing = []
    if missing:
        raise SystemExit("尚未判定 %d 張: %s" % (len(missing), sorted(missing)[:20]))
    extra = [i for i in SPEC if i not in want]
    if extra:
        raise SystemExit("SPEC 有批次外的卡: %s" % extra)

    result = []
    for e in batch["entries"]:
        cid = e["id"]
        if cid not in SPEC:
            continue
        rows = SPEC[cid]
        got = [(r[0], r[1]) for r in rows]
        if sorted(got) != sorted(want[cid]):
            raise SystemExit("[%s] 效果句集合不符\n  批次 %s\n  判定 %s"
                             % (cid, sorted(want[cid]), sorted(got)))
        if len(set(got)) != len(got):
            raise SystemExit("[%s] 同一條判了兩次: %s" % (cid, got))
        by_section = {}
        for section, index, kind, optional, note in rows:
            row = {"index": index, "kind": kind, "optional": optional,
                   "role": None}
            if note:
                row["note"] = note
            by_section.setdefault(section, []).append(row)
        for section in sorted(by_section):
            result.append({"id": cid, "section": section,
                           "clauses": by_section[section]})

    json.dump(result, io.open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    n = sum(len(r["clauses"]) for r in result)
    n_kind = sum(1 for r in result for c in r["clauses"] if c.get("kind"))
    n_empty = n - n_kind
    n_opt = sum(1 for r in result for c in r["clauses"] if c.get("optional"))
    print("卡 %d / 段落 %d / 效果句 %d / 有類型 %d / 留空 %d / 必發選發 %d"
          % (len({r["id"] for r in result}), len(result), n, n_kind, n_empty, n_opt))


if __name__ == "__main__":
    main()
