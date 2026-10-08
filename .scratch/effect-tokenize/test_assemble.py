# -*- coding: utf-8 -*-
"""效果句組裝的行為測試(票 effect-tokenize#13,ADR-0015)。

接縫:一張卡某段的標記句列 → 效果句列(tokenize.assemble)。只斷言輸出的
效果句:index、效果層、原文、parts(各段 index/kind/字元範圍),不測規則內部。

執行:PYTHONIOENCODING=utf-8 python -m unittest discover -s .scratch/effect-tokenize
"""
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "effect_tokenize", os.path.join(HERE, "tokenize.py"))
effect_tokenize = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(effect_tokenize)
assemble = effect_tokenize.assemble


def clause(index, kind, text_ja):
    return {"index": index, "section": "main", "kind": kind, "text_ja": text_ja}


# 220414 ②:賦予型領起句(效果外文本)+ 兩個子效果句
LEAD = "②：このカードは、このカードのカウンターの数によって以下の効果を得る。"
SUB1 = "●１つ：１ターンに１度、相手モンスターの攻撃宣言時に発動できる。その攻撃を無効にする。"
SUB2 = ("●２つ：このカードをリリースして発動できる。発動後２回目の相手エンドフェイズまで、"
        "フィールドのモンスターを全て除外する。")
FIRST = "①：自分バトルフェイズ開始時に発動できる。このカードにカウンターを１つ置く（最大２つまで）。"
CARD_220414 = [
    clause("①", "誘發效果(1速)", FIRST),
    clause("②", "效果外文本", LEAD),
    clause("②-●1", "誘發效果(1速)", SUB1),
    clause("②-●2", "啟動效果", SUB2),
]


class TestAssemble(unittest.TestCase):

    def test_sub_effect_clauses_join_their_lead_clause(self):
        out = assemble(CARD_220414)
        self.assertEqual([r["index"] for r in out], ["①", "②"])
        joined = out[1]
        self.assertEqual(joined["text_ja"], LEAD + "\n" + SUB1 + "\n" + SUB2)
        self.assertEqual([(p["index"], p["kind"]) for p in joined["parts"]],
                         [("②", "效果外文本"), ("②-●1", "誘發效果(1速)"),
                          ("②-●2", "啟動效果")])
        self.assertEqual(joined["kind"], "效果外文本")   # 領起句的效果類型

    def test_effect_sentence_with_sub_effects_is_effect_stratum(self):
        out = assemble(CARD_220414)
        self.assertEqual(out[1]["stratum"], "effect")   # 領起句是效果外文本也算效果層

    def test_part_ranges_reassemble_the_text(self):
        joined = assemble(CARD_220414)[1]
        pieces = [joined["text_ja"][p["start"]:p["end"]] for p in joined["parts"]]
        self.assertEqual(pieces, [LEAD, SUB1, SUB2])
        self.assertEqual("\n".join(pieces), joined["text_ja"])

    def test_plain_sentences_and_preamble_pass_through(self):
        pre = clause("0", "效果外文本", "レベル４「スプリガンズ」モンスター×２体以上")
        out = assemble([pre, CARD_220414[0]])
        self.assertEqual([(r["index"], r["kind"], r["stratum"], r["text_ja"])
                          for r in out],
                         [("0", "效果外文本", "extra", pre["text_ja"]),
                          ("①", "誘發效果(1速)", "effect", FIRST)])
        self.assertEqual([len(r["parts"]) for r in out], [1, 1])
        self.assertEqual(out[0]["parts"][0],
                         {"index": "0", "kind": "效果外文本", "start": 0,
                          "end": len(pre["text_ja"])})

    def test_old_style_numbered_lead(self):
        out = assemble([clause("1", "啟動效果", "以下の効果から１つを選択して発動できる。"),
                        clause("1-●1", "啟動効果", "●自分は１枚ドローする。")])
        self.assertEqual(len(out), 1)
        self.assertEqual([p["index"] for p in out[0]["parts"]], ["1", "1-●1"])

    def test_clause_without_text_is_skipped(self):
        out = assemble([clause("①", "啟動效果", None), CARD_220414[0]])
        self.assertEqual([r["text_ja"] for r in out], [FIRST])

    def test_context_accumulates_per_effect_sentence(self):
        """主線:同卡同段上文以組裝後的效果句累積——子效果句的 ● 標籤能看到領起句。"""
        with open(os.path.join(HERE, "lexicon.json"), encoding="utf-8") as f:
            import json
            tokenizer = effect_tokenize.Tokenizer(json.load(f))
        joined = assemble([
            clause("①", "啟動效果", "①：モンスターの種類を１つ宣言して発動できる。"),
            clause("①-●1", "啟動效果", "●融合：自分は１枚ドローする。"),
        ])[0]
        tokens = tokenizer.tokenize(joined["text_ja"], "")
        self.assertIn("●", tokens)
        self.assertIn("m:融合", tokens)


class TestOptionBoundaryToken(unittest.TestCase):

    def setUp(self):
        import json
        with open(os.path.join(HERE, "lexicon.json"), encoding="utf-8") as f:
            self.tokenizer = effect_tokenize.Tokenizer(json.load(f))

    def test_bullet_is_a_token_not_silent(self):
        tokens = self.tokenizer.tokenize(
            "①：以下の効果を適用する。\n●自分は１枚ドローする。\n●自分は１０００LP回復する。")
        self.assertEqual(tokens.count("●"), 2)
        self.assertNotIn("\n", "".join(tokens))

    def test_leading_bullet_kept_for_sub_effect_clause(self):
        tokens = self.tokenizer.tokenize("●魔法：自分の墓地から魔法カード１枚を手札に加える。")
        self.assertEqual(tokens[0], "●")
        self.assertIn("：", tokens)


if __name__ == "__main__":
    unittest.main()
