"""小型寫法(m3 票 02):每項只動一處規則或閉集——句尾括號版次數限制、支付的「ライフポイント」、
「〜表示に変更する/〜表示にならない」、觸發形「ダメージステップ時」「戦闘ダメージ計算時」、
抽牌推得的牌組標方、放置與去除的單字幹。

走接縫一(查詢判斷)與接縫二(反向檢查);每項一張真實卡(官方文本逐字寫在測試裡,
`data/sources/` 不入版控),其餘是句子取自真卡的合成卡。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, SPELL, card, faq

SELF = 10002001   # 本檔的合成卡


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def library(text, **kw):
    cards = [card(SELF, name_ja="甲", **kw)]
    return cards, build(cards, [faq(SELF, "甲", text)])


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def omitted(structure):
    return [(o["reason"], o["text"]) for o in structure["omitted"]]


def block_failures(structure, label):
    """反向檢查裡落在編號 `label` 那個區塊的不通過筆。"""
    block_ids = {b["id"] for b in structure["blocks"] if b["label"] == label}
    return [(f["segment"], f["reason"], f["detail"]) for f in check_card(structure)
            if f["block"] in block_ids]


SUBTERROR_GURAIOSU = 1151281   # サブテラーマリス・グライオース
SUBTERROR_GURAIOSU_TEXT = (
    "このカード名の③の効果は１ターンに１度しか使用できない。"
    "①：自分フィールドの表側表示モンスターが裏側表示になった時、"
    "自分フィールドに表側表示モンスターが存在しない場合に発動できる。"
    "このカードを手札から守備表示で特殊召喚する。"
    "②：自分メインフェイズに発動できる。このカードを裏側守備表示にする（１ターンに１度のみ）。"
    "③：このカードがリバースした場合に発動できる。デッキからカード１枚を選んで墓地へ送る。")
NOTE_ONCE = "（１ターンに１度のみ）"
NOTE_EACH_CHOICE = "（このカード名の以下の効果はそれぞれ１ターンに１度しか選択できない）"
NOTE_EACH_USE = "（このカード名の以下の効果はそれぞれ１ターンに１度しか使用できない）"
RANRAN_KENKOU = 25940932   # 絢嵐たる軒昂
RANRAN_KENKOU_TEXT = (
    f"①：以下の効果から１つを選択して発動できる{NOTE_EACH_CHOICE}。\n"
    "●自分の墓地からレベル６以下の「絢嵐」モンスター１体を特殊召喚する。\n"
    "●自分のデッキ・墓地から「サイクロン」１枚を手札に加える。\n"
    "②：このカードが「サイクロン」の効果で破壊された場合に発動できる。"
    "このカードを自分の魔法＆罠ゾーンにセットする。")


class BracketedLimitNoteTest(unittest.TestCase):
    """句尾括號版次數限制:剝成略過文本(原因 次數限制),前面的句子照常解析。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SUBTERROR_GURAIOSU, name_ja="サブテラーマリス・グライオース",
                          type=0x200021, level=8, race=0x40, attribute=0x1, atk=2600,
                          setcode=0x10ed)]
        cls.structures = build(cls.cards, [faq(SUBTERROR_GURAIOSU,
                                               "サブテラーマリス・グライオース",
                                               SUBTERROR_GURAIOSU_TEXT)])

    def test_guraiosu_flip_down_effect_hits_change_position(self):
        """② 的效果段「このカードを裏側守備表示にする」命中變更表示形式(對象是此卡)。"""
        segs = hit_segments(self.structures, self.cards, SUBTERROR_GURAIOSU,
                            actions=["變更表示形式"], card=SUBTERROR_GURAIOSU)
        self.assertEqual([s["text"] for s in segs], ["このカードを裏側守備表示にする"])

    def test_guraiosu_note_is_omitted_and_block_passes_reverse_check(self):
        structure = own(self.structures, SUBTERROR_GURAIOSU)
        self.assertIn(("次數限制", NOTE_ONCE), omitted(structure))
        self.assertEqual(block_failures(structure, "②"), [])

    def test_ranran_kenkou_branch_header_with_note_passes_whole_card(self):
        """絢嵐たる軒昂 25940932:引導句後帶注記,整張通過反向檢查;● 第一支命中「特殊召喚,從墓地」。"""
        cards = [card(RANRAN_KENKOU, name_ja="絢嵐たる軒昂", type=0x10002, setcode=0x1d1),
                 card(5318639, name_ja="サイクロン", type=0x10002)]
        structures, _ = build_structures(
            cards, [faq(RANRAN_KENKOU, "絢嵐たる軒昂", RANRAN_KENKOU_TEXT)],
            archetypes=[{"setcode": 0x1d1, "hex": "0x1d1", "names_ja": ["絢嵐"],
                         "name_zh": "絢嵐", "source": "strings.conf"}])
        structure = own(structures, RANRAN_KENKOU)
        self.assertEqual(omitted(structure), [("次數限制", NOTE_EACH_CHOICE)])
        self.assertEqual(check_card(structure), [])
        segs = hit_segments(structures, cards, RANRAN_KENKOU, actions=["特殊召喚"],
                            from_zones=["墓地"])
        self.assertEqual([s["text"] for s in segs],
                         ["自分の墓地からレベル６以下の「絢嵐」モンスター１体を特殊召喚する"])

    def test_note_after_branch_header_keeps_the_branch_mode(self):
        """引導句後的括號注記:引導句照常認成分歧(選1),整張通過反向檢查。"""
        for note in (NOTE_EACH_CHOICE, NOTE_EACH_USE):
            with self.subTest(note=note):
                _, structures = library(
                    f"①：以下の効果から１つを選択して発動できる{note}。\n"
                    "●このカードを破壊する。\n●このカードを除外する。")
                structure = own(structures, SELF)
                self.assertEqual(omitted(structure), [("次數限制", note)])
                self.assertEqual(check_card(structure), [])

    def test_note_after_premised_branch_header(self):
        cards, structures = library(
            "①：自分・相手のメインフェイズに、以下の効果から１つを選択して発動できる"
            f"{NOTE_EACH_CHOICE}。\n●このカードを破壊する。\n●このカードを除外する。")
        structure = own(structures, SELF)
        self.assertEqual(omitted(structure), [("次數限制", NOTE_EACH_CHOICE)])
        self.assertEqual(check_card(structure), [])
        self.assertEqual(run_query(structures, cards, {"actions": ["破壞"]})["groups"]["全部"],
                         [SELF])

    def test_note_after_activation_sentence(self):
        """「〜時に発動できる（〜に対してそれぞれ１ターンに１度しか発動できない）」:發動句照常切出條件段。"""
        note = ("（このカード名のこの効果は魔法・罠・モンスターの効果に対して"
                "それぞれ１ターンに１度しか発動できない）")
        cards, structures = library(
            f"①：相手がモンスターを特殊召喚した時に発動できる{note}。このカードを破壊する。")
        structure = own(structures, SELF)
        self.assertEqual(omitted(structure), [("次數限制", note)])
        self.assertEqual(check_card(structure), [])
        segs = hit_segments(structures, cards, SELF, actions=["特殊召喚"], kinds=["條件"],
                            include_condition=True)
        self.assertEqual([s["text"] for s in segs], ["相手がモンスターを特殊召喚した時"])

    def test_other_bracketed_notes_are_not_limits(self):
        """不是次數限制的括號注記(「（最大３つまで）」)不剝。"""
        _, structures = library("①：このカードに魔力カウンターを１つ置く（最大３つまで）。")
        self.assertEqual(omitted(own(structures, SELF)), [])


