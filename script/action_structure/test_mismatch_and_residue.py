"""寫得出就要與原文相符:反向檢查不該出現「字面不符」與「段外殘留」的幾種寫法。

只走接縫一(查詢判斷)與接縫二(反向檢查);官方文本逐字寫在測試裡(`data/sources/` 不入版控)。
- 句中的次數限制(「〜限り１度だけ、」「自分ターンに１度、」)落在條件段裡:觸發形後面的「に」照舊是接著詞。
- 召喚條件區塊裡的條件子句「自分が〜の召喚に成功した時」:誰的接法照條件子句(が)。
- 「属性がそのモンスターと同じで攻撃力〜」:「同じで」後面沒有讀點的寫法。
- 「魔法＆罠ゾーンにセットされたこのカードが墓地へ送られた」:物件前的「〜に」是物件的狀態,不是到。
"""
import unittest

from action_query import run_query
from card_structure import build_structures
from reverse_check import check_card
from test_golden import SPELL, card, faq

MISMATCH, RESIDUE = "字面不符", "段外殘留"


def build(cid, name, text, archetypes=(), **params):
    cards = [card(cid, name_ja=name, **params)]
    structures, _ = build_structures(cards, [faq(cid, name, text)], list(archetypes))
    return cards, structures, structures[0]


def failures(own, *reasons):
    """反向檢查的不通過筆裡,原因是 `reasons` 的 (原因, 段原文, 細節);段外殘留的段原文是 None。"""
    texts = {s["id"]: s["text"] for b in own["blocks"] for s in b["segments"]}
    return [(f["reason"], texts.get(f["segment"]), f["detail"]) for f in check_card(own)
            if f["reason"] in reasons]


def hit_texts(cards, structures, own, **query):
    result = run_query(structures, cards, query)
    ids = next((h["segments"] for h in result["hits"] if h["id"] == own["id"]), [])
    return [s["text"] for b in own["blocks"] for s in b["segments"] if s["id"] in ids]


BARONNE = 84815190   # フルール・ド・バロネス
BARONNE_TEXT = (
    "チューナー＋チューナー以外のモンスター１体以上\n"
    "このカード名の②の効果は１ターンに１度しか使用できない。①：１ターンに１度、フィールドのカード１枚を"
    "対象として発動できる。そのカードを破壊する。②：このカードがフィールドに表側表示で存在する限り"
    "１度だけ、魔法・罠・モンスターの効果が発動した時に発動できる。その発動を無効にし破壊する。"
    "③：お互いのスタンバイフェイズに、自分の墓地のレベル９以下のモンスター１体を対象として発動できる。"
    "このカードを持ち主のEXデッキに戻し、対象のモンスターを特殊召喚する。")
SANGA = 25955164   # 雷魔神－サンガ
SANGA_TEXT = (
    "①：このカードがフィールドに表側表示で存在する限り１度だけ、このカードが攻撃されたダメージ計算時に、"
    "攻撃モンスター１体を対象として発動できる。その攻撃モンスターの攻撃力を０にする。")
TEMUJIN = 16006416   # DDD烈火大王エグゼクティブ・テムジン
TEMUJIN_TEXT = (
    "レベル５以上の「DD」モンスター＋「DD」モンスター\n"
    "このカード名の①の効果は１ターンに１度しか使用できない。\n"
    "①：このカードがモンスターゾーンに存在する状態で、自分フィールドに「DD」モンスターが"
    "召喚・特殊召喚された場合、自分の墓地の「DD」モンスター１体を対象として発動できる。"
    "そのモンスターを特殊召喚する。\n"
    "②：自分ターンに１度、魔法・罠カードの効果が発動した時に発動できる。その発動を無効にする。")


