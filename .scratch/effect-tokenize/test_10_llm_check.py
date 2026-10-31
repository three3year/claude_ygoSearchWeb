# -*- coding: utf-8 -*-
"""具名查詢命中的 LLM 抽驗(named-queries 票 10)的行為測試。

接縫:llm_check.query_diff(目錄, 舊歸葉, 命中, 框架) → 逐名的差異與歸因(分層讀它);llm_check.pick(種子, 母體, 層, 配額)
→ 樣本(決定性);llm_check.sample_queries(種子) → 全語料的分層樣本(缺命中中間產物/舊歸葉檔時 skipTest 並印原因)。
只斷言差異清單、樣本的卡與層,不斷言批次檔怎麼排版。round1 的 89 筆全部歸到框架線(上游)、動作對象判定規則與目錄內容
三類規格 Out of Scope 的事(見票 Comments),目錄/評估器/命中轉換沒有要修的規則,所以本檔沒有修規則的回歸例子。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import llm_check  # noqa: E402
from closed_values import TRANSFER_FROM_SOURCE  # noqa: E402
from constraints import POS_COND, POS_EFFECT  # noqa: E402
from test_08_hits import SMALL, query  # noqa: E402


def frame(**fields):
    """一個動作框架(只給分層讀的鍵)。"""
    return dict({"kind": "動作", "position": POS_EFFECT}, **fields)


class TestQueryDiff(unittest.TestCase):
    """命中集合 vs 舊歸葉 的逐名歸因(docstring 的六個原因)。"""

    def setUp(self):
        self.cat = catalog.Catalog(SMALL)

    def test_lemma_node_newly_hit_is_the_default_leaf_going_away(self):
        diff = llm_check.query_diff(self.cat, ["破壊:モンスター"], ["破壊", "破壊:モンスター"], frame())
        self.assertEqual(diff, [("+", "破壊", llm_check.DIFF_DEFAULT)])

    def test_place_query_hit_through_transfer_from_source(self):
        diff = llm_check.query_diff(self.cat, [], ["破壊@フィールド"], frame(transfer=TRANSFER_FROM_SOURCE))
        self.assertEqual(diff, [("+", "破壊@フィールド", llm_check.DIFF_KARA)])

    def test_region_query_hit_through_anaphora_backfill(self):
        source = llm_check.query_diff(self.cat, ["特殊召喚"], ["特殊召喚", "特殊召喚←墓地"], frame(region_backfill="source"))
        place = llm_check.query_diff(self.cat, [], ["破壊@フィールド"], frame(region_backfill="place"))
        self.assertEqual(source, [("+", "特殊召喚←墓地", llm_check.DIFF_BACKFILL)])
        self.assertEqual(place, [("+", "破壊@フィールド", llm_check.DIFF_BACKFILL)])

    def test_backfill_into_another_field_does_not_count(self):
        diff = llm_check.query_diff(self.cat, [], ["特殊召喚←墓地"], frame(region_backfill="place"))
        self.assertEqual(diff, [("+", "特殊召喚←墓地", llm_check.DIFF_EXCLUSIVE)])

    def test_other_leaf_newly_hit_is_no_longer_exclusive(self):
        diff = llm_check.query_diff(self.cat, ["破壊:モンスター"], ["破壊:モンスター", "破壊@フィールド"], frame())
        self.assertEqual(diff, [("+", "破壊@フィールド", llm_check.DIFF_EXCLUSIVE)])

    def test_head_leaf_lost_is_the_suffix_rule(self):
        diff = llm_check.query_diff(self.cat, ["破壊:モンスター", "破壊@フィールド"], ["破壊@フィールド"], frame())
        self.assertEqual(diff, [("−", "破壊:モンスター", llm_check.DIFF_SUFFIX)])

    def test_same_sets_give_no_diff_and_order_follows_the_hits(self):
        self.assertEqual(llm_check.query_diff(self.cat, ["破壊"], ["破壊"], frame()), [])
        diff = llm_check.query_diff(self.cat, [], ["破壊", "破壊@フィールド"], frame(transfer=TRANSFER_FROM_SOURCE))
        self.assertEqual([name for _s, name, _w in diff], ["破壊", "破壊@フィールド"])

    def test_labels_skip_condition_position_and_add_patient_change(self):
        cat = self.cat
        row = {"card": 1, "section": "main", "index": "①", "order": 0, "queries": ["破壊"]}
        old = {"leaves": []}
        self.assertEqual(llm_check.queries_labels(cat, row, old, frame(position=POS_COND), set()), set())
        self.assertEqual(llm_check.queries_labels(cat, row, old, frame(), set()), {llm_check.DIFF_DEFAULT})
        self.assertEqual(llm_check.queries_labels(cat, row, old, frame(position=POS_COND), {(1, "main", "①", 0)}),
                         {llm_check.STRATUM_PATIENT})

    def test_patient_changed_table_parses_to_frame_keys(self):
        keys = llm_check.patient_changed_keys()
        self.assertEqual(len(keys), len(llm_check.PATIENT_CHANGED))
        self.assertIn((5997110, "pendulum", "①", 4), keys)
        self.assertIn((4628897, "main", "①", 1), keys)


class TestSamplingIsDeterministic(unittest.TestCase):
    """同種子同樣本、小層在前且配額大於母體時全取;批次只是樣本的輪流分配,樣本相同批次就相同。"""

    POOLS = {"尾綴": [3, 1, 2], "不再互斥": list(range(10, 40)), "預設葉取消": list(range(100, 200))}
    STRATA = ("尾綴", "不再互斥", "預設葉取消")
    QUOTA = {"尾綴": 16, "不再互斥": 5, "預設葉取消": 4}

    def test_same_seed_same_sample_and_small_stratum_taken_whole(self):
        first = llm_check.pick(20261101, self.POOLS, self.STRATA, self.QUOTA)
        second = llm_check.pick(20261101, self.POOLS, self.STRATA, self.QUOTA)
        self.assertEqual(first, second)
        self.assertEqual([p["card"] for p in first if p["stratum"] == "尾綴"], [1, 2, 3])
        self.assertEqual(Counter(p["stratum"] for p in first), {"尾綴": 3, "不再互斥": 5, "預設葉取消": 4})

    def test_another_seed_changes_the_sample(self):
        a = llm_check.pick(20261101, self.POOLS, self.STRATA, self.QUOTA)
        b = llm_check.pick(20261009, self.POOLS, self.STRATA, self.QUOTA)
        self.assertNotEqual([p["card"] for p in a], [p["card"] for p in b])


class TestCorpusSample(unittest.TestCase):
    """全語料的分層抽樣(round1 的樣本):100 張、各層配額、兩次相同。缺建置產物時略過並印原因。"""

    @classmethod
    def setUpClass(cls):
        missing = [p for p in (llm_check.FRAME_QUERIES, llm_check.FRAME_CATEGORIES, llm_check.FRAMES) if not os.path.exists(p)]
        cls.reason = ("沒有 %s(先跑 frames.py、categories.py、catalog_hits.py)" % "、".join(
            os.path.basename(p) for p in missing)) if missing else ""
        if cls.reason:
            print(cls.reason, file=sys.stderr)

    def test_round1_sample_is_reproducible(self):
        if self.reason:
            self.skipTest(self.reason)
        first = llm_check.sample_queries(20261101)
        second = llm_check.sample_queries(20261101)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 100)
        self.assertEqual(Counter(p["stratum"] for p in first), llm_check.QUOTA_QUERIES)


if __name__ == "__main__":
    unittest.main()
