"""受方與原因(action-search-web 票 11;spec「比對規則」的受方與原因)。

接縫一(查詢判斷 `run_query`)。查詢鍵:`recipient`(我方/對手)、`cause`(種類,或
`{"kind", "side"}` 再給是哪一方的),沒寫原因的被動句用票 10 的不限定開關 `include_unrestricted`。
- 受方:只比受方是玩家的段;受方是卡的段、沒有受方的段,在查詢給了受方時不命中。寫雙方各自的涵蓋兩方。
- 原因的種類:寫的和查的相同命中;寫戰鬥或效果時查戰鬥、查效果都命中;寫戰鬥以外時查效果命中、
  查戰鬥不命中;其餘寫什麼比什麼。哪一方:段沒寫方時命中,寫了就要相同或是雙方各自。
- 沒寫原因:被動句是不限定,開關開才命中;主動句不命中。
- 兩者都是段的欄,比的是段;對未解析組不生效。
標準卡(待站主核可,見票 11 的 Comments);官方文本逐字寫在測試裡。
"""
import json
import unittest

from action_index import build_action_index, decode_action_index
from action_query import run_query
from action_rows import flatten
from card_structure import build_structures
from structure_shape import iter_segments
from test_golden import ARCHETYPES, SPELL, TRAP, card, faq
from test_web_parity import front_end

POISON_SCORPION = 212652     # 毒サソリの罠
LAVA_GOLEM = 102380          # 溶岩魔神ラヴァ・ゴーレム
BUSTER_SNIPER = 39015        # バスター・スナイパー
CHOPMAN = 40884383           # 凶悪犯－チョップマン
MIRACLE_FLIPPER = 131182     # ミラクル・フリッパー
ANKURIBOH = 595626           # アンクリボー
LANCELOD = 123709            # ラヴァル・ランスロッド
LIMIT_REVERSE = 27551        # リミット・リバース
GOD_BINDING = 269012         # 神縛りの塚
SERPENT_DESCENT = 16067089   # 蛇神降臨
DARK_MAGIC_EXPANDED = 111280  # 黒魔導強化

POISON_SCORPION_TEXT = (
    "①：相手モンスターの直接攻撃宣言時に発動できる。そのモンスターを破壊する。"
    "その後、相手に３００ダメージを与える。")
LAVA_GOLEM_TEXT = (
    "このカードは通常召喚できない。\n"
    "相手フィールドのモンスター２体をリリースした場合に相手フィールドに特殊召喚できる。\n"
    "このカードを特殊召喚するターン、自分は通常召喚できない。\n"
    "①：自分スタンバイフェイズに発動する。自分は１０００ダメージを受ける。")
BUSTER_SNIPER_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：このカードをリリースして発動できる。手札・デッキから「バスター・スナイパー」以外の"
    "「バスター・モード」のカード名が記されたモンスター１体を特殊召喚する。この効果を発動したターン、"
    "自分はSモンスターしかEXデッキから特殊召喚できない。"
    "②：自分フィールドの表側表示モンスター１体を対象として発動できる。EXデッキのSモンスター１体を"
    "相手に見せ、対象のモンスターの種族・属性はターン終了時まで、見せたモンスターと同じになる。")
CHOPMAN_TEXT = (
    "このカードが反転召喚に成功した時、自分の墓地の装備魔法カード１枚をこのカードに装備する事ができる。")
MIRACLE_FLIPPER_TEXT = (
    "「ミラクル・フリッパー」が自分フィールド上に存在する場合、このカードは召喚・反転召喚・特殊召喚"
    "できない。このカードがフィールド上に表側表示で存在する限り、相手は他の表側表示のモンスターを"
    "攻撃対象に選択できない。このカードが戦闘によって破壊された場合、このカードを相手フィールド上に"
    "特殊召喚する。このカードが魔法・罠の効果によって破壊された場合、相手フィールド上のモンスター"
    "１体を破壊する。")
ANKURIBOH_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：相手モンスターの攻撃宣言時にこのカードを手札から捨て、このカード以外の自分または相手の墓地の"
    "モンスター１体を対象として発動できる。そのモンスターを自分フィールドに特殊召喚する。"
    "この効果で特殊召喚したモンスターはエンドフェイズに墓地へ送られる。"
    "②：このカードが戦闘・効果で破壊され墓地へ送られた場合に発動できる。このターンのエンドフェイズに、"
    "自分のデッキ・墓地から「死者蘇生」１枚を選んで手札に加える。")
