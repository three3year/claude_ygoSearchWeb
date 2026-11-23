"""兩邊答案一致(action-search-web spec 測試決策;票 08 起):同一份動作索引、同一批查詢,
Python 的 `run_query` 與網站的前端查詢引擎命中同一批卡。

測試內建的卡片結構建成動作索引(`build_action_index`),連同前端索引的卡與一批動作條件交給
node(`script/web/action_parity.js`,在接縫三的沙箱裡載入 `web/` 底下真實的前端檔)。前端把每條
動作條件換成列查詢、查出命中的卡;同一份列查詢交給 `run_query`,比命中的卡號(特定、泛用、
經引用的聯集,票 14)與無法確認的卡號(未解析組,票 15)。之後每張加篩選的票都往 `CONDS` 加查詢。

這組測試需要機器上有 node(spec「測試從哪幾個接縫驗」的決定)。
"""
import json
import os
import shutil
import subprocess
import unittest

from action_index import build_action_index
from action_query import run_query
from card_structure import build_structures
from test_action_index import fixture
from test_draw import (DARK_WORLD_DEALINGS, DARK_WORLD_DEALINGS_TEXT, SPELL, TSUPPA_REACH,
                       TSUPPA_REACH_TEXT)
from test_effect_reference import (ARCHETYPES_13, BLACK_PANTHER, BLACK_PANTHER_TEXT, DESTROYER,
                                   DESTROYER_TEXT, FRESHIA, GISHIKI_MIRROR, GISHIKI_MIRROR_TEXT,
                                   HOSHIAI, HOSHIAI_TEXT, NORMAL_TRAP, RITUAL_SPELL)
from test_golden import card, faq
from test_resistance_restriction import (ELEKIRIN, ELEKIRIN_TEXT, MASTER_MONK, MASTER_MONK_TEXT,
                                         RESISTANCE_ARCHETYPES, SERVAL_HAWK, SERVAL_HAWK_TEXT)

PARITY_JS = os.path.join(os.path.dirname(__file__), "..", "web", "action_parity.js")

