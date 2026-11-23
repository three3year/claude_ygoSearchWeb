import unittest

from action_index import build_action_index, decode_action_index
from action_query import run_query
from action_rows import flatten
from card_structure import build_structures
from structure_shape import iter_segments
from test_draw import DARK_WORLD_DEALINGS, DARK_WORLD_DEALINGS_TEXT
from test_golden import (ARCHETYPES, DARK_MAGICIAN_OF_DESTRUCTION,
                         DARK_MAGICIAN_OF_DESTRUCTION_TEXT, SPELL, card, faq)
from test_web_parity import front_end

MAGNUM = 43227
NIGHTMARE = 359563
PARALLEL_TELEPORT = 483
ORBITAEL = 44818
SKY_PUPIL = 122520
METAMORPOT = 33508719
FENRIR = 218704
MASKED_SORCERER = 10189126

MAGNUM_TEXT = (
    "EXデッキから特殊召喚されたモンスター＋手札のモンスター\n"
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：自分の墓地の、「融合」魔法カードか「フュージョン」魔法カード１枚を対象として発動できる。"
    "そのカードをデッキの一番下に戻す。その後、自分は１枚ドローする。\n"
    "②：他のカードの効果が発動した時、自分の墓地から「融合」魔法カードか「フュージョン」魔法カード"
    "１枚を除外し、フィールドのカード１枚を対象として発動できる。そのカードを破壊する。")
NIGHTMARE_TEXT = (
    "闇属性レベル４モンスター×２\n"
    "①：相手がモンスターを特殊召喚した時、このカードのX素材を１つ取り除いて発動できる。"
    "そのモンスターを裏側守備表示にする。")
PARALLEL_TELEPORT_TEXT = (
    "このカード名のカードは１ターンに１枚しか発動できず、このカードを発動するターン、"
    "自分はサイキック族モンスターしか特殊召喚できない。\n"
    "①：自分フィールドのレベルを持つサイキック族モンスター１体をリリースして発動できる。"
    "デッキ・EXデッキからレベル７以下のサイキック族モンスター１体を特殊召喚する。"
    "リリースしたモンスターとこの効果で特殊召喚したモンスターの元々のレベルが異なる場合、"
    "さらに自分はその差×１０００LPを失う。")
ORBITAEL_TEXT = (
    "このカード名の①②の効果はそれぞれ１ターンに１度しか使用できない。"
    "①：自分フィールドの光属性モンスター１体を対象として発動できる。そのモンスターをリリースし、"
    "デッキから「ホーリーナイツ」魔法・罠カード１枚を選んで自分フィールドにセットする。"
    "この効果は相手ターンでも発動できる。"
    "②：このカードが墓地に存在し、自分フィールドの表側表示のドラゴン族・光属性・レベル７モンスターが"
    "手札に戻った場合に発動できる。このカードを特殊召喚する。")
SKY_PUPIL_TEXT = (
    "「EMスカイ・ピューピル」の①の効果は１ターンに１度しか使用できない。"
    "①：自分フィールドのレベル５以上の「EM」モンスター１体を持ち主の手札に戻して発動できる。"
    "このカードを手札から特殊召喚する。この効果は相手ターンでも発動できる。"
    "②：このカードが相手モンスターと戦闘を行う場合、ダメージステップ終了時までそのモンスターの効果は"
    "無効化される。"
    "③：自分フィールドに他の「EM」モンスターが存在する場合、このカードが相手モンスターに攻撃する"
    "ダメージ計算前に発動できる。その相手モンスターを破壊する。")
METAMORPOT_TEXT = (
    "①：このカードがリバースした場合に発動する。手札があるプレイヤーは、その手札を全て捨てる。"
    "お互いにデッキから５枚ドローする。")
FENRIR_TEXT = (
    "このカードは通常召喚できない。自分の墓地の水属性モンスター２体をゲームから除外して"
    "特殊召喚する。このカードが戦闘によって相手モンスターを破壊した場合、"
    "次の相手ターンのドローフェイズをスキップする。")

MASKED_SORCERER_TEXT = (
    "このカードが相手ライフに戦闘ダメージを与えた時、自分のデッキからカードを１枚ドローする。")

