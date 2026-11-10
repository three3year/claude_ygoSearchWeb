"""去除:「取り除く」的對象只有超量素材與計數器兩種物件。

超量素材 `{kind: 超量素材, of: 所屬卡物件}`、計數器 `{kind: 計數器, counter: 種類名}`;
數量單位「つ」進對象線 `count`。代價、效果、代替、被動條件四種形態走既有機制。
走接縫一(查詢判斷)與接縫二(反向檢查);查詢層沒有的格(物件種類、`of`、`count`…)
先用查詢命中段,再讀該段的格。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, card, faq

ARCHETYPES_11 = ARCHETYPES + [
    {"setcode": 0xc6, "hex": "0xc6", "names_ja": ["Ｅｍ"], "name_zh": "娛樂法師",
     "source": "strings.conf"},
    {"setcode": 0x95, "hex": "0x95", "names_ja": ["ＲＵＭ"], "name_zh": "升階魔法",
     "source": "strings.conf"},
    {"setcode": 0x135, "hex": "0x135", "names_ja": ["＠イグニスター"], "name_zh": "@伊格尼斯者",
     "source": "strings.conf"},
    {"setcode": 0x10d, "hex": "0x10d", "names_ja": ["魔導獣"], "name_zh": "魔導獸",
     "source": "strings.conf"},
]
XYZ_MONSTER = 0x800021      # 效果怪獸 + 超量
PENDULUM_MONSTER = 0x1000021


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES_11)
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


SHADOW_MAKER = 69655484   # Em影絵師シャドー・メイカー
SHADOW_MAKER_TEXT = (
    "レベル５モンスター×３\nこのカード名の①③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードのX素材を１つ取り除き、デッキから「Em」モンスター１体を墓地へ送って"
    "発動できる。デッキから「RUM」魔法カード１枚を手札に加える。\n"
    "②：このカードを対象とする効果が発動した時、このカードのX素材を１つ取り除いて発動できる。"
    "EXデッキから「Em影絵師シャドー・メイカー」１体を特殊召喚する。\n"
    "③：このカードのX素材が全て取り除かれた場合に発動できる。"
    "自分の墓地から「Em」モンスター１体を特殊召喚する。")


class ShadowMakerTest(unittest.TestCase):
    """Em影絵師シャドー・メイカー 69655484。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SHADOW_MAKER, name_ja="Em影絵師シャドー・メイカー", type=XYZ_MONSTER,
                          level=5, race=0x2, attribute=0x20, atk=2600, setcode=0xc6,
                          **{"def": 1000})]
        cls.structures = build(cls.cards, [faq(SHADOW_MAKER, "Em影絵師シャドー・メイカー",
                                               SHADOW_MAKER_TEXT)])
        cls.objects = objects_of(cls.structures, SHADOW_MAKER)

    def test_cost_detach_hits_material_of_this_card(self):
        """①② 的代價段命中「去除」:物件是超量素材 of 物件0、`count` 1。"""
        segs = hit_segments(self.structures, self.cards, SHADOW_MAKER,
                            actions=["去除"], kinds=["代價"])
        self.assertEqual([s["predicate"] for s in segs], ["取り除き", "取り除いて"])
        for seg in segs:
            line, = seg["lines"]
            obj = self.objects[line["object"]]
            self.assertEqual((obj["kind"], obj["of"]), ("超量素材", "o0"))
            self.assertEqual((line["count"]["value"], line["count"]["unit"]), (1, "つ"))

    def test_material_is_not_a_card(self):
        """超量素材不是卡:指定卡片或只給條件時代不進去。"""
        self.assertEqual(hit_segments(self.structures, self.cards, SHADOW_MAKER,
                                      actions=["去除"], card=SHADOW_MAKER), [])
        self.assertEqual(hit_segments(self.structures, self.cards, SHADOW_MAKER,
                                      actions=["去除"], condition={"op": "大類", "value": "怪獸"}),
                         [])

    def test_all_materials_detached_is_passive_condition(self):
        """③「X素材が全て取り除かれた場合」:條件段命中「去除」,被動、`count` 全部。"""
        seg, = hit_segments(self.structures, self.cards, SHADOW_MAKER,
                            actions=["去除"], kinds=["條件"], include_condition=True)
        self.assertEqual((seg["voice"], seg["trigger"]), ("被動", "場合"))
        line, = seg["lines"]
        self.assertEqual(line["count"]["cmp"], "全部")
        obj = self.objects[line["object"]]
        self.assertEqual((obj["kind"], obj["of"]), ("超量素材", "o0"))

    def test_detach_segments_write_back(self):
        segs = hit_segments(self.structures, self.cards, SHADOW_MAKER, actions=["去除"],
                            include_condition=True)
        self.assertEqual(len(segs), 3)
        ids = {s["id"] for s in segs}
        failures = [f for f in check_card(own(self.structures, SHADOW_MAKER))
                    if f["segment"] in ids]
        self.assertEqual(failures, [])

    def test_effect_targeting_this_card_activated_is_condition(self):
        """②「このカードを対象とする効果が発動した時」:條件段命中「發動」。"""
        seg, = hit_segments(self.structures, self.cards, SHADOW_MAKER, actions=["發動"],
                            include_condition=True)
        self.assertEqual((seg["kind"], seg["trigger"]), ("條件", "時"))

    def test_effect_targeting_this_card_accepts_any_card(self):
        """效果所屬的卡沒有其他條件:只給條件「怪獸」也代得進去。"""
        segs = hit_segments(self.structures, self.cards, SHADOW_MAKER, actions=["發動"],
                            include_condition=True, condition={"op": "大類", "value": "怪獸"})
        self.assertEqual(len(segs), 1)

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, SHADOW_MAKER)), [])


