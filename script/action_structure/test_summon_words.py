"""召喚動作詞(m3 票 08)的查詢層與反向檢查斷言:輸入真實卡的官方 DB 文本與卡片參數,看查詢結果。

只驗接縫一(查詢判斷)與接縫二(反向檢查),不驗結構內部的格。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import SPELL, card, faq

GAGAGA_SISTER = 387282   # ガガガシスター(召喚に成功した時)
GAGAGA_SISTER_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。①：このカードが召喚に成功した時に発動できる。"
    "デッキから「ガガガ」魔法・罠カード１枚を手札に加える。②：このカード以外の自分フィールドの「ガガガ」"
    "モンスター１体を対象として発動できる。そのモンスターとこのカードは、ターン終了時までその２体のレベルを"
    "合計したレベルになる。")
DARK_SAGE = 92377303   # 黒衣の大賢者(このカードは通常召喚できない;この方法で特殊召喚に成功した時)
DARK_SAGE_TEXT = (
    "このカードは通常召喚できない。自分の「時の魔術師」のコイントスを当てた時、自分フィールド上に存在する"
    "「ブラック・マジシャン」１体をリリースして手札またはデッキから特殊召喚する事ができる。"
    "この方法で特殊召喚に成功した時、自分のデッキから魔法カード１枚を手札に加える。")
MAJESPECTER_FROG = 645794   # マジェスペクター・フロッグ(召喚・特殊召喚に成功した時)
MAJESPECTER_FROG_TEXT = (
    "「マジェスペクター・フロッグ」の①のモンスター効果は１ターンに１度しか使用できない。"
    "①：このカードが召喚・特殊召喚に成功した時に発動できる。デッキから「マジェスペクター」魔法・罠カード"
    "１枚を選んで自分フィールドにセットする。この効果でセットしたカードはこのターン発動できない。"
    "②：このカードはモンスターゾーンに存在する限り、相手の効果の対象にならず、相手の効果では破壊されない。")
DES_LACOODA = 2326738   # デス・ラクーダ(反転召喚に成功した場合)
DES_LACOODA_TEXT = (
    "①：自分メインフェイズに発動できる。このカードを裏側守備表示にする（１ターンに１度のみ）。"
    "②：このカードが反転召喚に成功した場合に発動する。自分はデッキから１枚ドローする。")
MOBIUS = 4929256   # 氷帝メビウス(アドバンス召喚に成功した時)
MOBIUS_TEXT = ("①：このカードがアドバンス召喚に成功した時、フィールドの魔法・罠カードを２枚まで"
               "対象として発動できる。そのカードを破壊する。")
MAXIMUM_SIX = 30707994   # マキシマム・シックス(舊式:生け贄召喚に成功した時)
MAXIMUM_SIX_TEXT = ("このカードが生け贄召喚に成功した時、サイコロを１回振る。このカードの攻撃力は、"
                    "フィールド上に表側表示で存在する限り、出た目×２００ポイントアップする。")
ETHEREAL_HOLY = 56804361   # 魔装聖龍 イーサルウェポン(P召喚に成功した時)
ETHEREAL_HOLY_TEXT = (
    "「魔装聖龍 イーサルウェポン」の効果は１ターンに１度しか使用できない。①：このカードがP召喚に成功した時、"
    "フィールドのカード１枚を対象として発動できる。そのカードを持ち主の手札に戻す。")
ZEROORL = 1487805   # 宇宙鋏ゼロオル(リンク召喚に成功した場合;爬虫類族モンスター１体を召喚する)
ZEROORL_TEXT = (
    "爬虫類族モンスター２体以上\nこのカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードがリンク召喚に成功した場合に発動できる。Aカウンターを置く効果を持つカード１枚を"
    "デッキから手札に加える。②：自分・相手フィールドのAカウンターを２つ取り除いて発動できる。"
    "爬虫類族モンスター１体を召喚する。③：このカードがモンスターゾーンに存在する限り、"
    "Aカウンターが置かれている相手モンスターは、守備表示になり、効果を発動できない。")
REAL_GENEX_MAGNA = 1533292   # レアル・ジェネクス・マグナ(新式:召喚した時)
REAL_GENEX_MAGNA_TEXT = ("①：このカードが召喚した時に発動できる。デッキからレベル２の「レアル・ジェネクス」"
                         "モンスター１体を手札に加える。")
YOKO = 3486020   # 麗の魔妖－妖狐(墓地からの特殊召喚に成功した場合)
YOKO_TEXT = (
    "チューナー＋チューナー以外のモンスター１体以上\nこのカード名の②③の効果はそれぞれ１ターンに１度しか"
    "使用できない。①：「麗の魔妖－妖狐」は自分フィールドに１体しか表側表示で存在できない。"
    "②：このカードが墓地に存在し、元々のレベルが１１の自分のSモンスターが戦闘または相手の効果で破壊された"
    "場合に発動できる。自分の墓地から他のアンデット族モンスター１体を除外し、このカードを特殊召喚する。"
    "③：このカードが墓地からの特殊召喚に成功した場合に発動できる。相手フィールドのモンスター１体を選んで"
    "破壊する。")
ALIEN_DOG = 15475415   # エーリアン・ドッグ(「X」モンスターの召喚に成功した時;この効果で特殊召喚に成功した時)
ALIEN_DOG_TEXT = (
    "自分が「エーリアン」と名のついたモンスターの召喚に成功した時、このカードを手札から特殊召喚できる。"
    "この効果で特殊召喚に成功した時、相手フィールド上に表側表示で存在するモンスターにAカウンターを２つ置く。")
RETIARI = 612115   # 剣闘獣レティアリィ(「X」と名のついたモンスターの効果によって特殊召喚に成功した時)
RETIARI_TEXT = (
    "このカードが「剣闘獣」と名のついたモンスターの効果によって特殊召喚に成功した時、相手の墓地のカード"
    "１枚を選択して除外できる。このカードが戦闘を行ったバトルフェイズ終了時にこのカードをデッキに戻す事で、"
    "デッキから「剣闘獣レティアリィ」以外の「剣闘獣」と名のついたモンスター１体を特殊召喚する。")
GILASAURUS = 45894482   # 俊足のギラザウルス(このカードの①の方法で特殊召喚に成功した場合)
GILASAURUS_TEXT = (
    "①：このカードは手札から特殊召喚できる。②：このカードの①の方法で特殊召喚に成功した場合に発動する。"
    "相手は自身の墓地のモンスター１体を選んで特殊召喚できる。")
SHADOW_VAMPIRE = 14212201   # シャドウ・ヴァンパイア(この効果で特殊召喚に成功したターン;被召喚的不是此卡)
SHADOW_VAMPIRE_TEXT = (
    "このカードをX召喚の素材とする場合、闇属性モンスターのX召喚にしか使用できない。"
    "①：このカードが召喚に成功した時に発動できる。手札・デッキから「シャドウ・ヴァンパイア」以外の闇属性の"
    "「ヴァンパイア」モンスター１体を特殊召喚する。この効果で特殊召喚に成功したターン、"
    "そのモンスター以外の自分のモンスターは攻撃できない。")
VAMPIRE_FRAULEIN = 6039967   # ヴァンパイア・フロイライン(闇屬性的「ヴァンパイア」怪獸,代入用)
MAGICAL_GEARS = 313513   # 魔法の歯車(解析不出的段裡有「召喚条件」「特殊召喚」「通常召喚」,沒有單獨的召喚)
MAGICAL_GEARS_TEXT = (
    "①：自分フィールドの表側表示の「アンティーク・ギア」カード３枚を墓地へ送って発動できる。"
    "手札及びデッキからそれぞれ１体まで、「古代の機械巨人」を召喚条件を無視して特殊召喚する。"
    "その後、自分フィールドに「古代の機械巨人」以外のモンスターが存在する場合、そのモンスターを全て破壊する。"
    "この効果の発動後、自分のターンで数えて２ターンの間、自分は通常召喚できない。")
LAVAL_LANCELORD = 123709   # ラヴァル・ランスロッド(這輪沒收的「リリースなしで召喚できる」)
LAVAL_LANCELORD_TEXT = (
    "このカードはリリースなしで召喚できる。この方法で召喚したこのカードは、エンドフェイズ時に墓地へ送られる。"
    "フィールド上のこのカードが破壊され墓地へ送られた時、ゲームから除外されている自分の炎属性モンスター"
    "１体を選択して手札に加える事ができる。")
CYBER_PRIMA = 2158562   # サイバー・プリマ(字母寫法:A召喚した場合)
CYBER_PRIMA_TEXT = "①：このカードがA召喚した場合に発動する。フィールドの表側表示の魔法カードを全て破壊する。"
PRIMA_LIGHT = 2507443   # プリマの光(手札の戦士族モンスター１体の召喚を行う)
PRIMA_LIGHT_TEXT = (
    "このカード名の①②の効果は１ターンに１度、いずれか１つしか使用できない。\n"
    "①：以下の効果から１つを選択して発動できる。\n"
    "●自分フィールドの戦士族・地属性モンスター１体をリリースし、手札・デッキから戦士族・光属性モンスター"
    "１体を特殊召喚する。\n●自分・相手のメインフェイズに発動できる。手札の戦士族モンスター１体の召喚を行う。\n"
    "②：自分メインフェイズに墓地のこのカードを除外して発動できる。デッキから戦士族・天使族の「サイバー」"
    "モンスター１体を手札に加える。")
REPTILE = 0x80000
ARCHETYPES = [
    {"setcode": 0x54, "hex": "0x54", "names_ja": ["ガガガ"], "name_zh": "我我我",
     "source": "strings.conf"},
    {"setcode": 0xd0, "hex": "0xd0", "names_ja": ["マジェスペクター"], "name_zh": "威風妖怪",
     "source": "strings.conf"},
    {"setcode": 0x1002, "hex": "0x1002", "names_ja": ["レアル・ジェネクス"], "name_zh": "真次世代",
     "source": "strings.conf"},
    {"setcode": 0x93, "hex": "0x93", "names_ja": ["サイバー"], "name_zh": "電子",
     "source": "strings.conf"},
    {"setcode": 0xc, "hex": "0xc", "names_ja": ["エーリアン"], "name_zh": "外星人",
     "source": "strings.conf"},
    {"setcode": 0x1019, "hex": "0x1019", "names_ja": ["剣闘獣", "グラディアルビースト"],
     "name_zh": "劍鬥獸", "source": "strings.conf"},
    {"setcode": 0x8e, "hex": "0x8e", "names_ja": ["ヴァンパイア"], "name_zh": "吸血鬼",
     "source": "strings.conf"},
]


class SummonFixture(unittest.TestCase):
    """固定夾:各種召喚寫法的真實卡。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(GAGAGA_SISTER, name_ja="ガガガシスター", level=2, race=0x2, attribute=0x20,
                 atk=200, setcode=0x54),
            card(DARK_SAGE, name_ja="黒衣の大賢者", level=9, race=0x2, attribute=0x20, atk=2800),
            card(MAJESPECTER_FROG, name_ja="マジェスペクター・フロッグ", type=0x1000021, level=4,
                 race=0x2, attribute=0x8, atk=1300, setcode=0xd0),
            card(DES_LACOODA, name_ja="デス・ラクーダ", level=3, race=0x10, attribute=0x1, atk=500),
            card(MOBIUS, name_ja="氷帝メビウス", level=6, race=0x40, attribute=0x2, atk=2400),
            card(MAXIMUM_SIX, name_ja="マキシマム・シックス", level=6, race=0x1, attribute=0x1,
                 atk=1900),
            card(ETHEREAL_HOLY, name_ja="魔装聖龍 イーサルウェポン", level=6, race=0x2000,
                 attribute=0x10, atk=2300, setcode=0xcb),
            card(ZEROORL, name_ja="宇宙鋏ゼロオル", type=0x4000021, level=3, race=REPTILE,
                 attribute=0x10, atk=2600),
            card(REAL_GENEX_MAGNA, name_ja="レアル・ジェネクス・マグナ", level=3, race=0x80,
                 attribute=0x4, atk=1000, setcode=0x1002),
            card(YOKO, name_ja="麗の魔妖－妖狐", type=0x2021, level=9, race=0x10, attribute=0x4,
                 atk=2900, setcode=0x121),
            card(1001, name_ja="爬虫類", level=4, race=REPTILE, attribute=0x1),
            card(CYBER_PRIMA, name_ja="サイバー・プリマ", level=6, race=0x1, attribute=0x10,
                 atk=2300, setcode=0x93),
            card(PRIMA_LIGHT, name_ja="プリマの光", type=0x10002),
            card(MAGICAL_GEARS, name_ja="魔法の歯車", type=SPELL),
            card(LAVAL_LANCELORD, name_ja="ラヴァル・ランスロッド", level=6, race=0x1,
                 attribute=0x4, atk=2100, setcode=0x39),
            card(ALIEN_DOG, name_ja="エーリアン・ドッグ", level=3, race=REPTILE, attribute=0x10,
                 atk=1500, setcode=0xc),
            card(RETIARI, name_ja="剣闘獣レティアリィ", level=3, race=0x40, attribute=0x2,
                 atk=1200, setcode=0x1019),
            card(GILASAURUS, name_ja="俊足のギラザウルス", level=3, race=0x10000, attribute=0x1,
                 atk=1400),
            card(SHADOW_VAMPIRE, name_ja="シャドウ・ヴァンパイア", level=5, race=0x10,
                 attribute=0x20, atk=2000, setcode=0x8e),
            card(VAMPIRE_FRAULEIN, name_ja="ヴァンパイア・フロイライン", level=5, race=0x10,
                 attribute=0x20, atk=600, setcode=0x8e),
        ]
        cls.faq = [
            faq(GAGAGA_SISTER, "ガガガシスター", GAGAGA_SISTER_TEXT),
            faq(DARK_SAGE, "黒衣の大賢者", DARK_SAGE_TEXT),
            faq(MAJESPECTER_FROG, "マジェスペクター・フロッグ", MAJESPECTER_FROG_TEXT),
            faq(DES_LACOODA, "デス・ラクーダ", DES_LACOODA_TEXT),
            faq(MOBIUS, "氷帝メビウス", MOBIUS_TEXT),
            faq(MAXIMUM_SIX, "マキシマム・シックス", MAXIMUM_SIX_TEXT),
            faq(ETHEREAL_HOLY, "魔装聖龍 イーサルウェポン", ETHEREAL_HOLY_TEXT),
            faq(ZEROORL, "宇宙鋏ゼロオル", ZEROORL_TEXT),
            faq(REAL_GENEX_MAGNA, "レアル・ジェネクス・マグナ", REAL_GENEX_MAGNA_TEXT),
            faq(YOKO, "麗の魔妖－妖狐", YOKO_TEXT),
            faq(CYBER_PRIMA, "サイバー・プリマ", CYBER_PRIMA_TEXT),
            faq(PRIMA_LIGHT, "プリマの光", PRIMA_LIGHT_TEXT),
            faq(MAGICAL_GEARS, "魔法の歯車", MAGICAL_GEARS_TEXT),
            faq(LAVAL_LANCELORD, "ラヴァル・ランスロッド", LAVAL_LANCELORD_TEXT),
            faq(ALIEN_DOG, "エーリアン・ドッグ", ALIEN_DOG_TEXT),
            faq(RETIARI, "剣闘獣レティアリィ", RETIARI_TEXT),
            faq(GILASAURUS, "俊足のギラザウルス", GILASAURUS_TEXT),
            faq(SHADOW_VAMPIRE, "シャドウ・ヴァンパイア", SHADOW_VAMPIRE_TEXT),
        ]
        cls.structures, cls.report = build_structures(cls.cards, cls.faq, archetypes=ARCHETYPES)

    def run_query(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return [hit["id"] for hit in self.run_query(**query)["hits"]]

    def hit_segments(self, cid, **query):
        """那張卡的命中段 id;沒命中回 None。"""
        return next((hit["segments"] for hit in self.run_query(**query)["hits"]
                     if hit["id"] == cid), None)

    def structure(self, cid):
        return next(c for c in self.structures if c["id"] == cid)


class BareSummonTest(SummonFixture):
    """單獨的「召喚」是動作詞 召喚,通常召喚的下位詞(spec「單獨的「召喚」記成什麼?」)。"""

    def test_summon_success_condition_hits_summon_and_normal_summon(self):
        """ガガガシスター「このカードが召喚に成功した時」:開條件段查「召喚」「通常召喚」都命中,
        指定此卡當物件也命中;條件段開關關時不命中。"""
        for action in ("召喚", "通常召喚"):
            self.assertIn(GAGAGA_SISTER, self.hits(actions=[action], include_condition=True))
            self.assertIn(GAGAGA_SISTER, self.hits(actions=[action], include_condition=True,
                                                   card=GAGAGA_SISTER))
        self.assertNotIn(GAGAGA_SISTER, self.hits(actions=["召喚"]))

    def test_summon_does_not_hit_a_literal_normal_summon(self):
        """黒衣の大賢者「このカードは通常召喚できない」:查「通常召喚」(極性 不能)命中,
        查「召喚」不命中,也不因字面「通常召喚」「特殊召喚」進未解析組。"""
        query = {"polarities": ["不能"], "kinds": ["限制"]}
        self.assertIn(DARK_SAGE, self.hits(actions=["通常召喚"], **query))
        result = self.run_query(actions=["召喚"], **query)
        self.assertNotIn(DARK_SAGE, [hit["id"] for hit in result["hits"]])
        self.assertNotIn(DARK_SAGE, result["groups"]["未解析"])

    def test_summon_as_an_effect_hits_with_the_summoned_monster(self):
        """宇宙鋏ゼロオル「爬虫類族モンスター１体を召喚する」:效果段的 召喚,爬虫類族代入命中、此卡自己
        (效果裡被召喚的不是此卡)不命中。"""
        self.assertIn(ZEROORL, self.hits(actions=["召喚"], card=1001))
        self.assertNotIn(ZEROORL, self.hits(actions=["召喚"], card=GAGAGA_SISTER))

    def test_new_style_summoned_and_old_style_succeeded_answer_the_same(self):
        """「このカードが召喚した時」(レアル・ジェネクス・マグナ)與「このカードが召喚に成功した時」
        (ガガガシスター)同一組查詢結果相同:此卡是被召喚的那一方。"""
        queries = [
            {"actions": ["召喚"], "include_condition": True},
            {"actions": ["通常召喚"], "include_condition": True},
            {"actions": ["召喚"], "kinds": ["條件"], "include_condition": True},
            {"actions": ["召喚"]},
            {"actions": ["特殊召喚"], "include_condition": True},
            {"actions": ["上級召喚"], "include_condition": True},
            {"actions": ["反轉召喚"], "include_condition": True},
        ]
        for query in queries:
            hits = self.hits(**query)
            self.assertEqual(REAL_GENEX_MAGNA in hits, GAGAGA_SISTER in hits, query)
        for cid in (REAL_GENEX_MAGNA, GAGAGA_SISTER):
            own = {"actions": ["召喚"], "kinds": ["條件"], "include_condition": True, "card": cid}
            self.assertEqual(self.hits(**own), [cid])
        self.assertIn(REAL_GENEX_MAGNA, self.hits(actions=["召喚"], include_condition=True))


class UnparsedGroupLiteralTest(SummonFixture):
    """未解析組比字面:「召喚」落在別種召喚與「召喚条件」裡不算(spec「查詢判斷」)。"""

    ALL = {"polarities": ["做", "不能", "不會", "可以", "只能", "必須"]}

    def test_other_summons_and_summon_condition_are_not_the_bare_summon(self):
        """魔法の歯車:解析不出的段寫的是「召喚条件を無視して特殊召喚する」「通常召喚できない」。
        查「召喚」不列它;查「特殊召喚」「通常召喚」照舊列進未解析組。"""
        self.assertNotIn(MAGICAL_GEARS, self.run_query(actions=["召喚"], **self.ALL)["groups"]["未解析"])
        self.assertNotIn(MAGICAL_GEARS, self.hits(actions=["召喚"], **self.ALL))
        for action in ("特殊召喚", "通常召喚"):
            self.assertIn(MAGICAL_GEARS,
                          self.run_query(actions=[action], **self.ALL)["groups"]["未解析"], action)

    def test_unparsed_bare_summon_is_not_silently_dropped(self):
        """ラヴァル・ランスロッド「このカードはリリースなしで召喚できる」這輪沒收:查「召喚」「通常召喚」時
        不是命中就是列在未解析組,不會兩邊都沒有;查「特殊召喚」「上級召喚」不列。"""
        for action in ("召喚", "通常召喚"):
            result = self.run_query(actions=[action])
            listed = result["groups"]["未解析"] + [hit["id"] for hit in result["hits"]]
            self.assertIn(LAVAL_LANCELORD, listed, action)
        for action in ("特殊召喚", "上級召喚", "反轉召喚"):
            result = self.run_query(actions=[action])
            self.assertNotIn(LAVAL_LANCELORD, result["groups"]["未解析"], action)


class SummonKindsTest(SummonFixture):
    """各種召喚的寫法與上下位詞(spec 使用者故事 4–8)。"""

    def test_enumerated_summons_hit_each_listed_action_on_the_same_segment(self):
        """マジェスペクター・フロッグ「召喚・特殊召喚に成功した時」:查「特殊召喚」與查「召喚」命中同一段,
        兩個一起查也命中;查「反轉召喚」不命中。"""
        special = self.hit_segments(MAJESPECTER_FROG, actions=["特殊召喚"], include_condition=True)
        normal = self.hit_segments(MAJESPECTER_FROG, actions=["召喚"], include_condition=True)
        self.assertIsNotNone(special)
        self.assertEqual(special, normal)
        self.assertEqual(len(special), 1)
        self.assertIn(MAJESPECTER_FROG, self.hits(actions=["召喚", "特殊召喚"],
                                                  include_condition=True))
        self.assertNotIn(MAJESPECTER_FROG, self.hits(actions=["反轉召喚"], include_condition=True))

    def test_flip_summon_is_its_own_action(self):
        """デス・ラクーダ「反転召喚に成功した場合」:查「反轉召喚」命中;查「召喚」「通常召喚」「特殊召喚」
        都不命中,也不進未解析組。"""
        self.assertIn(DES_LACOODA, self.hits(actions=["反轉召喚"], include_condition=True,
                                             card=DES_LACOODA))
        for action in ("召喚", "通常召喚", "特殊召喚"):
            result = self.run_query(actions=[action], include_condition=True)
            self.assertNotIn(DES_LACOODA, [hit["id"] for hit in result["hits"]], action)
            self.assertNotIn(DES_LACOODA, result["groups"]["未解析"], action)

    def test_tribute_summon_is_under_summon(self):
        """氷帝メビウス「アドバンス召喚に成功した時」與舊式 マキシマム・シックス「生け贄召喚に成功した時」:
        查「上級召喚」「召喚」「通常召喚」都命中;查「上級召喚」只命中寫アドバンス召喚、生け贄召喚(與字母寫法
        A召喚)的卡,不命中只寫「召喚」的 ガガガシスター、「召喚・特殊召喚」的 マジェスペクター・フロッグ。"""
        for action in ("上級召喚", "召喚", "通常召喚"):
            hits = self.hits(actions=[action], include_condition=True)
            self.assertIn(MOBIUS, hits, action)
            self.assertIn(MAXIMUM_SIX, hits, action)
        tribute = self.run_query(actions=["上級召喚"], include_condition=True)
        self.assertEqual(sorted(hit["id"] for hit in tribute["hits"]),
                         sorted([MOBIUS, MAXIMUM_SIX, CYBER_PRIMA]))
        self.assertNotIn(MOBIUS, self.hits(actions=["特殊召喚"], include_condition=True))

    def test_letter_a_summon_is_the_tribute_summon(self):
        """サイバー・プリマ「このカードがA召喚した場合」:A召喚是アドバンス召喚的字母寫法,
        查「上級召喚」「召喚」命中,查「特殊召喚」不命中。"""
        for action in ("上級召喚", "召喚"):
            self.assertIn(CYBER_PRIMA, self.hits(actions=[action], include_condition=True,
                                                 card=CYBER_PRIMA))
        self.assertNotIn(CYBER_PRIMA, self.hits(actions=["特殊召喚"], include_condition=True))

    def test_perform_a_summon_names_the_summoned_monster(self):
        """プリマの光「手札の戦士族モンスター１体の召喚を行う」:查「召喚,從手牌」戰士族代入命中,
        魔法使族不命中;那一段不是特殊召喚。"""
        query = {"actions": ["召喚"], "from_zones": ["手牌"]}
        segments = self.hit_segments(PRIMA_LIGHT, card=MAXIMUM_SIX, **query)
        self.assertIsNotNone(segments)
        self.assertIsNone(self.hit_segments(PRIMA_LIGHT, card=GAGAGA_SISTER, **query))
        special = self.hit_segments(PRIMA_LIGHT, actions=["特殊召喚"]) or []
        self.assertFalse(set(segments) & set(special))

    def test_pendulum_summon_is_under_special_summon(self):
        """魔装聖龍 イーサルウェポン「P召喚に成功した時」:查「特殊召喚」「P召喚」命中,查「召喚」不命中。"""
        for action in ("特殊召喚", "P召喚"):
            self.assertIn(ETHEREAL_HOLY, self.hits(actions=[action], include_condition=True,
                                                   card=ETHEREAL_HOLY))
        self.assertNotIn(ETHEREAL_HOLY, self.hits(actions=["召喚"], include_condition=True))

    def test_katakana_link_summon_is_the_letter_one(self):
        """宇宙鋏ゼロオル「リンク召喚に成功した場合」:查「L召喚」「特殊召喚」命中那一段,
        查「召喚」(條件段)不命中那一段。"""
        link = self.hit_segments(ZEROORL, actions=["L召喚"], kinds=["條件"], include_condition=True)
        self.assertIsNotNone(link)
        self.assertEqual(link, self.hit_segments(ZEROORL, actions=["特殊召喚"], kinds=["條件"],
                                                 include_condition=True))
        self.assertIsNone(self.hit_segments(ZEROORL, actions=["召喚"], kinds=["條件"],
                                            include_condition=True))

    def test_special_summon_from_graveyard_written_with_karano(self):
        """麗の魔妖－妖狐「このカードが墓地からの特殊召喚に成功した場合」:開條件段查
        「特殊召喚,從墓地」命中那一段(此卡代入),查「從手牌」不命中。"""
        query = {"actions": ["特殊召喚"], "kinds": ["條件"], "include_condition": True, "card": YOKO}
        self.assertIsNotNone(self.hit_segments(YOKO, from_zones=["墓地"], **query))
        self.assertIsNone(self.hit_segments(YOKO, from_zones=["手牌"], **query))


class SummonSuccessSlotsTest(SummonFixture):
    """「〜召喚に成功した」前面的助詞與原因(spec 預設 9)。"""

    def test_no_before_summon_success_marks_the_summoned_monster(self):
        """エーリアン・ドッグ「自分が「エーリアン」と名のついたモンスターの召喚に成功した時」:「の」前的
        怪獸是被召喚的那一方——「エーリアン」怪獸代入命中,別的怪獸不命中。"""
        query = {"actions": ["召喚"], "kinds": ["條件"], "include_condition": True}
        self.assertIsNotNone(self.hit_segments(ALIEN_DOG, card=ALIEN_DOG, **query))
        self.assertIsNone(self.hit_segments(ALIEN_DOG, card=GAGAGA_SISTER, **query))

    def test_effect_of_named_monsters_as_cause_keeps_this_card_summoned(self):
        """剣闘獣レティアリィ「このカードが「剣闘獣」と名のついたモンスターの効果によって特殊召喚に成功した時」:
        被召喚的是此卡(原因裡的「剣闘獣」怪獸不是對象)。"""
        query = {"actions": ["特殊召喚"], "kinds": ["條件"], "include_condition": True}
        self.assertIsNotNone(self.hit_segments(RETIARI, card=RETIARI, **query))
        self.assertIsNone(self.hit_segments(RETIARI, card=GAGAGA_SISTER, **query))

    def test_summoned_by_this_cards_own_effect(self):
        """俊足のギラザウルス「このカードの①の方法で特殊召喚に成功した場合」、エーリアン・ドッグ
        「この効果で特殊召喚に成功した時」:主語省略,被召喚的是那個效果召喚的此卡。"""
        query = {"actions": ["特殊召喚"], "kinds": ["條件"], "include_condition": True}
        for cid in (GILASAURUS, ALIEN_DOG):
            self.assertIsNotNone(self.hit_segments(cid, card=cid, **query), cid)
            self.assertIsNone(self.hit_segments(cid, card=GAGAGA_SISTER, **query), cid)

    def test_summoned_by_this_effect_is_what_the_effect_summoned(self):
        """シャドウ・ヴァンパイア「…「シャドウ・ヴァンパイア」以外の闇属性の「ヴァンパイア」モンスター１体を
        特殊召喚する。この効果で特殊召喚に成功したターン、」:被召喚的是效果召喚的那隻怪獸,不是此卡。"""
        query = {"actions": ["特殊召喚"], "kinds": ["條件"], "include_condition": True}
        self.assertIsNotNone(self.hit_segments(SHADOW_VAMPIRE, card=VAMPIRE_FRAULEIN, **query))
        self.assertIsNone(self.hit_segments(SHADOW_VAMPIRE, card=SHADOW_VAMPIRE, **query))


class SummonReverseCheckTest(SummonFixture):
    """接縫二:召喚的段寫得回原文。"""

    def failing_segments(self, cid):
        return [(f["segment"], f["reason"], f["detail"]) for f in check_card(self.structure(cid))]

    def test_whole_cards_pass_reverse_check(self):
        for cid in (MOBIUS, ETHEREAL_HOLY, GILASAURUS, CYBER_PRIMA, PRIMA_LIGHT):
            self.assertEqual(check_card(self.structure(cid)), [], cid)

    def test_summon_condition_segments_render_back(self):
        """整張還有別的寫法沒收的卡:召喚的那一段不在不通過清單裡。"""
        for cid, action in ((GAGAGA_SISTER, "召喚"), (MAJESPECTER_FROG, "召喚"),
                            (REAL_GENEX_MAGNA, "召喚"),
                            (DES_LACOODA, "反轉召喚"), (ZEROORL, "L召喚"), (YOKO, "特殊召喚"),
                            (ALIEN_DOG, "召喚"), (ALIEN_DOG, "特殊召喚"), (RETIARI, "特殊召喚"),
                            (SHADOW_VAMPIRE, "召喚"), (SHADOW_VAMPIRE, "特殊召喚")):
            segments = self.hit_segments(cid, actions=[action], kinds=["條件"],
                                         include_condition=True)
            self.assertIsNotNone(segments, cid)
            failing = {seg for seg, _, _ in self.failing_segments(cid)}
            self.assertFalse(failing & set(segments), (cid, self.failing_segments(cid)))


if __name__ == "__main__":
    unittest.main()
