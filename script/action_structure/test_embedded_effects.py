"""內嵌效果擴充(m2 票 12):依值分支、效果被換掉、以下の効果を持つ装備カード扱い。

走接縫一(查詢判斷)與接縫二(反向檢查);查詢層沒有的格(`pick`、前提、物件條件…)先用查詢命中段,
再讀該段的格。官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
"""
import unittest

from action_query import run_query
from card_structure import build_structures, load_structures, serialize_structures
from reverse_check import check_card
from structure_shape import iter_segments
from test_golden import ARCHETYPES, card, faq

ARCHETYPES_12 = ARCHETYPES + [
    {"setcode": 0x6, "hex": "0x6", "names_ja": ["暗黒界"], "name_zh": "暗黑界",
     "source": "strings.conf"},
    {"setcode": 0x26, "hex": "0x26", "names_ja": ["Ｄ", "ディフォーマー"], "name_zh": "變形鬥士",
     "source": "strings.conf"},
    {"setcode": 0x95, "hex": "0x95", "names_ja": ["ＲＵＭ"], "name_zh": "升階魔法",
     "source": "strings.conf"},
    {"setcode": 0xba, "hex": "0xba", "names_ja": ["ＲＲ"], "name_zh": "RR-",
     "source": "strings.conf"},
]


def build(cards, faqs):
    structures, _ = build_structures(cards, faqs, archetypes=ARCHETYPES_12)
    return structures


def own(structures, cid):
    return next(s for s in structures if s["id"] == cid)


def hit_segments(structures, cards, cid, **query):
    """查詢命中某卡的段(含內嵌效果的段);沒命中回空列表。"""
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == cid), [])
    return [seg for b in own(structures, cid)["blocks"] for _, seg in iter_segments(b)
            if seg["id"] in ids]


def embedded_of(structure):
    """卡上全部內嵌效果節點(依區塊、段樹順序)。"""
    found = []
    stack = list(structure["blocks"])
    while stack:
        block = stack.pop(0)
        items = list(block["tree"]["items"])
        while items:
            node = items.pop(0)
            if node["node"] == "內嵌效果":
                found.append(node)
                if node.get("block"):
                    stack.append(node["block"])
            elif node["node"] == "分歧":
                for branch in node["branches"]:
                    items.extend(branch["items"])
    return found


BRAVE_STRIX = 8617563   # RR－ブレイブ・ストリクス
BRAVE_STRIX_TEXT = (
    "レベル５モンスター×２\n"
    "このカード名の①②の効果は１ターンに１度、いずれか１つしか使用できない。\n"
    "①：このカードのX素材を１つ取り除いて発動できる。デッキから「RR」魔法・罠カード１枚を"
    "自分フィールドにセットする。\n"
    "②：このカードが鳥獣族モンスターをX素材としている場合、このカードのX素材を１つ取り除いて"
    "発動できる。デッキから「RUM」魔法カード１枚を手札に加える。\n"
    "③：このカードを素材として持っている「RR」Xモンスターは以下の効果を得る。\n"
    "●このカードの攻撃力は、自身のランク×１００アップする。")


