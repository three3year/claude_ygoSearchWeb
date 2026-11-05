# -*- coding: utf-8 -*-
"""原型(target-card 規格調查,2026-11-04):重跑框架抽取,記下回指的先行框索引,並把回指現成解法套到目的片語。

- 受事者回指:anaphora.resolve 寫的內部鍵 _anaphora_targets(目標框架清單)在 after_anaphora 結尾被 pop;這裡包住
  anaphora.resolve,在它之後、pop 之前把目標框架換成「同效果句框架清單裡的序」(= frames.json 的 order)。
- 目的片語回指(原型):目的片語第一段是指示詞(field_reference(ctx, frame, "goal") 是 Reference)時,做一個
  對象欄 = 目的字面、片語 object = 目的片語、無態的代理框架,跑 resolve 的同一套找法(対象/事件/欄位 → 字面)。
- 也重檢:重跑的 anaphora 欄與本機 frames.json 是否相同(frames.json 是否跟得上程式)。

輸出:results/anaphora_targets.json({"card|section|index": {order: {...}}})與 results/anaphora_targets.txt(摘要)。
用法:python -X utf8 .scratch/target-card/tools/anaphora_targets.py
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ET = os.path.join(ROOT, ".scratch", "effect-tokenize")
sys.path.insert(0, ET)
import anaphora  # noqa: E402
import frames  # noqa: E402
from referent import clean  # noqa: E402

RESULTS = os.path.join(HERE, "results")
_original = anaphora.resolve


def _index(frames_, targets):
    out = []
    for t in targets:
        k = next((i for i, f in enumerate(frames_) if f is t), None)
        out.append(k)
    return out


def _resolve_goal(ctx, tokens, frames_, phrase_list):
    actions = [f for f in frames_ if f["kind"] == "動作"]
    segmented = {p: anaphora._segments(ctx, p.text) for p in phrase_list}
    for k, frame in enumerate(actions):
        goal_phrase = (frame.get("phrases") or {}).get("goal")
        if not frame.get("goal") or not goal_phrase:
            continue
        ref = anaphora.field_reference(ctx, frame, "goal")
        if ref is None:
            continue
        if ref == anaphora.MODIFIER:
            frame["proto_goal"] = {"modifier": True}
            continue
        proxy = {key: v for key, v in frame.items() if key not in ("subject", "topic", "voice", "anaphora")}
        proxy["object"] = frame["goal"]
        proxy["phrases"] = {"object": goal_phrase}
        option = frame.get("option")
        start = (frame["sentence"], frame["span"][0])
        earlier = [f for f in actions[:k] if anaphora._in_scope(option, f.get("option"))
                   and (f["sentence"], f["span"][0]) < start]
        before = anaphora._phrases_before(phrase_list, proxy, option)
        if ref.kind == anaphora.KIND_TARGETED:
            found = anaphora._targeted(ctx, ref, earlier)
        elif ref.kind == anaphora.KIND_EVENT:
            found = anaphora._event_target(ctx, tokens, ref, earlier, before)
        else:
            found = anaphora._best(ref, list(anaphora._field_candidates(ctx, earlier)),
                                   list(anaphora._phrase_candidates(ctx, before, segmented)))
        if found:
            targets = found.pop("_targets", [])
            frame["proto_goal"] = dict(found, targets=_index(frames_, targets), kind=ref.kind)
        else:
            frame["proto_goal"] = {"blank": True, "kind": ref.kind}


def _patched(ctx, tokens, frames_, phrase_list):
    _original(ctx, tokens, frames_, phrase_list)
    for fr in frames_:
        if "_anaphora_targets" in fr:
            fr["proto_targets"] = _index(frames_, fr["_anaphora_targets"])
    _resolve_goal(ctx, tokens, frames_, phrase_list)


def main():
    anaphora.resolve = _patched
    extractor = frames.default_extractor()
    with open(frames.TOKENS, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(frames.CARDS, encoding="utf-8") as f:
        card_type = {c["id"]: frames.card_type_of(c["type"]) for c in json.load(f)}
    with open(frames.OUT, encoding="utf-8") as f:
        stored = {(s["card"], s["section"], s["index"]): s["frames"] for s in json.load(f)}
    out = {}
    mismatch = []
    t0 = time.time()
    for n, s in enumerate(sentences):
        got = extractor.frames_of_tokens(s["tokens"], text=s["text_ja"], extra=s["kind"] == "效果外文本",
                                         card_type=card_type.get(s["card"]))
        key = (s["card"], s["section"], s["index"])
        old = stored.get(key) or []
        if len(old) != len(got):
            mismatch.append((key, "框數 %d→%d" % (len(old), len(got))))
        rec = {}
        for k, fr in enumerate(got):
            if k < len(old) and (old[k].get("anaphora") or {}).get("text") != (fr.get("anaphora") or {}).get("text"):
                mismatch.append((key, "order %d 回指 %r→%r" % (k, (old[k].get("anaphora") or {}).get("text"),
                                                               (fr.get("anaphora") or {}).get("text"))))
            item = {}
            if "proto_targets" in fr:
                item["targets"] = fr["proto_targets"]
                item["via"] = fr["anaphora"]["via"] if fr.get("anaphora") else None
            if "proto_goal" in fr:
                item["goal"] = fr["proto_goal"]
            if item:
                rec[k] = item
        if rec:
            out["%s|%s|%s" % key] = rec
        if n % 2000 == 0:
            print("%d/%d %.0fs" % (n, len(sentences), time.time() - t0), flush=True)
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "anaphora_targets.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    lines = ["重跑框架抽取 %d 句,%.0f 秒" % (len(sentences), time.time() - t0),
             "與本機 frames.json 的差異 %d 筆(框數或回指字面)" % len(mismatch)]
    lines += ["  %s %s" % m for m in mismatch[:30]]
    with open(os.path.join(RESULTS, "anaphora_targets.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
