"""建置的「補方」:卡文沒寫方、但照規則推得出方的區域,建置時寫進結構、來源記規則
(spec「規則推得的方」;票 02 做物件寫的控制方與場上沒寫方兩條)。"""
import unittest

from card_structure import build_structures
from reverse_check import check_card
from rule_sides import fill_rule_sides
from structure_shape import (iter_segments, new_block, new_card, new_line, new_object,
                             new_segment, position, zone)
from test_golden import card, faq


def build(text):
    structures, _ = build_structures([card(1, name_ja="補方テスト")],
                                     [faq(1, "補方テスト", text)])
    return structures[0]


def ends(text, action, end):
    """有這個動作詞的段,每條線的從或到 → [(區域, 方, 方的來源)]。"""
    out = []
    for block in build(text)["blocks"]:
        for _, seg in iter_segments(block):
            if action in seg["actions"]:
                for line in seg["lines"]:
                    pos = line[end]
                    out.append([(z["zone"], z["side"], z["side_source"])
                                for z in pos["zones"]] if pos else None)
    return out


class WrittenControllerTest(unittest.TestCase):
    """從的區域沒寫方、物件的條件式寫了控制方 → 照寫的方;到的區域不用這條。"""

    def test_from_takes_the_controller_written_on_the_object(self):
        self.assertEqual(ends("①：相手の表側表示モンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "對手", "規則")]])

    def test_controller_fills_every_sideless_zone_of_the_from(self):
        """「自分の手札・フィールド（表側表示）の」:「自分の」是物件的控制方,位置原子的區域沒有方;
        從的手牌也照控制方補(手牌只是不套場上、墓地那幾條)。"""
        self.assertEqual(ends("①：このカード以外の自分の手札・フィールド（表側表示）の炎属性モンスター"
                              "１体を破壊する。", "破壞", "from"),
                         [[("手牌", "我方", "規則"), ("場上", "我方", "規則")]])

    def test_either_side_controller(self):
        self.assertEqual(ends("①：自分または相手の表側表示モンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "任一方", "規則")]])

    def test_to_does_not_take_the_controller(self):
        """控制方說的是物件出發時的位置:到的場上沒寫方照場上那條記任一方,不是對手。"""
        self.assertEqual(ends("①：相手モンスター１体を対象として発動できる。"
                              "そのモンスターをフィールドに特殊召喚する。", "特殊召喚", "to"),
                         [[("場上", "任一方", "規則")]])

    def test_written_or_default_side_is_kept(self):
        """「墓地の相手モンスター」:墓地沒寫方是預設我方,已經有方,不照物件的控制方改。"""
        self.assertEqual(ends("①：墓地の相手モンスター１体を対象として発動できる。"
                              "そのモンスターを特殊召喚する。", "特殊召喚", "from"),
                         [[("墓地", "我方", "預設")]])

    def test_subset_takes_the_controller_of_its_container(self):
        """子集、剩餘自己沒寫控制方時往上找來源物件(建置寫不出這種卡文,直接給補方一步)。"""
        container = new_object("b0.o1", {"kind": "新建"},
                               condition={"op": "控制方", "value": "對手", "text": "相手の"})
        subset = new_object("b0.o2", {"kind": "子集", "of": "b0.o1"},
                            condition={"op": "大類", "value": "怪獸"})
        rest = new_object("b0.o3", {"kind": "剩餘", "of": "b0.o1", "minus": "b0.o2"})
        seg = new_segment("b0.s0", "效果", (0, 1), "")
        seg["lines"] = [new_line(obj["id"], "受事",
                                 from_=position([zone("墓地")], "繼承"))
                        for obj in (subset, rest)]
        block = new_block("b0", "效果", None, "card_text", (0, 1), "")
        block["segments"] = [seg]
        one = new_card(1, "補方テスト")
        one["objects"] += [container, subset, rest]
        one["blocks"] = [block]
        fill_rule_sides(one)
        self.assertEqual([line["from"]["zones"] for line in seg["lines"]],
                         [[zone("墓地", "對手", "規則")]] * 2)


class FieldAnySideTest(unittest.TestCase):
    """場上系區域沒寫方 → 任一方;其他區域沒寫方的不補。"""

    def test_sideless_field_is_either_side(self):
        self.assertEqual(ends("①：フィールドのカードを全て破壊する。", "破壞", "from"),
                         [[("場上", "任一方", "規則")]])

    def test_later_segment_inheriting_the_field_is_either_side(self):
        self.assertEqual(ends("①：フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "任一方", "規則")]])

    def test_written_field_side_is_kept(self):
        """寫明的方、繼承來的寫明的方都不動。"""
        self.assertEqual(ends("①：自分フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "我方", "明寫")]])
        self.assertEqual(ends("①：相手フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを持ち主の手札に戻す。", "返回", "to"),
                         [[("手牌", "持有者", "明寫")]])

    def test_hand_without_side_is_not_filled(self):
        self.assertEqual(ends("①：デッキからモンスター１体を手札に加える。", "加入手牌", "to"),
                         [[("手牌", None, None)]])


class SelfSideTest(unittest.TestCase):
    """方是自身 → 換成這一段的誰(解法同查詢判斷算誰的那一套);雙方各自、不限定 → 任一方。"""

    def test_opponent_self_is_opponent(self):
        self.assertEqual(ends("①：相手は自身の墓地からモンスター１体を選んで特殊召喚できる。",
                              "特殊召喚", "from"),
                         [[("墓地", "對手", "規則")]])

    def test_written_self_agent_is_own_side(self):
        self.assertEqual(ends("①：自分は自身の墓地から通常モンスター１体を特殊召喚できる。",
                              "特殊召喚", "from"),
                         [[("墓地", "我方", "規則")]])

    def test_active_segment_without_agent_counts_as_own_side(self):
        """「ターンプレイヤーは」抽不出誰:效果段的主動句沒寫誰算我方。"""
        self.assertEqual(ends("①：ターンプレイヤーは自身の手札を１枚選んで捨てる。", "捨棄", "from"),
                         [[("手牌", "我方", "規則")]])

    def test_anaphoric_agent_resolves_to_the_referred_segment(self):
        """「ドローしたプレイヤーは」回指抽牌那一段,那一段的誰是對手。"""
        self.assertEqual(ends("①：相手はデッキから１枚ドローする。"
                              "その後、ドローしたプレイヤーは自身の手札を１枚選んで捨てる。",
                              "捨棄", "from"),
                         [[("手牌", "對手", "規則")]])

    def test_each_player_is_either_side(self):
        self.assertEqual(ends("①：お互いは自身の手札を全てデッキに戻す。", "返回", "from"),
                         [[("手牌", "任一方", "規則")]])
        self.assertEqual(ends("①：お互いのプレイヤーはデッキから１枚ドローする。"
                              "その後、ドローしたプレイヤーは自身の手札を１枚選んで捨てる。",
                              "捨棄", "from"),
                         [[("手牌", "任一方", "規則")]])

    def test_unrestricted_agent_is_either_side(self):
        """被動句沒寫誰是不限定(建置寫不出這種卡文,直接給補方一步)。"""
        seg = new_segment("b0.s0", "效果", (0, 1), "", voice="被動")
        seg["lines"] = [new_line("o0", "受事", from_=position([zone("場上", "自身", "明寫")], "明寫"))]
        block = new_block("b0", "效果", None, "card_text", (0, 1), "")
        block["segments"] = [seg]
        one = new_card(1, "補方テスト")
        one["blocks"] = [block]
        fill_rule_sides(one)
        self.assertEqual(seg["lines"][0]["from"]["zones"], [zone("場上", "任一方", "規則")])

    def test_built_structure_has_no_self_side(self):
        for text in ("①：相手は自身の手札・デッキから罠カード１枚を選んで自身の魔法＆罠ゾーンに"
                     "セットできる。",
                     "①：お互いは自身の墓地の魔法・罠カードを１枚選んでフィールドにセットする。"):
            sides = {z["side"] for block in build(text)["blocks"]
                     for _, seg in iter_segments(block) for line in seg["lines"]
                     for end in ("from", "to") if line[end] for z in line[end]["zones"]}
            self.assertNotIn("自身", sides, text)


class ReverseCheckTest(unittest.TestCase):
    """規則補的方不寫回字面;有字面的條目驗證時只比區域。"""

    def test_cards_with_rule_sides_pass(self):
        for text in ("①：フィールドのカードを全て破壊する。",
                     "①：フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。",
                     "①：相手の表側表示モンスター１体を対象として発動できる。そのモンスターを破壊する。",
                     "①：このカード以外の自分の手札・フィールド（表側表示）の炎属性モンスター"
                     "１体を破壊する。",
                     "①：相手モンスター１体を対象として発動できる。"
                     "そのモンスターをフィールドに特殊召喚する。",
                     # 「自身の」照字面寫回,結構裡已換成段的誰
                     "①：相手は自身の墓地からモンスター１体を選んで特殊召喚できる。",
                     "①：お互いは自身の手札を全てデッキに戻す。",
                     "①：相手はデッキから１枚ドローする。"
                     "その後、ドローしたプレイヤーは自身の手札を１枚選んで捨てる。",
                     "①：相手は自身の手札・デッキから罠カード１枚を選んで自身の魔法＆罠ゾーンに"
                     "セットできる。"):
            self.assertEqual(check_card(build(text)), [], text)

    def test_lines_sharing_one_literal_may_get_different_rule_sides(self):
        """兩條線共用「フィールドの」(第二個物件的從照舊共用前面的字面),各自照物件的控制方補成
        任一方與我方;規則的方不寫回字面,字面仍是同一個。"""
        self.assertEqual(check_card(build(
            "①：フィールドの表側表示モンスター１体と自分の墓地の儀式モンスター１体を"
            "対象として発動できる。")), [])


if __name__ == "__main__":
    unittest.main()
