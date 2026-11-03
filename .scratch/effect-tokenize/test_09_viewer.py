# -*- coding: utf-8 -*-
"""拆解頁總覽與報告小節的行為測試(named-queries 票 09)。

接縫兩個:prepare_view.query_overview(目錄, 每框的命中) → (總覽表, 分片)——每個具名查詢三個位置的框數/卡數、
大類/中類是底下具名查詢的聯集(由樹推得)、展開看框架的分片列;report.queries_section(目錄, 命中紀錄) → 報告
小節的行(節點數、三個位置的命中框數分佈、不留清單)。另:拆解頁每框的列帶命中的具名查詢號與動作對象。
只斷言總覽列、分片列、報告的行,不斷言樹怎麼存、分片怎麼分。小目錄與幾個框的命中都是合成的,不讀全語料。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import catalog  # noqa: E402
import prepare_view  # noqa: E402
import report  # noqa: E402
from constraints import POS_COND, POS_COST, POS_EFFECT, POS_PROCEDURE  # noqa: E402
from test_07_catalog import major, query  # noqa: E402

# 小目錄:大類 小目錄 列中類 墓地系;特殊召喚 的兩片葉宣告中類(路徑走 中類、不掛詞元節點);破壊 三片葉;
# 破壊(耐性) 在合成的命中裡沒有框(不留清單要列它)
SMALL = {"樹": [major("小目錄", [
    query("特殊召喚", [
        query("特殊召喚", 來源=[[None, "墓地"]], 中類="墓地系"),
        query("特殊召喚", 來源=[[None, "墓地"]], 受事者中心詞=["モンスター"], 中類="墓地系"),
    ]),
    query("破壊", [
        query("破壊", 受事者中心詞=["モンスター"]),
        query("破壊", 所在=[[None, "場上"]]),
        query("破壊", 否定形=["受身", "不成不受"]),
    ]),
], middles=["墓地系"])]}

# 合成的命中(frame_queries.json 一框一列的形狀,多帶子句原文):卡 1 兩框、卡 2 兩框(一框沒命中)、卡 3 一框
HITS = [
    {"card": 1, "section": "main", "index": "①", "order": 0, "position": POS_EFFECT,
     "text": "モンスター１体を破壊する", "queries": ["破壊", "破壊:モンスター"], "patient": "非此卡"},
    {"card": 1, "section": "main", "index": "①", "order": 1, "position": POS_COST,
     "text": "墓地から特殊召喚する", "queries": ["特殊召喚", "特殊召喚←墓地"], "patient": "此卡"},
    {"card": 2, "section": "main", "index": "①", "order": 0, "position": POS_EFFECT,
     "text": "フィールドのモンスターを破壊する", "queries": ["破壊", "破壊:モンスター", "破壊@フィールド"]},
    {"card": 2, "section": "main", "index": "②", "order": 0, "position": POS_COND,
     "text": "ドローした場合", "queries": []},
    {"card": 3, "section": "pendulum", "index": "①", "order": 0, "position": POS_EFFECT,
     "text": "墓地からモンスターを特殊召喚する", "queries": ["特殊召喚", "特殊召喚←墓地", "特殊召喚←墓地:モンスター"]},
]
NAMES = ["特殊召喚", "特殊召喚←墓地", "特殊召喚←墓地:モンスター", "破壊", "破壊:モンスター", "破壊@フィールド", "破壊(耐性)"]


def small():
    return catalog.Catalog(SMALL)


def overview():
    return prepare_view.query_overview(small(), HITS)


def node(rows, *names):
    """總覽樹依名字往下找節點列 [名, 查詢號, 框數, 卡數, 子]。"""
    found = None
    for name in names:
        found = next(n for n in rows if n[0] == name)
        rows = found[4]
    return found


class TestQueryOverview(unittest.TestCase):
    """具名查詢總覽:每個具名查詢各位置(代價/效果/條件/召喚手續)加合計的框數與卡數;大類/中類是聯集。"""

    def test_query_names_and_paths_follow_the_catalog_order(self):
        table, _ = overview()
        self.assertEqual(table["names"], NAMES)
        self.assertEqual(table["paths"][1], ["小目錄", "墓地系", "特殊召喚←墓地"])
        self.assertEqual(table["paths"][4], ["小目錄", "破壊", "破壊:モンスター"])

    def test_a_query_counts_frames_and_cards_per_position(self):
        """破壊:モンスター 命中卡 1、卡 2 各一框(效果位);合計欄是各位置的聯集。"""
        table, _ = overview()
        self.assertEqual(node(table["nodes"], "小目錄", "破壊", "破壊:モンスター")[1:4],
                         [4, [0, 2, 0, 0, 2], [0, 2, 0, 0, 2]])
        self.assertEqual(node(table["nodes"], "小目錄", "破壊", "破壊@フィールド")[1:4],
                         [5, [0, 1, 0, 0, 1], [0, 1, 0, 0, 1]])
        self.assertEqual(node(table["nodes"], "小目錄", "破壊", "破壊(耐性)")[1:4],
                         [6, [0, 0, 0, 0, 0], [0, 0, 0, 0, 0]])

    def test_a_lemma_node_is_a_query_with_its_own_hits(self):
        """詞元節點就是具名查詢(沒有預設葉):特殊召喚 命中卡 1 代價位與卡 3 效果位;兩片葉宣告了中類,
        不掛在它底下。"""
        table, _ = overview()
        row = node(table["nodes"], "小目錄", "特殊召喚")
        self.assertEqual(row[1:4], [0, [1, 1, 0, 0, 2], [1, 1, 0, 0, 2]])
        self.assertEqual(row[4], [])

    def test_major_and_middle_counts_are_unions_of_their_queries(self):
        """中類 墓地系 = 特殊召喚←墓地 ∪ 特殊召喚←墓地:モンスター;大類 = 全部具名查詢的聯集,一框多命中只算一次;
        條件位沒命中的框不算進任何節點。"""
        table, _ = overview()
        top = node(table["nodes"], "小目錄")
        self.assertEqual(top[1:4], [-1, [1, 3, 0, 0, 4], [1, 3, 0, 0, 3]])
        self.assertEqual([child[0] for child in top[4]], ["墓地系", "特殊召喚", "破壊"])
        middle = node(table["nodes"], "小目錄", "墓地系")
        self.assertEqual(middle[1:4], [-1, [1, 1, 0, 0, 2], [1, 1, 0, 0, 2]])
        self.assertEqual([child[0] for child in middle[4]], ["特殊召喚←墓地", "特殊召喚←墓地:モンスター"])

    def test_expanding_a_query_lists_its_frames_in_corpus_order(self):
        """分片列 [卡號, 段落, 句序, 框架序, 位置, 子句原文],鍵 q<查詢號>;沒有框的具名查詢沒有分片。"""
        table, shards = overview()
        rows = {key: rows for shard in shards for key, rows in shard.items()}
        self.assertEqual(rows["q0"], [[1, "main", "①", 1, POS_COST, "墓地から特殊召喚する"],
                                      [3, "pendulum", "①", 0, POS_EFFECT, "墓地からモンスターを特殊召喚する"]])
        self.assertEqual(rows["q4"], [[1, "main", "①", 0, POS_EFFECT, "モンスター１体を破壊する"],
                                      [2, "main", "①", 0, POS_EFFECT, "フィールドのモンスターを破壊する"]])
        self.assertNotIn("q6", rows)
        self.assertEqual(set(table["shard_of"]), {"q0", "q1", "q2", "q3", "q4", "q5"})
        self.assertEqual(shards[table["shard_of"]["q4"]]["q4"], rows["q4"])

    def test_dashboard_counts_nodes_and_hit_distribution(self):
        """儀表板:節點數(頂層/中類/具名查詢/詞元節點——述詞只有詞元或詞元加否定形的具名查詢,破壊(耐性) 也算)
        與各位置的命中框數分佈(命中 0/1/2/3+ 個具名查詢的框數)。"""
        table, _ = overview()
        self.assertEqual([table["majors"], table["middles"], table["queries"], table["lemma_nodes"]], [1, 1, 7, 3])
        self.assertEqual(table["frames"], 5)
        self.assertEqual(table["hits"], {POS_COST: [0, 0, 1, 0], POS_EFFECT: [0, 0, 1, 2], POS_COND: [1, 0, 0, 0],
                                        POS_PROCEDURE: [0, 0, 0, 0]})


class TestFrameRow(unittest.TestCase):
    """卡片拆解每框的列:命中的具名查詢號清單(f[14])與動作對象 [值, 理由](f[22]);約束框架沒有這兩欄。"""

    def test_action_frame_carries_query_numbers_and_patient_mode(self):
        fr = {"kind": "動作", "sentence": 0, "action": "破壊", "object": "モンスター", "source": None, "goal": None,
              "position": POS_EFFECT, "polarity": "肯定", "option": None, "label": None, "span": [0, 3],
              "clause": "モンスター を 破壊 する", "order": 0}
        row = prepare_view.frame_row(fr, None, [3, 4], ["非此卡", "受事者是卡片群體"])
        self.assertEqual(row[14], [3, 4])
        self.assertEqual(row[22], ["非此卡", "受事者是卡片群體"])

    def test_constraint_frame_has_no_query_columns(self):
        fr = {"kind": "約束", "sentence": 0, "category": "限制", "subtype": "次數", "polarity": None,
              "option": None, "label": None, "span": [0, 2], "clause": "１ターンに１度", "order": 0,
              "count": 1, "window": "ターン", "turn_condition": None, "event": None, "scope": None,
              "action": None, "names": None, "object": None}
        row = prepare_view.frame_row(fr, None, None, None)
        self.assertEqual(len(row), 15)


class TestReportSection(unittest.TestCase):
    """報告的「具名查詢目錄」小節。"""

    def test_section_lists_node_counts_distribution_and_unmatched_queries(self):
        lines = report.queries_section(small(), HITS)
        text = "\n".join(lines)
        self.assertEqual(lines[0], "## 具名查詢目錄(named-queries)")
        self.assertIn("頂層 1(大類 1、自成大類的具名查詢 0)、中類 1、具名查詢 7(詞元節點 3、葉 4)", text)
        self.assertIn("| 0 | 0 | 0 | 1 | 0 | 1 |", text)
        self.assertIn("| 2 | 1 | 1 | 0 | 0 | 2 |", text)
        self.assertIn("| 3+ | 0 | 2 | 0 | 0 | 2 |", text)
        self.assertIn("不留(三個位置都沒命中)1 個:破壊(耐性)", text)
        self.assertIn("### 動作對象(此卡/非此卡/皆非)框數分位置", text)
        self.assertIn("| 此卡 | 1 | 0 | 0 | 0 | 1 |", text)
        self.assertIn("| 非此卡 | 0 | 1 | 0 | 0 | 1 |", text)
        self.assertIn("| 皆非 | 0 | 2 | 1 | 0 | 3 |", text)

    def test_section_says_none_when_every_query_hits(self):
        hits = HITS + [{"card": 4, "section": "main", "index": "①", "order": 0, "position": POS_EFFECT,
                        "text": "破壊されない", "queries": ["破壊(耐性)"]}]
        self.assertIn("不留(三個位置都沒命中):無", "\n".join(report.queries_section(small(), hits)))


if __name__ == "__main__":
    unittest.main()
