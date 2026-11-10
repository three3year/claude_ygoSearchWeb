"""「選んで」:「〜を選んで+述語」不另成段,字面留在述語開頭、不標取對象。

走接縫一(查詢判斷)與接縫二(反向檢查);查詢層沒有的格(`count`、`pick`、物件條件、`display`…)
先用查詢命中段,再讀該段的格。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures, load_structures, serialize_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, EFFECT_MONSTER, card, faq

ARCHETYPES_09 = ARCHETYPES + [
    {"setcode": 0x64, "hex": "0x64", "names_ja": ["ハーピィ"], "name_zh": "神鷹",
     "source": "strings.conf"},
    {"setcode": 0xc8, "hex": "0xc8", "names_ja": ["イグナイト"], "name_zh": "點火騎士",
     "source": "strings.conf"},
    {"setcode": 0x1d8, "hex": "0x1d8", "names_ja": ["エルフェンノーツ"], "name_zh": "耀聖",
     "source": "strings.conf"},
]
PENDULUM_MONSTER = 0x1000021   # 效果怪獸 + 靈擺


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES_09)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def objects_of(structures, cid):
    return {o["id"]: o for o in own(structures, cid)["objects"]}


IGNITE_DRAGUNOV = 97024987   # イグナイト・ドラグノフ
IGNITE_DRAGUNOV_PEN = (
    "①：もう片方の自分のPゾーンに「イグナイト」カードが存在する場合に発動できる。"
    "自分のPゾーンのカードを全て破壊し、自分のデッキ・墓地から戦士族・炎属性モンスター１体を"
    "選んで手札に加える。")
IGNITE_DRAGUNOV_FLAVOR = (
    "一本気で曲がったことが嫌いなイグナイトのベテラン戦士。その性格のせいか、"
    "近頃は自分の持つ武器に疑問を抱いているようだ。")


class IgniteDragunovTest(unittest.TestCase):
    """イグナイト・ドラグノフ 97024987:「〜１体を選んで手札に加える」照常是加入手牌。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(IGNITE_DRAGUNOV, name_ja="イグナイト・ドラグノフ",
                          type=PENDULUM_MONSTER, level=4, race=0x1, attribute=0x4,
                          atk=1700, setcode=0xc8, **{"def": 1300})]
        cls.structures = build(cls.cards, [faq(IGNITE_DRAGUNOV, "イグナイト・ドラグノフ",
                                               IGNITE_DRAGUNOV_FLAVOR, IGNITE_DRAGUNOV_PEN)])

    def test_add_to_hand_from_deck_hits(self):
        segs = hit_segments(self.structures, self.cards, IGNITE_DRAGUNOV,
                            actions=["加入手牌"], from_zones=["牌組"])
        self.assertEqual([s["predicate"] for s in segs], ["選んで手札に加える"])

    def test_select_segment_writes_back(self):
        """「選んで」寫在述語開頭,整段原樣寫回。"""
        seg, = hit_segments(self.structures, self.cards, IGNITE_DRAGUNOV,
                            actions=["加入手牌"], from_zones=["牌組"])
        failures = [f for f in check_card(own(self.structures, IGNITE_DRAGUNOV))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])

    def test_select_is_not_targeting(self):
        segs = hit_segments(self.structures, self.cards, IGNITE_DRAGUNOV,
                            actions=["加入手牌"], targeting=True)
        self.assertEqual(segs, [])


IGNITE_BURST = 65872270   # イグナイト・バースト
IGNITE_BURST_TEXT = (
    "①：１ターンに１度、自分メインフェイズにこの効果を発動できる。"
    "このカード以外の自分フィールドの「イグナイト」カードを３枚まで選んで破壊する。"
    "その後、破壊した数だけ相手フィールドのカードを選んで持ち主の手札に戻す。"
    "②：このカードが墓地へ送られた場合に発動できる。"
    "自分のエクストラデッキの表側表示の「イグナイト」Pモンスター１体を選んで手札に加える。")


def _atoms(condition):
    if not isinstance(condition, dict):
        return []
    out = [condition]
    for arg in condition.get("args", []):
        out += _atoms(arg)
    if "arg" in condition:
        out += _atoms(condition["arg"])
    return out


