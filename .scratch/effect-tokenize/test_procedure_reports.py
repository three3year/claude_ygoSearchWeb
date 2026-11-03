# -*- coding: utf-8 -*-
"""報表與拆解頁分得出召喚手續(summon-procedure 票 04)。

接縫:report.position_items(位置 Counter) → 照位置清單排的 (位置, 框數)——分詞報表「位置分佈」與拆解頁覆蓋分頁
共用;phrases.quantity_section(紀錄) → 片語報表數量小節的行;report.queries_section(目錄, 命中) → 報告小節的行;
prepare_view.query_overview / frame_row → 拆解頁資料;viewer.html 的圖例(頁面看得到的字)。
位置欄的順序一律照 constraints.POSITIONS(召喚手續最後),不照字串排序。資料都是合成的,不讀全語料。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import os
import re
import sys
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import phrases  # noqa: E402
import prepare_view  # noqa: E402
import report  # noqa: E402
import test_09_viewer  # noqa: E402
from constraints import POS_COND, POS_COST, POS_EFFECT, POS_PROCEDURE, POSITIONS  # noqa: E402


class TestPositionItems(unittest.TestCase):
    """位置分佈照位置清單排:召喚手續在最後(字串排序會把它排第二);沒有框的位置記 0。"""

    def test_procedure_comes_last_not_in_string_order(self):
        counts = Counter({POS_EFFECT: 5, POS_PROCEDURE: 2, POS_COST: 3, POS_COND: 1})
        self.assertEqual(report.position_items(counts),
                         [(POS_COST, 3), (POS_EFFECT, 5), (POS_COND, 1), (POS_PROCEDURE, 2)])

    def test_a_position_without_frames_is_zero(self):
        self.assertEqual(report.position_items(Counter({POS_EFFECT: 4})),
                         [(POS_COST, 0), (POS_EFFECT, 4), (POS_COND, 0), (POS_PROCEDURE, 0)])


def quantity_frame(position):
    """帶一段數量(１体)的動作框架,只有數量小節讀的鍵。"""
    return {"kind": "動作", "position": position, "phrases": {"object": {"segments": [
        {"text": "モンスター１体", "quantity": {"kind": "個數", "from_clause": False}}]}}}


class TestQuantitySection(unittest.TestCase):
    """片語報表「數量各類框數」那一行:帶數量的動作框架數照位置清單各列一格,召喚手續最後。"""

    def test_the_line_lists_every_position_with_procedure_last(self):
        records = [{"frames": [quantity_frame(POS_EFFECT), quantity_frame(POS_PROCEDURE),
                               quantity_frame(POS_PROCEDURE), quantity_frame(POS_COST)]}]
        line = phrases.quantity_section(records)[0]
        self.assertTrue(line.startswith("帶數量的動作框架 4(代價 1、效果 1、條件 0、召喚手續 2);"), line)


# 卡 4 的召喚條件句:召喚手續位的 破壊 框命中 破壊、破壊:モンスター(合成;小目錄沒有除外節點,借破壊類)
PROCEDURE_HIT = {"card": 4, "section": "main", "index": "0-2", "order": 2, "position": POS_PROCEDURE,
                 "text": "モンスター１体を破壊した場合", "queries": ["破壊", "破壊:モンスター"], "patient": "非此卡"}


class TestQueriesSection(unittest.TestCase):
    """分詞報表「具名查詢目錄」小節:命中分佈與動作對象表多一欄召喚手續;說明不寫死位置個數。"""

    def section(self):
        return "\n".join(report.queries_section(test_09_viewer.small(), test_09_viewer.HITS + [PROCEDURE_HIT]))

    def test_distribution_has_a_procedure_column_before_the_total(self):
        text = self.section()
        self.assertIn("| 命中數 | 代價 | 效果 | 條件 | 召喚手續 | 合計 |", text)
        self.assertIn("| 2 | 1 | 1 | 0 | 1 | 3 |", text)
        self.assertIn("| 非此卡 | 0 | 1 | 0 | 1 | 2 |", text)

    def test_text_names_positions_from_the_position_list(self):
        text = self.section()
        self.assertIn("每個位置(代價、效果、條件、召喚手續)都算", text)
        self.assertIn("不留(每個位置都沒命中)1 個:破壊(耐性)", text)
        self.assertNotIn("三個位置", text)


class TestViewerData(unittest.TestCase):
    """拆解頁資料:召喚手續框的位置值照帶到框架列;總覽的位置欄與命中分佈多一格召喚手續,合計在最後一格。"""

    def test_procedure_frame_row_carries_its_position(self):
        fr = {"kind": "動作", "sentence": 0, "action": "除外", "object": "モンスター１体", "source": None,
              "goal": None, "position": POS_PROCEDURE, "polarity": "肯定", "option": None, "label": None,
              "span": [0, 3], "clause": "モンスター１体を除外した", "order": 2}
        self.assertEqual(prepare_view.frame_row(fr, None, [], ["非此卡", "受事者是卡片群體"])[1], POS_PROCEDURE)

    def test_overview_has_a_procedure_column_and_the_total_last(self):
        table, shards = prepare_view.query_overview(test_09_viewer.small(), test_09_viewer.HITS + [PROCEDURE_HIT])
        self.assertEqual(table["positions"], list(POSITIONS))
        self.assertEqual(table["positions"][-1], POS_PROCEDURE)
        self.assertEqual(test_09_viewer.node(table["nodes"], "小目錄", "破壊", "破壊:モンスター")[1:4],
                         [4, [0, 2, 0, 1, 3], [0, 2, 0, 1, 3]])
        self.assertEqual(table["hits"][POS_PROCEDURE], [0, 0, 1, 0])
        rows = {key: rows for shard in shards for key, rows in shard.items()}
        self.assertIn([4, "main", "0-2", 2, POS_PROCEDURE, "モンスター１体を破壊した場合"], rows["q4"])


VIEWER = os.path.join(HERE, "viewer.html")


class TestViewerLegend(unittest.TestCase):
    """拆解頁圖例(頁面看得到的字):每個位置一顆 chip、樣式各不相同,召喚手續不落到效果的樣式;
    每個位置的樣式在 CSS 裡有定義。"""

    def legend(self):
        with open(VIEWER, encoding="utf-8") as f:
            html = f.read()
        body = html[html.index('<div class="legend">'):]
        body = body[:body.index("</div>")]
        return html, dict((text, cls) for cls, text in re.findall(r'<span class="chip (f-[a-z]+)">([^<]+)</span>', body))

    def test_every_position_has_its_own_legend_style(self):
        html, chips = self.legend()
        for pos in POSITIONS:
            self.assertIn(pos, chips)
        styles = [chips[pos] for pos in POSITIONS]
        self.assertEqual(len(set(styles)), len(POSITIONS), styles)
        for cls in styles:
            self.assertIn("." + cls + "{", html)


if __name__ == "__main__":
    unittest.main()
