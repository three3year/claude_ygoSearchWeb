"""連用形的宣告左半「Xを選択し、」「Xを対象とし、」。

走接縫一(查詢判斷)與接縫二(反向檢查);查詢層沒有的格(受方、選者)先用查詢命中段,再讀該段的格。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, TRAP, card, faq

CONTINUOUS_TRAP = TRAP | 0x20000


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def segment_failures(structures, cid, segs):
    """這幾段的反向檢查不通過清單(空 = 都寫得回原文)。"""
    ids = {seg["id"] for seg in segs}
    return [f for f in check_card(own(structures, cid)) if f["segment"] in ids]


LIMIT_REVERSE = 27551   # リミット・リバース
LIMIT_REVERSE_TEXT = (
    "自分の墓地の攻撃力１０００以下のモンスター１体を選択し、表側攻撃表示で特殊召喚する。"
    "そのモンスターが守備表示になった時、そのモンスターとこのカードを破壊する。"
    "このカードがフィールド上から離れた時、そのモンスターを破壊する。"
    "そのモンスターが破壊された時、このカードを破壊する。")


class LimitReverseTest(unittest.TestCase):
    """リミット・リバース 27551:「〜１体を選択し、表側攻撃表示で特殊召喚する」——左半是取對象宣告,
    右半省略的物件指回它。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(LIMIT_REVERSE, name_ja="リミット・リバース", type=CONTINUOUS_TRAP)]
        cls.structures, _ = build_structures(
            cls.cards, [faq(LIMIT_REVERSE, "リミット・リバース", LIMIT_REVERSE_TEXT)],
            archetypes=ARCHETYPES)

    def test_special_summon_from_graveyard_hits_with_targeting(self):
        """查「特殊召喚,從墓地」只看取對象:命中右半,它的物件就是左半取對象的那一個。"""
        declared, = hit_segments(self.structures, self.cards, LIMIT_REVERSE,
                                 targeting=True, from_zones=["墓地"], kinds=["效果"],
                                 polarities=("做",))[:1]
        summon, = hit_segments(self.structures, self.cards, LIMIT_REVERSE,
                               actions=["特殊召喚"], from_zones=["墓地"], targeting=True)
        self.assertEqual(summon["text"], "表側攻撃表示で特殊召喚する")
        self.assertEqual(declared["text"], "自分の墓地の攻撃力１０００以下のモンスター１体を選択し")
        self.assertEqual([line["object"] for line in summon["lines"]],
                         [line["object"] for line in declared["lines"]])

    def test_right_half_writes_back(self):
        """右半省略物件,模板不寫物件與助詞(左半的「攻撃力１０００以下の」是修飾語)。"""
        summon = hit_segments(self.structures, self.cards, LIMIT_REVERSE,
                              actions=["特殊召喚"], targeting=True)
        self.assertEqual(len(summon), 1)
        self.assertEqual(segment_failures(self.structures, LIMIT_REVERSE, summon), [])


SPELL_RECYCLING = 29228529   # 魔法再生
SPELL_RECYCLING_TEXT = (
    "手札の魔法カードを２枚墓地に送る。自分の墓地から魔法カードを１枚選択し、手札に加える。")
BATTERY_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x28, "hex": "0x28", "names_ja": ["電池メン"], "name_zh": "電池人",
     "source": "strings.conf"},
]
PORTABLE_BATTERY = 61840587   # 携帯型バッテリー
PORTABLE_BATTERY_TEXT = (
    "自分の墓地の「電池メン」と名のついたモンスター２体を選択し、表側攻撃表示で特殊召喚する。"
    "このカードがフィールド上から離れた時、そのモンスターを全て破壊する。"
    "そのモンスターが全てフィールド上から離れた時、このカードを破壊する。")


