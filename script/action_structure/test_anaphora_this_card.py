"""物件修飾:回指與此卡——「他の」、「その+修飾+頭名詞」、帶狀態的此卡、召喚方式。

接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
import unittest

from card_structure import build_structures
from test_golden import SPELL, card, faq
from test_modifier_closed_sets import (DARK_BURST, DARK_BURST_TEXT, KURIBOH, LUSTER_DRAGON,
                                       STAT_CARDS)
from test_object_boundary import BLACK_MAGICIAN, NORMAL_MONSTER, POT_OF_GREED, GoldenCase

BLACK_MAGICIAN_CARD = card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER,
                           level=7, race=0x2, attribute=0x20, atk=2500)
POT_OF_GREED_CARD = card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL)


class ArchetypeGoldenCase(GoldenCase):
    """卡文裡有「」字段名的卡:建結構時要帶字段表。"""
    archetypes = []

    @classmethod
    def setUpClass(cls):
        cls.structures, _ = build_structures(cls.cards, cls.faq, cls.archetypes)


JUDGMENT_THUNDER = 59080
JUDGMENT_THUNDER_TEXT = (
    "このカード名はルール上「マギストス」カード、「エンディミオン」カードとしても扱う。\n"
    "①：自分フィールドの、他の表側表示の「マギストス」カード１枚を墓地へ送るか、魔力カウンターを２つ取り除き、"
    "以下の効果から１つを選択して発動できる（このカード名の以下の効果はそれぞれ１ターンに１度しか選択できない）。\n"
    "●自分の手札・EXデッキ（表側）・墓地から魔法使い族モンスター１体を特殊召喚する。\n"
    "●フィールドの他のカード１枚を除外する。")


class JudgmentThunderTest(GoldenCase):
    """聖魔 裁きの雷 59080:「フィールドの他のカード１枚を除外する」的「他の」是此卡以外。"""
    cards = [card(JUDGMENT_THUNDER, name_ja="聖魔 裁きの雷", type=SPELL),
             BLACK_MAGICIAN_CARD, POT_OF_GREED_CARD]
    faq = [faq(JUDGMENT_THUNDER, "聖魔 裁きの雷", JUDGMENT_THUNDER_TEXT)]

    def test_banish_hits_with_any_card_as_the_object(self):
        """查「除外」指定任一張卡:怪獸、魔法都命中,不落進未解析組。"""
        for other in (BLACK_MAGICIAN, POT_OF_GREED):
            query = dict(actions=["除外"], card=other)
            self.assertIn(JUDGMENT_THUNDER, self.hits(**query))
            self.assertNotIn(JUDGMENT_THUNDER, self.unparsed(**query))

    def test_another_copy_of_this_card_also_fits(self):
        """代入的是卡不是那一張實體:同名的另一張也算「他の」。"""
        self.assertIn(JUDGMENT_THUNDER, self.hits(actions=["除外"], card=JUDGMENT_THUNDER))

    def test_other_cards_is_not_a_generic_object(self):
        """「他のカード」帶著「此卡以外」,不是泛用物件。"""
        self.assertNotIn(JUDGMENT_THUNDER, self.hits(actions=["除外"], generic_only=True))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(JUDGMENT_THUNDER, "フィールドの他のカード１枚を除外する")


TEN_THOUSAND_DRAGON = 10000
TEN_THOUSAND_DRAGON_TEXT = (
    "このカードは通常召喚できない。攻撃力の合計と守備力の合計が、合わせて１００００以上になるように"
    "自分フィールドのモンスターをリリースした場合のみ特殊召喚できる。"
    "①：この方法で特殊召喚したこのカードの攻撃力・守備力は１００００になる。")


class TenThousandDragonTest(GoldenCase):
    """万物創世龍 10000:「この方法で特殊召喚したこのカード」是帶狀態的此卡(母體是此卡的子集)。"""
    cards = [card(TEN_THOUSAND_DRAGON, name_ja="万物創世龍", type=0x2000021, level=10,
                  race=0x2000, attribute=0x20, atk=-2),
             BLACK_MAGICIAN_CARD]
    faq = [faq(TEN_THOUSAND_DRAGON, "万物創世龍", TEN_THOUSAND_DRAGON_TEXT)]
    QUERY = dict(actions=["性質變更"], modified={"attr": "攻擊力", "form": "數值"})

    def test_stat_change_hits_with_this_card_as_the_object(self):
        self.assertIn(TEN_THOUSAND_DRAGON, self.hits(card=TEN_THOUSAND_DRAGON, **self.QUERY))

    def test_another_monster_is_not_the_object(self):
        """母體是此卡:別的怪獸代不進去(狀態本身任何卡都代得進去)。"""
        self.assertNotIn(TEN_THOUSAND_DRAGON, self.hits(card=BLACK_MAGICIAN, **self.QUERY))

    def test_this_card_with_a_state_is_not_a_generic_object(self):
        self.assertNotIn(TEN_THOUSAND_DRAGON, self.hits(generic_only=True, **self.QUERY))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(TEN_THOUSAND_DRAGON,
                              "この方法で特殊召喚したこのカードの攻撃力・守備力は１００００になる")


WORM_BEAST = 6285791
WORM_BEAST_TEXT = "①：自分エンドフェイズに発動する。フィールドの表側表示のこのカードを持ち主の手札に戻す。"


class WormBeastTest(GoldenCase):
    """邪悪なるワーム・ビースト 6285791:「表側表示のこのカード」的狀態是泛用原子,但物件是此卡。"""
    cards = [card(WORM_BEAST, name_ja="邪悪なるワーム・ビースト", level=3, race=0x4000,
                  attribute=0x1, atk=1400),
             BLACK_MAGICIAN_CARD]
    faq = [faq(WORM_BEAST, "邪悪なるワーム・ビースト", WORM_BEAST_TEXT)]

    def test_return_hits_with_this_card_only(self):
        self.assertIn(WORM_BEAST, self.hits(actions=["返回"], card=WORM_BEAST))
        self.assertNotIn(WORM_BEAST, self.hits(actions=["返回"], card=BLACK_MAGICIAN))

    def test_this_card_face_up_is_not_a_generic_object(self):
        self.assertNotIn(WORM_BEAST, self.hits(actions=["返回"], generic_only=True))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(WORM_BEAST), [])


CRUSH_WYVERN = 3405259
CRUSH_WYVERN_TEXT = (
    "①：１ターンに１度、以下の効果を１つ発動できる。\n"
    "●自分フィールドの機械族・光属性モンスター１体を対象とし、このカードを装備魔法カード扱いで装備する。"
    "装備モンスターが戦闘・効果で破壊される場合、代わりにこのカードを破壊する。\n"
    "●装備状態のこのカードを特殊召喚する。\n"
    "②：装備モンスターは相手の罠カードの効果を受けない。\n"
    "③：このカードがフィールドから墓地へ送られた場合に発動できる。"
    "手札からユニオンモンスター１体を特殊召喚する。")


class CrushWyvernTest(GoldenCase):
    """C－クラッシュ・ワイバーン 3405259:「装備状態のこのカードを特殊召喚する」。"""
    cards = [card(CRUSH_WYVERN, name_ja="C－クラッシュ・ワイバーン", type=0x421, level=4,
                  race=0x20, attribute=0x10, atk=1200),
             BLACK_MAGICIAN_CARD]
    faq = [faq(CRUSH_WYVERN, "C－クラッシュ・ワイバーン", CRUSH_WYVERN_TEXT)]

    def test_special_summon_hits_with_this_card_as_the_object(self):
        self.assertIn(CRUSH_WYVERN, self.hits(actions=["特殊召喚"], card=CRUSH_WYVERN))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(CRUSH_WYVERN, "装備状態のこのカードを特殊召喚する")


SKY_PUPIL = 122520
SKY_PUPIL_TEXT = (
    "「EMスカイ・ピューピル」の①の効果は１ターンに１度しか使用できない。"
    "①：自分フィールドのレベル５以上の「EM」モンスター１体を持ち主の手札に戻して発動できる。"
    "このカードを手札から特殊召喚する。この効果は相手ターンでも発動できる。"
    "②：このカードが相手モンスターと戦闘を行う場合、ダメージステップ終了時までそのモンスターの効果は無効化される。"
    "③：自分フィールドに他の「EM」モンスターが存在する場合、このカードが相手モンスターに攻撃する"
    "ダメージ計算前に発動できる。その相手モンスターを破壊する。")
EM_ARCHETYPES = [{"setcode": 0x9f, "hex": "0x9f", "names_ja": ["EM"], "name_zh": "娛樂夥伴",
                  "source": "strings.conf"}]


class SkyPupilTest(ArchetypeGoldenCase):
    """EMスカイ・ピューピル 122520:「その相手モンスターを破壊する」是回指,「相手」只是重述。"""
    cards = [card(SKY_PUPIL, name_ja="EMスカイ・ピューピル", level=3, race=0x2, attribute=0x10,
                  atk=800, setcode=0x9f),
             BLACK_MAGICIAN_CARD, POT_OF_GREED_CARD]
    faq = [faq(SKY_PUPIL, "EMスカイ・ピューピル", SKY_PUPIL_TEXT)]
    archetypes = EM_ARCHETYPES

    def test_destroy_judges_a_monster_as_the_object(self):
        """查「破壞」指定一張怪獸:判得了、命中。"""
        query = dict(actions=["破壞"], card=BLACK_MAGICIAN)
        self.assertIn(SKY_PUPIL, self.hits(**query))
        self.assertNotIn(SKY_PUPIL, self.unparsed(**query))

    def test_destroy_rejects_a_spell_as_the_object(self):
        """物件指回前文被攻擊的那隻怪獸:魔法卡代不進去,也不落進未解析組。"""
        query = dict(actions=["破壞"], card=POT_OF_GREED)
        self.assertNotIn(SKY_PUPIL, self.hits(**query))
        self.assertNotIn(SKY_PUPIL, self.unparsed(**query))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(SKY_PUPIL, "その相手モンスターを破壊する")


FIRE_KING_CIRCLE = 59388357
FIRE_KING_CIRCLE_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。\n"
    "①：自分フィールドの炎属性モンスター１体と自分の墓地の炎属性モンスター１体を対象として発動できる。"
    "対象の自分フィールドのモンスターを破壊し、対象の墓地のモンスターを特殊召喚する。")
FIELD, GRAVE = {"zone": "場上", "side": "我方"}, "墓地"


class FireKingCircleTest(GoldenCase):
    """炎王炎環 59388357:「対象の自分フィールドのモンスター」「対象の墓地のモンスター」各指回被取對象的
    兩隻裡在那個位置的那一隻。"""
    cards = [card(FIRE_KING_CIRCLE, name_ja="炎王炎環", type=0x10002), BLACK_MAGICIAN_CARD]
    faq = [faq(FIRE_KING_CIRCLE, "炎王炎環", FIRE_KING_CIRCLE_TEXT)]

    def test_the_field_target_is_the_one_destroyed(self):
        self.assertIn(FIRE_KING_CIRCLE,
                      self.hits(actions=["破壞"], targeting=True, from_zones=[FIELD]))
        self.assertNotIn(FIRE_KING_CIRCLE,
                         self.hits(actions=["破壞"], targeting=True, from_zones=[GRAVE]))

    def test_the_graveyard_target_is_the_one_summoned(self):
        self.assertIn(FIRE_KING_CIRCLE,
                      self.hits(actions=["特殊召喚"], targeting=True, from_zones=[GRAVE]))
        self.assertNotIn(FIRE_KING_CIRCLE,
                         self.hits(actions=["特殊召喚"], targeting=True, from_zones=[FIELD]))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(FIRE_KING_CIRCLE), [])


KARAKURI_INN = 3693034
KARAKURI_INN_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。"
    "①：自分フィールドの「カラクリ」モンスター１体と相手フィールドの効果モンスター１体を対象として発動できる。"
    "その自分のモンスターの表示形式を変更し、その相手モンスターの効果をターン終了時まで無効にする。"
    "②：自分フィールドに「カラクリ」モンスターが存在する場合、墓地のこのカードを除外し、"
    "フィールドの表側表示モンスター１体を対象として発動できる。そのモンスターの表示形式を変更する。")
OPPONENT_FIELD = {"zone": "場上", "side": "對手"}


class KarakuriInnTest(GoldenCase):
    """借カラクリ旅籠蔵 3693034:「その自分のモンスター」指回我方的那隻,不是最近提到的相手フィールドの
    効果モンスター。"""
    cards = [card(KARAKURI_INN, name_ja="借カラクリ旅籠蔵", type=0x4), BLACK_MAGICIAN_CARD]
    faq = [faq(KARAKURI_INN, "借カラクリ旅籠蔵", KARAKURI_INN_TEXT)]

    def test_the_position_change_is_on_my_monster(self):
        self.assertIn(KARAKURI_INN, self.hits(actions=["變更表示形式"], from_zones=[FIELD]))
        self.assertNotIn(KARAKURI_INN,
                         self.hits(actions=["變更表示形式"], from_zones=[OPPONENT_FIELD]))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(KARAKURI_INN, "その自分のモンスターの表示形式を変更し")


class DarkBurstAddToHandTest(GoldenCase):
    """ダーク・バースト 674561(使用者故事 23):加入手牌那一段的物件「その闇属性モンスター」是回指,
    指回被取對象的「攻撃力１５００以下の闇属性モンスター１体」。"""
    cards = [card(DARK_BURST, name_ja="ダーク・バースト", type=SPELL)] + STAT_CARDS
    faq = [faq(DARK_BURST, "ダーク・バースト", DARK_BURST_TEXT)]
    QUERY = dict(actions=["加入手牌"])

    def test_add_to_hand_hits_with_a_dark_monster_of_1500_or_less_attack(self):
        self.assertIn(DARK_BURST, self.hits(card=KURIBOH, **self.QUERY))

    def test_add_to_hand_rejects_a_dark_monster_with_more_attack(self):
        self.assertNotIn(DARK_BURST, self.hits(card=BLACK_MAGICIAN, **self.QUERY))
        self.assertNotIn(DARK_BURST, self.unparsed(card=BLACK_MAGICIAN, **self.QUERY))

    def test_add_to_hand_rejects_a_non_dark_monster(self):
        self.assertNotIn(DARK_BURST, self.hits(card=LUSTER_DRAGON, **self.QUERY))
        self.assertNotIn(DARK_BURST, self.unparsed(card=LUSTER_DRAGON, **self.QUERY))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(DARK_BURST), [])


CHAOS_SORCERER = 9596126
CHAOS_SORCERER_TEXT = (
    "このカードは通常召喚できない。\n"
    "自分の墓地から光・闇属性モンスターを１体ずつ除外した場合に特殊召喚できる。\n"
    "①：１ターンに１度、フィールドの表側表示モンスター１体を対象として発動できる"
    "（この効果を発動するターン、このカードは攻撃できない）。その表側表示モンスターを除外する。")


class ChaosSorcererTest(GoldenCase):
    """カオス・ソーサラー 9596126:前文帶括號注記的取對象句解析不出,「その表側表示モンスター」沒有
    物件可指——那一段不算命中,列進未解析組(不另建一個物件頂替)。"""
    cards = [card(CHAOS_SORCERER, name_ja="カオス・ソーサラー", type=0x2000021, level=6, race=0x2,
                  attribute=0x20, atk=2300)]
    faq = [faq(CHAOS_SORCERER, "カオス・ソーサラー", CHAOS_SORCERER_TEXT)]
    QUERY = dict(actions=["除外"], kinds=["效果"])

    def test_a_reference_with_nothing_to_point_at_is_listed_as_unparsed(self):
        self.assertNotIn(CHAOS_SORCERER, self.hits(**self.QUERY))
        self.assertIn(CHAOS_SORCERER, self.unparsed(**self.QUERY))


INVASION_WAVE = 18816758
INVASION_WAVE_TEXT = (
    "自分フィールド上のアドバンス召喚した「インヴェルズ」と名のついたモンスター１体を持ち主の手札に戻して"
    "発動できる。相手フィールド上のカード１枚を選択して破壊する。")
STEELSWARM_GIRASTAG = 58494728
STEELSWARM_ARCHETYPES = [{"setcode": 0x100a, "hex": "0x100a", "names_ja": ["インヴェルズ"],
                          "name_zh": "侵入魔", "source": "strings.conf"}]


class InvasionWaveTest(ArchetypeGoldenCase):
    """侵略の波動 18816758:連體子句「アドバンス召喚した」是召喚方式(狀態),任何卡都代得進去。"""
    cards = [card(INVASION_WAVE, name_ja="侵略の波動", type=0x4),
             card(STEELSWARM_GIRASTAG, name_ja="インヴェルズ・ギラファ", level=7, race=0x8,
                  attribute=0x20, atk=2600, setcode=0x100a),
             BLACK_MAGICIAN_CARD]
    faq = [faq(INVASION_WAVE, "侵略の波動", INVASION_WAVE_TEXT)]
    QUERY = dict(actions=["返回"], to_zones=["手牌"])
    archetypes = STEELSWARM_ARCHETYPES

    def test_return_cost_hits_with_a_steelswarm_monster(self):
        self.assertIn(INVASION_WAVE, self.hits(card=STEELSWARM_GIRASTAG, **self.QUERY))

    def test_return_cost_rejects_a_monster_outside_the_archetype(self):
        """其餘條件(字段)照常比:判得了、不命中,不落進未解析組。"""
        self.assertNotIn(INVASION_WAVE, self.hits(card=BLACK_MAGICIAN, **self.QUERY))
        self.assertNotIn(INVASION_WAVE, self.unparsed(card=BLACK_MAGICIAN, **self.QUERY))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(INVASION_WAVE), [])


MAGNUM_RELIEVER = 43227
MAGNUM_RELIEVER_TEXT = (
    "EXデッキから特殊召喚されたモンスター＋手札のモンスター\n"
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分の墓地の、「融合」魔法カードか「フュージョン」魔法カード１枚を対象として発動できる。"
    "そのカードをデッキの一番下に戻す。その後、自分は１枚ドローする。\n"
    "②：他のカードの効果が発動した時、自分の墓地から「融合」魔法カードか「フュージョン」魔法カード１枚を除外し、"
    "フィールドのカード１枚を対象として発動できる。そのカードを破壊する。")
FUSION_ARCHETYPES = [{"setcode": 0x46, "hex": "0x46", "names_ja": ["融合", "フュージョン"],
                      "name_zh": "融合", "source": "strings.conf"}]


class MagnumRelieverTest(ArchetypeGoldenCase):
    """マグナム・ザ・リリーバー 43227:「他のカードの効果が発動した時」的他のカード是此卡以外的任何卡。"""
    cards = [card(MAGNUM_RELIEVER, name_ja="マグナム・ザ・リリーバー", type=0x61, level=8, race=0x8,
                  attribute=0x10, atk=2800),
             BLACK_MAGICIAN_CARD, POT_OF_GREED_CARD]
    faq = [faq(MAGNUM_RELIEVER, "マグナム・ザ・リリーバー", MAGNUM_RELIEVER_TEXT)]
    QUERY = dict(actions=["發動"], kinds=["條件"], include_condition=True)
    archetypes = FUSION_ARCHETYPES

    def test_another_cards_effect_activation_hits_with_any_card(self):
        for other in (BLACK_MAGICIAN, POT_OF_GREED):
            self.assertIn(MAGNUM_RELIEVER, self.hits(card=other, **self.QUERY))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(MAGNUM_RELIEVER), [])


MASTER_OF_CHAOS = 85059922
MASTER_OF_CHAOS_TEXT = (
    "「ブラック・マジシャン」＋「カオス」儀式モンスター\n"
    "このカード名の①②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードが融合召喚した場合、自分の墓地の光・闇属性モンスター１体を対象として発動できる。"
    "そのモンスターを特殊召喚する。\n"
    "②：自分フィールドの光・闇属性モンスターを１体ずつリリースして発動できる。"
    "相手フィールドのモンスターを全て除外する。\n"
    "③：融合召喚したこのカードが戦闘・効果で破壊された場合、自分の墓地の魔法カード１枚を対象として発動できる。"
    "そのカードを手札に加える。")
CHAOS_ARCHETYPES = [{"setcode": 0xcf, "hex": "0xcf", "names_ja": ["カオス"], "name_zh": "混沌",
                     "source": "strings.conf"}]


class MasterOfChaosTest(ArchetypeGoldenCase):
    """超魔導戦士－マスター・オブ・カオス 85059922:「融合召喚したこのカード」是帶狀態(召喚方式)的此卡。"""
    cards = [card(MASTER_OF_CHAOS, name_ja="超魔導戦士－マスター・オブ・カオス", type=0x61, level=8,
                  race=0x2, attribute=0x20, atk=3000),
             BLACK_MAGICIAN_CARD, POT_OF_GREED_CARD]
    faq = [faq(MASTER_OF_CHAOS, "超魔導戦士－マスター・オブ・カオス", MASTER_OF_CHAOS_TEXT)]
    QUERY = dict(actions=["破壞"], kinds=["條件"], include_condition=True)
    archetypes = CHAOS_ARCHETYPES

    def test_destroyed_condition_hits_with_this_card(self):
        self.assertIn(MASTER_OF_CHAOS, self.hits(card=MASTER_OF_CHAOS, **self.QUERY))

    def test_destroyed_condition_rejects_another_monster(self):
        self.assertNotIn(MASTER_OF_CHAOS, self.hits(card=BLACK_MAGICIAN, **self.QUERY))
        self.assertNotIn(MASTER_OF_CHAOS, self.unparsed(card=BLACK_MAGICIAN, **self.QUERY))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(MASTER_OF_CHAOS), [])


KABUKI_DRAGON = 7541475
KABUKI_DRAGON_TEXT = (
    "①：１ターンに１度、自分のモンスターが相手のモンスターに攻撃したダメージ計算前に発動できる。"
    "その相手のモンスターの表示形式を変更する。"
    "②：１ターンに１度、相手のモンスターが自分のモンスターに攻撃したダメージ計算前に発動できる。"
    "その自分のモンスターの表示形式を変更する。")


class KabukiDragonTest(GoldenCase):
    """カブキ・ドラゴン 7541475:「Xが Yに 攻撃した」的 Y 是被攻擊的一方,後面的「その相手の/自分のモンスター」
    指回它。"""
    cards = [card(KABUKI_DRAGON, name_ja="カブキ・ドラゴン", level=6, race=0x2000, attribute=0x10,
                  atk=2300),
             BLACK_MAGICIAN_CARD, POT_OF_GREED_CARD]
    faq = [faq(KABUKI_DRAGON, "カブキ・ドラゴン", KABUKI_DRAGON_TEXT)]

    def test_attack_condition_hits_with_a_monster_as_the_attacked(self):
        query = dict(actions=["攻擊"], kinds=["條件"], include_condition=True)
        self.assertIn(KABUKI_DRAGON, self.hits(card=BLACK_MAGICIAN, **query))
        self.assertNotIn(KABUKI_DRAGON, self.hits(card=POT_OF_GREED, **query))

    def test_position_change_judges_a_monster_as_the_object(self):
        self.assertIn(KABUKI_DRAGON, self.hits(actions=["變更表示形式"], card=BLACK_MAGICIAN))
        self.assertNotIn(KABUKI_DRAGON, self.hits(actions=["變更表示形式"], card=POT_OF_GREED))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(KABUKI_DRAGON), [])


if __name__ == "__main__":
    unittest.main()
