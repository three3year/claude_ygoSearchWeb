# -*- coding: utf-8 -*-
"""剝鍵比對(frame-args-v4 票 01):第四版論元只加欄不換值——把新鍵剝掉後,frames.json 要和
修前凍結的基準檔逐紀錄、逐框、逐鍵相同。

- NEW_KEYS:框架的頂層新鍵(規格的全部新欄,票 01 先列齊;這份清單是唯一要維護的東西);
  NEW_ANAPHORA_KEYS:回指欄的新子鍵(票 09 的 moving)。
- strip(frame):剝掉新鍵的框架副本。
- strip_procedure(record):剝框重編(summon-procedure 票 01)——剝掉位置是召喚手續的框、框序照剩下的重編;
  diff 與 stripped_md5 比之前先過它,下游基準(downstream_baseline)也經它。
- diff(baseline_path, current_path):差異清單 [(卡號, 段落, 句序, 框序, 鍵, 基準值, 現值)];
  框數不同時框序 None、鍵 "frames";紀錄缺少時鍵 "record"。
- underscore_keys(records):底線開頭的內部鍵(票 02 暫存切前字面用,enrich 用完要 pop 掉),
  不得出現在 frames.json。

CLI:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/baseline_diff.py [--baseline P] [--current P]
預設 baseline/frames.json(gitignore)與 frames.json;環境變數 FRAMES_BASELINE 蓋過預設基準。
差異非 0 或有底線鍵時 exit 1。基準檔不入版控(26MB),所以另有一道入版控的守門:
`baseline-digest.json` 記 tokens.json 的 md5 與「剝鍵後 frames.json」的 md5(`--freeze` 寫入);
`check_digest()` 在語料沒變(tokens md5 相同)時比剝鍵後的 md5——規則改動碰到既有欄就會對不上,
語料變了(新卡、勘誤)則略過並要求重新凍結。沒有基準檔時 CLI 也只走這條。
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from constraints import POS_PROCEDURE  # noqa: E402

BASELINE = os.environ.get("FRAMES_BASELINE") or os.path.join(HERE, "baseline", "frames.json")
CURRENT = os.path.join(HERE, "frames.json")
TOKENS = os.path.join(HERE, "tokens.json")
DIGEST = os.path.join(HERE, "baseline-digest.json")   # 入版控:{"tokens_md5", "stripped_frames_md5"}

NEW_KEYS = ("phrases", "regions", "transfer", "agent", "agent_source", "agent_inferred",
            "manner", "manner_kind", "manner_value", "negation", "region_backfill")
NEW_ANAPHORA_KEYS = ("moving",)


def strip(frame):
    """剝掉新鍵的框架副本(原框架不動);回指欄也剝它的新子鍵。"""
    out = {k: v for k, v in frame.items() if k not in NEW_KEYS}
    anaphora = out.get("anaphora")
    if isinstance(anaphora, dict):
        out["anaphora"] = {k: v for k, v in anaphora.items() if k not in NEW_ANAPHORA_KEYS}
    return out


def strip_procedure(record):
    """剝框重編(summon-procedure 票 01):剝掉位置是召喚手續的框、框序照剩下的重編後的紀錄副本(原紀錄不動)。
    召喚手續框依原文順序和既有框混排,會把後面的框序往後推;剝掉再重編,既有框才能和沒有召喚手續框時的
    基準逐鍵比。剝鍵比對、下游基準(動作對象、回指)比之前都經這裡。"""
    kept = [f for f in record["frames"] if f.get("position") != POS_PROCEDURE]
    return dict(record, frames=[dict(f, order=k) for k, f in enumerate(kept)])


def _key(rec):
    return (rec["card"], rec["section"], rec["index"])


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def diff(baseline_path=BASELINE, current_path=CURRENT):
    """兩個框架檔 → 差異清單(剝框重編、剝掉新鍵後)。紀錄依 (卡號, 段落, 句序) 對齊,框依序比。"""
    base = {_key(r): strip_procedure(r) for r in _load(baseline_path)}
    cur = {_key(r): strip_procedure(r) for r in _load(current_path)}
    out = []
    for key in sorted(set(base) | set(cur)):
        if key not in cur:
            out.append(key + (None, "record", "基準有", "現在沒有"))
            continue
        if key not in base:
            out.append(key + (None, "record", "基準沒有", "現在有"))
            continue
        b_frames, c_frames = base[key]["frames"], cur[key]["frames"]
        if len(b_frames) != len(c_frames):
            out.append(key + (None, "frames", len(b_frames), len(c_frames)))
        for k, (b, c) in enumerate(zip(b_frames, c_frames)):
            b, c = strip(b), strip(c)
            for field in sorted(set(b) | set(c)):
                if b.get(field) != c.get(field):
                    out.append(key + (k, field, b.get(field), c.get(field)))
    return out


def underscore_keys(records):
    """[(卡號, 段落, 句序, 框序, 鍵)]:框架頂層以底線開頭的鍵。"""
    return [(r["card"], r["section"], r["index"], k, key)
            for r in records for k, fr in enumerate(r["frames"])
            for key in sorted(fr) if key.startswith("_")]


def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stripped_md5(records):
    """剝框重編、剝掉新鍵後全部紀錄的 md5(鍵排序、緊湊 JSON,和檔案排版無關)。"""
    stripped = [dict(r, frames=[strip(f) for f in strip_procedure(r)["frames"]]) for r in records]
    return hashlib.md5(json.dumps(stripped, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")).hexdigest()


def freeze(current_path=CURRENT, tokens_path=TOKENS, digest_path=DIGEST):
    """把現在的語料 md5 與剝鍵後 md5 寫進入版控的 digest(只在刻意改既有欄、確認差異是要的之後)。"""
    digest = {"tokens_md5": file_md5(tokens_path), "stripped_frames_md5": stripped_md5(_load(current_path))}
    with open(digest_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(digest, f, indent=2)
        f.write("\n")
    return digest


def check_digest(current_path=CURRENT, tokens_path=TOKENS, digest_path=DIGEST):
    """→ (狀態, 說明):ok / mismatch / skip(沒有 digest、沒有 tokens.json 或 frames.json、語料變了要重新凍結)。"""
    for path, what in ((digest_path, "baseline-digest.json"), (tokens_path, "tokens.json"),
                       (current_path, "frames.json")):
        if not os.path.exists(path):
            return "skip", "沒有 %s(%s)" % (what, path)
    digest = _load(digest_path)
    tokens_md5 = file_md5(tokens_path)
    if tokens_md5 != digest["tokens_md5"]:
        return "skip", ("語料變了(tokens.json md5 %s,digest 記 %s):字面欄守門這次略過;確認 frames 的變化"
                        "是語料造成的之後 python baseline_diff.py --freeze 重新凍結"
                        % (tokens_md5, digest["tokens_md5"]))
    actual = stripped_md5(_load(current_path))
    if actual != digest["stripped_frames_md5"]:
        return "mismatch", "剝鍵後 frames.json 的 md5 %s ≠ digest 記的 %s:既有欄被改了" % (
            actual, digest["stripped_frames_md5"])
    return "ok", "剝鍵後 md5 與 digest 相同(%s)" % actual


def main(argv=None):
    parser = argparse.ArgumentParser(description="剝掉第四版論元的新鍵後與基準框架檔比對")
    parser.add_argument("--baseline", default=BASELINE)
    parser.add_argument("--current", default=CURRENT)
    parser.add_argument("--limit", type=int, default=30, help="最多列幾處差異")
    parser.add_argument("--freeze", action="store_true",
                        help="把現在的剝鍵 md5 與語料 md5 寫進 baseline-digest.json")
    args = parser.parse_args(argv)
    if args.freeze:
        digest = freeze(args.current)
        print("已凍結:tokens %s、剝鍵後 frames %s → %s" % (
            digest["tokens_md5"], digest["stripped_frames_md5"], DIGEST))
        return 0
    status, message = check_digest(args.current)
    print("digest 守門:%s——%s" % (status, message))
    if not os.path.exists(args.baseline):
        print("沒有基準檔:%s(只有 digest 守門)" % args.baseline, file=sys.stderr)
        return 1 if status == "mismatch" else 0
    differences = diff(args.baseline, args.current)
    for row in differences[:args.limit]:
        print("差異:卡 %s %s/%s 框 %s 鍵 %s:基準 %r → 現在 %r" % row)
    underscored = underscore_keys(_load(args.current))
    for row in underscored[:args.limit]:
        print("底線鍵:卡 %s %s/%s 框 %s 鍵 %s" % row)
    print("剝鍵比對:差異 %d 處、底線鍵 %d 個(基準 %s)" % (
        len(differences), len(underscored), args.baseline))
    return 1 if differences or underscored or status == "mismatch" else 0


if __name__ == "__main__":
    sys.exit(main())
