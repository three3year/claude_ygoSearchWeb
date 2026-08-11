# -*- coding: utf-8 -*-
"""票36 — split-20 判定結果產生器。

拆句用「切點字串」表示,由本腳本從批次檔原文切出連續子字串,
確保硬性規則一(連續子字串)與二(無遺漏覆蓋)在寫檔前就成立。
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
BATCH = os.path.join(ROOT, ".scratch", "tag-card", "batches", "split-20.json")
OUT = os.path.join(ROOT, ".scratch", "tag-card", "judgments", "split-20.json")

NO_JA_NOTE = (
    "日文卡文缺漏(card_text_ja 為空):拆句表要求兩側原文的連續子字串與無遺漏覆蓋,"
    "日文側無從拆分對位;判定亦以日文卡文與補足情報為準(規範開頭),無從判。"
    "留待來源補齊日文後再拆(同票23-35 處理,票55 追蹤)。"
)

# id -> dict(zh=[切點...], ja=[切點...], segs=[(index, kind, optional, note), ...], ja_order=[...])
# 切點是「下一段的開頭字串」,必須在原文中唯一命中。
SPEC = {}


def add(cid, segs, zh=(), ja=(), ja_order=None):
    if segs is None:          # 來源沒有日文卡文,整團留空
        SPEC[cid] = dict(no_ja=True)
        return
    SPEC[cid] = dict(zh=list(zh), ja=list(ja), segs=segs, ja_order=ja_order)


from _spec20 import fill  # noqa: E402

fill(add)


def cut(text, marks, cid, side):
    """依切點把 text 切成 len(marks)+1 段,回傳段落 list。"""
    parts = []
    base = 0
    for m in marks:
        idx = text.find(m, base)
        if idx < 0:
            raise SystemExit("[%s] %s 切點找不到: %r" % (cid, side, m))
        if text.find(m, idx + 1) >= 0:
            raise SystemExit("[%s] %s 切點不唯一: %r" % (cid, side, m))
        parts.append(text[base:idx])
        base = idx
    parts.append(text[base:])
    return [p.strip() for p in parts]


def main():
    batch = json.load(io.open(BATCH, encoding="utf-8"))
    entries = {e["id"]: e for e in batch["entries"]}
    result = []
    missing = [i for i in entries if i not in SPEC]
    if missing and os.environ.get("PARTIAL"):
        batch["entries"] = [e for e in batch["entries"] if e["id"] in SPEC]
        print("PARTIAL: 略過未判 %d 張" % len(missing))
        missing = []
    if missing:
        raise SystemExit("尚未判定 %d 張: %s" % (len(missing), missing[:20]))
    extra = [i for i in SPEC if i not in entries]
    if extra:
        raise SystemExit("SPEC 有批次外的卡: %s" % extra)

    for e in batch["entries"]:
        cid = e["id"]
        spec = SPEC[cid]
        if spec.get("no_ja"):
            result.append({"id": cid, "section": "main", "split": True,
                           "clauses": [], "note": NO_JA_NOTE})
            continue
        tgt = e["split_targets"][0]
        zh_parts = cut(tgt["text_zh"], spec["zh"], cid, "zh")
        ja_parts = cut(tgt["text_ja"], spec["ja"], cid, "ja")
        segs = spec["segs"]
        if not (len(zh_parts) == len(ja_parts) == len(segs)):
            raise SystemExit("[%s] 段數不一致 zh=%d ja=%d segs=%d"
                             % (cid, len(zh_parts), len(ja_parts), len(segs)))
        order = spec.get("ja_order")
        ja_by_clause = [None] * len(segs)
        if order:
            if sorted(order) != list(range(len(segs))):
                raise SystemExit("[%s] ja_order 不是位置排列: %s" % (cid, order))
            for k, pos in enumerate(order):
                ja_by_clause[pos] = ja_parts[k]
        else:
            ja_by_clause = ja_parts
        clauses = []
        for i, (index, kind, optional, note) in enumerate(segs):
            c = {"index": index, "text_zh": zh_parts[i], "text_ja": ja_by_clause[i],
                 "kind": kind, "optional": optional, "role": None}
            if note:
                c["note"] = note
            clauses.append(c)
        row = {"id": cid, "section": "main", "split": True, "clauses": clauses}
        if order:
            row["ja_order"] = order
        result.append(row)

        # 覆蓋自檢(忽略空白)
        for side, parts, orig in (("zh", zh_parts, tgt["text_zh"]),
                                  ("ja", ja_parts, tgt["text_ja"])):
            joined = re.sub(r"\s+", "", "".join(parts))
            want = re.sub(r"\s+", "", orig)
            if joined != want:
                raise SystemExit("[%s] %s 覆蓋不符" % (cid, side))

    json.dump(result, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_seg = sum(len(r["clauses"]) for r in result)
    n_kind = sum(1 for r in result for c in r["clauses"] if c.get("kind"))
    n_opt = sum(1 for r in result for c in r["clauses"] if c.get("optional"))
    n_empty = sum(1 for r in result for c in r["clauses"] if not c.get("kind"))
    print("卡 %d / 段 %d / 有類型 %d / 類型留空 %d / 必發選發 %d / 整團未拆 %d"
          % (len(result), n_seg, n_kind, n_empty, n_opt,
             sum(1 for r in result if not r["clauses"])))


if __name__ == "__main__":
    main()
