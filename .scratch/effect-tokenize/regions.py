# -*- coding: utf-8 -*-
"""來源/目的/所在的結構化(frame-args-v4 票 05 結構化值與取自來源、票 06 取自で 的所在、票 09 回指回填)。

mark(ctx, tokens, frame):frame["regions"] = {"source"|"goal"|"place": [[玩家, 區域七值], …]}(依字面
順序去重;只放算得出區域的欄;推得的欄玩家 無),非移動類所在空而來源有字面時所在取來源的並
frame["transfer"] = "取自來源";算法就是 places.parse_zones,不另寫(玩家拼法過 closed_values.PLACE_PLAYER:
雙方 → お互い)。字面欄一個位元組不動。
place_from_de(frame, literal):票 06——で 接的區域進 regions["place"]、frame["transfer"] = "取自で"(字面所在、
取自來源 優先;manner.py 找到區域 で 片語時呼叫)。
backfill_from_anaphora(ctx, tokens, actions):回指回填(票 09)——受事者是指示詞的框架(回指欄只在那時
才帶)、回指欄有 place、找法不是事件、本框缺該欄字面(移動類看來源、非移動類看所在;推得的不算有、
取自來源轉欄來的算有)、目標非移動類時,把目標 place 字面經 parse_zones 寫進 regions[來源|所在],
frame["region_backfill"] 記欄名,蓋過推得的同欄結構化值;字面欄不動;跨句號(回指本來就跨)。回指欄
先補 moving:目標框架(anaphora.resolve 記在內部鍵 _anaphora_targets 的框架,含解到底的鏈上每一框)
任一是移動類就 true——鏈上有移動類表示卡已經不在目標的區域(対象として…特殊召喚し…その後そのモンスター
を破壊 的 破壊);目標是字面備援(沒有框架)時 false。拒絕的框依原因計數進報告(backfill_section)。
"""
from collections import Counter

import places
from anaphora import VIA_EVENT
from closed_values import (PLACE_PLAYER, PLAYER_NONE_SPELLING, REGION_KEYS, REGION_PLACE, REGION_SOURCE,
                           TRANSFER_FROM_DE, TRANSFER_FROM_SOURCE)
from report import position_table


def zones_of(literal, inferred=False):
    """地點字面 → [[玩家, 區域七值], …](依字面順序去重),認不出或沒有字面時 []。推得的欄照字面算、
    玩家一律 無(推得值表只有區域,沒有玩家可言)。"""
    pairs = places.parse_zones(literal) or []
    return [[PLAYER_NONE_SPELLING if inferred else PLACE_PLAYER[player], zone] for player, zone in pairs]


def mark(ctx, tokens, frame):
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
    if (frame["action"] not in ctx.move_actions and not frame.get(REGION_PLACE)
            and frame.get(REGION_SOURCE) and REGION_SOURCE not in inferred and REGION_SOURCE in regions):
        regions[REGION_PLACE] = list(regions[REGION_SOURCE])
        frame["transfer"] = TRANSFER_FROM_SOURCE
    if regions:
        frame["regions"] = regions


# 回指回填的結果(report 的小節依此計數;從框架內容算得,不用知道移動類清單)
BACKFILL_FILLED = "填"
BACKFILL_REJECT_MOVING = "拒:目標移動類"
BACKFILL_REJECT_OWN = "拒:本框已有字面"
BACKFILL_REJECT_NO_ZONE = "拒:目標區域認不出"
BACKFILL_STATUSES = (BACKFILL_FILLED, BACKFILL_REJECT_MOVING, BACKFILL_REJECT_OWN, BACKFILL_REJECT_NO_ZONE)


def _target_moving(ctx, frame):
    """目標框架(回指鏈上經過的每一框)任一是移動類 → True;字面備援沒有框架 → False。"""
    return any(f["action"] in ctx.move_actions for f in frame.get("_anaphora_targets") or ())


def _backfill_column(ctx, frame):
    return REGION_SOURCE if frame["action"] in ctx.move_actions else REGION_PLACE


def _has_own_literal(frame, column):
    """本框該欄有自己的字面:推得的不算;非移動類所在轉欄(取自來源/取自で)來的算——那是本框自己的
    から/で 字面。回填來的字面(選んで破壊する)也是字面。"""
    if column == REGION_PLACE:
        return bool(frame.get(REGION_PLACE)) or bool(frame.get("transfer"))
    return bool(frame.get(REGION_SOURCE)) and REGION_SOURCE not in (frame.get("inferred") or ())


def _is_candidate(anaphora):
    return bool(anaphora and anaphora.get("place") and anaphora.get("via") != VIA_EVENT)


def place_from_de(frame, literal):
    """票 06:で 接的區域(Pゾーンで破壊された、フィールドで発動した)不是方式,結構化所在取它、標 取自で
    (2026-10-31 定案;不分移動類)。優先序:字面所在已有值不動(字面優先)、已 取自來源 不蓋、只在
    結構化所在空時寫;認不出區域時沒有東西可寫。字面所在欄維持空。回指回填(票 09)把轉欄的所在當本框
    自己的字面,不會再蓋。"""
    if frame.get(REGION_PLACE) or frame.get("transfer") or REGION_PLACE in (frame.get("regions") or {}):
        return
    pairs = zones_of(literal)
    if not pairs:
        return
    frame.setdefault("regions", {})[REGION_PLACE] = pairs
    frame["transfer"] = TRANSFER_FROM_DE


