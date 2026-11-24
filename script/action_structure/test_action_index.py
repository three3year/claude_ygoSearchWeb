import contextlib
import copy
import io
import json
import os
import tempfile
import unittest

import build_action_index as cli
from action_index import build_action_index, decode_action_index, web_vocab
from action_rows import flatten
from card_structure import build_structures, serialize_structures
from test_effect_reference import (ARCHETYPES_13, BLACK_HOLE, BLACK_HOLE_TEXT, FRESHIA,
                                   FRESHIA_TEXT, NARAKU, NARAKU_TEXT, NORMAL_SPELL, NORMAL_TRAP,
                                   OTOSHIANA, OTOSHIANA_TEXT, XYZ_MONSTER)
from test_embedded_effects import BRAVE_STRIX, BRAVE_STRIX_TEXT
from test_golden import (EMPEROR_PENGUIN, EMPEROR_PENGUIN_TEXT, ODD_EYES_PEN_EFFECT,
                         ODD_EYES_PENDULUM_DRAGON, ODD_EYES_TEXT, PENGUIN_SOLDIER,
                         SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT, SPROUT, SPROUT_TEXT, card, faq)

NO_TEXT_CARD = 30000002


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
        sizes = {len(c) for segs in decoded.values() for lines in segs.values()
                 for c in lines if c is not None}
        self.assertIn(0, sizes)
        self.assertIn(1, sizes)
        self.assertGreaterEqual(max(sizes), len(self.cards) // 2)

    def test_reference_rows_round_trip(self):
        ref, = self.index["cards"][FRESHIA]["references"]
        expected, = [r for refs in self.rows.references.values() for r in refs]
        self.assertEqual(ref["candidates"], frozenset(expected.candidates))
        self.assertEqual(ref["candidates"], {OTOSHIANA, NARAKU})
        self.assertEqual(ref["effect"], {"part": "卡片發動"})
        self.assertFalse(ref["generic"])

    def test_unresolved_rows_round_trip(self):
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
        self.assertEqual(sorted(self.index["no_text"]), sorted([NO_TEXT_CARD, PENGUIN_SOLDIER]))

    def test_archetype_members(self):
        archetypes = self.index["archetypes"]
        self.assertEqual(archetypes[0x5a]["members"], {EMPEROR_PENGUIN, PENGUIN_SOLDIER})
        self.assertEqual(archetypes[0x5a]["name"], "企鵝")
        self.assertEqual(archetypes[0x4c]["members"], {OTOSHIANA, NARAKU})
        self.assertNotIn(0x1bc, archetypes)

    def test_given_values_come_from_the_canon(self):
        given = self.index["given"]
        self.assertEqual(given["cat"], {"m": "怪獸", "s": "魔法", "t": "陷阱"})
        self.assertEqual(given["attr"]["earth"], "地")
        self.assertEqual(given["attr"]["dark"], "闇")
        self.assertEqual(given["race"]["dragon"], "ドラゴン族")
        self.assertEqual(given["race"]["cyberse"], "サイバース族")
        self.assertEqual((len(given["attr"]), len(given["race"])), (7, 26))

    def test_canon_code_without_a_condition_value_fails(self):
        domains = dict(web_vocab.DOMAINS)
        domains[web_vocab.ATTR] = web_vocab.domain("屬性", web_vocab.SRC_BIT, (
            *web_vocab.entries(web_vocab.ATTR), web_vocab.entry("void", "虛", 0x80)))
        _, report = build_action_index(self.structures, self.cards, self.frontend,
                                       ARCHETYPES_13, domains=domains)
        self.assertEqual(len(report["problems"]), 1)
        self.assertIn("void", report["problems"][0])

    def test_action_words_carry_row_counts(self):
        destroy_rows = sum(1 for row in self.rows.rows if "破壞" in row.actions)
        self.assertGreater(destroy_rows, 0)
        self.assertEqual(self.index["actions"]["破壞"], destroy_rows)

    def test_same_input_same_bytes(self):
        text, _ = build_action_index(copy.deepcopy(self.structures), copy.deepcopy(self.cards),
                                     copy.deepcopy(self.frontend), ARCHETYPES_13)
        self.assertEqual(text, self.text)

    def test_frontend_order_is_the_card_order(self):
        text, report = build_action_index(self.structures, self.cards,
                                          list(reversed(self.frontend)), ARCHETYPES_13)
        self.assertEqual(report["problems"], [])
        index = decode_action_index(text)
        self.assertEqual(index["ids"], [entry["id"] for entry in reversed(self.frontend)])
        self.assertEqual(index["cards"], self.index["cards"])
        self.assertEqual(index["archetypes"], self.index["archetypes"])

    def test_card_missing_from_frontend_fails(self):
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

    def test_no_treated_names_section_is_empty(self):
        self.assertEqual(self.index["treated_names"], {})


class TreatedNamesTest(unittest.TestCase):
    """「當作的卡名」一節:每張有當作卡名的卡 → 對到的卡號與對不到卡的日文字面(票 06)。"""

    def test_treated_names_round_trip(self):
        from test_name_contains_query import (CITY, GLOW, OMOI, SAVIOR, TWINKLE,
                                              treated_fixture)
        cards, entries = treated_fixture()
        structures, _ = build_structures(cards, entries, archetypes=[])
        text, report = build_action_index(structures, cards,
                                          [{"id": entry["id"]} for entry in cards], [])
        self.assertEqual(report["problems"], [])
        self.assertEqual(decode_action_index(text)["treated_names"],
                         {OMOI: {"ids": [SAVIOR], "literals": []},
                          CITY: {"ids": [], "literals": ["海"]},
                          TWINKLE: {"ids": [GLOW], "literals": []}})
        self.assertIn("treatedNames", report["section_bytes"])


def clause(index, text_ja, section="main"):
    return {"index": index, "section": section, "text_ja": text_ja, "text_zh": f"句{index}"}


def mapping_fixture():
    cards = [
        card(ODD_EYES_PENDULUM_DRAGON, name_ja="オッドアイズ・ペンデュラム・ドラゴン",
             type=0x1000021, level=7, race=0x2000, attribute=0x20, scale=4),
        card(SPROUT, name_ja="森羅の神芽 スプラウト", level=1, race=0x400),
        card(BRAVE_STRIX, name_ja="RR－ブレイブ・ストリクス", type=0x800021, level=5,
             race=0x200, attribute=0x20, atk=2000, **{"def": 2500}, setcode=0xba),
        card(FRESHIA, name_ja="フレシアの蟲惑魔", type=XYZ_MONSTER, level=4, race=0x400,
             attribute=0x1, atk=300, **{"def": 2500}, setcode=0x108a),
        card(OTOSHIANA, name_ja="落とし穴", type=NORMAL_TRAP, setcode=0x4c),
        card(NARAKU, name_ja="奈落の落とし穴", type=NORMAL_TRAP, setcode=0x4c),
    ]
    cards.sort(key=lambda entry: entry["id"])
    structures, _ = build_structures(cards, [
        faq(ODD_EYES_PENDULUM_DRAGON, "オッドアイズ・ペンデュラム・ドラゴン", ODD_EYES_TEXT,
            pen_effect=ODD_EYES_PEN_EFFECT),
        faq(SPROUT, "森羅の神芽 スプラウト", SPROUT_TEXT),
        faq(BRAVE_STRIX, "RR－ブレイブ・ストリクス", BRAVE_STRIX_TEXT),
        faq(FRESHIA, "フレシアの蟲惑魔", FRESHIA_TEXT),
        faq(OTOSHIANA, "落とし穴", OTOSHIANA_TEXT),
        faq(NARAKU, "奈落の落とし穴", NARAKU_TEXT),
    ], archetypes=ARCHETYPES_13)
    pen_lines = ODD_EYES_PEN_EFFECT.split("\n")
    strix_lines = BRAVE_STRIX_TEXT.split("\n")
    freshia_lines = FRESHIA_TEXT.split("\n")
    tag_cards = [
        {"id": ODD_EYES_PENDULUM_DRAGON, "clauses": [
            clause("0", pen_lines[0], "pendulum"),
            clause("①", pen_lines[1], "pendulum"),
            clause("②", pen_lines[2], "pendulum"),
            clause("①", ODD_EYES_TEXT),
            clause("②", "②：このカードは主文の②ではない。")]},
        {"id": SPROUT, "clauses": [
            clause("0", "このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚まで"
                        "めくる事ができる。"),
            clause("1", "めくったカードの中に植物族モンスターがあった場合、それらのモンスターを全て"
                        "墓地へ送る。残りのカードは好きな順番でデッキの一番下に戻す。"),
            clause("2", "また、デッキのこのカードがカードの効果によってめくられて墓地へ送られた"
                        "場合、デッキから植物族・レベル１モンスター１体を特殊召喚できる。"),
            clause("3", "「森羅の神芽 スプラウト」のこの効果は１ターンに１度しか使用できない。")]},
        {"id": BRAVE_STRIX, "clauses": [
            clause("0", strix_lines[0]), clause("0", strix_lines[1]),
            clause("①", strix_lines[2]), clause("②", strix_lines[3]),
            clause("③", strix_lines[4]), clause("③-●1", strix_lines[5])]},
        {"id": FRESHIA, "clauses": [clause("0", freshia_lines[0])]
         + [clause(line[0], line) for line in freshia_lines[1:]]},
        {"id": OTOSHIANA, "clauses": [clause("0", "相手が召喚した時に発動できる。")]},
    ]
    frontend = [{"id": entry["id"]} for entry in cards]
    for entry in frontend:
        clauses = next((t["clauses"] for t in tag_cards if t["id"] == entry["id"]), [])
        if clauses:
            entry["tx"] = [c["text_zh"] for c in clauses]
    return structures, cards, frontend, tag_cards


class EffectMappingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.structures, cls.cards, cls.frontend, cls.tag_cards = mapping_fixture()
        cls.text, cls.report = build_action_index(
            cls.structures, cls.cards, cls.frontend, ARCHETYPES_13, tag_cards=cls.tag_cards)
        cls.index = decode_action_index(cls.text)

    def clauses(self, cid):
        return {seg["id"]: seg["clause"] for seg in self.index["cards"][cid]["segments"]}

    def test_builds_without_problems(self):
        self.assertEqual(self.report["problems"], [])

    def test_numbered_pendulum_block_maps_to_the_pendulum_clause(self):
        self.assertEqual(self.clauses(ODD_EYES_PENDULUM_DRAGON),
                         {"p72.s2": 2, "p72.s18": 2, "p72.s28": 2})

    def test_unnumbered_segments_map_by_position(self):
        self.assertEqual(self.clauses(SPROUT), {
            "b0.s0": 0, "b0.s17": 0,
            "b0.s44": 1, "b0.s69": 1, "b0.s87": 1,
            "b111.s3": 2, "b111.s38": 2})

    def test_embedded_segment_counts_on_its_block(self):
        clauses = self.clauses(BRAVE_STRIX)
        self.assertEqual(clauses["b185e39.s1"], 5)
        self.assertEqual(clauses["b49.s25"], 2)
        self.assertEqual(clauses["b108.s51"], 3)

    def test_reference_row_counts_on_the_referencing_effect(self):
        ref, = self.index["cards"][FRESHIA]["references"]
        self.assertEqual(ref["clause"], 3)

    def test_unmapped_segments_are_left_empty_and_reported(self):
        for cid in (OTOSHIANA, NARAKU):
            self.assertTrue(self.clauses(cid))
            self.assertEqual(set(self.clauses(cid).values()), {None})
        mapping = self.report["clause_mapping"]
        self.assertEqual(mapping["unmapped_cards"], [OTOSHIANA, NARAKU])
        unmapped = len(self.clauses(OTOSHIANA)) + len(self.clauses(NARAKU))
        self.assertEqual(mapping["unmapped"], unmapped)
        self.assertEqual(self.clauses(BRAVE_STRIX)["b0.s0"], 0)
        self.assertEqual(self.clauses(FRESHIA)["b0.s0"], 0)
        self.assertEqual(mapping["by_position"], 9)
        segments = sum(len(entry["segments"]) for entry in self.index["cards"].values())
        self.assertEqual(mapping["by_number"] + mapping["by_position"] + mapping["unmapped"],
                         segments)
        self.assertEqual((mapping["references"], mapping["unmapped_references"]), (1, 0))

    def test_clause_count_mismatch_fails(self):
        frontend = copy.deepcopy(self.frontend)
        sprout = next(entry for entry in frontend if entry["id"] == SPROUT)
        sprout["tx"].pop()
        text, report = build_action_index(self.structures, self.cards, frontend,
                                          ARCHETYPES_13, tag_cards=self.tag_cards)
        self.assertIsNone(text)
        self.assertEqual(len(report["problems"]), 1)
        self.assertIn("效果句數", report["problems"][0])
        self.assertIn(str(SPROUT), report["problems"][0])

    def test_same_input_same_bytes(self):
        text, _ = build_action_index(copy.deepcopy(self.structures), copy.deepcopy(self.cards),
                                     copy.deepcopy(self.frontend), ARCHETYPES_13,
                                     tag_cards=copy.deepcopy(self.tag_cards))
        self.assertEqual(text, self.text)


class CommandLineTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        structures, cards, frontend, tag_cards = mapping_fixture()
        cls.tmp = tempfile.TemporaryDirectory()
        cls.paths = {name: os.path.join(cls.tmp.name, name) for name in
                     ("structures.json", "cards.json", "data.js", "archetypes.json",
                      "tag_cards.json")}
        texts = {
            "structures.json": serialize_structures(structures),
            "cards.json": json.dumps(cards, ensure_ascii=False),
            "data.js": ("window.CARD_DATA=[\n" + ",\n".join(map(json.dumps, frontend))
                        + "\n];\nwindow.VOCAB={\n};\n"),
            "archetypes.json": json.dumps(ARCHETYPES_13, ensure_ascii=False),
            "tag_cards.json": json.dumps(tag_cards, ensure_ascii=False),
        }
        for name, text in texts.items():
            with open(cls.paths[name], "w", encoding="utf-8") as f:
                f.write(text)
        cls.expected, _ = build_action_index(structures, cards, frontend, ARCHETYPES_13,
                                             tag_cards=tag_cards)

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
                "--archetypes", self.paths["archetypes.json"],
                "--tags", self.paths["tag_cards.json"], "-o", output, *extra])
        written = None
        if os.path.exists(output):
            with open(output, encoding="utf-8", newline="") as f:
                written = f.read()
        return code, out.getvalue(), written

    def test_writes_the_index_and_prints_the_report(self):
        code, printed, written = self.run_cli()
        self.assertEqual(code, 0)
        self.assertEqual(written, self.expected)
        for label in ("列 ", "候選卡集合", "產物", "gzip", "時間", "讀檔", "攤平", "候選卡 ",
                      "tag_cards.json digest="):
            self.assertIn(label, printed)

    def test_report_lists_unmapped_segments_and_cards(self):
        code, printed, _ = self.run_cli("--no-write")
        self.assertEqual(code, 0)
        line = next(line for line in printed.splitlines() if line.startswith("效果對應"))
        self.assertIn("靠位置 9", line)
        self.assertIn("留空 ", line)
        unmapped = next(line for line in printed.splitlines() if line.startswith("留空的卡"))
        self.assertIn(f"{OTOSHIANA}, {NARAKU}", unmapped)

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