class IntervalInsideConditionSegmentTest(unittest.TestCase):
    """句中的次數限制落在條件段的範圍裡(前提與條件子句之間):不記、進略過文本,
    條件段後面的「に(発動できる)」照舊是接著詞,不留成段外殘留。"""

    def test_baronne_negate_block_writes_back(self):
        """フルール・ド・バロネス ②「〜存在する限り１度だけ、〜効果が発動した時に発動できる」:
        沒有段外殘留,開條件段查「發動」命中條件段。"""
        cards, structures, own = build(BARONNE, "フルール・ド・バロネス", BARONNE_TEXT,
                                       type=0x2021, level=10, race=0x1, attribute=0x8, atk=3000)
        self.assertEqual(failures(own, RESIDUE, MISMATCH), [])
        self.assertIn("このカードがフィールドに表側表示で存在する限り１度だけ、"
                      "魔法・罠・モンスターの効果が発動した時",
                      hit_texts(cards, structures, own, actions=["發動"], include_condition=True))

    def test_sanga_battle_timing_followed_by_ni_and_comma(self):
        """雷魔神－サンガ「〜限り１度だけ、このカードが攻撃されたダメージ計算時に、〜」:觸發形是時點字面,
        後面的「に、」不留成段外殘留。"""
        _, _, own = build(SANGA, "雷魔神－サンガ", SANGA_TEXT, level=7, race=0x1000,
                          attribute=0x10, atk=2600)
        self.assertEqual(failures(own, RESIDUE, MISMATCH), [])

    def test_temujin_once_per_own_turn(self):
        """DDD烈火大王エグゼクティブ・テムジン ②「自分ターンに１度、〜効果が発動した時に発動できる」。"""
        _, _, own = build(TEMUJIN, "DDD烈火大王エグゼクティブ・テムジン", TEMUJIN_TEXT,
                          type=0x61, level=8, race=0x8, attribute=0x4, atk=2800)
        self.assertEqual(failures(own, RESIDUE, MISMATCH), [])


OURURI = 54582424   # 幻蝶の刺客オオルリ
OURURI_TEXT = ("このカードは通常召喚できない。自分が戦士族モンスターの召喚に成功した時、"
               "このカードを手札から特殊召喚できる。このカードはシンクロ素材にできない。")
MAGNATOR = 50702124   # シンクロ・マグネーター
MAGNATOR_TEXT = ("このカードは通常召喚できない。自分がシンクロモンスターのシンクロ召喚に成功した時、"
                 "このカードを手札から特殊召喚する事ができる。")


class AgentInSummonConditionBlockTest(unittest.TestCase):
    """召喚條件區塊的「自分が〜召喚に成功した時、このカードを手札から特殊召喚できる」:條件子句是召喚手續段,
    誰的接法仍照條件子句寫「自分が」。"""

    def test_oururi_and_magnator_write_back(self):
        for cid, name, text, clause in (
                (OURURI, "幻蝶の刺客オオルリ", OURURI_TEXT,
                 "自分が戦士族モンスターの召喚に成功した時"),
                (MAGNATOR, "シンクロ・マグネーター", MAGNATOR_TEXT,
                 "自分がシンクロモンスターのシンクロ召喚に成功した時")):
            with self.subTest(card=name):
                cards, structures, own = build(cid, name, text)
                self.assertEqual(check_card(own), [])
                self.assertIn(clause, hit_texts(cards, structures, own, actions=["通常召喚"])
                              + hit_texts(cards, structures, own, actions=["S召喚"]))


STRATAGEM = 63899196   # 帝王の策略
STRATAGEM_TEXT = (
    "このカード名の②の効果は１ターンに１度しか使用できない。\n"
    "①：デッキから「帝王の策略」以外の「帝王」魔法・罠カード１枚を墓地へ送る。\n"
    "②：このカードが除外された場合、相手フィールドの表側表示モンスター１体を対象として発動できる。"
    "属性がそのモンスターと同じで攻撃力２４００／守備力１０００のモンスター１体を自分のデッキ・墓地から"
    "手札に加える。その後、以下の効果を適用できる。\n"
    "●「雷帝ザボルグ」「氷帝メビウス」「炎帝テスタロス」「地帝グランマーグ」「風帝ライザー」"
    "「邪帝ガイウス」のいずれか１体の召喚を行う。")
