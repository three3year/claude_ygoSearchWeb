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
    def test_from_takes_the_controller_written_on_the_object(self):
        self.assertEqual(ends("①：相手の表側表示モンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "對手", "規則")]])

    def test_controller_fills_every_sideless_zone_of_the_from(self):
        self.assertEqual(ends("①：このカード以外の自分の手札・フィールド（表側表示）の炎属性モンスター"
                              "１体を破壊する。", "破壞", "from"),
                         [[("手牌", "我方", "規則"), ("場上", "我方", "規則")]])

    def test_either_side_controller(self):
        self.assertEqual(ends("①：自分または相手の表側表示モンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "任一方", "規則")]])

    def test_to_does_not_take_the_controller(self):
        self.assertEqual(ends("①：相手モンスター１体を対象として発動できる。"
                              "そのモンスターをフィールドに特殊召喚する。", "特殊召喚", "to"),
                         [[("場上", "任一方", "規則")]])

    def test_written_or_default_side_is_kept(self):
        self.assertEqual(ends("①：墓地の相手モンスター１体を対象として発動できる。"
                              "そのモンスターを特殊召喚する。", "特殊召喚", "from"),
                         [[("墓地", "我方", "預設")]])

    def test_subset_takes_the_controller_of_its_container(self):
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
    def test_sideless_field_is_either_side(self):
        self.assertEqual(ends("①：フィールドのカードを全て破壊する。", "破壞", "from"),
                         [[("場上", "任一方", "規則")]])

    def test_later_segment_inheriting_the_field_is_either_side(self):
        self.assertEqual(ends("①：フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "任一方", "規則")]])

    def test_written_field_side_is_kept(self):
        self.assertEqual(ends("①：自分フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを破壊する。", "破壞", "from"),
                         [[("場上", "我方", "明寫")]])
        self.assertEqual(ends("①：相手フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを持ち主の手札に戻す。", "返回", "to"),
                         [[("手牌", "持有者", "明寫")]])

    def test_hand_without_side_is_not_filled(self):
        self.assertEqual(ends("①：デッキからモンスター１体を手札に加える。", "加入手牌", "to"),
                         [[("手牌", None, None)]])


class GraveyardBanishedOwnerTest(unittest.TestCase):
    def test_this_card_sent_to_graveyard_is_own(self):
        self.assertEqual(ends("①：このカードを墓地へ送る。", "送墓", "to"),
                         [[("墓地", "我方", "規則")]])

    def test_this_card_banished_is_own(self):
        self.assertEqual(ends("①：このカードを除外する。", "除外", "to"),
                         [[("除外", "我方", "規則")]])

    def test_other_object_sent_to_graveyard_is_owner(self):
        self.assertEqual(ends("①：相手フィールドのモンスター１体を対象として発動できる。"
                              "そのモンスターを墓地へ送る。", "送墓", "to"),
                         [[("墓地", "持有者", "規則")]])

    def test_other_object_banished_is_owner(self):
        self.assertEqual(ends("①：フィールドのカード１枚を対象として発動できる。"
                              "そのカードを除外する。", "除外", "to"),
                         [[("除外", "持有者", "規則")]])

    def test_this_card_leaving_the_graveyard_it_was_sent_to_is_own(self):
        self.assertEqual(ends("①：このカードが戦闘で破壊され墓地へ送られた場合に発動できる。"
                              "このカードを特殊召喚する。", "特殊召喚", "from"),
                         [[("墓地", "我方", "規則")]])

    def test_other_object_leaving_the_graveyard_is_owner(self):
        self.assertEqual(ends("①：モンスターが戦闘で破壊され墓地へ送られた時に発動できる。"
                              "そのモンスターを特殊召喚する。", "特殊召喚", "from"),
                         [[("墓地", "持有者", "規則")]])

    def test_other_object_leaving_banishment_is_owner(self):
        self.assertEqual(ends("①：除外されているモンスター１体を対象として発動できる。"
                              "そのモンスターを特殊召喚する。", "特殊召喚", "from"),
                         [[("除外", "持有者", "規則")]])

    def test_graveyard_from_default_side_is_kept(self):
        self.assertEqual(ends("①：墓地からモンスター１体を特殊召喚する。", "特殊召喚", "from"),
                         [[("墓地", "我方", "預設")]])

    def test_controller_written_on_the_object_comes_first(self):
        self.assertEqual(ends("①：除外されている相手モンスター１体を対象として発動できる。"
                              "そのモンスターを特殊召喚する。", "特殊召喚", "from"),
                         [[("除外", "對手", "規則")]])


class SelfSideTest(unittest.TestCase):
    def test_opponent_self_is_opponent(self):
        self.assertEqual(ends("①：相手は自身の墓地からモンスター１体を選んで特殊召喚できる。",
                              "特殊召喚", "from"),
                         [[("墓地", "對手", "規則")]])

    def test_written_self_agent_is_own_side(self):
        self.assertEqual(ends("①：自分は自身の墓地から通常モンスター１体を特殊召喚できる。",
                              "特殊召喚", "from"),
                         [[("墓地", "我方", "規則")]])

    def test_active_segment_without_agent_counts_as_own_side(self):
        self.assertEqual(ends("①：ターンプレイヤーは自身の手札を１枚選んで捨てる。", "捨棄", "from"),
                         [[("手牌", "我方", "規則")]])

    def test_anaphoric_agent_resolves_to_the_referred_segment(self):
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
    def test_cards_with_rule_sides_pass(self):
        for text in ("①：フィールドのカードを全て破壊する。",
                     "①：フィールドのモンスター１体を対象として発動できる。そのモンスターを破壊する。",
                     "①：相手の表側表示モンスター１体を対象として発動できる。そのモンスターを破壊する。",
                     "①：このカード以外の自分の手札・フィールド（表側表示）の炎属性モンスター"
                     "１体を破壊する。",
                     "①：相手モンスター１体を対象として発動できる。"
                     "そのモンスターをフィールドに特殊召喚する。",
                     "①：このカードを墓地へ送る。",
                     "①：相手フィールドのモンスター１体を対象として発動できる。"
                     "そのモンスターを除外する。",
                     "①：このカードが戦闘で破壊され墓地へ送られた場合に発動できる。"
                     "このカードを特殊召喚する。",
                     "①：除外されているモンスター１体を対象として発動できる。"
                     "そのモンスターを特殊召喚する。",
                     "①：相手は自身の墓地からモンスター１体を選んで特殊召喚できる。",
                     "①：お互いは自身の手札を全てデッキに戻す。",
                     "①：相手はデッキから１枚ドローする。"
                     "その後、ドローしたプレイヤーは自身の手札を１枚選んで捨てる。",
                     "①：相手は自身の手札・デッキから罠カード１枚を選んで自身の魔法＆罠ゾーンに"
                     "セットできる。"):
            self.assertEqual(check_card(build(text)), [], text)

    def test_lines_sharing_one_literal_may_get_different_rule_sides(self):
        self.assertEqual(check_card(build(
            "①：フィールドの表側表示モンスター１体と自分の墓地の儀式モンスター１体を"
            "対象として発動できる。")), [])


if __name__ == "__main__":
    unittest.main()
