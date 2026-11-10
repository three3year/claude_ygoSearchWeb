"""物件切點(m3 票 03):物件範圍不再往前吞進主語、時點、標籤等前文。

接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import SPELL, card, faq

NORMAL_MONSTER = 0x11
FUSION_MONSTER = 0x61
BLACK_MAGICIAN = 46986414
POT_OF_GREED = 24094653

FENRIR = 218704
FENRIR_TEXT = (
    "このカードは通常召喚できない。自分の墓地の水属性モンスター２体をゲームから除外して特殊召喚する。"
    "このカードが戦闘によって相手モンスターを破壊した場合、次の相手ターンのドローフェイズをスキップする。")

DARK_MAGIC_EXPANDED = 111280
DARK_MAGIC_EXPANDED_TEXT = (
    "①：お互いのフィールド・墓地の「ブラック・マジシャン」「ブラック・マジシャン・ガール」の数によって"
    "以下の効果を適用する。●１体以上：フィールドの魔法使い族・闇属性モンスター１体を選び、"
    "その攻撃力をターン終了時まで１０００アップする。●２体以上：このターン、自分の魔法・罠カードの"
    "効果の発動に対して、相手は魔法・罠・モンスターの効果を発動できず、自分フィールドの魔法・罠カードは"
    "相手の効果では破壊されない。●３体以上：自分フィールドの魔法使い族・闇属性モンスターは"
    "ターン終了時まで相手の効果を受けない。")

ULTIMATE_FLAME_SWORDSMAN = 324483
ULTIMATE_FLAME_SWORDSMAN_TEXT = (
    "「炎の剣士」＋「闘気炎斬龍」\n"
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：相手フィールドのモンスター１体を対象として発動できる（このカードが装備カードを装備している場合、"
    "この効果は相手ターンでも発動できる）。そのモンスターを破壊し、相手に５００ダメージを与える。\n"
    "②：このカードが戦闘を行うダメージステップ開始時に発動できる。このカードの攻撃力はターン終了時まで"
    "倍になる。このターンのエンドフェイズにこのカードは破壊される。")


class _Golden(unittest.TestCase):
    cards = []
    faq = []

    @classmethod
    def setUpClass(cls):
        cls.structures, _ = build_structures(cls.cards, cls.faq)

    def run_(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return [hit["id"] for hit in self.run_(**query)["hits"]]

    def unparsed(self, **query):
        return self.run_(**query)["groups"]["未解析"]

    def failures(self, cid):
        structure = next(s for s in self.structures if s["id"] == cid)
        return check_card(structure)

    def failed_texts(self, cid):
        """反向檢查沒過的段的原文(無模板與字面不符都算)。"""
        structure = next(s for s in self.structures if s["id"] == cid)
        failed = {f["segment"] for f in check_card(structure) if f["segment"]}
        return [seg["text"] for block in structure["blocks"] for seg in block["segments"]
                if seg["id"] in failed]


class FenrirTest(_Golden):
    """フェンリル 218704:「このカードが戦闘によって相手モンスターを破壊した場合」主語與受詞各自成物件。"""
    cards = [
        card(FENRIR, name_ja="フェンリル", level=4, race=0x4000, attribute=0x2, atk=1400),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
        card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
    ]
    faq = [faq(FENRIR, "フェンリル", FENRIR_TEXT)]

    def test_destroy_condition_judges_a_monster_as_the_object(self):
        """查「破壞」開條件段、指定一張怪獸當物件:被破壞的是「相手モンスター」,判得了、命中。"""
        self.assertIn(FENRIR, self.hits(actions=["破壞"], include_condition=True,
                                        card=BLACK_MAGICIAN))

    def test_destroy_condition_rejects_a_spell_as_the_object(self):
        """指定魔法卡:判得了、不命中,也不落進未解析組。"""
        query = dict(actions=["破壞"], include_condition=True, card=POT_OF_GREED)
        self.assertNotIn(FENRIR, self.hits(**query))
        self.assertNotIn(FENRIR, self.unparsed(**query))

    def test_the_condition_segment_writes_back_to_its_text(self):
        self.assertNotIn("このカードが戦闘によって相手モンスターを破壊した場合",
                         self.failed_texts(FENRIR))


class DarkMagicExpandedTest(_Golden):
    """黒魔導強化 111280:「●２体以上：」是依值分歧的標籤,不在任何物件的字面裡。"""
    cards = [
        card(DARK_MAGIC_EXPANDED, name_ja="黒魔導強化", type=SPELL),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
        card(FENRIR, name_ja="フェンリル", level=4, race=0x4000, attribute=0x2, atk=1400),
        card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
    ]
    faq = [faq(DARK_MAGIC_EXPANDED, "黒魔導強化", DARK_MAGIC_EXPANDED_TEXT)]

    def test_labels_are_branch_labels_not_part_of_any_object(self):
        """沒有物件因為吞進標籤而解析不出;標籤不是段外殘留;分歧是依值分歧(標籤的值這輪認不得,
        所以段樹那一筆是「分歧前提解析不出」,不是「分歧方式判不出」)。"""
        failures = self.failures(DARK_MAGIC_EXPANDED)
        self.assertNotIn("物件無模板:物件修飾解析不出", [f["detail"] for f in failures])
        self.assertEqual([f["detail"] for f in failures if f["reason"] == "段外殘留"], [])
        self.assertEqual([f["detail"] for f in failures if f["segment"] is None],
                         ["段樹無模板:分歧前提解析不出"])

    def test_no_segment_text_starts_with_a_label(self):
        """標籤後面的句子各自成段,段的原文不含「：」。"""
        texts = [seg["text"] for block in self.structures[0]["blocks"]
                 for seg in block["segments"]]
        self.assertEqual([text for text in texts if "：" in text], [])
        self.assertIn("自分フィールドの魔法使い族・闇属性モンスターはターン終了時まで相手の効果を受けない",
                      texts)

    def test_cannot_be_destroyed_still_hits_after_the_label(self):
        """「●２体以上：」那一支的後半句照舊命中(回歸守門)。"""
        self.assertIn(DARK_MAGIC_EXPANDED,
                      self.hits(actions=["破壞"], polarities=["不會"], card=POT_OF_GREED))


class UltimateFlameSwordsmanTest(_Golden):
    """極炎の剣士 324483:「このターンのエンドフェイズにこのカードは破壊される」時點不在物件裡。"""
    cards = [
        card(ULTIMATE_FLAME_SWORDSMAN, name_ja="極炎の剣士", type=FUSION_MONSTER, level=8,
             race=0x1, attribute=0x4, atk=2800),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
    ]
    faq = [faq(ULTIMATE_FLAME_SWORDSMAN, "極炎の剣士", ULTIMATE_FLAME_SWORDSMAN_TEXT)]

    def test_destroy_hits_with_this_card_as_the_object(self):
        """查「破壞」、指定此卡:②的「このカードは破壊される」命中。"""
        self.assertIn(ULTIMATE_FLAME_SWORDSMAN,
                      self.hits(actions=["破壞"], card=ULTIMATE_FLAME_SWORDSMAN))

    def test_the_delayed_segment_writes_back_to_its_text(self):
        self.assertNotIn("このターンのエンドフェイズにこのカードは破壊される",
                         self.failed_texts(ULTIMATE_FLAME_SWORDSMAN))


if __name__ == "__main__":
    unittest.main()