def backfill_from_anaphora(ctx, tokens, actions):
    """票 09:actions 是同一句效果句的全部動作框架。先替每個回指欄補 moving,再對候選框回填。"""
    for frame in actions:
        anaphora = frame.get("anaphora")
        if not anaphora:
            continue
        anaphora["moving"] = _target_moving(ctx, frame)
        if not _is_candidate(anaphora) or anaphora["moving"]:
            continue
        column = _backfill_column(ctx, frame)
        if _has_own_literal(frame, column):
            continue
        pairs = zones_of(anaphora["place"])
        if not pairs:
            continue
        regions = frame.setdefault("regions", {})
        regions[column] = pairs
        frame["region_backfill"] = column


def backfill_status(frame):
    """一個動作框架的回指回填結果:BACKFILL_STATUSES 之一,不是候選(沒有回指、回指沒有區域、事件類)
    時 None。從框架內容算得(report.py 讀 frames.json 時用)。"""
    anaphora = frame.get("anaphora")
    if not _is_candidate(anaphora):
        return None
    if frame.get("region_backfill"):
        return BACKFILL_FILLED
    if anaphora.get("moving"):
        return BACKFILL_REJECT_MOVING
    if not zones_of(anaphora["place"]):
        return BACKFILL_REJECT_NO_ZONE
    return BACKFILL_REJECT_OWN


def fill_state(key):
    """填充率的列(report.py 經 enrich.FILL_RATE_ROWS 讀):結構化的來源/目的/所在 → 回填(回指回填寫進的欄)/
    轉欄(所在取自來源/取自で)/推得(字面欄是推得的)/有值/None(沒有結構化值)。"""
    def state_of(frame):
        if key not in (frame.get("regions") or {}):
            return None
        if frame.get("region_backfill") == key:
            return "回填"
        if key == REGION_PLACE and frame.get("transfer"):
            return "轉欄"
        if key in (frame.get("inferred") or ()):
            return "推得"
        return "有值"
    return state_of


def backfill_state(frame):
    """填充率的列:回指回填寫進了哪一欄 → 回填。"""
    return "回填" if frame.get("region_backfill") else None


def backfill_section(records):
    """報告小節「回指回填 填/拒(依原因)」:候選(回指欄有區域、找法不是事件)的動作框架依結果 × 位置
    計數;填的再分寫進來源(移動類本框)/所在(非移動類本框)。"""
    counts = Counter()
    columns = Counter()
    for rec in records:
        for fr in rec["frames"]:
            status = backfill_status(fr)
            if status:
                counts[(status, fr["position"])] += 1
                if status == BACKFILL_FILLED:
                    columns[fr["region_backfill"]] += 1
    total = sum(counts.values())
    lines = ["候選是回指欄有區域(目標的所在/來源字面)且找法不是事件的動作框架,共 {:,} 框。填=目標區域的結構化值"
             "寫進本框的 regions 來源(移動類本框 {:,} 框)/所在(非移動類本框 {:,} 框),region_backfill 記欄名,"
             "字面欄不動;拒:目標移動類=目標框架(含解到底鏈上的框)是移動類,卡已不在那個區域;拒:本框已有字面="
             "本框該欄自己有字面(推得的不算、取自來源轉欄的算);拒:目標區域認不出=目標的區域字面過不了區域辨識。"
             .format(total, columns[REGION_SOURCE], columns[REGION_PLACE]), ""]
    return lines + position_table(counts, BACKFILL_STATUSES, "結果")


def transfer_state(which):
    """填充率的列:轉欄記號是 which(取自來源/取自で)→ 轉欄。"""
    return lambda frame: "轉欄" if frame.get("transfer") == which else None


# 鍵 → 中文(報告列名與批次檔格名共用)
REGION_LABELS = tuple(zip(REGION_KEYS, ("來源", "目的", "所在")))

FILL_RATE_ROWS = [("結構化%s regions.%s" % (label, key), fill_state(key)) for key, label in REGION_LABELS]
FILL_RATE_ROWS += [("轉欄 取自來源 transfer", transfer_state(TRANSFER_FROM_SOURCE)),
                  ("轉欄 取自で transfer", transfer_state(TRANSFER_FROM_DE)),
                  ("回指回填 region_backfill", backfill_state)]


def batch_cells(frame):
    """批次檔的格(llm_check.py 經 enrich.batch_cells 讀;票 05):結構化來源/目的/所在=(玩家,區域)・…;轉欄來的
    所在尾綴 (取自來源)/(取自で);回指回填寫進的欄(票 09)尾綴 (回指)。"""
    structured = frame.get("regions") or {}
    cells = []
    for key, label in REGION_LABELS:
        if key in structured:
            tag = ("(回指)" if frame.get("region_backfill") == key
                   else "(%s)" % frame["transfer"] if key == REGION_PLACE and frame.get("transfer") else "")
            cells.append("結構化%s=%s%s" % (label, "・".join("(%s,%s)" % tuple(p) for p in structured[key]), tag))
    return cells
