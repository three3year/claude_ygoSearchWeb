# -*- coding: utf-8 -*-
"""類別匯出的行為測試(.scratch/category-search 票 01,ADR-0017)。

接縫:(動作框架、框架類別、標記句)→ 類別匯出紀錄(export_categories.export)。
fixture 是合成的幾張卡的標記句列,經真的組裝(tokenize.assemble)、框架抽取
(frames.extract)與類別樹(categories)跑出框架與框架類別,再進匯出;只斷言匯出
紀錄(每句的效果位葉、代價位葉、原文雜湊)與匯出的問題清單,不測對句規則的內部。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import hashlib
import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import categories  # noqa: E402
import export_categories  # noqa: E402
import frames  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "effect_tokenize", os.path.join(HERE, "tokenize.py"))
effect_tokenize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(effect_tokenize)


def clause(index, text_ja, kind="啟動效果", section="main"):
    return {"index": index, "section": section, "kind": kind, "text_ja": text_ja}


def chain(cards):
    """{卡片密碼: 標記句列} → 分詞鏈的兩份中間產物(效果句與其框架、框架類別列),
    形狀同 frames.json(多帶 text_ja)與 frame_categories.json。"""
    tree = categories.default_tree()
    sentences, records = [], []
    for card, clauses in cards.items():
        sections = []
        for c in clauses:
            if c["section"] not in sections:
                sections.append(c["section"])
        for section in sections:
            context = ""
            for rec in effect_tokenize.assemble(
                    [c for c in clauses if c["section"] == section]):
                found = frames.extract(rec["text_ja"], context,
                                       extra=rec["kind"] == "效果外文本")
                for k, fr in enumerate(found):
                    fr["order"] = k
                sentences.append({"card": card, "section": section, "index": rec["index"],
                                  "parts": rec["parts"], "text_ja": rec["text_ja"],
                                  "frames": found})
                for fr, record in categories.classified(tree, found):
                    records.append({"card": card, "section": section,
                                    "index": rec["index"], "order": fr["order"],
                                    "status": record["status"], "leaves": record["leaves"]})
                context += rec["text_ja"]
    return sentences, records


def export(cards):
    sentences, records = chain(cards)
    return export_categories.export(sentences, records, categories.default_tree())


def rows(cards):
    """→ {(卡, 段落, index): (效果位葉, 代價位葉)};斷言匯出沒有問題。"""
    doc, problems = export(cards)
    assert not problems, problems
    return {(r["card"], r["section"], r["index"]): (r.get("effect", []), r.get("cost", []))
            for r in doc["句"]}


def sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


REVIVE = "①：自分の墓地からモンスター１体を特殊召喚する。"


class TestExport(unittest.TestCase):

    def test_single_sentence_effect_leaf_and_hash(self):
        doc, problems = export({1: [clause("①", REVIVE)]})
        self.assertEqual(problems, [])
        self.assertEqual(doc["句"], [{"card": 1, "section": "main", "index": "①",
                                      "hash": sha(REVIVE), "effect": ["特殊召喚←墓地"]}])

    def test_cost_leaves_are_grouped_apart_from_effect_leaves(self):
        self.assertEqual(rows({1: [clause("①", "①：手札を１枚捨てて発動できる。デッキから"
                                              "「試作機」１体を手札に加える。")]}),
                         {(1, "main", "①"): (["加える:デッキ→手札"], ["捨てる"])})

    def test_split_options_go_to_their_own_sub_sentences(self):
        """拆開的效果句:選項 n 的框架屬 index-●n,沒有選項的屬領起句;雜湊各是自己那一句。"""
        sub1 = "●自分の墓地からモンスター１体を特殊召喚する。"
        doc, problems = export({1: [
            clause("①", "①：以下の効果から１つを選択して発動できる。", kind="效果外文本"),
            clause("①-●1", sub1),
            clause("①-●2", "●フィールドのカード１枚を破壊する。")]})
        self.assertEqual(problems, [])
        by_index = {r["index"]: r for r in doc["句"]}
        self.assertEqual(list(by_index), ["①", "①-●1", "①-●2"])
        self.assertNotIn("effect", by_index["①"])
        self.assertEqual(by_index["①-●1"]["effect"], ["特殊召喚←墓地"])
        self.assertEqual(by_index["①-●2"]["effect"], ["破壊@フィールド"])
        self.assertEqual(by_index["①-●1"]["hash"], sha(sub1))

    def test_unsplit_options_stay_in_their_one_sentence(self):
        """官方沒拆的 ●:框架帶選項,效果句只有一段,整個屬那一句。"""
        self.assertEqual(
            rows({1: [clause("①", "①：以下の効果から１つを選択して発動できる。\n"
                                  "●自分の墓地からモンスター１体を特殊召喚する。\n"
                                  "●フィールドのカード１枚を破壊する。")]}),
            {(1, "main", "①"): (["特殊召喚←墓地", "破壊@フィールド"], [])})

    def test_extra_text_and_condition_frames_carry_no_leaves(self):
        """效果外文本照樣有紀錄(只是沒有葉);條件位(墓地へ送られた場合)不帶葉;
        複合區域的框架帶多個葉。"""
        self.assertEqual(
            rows({1: [clause("0", "このカード名の①の効果は１ターンに１度しか使用できない。",
                             kind="效果外文本"),
                      clause("①", "①：このカードが墓地へ送られた場合に発動できる。"
                                  "手札・墓地からモンスター１体を特殊召喚する。",
                             kind="誘發效果(1速)")]}),
            {(1, "main", "0"): ([], []),
             (1, "main", "①"): (["特殊召喚←手札", "特殊召喚←墓地"], [])})

    def test_pendulum_section_unplaced_frames_and_tree_order(self):
        """靈擺段落是自己的鍵;未歸的框架(振り直す)不帶葉;同句重複的葉只記一次、依樹序。"""
        self.assertEqual(
            rows({1: [clause("①", "①：自分フィールドのカード１枚を破壊する。",
                             section="pendulum"),
                      clause("①", "①：サイコロを振り直す。デッキからモンスター１体を墓地へ"
                                  "送り、自分の墓地からモンスター１体を特殊召喚する。その後、"
                                  "墓地からモンスター１体を特殊召喚する。")]}),
            {(1, "pendulum", "①"): (["破壊@自分フィールド"], []),
             (1, "main", "①"): (["特殊召喚←墓地", "送る:デッキ→墓地"], [])})

    def test_frame_without_a_sentence_fails_the_export(self):
        """不變式:每個動作框架剛好對到一句——選項對不到子效果句就失敗。"""
        sentences, records = chain({1: [
            clause("①", "①：以下の効果から１つを選択して発動できる。", kind="效果外文本"),
            clause("①-●1", "●自分の墓地からモンスター１体を特殊召喚する。"),
            clause("①-●2", "●フィールドのカード１枚を破壊する。")]})
        frame = next(f for f in sentences[0]["frames"] if f.get("option") == 2)
        frame["option"] = 3
        _, problems = export_categories.export(sentences, records, categories.default_tree())
        self.assertEqual(len(problems), 1)
        self.assertIn("對不到標記句", problems[0])

    def test_stale_frame_categories_fail_the_export(self):
        """框架類別與框架對不上(中間產物過時)就失敗,兩個方向都擋。"""
        sentences, records = chain({1: [clause("①", REVIVE)]})
        extra = dict(records[0], order=9)
        _, problems = export_categories.export(sentences, records + [extra],
                                               categories.default_tree())
        self.assertEqual(len(problems), 1)
        _, problems = export_categories.export(sentences, [], categories.default_tree())
        self.assertEqual(len(problems), 1)

    def test_tree_rides_along_with_leaf_names_in_tree_order(self):
        """匯出帶類別樹:葉名依樹序,巢狀節點的葉號指回葉名;詞元節點帶預設葉時同一節點
        既有葉號又有子節點(破壊 底下的 {})。"""
        doc, _ = export({1: [clause("①", REVIVE)]})
        leaves = doc["葉"]
        self.assertEqual(len(leaves), len(categories.default_tree().leaves))

        def find(nodes, path):
            node = next(n for n in nodes if n[0] == path[0])
            return node if len(path) == 1 else find(node[2], path[1:])
        revive = find(doc["樹"], ["召喚", "特殊召喚", "特殊召喚←墓地"])
        self.assertEqual(leaves[revive[1]], "特殊召喚←墓地")
        self.assertEqual(revive[2], [])
        destroy = find(doc["樹"], ["破壊"])
        self.assertEqual(leaves[destroy[1]], "破壊")
        self.assertTrue(destroy[2])

    def test_serialization_is_one_sentence_per_line_and_roundtrips(self):
        import json
        doc, _ = export({1: [clause("①", REVIVE)], 2: [clause("①", REVIVE)]})
        text = export_categories.serialize(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertEqual(sum(line.startswith('{"card"') for line in text.splitlines()), 2)

    def test_same_input_exports_byte_identical(self):
        cards = {1: [clause("①", REVIVE)],
                 2: [clause("①", "①：手札を１枚捨てて発動できる。デッキから「試作機」１体を"
                                 "手札に加える。")]}
        first = export_categories.serialize(export(cards)[0])
        self.assertEqual(first, export_categories.serialize(export(cards)[0]))


if __name__ == "__main__":
    unittest.main()
