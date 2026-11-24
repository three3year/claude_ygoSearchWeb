import json
import os
import shutil
import subprocess
import sys
import unittest

from action_index import build_action_index, decode_action_index
from action_query import run_query
from condition_judge import CATEGORY_BITS, CardView, eval_condition
from attribute_words import ATTRIBUTE_JA, RACE_JA
from card_structure import build_structures
from test_action_index import fixture
from test_draw import (DARK_WORLD_DEALINGS, DARK_WORLD_DEALINGS_TEXT, SPELL, TSUPPA_REACH,
                       TSUPPA_REACH_TEXT)
from test_effect_reference import (ARCHETYPES_13, BLACK_PANTHER, BLACK_PANTHER_TEXT, DESTROYER,
                                   DESTROYER_TEXT, FRESHIA, GISHIKI_MIRROR, GISHIKI_MIRROR_TEXT,
                                   HOSHIAI, HOSHIAI_TEXT, NORMAL_TRAP, RITUAL_SPELL)
from test_action_index import EMPEROR_PENGUIN, OTOSHIANA, PENGUIN_SOLDIER
from test_golden import card, faq
from test_object_self import CHOBHAM
from test_resistance_restriction import (ELEKIRIN, ELEKIRIN_TEXT, MASTER_MONK, MASTER_MONK_TEXT,
                                         RESISTANCE_ARCHETYPES, SERVAL_HAWK, SERVAL_HAWK_TEXT)

PARITY_JS = os.path.join(os.path.dirname(__file__), "..", "web", "action_parity.js")

