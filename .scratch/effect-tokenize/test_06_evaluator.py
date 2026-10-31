# -*- coding: utf-8 -*-
"""參考評估器的行為測試(named-queries 票 06)。

接縫:(述詞, 匯出的框列)→ 命中與否(predicate.matches)。例子來自入版控的夾具 predicate-fixture.json(規格 3 的
JS 評估器 node 測試讀同一張),逐條跑;另加幾條接縫例子:合成卡經真的組裝、框架抽取、框列匯出後的框列拿來評估、
述詞字彙(欄名 ↔ 匯出鍵、值域)的一致性、述詞的檢查(problems)、全語料張數輔助(card_sets/cards_hash)。
全語料的一條讀 data/action_frames.json,缺檔時略過並印原因。只斷言評估結果、問題清單與卡集合,不斷言怎麼比。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import closed_values  # noqa: E402
import export_frames  # noqa: E402
import predicate  # noqa: E402
from constraints import POSITIONS  # noqa: E402
from test_05_export_frames import DRAGON, REVIVE, clause, rows  # noqa: E402

FIXTURE = os.path.join(HERE, "predicate-fixture.json")


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class TestFixture(unittest.TestCase):
    """夾具逐條:述詞 × 框列 → 命中;夾具的版本、框列鍵與述詞都要合字彙。"""

    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()

    def test_every_example_evaluates_to_its_expected_hit(self):
        for ex in self.fixture["例子"]:
            with self.subTest(ex["名"]):
                row = self.fixture["框列"][ex["框列"]]
                self.assertIs(predicate.matches(ex["述詞"], row), ex["命中"])

    def test_fixture_follows_the_export_format_version(self):
        self.assertEqual(self.fixture["版本"], export_frames.VERSION)

    def test_fixture_rows_only_use_export_keys(self):
        for name, row in self.fixture["框列"].items():
            with self.subTest(name):
                self.assertEqual([k for k in row if k not in predicate.FRAME_KEYS], [])
                for key, segments in row.get("phrases", {}).items():
                    self.assertIn(key, predicate.PHRASE_KEYS)
                    for seg in segments:
                        self.assertEqual([k for k in seg if k not in predicate.SEGMENT_KEYS], [])

    def test_fixture_predicates_pass_the_vocabulary_check(self):
        for ex in self.fixture["例子"]:
            with self.subTest(ex["名"]):
                self.assertEqual(predicate.problems(ex["述詞"]), [])

    def test_hash_examples(self):
        for ex in self.fixture["雜湊"]:
            with self.subTest(ex["名"]):
                self.assertEqual(predicate.cards_hash(ex["卡"]), ex["雜湊"])

    def test_card_set_examples(self):
        block = self.fixture["張數"]
        predicates = [ex["述詞"] for ex in block["例子"]]
        found = predicate.card_sets(predicates, block["句"])
        for ex, sets in zip(block["例子"], found):
            with self.subTest(ex["名"]):
                self.assertEqual({pos: sorted(cards) for pos, cards in sets.items()},
                                 {pos: ex["張數"][pos]["卡"] for pos in POSITIONS})
                self.assertEqual({pos: predicate.cards_hash(cards) for pos, cards in sets.items()},
                                 {pos: ex["張數"][pos]["雜湊"] for pos in POSITIONS})


class TestVocabulary(unittest.TestCase):
    """述詞字彙只有一份:欄名對得到匯出鍵(票 05 的 FRAME_KEYS 不改),值域就是封閉表。"""

    def test_export_imports_its_keys_from_the_vocabulary(self):
        self.assertIs(export_frames.FRAME_KEYS, predicate.FRAME_KEYS)
        self.assertIs(export_frames.PHRASE_KEYS, predicate.PHRASE_KEYS)
        self.assertIs(export_frames.SEGMENT_KEYS, predicate.SEGMENT_KEYS)
        self.assertEqual(predicate.FRAME_KEYS, ("action", "position", "polarity", "voice", "negation", "regions",
                                                "agent", "manner_kind", "manner_value", "phrases", "patient_mode"))

    def test_every_field_maps_to_an_export_key_path(self):
        self.assertEqual(set(predicate.EXPORT_PATH), set(predicate.FIELDS))
        for field, path in predicate.EXPORT_PATH.items():
            with self.subTest(field):
                self.assertIn(path[0], predicate.FRAME_KEYS)
                if path[0] == "regions":
                    self.assertIn(path[1], closed_values.REGION_KEYS)
                if path[0] == "phrases":
                    self.assertIn(path[1], predicate.PHRASE_KEYS)
                    self.assertIn(path[2], predicate.SEGMENT_KEYS)

    def test_domains_are_the_closed_tables(self):
        self.assertIs(predicate.DOMAIN["否定形"], closed_values.NEGATION_FORMS)
        self.assertIs(predicate.DOMAIN["施事者"], closed_values.AGENTS)
        self.assertIs(predicate.DOMAIN["動作對象"], closed_values.PATIENT_MODES)
        self.assertEqual(predicate.DOMAIN["位置"], POSITIONS)

    def test_problems_name_unknown_fields_and_values_outside_the_domain(self):
        self.assertEqual(predicate.problems({"關鍵詞": ["モンスター"]}), ["不認得的欄:關鍵詞"])
        self.assertEqual(predicate.problems({"否定形": ["耐性"]}), ["否定形 的值不在值域:耐性"])
        self.assertEqual(predicate.problems({"來源": [["雙方", "墓地"]]}), ["來源 的玩家不在值域:雙方"])
        self.assertEqual(predicate.problems({"來源": [[None, "フィールド"]]}), ["來源 的區域不在值域:フィールド"])
        self.assertEqual(predicate.problems({"來源": ["自分", "墓地"]}),
                         ["來源 的每項要是 [玩家或 null, 區域]:自分", "來源 的每項要是 [玩家或 null, 區域]:墓地"])
        self.assertEqual(predicate.problems({"受事者中心詞": [""]}), ["受事者中心詞 的值要是非空字串:''"])
        self.assertEqual(predicate.problems({"詞元": "戻る"}), ["詞元 不是框架抽取產得出的正規詞元:戻る(正規詞元是 戻す)"])
        self.assertEqual(predicate.problems({"詞元": "裏側守備表示にする"}),
                         ["詞元 的補語是值或屬性,框架抽取不併入詞元:裏側守備表示にする(詞元寫 にする/とする、補語用目的中心詞)"])
        self.assertEqual(predicate.problems({"詞元": "破壊", "極性": ["肯定", "可能"], "來源": [[None, "墓地"]],
                                             "受事者中心詞": ["モンスター"], "動作對象": "此卡"}), [])

    def test_matching_an_unknown_field_raises(self):
        with self.assertRaises(ValueError):
            predicate.matches({"關鍵詞": ["モンスター"]}, {"action": "破壊"})


class TestExportedRows(unittest.TestCase):
    """接縫例子:合成卡經組裝、框架抽取、框列匯出後的框列,直接拿來評估。"""

    @classmethod
    def setUpClass(cls):
        found = rows({1: [clause("①", REVIVE)], 2: [clause("①", "①：このカードは戦闘では破壊されない。")]},
                     {1: DRAGON, 2: DRAGON})
        cls.revive = found[(1, "main", "①")][0]
        cls.resist = found[(2, "main", "①")][0]

    def test_named_query_hits_the_exported_row(self):
        self.assertTrue(predicate.matches({"詞元": "特殊召喚", "極性": ["肯定", "可能"], "來源": [["自分", "墓地"]],
                                           "受事者中心詞": ["モンスター"], "動作對象": ["非此卡"]}, self.revive))

    def test_named_query_misses_on_one_field(self):
        self.assertFalse(predicate.matches({"詞元": "特殊召喚", "來源": [["相手", "墓地"]]}, self.revive))
        self.assertFalse(predicate.matches({"詞元": "特殊召喚", "動作對象": ["此卡"]}, self.revive))

    def test_resistance_query_reads_negation_form_of_the_exported_row(self):
        resist = {"詞元": "破壊", "否定形": ["受身", "不成不受"]}
        self.assertTrue(predicate.matches(resist, self.resist))
        self.assertFalse(predicate.matches(resist, self.revive))
        self.assertTrue(predicate.matches({"動作對象": ["此卡"], "方式類": ["手段:戰鬥"]}, self.resist))


class TestCorpus(unittest.TestCase):
    """全語料:匯出檔的每一框都被空述詞命中(張數輔助的框數等於匯出檔的「位置」統計);缺檔時略過。"""

    @classmethod
    def setUpClass(cls):
        cls.reason = None
        if not os.path.exists(export_frames.OUT):
            cls.reason = "略過:沒有 %s(先跑 run_chain.py)" % export_frames.OUT
            print(cls.reason, file=sys.stderr)
            return
        with open(export_frames.OUT, encoding="utf-8") as f:
            cls.doc = json.load(f)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def test_empty_predicate_hits_every_exported_frame(self):
        self.assertEqual(self.doc["版本"], export_frames.VERSION)
        match = predicate.matcher({})
        counts = {position: 0 for position in POSITIONS}
        for row in self.doc["句"]:
            for fr in row["frames"]:
                if match(fr):
                    counts[fr["position"]] += 1
        self.assertEqual(counts, self.doc["統計"]["位置"])

    def test_ruling_queries_hit_cards_in_the_corpus(self):
        queries = [{"詞元": "破壊", "極性": ["肯定", "可能"], "受事者中心詞": ["モンスター"]},
                   {"詞元": "破壊", "否定形": ["受身", "不成不受"]},
                   {"詞元": "攻撃", "否定形": ["不可能"]},
                   {"詞元": "取り除く", "所在": [["お互い", "場上"]]}]
        sets = predicate.card_sets(queries, self.doc["句"])
        self.assertEqual([bool(sum(len(s) for s in per.values())) for per in sets], [True] * len(queries))
        self.assertEqual(len(sets[3]["效果"]), 0)      # 取り除く@お互いのフィールド 只在代價位
        self.assertGreater(len(sets[3]["代價"]), 0)


if __name__ == "__main__":
    unittest.main()