MASTER_GIG = 16191953   # マスター・ジーグ
MASTER_GIG_TEXT = (
    "１０００ライフポイントを払って発動する。自分フィールド上に表側表示で存在するサイキック族モンスターの"
    "数だけ、相手フィールド上に存在するモンスターを破壊する。この効果は１ターンに１度しか使用できない。")


class LifePointPaymentTest(unittest.TestCase):
    """支付的數量單位「ライフポイント」(舊式全寫)= 「LP」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(MASTER_GIG, name_ja="マスター・ジーグ", level=8, race=0x100000,
                          attribute=0x1, atk=2600)]
        cls.structures = build(cls.cards, [faq(MASTER_GIG, "マスター・ジーグ", MASTER_GIG_TEXT)])

    def test_master_gig_pay_hits_the_cost_written_in_full(self):
        seg, = hit_segments(self.structures, self.cards, MASTER_GIG, actions=["支付"])
        self.assertEqual((seg["kind"], seg["text"]), ("代價", "１０００ライフポイントを払って"))
        self.assertEqual((seg["amount"]["value"], seg["amount"]["unit"]), (1000, "ライフポイント"))
        self.assertEqual(seg["lines"], [])

    def test_master_gig_pay_is_not_a_destroy_cost(self):
        segs = hit_segments(self.structures, self.cards, MASTER_GIG, actions=["破壞"],
                            kinds=["代價"])
        self.assertEqual(segs, [])

    def test_master_gig_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, MASTER_GIG)), [])

    def test_unit_written_in_full_and_short_have_the_same_structure(self):
        shapes = []
        for unit in ("LP", "ライフポイント"):
            cards, structures = library(f"①：５００{unit}を払って発動できる。このカードを破壊する。")
            seg, = hit_segments(structures, cards, SELF, actions=["支付"])
            self.assertEqual(check_card(own(structures, SELF)), [])
            self.assertEqual(seg["amount"]["unit"], unit)
            shapes.append({k: v for k, v in seg.items() if k not in ("span", "text", "amount")}
                          | {"value": seg["amount"]["value"]})
        self.assertEqual(shapes[0], shapes[1])

    def test_formula_amount_stays_unparsed(self):
        """「１００の倍數のライフポイントを払って」是算式,這輪不收:不命中、列進未解析組。"""
        cards, structures = library(
            "①：１００の倍数のライフポイントを払って発動できる。このカードを破壊する。")
        result = run_query(structures, cards, {"actions": ["支付"]})
        self.assertEqual((result["groups"]["全部"], result["groups"]["未解析"]), ([], [SELF]))


WIND_UP_RAT = 57962537   # ゼンマイネズミ
WIND_UP_RAT_TEXT = (
    "自分のメインフェイズ時に発動できる。自分フィールド上に表側攻撃表示で存在するこのカードを"
    "表側守備表示に変更し、自分の墓地の「ゼンマイ」と名のついたモンスター１体を選択して"
    "表側守備表示で特殊召喚する。この効果はこのカードがフィールド上に表側表示で存在する限り"
    "１度しか使用できない。")
GUILLOTINE = 35686187    # 断頭台の惨劇
GUILLOTINE_TEXT = (
    "相手フィールド上に表側攻撃表示で存在するモンスターの表示形式が表側守備表示に変更された時に"
    "発動できる。相手フィールド上に守備表示で存在するモンスターを全て破壊する。")


class ChangePositionFormsTest(unittest.TestCase):
    """變更表示形式的寫法「〜表示に変更する」「〜表示にならない」;表示形式字面留在原述語字面。"""

    def test_wind_up_rat_changes_itself_to_defense(self):
        cards = [card(WIND_UP_RAT, name_ja="ゼンマイネズミ", level=3, race=0x4000,
                      attribute=0x1, atk=600, setcode=0x58)]
        structures = build(cards, [faq(WIND_UP_RAT, "ゼンマイネズミ", WIND_UP_RAT_TEXT)])
        seg, = hit_segments(structures, cards, WIND_UP_RAT, actions=["變更表示形式"],
                            card=WIND_UP_RAT)
        self.assertEqual(seg["text"],
                         "自分フィールド上に表側攻撃表示で存在するこのカードを表側守備表示に変更し")
        self.assertEqual(hit_segments(structures, cards, WIND_UP_RAT, actions=["變更表示形式"],
                                      polarities=["不能"]), [])
        failures = [f for f in check_card(own(structures, WIND_UP_RAT))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])

    def test_guillotine_position_changed_condition(self):
        """「Xの表示形式が表側守備表示に変更された時」:條件段命中變更表示形式(被動),整張通過。"""
        cards = [card(GUILLOTINE, name_ja="断頭台の惨劇", type=0x4)]
        structures = build(cards, [faq(GUILLOTINE, "断頭台の惨劇", GUILLOTINE_TEXT)])
        seg, = hit_segments(structures, cards, GUILLOTINE, actions=["變更表示形式"],
                            kinds=["條件"], include_condition=True)
        self.assertEqual((seg["voice"], seg["trigger"]), ("被動", "時"))
        self.assertEqual(hit_segments(structures, cards, GUILLOTINE, actions=["變更表示形式"]), [])
        self.assertEqual(check_card(own(structures, GUILLOTINE)), [])

    def test_position_written_as_object_of_change(self):
        cards, structures = library("①：このカードの表示形式を表側攻撃表示に変更する。")
        seg, = hit_segments(structures, cards, SELF, actions=["變更表示形式"], card=SELF)
        self.assertEqual(seg["predicate"], "表示形式を表側攻撃表示に変更する")
        self.assertEqual(check_card(own(structures, SELF)), [])

    def test_does_not_become_defense_position(self):
        """「Xは守備表示にならない」:極性不會,預設(只算做)不命中。"""
        cards, structures = library("①：このカードは守備表示にならない。")
        seg, = hit_segments(structures, cards, SELF, actions=["變更表示形式"],
                            polarities=["不會"])
        self.assertEqual(seg["predicate"], "守備表示にならない")
        self.assertEqual(hit_segments(structures, cards, SELF, actions=["變更表示形式"]), [])
        self.assertEqual(check_card(own(structures, SELF)), [])


if __name__ == "__main__":
    unittest.main()