AGENT_ARCHETYPES = ARCHETYPES + [
    {"setcode": 0xa, "hex": "0xa", "names_ja": ["ヴェルズ"], "name_zh": "入魔",
     "source": "strings.conf"},
    {"setcode": 0x46, "hex": "0x46", "names_ja": ["融合", "フュージョン"], "name_zh": "融合",
     "source": "strings.conf"},
    {"setcode": 0x9f, "hex": "0x9f", "names_ja": ["ＥＭ"], "name_zh": "娛樂夥伴",
     "source": "strings.conf"},
    {"setcode": 0x159, "hex": "0x159", "names_ja": ["ホーリーナイツ"], "name_zh": "聖夜騎士團",
     "source": "strings.conf"},
]


class AgentCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cards = [
            card(MAGNUM, name_ja="マグナム・ザ・リリーバー", type=0x61, level=8, race=0x8,
                 attribute=0x10, atk=2800, **{"def": 2000}),
            card(NIGHTMARE, name_ja="ヴェルズ・ナイトメア", type=0x800021, level=4, race=0x8,
                 attribute=0x20, atk=950, setcode=0xa, **{"def": 1950}),
            card(PARALLEL_TELEPORT, name_ja="パラレル・テレポート", type=SPELL | 0x10000),
            card(ORBITAEL, name_ja="ホーリーナイツ・オルビタエル", level=4, race=0x4,
                 attribute=0x10, atk=400, setcode=0x159, **{"def": 2100}),
            card(SKY_PUPIL, name_ja="ＥＭスカイ・ピューピル", level=3, race=0x2,
                 attribute=0x10, atk=800, setcode=0x9f, **{"def": 800}),
            card(METAMORPOT, name_ja="メタモルポット", type=0x200021, level=2, race=0x100,
                 attribute=0x1, atk=700, **{"def": 600}),
            card(FENRIR, name_ja="フェンリル", type=0x2000021, level=4, race=0x4000,
                 attribute=0x2, atk=1400, **{"def": 1200}),
            card(DARK_WORLD_DEALINGS, name_ja="暗黒界の取引", type=SPELL),
            card(MASKED_SORCERER, name_ja="仮面魔道士", level=4, race=0x2, attribute=0x20,
                 atk=900, **{"def": 1400}),
            card(DARK_MAGICIAN_OF_DESTRUCTION, name_ja="滅びの黒魔術師", type=0x61,
                 level=8, race=0x2, attribute=0x20, atk=2800),
        ]
        faqs = [
            faq(MAGNUM, "マグナム・ザ・リリーバー", MAGNUM_TEXT),
            faq(NIGHTMARE, "ヴェルズ・ナイトメア", NIGHTMARE_TEXT),
            faq(PARALLEL_TELEPORT, "パラレル・テレポート", PARALLEL_TELEPORT_TEXT),
            faq(ORBITAEL, "ホーリーナイツ・オルビタエル", ORBITAEL_TEXT),
            faq(SKY_PUPIL, "EMスカイ・ピューピル", SKY_PUPIL_TEXT),
            faq(METAMORPOT, "メタモルポット", METAMORPOT_TEXT),
            faq(FENRIR, "フェンリル", FENRIR_TEXT),
            faq(DARK_WORLD_DEALINGS, "暗黒界の取引", DARK_WORLD_DEALINGS_TEXT),
            faq(MASKED_SORCERER, "仮面魔道士", MASKED_SORCERER_TEXT),
            faq(DARK_MAGICIAN_OF_DESTRUCTION, "滅びの黒魔術師",
                DARK_MAGICIAN_OF_DESTRUCTION_TEXT),
        ]
        cls.structures, _ = build_structures(cls.cards, faqs, AGENT_ARCHETYPES)

    def result(self, **query):
        return run_query(self.structures, self.cards, query)

    def hits(self, **query):
        return self.result(**query)["groups"]["全部"]


