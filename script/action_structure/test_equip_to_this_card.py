"""裝備到此卡(m3b 票 06)。

「Xをこのカードに装備する」:裝備段的受方是此卡;X 是對象線,條件式、從、取對象照字面與既有規則
(X 是回指時指回前面被取對象的物件)。方式字面「装備カード扱いとして」「装備魔法カード扱いで」。
接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
import unittest

from test_golden import card, faq
from test_modifier_closed_sets import GoldenCase

FUSION_MONSTER = 0x61
SYNCHRO_MONSTER = 0x2021
LINK_MONSTER = 0x4000021
NORMAL_MONSTER = 0x11
MAGISTUS = 0x150

MILLENNIUM_EYES = 41578483
MILLENNIUM_EYES_TEXT = (
    "「サクリファイス」＋効果モンスター\n"
    "①：１ターンに１度、相手モンスターの効果が発動した時、相手のフィールド・墓地の効果モンスター１体を"
    "対象として発動できる。その相手の効果モンスターを装備カード扱いとしてこのカードに装備する。"
    "②：このカードの攻撃力・守備力は、このカードの効果で装備したモンスターのそれぞれの数値分アップする。"
    "③：このカードの効果で装備したモンスターと元々のカード名が同じモンスターは攻撃できず、"
    "その効果は無効化される。")
NIGHTMARE_EYES = 30138615
NIGHTMARE_EYES_TEXT = (
    "種族が異なる悪魔族・幻想魔族・魔法使い族モンスター×２\n"
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：このカードが特殊召喚した場合、またはこのカードが戦闘を行ったバトルフェイズ終了時に発動できる。"
    "相手フィールドのモンスター１体を装備魔法カード扱いでこのカードに装備する。\n"
    "②：このカードの攻撃力は、このカードの効果で装備しているモンスターの攻撃力分アップする。\n"
    "③：このカードがモンスターと戦闘を行う場合、その２体はその戦闘では破壊されない。\n"
    "④：相手モンスターは他のモンスターを攻撃できない。")
ZOROA = 95911373
ZOROA_TEXT = (
    "魔法使い族チューナー＋チューナー以外のモンスター１体以上\n"
    "このカード名の③の効果は１ターンに１度しか使用できない。"
    "①：このカードがS召喚に成功した場合に発動できる。"
    "EXデッキから「マギストス」モンスター１体を装備カード扱いとしてこのカードに装備する。"
    "②：自分の魔法＆罠ゾーンの「マギストス」モンスターカードと同じ種類（融合・S・X・リンク）の"
    "モンスターの効果を相手は発動できない。"
    "③：自分フィールドの「マギストス」カード１枚を対象として発動できる。"
    "そのカードを破壊し、このカードを墓地から特殊召喚する。")
MILLENNIUM_EQUIP = "その相手の効果モンスターを装備カード扱いとしてこのカードに装備する"
ARTEMIS = 34755994          # 聖魔の乙女アルテミス:「マギストス」連結怪獸(效果怪獸)
BLACK_MAGICIAN = 46986414   # ブラック・マジシャン:通常怪獸,不是「マギストス」

MAGISTUS_ARCHETYPES = [{"setcode": MAGISTUS, "hex": "0x150", "names_ja": ["マギストス"],
                        "name_zh": "偉魔", "source": "strings.conf"}]


class EquipToThisCardTest(GoldenCase):
    """千年眼納祭、幻惑眼納祭、偉魔代蒙 絕火之瑣羅亞(使用者故事 36–39)。"""
    cards = [
        card(MILLENNIUM_EYES, name_ja="ミレニアム・アイズ・サクリファイス", type=FUSION_MONSTER,
             level=1, race=0x2, attribute=0x20, atk=0, **{"def": 0}),
        card(NIGHTMARE_EYES, name_ja="ナイトメア・アイズ・サクリファイス", type=FUSION_MONSTER,
             level=1, race=0x2000000, attribute=0x20, atk=0, **{"def": 0}),
        card(ZOROA, name_ja="絶火の魔神ゾロア", type=SYNCHRO_MONSTER, level=8, race=0x2,
             attribute=0x4, atk=2900, setcode=MAGISTUS, **{"def": 1500}),
        card(ARTEMIS, name_ja="聖魔の乙女アルテミス", type=LINK_MONSTER, level=1, race=0x2,
             attribute=0x10, atk=800, setcode=MAGISTUS),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500, **{"def": 2100}),
    ]
    faq = [
        faq(MILLENNIUM_EYES, "ミレニアム・アイズ・サクリファイス", MILLENNIUM_EYES_TEXT),
        faq(NIGHTMARE_EYES, "ナイトメア・アイズ・サクリファイス", NIGHTMARE_EYES_TEXT),
        faq(ZOROA, "絶火の魔神ゾロア", ZOROA_TEXT),
    ]
    archetypes = MAGISTUS_ARCHETYPES

    def test_equip_hits_all_three(self):
        hits = self.hits(actions=["裝備"])
        for cid in (MILLENNIUM_EYES, NIGHTMARE_EYES, ZOROA):
            self.assertIn(cid, hits)

    def test_the_equip_segments_write_back_to_their_text(self):
        self.assertWritesBack(MILLENNIUM_EYES, MILLENNIUM_EQUIP)
        self.assertWritesBack(NIGHTMARE_EYES, "相手フィールドのモンスター１体を装備魔法カード扱いでこのカードに装備する")
        self.assertWritesBack(ZOROA, "EXデッキから「マギストス」モンスター１体を装備カード扱いとしてこのカードに装備する")

    def test_equip_targeting_only_hits_millennium_eyes(self):
        """千年眼納祭 的 X 是「その相手の効果モンスター」,指回取對象宣言的物件。"""
        self.assertIn(MILLENNIUM_EYES, self.hits(actions=["裝備"], targeting=True))

    def test_equip_targeting_only_misses_nightmare_eyes_and_zoroa(self):
        for cid in (NIGHTMARE_EYES, ZOROA):
            self.assertJudgedMiss(cid, actions=["裝備"], targeting=True)

    def test_equip_from_extra_deck_hits_zoroa(self):
        self.assertIn(ZOROA, self.hits(actions=["裝備"], from_zones=["額外牌組"]))

    def test_equip_from_extra_deck_misses_nightmare_eyes(self):
        """幻惑眼納祭 被裝上去的是對手場上的怪獸,不是從額外牌組。"""
        self.assertJudgedMiss(NIGHTMARE_EYES, actions=["裝備"], from_zones=["額外牌組"])

    def test_equip_with_a_non_magistus_monster_misses_zoroa_and_hits_nightmare_eyes(self):
        self.assertJudgedMiss(ZOROA, actions=["裝備"], card=BLACK_MAGICIAN)
        self.assertIn(NIGHTMARE_EYES, self.hits(actions=["裝備"], card=BLACK_MAGICIAN))

    def test_equip_with_a_magistus_monster_hits_zoroa(self):
        self.assertIn(ZOROA, self.hits(actions=["裝備"], card=ARTEMIS))

    def test_equip_with_a_normal_monster_misses_millennium_eyes(self):
        """千年眼納祭 只裝效果怪獸。它的③「このカードの効果で装備したモンスターと〜」照舊解析不出,
        所以整張仍在未解析組;裝備那一段本身判得了、不命中。"""
        query = dict(actions=["裝備"], card=BLACK_MAGICIAN)
        self.assertNotIn(MILLENNIUM_EYES, self.hits(**query))
        unparsed = next(row for row in self.run_(**query)["unparsed"] if row["id"] == MILLENNIUM_EYES)
        self.assertNotIn(MILLENNIUM_EQUIP, [s["text"] for s in unparsed["segments"]])

    def test_equip_with_an_effect_monster_hits_millennium_eyes(self):
        self.assertIn(MILLENNIUM_EYES, self.hits(actions=["裝備"], card=ARTEMIS))


DRAGUNITY = 0x29
DRAGUNITY_DUX = 28183605
DRAGUNITY_DUX_TEXT = (
    "①：このカードが召喚に成功した時、自分の墓地のドラゴン族・レベル３以下の「ドラグニティ」モンスター１体を"
    "対象として発動できる。そのドラゴン族モンスターを装備カード扱いとしてこのカードに装備する。"
    "②：このカードの攻撃力は、自分フィールドの「ドラグニティ」カードの数×２００アップする。")
SCISSOR_BEAR = 85545073
SCISSOR_BEAR_TEXT = (
    "「エッジインプ・シザー」＋「ファーニマル・ベア」\n"
    "①：このカードが戦闘で相手モンスターを破壊し墓地へ送った時に発動できる。"
    "そのモンスターを攻撃力１０００アップの装備カード扱いとしてこのカードに装備する。")


class WholeCardPassTest(GoldenCase):
    """三張標準卡都卡在這張票以外的寫法(見票檔 Comments),整張通過改用這張票之後才整張通過的卡。"""
    cards = [
        card(DRAGUNITY_DUX, name_ja="ドラグニティ－ドゥクス", level=4, race=0x200, attribute=0x8,
             atk=1500, setcode=DRAGUNITY),
        card(SCISSOR_BEAR, name_ja="デストーイ・シザー・ベアー", type=FUSION_MONSTER, level=6,
             race=0x8, attribute=0x20, atk=2200, setcode=0xad, **{"def": 1800}),
        card(30068120, name_ja="エッジインプ・シザー", level=3, race=0x8, attribute=0x20,
             atk=1200, setcode=0xc3),
        card(3841833, name_ja="ファーニマル・ベア", level=3, race=0x4, attribute=0x1, atk=1200,
             setcode=0xa9),
    ]
    faq = [
        faq(DRAGUNITY_DUX, "ドラグニティ－ドゥクス", DRAGUNITY_DUX_TEXT),
        faq(SCISSOR_BEAR, "デストーイ・シザー・ベアー", SCISSOR_BEAR_TEXT),
    ]
    archetypes = [{"setcode": DRAGUNITY, "hex": "0x29", "names_ja": ["ドラグニティ"],
                   "name_zh": "龍盟", "source": "strings.conf"}]

    def test_dragunity_dux_passes_as_a_whole(self):
        self.assertWholeCardPasses(DRAGUNITY_DUX)

    def test_scissor_bear_passes_as_a_whole(self):
        """「攻撃力１０００アップの装備カード扱いとして」另拆的性質變更段也寫得回。"""
        self.assertWholeCardPasses(SCISSOR_BEAR)


if __name__ == "__main__":
    unittest.main()
