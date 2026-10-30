# -*- coding: utf-8 -*-
"""類別匯出(.scratch/category-search 票 01,ADR-0017):分詞鏈 → 網站搜尋的類別檔。

接在框架類別(categories.py)之後:讀效果句與它的框架(frames.json)、效果句原文
(tokens.json)、框架類別(frame_categories.json)與類別樹,把每個動作框架的葉落到它所屬
的**標記句**上,寫出 data/action_categories.json(入版控;網站索引建置只讀這份檔,
不呼叫分詞鏈)。

匯出的單位是標記句,鍵同效果標記表(卡片密碼、段落、index;● 子效果句是自己的
index)。框架對標記句:效果句只有一段時框架全屬那一句;拆開的效果句(領起句+子效果
句),框架帶選項 n 時屬 index-●n 那一句、沒有選項時屬領起句。每個動作框架都要剛好對到
一句,框架類別也要與框架一一對上,否則匯出失敗、不寫檔。

每句記效果位與代價位的葉(各自去重、依樹序;條件位與未歸的框架不帶葉,約束框架不在
本檔)與那一句日文原文的雜湊(sha1 前 16 碼,同效果標記表 text_hash 的算法);索引建置
以標記表的原文重算比對,對不上就建置失敗。另帶類別樹(葉名清單與巢狀節點)當網站值域
的類別部分。同一份輸入兩次匯出逐位元組相同。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/export_categories.py
"""
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import categories  # noqa: E402
import patient  # noqa: E402
from constraints import KIND_ACTION  # noqa: E402
from frames import POS_COST, POS_EFFECT  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOKENS = os.path.join(HERE, "tokens.json")
CARDS = os.path.join(ROOT, "data", "cards.json")
OUT = os.path.join(ROOT, "data", "action_categories.json")

GROUPS = {POS_EFFECT: "effect", POS_COST: "cost"}
# [[動作對象]]:每組再分此卡葉與非此卡葉(皆非的框架只在原本那一組)
MODE_SUFFIX = {patient.SELF: "_self", patient.NONSELF: "_nonself"}
ROW_GROUPS = ("effect", "cost", "effect_self", "effect_nonself", "cost_self", "cost_nonself")
SUB_INDEX = re.compile(r"^(.+)-●(\d+)$")
# 網址以 › 連寫節點路徑(category-search spec「網址 hash」),節點名不能含它
PATH_SEP = "›"

DOC = ("動作類別匯出檔(.scratch/category-search,ADR-0017):由 .scratch/effect-tokenize/"
       "export_categories.py 產生,不要手改。「葉」是類別樹的葉名(樹序,索引以序號引用);"
       "「樹」是巢狀節點 [名, 葉號或 -1, 子節點](節點同時是葉與內部節點時是詞元節點帶預設葉);"
       "「句」每列一句新格式新卡的標記句:卡片密碼、段落、index、日文原文雜湊、效果位葉、"
       "代價位葉,以及[[動作對象]]的效果位此卡葉、效果位非此卡葉、代價位此卡葉、代價位非此卡葉"
       "(沒有就省略)。「統計」是動作對象判定的框架數與卡數(建置報告照登);「卡面」每列一張卡"
       "的此卡卡面參數雜湊(索引建置以卡片總表重算比對)。")


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


def tree_rows(tree):
    """類別樹 → (葉名清單, 巢狀節點 [名, 葉號或 -1, 子節點])。"""
    def row(node):
        leaf = -1 if node["leaf"] is None else node["leaf"]
        return [node["name"], leaf, [row(child) for child in node["children"]]]
    return [leaf.name for leaf in tree.leaves], [row(n) for n in categories.tree_nodes(tree)]


def tree_problems(nodes):
    found = []

    def walk(node):
        if PATH_SEP in node[0]:
            found.append("節點名含網址路徑分隔符 %s:%s" % (PATH_SEP, node[0]))
        for child in node[2]:
            walk(child)
    for node in nodes:
        walk(node)
    return found


def export(sentences, records, tree, faces=None):
    """效果句(frames.json 的列,多帶效果句原文 text_ja)+ 框架類別列 + 類別樹(+ 卡片密碼
    → 此卡卡面參數)→ (匯出文件, 問題清單);問題清單非空即匯出失敗。"""
    faces = faces or {}
    by_frame = {(r["card"], r["section"], r["index"], r["order"]): r for r in records}
    seen = set()
    problems = []
    order = tree.leaf_order
    out = []
    stats = Stats()
    for s in sentences:
        rows = {}
        for part in s["parts"]:
            rows[part["index"]] = dict(
                {"card": s["card"], "section": s["section"], "index": part["index"],
                 "hash": text_hash(s["text_ja"][part["start"]:part["end"]])},
                **{group: set() for group in ROW_GROUPS})
        verdicts = patient.judge_sentence(s["frames"], faces.get(s["card"]))
        for fr, verdict in zip(s["frames"], verdicts):
            if fr["kind"] != KIND_ACTION:
                continue
            key = (s["card"], s["section"], s["index"], fr["order"])
            record = by_frame.get(key)
            if record is None:
                problems.append("框架沒有框架類別:%s" % (key,))
                continue
            seen.add(key)
            index = owner(s, fr)
            if index is None:
                problems.append("框架對不到標記句(選項 %s):%s" % (fr.get("option"), key))
                continue
            group = GROUPS.get(fr["position"])
            if group and record["status"] == categories.STATUS_PLACED:
                rows[index][group].update(record["leaves"])
                if verdict.mode:
                    rows[index][group + MODE_SUFFIX[verdict.mode]].update(record["leaves"])
                stats.add(s["card"], verdict)
        for row in rows.values():
            for group in ROW_GROUPS:
                leaves = sorted(row[group], key=order.__getitem__)
                if leaves:
                    row[group] = leaves
                else:
                    del row[group]
            out.append(row)
    for key in sorted(set(by_frame) - seen, key=str):
        problems.append("框架類別沒有對應的框架:%s" % (key,))
    leaves, nodes = tree_rows(tree)
    problems.extend(tree_problems(nodes))
    covered = sorted({s["card"] for s in sentences} & set(faces))
    face_rows = [[card, face_hash(faces[card])] for card in covered]
    return {"說明": DOC, "葉": leaves, "樹": nodes, "統計": stats.doc(), "卡面": face_rows,
            "句": out}, problems


