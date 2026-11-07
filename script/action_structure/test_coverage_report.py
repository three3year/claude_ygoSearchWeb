"""覆蓋報告(票 03):張數加總等於卡片總表張數、依區塊種類/段類別/各格計數、
依原因附卡號、無官方日文整張列出;CLI 兩次產出逐位元組相同。"""
import contextlib
import io
import json
import os
import tempfile
import unittest

import build_report
from card_structure import build_structures, serialize_structures
from coverage_report import build_coverage, render_coverage
from test_card_structure import fixtures
from test_golden import SINGULARITY_FIEND, card


class BuildCoverageTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards, entries = fixtures()
        cls.structures, _ = build_structures(cls.cards, entries)
        cls.coverage = build_coverage(cls.structures)

    def test_card_counts_add_up_to_card_list(self):
        """有卡片結構的張數 + 無官方日文的張數 = 卡片總表張數。"""
        cov = self.coverage
        self.assertEqual(cov["cards"], len(self.cards))
        self.assertEqual(cov["with_structure"] + len(cov["no_official_text"]),
                         cov["cards"])
        self.assertEqual(cov["no_official_text"], [20240828])

    def test_blocks_by_kind_and_unparsed_reasons_with_card_ids(self):
        blocks = self.coverage["blocks"]
        self.assertEqual(blocks["parsed"] + blocks["unparsed"], blocks["total"])
        self.assertEqual(blocks["by_kind"]["靈擺效果"]["blocks"], 1)
        self.assertEqual(blocks["by_kind"]["靈擺效果"]["cards"], 1)
        self.assertEqual(sum(k["blocks"] for k in blocks["by_kind"].values()),
                         blocks["total"])
        self.assertEqual(blocks["reasons"]["區塊種類判不出"]["cards"],
                         [59400890])
        # 舊式無編號卡沒有標解析不出的區塊。
        self.assertNotIn(10753491, sum((r["cards"] for r in blocks["reasons"].values()), []))
        self.assertEqual(sum(r["blocks"] for r in blocks["reasons"].values()),
                         blocks["unparsed"])

    def test_segments_by_kind_and_unparsed_reasons_with_card_ids(self):
        segments = self.coverage["segments"]
        self.assertEqual(segments["parsed"] + segments["unparsed"],
                         segments["total"])
        self.assertEqual(sum(k["segments"] for k in segments["by_kind"].values()),
                         segments["total"])
        # 特異点の悪魔:條件、代價、效果各一段,全部解析出。
        for kind in ("條件", "代價", "效果"):
            self.assertGreaterEqual(segments["by_kind"][kind]["parsed"], 1)
        self.assertEqual(sum(r["segments"] for r in segments["reasons"].values()),
                         segments["unparsed"])
        for reason in segments["reasons"].values():
            self.assertEqual(reason["cards"], sorted(set(reason["cards"])))
            self.assertNotIn(SINGULARITY_FIEND, reason["cards"])

    def test_segment_fields_counted_over_parsed_segments(self):
        """各格的有值/留空/解析不出只對解析出的段計數(段整段解析不出已依原因列過)。"""
        fields = self.coverage["fields"]
        parsed = self.coverage["segments"]["parsed"]
        for name, cell in fields.items():
            self.assertEqual(cell["filled"] + cell["empty"] + cell["unparsed"],
                             parsed, name)
        # 存在前提的條件段(「めくったカードの中に植物族モンスターがあった場合」)沒有動作詞,留空。
        self.assertEqual(fields["actions"]["filled"] + fields["actions"]["empty"], parsed)
        self.assertEqual(fields["actions"]["unparsed"], 0)
        self.assertEqual(fields["trigger"]["filled"],
                         self.coverage["segments"]["by_kind"]["條件"]["parsed"])

    def test_line_positions_by_source(self):
        """從/到依來源(明寫、繼承、推得、留空)計數,加總等於對象線數。"""
        positions = self.coverage["positions"]
        for side in ("from", "to"):
            self.assertEqual(sum(positions[side].values()),
                             self.coverage["lines"])
        self.assertGreaterEqual(positions["from"]["明寫"], 1)  # 手札から
        self.assertGreaterEqual(positions["to"]["推得"], 1)    # 捨てる → 墓地

    def test_objects_unparsed_reasons_with_card_ids(self):
        objects = self.coverage["objects"]
        self.assertEqual(objects["parsed"] + objects["unparsed"], objects["total"])
        self.assertEqual(sum(r["objects"] for r in objects["reasons"].values()),
                         objects["unparsed"])
        self.assertEqual(objects["by_source"]["自己"], self.coverage["with_structure"])

    def test_unknown_quoted_names_listed_with_card_ids(self):
        """滅びの黒魔術師 的 fixture 引用「ブラック・マジシャン」,而這組 fixture 的總表沒有
        這張卡、也沒給字段表:名稱對不到 → 列進「不認得的「」名稱」附卡號。"""
        self.assertEqual(self.coverage["unknown_names"],
                         {"ブラック・マジシャン": [59400890]})
        text = render_coverage(self.coverage)
        self.assertIn("- 「ブラック・マジシャン」(1 張):`59400890`", text)


