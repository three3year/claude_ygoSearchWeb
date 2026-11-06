"""字段表(票 04):上游 strings.conf 的 !setname → setcode,中文名從同 setcode 卡的繁中
「」引用配對,補丁覆蓋;建置產物一筆一行、同一輸入兩次相同;配不到的列進報告。

fixture 在測試內程式化建立(小 strings.conf 文字與幾張卡),不碰真實資料檔。
"""
import contextlib
import io
import json
import os
import tempfile
import unittest

import build_archetypes
from archetype_table import (archetype_lookup, build_archetypes as build,
                             fold_width, load_archetypes, name_variants,
                             parse_setnames, render_report, serialize_archetypes,
                             setcode_matches, split_setcode)
from test_golden import SPELL, card, faq

CONF = (
    "﻿#The first line is used for comment\n"
    "!system 1 通常召喚\n"
    "#setnames, using tab for comment\n"
    "!setname 0x5a ペンギン\n"
    "!setname 0x7 古代の機械（アンティーク・ギア）\n"
    "!setname 0x46 融合／フュージョン\n"
    "!setname 0x1033 Ａ ＢＦ\tコメント\n"
    "#!setname 0xa2 マジシャン\n"
    "!setname 0x1b1 白き森\n"
    "!setname 0x1bc アザミナ\n"
    "!setname 0x1e2 ＡＮＧＥＬＥＣＨＹ\n"
)

PENGUIN = 6836211
PENGUIN_SOLDIER = 93920745
LISETTE = 38648860
GEAR = 11111111
GEAR_SPELL = 22222222
OTHER = 33333333   # 沒有 0x1e2 的卡,卻引用「ANGELECHY」:全部卡配對的退路


def fixtures():
    cards = [
        card(PENGUIN, name_ja="大皇帝ペンギン", name_zh="大皇帝企鵝", setcode=0x5a,
             desc="①：將此卡解放可以發動。從牌組將「大皇帝企鵝」以外的最多2隻「企鵝」怪獸特殊召喚。"),
        card(PENGUIN_SOLDIER, name_ja="ペンギン・ソルジャー", name_zh="企鵝士兵",
             setcode=0x5a, desc="①：此卡反轉的場合，將1隻「企鵝」怪獸從牌組加入手牌。"),
        card(LISETTE, name_ja="白き森の聖徒リゼット", name_zh="白森林的聖徒 莉賽特",
             setcode=0x1bc01b1,
             desc="①：從手牌將1隻「白森林」怪獸或「聖徒」怪獸特殊召喚。"),
        card(GEAR, name_ja="古代の機械巨人", name_zh="古代的機械巨人", setcode=0x7,
             desc="①：從牌組將1隻「古代的機械」怪獸特殊召喚。"),
        card(GEAR_SPELL, name_ja="古代の機械要塞", name_zh="古代的機械要塞", type=SPELL,
             setcode=0x7,
             desc="①：「古代的機械」怪獸以及記載「古代的機械」的魔法卡。"),
        card(OTHER, name_ja="天使の施し", name_zh="天使的施捨", type=SPELL,
             desc="①：從牌組將1隻「具象天使」怪獸加入手牌。"),
    ]
    entries = [
        faq(PENGUIN, "大皇帝ペンギン",
            "①：このカードをリリースして発動できる。デッキから「大皇帝ペンギン」以外の"
            "「ペンギン」モンスターを２体まで特殊召喚する。"),
        faq(PENGUIN_SOLDIER, "ペンギン・ソルジャー",
            "①：このカードがリバースした場合、デッキから「ペンギン」モンスター１体を手札に加える。"),
        faq(LISETTE, "白き森の聖徒リゼット",
            "①：手札から「白き森」モンスターまたは「アザミナ」モンスター１体を特殊召喚する。"),
        faq(GEAR, "古代の機械巨人",
            "①：デッキから「アンティーク・ギア」モンスター１体を特殊召喚する。"),
        faq(GEAR_SPELL, "古代の機械要塞",
            "①：「アンティーク・ギア」モンスター及び「アンティーク・ギア」のカード名が記された魔法カード。"),
        faq(OTHER, "天使の施し", "①：デッキから「ANGELECHY」モンスター１体を手札に加える。"),
    ]
    return cards, entries


