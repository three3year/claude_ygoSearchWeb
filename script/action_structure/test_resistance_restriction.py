"""m2 票 04 抗性/限制:既有動作詞加極性(不會/不能/只能)與攻擊家族。

接縫一(查詢判斷)與接縫二(反向檢查)。斷言裡的「原因效果」「`times` 2」這類現有查詢欄比不到的
條件,先用查詢命中、再讀命中段的格(spec「查詢判斷」不加篩選欄)。官方文本逐字寫在測試裡。
"""
import unittest

from card_structure import build_structures
from action_query import run_query
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, EFFECT_MONSTER, SPELL, card, faq

ELEKIRIN = 402568            # エレキリン
MASTER_MONK = 49814180       # マスターモンク
BERSERK_DEAD_DRAGON = 85605684  # バーサーク・デッド・ドラゴン
SERVAL_HAWK = 15335853       # 幻獣機サーバルホーク
KINO = 75416738              # キノの蟲惑魔
WATER_STAGE = 29047353       # 水舞台

ELEKIRIN_TEXT = (
    "①：このカードは直接攻撃できる。\n"
    "②：このカードが直接攻撃で相手に戦闘ダメージを与えた場合に発動する。"
    "このターン、相手は魔法・罠・モンスターの効果を発動できない。")
MASTER_MONK_TEXT = (
    "このカードは通常召喚できない。自分フィールド上に存在する「モンク・ファイター」１体を"
    "生け贄に捧げた場合のみ特殊召喚する事ができる。"
    "このカードは１ターンに２回攻撃をする事ができる。")
BERSERK_TEXT = (
    "このカードは「デーモンとの駆け引き」の効果でのみ特殊召喚が可能。"
    "相手フィールド上の全てのモンスターに１回ずつ攻撃が可能。"
    "自分のターンのエンドフェイズ毎にこのカードの攻撃力は５００ポイントダウンする。")
SERVAL_HAWK_TEXT = (
    "このカードは直接攻撃できない。自分の墓地に「幻獣機」と名のついたモンスター以外の"
    "モンスターが存在する場合、このカードは攻撃できない。このカードのレベルは自分フィールド上の"
    "「幻獣機トークン」のレベルの合計分だけ上がる。自分フィールド上にトークンが存在する限り、"
    "このカードは戦闘及び効果では破壊されない。また、１ターンに１度、トークン１体をリリースして"
    "発動できる。自分または相手の墓地のカード１枚を選択してゲームから除外する。")
KINO_TEXT = (
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：自分フィールドに「蟲惑魔」モンスターが存在する場合、自分・相手のメインフェイズに"
    "発動できる。このカードを手札から特殊召喚する。この効果の発動後、ターン終了時まで自分は"
    "昆虫族・植物族モンスターしかEXデッキから特殊召喚できない。\n"
    "②：このカードはモンスターゾーンに存在する限り、「ホール」通常罠カード及び"
    "「落とし穴」通常罠カードの効果を受けない。\n"
    "③：自分の魔法＆罠ゾーンの裏側表示カードはそれぞれ１ターンに１度だけ効果では破壊されない。")
WATER_STAGE_TEXT = (
    "①：自分フィールドの水属性モンスターは、水属性以外のモンスターとの戦闘では破壊されない。"
    "②：自分フィールドの「アクアアクトレス」モンスターは相手モンスターの効果を受けない。"
    "③：このカードがフィールドから墓地へ送られた場合、自分の墓地の水族モンスター１体を"
    "対象として発動できる。そのモンスターを特殊召喚する。この効果の発動後、ターン終了時まで"
    "自分は水族モンスターしか特殊召喚できない。")

RESISTANCE_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0x4c, "hex": "0x4c", "names_ja": ["落とし穴"], "name_zh": "落穴",
     "source": "strings.conf"},
    {"setcode": 0x89, "hex": "0x89", "names_ja": ["ホール"], "name_zh": "空洞",
     "source": "strings.conf"},
    {"setcode": 0xcd, "hex": "0xcd", "names_ja": ["アクアアクトレス"], "name_zh": "水伶女",
     "source": "strings.conf"},
    {"setcode": 0x101b, "hex": "0x101b", "names_ja": ["幻獣機"], "name_zh": "幻獸機",
     "source": "strings.conf"},
    {"setcode": 0x108a, "hex": "0x108a", "names_ja": ["蟲惑魔"], "name_zh": "蟲惑魔",
     "source": "strings.conf"},
]


