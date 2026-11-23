"""兩邊答案一致(action-search-web spec 測試決策;票 08 起):同一份動作索引、同一批查詢,
Python 的 `run_query` 與網站的前端查詢引擎命中同一批卡。

測試內建的卡片結構建成動作索引(`build_action_index`),連同前端索引的卡與一批動作條件交給
node(`script/web/action_parity.js`,在接縫三的沙箱裡載入 `web/` 底下真實的前端檔)。前端把每條
動作條件換成列查詢、查出命中的卡;同一份列查詢交給 `run_query`,比命中的卡號(特定與泛用;
經引用由票 14 加、無法確認的卡由票 15 加)。之後每張加篩選的票都往 `CONDS` 加查詢。

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
from test_effect_reference import ARCHETYPES_13
from test_golden import card, faq
from test_resistance_restriction import (ELEKIRIN, ELEKIRIN_TEXT, MASTER_MONK, MASTER_MONK_TEXT,
                                         RESISTANCE_ARCHETYPES, SERVAL_HAWK, SERVAL_HAWK_TEXT)

PARITY_JS = os.path.join(os.path.dirname(__file__), "..", "web", "action_parity.js")

# 玩家介面的動作條件。夾具裡:破壞在效果段、代價段、條件段與「不會」的段都有;特殊召喚在條件段
# 與效果段;解放在代價段(大皇帝ペンギン,與效果段的特殊召喚分在兩段)與召喚手續段(マスターモンク);
# 直接攻撃是「可以」(エレキリン)與「不能」(幻獣機サーバルホーク)。
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
    # 誰與「含不限定的」(票 10;夾具裡效果段、代價段、召喚手續段都是算我方,
    # 不限定的段與寫明對手的段另在 `test_agent_unrestricted.AgentParityTest` 的夾具)
    {"actions": ["破壞"], "agent": "我方"},
    {"actions": ["破壞"], "agent": "對手"},
    {"actions": ["破壞"], "agent": "對手", "unrestricted": True},
    {"actions": ["解放"], "agent": "我方", "unrestricted": True},
]


def parity_fixture():
    structures, cards, _ = fixture()
    extra = [card(ELEKIRIN, name_ja="エレキリン"), card(MASTER_MONK, name_ja="マスターモンク"),
             card(SERVAL_HAWK, name_ja="幻獣機サーバルホーク")]
    archetypes = {row["setcode"]: row for row in ARCHETYPES_13 + RESISTANCE_ARCHETYPES}
    more, _ = build_structures(extra, [
        faq(ELEKIRIN, "エレキリン", ELEKIRIN_TEXT),
        faq(MASTER_MONK, "マスターモンク", MASTER_MONK_TEXT),
        faq(SERVAL_HAWK, "幻獣機サーバルホーク", SERVAL_HAWK_TEXT),
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
        cls.front = front_end(text, cls.cards, CONDS)

    def test_player_defaults_become_the_row_query(self):
        """玩家介面的預設(spec「玩家介面」對應表):勾效果與代價、極性「會做」。"""
        self.assertEqual(self.front[0]["rowQuery"],
                         {"actions": ["破壞"], "kinds": ["效果", "召喚手續", "限制", "代價"],
                          "polarities": ["做", "可以", "必須"]})

    def test_action_words_hit_the_same_cards(self):
        """同一批動作詞查詢(單一、同一段多個),Python 與前端引擎命中的卡號相同。"""
        for cond, front in zip(CONDS, self.front):
            with self.subTest(cond=cond):
                python = run_query(self.structures, self.cards, front["rowQuery"])
                self.assertEqual(sorted(front["ids"]), sorted(python["groups"]["全部"]))
        # 夾具要問得出東西:有命中、也有「同一張卡分在兩段」被擋掉的
        hits = {tuple(c["actions"]): set(f["ids"]) for c, f in zip(CONDS, self.front)
                if set(c) == {"actions"}}
        self.assertTrue(hits[("破壞",)])
        both = hits[("解放",)] & hits[("特殊召喚",)]
        self.assertTrue(both)
        self.assertFalse(both & hits[("解放", "特殊召喚")])


if __name__ == "__main__":
    unittest.main()