STRATAGEM_SEARCH = ("属性がそのモンスターと同じで攻撃力２４００／守備力１０００のモンスター１体を"
                    "自分のデッキ・墓地から手札に加える")
MONARCH_ARCHETYPES = [{"setcode": 0xbe, "hex": "0xbe", "names_ja": ["帝王"], "name_zh": "帝王",
                       "source": "strings.conf"}]
SYNTHETIC = 10006001


class SameAsWithoutPauseTest(unittest.TestCase):
    """「属性がそのモンスターと同じで」後面有沒有讀點都照字面寫回。"""

    def test_stratagem_search_writes_back(self):
        """帝王の策略 ②:「同じで」後面直接接下一個條件;那一段命中「加入手牌,從牌組」並寫回原文相符。"""
        cards, structures, own = build(STRATAGEM, "帝王の策略", STRATAGEM_TEXT, MONARCH_ARCHETYPES,
                                       type=SPELL, setcode=0xbe)
        self.assertEqual(hit_texts(cards, structures, own, actions=["加入手牌"],
                                   from_zones=["牌組"]), [STRATAGEM_SEARCH])
        self.assertEqual(failures(own, MISMATCH), [])
        self.assertNotIn(STRATAGEM_SEARCH,
                         [text for _, text, _ in failures(own, "無模板", MISMATCH)])

    def test_with_and_without_pause_both_write_back(self):
        for pause in ("、", ""):
            with self.subTest(pause=pause):
                _, _, own = build(
                    SYNTHETIC, "甲",
                    "①：相手フィールドのモンスター１体を対象として発動できる。"
                    f"属性がそのモンスターと同じで{pause}攻撃力２４００のモンスター１体をデッキから手札に加える。")
                self.assertEqual(check_card(own), [])


TOY_SOLDIER = 65504487   # トイ・ソルジャー
TOY_SOLDIER_TEXT = (
    "このカード名の②③の効果はそれぞれ１ターンに１度しか使用できない。\n"
    "①：このカードは魔法カード扱いで手札から魔法＆罠ゾーンにセットできる。\n"
    "②：魔法＆罠ゾーンにセットされたこのカードが墓地へ送られた場合に発動できる。"
    "このカードを特殊召喚する。\n"
    "③：このカードが召喚・特殊召喚した場合に発動できる。デッキから「トイ・ボックス」１枚を手札に加える。"
    "自分フィールドに「トイ・ボックス」が存在する場合、代わりに光属性・レベル４モンスター１体を"
    "手札に加える事もできる。")
TOY_SOLDIER_SENT = "魔法＆罠ゾーンにセットされたこのカードが墓地へ送られた場合"


class PlaceBeforeTheObjectIsItsStateTest(unittest.TestCase):
    """「魔法＆罠ゾーンにセットされたこのカードが墓地へ送られた」:述語自己寫了到(墓地)時,物件前的
    「魔法＆罠ゾーンに」不是到,是物件的狀態(覆蓋在魔陷區的此卡)。"""

    def test_toy_soldier_is_sent_to_the_graveyard_not_to_the_spell_trap_zone(self):
        cards, structures, own = build(TOY_SOLDIER, "トイ・ソルジャー", TOY_SOLDIER_TEXT,
                                       level=4, race=0x1, attribute=0x10, atk=1500)
        sent = dict(actions=["送墓"], include_condition=True, kinds=["條件"], card=TOY_SOLDIER)
        self.assertEqual(hit_texts(cards, structures, own, to_zones=["墓地"], **sent),
                         [TOY_SOLDIER_SENT])
        self.assertEqual(hit_texts(cards, structures, own, to_zones=["魔陷區"], **sent), [])
        self.assertEqual(hit_texts(cards, structures, own, from_zones=["魔陷區"], **sent),
                         [TOY_SOLDIER_SENT])
        self.assertEqual(failures(own, MISMATCH), [])
        self.assertNotIn(TOY_SOLDIER_SENT,
                         [text for _, text, _ in failures(own, "無模板", MISMATCH)])


if __name__ == "__main__":
    unittest.main()
