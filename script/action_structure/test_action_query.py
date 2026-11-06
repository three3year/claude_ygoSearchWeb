"""查詢判斷的未解析組(票 03):字面含查詢動作詞、但結構不完整的段不靜默消失。

只走接縫一(`run_query`):輸入官方文本與卡片參數,看結果的 `unparsed` 與分組。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from test_golden import SINGULARITY_FIEND, SINGULARITY_FIEND_TEXT, card, faq

TAIL_UNKNOWN = 11111111   # 述語語尾「する事ができる」同義表沒收:段解析不出
MODS_UNKNOWN = 22222222   # 物件修飾「レベル４以下の」票 04 前解析不出
NO_TEXT = 33333333        # 無官方日文
BLACK_MAGICIAN = 46986414


def fixtures():
    cards = [
        card(SINGULARITY_FIEND, name_ja="特異点の悪魔", level=1, race=0x40),
        card(TAIL_UNKNOWN, name_ja="語尾不明"),
        card(MODS_UNKNOWN, name_ja="修飾不明"),
        card(NO_TEXT, name_ja="無日文"),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2),
    ]
    entries = [
        faq(SINGULARITY_FIEND, "特異点の悪魔", SINGULARITY_FIEND_TEXT),
        faq(TAIL_UNKNOWN, "語尾不明",
            "①：手札からモンスター１体を特殊召喚する事ができる。"),
        faq(MODS_UNKNOWN, "修飾不明",
            "①：手札からレベル４以下のモンスター１体を特殊召喚する。"),
    ]
    return cards, entries


class UnparsedGroupTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards, entries = fixtures()
        cls.structures, _ = build_structures(cls.cards, entries)

    def query(self, **query):
        return run_query(self.structures, self.cards, query)

    def test_segment_with_action_literal_but_unparsed_goes_to_unparsed_group(self):
        """字面含「特殊召喚」但述語語尾抽不出:進未解析組(附原因)、不進命中組。"""
        result = self.query(actions=["特殊召喚"])
        self.assertNotIn(TAIL_UNKNOWN, result["groups"]["全部"])
        self.assertIn(TAIL_UNKNOWN, result["groups"]["未解析"])
        entry = next(u for u in result["unparsed"] if u["id"] == TAIL_UNKNOWN)
        self.assertEqual([s["reason"] for s in entry["segments"]],
                         ["述語語尾不明"])
        self.assertIn("特殊召喚", entry["segments"][0]["text"])

    def test_unparsed_group_only_lists_segments_containing_the_action(self):
        """查「破壞」時,那個抽不出的段字面沒有「破壊」,不列進未解析組。"""
        result = self.query(actions=["破壞"])
        self.assertNotIn(TAIL_UNKNOWN, result["groups"]["未解析"])

    def test_object_unparsed_blocks_hit_and_goes_to_unparsed_group(self):
        """段抽得出動作詞,但物件修飾抽不出:指定卡代入判不了,
        不算命中、列進未解析組並附物件的原因。"""
        result = self.query(actions=["特殊召喚"], card=BLACK_MAGICIAN)
        self.assertNotIn(MODS_UNKNOWN, result["groups"]["全部"])
        self.assertIn(MODS_UNKNOWN, result["groups"]["未解析"])
        entry = next(u for u in result["unparsed"] if u["id"] == MODS_UNKNOWN)
        self.assertEqual([s["reason"] for s in entry["segments"]],
                         ["物件修飾解析不出"])

    def test_hit_segment_is_not_double_listed_as_unparsed(self):
        """只給動作詞時,物件不必代入,該段命中;命中的段不再列進未解析組。"""
        result = self.query(actions=["特殊召喚"])
        self.assertIn(MODS_UNKNOWN, result["groups"]["全部"])
        self.assertNotIn(MODS_UNKNOWN, result["groups"]["未解析"])

    def test_card_without_official_text_is_in_unparsed_group_with_reason(self):
        """無官方日文的卡:任何查詢都列進未解析組,原因「無官方日文」。"""
        result = self.query(actions=["破壞"])
        self.assertIn(NO_TEXT, result["groups"]["未解析"])
        entry = next(u for u in result["unparsed"] if u["id"] == NO_TEXT)
        self.assertEqual(entry["reason"], "無官方日文")
        self.assertEqual(entry["segments"], [])
        self.assertNotIn(NO_TEXT, result["groups"]["全部"])

    def test_unparsed_group_count_is_card_count(self):
        """未解析組附張數:同一張卡多段也只算一張。"""
        result = self.query(actions=["特殊召喚"])
        self.assertEqual(len(result["groups"]["未解析"]),
                         len({u["id"] for u in result["unparsed"]}))
        self.assertEqual(result["groups"]["未解析"],
                         sorted(result["groups"]["未解析"]))

    def test_golden_card_hits_do_not_appear_in_unparsed_group(self):
        """特異点の悪魔整張抽得出:查「捨棄」命中,不在未解析組。"""
        result = self.query(actions=["捨棄"], card=SINGULARITY_FIEND)
        self.assertIn(SINGULARITY_FIEND, result["groups"]["全部"])
        self.assertNotIn(SINGULARITY_FIEND, result["groups"]["未解析"])


if __name__ == "__main__":
    unittest.main()
