"""「装備」的讀法(m3b 票 05)。

「装備魔法カード」= 卡片子類型 裝備 且 大類 魔法;「装備カード」= 狀態原子 `裝備中`(正當成裝備卡裝在怪獸上的卡);
`裝備中` 指定卡代入時:怪獸一律符合、魔法要卡片子類型 裝備、陷阱要自己的官方日文含「装備」。
接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
import unittest

from test_golden import SPELL, TRAP, card, faq
from test_modifier_closed_sets import GoldenCase

EQUIP_SPELL = 0x40002
FIELD_SPELL = 0x80002
SYNCHRO_MONSTER = 0x2021

MONSTER_REBORN = 83764718
MONSTER_REBORN_TEXT = (
    "①：自分か相手の墓地のモンスター１体を対象として発動できる。"
    "そのモンスターを自分フィールドに特殊召喚する。")
MAGE_POWER = 83746708
MAGE_POWER_TEXT = "①：装備モンスターの攻撃力・守備力は、自分フィールドの魔法・罠カードの数×５００アップする。"

POWER_TOOL_DRAGON = 2403771
POWER_TOOL_DRAGON_TEXT = (
    "チューナー＋チューナー以外のモンスター１体以上\n"
    "①：１ターンに１度、自分メインフェイズに発動できる。デッキから装備魔法カード３枚を相手に見せ、"
    "相手はその中からランダムに１枚選ぶ。そのカード１枚を自分の手札に加え、残りをデッキに戻す。"
    "②：このカードが破壊される場合、代わりにこのカードに装備されている装備魔法カード１枚を墓地へ送る事ができる。")

SUPPORT_CARDS = [
    card(MONSTER_REBORN, name_ja="死者蘇生", type=SPELL),
    card(MAGE_POWER, name_ja="魔導師の力", type=EQUIP_SPELL),
]
SUPPORT_FAQ = [
    faq(MONSTER_REBORN, "死者蘇生", MONSTER_REBORN_TEXT),
    faq(MAGE_POWER, "魔導師の力", MAGE_POWER_TEXT),
]


class PowerToolDragonTest(GoldenCase):
    """パワー・ツール・ドラゴン 2403771:「デッキから装備魔法カード３枚を相手に見せ」(使用者故事 25)。"""
    cards = [card(POWER_TOOL_DRAGON, name_ja="パワー・ツール・ドラゴン", type=SYNCHRO_MONSTER,
                  level=7, race=0x20, attribute=0x1, atk=2300, **{"def": 2500})] + SUPPORT_CARDS
    faq = [faq(POWER_TOOL_DRAGON, "パワー・ツール・ドラゴン", POWER_TOOL_DRAGON_TEXT)] + SUPPORT_FAQ

    def test_reveal_hits_with_an_equip_spell(self):
        self.assertIn(POWER_TOOL_DRAGON, self.hits(actions=["展示"], card=MAGE_POWER))

    def test_reveal_misses_with_a_spell_that_is_not_an_equip_spell(self):
        self.assertJudgedMiss(POWER_TOOL_DRAGON, actions=["展示"], card=MONSTER_REBORN)

    def test_the_reveal_writes_back_to_its_text(self):
        self.assertWritesBack(POWER_TOOL_DRAGON, "デッキから装備魔法カード３枚を相手に見せ")


CURSED_EYE_BIRTH = 8775395
CURSED_EYE_BIRTH_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：デッキから「呪眼」モンスター１体と「呪眼」魔法・罠カード１枚を墓地へ送って発動できる。"
    "デッキから「呪眼」装備魔法カード１枚を手札に加える。"
    "このターン、自分が「呪眼」カード以外のカードの効果を発動する度に自分は５００LPを失う。"
    "②：自分が「呪眼」リンクモンスターのリンク召喚に成功した場合、墓地のこのカードを除外して発動できる。"
    "自分の墓地から「呪眼」装備魔法カード１枚を選び、自分フィールドの「呪眼」リンクモンスター１体に装備する。")
EVIL_EYE_OF_SELENE = 44133040   # セレンの呪眼:「呪眼」裝備魔法
CURSED_EYE = 0x129
CURSED_EYE_ARCHETYPES = [{"setcode": CURSED_EYE, "hex": "0x129", "names_ja": ["呪眼"],
                          "name_zh": "咒眼", "source": "strings.conf"}]


class CursedEyeBirthTest(GoldenCase):
    """災誕の呪眼 8775395:「デッキから「呪眼」装備魔法カード１枚を手札に加える」(使用者故事 26)。"""
    cards = [card(CURSED_EYE_BIRTH, name_ja="災誕の呪眼", type=SPELL, setcode=CURSED_EYE),
             card(EVIL_EYE_OF_SELENE, name_ja="セレンの呪眼", type=EQUIP_SPELL, setcode=CURSED_EYE)
             ] + SUPPORT_CARDS
    faq = [faq(CURSED_EYE_BIRTH, "災誕の呪眼", CURSED_EYE_BIRTH_TEXT)] + SUPPORT_FAQ
    archetypes = CURSED_EYE_ARCHETYPES

    def query(self):
        return dict(actions=["加入手牌"], from_zones=["牌組"])

    def test_add_to_hand_hits_with_a_cursed_eye_equip_spell(self):
        self.assertIn(CURSED_EYE_BIRTH, self.hits(**self.query(), card=EVIL_EYE_OF_SELENE))

    def test_add_to_hand_misses_with_an_equip_spell_outside_the_archetype(self):
        self.assertJudgedMiss(CURSED_EYE_BIRTH, **self.query(), card=MAGE_POWER)

    def test_add_to_hand_misses_with_a_cursed_eye_spell_that_is_not_an_equip_spell(self):
        self.assertJudgedMiss(CURSED_EYE_BIRTH, **self.query(), card=CURSED_EYE_BIRTH)

    def test_the_add_to_hand_writes_back_to_its_text(self):
        self.assertWritesBack(CURSED_EYE_BIRTH, "デッキから「呪眼」装備魔法カード１枚を手札に加える")


HOLY_SWORD_CASTLE = 15635751
HOLY_SWORD_CASTLE_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：自分メインフェイズに発動できる。このカードを次のスタンバイフェイズまで除外し、"
    "自分の手札・デッキ・墓地から「円卓の聖騎士」１枚を自分のフィールドゾーンに表側表示で置く。"
    "その後、以下の効果を適用できる。\n"
    "●自分のデッキ・墓地から、「アルトリウス」モンスター１体を特殊召喚するか「聖剣」カード１枚を手札に加える。\n"
    "②：１ターンに１度、自分フィールドの「聖騎士」カードが戦闘・効果で破壊される場合、"
    "代わりに自分フィールドの装備カード１枚を破壊できる。")
HOLY_SWORD_ARCHETYPES = [
    {"setcode": 0xa7, "hex": "0xa7", "names_ja": ["アルトリウス"], "name_zh": "阿爾托利斯",
     "source": "strings.conf"},
    {"setcode": 0x107a, "hex": "0x107a", "names_ja": ["聖騎士"], "name_zh": "聖騎士",
     "source": "strings.conf"},
    {"setcode": 0x207a, "hex": "0x207a", "names_ja": ["聖剣"], "name_zh": "聖劍",
     "source": "strings.conf"},
]
METALMORPH = 68540058          # メタル化・魔法反射装甲:官方日文含「装備」的陷阱
METALMORPH_TEXT = (
    "①：フィールドの表側表示モンスター１体を対象としてこのカードを発動できる。"
    "このカードを攻撃力・守備力３００アップの装備カード扱いでそのモンスターに装備する。\n"
    "②：このカードの効果でこのカードを装備したモンスターの攻撃力は、"
    "モンスターに攻撃するダメージ計算時のみ、その攻撃対象モンスターの攻撃力の半分だけアップする。")
MIRROR_FORCE = 44095762        # 聖なるバリア －ミラーフォース－:官方日文不含「装備」的陷阱
MIRROR_FORCE_TEXT = "①：相手モンスターの攻撃宣言時に発動できる。相手フィールドの攻撃表示モンスターを全て破壊する。"
BLACK_MAGICIAN = 46986414


class HolySwordCastleTest(GoldenCase):
    """聖騎士と聖剣の巨城 15635751:「代わりに自分フィールドの装備カード１枚を破壊できる」(使用者故事 27、28)。"""
    cards = [card(HOLY_SWORD_CASTLE, name_ja="聖騎士と聖剣の巨城", type=FIELD_SPELL,
                  setcode=0x207a107a),
             card(METALMORPH, name_ja="メタル化・魔法反射装甲", type=TRAP),
             card(MIRROR_FORCE, name_ja="聖なるバリア －ミラーフォース－", type=TRAP),
             card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=0x11, level=7, race=0x1,
                  attribute=0x20, atk=2500, **{"def": 2100}),
             ] + SUPPORT_CARDS
    faq = [faq(HOLY_SWORD_CASTLE, "聖騎士と聖剣の巨城", HOLY_SWORD_CASTLE_TEXT),
           faq(METALMORPH, "メタル化・魔法反射装甲", METALMORPH_TEXT),
           faq(MIRROR_FORCE, "聖なるバリア －ミラーフォース－", MIRROR_FORCE_TEXT)] + SUPPORT_FAQ
    archetypes = HOLY_SWORD_ARCHETYPES

    def destroy(self, card_id):
        return self.hits(actions=["破壞"], replacement=True, card=card_id)

    def test_destroy_hits_with_an_equip_spell(self):
        self.assertIn(HOLY_SWORD_CASTLE, self.destroy(MAGE_POWER))

    def test_destroy_hits_with_any_monster(self):
        self.assertIn(HOLY_SWORD_CASTLE, self.destroy(BLACK_MAGICIAN))

    def test_destroy_misses_with_a_spell_that_is_not_an_equip_spell(self):
        self.assertJudgedMiss(HOLY_SWORD_CASTLE, actions=["破壞"], replacement=True,
                              card=MONSTER_REBORN)

    def test_destroy_hits_with_a_trap_whose_text_mentions_equipping(self):
        self.assertIn(HOLY_SWORD_CASTLE, self.destroy(METALMORPH))

    def test_destroy_misses_with_a_trap_whose_text_never_mentions_equipping(self):
        self.assertJudgedMiss(HOLY_SWORD_CASTLE, actions=["破壞"], replacement=True,
                              card=MIRROR_FORCE)

    def test_the_replacement_writes_back_to_its_text(self):
        self.assertWritesBack(HOLY_SWORD_CASTLE, "代わりに自分フィールドの装備カード１枚を破壊できる")


ROCKET_HAND = 13317419
ROCKET_HAND_TEXT = (
    "このカード名の①②の効果は１ターンに１度、いずれか１つしか使用できない。"
    "①：自分フィールドの攻撃力８００以上の攻撃表示モンスター１体を対象としてこのカードを発動できる。"
    "このカードを攻撃力８００アップの装備カード扱いとしてそのモンスターに装備する。"
    "②：装備されているこのカードを墓地へ送り、フィールドの表側表示のカード１枚を対象として発動できる。"
    "そのカードを破壊する。その後、このカードを装備していたモンスターは攻撃力が０になり、表示形式を変更できない。")


class RocketHandTest(GoldenCase):
    """ロケットハンド 13317419:既有的 `裝備中` 字面「装備されているこのカード」用同一條判法(使用者故事 29);
    「装備カード扱いとして」照舊是裝備段的方式字面。"""
    cards = [card(ROCKET_HAND, name_ja="ロケットハンド", type=TRAP)] + SUPPORT_CARDS
    faq = [faq(ROCKET_HAND, "ロケットハンド", ROCKET_HAND_TEXT)] + SUPPORT_FAQ

    def test_send_to_graveyard_hits_with_this_trap_itself(self):
        self.assertIn(ROCKET_HAND, self.hits(actions=["送墓"], card=ROCKET_HAND))

    def test_send_to_graveyard_misses_with_monster_reborn(self):
        self.assertJudgedMiss(ROCKET_HAND, actions=["送墓"], card=MONSTER_REBORN)

    def test_the_equip_segment_keeps_its_treat_literal(self):
        self.assertWritesBack(
            ROCKET_HAND, "このカードを攻撃力８００アップの装備カード扱いとしてそのモンスターに装備する")


class EquippedMonsterTest(GoldenCase):
    """魔導師の力 83746708:「装備モンスター」照舊讀成 `被裝備者`,任何怪獸都代得進去(使用者故事 30)。"""
    cards = list(SUPPORT_CARDS) + [
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=0x11, level=7, race=0x1,
             attribute=0x20, atk=2500, **{"def": 2100})]
    faq = list(SUPPORT_FAQ)

    def test_stat_change_hits_with_any_monster(self):
        self.assertIn(MAGE_POWER, self.hits(actions=["性質變更"], card=BLACK_MAGICIAN))


# 整張通過反向檢查的標準卡:四張候選卡都卡在這張票以外的寫法,改用這兩張(票 05 之後才整張通過)。
WITCH_MORGAN = 24027078
WITCH_MORGAN_TEXT = (
    "このカード名の効果は１ターンに１度しか使用できない。"
    "①：自分フィールドに「聖騎士」モンスター及び「聖剣」装備魔法カードが存在し、"
    "相手が魔法・罠・モンスターの効果を発動した時、このカードを手札から墓地へ送って発動できる。"
    "自分フィールドの「聖剣」装備魔法カード１枚を選んで破壊し、その発動を無効にする。")
CALIBURN = 23562407            # 聖剣カリバーン:「聖剣」裝備魔法
SWORD_MUSEUM = 25807544        # 大聖剣博物館:「聖剣」場地魔法


class WitchMorganTest(GoldenCase):
    """アヴァロンの魔女モルガン 24027078:「「聖剣」装備魔法カード」。"""
    cards = [card(WITCH_MORGAN, name_ja="アヴァロンの魔女モルガン", level=3, race=0x2,
                  attribute=0x20, atk=1300, **{"def": 1600}),
             card(CALIBURN, name_ja="聖剣カリバーン", type=EQUIP_SPELL, setcode=0x207a),
             card(SWORD_MUSEUM, name_ja="大聖剣博物館", type=FIELD_SPELL, setcode=0x207a)]
    faq = [faq(WITCH_MORGAN, "アヴァロンの魔女モルガン", WITCH_MORGAN_TEXT)]
    archetypes = HOLY_SWORD_ARCHETYPES

    def test_destroy_hits_with_a_holy_sword_equip_spell(self):
        self.assertIn(WITCH_MORGAN, self.hits(actions=["破壞"], card=CALIBURN))

    def test_destroy_misses_with_a_holy_sword_field_spell(self):
        self.assertJudgedMiss(WITCH_MORGAN, actions=["破壞"], card=SWORD_MUSEUM)

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertWholeCardPasses(WITCH_MORGAN)


DEMONSMITH = 60764609
DEMONSMITH_TEXT = (
    "このカード名の①②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードを手札から捨てて発動できる。デッキから「デモンスミス」魔法・罠カード１枚を手札に加える。\n"
    "②：自分フィールドの「デモンスミス」装備カード１枚とフィールドのモンスター１体を対象として発動できる。"
    "そのカードを墓地へ送る。\n"
    "③：このカードが墓地に存在する場合、自分の墓地から他の悪魔族・光属性モンスター１体を"
    "デッキ・EXデッキに戻して発動できる。このカードを特殊召喚する。")
DEMONSMITH_ARCHETYPES = [{"setcode": 0x1b0, "hex": "0x1b0", "names_ja": ["デモンスミス"],
                          "name_zh": "刻魔", "source": "strings.conf"}]


class DemonsmithTest(GoldenCase):
    """魔を刻むデモンスミス 60764609:「「デモンスミス」装備カード１枚」(取對象宣言那一段沒有動作詞,
    查詢比不到;只驗整張寫得回原文)。"""
    cards = [card(DEMONSMITH, name_ja="魔を刻むデモンスミス", level=6, race=0x8, attribute=0x10,
                  atk=1800, setcode=0x1b0, **{"def": 2400})]
    faq = [faq(DEMONSMITH, "魔を刻むデモンスミス", DEMONSMITH_TEXT)]
    archetypes = DEMONSMITH_ARCHETYPES

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertWholeCardPasses(DEMONSMITH)


if __name__ == "__main__":
    unittest.main()
