"""標準卡剩下的時點與降臨:只走接縫一(查詢判斷)與接縫二(反向檢查)。

- 「「X」により降臨」:召喚手續段,動作詞 儀式召喚,原因 效果帶物件 X,極性 做。
- 「Xした/されたターンのエンドフェイズに」:前提 本回合發生過(指向那個動作的條件段)且
  遊戲狀態 結束階段;舊式「〜ターンのエンドフェイズ時」同一個讀法。
- 時點列舉「〜ターンのエンドフェイズ及び、〜ターンのエンドフェイズに」:兩個時點的或。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import card, faq

RITUAL_MONSTER = 0x81
RITUAL_SPELL = 0x82

LAW_GUARDIAN = 3627449      # ローガーディアン
LAW_GUARDIAN_TEXT = (
    "「ローの祈り」により降臨。場か手札から、星の数が合計７個以上になるようカードを"
    "生け贄に捧げなければならない。")
LAW_PRAYER = 43694075       # ローの祈り


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs)
    return structures


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def own(structures, cid):
    return next(c for c in structures if c["id"] == cid)


def failed_texts(structure):
    """反向檢查沒過的段的原文(段外殘留與段樹的列 None)。"""
    texts = {s["id"]: s["text"] for b in structure["blocks"] for s in b["segments"]}
    return [texts.get(f["segment"]) for f in check_card(structure)]


class LawGuardianTest(unittest.TestCase):
    """ローガーディアン 3627449:「「ローの祈り」により降臨」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(LAW_GUARDIAN, name_ja="ローガーディアン", type=RITUAL_MONSTER, level=7,
                 race=0x1, attribute=0x10, atk=2050, **{"def": 2500}),
            card(LAW_PRAYER, name_ja="ローの祈り", type=RITUAL_SPELL),
        ]
        cls.structures = build(cls.cards, [faq(LAW_GUARDIAN, "ローガーディアン",
                                               LAW_GUARDIAN_TEXT)])

    def test_ritual_summon_hits_the_descent_line(self):
        """查「儀式召喚」命中「「ローの祈り」により降臨」(召喚手續段,預設就看)。"""
        self.assertIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["儀式召喚"]))

    def test_special_summon_hits_through_the_hypernym(self):
        """儀式召喚是特殊召喚的下位詞:查「特殊召喚」也命中。"""
        self.assertIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["特殊召喚"]))

    def test_other_actions_do_not_hit_the_descent_line(self):
        """查「融合召喚」不命中;查「儀式召喚」只算不能/只能的極性時也不命中(極性是做)。"""
        self.assertNotIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["融合召喚"]))
        self.assertNotIn(LAW_GUARDIAN, hits(self.cards, self.structures, actions=["儀式召喚"],
                                            polarities=["不能", "只能"]))

    def test_descent_line_writes_back(self):
        """降臨句寫回原文相符。"""
        self.assertNotIn("「ローの祈り」により降臨",
                         failed_texts(own(self.structures, LAW_GUARDIAN)))


SAURAVIS = 4810828          # 古聖戴サウラヴィス
SAURAVIS_TEXT = (
    "「精霊の祝福」により降臨\n"
    "①：自分フィールドのモンスターを対象とする魔法・罠・モンスターの効果を相手が発動した時、"
    "このカードを手札から捨てて発動できる。その発動を無効にする。")
SPIRIT_BLESSING = 37626500  # 精霊の祝福


