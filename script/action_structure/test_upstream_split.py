"""上游切分(m2 票 03):「限り」前提、句首期間、略過文本的新原因。

走接縫一(查詢判斷)與接縫二(反向檢查);票上指明「只驗前提剝得掉、段的 duration 有值」
的兩張卡(動作詞留給票 04)另讀段的前提與期間格,因為那兩段的述語本票還解析不出。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import ARCHETYPES, SPELL, card, faq

SELF = 10000101
VANGUARD = 2460565   # 切り込み隊長
VANGUARD_TEXT = (
    "①：このカードが召喚に成功した時に発動できる。手札からレベル４以下のモンスター１体を"
    "特殊召喚する。②：このカードがモンスターゾーンに存在する限り、相手は他の戦士族モンスターを"
    "攻撃対象に選択できない。")
BAHAMUT_SHARK = 440556   # バハムート・シャーク
BAHAMUT_SHARK_TEXT = (
    "水属性レベル４モンスター×２\n①：１ターンに１度、このカードのX素材を１つ取り除いて"
    "発動できる。EXデッキからランク３以下の水属性Xモンスター１体を特殊召喚する。"
    "この効果の発動後、ターン終了時までこのカードは攻撃できない。")
RB_JUMP_NUMBER = 5109321   # R.B.ジャンプ・ナンバー(通常魔法)
RB_JUMP_NUMBER_TEXT = (
    "このカードを発動するターン、自分は元々の攻撃力が１５００以下の機械族モンスターしか"
    "EXデッキから特殊召喚できない。\n①：同名カードが自分フィールドに存在しない「R.B.」"
    "モンスター１体をデッキ・EXデッキから特殊召喚する。\n②：自分フィールドの「R.B.」"
    "モンスターが戦闘・効果で破壊される場合、代わりに墓地のこのカードを除外できる。")
WOLFRAYET = 3322931   # 星風狼ウォルフライエ
WOLFRAYET_TEXT = (
    "チューナー＋チューナー以外のモンスター１体以上\n①：「星風狼ウォルフライエ」は"
    "自分フィールドに１体しか表側表示で存在できない。②：攻撃力４０００未満のこのカードが"
    "モンスターゾーンに存在する限り、このカード以外のモンスターの効果が発動する度に、"
    "このカードの攻撃力は３００アップする。③：１ターンに１度、このカードの攻撃力が"
    "４０００以上の場合に発動できる。このカードと相手フィールドのモンスターを全て"
    "持ち主のデッキに戻す。この効果は相手ターンでも発動できる。")
SUMMON_REACTOR = 89493368   # サモン・リアクター・AI
SUMMON_REACTOR_TEXT = (
    "このカードが自分フィールド上に表側表示で存在する限り、相手フィールド上にモンスターが"
    "召喚・反転召喚・特殊召喚された時、相手ライフに８００ポイントダメージを与える。"
    "この効果は１ターンに１度しか使用できない。この効果を使用したターンのバトルフェイズ時、"
    "相手モンスター１体の攻撃を無効にできる。")
SUMMON_REACTOR_SUPPLEMENT = (
    "■『このカードが自分フィールド上に表側表示で存在する限り、相手フィールド上にモンスターが"
    "召喚・反転召喚・特殊召喚された時、相手ライフに８００ポイントダメージを与える。"
    "この効果は１ターンに１度しか使用できない』モンスター効果は誘発効果です。")
BLACK_MAGICIAN = 46986414


def build(cid, name_ja, text, **kw):
    """一張卡加一張被「」點名用的ブラック・マジシャン;回傳 (卡片總表, 該卡的結構列表)。"""
    cards = [card(cid, name_ja=name_ja, **kw),
             card(BLACK_MAGICIAN, name_ja="ブラック・マジシャン", level=7, race=0x2,
                  attribute=0x20, atk=2500)]
    structures, _ = build_structures(cards, [faq(cid, name_ja, text)],
                                     archetypes=ARCHETYPES)
    return cards, [s for s in structures if s["id"] == cid]


def hits(cards, structures, **query):
    return [h["id"] for h in run_query(structures, cards, query)["hits"]]


def segment_starting(structure, prefix):
    """原文以 prefix 開頭的段(段的範圍從前提起算)。"""
    for block in structure["blocks"]:
        for seg in block["segments"]:
            if block["text"][seg["span"][0]:].startswith(prefix):
                return seg
    raise AssertionError(f"找不到以「{prefix}」開頭的段")


class KagiriPremiseTest(unittest.TestCase):
    """「〜に存在する限り、」剝成前提(form 限り、),段的期間記持續。"""

    def test_vanguard_premise_is_stripped_and_segment_lasts(self):
        """切り込み隊長 ②:前提是此卡的位置原子、form「限り、」,段的期間是持續
        (述語「攻撃対象に選択できない」留給票 04)。"""
        _, structures = build(VANGUARD, "切り込み隊長", VANGUARD_TEXT)
        seg = segment_starting(structures[0], "このカードがモンスターゾーンに存在する限り")
        self.assertEqual(seg["premise"]["op"], "位置")
        self.assertEqual(seg["premise"]["form"], "限り、")
        self.assertEqual(seg["duration"], {"kind": "持續"})
        self.assertFalse(seg["predicate"].startswith("存在"))

    def test_kagiri_premise_segment_hits_and_passes_reverse_check(self):
        """「限り」前提後的效果照常命中(極性不能),整張通過反向檢查。"""
        cards, structures = build(
            SELF, "甲", "①：このカードが墓地に存在する限り、自分は手札からモンスターを"
                        "特殊召喚できない。")
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 polarities=["不能"], from_zones=["手牌"]))
        self.assertEqual(check_card(structures[0]), [])

    def test_kagiri_premise_on_an_action_reference_is_written_back(self):
        """前提的物件是動作回指(「この効果で特殊召喚したモンスターが〜に存在する限り」):
        回指字面記在原子上,反向檢查照它寫回。"""
        _, structures = build(
            SELF, "甲", "①：手札からモンスター１体を特殊召喚する。この効果で特殊召喚した"
                        "モンスターがモンスターゾーンに存在する限り、自分は手札からモンスターを"
                        "特殊召喚できない。")
        self.assertEqual(check_card(structures[0]), [])

    def test_kagiri_without_comma_is_still_a_premise(self):
        """讀點沒寫(「存在する限り自分は」)也剝成前提,模板照原文不寫讀點。"""
        cards, structures = build(
            SELF, "甲", "①：このカードが墓地に存在する限り自分は手札からモンスターを"
                        "特殊召喚できない。")
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 polarities=["不能"]))
        self.assertEqual(check_card(structures[0]), [])

    def test_toki_existence_is_a_premise_not_a_trigger(self):
        """舊式「フィールド上に「X」が存在する時、〜」:「存在する時」是狀態前提,不是條件段;
        後面的效果照常命中,整張通過反向檢查。"""
        cards, structures = build(
            SELF, "甲", "自分フィールド上に「ブラック・マジシャン」が存在する時、"
                        "このカードを破壊する。")
        self.assertIn(SELF, hits(cards, structures, actions=["破壞"]))
        self.assertEqual(check_card(structures[0]), [])


class LeadingDurationTest(unittest.TestCase):
    """句首時間狀語剝成期間,套到同一句後面所有段;字面在第一段,反向檢查原樣寫回。"""

    def test_bahamut_shark_after_activation_until_end_of_turn(self):
        """バハムート・シャーク ③ 句:期間本回合、range 發動後(動作詞攻擊留給票 04)。"""
        _, structures = build(BAHAMUT_SHARK, "バハムート・シャーク", BAHAMUT_SHARK_TEXT,
                              type=0x800021)
        seg = segment_starting(structures[0], "この効果の発動後")
        self.assertEqual(seg["duration"]["kind"], "本回合")
        self.assertEqual(seg["duration"]["range"], "發動後")
        self.assertFalse(seg["predicate"].startswith("ターン"))

    def assert_written_back(self, adverbial, kind, range_):
        cards, structures = build(
            SELF, "甲", f"①：このカードを破壊する。{adverbial}自分は手札からモンスターを"
                        "特殊召喚できない。")
        self.assertIn(SELF, hits(cards, structures, actions=["特殊召喚"],
                                 polarities=["不能"], from_zones=["手牌"]))
        seg = segment_starting(structures[0], adverbial)
        self.assertEqual(seg["duration"]["kind"], kind)
        self.assertEqual(seg["duration"].get("range"), range_)
        self.assertEqual(check_card(structures[0]), [])

    def test_this_turn(self):
        """「このターン、」= 本回合、沒有 range。"""
        self.assert_written_back("このターン、", "本回合", None)

    def test_after_this_effect_is_activated(self):
        """「この効果の発動後、ターン終了時まで」= 本回合、range 發動後。"""
        self.assert_written_back("この効果の発動後、ターン終了時まで", "本回合", "發動後")

    def test_turn_this_effect_is_activated(self):
        """「この効果を発動するターン、」= 本回合、range 整回合。"""
        self.assert_written_back("この効果を発動するターン、", "本回合", "整回合")

    def rb_jump_number(self):
        cards = [card(RB_JUMP_NUMBER, name_ja="R.B.ジャンプ・ナンバー", type=SPELL)]
        structures, _ = build_structures(
            cards, [faq(RB_JUMP_NUMBER, "R.B.ジャンプ・ナンバー", RB_JUMP_NUMBER_TEXT)],
            archetypes=ARCHETYPES)
        return cards, structures

    def test_rb_jump_number_oath_hits_only_from_extra_deck(self):
        """R.B.ジャンプ・ナンバー 的誓約句:「特殊召喚,只能,從額外牌組」命中;
        期間本回合、range 整回合。"""
        cards, structures = self.rb_jump_number()
        self.assertIn(RB_JUMP_NUMBER, hits(cards, structures, actions=["特殊召喚"],
                                           polarities=["只能"],
                                           from_zones=["額外牌組"]))
        seg = segment_starting(structures[0], "このカードを発動するターン、")
        self.assertEqual(seg["duration"]["kind"], "本回合")
        self.assertEqual(seg["duration"]["range"], "整回合")

    def test_rb_jump_number_oath_is_not_a_default_polarity_hit(self):
        """誓約句(卡片發動區塊)查「特殊召喚」預設極性:不命中、也不列未解析組
        (① 的「特殊召喚する」在編號效果區塊,另由區塊種類篩掉)。"""
        cards, structures = self.rb_jump_number()
        result = run_query(structures, cards, {"actions": ["特殊召喚"],
                                               "block_kinds": ["卡片發動"]})
        self.assertNotIn(RB_JUMP_NUMBER, result["groups"]["全部"])
        self.assertNotIn(RB_JUMP_NUMBER, result["groups"]["未解析"])

    def test_duration_applies_to_every_segment_of_the_sentence(self):
        """「このターン、〜し、〜できない」:連用形切開的兩段都帶期間,字面只在第一段。"""
        _, structures = build(
            SELF, "甲", "①：このターン、このカードを手札に戻し、自分は手札からモンスターを"
                        "特殊召喚できない。")
        segs = structures[0]["blocks"][0]["segments"]
        self.assertGreaterEqual(len(segs), 2)
        self.assertTrue(all(s["duration"] and s["duration"]["kind"] == "本回合"
                            for s in segs))
        self.assertEqual(check_card(structures[0]), [])


def omitted_reasons(structure):
    return [(o["text"].rstrip("。"), o["reason"]) for o in structure["omitted"]]


def failing_blocks(structure):
    return {f["block"] for f in check_card(structure)}


class OmittedTextTest(unittest.TestCase):
    """略過文本的新原因:場上唯一、句中的次數限制句;不進動作搜尋,反向檢查扣掉它。"""

    def test_wolfrayet_unique_on_field_is_omitted(self):
        """星風狼ウォルフライエ ①:進略過文本、原因場上唯一;① 區塊沒有段、反向檢查不列它;
        查詢不命中也不列未解析組。"""
        cards, structures = build(WOLFRAYET, "星風狼ウォルフライエ", WOLFRAYET_TEXT,
                                  type=0x2021)
        structure = structures[0]
        self.assertIn(("「星風狼ウォルフライエ」は自分フィールドに１体しか表側表示で存在できない",
                       "場上唯一"), omitted_reasons(structure))
        first = next(b for b in structure["blocks"] if b["label"] == "①")
        self.assertEqual(first["segments"], [])
        self.assertNotIn(first["id"], failing_blocks(structure))
        for action in ("特殊召喚", "破壞", "除外"):
            result = run_query(structures, cards, {
                "actions": [action],
                "polarities": ["做", "不能", "不會", "可以", "只能", "必須"]})
            listed = [s["segment"] for u in result["unparsed"] for s in u["segments"]]
            listed += [s for h in result["hits"] for s in h["segments"]]
            self.assertFalse([s for s in listed if s.startswith(first["id"] + ".")])

    def test_summon_reactor_limit_sentence_inside_a_block_is_omitted(self):
        """サモン・リアクター・AI:補足情報的『』引用讓「この効果は１ターンに１度しか使用
        できない」留在效果區塊裡;句子層把它收進略過文本(原因次數限制),不再是解析不出的段。"""
        entry = faq(SUMMON_REACTOR, "サモン・リアクター・AI", SUMMON_REACTOR_TEXT)
        entry["supplement"] = SUMMON_REACTOR_SUPPLEMENT
        cards = [card(SUMMON_REACTOR, name_ja="サモン・リアクター・AI")]
        structures, _ = build_structures(cards, [entry], archetypes=ARCHETYPES)
        structure = structures[0]
        self.assertIn(("この効果は１ターンに１度しか使用できない", "次數限制"),
                      omitted_reasons(structure))
        texts = [b["text"][s["span"][0]:s["span"][1]]
                 for b in structure["blocks"] for s in b["segments"]]
        self.assertNotIn("この効果は１ターンに１度しか使用できない", texts)
        result = run_query(structures, cards, {
            "actions": ["發動"], "polarities": ["做", "不能", "不會", "可以", "只能", "必須"]})
        listed = [s["text"] for u in result["unparsed"] for s in u["segments"]]
        self.assertNotIn("この効果は１ターンに１度しか使用できない", listed)
        details = [f["detail"] for f in check_card(structure)]
        self.assertFalse([f for f in check_card(structure) if f["reason"] == "段外殘留"])
        self.assertTrue(details)   # 其他段本票還解析不出,只確認略過的那句不殘留


if __name__ == "__main__":
    unittest.main()
