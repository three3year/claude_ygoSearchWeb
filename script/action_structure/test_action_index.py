"""動作索引建置(action-search-web 票 06):接縫二 `build_action_index`。

輸入卡片結構、卡片總表、前端索引(卡的順序)與字段表,輸出動作索引的文字與報告。
不斷言編碼:產物一律用 `decode_action_index` 讀回,比的是讀回來的卡、列與候選卡。
"""
import contextlib
import copy
import io
import json
import os
import tempfile
import unittest

import build_action_index as cli
from action_index import build_action_index, decode_action_index
from action_rows import flatten
from card_structure import build_structures, serialize_structures
from test_effect_reference import (ARCHETYPES_13, BLACK_HOLE, BLACK_HOLE_TEXT, FRESHIA,
                                   FRESHIA_TEXT, NARAKU, NARAKU_TEXT, NORMAL_SPELL, NORMAL_TRAP,
                                   OTOSHIANA, OTOSHIANA_TEXT, XYZ_MONSTER)
from test_golden import (EMPEROR_PENGUIN, EMPEROR_PENGUIN_TEXT, PENGUIN_SOLDIER,
                         SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT, card, faq)

NO_TEXT_CARD = 30000002   # 測試用:卡片總表有、官方 DB 文本沒有


def fixture():
    cards = [
        card(SINGULARITY_FIEND, name_ja="特異点の悪魔", level=1, race=0x40),
        card(EMPEROR_PENGUIN, name_ja="大皇帝ペンギン", level=5, race=0x40,
             attribute=0x2, setcode=0x5a),
        card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", level=2, race=0x40,
             attribute=0x2, setcode=0x5a),
        card(FRESHIA, name_ja="フレシアの蟲惑魔", type=XYZ_MONSTER, level=4, race=0x400,
             attribute=0x1, atk=300, **{"def": 2500}, setcode=0x108a),
        card(OTOSHIANA, name_ja="落とし穴", type=NORMAL_TRAP, setcode=0x4c),
        card(NARAKU, name_ja="奈落の落とし穴", type=NORMAL_TRAP, setcode=0x4c),
        card(BLACK_HOLE, name_ja="ブラック・ホール", type=NORMAL_SPELL),
        card(NO_TEXT_CARD, name_ja="テキストなし"),
    ]
    cards.sort(key=lambda entry: entry["id"])
    structures, _ = build_structures(cards, [
        faq(SINGULARITY_FIEND, "特異点の悪魔", SINGULARITY_FIEND_TEXT),
        faq(EMPEROR_PENGUIN, "大皇帝ペンギン", EMPEROR_PENGUIN_TEXT),
        faq(FRESHIA, "フレシアの蟲惑魔", FRESHIA_TEXT),
        faq(OTOSHIANA, "落とし穴", OTOSHIANA_TEXT),
        faq(NARAKU, "奈落の落とし穴", NARAKU_TEXT),
        faq(BLACK_HOLE, "ブラック・ホール", BLACK_HOLE_TEXT),
    ], archetypes=ARCHETYPES_13)
    frontend = [{"id": entry["id"]} for entry in cards]
    return structures, cards, frontend


def ids_of(cards, mask):
    return frozenset(entry["id"] for i, entry in enumerate(cards) if mask >> i & 1)


class ActionIndexTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.structures, cls.cards, cls.frontend = fixture()
        cls.text, cls.report = build_action_index(
            cls.structures, cls.cards, cls.frontend, ARCHETYPES_13)
        cls.index = decode_action_index(cls.text)
        cls.rows = flatten(cls.structures, cls.cards)

    def test_builds_without_problems(self):
        self.assertEqual(self.report["problems"], [])

    def test_line_candidates_round_trip(self):
        """每條對象線的候選卡:從產物讀回來,和攤平算出來的是同一批卡。"""
        expected = {}
        for row in self.rows.rows:
            lines = expected.setdefault(row.card, {}).setdefault(row.segment, [])
            if row.line is not None:
                obj = row.line.object
                lines.append(None if obj is None else ids_of(self.cards, obj.candidates.mask))
        decoded = {cid: {seg["id"]: [None if line["object"] is None
                                     else line["object"]["candidates"]
                                     for line in seg["lines"]]
                         for seg in entry["segments"]}
                   for cid, entry in self.index["cards"].items() if entry["segments"]}
        self.assertEqual(decoded, expected)
        # 夾具裡要真的有大的、小的與空的候選卡集合,三種存法都走過。
        sizes = {len(c) for segs in decoded.values() for lines in segs.values()
                 for c in lines if c is not None}
        self.assertIn(0, sizes)
        self.assertIn(1, sizes)
        self.assertGreaterEqual(max(sizes), len(self.cards) // 2)

    def test_reference_rows_round_trip(self):
        """フレシアの蟲惑魔 ③ 的引用列:被引用物件的候選卡與指定的部分(卡片發動)讀得回來。"""
        ref, = self.index["cards"][FRESHIA]["references"]
        expected, = [r for refs in self.rows.references.values() for r in refs]
        self.assertEqual(ref["candidates"], frozenset(expected.candidates))
        self.assertEqual(ref["candidates"], {OTOSHIANA, NARAKU})
        self.assertEqual(ref["effect"], {"part": "卡片發動"})
        self.assertFalse(ref["generic"])

    def test_unresolved_rows_round_trip(self):
        """未解析組的來源:字面含動作詞的都讀得回來(段類別、極性、四種原因旗標、字面動作詞)。"""
        expected = sorted(
            (s.card, s.kind, s.polarity, bool(s.reason), bool(s.reason_substituting),
             tuple(sorted(s.literal_actions)))
            for s in self.rows.unresolved if s.literal_actions)
        decoded = sorted(
            (cid, u["kind"], u["polarity"], u["reason"], u["reason_substituting"],
             tuple(sorted(u["literal_actions"])))
            for cid, entry in self.index["cards"].items() for u in entry["unresolved"])
        self.assertEqual(decoded, expected)

    def test_no_text_cards_are_listed(self):
        """ペンギン・ソルジャー 與測試用的卡都沒有官方 DB 文本。"""
        self.assertEqual(sorted(self.index["no_text"]), sorted([NO_TEXT_CARD, PENGUIN_SOLDIER]))

    def test_archetype_members(self):
        """字段與它的成員卡(照卡片屬性表):企鵝、落穴;沒有成員的字段不列。"""
        archetypes = self.index["archetypes"]
        self.assertEqual(archetypes[0x5a]["members"], {EMPEROR_PENGUIN, PENGUIN_SOLDIER})
        self.assertEqual(archetypes[0x5a]["name"], "企鵝")
        self.assertEqual(archetypes[0x4c]["members"], {OTOSHIANA, NARAKU})
        self.assertNotIn(0x1bc, archetypes)

    def test_action_words_carry_row_counts(self):
        """動作詞的清單帶列數(介面選項依列數排)。"""
        destroy_rows = sum(1 for row in self.rows.rows if "破壞" in row.actions)
        self.assertGreater(destroy_rows, 0)
        self.assertEqual(self.index["actions"]["破壞"], destroy_rows)

    def test_same_input_same_bytes(self):
        """同樣的輸入(另一份複本)兩次產出逐位元組相同。"""
        text, _ = build_action_index(copy.deepcopy(self.structures), copy.deepcopy(self.cards),
                                     copy.deepcopy(self.frontend), ARCHETYPES_13)
        self.assertEqual(text, self.text)

    def test_frontend_order_is_the_card_order(self):
        """前端索引的卡順序和卡片總表不同時,候選卡照樣讀回同一批卡。"""
        text, report = build_action_index(self.structures, self.cards,
                                          list(reversed(self.frontend)), ARCHETYPES_13)
        self.assertEqual(report["problems"], [])
        index = decode_action_index(text)
        self.assertEqual(index["ids"], [entry["id"] for entry in reversed(self.frontend)])
        self.assertEqual(index["cards"], self.index["cards"])
        self.assertEqual(index["archetypes"], self.index["archetypes"])

    def test_card_missing_from_frontend_fails(self):
        """卡片結構的卡不在前端索引裡:建置失敗,問題寫出卡號。"""
        frontend = [entry for entry in self.frontend if entry["id"] != FRESHIA]
        text, report = build_action_index(self.structures, self.cards, frontend, ARCHETYPES_13)
        self.assertIsNone(text)
        self.assertTrue(report["problems"])
        self.assertIn(str(FRESHIA), report["problems"][0])

    def test_over_the_size_limit_fails(self):
        text, report = build_action_index(self.structures, self.cards, self.frontend,
                                          ARCHETYPES_13, size_limit=100)
        self.assertEqual(len(report["problems"]), 1)
        self.assertIn("超過門檻", report["problems"][0])
        self.assertEqual(report["bytes"], len(text.encode("utf-8")))

    def test_report(self):
        """報告:列數、各種列的數量、集合的數量與大小、產物體積、各階段時間。"""
        report = self.report
        self.assertEqual(report["rows"], len(self.rows.rows))
        self.assertEqual(report["references"], 1)
        self.assertEqual(report["no_text"], 2)
        self.assertEqual(report["unresolved"], len(self.rows.unresolved))
        self.assertGreater(report["sets"], 0)
        self.assertEqual(report["list_sets"] + report["bitset_sets"], report["sets"])
        self.assertEqual(report["bytes"], len(self.text.encode("utf-8")))
        self.assertLess(0, report["gzip_bytes"])
        self.assertLess(report["gzip_bytes"], report["bytes"])
        self.assertEqual(set(report["timings"]), {"攤平", "候選卡", "編碼"})



class CommandLineTest(unittest.TestCase):
    """建置入口:讀檔、寫檔、印報告;只驗證不寫檔的模式;建置失敗時不寫檔、結束碼非 0。"""

    @classmethod
    def setUpClass(cls):
        structures, cards, frontend = fixture()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = {name: os.path.join(cls.tmp.name, name) for name in
                     ("structures.json", "cards.json", "data.js", "archetypes.json")}
        texts = {
            "structures.json": serialize_structures(structures),
            "cards.json": json.dumps(cards, ensure_ascii=False),
            "data.js": ("window.CARD_DATA=[\n" + ",\n".join(map(json.dumps, frontend))
                        + "\n];\nwindow.VOCAB={\n};\n"),
            "archetypes.json": json.dumps(ARCHETYPES_13, ensure_ascii=False),
        }
        for name, text in texts.items():
            with open(cls.paths[name], "w", encoding="utf-8") as f:
                f.write(text)
        cls.expected, _ = build_action_index(structures, cards, frontend, ARCHETYPES_13)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_cli(self, *extra):
        output = os.path.join(self.tmp.name, "action-data.js")
        if os.path.exists(output):
            os.remove(output)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main([
                "--structures", self.paths["structures.json"],
                "--cards", self.paths["cards.json"], "--frontend", self.paths["data.js"],
                "--archetypes", self.paths["archetypes.json"], "-o", output, *extra])
        written = None
        if os.path.exists(output):
            with open(output, encoding="utf-8", newline="") as f:
                written = f.read()
        return code, out.getvalue(), written

    def test_writes_the_index_and_prints_the_report(self):
        code, printed, written = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(written, self.expected)
        for label in ("列 ", "候選卡集合", "產物", "gzip", "時間", "讀檔", "攤平", "候選卡 "):
            self.assertIn(label, printed)

    def test_no_write_only_checks(self):
        code, printed, written = self.run_cli("--no-write")
        self.assertEqual(code, 0)
        self.assertIsNone(written)
        self.assertIn("全部檢查通過", printed)

    def test_over_the_size_limit_fails_without_writing(self):
        code, printed, written = self.run_cli("--size-limit", "100")
        self.assertEqual(code, 1)
        self.assertIsNone(written)
        self.assertIn("超過門檻", printed)


if __name__ == "__main__":
    unittest.main()