class DescentWithoutPeriodTest(unittest.TestCase):
    """古聖戴サウラヴィス 4810828:降臨句不以句號結尾,被區塊切分歸成素材行。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SAURAVIS, name_ja="古聖戴サウラヴィス", type=0xa1, level=7, race=0x2000,
                 attribute=0x10, atk=2600, **{"def": 2800}),
            card(SPIRIT_BLESSING, name_ja="精霊の祝福", type=RITUAL_SPELL),
        ]
        cls.structures = build(cls.cards, [faq(SAURAVIS, "古聖戴サウラヴィス", SAURAVIS_TEXT)])

    def test_ritual_summon_hits(self):
        self.assertIn(SAURAVIS, hits(self.cards, self.structures, actions=["儀式召喚"]))

    def test_descent_line_writes_back(self):
        self.assertNotIn("「精霊の祝福」により降臨",
                         failed_texts(own(self.structures, SAURAVIS)))


MIRACLE_RAVEN = 18988396    # ミラクル・レイヴン－供物の儀式－(儀式・靈擺怪獸)
MIRACLE_RAVEN_TEXT = (
    "「ミラクル・レイヴン－供物の儀式－」により降臨\n"
    "このカードは儀式召喚でしか特殊召喚できない。")


class DescentByOwnNameTest(unittest.TestCase):
    """ミラクル・レイヴン－供物の儀式－ 18988396:降臨句寫的是自己的卡名。"""

    def test_own_name_writes_back_as_the_name(self):
        cards = [card(MIRACLE_RAVEN, name_ja="ミラクル・レイヴン－供物の儀式－", type=0x10000a1,
                      level=1, race=0x8, attribute=0x20, atk=300, **{"def": 300})]
        structures = build(cards, [faq(MIRACLE_RAVEN, "ミラクル・レイヴン－供物の儀式－",
                                       MIRACLE_RAVEN_TEXT)])
        self.assertEqual(check_card(own(structures, MIRACLE_RAVEN)), [])
        self.assertIn(MIRACLE_RAVEN, hits(cards, structures, actions=["儀式召喚"]))


LEARNER_DEVICE = 42149850   # 使い捨て学習装置
LEARNER_DEVICE_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。①：装備モンスターの攻撃力は、"
    "自分の墓地のモンスターの数×２００アップする。②：このカードがフィールドから墓地へ送られた"
    "ターンのエンドフェイズに発動できる。このカードを自分フィールドにセットする。"
    "この効果でセットしたこのカードはフィールドから離れた場合に除外される。")


class LearnerDeviceTest(unittest.TestCase):
    """使い捨て学習装置 42149850 ②:「このカードがフィールドから墓地へ送られたターンのエンドフェイズに
    発動できる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(LEARNER_DEVICE, name_ja="使い捨て学習装置", type=0x40002)]
        cls.structures = build(cls.cards, [faq(LEARNER_DEVICE, "使い捨て学習装置",
                                               LEARNER_DEVICE_TEXT)])

    def test_sent_to_graveyard_is_a_condition_segment(self):
        """「フィールドから墓地へ送られたターン」是條件段:查「送墓,從場上」開條件段命中,
        關掉不命中。"""
        query = dict(actions=["送墓"], from_zones=["場上"], card=LEARNER_DEVICE)
        self.assertIn(LEARNER_DEVICE, hits(self.cards, self.structures,
                                           include_condition=True, **query))
        self.assertNotIn(LEARNER_DEVICE, hits(self.cards, self.structures, **query))

    def test_set_inherits_the_graveyard_from_the_condition(self):
        """後面的「このカードを自分フィールドにセットする」從墓地出發(繼承條件段的到)。"""
        self.assertIn(LEARNER_DEVICE, hits(self.cards, self.structures, actions=["覆蓋"],
                                           from_zones=["墓地"], card=LEARNER_DEVICE))

    def test_whole_card_writes_back(self):
        """整張寫回原文相符:發動句的兩段(條件段、只有前提的段)與離場那一句都過。"""
        self.assertEqual(check_card(own(self.structures, LEARNER_DEVICE)), [])


SAFFIRA = 56350972          # 竜姫神サフィラ
SAFFIRA_TEXT = (
    "「祝祷の聖歌」により降臨。このカード名の効果は１ターンに１度しか使用できない。"
    "①：このカードが儀式召喚したターンのエンドフェイズ及び、このカードがモンスターゾーンに存在し、"
    "手札・デッキから光属性モンスターが墓地へ送られたターンのエンドフェイズに、"
    "以下の効果から１つを選択して発動できる。\n"
    "●自分はデッキから２枚ドローし、その後手札を１枚選んで捨てる。\n"
    "●相手の手札をランダムに１枚選んで墓地へ捨てる。\n"
    "●自分の墓地の光属性モンスター１体を選んで手札に加える。")
