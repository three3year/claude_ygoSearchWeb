"""抽牌:抽到的卡是新建物件、張數進對象線 `count`、從牌組到手牌;「カードを」有沒有寫
結構相同;「自分は/相手は/お互いは」是 `agent`,「ドローしたプレイヤーは」是指回抽牌段的 `agent`。

走接縫一(查詢判斷)與接縫二(反向檢查);查詢層沒有的格(`agent`、`count`、`cause`…)先用查詢
命中段,再讀該段的格。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, SPELL, card, faq


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


DARK_WORLD_DEALINGS = 74117290   # 暗黒界の取引
DARK_WORLD_DEALINGS_TEXT = (
    "①：お互いはそれぞれデッキから１枚ドローする。"
    "その後、ドローしたプレイヤーは自身の手札を１枚選んで捨てる。")


class DarkWorldDealingsTest(unittest.TestCase):
    """暗黒界の取引 74117290。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(DARK_WORLD_DEALINGS, name_ja="暗黒界の取引", type=SPELL, setcode=0x6)]
        cls.structures = build(cls.cards, [faq(DARK_WORLD_DEALINGS, "暗黒界の取引",
                                               DARK_WORLD_DEALINGS_TEXT)])

    def draw_segment(self):
        seg, = hit_segments(self.structures, self.cards, DARK_WORLD_DEALINGS, actions=["抽牌"])
        return seg

    def test_draw_hits_with_both_players_each_drawing_one_from_deck(self):
        seg = self.draw_segment()
        self.assertEqual(seg["agent"], "雙方各自")
        line, = seg["lines"]
        self.assertEqual(line["count"]["value"], 1)
        self.assertEqual([z["zone"] for z in line["from"]["zones"]], ["牌組"])

    def test_deck_to_hand_hits_without_action_word(self):
        """抽到的卡是新建物件、線帶從/到:只給「牌組 → 手牌」(到是推得)也命中抽牌段。"""
        segs = hit_segments(self.structures, self.cards, DARK_WORLD_DEALINGS,
                            from_zones=["牌組"], to_zones=["手牌"], include_inferred=True)
        self.assertEqual([s["id"] for s in segs], [self.draw_segment()["id"]])

    def test_discard_agent_refers_back_to_the_draw_segment(self):
        seg, = hit_segments(self.structures, self.cards, DARK_WORLD_DEALINGS,
                            actions=["捨棄"], from_zones=["手牌"])
        self.assertEqual(seg["agent"], {"ref": "ドローしたプレイヤー",
                                        "segment": self.draw_segment()["id"]})

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, DARK_WORLD_DEALINGS)), [])


TSUPPA_REACH = 20216608   # ツッパリーチ
TSUPPA_REACH_TEXT = (
    "①：自分ドローフェイズに通常のドローをした時、そのカード１枚を相手に見せて発動できる。"
    "そのカードをデッキの一番下に戻し、自分はデッキから１枚ドローする。"
    "②：自分が効果でカードをドローした時、そのカード１枚を相手に見せて発動できる。"
    "このカードを墓地へ送り、見せたカードをデッキの一番下に戻し、自分はデッキから１枚ドローする。")


