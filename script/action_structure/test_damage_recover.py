"""傷害與回復:動作詞傷害(与える/受ける 同一詞)、回復,傷害值變更記成性質變更 `attr` 傷害。

走接縫一(查詢判斷)與接縫二(反向檢查)。spec「查詢判斷」只加 `modified` 欄,「受方對手」「原因戰鬥」
「施事是物件0」這類條件先用既有欄查到命中段,再讀命中段的格(`hit_segments`)。
官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, card, faq

FLAMVELL_DEVIL = 91711547   # フレムベル・デビル
FLAMVELL_DEVIL_TEXT = (
    "このカードが相手ライフに戦闘ダメージを与えた時、自分の墓地の炎族モンスターの数×２００"
    "ポイントダメージを相手ライフに与える。")
ECO = 4192696   # 森の聖霊 エーコ
ECO_TEXT = (
    "相手のカードの効果によって自分がダメージを受けた時に発動できる。このカードを手札から"
    "特殊召喚し、受けたダメージと同じダメージを相手ライフに与える。さらに、このターンお互いが"
    "受ける効果ダメージは０になる。")
LAVA_GOLEM = 102380   # 溶岩魔神ラヴァ・ゴーレム
LAVA_GOLEM_TEXT = (
    "このカードは通常召喚できない。\n相手フィールドのモンスター２体をリリースした場合に"
    "相手フィールドに特殊召喚できる。\nこのカードを特殊召喚するターン、自分は通常召喚できない。"
    "\n①：自分スタンバイフェイズに発動する。自分は１０００ダメージを受ける。")
RECOVER_CARD = 10000601   # 合成卡:回復句(全庫 49 段「自分はNLP回復する」的寫法)
RECOVER_TEXT = "①：自分メインフェイズに発動できる。自分は１０００LP回復する。"
SYNTHETIC = 10000602   # 合成卡:各句型一句
YUBEL = 78371393   # ユベル
YUBEL_TEXT = (
    "①：このカードは戦闘では破壊されず、このカードの戦闘で発生する自分への戦闘ダメージは"
    "０になる。\n②：攻撃表示のこのカードが攻撃対象に選択された場合、そのダメージ計算前に"
    "発動する。攻撃モンスターの攻撃力分のダメージを相手に与える。\n③：自分エンドフェイズに"
    "発動する。自分フィールドの他のモンスター１体をリリースするか、このカードを破壊する。\n"
    "④：この③の効果以外でこのカードが破壊された時に発動できる。自分の手札・デッキ・墓地から"
    "「ユベル－Das Abscheulich Ritter」１体を特殊召喚する。")
ODD_EYES = 75787708   # 四天の龍 オッドアイズ・ペンデュラム・ドラゴン
ODD_EYES_TEXT = (
    "このカード名の②のモンスター効果は１ターンに１度しか使用できない。\n①：P召喚した"
    "このカードは以下の効果を得る。\n●自分のPゾーンにカードが２枚存在する限り、そのPスケールの"
    "差×３００だけ、このカードの攻撃力はアップする。\n●このカードの戦闘で発生する相手への"
    "戦闘ダメージは倍になる。\n②：モンスターゾーンのこのカードが戦闘・効果で破壊された場合に"
    "発動できる。このカードを手札に加える。このカードが相手によって破壊されていた場合、"
    "さらにこのカードを特殊召喚できる。")
CLOCK_TOWER = 75041269   # 幽獄の時計塔
CLOCK_TOWER_TEXT = (
    "相手ターンのスタンバイフェイズ時に、このカードに時計カウンターを１個乗せる。"
    "時計カウンターの合計が４個以上になった場合、このカードのコントローラーは戦闘ダメージを"
    "受けない。時計カウンターが４個以上乗ったこのカードが破壊され墓地へ送られた時、手札または"
    "デッキから「D-HERO ドレッドガイ」１体を特殊召喚する。")
TRAPEZE = 17016362   # Emトラピーズ・マジシャン
TRAPEZE_TEXT = (
    "魔法使い族レベル４モンスター×２\n①：このカードがモンスターゾーンに存在する限り、"
    "自分はこのカードの攻撃力以下の戦闘・効果ダメージを受けない。\n②：自分・相手のメイン"
    "フェイズ１に１度、このカードのX素材を１つ取り除き、ターンプレイヤーのフィールドの他の"
    "表側攻撃表示モンスター１体を対象として発動できる。このターン、そのモンスターは２回攻撃でき、"
    "バトルフェイズ終了時に破壊される。\n③：このカードが戦闘または相手の効果で破壊され墓地へ"
    "送られた場合に発動できる。デッキから「Em」モンスター１体を特殊召喚する。")


def build(*entries):
    cards = [card(cid, name_ja=name, **kw) for cid, name, _, kw in entries]
    structures, _ = build_structures(
        cards, [faq(cid, name, text) for cid, name, text, _ in entries], ARCHETYPES)
    return cards, structures


def hit_segments(cards, structures, cid, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    structure = next(s for s in structures if s["id"] == cid)
    return [seg for block in structure["blocks"] for _, seg in iter_segments(block)
            if seg["id"] in ids]


def side_of(recipient):
    return recipient["side"] if isinstance(recipient, dict) else recipient


class FlamvellDevilTest(unittest.TestCase):
    """フレムベル・デビル 91711547:戰鬥傷害觸發、算式傷害。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (FLAMVELL_DEVIL, "フレムベル・デビル", FLAMVELL_DEVIL_TEXT,
             {"level": 5, "race": 0x8, "attribute": 0x4, "atk": 2100, "def": 1200}))

    def test_battle_damage_condition_is_dealt_by_this_card_to_opponent(self):
        """條件段「傷害,原因戰鬥,受方對手」命中,施事是物件0。"""
        segs = hit_segments(self.cards, self.structures, FLAMVELL_DEVIL,
                            actions=["傷害"], include_condition=True, kinds=["條件"])
        self.assertEqual(len(segs), 1)
        seg = segs[0]
        self.assertEqual(seg["cause"]["kind"], "戰鬥")
        self.assertEqual(side_of(seg["recipient"]), "對手")
        self.assertEqual([(l["object"], l["role"]) for l in seg["lines"]], [("o0", "施事")])

    def test_formula_damage_to_opponent(self):
        """效果段「傷害,受方對手」命中,amount 是算式字面。"""
        segs = hit_segments(self.cards, self.structures, FLAMVELL_DEVIL, actions=["傷害"])
        self.assertEqual(len(segs), 1)
        self.assertEqual(side_of(segs[0]["recipient"]), "對手")
        self.assertEqual(segs[0]["amount"], {"kind": "算式",
                                             "text": "自分の墓地の炎族モンスターの数×２００ポイント"})

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structures[0]), [])


