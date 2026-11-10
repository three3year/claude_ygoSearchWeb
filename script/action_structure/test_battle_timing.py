"""戰鬥時點:觸發形「ダメージ計算前/時/後」「ダメージステップ開始時/終了時」、
動作詞戰鬥(「Xと戦闘を行う」,施事與受事都是物件)、期間該戰鬥(「ダメージ計算時のみ」)。

走接縫一(查詢判斷)與接縫二(反向檢查)。施事/受事、觸發形、期間沒有查詢欄(spec「查詢判斷」),
先用既有欄查到命中段再讀該段的格。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, card, faq

YUBEL = 78371393   # ユベル
YUBEL_TEXT = (
    "①：このカードは戦闘では破壊されず、このカードの戦闘で発生する自分への戦闘ダメージは"
    "０になる。\n②：攻撃表示のこのカードが攻撃対象に選択された場合、そのダメージ計算前に"
    "発動する。攻撃モンスターの攻撃力分のダメージを相手に与える。\n③：自分エンドフェイズに"
    "発動する。自分フィールドの他のモンスター１体をリリースするか、このカードを破壊する。\n"
    "④：この③の効果以外でこのカードが破壊された時に発動できる。自分の手札・デッキ・墓地から"
    "「ユベル－Das Abscheulich Ritter」１体を特殊召喚する。")
YUBEL_RITTER = 4779091   # ユベル－Das Abscheulich Ritter
GUILTY_GEAR = 49161188   # 鋼鉄の魔導騎士－ギルティギア・フリード
GUILTY_GEAR_TEXT = (
    "属性が異なる戦士族モンスター×２\n①：１ターンに１度、このカードを対象とする魔法・罠・"
    "モンスターの効果が発動した時に発動できる。その効果を無効にし、フィールドのカード１枚を"
    "選んで破壊する。②：フィールドのモンスターのみを素材として融合召喚したこのカードは１度の"
    "バトルフェイズ中に２回攻撃できる。③：１ターンに１度、このカードが相手モンスターと戦闘を"
    "行うダメージ計算時に、自分の墓地から魔法カード１枚を除外して発動できる。このカードの"
    "攻撃力はターン終了時まで、このカードの守備力の半分アップする。")
LILY = 79575620   # お注射天使リリー
LILY_TEXT = (
    "①：このカードが戦闘を行うダメージ計算時に１度、２０００LPを払って発動できる。"
    "このカードの攻撃力はそのダメージ計算時のみ３０００アップする。")
POWER_CODE_TALKER = 15844566   # パワーコード・トーカー
POWER_CODE_TALKER_TEXT = (
    "モンスター３体\n①：１ターンに１度、フィールドの表側表示モンスター１体を対象として発動"
    "できる。そのモンスターの効果をターン終了時まで無効にする。②：１ターンに１度、このカードが"
    "相手モンスターと戦闘を行うダメージ計算時に、このカードのリンク先の自分のモンスター１体を"
    "リリースして発動できる。このカードの攻撃力はそのダメージ計算時のみ、元々の攻撃力の倍になる。")


def build(*entries):
    cards = [c for c, _ in entries]
    structures, _ = build_structures(cards, [f for _, f in entries if f], ARCHETYPES)
    return cards, structures


def structure_of(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in structure_of(structures, cid)["blocks"]
            for _, seg in iter_segments(b) if seg["id"] in ids]


def segment_with(structure, literal):
    for block in structure["blocks"]:
        for _, seg in iter_segments(block):
            if literal in seg["text"]:
                return seg
    raise AssertionError(f"找不到含「{literal}」的段")


def failures_on(structure, seg):
    return [f for f in check_card(structure) if f["segment"] == seg["id"]]


class GuiltyGearTest(unittest.TestCase):
    """鋼鉄の魔導騎士－ギルティギア・フリード ③「このカードが相手モンスターと戦闘を行う
    ダメージ計算時に」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(GUILTY_GEAR, name_ja="鋼鉄の魔導騎士－ギルティギア・フリード", type=97,
                  level=8, race=1, attribute=16, atk=2700, **{"def": 1600}),
             faq(GUILTY_GEAR, "鋼鉄の魔導騎士－ギルティギア・フリード", GUILTY_GEAR_TEXT)))
        cls.structure = structure_of(cls.structures, GUILTY_GEAR)

    def battle_segments(self):
        return hit_segments(self.structures, self.cards, GUILTY_GEAR,
                            actions=["戰鬥"], include_condition=True)

    def test_battle_condition_hits_with_this_card_as_agent(self):
        segs = self.battle_segments()
        self.assertEqual(len(segs), 1)
        roles = {line["role"]: line["object"] for line in segs[0]["lines"]}
        self.assertEqual(roles["施事"], "o0")
        partner = next(o for o in self.structure["objects"] if o["id"] == roles["受事"])
        self.assertEqual(partner["source"]["kind"], "新建")

    def test_battle_condition_trigger_is_damage_calculation(self):
        self.assertEqual([s["trigger"] for s in self.battle_segments()], ["ダメージ計算時"])

    def test_battle_off_condition_scope_does_not_hit(self):
        self.assertEqual(self.battle_segments()[0]["kind"], "條件")
        self.assertEqual(hit_segments(self.structures, self.cards, GUILTY_GEAR,
                                      actions=["戰鬥"]), [])

    def test_battle_condition_passes_reverse_check(self):
        self.assertEqual(failures_on(self.structure, self.battle_segments()[0]), [])