# 玩家介面的動作條件。夾具裡:破壞在效果段、代價段、條件段與「不會」的段都有;特殊召喚在條件段
# 與效果段;解放在代價段(大皇帝ペンギン,與效果段的特殊召喚分在兩段)與召喚手續段(マスターモンク);
# 直接攻撃是「可以」(エレキリン)與「不能」(幻獣機サーバルホーク)。
# 經引用(票 14):フレシアの蟲惑魔 引用落とし穴、奈落の落とし穴(破壞、除外);星逢の天河 只引用
# 氷魔鏡含儀式召喚的區塊(儀式召喚收、返回不收);甲、乙的候選卡是甲、乙、星逢の天河(成環;
# 加入手牌時經星逢 ① 收);Ｎ・ブラック・パンサー 是泛用引用(破壞者有破壞,泛用引用固定關,不收)。
CONDS = [
    {"actions": ["破壞"]},
    {"actions": ["特殊召喚"]},
    {"actions": ["解放"]},
    {"actions": ["直接攻擊"]},
    {"actions": ["通常召喚"]},
    {"actions": ["除外"]},
    {"actions": ["破壞", "除外"]},          # 同一段裡兩個都有
    {"actions": ["解放", "特殊召喚"]},      # 同一張卡、不同段
    {"actions": ["破壞", "特殊召喚"]},
    {"actions": ["不存在的動作"]},
    {"actions": ["儀式召喚"]},
    {"actions": ["返回"]},
    {"actions": ["加入手牌"]},
] + [
    # 票 09:從、到(含哪一方、子區域、推得的不算)、段類別勾選、極性三選一。夾具裡:
    # 特殊召喚從我方牌組(大皇帝ペンギン);除外從墓地到除外(幻獣機サーバルホーク);
    # 送墓是代價、從我方牌組到墓地(特異点の悪魔);抽牌從我方牌組(ツッパリーチ)與
    # 雙方各自的牌組(暗黒界の取引);ツッパリーチ回到牌組底(子區域,查牌組也算)。
    {"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "我方"}},
    {"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "對手"}},
    {"actions": ["特殊召喚"], "to": {"zone": "場上"}},              # 到場上全是推得的
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


def front_end(action_text, cards, conds):
    """動作條件 → 前端那一邊的 [{"rowQuery", "ids"}]。"""
    node = shutil.which("node")
    if node is None:
        # 不跳過:跳過的話少了這組檢查也是綠的(spec 接受「這組測試需要 node」)
        raise RuntimeError("機器上沒有 node:「兩邊答案一致」的測試需要 node")
    payload = {"actionData": action_text,
               "cards": [{"id": entry["id"], "n": entry["name_zh"]} for entry in cards],
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
        """玩家介面的預設(spec「玩家介面」對應表):勾效果與代價、極性「會做」。"""
        self.assertEqual(self.front[0]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["效果", "召喚手續", "限制", "代價"],
                          "polarities": ["做", "可以", "必須"]})

    def test_action_words_hit_the_same_cards(self):
        """同一批動作詞查詢(單一、同一段多個、經引用),Python 與前端引擎命中的卡號相同:
        特定、泛用、經引用的聯集(網站的清單不分組)。"""
        for cond, front in zip(CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]),
                                 sorted(python["groups"]["全部"] + python["groups"]["經引用"]))
        # 夾具要問得出東西:有命中、也有「同一張卡分在兩段」被擋掉的
        hits = {tuple(c["actions"]): set(f["ids"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        self.assertTrue(hits[("破壞",)])
        both = hits[("解放",)] & hits[("特殊召喚",)]
        self.assertTrue(both)
        self.assertFalse(both & hits[("解放", "特殊召喚")])

    def test_via_reference_cases_are_asked(self):
        """夾具要問得出經引用:有經引用才收的卡、只看指定的部分、環、泛用引用不展開。"""
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
        """前端的無法確認的卡號與 `run_query` 的未解析組相同(spec 測試決策,票 15)。"""
        for cond, front in zip(CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["unsure"]), sorted(python["groups"]["未解析"]))
        # 夾具要問得出東西:有無官方日文以外的未解析卡;マスターモンク的解放命中,另有一段
        # 字面含解放的段解析不出,只在命中的清單
        unsure = {tuple(c["actions"]): set(f["unsure"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        hits = {tuple(c["actions"]): set(f["ids"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        self.assertTrue(unsure[("破壞",)] - unsure[("不存在的動作",)])
        self.assertIn(MASTER_MONK, hits[("解放",)])
        self.assertNotIn(MASTER_MONK, unsure[("解放",)])

    def test_zones_kinds_polarity_ask_something(self):
        """票 09 的查詢問得出東西:哪一方、子區域、推得的不算、觸發條件、抗性與限制各有分別。"""
        hits = {json.dumps(c, ensure_ascii=False, sort_keys=True): set(f["ids"])
                for c, f in zip(CONDS, self.front)}

        def of(cond):
            return hits[json.dumps(cond, ensure_ascii=False, sort_keys=True)]
        self.assertEqual(of({"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "我方"}}),
                         {6836211})
        self.assertFalse(of({"actions": ["特殊召喚"], "from": {"zone": "牌組", "side": "對手"}}))
        # 到場上全是推得的:不算
        self.assertFalse(of({"actions": ["特殊召喚"], "to": {"zone": "場上"}}))
        # 牌組底算在牌組內(另有經引用收進來的リチュアの氷魔鏡)
        self.assertIn(TSUPPA_REACH, of({"actions": ["返回"], "to": {"zone": "牌組"}}))
        # 勾觸發條件才查到條件段;抗性、限制查得到預設不命中的段
        self.assertTrue(of({"actions": ["特殊召喚"], "kinds": ["cond"]}) - of({"actions": ["特殊召喚"]}))
        self.assertEqual(of({"actions": ["破壞"], "pol": "resist"}), {6511113})
        # 預設的「會做」不直接命中它(它另有經引用的命中,所以看 run_query 的直接命中)
        default = next(f["rowQuery"] for c, f in zip(CONDS, self.front) if c == {"actions": ["破壞"]})
        self.assertNotIn(6511113, run_query(self.structures, self.cards, default)["groups"]["全部"])
        self.assertEqual(of({"actions": ["通常召喚"], "pol": "limit"}), {MASTER_MONK})
        self.assertFalse(of({"actions": ["通常召喚"]}))

    def test_kinds_and_polarity_become_the_row_query(self):
        """介面選項到查詢的對應(spec「玩家介面」對應表):勾觸發條件連條件段開關一起開。"""
        front = front_end(self.text, self.cards,
                          [{"actions": ["破壞"], "kinds": ["eff", "cost", "cond"], "pol": "resist"},
                           {"actions": ["破壞"], "kinds": ["cost"], "pol": "limit"}])
        self.assertEqual(front[0]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["效果", "召喚手續", "限制", "代價", "條件"],
                          "include_condition": True, "polarities": ["不會"]})
        self.assertEqual(front[1]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["代價"], "polarities": ["不能", "只能"]})


if __name__ == "__main__":
    unittest.main()
