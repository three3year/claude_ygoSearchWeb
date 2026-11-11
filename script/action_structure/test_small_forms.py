"""小型寫法:每項只動一處規則或閉集——句尾括號版次數限制、支付的「ライフポイント」、
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
        """查「支付」命中代價段(只看效果段就不命中);這一段沒有物件,指定卡代入不命中。
        數量「１０００ライフポイント」由數量格寫回(整張通過反向檢查,見下)。"""
        segs = hit_segments(self.structures, self.cards, MASTER_GIG, actions=["支付"],
                            kinds=["代價"])
        self.assertEqual([seg["text"] for seg in segs], ["１０００ライフポイントを払って"])
        self.assertEqual(hit_segments(self.structures, self.cards, MASTER_GIG, actions=["支付"],
                                      kinds=["效果"]), [])
        self.assertEqual(hit_segments(self.structures, self.cards, MASTER_GIG, actions=["支付"],
                                      card=MASTER_GIG), [])

    def test_master_gig_pay_is_not_a_destroy_cost(self):
        segs = hit_segments(self.structures, self.cards, MASTER_GIG, actions=["破壞"],
                            kinds=["代價"])
        self.assertEqual(segs, [])

    def test_master_gig_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, MASTER_GIG)), [])

    def test_unit_written_in_full_and_short_read_the_same(self):
        """單位寫「LP」或「ライフポイント」:同樣命中支付的代價段,整張都寫回原文(單位照字面)。"""
        for unit in ("LP", "ライフポイント"):
            with self.subTest(unit=unit):
                cards, structures = library(
                    f"①：５００{unit}を払って発動できる。このカードを破壊する。")
                segs = hit_segments(structures, cards, SELF, actions=["支付"], kinds=["代價"])
                self.assertEqual([seg["text"] for seg in segs], [f"５００{unit}を払って"])
                self.assertEqual(check_card(own(structures, SELF)), [])

    def test_formula_amount_stays_unparsed(self):
        """「１００の倍數のライフポイントを払って」是算式,不收:不命中、列進未解析組。"""
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
        self.assertEqual(seg["text"], "相手フィールド上に表側攻撃表示で存在するモンスターの表示形式が"
                                      "表側守備表示に変更された時")
        self.assertEqual(hit_segments(structures, cards, GUILLOTINE, actions=["變更表示形式"]), [])
        self.assertEqual(check_card(own(structures, GUILLOTINE)), [])

    def test_position_written_as_object_of_change(self):
        cards, structures = library("①：このカードの表示形式を表側攻撃表示に変更する。")
        seg, = hit_segments(structures, cards, SELF, actions=["變更表示形式"], card=SELF)
        self.assertEqual(seg["text"], "このカードの表示形式を表側攻撃表示に変更する")
        self.assertEqual(check_card(own(structures, SELF)), [])

    def test_does_not_become_defense_position(self):
        """「Xは守備表示にならない」:極性不會,預設(只算做)不命中。"""
        cards, structures = library("①：このカードは守備表示にならない。")
        seg, = hit_segments(structures, cards, SELF, actions=["變更表示形式"],
                            polarities=["不會"])
        self.assertEqual(seg["text"], "このカードは守備表示にならない")
        self.assertEqual(hit_segments(structures, cards, SELF, actions=["變更表示形式"]), [])
        self.assertEqual(check_card(own(structures, SELF)), [])


SHIELD_WARRIOR = 95360850   # シールド・ウォリアー
SHIELD_WARRIOR_TEXT = (
    "戦闘ダメージ計算時、自分の墓地に存在するこのカードをゲームから除外して発動する事ができる。"
    "自分フィールド上に存在するモンスターはその戦闘では破壊されない。")
LAVALVAL_IGNIS = 3989465    # ラヴァルバル・イグニス
LAVALVAL_IGNIS_TEXT = (
    "レベル３モンスター×２\n"
    "このカードが戦闘を行うダメージステップ時に１度だけ、このカードのエクシーズ素材を１つ取り除いて"
    "発動できる。このカードの攻撃力はエンドフェイズ時まで５００ポイントアップする。")


class DamageStepTriggerTest(unittest.TestCase):
    """觸發形閉集的「ダメージステップ時」「戦闘ダメージ計算時」(與「ダメージ計算時」同一種戰鬥時點)。"""

    def conditions(self, cards, structures, cid, **query):
        """命中的條件段的原文(條件段的範圍到觸發形為止;解析不出的段不會命中)。"""
        return [s["text"] for s in hit_segments(
            structures, cards, cid, kinds=["條件"], include_condition=True, **query)]

    def test_shield_warrior_battle_damage_calculation_timing(self):
        """「戦闘ダメージ計算時、〜て発動する事ができる」:時點是沒有動作詞的條件段,整張通過;
        代價段命中「除外,從墓地」且對象是此卡。"""
        cards = [card(SHIELD_WARRIOR, name_ja="シールド・ウォリアー", level=3, race=0x1,
                      attribute=0x1, atk=800)]
        structures = build(cards, [faq(SHIELD_WARRIOR, "シールド・ウォリアー",
                                       SHIELD_WARRIOR_TEXT)])
        self.assertEqual(self.conditions(cards, structures, SHIELD_WARRIOR),
                         ["戦闘ダメージ計算時"])
        self.assertEqual(check_card(own(structures, SHIELD_WARRIOR)), [])
        banish = dict(actions=["除外"], from_zones=["墓地"], card=SHIELD_WARRIOR)
        self.assertEqual(
            [s["text"] for s in hit_segments(structures, cards, SHIELD_WARRIOR, kinds=["代價"],
                                             **banish)],
            ["自分の墓地に存在するこのカードをゲームから除外して"])
        self.assertEqual(hit_segments(structures, cards, SHIELD_WARRIOR, kinds=["效果"],
                                      **banish), [])

    def test_lavalval_ignis_battles_at_damage_step(self):
        """「このカードが戦闘を行うダメージステップ時に」:條件段命中戰鬥(施事是此卡)——觸發形是整個時點
        字面,子句「このカードが戦闘を行う」才解析得出;這一段寫回原文相符。"""
        cards = [card(LAVALVAL_IGNIS, name_ja="ラヴァルバル・イグニス", type=0x800021, level=3,
                      race=0x1, attribute=0x4, atk=1800, setcode=0x39)]
        structures = build(cards, [faq(LAVALVAL_IGNIS, "ラヴァルバル・イグニス",
                                       LAVALVAL_IGNIS_TEXT)])
        seg, = hit_segments(structures, cards, LAVALVAL_IGNIS, actions=["戰鬥"],
                            card=LAVALVAL_IGNIS, kinds=["條件"], include_condition=True)
        self.assertEqual(seg["text"], "このカードが戦闘を行うダメージステップ時")
        self.assertEqual(hit_segments(structures, cards, LAVALVAL_IGNIS, actions=["戰鬥"]), [])
        failures = [f for f in check_card(own(structures, LAVALVAL_IGNIS))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])

    def test_damage_step_timing_after_a_condition(self):
        """「〜する場合、ダメージステップ時に発動する事ができる」:時點另成一個條件段。"""
        cards, structures = library(
            "①：このカードが破壊された場合、ダメージステップ時に発動する事ができる。"
            "このカードを除外する。")
        self.assertEqual(self.conditions(cards, structures, SELF),
                         ["このカードが破壊された場合", "ダメージステップ時"])
        self.assertEqual(check_card(own(structures, SELF)), [])

    def test_damage_step_start_and_end_are_still_their_own_triggers(self):
        for trigger in ("ダメージステップ開始時", "ダメージステップ終了時", "ダメージ計算時"):
            with self.subTest(trigger=trigger):
                cards, structures = library(
                    f"①：このカードが戦闘を行う{trigger}に発動できる。このカードを破壊する。")
                self.assertEqual(
                    self.conditions(cards, structures, SELF, actions=["戰鬥"], card=SELF),
                    [f"このカードが戦闘を行う{trigger}"])
                self.assertEqual(check_card(own(structures, SELF)), [])


DARK_BRIBE = 77538567       # 魔宮の賄賂
DARK_BRIBE_TEXT = ("①：相手が魔法・罠カードを発動した時に発動できる。その発動を無効にし破壊する。"
                   "相手は１枚ドローする。")
SCRAP_SQUALL = 48445393     # スクラップ・スコール
SCRAP_SQUALL_TEXT = (
    "自分フィールド上に表側表示で存在する「スクラップ」と名のついたモンスター１体を選択して発動する。"
    "自分のデッキから「スクラップ」と名のついたモンスター１体を墓地へ送り、カードを１枚ドローする。"
    "その後、選択したモンスターを破壊する。")
MINE, THEIRS = {"zone": "牌組", "side": "我方"}, {"zone": "牌組", "side": "對手"}


class InferredDeckSideTest(unittest.TestCase):
    """抽牌沒寫「デッキから」、牌組由推得表補上時,牌組的方照抽牌者標;抽牌者沒寫的記我方。"""

    def draws_from(self, cards, structures, cid, deck, **query):
        return [s["text"] for s in hit_segments(structures, cards, cid, actions=["抽牌"],
                                                from_zones=[deck], **query)]

    def test_dark_bribe_opponent_draws_from_their_deck(self):
        cards = [card(DARK_BRIBE, name_ja="魔宮の賄賂", type=0x100004)]
        structures = build(cards, [faq(DARK_BRIBE, "魔宮の賄賂", DARK_BRIBE_TEXT)])
        self.assertEqual(self.draws_from(cards, structures, DARK_BRIBE, THEIRS,
                                         include_inferred=True), ["相手は１枚ドローする"])
        self.assertEqual(self.draws_from(cards, structures, DARK_BRIBE, MINE,
                                         include_inferred=True), [])
        self.assertEqual(self.draws_from(cards, structures, DARK_BRIBE, THEIRS), [])
        self.assertEqual(check_card(own(structures, DARK_BRIBE)), [])

    def test_scrap_squall_unwritten_drawer_draws_from_my_deck(self):
        cards = [card(SCRAP_SQUALL, name_ja="スクラップ・スコール", type=0x10002, setcode=0x24)]
        structures, _ = build_structures(
            cards, [faq(SCRAP_SQUALL, "スクラップ・スコール", SCRAP_SQUALL_TEXT)],
            archetypes=[{"setcode": 0x24, "hex": "0x24", "names_ja": ["スクラップ"],
                         "name_zh": "廢鐵", "source": "strings.conf"}])
        self.assertEqual(self.draws_from(cards, structures, SCRAP_SQUALL, MINE,
                                         include_inferred=True), ["カードを１枚ドローする"])
        self.assertEqual(self.draws_from(cards, structures, SCRAP_SQUALL, THEIRS,
                                         include_inferred=True), [])
        self.assertEqual(self.draws_from(cards, structures, SCRAP_SQUALL, MINE), [])
        self.assertEqual(check_card(own(structures, SCRAP_SQUALL)), [])

    def test_each_drawer_side(self):
        both = {"zone": "牌組", "side": "雙方各自"}
        for text, hit, miss in (
                ("①：自分は２枚ドローする。", [MINE], [THEIRS, both]),
                ("①：相手プレイヤーはカードを１枚ドローする。", [THEIRS], [MINE, both]),
                ("①：お互いはそれぞれ１枚ドローする。", [both], [MINE, THEIRS])):
            cards, structures = library(text)
            self.assertEqual(check_card(own(structures, SELF)), [])
            for deck in hit + miss:
                with self.subTest(text=text, deck=deck):
                    found = self.draws_from(cards, structures, SELF, deck, include_inferred=True)
                    self.assertEqual(bool(found), deck in hit)

    def test_drawing_this_card_condition(self):
        """「相手がこのカードをドローした時」(簡單子句,物件是此卡):推得的牌組同樣照抽牌者標。"""
        for text, deck in (("①：このカードをドローした時に発動できる。このカードを破壊する。", MINE),
                           ("①：相手がこのカードをドローした時に発動できる。このカードを破壊する。",
                            THEIRS)):
            with self.subTest(text=text):
                cards, structures = library(text)
                hits = {d["side"]: bool(self.draws_from(
                    cards, structures, SELF, d, include_inferred=True, kinds=["條件"],
                    include_condition=True)) for d in (MINE, THEIRS)}
                self.assertEqual(hits, {d["side"]: d == deck for d in (MINE, THEIRS)})
                self.assertEqual(check_card(own(structures, SELF)), [])


CRYSTAL_BRILLIANCE = 47149093   # 宝玉の玲瓏
CRYSTAL_BRILLIANCE_TEXT = (
    "①：「宝玉の玲瓏」は自分フィールドに１枚しか表側表示で存在できない。"
    "②：自分フィールドの「宝玉獣」モンスターの攻撃力は、その元々の守備力分アップする。"
    "③：自分の魔法＆罠ゾーンに「宝玉獣」カードが置かれた場合、魔法＆罠ゾーンの表側表示のこのカードを"
    "墓地へ送って発動できる（ダメージステップでも発動可能）。自分の手札・墓地から「宝玉獣」モンスター"
    "１体を選んで特殊召喚する。このターン、自分が受ける全てのダメージは半分になる。")
CRYSTAL_CORE = 22790789         # 巨大戦艦 クリスタル・コア
CRYSTAL_CORE_TEXT = (
    "①：このカードが召喚した場合に発動する。このカードにカウンターを３つ置く。\n"
    "②：このカードは戦闘では破壊されない。\n"
    "③：１ターンに１度、相手フィールドの表側攻撃表示モンスター１体を対象として発動できる。"
    "その相手の表側攻撃表示モンスターを表側守備表示にする。\n"
    "④：このカードが戦闘を行ったダメージステップ終了時に発動する。"
    "このカードのカウンターを１つ取り除く。取り除けない場合、このカードを破壊する。")
CRYSTAL_BEASTS = [{"setcode": 0x1034, "hex": "0x1034", "names_ja": ["宝玉獣"],
                   "name_zh": "寶玉獸", "source": "strings.conf"}]


class PlaceAndRemoveStemTest(unittest.TestCase):
    """放置、去除是單字幹(置、取り除)加カ行的語尾;被動「置かれた」解析得出(「取り除けない」
    m3b 票 07 起不收);字幹假朋友(位置、装置、置換)不算放置的字面。"""

    def test_crystal_brilliance_card_placed_in_spell_trap_zone(self):
        """③「自分の魔法＆罠ゾーンに「宝玉獣」カードが置かれた場合」:條件段命中「放置,到我方魔陷區」(被動)。"""
        cards = [card(CRYSTAL_BRILLIANCE, name_ja="宝玉の玲瓏", type=0x20004, setcode=0x34),
                 card(7093411, name_ja="宝玉獣 サファイア・ペガサス", setcode=0x1034)]
        structures, _ = build_structures(
            cards, [faq(CRYSTAL_BRILLIANCE, "宝玉の玲瓏", CRYSTAL_BRILLIANCE_TEXT)],
            archetypes=CRYSTAL_BEASTS)
        placed = dict(actions=["放置"], to_zones=[{"zone": "魔陷區", "side": "我方"}],
                      kinds=["條件"], include_condition=True)
        seg, = hit_segments(structures, cards, CRYSTAL_BRILLIANCE, card=7093411, **placed)
        self.assertEqual(seg["text"], "自分の魔法＆罠ゾーンに「宝玉獣」カードが置かれた場合")
        self.assertEqual(hit_segments(structures, cards, CRYSTAL_BRILLIANCE,
                                      card=CRYSTAL_BRILLIANCE, **placed), [])
        self.assertEqual(hit_segments(structures, cards, CRYSTAL_BRILLIANCE, actions=["放置"]), [])
        failures = [f for f in check_card(own(structures, CRYSTAL_BRILLIANCE))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])

    def test_crystal_core_cannot_remove_condition(self):
        """④「取り除けない場合、このカードを破壊する」:m3b 票 07 起「けない」不在語尾表,
        條件段不命中去除(極性 不能);前一句的去除照舊命中。"""
        cards = [card(CRYSTAL_CORE, name_ja="巨大戦艦 クリスタル・コア", level=5, race=0x20,
                      attribute=0x2, atk=2100, setcode=0x15)]
        structures = build(cards, [faq(CRYSTAL_CORE, "巨大戦艦 クリスタル・コア",
                                       CRYSTAL_CORE_TEXT)])
        self.assertEqual(hit_segments(structures, cards, CRYSTAL_CORE, actions=["去除"],
                                      polarities=["不能"], kinds=["條件"],
                                      include_condition=True), [])
        removes = hit_segments(structures, cards, CRYSTAL_CORE, actions=["去除"],
                               include_condition=True, kinds=["條件", "效果"])
        self.assertEqual([s["text"] for s in removes], ["このカードのカウンターを１つ取り除く"])

    def test_existing_forms_keep_their_reading(self):
        """各語尾(終止、可能、連用、て形、被動)照舊命中那個動作詞的段,整張寫回原文相符
        (述語字面拆得回動作詞與態才寫得回)。"""
        for text, action, clause in (
                ("①：このカードを自分の魔法＆罠ゾーンに表側表示で置く。", "放置",
                 "このカードを自分の魔法＆罠ゾーンに表側表示で置く"),
                ("①：このカードを自分の魔法＆罠ゾーンに表側表示で置く事ができる。", "放置",
                 "このカードを自分の魔法＆罠ゾーンに表側表示で置く事ができる"),
                ("①：このカードを自分の魔法＆罠ゾーンに表側表示で置き、手札を１枚捨てる。", "放置",
                 "このカードを自分の魔法＆罠ゾーンに表側表示で置き"),
                ("①：このカードを自分の魔法＆罠ゾーンに置いて発動できる。手札を１枚捨てる。", "放置",
                 "このカードを自分の魔法＆罠ゾーンに置いて"),
                ("①：自分の魔法＆罠ゾーンにカードが置かれた場合に発動できる。手札を１枚捨てる。",
                 "放置", "自分の魔法＆罠ゾーンにカードが置かれた場合"),
                ("①：このカードのX素材を１つ取り除く。", "去除", "このカードのX素材を１つ取り除く"),
                ("①：このカードのX素材を１つ取り除いて発動できる。手札を１枚捨てる。", "去除",
                 "このカードのX素材を１つ取り除いて"),
                ("①：このカードのX素材が全て取り除かれた場合に発動できる。手札を１枚捨てる。",
                 "去除", "このカードのX素材が全て取り除かれた場合")):
            with self.subTest(text=text):
                cards, structures = library(text)
                seg, = hit_segments(structures, cards, SELF, actions=[action],
                                    include_condition=True, kinds=["條件", "代價", "效果"])
                self.assertEqual(seg["text"], clause)
                self.assertEqual(check_card(own(structures, SELF)), [])

    def unparsed_group(self, text, action):
        cards, structures = library(text)
        result = run_query(structures, cards, {"actions": [action], "include_condition": True})
        self.assertEqual(result["groups"]["全部"], [])
        return result["groups"]["未解析"]

    def test_false_friends_are_not_place_literals(self):
        """解析不出的段只含「位置」「装置」「置換」:不列進放置的未解析組。"""
        for text in ("①：このカードの位置を、他の自分のメインモンスターゾーンに移動する。",
                     "①：「強制脱出装置」のカード名が記されたカードを確認する。",
                     "①：「置換融合」のカード名が記されたカードを確認する。"):
            with self.subTest(text=text):
                self.assertEqual(self.unparsed_group(text, "放置"), [])

    def test_unparsed_place_and_remove_forms_are_listed(self):
        """字面真的是放置、去除(沒收的語尾)而段解析不出:照樣列進未解析組。"""
        self.assertEqual(self.unparsed_group(
            "①：魔力カウンターが置かれているこのカードは直接攻撃できる。", "放置"), [SELF])
        self.assertEqual(self.unparsed_group(
            "①：このカードのX素材を取り除かずに発動する事もできる。", "去除"), [SELF])


if __name__ == "__main__":
    unittest.main()
