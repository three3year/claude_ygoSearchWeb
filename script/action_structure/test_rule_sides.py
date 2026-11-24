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


class GraveyardBanishedOwnerTest(unittest.TestCase):
    """墓地、除外沒寫方(從與到):物件是此卡記我方,其他物件記持有者(卡一定進持有者的墓地、除外)。"""

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
        """「このカードが戦闘で破壊され墓地へ送られた場合、このカードを特殊召喚する」:
        特殊召喚的從繼承前提的墓地、沒寫方,物件是此卡 → 我方。"""
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
        """「墓地から」沒寫方是預設我方,已經有方,不套這條。"""
        self.assertEqual(ends("①：墓地からモンスター１体を特殊召喚する。", "特殊召喚", "from"),
                         [[("墓地", "我方", "預設")]])

    def test_controller_written_on_the_object_comes_first(self):
        """物件寫了控制方的從照物件(票 02),不套持有者。"""
        self.assertEqual(ends("①：除外されている相手モンスター１体を対象として発動できる。"
                              "そのモンスターを特殊召喚する。", "特殊召喚", "from"),
                         [[("除外", "對手", "規則")]])


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
                     "①：このカードを墓地へ送る。",
                     "①：相手フィールドのモンスター１体を対象として発動できる。"
                     "そのモンスターを除外する。",
                     "①：このカードが戦闘で破壊され墓地へ送られた場合に発動できる。"
                     "このカードを特殊召喚する。",
                     "①：除外されているモンスター１体を対象として発動できる。"
                     "そのモンスターを特殊召喚する。"):
            self.assertEqual(check_card(build(text)), [], text)

    def test_lines_sharing_one_literal_may_get_different_rule_sides(self):
        """兩條線共用「フィールドの」(第二個物件的從照舊共用前面的字面),各自照物件的控制方補成
        任一方與我方;規則的方不寫回字面,字面仍是同一個。"""
        self.assertEqual(check_card(build(
            "①：フィールドの表側表示モンスター１体と自分の墓地の儀式モンスター１体を"
            "対象として発動できる。")), [])


if __name__ == "__main__":
    unittest.main()