HYMN = 80566312             # 祝祷の聖歌
FIRST_TIMEPOINT = "このカードが儀式召喚したターン"
SECOND_TIMEPOINT = ("このカードがモンスターゾーンに存在し、"
                    "手札・デッキから光属性モンスターが墓地へ送られたターン")


class SaffiraTimepointsTest(unittest.TestCase):
    """竜姫神サフィラ 56350972 ①:時點列舉「〜ターンのエンドフェイズ及び、〜ターンのエンドフェイズに、
    以下の効果から１つを選択して発動できる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SAFFIRA, name_ja="竜姫神サフィラ", type=0xa1, level=6, race=0x2000,
                 attribute=0x10, atk=2500, **{"def": 2400}),
            card(HYMN, name_ja="祝祷の聖歌", type=RITUAL_SPELL),
        ]
        cls.structures = build(cls.cards, [faq(SAFFIRA, "竜姫神サフィラ", SAFFIRA_TEXT)])
        cls.own = own(cls.structures, SAFFIRA)

    def hit_texts(self, **query):
        texts = {s["id"]: s["text"] for b in self.own["blocks"] for s in b["segments"]}
        result = run_query(self.structures, self.cards, query)
        return [texts[seg_id] for hit in result["hits"] if hit["id"] == SAFFIRA
                for seg_id in hit["segments"]]

    def test_descent_line_hits_ritual_summon_and_writes_back(self):
        self.assertIn("「祝祷の聖歌」により降臨", self.hit_texts(actions=["儀式召喚"]))
        self.assertNotIn("「祝祷の聖歌」により降臨", failed_texts(self.own))

    def test_first_timepoint_is_a_condition_segment(self):
        """「このカードが儀式召喚したターン」是條件段:開條件段查「儀式召喚」命中它,關掉只中降臨句。"""
        self.assertIn(FIRST_TIMEPOINT,
                      self.hit_texts(actions=["儀式召喚"], include_condition=True))
        self.assertNotIn(FIRST_TIMEPOINT, self.hit_texts(actions=["儀式召喚"]))

    def test_second_timepoint_is_its_own_condition_segment(self):
        """第二個時點的動作子句自成條件段(句首的「存在し、」是它的前提),不與第一個時點黏在一起:
        開條件段查「送墓,從手牌」命中的就是它;關掉條件段不命中,也不列進未解析組。"""
        query = dict(actions=["送墓"], from_zones=["手牌"])
        self.assertEqual(self.hit_texts(include_condition=True, **query), [SECOND_TIMEPOINT])
        off = run_query(self.structures, self.cards, query)
        self.assertNotIn(SAFFIRA, [h["id"] for h in off["hits"]] + off["groups"]["未解析"])

    def test_timepoint_enumeration_writes_back(self):
        """整張寫回原文相符:時點列舉、分歧引導句與兩個時點的動作子句都過,區塊沒有段外殘留。"""
        self.assertEqual(check_card(self.own), [])

    def test_branches_still_hit(self):
        """● 各支照舊命中(分歧的各支不因引導句的前提改變)。"""
        self.assertTrue(self.hit_texts(actions=["抽牌"], from_zones=["牌組"]))
        self.assertTrue(self.hit_texts(actions=["加入手牌"], from_zones=["墓地"]))


TG_WEREWOLF = 293542        # TG ワーウルフ
TG_WEREWOLF_TEXT = (
    "①：レベル４以下のモンスターが特殊召喚された時に発動できる。このカードを手札から特殊召喚する。\n"
    "②：フィールドのこのカードが破壊され墓地へ送られたターンのエンドフェイズに発動できる。"
    "デッキから「TG ワーウルフ」以外の「TG」モンスター１体を手札に加える。")
TG_STRIKER = 1315120        # TG ストライカー(setcode 0x27)
TG_DESTROYED = "フィールドのこのカードが破壊され墓地へ送られたターン"
TG_ARCHETYPES = [{"setcode": 0x27, "hex": "0x27", "names_ja": ["TG"], "name_zh": "T.G.",
                  "source": "strings.conf"}]


class TgWerewolfTest(unittest.TestCase):
    """TG ワーウルフ 293542 ②:「〜破壊され墓地へ送られたターンのエンドフェイズに発動できる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(TG_WEREWOLF, name_ja="TG ワーウルフ", level=3, race=0x8000, attribute=0x20,
                 atk=1200, setcode=0x27, **{"def": 0}),
            card(TG_STRIKER, name_ja="TG ストライカー", level=2, race=0x1, attribute=0x1,
                 atk=800, setcode=0x27, type=0x1021, **{"def": 0}),
        ]
        cls.structures, _ = build_structures(
            cls.cards, [faq(TG_WEREWOLF, "TG ワーウルフ", TG_WEREWOLF_TEXT)],
            archetypes=TG_ARCHETYPES)
        cls.own = own(cls.structures, TG_WEREWOLF)

    def listed(self, **query):
        result = run_query(self.structures, self.cards, query)
        return [h["id"] for h in result["hits"]] + result["groups"]["未解析"]

    def test_destroyed_turn_is_a_condition_not_a_cost(self):
        """「破壊され墓地へ送られたターン」是條件段:查「破壞」預設(不看條件段)時這張卡不在命中組
        也不在未解析組;開條件段才列出(命中,或連用形被動串接解析不出時列進未解析組)。"""
        self.assertNotIn(TG_WEREWOLF, self.listed(actions=["破壞"]))
        self.assertIn(TG_WEREWOLF, self.listed(actions=["破壞"], include_condition=True))

    def test_search_effect_still_hits(self):
        self.assertIn(TG_WEREWOLF, hits(self.cards, self.structures, actions=["加入手牌"],
                                        from_zones=["牌組"], card=TG_STRIKER))
        self.assertNotIn(TG_WEREWOLF, hits(self.cards, self.structures, actions=["加入手牌"],
                                           from_zones=["牌組"], card=TG_WEREWOLF))

    def test_activation_sentence_is_parsed_and_the_phase_writes_back(self):
        """發動句不標「發動句解析不出」;「のエンドフェイズに」那一段寫回原文相符。沒過的只剩
        條件段的述語「破壊され墓地へ送られた」(連用形被動串接)。"""
        details = [f["detail"] for f in check_card(self.own)]
        self.assertNotIn("段解析不出:發動句解析不出", details)
        self.assertLessEqual(set(failed_texts(self.own)), {TG_DESTROYED})