class ParseTest(unittest.TestCase):

    def test_setname_lines_only_with_tab_comment_stripped(self):
        """只收 !setname;名稱後的 tab 是註解;#!setname 是被註解掉的系列,不算。"""
        self.assertEqual(parse_setnames(CONF), [
            (0x5a, "ペンギン"), (0x7, "古代の機械（アンティーク・ギア）"),
            (0x46, "融合／フュージョン"), (0x1033, "Ａ ＢＦ"), (0x1b1, "白き森"),
            (0x1bc, "アザミナ"), (0x1e2, "ＡＮＧＥＬＥＣＨＹ")])

    def test_reading_and_slash_variants(self):
        """「漢字（読み）」與「A／B」兩種寫法都登記,官方卡文用哪一半不固定(筆記 06)。"""
        self.assertEqual(name_variants("古代の機械（アンティーク・ギア）"),
                         ["古代の機械", "アンティーク・ギア"])
        self.assertEqual(name_variants("融合／フュージョン"), ["融合", "フュージョン"])
        self.assertEqual(name_variants("千年/ミレニアム"), ["千年", "ミレニアム"])
        self.assertEqual(name_variants("白き森"), ["白き森"])
        self.assertEqual(name_variants("／バスター"), ["／バスター"])

    def test_fold_width(self):
        self.assertEqual(fold_width("Ａ ＢＦ"), "A BF")
        self.assertEqual(fold_width("Ｅ・ＨＥＲＯ"), "E・HERO")
        self.assertEqual(fold_width("ＳＰＹＲＡＬ　ＧＥＡＲ"), "SPYRAL GEAR")
        self.assertEqual(fold_width("No.１０１"), "No.101")

    def test_setcode_split_and_match(self):
        """cards.json 的 setcode 每 16 位一個系列碼;比對照 ygopro-core:低 12 位是本體、
        高 4 位是子系列旗標(查本體命中子系列的卡,查子系列只命中帶旗標的卡)。"""
        self.assertEqual(split_setcode(0x1bc01b1), [0x1b1, 0x1bc])
        self.assertEqual(split_setcode(0), [])
        self.assertTrue(setcode_matches(0x104f, 0x4f))
        self.assertFalse(setcode_matches(0x4f, 0x104f))
        self.assertTrue(setcode_matches(0x104f, 0x104f))
        self.assertFalse(setcode_matches(0x5a, 0x7))


class BuildTest(unittest.TestCase):

    def setUp(self):
        self.cards, self.entries = fixtures()

    def rows(self, patches=()):
        rows, report = build(parse_setnames(CONF), list(patches), self.cards,
                             self.entries)
        return rows, report

    def test_zh_name_paired_from_same_setcode_cards(self):
        """中文名:同 setcode 的卡,日文「」引用與繁中「」引用依位置配對。"""
        rows, _ = self.rows()
        by_code = {r["setcode"]: r for r in rows}
        self.assertEqual(by_code[0x5a]["name_zh"], "企鵝")
        self.assertEqual(by_code[0x5a]["names_ja"], ["ペンギン"])
        self.assertEqual(by_code[0x1b1]["name_zh"], "白森林")
        self.assertEqual(by_code[0x1bc]["name_zh"], "聖徒")

    def test_reading_variant_pairs_to_zh_name(self):
        """讀音型:卡文寫「アンティーク・ギア」,照樣配到「古代的機械」。"""
        rows, _ = self.rows()
        gear = next(r for r in rows if r["setcode"] == 0x7)
        self.assertEqual(gear["names_ja"], ["古代の機械", "アンティーク・ギア"])
        self.assertEqual(gear["name_zh"], "古代的機械")

    def test_unmatched_rows_are_reported(self):
        """沒有任何卡配得到的字段:name_zh 留 None、列進報告。"""
        rows, report = self.rows()
        unmatched = {r["setcode"] for r in report["unmatched"]}
        self.assertEqual(unmatched, {0x46, 0x1033})
        self.assertIsNone(next(r for r in rows if r["setcode"] == 0x46)["name_zh"])
        self.assertEqual(report["total"], 7)
        self.assertEqual(report["matched"], 5)

    def test_fallback_to_all_cards_when_same_setcode_cards_do_not_quote_it(self):
        """同 setcode 的卡沒引用字段名(ＡＮＧＥＬＥＣＨＹ 只在卡名裡):退而用全部卡的
        成對配到「具象天使」,並列進報告的「用全部卡配對」。"""
        rows, report = self.rows()
        self.assertEqual(next(r for r in rows if r["setcode"] == 0x1e2)["name_zh"],
                         "具象天使")
        self.assertEqual([f["setcode"] for f in report["fallback"]], [0x1e2])

    def test_patch_overrides_zh_adds_missing_and_removes_wrong(self):
        """補丁:蓋中文名、補上游缺漏(新 setcode)、移除上游錯誤的列;套用的記進報告。"""
        patches = [
            {"setcode": "0x1e2", "name_zh": "具象天使 A", "reason": "卡文沒引用字段名"},
            {"setcode": "0x1e3", "names_ja": ["新字段"], "name_zh": "新字段",
             "reason": "上游缺漏"},
            {"setcode": "0x1033", "remove": True, "reason": "上游錯誤"},
        ]
        rows, report = self.rows(patches)
        by_code = {r["setcode"]: r for r in rows}
        self.assertEqual(by_code[0x1e2]["name_zh"], "具象天使 A")
        self.assertEqual(by_code[0x1e2]["source"], "補丁")
        self.assertEqual(report["fallback"], [])
        self.assertEqual(by_code[0x1e3]["names_ja"], ["新字段"])
        self.assertNotIn(0x1033, by_code)
        self.assertEqual([p["setcode"] for p in report["patches"]],
                         [0x1e2, 0x1e3, 0x1033])
        self.assertEqual({r["setcode"] for r in report["unmatched"]}, {0x46})

    def test_bad_patch_is_a_problem(self):
        """補丁欄位不認得、setcode 不是十六進位:進 problems,不靜默略過。"""
        _, report = self.rows([{"setcode": "5a", "name_zh": "企鵝", "reason": "x"},
                               {"setcode": "0x5a", "zh": "企鵝", "reason": "x"}])
        self.assertEqual(len(report["problems"]), 2)

    def test_rows_sorted_and_serialization_stable(self):
        """一筆一行、依 setcode 排序;輸入順序打亂建兩次逐位元組相同;讀回相等。"""
        rows_a, _ = self.rows()
        self.cards.reverse()
        self.entries.reverse()
        rows_b, _ = build(list(reversed(parse_setnames(CONF))), [], self.cards,
                          self.entries)
        text_a, text_b = serialize_archetypes(rows_a), serialize_archetypes(rows_b)
        self.assertEqual(text_a.encode("utf-8"), text_b.encode("utf-8"))
        self.assertEqual([r["setcode"] for r in rows_a],
                         sorted(r["setcode"] for r in rows_a))
        self.assertEqual(len(text_a.splitlines()), len(rows_a) + 2)
        self.assertNotIn("\\u", text_a)
        self.assertEqual(load_archetypes(text_a), rows_a)

    def test_lookup_folds_width_and_keeps_both_variants(self):
        """折疊後的名稱 → setcode 列表:全形 ＡＮＧＥＬＥＣＨＹ 以半形查得到,讀音兩半都查得到。"""
        rows, _ = self.rows()
        lookup = archetype_lookup(rows)
        self.assertEqual(lookup["ANGELECHY"], [0x1e2])
        self.assertEqual(lookup["古代の機械"], [0x7])
        self.assertEqual(lookup["アンティーク・ギア"], [0x7])
        self.assertEqual(lookup["フュージョン"], [0x46])
        self.assertNotIn("ＡＮＧＥＬＥＣＨＹ", lookup)