class Stats:
    """動作對象判定的計數:帶葉的效果位/代價位框架,依值與理由分。"""

    SAMPLES = 20

    def __init__(self):
        self.frames = {}
        self.cards = {}
        self.reasons = {}
        self.unknown = {}
        self.launch = {}

    def add(self, card, verdict):
        key = verdict.mode or "皆非"
        why = key + ":" + verdict.why
        self.frames[key] = self.frames.get(key, 0) + 1
        self.cards.setdefault(key, set()).add(card)
        self.reasons[why] = self.reasons.get(why, 0) + 1
        if verdict.why == patient.WHY_UNKNOWN:
            self.unknown[verdict.text] = self.unknown.get(verdict.text, 0) + 1
        if verdict.launch:
            self.launch[verdict.launch] = self.launch.get(verdict.launch, 0) + 1

    def doc(self):
        keys = (patient.SELF, patient.NONSELF, "皆非")
        top = sorted(self.unknown.items(), key=lambda kv: (-kv[1], kv[0]))[:self.SAMPLES]
        return {"框架": {k: self.frames.get(k, 0) for k in keys},
                "卡": {k: len(self.cards.get(k, ())) for k in keys},
                "理由": dict(sorted(self.reasons.items())),
                "發動位置": dict(sorted(self.launch.items())),
                "表外受事者": dict(top)}


def serialize(doc):
    """一句一行、樹一行:入版控的檔要 diff 讀得出改了什麼。"""
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    return ("{\n" + '"說明":' + dump(doc["說明"]) + ",\n"
            + '"葉":' + dump(doc["葉"]) + ",\n"
            + '"樹":' + dump(doc["樹"]) + ",\n"
            + '"統計":' + dump(doc["統計"]) + ",\n"
            + '"卡面":[\n' + ",\n".join(dump(r) for r in doc["卡面"]) + "\n],\n"
            + '"句":[\n' + ",\n".join(dump(r) for r in doc["句"]) + "\n]\n}\n")


def load_sentences():
    """frames.json 的效果句,補上 tokens.json 的效果句原文(兩檔同序同鍵)。"""
    with open(categories.FRAMES, encoding="utf-8") as f:
        sentences = json.load(f)
    with open(TOKENS, encoding="utf-8") as f:
        texts = {(t["card"], t["section"], t["index"]): t["text_ja"] for t in json.load(f)}
    for s in sentences:
        s["text_ja"] = texts[(s["card"], s["section"], s["index"])]
    return sentences


def main():
    try:
        tree = categories.load_tree()
    except categories.TreeError as e:
        print(e, file=sys.stderr)
        return 1
    with open(categories.OUT, encoding="utf-8") as f:
        records = json.load(f)
    with open(CARDS, encoding="utf-8") as f:
        faces = {card["id"]: card_face(card) for card in json.load(f)}
    doc, problems = export(load_sentences(), records, tree, faces)
    if problems:
        print("**匯出失敗**,%d 個問題(前 20 筆):" % len(problems), file=sys.stderr)
        for p in problems[:20]:
            print("  " + p, file=sys.stderr)
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize(doc))
    rows = doc["句"]
    print("標記句 %d(卡 %d 張);帶效果位葉 %d、帶代價位葉 %d;類別樹葉 %d;已寫出 %s" % (
        len(rows), len({r["card"] for r in rows}), sum("effect" in r for r in rows),
        sum("cost" in r for r in rows), len(doc["葉"]), OUT))
    stats = doc["統計"]
    print("動作對象(帶葉的效果位/代價位框架):" + "、".join(
        "%s %d 框 %d 張" % (k, n, stats["卡"][k]) for k, n in stats["框架"].items()))
    for why, n in stats["理由"].items():
        print("  %s %d" % (why, n))
    print("  發動位置(全部類框架):" + "、".join(
        "%s %d" % kv for kv in stats["發動位置"].items()))
    print("  表外受事者(前 %d 種):%s" % (len(stats["表外受事者"]), "、".join(
        "%s×%d" % kv for kv in stats["表外受事者"].items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
