"""離場(m3 票 10)——「フィールドから離れた」的動作詞、連動的「離れた時に〜は破壊される」、
自我限制的「フィールドから離れた場合に除外される」(照代替記)、原因「相手によって」。

接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
from test_golden import SPELL, TRAP, card, faq
from test_object_boundary import BLACK_MAGICIAN, NORMAL_MONSTER, _Golden

BLACK_MAGICIAN_CARD = card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER,
                           level=7, race=0x2, attribute=0x20, atk=2500)

LIMIT_REVERSE = 27551
LIMIT_REVERSE_TEXT = (
    "自分の墓地の攻撃力１０００以下のモンスター１体を選択し、表側攻撃表示で特殊召喚する。"
    "そのモンスターが守備表示になった時、そのモンスターとこのカードを破壊する。"
    "このカードがフィールド上から離れた時、そのモンスターを破壊する。"
    "そのモンスターが破壊された時、このカードを破壊する。")

ANCIENT_GEAR_FRAME = 1278431
ANCIENT_GEAR_FRAME_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：手札を１枚捨てて発動できる。「古代の機械巨人」１体またはそのカード名が記された魔法・罠カード１枚を"
    "デッキから手札に加える。\n"
    "②：このカードが攻撃する場合、相手はダメージステップ終了時まで魔法・罠カードを発動できない。\n"
    "③：表側表示のこのカードが相手の効果でフィールドから離れた場合に発動できる。"
    "手札から「古代の機械巨人」「古代の機械巨人－アルティメット・パウンド」を合計３体まで"
    "召喚条件を無視して特殊召喚する。")


class LimitReverseTest(_Golden):
    """リミット・リバース 27551:「このカードがフィールド上から離れた時」是條件段 離場。"""
    cards = [card(LIMIT_REVERSE, name_ja="リミット・リバース", type=TRAP | 0x20000),
             BLACK_MAGICIAN_CARD]
    faq = [faq(LIMIT_REVERSE, "リミット・リバース", LIMIT_REVERSE_TEXT)]

    def test_leaving_the_field_hits_with_condition_segments(self):
        self.assertIn(LIMIT_REVERSE, self.hits(actions=["離場"], include_condition=True))

    def test_leaving_the_field_is_a_condition_not_an_effect(self):
        """條件段開關關著時不命中,也不落進未解析組。"""
        self.assertNotIn(LIMIT_REVERSE, self.hits(actions=["離場"]))
        self.assertNotIn(LIMIT_REVERSE, self.unparsed(actions=["離場"]))

    def test_this_card_is_what_leaves(self):
        query = dict(actions=["離場"], include_condition=True)
        self.assertIn(LIMIT_REVERSE, self.hits(card=LIMIT_REVERSE, **query))
        self.assertNotIn(LIMIT_REVERSE, self.hits(card=BLACK_MAGICIAN, **query))

    def test_it_leaves_from_the_field(self):
        query = dict(actions=["離場"], include_condition=True)
        self.assertIn(LIMIT_REVERSE, self.hits(from_zones=["場上"], **query))
        self.assertNotIn(LIMIT_REVERSE, self.hits(from_zones=["墓地"], **query))
        self.assertNotIn(LIMIT_REVERSE, self.hits(to_zones=["墓地"], include_inferred=True, **query))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(LIMIT_REVERSE, "このカードがフィールド上から離れた時")


class AncientGearFrameTest(_Golden):
    """古代の機械素体 1278431:「表側表示のこのカードが相手の効果でフィールドから離れた場合」。"""
    cards = [card(ANCIENT_GEAR_FRAME, name_ja="古代の機械素体", level=4, race=0x20,
                  attribute=0x1, atk=1600),
             BLACK_MAGICIAN_CARD]
    faq = [faq(ANCIENT_GEAR_FRAME, "古代の機械素体", ANCIENT_GEAR_FRAME_TEXT)]

    def test_leaving_the_field_hits_with_condition_segments(self):
        query = dict(actions=["離場"], include_condition=True)
        self.assertIn(ANCIENT_GEAR_FRAME, self.hits(**query))
        self.assertIn(ANCIENT_GEAR_FRAME, self.hits(card=ANCIENT_GEAR_FRAME, **query))
        self.assertNotIn(ANCIENT_GEAR_FRAME, self.hits(card=BLACK_MAGICIAN, **query))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(ANCIENT_GEAR_FRAME,
                              "表側表示のこのカードが相手の効果でフィールドから離れた場合")

    def test_leaving_is_not_destroying_banishing_sending_or_returning(self):
        """離場只比字面:查破壞、除外、送墓、返回不因「離れた」命中,也不落進未解析組。"""
        for action in ("破壞", "除外", "送墓", "返回"):
            query = dict(actions=[action], include_condition=True)
            self.assertNotIn(ANCIENT_GEAR_FRAME, self.hits(**query), action)
            self.assertNotIn(ANCIENT_GEAR_FRAME, self.unparsed(**query), action)

    def test_discarding_and_adding_to_hand_are_not_leaving(self):
        """①「手札を１枚捨てて」「手札に加える」不是離場:只開效果、代價段查不到。"""
        self.assertNotIn(ANCIENT_GEAR_FRAME, self.hits(actions=["離場"]))


EXOSISTER_MARTHA = 37343995
EXOSISTER_MARTHA_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分フィールドのモンスターが、存在しない場合またはXモンスターのみの場合に発動できる"
    "（この効果を発動するターン、自分は「エクソシスター」モンスターしか特殊召喚できない）。"
    "このカードを手札から特殊召喚し、デッキから「エクソシスター・エリス」１体を特殊召喚する。\n"
    "②：自分か相手のカードが墓地から離れた場合に発動できる。「エクソシスター」Xモンスター１体を"
    "自分フィールドのこのカードの上に重ねてX召喚扱いでEXデッキから特殊召喚する。")


class LeavingTheGraveyardTest(_Golden):
    """エクソシスター・マルファ 37343995:「墓地から離れた」不是離場(離場只算從場上離開)。"""
    cards = [card(EXOSISTER_MARTHA, name_ja="エクソシスター・マルファ", level=4, race=0x2,
                  attribute=0x10, atk=1600)]
    faq = [faq(EXOSISTER_MARTHA, "エクソシスター・マルファ", EXOSISTER_MARTHA_TEXT)]

    def test_leaving_the_graveyard_is_not_leaving_the_field(self):
        query = dict(actions=["離場"], include_condition=True)
        self.assertNotIn(EXOSISTER_MARTHA, self.hits(**query))
        self.assertNotIn(EXOSISTER_MARTHA, self.unparsed(**query))


JET_WARRIOR = 286392
JET_WARRIOR_TEXT = (
    "「ジェット・シンクロン」＋チューナー以外のモンスター１体以上\n"
    "「ジェット・ウォリアー」の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードがS召喚に成功した場合、相手フィールドのカード１枚を対象として発動できる。"
    "そのカードを持ち主の手札に戻す。"
    "②：このカードが墓地に存在する場合、自分フィールドのレベル２以下のモンスター１体をリリースして発動できる。"
    "このカードを墓地から守備表示で特殊召喚する。"
    "この効果で特殊召喚したこのカードは、フィールドから離れた場合に除外される。")
JET_WARRIOR_LEAVES = "この効果で特殊召喚したこのカードは、フィールドから離れた場合"


class JetWarriorTest(_Golden):
    """ジェット・ウォリアー 286392:「フィールドから離れた場合に除外される」照代替記——離場是被代替段、
    除外是做代替的段,文面沒有「代わりに」。"""
    cards = [card(JET_WARRIOR, name_ja="ジェット・ウォリアー", type=0x2021, level=5, race=0x1,
                  attribute=0x4, atk=2100),
             BLACK_MAGICIAN_CARD]
    faq = [faq(JET_WARRIOR, "ジェット・ウォリアー", JET_WARRIOR_TEXT)]

    def segment_texts(self, segment_ids):
        structure = next(s for s in self.structures if s["id"] == JET_WARRIOR)
        return [seg["text"] for block in structure["blocks"] for seg in block["segments"]
                if seg["id"] in segment_ids]

    def test_banish_does_not_hit_the_self_restriction_by_default(self):
        self.assertNotIn(JET_WARRIOR, self.hits(actions=["除外"]))
        self.assertNotIn(JET_WARRIOR, self.unparsed(actions=["除外"]))

    def test_banish_hits_the_replacing_segment_with_the_replacement_switch(self):
        hit = next(h for h in self.run_(actions=["除外"], replacement=True)["hits"]
                   if h["id"] == JET_WARRIOR)
        self.assertEqual(self.segment_texts(hit["segments"]), ["除外される"])

    def test_leaving_hits_with_the_replacement_switch_and_points_at_the_banish(self):
        hit = next(h for h in self.run_(actions=["離場"], replacement=True)["hits"]
                   if h["id"] == JET_WARRIOR)
        self.assertEqual(self.segment_texts(hit["segments"]), [JET_WARRIOR_LEAVES])
        self.assertEqual(self.segment_texts(hit["replaced_by"].values()), ["除外される"])

    def test_leaving_does_not_hit_without_the_replacement_switch(self):
        """被代替段只在代替開關開時看:條件段開關開著也不命中,不落進未解析組。"""
        query = dict(actions=["離場"], include_condition=True)
        self.assertNotIn(JET_WARRIOR, self.hits(**query))
        self.assertNotIn(JET_WARRIOR, self.unparsed(**query))

    def test_this_card_is_what_gets_banished(self):
        query = dict(actions=["除外"], replacement=True)
        self.assertIn(JET_WARRIOR, self.hits(card=JET_WARRIOR, **query))
        self.assertNotIn(JET_WARRIOR, self.hits(card=BLACK_MAGICIAN, **query))

    def test_leaving_does_not_hit_the_return_to_hand(self):
        """①「そのカードを持ち主の手札に戻す」只是返回,查離場(含代替、條件段)命中的只有離場那一段。"""
        hit = next(h for h in self.run_(actions=["離場"], replacement=True,
                                        include_condition=True)["hits"] if h["id"] == JET_WARRIOR)
        self.assertEqual(self.segment_texts(hit["segments"]), [JET_WARRIOR_LEAVES])

    def test_both_segments_write_back_to_their_text(self):
        self.assertWritesBack(JET_WARRIOR, JET_WARRIOR_LEAVES)
        self.assertWritesBack(JET_WARRIOR, "除外される")


CYBER_AMPLIFIER = 303660
CYBER_AMPLIFIER_TEXT = (
    "「人造人間－サイコ・ショッカー」にのみ装備可能。このカードの発動と効果は無効化されない。"
    "①：装備モンスターの持つ、「お互いにフィールドの罠カードの効果を発動できず、フィールドの罠カードの効果は"
    "無効化される」効果は、「相手はフィールドの罠カードの効果を発動できず、相手フィールドの罠カードの効果は"
    "無効化される」として適用される。"
    "②：このカードがフィールドから離れた時に装備モンスターは破壊される。")


class CyberAmplifierTest(_Golden):
    """電脳増幅器 303660:「このカードがフィールドから離れた時に装備モンスターは破壊される」
    在「時に」切成條件段(離場)加效果段(破壞)。"""
    cards = [card(CYBER_AMPLIFIER, name_ja="電脳増幅器", type=SPELL | 0x40000),
             BLACK_MAGICIAN_CARD]
    faq = [faq(CYBER_AMPLIFIER, "電脳増幅器", CYBER_AMPLIFIER_TEXT)]

    def test_destroy_hits_the_linked_destruction(self):
        self.assertIn(CYBER_AMPLIFIER, self.hits(actions=["破壞"]))
        self.assertIn(CYBER_AMPLIFIER, self.hits(actions=["破壞"], card=BLACK_MAGICIAN))
        self.assertNotIn(CYBER_AMPLIFIER, self.hits(actions=["破壞"], card=CYBER_AMPLIFIER))

    def test_leaving_hits_only_with_condition_segments(self):
        self.assertIn(CYBER_AMPLIFIER, self.hits(actions=["離場"], include_condition=True,
                                                 card=CYBER_AMPLIFIER))
        self.assertNotIn(CYBER_AMPLIFIER, self.hits(actions=["離場"]))

    def test_both_segments_write_back_to_their_text(self):
        self.assertWritesBack(CYBER_AMPLIFIER, "このカードがフィールドから離れた時")
        self.assertWritesBack(CYBER_AMPLIFIER, "装備モンスターは破壊される")


DARK_KNIGHT = 86282581
DARK_KNIGHT_TEXT = (
    "悪魔族モンスター＋戦士族モンスター\n"
    "このカードは「ダーク・フュージョン」の効果でのみ特殊召喚できる。\n"
    "①：相手フィールドのモンスターの攻撃力は、このカードの融合素材としたモンスターの元々の攻撃力の合計分ダウンする。\n"
    "②：このカードは１度のバトルフェイズ中に２回攻撃できる。\n"
    "③：特殊召喚した表側表示のこのカードが相手によってフィールドから離れた場合、"
    "自分の墓地の悪魔族・戦士族モンスター１体を対象として発動できる。そのモンスターを守備表示で特殊召喚する。")


class DarkKnightTest(_Golden):
    """E-HERO ダーク・ナイト 86282581:原因「相手によって」(戰鬥或效果、方 對手)。"""
    cards = [card(DARK_KNIGHT, name_ja="E-HERO ダーク・ナイト", type=0x61, level=8, race=0x8,
                  attribute=0x1, atk=1600),
             card(94820406, name_ja="ダーク・フュージョン", type=SPELL)]
    faq = [faq(DARK_KNIGHT, "E-HERO ダーク・ナイト", DARK_KNIGHT_TEXT)]

    def test_leaving_by_the_opponent_hits_with_condition_segments(self):
        query = dict(actions=["離場"], include_condition=True)
        self.assertIn(DARK_KNIGHT, self.hits(card=DARK_KNIGHT, **query))
        self.assertNotIn(DARK_KNIGHT, self.unparsed(**query))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(DARK_KNIGHT,
                              "特殊召喚した表側表示のこのカードが相手によってフィールドから離れた場合")

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(DARK_KNIGHT), [])


DISPOSABLE_LEARNER = 42149850
DISPOSABLE_LEARNER_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。"
    "①：装備モンスターの攻撃力は、自分の墓地のモンスターの数×２００アップする。"
    "②：このカードがフィールドから墓地へ送られたターンのエンドフェイズに発動できる。"
    "このカードを自分フィールドにセットする。"
    "この効果でセットしたこのカードはフィールドから離れた場合に除外される。")


class DisposableLearnerTest(_Golden):
    """使い捨て学習装置 42149850:「この効果でセットしたこのカードはフィールドから離れた場合に除外される」
    (「は」後沒有讀點)。"""
    cards = [card(DISPOSABLE_LEARNER, name_ja="使い捨て学習装置", type=SPELL | 0x40000)]
    faq = [faq(DISPOSABLE_LEARNER, "使い捨て学習装置", DISPOSABLE_LEARNER_TEXT)]

    def test_banish_only_hits_with_the_replacement_switch(self):
        self.assertNotIn(DISPOSABLE_LEARNER, self.hits(actions=["除外"]))
        self.assertIn(DISPOSABLE_LEARNER,
                      self.hits(actions=["除外"], replacement=True, card=DISPOSABLE_LEARNER))

    def test_the_whole_card_passes_the_reverse_check(self):
        self.assertEqual(self.failures(DISPOSABLE_LEARNER), [])


BIPOLAR_UNCHAINED = 1966438
BIPOLAR_UNCHAINED_TEXT = (
    "自分は「雙極の破械神」を１ターンに１度しか特殊召喚できない。\n"
    "①：自分フィールドのカードが戦闘・効果で破壊された場合に発動できる。このカードを手札から特殊召喚する。\n"
    "②：このカードが特殊召喚した場合、手札を１枚捨てて発動できる。フィールドのカード１枚を破壊する。\n"
    "③：フィールドのこのカードが破壊され墓地へ送られたターンのエンドフェイズに発動できる。"
    "このカードを特殊召喚する。"
    "この効果で特殊召喚したこのカードは、フィールドから離れた場合にデッキの一番下に戻る。")


class BipolarUnchainedTest(_Golden):
    """雙極の破械神 1966438:去處是「デッキの一番下に戻る」的自我限制,返回是做代替的段。"""
    cards = [card(BIPOLAR_UNCHAINED, name_ja="雙極の破械神", level=8, race=0x8, attribute=0x20,
                  atk=3000)]
    faq = [faq(BIPOLAR_UNCHAINED, "雙極の破械神", BIPOLAR_UNCHAINED_TEXT)]

    def test_return_to_the_bottom_of_the_deck_only_hits_with_the_replacement_switch(self):
        query = dict(actions=["返回"], to_zones=["牌組底"])
        self.assertNotIn(BIPOLAR_UNCHAINED, self.hits(**query))
        self.assertIn(BIPOLAR_UNCHAINED, self.hits(replacement=True, **query))

    def test_both_segments_write_back_to_their_text(self):
        self.assertWritesBack(BIPOLAR_UNCHAINED,
                              "この効果で特殊召喚したこのカードは、フィールドから離れた場合")
        self.assertWritesBack(BIPOLAR_UNCHAINED, "デッキの一番下に戻る")


CHAIN_DOG = 96930127
CHAIN_DOG_TEXT = (
    "自分フィールド上に獣族モンスターが表側表示で２体存在する場合、このカードを墓地から特殊召喚する事ができる。"
    "この効果で特殊召喚したこのカードはフィールド上から離れた場合、ゲームから除外される。"
    "このカードをシンクロ素材とする場合、獣族モンスターのシンクロ召喚にしか使用できない。")


class ChainDogTest(_Golden):
    """チェーンドッグ 96930127:舊式「フィールド上から離れた場合、ゲームから除外される」(觸發形後有讀點)
    同樣照代替記。"""
    cards = [card(CHAIN_DOG, name_ja="チェーンドッグ", level=4, race=0x4000, attribute=0x1, atk=1600)]
    faq = [faq(CHAIN_DOG, "チェーンドッグ", CHAIN_DOG_TEXT)]

    def test_banish_only_hits_with_the_replacement_switch(self):
        self.assertNotIn(CHAIN_DOG, self.hits(actions=["除外"]))
        self.assertNotIn(CHAIN_DOG, self.unparsed(actions=["除外"]))
        self.assertIn(CHAIN_DOG, self.hits(actions=["除外"], replacement=True, card=CHAIN_DOG))

    def test_leaving_points_at_the_banish(self):
        hit = next(h for h in self.run_(actions=["離場"], replacement=True)["hits"]
                   if h["id"] == CHAIN_DOG)
        self.assertEqual(len(hit["replaced_by"]), 1)

    def test_both_segments_write_back_to_their_text(self):
        self.assertWritesBack(CHAIN_DOG, "この効果で特殊召喚したこのカードはフィールド上から離れた場合")
        self.assertWritesBack(CHAIN_DOG, "ゲームから除外される")


WHITE_VEIL = 49306994
WHITE_VEIL_TEXT = (
    "①：装備モンスターが戦闘を行う場合、相手はダメージステップ終了時まで魔法・罠カードを発動できない。"
    "②：装備モンスターが戦闘を行う攻撃宣言時に発動する。相手フィールドの表側表示の魔法・罠カードの効果は"
    "ダメージステップ終了時まで無効化される。"
    "③：装備モンスターが戦闘で相手モンスターを破壊した時に発動できる。相手フィールドの魔法・罠カードを全て破壊する。"
    "④：魔法＆罠ゾーンの表側表示のこのカードがフィールドから離れた時に自分は３０００ダメージを受ける。")


class WhiteVeilTest(_Golden):
    """白のヴェール 49306994:主語帶區域(魔法＆罠ゾーンの〜このカード)的離場,連動的是傷害。"""
    cards = [card(WHITE_VEIL, name_ja="白のヴェール", type=SPELL | 0x40000)]
    faq = [faq(WHITE_VEIL, "白のヴェール", WHITE_VEIL_TEXT)]

    def test_leaving_from_the_spell_and_trap_zone_hits(self):
        query = dict(actions=["離場"], include_condition=True, card=WHITE_VEIL)
        self.assertIn(WHITE_VEIL, self.hits(from_zones=["魔陷區"], **query))
        self.assertIn(WHITE_VEIL, self.hits(from_zones=["場上"], **query))
        self.assertNotIn(WHITE_VEIL, self.hits(from_zones=["怪獸區"], **query))

    def test_damage_hits_the_linked_segment(self):
        self.assertIn(WHITE_VEIL, self.hits(actions=["傷害"]))

    def test_both_segments_write_back_to_their_text(self):
        self.assertWritesBack(WHITE_VEIL, "魔法＆罠ゾーンの表側表示のこのカードがフィールドから離れた時")
        self.assertWritesBack(WHITE_VEIL, "自分は３０００ダメージを受ける")


ZOMBIE_CARRIER = 33420078
ZOMBIE_CARRIER_TEXT = (
    "①：このカードが墓地に存在する場合、手札を１枚デッキの一番上に戻して発動できる。"
    "このカードを特殊召喚する。"
    "この効果で特殊召喚したこのカードは、フィールドから離れた場合に除外される。")

AUTONOMOUS_ACTION_UNIT = 71453557
AUTONOMOUS_ACTION_UNIT_TEXT = (
    "①：１５００LPを払い、相手の墓地のモンスター１体を対象としてこのカードを発動できる。"
    "そのモンスターを自分フィールドに攻撃表示で特殊召喚し、このカードを装備する。"
    "このカードがフィールドから離れた時にそのモンスターは破壊される。")

REBORN_TENGU = 10028593
REBORN_TENGU_TEXT = (
    "①：表側表示のこのカードがフィールドから離れた場合に発動する。"
    "デッキから「輪廻天狗」１体を特殊召喚する。")


class WholeCardTest(_Golden):
    """三種寫法各一張整張通過反向檢查的卡:自我限制(ゾンビキャリア 33420078)、連動
    (自律行動ユニット 71453557)、條件(輪廻天狗 10028593)。"""
    cards = [card(ZOMBIE_CARRIER, name_ja="ゾンビキャリア", type=0x1021, level=2, race=0x10,
                  attribute=0x20, atk=400),
             card(AUTONOMOUS_ACTION_UNIT, name_ja="自律行動ユニット", type=SPELL | 0x40000),
             card(REBORN_TENGU, name_ja="輪廻天狗", level=4, race=0x8000, attribute=0x8, atk=1700),
             BLACK_MAGICIAN_CARD]
    faq = [faq(ZOMBIE_CARRIER, "ゾンビキャリア", ZOMBIE_CARRIER_TEXT),
           faq(AUTONOMOUS_ACTION_UNIT, "自律行動ユニット", AUTONOMOUS_ACTION_UNIT_TEXT),
           faq(REBORN_TENGU, "輪廻天狗", REBORN_TENGU_TEXT)]

    def test_the_whole_cards_pass_the_reverse_check(self):
        for cid in (ZOMBIE_CARRIER, AUTONOMOUS_ACTION_UNIT, REBORN_TENGU):
            self.assertEqual(self.failures(cid), [], cid)

    def test_banish_only_hits_the_self_restriction_with_the_replacement_switch(self):
        self.assertEqual(self.hits(actions=["除外"]), [])
        self.assertEqual(self.hits(actions=["除外"], replacement=True), [ZOMBIE_CARRIER])

    def test_destroy_hits_the_linked_destruction_of_the_equipped_monster(self):
        """連動破壞的是特殊召喚出來的那隻(指回取對象的怪獸),不是這張裝備卡。"""
        self.assertEqual(self.hits(actions=["破壞"]), [AUTONOMOUS_ACTION_UNIT])
        self.assertEqual(self.hits(actions=["破壞"], card=BLACK_MAGICIAN), [AUTONOMOUS_ACTION_UNIT])
        self.assertEqual(self.hits(actions=["破壞"], card=AUTONOMOUS_ACTION_UNIT), [])

    def test_leaving_hits_by_segment_kind(self):
        """條件段開關只看得到條件的離場,代替開關只看得到自我限制的離場。"""
        self.assertEqual(self.hits(actions=["離場"]), [])
        self.assertEqual(sorted(self.hits(actions=["離場"], include_condition=True)),
                         sorted([AUTONOMOUS_ACTION_UNIT, REBORN_TENGU]))
        self.assertEqual(self.hits(actions=["離場"], replacement=True), [ZOMBIE_CARRIER])


GANASHIA = 18282103
GANASHIA_TEXT = (
    "①：このカードが手札から墓地へ捨てられた場合に発動する。このカードを特殊召喚する。"
    "この効果で特殊召喚したこのカードは、攻撃力が２００アップし、フィールドから離れた場合に除外される。")

NURIKABE = 60681372
NURIKABE_TEXT = (
    "このカード名の効果は１ターンに１度しか使用できない。\n"
    "①：このターンに墓地へ送られていないこのカードが墓地に存在する場合、１０００LPを払い、"
    "自分の墓地の他のアンデット族モンスター１体を対象として発動できる。そのモンスターとこのカードを特殊召喚する。"
    "この効果で特殊召喚したモンスターの効果は無効化され、フィールドから離れた場合に除外される。")


class ElidedSubjectTest(_Golden):
    """主語省略的「〜し、フィールドから離れた場合に除外される」:承本句的「Xは」;沒有「Xは」可承的不退回此卡。"""
    cards = [card(GANASHIA, name_ja="魔轟神獣ガナシア", level=3, race=0x4000, attribute=0x10,
                  atk=1600),
             card(NURIKABE, name_ja="妖魔ヌリカベ", level=4, race=0x10, attribute=0x1, atk=900),
             BLACK_MAGICIAN_CARD]
    faq = [faq(GANASHIA, "魔轟神獣ガナシア", GANASHIA_TEXT),
           faq(NURIKABE, "妖魔ヌリカベ", NURIKABE_TEXT)]

    def test_the_topic_of_the_sentence_is_what_gets_banished(self):
        """魔轟神獣ガナシア 18282103:省略的主語是句首的「この効果で特殊召喚したこのカードは」。"""
        query = dict(actions=["除外"], replacement=True)
        self.assertIn(GANASHIA, self.hits(card=GANASHIA, **query))
        self.assertNotIn(GANASHIA, self.hits(card=BLACK_MAGICIAN, **query))
        self.assertWritesBack(GANASHIA, "フィールドから離れた場合")
        self.assertWritesBack(GANASHIA, "除外される")

    def test_without_a_topic_this_card_is_not_assumed(self):
        """妖魔ヌリカベ 60681372:句首是「〜モンスターの効果は」,離場的主語沒有「Xは」可承——
        不當成此卡被除外,那一句留在未解析組。"""
        query = dict(actions=["除外"], replacement=True)
        self.assertNotIn(NURIKABE, self.hits(**query))
        self.assertIn(NURIKABE, self.unparsed(**query))
