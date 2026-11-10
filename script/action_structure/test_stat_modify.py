"""攻守增減:「Nアップ/ダウンする」併進性質變更,`form` 增/減、`value` 差量或算式字面;
`attr` 多值並擴到等級;主語是任意物件短語(群體、被裝備者);「Nアップの装備カード扱いで」拆成
裝備段加衍生的性質變更段。

走接縫一(查詢判斷)與接縫二(反向檢查)。spec「查詢判斷」只加 `modified` 欄,前提、期間、主語、
`value` 這類條件先用查詢查到命中段,再讀命中段的格(`hit_segments`)。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, SPELL, TRAP, card, faq

SELF = 10000801   # 合成卡(本檔號段 10000801 起)
URBONUS = 47077697   # 呪念の化身ウルボヌス
URBONUS_TEXT = (
    "このカード名の①③の効果はそれぞれ１ターンに１度しか使用できない。①：自分フィールドの"
    "爬虫類族モンスター１体をリリースして発動できる。このカードを手札から特殊召喚する。②：この"
    "カードがモンスターゾーンに存在する限り、相手フィールドのモンスターの攻撃力・守備力は３００"
    "ダウンする。③：自分フィールドのモンスター１体をリリースして発動できる。相手フィールドの全ての"
    "モンスターの攻撃力・守備力はターン終了時まで、リリースしたモンスターの元々の攻撃力分ダウンする。")
CIPHER_SCOUTER = 79853073   # サイファー・スカウター
CIPHER_SCOUTER_TEXT = (
    "このカードが戦士族モンスターと戦闘を行うダメージ計算時に発動する。このカードの攻撃力・"
    "守備力は、そのダメージ計算時のみ２０００ポイントアップする。")
LEARNER_DEVICE = 42149850   # 使い捨て学習装置
LEARNER_DEVICE_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。①：装備モンスターの攻撃力は、"
    "自分の墓地のモンスターの数×２００アップする。②：このカードがフィールドから墓地へ送られた"
    "ターンのエンドフェイズに発動できる。このカードを自分フィールドにセットする。この効果で"
    "セットしたこのカードはフィールドから離れた場合に除外される。")
GAGAGA_GIRL = 3606728   # ガガガガール
GAGAGA_GIRL_TEXT = (
    "①：自分フィールドの「ガガガマジシャン」１体を対象として発動できる。このカードのレベルは"
    "そのモンスターと同じになる。\n②：このカードを含むフィールドの「ガガガ」モンスターのみを"
    "素材としてX召喚したモンスターは以下の効果を得る。\n●このカードがX召喚した時、相手"
    "フィールドの特殊召喚されたモンスター１体を対象として発動できる。そのモンスターの攻撃力を"
    "０にする。")
GAGAGA_MAGICIAN = 26082117   # ガガガマジシャン
METAL_ARMOR = 68540058   # メタル化・魔法反射装甲
METAL_ARMOR_TEXT = (
    "①：フィールドの表側表示モンスター１体を対象としてこのカードを発動できる。このカードを"
    "攻撃力・守備力３００アップの装備カード扱いでそのモンスターに装備する。\n②：このカードの効果で"
    "このカードを装備したモンスターの攻撃力は、モンスターに攻撃するダメージ計算時のみ、その"
    "攻撃対象モンスターの攻撃力の半分だけアップする。")


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


def in_block(structure, seg, label):
    return any(b["label"] == label and seg in b["segments"] for b in structure["blocks"])


class UrbonusTest(unittest.TestCase):
    """呪念の化身ウルボヌス 47077697 ②③:群體主語的攻守同時減少。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(URBONUS, name_ja="呪念の化身ウルボヌス", level=5, race=524288, attribute=32,
                  atk=2000, **{"def": 800}),
             faq(URBONUS, "呪念の化身ウルボヌス", URBONUS_TEXT)))
        cls.structure = structure_of(cls.structures, URBONUS)

    def decreased(self, attr, label):
        segs = hit_segments(self.structures, self.cards, URBONUS, actions=["性質變更"],
                            modified={"attr": attr, "form": "減"})
        return [s for s in segs if in_block(self.structure, s, label)]

    def test_lasting_decrease_hits_attack_and_defense(self):
        self.assertEqual(len(self.decreased("攻擊力", "②")), 1)
        self.assertEqual(len(self.decreased("守備力", "②")), 1)

    def test_lasting_decrease_is_premised_on_kagiri(self):
        seg, = self.decreased("攻擊力", "②")
        self.assertEqual(seg["premise"]["form"], "限り、")
        self.assertEqual(seg["duration"], {"kind": "持續"})

    def test_lasting_decrease_subject_is_the_opponent_field_group(self):
        seg, = self.decreased("攻擊力", "②")
        line, = seg["lines"]
        subject = next(o for o in self.structure["objects"] if o["id"] == line["object"])
        self.assertEqual((subject["source"]["kind"], subject["condition"]),
                         ("新建", {"op": "大類", "value": "怪獸"}))
        self.assertEqual(line["from"]["zones"],
                         [{"zone": "場上", "side": "對手", "side_source": "明寫"}])
        self.assertIsNone(line["ref"])

    def test_released_decrease_lasts_this_turn_with_formula_value(self):
        seg, = self.decreased("守備力", "③")
        self.assertEqual(seg["duration"]["kind"], "本回合")
        self.assertEqual(seg["modified"]["value"],
                         {"kind": "算式", "text": "リリースしたモンスターの元々の攻撃力分"})

    def test_all_monsters_subject_counts_all(self):
        seg, = self.decreased("攻擊力", "③")
        self.assertEqual(seg["lines"][0]["count"], {"text": "全ての", "cmp": "全部"})

    def test_increase_query_does_not_hit(self):
        self.assertEqual(hit_segments(self.structures, self.cards, URBONUS,
                                      actions=["性質變更"], modified={"form": "增"}), [])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure), [])


