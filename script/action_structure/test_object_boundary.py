"""物件切點:物件範圍不往前吞進主語、時點、標籤等前文。

接縫只有查詢判斷(`run_query`)與反向檢查(`check_card`);官方文本逐字寫在測試裡。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import SPELL, card, faq

NORMAL_MONSTER = 0x11
FUSION_MONSTER = 0x61
BLACK_MAGICIAN = 46986414
POT_OF_GREED = 24094653

FENRIR = 218704
FENRIR_TEXT = (
    "このカードは通常召喚できない。自分の墓地の水属性モンスター２体をゲームから除外して特殊召喚する。"
    "このカードが戦闘によって相手モンスターを破壊した場合、次の相手ターンのドローフェイズをスキップする。")

DARK_MAGIC_EXPANDED = 111280
DARK_MAGIC_EXPANDED_TEXT = (
    "①：お互いのフィールド・墓地の「ブラック・マジシャン」「ブラック・マジシャン・ガール」の数によって"
    "以下の効果を適用する。●１体以上：フィールドの魔法使い族・闇属性モンスター１体を選び、"
    "その攻撃力をターン終了時まで１０００アップする。●２体以上：このターン、自分の魔法・罠カードの"
    "効果の発動に対して、相手は魔法・罠・モンスターの効果を発動できず、自分フィールドの魔法・罠カードは"
    "相手の効果では破壊されない。●３体以上：自分フィールドの魔法使い族・闇属性モンスターは"
    "ターン終了時まで相手の効果を受けない。")

ULTIMATE_FLAME_SWORDSMAN = 324483
ULTIMATE_FLAME_SWORDSMAN_TEXT = (
    "「炎の剣士」＋「闘気炎斬龍」\n"
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：相手フィールドのモンスター１体を対象として発動できる（このカードが装備カードを装備している場合、"
    "この効果は相手ターンでも発動できる）。そのモンスターを破壊し、相手に５００ダメージを与える。\n"
    "②：このカードが戦闘を行うダメージステップ開始時に発動できる。このカードの攻撃力はターン終了時まで"
    "倍になる。このターンのエンドフェイズにこのカードは破壊される。")


class GoldenCase(unittest.TestCase):
    cards = []
    faq = []

    @classmethod
    def setUpClass(cls):
        cls.structures, _ = build_structures(cls.cards, cls.faq)

    def run_(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return [hit["id"] for hit in self.run_(**query)["hits"]]

    def unparsed(self, **query):
        return self.run_(**query)["groups"]["未解析"]

    def failures(self, cid):
        structure = next(s for s in self.structures if s["id"] == cid)
        return check_card(structure)

    def assertWritesBack(self, cid, text):
        """那一段存在(原文正好是 `text`),而且通過反向檢查。"""
        structure = next(s for s in self.structures if s["id"] == cid)
        texts = [seg["text"] for block in structure["blocks"] for seg in block["segments"]]
        self.assertIn(text, texts)
        self.assertNotIn(text, self.failed_texts(cid))

    def failed_texts(self, cid):
        """反向檢查沒過的段的原文(無模板與字面不符都算)。"""
        structure = next(s for s in self.structures if s["id"] == cid)
        failed = {f["segment"] for f in check_card(structure) if f["segment"]}
        return [seg["text"] for block in structure["blocks"] for seg in block["segments"]
                if seg["id"] in failed]


class FenrirTest(GoldenCase):
    """フェンリル 218704:「このカードが戦闘によって相手モンスターを破壊した場合」主語與受詞各自成物件。"""
    cards = [
        card(FENRIR, name_ja="フェンリル", level=4, race=0x4000, attribute=0x2, atk=1400),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
        card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
    ]
    faq = [faq(FENRIR, "フェンリル", FENRIR_TEXT)]

    def test_destroy_condition_judges_a_monster_as_the_object(self):
        """查「破壞」開條件段、指定一張怪獸當物件:被破壞的是「相手モンスター」,判得了、命中。"""
        self.assertIn(FENRIR, self.hits(actions=["破壞"], include_condition=True,
                                        card=BLACK_MAGICIAN))

    def test_destroy_condition_rejects_a_spell_as_the_object(self):
        """指定魔法卡:判得了、不命中,也不落進未解析組。"""
        query = dict(actions=["破壞"], include_condition=True, card=POT_OF_GREED)
        self.assertNotIn(FENRIR, self.hits(**query))
        self.assertNotIn(FENRIR, self.unparsed(**query))

    def test_the_condition_segment_writes_back_to_its_text(self):
        self.assertWritesBack(FENRIR, "このカードが戦闘によって相手モンスターを破壊した場合")


class DarkMagicExpandedTest(GoldenCase):
    """黒魔導強化 111280:「●２体以上：」是依值分歧的標籤,不在任何物件的字面裡。"""
    cards = [
        card(DARK_MAGIC_EXPANDED, name_ja="黒魔導強化", type=SPELL),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
        card(FENRIR, name_ja="フェンリル", level=4, race=0x4000, attribute=0x2, atk=1400),
        card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
    ]
    faq = [faq(DARK_MAGIC_EXPANDED, "黒魔導強化", DARK_MAGIC_EXPANDED_TEXT)]

    def test_labels_are_branch_labels_not_part_of_any_object(self):
        """沒有物件因為吞進標籤而解析不出;標籤不是段外殘留;分歧是依值分歧(標籤的值認不得,
        所以段樹那一筆是「分歧前提解析不出」,不是「分歧方式判不出」)。"""
        failures = self.failures(DARK_MAGIC_EXPANDED)
        self.assertNotIn("物件無模板:物件修飾解析不出", [f["detail"] for f in failures])
        self.assertEqual([f["detail"] for f in failures if f["reason"] == "段外殘留"], [])
        self.assertEqual([f["detail"] for f in failures if f["segment"] is None],
                         ["段樹無模板:分歧前提解析不出"])

    def test_no_segment_text_starts_with_a_label(self):
        """標籤後面的句子各自成段,段的原文不含「：」。"""
        texts = [seg["text"] for block in self.structures[0]["blocks"]
                 for seg in block["segments"]]
        self.assertEqual([text for text in texts if "：" in text], [])
        self.assertIn("自分フィールドの魔法使い族・闇属性モンスターはターン終了時まで相手の効果を受けない",
                      texts)

    def test_cannot_be_destroyed_still_hits_after_the_label(self):
        """「●２体以上：」那一支的後半句照舊命中(回歸守門)。"""
        self.assertIn(DARK_MAGIC_EXPANDED,
                      self.hits(actions=["破壞"], polarities=["不會"], card=POT_OF_GREED))


class UltimateFlameSwordsmanTest(GoldenCase):
    """極炎の剣士 324483:「このターンのエンドフェイズにこのカードは破壊される」時點不在物件裡。"""
    cards = [
        card(ULTIMATE_FLAME_SWORDSMAN, name_ja="極炎の剣士", type=FUSION_MONSTER, level=8,
             race=0x1, attribute=0x4, atk=2800),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
    ]
    faq = [faq(ULTIMATE_FLAME_SWORDSMAN, "極炎の剣士", ULTIMATE_FLAME_SWORDSMAN_TEXT)]

    def test_destroy_hits_with_this_card_as_the_object(self):
        """查「破壞」、指定此卡:②的「このカードは破壊される」命中。"""
        self.assertIn(ULTIMATE_FLAME_SWORDSMAN,
                      self.hits(actions=["破壞"], card=ULTIMATE_FLAME_SWORDSMAN))

    def test_the_delayed_segment_writes_back_to_its_text(self):
        self.assertWritesBack(ULTIMATE_FLAME_SWORDSMAN,
                              "このターンのエンドフェイズにこのカードは破壊される")


VALLET_RECHARGER = 5969957
VALLET_RECHARGER_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：EXデッキから特殊召喚された自分フィールドの表側表示の闇属性モンスターが戦闘・効果で破壊された場合、"
    "手札・フィールドのこのカードを墓地へ送り、その破壊されたモンスターの内の１体を対象として発動できる。"
    "そのモンスターとは元々のカード名が異なる闇属性モンスター１体を自分の墓地から特殊召喚する。\n"
    "②：EXデッキから特殊召喚された闇属性モンスターが自分フィールドに存在する限り、"
    "相手モンスターはこのカードを攻撃対象に選択できない。")


class ValletRechargerTest(GoldenCase):
    """ヴァレット・リチャージャー 5969957:「相手モンスターはこのカードを攻撃対象に選択できない」
    主語(相手モンスター)是做動作的一方,查詢指定的卡比的是受詞(このカード)。"""
    cards = [
        card(VALLET_RECHARGER, name_ja="ヴァレット・リチャージャー", level=4, race=0x2000,
             attribute=0x20, atk=0),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
    ]
    faq = [faq(VALLET_RECHARGER, "ヴァレット・リチャージャー", VALLET_RECHARGER_TEXT)]
    QUERY = dict(actions=["選為攻擊對象"], polarities=["不能"])

    def test_hits_with_this_card_as_the_attack_target(self):
        self.assertIn(VALLET_RECHARGER, self.hits(card=VALLET_RECHARGER, **self.QUERY))

    def test_the_subject_monster_is_not_the_attack_target(self):
        """指定別的怪獸:它只對得上主語「相手モンスター」,不命中,也不落進未解析組。"""
        self.assertNotIn(VALLET_RECHARGER, self.hits(card=BLACK_MAGICIAN, **self.QUERY))
        self.assertNotIn(VALLET_RECHARGER, self.unparsed(card=BLACK_MAGICIAN, **self.QUERY))

    def test_the_segment_writes_back_to_its_text(self):
        self.assertWritesBack(
            VALLET_RECHARGER,
            "EXデッキから特殊召喚された闇属性モンスターが自分フィールドに存在する限り、"
            "相手モンスターはこのカードを攻撃対象に選択できない")


SHADOW_LICH = 1426714
SHADOW_LICH_TEXT = (
    "レベル３モンスター×２\n"
    "①：相手ターンに１度、このカードのX素材を１つ取り除いて発動できる。自分フィールドに「幻影トークン」"
    "（悪魔族・闇・星１・攻／守５００）１体を特殊召喚する。②：このカードの攻撃力は、自分フィールドの"
    "「幻影トークン」の数×５００アップする。③：自分フィールドに「幻影トークン」が存在する限り、"
    "相手はこのカードを攻撃対象に選択できない。")
XYZ_MONSTER = 0x800021


class ShadowLichTest(GoldenCase):
    """No.48 シャドー・リッチ 1426714:「相手ターンに１度、」是前提加次數限制,不在物件(超量素材的
    所屬卡)裡。"""
    cards = [card(SHADOW_LICH, name_ja="No.48 シャドー・リッチ", type=XYZ_MONSTER, level=3,
                  race=0x10, attribute=0x20, atk=1800)]
    faq = [faq(SHADOW_LICH, "No.48 シャドー・リッチ", SHADOW_LICH_TEXT)]

    def test_detach_cost_hits(self):
        self.assertIn(SHADOW_LICH, self.hits(actions=["去除"]))

    def test_the_cost_segment_writes_back_to_its_text(self):
        self.assertWritesBack(SHADOW_LICH, "相手ターンに１度、このカードのX素材を１つ取り除いて")


WAKE_CUP_KURO = 6361316
WAKE_CUP_KURO_TEXT = (
    "このカード名の①②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：手札のこのカードを相手に見せて発動できる。デッキから「WAKE CUP！ クロ」以外の風属性"
    "リバースモンスター１体を手札に加える。その後、自分の手札を１枚選んで捨てる。\n"
    "②：このカードがリバースした場合、フィールドの他の表側表示モンスター１体を対象として発動できる。"
    "そのモンスターを裏側守備表示にする。\n"
    "③：自分・相手ターンに、フィールドの裏側守備表示モンスター１体を対象として発動できる。"
    "そのモンスターを表側守備表示にする。")


class WakeCupKuroTest(GoldenCase):
    """WAKE CUP！ クロ 6361316 ③:「自分・相手ターンに、」沒有規則認得,那一段標
    解析不出;但物件不帶這截字面,後面的「そのモンスター」照常指回它、判得了。"""
    cards = [
        card(WAKE_CUP_KURO, name_ja="WAKE CUP！ クロ", level=7, race=0x40, attribute=0x8, atk=400),
        card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", type=NORMAL_MONSTER, level=7,
             race=0x2, attribute=0x20, atk=2500),
        card(POT_OF_GREED, name_ja="強欲な壺", type=SPELL),
    ]
    faq = [faq(WAKE_CUP_KURO, "WAKE CUP！ クロ", WAKE_CUP_KURO_TEXT)]
    QUERY = dict(actions=["變更表示形式"], targeting=True)

    def test_change_position_judges_a_monster_as_the_target(self):
        self.assertIn(WAKE_CUP_KURO, self.hits(card=BLACK_MAGICIAN, **self.QUERY))

    def test_change_position_rejects_a_spell_as_the_target(self):
        self.assertNotIn(WAKE_CUP_KURO, self.hits(card=POT_OF_GREED, **self.QUERY))

    def test_the_segment_with_the_unknown_front_is_not_written_back(self):
        """前文認不得的那一段不算通過反向檢查;指回它物件的下一段寫回原文相符。"""
        self.assertIn("自分・相手ターンに、フィールドの裏側守備表示モンスター１体を対象として",
                      self.failed_texts(WAKE_CUP_KURO))
        self.assertWritesBack(WAKE_CUP_KURO, "そのモンスターを表側守備表示にする")


if __name__ == "__main__":
    unittest.main()
