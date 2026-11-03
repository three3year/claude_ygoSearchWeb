# -*- coding: utf-8 -*-
"""下游基準(named-queries 票 01):動作對象與回指改讀論元片語之前,先把全語料每個動作框架的
現值凍結成基準,改讀之後逐框比對、列出差異的卡與前後值。

兩把尺(RULERS,CLI 的子命令名):
- patient   動作對象:每個動作框架的 {"mode": 此卡|非此卡|None, "why": 理由}(patient.judge_sentence
            逐句判,帶 data/cards.json 的卡面參數;條件位的框架也判,約束框架不在基準裡)。
- anaphora  回指欄:每個動作框架的整個 anaphora dict(含新子鍵 moving),沒有就是 None。

接縫:
- snapshot(ruler, records, faces=None) → {(卡號, 段落, 句序, 框序): 值}(frames.json 的紀錄清單)。先剝框重編
  (baseline_diff.strip_procedure,summon-procedure 票 01):召喚手續框不在基準裡,框序是剝掉它們後重編的;
  動作對象仍整句判完才剝。
- diff(base, cur, clauses=None, why_aliases=WHY_ALIASES) → [(卡號, 段落, 句序, 框序, 子句字面, 基準值, 現值)];
  一邊沒有的框記 MISSING(回指欄的 None 是正常值,要分得開)。動作對象的理由碼改名時填 WHY_ALIASES
  (舊 → 新),基準值比對前先換,基準不必重凍。
- freeze(ruler, loc) 寫 baseline/<尺>.json(gitignore,逐框的值一列一框)與 <尺>-digest.json(入版控:
  tokens.json 與 cards.json 的 md5、值的 md5);check_digest(ruler, loc)
  → (ok|mismatch|skip, 說明):語料或卡面變了就 skip 並要求重新凍結,沒變時 md5 要相同——基準檔
  不在的工作樹也有這道守門。load_baseline(ruler, loc) 讀回凍結時的 snapshot。
- Locations(frames, tokens, cards, baseline_dir, digest_dir):檔案位置,預設 DEFAULT;測試換暫存目錄。

CLI:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/downstream_baseline.py <尺> [--freeze] [--limit N]
  不帶 --freeze:印 digest 守門結果,有基準檔時再逐框比對、列差異(前 N 筆);差異非 0 或 mismatch 時 exit 1。
  --freeze:只在確認差異是要的之後(改讀後更對、或語料變了)重新凍結。
"""
import argparse
from collections import namedtuple
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patient  # noqa: E402
from baseline_diff import renumbered_without_procedure, strip_procedure  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from digest_common import changed_input, file_md5, json_md5, write_digest  # noqa: E402
from export_common import card_face  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FRAMES = os.path.join(HERE, "frames.json")
TOKENS = os.path.join(HERE, "tokens.json")
CARDS = os.path.join(ROOT, "data", "cards.json")
BASELINE_DIR = os.path.join(HERE, "baseline")

Locations = namedtuple("Locations", "frames tokens cards baseline_dir digest_dir")
DEFAULT = Locations(FRAMES, TOKENS, CARDS, BASELINE_DIR, HERE)

PATIENT, ANAPHORA = "patient", "anaphora"
RULERS = (PATIENT, ANAPHORA)
# 動作對象理由碼的對照表(舊 → 新):改讀後理由名跟著讀法變時填這裡,基準不必重凍(票 02 填)
WHY_ALIASES = {}
MISSING = "(沒有這個框)"


def frame_key(rec, frame):
    return (rec["card"], rec["section"], rec["index"], frame["order"])


def _patient_values(records, faces):
    faces = faces or {}
    out = {}
    for rec in records:
        whole_sentence_verdicts = patient.judge_sentence(rec["frames"], faces.get(rec["card"]), rec["section"])
        for before_strip, fr in renumbered_without_procedure(rec):
            if fr.get("kind") == KIND_ACTION:
                verdict = whole_sentence_verdicts[before_strip]
                out[frame_key(rec, fr)] = {"mode": verdict.mode, "why": verdict.why}
    return out


