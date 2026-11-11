"""連用形被動串接:述語的串接語尾加「され」「られ」,不限後面接哪個述語;
讀法同て形串接,一段兩個動作詞共用一條線。只走接縫一(查詢判斷)與接縫二(反向檢查)。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import card, faq

LINK_MONSTER = 0x4000021

ZENMAICON = 1735088
ZENMAICON_TEXT = (
    "「ゼンマイ」モンスター２体\nこのカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードがリンク召喚に成功した場合に発動できる。デッキから「ゼンマイ」カード１枚を手札に加える。"
    "②：自分フィールドの表側表示の「ゼンマイ」モンスター１体を裏側表示で除外して発動できる。"
    "それと同名のモンスター１体をデッキから特殊召喚する。③：このカードが破壊され墓地へ送られた場合、"
    "自分フィールドの「ゼンマイ」Xモンスター１体を対象として発動できる。"
    "このカードをそのモンスターの下に重ねてX素材とする。")
ZENMAICON_DESTROYED = "このカードが破壊され墓地へ送られた場合"


def own(structures, cid):
    return next(c for c in structures if c["id"] == cid)


def hit_texts(cards, structures, cid, **query):
    structure = own(structures, cid)
    texts = {s["id"]: s["text"] for b in structure["blocks"] for s in b["segments"]}
    result = run_query(structures, cards, query)
    return [texts[seg_id] for hit in result["hits"] if hit["id"] == cid
            for seg_id in hit["segments"]]


def failed_texts(structure):
    """反向檢查沒過的段的原文(段外殘留與段樹的列 None)。"""
    texts = {s["id"]: s["text"] for b in structure["blocks"] for s in b["segments"]}
    return [texts.get(f["segment"]) for f in check_card(structure)]


class ZenmaiconTest(unittest.TestCase):
    """発条補修ゼンマイコン 1735088 ③:「このカードが破壊され墓地へ送られた場合」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(ZENMAICON, name_ja="発条補修ゼンマイコン", type=LINK_MONSTER, level=2,
                          race=0x20, attribute=0x10, atk=1800, setcode=0x58)]
        cls.structures, _ = build_structures(
            cls.cards, [faq(ZENMAICON, "発条補修ゼンマイコン", ZENMAICON_TEXT)])

    def test_condition_hits_both_destroy_and_send_to_graveyard(self):
        """開條件段查「破壞」、查「送墓」都命中那一段(一段兩個動作詞),物件是此卡。"""
        for action in ("破壞", "送墓"):
            with self.subTest(action=action):
                self.assertIn(ZENMAICON_DESTROYED, hit_texts(
                    self.cards, self.structures, ZENMAICON, actions=[action],
                    include_condition=True, card=ZENMAICON))

    def test_condition_is_not_hit_without_including_conditions(self):
        self.assertNotIn(ZENMAICON_DESTROYED, hit_texts(
            self.cards, self.structures, ZENMAICON, actions=["破壞"]))

    def test_condition_writes_back(self):
        self.assertNotIn(ZENMAICON_DESTROYED, failed_texts(own(self.structures, ZENMAICON)))


TG_WEREWOLF = 293542
TG_WEREWOLF_TEXT = (
    "①：レベル４以下のモンスターが特殊召喚された時に発動できる。このカードを手札から特殊召喚する。\n"
    "②：フィールドのこのカードが破壊され墓地へ送られたターンのエンドフェイズに発動できる。"
    "デッキから「TG ワーウルフ」以外の「TG」モンスター１体を手札に加える。")
TG_DESTROYED = "フィールドのこのカードが破壊され墓地へ送られたターン"
TG_ARCHETYPES = [{"setcode": 0x27, "hex": "0x27", "names_ja": ["TG"], "name_zh": "T.G.",
                  "source": "strings.conf"}]


class TgWerewolfTest(unittest.TestCase):
    """TG ワーウルフ 293542 ②:「フィールドのこのカードが破壊され墓地へ送られたターン」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(TG_WEREWOLF, name_ja="TG ワーウルフ", level=3, race=0x8000,
                          attribute=0x20, atk=1200, setcode=0x27, **{"def": 0})]
        cls.structures, _ = build_structures(
            cls.cards, [faq(TG_WEREWOLF, "TG ワーウルフ", TG_WEREWOLF_TEXT)],
            archetypes=TG_ARCHETYPES)

    def test_destroyed_turn_writes_back(self):
        self.assertEqual(check_card(own(self.structures, TG_WEREWOLF)), [])

    def test_condition_hits_destroy_from_the_field(self):
        """開條件段查「破壞,從 場上」、查「送墓」命中那一段,物件是此卡。"""
        self.assertIn(TG_DESTROYED, hit_texts(
            self.cards, self.structures, TG_WEREWOLF, actions=["破壞"], from_zones=["場上"],
            include_condition=True, card=TG_WEREWOLF))
        self.assertIn(TG_DESTROYED, hit_texts(
            self.cards, self.structures, TG_WEREWOLF, actions=["送墓"],
            include_condition=True, card=TG_WEREWOLF))


DARK_DIMENSION_RELEASE = 31550470
DARK_DIMENSION_RELEASE_TEXT = (
    "①：除外されている自分の闇属性モンスター１体を対象としてこのカードを発動できる。"
    "そのモンスターを特殊召喚する。このカードがフィールドから離れた時にそのモンスターは破壊され"
    "除外される。そのモンスターが破壊された時にこのカードは破壊される。")
DARK_DIMENSION_DESTROYED = "そのモンスターは破壊され除外される"
DARK_MONSTER = 10001301


class DestroyedThenBanishedTest(unittest.TestCase):
    """闇次元の解放 31550470:「そのモンスターは破壊され除外される」——後面不是送墓的連用形被動串接。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(DARK_DIMENSION_RELEASE, name_ja="闇次元の解放", type=0x4),
                     card(DARK_MONSTER, name_ja="闇の怪獸", level=4, race=0x1, attribute=0x20)]
        cls.structures, _ = build_structures(
            cls.cards, [faq(DARK_DIMENSION_RELEASE, "闇次元の解放", DARK_DIMENSION_RELEASE_TEXT)])

    def test_destroyed_then_banished_writes_back(self):
        self.assertNotIn(DARK_DIMENSION_DESTROYED,
                         failed_texts(own(self.structures, DARK_DIMENSION_RELEASE)))

    def test_hits_both_destroy_and_banish(self):
        """查「破壞」、查「除外」都命中那一段(一段兩個動作詞共用一條線)。"""
        for action in ("破壞", "除外"):
            with self.subTest(action=action):
                self.assertIn(DARK_DIMENSION_DESTROYED, hit_texts(
                    self.cards, self.structures, DARK_DIMENSION_RELEASE, actions=[action],
                    card=DARK_MONSTER))


if __name__ == "__main__":
    unittest.main()