class CipherScouterTest(unittest.TestCase):
    """サイファー・スカウター 79853073:「攻撃力・守備力は、そのダメージ計算時のみ２０００ポイントアップする」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(CIPHER_SCOUTER, name_ja="サイファー・スカウター", level=3, race=32,
                  attribute=1, atk=1350, setcode=229, **{"def": 1800}),
             faq(CIPHER_SCOUTER, "サイファー・スカウター", CIPHER_SCOUTER_TEXT)))
        cls.structure = structure_of(cls.structures, CIPHER_SCOUTER)

    def increased(self, attr):
        return hit_segments(self.structures, self.cards, CIPHER_SCOUTER, actions=["性質變更"],
                            modified={"attr": attr, "form": "增"})

    def test_attack_increase_hits_and_changes_both_stats(self):
        seg, = self.increased("攻擊力")
        self.assertEqual(seg["modified"]["attr"], ["攻擊力", "守備力"])
        self.assertEqual(self.increased("守備力"), [seg])

    def test_increase_lasts_for_that_battle(self):
        seg, = self.increased("攻擊力")
        self.assertEqual(seg["duration"], {"kind": "該戰鬥", "text": "そのダメージ計算時のみ"})

    def test_old_style_points_keep_the_value(self):
        seg, = self.increased("攻擊力")
        self.assertEqual((seg["modified"]["value"], seg["modified"].get("unit")),
                         (2000, "ポイント"))
        self.assertEqual(len(hit_segments(self.structures, self.cards, CIPHER_SCOUTER,
                                          actions=["性質變更"], modified={"value": 2000})), 1)

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure), [])


class DisposableLearnerDeviceTest(unittest.TestCase):
    """使い捨て学習装置 42149850 ①:「装備モンスターの攻撃力は、〜の数×２００アップする」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(LEARNER_DEVICE, name_ja="使い捨て学習装置", type=262146),
             faq(LEARNER_DEVICE, "使い捨て学習装置", LEARNER_DEVICE_TEXT)))
        cls.structure = structure_of(cls.structures, LEARNER_DEVICE)

    def increased(self):
        return hit_segments(self.structures, self.cards, LEARNER_DEVICE, actions=["性質變更"],
                            modified={"attr": "攻擊力", "form": "增"})

    def test_equipped_monster_attack_increase_hits(self):
        seg, = self.increased()
        self.assertEqual(seg["modified"]["attr"], ["攻擊力"])

    def test_subject_is_the_equipped_monster_of_this_card(self):
        seg, = self.increased()
        subject = next(o for o in self.structure["objects"]
                       if o["id"] == seg["lines"][0]["object"])
        atoms = subject["condition"]["args"]
        self.assertEqual([a["op"] for a in atoms], ["被裝備者", "大類"])
        self.assertEqual(atoms[0]["equip"], "o0")

    def test_value_is_the_formula_literal(self):
        seg, = self.increased()
        self.assertEqual(seg["modified"]["value"],
                         {"kind": "算式", "text": "自分の墓地のモンスターの数×２００"})

    def test_increase_passes_reverse_check(self):
        seg, = self.increased()
        self.assertEqual([f for f in check_card(self.structure) if f["segment"] == seg["id"]], [])

    def test_unwritten_duration_is_not_inferred(self):
        seg, = self.increased()
        self.assertIsNone(seg["duration"])