OLD_STYLE = 10001101        # 合成卡:舊式「エンドフェイズ時」與列舉的一般規則
FAIRY = 10001102            # 合成卡:光屬性怪獸


def synthetic(text):
    cards = [card(OLD_STYLE, name_ja="甲"), card(FAIRY, name_ja="乙", race=0x4, attribute=0x10)]
    return cards, build(cards, [faq(OLD_STYLE, "甲", text)])


class TurnPhaseFormsTest(unittest.TestCase):
    """「Xしたターンの〈階段〉に」各種寫法(句型取自官方卡文,物件換成此卡)。"""

    def test_old_style_end_phase_toki_reads_the_same(self):
        """舊式「〜ターンのエンドフェイズ時に破壊される」(ボーンクラッシャー 37675138 的句子):
        條件段是特殊召喚(開條件段才命中),破壞段照常命中;整張通過。"""
        cards, structures = synthetic(
            "このカードは特殊召喚されたターンのエンドフェイズ時に破壊される。")
        self.assertEqual(check_card(own(structures, OLD_STYLE)), [])
        self.assertIn(OLD_STYLE, hits(cards, structures, actions=["破壞"], card=OLD_STYLE))
        self.assertNotIn(OLD_STYLE, hits(cards, structures, actions=["特殊召喚"]))
        self.assertIn(OLD_STYLE, hits(cards, structures, actions=["特殊召喚"],
                                      include_condition=True))

    def test_old_style_toki_with_comma_and_cost_after_the_phase(self):
        for text in (
                "このカードが墓地へ送られたターンのエンドフェイズ時、このカードを除外する。",
                "①：このカードが墓地へ送られたターンのエンドフェイズに、このカードを除外して"
                "発動できる。デッキからカードを１枚ドローする。"):
            with self.subTest(text=text):
                cards, structures = synthetic(text)
                self.assertEqual(check_card(own(structures, OLD_STYLE)), [])
                self.assertIn(OLD_STYLE, hits(cards, structures, actions=["除外"],
                                              from_zones=["墓地"], card=OLD_STYLE))

    def test_other_phases_of_that_turn(self):
        """階段不限結束階段:「このカードを発動したターンの自分メインフェイズに」。"""
        cards, structures = synthetic(
            "①：このカードを発動したターンの自分メインフェイズに発動できる。"
            "このカードを破壊する。")
        self.assertEqual(check_card(own(structures, OLD_STYLE)), [])

    def test_enumerated_timepoints_at_sentence_level(self):
        """時點列舉不只在分歧引導句:「T1及び、T2に発動できる」兩個時點各成條件段,整張通過。"""
        cards, structures = synthetic(
            "①：このカードが儀式召喚したターンのエンドフェイズ及び、このカードが墓地へ送られた"
            "ターンのエンドフェイズに発動できる。このカードを除外する。")
        self.assertEqual(check_card(own(structures, OLD_STYLE)), [])
        for action in ("儀式召喚", "送墓"):
            self.assertIn(OLD_STYLE, hits(cards, structures, actions=[action],
                                          include_condition=True))
            self.assertNotIn(OLD_STYLE, hits(cards, structures, actions=[action]))

    def test_later_timepoint_keeps_its_own_leading_premise(self):
        """第二個時點帶自己的句首前提(サフィラ ① 的句型,前提換成已收的「〜状態で、」):
        前提掛在那個時點的條件段上,整張通過。"""
        cards, structures = synthetic(
            "①：このカードが儀式召喚したターンのエンドフェイズ及び、このカードがモンスターゾーンに"
            "存在する状態で、手札・デッキから光属性モンスターが墓地へ送られたターンのエンドフェイズに、"
            "以下の効果から１つを選択して発動できる。\n●このカードを破壊する。\n●このカードを除外する。")
        self.assertEqual(check_card(own(structures, OLD_STYLE)), [])
        query = dict(actions=["送墓"], from_zones=["牌組"], include_condition=True)
        self.assertIn(OLD_STYLE, hits(cards, structures, card=FAIRY, **query))
        self.assertNotIn(OLD_STYLE, hits(cards, structures, card=OLD_STYLE, **query))

    def test_condition_position_flows_into_the_branches(self):
        """引導句的時點發生在各支之前:條件段的到(墓地)是各支的從。"""
        cards, structures = synthetic(
            "①：このカードが墓地へ送られたターンのエンドフェイズに、以下の効果から１つを選択して"
            "発動できる。\n●このカードを特殊召喚する。\n●このカードを除外する。")
        self.assertEqual(check_card(own(structures, OLD_STYLE)), [])
        self.assertIn(OLD_STYLE, hits(cards, structures, actions=["特殊召喚"],
                                      from_zones=["墓地"], card=OLD_STYLE))

    def test_forms_outside_this_rule_stay_unparsed(self):
        """不收的寫法照舊解析不出、不被這條規則誤認:「〜エンドフェイズ時まで」(期間)、
        「〜した相手ターンのエンドフェイズに」(回合另帶方)。被誤認的話,「ターン」前的動作子句會成條件段、
        開條件段查那個動作詞就命中;照舊解析不出則不命中、列進未解析組。"""
        for text, action in (
                ("このカードの効果は発動したターンのエンドフェイズ時まで適用される。", "發動"),
                ("①：このカードが墓地へ送られた相手ターンのエンドフェイズに発動できる。"
                 "このカードを特殊召喚する。", "送墓")):
            with self.subTest(text=text):
                cards, structures = synthetic(text)
                result = run_query(structures, cards,
                                   {"actions": [action], "include_condition": True})
                self.assertNotIn(OLD_STYLE, [h["id"] for h in result["hits"]])
                self.assertIn(OLD_STYLE, result["groups"]["未解析"])

    def test_turn_comma_then_game_state_keeps_the_condition_segment(self):
        """「〜したターン、自分メインフェイズに発動できる」:條件段不掉成段外殘留。"""
        _, structures = synthetic(
            "①：このカードを発動したターン、自分メインフェイズに発動できる。このカードを破壊する。")
        self.assertEqual(check_card(own(structures, OLD_STYLE)), [])


if __name__ == "__main__":
    unittest.main()
