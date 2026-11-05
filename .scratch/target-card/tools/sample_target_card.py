# -*- coding: utf-8 -*-
"""針對卡片原型(記憶體內實算,不改 repo 程式):給卡 C,逐動作框判受事者/目的片語的段是否滿足。

口徑(本原型自定,回報時說明):
- 片語組:受事者(patient.patient)——自己指名此卡優先;有 frame["anaphora"] 時改讀回指目標字面重切的段(via 事件 → 比不了);
  指示詞判 REFERENCE 卻沒有回指欄 → 比不了;目的片語(frame goal)——段首指示詞 → 比不了(回指線尚未解目的片語)。
- 每組只取卡類段(head_class == CARD);卡類段為空而尾段是屬性 → 取屬性主人的卡類段。
  區域段(墓地、手札、自分フィールド:片語把它當卡類中心詞)不算——否則目的片語的區域會讓每張卡空泛地過。
  「ドラゴン族・光属性・レベル7モンスター」片語切成 屬性段 + 卡段:屬性段的種族/屬性修飾語併進下一個卡段(MERGE_ATTR)。
  目的片語在 とする/なる/同じにする 不算(陷阱怪獸的「通常モンスター(…)」是身分,不是被作用的卡)。
- 段判定:このカード 段 → 寫了條件,C 正是框所屬卡才過;其餘段 _segment_blocker(seg, face) 為 None 即過。
  「寫了條件」= 比得了的非卡種條件數 > 0(種族/屬性/字段卡名/子類型(_subtype_block 非 None)/數值(_numeric_block 非 None))。
- 預設模式:沒有任何可比段的框照過(空泛);有比不了的組照過(標部分未比對);否則任一段過即過。
- 只看有寫條件的:任一段 過 且 寫了條件 > 0。
- 擋下:有可比段、沒有比不了的組、所有段都被擋;其中「有寫條件」= 任一段寫了非卡種條件(否則是只被卡種擋)。
"""
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ET = os.path.join(ROOT, ".scratch", "effect-tokenize")
sys.path.insert(0, ET)

import patient as P  # noqa: E402
from referent import VIA_EVENT  # noqa: E402
from constraints import KIND_ACTION, POSITIONS  # noqa: E402
from export_common import card_face  # noqa: E402


GOAL_ROLE_ACTIONS = ("とする", "なる", "同じにする")   # 目的是身分/比較基準,不是被作用的卡(陷阱怪獸的 通常モンスター(…))
MERGE_ATTR = True                                     # 「ドラゴン族・光属性・レベル7モンスター」切出的屬性段併進下一個卡段


def is_zone_seg(seg):
    """段本身是區域(墓地、自分フィールド、手札):中心詞不是卡種詞/カード/トークン/「卡名」而段帶區域。"""
    head = seg["head"] or ""
    return bool(seg["zones"]) and P._head_face(head)[0] is None and head not in P.ANY_KIND_HEADS \
        and not (head.startswith("「") and head.endswith("」"))


def merge_attr(segs):
    if not MERGE_ATTR:
        return list(segs)
    out, carry = [], []
    for s in segs:
        if (s["head_kind"] == "屬性" and s["head"] in ("属性", "種族") and s["modifiers"]
                and all(m["kind"] in (P.MOD_RACE, P.MOD_ATTRIBUTE) for m in s["modifiers"])):
            carry += s["modifiers"]
            continue
        if carry and P.head_class(s) == P.CARD:
            s = dict(s, modifiers=carry + list(s["modifiers"]))
        carry = []
        out.append(s)
    return out


def card_segs(segs):
    segs = merge_attr(segs)
    cards = [s for s in segs if P.head_class(s) == P.CARD]
    if not cards and segs and P.head_class(segs[-1]) == P.VALUE:
        k = P._attribute_run(segs)
        if k is not None:
            owner = tuple(segs[:k]) + P._owner(segs[k])
            cards = [s for s in owner if P.head_class(s) == P.CARD]
    return [s for s in cards if not is_zone_seg(s)]


