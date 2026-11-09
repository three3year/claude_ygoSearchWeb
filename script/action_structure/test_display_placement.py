"""表示形式與放置(m2 票 05):表示形式字面依句中位置落格、新動作詞放置與覆蓋。

走接縫一(查詢判斷)與接縫二(反向檢查);查詢層沒有的格(`display`、`treat`、前提的 `face`、
原因、物件修飾)先用查詢命中段,再讀該段的格。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures, load_structures, serialize_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, TRAP, card, faq

WHITE_MAIDEN = 17947697   # 白き乙女
WHITE_MAIDEN_TEXT = (
    "このカード名の①②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：手札・フィールドのこのカードを墓地へ送って発動できる。自分の手札・デッキ・墓地から"
    "「真の光」１枚を自分の魔法＆罠ゾーンに表側表示で置く。\n"
    "②：このカードが墓地に存在する状態で、自分が「青眼の白龍」を特殊召喚した場合に発動できる。"
    "このカードを特殊召喚する。\n"
    "③：フィールドのこのカードが攻撃・効果の対象になった時に発動できる。自分の墓地から"
    "「青眼の白龍」か光属性・レベル１チューナー１体を特殊召喚する。")
TRUE_LIGHT = 62089826     # 真の光
BLUE_EYES = 89631139      # 青眼の白龍
PLACE_SENTENCE = "自分の手札・デッキ・墓地から「真の光」１枚を自分の魔法＆罠ゾーンに表側表示で置く"

ARCHETYPES_05 = ARCHETYPES + [
    {"setcode": 0x7, "hex": "0x7", "names_ja": ["古代の機械", "アンティーク・ギア"],
     "name_zh": "古代機械齒輪", "source": "strings.conf"},
    {"setcode": 0x10, "hex": "0x10", "names_ja": ["ガスタ"], "name_zh": "薰風",
     "source": "strings.conf"},
    {"setcode": 0x1a2, "hex": "0x1a2", "names_ja": ["センチュリオン"], "name_zh": "百夫長",
     "source": "strings.conf"},
]


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES_05)
    return structures


def hit_segments(structures, cards, cid, **query):
    """查詢命中某卡的段(含內嵌效果的段);沒命中回空列表。"""
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    structure = next(s for s in structures if s["id"] == cid)
    return [seg for b in structure["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def failures_of(structures, cid, seg):
    """反向檢查中屬於這一段的不通過項。"""
    return [f for f in check_card(own(structures, cid)) if f["segment"] == seg["id"]]


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


class WhiteMaidenTest(unittest.TestCase):
    """白き乙女 17947697:「〜を魔法＆罠ゾーンに表側表示で置く」是放置,不是特殊召喚或裝備。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(WHITE_MAIDEN, name_ja="白き乙女", level=1, race=0x2, attribute=0x10,
                 atk=0, **{"def": 0}),
            card(TRUE_LIGHT, name_ja="真の光", type=0x20004),
            card(BLUE_EYES, name_ja="青眼の白龍", type=0x11, level=8, race=0x2000,
                 attribute=0x10, atk=3000, setcode=0xdd, **{"def": 2500}),
        ]
        cls.structures = build(cls.cards, [faq(WHITE_MAIDEN, "白き乙女", WHITE_MAIDEN_TEXT)])

    def test_place_to_spell_trap_zone_hits(self):
        segs = hit_segments(self.structures, self.cards, WHITE_MAIDEN,
                            actions=["放置"], to_zones=["魔陷區"])
        self.assertEqual([s["text"] for s in segs], [PLACE_SENTENCE])

    def test_place_segment_is_not_special_summon_or_equip(self):
        """查「特殊召喚」命中的是 ②③ 的段,不含放置段;查「裝備」整張不命中。"""
        summon = hit_segments(self.structures, self.cards, WHITE_MAIDEN, actions=["特殊召喚"])
        self.assertTrue(summon)
        self.assertNotIn(PLACE_SENTENCE, [s["text"] for s in summon])
        self.assertEqual(hit_segments(self.structures, self.cards, WHITE_MAIDEN,
                                      actions=["裝備"]), [])

    def test_place_segment_records_display_face_up(self):
        [seg] = hit_segments(self.structures, self.cards, WHITE_MAIDEN,
                             actions=["放置"], to_zones=["魔陷區"])
        self.assertEqual(seg["lines"][0]["to"]["form"]["display"],
                         {"text": "表側表示で", "alternatives": [{"face": "表側", "position": None}]})

    def test_place_segment_passes_reverse_check(self):
        """③ 的「攻撃・効果の対象になった時」不在本票範圍,只驗放置段。"""
        [seg] = hit_segments(self.structures, self.cards, WHITE_MAIDEN, actions=["放置"])
        self.assertEqual(failures_of(self.structures, WHITE_MAIDEN, seg), [])


