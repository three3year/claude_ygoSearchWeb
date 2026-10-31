# -*- coding: utf-8 -*-
"""框列匯出(named-queries 票 05,ADR-0018):分詞鏈 → 網站搜尋的框架檔 data/action_frames.json。

接在框架抽取之後(與舊的 類別 → 舊匯出 兩步無關,不 import 歸葉程式):讀效果句與它的框架(frames.json)、
效果句原文(tokens.json)與卡片總表的卡面,把每個**動作框架**(三個位置都匯)落到它所屬的標記句上,寫出
入版控、一句一行、決定性的匯出檔;索引建置(規格 3)與 Python 參考評估器(票 06)讀的都是這份檔的框列。
單位、框架對標記句的規則、原文雜湊、卡面雜湊、統計都與舊匯出同一份(export_common.py)。

頂層:
    說明    本檔怎麼來的(字串)。
    版本    格式版本(整數,VERSION;欄位語意變就加一,讀的人不符即失敗)。
    目錄    具名查詢目錄(票 08 填;本票空清單;列的欄預留在 CATALOG_KEYS)。
    統計    動作對象判定的框數與理由(Stats.doc(),同舊匯出),另加「位置」:匯出的框數分位置。
    卡面    每列 [卡片密碼, 此卡卡面參數雜湊](只含語料有的卡)。
    句      每列一句標記句:card、section、index、hash(原文雜湊)、frames(框列清單,依原文順序)。

框列(FRAME_KEYS;全部可選鍵、只在有值時帶;字面——子句、受事者整段、修飾語字面、數量字面——不匯):
    action        動作詞元
    position      位置(代價/效果/條件)
    polarity      極性(肯定/否定/可能)
    voice         態(他動/自動/受身)
    negation      否定形(受身/不成不受/不可能/一般)
    regions       來源/目的/所在的結構化值 {source|goal|place: [[玩家, 區域七值]…]}——frames.json 的 regions
                  照抄(含轉欄、回指回填寫進的);transfer/region_backfill 記號不匯
    agent         施事者(自分/相手/お互い/此卡/其他卡)
    manner_kind   方式類;manner_value 表示形式值(只在方式類是 表示形式)
    phrases       {patient: [段…], goal: [段…]}——受事者片語取 對象→主語→主題 第一個有片語的欄
                  (PATIENT_SOURCES,與舊關鍵詞同),目的片語取 goal;每段 SEGMENT_KEYS:head 中心詞、
                  head_kind 中心詞類、quantity 數量類(引用量類空時不帶)、modifiers 修飾語類集合
                  (去重、依封閉表序)
    patient_mode  動作對象(此卡/非此卡;皆非不帶),patient.judge_sentence 的 Verdict.mode
鍵名沿用 frames.json 與 closed_values.py 的拼法;玩家 自分/相手/お互い/相對/無。述詞字彙(欄名、值域)票 06
開單一來源模組時接 FRAME_KEYS/SEGMENT_KEYS/PHRASE_KEYS。

每個動作框架都要剛好對到一句標記句,否則匯出失敗、不寫檔(問題清單)。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/export_frames.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patient  # noqa: E402
from closed_values import MODIFIER_KINDS, REGION_KEYS  # noqa: E402
from constraints import KIND_ACTION, POSITIONS  # noqa: E402
from export_common import (ROOT, Stats, face_hash, load_faces, load_sentences, owner,  # noqa: E402
                           print_stats, text_hash)

OUT = os.path.join(ROOT, "data", "action_frames.json")

# 格式版本:欄位語意變就加一(規格「匯出檔要不要格式版本號」(a));索引建置與參考評估器比對不符即失敗
VERSION = 1
# 框列的鍵(匯出順序);票 06 的述詞字彙模組接這裡
FRAME_KEYS = ("action", "position", "polarity", "voice", "negation", "regions", "agent",
              "manner_kind", "manner_value", "phrases", "patient_mode")
# 框架上照抄的單值鍵(有值才帶)
_COPIED_KEYS = ("action", "position", "polarity", "voice", "negation", "agent", "manner_kind", "manner_value")
PHRASE_KEYS = ("patient", "goal")
PATIENT_PHRASE, GOAL_PHRASE = PHRASE_KEYS
# 受事者片語取哪一欄:對象 → 主語 → 主題 第一個有片語的(與舊關鍵詞類條件的取法同)
PATIENT_SOURCES = ("object", "subject", "topic")
SEGMENT_KEYS = ("head", "head_kind", "quantity", "modifiers")
# 目錄列的欄(票 08 填:名、路徑、述詞或空、三個位置的張數、卡集合雜湊;本票目錄是空清單)
CATALOG_KEYS = ("name", "path", "predicate", "cards", "hash")

DOC = ("動作框架匯出檔(.scratch/named-queries,ADR-0018):由 .scratch/effect-tokenize/export_frames.py 產生,"
       "不要手改。「版本」是格式版本(整數,欄位語意變就加一);「目錄」是具名查詢目錄(名、路徑、述詞、"
       "三個位置的張數、卡集合雜湊;目錄序);「句」每列一句新格式新卡的標記句:卡片密碼、段落、index、"
       "日文原文雜湊,與它的動作框架框列(依原文順序;三個位置都匯)——詞元、位置、極性、態、否定形、"
       "來源/目的/所在的結構化值、施事者、方式類、表示形式值、受事者片語與目的片語的段(中心詞、中心詞類、"
       "數量類、修飾語類)、動作對象;全部可選鍵、只在有值時帶,字面不匯。「統計」是動作對象判定的框數與"
       "卡數,與匯出的框數分位置(建置報告照登);「卡面」每列一張卡的此卡卡面參數雜湊(索引建置以卡片總表"
       "重算比對)。")


def segment_row(segment):
    """片語的一段 → 匯出的段:中心詞、中心詞類、數量類(有類才帶)、修飾語類集合(去重、封閉表序)。"""
    row = {"head": segment["head"], "head_kind": segment["head_kind"]}
    quantity = segment.get("quantity")
    if quantity and quantity.get("kind"):
        row["quantity"] = quantity["kind"]
    kinds = {mod["kind"] for mod in segment.get("modifiers") or ()}
    if kinds:
        row["modifiers"] = [kind for kind in MODIFIER_KINDS if kind in kinds]
    return row


def phrase_rows(frame):
    """框架 → {patient: [段…], goal: [段…]}(沒有的鍵不帶)。"""
    phrases = frame.get("phrases") or {}
    out = {}
    source = next((key for key in PATIENT_SOURCES if phrases.get(key)), None)
    if source:
        out[PATIENT_PHRASE] = [segment_row(seg) for seg in phrases[source]["segments"]]
    if phrases.get("goal"):
        out[GOAL_PHRASE] = [segment_row(seg) for seg in phrases["goal"]["segments"]]
    return out


def frame_row(frame, mode):
    """一個動作框架(與它的動作對象判定值)→ 框列。"""
    row = {}
    for key in _COPIED_KEYS:
        if frame.get(key) is not None:
            row[key] = frame[key]
    regions = {key: frame["regions"][key] for key in REGION_KEYS if (frame.get("regions") or {}).get(key)}
    phrases = phrase_rows(frame)
    extra = {"regions": regions, "phrases": phrases, "patient_mode": mode}
    return {key: (row[key] if key in row else extra[key]) for key in FRAME_KEYS
            if key in row or extra.get(key)}


def export(sentences, faces=None):
    """效果句(frames.json 的列,多帶效果句原文 text_ja)+ 卡片密碼 → 此卡卡面參數
    → (匯出文件, 問題清單);問題清單非空即匯出失敗。"""
    faces = faces or {}
    problems = []
    out = []
    stats = Stats()
    positions = {position: 0 for position in POSITIONS}
    for s in sentences:
        rows = {}
        for part in s["parts"]:
            rows[part["index"]] = {"card": s["card"], "section": s["section"], "index": part["index"],
                                   "hash": text_hash(s["text_ja"][part["start"]:part["end"]]), "frames": []}
        verdicts = patient.judge_sentence(s["frames"], faces.get(s["card"]), s["section"])
        for fr, verdict in zip(s["frames"], verdicts):
            if fr["kind"] != KIND_ACTION:
                continue
            index = owner(s, fr)
            if index is None:
                problems.append("框架對不到標記句(選項 %s):%s" % (
                    fr.get("option"), (s["card"], s["section"], s["index"], fr["order"])))
                continue
            rows[index]["frames"].append(frame_row(fr, verdict.mode))
            positions[fr["position"]] += 1
            stats.add(s["card"], verdict)
        out.extend(rows.values())
    covered = sorted({s["card"] for s in sentences} & set(faces))
    face_rows = [[card, face_hash(faces[card])] for card in covered]
    return {"說明": DOC, "版本": VERSION, "目錄": [], "統計": dict(stats.doc(), 位置=positions),
            "卡面": face_rows, "句": out}, problems


def serialize(doc):
    """一句一行、目錄一列一行、卡面一列一行:入版控的檔要 diff 讀得出改了什麼。"""
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    lines = lambda rows: "[]" if not rows else "[\n" + ",\n".join(dump(r) for r in rows) + "\n]"  # noqa: E731
    return ("{\n" + '"說明":' + dump(doc["說明"]) + ",\n"
            + '"版本":' + dump(doc["版本"]) + ",\n"
            + '"目錄":' + lines(doc["目錄"]) + ",\n"
            + '"統計":' + dump(doc["統計"]) + ",\n"
            + '"卡面":' + lines(doc["卡面"]) + ",\n"
            + '"句":' + lines(doc["句"]) + "\n}\n")


def column_counts(rows):
    """句列 → 框列每個鍵有值的框數(建置報告與票 Comments 用)。"""
    counts = {key: 0 for key in FRAME_KEYS}
    for row in rows:
        for fr in row["frames"]:
            for key in fr:
                counts[key] += 1
    return counts


def main():
    doc, problems = export(load_sentences(), load_faces())
    if problems:
        print("**匯出失敗**,%d 個問題(前 20 筆):" % len(problems), file=sys.stderr)
        for p in problems[:20]:
            print("  " + p, file=sys.stderr)
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize(doc))
    rows = doc["句"]
    positions = doc["統計"]["位置"]
    print("標記句 %d(卡 %d 張);框列 %d(%s);版本 %d;已寫出 %s" % (
        len(rows), len({r["card"] for r in rows}), sum(positions.values()),
        "、".join("%s %d" % kv for kv in positions.items()), doc["版本"], OUT))
    print("各欄有值的框數:" + "、".join("%s %d" % kv for kv in column_counts(rows).items()))
    print_stats(doc["統計"], "動作對象(匯出的全部動作框架)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