class IgniteBurstTest(unittest.TestCase):
    """イグナイト・バースト 65872270。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(IGNITE_BURST, name_ja="イグナイト・バースト", type=0x20004,
                          setcode=0xc8)]
        cls.structures = build(cls.cards, [faq(IGNITE_BURST, "イグナイト・バースト",
                                               IGNITE_BURST_TEXT)])
        cls.objects = objects_of(cls.structures, IGNITE_BURST)

    def test_destroy_from_field_up_to_three_except_this_card(self):
        seg, = hit_segments(self.structures, self.cards, IGNITE_BURST,
                            actions=["破壞"], from_zones=["場上"])
        line, = seg["lines"]
        self.assertEqual((line["count"]["cmp"], line["count"]["value"]), ("≤", 3))
        ops = [a["op"] for a in _atoms(self.objects[line["object"]]["condition"])]
        self.assertIn("非", ops)

    def test_return_to_owners_hand(self):
        seg, = hit_segments(self.structures, self.cards, IGNITE_BURST,
                            actions=["返回"], to_zones=["手牌"])
        line, = seg["lines"]
        self.assertEqual(line["to"]["zones"][0]["side"], "持有者")
        self.assertEqual(line["count"], {"kind": "算式", "text": "破壊した数だけ",
                                         "placement": "名詞前"})

    def test_return_to_my_hand_does_not_hit(self):
        """持ち主 靜態判不了,指定我方或對手都不命中。"""
        for side in ("我方", "對手"):
            self.assertEqual(hit_segments(self.structures, self.cards, IGNITE_BURST,
                                          actions=["返回"],
                                          to_zones=[{"zone": "手牌", "side": side}]), [])

    def test_add_to_hand_from_extra_deck_face_up(self):
        seg, = hit_segments(self.structures, self.cards, IGNITE_BURST,
                            actions=["加入手牌"], from_zones=["額外牌組"])
        line, = seg["lines"]
        faces = [a["value"] for a in _atoms(self.objects[line["object"]]["condition"])
                 if a["op"] == "表示形式"]
        self.assertEqual(faces, ["表側表示"])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, IGNITE_BURST)), [])


SAFFIRA = 56350972         # 竜姫神サフィラ
SAFFIRA_TEXT = (
    "「祝祷の聖歌」により降臨。このカード名の効果は１ターンに１度しか使用できない。"
    "①：このカードが儀式召喚したターンのエンドフェイズ及び、このカードがモンスターゾーンに存在し、"
    "手札・デッキから光属性モンスターが墓地へ送られたターンのエンドフェイズに、"
    "以下の効果から１つを選択して発動できる。\n"
    "●自分はデッキから２枚ドローし、その後手札を１枚選んで捨てる。\n"
    "●相手の手札をランダムに１枚選んで墓地へ捨てる。\n"
    "●自分の墓地の光属性モンスター１体を選んで手札に加える。")
HYMN = 80566312            # 祝祷の聖歌


class SaffiraTest(unittest.TestCase):
    """竜姫神サフィラ 56350972。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(SAFFIRA, name_ja="竜姫神サフィラ", type=0xa1, level=6, race=0x2000,
                 attribute=0x10, atk=2500, **{"def": 2400}),
            card(HYMN, name_ja="祝祷の聖歌", type=0x82),
        ]
        cls.structures = build(cls.cards, [faq(SAFFIRA, "竜姫神サフィラ", SAFFIRA_TEXT)])

    def test_discard_from_my_hand_zone_as_object(self):
        """「手札を１枚選んで捨てる」:手牌當區域,物件是新建的卡、從手牌(我方)、count 1。"""
        seg, = hit_segments(self.structures, self.cards, SAFFIRA, actions=["捨棄"],
                            from_zones=[{"zone": "手牌", "side": "我方"}])
        line, = seg["lines"]
        self.assertEqual(line["count"]["value"], 1)
        self.assertIsNone(line["pick"])

    def test_discard_from_opponents_hand_at_random(self):
        seg, = hit_segments(self.structures, self.cards, SAFFIRA, actions=["捨棄"],
                            from_zones=[{"zone": "手牌", "side": "對手"}])
        line, = seg["lines"]
        self.assertEqual(line["pick"], "隨機")

    def test_add_to_hand_from_graveyard(self):
        segs = hit_segments(self.structures, self.cards, SAFFIRA, actions=["加入手牌"],
                            from_zones=["墓地"])
        self.assertEqual(len(segs), 1)

    def test_select_segments_write_back(self):
        """● 裡三個「選んで」段原樣寫回。"""
        segs = [s for b in own(self.structures, SAFFIRA)["blocks"] for _, s in iter_segments(b)
                if "選んで" in (s["predicate"] or "")]
        failed = {f["segment"] for f in check_card(own(self.structures, SAFFIRA))}
        self.assertEqual(len(segs), 3)
        self.assertEqual([s["id"] for s in segs if s["id"] in failed], [])

    def test_draw_branch_writes_back(self):
        """● 第一支「自分はデッキから２枚ドローし、その後手札を１枚選んで捨てる」
        的抽牌段命中、誰我方、張數 2,抽牌與捨棄兩段都寫回。"""
        draw_seg, = hit_segments(self.structures, self.cards, SAFFIRA, actions=["抽牌"],
                                 from_zones=["牌組"])
        self.assertEqual((draw_seg["agent"], draw_seg["lines"][0]["count"]["value"]), ("我方", 2))
        discard, = hit_segments(self.structures, self.cards, SAFFIRA, actions=["捨棄"],
                                from_zones=[{"zone": "手牌", "side": "我方"}])
        failed = {f["segment"] for f in check_card(own(self.structures, SAFFIRA))}
        self.assertEqual({draw_seg["id"], discard["id"]} & failed, set())

    def test_round_trip(self):
        text = serialize_structures(self.structures)
        self.assertEqual(load_structures(text), self.structures)
        self.assertEqual(serialize_structures(load_structures(text)), text)