CENTURION = 41371602   # スタンドアップ・センチュリオン！(永續陷阱)
CENTURION_TEXT = (
    "このカード名の②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分フィールドに「センチュリオン」モンスターカードが存在する限り、"
    "このカードは相手の効果では破壊されない。\n"
    "②：このカードを発動したターンの自分メインフェイズに、手札を１枚墓地へ送って発動できる。"
    "デッキから「センチュリオン」モンスター１体を永続罠カード扱いで自分の魔法＆罠ゾーンに"
    "表側表示で置く。\n"
    "③：モンスターが特殊召喚された場合に発動できる。「センチュリオン」モンスターを含む"
    "自分フィールドのモンスターを素材としてS召喚を行う。")


class CenturionTest(unittest.TestCase):
    """スタンドアップ・センチュリオン！ 41371602:treat 與 display 同時有值,各寫回自己的位置。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(CENTURION, name_ja="スタンドアップ・センチュリオン！", type=0x80004,
                          setcode=0x1a2)]
        cls.structures = build(cls.cards, [faq(CENTURION, "スタンドアップ・センチュリオン！",
                                               CENTURION_TEXT)])

    def place_segment(self):
        [seg] = hit_segments(self.structures, self.cards, CENTURION,
                             actions=["放置"], to_zones=["魔陷區"], from_zones=["牌組"])
        return seg

    def test_treat_and_display_both_recorded(self):
        form = self.place_segment()["lines"][0]["to"]["form"]
        self.assertEqual(form["treat"], {"text": "永続罠カード扱いで", "kind": "永續陷阱"})
        self.assertEqual(form["display"]["alternatives"], [{"face": "表側", "position": None}])

    def test_place_segment_passes_reverse_check(self):
        """treat 寫在區域前、display 寫在述語前,原樣寫回(② 的代價句、③ 不在本票範圍)。"""
        self.assertEqual(failures_of(self.structures, CENTURION, self.place_segment()), [])


LITTLE_OPPOSITION = 15967552   # リトル・オポジション(通常陷阱)
# 真卡的 ● 句「自身の手札・デッキからレベル２以下のモンスター１体を選び、指定された自身の
# メインモンスターゾーンに表側攻撃表示か裏側守備表示で特殊召喚する」帶「選び」(m2 票 09)與
# 區域位置(spec 不做),整段解析不出;這裡把該句去掉範圍外的兩截,當合成卡的效果。
LITTLE_OPPOSITION_SENTENCE = (
    "自分の手札・デッキからレベル２以下のモンスター１体を表側攻撃表示か裏側守備表示で特殊召喚する")
WAKE_CUP_AL = 85586937   # WAKE CUP！ アル
WAKE_CUP_AL_TEXT = (
    "このカード名の①②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードが手札に存在する場合に発動できる。自分の手札から他のリバースモンスター１体を"
    "選んで捨て、このカードを表側攻撃表示か裏側守備表示で特殊召喚する。\n"
    "②：このカードがリバースした場合に発動できる。自分フィールドのリバースモンスターの数まで、"
    "相手フィールドの表側表示カードを墓地へ送る。\n"
    "③：自分エンドフェイズに、自分の墓地のリバースモンスター１体を対象として発動できる。"
    "そのモンスターを裏側守備表示で特殊召喚する。")
FACE_UP_ATTACK_OR_FACE_DOWN_DEFENSE = {
    "text": "表側攻撃表示か裏側守備表示で",
    "alternatives": [{"face": "表側", "position": "攻擊"}, {"face": "裏側", "position": "守備"}]}


class AlternativesTest(unittest.TestCase):
    """「X表示かY表示で」:display 的 alternatives 兩項,text 原樣寫回。"""

    def test_little_opposition_sentence(self):
        cards = [card(LITTLE_OPPOSITION, name_ja="リトル・オポジション", type=TRAP)]
        structures = build(cards, [faq(LITTLE_OPPOSITION, "リトル・オポジション",
                                       "①：" + LITTLE_OPPOSITION_SENTENCE + "。")])
        [seg] = hit_segments(structures, cards, LITTLE_OPPOSITION, actions=["特殊召喚"],
                             from_zones=["手牌"])
        self.assertEqual(seg["lines"][0]["to"]["form"]["display"],
                         FACE_UP_ATTACK_OR_FACE_DOWN_DEFENSE)
        self.assertEqual(check_card(own(structures, LITTLE_OPPOSITION)), [])

    def test_real_card_self_special_summon(self):
        """WAKE CUP！ アル ①後半「このカードを表側攻撃表示か裏側守備表示で特殊召喚する」
        (前半「選んで捨て」是 m2 票 09)。"""
        cards = [card(WAKE_CUP_AL, name_ja="WAKE CUP！ アル", type=0x200021, level=7,
                      race=0x40, attribute=0x8, atk=2700, **{"def": 400})]
        structures = build(cards, [faq(WAKE_CUP_AL, "WAKE CUP！ アル", WAKE_CUP_AL_TEXT)])
        segs = hit_segments(structures, cards, WAKE_CUP_AL, actions=["特殊召喚"],
                            from_zones=["手牌"])
        [seg] = [s for s in segs if s["text"].startswith("このカードを表側攻撃表示か")]
        self.assertEqual(seg["lines"][0]["to"]["form"]["display"],
                         FACE_UP_ATTACK_OR_FACE_DOWN_DEFENSE)
        self.assertEqual(failures_of(structures, WAKE_CUP_AL, seg), [])


ANCIENT_GEAR = 31557782   # 古代の歯車
ANCIENT_GEAR_TEXT = ("自分フィールド上に「古代の歯車」が表側表示で存在する時、"
                     "手札からこのカードを攻撃表示で特殊召喚する事ができる。")


class AncientGearTest(unittest.TestCase):
    """古代の歯車 31557782:前提的存在原子帶表示形式,效果段的放置形式攻擊表示。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(ANCIENT_GEAR, name_ja="古代の歯車", level=2, race=0x20,
                          attribute=0x1, atk=100, setcode=0x7, **{"def": 800})]
        cls.structures = build(cls.cards, [faq(ANCIENT_GEAR, "古代の歯車", ANCIENT_GEAR_TEXT)])

    def summon_segment(self):
        [seg] = hit_segments(self.structures, self.cards, ANCIENT_GEAR,
                             actions=["特殊召喚"], from_zones=["手牌"])
        return seg

    def test_special_summon_from_hand_in_attack_position(self):
        seg = self.summon_segment()
        self.assertTrue(seg["optional"])
        self.assertEqual(seg["lines"][0]["to"]["form"]["display"],
                         {"text": "攻撃表示で", "alternatives": [{"face": None, "position": "攻擊"}]})

    def test_premise_is_face_up_existence_with_toki(self):
        premise = self.summon_segment()["premise"]
        self.assertEqual(premise["op"], "存在")
        self.assertEqual(premise["face"], "表側")
        self.assertNotIn("position", premise)
        self.assertEqual(premise["form"], "時、")

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, ANCIENT_GEAR)), [])


