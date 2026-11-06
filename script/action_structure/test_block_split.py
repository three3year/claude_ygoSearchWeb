"""區塊切分(接縫三):編號切、前言逐行、次數限制略過、召喚條件句不被當次數限制;
舊式無編號卡依句號與開頭切、補足引用不被切斷、邊界補丁先讀。"""
import unittest

from block_split import (PATCH_APPLIED, PATCH_COVERAGE, PATCH_MALFORMED,
                         PATCH_QUOTE, PATCH_STALE, boundary_patch_hash,
                         split_blocks)

LIMIT_LINES = (
    "このカード名の効果は１ターンに１度しか使用できない。",
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。",
    "このカード名のカードは１ターンに１枚しか発動できない。",
    "自分は「想い集いし竜」を１ターンに１度しか特殊召喚できない。",
    "このカード名の①の方法による特殊召喚は１ターンに１度しかできない。",
    "このカード名の①の効果は１ターンに２度まで使用できる。",
    "このカード名の①②の効果は、それぞれ１ターンに１度しか使用できず、同一チェーン上では発動できない。",
)
KEPT_LINES = (
    "「滅びの黒魔術師」は１ターンに１度、融合召喚及び以下の方法でのみ特殊召喚できる。",
    "このカードは通常召喚できず、「バスター・モード」の効果でのみ特殊召喚できる。",
    "「ブラック・マジシャン」＋光・闇属性モンスター",
)

# 森羅の神芽 スプラウト 10753491 的官方 DB 文本與補足情報(筆記 02)。
SPROUT_TEXT = (
    "このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚までめくる事ができる。"
    "めくったカードの中に植物族モンスターがあった場合、それらのモンスターを全て墓地へ送る。"
    "残りのカードは好きな順番でデッキの一番下に戻す。"
    "また、デッキのこのカードがカードの効果によってめくられて墓地へ送られた場合、"
    "デッキから植物族・レベル１モンスター１体を特殊召喚できる。"
    "「森羅の神芽 スプラウト」のこの効果は１ターンに１度しか使用できない。")
SPROUT_SUPPLEMENT = (
    "■『このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚までめくる事ができる。"
    "めくったカードの中に植物族モンスターがあった場合、それらのモンスターを全て墓地へ送る。"
    "残りのカードは好きな順番でデッキの一番下に戻す』モンスター効果は誘発効果です。\n"
    "■『デッキのこのカードがカードの効果によってめくられて墓地へ送られた場合、"
    "デッキから植物族・レベル１モンスター１体を特殊召喚できる』モンスター効果は、"
    "墓地にて発動する誘発効果です。")
SPROUT_BLOCKS = [
    "このカードが特殊召喚に成功した時、自分のデッキの上からカードを２枚までめくる事ができる。"
    "めくったカードの中に植物族モンスターがあった場合、それらのモンスターを全て墓地へ送る。"
    "残りのカードは好きな順番でデッキの一番下に戻す。",
    "また、デッキのこのカードがカードの効果によってめくられて墓地へ送られた場合、"
    "デッキから植物族・レベル１モンスター１体を特殊召喚できる。",
]


def texts(blocks):
    return [b["text"] for b in blocks]


