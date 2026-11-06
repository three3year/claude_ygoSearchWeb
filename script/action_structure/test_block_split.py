"""區塊切分(接縫三):編號切、前言逐行、次數限制略過、召喚條件句不被當次數限制。"""
import unittest

from block_split import split_blocks

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


class SplitBlocksTest(unittest.TestCase):

    def test_numbered_blocks_split_on_marker_even_without_newline(self):
        """①②接在同一行(筆記 01:3,422 張)也要切成兩個區塊。"""
        blocks, _ = split_blocks("①：Aを破壊する。②：Bを除外する。")
        self.assertEqual([b["label"] for b in blocks], ["①", "②"])
        self.assertEqual([b["text"] for b in blocks],
                         ["①：Aを破壊する。", "②：Bを除外する。"])

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
                self.assertEqual([b["text"] for b in blocks][0], line)
                self.assertEqual(blocks[0]["unparsed"]["reason"], "區塊種類判不出")

    def test_old_style_text_is_one_unsplit_block(self):
        blocks, _ = split_blocks("Aを破壊する。Bを除外する。")
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["unparsed"]["reason"], "舊式無編號卡未切分")

    def test_pendulum_effect_blocks_come_from_pen_effect(self):
        blocks, _ = split_blocks("①：Aを破壊する。", pen_effect="①：Bを除外する。")
        self.assertEqual([(b["kind"], b["source"]) for b in blocks],
                         [("編號效果", "card_text"), ("靈擺效果", "pen_effect")])


if __name__ == "__main__":
    unittest.main()