def _anaphora_values(records, faces):
    return {frame_key(rec, fr): fr.get("anaphora")
            for rec in map(strip_procedure, records) for fr in rec["frames"] if fr.get("kind") == KIND_ACTION}


_VALUES = {PATIENT: _patient_values, ANAPHORA: _anaphora_values}


def snapshot(ruler, records, faces=None):
    """frames.json 的紀錄清單(+ 卡號 → 卡面參數,動作對象用)→ {(卡號, 段落, 句序, 框序): 值}。"""
    return _VALUES[ruler](records, faces)


def _aliased(value, why_aliases):
    if isinstance(value, dict) and value.get("why") in why_aliases:
        return dict(value, why=why_aliases[value["why"]])
    return value


def diff(base, cur, clauses=None, why_aliases=None):
    """兩份 snapshot → 差異清單 [(卡號, 段落, 句序, 框序, 子句字面, 基準值, 現值)],依框鍵排序;
    clauses 是 {框鍵: 子句字面}(frame_clauses 取自現在的 frames.json),沒有時空字串。"""
    clauses = clauses or {}
    why_aliases = WHY_ALIASES if why_aliases is None else why_aliases
    out = []
    for key in sorted(set(base) | set(cur)):
        b = _aliased(base[key], why_aliases) if key in base else MISSING
        c = cur[key] if key in cur else MISSING
        if b != c:
            out.append(key + (clauses.get(key, ""), b, c))
    return out


def frame_clauses(records):
    """{框鍵: 子句字面}——差異清單的原文欄(框鍵是剝框重編後的,和 snapshot 同)。"""
    return {frame_key(rec, fr): fr.get("clause") or "" for rec in map(strip_procedure, records)
            for fr in rec["frames"]}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_faces(cards_path):
    """data/cards.json → {卡號: 卡面參數}(動作對象全部類比對用;同匯出)。"""
    return {card["id"]: card_face(card) for card in _load(cards_path)}


def load_records(loc=DEFAULT):
    return _load(loc.frames)


def current_snapshot(ruler, loc=DEFAULT, records=None):
    """現在的 frames.json(與卡面)算出的 snapshot;records 已讀好時傳進來省一次讀檔。"""
    records = load_records(loc) if records is None else records
    faces = load_faces(loc.cards) if ruler == PATIENT else None
    return snapshot(ruler, records, faces)


def _rows(snap):
    return [list(key) + [snap[key]] for key in sorted(snap)]


def values_md5(snap):
    """snapshot 的 md5(鍵排序、緊湊 JSON,和檔案排版無關)。"""
    return json_md5(_rows(snap))


def baseline_path(ruler, loc=DEFAULT):
    return os.path.join(loc.baseline_dir, ruler + ".json")


def digest_path(ruler, loc=DEFAULT):
    return os.path.join(loc.digest_dir, ruler + "-digest.json")