GUSTA_FALCO = 46044841   # ガスタ・ファルコ
GUSTA_FALCO_TEXT = (
    "フィールド上に表側表示で存在するこのカードが戦闘以外によって墓地へ送られた時、"
    "デッキから「ガスタ」と名のついたモンスター１体を裏側守備表示で特殊召喚できる。")
GUSTA_CONDITION = "フィールド上に表側表示で存在するこのカードが戦闘以外によって墓地へ送られた時"


class GustaFalcoTest(unittest.TestCase):
    """ガスタ・ファルコ 46044841:效果段裏側守備表示;條件段的原因與從的表示形式。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(GUSTA_FALCO, name_ja="ガスタ・ファルコ", type=0x1021, level=2,
                          race=0x200, attribute=0x8, atk=600, setcode=0x10, **{"def": 1400})]
        cls.structures = build(cls.cards, [faq(GUSTA_FALCO, "ガスタ・ファルコ", GUSTA_FALCO_TEXT)])

    def test_special_summon_from_deck_face_down_defense(self):
        [seg] = hit_segments(self.structures, self.cards, GUSTA_FALCO,
                             actions=["特殊召喚"], from_zones=["牌組"])
        self.assertEqual(seg["lines"][0]["to"]["form"]["display"],
                         {"text": "裏側守備表示で",
                          "alternatives": [{"face": "裏側", "position": "守備"}]})

    def test_condition_cause_and_face_up_from(self):
        """條件段:原因「戦闘以外によって」;「フィールド上に表側表示で存在するこのカード」的
        表示形式記在從的放置形式(物件0 不帶條件式,見票 Comments)。"""
        [seg] = hit_segments(self.structures, self.cards, GUSTA_FALCO, actions=["送墓"],
                             include_condition=True, kinds=["條件"], card=GUSTA_FALCO)
        self.assertEqual(seg["text"], GUSTA_CONDITION)
        self.assertEqual(seg["trigger"], "時")
        self.assertEqual(seg["cause"], {"kind": "戰鬥以外", "text": "戦闘以外によって"})
        line = seg["lines"][0]
        self.assertEqual(line["from"]["zones"], [{"zone": "場上", "side": None,
                                                  "side_source": None}])
        self.assertEqual(line["from"]["form"]["display"]["alternatives"],
                         [{"face": "表側", "position": None}])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, GUSTA_FALCO)), [])


SUMMON_REACTOR = 89493368   # サモン・リアクター・AI(m2 票 03 留給本票的「表側表示で存在する限り」)
SUMMON_REACTOR_TEXT = (
    "このカードが自分フィールド上に表側表示で存在する限り、相手フィールド上にモンスターが"
    "召喚・反転召喚・特殊召喚された時、相手ライフに８００ポイントダメージを与える。"
    "この効果は１ターンに１度しか使用できない。この効果を使用したターンのバトルフェイズ時、"
    "相手モンスター１体の攻撃を無効にできる。")


class FaceUpKagiriPremiseTest(unittest.TestCase):
    """「このカードが〜に表側表示で存在する限り、」剝成此卡的位置原子(帶 face),段期間持續。"""

    def test_premise_is_stripped_with_face(self):
        cards = [card(SUMMON_REACTOR, name_ja="サモン・リアクター・AI", level=4)]
        structures = build(cards, [faq(SUMMON_REACTOR, "サモン・リアクター・AI",
                                       SUMMON_REACTOR_TEXT)])
        block = own(structures, SUMMON_REACTOR)["blocks"][0]
        seg = block["segments"][0]
        self.assertEqual(seg["premise"]["op"], "位置")
        self.assertEqual((seg["premise"]["face"], seg["premise"]["form"]), ("表側", "限り、"))
        self.assertEqual(seg["duration"], {"kind": "持續"})
        self.assertNotIn("存在", seg["predicate"] or "")


SOUKO = 96381979   # 魁炎星王－ソウコ
SOUKO_TEXT = (
    "獣戦士族レベル４モンスター×２\n①：このカードがX召喚に成功した時に発動できる。"
    "デッキから「炎舞」魔法・罠カード１枚をセットする。②：１ターンに１度、このカードのX素材を"
    "１つ取り除いて発動できる。獣戦士族以外のフィールドの全ての効果モンスターの効果は"
    "相手ターン終了時まで無効化される。③：このカードがフィールドから墓地へ送られた時、"
    "自分フィールドの表側表示の「炎舞」魔法・罠カード３枚を墓地へ送って発動できる。"
    "レベル４以下で同じ攻撃力の獣戦士族モンスター２体をデッキから守備表示で特殊召喚する。")
SET_SENTENCE = "デッキから「炎舞」魔法・罠カード１枚をセットする"


class SetTest(unittest.TestCase):
    """覆蓋(セット):沒寫到時推得魔陷區。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SOUKO, name_ja="魁炎星王－ソウコ", type=0x800021, level=4,
                          race=0x8000, attribute=0x4, atk=2200, setcode=0x79,
                          **{"def": 1800})]
        archetypes = ARCHETYPES_05 + [{"setcode": 0x7c, "hex": "0x7c", "names_ja": ["炎舞"],
                                       "name_zh": "炎舞", "source": "strings.conf"}]
        cls.structures, _ = build_structures(
            cls.cards, [faq(SOUKO, "魁炎星王－ソウコ", SOUKO_TEXT)], archetypes=archetypes)

    def test_set_hits_inferred_spell_trap_zone_only_with_switch(self):
        query = {"actions": ["覆蓋"], "to_zones": ["魔陷區"]}
        self.assertEqual(hit_segments(self.structures, self.cards, SOUKO, **query), [])
        [seg] = hit_segments(self.structures, self.cards, SOUKO, include_inferred=True, **query)
        self.assertEqual(seg["text"], SET_SENTENCE)
        self.assertEqual(failures_of(self.structures, SOUKO, seg), [])


