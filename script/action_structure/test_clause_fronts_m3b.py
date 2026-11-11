"""m3b 票 01 前文:回合方任一方、本卡效果的原因。只走接縫一(查詢判斷)與接縫二(反向檢查)。

- 「自分・相手ターンに」是遊戲狀態前提(回合方 任一方),規則同「相手ターンに」:句首帶讀點、
  不帶讀點直接接後文、單獨成段都認得,後面的段照常解析;「自分・相手ターンに１度、」的「１度、」進略過文本。
- 原因「本卡自己的效果」(「この効果で」「この方法で」「このカードの①の効果で」)寫在任何動作詞前都認,
  指向之前做同一個動作(上下位詞也算)的段;找不到就整段標「指回的物件找不到」。
前提與原因不參與查詢:回合方記成哪個值從這兩個接縫分不出來,這裡只驗前文剝得出(後面的段照常命中)
與寫回原文相符。標準卡的官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import ARCHETYPES, card, faq

FUSION_MONSTER = 0x41
BLACK_MAGICIAN = 46986414
SELF = 10000301


LOCAL_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x108, "hex": "0x108", "names_ja": ["魔弾"], "name_zh": "魔彈", "source": "strings.conf"},
    {"setcode": 0x16c, "hex": "0x16c", "names_ja": ["氷水"], "name_zh": "冰水", "source": "strings.conf"},
]


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=LOCAL_ARCHETYPES)
    return structures


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def own(structures, cid):
    return next(c for c in structures if c["id"] == cid)


def failures_on(structure, fragment):
    """反向檢查的不通過清單裡與這段字面有關的:沒過的段原文含它,或是段外殘留、段樹的無模板。"""
    texts = {s["id"]: s["text"] for b in structure["blocks"] for s in b["segments"]}
    return [f for f in check_card(structure)
            if fragment in (texts.get(f["segment"]) or "") or f["segment"] is None]


def assert_segment_writes_back(test, structure, fragment):
    """原文含 fragment 的段都解析得出,而且反向檢查沒有與它有關的不通過。"""
    segs = [s for b in structure["blocks"] for s in b["segments"] if fragment in s["text"]]
    test.assertTrue(segs, fragment)
    test.assertEqual([s["unparsed"] for s in segs], [None] * len(segs))
    test.assertEqual(failures_on(structure, fragment), [])


ABC_DRAGON_BUSTER = 1561110     # ABC－ドラゴン・バスター
ABC_DRAGON_BUSTER_TEXT = (
    "「A－アサルト・コア」＋「B－バスター・ドレイク」＋「C－クラッシュ・ワイバーン」\n"
    "自分のフィールド・墓地の上記のカードを除外した場合のみEXデッキから特殊召喚できる。\n"
    "①：自分・相手ターンに１度、手札を１枚捨て、フィールドのカード１枚を対象として発動できる。"
    "そのカードを除外する。\n"
    "②：相手ターンに、このカードをリリースし、自分の除外状態の機械族・光属性ユニオンモンスター３体を"
    "対象として発動できる（同名カードは１枚まで）。そのモンスターを特殊召喚する。")


ORICHALCOS_SWORD = 847217     # オレイカルコスの魔封剣(裝備魔法)
ORICHALCOS_SWORD_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。\n"
    "①：装備モンスターの効果は無効化される。\n"
    "②：自分のフィールドゾーンにカードが存在する場合、自分フィールドの効果モンスター１体を対象として"
    "発動できる。その効果モンスターは相手ターン終了時まで以下の効果を得る。\n"
    "●自分・相手ターンに１度、手札を１枚墓地へ送り、フィールドの表側表示カード１枚を対象として"
    "発動できる。その表側表示カードを破壊する。")
DD_CROW = 24508238     # D.D.クロウ
DD_CROW_TEXT = ("①：自分・相手ターンに、このカードを手札から墓地へ捨て、相手の墓地のカード１枚を"
                "対象として発動できる。そのカードを除外する。")
TORNADO_DRAGON = 6983839     # 竜巻竜
TORNADO_DRAGON_TEXT = (
    "レベル４モンスター×２\n"
    "①：自分・相手ターンに１度、このカードのX素材を１つ取り除き、フィールドの魔法・罠カード１枚を"
    "対象として発動できる。そのカードを破壊する。")


class EitherTurnTest(unittest.TestCase):

    def test_discard_cost_after_either_turn_once_hits(self):
        """ABC－ドラゴン・バスター「自分・相手ターンに１度、手札を１枚捨て」:查「捨棄」命中。"""
        cards = [card(ABC_DRAGON_BUSTER, name_ja="ABC－ドラゴン・バスター", type=FUSION_MONSTER,
                      level=8, race=0x20, attribute=0x10),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
                      attribute=0x20)]
        structures = build(cards, [faq(ABC_DRAGON_BUSTER, "ABC－ドラゴン・バスター",
                                       ABC_DRAGON_BUSTER_TEXT)])
        self.assertIn(ABC_DRAGON_BUSTER, hits(cards, structures, actions=["捨棄"]))

    def test_dd_crow_passes_whole_and_discard_hits(self):
        """D.D.クロウ「自分・相手ターンに、このカードを手札から墓地へ捨て」(候選卡卡在票外寫法時的整張通過替代卡):
        整張通過反向檢查;查「捨棄」從手牌、指定此卡命中。"""
        cards = [card(DD_CROW, name_ja="D.D.クロウ", level=1, race=0x200, attribute=0x20, atk=100),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(DD_CROW, "D.D.クロウ", DD_CROW_TEXT)])
        self.assertEqual(check_card(own(structures, DD_CROW)), [])
        self.assertIn(DD_CROW, hits(cards, structures, actions=["捨棄"], from_zones=["手牌"], card=DD_CROW))

    def test_tornado_dragon_passes_whole_and_detach_hits(self):
        """竜巻竜「自分・相手ターンに１度、このカードのX素材を１つ取り除き」(整張通過替代卡):
        整張通過反向檢查;查「去除」命中。"""
        cards = [card(TORNADO_DRAGON, name_ja="竜巻竜", type=0x800021, level=4, race=0x800000,
                      attribute=0x8, atk=2100),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(TORNADO_DRAGON, "竜巻竜", TORNADO_DRAGON_TEXT)])
        self.assertEqual(check_card(own(structures, TORNADO_DRAGON)), [])
        self.assertIn(TORNADO_DRAGON, hits(cards, structures, actions=["去除"]))

    def test_either_turn_once_in_a_granted_effect_hits(self):
        """オレイカルコスの魔封剣 ②給的效果「●自分・相手ターンに１度、手札を１枚墓地へ送り」:
        那一段解析得出,查「送墓」從手牌命中。整張卡在票外的「以下の効果を得る」,不要求整張通過。"""
        cards = [card(ORICHALCOS_SWORD, name_ja="オレイカルコスの魔封剣", type=0x40002),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(ORICHALCOS_SWORD, "オレイカルコスの魔封剣", ORICHALCOS_SWORD_TEXT)])
        segs = [s for b in own(structures, ORICHALCOS_SWORD)["blocks"] for s in b["segments"]
                if s["text"] == "自分・相手ターンに１度、手札を１枚墓地へ送り"]
        self.assertEqual([s["unparsed"] for s in segs], [None])
        self.assertIn(ORICHALCOS_SWORD, hits(cards, structures, actions=["送墓"], from_zones=["手牌"]))

    def test_either_turn_with_comma_before_premise_writes_back(self):
        """氷水艇エーギロカシス「自分・相手ターンに、このカードが手札・墓地に存在する場合」:
        那一段解析得出、寫回原文相符。"""
        structure = one_card(HYOSUITEI_AEGIROCASSIS, "氷水艇エーギロカシス",
                             HYOSUITEI_AEGIROCASSIS_TEXT, type=0x1021, level=7, race=0x40,
                             attribute=0x2, setcode=0x16c)
        assert_segment_writes_back(self, structure, "自分・相手ターンに、このカードが手札・墓地に存在する場合")

    def test_either_turn_alone_as_activation_condition_writes_back(self):
        """二つの心「自分・相手ターンに発動できる。」:單獨成段的前提,那一段解析得出、寫回原文相符;
        後面的效果段照常命中。"""
        structure = one_card(FUTATSU_NO_KOKORO, "二つの心", FUTATSU_NO_KOKORO_TEXT, type=0x20004)
        assert_segment_writes_back(self, structure, "自分・相手ターンに")

    def test_either_turn_without_comma_before_cost_writes_back(self):
        """「自分・相手ターンに墓地のこのカードを除外して発動できる」(ネクロ・ガードナー 4906301 的
        「相手ターンに」換成「自分・相手ターンに」):不帶讀點直接接後文,那一段解析得出、寫回原文相符,
        查「除外」從墓地命中。全庫不帶讀點的只有「魔弾」8 張,卡在這輪不收的「自分は〜を手札から発動できる」
        (換成「相手ターンに」也一樣),所以用這個句型驗。"""
        cards = [card(SELF, name_ja="甲"),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(SELF, "甲", (
            "①：自分・相手ターンに墓地のこのカードを除外して発動できる。"
            "このターン、相手モンスターの攻撃を１度だけ無効にする。"))])
        assert_segment_writes_back(self, own(structures, SELF), "自分・相手ターンに墓地のこのカード")
        self.assertIn(SELF, hits(cards, structures, actions=["除外"], from_zones=["墓地"], card=SELF))


HYOSUITEI_AEGIROCASSIS = 1295442     # 氷水艇エーギロカシス
HYOSUITEI_AEGIROCASSIS_TEXT = (
    "このカード名の①③の効果は１ターンに１度、いずれか１つしか使用できない。\n"
    "①：自分・相手ターンに、このカードが手札・墓地に存在する場合、自分フィールドの「氷水」モンスター"
    "１体を対象として発動できる。このカードを装備魔法カード扱いでその自分のモンスターに装備する。\n"
    "②：このカードを装備したモンスターの攻撃力・守備力は、除外状態のモンスターの数×４００アップする。\n"
    "③：このカードが装備されている場合に発動できる。このカードを特殊召喚する。")


FUTATSU_NO_KOKORO = 24749710     # 二つの心(永續陷阱)
FUTATSU_NO_KOKORO_TEXT = (
    "このカード名の、①の効果は１ターンに１度しか使用できず、①②の効果は同一チェーン上では発動できない。\n"
    "①：自分・相手ターンに発動できる。デッキから「光と闇の儀式」のカード名が記されたモンスター１体を"
    "手札に加える。その後、自分の手札を１枚選んで捨てる。\n"
    "②：相手がカードの効果を発動した時、自分フィールドのレベル７以上のモンスター１体を手札に戻して"
    "発動できる。戻したモンスターとはカード名が異なる、「光と闇の儀式」のカード名が記された"
    "モンスター１体を手札から召喚条件を無視して特殊召喚する。")

def one_card(cid, name_ja, text, **kw):
    """只有這張卡(加一張對照怪獸)的卡庫 → 這張卡的結構。"""
    cards = [card(cid, name_ja=name_ja, **kw),
             card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
    return own(build(cards, [faq(cid, name_ja, text)]), cid)


SERIAL_KILLER = 33776843     # CNo.15 ギミック・パペット－シリアルキラー
SERIAL_KILLER_TEXT = (
    "レベル９モンスター×３\n"
    "①：１ターンに１度、このカードのX素材を１つ取り除き、相手フィールドのカード１枚を対象として"
    "発動できる。そのカードを破壊する。この効果でモンスターを破壊した場合、さらにそのモンスターの"
    "元々の攻撃力分のダメージを相手に与える。")
BERSERK_DAEMON = 13744068     # バーサーク・デーモン
BERSERK_DAEMON_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：悪魔族モンスターを含む自分フィールドの表側表示モンスターを２体まで対象として発動できる。"
    "このカードを手札から特殊召喚し、対象のモンスターを破壊する。\n"
    "②：このカードの①の効果でモンスターを破壊した時、その数だけ相手フィールドの表側表示モンスターを"
    "対象として発動できる。このカードの攻撃力は次の自分ターンの終了時まで、対象のモンスターの"
    "元々の攻撃力の合計分アップする。")
MASK_CHANGE = 21143940     # マスク・チェンジ(速攻魔法)
MASK_CHANGE_TEXT = (
    "①：自分フィールドの「HERO」モンスター１体を対象として発動できる。そのモンスターの属性を確認し、"
    "墓地へ送る。この効果でそのモンスターがフィールドから離れた場合、さらに同じ属性を持つ"
    "「M・HERO」モンスター１体をEXデッキから特殊召喚する。")
BUSOU_HOUKI = 21056275     # 武装蜂起(通常魔法)
BUSOU_HOUKI_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。\n"
    "①：手札・デッキから攻撃力１０００以下の昆虫族モンスター１体を特殊召喚する。"
    "この効果でデッキから特殊召喚した場合、さらに自分フィールドのモンスター１体を墓地へ送る。"
    "このカードの発動後、ターン終了時まで自分は昆虫族モンスターしか特殊召喚できない。\n"
    "②：このカードが墓地に存在する状態で、自分フィールドの表側表示の昆虫族Sモンスターが戦闘・効果で"
    "破壊された場合、このカードを除外して発動できる。デッキから「一斉蜂起」１枚を手札に加える。")
INSECT = 10000302     # 測試用:攻擊力 1000 的昆蟲族怪獸
ISSEI_HOUKI = 52838896     # 一斉蜂起(②的「」名稱)
ABDUCTION = 21846145     # アブダクション(通常陷阱)
ABDUCTION_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。\n"
    "①：相手フィールドの表側表示モンスター１体を対象として発動できる。元々の種族と元々の属性と"
    "元々のレベル・ランク・リンクが対象のモンスターと同じモンスター１体をデッキ・EXデッキから除外し、"
    "対象のモンスターのコントロールを得る。元々のカード名が対象のモンスターと同じモンスターを"
    "この効果で除外した場合、この効果でコントロールを得たモンスターの効果は無効化される。")
CONDITION_ONLY = dict(kinds=["條件"], include_condition=True)


class OwnEffectCauseTest(unittest.TestCase):

    def test_own_effect_before_destroy_condition_hits(self):
        """シリアルキラー「この効果でモンスターを破壊した場合」:開條件段、只看條件段查「破壞」命中;
        整張通過反向檢查(原因指回前面「そのカードを破壊する」)。"""
        cards = [card(SERIAL_KILLER, name_ja="CNo.15 ギミック・パペット－シリアルキラー",
                      type=0x800021, level=9, race=0x20, attribute=0x20),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(SERIAL_KILLER, "CNo.15 ギミック・パペット－シリアルキラー",
                                       SERIAL_KILLER_TEXT)])
        self.assertIn(SERIAL_KILLER, hits(cards, structures, actions=["破壞"], **CONDITION_ONLY))
        self.assertEqual(check_card(own(structures, SERIAL_KILLER)), [])

    def test_numbered_own_effect_points_into_that_block(self):
        """バーサーク・デーモン「このカードの①の効果でモンスターを破壊した時」:指回①的「破壊する」;
        開條件段查「破壞」命中,那一段寫回原文相符。"""
        cards = [card(BERSERK_DAEMON, name_ja="バーサーク・デーモン", level=6, race=0x8, attribute=0x20),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(BERSERK_DAEMON, "バーサーク・デーモン", BERSERK_DAEMON_TEXT)])
        self.assertIn(BERSERK_DAEMON, hits(cards, structures, actions=["破壞"], **CONDITION_ONLY))
        assert_segment_writes_back(self, own(structures, BERSERK_DAEMON),
                                   "このカードの①の効果でモンスターを破壊した時")

    def test_own_effect_with_elided_subject_points_at_the_summoned(self):
        """武装蜂起「この効果でデッキから特殊召喚した場合」(主語省略,沒有「成功」):被召喚的是前面
        「昆虫族モンスター１体を特殊召喚する」的物件——開條件段查「特殊召喚」指定攻擊力 1000 的昆蟲族命中、
        指定 ブラック・マジシャン 不命中;整張通過反向檢查。"""
        cards = [card(BUSOU_HOUKI, name_ja="武装蜂起", type=0x2),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20,
                      atk=2500),
                 card(INSECT, name_ja="丙", level=3, race=0x800, attribute=0x10, atk=1000),
                 card(ISSEI_HOUKI, name_ja="一斉蜂起", type=0x2)]
        structures = build(cards, [faq(BUSOU_HOUKI, "武装蜂起", BUSOU_HOUKI_TEXT)])
        query = dict(actions=["特殊召喚"], **CONDITION_ONLY)
        self.assertIn(BUSOU_HOUKI, hits(cards, structures, card=INSECT, **query))
        self.assertNotIn(BUSOU_HOUKI, hits(cards, structures, card=BLACK_MAGICIAN, **query))
        self.assertEqual(check_card(own(structures, BUSOU_HOUKI)), [])

    def test_own_effect_after_the_object_hits(self):
        """アブダクション「〜同じモンスターをこの効果で除外した場合」(原因寫在物件後、動作詞前):
        開條件段查「除外」命中。"""
        cards = [card(ABDUCTION, name_ja="アブダクション", type=0x4),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(ABDUCTION, "アブダクション", ABDUCTION_TEXT)])
        self.assertIn(ABDUCTION, hits(cards, structures, actions=["除外"], **CONDITION_ONLY))

    def test_own_effect_without_matching_source_is_unparsed(self):
        """マスク・チェンジ「この効果でそのモンスターがフィールドから離れた場合」:前面只有「墓地へ送る」,
        送墓與離場沒有上下位關係,指不回 → 開條件段查「離場」時列在未解析組,原因「指回的物件找不到」。"""
        cards = [card(MASK_CHANGE, name_ja="マスク・チェンジ", type=0x10002),
                 card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2, attribute=0x20)]
        structures = build(cards, [faq(MASK_CHANGE, "マスク・チェンジ", MASK_CHANGE_TEXT)])
        result = run_query(structures, cards, dict(actions=["離場"], **CONDITION_ONLY))
        self.assertNotIn(MASK_CHANGE, [h["id"] for h in result["hits"]])
        unparsed = next(u for u in result["unparsed"] if u["id"] == MASK_CHANGE)
        self.assertEqual([(s["text"], s["reason"]) for s in unparsed["segments"]],
                         [("この効果でそのモンスターがフィールドから離れた場合", "指回的物件找不到")])


if __name__ == "__main__":
    unittest.main()
