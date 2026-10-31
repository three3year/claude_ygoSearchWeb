# -*- coding: utf-8 -*-
"""具名查詢的命中(named-queries 票 08,ADR-0018):重跑鏈的「目錄」一步,接在框架之後、框列匯出之前。

做三件事:載入並檢查目錄(catalog.load,違反即失敗)、對全語料每個動作框架算命中的具名查詢(三個位置都算)、
檢查「每個具名查詢在全語料三個位置合計至少命中一張」(規格「不留位置口徑」(a));過了才寫中間產物
frame_queries.json(gitignore)。命中用參考評估器(predicate.matcher)對**匯出的框列**算:框架先經 export_frames.frame_rows
轉成框列(框架 → 框列只有那一份),評估器讀的就是匯出檔裡的同一個 dict——所以拆解頁、LLM 抽驗看到的命中與索引
(規格 3 的 JS 評估器)算出的是同一回事。大類/中類的命中是底下具名查詢的聯集(catalog.Catalog.members),由樹推得、
不另存。它取代舊的框架類別檔 frame_categories.json 的角色(過渡期舊檔照產)。

frame_queries.json(JSON 清單,一框一行;前四鍵是框架身分,同舊框架類別檔、對得回 frames.json):
    card      卡片密碼
    section   段落(main/pendulum)
    index     效果句 index(frames.json 的句,不是標記句)
    order     框架在句裡的序(frames.json 的 order)
    action    動作詞元
    position  位置(代價/效果/條件)
    queries   命中的具名查詢名清單(目錄序;空清單 = 沒命中任何具名查詢)
    patient   動作對象(此卡/非此卡;皆非是 null)——票 09 拆解頁每框照舊顯示,與匯出框列的 patient_mode 同一個判定
    why       動作對象的理由(patient.WHY_*;拆解頁的 title)

接縫:query_names(原文, 上文, 目錄, 卡面) → 每個動作框架命中的具名查詢名清單(依原文順序;目錄預設是真目錄,
測試可傳小目錄驗機制)。hits(目錄, 框列清單) → 每框列的命中名清單。

「不留」檢查失敗的輸出(stderr):「**具名查詢在全語料三個位置都沒有命中(不留)**,N 個:」接著每行一個名字
(目錄序),exit 1、不寫檔。目錄載入失敗同樣印 CatalogError 的清單、exit 1。

用法:PYTHONIOENCODING=utf-8 python .scratch/effect-tokenize/catalog_hits.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import export_frames  # noqa: E402
import frames  # noqa: E402
import predicate  # noqa: E402
from constraints import POSITIONS  # noqa: E402
from export_common import load_faces, load_sentences  # noqa: E402

OUT = os.path.join(HERE, "frame_queries.json")

_default = []


def default_catalog():
    """真目錄(載入一次)。"""
    if not _default:
        _default.append(catalog.load())
    return _default[0]


def compiled(cat):
    """目錄 → [(具名查詢名, 判定函式)…](目錄序;全語料跑時每個述詞只編一次)。"""
    return [(q.name, predicate.matcher(q.predicate)) for q in cat.queries]


def hits(cat, rows):
    """目錄 × 框列清單 → 每個框列命中的具名查詢名清單(目錄序)。"""
    matchers = compiled(cat)
    return [[name for name, match in matchers if match(row)] for row in rows]


def query_names(text, context="", cat=None, face=None):
    """接縫:一句效果句原文(帶同卡同段上文)→ 每個動作框架命中的具名查詢名清單(依原文順序)。
    cat 預設是真目錄;face 是此卡卡面參數(動作對象要讀卡面時給)。"""
    sentence = {"card": 0, "section": "main", "frames": frames.extract(text, context)}
    rows = [row for _, row, _ in export_frames.frame_rows(sentence, {0: face} if face else {})]
    return hits(cat or default_catalog(), rows)


def records(cat, sentences, faces):
    """全語料:效果句列 → (每框一列的命中紀錄, 每個具名查詢三個位置的卡集合)。框架先轉成框列(框架 → 框列
    只有 export_frames 那一份),命中與張數都對框列算。"""
    matchers = compiled(cat)
    out = []
    pseudo = []                         # 句列的形狀 {card, frames},給 predicate.card_sets
    for s in sentences:
        rows = []
        for fr, row, verdict in export_frames.frame_rows(s, faces):
            rows.append(row)
            out.append({"card": s["card"], "section": s["section"], "index": s["index"], "order": fr["order"],
                        "action": fr["action"], "position": fr["position"],
                        "queries": [name for name, match in matchers if match(row)],
                        "patient": verdict.mode, "why": verdict.why})
        pseudo.append({"card": s["card"], "frames": rows})
    return out, export_frames.query_sets(cat, pseudo)


def serialize(found):
    """一框一行(diff 讀得出哪一框的命中變了)。"""
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    return "[]\n" if not found else "[\n" + ",\n".join(dump(r) for r in found) + "\n]\n"


def main():
    try:
        cat = catalog.load()
    except catalog.CatalogError as e:
        print(e, file=sys.stderr)
        return 1
    found, sets = records(cat, load_sentences(), load_faces())
    missing = export_frames.unmatched(cat, sets)
    if missing:
        print("**具名查詢在全語料三個位置都沒有命中(不留)**,%d 個:" % len(missing), file=sys.stderr)
        for name in missing:
            print("  " + name, file=sys.stderr)
        return 1
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(serialize(found))
    hit = [r for r in found if r["queries"]]
    print("具名查詢 %d(全部至少命中一張);動作框架 %d,命中任一具名查詢的 %d(%s);已寫出 %s" % (
        len(cat.queries), len(found), len(hit),
        "、".join("%s %d" % (position, sum(r["position"] == position for r in hit)) for position in POSITIONS),
        OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