TOY_SOLDIER = 65504487   # トイ・ソルジャー


class TreatBeforeFromTest(unittest.TestCase):
    """「魔法カード扱いで手札から魔法＆罠ゾーンにセットできる」:treat 寫在述語前的從之前。"""

    def test_toy_soldier_set_passes_reverse_check(self):
        cards = [card(TOY_SOLDIER, name_ja="トイ・ソルジャー", level=4, race=0x1,
                      attribute=0x10, atk=1500)]
        text = "①：このカードは魔法カード扱いで手札から魔法＆罠ゾーンにセットできる。"
        structures = build(cards, [faq(TOY_SOLDIER, "トイ・ソルジャー", text)])
        [seg] = hit_segments(structures, cards, TOY_SOLDIER, actions=["覆蓋"],
                             from_zones=["手牌"], to_zones=["魔陷區"])
        self.assertEqual(seg["lines"][0]["to"]["form"]["treat"],
                         {"text": "魔法カード扱いで", "kind": "魔法"})
        self.assertEqual(failures_of(structures, TOY_SOLDIER, seg), [])


class RoundTripTest(unittest.TestCase):
    """產物讀回:display 的 alternatives 裡沒寫的一半(None)被省略後要補回,反向檢查照常通過。"""

    def test_reloaded_structures_equal_and_pass(self):
        cards = [card(ANCIENT_GEAR, name_ja="古代の歯車", level=2, race=0x20, attribute=0x1,
                      atk=100, setcode=0x7, **{"def": 800}),
                 card(GUSTA_FALCO, name_ja="ガスタ・ファルコ", type=0x1021, level=2,
                      race=0x200, attribute=0x8, atk=600, setcode=0x10, **{"def": 1400})]
        structures = build(cards, [faq(ANCIENT_GEAR, "古代の歯車", ANCIENT_GEAR_TEXT),
                                   faq(GUSTA_FALCO, "ガスタ・ファルコ", GUSTA_FALCO_TEXT)])
        reloaded = load_structures(serialize_structures(structures))
        self.assertEqual(reloaded, structures)
        self.assertEqual([check_card(s) for s in reloaded], [[], []])