class ResistanceCase(unittest.TestCase):
    """共用:建結構、查命中卡號、讀命中段的格。"""
    CARDS = []
    FAQ = []

    @classmethod
    def setUpClass(cls):
        cls.cards = cls.CARDS
        cls.structures, _ = build_structures(cls.cards, cls.FAQ, RESISTANCE_ARCHETYPES)

    def hits(self, **query):
        return [h["id"] for h in run_query(self.structures, self.cards, query)["hits"]]

    def hit_segments(self, cid, **query):
        """命中段的段物件:錨定在查詢結果上,再讀段的格。"""
        result = run_query(self.structures, self.cards, query)
        ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
        structure = self.structure(cid)
        return [seg for block in structure["blocks"] for _, seg in iter_segments(block)
                if seg["id"] in ids]

    def structure(self, cid):
        return next(c for c in self.structures if c["id"] == cid)


class AttackFamilyTest(ResistanceCase):
    """攻擊家族:攻擊 > 直接攻擊、多次攻擊、全體攻擊;永續許可擴到攻擊家族(spec)。"""
    CARDS = [
        card(ELEKIRIN, name_ja="エレキリン", level=4, race=0x1000, attribute=0x10,
             atk=1200, setcode=0xe, **{"def": 100}),
        card(MASTER_MONK, name_ja="マスターモンク", level=5, race=0x100, attribute=0x1,
             atk=1900, **{"def": 1000}),
        card(3810071, name_ja="モンク・ファイター", level=3, race=0x100, attribute=0x1),
        card(BERSERK_DEAD_DRAGON, name_ja="バーサーク・デッド・ドラゴン", level=8,
             race=0x10, attribute=0x20, atk=3500, **{"def": 0}),
        card(6850209, name_ja="デーモンとの駆け引き", type=SPELL | 0x10000),
        card(SERVAL_HAWK, name_ja="幻獣機サーバルホーク", level=4, race=0x20,
             attribute=0x8, atk=2100, setcode=0x101b, **{"def": 100}),
    ]
    FAQ = [faq(ELEKIRIN, "エレキリン", ELEKIRIN_TEXT),
           faq(MASTER_MONK, "マスターモンク", MASTER_MONK_TEXT),
           faq(BERSERK_DEAD_DRAGON, "バーサーク・デッド・ドラゴン", BERSERK_TEXT),
           faq(SERVAL_HAWK, "幻獣機サーバルホーク", SERVAL_HAWK_TEXT)]

    def test_direct_attack_permission(self):
        hits = self.hits(actions=["直接攻擊"], polarities=["可以"])
        self.assertIn(ELEKIRIN, hits)
        self.assertNotIn(MASTER_MONK, hits)

    def test_multiple_attacks_record_times(self):
        self.assertIn(MASTER_MONK, self.hits(actions=["多次攻擊"], polarities=["可以"]))
        segs = self.hit_segments(MASTER_MONK, actions=["多次攻擊"], polarities=["可以"])
        self.assertEqual([seg["times"]["value"] for seg in segs], [2])

    def test_attack_all_monsters(self):
        self.assertIn(BERSERK_DEAD_DRAGON,
                      self.hits(actions=["全體攻擊"], polarities=["可以"]))

    def test_cannot_attack_includes_cannot_direct_attack(self):
        self.assertIn(SERVAL_HAWK, self.hits(actions=["攻擊"], polarities=["不能"]))

    def test_attack_permission_covers_the_whole_family(self):
        hits = self.hits(actions=["攻擊"], polarities=["可以"])
        for cid in (ELEKIRIN, MASTER_MONK, BERSERK_DEAD_DRAGON):
            self.assertIn(cid, hits)
        self.assertNotIn(SERVAL_HAWK, hits)

    def test_attack_power_is_not_an_attack_literal(self):
        """「攻撃力は５００ポイントダウンする」(解析不出)不因字面含「攻撃」列進查「攻擊」的未解析組。"""
        result = run_query(self.structures, self.cards, {"actions": ["攻擊"]})
        self.assertNotIn(BERSERK_DEAD_DRAGON, result["groups"]["未解析"])

    def test_attack_family_segments_pass_reverse_check(self):
        """マスターモンク ③、バーサーク ② 的攻擊段寫得回原文。"""
        for cid in (MASTER_MONK, BERSERK_DEAD_DRAGON):
            failed = {f["segment"] for f in check_card(self.structure(cid))}
            for seg in self.hit_segments(cid, actions=["攻擊"], polarities=["可以"]):
                self.assertNotIn(seg["id"], failed)