def groups(frame):
    """→ [(來源, 段清單 或 None=比不了)];來源 direct/anaphora/goal。"""
    out = []
    _, segs, _ = P.patient(frame)
    if segs:
        named = P.self_rule(segs)
        if frame.get("anaphora") and not named:
            t = frame["anaphora"]
            if t.get("via") == VIA_EVENT:
                out.append(("anaphora", None))
            else:
                out.append(("anaphora", card_segs(P.segments_of(t.get("text")))))
        else:
            role = None if named else P._demonstrative_role(segs)
            out.append(("direct", None if role == P.REFERENCE else card_segs(segs)))
    goal = P._segments(frame, "goal") if frame.get("goal") else ()
    if goal and frame.get("action") not in GOAL_ROLE_ACTIONS:
        out.append(("goal", None if goal[0]["demonstrative"] else card_segs(goal)))
    return [(src, g) for src, g in out if g is None or g]


def written_conditions(seg, face):
    """比得了的非卡種條件數(與 _segment_blocker 同一套拆法)。"""
    kind, prefix, _ = P._head_face(seg["head"])
    n, subtypes, numerics = 0, [], []
    mods = seg["modifiers"]
    for i, mod in enumerate(mods):
        text, mk = P._unelide(mod["text"]), mod["kind"]
        if mk == P.MOD_SUBTYPE and i + 1 < len(mods) and mods[i + 1]["text"].startswith(P.MATERIAL):
            continue
        if mk == P.MOD_RACE and text in P._RACE_BITS:
            n += 1
        elif mk == P.MOD_ATTRIBUTE and text[:1] in P._ATTR_BITS:
            n += 1
        elif mk == P.MOD_ARCHETYPE:
            n += 1
        elif mk == P.MOD_SUBTYPE:
            subtypes.append(text)
        elif mk == P.MOD_NUMERIC:
            numerics.append(mod)
    if prefix:
        subtypes += prefix.split("・")
    head = seg["head"] or ""
    if head.startswith("「") and head.endswith("」"):
        n += 1
    if subtypes and kind and P._subtype_block(kind, subtypes, face) is not None:
        n += 1
    n += sum(1 for m in numerics if P._numeric_block(m, face) is not None)
    return n


def seg_eval(seg, face, is_self):
    """→ (過, 寫了條件數, 有比不了, 擋下理由)。"""
    if P._is_this_card(seg):
        return is_self, 1, False, None if is_self else "このカード"
    blocker, unc = P._segment_blocker(seg, face)
    return blocker is None, written_conditions(seg, face), unc, blocker


def judge(frame_groups, face, is_self):
    """一個框 → dict(default, strict, partial_d, partial_s, blocked, blocked_written, sources_s, sources_d, why)。"""
    evals = []          # (src, 過, written, unc, blocker)
    none_group = [src for src, g in frame_groups if g is None]
    for src, g in frame_groups:
        if g is None:
            continue
        for seg in g:
            ok, w, unc, b = seg_eval(seg, face, is_self)
            evals.append((src, ok, w, unc, b))
    passing = [e for e in evals if e[1]]
    strict = [e for e in passing if e[2] > 0]
    empty = not evals and not none_group
    default = empty or bool(none_group) or bool(passing)
    blocked = bool(evals) and not none_group and not passing
    return {
        "empty": empty,
        "default": default,
        "strict": bool(strict),
        "partial_d": default and not empty and (bool(none_group) or any(e[3] for e in passing)),
        "partial_s": bool(strict) and (all(e[3] for e in strict) or bool(none_group)),
        "blocked": blocked,
        "blocked_written": blocked and any(e[2] > 0 for e in evals),
        "blocked_cond": blocked and any(e[2] > 0 and e[4] != "このカード" for e in evals),
        "sources_s": {e[0] for e in strict},
        "why": [e[4] for e in evals if not e[1]],
    }


def load():
    with open(os.path.join(ET, "frames.json"), encoding="utf-8") as f:
        sentences = json.load(f)
    with open(os.path.join(ROOT, "data", "cards.json"), encoding="utf-8") as f:
        cards = {c["id"]: c for c in json.load(f)}
    table = []      # (card, position, groups, frame)
    for s in sentences:
        for fr in s["frames"]:
            if fr.get("kind") == KIND_ACTION:
                table.append((s["card"], fr["position"], groups(fr), fr, s))
    return sentences, cards, table