DINA = 59581480            # 耀聖の波詩ディーナ
DINA_TEXT = (
    "このカード名の、①の方法による特殊召喚は１ターンに１度しかできず、"
    "②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードは手札から自分の中央のメインモンスターゾーンに特殊召喚できる。\n"
    "②：自分メインフェイズに発動できる。デッキから「エルフェンノーツ」永続魔法カード１枚を"
    "自分フィールドに表側表示で置く。\n"
    "③：相手ターンに発動できる。自分のメインモンスターゾーンの、このカードと中央のモンスターの"
    "位置を入れ替える。その後、相手の手札をランダムに１枚選んでエンドフェイズまで表側で除外できる。")
DINA_BANISH = "相手の手札をランダムに１枚選んでエンドフェイズまで表側で除外できる"


class DinaTest(unittest.TestCase):
    """耀聖の波詩ディーナ 59581480:只驗 ③ 後半;① 的區域位置與 ③ 前半的
    「入れ替える」不在範圍,整張反向檢查不要求。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(DINA, name_ja="耀聖の波詩ディーナ", level=6, race=0x2, attribute=0x2,
                          atk=2400, setcode=0x1d8, **{"def": 1800})]
        cls.structures = build(cls.cards, [faq(DINA, "耀聖の波詩ディーナ", DINA_TEXT)])
        cls.seg, = hit_segments(cls.structures, cls.cards, DINA, actions=["除外"],
                                from_zones=[{"zone": "手牌", "side": "對手"}])

    def test_banish_from_opponents_hand_hits(self):
        self.assertEqual(self.seg["text"], DINA_BANISH)

    def test_random_pick_until_end_phase_face_up_optional(self):
        line, = self.seg["lines"]
        self.assertEqual(line["pick"], "隨機")
        self.assertEqual(self.seg["duration"]["kind"], "到X為止")
        self.assertEqual(line["to"]["form"]["display"]["alternatives"],
                         [{"face": "表側", "position": None}])
        self.assertTrue(self.seg["optional"])

    def test_banish_segment_writes_back(self):
        failures = [f for f in check_card(own(self.structures, DINA))
                    if f["segment"] == self.seg["id"]]
        self.assertEqual(failures, [])


HARPIE_ELEGANT = 65664792  # 華麗なるハーピィ・レディ
HARPIE_ELEGANT_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：自分フィールドの「ハーピィ・レディ三姉妹」１体を選んで持ち主のデッキに戻す。"
    "その後、元々のカード名が異なる「ハーピィ」モンスター３体を、自分の手札・デッキ・墓地から"
    "それぞれ１体ずつ選んで特殊召喚できる。"
    "このカードの発動後、ターン終了時まで自分は風属性モンスターしか特殊召喚できない。"
    "②：フィールドのこのカードが相手の効果または自分の「ハーピィ」カードの効果で破壊された場合に"
    "発動する。デッキから「ハーピィ」モンスター１体を手札に加える。")
HARPIE_SISTERS = 12206212  # ハーピィ・レディ三姉妹


class HarpieElegantTest(unittest.TestCase):
    """華麗なるハーピィ・レディ 65664792:「それぞれ１体ずつ選んで」的 count 帶 each。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(HARPIE_ELEGANT, name_ja="華麗なるハーピィ・レディ", type=0x4, setcode=0x64),
            card(HARPIE_SISTERS, name_ja="ハーピィ・レディ三姉妹", type=0x2000021, level=6,
                 race=0x200, attribute=0x8, atk=1950, setcode=0x64, **{"def": 2100}),
        ]
        cls.structures = build(cls.cards, [faq(HARPIE_ELEGANT, "華麗なるハーピィ・レディ",
                                               HARPIE_ELEGANT_TEXT)])

    def test_special_summon_count_each(self):
        seg, = hit_segments(self.structures, self.cards, HARPIE_ELEGANT,
                            actions=["特殊召喚"], from_zones=["手牌"])
        line, = seg["lines"]
        self.assertEqual(line["count"], {"text": "それぞれ１体ずつ", "value": 1, "unit": "体",
                                         "cmp": "=", "each": True, "placement": "述語前"})

    def test_return_to_owners_deck(self):
        seg, = hit_segments(self.structures, self.cards, HARPIE_ELEGANT, actions=["返回"],
                            to_zones=["牌組"])
        self.assertEqual(seg["lines"][0]["to"]["zones"][0]["side"], "持有者")


