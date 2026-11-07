"""spec 故事 28「重複到停為止」(未結構化)與名稱表的「宣言」來源:真實卡與合成卡。

官方 DB 文本逐字寫在測試裡(`data/sources/` 不入版控)。斷言寫在查詢層、反向檢查與報告上。
"""
import unittest

from action_query import run_query
from card_structure import build_structures, load_structures, serialize_structures
from coverage_report import build_coverage, render_coverage
from reverse_check import check_card, check_structures, render_report
from test_golden import TRAP, card, faq

VOLTESTER = 18585765  # ボルテスター:「さらに「〜」処理を繰り返す。」
VOLTESTER_TEXT = (
    "このカード名の効果は１ターンに１度しか使用できない。①：このカードがリンクモンスターの"
    "リンク先に特殊召喚された場合に発動する。このカードとリンク状態になっているリンクモンスターを"
    "全て破壊する。さらに「破壊したリンクモンスターのリンク先のモンスターも全て破壊する」処理を"
    "繰り返す。（この効果でこのカードは破壊されない。）")
BERSERKER_SOUL = 15381252  # 狂戦士の魂:「その後、〜までこの効果を（最大で７回）繰り返す。」
BERSERKER_SOUL_TEXT = (
    "「狂戦士の魂」は１ターンに１枚しか発動できない。①：自分フィールドのモンスターが直接攻撃で"
    "相手に１５００以下のダメージを与えた時、手札を全て捨てて発動できる。自分のデッキの一番上の"
    "カードをめくり、それがモンスターだった場合、そのモンスターを墓地へ送り、相手に５００ダメージを"
    "与える。その後、モンスター以外がめくられるまでこの効果を（最大で７回）繰り返す。めくったカードが"
    "モンスター以外だった場合、そのカードをデッキの一番上に戻す。")
CLASHING_SOULS = 57496978  # ぶつかり合う魂:「その後、お互いがLPを払わなくなるまでこの効果を繰り返す。」
CLASHING_SOULS_TEXT = (
    "①：自分の攻撃表示モンスターが自身の攻撃力より高い攻撃力を持つ相手の攻撃表示モンスターと"
    "戦闘を行うダメージ計算時に発動できる。その戦闘を行うモンスターの内、攻撃力が低いモンスターの"
    "コントローラーは、５００LPを払ってそのモンスターの攻撃力をダメージ計算時のみ５００アップできる。"
    "その後、お互いがLPを払わなくなるまでこの効果を繰り返す。その戦闘で発生するお互いの戦闘ダメージは"
    "０になり、ダメージ計算後にその戦闘でモンスターが破壊されたプレイヤーのフィールドのカードは全て"
    "墓地へ送られる。")
SPIKE_HEAD = 87511987  # スパイク・ヘッド(通常怪獸):故事文「攻撃を繰り返す」不是效果
SPIKE_HEAD_TEXT = "地獄の魔術師が生み出した機械兵。両腕の鉄球で敵味方関係なしに攻撃を繰り返す。"
SYNTHETIC = 99  # 合成卡:第一句解析得出、第二句是重複到停為止,裡面的動作詞只在「」裡
SYNTHETIC_TEXT = "①：このカードを破壊する。「相手の手札を１枚除外する」処理を繰り返す。"

UNSTRUCTURED = ("未結構化", "重複到停為止")


class RepeatUntilStopTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(VOLTESTER, name_ja="ボルテスター", level=7, race=0x1000, attribute=0x20,
                 atk=2500),
            card(BERSERKER_SOUL, name_ja="狂戦士の魂", type=0x10002),
            card(CLASHING_SOULS, name_ja="ぶつかり合う魂", type=0x10002),
            card(SPIKE_HEAD, name_ja="スパイク・ヘッド", type=0x11, level=4, race=0x20,
                 attribute=0x1, atk=1800),
            card(SYNTHETIC, name_ja="甲"),
        ]
        cls.structures, _ = build_structures(cls.cards, [
            faq(VOLTESTER, "ボルテスター", VOLTESTER_TEXT),
            faq(BERSERKER_SOUL, "狂戦士の魂", BERSERKER_SOUL_TEXT),
            faq(CLASHING_SOULS, "ぶつかり合う魂", CLASHING_SOULS_TEXT),
            faq(SPIKE_HEAD, "スパイク・ヘッド", SPIKE_HEAD_TEXT),
            faq(SYNTHETIC, "甲", SYNTHETIC_TEXT),
        ])

    def structure(self, cid):
        return next(c for c in self.structures if c["id"] == cid)

    def failures(self, cid):
        return [(f["reason"], f["detail"]) for f in check_card(self.structure(cid))]

    def test_real_cards_record_exactly_one_unstructured_segment_and_no_residue(self):
        """三張真實卡:繰り返す 那一句記「未結構化」各一次、不是字面不符、也沒變成段外殘留;
        其他句子照常(解析不出的仍列無模板)。"""
        for cid, sentence in ((VOLTESTER, "処理を繰り返す"),
                              (BERSERKER_SOUL, "（最大で７回）繰り返す"),
                              (CLASHING_SOULS, "この効果を繰り返す")):
            with self.subTest(card=cid):
                failures = check_card(self.structure(cid))
                unstructured = [f for f in failures if f["reason"] == "未結構化"]
                self.assertEqual(len(unstructured), 1)
                self.assertEqual(unstructured[0]["detail"], "重複到停為止")
                self.assertIn(sentence, unstructured[0]["original"])
                self.assertEqual([f for f in failures
                                  if f["reason"] in ("字面不符", "段外殘留")], [])

    def test_flavor_text_is_not_a_repeat(self):
        """通常怪獸的故事文「攻撃を繰り返す」沒有「処理を/この効果を」:不是重複到停為止。"""
        self.assertNotIn(UNSTRUCTURED, self.failures(SPIKE_HEAD))

    def test_unstructured_sentence_neither_hits_nor_goes_to_unparsed_group(self):
        """合成卡:第一句「このカードを破壊する」照常命中;「」裡的「除外」只在重複句裡,
        查「除外」不命中、也不列未解析組(未結構化不是解析不出);空查詢也不把它當命中段。"""
        destroy = run_query(self.structures, self.cards, {"actions": ["破壞"], "card": SYNTHETIC})
        self.assertIn(SYNTHETIC, destroy["groups"]["全部"])
        banish = run_query(self.structures, self.cards, {"actions": ["除外"], "card": SYNTHETIC})
        self.assertNotIn(SYNTHETIC, banish["groups"]["全部"])
        self.assertNotIn(SYNTHETIC, banish["groups"]["未解析"])
        everything = run_query(self.structures, self.cards, {"actions": []})
        hit = next(h for h in everything["hits"] if h["id"] == SYNTHETIC)
        self.assertEqual(len(hit["segments"]), 1)
        self.assertEqual(self.failures(SYNTHETIC), [UNSTRUCTURED])

    def test_reverse_check_report_counts_unstructured_separately(self):
        """全庫報告:未結構化另列一類,通過與不通過都不含它。"""
        report = check_structures(self.structures)
        self.assertEqual(report["unstructured"], 4)
        self.assertEqual(report["passed"] + report["failed"] + report["unstructured"],
                         report["segments"])
        md = render_report(report)
        self.assertIn("| 未結構化(不計) | 4 |", md)
        self.assertIn("### 未結構化(4 段 / 4 張)", md)
        self.assertIn(f"- 重複到停為止(4 段 / 4 張):{SYNTHETIC}, {BERSERKER_SOUL}, "
                      f"{VOLTESTER}, {CLASHING_SOULS}", md)

    def test_coverage_report_counts_unstructured_separately(self):
        """覆蓋報告:段的總數 = 解析出 + 解析不出 + 未結構化,未結構化附卡號。"""
        cov = build_coverage(self.structures)
        segments = cov["segments"]
        self.assertEqual(segments["unstructured"], 4)
        self.assertEqual(segments["parsed"] + segments["unparsed"] + segments["unstructured"],
                         segments["total"])
        self.assertEqual(segments["unstructured_cards"],
                         [SYNTHETIC, BERSERKER_SOUL, VOLTESTER, CLASHING_SOULS])
        self.assertEqual(segments["by_kind"]["效果"]["unstructured"], 4)
        md = render_coverage(cov)
        self.assertIn("### 未結構化的段(重複到停為止,4 段 / 4 張)", md)
        self.assertIn(f"- `{CLASHING_SOULS}`", md)

    def test_round_trip_keeps_the_unstructured_mark(self):
        loaded = load_structures(serialize_structures(self.structures))
        self.assertEqual(loaded, self.structures)
        self.assertEqual(serialize_structures(loaded), serialize_structures(self.structures))