class TsuppaReachTest(unittest.TestCase):
    """ツッパリーチ 20216608。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(TSUPPA_REACH, name_ja="ツッパリーチ", type=0x80002)]
        cls.structures = build(cls.cards, [faq(TSUPPA_REACH, "ツッパリーチ", TSUPPA_REACH_TEXT)])

    def test_draw_conditions_by_rule_and_by_effect(self):
        segs = hit_segments(self.structures, self.cards, TSUPPA_REACH, actions=["抽牌"],
                            kinds=["條件"], include_condition=True)
        self.assertEqual([(s["predicate"], s["cause"]["kind"]) for s in segs],
                         [("ドローをした", "規則"), ("ドローした", "效果")])
        self.assertEqual(segs[0]["cause"], {"kind": "規則", "text": "通常の"})

    def test_effect_draws_are_mine(self):
        segs = hit_segments(self.structures, self.cards, TSUPPA_REACH, actions=["抽牌"])
        self.assertEqual([(s["kind"], s["agent"]) for s in segs],
                         [("效果", "我方"), ("效果", "我方")])

    def test_shown_card_is_the_drawn_card(self):
        """「そのカード１枚を相手に見せて」指回條件段抽到的卡,張數記在這次提及。"""
        drawn = hit_segments(self.structures, self.cards, TSUPPA_REACH, actions=["抽牌"],
                             kinds=["條件"], include_condition=True)
        shown = hit_segments(self.structures, self.cards, TSUPPA_REACH, actions=["展示"],
                             kinds=["代價"])
        self.assertEqual([s["lines"][0]["object"] for s in shown],
                         [s["lines"][0]["object"] for s in drawn])
        self.assertEqual([(s["lines"][0]["ref"], s["lines"][0]["count"]["value"]) for s in shown],
                         [("そのカード", 1), ("そのカード", 1)])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, TSUPPA_REACH)), [])


CROWLEY = 875572        # 天賦の魔導士クロウリー(① 只取發動條件那句)
PUPPET_KING = 3167573   # パペット・キング
DECK_LOCK = 1149109     # デッキロック


def non_draw_add_to_hand(cid, name, text, **kw):
    cards = [card(cid, name_ja=name, **kw)]
    structures = build(cards, [faq(cid, name, text)])
    return cards, structures


class AddedToHandExceptByDrawTest(unittest.TestCase):
    """「ドロー以外の方法で手札に加わった/加えた」:動作詞仍是加入手牌,原因是方法、exclude 抽牌。"""

    def test_crowley_added_to_hand_except_by_draw(self):
        cards, structures = non_draw_add_to_hand(
            CROWLEY, "天賦の魔導士クロウリー",
            "①：このカードがドロー以外の方法で手札に加わった場合に発動できる。"
            "このカードを特殊召喚する。",
            level=4, race=0x2, attribute=0x20, atk=1800)
        seg, = hit_segments(structures, cards, CROWLEY, actions=["加入手牌"],
                            kinds=["條件"], include_condition=True)
        self.assertEqual(seg["cause"], {"kind": "方法", "exclude": ["抽牌"],
                                        "text": "ドロー以外の方法で"})
        self.assertEqual(check_card(own(structures, CROWLEY)), [])

    def test_puppet_king_opponent_added_from_deck_except_by_draw(self):
        cards, structures = non_draw_add_to_hand(
            PUPPET_KING, "パペット・キング",
            "①：相手がドロー以外の方法でデッキからモンスターを手札に加えた時に発動できる。"
            "このカードを手札から特殊召喚する。②：このカードの①の効果で特殊召喚に成功した場合、"
            "次の自分ターンのエンドフェイズに発動する。このカードを破壊する。",
            level=7, race=0x1, attribute=0x1, atk=2800)
        seg, = hit_segments(structures, cards, PUPPET_KING, actions=["加入手牌"],
                            kinds=["條件"], include_condition=True)
        self.assertEqual(seg["cause"]["exclude"], ["抽牌"])
        self.assertEqual(seg["agent"], "對手")
        failures = [f for f in check_card(own(structures, PUPPET_KING))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])

    def test_deck_lock_cannot_add_to_hand(self):
        cards, structures = non_draw_add_to_hand(
            DECK_LOCK, "デッキロック",
            "このカードは発動後、２回目の自分スタンバイフェイズに破壊される。\n"
            "①：このカードが魔法＆罠ゾーンに存在する限り、お互いにドロー以外の方法で"
            "デッキからカードを手札に加える事ができず、デッキからモンスターを特殊召喚する事もできない。",
            type=0x20002)
        seg, = hit_segments(structures, cards, DECK_LOCK, actions=["加入手牌"],
                            polarities=["不能"])
        self.assertEqual(seg["agent"], {"side": "雙方各自", "text": "お互いに"})
        self.assertEqual(seg["cause"]["exclude"], ["抽牌"])
        failures = [f for f in check_card(own(structures, DECK_LOCK))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])


KAIJU_CAPTURE = 81057455   # 壊獣捕獲大作戦
FIRE_SOUL = 95026693       # ファイヤー・ソウル
_LITERAL_KEYS = {"id", "span", "text", "block", "marker", "object"}


def _sideless(zones):
    return [{k: v for k, v in z.items() if k != "side"} for z in zones]


def draw_shape(cid, name, text):
    """抽牌段的結構去掉字面、誰、張數與牌組的方;另回誰、張數、牌組的方、反向檢查通過與否
    與查「抽牌,從對手的牌組」命中與否。"""
    cards = [card(cid, name_ja=name, type=SPELL)]
    structures = build(cards, [faq(cid, name, text)])
    seg, = hit_segments(structures, cards, cid, actions=["抽牌"])
    line, = seg["lines"]
    obj = next(o for o in own(structures, cid)["objects"] if o["id"] == line["object"])
    deck_side = {z["side"] for z in line["from"]["zones"]}
    line = {**line, "from": {**line["from"], "zones": _sideless(line["from"]["zones"])}}
    obj = {**obj, "initial_position": _sideless(obj["initial_position"])}
    shape = ({k: v for k, v in seg.items() if k not in _LITERAL_KEYS | {"lines", "agent"}},
             {k: v for k, v in line.items() if k not in _LITERAL_KEYS | {"count"}},
             {k: v for k, v in obj.items() if k not in _LITERAL_KEYS})
    passes = not [f for f in check_card(own(structures, cid)) if f["segment"] == seg["id"]]
    from_opponent_deck = bool(hit_segments(
        structures, cards, cid, actions=["抽牌"], from_zones=[{"zone": "牌組", "side": "對手"}]))
    return shape, seg["agent"], line["count"]["value"], deck_side, passes, from_opponent_deck


class DrawObjectWrittenOrNotTest(unittest.TestCase):
    """「カードを」有沒有寫,抽牌段結構相同,只差誰、張數與牌組的方(沒寫方的牌組是抽牌者的,
    「相手はデッキから」是對手的牌組;站主 2026-11-10)。"""

    def test_same_structure_differing_only_in_agent_count_and_deck_side(self):
        kaiju = draw_shape(
            KAIJU_CAPTURE, "壊獣捕獲大作戦",
            "「壊獣捕獲大作戦」の②の効果は１ターンに１度しか使用できない。"
            "①：１ターンに１度、フィールドの「壊獣」モンスター１体を対象として発動できる。"
            "そのモンスターを裏側守備表示にする。その後、このカードに壊獣カウンターを１つ置く"
            "（最大３つまで）。②：このカードが相手の効果で破壊され墓地へ送られた場合に発動できる。"
            "自分はデッキから２枚ドローする。")
        fire = draw_shape(
            FIRE_SOUL, "ファイヤー・ソウル",
            "相手はデッキからカードを１枚ドローする。自分のデッキから炎族モンスター１体を選んで"
            "ゲームから除外し、除外したモンスターの攻撃力の半分のダメージを相手ライフに与える。"
            "このカードを発動するターン、自分は攻撃宣言できない。")
        self.assertEqual(kaiju[0], fire[0])
        self.assertEqual(kaiju[1:], ("我方", 2, {"我方"}, True, False))
        self.assertEqual(fire[1:], ("對手", 1, {"對手"}, True, True))


SELF = 10001001   # 本檔的合成卡(10001001 起)


def library(text):
    cards = [card(SELF, name_ja="甲", type=SPELL)]
    return cards, build(cards, [faq(SELF, "甲", text)])


class DrawPatternTest(unittest.TestCase):
    """抽牌各寫法的句型層級測試(合成卡,句子取自真卡)。"""

    def draw_line(self, text, **query):
        cards, structures = library(text)
        seg, = hit_segments(structures, cards, SELF, actions=["抽牌"], **query)
        self.assertEqual(check_card(own(structures, SELF)), [])
        return seg, seg["lines"][0]

    def test_deck_not_written_is_inferred(self):
        seg, line = self.draw_line("①：自分は２枚ドローする。", from_zones=["牌組"],
                                   include_inferred=True)
        self.assertEqual((line["from"]["source"], line["count"]["value"]), ("推得", 2))
        cards, structures = library("①：自分は２枚ドローする。")
        self.assertEqual(hit_segments(structures, cards, SELF, actions=["抽牌"],
                                      from_zones=["牌組"]), [])

    def test_formula_count_before_subject(self):
        seg, line = self.draw_line("①：破壊した数だけ自分はデッキからドローする。")
        self.assertEqual(line["count"], {"kind": "算式", "text": "破壊した数だけ",
                                         "placement": "主語前"})
        self.assertEqual(seg["agent"], "我方")

    def test_formula_count_after_subject(self):
        seg, line = self.draw_line("①：自分はデッキに戻した数だけデッキからドローする。")
        self.assertEqual(line["count"], {"kind": "算式", "text": "デッキに戻した数だけ",
                                         "placement": "名詞前"})

    def test_both_players_written_out(self):
        seg, line = self.draw_line("①：お互いのプレイヤーは、それぞれデッキから１枚ドローする。")
        self.assertEqual(seg["agent"], {"side": "雙方各自", "text": "お互いのプレイヤーは、"})
        self.assertTrue(line["count"]["each"])

    def test_opponent_draws_condition(self):
        seg, _ = self.draw_line("①：相手がドローした場合に発動できる。このカードを破壊する。",
                                kinds=["條件"], include_condition=True)
        self.assertEqual(seg["agent"], "對手")

    def test_draw_phase_is_not_a_draw(self):
        """「ドローフェイズ」是階段字面:不命中抽牌,也不因字面列進抽牌的未解析組。"""
        cards, structures = library(
            "①：自分ドローフェイズに発動できる。このカードを手札に加える。")
        result = run_query(structures, cards, {"actions": ["抽牌"], "include_condition": True})
        self.assertEqual((result["groups"]["全部"], result["groups"]["未解析"]), ([], []))


if __name__ == "__main__":
    unittest.main()