class WrittenAgentTest(AgentCase):

    def test_written_self_agent(self):
        self.assertIn(MAGNUM, self.hits(actions=["抽牌"], agent="我方"))
        self.assertNotIn(MAGNUM, self.hits(actions=["抽牌"], agent="對手"))

    def test_written_opponent_in_a_condition(self):
        query = {"actions": ["特殊召喚"], "include_condition": True}
        self.assertIn(NIGHTMARE, self.hits(agent="對手", **query))
        self.assertNotIn(NIGHTMARE, self.hits(agent="我方", **query))
        self.assertNotIn(NIGHTMARE, self.hits(agent="我方", include_unrestricted=True, **query))

    def test_both_sides_cover_either_side(self):
        for side in ("我方", "對手"):
            with self.subTest(agent=side):
                self.assertIn(METAMORPOT, self.hits(actions=["抽牌"], agent=side))

    def test_player_back_reference_takes_the_referred_agent(self):
        self.assertIn(DARK_WORLD_DEALINGS, self.hits(actions=["捨棄"], agent="對手"))
        self.assertIn(DARK_WORLD_DEALINGS, self.hits(actions=["捨棄"], agent="我方"))


class ImpliedSelfTest(AgentCase):

    def test_active_effect_without_agent_counts_as_self(self):
        self.assertIn(PARALLEL_TELEPORT, self.hits(actions=["特殊召喚"], agent="我方"))
        self.assertNotIn(PARALLEL_TELEPORT, self.hits(actions=["特殊召喚"], agent="對手"))
        self.assertNotIn(PARALLEL_TELEPORT, self.hits(actions=["特殊召喚"], agent="對手",
                                                      include_unrestricted=True))

    def test_draw_without_subject_counts_as_self(self):
        self.assertIn(MASKED_SORCERER, self.hits(actions=["抽牌"], agent="我方"))
        self.assertIn(MAGNUM, self.hits(actions=["抽牌"], agent="我方"))
        self.assertNotIn(MASKED_SORCERER, self.hits(actions=["抽牌"], agent="對手"))

    def test_active_cost_without_agent_counts_as_self(self):
        self.assertIn(PARALLEL_TELEPORT, self.hits(actions=["解放"], agent="我方"))
        self.assertNotIn(PARALLEL_TELEPORT, self.hits(actions=["解放"], agent="對手"))

    def test_summoning_procedure_counts_as_self(self):
        self.assertIn(FENRIR, self.hits(actions=["除外"], agent="我方"))
        self.assertNotIn(FENRIR, self.hits(actions=["除外"], agent="對手"))

    def test_agent_is_compared_per_segment(self):
        self.assertIn(NIGHTMARE, self.hits(actions=["變更表示形式"], agent="我方"))
        self.assertNotIn(NIGHTMARE, self.hits(actions=["變更表示形式"], agent="對手",
                                              include_condition=True))


class UnrestrictedTest(AgentCase):

    def test_condition_without_agent_needs_the_switch(self):
        query = {"actions": ["返回"], "include_condition": True}
        for side in ("我方", "對手"):
            with self.subTest(agent=side):
                self.assertNotIn(ORBITAEL, self.hits(agent=side, **query))
                self.assertIn(ORBITAEL, self.hits(agent=side, include_unrestricted=True,
                                                  **query))

    def test_passive_effect_without_agent_needs_the_switch(self):
        self.assertNotIn(SKY_PUPIL, self.hits(actions=["無效"], agent="對手"))
        self.assertIn(SKY_PUPIL, self.hits(actions=["無效"], agent="對手",
                                           include_unrestricted=True))

    def test_restriction_without_agent_needs_the_switch(self):
        query = {"actions": ["通常召喚"], "kinds": ["限制"], "polarities": ["不能"]}
        self.assertNotIn(FENRIR, self.hits(agent="我方", **query))
        self.assertIn(FENRIR, self.hits(agent="我方", include_unrestricted=True, **query))

    def test_modifier_without_agent_needs_the_switch(self):
        query = {"kinds": ["修飾"]}
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION, self.hits(**query))
        self.assertNotIn(DARK_MAGICIAN_OF_DESTRUCTION, self.hits(agent="我方", **query))
        self.assertIn(DARK_MAGICIAN_OF_DESTRUCTION,
                      self.hits(agent="我方", include_unrestricted=True, **query))


class WithoutAgentTest(AgentCase):

    def test_no_agent_matches_everything_as_before(self):
        for query in ({"actions": ["無效"]}, {"actions": ["返回"], "include_condition": True},
                      {"actions": ["特殊召喚"]}):
            with self.subTest(query=query):
                self.assertEqual(self.result(**query),
                                 self.result(include_unrestricted=True, **query))
        self.assertIn(SKY_PUPIL, self.hits(actions=["無效"]))

    def test_agent_does_not_filter_the_unparsed_group(self):
        self.assertIn(METAMORPOT, self.result(actions=["捨棄"])["groups"]["未解析"])
        self.assertIn(METAMORPOT,
                      self.result(actions=["捨棄"], agent="對手")["groups"]["未解析"])

    def test_agent_must_be_a_side(self):
        with self.assertRaises(ValueError):
            self.result(actions=["抽牌"], agent="雙方各自")


