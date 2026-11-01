# -*- coding: utf-8 -*-
"""LLM 抽驗讀具名查詢目錄與命中(named-queries 票 10;規格 4 票 08 起不再對照舊歸葉)的行為測試。

接縫:llm_check.hit_reasons(目錄, 命中, 框架) → 逐名的命中來由(分層讀它);lemma_node_of(目錄, 命中) → 批次檔分組的詞元節點;
pick(種子, 母體, 層, 配額) → 樣本(決定性);sample_queries/sample_categories(種子) 與兩支寫批次檔 → 全語料跑一次
(缺命中中間產物時 skipTest 並印原因)。只斷言來由清單、樣本的鍵與層、批次檔帶了什麼,不斷言排版。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import json
import os
import sys
import tempfile
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import llm_check  # noqa: E402
from closed_values import TRANSFER_FROM_SOURCE  # noqa: E402
from constraints import POS_COND, POS_EFFECT  # noqa: E402
from test_08_hits import SMALL  # noqa: E402


def frame(**fields):
    """一個動作框架(只給分層讀的鍵)。"""
    return dict({"kind": "動作", "position": POS_EFFECT}, **fields)


class TestHitReasons(unittest.TestCase):
    """命中的逐名來由:詞元節點 / 取自來源 / 回指回填 / 中心詞 / 區域,前面的優先。"""

    def setUp(self):
        self.cat = catalog.Catalog(SMALL)

    def reasons(self, queries, **fields):
        return llm_check.hit_reasons(self.cat, queries, frame(**fields))

    def test_lemma_node_hit_is_its_own_reason(self):
        self.assertEqual(self.reasons(["破壊"]), [("破壊", llm_check.HIT_NODE)])
        self.assertEqual(self.reasons(["破壊(耐性)"]), [("破壊(耐性)", llm_check.HIT_NODE)])

    def test_place_query_hit_through_transfer_from_source(self):
        self.assertEqual(self.reasons(["破壊@フィールド"], transfer=TRANSFER_FROM_SOURCE),
                         [("破壊@フィールド", llm_check.HIT_KARA)])

    def test_region_query_hit_through_anaphora_backfill(self):
        self.assertEqual(self.reasons(["特殊召喚←墓地"], region_backfill="source"),
                         [("特殊召喚←墓地", llm_check.HIT_BACKFILL)])
        self.assertEqual(self.reasons(["破壊@フィールド"], region_backfill="place"),
                         [("破壊@フィールド", llm_check.HIT_BACKFILL)])

    def test_backfill_into_another_field_does_not_count(self):
        self.assertEqual(self.reasons(["特殊召喚←墓地"], region_backfill="place"),
                         [("特殊召喚←墓地", llm_check.HIT_REGION)])

    def test_head_query_is_read_by_its_suffix_rule(self):
        self.assertEqual(self.reasons(["破壊:モンスター"]), [("破壊:モンスター", llm_check.HIT_HEAD)])

    def test_order_follows_the_hits(self):
        found = self.reasons(["破壊", "破壊@フィールド"], transfer=TRANSFER_FROM_SOURCE)
        self.assertEqual([name for name, _why in found], ["破壊", "破壊@フィールド"])

    def test_labels_cover_every_position_and_add_patient_change(self):
        row = {"card": 1, "section": "main", "index": "①", "order": 0, "queries": ["破壊"]}
        self.assertEqual(llm_check.queries_labels(self.cat, row, frame(position=POS_COND), set()), {llm_check.HIT_NODE})
        self.assertEqual(llm_check.queries_labels(self.cat, row, frame(), {(1, "main", "①", 0)}),
                         {llm_check.HIT_NODE, llm_check.STRATUM_PATIENT})
        self.assertEqual(llm_check.queries_labels(self.cat, dict(row, queries=[]), frame(), set()), set())

    def test_patient_changed_table_parses_to_frame_keys(self):
        keys = llm_check.patient_changed_keys()
        self.assertEqual(len(keys), len(llm_check.PATIENT_CHANGED))
        self.assertIn((5997110, "pendulum", "①", 4), keys)
        self.assertIn((4628897, "main", "①", 1), keys)


class TestLemmaNodeGrouping(unittest.TestCase):
    """批次檔依框架命中的第一個詞元節點分組;節點的清單是節點自己與底下全部具名查詢(目錄序)。"""

    def setUp(self):
        self.cat = catalog.Catalog(SMALL)

    def test_first_lemma_node_among_the_hits(self):
        self.assertEqual(llm_check.lemma_node_of(self.cat, ["破壊", "破壊@フィールド"]).name, "破壊")
        self.assertEqual(llm_check.lemma_node_of(self.cat, ["破壊(耐性)"]).name, "破壊(耐性)")

    def test_no_lemma_node_among_the_hits(self):
        self.assertIsNone(llm_check.lemma_node_of(self.cat, []))
        self.assertIsNone(llm_check.lemma_node_of(self.cat, ["破壊@フィールド"]))

    def test_node_lines_list_the_node_and_its_children_with_predicates(self):
        lines = llm_check.node_lines(self.cat.by_name["特殊召喚"])
        self.assertEqual(len(lines), 3)
        self.assertIn("**特殊召喚←墓地**", lines[1])
        self.assertIn("來源=(不限,墓地)", lines[1])


class TestSamplingIsDeterministic(unittest.TestCase):
    """同種子同樣本、小層在前且配額大於母體時全取;批次只是樣本的輪流分配,樣本相同批次就相同。"""

    POOLS = {"中心詞": [3, 1, 2], "區域": list(range(10, 40)), "詞元節點": list(range(100, 200))}
    STRATA = ("中心詞", "區域", "詞元節點")
    QUOTA = {"中心詞": 16, "區域": 5, "詞元節點": 4}

    def test_same_seed_same_sample_and_small_stratum_taken_whole(self):
        first = llm_check.pick(20261101, self.POOLS, self.STRATA, self.QUOTA)
        second = llm_check.pick(20261101, self.POOLS, self.STRATA, self.QUOTA)
        self.assertEqual(first, second)
        self.assertEqual([p["card"] for p in first if p["stratum"] == "中心詞"], [1, 2, 3])
        self.assertEqual(Counter(p["stratum"] for p in first), {"中心詞": 3, "區域": 5, "詞元節點": 4})

    def test_another_seed_changes_the_sample(self):
        a = llm_check.pick(20261101, self.POOLS, self.STRATA, self.QUOTA)
        b = llm_check.pick(20261009, self.POOLS, self.STRATA, self.QUOTA)
        self.assertNotEqual([p["card"] for p in a], [p["card"] for p in b])


class TestCorpusSample(unittest.TestCase):
    """全語料跑一次:兩條線的樣本可重現、批次檔真的寫得出來(只讀目錄與 frame_queries.json)。缺建置產物時略過並印原因。"""

    @classmethod
    def setUpClass(cls):
        missing = [p for p in (llm_check.FRAME_QUERIES, llm_check.FRAMES) if not os.path.exists(p)]
        cls.reason = ("沒有 %s(先跑 frames.py、catalog_hits.py)" % "、".join(
            os.path.basename(p) for p in missing)) if missing else ""
        if cls.reason:
            print(cls.reason, file=sys.stderr)

    def setUp(self):
        if self.reason:
            self.skipTest(self.reason)

    def read(self, root, name):
        with open(os.path.join(root, name), encoding="utf-8") as f:
            return f.read()

    def test_query_sample_is_reproducible_and_fills_every_quota(self):
        first = llm_check.sample_queries(20261101)
        self.assertEqual(first, llm_check.sample_queries(20261101))
        self.assertEqual(len(first), 100)
        self.assertEqual(Counter(p["stratum"] for p in first), llm_check.QUOTA_QUERIES)

    def test_query_batches_carry_hits_and_patient_without_the_old_leaves(self):
        picked = llm_check.sample_queries(20261101)
        with tempfile.TemporaryDirectory() as root:
            llm_check.write_query_batches(root, picked, {"batches": 4})
            batch = self.read(root, "batch-0.md")
            self.assertIn("命中=", batch)
            self.assertIn("動作對象=", batch)
            self.assertNotIn("舊歸葉", batch)
            self.assertIn("**破壊@フィールド**", self.read(root, "catalog.md"))

    def test_category_sample_draws_from_every_query_and_the_unhit_frames(self):
        first = llm_check.sample_categories(20261102)
        self.assertEqual(first, llm_check.sample_categories(20261102))
        strata = Counter(p["stratum"] for p in first)
        self.assertEqual(strata[llm_check.STRATUM_NO_HIT], llm_check.NO_HIT_QUOTA)
        self.assertLessEqual(max(n for name, n in strata.items() if name != llm_check.STRATUM_NO_HIT),
                             llm_check.PER_QUERY)
        self.assertLessEqual(set(strata) - {llm_check.STRATUM_NO_HIT}, set(catalog.load().by_name))
        self.assertEqual(len({llm_check.frame_key(p) for p in first}), len(first))

    def test_category_batches_and_tree_read_the_catalog(self):
        picked = llm_check.sample_categories(20261102)
        with tempfile.TemporaryDirectory() as root:
            llm_check.write_category_batches(root, picked, {"batches": 8})
            tree = self.read(root, "tree.md")
            for query in catalog.load().queries:
                self.assertIn("**%s**" % query.name, tree)
            text = "".join(self.read(root, "batch-%d.md" % k) for k in range(8))
            self.assertEqual(text.count("### 樣本 "), len(picked))
            self.assertIn("命中 → ", text)
            self.assertIn("沒命中", text)

    def test_category_report_shows_the_current_hits(self):
        picked = llm_check.sample_categories(20261102)
        sample = picked[0]
        with tempfile.TemporaryDirectory() as root:
            llm_check.write_sample_meta(root, picked, {"seed": 20261102, "batches": 1,
                                                       "error_types": list(llm_check.ERROR_TYPES_CATEGORY)})
            with open(os.path.join(root, "findings-0.json"), "w", encoding="utf-8") as f:
                json.dump([{"sample": sample["id"], "type": llm_check.ERROR_TYPES_CATEGORY[0], "expected": [],
                            "cause": llm_check.CATEGORY_CAUSES[0], "reason": "測試"}], f)
            llm_check.report_categories(root)
            self.assertIn(sample["stratum"], self.read(root, "report.md"))


if __name__ == "__main__":
    unittest.main()
