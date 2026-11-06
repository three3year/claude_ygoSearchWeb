"""舊式用語同義表(票 11)的查詢層斷言:輸入真實卡的官方 DB 文本與卡片參數,看查詢結果。

只驗接縫一(查詢判斷)與接縫二(反向檢查),不驗結構內部的格。
每組挑同一機制的舊式寫法與新式寫法各一張真實卡,查同一動作詞都要命中。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import (BLACK_MAGICIAN, LONEFIRE, PLANT, SPELL, SPROUT, SPROUT_TEXT,
                         TRAP, card, faq)

DEEP_SWEEPER = 8649148  # ディープ・スィーパー(舊式:フィールド上の、を選択して;新式詞 リリース)
DEEP_SWEEPER_TEXT = ("このカードをリリースして発動できる。"
                     "フィールド上の魔法・罠カード１枚を選択して破壊する。")
EVOLUTION_PILL = 22431243  # 超進化薬(舊式:生け贄に捧げる)
EVOLUTION_PILL_TEXT = ("自分フィールド上の爬虫類族モンスター１体を生け贄に捧げる。"
                       "手札から恐竜族モンスター１体を特殊召喚する。")
SEAL_OF_HIERATIC = 11975962  # 抹殺の聖刻印(舊式:ゲームから除外する)
SEAL_OF_HIERATIC_TEXT = ("自分フィールド上の「聖刻」と名のついたモンスター１体をリリースして発動できる。"
                         "相手フィールド上のカード１枚を選択してゲームから除外する。")
ETHEREAL_WEAPON = 28865322  # 魔装邪龍 イーサルウェポン(新式:を対象として、除外する)
ETHEREAL_WEAPON_TEXT = ("①：このカードが召喚・特殊召喚に成功した時、フィールドのモンスター１体を"
                        "対象として発動できる。そのモンスターを除外する。")
TREACHEROUS_TRAP = 99590524  # 狡猾な落とし穴(新式:を対象として、そのモンスターを破壊する)
TREACHEROUS_TRAP_TEXT = ("①：自分の墓地に罠カードが存在しない場合、フィールドのモンスター２体を"
                         "対象として発動できる。そのモンスターを破壊する。")
ALTAR_OF_TRIBUTE = 21070956  # 生贄の祭壇(舊式:を１体選択して、墓地に送る)
ALTAR_OF_TRIBUTE_TEXT = ("自分フィールド上のモンスターを１体選択して墓地に送る。"
                         "このモンスターの元々の攻撃力分のライフポイントを回復する。")
SOKUSHINBUTSU = 15103313  # 即神仏(舊式:フィールド上に存在する、を選択して)
SOKUSHINBUTSU_TEXT = "自分フィールド上に存在するモンスター１体を選択して墓地へ送る。"
SHIELD_WARRIOR = 95360850  # シールド・ウォリアー(舊式:墓地に存在する、ゲームから除外して発動する事ができる)
SHIELD_WARRIOR_TEXT = ("戦闘ダメージ計算時、自分の墓地に存在するこのカードをゲームから除外して"
                       "発動する事ができる。自分フィールド上に存在するモンスターはその戦闘では破壊されない。")
AVATAR_OF_CREATOR = 97093037  # 創世者の化身(舊式代價句:〜を生け贄に捧げる事で、〜)
AVATAR_OF_CREATOR_TEXT = "このカードを生け贄に捧げる事で、手札の「創世神」１体を特殊召喚する。"
THE_CREATOR = 61505339  # 創世神
POT_OF_GREED = 24094653
MIRROR_FORCE = 44095762
HIERATIC_DRAGON = 46911809   # 聖刻龍－トフェニドラゴン(setcode 0x69)
REPTILE = 0x80000
DINOSAUR = 0x10000
ARCHETYPES = [{"setcode": 0x69, "hex": "0x69", "names_ja": ["聖刻"], "name_zh": "聖刻",
               "source": "strings.conf"}]


class OldStyleFixture(unittest.TestCase):
    """固定夾:同一機制的舊式與新式真實卡,外加代入用的黑魔導、強欲な壺、ミラーフォース、
    ローンファイア(植物族等級 3)、聖刻龍(字段 聖刻)、爬虫類族與恐竜族各一張。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(DEEP_SWEEPER, name_ja="ディープ・スィーパー", level=4, race=0x20000,
                 attribute=0x2, atk=1600),
            card(EVOLUTION_PILL, name_ja="超進化薬", type=SPELL, setcode=0x10e),
            card(SEAL_OF_HIERATIC, name_ja="抹殺の聖刻印", type=TRAP, setcode=0x69),
            card(ETHEREAL_WEAPON, name_ja="魔装邪龍 イーサルウェポン", level=6, race=0x2000,
                 attribute=0x20, atk=2300, setcode=0xcb),
            card(TREACHEROUS_TRAP, name_ja="狡猾な落とし穴", type=TRAP, setcode=0x4c),
            card(ALTAR_OF_TRIBUTE, name_ja="生贄の祭壇", type=TRAP),
            card(SOKUSHINBUTSU, name_ja="即神仏", type=SPELL),
            card(SHIELD_WARRIOR, name_ja="シールド・ウォリアー", level=3, race=0x1,
                 attribute=0x1, atk=800),
            card(SPROUT, name_ja="森羅の神芽 スプラウト", level=1, race=PLANT,
                 attribute=0x10, atk=100, setcode=0xa60090),
            card(LONEFIRE, name_ja="ローンファイア・ブロッサム", level=3, race=PLANT,
                 attribute=0x4, atk=500),
            card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
                 attribute=0x20, atk=2500),
            card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
            card(MIRROR_FORCE, name_ja="ミラーフォース", type=TRAP),
            card(HIERATIC_DRAGON, name_ja="聖刻龍－トフェニドラゴン", level=6, race=0x2000,
                 attribute=0x10, atk=2100, setcode=0x69),
            card(AVATAR_OF_CREATOR, name_ja="創世者の化身", level=4, race=0x1,
                 attribute=0x10, atk=1600),
            card(THE_CREATOR, name_ja="創世神", level=8, race=0x1000, attribute=0x10,
                 atk=2300),
            card(1001, name_ja="爬虫類", level=4, race=REPTILE, attribute=0x1),
            card(1002, name_ja="恐竜", level=4, race=DINOSAUR, attribute=0x1),
        ]
        cls.faq = [
            faq(DEEP_SWEEPER, "ディープ・スィーパー", DEEP_SWEEPER_TEXT),
            faq(EVOLUTION_PILL, "超進化薬", EVOLUTION_PILL_TEXT),
            faq(SEAL_OF_HIERATIC, "抹殺の聖刻印", SEAL_OF_HIERATIC_TEXT),
            faq(ETHEREAL_WEAPON, "魔装邪龍 イーサルウェポン", ETHEREAL_WEAPON_TEXT),
            faq(TREACHEROUS_TRAP, "狡猾な落とし穴", TREACHEROUS_TRAP_TEXT),
            faq(ALTAR_OF_TRIBUTE, "生贄の祭壇", ALTAR_OF_TRIBUTE_TEXT),
            faq(SOKUSHINBUTSU, "即神仏", SOKUSHINBUTSU_TEXT),
            faq(SHIELD_WARRIOR, "シールド・ウォリアー", SHIELD_WARRIOR_TEXT),
            faq(AVATAR_OF_CREATOR, "創世者の化身", AVATAR_OF_CREATOR_TEXT),
            faq(SPROUT, "森羅の神芽 スプラウト", SPROUT_TEXT),
        ]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq,
                                                      archetypes=ARCHETYPES)

    def hits(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [hit["id"] for hit in result["hits"]]

    def structure(self, cid):
        return next(c for c in self.structures if c["id"] == cid)


class TargetingSelectTest(OldStyleFixture):
    """舊式「〜１枚を選択して破壊する」= 取對象,標在對象線、不收成「選擇」;
    新式「〜を対象として発動できる。そのモンスターを破壊する」同一機制。"""

    def test_old_style_select_counts_as_targeting(self):
        """ディープ・スィーパー 查「取對象 破壞 場上」:魔法卡、陷阱卡代入命中;怪獸不符。"""
        self.assertIn(DEEP_SWEEPER, self.hits(actions=["破壞"], targeting=True))
        self.assertIn(DEEP_SWEEPER, self.hits(actions=["破壞"], targeting=True,
                                              from_zones=["場上"], card=POT_OF_GREED))
        self.assertIn(DEEP_SWEEPER, self.hits(actions=["破壞"], targeting=True,
                                              card=MIRROR_FORCE))
        self.assertNotIn(DEEP_SWEEPER, self.hits(actions=["破壞"], card=BLACK_MAGICIAN))

    def test_new_style_target_and_old_style_select_hit_the_same_query(self):
        """「取對象 破壞 場上 → 」黑魔導代入:新式 狡猾な落とし穴(そのモンスター 指回被取對象的怪獸)
        與舊式 ディープ・スィーパー(魔陷)各自命中自己的對象;不取對象的卡(超進化薬)不在內。"""
        hits = self.hits(actions=["破壞"], targeting=True, from_zones=["場上"],
                         card=BLACK_MAGICIAN)
        self.assertIn(TREACHEROUS_TRAP, hits)
        self.assertNotIn(DEEP_SWEEPER, hits)
        self.assertNotIn(EVOLUTION_PILL, hits)
        self.assertNotIn(TREACHEROUS_TRAP, self.hits(actions=["破壞"], targeting=True,
                                                     card=POT_OF_GREED))

    def test_count_before_select_is_targeting_too(self):
        """生贄の祭壇「モンスターを１体選択して墓地に送る」:助詞後的數量、舊式助詞 に 的送墓,
        仍是取對象、從場上、到墓地(述語寫明)。"""
        self.assertIn(ALTAR_OF_TRIBUTE, self.hits(actions=["送墓"], targeting=True,
                                                  from_zones=["場上"], to_zones=["墓地"],
                                                  card=BLACK_MAGICIAN))
        self.assertNotIn(ALTAR_OF_TRIBUTE, self.hits(actions=["送墓"], card=POT_OF_GREED))

    def test_select_is_not_an_action_word(self):
        """「選択」不是動作詞:查「選擇」沒有命中,舊式卡也不進未解析組。"""
        result = run_query(self.structures, self.cards, {"actions": ["選擇"]})
        self.assertEqual(result["groups"]["全部"], [])
        self.assertNotIn(DEEP_SWEEPER, result["groups"]["未解析"])

    def test_whole_cards_pass_reverse_check(self):
        for cid in (DEEP_SWEEPER, SOKUSHINBUTSU):
            self.assertEqual(check_card(self.structure(cid)), [], cid)


class SameMechanismOldAndNewTest(OldStyleFixture):
    """機制相同、寫法不同收成同一動作詞:舊式與新式的卡查同一動作詞都命中。"""

    def test_tribute_and_release_are_both_release(self):
        """解放:舊式 超進化薬「生け贄に捧げる」與新式 ディープ・スィーパー「リリースして」都命中;
        超進化薬 的對象是場上的爬虫類族(恐竜族不符)。"""
        hits = self.hits(actions=["解放"])
        self.assertIn(EVOLUTION_PILL, hits)
        self.assertIn(DEEP_SWEEPER, hits)
        self.assertIn(EVOLUTION_PILL, self.hits(actions=["解放"], from_zones=["場上"],
                                                card=1001))
        self.assertNotIn(EVOLUTION_PILL, self.hits(actions=["解放"], card=1002))
        self.assertIn(EVOLUTION_PILL, self.hits(actions=["特殊召喚"], from_zones=["手牌"],
                                                card=1002))

    def test_banish_from_game_and_banish_are_both_banish(self):
        """除外:舊式 抹殺の聖刻印「ゲームから除外する」與新式 魔装邪龍「除外する」,
        查「取對象 除外 場上 → 除外」黑魔導代入都命中;到 除外 是述語寫明的、不必開推得。"""
        hits = self.hits(actions=["除外"], targeting=True, from_zones=["場上"],
                         to_zones=["除外"], card=BLACK_MAGICIAN)
        self.assertIn(SEAL_OF_HIERATIC, hits)
        self.assertIn(ETHEREAL_WEAPON, hits)
        self.assertIn(SEAL_OF_HIERATIC, self.hits(actions=["解放"], card=HIERATIC_DRAGON))
        self.assertNotIn(SEAL_OF_HIERATIC, self.hits(actions=["解放"], card=BLACK_MAGICIAN))

    def test_send_to_graveyard_with_ni_and_he_are_both_send(self):
        """送墓:舊式 生贄の祭壇「墓地に送る」、即神仏「墓地へ送る」與新式 スプラウト「墓地へ送る」
        都命中「送墓 → 墓地」。"""
        hits = self.hits(actions=["送墓"], to_zones=["墓地"])
        for cid in (ALTAR_OF_TRIBUTE, SOKUSHINBUTSU, SPROUT):
            self.assertIn(cid, hits)

    def test_old_style_activation_suffix_is_an_activation(self):
        """シールド・ウォリアー「〜ゲームから除外して発動する事ができる」是發動句:
        代價段「墓地のこのカード → 除外」命中;「発動する事ができる」不是效果句的述語。"""
        self.assertIn(SHIELD_WARRIOR, self.hits(actions=["除外"], from_zones=["墓地"],
                                                to_zones=["除外"], card=SHIELD_WARRIOR))
        self.assertIn(SHIELD_WARRIOR, self.hits(actions=["除外"], kinds=["代價"],
                                                card=SHIELD_WARRIOR))

    def test_old_style_koto_de_is_cost_plus_effect(self):
        """創世者の化身「このカードを生け贄に捧げる事で、手札の「創世神」１体を特殊召喚する」:
        「〜る事で、」= 舊式的「〜して発動できる。」,切成代價段(解放 此卡)+ 效果段
        (手牌 → 特殊召喚 創世神);不是一整句解析不出。"""
        self.assertIn(AVATAR_OF_CREATOR, self.hits(actions=["解放"], kinds=["代價"],
                                                   card=AVATAR_OF_CREATOR))
        self.assertIn(AVATAR_OF_CREATOR, self.hits(actions=["特殊召喚"], from_zones=["手牌"],
                                                   card=THE_CREATOR))
        self.assertNotIn(AVATAR_OF_CREATOR, self.hits(actions=["特殊召喚"],
                                                      card=BLACK_MAGICIAN))

    def test_whole_cards_pass_reverse_check(self):
        for cid in (EVOLUTION_PILL, SEAL_OF_HIERATIC, AVATAR_OF_CREATOR):
            self.assertEqual(check_card(self.structure(cid)), [], cid)


if __name__ == "__main__":
    unittest.main()
