"""異同原子與「〜とは〜が異なり、」(m3 票 06)。

「與某物件的某屬性相同/不同」:物件群內成員之間(カード名が異なるカード３枚)單張卡代入一律符合;
比較對象是別的物件(そのモンスターとはカード名が異なる〜)時照引用比較,先求被引用物件的候選卡。
接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
from test_anaphora_this_card import _WithArchetypes
from test_golden import SPELL, TRAP, card, faq
from test_object_boundary import BLACK_MAGICIAN, NORMAL_MONSTER, POT_OF_GREED

BLACK_MAGICIAN_CARD = card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER,
                           level=7, race=0x2, attribute=0x20, atk=2500)
POT_OF_GREED_CARD = card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL)
KURIBOH = 40640057           # クリボー:效果怪獸、闇
KURIBOH_CARD = card(KURIBOH, name_ja="クリボー", level=1, race=0x8, attribute=0x20, atk=300)
ZANJI = 95519486             # 六武衆－ザンジ:戰士族、光、攻 1800
XYZ_MONSTER = 0x800021


class _Cards(_WithArchetypes):
    def assertJudgedMiss(self, cid, **query):
        """判得了、不命中:不在命中組,也不落進未解析組。"""
        self.assertNotIn(cid, self.hits(**query))
        self.assertNotIn(cid, self.unparsed(**query))

    def segment_texts(self, cid):
        structure = next(s for s in self.structures if s["id"] == cid)
        return [seg["text"] for block in structure["blocks"] for seg in block["segments"]]


DESTINY_DRAW = 856784
DESTINY_DRAW_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。"
    "①：自分のLPが相手より少なく、フィールドの攻撃力が一番高いモンスターが相手フィールドに存在する場合に発動できる。"
    "デッキからカード名が異なるカード３枚を選んで相手に見せ、その３枚をシャッフルしてデッキの上に戻す。"
    "その後、自分はデッキから１枚ドローする。"
    "このカードの発動後、ターン終了時まで自分は魔法・罠カードをセットできず、"
    "魔法・罠・モンスターの効果を１度しか発動できない。")


class DestinyDrawTest(_Cards):
    """運命のドロー 856784:「カード名が異なるカード３枚」是同群成員之間的卡名不同(使用者故事 29)。"""
    cards = [card(DESTINY_DRAW, name_ja="運命のドロー", type=SPELL),
             BLACK_MAGICIAN_CARD, POT_OF_GREED_CARD]
    faq = [faq(DESTINY_DRAW, "運命のドロー", DESTINY_DRAW_TEXT)]

    def test_reveal_hits_with_any_card_as_the_object(self):
        """查「展示」指定任一張卡:單張卡代入一律符合,不落進未解析組。"""
        for other in (BLACK_MAGICIAN, POT_OF_GREED):
            query = dict(actions=["展示"], card=other)
            self.assertIn(DESTINY_DRAW, self.hits(**query))
            self.assertNotIn(DESTINY_DRAW, self.unparsed(**query))

    def test_cards_with_different_names_is_not_a_generic_object(self):
        """帶著「卡名彼此不同」,不是泛用物件。"""
        self.assertNotIn(DESTINY_DRAW, self.hits(actions=["展示"], generic_only=True))

    def test_the_reveal_writes_back_to_its_text(self):
        self.assertWritesBack(DESTINY_DRAW, "デッキからカード名が異なるカード３枚を選んで相手に見せ")


SIX_SAMURAI = 0x103d
SIX_SAMURAI_ARCHETYPES = [
    {"setcode": SIX_SAMURAI, "hex": "0x103d", "names_ja": ["六武衆"], "name_zh": "六武眾",
     "source": "strings.conf"},
]
ASCETICISM = 27821104
ASCETICISM_TEXT = (
    "①：自分フィールドの「六武衆」モンスター１体を対象として発動できる。"
    "そのモンスターとはカード名が異なり、攻撃力が同じ「六武衆」モンスター１体をデッキから特殊召喚する。"
    "対象のモンスターはこのターンのエンドフェイズに破壊される。")
KIZAN = 49721904      # 真六武衆－キザン:攻 1800(與 ザンジ 同攻)
INSTRUCTOR = 83039729  # 六武衆の師範:攻 2100(沒有別的六武眾同攻)


class AsceticismOfTheSixSamuraiTest(_Cards):
    """六武衆の荒行 27821104:「そのモンスターとはカード名が異なり、」是右半物件的條件(卡名與對象不同),
    不另成段;「攻撃力が同じ」比的也是對象(使用者故事 38)。"""
    archetypes = SIX_SAMURAI_ARCHETYPES
    cards = [
        card(ASCETICISM, name_ja="六武衆の荒行", type=0x10002, setcode=SIX_SAMURAI),
        card(ZANJI, name_ja="六武衆－ザンジ", level=4, race=0x1, attribute=0x10, atk=1800,
             setcode=SIX_SAMURAI),
        card(KIZAN, name_ja="真六武衆－キザン", level=4, race=0x1, attribute=0x1, atk=1800,
             setcode=SIX_SAMURAI),
        card(INSTRUCTOR, name_ja="六武衆の師範", level=5, race=0x1, attribute=0x1, atk=2100,
             setcode=SIX_SAMURAI),
        BLACK_MAGICIAN_CARD,
    ]
    faq = [faq(ASCETICISM, "六武衆の荒行", ASCETICISM_TEXT)]

    def test_the_left_half_is_not_a_segment_of_its_own(self):
        self.assertFalse([text for text in self.segment_texts(ASCETICISM)
                          if text.endswith("異なり")])

    def test_special_summon_from_deck_still_hits(self):
        self.assertIn(ASCETICISM, self.hits(actions=["特殊召喚"], from_zones=["牌組"]))

    def test_hits_for_a_six_samurai_with_the_same_attack_and_another_name(self):
        """指定 ザンジ:對象可以是同攻、不同名的 キザン。"""
        self.assertIn(ASCETICISM, self.hits(actions=["特殊召喚"], card=ZANJI))

    def test_misses_when_the_only_target_with_that_attack_has_the_same_name(self):
        """指定 師範:同攻的六武眾只有它自己(同名),判得了、不命中。"""
        self.assertJudgedMiss(ASCETICISM, actions=["特殊召喚"], card=INSTRUCTOR)

    def test_misses_for_a_monster_that_is_not_a_six_samurai(self):
        self.assertJudgedMiss(ASCETICISM, actions=["特殊召喚"], card=BLACK_MAGICIAN)

    def test_the_summon_writes_back_to_its_text(self):
        self.assertWritesBack(
            ASCETICISM,
            "そのモンスターとはカード名が異なり、攻撃力が同じ「六武衆」モンスター１体をデッキから特殊召喚する")

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(ASCETICISM), [])


UA = 0xb2
UA_ARCHETYPES = [
    {"setcode": UA, "hex": "0xb2", "names_ja": ["Ｕ.Ａ."], "name_zh": "U.A.", "source": "strings.conf"},
]
LIBERO_SPIKER = 11637481
LIBERO_SPIKER_TEXT = (
    "このカード名の、①の方法による特殊召喚は１ターンに１度しかできず、②の効果は１ターンに１度しか使用できない。"
    "①：このカードは「U.A.リベロスパイカー」以外の自分フィールドの「U.A.」モンスター１体を手札に戻し、"
    "手札から特殊召喚できる。"
    "②：相手メインフェイズに発動できる。手札のレベル５以上の「U.A.」モンスター１体をデッキに戻し、"
    "そのモンスターとはカード名が異なる「U.A.」モンスター１体をデッキから特殊召喚する。"
    "その後、フィールドのこのカードを持ち主の手札に戻す。")
MIGHTY_SLUGGER = 56421754   # U.A.マイティスラッガー:等級 5
FANTASISTA = 72491806       # U.A.ファンタジスタ:等級 4


class LiberoSpikerTest(_Cards):
    """U.A.リベロスパイカー 11637481:「そのモンスターとはカード名が異なる「U.A.」モンスター１体」——
    比較對象寫在物件短語裡,「と」不是兩個物件的連接。"""
    archetypes = UA_ARCHETYPES
    cards = [
        card(LIBERO_SPIKER, name_ja="Ｕ．Ａ．リベロスパイカー", level=4, race=0x1, attribute=0x1,
             atk=1800, setcode=UA),
        card(MIGHTY_SLUGGER, name_ja="Ｕ．Ａ．マイティスラッガー", level=5, race=0x1, attribute=0x1,
             atk=2300, setcode=UA),
        card(FANTASISTA, name_ja="Ｕ．Ａ．ファンタジスタ", level=4, race=0x1, attribute=0x1,
             atk=1200, setcode=UA),
        BLACK_MAGICIAN_CARD,
    ]
    faq = [faq(LIBERO_SPIKER, "U.A.リベロスパイカー", LIBERO_SPIKER_TEXT)]

    def test_summon_from_deck_hits_for_a_ua_monster_named_differently_from_the_returned_one(self):
        """指定 ファンタジスタ:送回牌組的可以是等級 5 的 マイティスラッガー(不同名)。"""
        self.assertIn(LIBERO_SPIKER,
                      self.hits(actions=["特殊召喚"], from_zones=["牌組"], card=FANTASISTA))

    def test_summon_from_deck_misses_for_the_only_monster_that_can_be_returned(self):
        """指定 マイティスラッガー:等級 5 以上的 U.A. 只有它自己,同名;送回牌組的那一隻不是被特殊召喚的。"""
        self.assertJudgedMiss(LIBERO_SPIKER, actions=["特殊召喚"], from_zones=["牌組"],
                              card=MIGHTY_SLUGGER)

    def test_summon_from_deck_misses_for_a_monster_that_is_not_ua(self):
        self.assertJudgedMiss(LIBERO_SPIKER, actions=["特殊召喚"], from_zones=["牌組"],
                              card=BLACK_MAGICIAN)

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(LIBERO_SPIKER), [])


PAINFUL_DECISION = 1033312
PAINFUL_DECISION_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。"
    "①：デッキからレベル４以下の通常モンスター１体を墓地へ送り、その同名モンスター１体をデッキから手札に加える。")
SAPPHIRE_DRAGON = 11091375   # サファイアドラゴン:等級 4 的通常怪獸


class PainfulDecisionTest(_Cards):
    """苦渋の決断 1033312:「その同名モンスター１体」——與剛送去墓地的那一隻同名。"""
    cards = [
        card(PAINFUL_DECISION, name_ja="苦渋の決断", type=SPELL),
        card(SAPPHIRE_DRAGON, name_ja="サファイアドラゴン", type=NORMAL_MONSTER, level=4,
             race=0x2000, attribute=0x8, atk=1900),
        KURIBOH_CARD,
        BLACK_MAGICIAN_CARD,
    ]
    faq = [faq(PAINFUL_DECISION, "苦渋の決断", PAINFUL_DECISION_TEXT)]

    def test_add_to_hand_hits_for_a_normal_monster_that_can_be_sent(self):
        self.assertIn(PAINFUL_DECISION, self.hits(actions=["加入手牌"], card=SAPPHIRE_DRAGON))

    def test_add_to_hand_misses_for_monsters_that_cannot_be_the_sent_one(self):
        """效果怪獸、等級 7 的通常怪獸都不會是送去墓地的那一隻,也就沒有同名的。"""
        for other in (KURIBOH, BLACK_MAGICIAN):
            self.assertJudgedMiss(PAINFUL_DECISION, actions=["加入手牌"], card=other)

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(PAINFUL_DECISION), [])


FUMA_WAVE = 2994495
FUMA_WAVE_TEXT = (
    "①：フィールドの表側表示モンスター１体を対象として発動できる。"
    "そのモンスターとはカード名が異なり、同じ属性を持つフィールドのモンスター１体を選んで破壊する。")


class FumaWaveTest(_Cards):
    """風魔の波動 2994495:「そのモンスターとはカード名が異なり、同じ属性を持つ〜」——左半不另成段,
    「同じ属性を持つ」比的也是對象。"""
    cards = [
        card(FUMA_WAVE, name_ja="風魔の波動", type=TRAP),
        KURIBOH_CARD,
        BLACK_MAGICIAN_CARD,
        card(ZANJI, name_ja="六武衆－ザンジ", level=4, race=0x1, attribute=0x10, atk=1800),
        POT_OF_GREED_CARD,
    ]
    faq = [faq(FUMA_WAVE, "風魔の波動", FUMA_WAVE_TEXT)]

    def test_destroy_hits_when_another_monster_shares_the_attribute(self):
        """指定 クリボー(闇):對象可以是同屬性、不同名的 ブラック・マジシャン。"""
        self.assertIn(FUMA_WAVE, self.hits(actions=["破壞"], card=KURIBOH))

    def test_destroy_misses_when_no_other_monster_shares_the_attribute(self):
        """ザンジ 是這份卡表裡唯一的光屬性怪獸。"""
        self.assertJudgedMiss(FUMA_WAVE, actions=["破壞"], card=ZANJI)

    def test_destroy_misses_for_a_spell(self):
        self.assertJudgedMiss(FUMA_WAVE, actions=["破壞"], card=POT_OF_GREED)

    def test_the_whole_card_is_two_segments_and_passes_the_reverse_check(self):
        self.assertEqual(len(self.segment_texts(FUMA_WAVE)), 2)
        self.assertEqual(self.failures(FUMA_WAVE), [])


VISAS = 56099748
VISAS_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。"
    "①：このカードが手札に存在する場合、このカードとは種族と属性が異なる自分フィールドのモンスター１体を"
    "対象として発動できる。そのモンスターを破壊し、このカードを特殊召喚する。"
    "②：このカードが戦闘で相手モンスターを破壊した時に発動できる。"
    "そのモンスターの元々の攻撃力と元々の守備力の内、高い方の数値の半分だけこのカードの攻撃力はアップする。")
VALKYRIA = 80304126   # マジシャンズ・ヴァルキリア:魔法使族、光——只有種族與此卡不同


class VisasStarfrostTest(_Cards):
    """ヴィサス＝スタフロスト 56099748:「このカードとは種族と属性が異なる〜」——比較對象是此卡;
    屬性寫了兩個,兩個都不同才算。"""
    cards = [
        card(VISAS, name_ja="ヴィサス＝スタフロスト", level=6, race=0x1, attribute=0x10, atk=2100),
        BLACK_MAGICIAN_CARD,   # 魔法使族、闇:兩個都不同
        card(VALKYRIA, name_ja="マジシャンズ・ヴァルキリア", level=4, race=0x2, attribute=0x10,
             atk=1600),
        card(ZANJI, name_ja="六武衆－ザンジ", level=4, race=0x1, attribute=0x10, atk=1800),
    ]
    faq = [faq(VISAS, "ヴィサス＝スタフロスト", VISAS_TEXT)]

    def test_targets_a_monster_whose_race_and_attribute_both_differ(self):
        self.assertIn(VISAS, self.hits(targeting=True, actions=["破壞"], card=BLACK_MAGICIAN))

    def test_does_not_target_a_monster_that_shares_the_attribute(self):
        for other in (VALKYRIA, ZANJI):
            self.assertJudgedMiss(VISAS, targeting=True, actions=["破壞"], card=other)

    def test_the_targeting_declaration_writes_back_to_its_text(self):
        self.assertWritesBack(
            VISAS,
            "このカードが手札に存在する場合、このカードとは種族と属性が異なる自分フィールドのモンスター１体を"
            "対象として")


CYBERSPACE = 0x14e
CYBERSPACE_ARCHETYPES = [
    {"setcode": CYBERSPACE, "hex": "0x14e", "names_ja": ["電脳堺"], "name_zh": "電腦堺",
     "source": "strings.conf"},
]
CHUCHU = 12571621
CHUCHU_TEXT = (
    "このカード名の効果は１ターンに１度しか使用できない。"
    "①：このカードが手札に存在する場合、自分フィールドの「電脳堺」カード１枚を対象として発動できる。"
    "そのカードとは種類（モンスター・魔法・罠）が異なる「電脳堺」カード１枚をデッキから墓地へ送り、"
    "このカードを特殊召喚する。"
    "このターンのエンドフェイズに、自分の墓地から「電脳堺豸－豸々」以外の「電脳堺」モンスター１体を選んで"
    "手札に加える事ができる。"
    "このターン、自分はレベルまたはランクが３以上のモンスターしか特殊召喚できない。")
NYANNYAN = 8736823    # 電脳堺姫－娘々:怪獸
KOWLOON = 14886190    # 電脳堺都－九竜:魔法
_CHUCHU_CARDS = [
    card(CHUCHU, name_ja="電脳堺豸－豸々", level=3, race=0x800000, attribute=0x1, atk=1000,
         setcode=CYBERSPACE),
    card(NYANNYAN, name_ja="電脳堺姫－娘々", level=3, race=0x100000, attribute=0x8, atk=1500,
         setcode=CYBERSPACE),
    POT_OF_GREED_CARD,
]


class CardKindDiffersTest(_Cards):
    """電脳堺豸－豸々 12571621:「そのカードとは種類（モンスター・魔法・罠）が異なる「電脳堺」カード１枚」。"""
    archetypes = CYBERSPACE_ARCHETYPES
    cards = _CHUCHU_CARDS + [card(KOWLOON, name_ja="電脳堺都－九竜", type=SPELL, setcode=CYBERSPACE)]
    faq = [faq(CHUCHU, "電脳堺豸－豸々", CHUCHU_TEXT)]

    def test_send_to_grave_hits_when_the_target_can_be_another_kind_of_card(self):
        """指定怪獸:對象可以是魔法卡 九竜;指定 九竜:對象可以是怪獸。"""
        for other in (NYANNYAN, KOWLOON):
            self.assertIn(CHUCHU, self.hits(actions=["送墓"], card=other))

    def test_send_to_grave_misses_for_a_card_outside_the_archetype(self):
        self.assertJudgedMiss(CHUCHU, actions=["送墓"], card=POT_OF_GREED)

    def test_the_send_writes_back_to_its_text(self):
        self.assertWritesBack(
            CHUCHU, "そのカードとは種類（モンスター・魔法・罠）が異なる「電脳堺」カード１枚をデッキから墓地へ送り")


class CardKindAllTheSameTest(_Cards):
    """同一句,卡表裡的「電脳堺」卡全是怪獸:對象也只能是怪獸,指定怪獸時種類相同、不命中。"""
    archetypes = CYBERSPACE_ARCHETYPES
    cards = _CHUCHU_CARDS
    faq = [faq(CHUCHU, "電脳堺豸－豸々", CHUCHU_TEXT)]

    def test_send_to_grave_misses_when_every_possible_target_is_the_same_kind(self):
        self.assertJudgedMiss(CHUCHU, actions=["送墓"], card=NYANNYAN)


XYZ_SHIFT = 8339504
XYZ_SHIFT_TEXT = (
    "自分フィールド上のエクシーズモンスター１体をリリースして発動できる。"
    "リリースしたモンスターと同じ種族・属性・ランクでカード名が異なるモンスター１体をエクストラデッキから特殊召喚し、"
    "このカードを下に重ねてエクシーズ素材とする。"
    "この効果で特殊召喚したモンスターは、エンドフェイズ時に墓地へ送られる。"
    "「エクシーズ・シフト」は１ターンに１枚しか発動できない。")
UTOPIA = 84013237        # No.39 希望皇ホープ:戰士族、光、階級 4
EXCALIBUR = 60645181     # H－C エクスカリバー:戰士族、光、階級 4
EMERAL = 581014          # ダイガスタ・エメラル:岩石族、風、階級 4


class XyzShiftTest(_Cards):
    """エクシーズ・シフト 8339504:「リリースしたモンスターと同じ種族・属性・ランクでカード名が異なるモンスター１体」——
    屬性寫了三個,三個都相同才算;後面的「カード名が異なる」比的是同一隻。"""
    cards = [
        card(XYZ_SHIFT, name_ja="エクシーズ・シフト", type=SPELL),
        card(UTOPIA, name_ja="Ｎｏ．３９ 希望皇ホープ", type=XYZ_MONSTER, level=4, race=0x1,
             attribute=0x10, atk=2500),
        card(EXCALIBUR, name_ja="Ｈ－Ｃ エクスカリバー", type=XYZ_MONSTER, level=4, race=0x1,
             attribute=0x10, atk=2000),
        card(EMERAL, name_ja="ダイガスタ・エメラル", type=XYZ_MONSTER, level=4, race=0x100,
             attribute=0x8, atk=1800),
    ]
    faq = [faq(XYZ_SHIFT, "エクシーズ・シフト", XYZ_SHIFT_TEXT)]

    def test_summon_hits_when_another_xyz_shares_race_attribute_and_rank(self):
        self.assertIn(XYZ_SHIFT, self.hits(actions=["特殊召喚"], card=UTOPIA))

    def test_summon_misses_when_no_other_xyz_shares_all_three(self):
        """エメラル:同階級,但種族、屬性沒有別的超量怪獸相同。(後面「この効果で特殊召喚したモンスターは、
        エンドフェイズ時に墓地へ送られる」這輪解析不出,所以這張卡仍列在未解析組。)"""
        self.assertNotIn(XYZ_SHIFT, self.hits(actions=["特殊召喚"], card=EMERAL))

    def test_the_summon_writes_back_to_its_text(self):
        self.assertWritesBack(
            XYZ_SHIFT,
            "リリースしたモンスターと同じ種族・属性・ランクでカード名が異なるモンスター１体を"
            "エクストラデッキから特殊召喚し")


CLAN_GATHERING = 8608979
CLAN_GATHERING_TEXT = (
    "①：フィールドの表側表示モンスター１体を対象として発動できる。"
    "そのモンスターと元々のカード名が異なり、元々の種族が同じモンスター１体を自分の手札・墓地から選んで特殊召喚する。"
    "②：魔法＆罠ゾーンのこのカードが相手の効果で破壊された場合に発動できる。"
    "デッキから「一族の結集」１枚を選んで自分の魔法＆罠ゾーンにセットする。")


class ClanGatheringTest(_Cards):
    """一族の結集 8608979:「そのモンスターと元々のカード名が異なり、元々の種族が同じ〜」——沒有「は」的寫法、
    帶「元々の」。"""
    cards = [
        card(CLAN_GATHERING, name_ja="一族の結集", type=TRAP),
        KURIBOH_CARD,   # 惡魔族
        card(ZANJI, name_ja="六武衆－ザンジ", level=4, race=0x1, attribute=0x10, atk=1800),
        card(KIZAN, name_ja="真六武衆－キザン", level=4, race=0x1, attribute=0x1, atk=1800),
    ]
    faq = [faq(CLAN_GATHERING, "一族の結集", CLAN_GATHERING_TEXT)]

    def test_summon_hits_when_another_monster_shares_the_race(self):
        """指定 ザンジ(戰士族):對象可以是同種族、不同名的 キザン。"""
        self.assertIn(CLAN_GATHERING, self.hits(actions=["特殊召喚"], card=ZANJI))

    def test_summon_misses_when_no_other_monster_shares_the_race(self):
        """クリボー 是這份卡表裡唯一的惡魔族。"""
        self.assertJudgedMiss(CLAN_GATHERING, actions=["特殊召喚"], card=KURIBOH)

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(CLAN_GATHERING), [])


INTO_THE_VRAINS = 28827503
INTO_THE_VRAINS_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。"
    "①：手札からモンスター１体を効果を無効にして特殊召喚し、"
    "そのモンスターを含む自分フィールドのモンスターを素材としてリンク召喚する。"
    "そのリンク召喚は無効化されず、そのリンク召喚成功時に相手は魔法・罠・モンスターの効果を発動できない。"
    "②：このカードが墓地に存在する状態で、自分フィールドのリンクモンスターが戦闘・効果で破壊された場合、"
    "このカードを除外して発動できる。"
    "元々の種族がそのモンスターと同じモンスター１体を自分の墓地から選んで手札に加える。")
LINK_MONSTER = 0x4000021
DECODE_TALKER = 1861629   # デコード・トーカー:電子界族的連結怪獸
CYBERSE = 0x1000000


class IntoTheVrainsTest(_Cards):
    """Into the VRAINS！ 28827503:「元々の種族がそのモンスターと同じモンスター１体」——比較對象寫在屬性後面。"""
    cards = [
        card(INTO_THE_VRAINS, name_ja="Ｉｎｔｏ ｔｈｅ ＶＲＡＩＮＳ！", type=SPELL),
        card(DECODE_TALKER, name_ja="デコード・トーカー", type=LINK_MONSTER, level=3, race=CYBERSE,
             attribute=0x20, atk=2300),
        card(KURIBOH, name_ja="クリボー", level=1, race=CYBERSE, attribute=0x20, atk=300),
        BLACK_MAGICIAN_CARD,
    ]
    faq = [faq(INTO_THE_VRAINS, "Into the VRAINS！", INTO_THE_VRAINS_TEXT)]

    def test_add_to_hand_hits_for_a_monster_of_the_same_race_as_a_link_monster(self):
        """這份卡表把 クリボー 設成電子界族:與連結怪獸 デコード・トーカー 同種族。"""
        self.assertIn(INTO_THE_VRAINS, self.hits(actions=["加入手牌"], card=KURIBOH))

    def test_add_to_hand_misses_for_a_race_no_link_monster_has(self):
        self.assertNotIn(INTO_THE_VRAINS, self.hits(actions=["加入手牌"], card=BLACK_MAGICIAN))

    def test_the_add_writes_back_to_its_text(self):
        self.assertWritesBack(
            INTO_THE_VRAINS, "元々の種族がそのモンスターと同じモンスター１体を自分の墓地から選んで手札に加える")


PAIR_CYCROID = 16114248
PAIR_CYCROID_TEXT = "同名の機械族モンスター×２\n①：このカードは直接攻撃できる。"
FUSION_MONSTER = 0x61


class PairCycroidTest(_Cards):
    """ペアサイクロイド 16114248:素材行「同名の機械族モンスター×２」——同群成員之間同名。"""
    cards = [card(PAIR_CYCROID, name_ja="ペアサイクロイド", type=FUSION_MONSTER, level=5, race=0x20,
                  attribute=0x1, atk=1600)]
    faq = [faq(PAIR_CYCROID, "ペアサイクロイド", PAIR_CYCROID_TEXT)]

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertIn("同名の機械族モンスター×２", self.segment_texts(PAIR_CYCROID))
        self.assertEqual(self.failures(PAIR_CYCROID), [])


PURRELY = 0x18c
PURRELY_ARCHETYPES = [
    {"setcode": PURRELY, "hex": "0x18c", "names_ja": ["ピュアリィ"], "name_zh": "純愛妖精",
     "source": "strings.conf"},
]
PURRELY_SHARELY = 10780049
PURRELY_SHARELY_TEXT = (
    "①：自分フィールドの「ピュアリィ」Xモンスター１体を対象として発動できる。"
    "デッキからレベル１の「ピュアリィ」モンスター１体を効果を無効にして特殊召喚し、"
    "対象のモンスターとは属性が異なり、ランクが同じ「ピュアリィ」Xモンスター１体を"
    "その特殊召喚したモンスターの上に重ねてX召喚扱いでEXデッキから特殊召喚する。"
    "その後、以下の効果を適用できる。\n"
    "●対象のモンスターがX素材としている「ピュアリィ」速攻魔法カードの同名カード１枚をデッキから選び、"
    "そのX召喚したモンスターのX素材とする。")


class PurrelySharelyTest(_Cards):
    """ピュアリィ・シェアリィ！？ 10780049:「対象のモンスターとは属性が異なり、」同一個讀法——不另成段。
    右半「〜の上に重ねてX召喚扱いで〜特殊召喚する」這輪不收,整張不要求。"""
    archetypes = PURRELY_ARCHETYPES
    cards = [card(PURRELY_SHARELY, name_ja="ピュアリィ・シェアリィ！？", type=TRAP, setcode=PURRELY)]
    faq = [faq(PURRELY_SHARELY, "ピュアリィ・シェアリィ！？", PURRELY_SHARELY_TEXT)]

    def test_the_left_half_stays_in_the_segment_of_the_summon(self):
        texts = self.segment_texts(PURRELY_SHARELY)
        self.assertFalse([text for text in texts if text.endswith("異なり")])
        self.assertTrue([text for text in texts
                         if text.startswith("対象のモンスターとは属性が異なり、ランクが同じ")
                         and text.endswith("特殊召喚する")])
