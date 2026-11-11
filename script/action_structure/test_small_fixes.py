"""里程碑三摘要裁定要改的五個小項(m3b 票 07):「取り除けない」不再解析、召喚進推得表、
出發地含牌組/手牌/額外牌組的「選択して」記選擇、スキヤナー 的反向檢查模板、
數量恰好一張又沒寫比較對象的異同原子判不了。

走接縫一(查詢判斷)與接縫二(反向檢查);標準卡的官方文本逐字寫在測試裡
(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, card, faq


def build(cards, faqs, archetypes=ARCHETYPES):
    structures, _ = build_structures(cards, faqs, archetypes=archetypes)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def unparsed_texts(structures, cards, cid, **query):
    """查詢結果未解析組裡這張卡列出的段原文。"""
    result = run_query(structures, cards, query)
    entry = next((u for u in result["unparsed"] if u["id"] == cid), None)
    return [s["text"] for s in entry["segments"]] if entry else []


CRYSTAL_CORE = 22790789         # 巨大戦艦 クリスタル・コア
CRYSTAL_CORE_TEXT = (
    "①：このカードが召喚した場合に発動する。このカードにカウンターを３つ置く。\n"
    "②：このカードは戦闘では破壊されない。\n"
    "③：１ターンに１度、相手フィールドの表側攻撃表示モンスター１体を対象として発動できる。"
    "その相手の表側攻撃表示モンスターを表側守備表示にする。\n"
    "④：このカードが戦闘を行ったダメージステップ終了時に発動する。"
    "このカードのカウンターを１つ取り除く。取り除けない場合、このカードを破壊する。")


class CannotRemoveTest(unittest.TestCase):
    """去除的語尾沒有「けない」:「取り除けない場合」省略的受詞是前一句的計數器,
    照主語省略規則會記成此卡,所以那一段回到解析不出。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(CRYSTAL_CORE, name_ja="巨大戦艦 クリスタル・コア", level=5,
                          race=0x20, attribute=0x2, atk=2100, setcode=0x15)]
        cls.structures = build(cls.cards, [faq(CRYSTAL_CORE, "巨大戦艦 クリスタル・コア",
                                               CRYSTAL_CORE_TEXT)])

    def test_cannot_remove_condition_is_unparsed(self):
        """開條件段查「去除,極性 不能」並指定此卡:不命中;那一段解析不出,
        開條件段查「去除」時列進未解析組(解析不出的段極性照預設的做)。"""
        query = dict(actions=["去除"], kinds=["條件"], include_condition=True, card=CRYSTAL_CORE)
        self.assertEqual(hit_segments(self.structures, self.cards, CRYSTAL_CORE,
                                      polarities=["不能"], **query), [])
        self.assertEqual(unparsed_texts(self.structures, self.cards, CRYSTAL_CORE, **query),
                         ["取り除けない場合"])

    def test_removing_the_counter_still_hits(self):
        """前一句「このカードのカウンターを１つ取り除く」照舊命中去除。"""
        removes = hit_segments(self.structures, self.cards, CRYSTAL_CORE, actions=["去除"])
        self.assertEqual([s["text"] for s in removes], ["このカードのカウンターを１つ取り除く"])


FALLEN_PLEASURE = 55289183      # 享楽の堕天使
FALLEN_PLEASURE_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：自分・相手のメインフェイズに発動できる。天使族モンスター１体を表側表示でアドバンス召喚する。"
    "②：このカードが墓地へ送られた場合に発動できる。相手フィールドの全てのモンスターの攻撃力・守備力は"
    "ターン終了時まで、フィールドの天使族モンスターの数×５００ダウンする。")
GHOSTRICK_YETI = 84472026       # ゴーストリック・イエティ
GHOSTRICK_YETI_TEXT = (
    "自分フィールドに「ゴーストリック」モンスターが存在する場合のみ、このカードは表側表示で召喚できる。"
    "①：自分メインフェイズに発動できる。このカードを裏側守備表示にする（１ターンに１度のみ）。"
    "②：このカードがリバースした時、フィールドの「ゴーストリック」モンスター１体を対象として発動できる。"
    "そのモンスターはこのターン戦闘・効果では破壊されない。")
GHOSTRICK = [{"setcode": 0x8d, "hex": "0x8d", "names_ja": ["ゴーストリック"],
              "name_zh": "鬼計", "source": "strings.conf"}]
REASON_DISPLAY = "表示形式沒有到"