LIGHT_DRAGON = 61399402   # ライトドラゴン＠イグニスター
LIGHT_DRAGON_TEXT = (
    "レベル４モンスター×２\nこのカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードのX素材を１つ取り除いて発動できる。自分フィールドの「＠イグニスター」"
    "モンスターの数まで、相手フィールドの表側表示モンスターを選んで破壊する。"
    "②：このカード以外の自分のサイバース族モンスターが相手に戦闘ダメージを与えた時に発動できる。"
    "自分の墓地からリンクモンスター１体を選んで特殊召喚する。"
    "③：自分フィールドのモンスターが効果で破壊される場合、"
    "代わりにこのカードのX素材を１つ取り除く事ができる。")


class LightDragonTest(unittest.TestCase):
    """ライトドラゴン＠イグニスター 61399402。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(LIGHT_DRAGON, name_ja="ライトドラゴン＠イグニスター", type=XYZ_MONSTER,
                          level=4, race=0x1000000, attribute=0x10, atk=2300, setcode=0x135,
                          **{"def": 1500})]
        cls.structures = build(cls.cards, [faq(LIGHT_DRAGON, "ライトドラゴン＠イグニスター",
                                               LIGHT_DRAGON_TEXT)])
        cls.objects = objects_of(cls.structures, LIGHT_DRAGON)

    def test_cost_detach_hits(self):
        seg, = hit_segments(self.structures, self.cards, LIGHT_DRAGON, actions=["去除"])
        self.assertEqual((seg["kind"], seg["predicate"]), ("代價", "取り除いて"))
        obj = self.objects[seg["lines"][0]["object"]]
        self.assertEqual((obj["kind"], obj["of"]), ("超量素材", "o0"))

    def test_replacement_detach_hits_with_replacement(self):
        """③ 做代替的段只在查詢含代替時命中「去除」;被代替的「破壞」段的 replaced_by 指向它。"""
        detach = hit_segments(self.structures, self.cards, LIGHT_DRAGON, actions=["去除"],
                              replacement=True)
        replacing = next(s for s in detach if s["replaces"])
        self.assertEqual(replacing["predicate"], "取り除く事ができる")
        result = run_query(self.structures, self.cards,
                           {"actions": ["破壞"], "replacement": True})
        hit = next(h for h in result["hits"] if h["id"] == LIGHT_DRAGON)
        self.assertEqual(hit["replaced_by"], {replacing["replaces"]: replacing["id"]})

    def test_battle_damage_condition_hits(self):
        seg, = hit_segments(self.structures, self.cards, LIGHT_DRAGON, actions=["傷害"],
                            include_condition=True)
        self.assertEqual((seg["kind"], seg["cause"]["kind"]), ("條件", "戰鬥"))

    def test_select_segments_hit(self):
        destroy, = hit_segments(self.structures, self.cards, LIGHT_DRAGON, actions=["破壞"],
                                from_zones=[{"zone": "場上", "side": "對手"}])
        self.assertEqual(destroy["predicate"], "選んで破壊する")
        summon, = hit_segments(self.structures, self.cards, LIGHT_DRAGON,
                               actions=["特殊召喚"], from_zones=["墓地"])
        self.assertEqual(summon["predicate"], "選んで特殊召喚する")

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, LIGHT_DRAGON)), [])


KING_JACKAL = 27354732   # 魔導獣 キングジャッカル
KING_JACKAL_TEXT = (
    "①：このカードがモンスターゾーンに存在する限り、自分または相手が魔法カードを発動する度に、"
    "このカードに魔力カウンターを２つ置く。②：１ターンに１度、相手モンスターの効果が発動した時、"
    "自分フィールドの魔力カウンターを２つ取り除いて発動できる。その発動を無効にし破壊する。")
KING_JACKAL_PEN = (
    "このカード名のP効果は１ターンに１度しか使用できない。①：もう片方の自分のPゾーンにカードが"
    "存在しない場合に発動できる。このカードを破壊し、自分のEXデッキから「魔導獣 キングジャッカル」"
    "以外の表側表示の「魔導獣」Pモンスター１体を特殊召喚する。")


class KingJackalTest(unittest.TestCase):
    """魔導獣 キングジャッカル 27354732:「自分フィールドの魔力カウンターを２つ取り除いて」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(KING_JACKAL, name_ja="魔導獣 キングジャッカル", type=PENDULUM_MONSTER,
                          level=6, race=0x2, attribute=0x20, atk=2400, setcode=0x10d,
                          **{"def": 1400})]
        cls.structures = build(cls.cards, [faq(KING_JACKAL, "魔導獣 キングジャッカル",
                                               KING_JACKAL_TEXT, KING_JACKAL_PEN)])
        cls.objects = objects_of(cls.structures, KING_JACKAL)

    def test_cost_detaches_spell_counters_from_own_field(self):
        seg, = hit_segments(self.structures, self.cards, KING_JACKAL, actions=["去除"],
                            from_zones=[{"zone": "場上", "side": "我方"}])
        self.assertEqual(seg["kind"], "代價")
        line, = seg["lines"]
        obj = self.objects[line["object"]]
        self.assertEqual((obj["kind"], obj["counter"]), ("計數器", "魔力カウンター"))
        self.assertEqual([(z["zone"], z["side"]) for z in obj["initial_position"]],
                         [("場上", "我方")])
        self.assertEqual((line["count"]["value"], line["count"]["unit"]), (2, "つ"))

    def test_cost_segment_writes_back(self):
        seg, = hit_segments(self.structures, self.cards, KING_JACKAL, actions=["去除"])
        failures = [f for f in check_card(own(self.structures, KING_JACKAL))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])