class SpellRecyclingTest(unittest.TestCase):
    """魔法再生 29228529:「自分の墓地から魔法カードを１枚選択し、手札に加える」——墓地的卡是取對象,
    右半只剩述語。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SPELL_RECYCLING, name_ja="魔法再生", type=TRAP)]
        cls.structures, _ = build_structures(
            cls.cards, [faq(SPELL_RECYCLING, "魔法再生", SPELL_RECYCLING_TEXT)],
            archetypes=ARCHETYPES)

    def test_add_to_hand_from_graveyard_hits_with_targeting(self):
        added, = hit_segments(self.structures, self.cards, SPELL_RECYCLING,
                              actions=["加入手牌"], from_zones=["墓地"], targeting=True)
        self.assertEqual(added["text"], "手札に加える")
        declared, = hit_segments(self.structures, self.cards, SPELL_RECYCLING, actions=[],
                                 from_zones=["墓地"], targeting=True)[:1]
        self.assertEqual(declared["text"], "自分の墓地から魔法カードを１枚選択し")
        self.assertEqual([line["object"] for line in added["lines"]],
                         [line["object"] for line in declared["lines"]])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, SPELL_RECYCLING)), [])


class PortableBatteryTest(unittest.TestCase):
    """携帯型バッテリー 61840587:「〜モンスター２体を選択し、」數量照字面記。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(PORTABLE_BATTERY, name_ja="携帯型バッテリー", type=CONTINUOUS_TRAP)]
        cls.structures, _ = build_structures(
            cls.cards, [faq(PORTABLE_BATTERY, "携帯型バッテリー", PORTABLE_BATTERY_TEXT)],
            archetypes=BATTERY_ARCHETYPES)

    def test_two_monsters_are_targeted_and_summoned(self):
        summon, = hit_segments(self.structures, self.cards, PORTABLE_BATTERY,
                               actions=["特殊召喚"], from_zones=["墓地"], targeting=True)
        line, = summon["lines"]
        target = next(o for o in own(self.structures, PORTABLE_BATTERY)["objects"]
                      if o["id"] == line["object"])
        self.assertEqual((target["count"]["value"], target["count"]["text"]), (2, "２体"))

    def test_both_halves_write_back(self):
        segs = hit_segments(self.structures, self.cards, PORTABLE_BATTERY,
                            from_zones=["墓地"], targeting=True)[:2]
        self.assertEqual([seg["text"] for seg in segs],
                         ["自分の墓地の「電池メン」と名のついたモンスター２体を選択し",
                          "表側攻撃表示で特殊召喚する"])
        self.assertEqual(segment_failures(self.structures, PORTABLE_BATTERY, segs), [])


FROG_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x12, "hex": "0x12", "names_ja": ["ガエル"], "name_zh": "青蛙",
     "source": "strings.conf"},
]
SUBSTITOAD = 20663556   # イレカエル
SUBSTITOAD_TEXT = (
    "自分フィールド上に存在するモンスター１体を生け贄に捧げる。"
    "自分のデッキから「ガエル」と名のついたモンスター１体を選択し、自分フィールド上に特殊召喚する。"
    "このカードがフィールド上に存在する限り、「ガエル」と名のついたモンスターは"
    "戦闘によっては破壊されない。")


