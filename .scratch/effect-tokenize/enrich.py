# -*- coding: utf-8 -*-
"""第四版論元的後處理 pass(frame-args-v4;票 01 建骨架,各票填步驟)。

frames.py 的 frames_of_tokens 在 anaphora.resolve 之後呼叫 enrich(ctx, tokens, frames):所有新欄
都是新鍵、讀既有欄的**最終**字面(主題延續、回填、推得、正規化、回指都已做完),所以放在框架抽取
的最後一步;既有鍵一個位元組都不改(baseline_diff.py 剝掉新鍵後與基準比,差異要 0)。

pass 內的順序照規格:片語結構化(phrases)→ 來源/目的/所在結構化與轉欄(regions)→ 施事者(agent)
→ 方式(manner)→ 否定形(negation)→ 回指回填(regions.backfill_from_anaphora)。前五步逐個動作框架
呼叫 step(ctx, tokens, frame);回填一次拿整句的框架清單(要找回指的目標框架)。只處理 kind == 動作
的框架。最後 pop 掉底線開頭的內部鍵(票 02 在切區域時暫存切前字面的 frame["_raw"] 這類),
它們不得進 frames.json。

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

報告的 registry(report.py 讀):
    FILL_RATE_ROWS   [(新欄名稱, 函式 frame → 狀態字串 | None)];狀態字串是 FILL_STATES 之一(None 是 空)。
                     各票只加自己的列,不改報告的程式。列名一律「中文名 鍵名」(片語·對象 phrases.object)。
    報告小節共用的表:report.count_by_position / report.position_table(值 × 位置 的 markdown 表)。
    REPORT_SECTIONS  [(標題, 函式 records → markdown 行清單)];留給「其他類的中心詞 top 100」(票 02)、
                     「其他類的修飾語 top 100」(票 03)、「回指回填 填/拒(依原因)」(票 09)。
"""
from collections import namedtuple

from constraints import KIND_ACTION

import agent
import manner
import negation
import phrases
import regions

Context = namedtuple("Context", "surface word is_noun_like move_actions coordinates is_predicate tokenize")

# 填充率的狀態欄(報告表的欄序);None 算 空
FILL_STATES = ("有值", "推得", "轉欄", "取自子句", "回填", "其他")
FILL_RATE_ROWS = [*phrases.FILL_RATE_ROWS]      # 票 02:片語·對象/主題/主語/目的;票 04:片語·數量
FILL_RATE_ROWS += list(regions.FILL_RATE_ROWS)   # 票 05:結構化來源/目的/所在、取自來源;票 09:回指回填
FILL_RATE_ROWS += [
    ("施事者 agent", agent.fill_state),                                # 票 07
    ("方式 manner", manner.fill_state),                                # 票 06
    ("否定形 negation", negation.fill_state),                          # 票 08
]
REPORT_SECTIONS = [*phrases.REPORT_SECTIONS]    # 票 02:其他類的中心詞 top 100;票 04:數量各類框數
REPORT_SECTIONS += [
    ("施事者各值 × 來源", agent.count_section),                          # 票 07
    ("方式各類框數", manner.count_section),                              # 票 06
    ("否定形各值框數", negation.count_section),                          # 票 08
    ("回指回填 填/拒(依原因)", regions.backfill_section),                # 票 09
]

_STEPS = (phrases.structure, regions.structure, agent.mark, manner.mark, negation.mark)


def enrich(ctx, tokens, frames):
    """就地替每個動作框架加第四版論元的新鍵;回傳同一個清單。"""
    actions = [fr for fr in frames if fr.get("kind") == KIND_ACTION]
    for step in _STEPS:
        for fr in actions:
            step(ctx, tokens, fr)
    regions.backfill_from_anaphora(ctx, tokens, actions)
    for fr in actions:
        for key in [k for k in fr if k.startswith("_")]:
            del fr[key]
    return frames