SELF = 10000901   # 本檔的合成卡(10000901 起)


def library(text):
    cards = [card(SELF, name_ja="甲", type=0x2)]
    return cards, build(cards, [faq(SELF, "甲", text)])


def passes(structures):
    return check_card(own(structures, SELF)) == []


class SelectPatternTest(unittest.TestCase):
    """「選んで」各寫法的句型層級測試(合成卡,句子取自真卡)。"""

    def test_zone_as_object_same_structure_as_from_hand(self):
        """「自分の手札を１枚選んで捨てる」與「手札からカードを１枚捨てる」產出相同結構(字面除外)。"""
        def shape(text):
            cards, structures = library(text)
            seg, = hit_segments(structures, cards, SELF, actions=["捨棄"], from_zones=["手牌"])
            self.assertTrue(passes(structures))
            line, = seg["lines"]
            obj = objects_of(structures, SELF)[line["object"]]
            return ({k: v for k, v in line["from"].items() if k not in ("text", "placement")},
                    line["count"], line["to"], obj["source"], obj["condition"],
                    obj["initial_position"], obj["count"])

        self.assertEqual(shape("①：手札を１枚選んで捨てる。"),
                         shape("①：手札からカードを１枚捨てる。"))
        self.assertEqual(shape("①：自分の手札を１枚選んで捨てる。"),
                         shape("①：自分の手札からカードを１枚捨てる。"))

    def test_random_without_count(self):
        cards, structures = library("①：相手の手札をランダムに選んで捨てる。")
        seg, = hit_segments(structures, cards, SELF, actions=["捨棄"],
                            from_zones=[{"zone": "手牌", "side": "對手"}])
        self.assertEqual(seg["lines"][0]["pick"], "隨機")
        self.assertTrue(passes(structures))

    def test_any_number_is_formula_count(self):
        cards, structures = library(
            "①：自分の墓地の闇属性モンスターを任意の数だけ選んで除外する。")
        seg, = hit_segments(structures, cards, SELF, actions=["除外"], from_zones=["墓地"])
        self.assertEqual(seg["lines"][0]["count"], {"kind": "算式", "text": "任意の数だけ"})
        self.assertTrue(passes(structures))

    def test_each_count_writes_back(self):
        cards, structures = library(
            "①：「ハーピィ」モンスター３体を、自分の手札・デッキ・墓地から"
            "それぞれ１体ずつ選んで特殊召喚する。")
        self.assertTrue(hit_segments(structures, cards, SELF, actions=["特殊召喚"],
                                     from_zones=["墓地"]))
        self.assertTrue(passes(structures))

    def test_cost_clause_ending_with_select(self):
        """「デッキから〜１枚を選んで発動する」:以「選んで」收尾的是發動句的代價子句(沒有動作詞)。"""
        cards, structures = library("デッキから魔法カード１枚を選んで発動する。")
        seg, = [s for b in own(structures, SELF)["blocks"] for _, s in iter_segments(b)]
        self.assertEqual((seg["kind"], seg["actions"], seg["predicate"], seg["unparsed"]),
                         ("代價", [], "選んで", None))
        self.assertFalse(seg["lines"][0]["targeting"])
        self.assertTrue(passes(structures))

    def test_select_one_and_apply_is_branch(self):
        """「以下の効果から１つを選んで適用する」交給分歧引導句,● 的段照常命中。"""
        cards, structures = library(
            "①：以下の効果から１つを選んで適用する。\n"
            "●フィールドのモンスター１体を選んで破壊する。\n"
            "●自分の墓地のモンスター１体を選んで手札に加える。")
        block, = own(structures, SELF)["blocks"]
        self.assertEqual([n["node"] for n in block["tree"]["items"]], ["分歧"])
        self.assertTrue(hit_segments(structures, cards, SELF, actions=["破壞"]))
        self.assertTrue(passes(structures))

    def test_end_phase_duration_before_predicate(self):
        cards, structures = library(
            "①：フィールドのモンスター１体を選んでエンドフェイズまで除外する。")
        seg, = hit_segments(structures, cards, SELF, actions=["除外"])
        self.assertEqual(seg["duration"], {"kind": "到X為止", "text": "エンドフェイズまで"})
        self.assertTrue(passes(structures))


if __name__ == "__main__":
    unittest.main()
