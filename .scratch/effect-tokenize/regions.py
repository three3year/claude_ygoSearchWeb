# -*- coding: utf-8 -*-
"""來源/目的/所在的結構化(frame-args-v4 票 05 結構化值與取自來源、票 06 取自で 的所在、票 09 回指回填)。

structure(ctx, tokens, frame):frame["regions"] = {"source"|"goal"|"place": [[玩家, 區域七值], …]}(依字面
順序去重;只放算得出區域的欄;推得的欄玩家 無),非移動類所在空而來源有字面時所在取來源的並
frame["transfer"] = "取自來源";算法就是 places.parse_zones + parse_place,不另寫。
backfill_from_anaphora(ctx, tokens, actions):回指回填——把目標 place 字面的結構化值寫進本框架的
regions[來源|所在],frame["region_backfill"] 記欄名;字面欄不動。票 01 只建骨架:什麼都不做。
"""


def structure(ctx, tokens, frame):
    """票 05/06 填。"""


def backfill_from_anaphora(ctx, tokens, actions):
    """票 09 填。actions 是同一句效果句的全部動作框架(含回指的目標)。"""
