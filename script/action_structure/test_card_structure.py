"""建置管線與 CLI 薄殼:產物一卡一行、同一輸入兩次逐位元組相同、抽不出的不中斷建置。"""
import contextlib
import io
import json
import os
import tempfile
import unittest

import build_structure
from action_query import run_query
from card_structure import (build_structures, load_structures,
                            serialize_structures)
from test_golden import (ARCHETYPES, SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT,
                         SPELL, card, faq)

OLD_STYLE_TEXT = (
    "このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚までめくる事"
    "ができる。めくったカードの中に植物族モンスターがあった場合、それらのモンスターを"
    "全て墓地へ送る。")
FUSION_TEXT = (
    "「ブラック・マジシャン」＋光・闇属性モンスター\n"
    "①：このカードが特殊召喚した場合に発動できる。「ブラック・マジシャン」１体を"
    "デッキから手札に加える。")
PENDULUM_TEXT = "①：自分フィールドのモンスターの攻撃力は３００アップする。"


def fixtures():
    cards = [
        card(SINGULARITY_FIEND, name_ja="特異点の悪魔", level=1, race=0x40),
        card(10753491, name_ja="森羅の神芽 スプラウト", level=1, race=0x400),
        card(59400890, name_ja="滅びの黒魔術師", level=8, type=0x61),
        card(94415058, name_ja="靈擺測試卡", type=0x1000021, scale=4),
        card(20240828, name_ja="デコピン", type=SPELL),  # 無官方日文
    ]
    entries = [
        faq(SINGULARITY_FIEND, "特異点の悪魔", SINGULARITY_FIEND_TEXT),
        faq(10753491, "森羅の神芽 スプラウト", OLD_STYLE_TEXT),
        faq(59400890, "滅びの黒魔術師", FUSION_TEXT),
        faq(94415058, "靈擺測試卡", "①：このカードを破壊する。",
            pen_effect=PENDULUM_TEXT),
    ]
    return cards, entries


class BuildStructuresTest(unittest.TestCase):

    def test_same_input_builds_byte_identical_output(self):
        """輸入順序打亂、建兩次,序列化後逐位元組相同;時間雜湊不進產物。"""
        cards, entries = fixtures()
        first, _ = build_structures(cards, entries, built_at="2026-11-07T00:00:00")
        second, _ = build_structures(list(reversed(cards)),
                                     list(reversed(entries)),
                                     built_at="2026-11-08T12:34:56")
        self.assertEqual(serialize_structures(first).encode("utf-8"),
                         serialize_structures(second).encode("utf-8"))

    def test_one_card_per_line_sorted_by_id_without_escapes(self):
        cards, entries = fixtures()
        structures, _ = build_structures(cards, entries)
        text = serialize_structures(structures)
        lines = text.split("\n")
        self.assertEqual(len(lines), len(cards) + 3)  # [、每卡一行、]、結尾空行
        self.assertEqual(lines[0], "[")
        self.assertEqual(lines[-2], "]")
        self.assertNotIn("\\u", text)
        ids = [c["id"] for c in json.loads(text)]
        self.assertEqual(ids, sorted(ids))

    def test_serialized_product_loads_back_to_the_same_structure(self):
        """產物省略空格,讀回補齊後與建置結果相等,再序列化也逐位元組相同。"""
        cards, entries = fixtures()
        structures, _ = build_structures(cards, entries)
        text = serialize_structures(structures)
        loaded = load_structures(text)
        self.assertEqual(loaded, structures)
        self.assertEqual(serialize_structures(loaded), text)
        self.assertEqual(
            run_query(loaded, cards, {"actions": ["捨棄"],
                                      "card": SINGULARITY_FIEND})["groups"],
            run_query(structures, cards, {"actions": ["捨棄"],
                                          "card": SINGULARITY_FIEND})["groups"])

    def test_card_without_official_text_is_unparsed_with_reason(self):
        """沒有官方日文的卡:整張標未解析、原因「無官方日文」,查詢不會命中它。"""
        cards, entries = fixtures()
        structures, report = build_structures(cards, entries)
        deco = next(c for c in structures if c["id"] == 20240828)
        self.assertEqual(deco["unparsed"], {"reason": "無官方日文"})
        self.assertEqual(report["no_official_text"], [20240828])
        self.assertEqual(
            run_query(structures, cards, {"actions": []})["groups"]["全部"]
            .count(20240828), 0)

    def test_unparsable_text_does_not_abort_build(self):
        """舊式無編號卡、素材行、靈擺效果:抽不出的區塊與段標原因,建置照常。"""
        cards, entries = fixtures()
        structures, report = build_structures(cards, entries)
        by_id = {c["id"]: c for c in structures}
        old = by_id[10753491]["blocks"]
        self.assertEqual([(b["kind"], b["label"], b["unparsed"]) for b in old],
                         [("編號效果", None, None)])
        fusion = by_id[59400890]["blocks"]
        self.assertEqual([b["unparsed"] and b["unparsed"]["reason"]
                          for b in fusion], ["區塊種類判不出", None])
        pendulum = by_id[94415058]["blocks"]
        self.assertEqual([b["kind"] for b in pendulum], ["編號效果", "靈擺效果"])
        self.assertGreater(report["unparsed_segments"], 0)
        self.assertEqual(report["cards"], len(cards))


class CliTest(unittest.TestCase):
    """走 CLI 入口:讀兩份檔、寫產物;兩次寫出的檔逐位元組相同。"""

    def setUp(self):
        # 報告印到 stdout,測試時收進緩衝區免得淹掉測試輸出。
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()
        self.addCleanup(self._quiet.__exit__, None, None, None)

    def test_cli_writes_identical_file_twice(self):
        cards, entries = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            cards_path = os.path.join(tmp, "cards.json")
            faq_path = os.path.join(tmp, "faq_info.json")
            out_path = os.path.join(tmp, "action_structure.json")
            for path, payload in ((cards_path, cards), (faq_path, entries)):
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(payload, f, ensure_ascii=False)
            argv = ["--cards", cards_path, "--faq", faq_path, "-o", out_path]
            self.assertEqual(build_structure.main(argv), 0)
            with open(out_path, "rb") as f:
                first = f.read()
            self.assertEqual(build_structure.main(argv), 0)
            with open(out_path, "rb") as f:
                second = f.read()
            self.assertEqual(first, second)
            self.assertNotIn(b"\r\n", first)
            self.assertEqual(len(json.loads(first.decode("utf-8"))), len(cards))

    def test_cli_no_write_leaves_no_file(self):
        cards, entries = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            cards_path = os.path.join(tmp, "cards.json")
            faq_path = os.path.join(tmp, "faq_info.json")
            out_path = os.path.join(tmp, "action_structure.json")
            for path, payload in ((cards_path, cards), (faq_path, entries)):
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    json.dump(payload, f, ensure_ascii=False)
            self.assertEqual(build_structure.main(
                ["--cards", cards_path, "--faq", faq_path, "-o", out_path,
                 "--no-write"]), 0)
            self.assertFalse(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