SPACE_CYCLONE = 69176131   # スペース・サイクロン
SPACE_CYCLONE_TEXT = "フィールド上に存在するエクシーズ素材を１つ取り除く。"


class SpaceCycloneTest(unittest.TestCase):
    """スペース・サイクロン 69176131:沒寫所屬卡的超量素材,所屬卡是新建的物件。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(SPACE_CYCLONE, name_ja="スペース・サイクロン", type=0x10002)]
        cls.structures = build(cls.cards, [faq(SPACE_CYCLONE, "スペース・サイクロン",
                                               SPACE_CYCLONE_TEXT)])
        cls.objects = objects_of(cls.structures, SPACE_CYCLONE)

    def test_material_of_new_object_on_field(self):
        seg, = hit_segments(self.structures, self.cards, SPACE_CYCLONE, actions=["去除"],
                            from_zones=["場上"])
        line, = seg["lines"]
        obj = self.objects[line["object"]]
        self.assertEqual(obj["kind"], "超量素材")
        owner = self.objects[obj["of"]]
        self.assertEqual(owner["source"]["kind"], "新建")
        self.assertEqual([z["zone"] for z in owner["initial_position"]], ["場上"])
        self.assertEqual((line["count"]["value"], line["count"]["unit"]), (1, "つ"))

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(own(self.structures, SPACE_CYCLONE)), [])


INVERZ_ROACH = 37926346   # インヴェルズ・ローチ
INVERZ_ROACH_TEXT = ("レベル４モンスター×２\nこのカードのエクシーズ素材を１つ取り除く事で、"
                     "レベル５以上のモンスターの特殊召喚を無効にし破壊する。")


class OldStyleDetachCostTest(unittest.TestCase):
    """舊式代價句「エクシーズ素材を１つ取り除く事で、」= 新式「X素材を１つ取り除いて発動できる」。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(INVERZ_ROACH, name_ja="インヴェルズ・ローチ", type=XYZ_MONSTER, level=4,
                          race=0x8, attribute=0x20, atk=1900, **{"def": 0})]
        cls.structures = build(cls.cards, [faq(INVERZ_ROACH, "インヴェルズ・ローチ",
                                               INVERZ_ROACH_TEXT)])

    def test_cost_detach_hits_and_writes_back(self):
        seg, = hit_segments(self.structures, self.cards, INVERZ_ROACH, actions=["去除"],
                            kinds=["代價"])
        self.assertEqual(seg["predicate"], "取り除く")
        failures = [f for f in check_card(own(self.structures, INVERZ_ROACH))
                    if f["segment"] == seg["id"]]
        self.assertEqual(failures, [])