class EcoForestSpiritTest(unittest.TestCase):
    """森の聖霊 エーコ 4192696:受到傷害的條件、回彈傷害、傷害值變成 0。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (ECO, "森の聖霊 エーコ", ECO_TEXT,
             {"level": 4, "race": 0x400, "attribute": 0x1, "atk": 1700, "def": 1000}))

    def test_condition_damage_to_me_by_opponent_effect(self):
        """「傷害,受方我方」(條件段開)命中,原因是對手的效果。"""
        segs = [seg for seg in hit_segments(self.cards, self.structures, ECO, actions=["傷害"],
                                            include_condition=True)
                if side_of(seg["recipient"]) == "我方"]
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["kind"], "條件")
        self.assertEqual((segs[0]["cause"]["kind"], segs[0]["cause"].get("side")), ("效果", "對手"))

    def test_damage_to_opponent(self):
        segs = hit_segments(self.cards, self.structures, ECO, actions=["傷害"])
        self.assertEqual([side_of(seg["recipient"]) for seg in segs], ["對手"])

    def test_effect_damage_becomes_zero_for_both_players_this_turn(self):
        """「性質變更,屬性傷害,數值 0」命中:受方雙方各自、原因效果、期間本回合。"""
        segs = hit_segments(self.cards, self.structures, ECO, actions=["性質變更"],
                            modified={"attr": "傷害", "form": "數值", "value": 0})
        self.assertEqual(len(segs), 1)
        seg = segs[0]
        self.assertEqual(side_of(seg["recipient"]), "雙方各自")
        self.assertEqual(seg["cause"]["kind"], "效果")
        self.assertEqual(seg["duration"]["kind"], "本回合")

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structures[0]), [])


class SelfDamageAndRecoverTest(unittest.TestCase):
    """玩家主語是受方、不建物件;回復形狀同傷害。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (LAVA_GOLEM, "溶岩魔神ラヴァ・ゴーレム", LAVA_GOLEM_TEXT,
             {"type": 0x2000021, "level": 8, "race": 0x8, "attribute": 0x4, "atk": 3000,
              "def": 2500}),
            (RECOVER_CARD, "甲", RECOVER_TEXT, {}))

    def test_lava_golem_damages_its_controller_without_object(self):
        """「自分は１０００ダメージを受ける」:受方我方、沒有物件。"""
        segs = hit_segments(self.cards, self.structures, LAVA_GOLEM, actions=["傷害"])
        self.assertEqual(len(segs), 1)
        self.assertEqual(side_of(segs[0]["recipient"]), "我方")
        self.assertEqual((segs[0]["lines"], segs[0]["agent"]), ([], None))
        self.assertEqual(segs[0]["amount"]["value"], 1000)

    def test_lava_golem_damage_segment_passes_reverse_check(self):
        lava = next(s for s in self.structures if s["id"] == LAVA_GOLEM)
        failing = {f["segment"] for f in check_card(lava)}
        seg = hit_segments(self.cards, self.structures, LAVA_GOLEM, actions=["傷害"])[0]
        self.assertNotIn(seg["id"], failing)

    def test_recover_to_me(self):
        """回復句「〜LP回復する」查「回復,受方我方」命中。"""
        segs = hit_segments(self.cards, self.structures, RECOVER_CARD, actions=["回復"])
        self.assertEqual([side_of(seg["recipient"]) for seg in segs], ["我方"])
        self.assertEqual(check_card(next(s for s in self.structures
                                         if s["id"] == RECOVER_CARD)), [])


