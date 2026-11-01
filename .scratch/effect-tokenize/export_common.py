# -*- coding: utf-8 -*-
"""框列匯出的共用部分(named-queries 票 05 抽出;ADR-0017/0018)。

框列匯出(export_frames.py → data/action_frames.json)、下游基準與 LLM 抽驗讀的同一套:標記句日文原文的雜湊、
此卡卡面參數與它的雜湊、框架對標記句的規則、動作對象的統計,以及讀 frames.json + tokens.json 成「效果句列
(帶原文)」。算法只有一份——索引建置(script/web/webindex.py)以同一算法重算比對,改這裡就是改契約。

- text_hash(原文) → sha1 前 16 碼(同效果標記表 text_hash)。
- card_face(卡片總表的一列) → 此卡卡面參數;face_hash(卡面) → sha1 前 16 碼(webindex._face_hash 同算法)。
- owner(效果句, 框架) → 框架所屬標記句的 index:效果句只有一段時框架全屬那一句;拆開的效果句(領起句+
  子效果句)框架帶選項 n 時屬 index-●n、沒有選項時屬領起句;對不到回 None(匯出失敗)。
- Stats:動作對象判定的計數(值/理由/發動位置/比不了),匯出的「統計」區塊。
- load_sentences() → frames.json 的效果句,補上 tokens.json 的效果句原文 text_ja(兩檔同序同鍵)。
"""
from collections import Counter
import hashlib
import json
import os

import patient

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FRAMES = os.path.join(HERE, "frames.json")
TOKENS = os.path.join(HERE, "tokens.json")
CARDS = os.path.join(ROOT, "data", "cards.json")


def text_hash(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# [[動作對象]]全部類比對用的此卡卡面參數(卡片總表的欄位);索引建置以總表重算雜湊比對,
# 卡面參數變了而沒重跑分詞鏈就建置失敗(script/web/webindex.py 的 _face_hash 同算法)
FACE_FIELDS = ("type", "race", "attribute", "level", "atk", "def", "name_ja")


def card_face(card):
    """卡片總表的一列 → 此卡卡面參數。"""
    return {field: card.get(field) for field in FACE_FIELDS}


def face_hash(face):
    payload = json.dumps([face.get(field) for field in FACE_FIELDS], ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def owner(sentence, frame):
    """框架所屬標記句的 index;對不到時回 None。"""
    parts = sentence["parts"]
    if len(parts) == 1:
        return parts[0]["index"]
    if frame.get("option") is None:
        return parts[0]["index"]
    wanted = "%s-●%d" % (parts[0]["index"], frame["option"])
    return wanted if any(p["index"] == wanted for p in parts) else None


class Stats:
    """動作對象判定的計數:加進來的框架依值與理由分(框列匯出加全部匯出的動作框架)。"""

    SAMPLES = 20

    def __init__(self):
        self.frames = Counter()
        self.cards = {}
        self.reasons = Counter()
        self.reason_cards = {}
        self.unknown = Counter()
        self.launch = Counter()
        self.neither_launch = Counter()
        self.uncomparable = Counter()

    def add(self, card, verdict):
        key = verdict.mode or patient.NEITHER
        self.frames[key] += 1
        self.cards.setdefault(key, set()).add(card)
        self.reasons[key + ":" + verdict.why] += 1
        self.reason_cards.setdefault(key + ":" + verdict.why, set()).add(card)
        if verdict.why == patient.WHY_UNKNOWN:
            self.unknown[verdict.text] += 1
        if patient.is_uncomparable(verdict.why):
            self.uncomparable[verdict.text] += 1
        if verdict.launch:
            self.launch[verdict.launch] += 1
            if not verdict.mode:
                self.neither_launch[verdict.launch] += 1

    def doc(self):
        keys = (patient.SELF, patient.NONSELF, patient.NEITHER)
        top = lambda counts: dict(sorted(  # noqa: E731
            counts.items(), key=lambda kv: (-kv[1], kv[0]))[:self.SAMPLES])
        return {"框架": {k: self.frames[k] for k in keys},
                "卡": {k: len(self.cards.get(k, ())) for k in keys},
                "理由": dict(sorted(self.reasons.items())),
                "理由卡": {k: len(v) for k, v in sorted(self.reason_cards.items())},
                "發動位置": dict(sorted(self.launch.items())),
                "皆非發動位置": dict(sorted(self.neither_launch.items())),
                "表外受事者": top(self.unknown),
                "比不了字面": top(self.uncomparable),
                "比不了": sum(self.uncomparable.values())}


def print_stats(stats, label="動作對象"):
    """建置報告的動作對象段;stats 是 Stats.doc() 的結果。"""
    print(label + ":" + "、".join(
        "%s %d 框 %d 張" % (k, n, stats["卡"][k]) for k, n in stats["框架"].items()))
    for why, n in stats["理由"].items():
        print("  %s %d 框 %d 張" % (why, n, stats["理由卡"][why]))
    print("  發動位置(全部類框架):" + "、".join(
        "%s %d" % kv for kv in stats["發動位置"].items()) + ";其中皆非:" + "、".join(
        "%s %d" % kv for kv in stats["皆非發動位置"].items()))
    print("  比不了而視為可能包含 %d 框,前 %d 種:%s" % (
        stats["比不了"], len(stats["比不了字面"]), "、".join(
            "%s×%d" % kv for kv in stats["比不了字面"].items())))
    print("  表外受事者(前 %d 種):%s" % (len(stats["表外受事者"]), "、".join(
        "%s×%d" % kv for kv in stats["表外受事者"].items())))


def load_sentences():
    """frames.json 的效果句,補上 tokens.json 的效果句原文(兩檔同序同鍵)。"""
    with open(FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(TOKENS, encoding="utf-8") as f:
        texts = {(t["card"], t["section"], t["index"]): t["text_ja"] for t in json.load(f)}
    for s in sentences:
        s["text_ja"] = texts[(s["card"], s["section"], s["index"])]
    return sentences


def load_faces():
    """卡片總表 → {卡片密碼: 此卡卡面參數}。"""
    with open(CARDS, encoding="utf-8") as f:
        return {card["id"]: card_face(card) for card in json.load(f)}