class YubelTest(unittest.TestCase):
    """ユベル ②「攻撃表示のこのカードが攻撃対象に選択された場合、そのダメージ計算前に発動する」:
    「そのダメージ計算前」是另一個條件段(觸發形 ダメージ計算前,指回前一個條件段)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(YUBEL, name_ja="ユベル", level=10, race=8, attribute=32, atk=0,
                  **{"def": 0}),
             faq(YUBEL, "ユベル", YUBEL_TEXT)),
            (card(YUBEL_RITTER, name_ja="ユベル－Das Abscheulich Ritter", level=11, race=8,
                  attribute=32, atk=0, **{"def": 0}), None))
        cls.structure = structure_of(cls.structures, YUBEL)
        cls.timing = segment_with(cls.structure, "そのダメージ計算前")

    def test_damage_calculation_timing_is_a_parsed_condition(self):
        self.assertEqual((self.timing["kind"], self.timing["trigger"], self.timing["unparsed"]),
                         ("條件", "ダメージ計算前", None))

    def test_timing_points_back_to_the_selected_condition(self):
        selected = segment_with(self.structure, "攻撃対象に選択された場合")
        self.assertEqual(self.timing["premise"], {"op": "段已執行", "segment": selected["id"]})

    def test_timing_condition_passes_reverse_check(self):
        self.assertEqual(failures_on(self.structure, self.timing), [])

    def test_activation_sentence_leaves_no_residue(self):
        block = next(b for b in self.structure["blocks"] if "そのダメージ計算前" in b["text"])
        self.assertEqual([f for f in check_card(self.structure)
                          if f["block"] == block["id"] and f["segment"] is None], [])


class LilyTest(unittest.TestCase):
    """お注射天使リリー「このカードが戦闘を行うダメージ計算時に」「そのダメージ計算時のみ３０００
    アップする」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(LILY, name_ja="お注射天使リリー", level=3, race=2, attribute=1, atk=400,
                  **{"def": 1500}),
             faq(LILY, "お注射天使リリー", LILY_TEXT)))
        cls.structure = structure_of(cls.structures, LILY)

    def test_battle_without_partner_hits_with_this_card_as_agent(self):
        segs = hit_segments(self.structures, self.cards, LILY,
                            actions=["戰鬥"], include_condition=True)
        self.assertEqual([[(line["role"], line["object"]) for line in s["lines"]] for s in segs],
                         [[("施事", "o0")]])
        self.assertEqual(segs[0]["trigger"], "ダメージ計算時")
        self.assertEqual(failures_on(self.structure, segs[0]), [])

    def test_boost_lasts_for_that_battle(self):
        """增減本身(「３０００アップする」)解析成性質變更,期間仍是該戰鬥。"""
        boost, = hit_segments(self.structures, self.cards, LILY, actions=["性質變更"],
                              modified={"attr": "攻擊力", "form": "增", "value": 3000})
        self.assertEqual(boost["duration"], {"kind": "該戰鬥", "text": "そのダメージ計算時のみ"})
        self.assertEqual(failures_on(self.structure, boost), [])


class PowerCodeTalkerTest(unittest.TestCase):
    """パワーコード・トーカー 15844566 ②:性質變更句的期間槽寫得回該戰鬥
    「このカードの攻撃力はそのダメージ計算時のみ、元々の攻撃力の倍になる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(POWER_CODE_TALKER, name_ja="パワーコード・トーカー", type=67108897, level=3,
                  race=16777216, attribute=4, atk=2300, link_marker=41, **{"def": None}),
             faq(POWER_CODE_TALKER, "パワーコード・トーカー", POWER_CODE_TALKER_TEXT)))
        cls.structure = structure_of(cls.structures, POWER_CODE_TALKER)

    def test_doubled_attack_lasts_for_that_battle(self):
        segs = hit_segments(self.structures, self.cards, POWER_CODE_TALKER,
                            actions=["性質變更"])
        self.assertEqual([s["duration"] for s in segs],
                         [{"kind": "該戰鬥", "text": "そのダメージ計算時のみ、"}])
        self.assertEqual(failures_on(self.structure, segs[0]), [])

    def test_battle_condition_passes_reverse_check(self):
        segs = hit_segments(self.structures, self.cards, POWER_CODE_TALKER,
                            actions=["戰鬥"], include_condition=True)
        self.assertEqual([(s["trigger"], failures_on(self.structure, s)) for s in segs],
                         [("ダメージ計算時", [])])


if __name__ == "__main__":
    unittest.main()