class RenderCoverageTest(unittest.TestCase):

    def test_markdown_lists_every_card_id_without_truncation(self):
        """「附卡號」要列全部:60 張無官方日文的卡,每個卡號都在報告裡。"""
        cards = [card(90000000 + i, name_ja=f"無日文{i}") for i in range(60)]
        structures, _ = build_structures(cards, [])
        text = render_coverage(build_coverage(structures))
        for entry in cards:
            self.assertIn(str(entry["id"]), text)
        self.assertIn("卡片總表 60 張", text)
        self.assertIn("無官方日文 60 張", text)

    def test_markdown_has_no_timestamp_and_is_deterministic(self):
        cards, entries = fixtures()
        first = render_coverage(build_coverage(build_structures(cards, entries)[0]))
        second = render_coverage(build_coverage(build_structures(
            list(reversed(cards)), list(reversed(entries)))[0]))
        self.assertEqual(first, second)
        self.assertNotIn("2026", first)


class CliTest(unittest.TestCase):
    """走 CLI 入口:讀產物與卡片總表、寫 md;兩次寫出的檔逐位元組相同。"""

    def setUp(self):
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()
        self.addCleanup(self._quiet.__exit__, None, None, None)

    def _write_inputs(self, tmp, cards, structures):
        structures_path = os.path.join(tmp, "action_structure.json")
        cards_path = os.path.join(tmp, "cards.json")
        with open(structures_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(serialize_structures(structures))
        with open(cards_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cards, f, ensure_ascii=False)
        return structures_path, cards_path

    def test_cli_writes_identical_report_twice(self):
        cards, entries = fixtures()
        structures, _ = build_structures(cards, entries)
        with tempfile.TemporaryDirectory() as tmp:
            structures_path, cards_path = self._write_inputs(tmp, cards, structures)
            out_path = os.path.join(tmp, "report", "coverage.md")
            argv = ["--structures", structures_path, "--cards", cards_path,
                    "--out", out_path]
            self.assertEqual(build_report.main(argv), 0)
            with open(out_path, "rb") as f:
                first = f.read()
            self.assertEqual(build_report.main(argv), 0)
            with open(out_path, "rb") as f:
                second = f.read()
            self.assertEqual(first, second)
            self.assertNotIn(b"\r\n", first)
            text = first.decode("utf-8")
            self.assertIn("卡片總表 5 張", text)
            self.assertIn("無官方日文 1 張", text)
            self.assertIn("20240828", text)
            self.assertIn("區塊種類判不出", text)
            self.assertIn("59400890", text)

    def test_cli_fails_when_product_does_not_cover_card_list(self):
        """產物張數與卡片總表不符:報告的加總對不上,以非 0 結束、不寫檔。"""
        cards, entries = fixtures()
        structures, _ = build_structures(cards, entries)
        with tempfile.TemporaryDirectory() as tmp:
            structures_path, cards_path = self._write_inputs(
                tmp, cards + [card(99999999)], structures)
            out_path = os.path.join(tmp, "coverage.md")
            self.assertEqual(build_report.main(
                ["--structures", structures_path, "--cards", cards_path,
                 "--out", out_path]), 1)
            self.assertFalse(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