CONDS = [
    {"actions": ["破壞"]},
    {"actions": ["特殊召喚"]},
    {"actions": ["解放"]},
    {"actions": ["直接攻擊"]},
    {"actions": ["通常召喚"]},
    {"actions": ["除外"]},
    {"actions": ["破壞", "除外"]},
    {"actions": ["解放", "特殊召喚"]},
    {"actions": ["破壞", "特殊召喚"]},
    {"actions": ["不存在的動作"]},
    {"actions": ["儀式召喚"]},
    {"actions": ["返回"]},
    {"actions": ["加入手牌"]},
] + [
    {"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "我方"}},
    {"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "對手"}},
    {"actions": ["特殊召喚"], "to": {"zone": "場上"}},
    {"actions": ["除外"], "from": {"zone": "墓地"}, "to": {"zone": "除外"}},
    {"actions": ["破壞"], "from": {"zone": "場上"}},
    {"to": {"zone": "墓地"}},
    {"from": {"zone": "牌組"}, "to": {"zone": "墓地"}, "kinds": ["cost"]},
    {"actions": ["返回"], "to": {"zone": "牌組"}},
    {"actions": ["返回"], "to": {"zone": "牌組底"}},
    {"actions": ["抽牌"], "from": {"zone": "牌組", "side": "我方"}},
    {"actions": ["抽牌"], "from": {"zone": "牌組", "side": "對手"}},
    {"actions": ["抽牌"], "from": {"zone": "牌組"}},
    {"actions": ["破壞"], "kinds": ["eff", "cost", "cond"]},
    {"actions": ["特殊召喚"], "kinds": ["cond"]},
    {"actions": ["解放"], "kinds": ["cost"]},
    {"actions": ["解放"], "kinds": ["eff"]},
    {"actions": ["破壞"], "pol": "resist"},
    {"actions": ["破壞"], "pol": "resist", "kinds": ["eff", "cond"]},
    {"actions": ["通常召喚"], "pol": "limit"},
    {"actions": ["直接攻擊"], "pol": "limit"},
    {"actions": ["特殊召喚"], "pol": "limit", "kinds": ["eff", "cond"]},
    {"actions": ["攻擊"], "pol": "limit", "kinds": ["cost"]},
] + [
    {"actions": ["抽牌"], "agent": "對手"},
    {"actions": ["捨棄"], "agent": "對手"},
    {"actions": ["破壞"], "agent": "對手"},
    {"actions": ["破壞"], "agent": "我方"},
    {"actions": ["特殊召喚"], "kinds": ["eff", "cond"], "agent": "對手"},
    {"actions": ["特殊召喚"], "kinds": ["eff", "cond"], "agent": "我方"},
    {"actions": ["破壞"], "pol": "resist", "agent": "對手"},
    {"actions": ["破壞"], "pol": "resist", "agent": "對手", "include_unrestricted": True},
    {"actions": ["通常召喚"], "pol": "limit", "agent": "我方", "include_unrestricted": True},
    {"agent": "對手", "kinds": ["cond"]},
] + [
    {"actions": ["展示"], "recipient": "對手"},
    {"actions": ["展示"], "recipient": "我方"},
    {"recipient": "對手", "kinds": ["cost"]},
    {"actions": ["抽牌"], "kinds": ["eff", "cond"], "cause": {"kind": "效果"}},
    {"actions": ["抽牌"], "kinds": ["eff", "cond"], "cause": {"kind": "規則"}},
    {"actions": ["抽牌"], "kinds": ["eff", "cond"], "cause": {"kind": "效果", "side": "對手"}},
    {"actions": ["破壞"], "pol": "resist", "cause": {"kind": "戰鬥"}},
    {"actions": ["破壞"], "pol": "resist", "cause": {"kind": "效果", "side": "對手"}},
    {"actions": ["破壞"], "cause": {"kind": "效果"}},
    {"actions": ["召喚"], "kinds": ["cond"], "cause": {"kind": "戰鬥"}},
    {"actions": ["召喚"], "kinds": ["cond"], "cause": {"kind": "戰鬥"}, "include_unrestricted": True},
]
LOOP_A, LOOP_B = 11, 12
LOOP_TEXT = ("①：手札から通常罠カード１枚を墓地へ送って発動できる。"
             "この効果は、その罠カード発動時の効果と同じになる。")


def parity_fixture():
    structures, cards, _ = fixture()
    extra = [card(ELEKIRIN, name_ja="エレキリン"), card(MASTER_MONK, name_ja="マスターモンク"),
             card(SERVAL_HAWK, name_ja="幻獣機サーバルホーク"),
             card(DARK_WORLD_DEALINGS, name_ja="暗黒界の取引", type=SPELL, setcode=0x6),
             card(TSUPPA_REACH, name_ja="ツッパリーチ", type=0x80002),
             card(HOSHIAI, name_ja="星逢の天河", type=NORMAL_TRAP),
             card(GISHIKI_MIRROR, name_ja="リチュアの氷魔鏡", type=RITUAL_SPELL, setcode=0x3a),
             card(LOOP_A, name_ja="甲", type=NORMAL_TRAP), card(LOOP_B, name_ja="乙", type=NORMAL_TRAP),
             card(BLACK_PANTHER, name_ja="Ｎ・ブラック・パンサー", level=3, race=0x4000,
                  attribute=0x20, atk=1000, **{"def": 500}, setcode=0x1f),
             card(DESTROYER, name_ja="破壊者")]
    archetypes = {row["setcode"]: row for row in ARCHETYPES_13 + RESISTANCE_ARCHETYPES}
    more, _ = build_structures(extra, [
        faq(ELEKIRIN, "エレキリン", ELEKIRIN_TEXT),
        faq(MASTER_MONK, "マスターモンク", MASTER_MONK_TEXT),
        faq(SERVAL_HAWK, "幻獣機サーバルホーク", SERVAL_HAWK_TEXT),
        faq(DARK_WORLD_DEALINGS, "暗黒界の取引", DARK_WORLD_DEALINGS_TEXT),
        faq(TSUPPA_REACH, "ツッパリーチ", TSUPPA_REACH_TEXT),
        faq(HOSHIAI, "星逢の天河", HOSHIAI_TEXT),
        faq(GISHIKI_MIRROR, "リチュアの氷魔鏡", GISHIKI_MIRROR_TEXT),
        faq(LOOP_A, "甲", LOOP_TEXT), faq(LOOP_B, "乙", LOOP_TEXT),
        faq(BLACK_PANTHER, "Ｎ・ブラック・パンサー", BLACK_PANTHER_TEXT),
        faq(DESTROYER, "破壊者", DESTROYER_TEXT),
    ], list(archetypes.values()))
    cards = sorted(cards + extra, key=lambda entry: entry["id"])
    structures = sorted(structures + more, key=lambda s: s["id"])
    return structures, cards, list(archetypes.values())


def front_end(action_text, cards, conds, front=None):
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("機器上沒有 node:「兩邊答案一致」的測試需要 node")
    payload = {"actionData": action_text,
               "cards": front["cards"] if front else
               [{"id": entry["id"], "n": entry["name_zh"]} for entry in cards],
               "vocab": front["vocab"] if front else {},
               "conds": conds}
    done = subprocess.run([node, PARITY_JS], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, encoding="utf-8", check=False)
    if done.returncode:
        raise AssertionError(f"action_parity.js 失敗:\n{done.stderr}")
    return json.loads(done.stdout)


class WebParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.structures, cls.cards, archetypes = parity_fixture()
        text, report = build_action_index(cls.structures, cls.cards,
                                          [{"id": entry["id"]} for entry in cls.cards], archetypes)
        assert not report["problems"], report["problems"]
        cls.text = text
        cls.front = front_end(text, cls.cards, CONDS)

    def test_player_defaults_become_the_row_query(self):
        self.assertEqual(self.front[0]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["效果", "召喚手續", "限制", "代價"],
                          "polarities": ["做", "可以", "必須"]})

    def test_action_words_hit_the_same_cards(self):
        for cond, front in zip(CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]),
                                 sorted(python["groups"]["全部"] + python["groups"]["經引用"]))
        hits = {tuple(c["actions"]): set(f["ids"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        self.assertTrue(hits[("破壞",)])
        both = hits[("解放",)] & hits[("特殊召喚",)]
        self.assertTrue(both)
        self.assertFalse(both & hits[("解放", "特殊召喚")])

    def test_via_reference_cases_are_asked(self):
        hits = {tuple(c["actions"]): set(f["ids"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        via = {tuple(c["actions"]): set(run_query(self.structures, self.cards,
                                                  f["rowQuery"])["groups"]["經引用"])
               for c, f in zip(CONDS, self.front) if set(c) == {"actions"}}
        self.assertIn(FRESHIA, via[("破壞",)])
        self.assertIn(FRESHIA, hits[("破壞",)])
        self.assertIn(HOSHIAI, hits[("儀式召喚",)])
        self.assertIn(GISHIKI_MIRROR, hits[("返回",)])
        self.assertNotIn(HOSHIAI, hits[("返回",)])
        self.assertIn(DESTROYER, hits[("破壞",)])
        self.assertNotIn(BLACK_PANTHER, hits[("破壞",)])
        self.assertFalse({LOOP_A, LOOP_B} & hits[("直接攻擊",)])
        self.assertLessEqual({LOOP_A, LOOP_B}, via[("加入手牌",)])

    def test_cannot_confirm_cards_are_the_unparsed_group(self):
        for cond, front in zip(CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["unsure"]), sorted(python["groups"]["未解析"]))
        unsure = {tuple(c["actions"]): set(f["unsure"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        hits = {tuple(c["actions"]): set(f["ids"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        self.assertTrue(unsure[("破壞",)] - unsure[("不存在的動作",)])
        self.assertIn(MASTER_MONK, hits[("解放",)])
        self.assertNotIn(MASTER_MONK, unsure[("解放",)])

    def test_zones_kinds_polarity_ask_something(self):
        hits = {json.dumps(c, ensure_ascii=False, sort_keys=True): set(f["ids"])
                for c, f in zip(CONDS, self.front)}

        def of(cond):
            return hits[json.dumps(cond, ensure_ascii=False, sort_keys=True)]
        self.assertEqual(of({"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "我方"}}),
                         {6836211})
        self.assertFalse(of({"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "對手"}}))
        self.assertFalse(of({"actions": ["特殊召喚"], "to": {"zone": "場上"}}))
        self.assertIn(TSUPPA_REACH, of({"actions": ["返回"], "to": {"zone": "牌組"}}))
        self.assertTrue(of({"actions": ["特殊召喚"], "kinds": ["cond"]}) - of({"actions": ["特殊召喚"]}))
        self.assertEqual(of({"actions": ["破壞"], "pol": "resist"}), {6511113})
        default = next(f["rowQuery"] for c, f in zip(CONDS, self.front) if c == {"actions": ["破壞"]})
        self.assertNotIn(6511113, run_query(self.structures, self.cards, default)["groups"]["全部"])
        self.assertEqual(of({"actions": ["通常召喚"], "pol": "limit"}), {MASTER_MONK})
        self.assertFalse(of({"actions": ["通常召喚"]}))

    def test_agent_and_unrestricted_ask_something(self):
        hits = {json.dumps(c, ensure_ascii=False, sort_keys=True): set(f["ids"])
                for c, f in zip(CONDS, self.front)}

        def of(cond):
            return hits[json.dumps(cond, ensure_ascii=False, sort_keys=True)]
        self.assertIn(DARK_WORLD_DEALINGS, of({"actions": ["抽牌"], "agent": "對手"}))
        self.assertIn(DARK_WORLD_DEALINGS, of({"actions": ["捨棄"], "agent": "對手"}))
        self.assertTrue(of({"actions": ["破壞"], "agent": "我方"}))
        self.assertFalse(of({"actions": ["破壞"], "agent": "對手"}))
        on_condition = of({"actions": ["特殊召喚"], "kinds": ["eff", "cond"], "agent": "對手"})
        self.assertTrue(on_condition)
        self.assertTrue(on_condition
                        - of({"actions": ["特殊召喚"], "kinds": ["eff", "cond"], "agent": "我方"}))
        self.assertFalse(of({"actions": ["破壞"], "pol": "resist", "agent": "對手"}))
        self.assertEqual(of({"actions": ["破壞"], "pol": "resist", "agent": "對手",
                             "include_unrestricted": True}), {6511113})
        self.assertEqual(of({"actions": ["通常召喚"], "pol": "limit", "agent": "我方",
                             "include_unrestricted": True}), {MASTER_MONK})
        self.assertTrue(of({"agent": "對手", "kinds": ["cond"]}))

    def test_recipient_and_cause_ask_something(self):
        hits = {json.dumps(c, ensure_ascii=False, sort_keys=True): set(f["ids"])
                for c, f in zip(CONDS, self.front)}

        def of(cond):
            return hits[json.dumps(cond, ensure_ascii=False, sort_keys=True)]
        self.assertLessEqual({TSUPPA_REACH, HOSHIAI}, of({"actions": ["展示"], "recipient": "對手"}))
        self.assertFalse(of({"actions": ["展示"], "recipient": "我方"}))
        draw = {"actions": ["抽牌"], "kinds": ["eff", "cond"]}
        self.assertIn(TSUPPA_REACH, of({**draw, "cause": {"kind": "效果"}}))
        self.assertIn(TSUPPA_REACH, of({**draw, "cause": {"kind": "規則"}}))
        self.assertIn(TSUPPA_REACH, of({**draw, "cause": {"kind": "效果", "side": "對手"}}))
        self.assertEqual(of({"actions": ["破壞"], "pol": "resist", "cause": {"kind": "戰鬥"}}),
                         {FRESHIA})
        self.assertFalse(of({"actions": ["召喚"], "kinds": ["cond"], "cause": {"kind": "戰鬥"}}))
        self.assertIn(DESTROYER, of({"actions": ["召喚"], "kinds": ["cond"],
                                     "cause": {"kind": "戰鬥"}, "include_unrestricted": True}))

    def test_kinds_and_polarity_become_the_row_query(self):
        front = front_end(self.text, self.cards,
                          [{"actions": ["破壞"], "kinds": ["eff", "cost", "cond"], "pol": "resist"},
                           {"actions": ["破壞"], "kinds": ["cost"], "pol": "limit"}])
        self.assertEqual(front[0]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["效果", "召喚手續", "限制", "代價", "條件"],
                          "include_condition": True, "polarities": ["不會"]})
        self.assertEqual(front[1]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["代價"], "polarities": ["不能", "只能"]})


OBJECT_ACTIONS = [["破壞"], ["特殊召喚"], ["解放"], ["除外"], []]


def object_parity_fixture():
    from test_object_self import self_fixture
    structures, cards, archetypes = parity_fixture()
    more, more_cards, more_archetypes = self_fixture()
    rows = {row["setcode"]: row for row in archetypes + more_archetypes}
    return (sorted(structures + more, key=lambda s: s["id"]),
            sorted(cards + more_cards, key=lambda entry: entry["id"]), list(rows.values()))


class ObjectParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.structures, cls.cards, archetypes = object_parity_fixture()
        text, report = build_action_index(cls.structures, cls.cards,
                                          [{"id": entry["id"]} for entry in cls.cards], archetypes)
        assert not report["problems"], report["problems"]
        cls.conds = [{"actions": actions, "target": target} for actions in OBJECT_ACTIONS
                     for target in ["this_card"] + [{"card": entry["id"]} for entry in cls.cards]]
        cls.front = front_end(text, cls.cards, cls.conds)

    def test_object_conditions_hit_the_same_cards(self):
        for cond, front in zip(self.conds, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]),
                                 sorted(python["groups"]["全部"] + python["groups"]["經引用"]))
                self.assertEqual(sorted(front["unsure"]), sorted(python["groups"]["未解析"]))
        found = [(cond, set(front["ids"]), set(front["unsure"]))
                 for cond, front in zip(self.conds, self.front)]
        self.assertTrue(any(ids for cond, ids, _ in found if cond["target"] == "this_card"))
        card_hits = [ids for cond, ids, _ in found if cond["target"] != "this_card"]
        self.assertTrue(any(card_hits))
        generic = set(run_query(self.structures, self.cards, {"actions": ["破壞"]})["groups"]["泛用"])
        self.assertTrue(generic & set().union(*card_hits))
        no_text = {entry["id"] for entry in self.cards} - {s["id"] for s in self.structures
                                                          if not s["unparsed"]}
        self.assertTrue(any(unsure - no_text for cond, _, unsure in found
                            if cond["target"] != "this_card"))

    def test_object_condition_becomes_the_row_query(self):
        self.assertEqual(self.front[0]["rowQuery"]["this_card"], True)
        self.assertEqual(self.front[1]["rowQuery"]["card"], self.conds[1]["target"]["card"])


CONDITION_ACTIONS = [["特殊召喚"], ["破壞"], ["除外"], ["加入手牌"], []]
CONDITIONS = [
    {"cat": "m"}, {"cat": "s"}, {"cat": "t"},
    {"attr": "water"}, {"attr": "earth"}, {"attr": "dark"}, {"attr": "light"}, {"attr": "wind"},
    {"race": "aqua"}, {"race": "plant"}, {"race": "dragon"}, {"race": "warrior"},
    {"race": "beast"},
    {"lvMin": 5}, {"lvMax": 4}, {"lvMin": 4, "lvMax": 4}, {"lvMin": 12},
    {"race": "plant", "lvMax": 4},
    {"name": "ペンギン"}, {"name": "ドラゴン"}, {"name": "N・"}, {"name": "落とし穴"},
    {"name": "沒有這張"},
    {"race": "dragon", "lvMin": 5}, {"cat": "m", "attr": "water", "name": "ペンギン"},
    {"set": 0x5a, "race": "aqua"}, {"cat": "t", "set": 0x4c},
] + [
    {"name": "企鵝士"}, {"name": "penguin SOL"}, {"name": "企鵝兵"}, {"name": "Trap Hole"},
    {"name": "企%兵"}, {"name": "ペン%ソル"}, {"name": "兵%企"}, {"name": "%落%穴%"},
    {"name": "ＰＥＮＧＵＩＮ"}, {"name": "ｔｒａｐ　ｈｏｌｅ"}, {"name": "企鵝％兵"},
    {"cat": "m", "name": "%"}, {"cat": "t", "name": " ％ "},
]
# 卡名包含比中文名、日文名、英文名與別名(中文卡文「※ 別名」):給幾張卡補上這三種名字。
OTHER_NAMES = {
    PENGUIN_SOLDIER: {"name_zh": "企鵝士兵", "name_en": "Penguin Soldier",
                      "desc": "①：這樣。\n\n※企鵝兵"},
    OTOSHIANA: {"name_zh": "落穴", "name_en": "Trap Hole"},
}


def web_index():
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")
    if here not in sys.path:
        sys.path.append(here)
    import vocab
    import webindex
    return vocab, webindex


class ConditionParityTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.vocab, webindex = web_index()
        cls.structures, cards, archetypes = object_parity_fixture()
        cls.cards = [{**entry, **OTHER_NAMES.get(entry["id"], {})} for entry in cards]
        cls.front_index, _ = webindex.build_index(cls.cards, [])
        text, report = build_action_index(cls.structures, cls.cards, cls.front_index["cards"],
                                          archetypes)
        assert not report["problems"], report["problems"]
        cls.text = text
        cls.archetypes = decode_action_index(text)["archetypes"]
        conditions = CONDITIONS + [{"set": code} for code in sorted(cls.archetypes)]
        cls.conds = [{"actions": actions, "target": {"condition": condition}}
                     for actions in CONDITION_ACTIONS for condition in conditions]
        cls.front = front_end(text, cls.cards, cls.conds, cls.front_index)

    def test_given_conditions_hit_the_same_cards(self):
        for cond, front in zip(self.conds, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]),
                                 sorted(python["groups"]["全部"] + python["groups"]["經引用"]))
                self.assertEqual(sorted(front["unsure"]), sorted(python["groups"]["未解析"]))

    def test_given_conditions_ask_something(self):
        hits = {json.dumps(c, ensure_ascii=False, sort_keys=True): set(f["ids"])
                for c, f in zip(self.conds, self.front)}

        def of(condition, actions=("特殊召喚",)):
            return hits[json.dumps({"actions": list(actions), "target": {"condition": condition}},
                                   ensure_ascii=False, sort_keys=True)]
        everything = set().union(*hits.values())
        for kind in ("cat", "attr", "race", "lvMin", "lvMax", "set", "name"):
            asked = [set(f["ids"]) for c, f in zip(self.conds, self.front)
                     if set(c["target"]["condition"]) == {kind}]
            with self.subTest(kind=kind):
                self.assertTrue(any(asked))
                self.assertTrue(any(ids < everything for ids in asked))
        both = of({"race": "dragon", "lvMin": 5}, ())
        self.assertTrue(both)
        self.assertTrue(of({"race": "dragon"}, ()) - both)
        self.assertTrue(of({"lvMin": 5}, ()) - both)
        self.assertEqual(of({"race": "dragon"}), {CHOBHAM})
        self.assertIn(EMPEROR_PENGUIN, of({"race": "aqua"}))
        for text in ("企鵝士", "penguin SOL", "企鵝兵", "企%兵", "ＰＥＮＧＵＩＮ", "企鵝％兵"):
            self.assertIn(EMPEROR_PENGUIN, of({"name": text}), text)
        self.assertEqual(of({"name": "兵%企"}, ()), set())
        self.assertTrue(of({"name": "落とし穴"}, ()))
        for text in ("Trap Hole", "ｔｒａｐ　ｈｏｌｅ", "%落%穴%"):
            self.assertEqual(of({"name": text}, ()), of({"name": "落とし穴"}, ()), text)
        self.assertEqual(of({"cat": "m", "name": "%"}), of({"cat": "m"}))

    def test_archetype_members_are_what_python_calls_members(self):
        structure = {s["id"]: s for s in self.structures}
        self.assertTrue(self.archetypes)
        for code, row in self.archetypes.items():
            condition = {"op": "字段", "setcodes": [code]}
            members = {entry["id"] for entry in self.cards
                       if eval_condition(condition, CardView(entry, structure.get(entry["id"])))
                       is True}
            self.assertEqual(set(row["members"]), members, hex(code))

    def test_every_canon_button_asks_python_the_same_value(self):
        python_value = {"cat": CATEGORY_BITS, "attr": ATTRIBUTE_JA, "race": RACE_JA}
        domains = {"cat": self.vocab.CAT, "attr": self.vocab.ATTR, "race": self.vocab.RACE}
        conds = [{"target": {"condition": {key: e["code"]}}}
                 for key, name in domains.items() for e in self.vocab.entries(name)]
        front = front_end(self.text, self.cards, conds, self.front_index)
        for cond, result in zip(conds, front):
            [(key, code)] = cond["target"]["condition"].items()
            with self.subTest(cond=cond):
                atom = result["rowQuery"].get("condition")
                self.assertIsNotNone(atom)
                bit = next(e["src"] for e in self.vocab.entries(domains[key]) if e["code"] == code)
                self.assertEqual(python_value[key].get(atom["value"]), bit)

    def test_given_condition_becomes_the_row_query(self):
        rq = self.front[0]["rowQuery"]
        self.assertEqual(rq["condition"], {"op": "大類", "value": "怪獸"})
        self.assertNotIn("card", rq)
        self.assertNotIn("this_card", rq)


if __name__ == "__main__":
    unittest.main()