class LeadingFormulaTest(unittest.TestCase):
    """數值寫在主語前(「その差分×５００だけこのカードの攻撃力はアップする」,
    No.4 猛毒刺胞ステルス・クラーゲン 39321065 等 14 句的寫法):value 是算式字面、記 placement 主語前。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(SELF, name_ja="甲"),
             faq(SELF, "甲", "②：このカードのレベルが元々のレベルより高い場合、その差分×５００だけ"
                             "このカードの攻撃力はアップする。")))
        cls.structure = structure_of(cls.structures, SELF)

    def test_increase_hits_with_the_leading_formula(self):
        seg, = hit_segments(self.structures, self.cards, SELF, actions=["性質變更"],
                            modified={"attr": "攻擊力", "form": "增"})
        self.assertEqual(seg["modified"]["value"],
                         {"kind": "算式", "text": "その差分×５００だけ", "placement": "主語前"})
        self.assertEqual([f for f in check_card(self.structure) if f["segment"] == seg["id"]], [])


class GagagaGirlTest(unittest.TestCase):
    """ガガガガール 3606728 ①:「このカードのレベルはそのモンスターと同じになる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(GAGAGA_GIRL, name_ja="ガガガガール", level=3, race=2, attribute=32,
                  atk=1000, setcode=84, **{"def": 800}),
             faq(GAGAGA_GIRL, "ガガガガール", GAGAGA_GIRL_TEXT)),
            (card(GAGAGA_MAGICIAN, name_ja="ガガガマジシャン", level=4, race=2, attribute=32,
                  atk=1500, setcode=84), None))

    def test_level_change_hits(self):
        seg, = hit_segments(self.structures, self.cards, GAGAGA_GIRL, actions=["性質變更"],
                            modified={"attr": "等級"})
        self.assertEqual(seg["modified"], {"attr": ["等級"], "form": "數值",
                                           "value": {"kind": "算式", "text": "そのモンスターと同じ"}})
        self.assertEqual(seg["lines"][0]["object"], "o0")

    def test_level_change_passes_reverse_check(self):
        seg, = hit_segments(self.structures, self.cards, GAGAGA_GIRL, actions=["性質變更"],
                            modified={"attr": "等級"})
        failures = check_card(structure_of(self.structures, GAGAGA_GIRL))
        self.assertEqual([f for f in failures if f["segment"] == seg["id"]], [])

    def test_damage_query_does_not_hit(self):
        self.assertEqual(hit_segments(self.structures, self.cards, GAGAGA_GIRL,
                                      actions=["性質變更"], modified={"attr": "傷害"}), [])


class MetalReflectArmorTest(unittest.TestCase):
    """メタル化・魔法反射装甲 68540058:①「攻撃力・守備力３００アップの装備カード扱いで〜に装備する」
    拆成裝備段加衍生的性質變更段;②「このカードの効果でこのカードを装備したモンスターの攻撃力は、
    モンスターに攻撃するダメージ計算時のみ、〜の半分だけアップする」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (card(METAL_ARMOR, name_ja="メタル化・魔法反射装甲", type=TRAP, setcode=442),
             faq(METAL_ARMOR, "メタル化・魔法反射装甲", METAL_ARMOR_TEXT)))
        cls.structure = structure_of(cls.structures, METAL_ARMOR)

    def segments(self, label, **query):
        return [s for s in hit_segments(self.structures, self.cards, METAL_ARMOR, **query)
                if in_block(self.structure, s, label)]

    def test_equip_hits_with_the_boost_in_treat(self):
        seg, = self.segments("①", actions=["裝備"])
        self.assertEqual(seg["lines"][0]["to"]["form"]["treat"],
                         {"text": "攻撃力・守備力３００アップの装備カード扱いで", "kind": "裝備卡"})

    def test_boost_derived_from_the_equip_segment_hits(self):
        equip, = self.segments("①", actions=["裝備"])
        boost, = self.segments("①", actions=["性質變更"],
                               modified={"attr": "攻擊力", "form": "增", "value": 300})
        self.assertEqual(boost["derived_from"], equip["id"])
        self.assertEqual(boost["modified"]["attr"], ["攻擊力", "守備力"])
        self.assertEqual(boost["lines"][0]["object"], equip["recipient"]["object"])

    def test_boost_is_joined_with_the_equip_segment(self):
        block = next(b for b in self.structure["blocks"] if b["label"] == "①")
        joins = [n["join"] for n in block["tree"]["items"]]
        self.assertEqual(joins[-1], "同時")

    def test_battle_boost_hits_and_lasts_for_that_battle(self):
        seg, = self.segments("②", actions=["性質變更"],
                             modified={"attr": "攻擊力", "form": "增"})
        self.assertEqual(seg["duration"]["kind"], "該戰鬥")
        self.assertEqual(seg["modified"]["value"],
                         {"kind": "算式", "text": "その攻撃対象モンスターの攻撃力の半分だけ"})

    def test_battle_boost_subject_is_the_monster_this_card_equips(self):
        seg, = self.segments("②", actions=["性質變更"], modified={"attr": "攻擊力"})
        subject = next(o for o in self.structure["objects"]
                       if o["id"] == seg["lines"][0]["object"])
        self.assertEqual(subject["condition"]["args"][0]["op"], "被裝備者")

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure), [])


if __name__ == "__main__":
    unittest.main()