class CliTest(unittest.TestCase):

    def test_cli_writes_table_and_report_byte_identical_twice(self):
        cards, entries = fixtures()
        with tempfile.TemporaryDirectory() as tmp:
            conf = os.path.join(tmp, "strings.conf")
            with open(conf, "w", encoding="utf-8", newline="\n") as f:
                f.write(CONF)
            paths = {}
            for name, data in (("cards.json", cards), ("faq_info.json", entries),
                               ("patches.json", [{"setcode": "0x1e2",
                                                  "name_zh": "具象天使",
                                                  "reason": "x"}])):
                paths[name] = os.path.join(tmp, name)
                with open(paths[name], "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
            out = os.path.join(tmp, "archetypes.json")
            report = os.path.join(tmp, "archetypes.md")
            argv = ["--strings", conf, "--cards", paths["cards.json"],
                    "--faq", paths["faq_info.json"], "--patches",
                    paths["patches.json"], "-o", out, "--report", report]
            outputs = []
            for _ in range(2):
                with contextlib.redirect_stdout(io.StringIO()) as buf:
                    self.assertEqual(build_archetypes.main(argv), 0)
                with open(out, "rb") as f, open(report, "rb") as r:
                    outputs.append((f.read(), r.read()))
            self.assertEqual(outputs[0], outputs[1])
            self.assertIn("字段 7 筆", buf.getvalue())
            table = load_archetypes(outputs[0][0].decode("utf-8"))
            self.assertEqual(next(r for r in table if r["setcode"] == 0x1e2)["name_zh"],
                             "具象天使")
            md = outputs[0][1].decode("utf-8")
            self.assertIn("0x46", md)         # 配不到中文名的列進報告
            self.assertIn("融合／フュージョン", md)
            self.assertNotIn("2026", md)      # 報告正文不寫時間


class ReportTest(unittest.TestCase):

    def test_report_lists_unmatched_ambiguous_and_patches(self):
        md = render_report({
            "total": 3, "matched": 1,
            "unmatched": [{"setcode": 0x46, "names_ja": ["融合", "フュージョン"]}],
            "ambiguous": [{"setcode": 0x1e, "names_ja": ["Ｃ", "コクーン"],
                           "name_zh": "繭狀體",
                           "candidates": [["繭狀體", 5], ["鐵鍊", 5]]}],
            "fallback": [{"setcode": 0x41, "names_ja": ["ＬＶ"]}],
            "patches": [{"setcode": 0x1e2, "names_ja": ["ＡＮＧＥＬＥＣＨＹ"],
                         "name_zh": "具象天使", "reason": "卡文沒引用字段名"}],
            "problems": [],
        })
        self.assertIn("`0x46` 融合／フュージョン", md)
        self.assertIn("`0x1e` Ｃ／コクーン:繭狀體 5、鐵鍊 5", md)
        self.assertIn("`0x1e2` ＡＮＧＥＬＥＣＨＹ → 具象天使(卡文沒引用字段名)", md)
        self.assertIn("`0x41` ＬＶ", md)


if __name__ == "__main__":
    unittest.main()
