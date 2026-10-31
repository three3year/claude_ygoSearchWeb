# -*- coding: utf-8 -*-
"""第四版論元的後處理 pass(frame-args-v4;票 01 建骨架,各票填步驟;named-queries 票 02 拆成回指前後兩段)。

frames.py 的 frames_of_tokens 把這個 pass 夾在回指兩側:

    既有步驟(主題延續、回填、列舉、推得、正規化、排序)
    → before_anaphora(ctx, tokens, frames)   回指前的步驟:片語結構化(phrases)
    → anaphora.resolve                        回指(named-queries 票 03 起改讀片語段)
    → after_anaphora(ctx, tokens, frames)    回指後的步驟:結構化區域與轉欄(regions)→ 施事者(agent)
                                              → 方式(manner)→ 否定形(negation)→ 回指回填
                                              (regions.backfill_from_anaphora)→ pop 底線鍵

所有新欄都是新鍵、讀既有欄的**最終**字面(主題延續、回填、推得、正規化都已做完);既有鍵一個位元組都
不改(baseline_diff.py 剝掉新鍵後與基準比,差異要 0)。片語只讀既有欄與切區域前的字面、不讀回指,所以搬到
回指前片語欄逐位元組不變;後段的步驟讀回指欄(regions 的回填、agent 的事件主語)或片語段,留在回指後。

STEPS 這張表就是 pass 順序,逐個動作框架呼叫各模組的 mark(ctx, tokens, frame);哪些步驟在回指前由模組自己
宣告(BEFORE_ANAPHORA = True;沒宣告的在回指後),宣告在回指前的要排在 STEPS 前段(test_lint 守),所以
STEPS 的順序仍是執行順序。回填一次拿整句的框架清單(要找回指的目標框架),是 pass 明寫的最後一步。只處理
kind == 動作的框架。底線開頭的內部鍵(frames.py 切區域時暫存切前字面的 frame["_raw"]、anaphora 記目標框架的
frame["_anaphora_targets"])要留到回指與後段都讀完,只在 after_anaphora 結尾 pop,它們不得進 frames.json。

步驟模組自己宣告、收集端只有 STEPS 一張表(retro 第 9 項:多張票平行時合併只碰那一行;新模組在
STEPS 加一行,其餘都是它自己檔裡的宣告,沒宣告的當空):
    mark(ctx, tokens, frame)   就地替動作框架加自己的新鍵
    BEFORE_ANAPHORA            True 時在回指前跑(只讀既有欄與底線鍵、不讀回指;回指可以讀它);沒宣告的在回指後
    FILL_RATE_ROWS             [(新欄名稱, 函式 frame → 狀態字串 | None)];狀態是 FILL_STATES 之一(None 是 空);
                               列名一律「中文名 鍵名」(片語·對象 phrases.object)
    REPORT_SECTIONS            [(標題, 函式 records → markdown 行清單)];小節共用的表 report.count_by_position /
                               report.position_table
    batch_cells(frame)         批次檔的格 ["片語·對象=…", …];推得/轉欄/取自子句標 (推得)/(取自來源)/(取自子句)
                               讓子代理分得開
這裡依 STEPS 的順序收成 FILL_RATE_ROWS / REPORT_SECTIONS(report.py 讀)與 batch_cells(llm_check.py 讀);
拆解頁的格是 viewer.html 的 V4_RENDERERS 清單(每個模組一個 JS 小函式),同一個順序。回指回填的小節是
pass 最後一步的,排在各模組小節之後。

循環 import:frames.py import 這裡,這裡與各步驟模組**不**import frames;要用的常數與分詞輔助由
frames.py 裝進 Context 傳進來(constraints/action_lemmas/places 可直接 import)。

Context 欄位:
    surface(token) / word(token) / is_noun_like(token)  FrameExtractor 的分詞輔助(字面、詞、是否名詞格)
    move_actions                                       移動類動作(frames.MOVE_ACTIONS;regions 的轉欄/回填判準)
    coordinates(chunk, k)                              FrameExtractor 的並列分隔判準(と同じ 的 と 不算;票 02 切段用)
    is_predicate(token)                                定語述語判準(FrameExtractor._is_predicate:動詞/形容詞/
                                                       する家族/補助/否定/活用尾;票 02 切段、讀區域用,票 06 用來
                                                       認定語子句裡的 で)
    tokenize(text)                                     分詞器(票 02:字面對不回句子的詞序列時的備援)
"""
from collections import namedtuple

from constraints import KIND_ACTION

import agent
import manner
import negation
import phrases
import regions

Context = namedtuple("Context", "surface word is_noun_like move_actions coordinates is_predicate tokenize")

# pass 順序就是這張表;新的步驟模組在這裡加一行,其餘(mark / BEFORE_ANAPHORA / FILL_RATE_ROWS / REPORT_SECTIONS /
# batch_cells)它自己宣告。宣告 BEFORE_ANAPHORA 的(phrases)排前段、在回指前跑;其餘在回指後跑
STEPS = (phrases, regions, agent, manner, negation)

# 填充率的狀態欄(報告表的欄序);None 算 空
FILL_STATES = ("有值", "推得", "轉欄", "取自子句", "回填", "其他")


def declared(name):
    """依 STEPS 的順序串起各模組宣告的清單;沒宣告的模組當空。"""
    return [item for module in STEPS for item in getattr(module, name, ())]


FILL_RATE_ROWS = declared("FILL_RATE_ROWS")
# 回指回填是 pass 明寫的最後一步(整句一次、不逐框),它的小節也排在各模組的小節之後
REPORT_SECTIONS = declared("REPORT_SECTIONS") + [("回指回填 填/拒(依原因)", regions.backfill_section)]


def batch_cells(frame):
    """批次檔的第四版論元格:依 STEPS 的順序接各模組的 batch_cells。"""
    return [cell for module in STEPS for cell in module.batch_cells(frame)]


def _runs_before_anaphora(module):
    """模組自己宣告的 BEFORE_ANAPHORA;沒宣告的在回指後。"""
    return bool(getattr(module, "BEFORE_ANAPHORA", False))


def _actions(frames):
    return [fr for fr in frames if fr.get("kind") == KIND_ACTION]


def _run(modules, ctx, tokens, actions):
    for module in modules:
        for fr in actions:
            module.mark(ctx, tokens, fr)


def before_anaphora(ctx, tokens, frames):
    """回指前的步驟(片語結構化):就地替每個動作框架加新鍵;底線鍵留著給回指與後段讀。回傳同一個清單。"""
    _run([m for m in STEPS if _runs_before_anaphora(m)], ctx, tokens, _actions(frames))
    return frames


def after_anaphora(ctx, tokens, frames):
    """回指後的步驟(結構化區域、施事者、方式、否定形)與回指回填,最後 pop 底線鍵。回傳同一個清單。"""
    actions = _actions(frames)
    _run([m for m in STEPS if not _runs_before_anaphora(m)], ctx, tokens, actions)
    regions.backfill_from_anaphora(ctx, tokens, actions)
    for fr in actions:
        for key in [k for k in fr if k.startswith("_")]:
            del fr[key]
    return frames
