"""區塊邊界比對報告(接縫三):規則切法對共識集一致幾張、不一致逐張列出、無共識清單、補丁結果;
走 CLI 入口寫出的檔兩次逐位元組相同。"""
import contextlib
import io
import json
import os
import tempfile
import unittest

import build_block_boundaries
from block_boundary_report import compare_boundaries, render_block_boundaries
from block_split import boundary_patch_hash
from test_block_split import SPROUT_BLOCKS, SPROUT_SUPPLEMENT, SPROUT_TEXT
from test_golden import card, faq

SPROUT = 10753491
# 規則會把三句連成一塊(都是動詞句),拆句表說是兩個效果 → 不一致。
TWO_EFFECTS_TEXT = "Aを破壊する。Bを除外する。Cを手札に加える。"
# 素材行 + 召喚條件 + 一個效果:前言不算效果起點,雙方一致。
FUSION_TEXT = ("「A」＋「B」\nこのカードは融合召喚でしか特殊召喚できない。"
               "このカードが戦闘によって相手モンスターを破壊した場合、そのモンスターを除外する。")


def split_record(cid, segments, ja_order=None):
    record = {"id": cid, "section": "main", "ticket": "票1", "text_hash": "0" * 16,
              "segments": [{"index": index, "text_zh": "", "text_ja": text}
                           for index, text in segments]}
    if ja_order is not None:
        record["ja_order"] = ja_order
    return record


def fixtures():
    cards = [card(SPROUT, name_ja="森羅の神芽 スプラウト", name_zh="森羅的神芽 幼苗"),
             card(1, name_ja="二效果卡"), card(2, name_ja="融合卡"),
             card(3, name_ja="語序卡"), card(4, name_ja="無紀錄卡"),
             card(5, name_ja="無共識卡", name_zh="無共識"), card(6, name_ja="無共識無日文")]
    entries = [
        faq(SPROUT, "森羅の神芽 スプラウト", SPROUT_TEXT),
        faq(1, "二效果卡", TWO_EFFECTS_TEXT),
        faq(2, "融合卡", FUSION_TEXT),
        faq(3, "語序卡", "Aを破壊する。また、Bを除外する。"),
        faq(4, "無紀錄卡", "Aを破壊する。"),
        faq(5, "無共識卡", "Aを破壊する。"),
    ]
    entries[0]["supplement"] = SPROUT_SUPPLEMENT
    splits = [
        split_record(SPROUT, [("1", SPROUT_BLOCKS[0]),
                              ("2", SPROUT_BLOCKS[1] + "「森羅の神芽 スプラウト」のこの効果は１ターンに１度しか使用できない。")]),
        split_record(1, [("1", "Aを破壊する。"), ("2", "Bを除外する。Cを手札に加える。")]),
        split_record(2, [("0", "「A」＋「B」\nこのカードは融合召喚でしか特殊召喚できない。"),
                         ("1", "このカードが戦闘によって相手モンスターを破壊した場合、そのモンスターを除外する。")]),
        # 繁中順序與日文相反,ja_order 說日文先讀第 1 段。
        split_record(3, [("2", "また、Bを除外する。"), ("1", "Aを破壊する。")], ja_order=[1, 0]),
    ]
    consensus = {"full_agree": [SPROUT, 1, 2, 3, 4], "no_consensus": [5, 6]}
    return cards, entries, splits, consensus


class CompareBoundariesTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.entries, cls.splits, cls.consensus = fixtures()
        cls.report = compare_boundaries(cls.entries, cls.consensus, cls.splits,
                                        [], cls.cards)

    def test_agreement_counts_and_disagreements_listed_with_both_sides(self):
        report = self.report
        self.assertEqual(report["consensus_total"], 5)
        self.assertEqual(report["compared"], 5)
        self.assertEqual(report["agree"], 3)  # スプラウト、融合卡、語序卡
        bad = {r["id"]: r for r in report["disagree"]}
        self.assertEqual(sorted(bad), [1, 4])
        self.assertEqual([kind for kind, _, _ in bad[1]["rule"]], ["編號效果"])
        self.assertEqual([(idx, pos) for idx, _, pos in bad[1]["consensus"]],
                         [("1", 0), ("2", 7)])
        self.assertEqual(bad[4]["reason"], "拆句表無紀錄")

    def test_preamble_and_omitted_limit_are_not_effect_starts(self):
        """素材、召喚條件、次數限制兩側都不算效果起點:融合卡與スプラウト一致。"""
        agreed = {r["id"] for r in self.report["disagree"]}
        self.assertNotIn(2, agreed)
        self.assertNotIn(SPROUT, agreed)

    def test_no_consensus_list_carries_names_even_without_official_text(self):
        self.assertEqual(self.report["no_consensus"], [
            {"id": 5, "name_ja": "無共識卡", "name_zh": "無共識"},
            {"id": 6, "name_ja": "無共識無日文", "name_zh": "卡6"}])

    def test_patch_statuses_are_reported_and_patched_card_agrees(self):
        patches = [
            {"id": 1, "text_hash": boundary_patch_hash(TWO_EFFECTS_TEXT),
             "blocks": ["Aを破壊する。", "Bを除外する。Cを手札に加える。"]},
            {"id": 4, "text_hash": "deadbeefdeadbeef", "blocks": ["Aを破壊する。"]},
            {"id": 7, "text_hash": "deadbeefdeadbeef", "blocks": ["Aを破壊する。"]},
        ]
        report = compare_boundaries(self.entries, self.consensus, self.splits,
                                    patches, self.cards)
        self.assertEqual(report["patches"],
                         {"生效": [1], "卡文已變動": [4], "無官方日文": [7]})
        self.assertEqual(report["agree"], 4)
        self.assertEqual([r["id"] for r in report["disagree"]], [4])

    def test_render_lists_everything_without_timestamps(self):
        text = render_block_boundaries(self.report)
        self.assertIn("| 一致 | 3 |", text)
        self.assertIn("| 不一致 | 2 |", text)
        self.assertIn("| 無共識(交站主判) | 2 |", text)
        self.assertIn("- `1` 二效果卡", text)
        self.assertIn("規則:`[編號效果]` " + TWO_EFFECTS_TEXT, text)
        self.assertIn("共識:`[2]` Bを除外する。Cを手札に加える。", text)
        self.assertIn("- `4` 無紀錄卡(拆句表無紀錄)", text)
        self.assertIn("| 5 | 無共識卡 | 無共識 |", text)
        self.assertIn("| 6 | 無共識無日文 | 卡6 |", text)
        self.assertNotIn("2026", text)
        self.assertEqual(text, render_block_boundaries(compare_boundaries(
            list(reversed(self.entries)), self.consensus,
            list(reversed(self.splits)), [], self.cards)))


class CliTest(unittest.TestCase):

    def setUp(self):
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()
        self.addCleanup(self._quiet.__exit__, None, None, None)

    def _write(self, tmp, name, payload):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False)
        return path

    def test_cli_writes_identical_report_twice(self):
        cards, entries, splits, consensus = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "block_boundaries.md")
            argv = ["--cards", self._write(tmp, "cards.json", cards),
                    "--faq", self._write(tmp, "faq_info.json", entries),
                    "--splits", self._write(tmp, "clause_splits.json", splits),
                    "--consensus", self._write(tmp, "consensus.json", consensus),
                    "--boundaries", os.path.join(tmp, "missing.json"),
                    "--out", out]
            self.assertEqual(build_block_boundaries.main(argv), 0)
            with open(out, "rb") as f:
                first = f.read()
            self.assertEqual(build_block_boundaries.main(argv), 0)
            with open(out, "rb") as f:
                second = f.read()
            self.assertEqual(first, second)
            self.assertNotIn(b"\r\n", first)
            text = first.decode("utf-8")
            self.assertIn("沒有邊界補丁", text)
            self.assertIn("| 一致 | 3 |", text)
            self.assertEqual(build_block_boundaries.main(argv + ["--no-write"]), 0)

    def test_cli_fails_without_official_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build_block_boundaries.main(
                ["--faq", os.path.join(tmp, "missing.json")]), 1)


if __name__ == "__main__":
    unittest.main()