class KinoTest(ResistanceCase):
    """キノの蟲惑魔 75416738(標準卡,m2 票 04)。"""
    CARDS = [card(KINO, name_ja="キノの蟲惑魔", level=4, race=0x800, attribute=0x1,
                  atk=1300, setcode=0x108a, **{"def": 1500})]
    FAQ = [faq(KINO, "キノの蟲惑魔", KINO_TEXT)]

    def test_only_special_summon_from_extra_deck_after_activation(self):
        """①:「特殊召喚,只能,從額外牌組」命中,期間本回合、range 發動後。"""
        query = {"actions": ["特殊召喚"], "polarities": ["只能"], "from_zones": ["額外牌組"]}
        self.assertIn(KINO, self.hits(**query))
        durations = [seg["duration"] for seg in self.hit_segments(KINO, **query)]
        self.assertEqual([(d["kind"], d.get("range")) for d in durations],
                         [("本回合", "發動後")])

    def test_unaffected_by_hole_and_trap_hole_while_in_monster_zone(self):
        """②:「受到效果影響,不會」命中;原因帶字段物件(ホール、落とし穴),前提「限り」。"""
        query = {"actions": ["受到效果影響"], "polarities": ["不會"]}
        self.assertIn(KINO, self.hits(**query))
        (seg,) = self.hit_segments(KINO, **query)
        self.assertEqual(seg["cause"]["kind"], "效果")
        objects = {o["id"]: o for o in self.structure(KINO)["objects"]}
        setcodes = [atom["setcodes"]
                    for obj_id in seg["cause"]["objects"]
                    for atom in objects[obj_id]["condition"]["args"]
                    if atom.get("op") == "字段"]
        self.assertEqual(setcodes, [[0x89], [0x4c]])
        self.assertEqual(seg["premise"]["form"].rstrip("、"), "限り")

    def test_set_cards_not_destroyed_by_effects_once_per_turn(self):
        """③:「破壞,不會」命中、原因效果、`per_turn` 1。"""
        query = {"actions": ["破壞"], "polarities": ["不會"]}
        self.assertIn(KINO, self.hits(**query))
        (seg,) = self.hit_segments(KINO, **query)
        self.assertEqual(seg["cause"]["kind"], "效果")
        self.assertEqual(seg["per_turn"]["value"], 1)

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure(KINO)), [])


class WaterStageTest(ResistanceCase):
    """水舞台 29047353(標準卡,m2 票 04)。"""
    CARDS = [card(WATER_STAGE, name_ja="水舞台", type=SPELL | 0x80000)]
    FAQ = [faq(WATER_STAGE, "水舞台", WATER_STAGE_TEXT)]

    def test_not_destroyed_by_battle_with_non_water_monsters(self):
        """①:「破壞,不會」命中,原因戰鬥、帶物件(水属性以外のモンスター)。"""
        query = {"actions": ["破壞"], "polarities": ["不會"]}
        self.assertIn(WATER_STAGE, self.hits(**query))
        (seg,) = self.hit_segments(WATER_STAGE, **query)
        self.assertEqual(seg["cause"]["kind"], "戰鬥")
        objects = {o["id"]: o for o in self.structure(WATER_STAGE)["objects"]}
        (opponent,) = seg["cause"]["objects"]
        self.assertEqual(objects[opponent]["condition"]["args"][0],
                         {"op": "非", "arg": {"op": "屬性比較", "attr": "屬性", "cmp": "=",
                                              "value": "水"}})

    def test_aqua_actress_unaffected_by_opponent_monster_effects(self):
        """②:「受到效果影響,不會」命中。"""
        self.assertIn(WATER_STAGE,
                      self.hits(actions=["受到效果影響"], polarities=["不會"]))

    def test_summon_restriction_after_activation(self):
        """③ 句尾:「特殊召喚,只能」命中;查「特殊召喚」(預設極性做)命中的是前一句。"""
        self.assertIn(WATER_STAGE, self.hits(actions=["特殊召喚"], polarities=["只能"]))

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure(WATER_STAGE)), [])


KOZMO_FORERUNNER = 20849090  # Kozmo－フォアランナー
PUMPKIN_CARRIAGE = 14512825  # カボチャの馬車


