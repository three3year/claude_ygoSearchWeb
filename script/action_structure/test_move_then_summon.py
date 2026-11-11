"""移走 + 召喚的て形串接(「XをリリースしてY召喚する」)切成兩段:輸入真實卡的官方 DB 文本與卡片參數,
看查詢結果與反向檢查。

只驗接縫一(查詢判斷)與接縫二(反向檢查),不驗結構內部的格。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import REASON_REF
from test_golden import SPELL, card, faq

GRAVEKEEPER_PRIEST = 3825890   # 墓守の大神官(召喚條件:「墓守の」怪獸をリリースして召喚できる)
GRAVEKEEPER_PRIEST_TEXT = (
    "このカードは「墓守の」と名のついたモンスター１体をリリースして召喚できる。このカードの攻撃力は、"
    "自分の墓地の「墓守の」と名のついたモンスターの数×２００ポイントアップする。また、フィールド上に"
    "表側表示で存在するこのカードが破壊される場合、代わりに手札から「墓守の」と名のついたモンスター１体を"
    "捨てる事ができる。")
ROOKLORD = 10060427   # コアキメイル・ルークロード(召喚條件:「コアキメイル」怪獸をリリースしてアドバンス召喚できる)
ROOKLORD_TEXT = (
    "このカードのコントローラーは自分のエンドフェイズ毎に、手札から「コアキメイルの鋼核」１枚を墓地へ送るか、"
    "手札の戦士族モンスター１体を相手に見せる。または、どちらも行わずにこのカードを破壊する。"
    "このカードは「コアキメイル」と名のついたモンスター１体をリリースしてアドバンス召喚できる。"
    "このカードが召喚に成功した時、自分の墓地の「コアキメイル」と名のついたカード１枚をゲームから除外する事で、"
    "相手フィールド上のカードを２枚まで選択して破壊する。")
FENRIR = 218704   # フェンリル(召喚條件:水屬性怪獸をゲームから除外して特殊召喚する)
FENRIR_TEXT = (
    "このカードは通常召喚できない。自分の墓地の水属性モンスター２体をゲームから除外して特殊召喚する。"
    "このカードが戦闘によって相手モンスターを破壊した場合、次の相手ターンのドローフェイズをスキップする。")
GAZER_SHARK = 23536866   # ゲイザー・シャーク(不切:効果を無効にして特殊召喚し)
GAZER_SHARK_TEXT = (
    "墓地のこのカードをゲームから除外し、「ゲイザー・シャーク」以外の自分の墓地の水属性・レベル５モンスター"
    "２体を選択して発動できる。選択したモンスター２体の効果を無効にして特殊召喚し、その２体のみを素材として"
    "水属性のエクシーズモンスター１体をエクシーズ召喚する。「ゲイザー・シャーク」の効果は１ターンに１度しか"
    "使用できない。")
LETHAL_WEAPON = 45450218   # A・O・J リーサル・ウェポン(不切:相手に見せて特殊召喚できる)
LETHAL_WEAPON_TEXT = (
    "このカードが戦闘によって光属性モンスターを破壊し墓地へ送った時、デッキからカードを１枚ドローする。"
    "さらに、この効果でドローしたカードがレベル４以下の闇属性モンスターだった場合、そのカードを相手に見せて"
    "特殊召喚できる。")
CROSSING_SOULS = 5253985   # 交差する魂(魔法卡;右半沒寫主語,指回前面那次 A召喚的怪獸)
CROSSING_SOULS_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できない。\n①：自分・相手のメインフェイズに発動できる。"
    "幻神獣族モンスター１体のA召喚を行う。その際、自分フィールドのモンスターの代わりに相手フィールドの"
    "モンスターをリリースする事もできる。相手フィールドのモンスターをリリースしてA召喚した場合、"
    "以下の効果を適用する。\n●このカードの発動後、次のターンの終了時まで自分は幻神獣族モンスター以外の"
    "魔法・罠・モンスターの効果を１ターンに１度しか発動できない。")
GETSUGA = 76930964   # 黄昏の忍者将軍－ゲツガ(整張通過的替代卡:「忍者」怪獸をリリースしてアドバンス召喚できる)
GETSUGA_TEXT = (
    "このカードは「忍者」モンスター１体をリリースしてアドバンス召喚できる。「黄昏の忍者将軍－ゲツガ」の効果は"
    "１ターンに１度しか使用できない。①：このカードがフィールドに攻撃表示で存在する場合、"
    "「黄昏の忍者将軍－ゲツガ」以外の自分の墓地の「忍者」モンスター２体を対象として発動できる。"
    "このカードを守備表示にし、対象のモンスターを特殊召喚する。")
# 交差する魂拿掉前面「幻神獣族モンスター１体のA召喚を行う」那幾句的改寫(全庫沒有這種真實卡文,只驗找不到時的規則)。
ORPHAN_SOULS = 9001
ORPHAN_SOULS_TEXT = "①：相手フィールドのモンスターをリリースしてA召喚した場合、以下の効果を適用する。"
ARMY_GENEX = 93211836   # アーミー・ジェネクス(整張通過的替代卡;條件段:このカードが〜をリリースしてアドバンス召喚した時)
ARMY_GENEX_TEXT = (
    "①：このカードが「ジェネクス」モンスターをリリースしてアドバンス召喚した時、相手フィールドのカード１枚を"
    "対象として発動できる。その相手のカードを破壊する。")
ADVANCE_FORCE = 38589847   # アドバンス・フォース(永續魔法;主語「レベル７以上のモンスターは」寫在左半前)
ADVANCE_FORCE_TEXT = ("このカードがフィールド上に存在する限り、レベル７以上のモンスターはレベル５以上の"
                      "モンスター１体をリリースしてアドバンス召喚する事ができる。")
GRAVEKEEPER = 2001   # 「墓守の」怪獸(代入用)
NINJA = 2002   # 「忍者」怪獸(代入用)
CORE = 2003   # 「コアキメイル」怪獸(代入用)
GENEX = 2004   # 「ジェネクス」怪獸(代入用)
PLAIN = 2005   # 沒有字段的地屬性戰士族怪獸(代入用)
WATER = 2006   # 水屬性怪獸(代入用)
DIVINE = 2007   # 幻神獸族怪獸(代入用)
LEVEL_8 = 2008   # 等級 8 怪獸(代入用)
LEVEL_6 = 2009   # 等級 6 怪獸(代入用)
DIVINE_BEAST = 0x200000
WATER_ATTRIBUTE = 0x2
ARCHETYPES = [
    {"setcode": 0x2e, "hex": "0x2e", "names_ja": ["墓守"], "name_zh": "守墓", "source": "strings.conf"},
    {"setcode": 0x1d, "hex": "0x1d", "names_ja": ["コアキメイル"], "name_zh": "核成",
     "source": "strings.conf"},
    {"setcode": 0x2b, "hex": "0x2b", "names_ja": ["忍者"], "name_zh": "忍者", "source": "strings.conf"},
    {"setcode": 0x2, "hex": "0x2", "names_ja": ["ジェネクス"], "name_zh": "次世代",
     "source": "strings.conf"},
]


class MoveThenSummonFixture(unittest.TestCase):
    """固定夾:移走 + 召喚的真實卡、不切的對照卡與代入用的怪獸。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(GRAVEKEEPER_PRIEST, name_ja="墓守の大神官", level=8, race=0x2, attribute=0x20,
                 atk=2000, setcode=0x2e),
            card(ROOKLORD, name_ja="コアキメイル・ルークロード", level=7, race=0x1, attribute=0x1,
                 atk=2800, setcode=0x1d),
            card(FENRIR, name_ja="フェンリル", type=0x2000021, level=4, race=0x4000,
                 attribute=WATER_ATTRIBUTE, atk=1400),
            card(GAZER_SHARK, name_ja="ゲイザー・シャーク", level=5, race=0x20000,
                 attribute=WATER_ATTRIBUTE, atk=1000, setcode=0x1b8),
            card(LETHAL_WEAPON, name_ja="Ａ・Ｏ・Ｊ リーサル・ウェポン", level=5, race=0x20,
                 attribute=0x20, atk=2200, setcode=0x1),
            card(CROSSING_SOULS, name_ja="交差する魂", type=0x10002),
            card(GETSUGA, name_ja="黄昏の忍者将軍－ゲツガ", level=8, race=0x1, attribute=0x20,
                 atk=2000, setcode=0x2b),
            card(ARMY_GENEX, name_ja="アーミー・ジェネクス", level=6, race=0x20, attribute=0x1,
                 atk=2300, setcode=0x2),
            card(ADVANCE_FORCE, name_ja="アドバンス・フォース", type=0x20002),
            card(ORPHAN_SOULS, name_ja="孤立する魂", type=SPELL),
            card(GRAVEKEEPER, name_ja="墓守の偵察者", level=4, race=0x2, attribute=0x20, setcode=0x2e),
            card(NINJA, name_ja="忍者マスター", level=4, race=0x1, attribute=0x20, setcode=0x2b),
            card(CORE, name_ja="コアキメイル・ガーディアン", level=4, race=0x1, attribute=0x1,
                 setcode=0x1d),
            card(GENEX, name_ja="ジェネクス・コントローラー", level=3, race=0x20, attribute=0x20,
                 setcode=0x2),
            card(PLAIN, name_ja="戦士", level=4, race=0x1, attribute=0x1),
            card(WATER, name_ja="水の怪獸", level=4, race=0x40, attribute=WATER_ATTRIBUTE),
            card(DIVINE, name_ja="幻神獣", level=10, race=DIVINE_BEAST, attribute=0x10),
            card(LEVEL_8, name_ja="大きな怪獸", level=8, race=0x1, attribute=0x1),
            card(LEVEL_6, name_ja="中くらいの怪獸", level=6, race=0x1, attribute=0x1),
        ]
        cls.faq = [
            faq(GRAVEKEEPER_PRIEST, "墓守の大神官", GRAVEKEEPER_PRIEST_TEXT),
            faq(ROOKLORD, "コアキメイル・ルークロード", ROOKLORD_TEXT),
            faq(FENRIR, "フェンリル", FENRIR_TEXT),
            faq(GAZER_SHARK, "ゲイザー・シャーク", GAZER_SHARK_TEXT),
            faq(LETHAL_WEAPON, "A・O・J リーサル・ウェポン", LETHAL_WEAPON_TEXT),
            faq(CROSSING_SOULS, "交差する魂", CROSSING_SOULS_TEXT),
            faq(GETSUGA, "黄昏の忍者将軍－ゲツガ", GETSUGA_TEXT),
            faq(ARMY_GENEX, "アーミー・ジェネクス", ARMY_GENEX_TEXT),
            faq(ADVANCE_FORCE, "アドバンス・フォース", ADVANCE_FORCE_TEXT),
            faq(ORPHAN_SOULS, "孤立する魂", ORPHAN_SOULS_TEXT),
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


class ReleasedMonsterIsNotSummonedTest(MoveThenSummonFixture):
    """被解放(除外)的怪獸記在移走那一段,不再標成被召喚(spec 使用者故事 17–21)。"""

    def test_summon_does_not_hit_with_the_released_monster(self):
        """墓守の大神官「〜「墓守の」と名のついたモンスター１体をリリースして召喚できる」:查「召喚」照舊命中,
        被召喚的是此卡;指定另一張「墓守の」怪獸時不因為那一段命中。"""
        self.assertIn(GRAVEKEEPER_PRIEST, self.hits(actions=["召喚"]))
        self.assertIn(GRAVEKEEPER_PRIEST, self.hits(actions=["召喚"], card=GRAVEKEEPER_PRIEST))
        self.assertNotIn(GRAVEKEEPER_PRIEST, self.hits(actions=["召喚"], card=GRAVEKEEPER))

    def test_release_hits_with_the_released_monster(self):
        """墓守の大神官:查「解放」命中。「墓守の」不是字段名(字段是「墓守」),被解放的物件解析不出,
        指定卡代入判不了:指定「墓守の」怪獸或非「墓守の」的怪獸都不命中,而是列進未解析組(票外的寫法)。"""
        self.assertIn(GRAVEKEEPER_PRIEST, self.hits(actions=["解放"]))
        for cid in (GRAVEKEEPER, PLAIN):
            result = self.run_query(actions=["解放"], card=cid)
            self.assertNotIn(GRAVEKEEPER_PRIEST, [hit["id"] for hit in result["hits"]], cid)
            self.assertIn(GRAVEKEEPER_PRIEST, result["groups"]["未解析"], cid)

    def test_release_line_names_the_released_archetype(self):
        """黄昏の忍者将軍－ゲツガ「このカードは「忍者」モンスター１体をリリースしてアドバンス召喚できる」:
        查「解放」指定「忍者」怪獸命中、非「忍者」的怪獸不命中;查「上級召喚」指定此卡命中、
        指定「忍者」怪獸不命中。"""
        self.assertIn(GETSUGA, self.hits(actions=["解放"], card=NINJA))
        self.assertNotIn(GETSUGA, self.hits(actions=["解放"], card=PLAIN))
        self.assertIn(GETSUGA, self.hits(actions=["上級召喚"], card=GETSUGA))
        self.assertNotIn(GETSUGA, self.hits(actions=["上級召喚"], card=NINJA))

    def test_tribute_summon_names_this_card_and_the_released_core(self):
        """コアキメイル・ルークロード「〜「コアキメイル」と名のついたモンスター１体をリリースしてアドバンス召喚
        できる」:查「上級召喚」指定此卡命中、指定別的「コアキメイル」怪獸不命中;查「解放」指定「コアキメイル」
        怪獸命中、非「コアキメイル」的怪獸不命中。"""
        self.assertIn(ROOKLORD, self.hits(actions=["上級召喚"], card=ROOKLORD))
        self.assertNotIn(ROOKLORD, self.hits(actions=["上級召喚"], card=CORE))
        self.assertIn(ROOKLORD, self.hits(actions=["解放"], card=CORE))
        self.assertNotIn(ROOKLORD, self.hits(actions=["解放"], card=PLAIN))

    def test_banished_water_monsters_are_not_special_summoned(self):
        """フェンリル「自分の墓地の水属性モンスター２体をゲームから除外して特殊召喚する」:查「除外」指定水屬性怪獸
        命中、非水屬性不命中;查「特殊召喚」指定此卡命中,指定別的水屬性怪獸不因為那一段命中。"""
        self.assertIn(FENRIR, self.hits(actions=["除外"], card=WATER))
        self.assertNotIn(FENRIR, self.hits(actions=["除外"], card=PLAIN))
        self.assertIn(FENRIR, self.hits(actions=["特殊召喚"], card=FENRIR))
        self.assertNotIn(FENRIR, self.hits(actions=["特殊召喚"], card=WATER))

    def test_subject_written_before_the_release_is_the_summoned(self):
        """アドバンス・フォース(永續魔法)「レベル７以上のモンスターはレベル５以上のモンスター１体をリリースして
        アドバンス召喚する事ができる」:寫了主語,右半的被召喚者是那個主語(不指回別段、也不是此卡)。
        查「上級召喚」指定等級 8 怪獸命中、指定等級 6 怪獸(只夠被解放)或此卡不命中;
        查「解放」指定等級 6、8 怪獸命中,等級 4 怪獸不命中。"""
        self.assertIn(ADVANCE_FORCE, self.hits(actions=["上級召喚"], card=LEVEL_8))
        self.assertNotIn(ADVANCE_FORCE, self.hits(actions=["上級召喚"], card=LEVEL_6))
        self.assertNotIn(ADVANCE_FORCE, self.hits(actions=["上級召喚"], card=ADVANCE_FORCE))
        self.assertIn(ADVANCE_FORCE, self.hits(actions=["解放"], card=LEVEL_6))
        self.assertNotIn(ADVANCE_FORCE, self.hits(actions=["解放"], card=PLAIN))
        self.assertIn(ADVANCE_FORCE, self.hits(actions=["解放"], card=LEVEL_8))



class NonMovingChainStaysOneSegmentTest(MoveThenSummonFixture):
    """左半是不移走卡的動作詞(無效、展示)時照舊一段共用一條線(spec 使用者故事 22)。"""

    def test_negate_and_special_summon_share_one_segment(self):
        """ゲイザー・シャーク「選択したモンスター２体の効果を無効にして特殊召喚し」:查「特殊召喚」命中,
        查「無效」與查「特殊召喚」命中同一段,兩個一起查也命中那一段。"""
        special = self.hit_segments(GAZER_SHARK, actions=["特殊召喚"])
        self.assertIsNotNone(special)
        both = self.hit_segments(GAZER_SHARK, actions=["無效", "特殊召喚"])
        self.assertEqual(len(both), 1)
        self.assertIn(both[0], special)

    def test_reveal_and_special_summon_share_one_segment(self):
        """A・O・J リーサル・ウェポン「そのカードを相手に見せて特殊召喚できる」:查「展示」「特殊召喚」一起查
        命中同一段。"""
        both = self.hit_segments(LETHAL_WEAPON, actions=["展示", "特殊召喚"])
        self.assertIsNotNone(both)
        self.assertEqual(len(both), 1)


class SummonHalfOfASpellTest(MoveThenSummonFixture):
    """右半沒寫主語、此卡不是怪獸:指回同一區塊前面那次召喚的怪獸(spec 使用者故事 44)。"""

    CONDITION = {"actions": ["上級召喚"], "kinds": ["條件"], "include_condition": True}

    def test_unwritten_summoned_is_the_earlier_tribute_summoned_monster(self):
        """交差する魂「相手フィールドのモンスターをリリースしてA召喚した場合」:開條件段只查條件段的「上級召喚」,
        指定幻神獸族怪獸命中;指定這張魔法卡自己或非幻神獸族的怪獸不命中。"""
        self.assertIn(CROSSING_SOULS, self.hits(card=DIVINE, **self.CONDITION))
        self.assertNotIn(CROSSING_SOULS, self.hits(card=CROSSING_SOULS, **self.CONDITION))
        self.assertNotIn(CROSSING_SOULS, self.hits(card=PLAIN, **self.CONDITION))

    def test_no_earlier_summon_leaves_the_summon_half_unparsed(self):
        """改寫的 交差する魂(前面沒有做 A召喚 的段):右半標「指回的物件找不到」列進未解析組,不記成魔法卡
        被召喚;左半的解放照常命中。"""
        result = self.run_query(**self.CONDITION)
        self.assertNotIn(ORPHAN_SOULS, [hit["id"] for hit in result["hits"]])
        entry = next(e for e in result["unparsed"] if e["id"] == ORPHAN_SOULS)
        self.assertEqual([s["reason"] for s in entry["segments"]], [REASON_REF])
        self.assertIn(ORPHAN_SOULS, self.hits(actions=["解放"], kinds=["條件"], include_condition=True))

    def test_release_half_of_the_condition_names_the_opponents_monster(self):
        """交差する魂:開條件段只查條件段的「解放」,左半照常解析出,不指定卡時命中。"""
        self.assertIn(CROSSING_SOULS, self.hits(actions=["解放"], kinds=["條件"],
                                                include_condition=True))


class SplitHalvesWriteBackTest(MoveThenSummonFixture):
    """切開的兩段接回一句,寫回原文相符(spec「述語的串接」最後一條)。"""

    def assert_segments_pass(self, cid, *texts):
        """那張卡原文是 `texts` 的段都解析得出、反向檢查通過。"""
        card_ = self.structure(cid)
        failed = {f["segment"] for f in check_card(card_)}
        found = {seg["text"]: seg for block in card_["blocks"] for seg in block["segments"]}
        for text in texts:
            self.assertIn(text, found, text)
            self.assertIsNone(found[text]["unparsed"], text)
            self.assertNotIn(found[text]["id"], failed, text)

    def test_standard_cards_pass_whole(self):
        """替代標準卡 黄昏の忍者将軍－ゲツガ(召喚條件)、アーミー・ジェネクス(條件段)整張通過。"""
        for cid in (GETSUGA, ARMY_GENEX):
            self.assertEqual(check_card(self.structure(cid)), [], cid)

    def test_candidate_halves_pass(self):
        """候選卡卡在票外的寫法,只驗切開的兩段:各自解析得出、寫回原文相符。"""
        self.assert_segments_pass(ROOKLORD, "このカードは「コアキメイル」と名のついたモンスター１体をリリースして",
                                  "アドバンス召喚できる")
        self.assert_segments_pass(FENRIR, "自分の墓地の水属性モンスター２体をゲームから除外して", "特殊召喚する")
        self.assert_segments_pass(GRAVEKEEPER_PRIEST, "召喚できる")
        self.assert_segments_pass(CROSSING_SOULS, "相手フィールドのモンスターをリリースして", "A召喚した場合")
        self.assert_segments_pass(ADVANCE_FORCE, "アドバンス召喚する事ができる")


if __name__ == "__main__":
    unittest.main()