DEMON_DECLARATION = 22796548  # デーモンの宣告:「カード名を１つ宣言して発動できる」
DEMON_DECLARATION_TEXT = (
    "①：１ターンに１度、５００LPを払い、カード名を１つ宣言して発動できる。自分のデッキの一番上の"
    "カードをめくり、宣言したカードだった場合、そのカードを手札に加える。違った場合、めくったカードを"
    "墓地へ送る。")
MIND_CRUSH = 15800838  # マインドクラッシュ
MIND_CRUSH_TEXT = (
    "①：カード名を１つ宣言して発動できる。宣言したカードが相手の手札にある場合、相手は手札の"
    "そのカードを全て捨てる。宣言したカードが相手の手札に無い場合、自分の手札をランダムに１枚選んで"
    "捨てる。")
PLAIN = 98  # 沒有宣言的對照卡


class DeclaredNameTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(DEMON_DECLARATION, name_ja="デーモンの宣告", type=0x20002, setcode=0x45),
            card(MIND_CRUSH, name_ja="マインドクラッシュ", type=TRAP),
            card(PLAIN, name_ja="乙"),
        ]
        cls.structures, _ = build_structures(cls.cards, [
            faq(DEMON_DECLARATION, "デーモンの宣告", DEMON_DECLARATION_TEXT),
            faq(MIND_CRUSH, "マインドクラッシュ", MIND_CRUSH_TEXT),
            faq(PLAIN, "乙", "①：このカードを破壊する。"),
        ])

    def structure(self, cid):
        return next(c for c in self.structures if c["id"] == cid)

    def test_declaration_makes_one_name_row_with_empty_text(self):
        """「カード名を１つ宣言して」:名稱表一列,來源「宣言」、字串留空、不算不認得;
        多次宣言仍一列(マインドクラッシュ 的「宣言したカード」不是宣言句)。"""
        for cid, offset in ((DEMON_DECLARATION, 19), (MIND_CRUSH, 2)):
            with self.subTest(card=cid):
                rows = [r for r in self.structure(cid)["names"] if r["source"] == "宣言"]
                self.assertEqual([(r["id"], r["text"], r["unparsed"]) for r in rows],
                                 [(f"n{offset}", "", None)])
        self.assertEqual(self.structure(PLAIN)["names"], [])

    def test_declared_name_is_not_an_unknown_name_and_is_counted(self):
        """覆蓋報告:宣言列計進名稱表的來源計數,不進「不認得的「」名稱」。"""
        cov = build_coverage(self.structures)
        self.assertEqual(cov["names"], {"「」引用": 0, "宣言": 2})
        self.assertEqual(cov["unknown_names"], {})
        self.assertIn("名稱表:「」引用 0 列、宣言 2 列。", render_coverage(cov))

    def test_queries_do_not_compare_declared_names(self):
        """查詢不比宣言:指定任何卡查「加入手牌」都不會因為宣言列而命中或誤判;產物往返保留該列。"""
        result = run_query(self.structures, self.cards,
                           {"actions": ["加入手牌"], "card": PLAIN})
        self.assertNotIn(DEMON_DECLARATION, result["groups"]["全部"])
        loaded = load_structures(serialize_structures(self.structures))
        self.assertEqual(loaded, self.structures)


if __name__ == "__main__":
    unittest.main()