LANCELOD_TEXT = (
    "このカードはリリースなしで召喚できる。この方法で召喚したこのカードは、エンドフェイズ時に"
    "墓地へ送られる。フィールド上のこのカードが破壊され墓地へ送られた時、ゲームから除外されている"
    "自分の炎属性モンスター１体を選択して手札に加える事ができる。")
LIMIT_REVERSE_TEXT = (
    "自分の墓地の攻撃力１０００以下のモンスター１体を選択し、表側攻撃表示で特殊召喚する。"
    "そのモンスターが守備表示になった時、そのモンスターとこのカードを破壊する。"
    "このカードがフィールド上から離れた時、そのモンスターを破壊する。"
    "そのモンスターが破壊された時、このカードを破壊する。")
GOD_BINDING_TEXT = (
    "①：フィールドのレベル１０以上のモンスターは効果の対象にならず、効果では破壊されない。"
    "②：自分または相手のレベル１０以上のモンスターが戦闘でモンスターを破壊し墓地へ送った場合に"
    "発動する。破壊されたモンスターのコントローラーは１０００ダメージを受ける。"
    "③：フィールドのこのカードが効果で破壊され墓地へ送られた時に発動できる。"
    "デッキから神属性モンスター１体を手札に加える。")
SERPENT_DESCENT_TEXT = (
    "自分フィールド上に表側表示で存在する「毒蛇王ヴェノミノン」が戦闘以外で破壊された時に発動できる。"
    "手札・デッキから「毒蛇神ヴェノミナーガ」１体を特殊召喚する。")
DARK_MAGIC_EXPANDED_TEXT = (
    "①：お互いのフィールド・墓地の「ブラック・マジシャン」「ブラック・マジシャン・ガール」の数によって"
    "以下の効果を適用する。●１体以上：フィールドの魔法使い族・闇属性モンスター１体を選び、"
    "その攻撃力をターン終了時まで１０００アップする。●２体以上：このターン、自分の魔法・罠カードの"
    "効果の発動に対して、相手は魔法・罠・モンスターの効果を発動できず、自分フィールドの魔法・罠カードは"
    "相手の効果では破壊されない。●３体以上：自分フィールドの魔法使い族・闇属性モンスターは"
    "ターン終了時まで相手の効果を受けない。")


def recipient_cause_cards():
    """(卡片總表, faq) 的夾具:受方與原因的標準卡。"""
    cards = [
        card(POISON_SCORPION, name_ja="毒サソリの罠", type=TRAP),
        card(LAVA_GOLEM, name_ja="溶岩魔神ラヴァ・ゴーレム", type=0x2000021, level=8, race=0x8,
             attribute=0x4, atk=3000, **{"def": 2500}),
        card(BUSTER_SNIPER, name_ja="バスター・スナイパー", level=4, race=0x8000, attribute=0x1,
             atk=1600, **{"def": 800}),
        card(CHOPMAN, name_ja="凶悪犯－チョップマン", type=0x21, level=3, race=0x10,
             attribute=0x20, atk=1100, **{"def": 500}),
        card(MIRACLE_FLIPPER, name_ja="ミラクル・フリッパー", type=0x21, level=2, race=0x2,
             attribute=0x10, atk=300, **{"def": 500}),
        card(ANKURIBOH, name_ja="アンクリボー", level=1, race=0x8, attribute=0x20, atk=300,
             **{"def": 200}),
        card(LANCELOD, name_ja="ラヴァル・ランスロッド", level=6, race=0x1, attribute=0x4,
             atk=2100, **{"def": 200}),
        card(LIMIT_REVERSE, name_ja="リミット・リバース", type=TRAP | 0x20000),
        card(GOD_BINDING, name_ja="神縛りの塚", type=SPELL | 0x80000),
        card(SERPENT_DESCENT, name_ja="蛇神降臨", type=TRAP),
        card(DARK_MAGIC_EXPANDED, name_ja="黒魔導強化", type=TRAP | 0x10000),
    ]
    faqs = [
        faq(POISON_SCORPION, "毒サソリの罠", POISON_SCORPION_TEXT),
        faq(LAVA_GOLEM, "溶岩魔神ラヴァ・ゴーレム", LAVA_GOLEM_TEXT),
        faq(BUSTER_SNIPER, "バスター・スナイパー", BUSTER_SNIPER_TEXT),
        faq(CHOPMAN, "凶悪犯－チョップマン", CHOPMAN_TEXT),
        faq(MIRACLE_FLIPPER, "ミラクル・フリッパー", MIRACLE_FLIPPER_TEXT),
        faq(ANKURIBOH, "アンクリボー", ANKURIBOH_TEXT),
        faq(LANCELOD, "ラヴァル・ランスロッド", LANCELOD_TEXT),
        faq(LIMIT_REVERSE, "リミット・リバース", LIMIT_REVERSE_TEXT),
        faq(GOD_BINDING, "神縛りの塚", GOD_BINDING_TEXT),
        faq(SERPENT_DESCENT, "蛇神降臨", SERPENT_DESCENT_TEXT),
        faq(DARK_MAGIC_EXPANDED, "黒魔導強化", DARK_MAGIC_EXPANDED_TEXT),
    ]
    return cards, faqs


class RecipientCauseCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards, faqs = recipient_cause_cards()
        cls.structures, _ = build_structures(cls.cards, faqs, ARCHETYPES)

    def result(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return self.result(**query)["groups"]["全部"]


class RecipientTest(RecipientCauseCase):
    """受方:只比受方是玩家的段。"""

    def test_damage_to_opponent_or_to_self(self):
        """毒サソリの罠「相手に３００ダメージを与える」、溶岩魔神ラヴァ・ゴーレム「自分は１０００ダメージを
        受ける」:受方 對手、傷害 命中前者不命中後者;受方 我方 相反。"""
        self.assertIn(POISON_SCORPION, self.hits(actions=["傷害"], recipient="對手"))
        self.assertNotIn(LAVA_GOLEM, self.hits(actions=["傷害"], recipient="對手"))
        self.assertIn(LAVA_GOLEM, self.hits(actions=["傷害"], recipient="我方"))
        self.assertNotIn(POISON_SCORPION, self.hits(actions=["傷害"], recipient="我方"))

    def test_recipient_other_than_damage(self):
        """バスター・スナイパー「EXデッキのSモンスター１体を相手に見せ」(受方寫「相手に」的展示):
        受方 對手 命中、我方 不命中。"""
        self.assertIn(BUSTER_SNIPER, self.hits(actions=["展示"], recipient="對手"))
        self.assertNotIn(BUSTER_SNIPER, self.hits(actions=["展示"], recipient="我方"))

    def test_card_recipient_does_not_hit(self):
        """凶悪犯－チョップマン「…装備魔法カード１枚をこのカードに装備する事ができる」(受方是卡):
        沒給受方命中;給了受方(我方或對手)都不命中。"""
        self.assertIn(CHOPMAN, self.hits(actions=["裝備"]))
        for side in ("我方", "對手"):
            with self.subTest(recipient=side):
                self.assertNotIn(CHOPMAN, self.hits(actions=["裝備"], recipient=side))

    def test_segment_without_recipient_does_not_hit(self):
        """毒サソリの罠的破壞段「そのモンスターを破壊する」沒有受方:受方 對手、破壞 不命中。"""
        self.assertNotIn(POISON_SCORPION, self.hits(actions=["破壞"], recipient="對手"))

    def test_recipient_must_be_a_side(self):
        with self.assertRaises(ValueError):
            self.result(actions=["傷害"], recipient="雙方各自")


class CauseKindTest(RecipientCauseCase):
    """原因的種類。"""

    BATTLE_DESTROYED = {"actions": ["破壞"], "include_condition": True, "cause": "戰鬥"}

    def test_battle_hits_battle_and_battle_or_effect(self):
        """原因 戰鬥、破壞、條件段:命中ミラクル・フリッパー「このカードが戦闘によって破壊された場合」
        與アンクリボー「このカードが戦闘・効果で破壊され墓地へ送られた場合」(戰鬥或效果)。"""
        hits = self.hits(**self.BATTLE_DESTROYED)
        self.assertIn(MIRACLE_FLIPPER, hits)
        self.assertIn(ANKURIBOH, hits)

    def test_active_destruction_without_cause_does_not_hit(self):
        """リミット・リバース「そのモンスターとこのカードを破壊する」(主動去破壞、沒寫原因):同一個查詢
        不命中;開了不限定開關也不命中(主動句沒寫原因不是不限定)。"""
        self.assertIn(LIMIT_REVERSE, self.hits(actions=["破壞"]))
        self.assertNotIn(LIMIT_REVERSE, self.hits(**self.BATTLE_DESTROYED))
        self.assertNotIn(LIMIT_REVERSE, self.hits(include_unrestricted=True,
                                                  **self.BATTLE_DESTROYED))

    def test_effect_hits_battle_or_effect(self):
        """原因 效果 也命中アンクリボー的「戦闘・効果で」;不命中ミラクル・フリッパー的「戦闘によって」。"""
        hits = self.hits(actions=["破壞"], include_condition=True, cause="效果")
        self.assertIn(ANKURIBOH, hits)
        self.assertNotIn(MIRACLE_FLIPPER, hits)

    def test_other_than_battle_counts_as_effect(self):
        """蛇神降臨「「毒蛇王ヴェノミノン」が戦闘以外で破壊された時」:原因 效果 命中、戰鬥 不命中。"""
        query = {"actions": ["破壞"], "include_condition": True}
        self.assertIn(SERPENT_DESCENT, self.hits(cause="效果", **query))
        self.assertNotIn(SERPENT_DESCENT, self.hits(cause="戰鬥", **query))

    def test_cause_kind_must_be_known(self):
        with self.assertRaises(ValueError):
            self.result(actions=["破壞"], cause="魔法")
        with self.assertRaises(ValueError):
            self.result(actions=["破壞"], cause={"kind": "效果", "side": "雙方各自"})


class UnwrittenCauseTest(RecipientCauseCase):
    """沒寫原因:被動句是不限定,不限定開關開才命中。"""

    def test_passive_without_cause_needs_the_switch(self):
        """ラヴァル・ランスロッド「フィールド上のこのカードが破壊され墓地へ送られた時」:原因 戰鬥、破壞、
        條件段預設不命中,開關開才命中。"""
        query = {"actions": ["破壞"], "include_condition": True, "cause": "戰鬥"}
        self.assertNotIn(LANCELOD, self.hits(**query))
        self.assertIn(LANCELOD, self.hits(include_unrestricted=True, **query))


class CauseSideTest(RecipientCauseCase):
    """原因的哪一方:段沒寫方時命中(寫得比查詢寬);寫了方就要相同。"""

    OPPONENT_EFFECT = {"actions": ["破壞"], "polarities": ["不會"],
                       "cause": {"kind": "效果", "side": "對手"}}

    def test_opponent_effect_resistance(self):
        """原因 效果、方 對手、極性 不會、破壞:命中黒魔導強化「…相手の効果では破壊されない」,也命中沒寫
        是誰的效果的神縛りの塚「効果では破壊されない」。"""
        hits = self.hits(**self.OPPONENT_EFFECT)
        self.assertIn(DARK_MAGIC_EXPANDED, hits)
        self.assertIn(GOD_BINDING, hits)

    def test_written_side_must_match(self):
        """查方 我方:黒魔導強化寫的是對手的效果,不命中;神縛りの塚沒寫方,照樣命中。"""
        hits = self.hits(actions=["破壞"], polarities=["不會"],
                         cause={"kind": "效果", "side": "我方"})
        self.assertNotIn(DARK_MAGIC_EXPANDED, hits)
        self.assertIn(GOD_BINDING, hits)

    def test_side_free_query_hits_any_side(self):
        """只給種類不給方:兩張都命中。"""
        hits = self.hits(actions=["破壞"], polarities=["不會"], cause="效果")
        self.assertIn(DARK_MAGIC_EXPANDED, hits)
        self.assertIn(GOD_BINDING, hits)


class SegmentColumnsTest(RecipientCauseCase):
    """受方與原因是段的欄,比的是段;沒給時行為不變;對未解析組不生效。"""

    def test_cause_is_compared_per_segment(self):
        """神縛りの塚③「フィールドのこのカードが効果で破壊され墓地へ送られた時」寫效果;查原因 戰鬥、
        破壞、條件段:②「…戦闘でモンスターを破壊し墓地へ送った場合」寫戰鬥(主動)命中,
        改查效果也命中(③);只查加入手牌、原因 效果 不命中(效果寫在條件段,加入手牌在另一段)。"""
        condition = {"actions": ["破壞"], "include_condition": True}
        self.assertIn(GOD_BINDING, self.hits(cause="戰鬥", **condition))
        self.assertIn(GOD_BINDING, self.hits(cause="效果", **condition))
        self.assertNotIn(GOD_BINDING, self.hits(actions=["加入手牌"], cause="效果",
                                                include_condition=True))

    def test_without_recipient_and_cause_nothing_changes(self):
        for query in ({"actions": ["破壞"]}, {"actions": ["破壞"], "include_condition": True},
                      {"actions": ["傷害"]}):
            with self.subTest(query=query):
                self.assertEqual(self.result(**query),
                                 self.result(recipient=None, cause=None, **query))

    def test_unparsed_group_ignores_recipient_and_cause(self):
        """ミラクル・フリッパー「このカードが魔法・罠の効果によって破壊された場合」解析不出;
        リミット・リバース「そのモンスターが破壊された時」解析不出:給了受方、原因,兩張都進未解析組
        (直接命中被受方、原因篩掉後,解析不出的段照未解析組的規則列,不看受方、原因)。"""
        query = {"actions": ["破壞"], "include_condition": True}
        filtered = self.result(cause="效果", recipient="對手", **query)
        self.assertEqual(filtered["groups"]["全部"], [])
        self.assertIn(LIMIT_REVERSE, filtered["groups"]["未解析"])
        self.assertIn(MIRACLE_FLIPPER, filtered["groups"]["未解析"])


class RecipientCauseIndexTest(RecipientCauseCase):
    """接縫二:動作索引多受方、原因兩欄,讀回與攤平相同;原因值的清單與列數進索引的表。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        text, cls.report = build_action_index(
            cls.structures, cls.cards, [{"id": entry["id"]} for entry in cls.cards], ARCHETYPES)
        cls.raw = json.loads(text[len("window.ACTION_DATA="):-2])
        cls.index = decode_action_index(text)

    def segment(self, cid, text):
        structure = next(s for s in self.structures if s["id"] == cid)
        segments = {seg["id"]: seg for block in structure["blocks"]
                    for _, seg in iter_segments(block)}
        found = [seg for seg in self.index["cards"][cid]["segments"]
                 if segments[seg["id"]]["text"] == text]
        self.assertEqual(len(found), 1, text)
        return found[0]

    def test_builds_without_problems(self):
        self.assertEqual(self.report["problems"], [])

    def test_recipient_kinds_are_kept_apart(self):
        self.assertEqual(self.segment(POISON_SCORPION, "相手に３００ダメージを与える")["recipient"],
                         "對手")
        self.assertEqual(self.segment(LAVA_GOLEM, "自分は１０００ダメージを受ける")["recipient"],
                         "我方")
        self.assertIsNone(self.segment(
            CHOPMAN, "自分の墓地の装備魔法カード１枚をこのカードに装備する事ができる")["recipient"])

    def test_cause_kinds_are_kept_apart(self):
        """寫明的種類與方、沒寫的被動句(不限定)、沒寫的主動句(None)分得開。"""
        self.assertEqual(self.segment(MIRACLE_FLIPPER, "このカードが戦闘によって破壊された場合")
                         ["cause"], ("戰鬥", None))
        self.assertEqual(self.segment(DARK_MAGIC_EXPANDED,
                                      "自分フィールドの魔法・罠カードは相手の効果では破壊されない")
                         ["cause"], ("效果", "對手"))
        self.assertEqual(self.segment(LANCELOD, "フィールド上のこのカードが破壊され墓地へ送られた時")
                         ["cause"], ("不限定", None))
        self.assertIsNone(self.segment(LIMIT_REVERSE, "そのモンスターとこのカードを破壊する")
                          ["cause"])

    def test_columns_round_trip(self):
        """每一段讀回的受方、原因與攤平算的相同。"""
        flat = {(row.card, row.segment): (row.recipient, row.cause)
                for row in flatten(self.structures, self.cards).rows}
        decoded = {(cid, seg["id"]): (seg["recipient"], seg["cause"])
                   for cid, entry in self.index["cards"].items() for seg in entry["segments"]}
        self.assertEqual(decoded, flat)

    def test_cause_table_has_values_and_row_counts(self):
        """`causes`:[值, 列數],寫明的種類都在表裡(戰鬥或效果、戰鬥以外也在,由網站決定不列成選項)。"""
        causes = dict(self.raw["causes"])
        self.assertEqual(causes["戰鬥以外"], 1)        # 蛇神降臨
        self.assertGreaterEqual(causes["戰鬥或效果"], 1)  # アンクリボー
        self.assertGreaterEqual(causes["戰鬥"], 2)      # ミラクル・フリッパー、神縛りの塚
        self.assertGreaterEqual(causes["效果"], 3)      # 神縛りの塚、黒魔導強化


# 玩家介面的動作條件:受方、原因(種類與方)、「含不限定的」。
CONDITION = ["eff", "cost", "cond"]
PARITY_CONDS = [
    {"actions": ["傷害"], "recipient": "對手"},
    {"actions": ["傷害"], "recipient": "我方"},
    {"actions": ["裝備"], "recipient": "我方"},
    {"actions": ["展示"], "recipient": "對手"},
    {"actions": ["破壞"], "kinds": CONDITION, "cause": {"kind": "戰鬥"}},
    {"actions": ["破壞"], "kinds": CONDITION, "cause": {"kind": "戰鬥"}, "unrestricted": True},
    {"actions": ["破壞"], "kinds": CONDITION, "cause": {"kind": "效果"}},
    {"actions": ["破壞"], "pol": "resist", "cause": {"kind": "效果", "side": "對手"}},
    {"actions": ["破壞"], "pol": "resist", "cause": {"kind": "效果", "side": "我方"}},
    {"actions": ["破壞"], "kinds": CONDITION, "cause": {"kind": "效果"}, "recipient": "對手"},
    {"actions": ["特殊召喚"], "cause": {"kind": "戰鬥"}, "unrestricted": True},
]


class RecipientCauseParityTest(RecipientCauseCase):
    """兩邊答案一致:受方與原因,Python 與前端引擎命中同一批卡、無法確認的卡相同。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        text, report = build_action_index(
            cls.structures, cls.cards, [{"id": entry["id"]} for entry in cls.cards], ARCHETYPES)
        assert not report["problems"], report["problems"]
        cls.front = front_end(text, cls.cards, PARITY_CONDS)

    def test_recipient_and_cause_hit_the_same_cards(self):
        for cond, front in zip(PARITY_CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]),
                                 sorted(python["groups"]["全部"] + python["groups"]["經引用"]))
                self.assertEqual(sorted(front["unsure"]), sorted(python["groups"]["未解析"]))
        # 夾具要問得出東西:受方分得出兩方、戰鬥或效果兩邊都算、開關加進沒寫原因的被動句、方篩掉卡
        hits = [set(front["ids"]) for front in self.front]
        self.assertEqual(hits[0], {POISON_SCORPION})
        self.assertEqual(hits[1], {LAVA_GOLEM})
        self.assertFalse(hits[2])
        self.assertEqual(hits[4], {MIRACLE_FLIPPER, ANKURIBOH, GOD_BINDING})
        self.assertEqual(hits[5] - hits[4], {LANCELOD})
        self.assertIn(SERPENT_DESCENT, hits[6])
        self.assertEqual(hits[7], {DARK_MAGIC_EXPANDED, GOD_BINDING})
        self.assertEqual(hits[8], {GOD_BINDING})

    def test_recipient_and_cause_become_query_keys(self):
        self.assertEqual(self.front[0]["rowQuery"]["recipient"], "對手")
        self.assertEqual(self.front[7]["rowQuery"]["cause"], {"kind": "效果", "side": "對手"})
        self.assertIs(self.front[5]["rowQuery"]["include_unrestricted"], True)


if __name__ == "__main__":
    unittest.main()