class SubstitoadTest(unittest.TestCase):
    """イレカエル 20663556:「自分のデッキから〜１体を選択し、」是選擇,不是取對象。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SUBSTITOAD, name_ja="イレカエル", level=1, race=0x40, attribute=0x2,
                          atk=100, **{"def": 2000})]
        cls.structures, _ = build_structures(
            cls.cards, [faq(SUBSTITOAD, "イレカエル", SUBSTITOAD_TEXT)],
            archetypes=FROG_ARCHETYPES)

    def test_special_summon_from_deck_hits(self):
        """查「特殊召喚,從牌組」命中右半:省略的物件就是左半選的那一張。"""
        summon, = hit_segments(self.structures, self.cards, SUBSTITOAD,
                               actions=["特殊召喚"], from_zones=["牌組"])
        self.assertEqual(summon["text"], "自分フィールド上に特殊召喚する")
        selected, = hit_segments(self.structures, self.cards, SUBSTITOAD,
                                 from_zones=["牌組"], kinds=["效果"], actions=[])[:1]
        self.assertEqual(selected["text"],
                         "自分のデッキから「ガエル」と名のついたモンスター１体を選択し")
        self.assertEqual([line["object"] for line in summon["lines"]],
                         [line["object"] for line in selected["lines"]])

    def test_selection_from_deck_is_not_targeting(self):
        """只看取對象時,選擇的左半與接著的特殊召喚都不命中。"""
        self.assertEqual(hit_segments(self.structures, self.cards, SUBSTITOAD,
                                      actions=["特殊召喚"], targeting=True), [])
        self.assertEqual(hit_segments(self.structures, self.cards, SUBSTITOAD,
                                      from_zones=["牌組"], targeting=True), [])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, SUBSTITOAD)), [])


EMISSARY = 75043725   # 冥界の使者
EMISSARY_TEXT = (
    "このカードがフィールド上から墓地に送られた時、お互いに自分のデッキからレベル３以下の"
    "通常モンスター１体を選択し、お互いに確認して手札に加える。その後デッキをシャッフルする。")


def agent_side(seg):
    return seg["agent"]["side"] if isinstance(seg["agent"], dict) else seg["agent"]


class EmissaryOfTheAfterlifeTest(unittest.TestCase):
    """冥界の使者 75043725:「お互いに自分のデッキから〜１体を選択し、」記選擇,選者照主語(雙方各自)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(EMISSARY, name_ja="冥界の使者", race=0x8, attribute=0x20, atk=1600,
                          **{"def": 600})]
        cls.structures, _ = build_structures(
            cls.cards, [faq(EMISSARY, "冥界の使者", EMISSARY_TEXT)], archetypes=ARCHETYPES)

    def selection(self):
        seg, = hit_segments(self.structures, self.cards, EMISSARY, from_zones=["牌組"],
                            kinds=["效果"])
        return seg

    def test_selection_from_deck_is_recorded_with_both_players_choosing(self):
        seg = self.selection()
        self.assertEqual(seg["text"],
                         "お互いに自分のデッキからレベル３以下の通常モンスター１体を選択し")
        self.assertEqual(seg["actions"], [])
        self.assertEqual(agent_side(seg), "雙方各自")

    def test_add_to_hand_with_targeting_does_not_hit(self):
        """牌組裡的卡不是取對象:只看取對象時,查「加入手牌」與左半都不命中。"""
        self.assertEqual(hit_segments(self.structures, self.cards, EMISSARY,
                                      actions=["加入手牌"], targeting=True), [])
        self.assertEqual(hit_segments(self.structures, self.cards, EMISSARY,
                                      from_zones=["牌組"], targeting=True), [])

    def test_selection_writes_back(self):
        self.assertEqual(segment_failures(self.structures, EMISSARY, [self.selection()]), [])


UNION_MONSTER = 0x421   # 效果怪獸 + 聯合
CRUSH_WYVERN = 3405259   # C－クラッシュ・ワイバーン
CRUSH_WYVERN_TEXT = (
    "①：１ターンに１度、以下の効果を１つ発動できる。\n"
    "●自分フィールドの機械族・光属性モンスター１体を対象とし、"
    "このカードを装備魔法カード扱いで装備する。"
    "装備モンスターが戦闘・効果で破壊される場合、代わりにこのカードを破壊する。\n"
    "●装備状態のこのカードを特殊召喚する。\n"
    "②：装備モンスターは相手の罠カードの効果を受けない。\n"
    "③：このカードがフィールドから墓地へ送られた場合に発動できる。"
    "手札からユニオンモンスター１体を特殊召喚する。")
VALKYRIE_CHARIOT = 19190082   # 戦乙女の戦車
VALKYRIE_CHARIOT_TEXT = (
    "①：１ターンに１度、以下の効果から１つを選択して発動できる。"
    "●自分フィールドの天使族モンスター１体を対象とし、"
    "このカードを装備カード扱いとしてそのモンスターに装備する。"
    "装備モンスターが戦闘・効果で破壊される場合、代わりにこのカードを破壊する。"
    "●装備されているこのカードを特殊召喚する。"
    "②：装備モンスターの攻撃宣言時に発動できる。装備モンスターの攻撃力は５００アップする。")