class TargetingImmunityTest(ResistanceCase):
    """取對象只用在非「做」的段(spec「新增動作詞「取對象」只用在非「做」嗎?」)。"""
    CARDS = [
        card(KOZMO_FORERUNNER, name_ja="Kozmo－フォアランナー", level=7),
        card(PUMPKIN_CARRIAGE, name_ja="カボチャの馬車", level=4),
        card(23440231, name_ja="シンデレラ", level=4),
        card(13790603, name_ja="シュトロームベルクの金の城", type=SPELL | 0x80000),
    ]
    FAQ = [
        faq(KOZMO_FORERUNNER, "Kozmo－フォアランナー",
            "①：このカードは相手の効果の対象にならない。②：自分スタンバイフェイズに発動する。"
            "自分は１０００LP回復する。③：このカードが戦闘・効果で破壊され墓地へ送られた場合、"
            "墓地のこのカードを除外して発動できる。デッキからレベル６以下の「Kozmo」モンスター"
            "１体を特殊召喚する。"),
        faq(PUMPKIN_CARRIAGE, "カボチャの馬車",
            "①：このカードがモンスターゾーンに存在する限り、自分の「シンデレラ」は直接攻撃できる。"
            "②：このカードがモンスターゾーンに存在する限り、自分フィールドの"
            "「シュトロームベルクの金の城」は効果では破壊されず、相手の効果の対象にならない。"),
    ]

    def test_cannot_be_targeted_by_opponent_effects(self):
        query = {"actions": ["取對象"], "polarities": ["不會"]}
        hits = self.hits(**query)
        self.assertIn(KOZMO_FORERUNNER, hits)
        self.assertIn(PUMPKIN_CARRIAGE, hits)
        (seg,) = self.hit_segments(KOZMO_FORERUNNER, **query)
        self.assertEqual((seg["cause"]["kind"], seg["cause"]["side"]), ("效果", "對手"))

    def test_targeting_is_never_a_done_action(self):
        self.assertEqual(self.hits(actions=["取對象"]), [])

    def test_resistance_segments_pass_reverse_check(self):
        """Kozmo ①、馬車 ② 兩截(效果では破壊されず/相手の効果の対象にならない)寫得回原文。"""
        for cid in (KOZMO_FORERUNNER, PUMPKIN_CARRIAGE):
            failed = {f["segment"] for f in check_card(self.structure(cid))}
            segs = self.hit_segments(cid, actions=["取對象"], polarities=["不會"])
            segs += self.hit_segments(cid, actions=["破壞"], polarities=["不會"])
            self.assertTrue(segs)
            for seg in segs:
                self.assertNotIn(seg["id"], failed)


CHIMERATECH_FORTRESS = 79229522   # キメラテック・フォートレス・ドラゴン
BLUE_EYES_HEART = 54475145        # 心宿りし青眼竜
PETAL_ELF = 68625727              # 占術姫ペタルエルフ
PAZUZULE = 77384395               # パズズル


class LockTest(ResistanceCase):
    """作為素材、變更控制權、變更表示形式的「不能」;「無効化」併進無效(spec 故事 7)。"""
    CARDS = [
        card(CHIMERATECH_FORTRESS, name_ja="キメラテック・フォートレス・ドラゴン",
             type=EFFECT_MONSTER | 0x40, level=8, race=0x20, attribute=0x20, atk=0),
        card(70095154, name_ja="サイバー・ドラゴン", level=5, race=0x20, attribute=0x10),
        card(BLUE_EYES_HEART, name_ja="心宿りし青眼竜", level=8),
        card(PETAL_ELF, name_ja="占術姫ペタルエルフ", level=2),
        card(PAZUZULE, name_ja="パズズル", level=1),
    ]
    FAQ = [
        faq(CHIMERATECH_FORTRESS, "キメラテック・フォートレス・ドラゴン",
            "「サイバー・ドラゴン」＋機械族モンスター１体以上\n"
            "自分・相手フィールドの上記のカードを墓地へ送った場合のみEXデッキから特殊召喚できる。\n"
            "このカードは融合素材にできない。\n"
            "①：このカードの元々の攻撃力は、このカードの融合素材としたモンスターの数×１０００になる。"),
        faq(BLUE_EYES_HEART, "心宿りし青眼竜", "②：このカードのコントロールは変更できない。"),
        faq(PETAL_ELF, "占術姫ペタルエルフ",
            "①：このカードがリバースした場合に発動できる。相手フィールドの表側攻撃表示モンスターを"
            "全て守備表示にする。この効果で守備表示になったモンスターは表示形式を変更できない。"),
        faq(PAZUZULE, "パズズル",
            "①：このカードがモンスターゾーンに存在する限り、自分のモンスターのP召喚は無効化されない。"),
    ]

    def test_cannot_be_material_is_a_restriction_in_summon_condition_block(self):
        """召喚條件區塊裡的抗性段改成限制(同 m1 票 09)。"""
        self.assertIn(CHIMERATECH_FORTRESS,
                      self.hits(actions=["作為素材"], polarities=["不能"], kinds=["限制"]))

    def test_control_cannot_change(self):
        self.assertIn(BLUE_EYES_HEART, self.hits(actions=["變更控制權"], polarities=["不能"]))
        self.assertEqual(check_card(self.structure(BLUE_EYES_HEART)), [])

    def test_display_form_cannot_change(self):
        self.assertIn(PETAL_ELF, self.hits(actions=["變更表示形式"], polarities=["不能"]))

    def test_mukouka_is_negate(self):
        """「無効化されない」的字面認得是無效:物件還解析不出時列在查「無效」的未解析組。"""
        result = run_query(self.structures, self.cards,
                           {"actions": ["無效"], "polarities": ["不會"]})
        self.assertIn(PAZUZULE, result["groups"]["未解析"])


if __name__ == "__main__":
    unittest.main()
