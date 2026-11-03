"""原型(不改 repo):召喚條件手續步驟的錨點另出動作框架、位置 召喚手續,寫到 scratchpad 的 frames 檔。
用法:python -X utf8 proto_frames.py <out.json> [--wide]   --wide 白名單另含 発動、選ぶ"""
import json
import os
import sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "effect-tokenize")
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")
import constraints  # noqa: E402

POS_PROC = "召喚手續"
constraints.POSITIONS = constraints.POSITIONS + (POS_PROC,)
import frames  # noqa: E402
import enrich  # noqa: E402
import agent  # noqa: E402

WHITE = {"リリース", "除外", "重ねる", "送る", "戻す", "捨てる", "取り除く", "見せる", "払う"}
if "--wide" in sys.argv:
    WHITE |= {"発動", "選ぶ"}
PROC_ENDS = set()
SEEN = []

orig_sc = constraints.ConstraintFinder.summon_conditions


def summon_conditions(self, tokens, sentence, anchors, prefixes):
    found = orig_sc(self, tokens, sentence, anchors, prefixes)
    for fr in found:
        lo, hi = fr["span"]
        carve = []
        for a in anchors:
            if lo <= a["verb_at"] < hi and a["head"] < hi and not (a["action"].endswith("召喚") and a["nominalizer"] is None):
                name = self._action_name(tokens, a)
                SEEN.append(name)
                if name in WHITE or a["action"] in WHITE:
                    carve.append(a["verb_at"])
                    PROC_ENDS.add(a["end"])
        if not carve:
            continue
        new = []
        for (clo, chi) in self.consumed:
            if clo == lo and chi == hi:
                cuts = sorted(carve)
                start = clo
                for v in cuts:
                    new.append((start, v))
                    start = v + 1
                new.append((start, chi))
            else:
                new.append((clo, chi))
        self.consumed[:] = new
    return found


constraints.ConstraintFinder.summon_conditions = summon_conditions

orig_before = enrich.before_anaphora


def before_anaphora(ctx, tokens, frames_):
    for fr in frames_:
        if fr.get("kind") == constraints.KIND_ACTION and fr["span"][1] in PROC_ENDS:
            fr["position"] = POS_PROC
    PROC_ENDS.clear()
    return orig_before(ctx, tokens, frames_)


enrich.before_anaphora = before_anaphora
agent.POSITIONS_DEFAULT = agent.POSITIONS_DEFAULT + (POS_PROC,)


def main():
    out_path = sys.argv[1]
    extractor = frames.default_extractor()
    with open(frames.TOKENS, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(frames.CARDS, encoding="utf-8") as f:
        card_type = {c["id"]: frames.card_type_of(c["type"]) for c in json.load(f)}
    out = []
    for s in sentences:
        PROC_ENDS.clear()
        frs = extractor.frames_of_tokens(s["tokens"], text=s["text_ja"], extra=s["kind"] == "效果外文本",
                                         card_type=card_type.get(s["card"]))
        for k, fr in enumerate(frs):
            fr["order"] = k
        out.append({"card": s["card"], "section": s["section"], "index": s["index"], "stratum": s["stratum"],
                    "parts": s["parts"], "frames": frs})
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    from collections import Counter
    print("非召喚錨點名", Counter(SEEN).most_common())
    n = sum(1 for r in out for fr in r["frames"] if fr.get("position") == POS_PROC)
    print("召喚手續框", n, "張", len({r["card"] for r in out for fr in r["frames"] if fr.get("position") == POS_PROC}))
    print(Counter(fr["action"] for r in out for fr in r["frames"] if fr.get("position") == POS_PROC).most_common())


if __name__ == "__main__":
    main()