def evaluate(cid, cards, table):
    face = card_face(cards[cid])
    rows = []
    for card, pos, gs, fr, s in table:
        rows.append((card, pos, judge(gs, face, card == cid), fr, s))
    return rows


def summarize(rows):
    def fc(pred):
        sel = [r for r in rows if pred(r)]
        return len(sel), len({r[0] for r in sel})
    out = collections.OrderedDict()
    out["預設模式(含空泛)"] = fc(lambda r: r[2]["default"])
    out["預設模式:有可比段或比不了組才算"] = fc(lambda r: r[2]["default"] and not r[2]["empty"])
    out["預設:部分條件未比對"] = fc(lambda r: r[2]["partial_d"])
    out["只看有寫條件的"] = fc(lambda r: r[2]["strict"])
    out["只看有寫:直接比(受事者或目的)"] = fc(lambda r: r[2]["strict"] and r[2]["sources_s"] & {"direct", "goal"})
    out["只看有寫:只靠追回指多出"] = fc(lambda r: r[2]["strict"] and r[2]["sources_s"] == {"anaphora"})
    out["只看有寫:目的片語才中"] = fc(lambda r: r[2]["strict"] and r[2]["sources_s"] == {"goal"})
    out["只看有寫:部分條件未比對"] = fc(lambda r: r[2]["strict"] and r[2]["partial_s"])
    out["擋下(全部段被擋)"] = fc(lambda r: r[2]["blocked"])
    out["擋下且有寫非卡種條件"] = fc(lambda r: r[2]["blocked_written"])
    out["擋下:被非このカード的寫出條件擋"] = fc(lambda r: r[2]["blocked_cond"])
    return out


def by_position(rows, pred):
    out = {}
    for pos in POSITIONS:
        sel = [r for r in rows if r[1] == pos and pred(r)]
        out[pos] = (len(sel), len({r[0] for r in sel}))
    return out


def fmt(pair):
    return "%d 框/%d 張" % pair


def report_card(cid, cards, table, lines, detail=False):
    rows = evaluate(cid, cards, table)
    c = cards[cid]
    lines.append("== %s %s(%s)type=%d" % (cid, c["name_ja"], c["name_zh"], c["type"]))
    for k, v in summarize(rows).items():
        lines.append("  %-28s %s" % (k, fmt(v)))
    if detail:
        preds = [("預設(含空泛)", lambda r: r[2]["default"]),
                 ("預設(非空泛)", lambda r: r[2]["default"] and not r[2]["empty"]),
                 ("預設:部分未比對", lambda r: r[2]["partial_d"]),
                 ("只看有寫", lambda r: r[2]["strict"]),
                 ("只看有寫:直接", lambda r: r[2]["strict"] and r[2]["sources_s"] & {"direct", "goal"}),
                 ("只看有寫:追回指多出", lambda r: r[2]["strict"] and r[2]["sources_s"] == {"anaphora"}),
                 ("只看有寫:部分未比對", lambda r: r[2]["strict"] and r[2]["partial_s"]),
                 ("擋下有寫", lambda r: r[2]["blocked_written"]),
                 ("擋下:非このカード", lambda r: r[2]["blocked_cond"])]
        lines.append("  -- 依位置 " + " / ".join(POSITIONS))
        for name, pred in preds:
            bp = by_position(rows, pred)
            lines.append("  %-20s %s" % (name, " | ".join(fmt(bp[p]) for p in POSITIONS)))
    return rows


def main():
    t0 = time.time()
    _, cards, table = load()
    lines = ["frames 動作框 %d(載入 %.0fs)" % (len(table), time.time() - t0)]
    ids = [int(a) for a in sys.argv[1:]] or [46986414]
    for i, cid in enumerate(ids):
        report_card(cid, cards, table, lines, detail=(i == 0 or len(ids) <= 3))
    lines.append("耗時 %.0fs" % (time.time() - t0))
    text = "\n".join(lines)
    print(text)
    with open(os.path.join(HERE, "results", "sample_target_card.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


if __name__ == "__main__":
    main()