class EquipAfterTargetingTest(unittest.TestCase):
    """「Xを対象とし、このカードを〜装備する」:左半的對象是裝備段的裝備對象(受方)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(CRUSH_WYVERN, name_ja="C－クラッシュ・ワイバーン", type=UNION_MONSTER,
                          race=0x20, attribute=0x10, atk=1200, **{"def": 2000}),
                     card(VALKYRIE_CHARIOT, name_ja="戦乙女の戦車", type=UNION_MONSTER,
                          race=0x4, attribute=0x10, level=3, atk=500, **{"def": 1000})]
        cls.structures, _ = build_structures(
            cls.cards, [faq(CRUSH_WYVERN, "C－クラッシュ・ワイバーン", CRUSH_WYVERN_TEXT),
                        faq(VALKYRIE_CHARIOT, "戦乙女の戦車", VALKYRIE_CHARIOT_TEXT)],
            archetypes=ARCHETYPES)

    def halves(self, cid):
        """(取對象宣告的左半, 裝備段)。"""
        declared, = hit_segments(self.structures, self.cards, cid, actions=[], targeting=True,
                                 from_zones=["場上"])
        equip, = hit_segments(self.structures, self.cards, cid, actions=["裝備"], targeting=True)
        return declared, equip

    def test_equip_hits_with_targeting_and_its_recipient_is_the_target(self):
        """查「裝備」只看取對象時命中;裝備對象沒寫出來(C－クラッシュ・ワイバーン)或寫成
        「そのモンスターに」(戦乙女の戦車),都是左半的對象。"""
        for cid, left, right in (
                (CRUSH_WYVERN, "自分フィールドの機械族・光属性モンスター１体を対象とし",
                 "このカードを装備魔法カード扱いで装備する"),
                (VALKYRIE_CHARIOT, "自分フィールドの天使族モンスター１体を対象とし",
                 "このカードを装備カード扱いとしてそのモンスターに装備する")):
            with self.subTest(card=cid):
                declared, equip = self.halves(cid)
                self.assertEqual((declared["text"], equip["text"]), (left, right))
                self.assertEqual([equip["recipient"]["object"]],
                                 [line["object"] for line in declared["lines"]])

    def test_equipped_card_itself_is_not_targeted(self):
        """被裝備上去的是此卡,它那條線不標取對象。"""
        _, equip = self.halves(CRUSH_WYVERN)
        self.assertEqual([line["targeting"] for line in equip["lines"]], [False])

    def test_both_halves_write_back(self):
        for cid in (CRUSH_WYVERN, VALKYRIE_CHARIOT):
            with self.subTest(card=cid):
                self.assertEqual(segment_failures(self.structures, cid, self.halves(cid)), [])


POWER_CONVERGENCE = 7565547   # 力の集約
POWER_CONVERGENCE_TEXT = (
    "フィールド上に表側表示で存在するモンスター１体を選択して発動する。"
    "フィールド上に存在する全ての装備カードを選択したモンスターに装備する。"
    "対象が正しくない装備カードは破壊する。")


class TargetReferenceIsNotADeclarationTest(unittest.TestCase):
    """力の集約 7565547:「選択したモンスターに装備する」的「選択した」是回指,不是連用形的取對象字面。"""

    def test_equip_to_the_selected_monster_hits_with_targeting(self):
        cards = [card(POWER_CONVERGENCE, name_ja="力の集約", type=TRAP)]
        structures, _ = build_structures(
            cards, [faq(POWER_CONVERGENCE, "力の集約", POWER_CONVERGENCE_TEXT)],
            archetypes=ARCHETYPES)
        equip, = hit_segments(structures, cards, POWER_CONVERGENCE, actions=["裝備"],
                              targeting=True)
        self.assertEqual(equip["recipient"]["ref"], "選択したモンスター")


BRANCH_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x133, "hex": "0x133", "names_ja": ["ドラゴンメイド"], "name_zh": "龍女僕",
     "source": "strings.conf"},
    {"setcode": 0x52, "hex": "0x52", "names_ja": ["ガーディアン"], "name_zh": "守護者",
     "source": "strings.conf"},
]
DRAGONMAID_TIDYING = 77515704   # ドラゴンメイド・リラクゼーション
DRAGONMAID_TIDYING_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：自分フィールドの「ドラゴンメイド」モンスター１体を対象とし、"
    "以下の効果から１つを選択して発動できる。\n"
    "●対象のモンスターを手札に戻し、デッキから「ドラゴンメイド・リラクゼーション」以外の"
    "「ドラゴンメイド」カード１枚を手札に加える。\n"
    "●対象のモンスターを手札に戻し、相手フィールドの魔法・罠カード１枚を手札に戻す。")
PRINCIPUG = 11496832   # プリンシパグ
PRINCIPUG_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：元々のカード名に「ガーディアン」を含む自分フィールドの通常召喚できないモンスター１体を"
    "対象として発動できる。このターン、そのモンスターは１度のバトルフェイズ中に２回攻撃できる。\n"
    "②：墓地のこのカードを除外し、自分の墓地の通常召喚できない「ガーディアン」モンスター１体を"
    "対象とし、以下の効果から１つを選択して発動できる。\n"
    "●対象のモンスターを手札に加える。\n"
    "●対象のモンスターにカード名が記されたカード１枚を自分の墓地から手札に加える。")


class BranchAfterTargetingTest(unittest.TestCase):
    """「Xを対象とし、以下の効果から１つを選択して発動できる。●〜」:左半先成段,各支的回指指回它。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(DRAGONMAID_TIDYING, name_ja="ドラゴンメイド・リラクゼーション",
                          type=TRAP, setcode=0x133),
                     card(PRINCIPUG, name_ja="プリンシパグ", level=1, race=0x4000, attribute=0x1,
                          atk=0, **{"def": 0})]
        cls.structures, _ = build_structures(
            cls.cards, [faq(DRAGONMAID_TIDYING, "ドラゴンメイド・リラクゼーション",
                            DRAGONMAID_TIDYING_TEXT),
                        faq(PRINCIPUG, "プリンシパグ", PRINCIPUG_TEXT)],
            archetypes=BRANCH_ARCHETYPES)

    def test_each_branch_refers_back_to_the_target(self):
        """查「返回,到手牌」只看取對象:兩支的「対象のモンスターを手札に戻し」都命中,物件是左半的對象。"""
        declared, = hit_segments(self.structures, self.cards, DRAGONMAID_TIDYING, actions=[],
                                 targeting=True, kinds=["代價"])
        self.assertEqual(declared["text"], "自分フィールドの「ドラゴンメイド」モンスター１体を対象とし")
        returned = hit_segments(self.structures, self.cards, DRAGONMAID_TIDYING,
                                actions=["返回"], to_zones=["手牌"], targeting=True)
        self.assertEqual([seg["text"] for seg in returned], ["対象のモンスターを手札に戻し"] * 2)
        for seg in returned:
            self.assertEqual([line["object"] for line in seg["lines"]],
                             [line["object"] for line in declared["lines"]])

    def test_whole_card_passes_reverse_check(self):
        """引導句照常是「選1」的分歧引導,左半自成一段:整張寫得回原文。"""
        self.assertEqual(check_card(own(self.structures, DRAGONMAID_TIDYING)), [])

    def test_cost_before_the_declaration_stays_a_cost(self):
        """プリンシパグ ②:「墓地のこのカードを除外し、〜を対象とし、以下の効果から〜」——除外是代價段,
        第一支「対象のモンスターを手札に加える」指回左半的對象。"""
        cost, = hit_segments(self.structures, self.cards, PRINCIPUG, actions=["除外"],
                             kinds=["代價"])
        self.assertEqual(cost["text"], "墓地のこのカードを除外し")
        added, = hit_segments(self.structures, self.cards, PRINCIPUG, actions=["加入手牌"],
                              targeting=True)
        self.assertEqual(added["text"], "対象のモンスターを手札に加える")
        declared, = [seg for seg in hit_segments(self.structures, self.cards, PRINCIPUG,
                                                 actions=[], targeting=True, kinds=["代價"])
                     if seg["text"].endswith("対象とし")]
        self.assertEqual([line["object"] for line in added["lines"]],
                         [line["object"] for line in declared["lines"]])


if __name__ == "__main__":
    unittest.main()
