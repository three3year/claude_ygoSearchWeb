# -*- coding: utf-8 -*-
"""來源/目的/所在的結構化(frame-args-v4 票 05 結構化值與取自來源、票 06 取自で 的所在、票 09 回指回填)。

structure(ctx, tokens, frame):frame["regions"] = {"source"|"goal"|"place": [[玩家, 區域七值], …]}(依字面
順序去重;只放算得出區域的欄;推得的欄玩家 無),非移動類所在空而來源有字面時所在取來源的並
frame["transfer"] = "取自來源";算法就是 places.parse_zones,不另寫(玩家拼法過 closed_values.PLACE_PLAYER:
雙方 → お互い)。字面欄一個位元組不動。
backfill_from_anaphora(ctx, tokens, actions):回指回填——把目標 place 字面的結構化值寫進本框架的
regions[來源|所在],frame["region_backfill"] 記欄名;字面欄不動。票 01 只建骨架:什麼都不做。
"""
import places
from closed_values import PLACE_PLAYER, REGION_KEYS, PLAYER_NONE_SPELLING

TRANSFER_FROM_SOURCE = "取自來源"


def zones_of(literal, inferred=False):
    """地點字面 → [[玩家, 區域七值], …](依字面順序去重),認不出或沒有字面時 []。推得的欄照字面算、
    玩家一律 無(推得值表只有區域,沒有玩家可言)。"""
    pairs = places.parse_zones(literal) or []
    return [[PLAYER_NONE_SPELLING if inferred else PLACE_PLAYER[player], zone] for player, zone in pairs]


def structure(ctx, tokens, frame):
    """票 05:三欄的結構化值與取自來源(票 06 再加取自で)。"""
    inferred = frame.get("inferred") or ()
    regions = {}
    for key in REGION_KEYS:
        pairs = zones_of(frame.get(key), inferred=key in inferred)
        if pairs:
            regions[key] = pairs
    # 非移動類(破壊、選ぶ、対象とする…)的 から 說的是受事者在哪裡:所在字面空、來源有字面(推得的不算;
    # 非移動類本來也沒有推得的來源)時,所在的結構化值取來源的、標 取自來源(2026-10-31 定案);
    # 來源認不出區域時沒有東西可轉,不標。移動類的來源是移動的起點,不轉;所在已有字面不轉。
    if (frame["action"] not in ctx.move_actions and not frame.get("place")
            and frame.get("source") and "source" not in inferred and "source" in regions):
        regions["place"] = list(regions["source"])
        frame["transfer"] = TRANSFER_FROM_SOURCE
    if regions:
        frame["regions"] = regions


def backfill_from_anaphora(ctx, tokens, actions):
    """票 09 填。actions 是同一句效果句的全部動作框架(含回指的目標)。"""


def fill_state(key):
    """填充率的列(report.py 經 enrich.FILL_RATE_ROWS 讀):結構化的來源/目的/所在 → 有值/推得/轉欄/None。"""
    def state_of(frame):
        if key not in (frame.get("regions") or {}):
            return None
        if key == "place" and frame.get("transfer"):
            return "轉欄"
        if key in (frame.get("inferred") or ()):
            return "推得"
        return "有值"
    return state_of


def transfer_state(frame):
    """填充率的列:取自來源 → 轉欄(票 06 的取自で 另一列)。"""
    return "轉欄" if frame.get("transfer") == TRANSFER_FROM_SOURCE else None


FILL_RATE_ROWS = [("結構化來源 regions.source", fill_state("source")),
                  ("結構化目的 regions.goal", fill_state("goal")),
                  ("結構化所在 regions.place", fill_state("place")),
                  ("轉欄 取自來源", transfer_state)]