class BraveStrixTest(unittest.TestCase):
    """RR－ブレイブ・ストリクス 8617563 ③:內嵌效果裡的增減段讓整張卡命中,段 id 帶 e。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(BRAVE_STRIX, name_ja="RR－ブレイブ・ストリクス", type=0x800021,
                          level=5, race=0x200, attribute=0x20, atk=2000,
                          **{"def": 2500}, setcode=0xba)]
        cls.structures = build(cls.cards, [faq(BRAVE_STRIX, "RR－ブレイブ・ストリクス",
                                               BRAVE_STRIX_TEXT)])

    def test_embedded_attack_up_hits_with_e_segment(self):
        segs = hit_segments(self.structures, self.cards, BRAVE_STRIX, actions=["性質變更"],
                            modified={"attr": "攻擊力", "form": "增"})
        self.assertEqual(len(segs), 1)
        self.assertIn("e", segs[0]["id"].split(".")[0])


DARK_WORLD_BRAINWASH = 10131855   # 暗黒界の洗脳
DARK_WORLD_BRAINWASH_TEXT = (
    "①：自分の手札が３枚以上存在し、相手がモンスターの効果を発動した時、フィールドの「暗黒界」"
    "モンスター１体を対象としてこの効果を発動できる。対象のモンスターを持ち主の手札に戻し、"
    "その相手の効果は「相手の手札をランダムに１枚選んで捨てる」となる。")


class DarkWorldBrainwashTest(unittest.TestCase):
    """暗黒界の洗脳 10131855:效果被換掉,引號裡的方先對調再存(綁定 我方 = 對手)。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(DARK_WORLD_BRAINWASH, name_ja="暗黒界の洗脳", type=0x20004,
                          setcode=0x6)]
        cls.structures = build(cls.cards, [faq(DARK_WORLD_BRAINWASH, "暗黒界の洗脳",
                                               DARK_WORLD_BRAINWASH_TEXT)])
        cls.structure = own(cls.structures, DARK_WORLD_BRAINWASH)

    def discard(self, side):
        return hit_segments(self.structures, self.cards, DARK_WORLD_BRAINWASH,
                            actions=["捨棄"], from_zones=[{"zone": "手牌", "side": side}])

    def test_discard_from_own_hand_hits_after_swap(self):
        segs = self.discard("我方")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["lines"][0]["pick"], "隨機")

    def test_discard_from_opponent_hand_does_not_hit(self):
        self.assertEqual(self.discard("對手"), [])

    def test_binding_swaps_sides(self):
        node, = embedded_of(self.structure)
        self.assertEqual(node["binding"]["我方"], "對手")

    def test_reverse_check_writes_back_opponent_hand(self):
        """存的是我方手牌,反向檢查依綁定對調回去,原文「相手の手札を」比得上;引導句不留殘留。"""
        seg, = self.discard("我方")
        block_id = seg["id"].split(".")[0]
        failures = check_card(self.structure)
        self.assertEqual([f for f in failures if f["block"] == block_id], [])
        self.assertEqual([f for f in failures if f["segment"] is None], [])


D_SCANNAN = 1876841   # D・スキャナン
D_SCANNAN_TEXT = (
    "このカードは通常召喚できない。手札から「D」モンスター１体を除外した場合に特殊召喚できる。"
    "①：このカードは表示形式によって以下の効果を得る。"
    "●攻撃表示：１ターンに１度、自分メインフェイズに発動できる。デッキから「D」魔法・罠カード"
    "１枚を手札に加える。その後、手札を１枚選んでデッキの一番上に戻す。"
    "●守備表示：１ターンに１度、自分メインフェイズに発動できる。自分の墓地からレベル４以下の"
    "「D」モンスター１体を選んで手札に加える。その後、手札を１枚選んでデッキの一番上に戻す。")


class DScannanTest(unittest.TestCase):
    """D・スキャナン 1876841 ①:依值分支型「〜によって以下の効果を得る」→ 一個內嵌效果節點,
    內容是依前提分歧,每個 ● 的標籤(攻撃表示/守備表示)是那一支的前提。"""

    @classmethod
    def setUpClass(cls):
        cls.cards = [card(D_SCANNAN, name_ja="D・スキャナン", type=0x2000021, level=6,
                          race=0x20, attribute=0x1, atk=1500, **{"def": 600}, setcode=0x26)]
        cls.structures = build(cls.cards, [faq(D_SCANNAN, "D・スキャナン", D_SCANNAN_TEXT)])
        cls.structure = own(cls.structures, D_SCANNAN)

    def test_one_embedded_node_branching_on_position(self):
        node, = embedded_of(self.structure)
        self.assertEqual(node["binding"], {"自己": "o0"})
        tree = node["block"]["tree"]["items"]
        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["mode"], "依前提")
        self.assertEqual([b["premise"].get("position") for b in tree[0]["branches"]],
                         ["攻擊", "守備"])
        self.assertEqual([b["premise"]["object"] for b in tree[0]["branches"]], ["o0", "o0"])

    def test_both_branches_add_to_hand(self):
        from_deck = hit_segments(self.structures, self.cards, D_SCANNAN,
                                 actions=["加入手牌"], from_zones=["牌組"])
        from_grave = hit_segments(self.structures, self.cards, D_SCANNAN,
                                  actions=["加入手牌"], from_zones=["墓地"])
        self.assertEqual(len(from_deck), 1)
        self.assertEqual(len(from_grave), 1)
        self.assertIn("e", from_deck[0]["id"].split(".")[0])

    def test_whole_card_passes_reverse_check(self):
        self.assertEqual(check_card(self.structure), [])

    def test_round_trip(self):
        text = serialize_structures(self.structures)
        self.assertEqual(load_structures(text), self.structures)


if __name__ == "__main__":
    unittest.main()