class SummonInferredToFieldTest(unittest.TestCase):
    """推得表有召喚、通常召喚、上級召喚、反轉召喚 → 場上:「表側表示で〜召喚」沒寫到哪裡也不再標
    「表示形式沒有到」,開推得查「召喚,到 場上」命中。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(FALLEN_PLEASURE, name_ja="享楽の堕天使", type=0x21, level=4, race=0x4,
                          attribute=0x20, atk=0, setcode=0xef),
                     card(GHOSTRICK_YETI, name_ja="ゴーストリック・イエティ", type=0x21, level=3,
                          race=0x10, attribute=0x20, atk=300, setcode=0x8d)]
        cls.structures = build(cls.cards, [
            faq(FALLEN_PLEASURE, "享楽の堕天使", FALLEN_PLEASURE_TEXT),
            faq(GHOSTRICK_YETI, "ゴーストリック・イエティ", GHOSTRICK_YETI_TEXT)],
            archetypes=GHOSTRICK)

    def test_tribute_summon_face_up_reaches_field_when_inferred(self):
        """享楽の堕天使 ①:開推得查「召喚,到 場上」命中「天使族モンスター１体を表側表示でアドバンス召喚する」;
        不開推得不命中。"""
        query = dict(actions=["召喚"], to_zones=["場上"])
        segs = hit_segments(self.structures, self.cards, FALLEN_PLEASURE,
                            include_inferred=True, **query)
        self.assertEqual([s["text"] for s in segs], ["天使族モンスター１体を表側表示でアドバンス召喚する"])
        self.assertEqual(hit_segments(self.structures, self.cards, FALLEN_PLEASURE, **query), [])

    def test_fallen_pleasure_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, FALLEN_PLEASURE)), [])

    def test_ghostrick_face_up_summon_no_longer_lacks_destination(self):
        """ゴーストリック・イエティ「〜場合のみ、このカードは表側表示で召喚できる」:不再標
        「表示形式沒有到」;前文「〜場合のみ、」這輪不收,那一段照舊解析不出。"""
        structure = own(self.structures, GHOSTRICK_YETI)
        seg = next(s for b in structure["blocks"] for _, s in iter_segments(b)
                   if s["text"].endswith("このカードは表側表示で召喚できる"))
        self.assertIsNotNone(seg["unparsed"])
        self.assertNotEqual(seg["unparsed"]["reason"], REASON_DISPLAY)


RAINBOW_PATH = 7617253          # 虹の行方
RAINBOW_PATH_TEXT = (
    "相手モンスターの攻撃宣言時に、自分の魔法＆罠カードゾーンに存在する「宝玉獣」と名のついたカード１枚を"
    "選択して墓地へ送り発動する。相手モンスター１体の攻撃を無効にし、自分のデッキから「究極宝玉神」と"
    "名のついたカード１枚を選択して手札に加える事ができる。")
EXTRA_GATE = 7405310            # エクストラゲート
EXTRA_GATE_TEXT = (
    "１から１２までの任意のレベルを宣言して発動する。相手はエクストラデッキに存在する宣言されたレベルを"
    "持つモンスター１体をゲームから除外する。宣言したレベルを持つモンスターが相手のエクストラデッキに"
    "無かった場合、自分の手札を１枚選択して捨てる。")
ERASER_TRAP = 3055837           # 黒板消しの罠
ERASER_TRAP_TEXT = (
    "ダメージを与える効果が発動した時に発動する事ができる。"
    "自分が受けるその効果ダメージを無効にし、相手は手札を１枚選択して捨てる。")
GRACEFUL_CHARITY = 79571449     # 天使の施し
GRACEFUL_CHARITY_TEXT = "自分のデッキからカードを３枚ドローし、その後手札を２枚選択して捨てる。"
DAWN_KNIGHT = 6351548           # 曙光の騎士
DAWN_KNIGHT_TEXT = (
    "フィールド上のこのカードが墓地へ送られた場合、デッキから光属性モンスター１体を墓地へ送る事ができる。"
    "また、このカードがデッキから墓地へ送られた場合、自分の墓地の光属性モンスター１体を選択して"
    "デッキの一番上に置く。「曙光の騎士」の効果は１ターンに１度しか使用できない。")
CRYSTAL_BEASTS = [{"setcode": 0x1034, "hex": "0x1034", "names_ja": ["宝玉獣"],
                   "name_zh": "寶玉獸", "source": "strings.conf"},
                  {"setcode": 0x2034, "hex": "0x2034", "names_ja": ["究極宝玉神"],
                   "name_zh": "究極寶玉神", "source": "strings.conf"}]


class PrivateSelectionTest(unittest.TestCase):
    """「選択して」而且明寫的出發地含牌組、手牌或額外牌組時是選擇,對象線不標取對象
    (與「選択し」同一把尺);明寫的出發地只有墓地或場上的照舊標取對象。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(RAINBOW_PATH, name_ja="虹の行方", type=0x4),
                     card(EXTRA_GATE, name_ja="エクストラゲート", type=0x10002),
                     card(ERASER_TRAP, name_ja="黒板消しの罠", type=0x100004),
                     card(GRACEFUL_CHARITY, name_ja="天使の施し", type=0x2),
                     card(DAWN_KNIGHT, name_ja="曙光の騎士", type=0x21, level=4, race=0x1,
                          attribute=0x10, atk=1400)]
        cls.structures = build(cls.cards, [
            faq(RAINBOW_PATH, "虹の行方", RAINBOW_PATH_TEXT),
            faq(EXTRA_GATE, "エクストラゲート", EXTRA_GATE_TEXT),
            faq(ERASER_TRAP, "黒板消しの罠", ERASER_TRAP_TEXT),
            faq(GRACEFUL_CHARITY, "天使の施し", GRACEFUL_CHARITY_TEXT),
            faq(DAWN_KNIGHT, "曙光の騎士", DAWN_KNIGHT_TEXT)], archetypes=CRYSTAL_BEASTS)

    def texts(self, cid, **query):
        return [s["text"] for s in hit_segments(self.structures, self.cards, cid, **query)]

    def test_selecting_from_deck_is_not_targeting(self):
        """虹の行方:查「加入手牌」並只看取對象不命中;只給動作詞照舊命中。"""
        self.assertEqual(self.texts(RAINBOW_PATH, actions=["加入手牌"], targeting=True), [])
        self.assertEqual(self.texts(RAINBOW_PATH, actions=["加入手牌"]),
                         ["自分のデッキから「究極宝玉神」と名のついたカード１枚を選択して手札に加える事ができる"])

    def test_selecting_from_hand_is_not_targeting(self):
        """エクストラゲート、黒板消しの罠、天使の施し:查「捨棄」並只看取對象不命中;只給動作詞照舊命中。"""
        for cid, text in ((EXTRA_GATE, "自分の手札を１枚選択して捨てる"),
                          (ERASER_TRAP, "相手は手札を１枚選択して捨てる"),
                          (GRACEFUL_CHARITY, "手札を２枚選択して捨てる")):
            with self.subTest(cid=cid):
                self.assertEqual(self.texts(cid, actions=["捨棄"], targeting=True), [])
                self.assertEqual([t[-len(text):] for t in self.texts(cid, actions=["捨棄"])], [text])

    def test_selecting_from_graveyard_is_still_targeting(self):
        """曙光の騎士「自分の墓地の光属性モンスター１体を選択してデッキの一番上に置く」:只看取對象時照舊命中。"""
        self.assertEqual(self.texts(DAWN_KNIGHT, actions=["放置"], targeting=True),
                         ["自分の墓地の光属性モンスター１体を選択してデッキの一番上に置く"])

    def test_standard_cards_pass_reverse_check(self):
        """天使の施し、曙光の騎士整張通過反向檢查(其餘三張卡在票外的寫法,只驗段)。"""
        for cid in (GRACEFUL_CHARITY, DAWN_KNIGHT):
            with self.subTest(cid=cid):
                self.assertEqual(check_card(own(self.structures, cid)), [])