SELF = 10001101   # 合成卡(本檔號段 10001101 起)


class MaterialLineAndJoinerTest(unittest.TestCase):
    """超量素材行「×N」,與修飾語的連接字照原文寫回(素材行「水属性レベル４」不寫「・」,
    「ドラゴン族のシンクロモンスター」寫「の」)。"""

    @staticmethod
    def failures(text, **kw):
        cards = [card(SELF, name_ja="甲", **kw)]
        structures = build(cards, [faq(SELF, "甲", text)])
        return [(f["reason"], f["rendered"]) for f in check_card(own(structures, SELF))]

    def test_xyz_material_line_with_attribute_and_level_writes_back(self):
        self.assertEqual(self.failures("水属性レベル４モンスター×２\n①：このカードを破壊する。",
                                       type=XYZ_MONSTER), [])

    def test_xyz_material_line_with_level_and_archetype_writes_back(self):
        self.assertEqual(self.failures("レベル４「Ｅｍ」モンスター×２\n①：このカードを破壊する。",
                                       type=XYZ_MONSTER), [])

    def test_race_then_katakana_subtype_writes_back(self):
        self.assertEqual(self.failures("①：自分の墓地からドラゴン族のシンクロモンスター１体を"
                                       "特殊召喚する。"), [])


DEMETTO = 44190146   # デメット爺さん
DEMETTO_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。①：自分の「プリンセス・コロン」"
    "のX素材を１つ取り除いて発動できる。自分の墓地から攻撃力か守備力が０の通常モンスターを２体まで"
    "選び、闇属性・レベル８モンスターとして守備表示で特殊召喚する。②：自分のXモンスターが、"
    "X素材としている通常モンスターを取り除いて効果を発動した場合、そのXモンスター１体と相手フィールドの"
    "モンスター１体を対象として発動できる。その相手モンスターを破壊し、対象のXモンスターのランク×３００"
    "ダメージを相手に与える。")


class MaterialAttachedIsOutOfScopeTest(unittest.TestCase):
    """「X素材としている」(作為超量素材)那段解析不出,查「去除」列未解析組、不命中。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(DEMETTO, name_ja="デメット爺さん", level=1, race=0x2, attribute=0x20,
                          atk=0, **{"def": 0})]
        cls.structures = build(cls.cards, [faq(DEMETTO, "デメット爺さん", DEMETTO_TEXT)])

    def test_attached_segment_stays_unparsed(self):
        result = run_query(self.structures, self.cards, {"actions": ["去除"],
                                                         "include_condition": True})
        self.assertNotIn(DEMETTO, result["groups"]["全部"])
        entry = next(u for u in result["unparsed"] if u["id"] == DEMETTO)
        texts = [s["text"] for s in entry["segments"]]
        self.assertIn("自分のXモンスターが、X素材としている通常モンスターを取り除いて効果を発動した"
                      "場合", texts)


if __name__ == "__main__":
    unittest.main()