class SplitBlocksTest(unittest.TestCase):

    def test_numbered_blocks_split_on_marker_even_without_newline(self):
        """①②接在同一行(筆記 01:3,422 張)也要切成兩個區塊。"""
        blocks, _ = split_blocks("①：Aを破壊する。②：Bを除外する。")
        self.assertEqual([b["label"] for b in blocks], ["①", "②"])
        self.assertEqual(texts(blocks), ["①：Aを破壊する。", "②：Bを除外する。"])

    def test_limit_lines_are_omitted_not_blocks(self):
        for line in LIMIT_LINES:
            with self.subTest(line=line):
                blocks, omitted = split_blocks(line + "\n①：Aを破壊する。")
                self.assertEqual([b["label"] for b in blocks], ["①"])
                self.assertEqual([o["reason"] for o in omitted], ["次數限制"])
                self.assertEqual(omitted[0]["text"], line)

    def test_summon_condition_and_material_lines_stay_as_blocks(self):
        for line in KEPT_LINES:
            with self.subTest(line=line):
                blocks, omitted = split_blocks(line + "\n①：Aを破壊する。")
                self.assertEqual(omitted, [])
                self.assertEqual(texts(blocks)[0], line)
                self.assertEqual(blocks[0]["unparsed"]["reason"], "區塊種類判不出")

    def test_pendulum_effect_blocks_come_from_pen_effect(self):
        blocks, _ = split_blocks("①：Aを破壊する。", pen_effect="①：Bを除外する。")
        self.assertEqual([(b["kind"], b["source"]) for b in blocks],
                         [("編號效果", "card_text"), ("靈擺效果", "pen_effect")])


class OldStyleSplitTest(unittest.TestCase):
    """舊式無編號卡:素材行、召喚條件句各自切出,其餘在句號處依開頭決定切不切。"""

    def test_material_line_and_summon_condition_are_their_own_blocks(self):
        text = ("「E・HERO ネオス」＋「N・グラン・モール」\n"
                "このカードは融合召喚でしか特殊召喚できない。"
                "このカードが戦闘によって相手モンスターを破壊した場合、そのモンスターを除外する。"
                "エンドフェイズ時にこのカードは融合デッキに戻る。")
        blocks, omitted = split_blocks(text)
        self.assertEqual([b["kind"] for b in blocks],
                         ["素材", "召喚條件", "編號效果", "編號效果"])
        self.assertEqual(texts(blocks), [
            "「E・HERO ネオス」＋「N・グラン・モール」",
            "このカードは融合召喚でしか特殊召喚できない。",
            "このカードが戦闘によって相手モンスターを破壊した場合、そのモンスターを除外する。",
            "エンドフェイズ時にこのカードは融合デッキに戻る。"])
        self.assertEqual(omitted, [])
        self.assertTrue(all(b["unparsed"] is None for b in blocks))
        self.assertTrue(all(b["label"] is None for b in blocks))

    def test_blocks_are_substrings_at_their_spans(self):
        blocks, omitted = split_blocks(SPROUT_TEXT, supplement=SPROUT_SUPPLEMENT)
        for b in blocks:
            self.assertEqual(SPROUT_TEXT[b["span"][0]:b["span"][1]], b["text"])
            self.assertEqual(b["id"], f"b{b['span'][0]}")
        for o in omitted:
            self.assertEqual(SPROUT_TEXT[o["span"][0]:o["span"][1]], o["text"])

    def test_mata_cuts_but_continuation_openers_do_not(self):
        """「また、」切;「その後」「選択した」「この効果は」「このターン」續前一區塊。"""
        text = ("フィールド上のモンスター１体を選択して破壊する。"
                "その後、選択したモンスターのコントローラーは１枚ドローする。"
                "この効果は相手ターンでも発動できる。"
                "また、このカードが墓地に存在する場合、このカードを除外して発動できる。"
                "このターン、自分は通常召喚できない。")
        blocks, _ = split_blocks(text)
        self.assertEqual(texts(blocks), [
            "フィールド上のモンスター１体を選択して破壊する。"
            "その後、選択したモンスターのコントローラーは１枚ドローする。"
            "この効果は相手ターンでも発動できる。",
            "また、このカードが墓地に存在する場合、このカードを除外して発動できる。"
            "このターン、自分は通常召喚できない。"])

    def test_sentence_opening_with_a_trigger_clause_cuts(self):
        """「〜時、」「〜場合、」「〜毎に」開頭的句子是新效果;動詞句開頭(自分の〜を…する)續前句。"""
        text = ("相手フィールド上のモンスター１体を選択して破壊する。"
                "自分のデッキからカードを１枚ドローする。"
                "自分のスタンバイフェイズ時、自分の墓地のモンスター１体を選択して手札に加える。"
                "相手のスタンバイフェイズ毎に相手ライフに５００ポイントダメージを与える。")
        blocks, _ = split_blocks(text)
        self.assertEqual(texts(blocks), [
            "相手フィールド上のモンスター１体を選択して破壊する。"
            "自分のデッキからカードを１枚ドローする。",
            "自分のスタンバイフェイズ時、自分の墓地のモンスター１体を選択して手札に加える。",
            "相手のスタンバイフェイズ毎に相手ライフに５００ポイントダメージを与える。"])

    def test_trailing_limit_sentence_is_omitted(self):
        blocks, omitted = split_blocks(SPROUT_TEXT, supplement=SPROUT_SUPPLEMENT)
        self.assertEqual(texts(blocks), SPROUT_BLOCKS)
        self.assertEqual([(o["reason"], o["text"]) for o in omitted], [
            ("次數限制", "「森羅の神芽 スプラウト」のこの効果は１ターンに１度しか使用できない。")])

    def test_supplement_quote_spanning_a_cut_point_keeps_sentences_together(self):
        """硬約束:補足情報『』引用跨句號時不得切斷,即使開頭是「また、」。"""
        text = ("自分フィールド上のモンスター１体を選択して破壊する。"
                "また、このカードが墓地に存在する場合、このカードを除外して発動できる。")
        blocks, _ = split_blocks(text)
        self.assertEqual(len(blocks), 2)
        supplement = ("■『自分フィールド上のモンスター１体を選択して破壊する。また、このカードが"
                      "墓地に存在する場合、このカードを除外して発動できる』効果です。")
        blocks, _ = split_blocks(text, supplement=supplement)
        self.assertEqual(texts(blocks), [text])

    def test_sequence_quotes_in_supplement_are_ignored(self):
        """『①』『●』這種序號引用不是原文引用,不影響切分。"""
        text = "Aを破壊する。また、Bを除外する。"
        blocks, _ = split_blocks(text, supplement="『①』『●』の効果です。")
        self.assertEqual(len(blocks), 2)

    def test_sentence_split_ignores_periods_inside_brackets(self):
        text = ("「黒羽の宝札」の効果を発動する。"
                "また、『Aを破壊する。Bを除外する』と記されたカードを手札に加える。")
        blocks, _ = split_blocks(text)
        self.assertEqual(texts(blocks), [
            "「黒羽の宝札」の効果を発動する。",
            "また、『Aを破壊する。Bを除外する』と記されたカードを手札に加える。"])