SCANNER = 75198893              # スキヤナー
SCANNER_TEXT = (
    "ゲームから除外されている相手のモンスター１体を選択して発動する。このカードはエンドフェイズ時まで"
    "選択したモンスターと同名カードとして扱い、選択したモンスターと同じ属性・レベル・攻撃力・守備力になる。"
    "この効果は１ターンに１度しか使用できない。この効果が適用されたこのカードはフィールド上から離れた場合、"
    "ゲームから除外される。")


class ScannerDestinationTest(unittest.TestCase):
    """舊式、有讀點的「〜離れた場合、ゲームから除外される」照代替記;離場那一段解析不出時,
    去處寫回原文也不多寫「代わりに」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SCANNER, name_ja="スキヤナー", type=0x21, level=1, race=0x20,
                          attribute=0x10, atk=-2)]
        cls.structures = build(cls.cards, [faq(SCANNER, "スキヤナー", SCANNER_TEXT)])

    def test_no_literal_mismatch(self):
        """整張沒有字面不符(去處「ゲームから除外される」寫回原文相符)。"""
        failures = check_card(own(self.structures, SCANNER))
        self.assertEqual([f for f in failures if f["reason"] == "字面不符"], [])
        destination = next(s for b in own(self.structures, SCANNER)["blocks"]
                           for _, s in iter_segments(b) if s["text"] == "ゲームから除外される")
        self.assertEqual([f for f in failures if f["segment"] == destination["id"]], [])

    def test_banish_still_hits_with_replacement(self):
        """開代替查「除外」照舊命中「ゲームから除外される」;不開代替不命中。"""
        segs = hit_segments(self.structures, self.cards, SCANNER, actions=["除外"],
                            replacement=True)
        self.assertEqual([s["text"] for s in segs], ["ゲームから除外される"])
        self.assertEqual(hit_segments(self.structures, self.cards, SCANNER, actions=["除外"]), [])


if __name__ == "__main__":
    unittest.main()
