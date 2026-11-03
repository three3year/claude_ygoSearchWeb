# -*- coding: utf-8 -*-
"""框列匯出的行為測試(named-queries 票 05)。

接縫:(效果句與它的動作框架、標記句、卡面)→ 框列匯出文件(export_frames.export)與它的序列化
(export_frames.serialize)。fixture 是合成的幾張卡的標記句列,經真的組裝(tokenize.assemble)與框架抽取
(frames.extract)跑出框架,再進匯出;只斷言匯出的每句列(卡片密碼、段落、index、原文雜湊、框列的每個欄,
含動作對象)、卡面雜湊、問題清單與序列化的形狀,不測框架抽取與判定的內部。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import hashlib
import importlib.util
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import closed_values  # noqa: E402
import export_common  # noqa: E402
import export_frames  # noqa: E402
import frames  # noqa: E402
import predicate  # noqa: E402

_spec = importlib.util.spec_from_file_location("effect_tokenize", os.path.join(HERE, "tokenize.py"))
effect_tokenize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(effect_tokenize)


def clause(index, text_ja, kind="啟動效果", section="main"):
    return {"index": index, "section": section, "kind": kind, "text_ja": text_ja}


def chain(cards):
    """{卡片密碼: 標記句列} → 效果句與其框架(形狀同 frames.json,多帶 text_ja)。"""
    sentences = []
    for card, clauses in cards.items():
        sections = []
        for c in clauses:
            if c["section"] not in sections:
                sections.append(c["section"])
        for section in sections:
            context = ""
            for rec in effect_tokenize.assemble([c for c in clauses if c["section"] == section]):
                found = frames.extract(rec["text_ja"], context, extra=rec["kind"] == "效果外文本")
                for k, fr in enumerate(found):
                    fr["order"] = k
                sentences.append({"card": card, "section": section, "index": rec["index"],
                                  "parts": rec["parts"], "text_ja": rec["text_ja"], "frames": found})
                context += rec["text_ja"]
    return sentences


def export(cards, faces=None):
    return export_frames.export(chain(cards), faces=faces)


def rows(cards, faces=None):
    """→ {(卡, 段落, index): 框列清單};斷言匯出沒有問題。"""
    doc, problems = export(cards, faces)
    assert not problems, problems
    return {(r["card"], r["section"], r["index"]): r["frames"] for r in doc["句"]}


def sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# 合成的卡面參數(卡片總表的欄位):等級 7 的暗屬性龍族效果怪獸
DRAGON = {"id": 1, "type": 0x21, "race": 0x2000, "attribute": 0x20, "level": 7,
          "atk": 2500, "def": 2000, "name_ja": "テスト・ドラゴン"}
REVIVE = "①：自分の墓地からモンスター１体を特殊召喚する。"
REVIVE_ROW = {"action": "特殊召喚", "position": "效果", "polarity": "肯定",
              "regions": {"source": [["自分", "墓地"]], "goal": [["無", "場上"]]}, "agent": "自分",
              "phrases": {"patient": [{"head": "モンスター", "head_kind": "卡", "quantity": "定數"}]},
              "patient_mode": "非此卡"}


class TestSentenceRows(unittest.TestCase):
    """每句標記句一列:鍵、原文雜湊、框列(依原文順序);框架對標記句的規則在 export_common.owner。"""

    def test_single_sentence_row_carries_every_column_of_its_frame(self):
        """一句一框:詞元、位置、極性、結構化區域(含推得的目的,玩家 無)、施事者、受事者片語的段
        (中心詞、中心詞類、數量類)、動作對象;沒值的欄(態、否定形、方式、目的片語、修飾語)不帶。"""
        doc, problems = export({1: [clause("①", REVIVE)]})
        self.assertEqual(problems, [])
        self.assertEqual(doc["句"], [{"card": 1, "section": "main", "index": "①", "hash": sha(REVIVE),
                                      "frames": [REVIVE_ROW]}])

    def test_split_options_go_to_their_own_sub_sentences(self):
        """拆開的效果句:選項 n 的框架屬 index-●n,沒有選項的(領起句的 選択,條件位)屬領起句;
        雜湊各是自己那一句;四個位置都匯。"""
        sub1 = "●自分の墓地からモンスター１体を特殊召喚する。"
        doc, problems = export({1: [
            clause("①", "①：以下の効果から１つを選択して発動できる。", kind="效果外文本"),
            clause("①-●1", sub1),
            clause("①-●2", "●フィールドのカード１枚を破壊する。")]})
        self.assertEqual(problems, [])
        by_index = {r["index"]: r for r in doc["句"]}
        self.assertEqual(list(by_index), ["①", "①-●1", "①-●2"])
        self.assertEqual([fr["action"] for fr in by_index["①"]["frames"]], ["選択"])
        self.assertEqual(by_index["①"]["frames"][0]["position"], "條件")
        self.assertEqual(by_index["①-●1"]["frames"], [REVIVE_ROW])
        self.assertEqual(by_index["①-●1"]["hash"], sha(sub1))
        self.assertEqual(by_index["①-●2"]["frames"], [
            {"action": "破壊", "position": "效果", "polarity": "肯定", "regions": {"place": [["無", "場上"]]},
             "agent": "自分", "phrases": {"patient": [{"head": "カード", "head_kind": "卡", "quantity": "定數",
                                                      "modifiers": ["區域"]}]},
             "patient_mode": "非此卡"}])

    def test_unsplit_options_stay_in_their_one_sentence(self):
        """官方沒拆的 ●:效果句只有一段,框架全屬那一句、依原文順序。"""
        found = rows({1: [clause("①", "①：以下の効果から１つを選択して発動できる。\n"
                                      "●自分の墓地からモンスター１体を特殊召喚する。\n"
                                      "●フィールドのカード１枚を破壊する。")]})
        self.assertEqual([fr["action"] for fr in found[(1, "main", "①")]], ["選択", "特殊召喚", "破壊"])

    def test_frame_without_a_sentence_fails_the_export(self):
        """不變式:每個動作框架剛好對到一句——選項對不到子效果句就失敗。"""
        sentences = chain({1: [
            clause("①", "①：以下の効果から１つを選択して発動できる。", kind="效果外文本"),
            clause("①-●1", "●自分の墓地からモンスター１体を特殊召喚する。"),
            clause("①-●2", "●フィールドのカード１枚を破壊する。")]})
        frame = next(f for f in sentences[0]["frames"] if f.get("option") == 2)
        frame["option"] = 3
        _, problems = export_frames.export(sentences)
        self.assertEqual(len(problems), 1)
        self.assertIn("對不到標記句(選項 3)", problems[0])

    def test_extra_text_and_constraint_only_sentences_have_empty_frame_lists(self):
        """效果外文本與只有約束框架的句照樣有紀錄,框列空;靈擺段落是自己的鍵。"""
        found = rows({1: [clause("0", "このカード名の①の効果は１ターンに１度しか使用できない。", kind="效果外文本"),
                          clause("①", REVIVE, section="pendulum")]})
        self.assertEqual(found, {(1, "main", "0"): [], (1, "pendulum", "①"): [REVIVE_ROW]})


class TestFrameColumns(unittest.TestCase):
    """框列每個欄的來源與「只在有值時帶」。"""

    def frame(self, text, faces=None, kind="啟動效果"):
        found = rows({1: [clause("①", text, kind=kind)]}, faces)
        return found[(1, "main", "①")]

    def test_voice_negation_manner_kind_and_self_patient_from_topic(self):
        """受身否定:態、否定形、方式類(手段:戰鬥,沒有表示形式值);受事者片語取主題;動作對象 此卡;
        沒區域、沒施事者就沒那些鍵。"""
        self.assertEqual(self.frame("①：このカードは戦闘では破壊されない。"), [
            {"action": "破壊", "position": "效果", "polarity": "否定", "voice": "受身", "negation": "受身",
             "manner_kind": "手段:戰鬥", "phrases": {"patient": [{"head": "カード", "head_kind": "卡"}]},
             "patient_mode": "此卡"}])

    def test_manner_value_modifier_kinds_and_cost_position(self):
        """代價位的框架也匯(取自子句的數量仍是定數);表示形式值只在方式類是 表示形式;修飾語類集合
        依封閉表序(字段 在 數值 前),字面不匯。"""
        cost, effect = self.frame("①：手札を１枚捨てて発動できる。デッキからレベル８の「DDD」モンスター１体を"
                                  "守備表示で特殊召喚する。")
        self.assertEqual(cost, {"action": "捨てる", "position": "代價", "polarity": "肯定",
                                "regions": {"source": [["無", "手牌"]], "goal": [["無", "墓地"]]}, "agent": "自分",
                                "phrases": {"patient": [{"head": "手札", "head_kind": "卡", "quantity": "定數"}]},
                                "patient_mode": "非此卡"})
        self.assertEqual(effect, {"action": "特殊召喚", "position": "效果", "polarity": "肯定",
                                  "regions": {"source": [["無", "牌組"]], "goal": [["無", "場上"]]}, "agent": "自分",
                                  "manner_kind": "表示形式", "manner_value": "守備表示",
                                  "phrases": {"patient": [{"head": "モンスター", "head_kind": "卡",
                                                           "quantity": "定數", "modifiers": ["字段", "數值"]}]},
                                  "patient_mode": "非此卡"})

    def test_condition_frames_goal_phrase_and_backfilled_regions(self):
        """條件位框架照匯(受身的受事者取主語);目的片語是自己的段清單;回指回填寫進的所在也在結構化值裡
        (記號不匯);指示詞受事者沿用目標的判定。"""
        found = self.frame("①：このカードが墓地へ送られた場合に発動できる。相手フィールドの表側表示モンスター"
                           "１体を対象として発動できる。そのモンスターの攻撃力を０にする。", kind="誘發效果(1速)")
        self.assertEqual(found, [
            {"action": "送る", "position": "條件", "polarity": "肯定", "voice": "受身",
             "regions": {"goal": [["無", "墓地"]]},
             "phrases": {"patient": [{"head": "カード", "head_kind": "卡"}],
                         "goal": [{"head": "墓地", "head_kind": "卡"}]},
             "patient_mode": "此卡"},
            {"action": "対象とする", "position": "條件", "polarity": "肯定",
             "regions": {"place": [["相手", "場上"]]},
             "phrases": {"patient": [{"head": "モンスター", "head_kind": "卡", "quantity": "定數",
                                      "modifiers": ["區域", "表示形式"]}]},
             "patient_mode": "非此卡"},
            {"action": "にする", "position": "效果", "polarity": "肯定", "voice": "他動",
             "regions": {"place": [["相手", "場上"]]}, "agent": "自分",
             "phrases": {"patient": [{"head": "攻撃力", "head_kind": "屬性", "modifiers": ["其他"]}],
                         "goal": [{"head": "0", "head_kind": "非卡"}]},
             "patient_mode": "非此卡"}])

    def test_neither_mode_leaves_the_key_out_and_agent_from_topic(self):
        """皆非(ドロー 沒有卡片受事者)不帶動作對象;主題是玩家時施事者取主題、受事者片語仍是主題段。"""
        self.assertEqual(self.frame("①：自分はデッキから１枚ドローする。"), [
            {"action": "ドロー", "position": "效果", "polarity": "肯定",
             "regions": {"source": [["無", "牌組"]], "goal": [["無", "手牌"]]}, "agent": "自分",
             "phrases": {"patient": [{"head": "自分", "head_kind": "玩家"}]}}])

    def test_transferred_place_is_exported_as_a_region_without_its_marker(self):
        """非移動類的 から 轉成結構化所在(取自來源)——所在匯出、記號不匯。"""
        choose = self.frame("①：手札・墓地から「ドラゴン」モンスター１体を選んで特殊召喚する。")[0]
        self.assertEqual(choose["action"], "選ぶ")
        self.assertEqual(choose["regions"], {"source": [["無", "手牌"], ["無", "墓地"]],
                                             "place": [["無", "手牌"], ["無", "墓地"]]})
        self.assertNotIn("transfer", choose)

    def test_patient_mode_reads_the_card_face(self):
        """全部類比對讀此卡卡面:龍族此卡對 自分フィールドのドラゴン族モンスター 全部 → 含此卡(皆非、不帶);
        卡面是魔法時卡種對不上 → 非此卡。"""
        text = "①：自分フィールドのドラゴン族モンスターの攻撃力は５００アップする。"
        faces = {1: export_common.card_face(DRAGON)}
        self.assertNotIn("patient_mode", self.frame(text, faces)[0])
        spell = dict(DRAGON, type=0x2, race=0, attribute=0, level=0)
        faces = {1: export_common.card_face(spell)}
        self.assertEqual(self.frame(text, faces)[0]["patient_mode"], "非此卡")


class TestDocument(unittest.TestCase):
    """頂層:說明、版本、值域(規格 3 票 01)、目錄(本票空)、統計、卡面、句;序列化一句一行;決定性。"""

    def test_top_level_keys_version_empty_catalog_faces_and_stats(self):
        faces = {1: export_common.card_face(DRAGON)}
        doc, problems = export({1: [clause("①", REVIVE)], 2: [clause("①", "①：このカードを墓地へ送る。")]},
                               faces)
        self.assertEqual(problems, [])
        self.assertEqual(list(doc), ["說明", "版本", "值域", "目錄", "統計", "卡面", "句"])
        self.assertEqual(doc["版本"], 3)
        self.assertEqual(doc["目錄"], [])
        self.assertEqual(doc["卡面"], [[1, export_common.face_hash(DRAGON)]])
        self.assertEqual(doc["統計"]["框架"], {"此卡": 1, "非此卡": 1, "皆非": 0})
        self.assertEqual(doc["統計"]["位置"], {"代價": 0, "效果": 2, "條件": 0, "召喚手續": 0})

    def test_procedure_frames_are_exported_under_the_fourth_position(self):
        """summon-procedure 票 02:召喚條件的白名單手續步驟以位置 召喚手續 匯出,統計位置多一格。"""
        text = "自分の墓地のモンスター１体を除外した場合のみ特殊召喚できる。"
        doc, problems = export({1: [clause("0", text, kind="效果外文本")]})
        self.assertEqual(problems, [])
        self.assertEqual([(fr["action"], fr["position"]) for r in doc["句"] for fr in r["frames"]],
                         [("除外", "召喚手續")])
        self.assertEqual(doc["統計"]["位置"], {"代價": 0, "效果": 0, "條件": 0, "召喚手續": 1})

    def test_serialization_is_one_sentence_per_line_and_roundtrips(self):
        doc, _ = export({1: [clause("①", REVIVE)], 2: [clause("①", REVIVE)]})
        text = export_frames.serialize(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertEqual(sum(line.startswith('{"card"') for line in text.splitlines()), 2)
        self.assertIn('\n"目錄":[],\n', text)
        self.assertIn('\n"版本":3,\n', text)

    def test_domains_follow_the_reference_evaluator_in_declared_order(self):
        """規格 3 票 01:值域是參考評估器每個封閉類欄的值域,另加玩家與區域兩張;欄序與值序都是宣告序,
        序列化後(索引建置讀到的)也一樣。比清單不比集合:索引的整數碼是值域序號,順序就是內容。"""
        doc, problems = export({1: [clause("①", REVIVE)]})
        self.assertEqual(problems, [])
        expected = [(field, list(values)) for field, values in predicate.DOMAIN.items()]
        expected += [("玩家", list(closed_values.PLAYERS)), ("區域", list(closed_values.ZONES))]
        self.assertEqual(list(doc["值域"].items()), expected)
        self.assertEqual(list(json.loads(export_frames.serialize(doc))["值域"].items()), expected)

    def test_domains_are_there_without_a_catalog_or_sentences(self):
        """值域不看語料:沒有句、沒有目錄也帶,且一樣完整(索引建置靠它擋值域外的值)。"""
        doc, problems = export_frames.export([])
        self.assertEqual(problems, [])
        self.assertEqual(doc["值域"], export({1: [clause("①", REVIVE)]})[0]["值域"])

    def test_same_input_exports_byte_identical(self):
        cards = {1: [clause("①", REVIVE)],
                 2: [clause("①", "①：手札を１枚捨てて発動できる。デッキからレベル８の「DDD」モンスター１体を"
                                 "守備表示で特殊召喚する。")]}
        faces = {1: export_common.card_face(DRAGON)}
        first = export_frames.serialize(export(cards, faces)[0])
        self.assertEqual(first, export_frames.serialize(export(cards, faces)[0]))


if __name__ == "__main__":
    unittest.main()