def write_baseline(ruler, snap, loc=DEFAULT):
    """逐框的值寫成 baseline/<尺>.json:一列一框 [卡號, 段落, 句序, 框序, 值],diff 讀得出改了哪框。"""
    os.makedirs(loc.baseline_dir, exist_ok=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    with open(baseline_path(ruler, loc), "w", encoding="utf-8", newline="\n") as f:
        f.write("[\n" + ",\n".join(dump(row) for row in _rows(snap)) + "\n]\n")


def load_baseline(ruler, loc=DEFAULT):
    """baseline/<尺>.json → snapshot({框鍵: 值})。"""
    return {tuple(row[:4]): row[4] for row in _load(baseline_path(ruler, loc))}


def _inputs(ruler, loc):
    """這把尺的 digest 要記哪些輸入檔的 md5:語料一定記,動作對象還看卡面。"""
    inputs = [("tokens_md5", loc.tokens)]
    if ruler == PATIENT:
        inputs.append(("cards_md5", loc.cards))
    return inputs


def freeze(ruler, loc=DEFAULT):
    """現值凍結成基準:逐框的值寫 baseline/<尺>.json,輸入檔與值的 md5 寫 <尺>-digest.json。"""
    digest = {name: file_md5(path) for name, path in _inputs(ruler, loc)}
    snap = current_snapshot(ruler, loc)
    write_baseline(ruler, snap, loc)
    digest["values_md5"] = values_md5(snap)
    write_digest(digest_path(ruler, loc), digest)
    return digest


def check_digest(ruler, loc=DEFAULT, records=None):
    """→ (ok|mismatch|skip, 說明)。skip:沒有 digest 或輸入檔,或語料/卡面變了(要重新凍結);
    mismatch:輸入沒變而值變了——改讀動到了判定(或回指欄)。"""
    needed = [(digest_path(ruler, loc), ruler + "-digest.json")]
    needed += [(path, os.path.basename(path)) for _, path in _inputs(ruler, loc)]
    needed.append((loc.frames, "frames.json"))
    for path, what in needed:
        if not os.path.exists(path):
            return "skip", "沒有 %s(%s)" % (what, path)
    digest = _load(digest_path(ruler, loc))
    changed = changed_input(_inputs(ruler, loc), digest)
    if changed:
        name, path, actual, frozen = changed
        return "skip", ("%s 變了(%s md5 %s,digest 記 %s):%s 尺這次略過;確認變化是輸入造成的之後 "
                        "python downstream_baseline.py %s --freeze 重新凍結"
                        % (os.path.basename(path), name, actual, frozen, ruler, ruler))
    actual, expected = values_md5(current_snapshot(ruler, loc, records)), digest["values_md5"]
    if actual != expected:
        return "mismatch", "逐框值的 md5 %s ≠ digest 記的 %s:%s 尺的值被改了" % (actual, expected, ruler)
    return "ok", "逐框值的 md5 與 digest 相同(%s)" % actual


def main(argv=None, loc=DEFAULT):
    parser = argparse.ArgumentParser(description="下游基準:動作對象判定 / 回指欄的凍結與比對")
    parser.add_argument("ruler", choices=RULERS)
    parser.add_argument("--freeze", action="store_true", help="把現值凍結成基準(確認差異是要的之後)")
    parser.add_argument("--limit", type=int, default=30, help="最多列幾處差異")
    args = parser.parse_args(argv)
    if args.freeze:
        digest = freeze(args.ruler, loc)
        print("已凍結 %s:%s → %s" % (args.ruler, "、".join("%s %s" % kv for kv in digest.items()),
                                      digest_path(args.ruler, loc)))
        return 0
    records = load_records(loc) if os.path.exists(loc.frames) else None
    status, message = check_digest(args.ruler, loc, records)
    print("digest 守門(%s):%s——%s" % (args.ruler, status, message))
    if records is None:
        return 1 if status == "mismatch" else 0
    if not os.path.exists(baseline_path(args.ruler, loc)):
        print("沒有基準檔:%s(只有 digest 守門;worktree_bootstrap.py 會從主 repo 複製)"
              % baseline_path(args.ruler, loc), file=sys.stderr)
        return 1 if status == "mismatch" else 0
    differences = diff(load_baseline(args.ruler, loc), current_snapshot(args.ruler, loc, records),
                       frame_clauses(records))
    for row in differences[:args.limit]:
        print("差異:卡 %s %s/%s 框 %s「%s」:基準 %r → 現在 %r" % row)
    print("逐框比對(%s):差異 %d 處(基準 %s)" % (args.ruler, len(differences), baseline_path(args.ruler, loc)))
    return 1 if differences or status == "mismatch" else 0


if __name__ == "__main__":
    sys.exit(main())