class BoundaryPatchTest(unittest.TestCase):
    """邊界補丁:一卡一筆、只記官方日文的區塊子字串、雜湊只算官方日文;
    規則先讀補丁,補丁不能用時整筆失效退回規則。"""

    TEXT = ("Aを破壊する。Bを除外する。Cを手札に加える。")

    def patch(self, blocks, text=None, **extra):
        record = {"id": 1, "text_hash": boundary_patch_hash(text or self.TEXT),
                  "blocks": blocks}
        record.update(extra)
        return record

    def test_patch_overrides_rule_split(self):
        """規則把三句連成一塊(都是動詞句);補丁說第二句起是另一效果,照補丁。"""
        blocks, _ = split_blocks(self.TEXT)
        self.assertEqual(texts(blocks), [self.TEXT])
        patch = self.patch(["Aを破壊する。", "Bを除外する。Cを手札に加える。"])
        status = {}
        blocks, _ = split_blocks(self.TEXT, boundary_patch={"card_text": patch},
                                 patch_status=status)
        self.assertEqual(texts(blocks), ["Aを破壊する。", "Bを除外する。Cを手札に加える。"])
        self.assertEqual([b["kind"] for b in blocks], ["編號效果", "編號效果"])
        self.assertEqual(blocks[1]["span"], [7, 23])
        self.assertEqual(status, {"card_text": PATCH_APPLIED})

    def test_patch_pieces_are_classified_like_rule_units(self):
        """補丁只記切點:切出的素材行、召喚條件句、次數限制照規則定種類。"""
        text = ("「A」＋「B」\nこのカードは融合召喚でしか特殊召喚できない。"
                "Cを破壊する。Dを除外する。この効果は１ターンに１度しか使用できない。")
        patch = self.patch(["「A」＋「B」", "このカードは融合召喚でしか特殊召喚できない。",
                            "Cを破壊する。Dを除外する。",
                            "この効果は１ターンに１度しか使用できない。"],
                           text=text)
        blocks, omitted = split_blocks(text, boundary_patch={"card_text": patch})
        self.assertEqual([b["kind"] for b in blocks], ["素材", "召喚條件", "編號效果"])
        self.assertEqual(blocks[2]["text"], "Cを破壊する。Dを除外する。")
        self.assertEqual([o["reason"] for o in omitted], ["次數限制"])

    def test_stale_hash_invalidates_whole_record(self):
        """卡文變動(雜湊不符)整筆失效、退回規則,不保留舊切點。"""
        patch = self.patch(["Aを破壊する。", "Bを除外する。Cを手札に加える。"],
                           text="舊版卡文。")
        status = {}
        blocks, _ = split_blocks(self.TEXT, boundary_patch={"card_text": patch},
                                 patch_status=status)
        self.assertEqual(texts(blocks), [self.TEXT])
        self.assertEqual(status, {"card_text": PATCH_STALE})

    def test_patch_that_does_not_cover_the_text_is_rejected(self):
        patch = self.patch(["Aを破壊する。", "Cを手札に加える。"])
        status = {}
        blocks, _ = split_blocks(self.TEXT, boundary_patch={"card_text": patch},
                                 patch_status=status)
        self.assertEqual(texts(blocks), [self.TEXT])
        self.assertEqual(status, {"card_text": PATCH_COVERAGE})

    def test_patch_cutting_a_supplement_quote_is_rejected(self):
        patch = self.patch(["Aを破壊する。", "Bを除外する。Cを手札に加える。"])
        supplement = "『Aを破壊する。Bを除外する』効果です。"
        status = {}
        blocks, _ = split_blocks(self.TEXT, supplement=supplement,
                                 boundary_patch={"card_text": patch},
                                 patch_status=status)
        self.assertEqual(texts(blocks), [self.TEXT])
        self.assertEqual(status, {"card_text": PATCH_QUOTE})

    def test_malformed_patch_is_rejected(self):
        for blocks in ([], ["Aを破壊する。", ""], "Aを破壊する。"):
            with self.subTest(blocks=blocks):
                patch = self.patch(blocks)
                status = {}
                got, _ = split_blocks(self.TEXT, boundary_patch={"card_text": patch},
                                      patch_status=status)
                self.assertEqual(texts(got), [self.TEXT])
                self.assertEqual(status, {"card_text": PATCH_MALFORMED})

    def test_patch_whitespace_is_ignored_but_spans_are_exact(self):
        """覆蓋比對忽略空白(同拆句表),切出的仍是原文的連續子字串。"""
        text = "Aを破壊する。\nBを除外する。"
        patch = self.patch(["Aを破壊する。", "B を除外する。"], text=text)
        blocks, _ = split_blocks(text, boundary_patch={"card_text": patch})
        self.assertEqual(texts(blocks), ["Aを破壊する。", "Bを除外する。"])
        self.assertEqual(blocks[1]["span"], [8, 15])

    def test_hash_only_covers_official_japanese(self):
        self.assertEqual(len(boundary_patch_hash("Aを破壊する。")), 16)
        self.assertNotEqual(boundary_patch_hash("Aを破壊する。"),
                            boundary_patch_hash("Aを破壊する。 "))


if __name__ == "__main__":
    unittest.main()