class DamageModifyTest(unittest.TestCase):
    """傷害值變更(０になる、倍になる、受けない)是性質變更 attr 傷害,查「傷害」不命中。"""

    @classmethod
    def setUpClass(cls):
        cls.cards, cls.structures = build(
            (YUBEL, "ユベル", YUBEL_TEXT,
             {"level": 10, "race": 0x8, "attribute": 0x20, "atk": 0, "def": 0}),
            (ODD_EYES, "四天の龍 オッドアイズ・ペンデュラム・ドラゴン", ODD_EYES_TEXT,
             {"type": 0x1000021, "level": 7, "race": 0x2000, "attribute": 0x20, "atk": 2500,
              "def": 2000}),
            (CLOCK_TOWER, "幽獄の時計塔", CLOCK_TOWER_TEXT, {"type": 0x80002}),
            (TRAPEZE, "Emトラピーズ・マジシャン", TRAPEZE_TEXT,
             {"type": 0x800021, "level": 4, "race": 0x2, "attribute": 0x10, "atk": 2500,
              "def": 2000}))

    def modify_hits(self, cid, **modified):
        return hit_segments(self.cards, self.structures, cid, actions=["性質變更"],
                            modified={"attr": "傷害", **modified})

    def block_label(self, cid, seg):
        structure = next(s for s in self.structures if s["id"] == cid)
        return next(b["label"] for b in structure["blocks"]
                    if any(s["id"] == seg["id"] for _, s in iter_segments(b)))

    def test_yubel_battle_damage_becomes_zero(self):
        """ユベル ①:「性質變更,屬性傷害,數值 0」命中、「傷害」不命中。"""
        segs = self.modify_hits(YUBEL, form="數值", value=0)
        self.assertEqual([self.block_label(YUBEL, s) for s in segs], ["①"])
        damage = hit_segments(self.cards, self.structures, YUBEL, actions=["傷害"],
                              include_condition=True)
        self.assertNotIn("①", [self.block_label(YUBEL, s) for s in damage])

    def test_yubel_is_not_unparsed_for_damage(self):
        """m2 票 07 驗收第一條後半:查「傷害」時ユベル不在未解析組(② 的效果段命中傷害)。"""
        result = run_query(self.structures, self.cards, {"actions": ["傷害"]})
        self.assertNotIn(YUBEL, result["groups"]["未解析"])
        self.assertIn(YUBEL, result["groups"]["全部"])

    def test_odd_eyes_doubles_battle_damage(self):
        """四天の龍 オッドアイズ:「倍になる」「性質變更,屬性傷害」命中、「傷害」不命中。"""
        self.assertEqual([s["modified"]["form"] for s in self.modify_hits(ODD_EYES)], ["倍"])
        self.assertEqual(hit_segments(self.cards, self.structures, ODD_EYES, actions=["傷害"],
                                      include_condition=True), [])

    def test_clock_tower_takes_no_battle_damage(self):
        """幽獄の時計塔:「受けない」記數值 0、predicate 寫回「受けない」。"""
        segs = self.modify_hits(CLOCK_TOWER, form="數值", value=0)
        self.assertEqual([s["predicate"] for s in segs], ["受けない"])
        tower = next(s for s in self.structures if s["id"] == CLOCK_TOWER)
        self.assertNotIn(segs[0]["id"], {f["segment"] for f in check_card(tower)})

    def test_trapeze_magician_has_damage_limit(self):
        """Emトラピーズ・マジシャン:門檻「このカードの攻撃力以下の」記在 limit。"""
        segs = self.modify_hits(TRAPEZE, form="數值", value=0)
        self.assertEqual([s["modified"].get("limit") for s in segs],
                         [{"cmp": "≤", "text": "このカードの攻撃力以下の"}])