class AgentIndexTest(AgentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        text, cls.report = build_action_index(
            cls.structures, cls.cards, [{"id": entry["id"]} for entry in cls.cards],
            AGENT_ARCHETYPES)
        cls.index = decode_action_index(text)

    def agent(self, cid, text):
        segments = {seg["id"]: seg for block in self.structure(cid)["blocks"]
                    for _, seg in iter_segments(block)}
        found = [seg["agent"] for seg in self.index["cards"][cid]["segments"]
                 if segments[seg["id"]]["text"] == text]
        self.assertEqual(len(found), 1, text)
        return found[0]

    def structure(self, cid):
        return next(s for s in self.structures if s["id"] == cid)

    def test_builds_without_problems(self):
        self.assertEqual(self.report["problems"], [])

    def test_three_kinds_of_agent_are_kept_apart(self):
        self.assertEqual(self.agent(MAGNUM, "自分は１枚ドローする"), "我方")
        self.assertEqual(self.agent(NIGHTMARE, "相手がモンスターを特殊召喚した時"), "對手")
        self.assertEqual(self.agent(METAMORPOT, "お互いにデッキから５枚ドローする"), "雙方各自")
        self.assertEqual(self.agent(PARALLEL_TELEPORT,
                                    "デッキ・EXデッキからレベル７以下のサイキック族モンスター"
                                    "１体を特殊召喚する"), "算我方")
        self.assertEqual(self.agent(SKY_PUPIL, "ダメージステップ終了時までそのモンスターの効果は"
                                               "無効化される"), "不限定")
        self.assertEqual(self.agent(FENRIR, "このカードは通常召喚できない"), "不限定")

    def test_agent_round_trips(self):
        flat = {(row.card, row.segment): row.agent for row in flatten(self.structures, self.cards).rows}
        decoded = {(cid, seg["id"]): seg["agent"] for cid, entry in self.index["cards"].items()
                   for seg in entry["segments"]}
        self.assertEqual(decoded, flat)


PARITY_CONDS = [
    {"actions": ["抽牌"], "agent": "我方"},
    {"actions": ["抽牌"], "agent": "對手"},
    {"actions": ["捨棄"], "agent": "對手"},
    {"actions": ["無效"], "agent": "對手"},
    {"actions": ["無效"], "agent": "對手", "unrestricted": True},
    {"actions": ["無效"], "unrestricted": True},
    {"actions": ["特殊召喚"], "agent": "我方"},
    {"actions": ["特殊召喚"], "agent": "對手", "unrestricted": True},
    {"actions": ["除外"], "agent": "我方"},
]


class AgentParityTest(AgentCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        text, report = build_action_index(
            cls.structures, cls.cards, [{"id": entry["id"]} for entry in cls.cards],
            AGENT_ARCHETYPES)
        assert not report["problems"], report["problems"]
        cls.front = front_end(text, cls.cards, PARITY_CONDS)

    def test_agent_conditions_hit_the_same_cards(self):
        for cond, front in zip(PARITY_CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]),
                                 sorted(python["groups"]["全部"] + python["groups"]["經引用"]))
                self.assertEqual(sorted(front["unsure"]), sorted(python["groups"]["未解析"]))
        hits = [set(front["ids"]) for front in self.front]
        self.assertIn(MAGNUM, hits[0])
        self.assertNotIn(MAGNUM, hits[1])
        self.assertIn(METAMORPOT, hits[1])
        self.assertIn(DARK_WORLD_DEALINGS, hits[2])
        self.assertNotIn(SKY_PUPIL, hits[3])
        self.assertIn(SKY_PUPIL, hits[4])

    def test_agent_and_switch_become_query_keys(self):
        self.assertEqual(self.front[4]["rowQuery"]["agent"], "對手")
        self.assertIs(self.front[4]["rowQuery"]["include_unrestricted"], True)


if __name__ == "__main__":
    unittest.main()