class DamageTemplateTest(unittest.TestCase):
    """常見寫法各一句(全庫真實句型)整張通過反向檢查:受方寫在名詞前/述語前、原因寫在受方後、
    雙方各自、回復的三種接法、「相手に与える」的變更、寫在受方前的算式「〜だけ」。"""

    TEXT = (
        "①：このカードが相手に戦闘ダメージを与えた時に発動できる。相手に５００ダメージを与える。"
        "②：自分が戦闘・効果でダメージを受けた場合に発動できる。お互いのプレイヤーは１０００"
        "ダメージを受ける。③：自分メインフェイズに発動できる。その数値分だけ自分のLPを回復する。"
        "④：自分メインフェイズに発動できる。相手は１０００LP回復する。⑤：このカードがモンスター"
        "ゾーンに存在する限り、相手に与える戦闘ダメージは半分になる。⑥：自分のLPが回復した時に"
        "発動できる。その守備力を攻撃力が超えた分だけ相手に戦闘ダメージを与える。")

    def test_whole_card_passes_reverse_check(self):
        cards, structures = build((SYNTHETIC, "甲", self.TEXT, {}))
        self.assertEqual(check_card(structures[0]), [])
        recipients = [side_of(seg["recipient"])
                      for seg in hit_segments(cards, structures, SYNTHETIC,
                                              actions=["傷害"], include_condition=True)]
        self.assertEqual(recipients, ["對手", "對手", "我方", "雙方各自", "對手"])


BYE_BYE_DAMAGE = 20735371   # バイバイダメージ
BYE_BYE_DAMAGE_TEXT = (
    "①：自分のモンスターが攻撃されたダメージ計算時に発動できる。その自分のモンスターはその戦闘"
    "では破壊されない。その戦闘で自分が戦闘ダメージを受けた時、相手はその数値の倍の効果ダメージを"
    "受ける。")


class CauseWrittenTwiceTest(unittest.TestCase):
    """「その戦闘で自分が戦闘ダメージを受けた時」:原因寫在述語前(その戦闘で)又寫在名詞(戦闘ダメージ),
    不猜哪一處算數;未解析組列的原因是「同一格寫了兩處」,不是一般的原因解析不出。"""

    def test_unparsed_reason_says_written_twice(self):
        cards = [card(BYE_BYE_DAMAGE, name_ja="バイバイダメージ", type=0x4)]
        structures, _ = build_structures(
            cards, [faq(BYE_BYE_DAMAGE, "バイバイダメージ", BYE_BYE_DAMAGE_TEXT)])
        result = run_query(structures, cards, {"actions": ["傷害"], "include_condition": True})
        reasons = {seg["text"]: seg["reason"] for entry in result["unparsed"]
                   for seg in entry["segments"]}
        self.assertEqual(reasons.get("その戦闘で自分が戦闘ダメージを受けた時"), "同一格寫了兩處")


if __name__ == "__main__":
    unittest.main()
