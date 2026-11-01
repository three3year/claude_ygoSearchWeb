# -*- coding: utf-8 -*-
"""重跑分詞鏈(.scratch/category-search 票 05,ADR-0017;named-queries 票 05 加框列匯出、票 08 加目錄):
分詞 → 框架 → 目錄 → 框列匯出 → 類別 → 類別匯出。

[[差值更新]]在效果標記表更新之後、重建網站資料(script/web/build_index.py)之前跑這一支:
新卡與勘誤改了標記句的日文原文時,匯出檔的雜湊會對不上,索引建置因此失敗——重跑全鏈讓
匯出跟上卡文。任一步失敗就停下並說是哪一步,後面的步驟不跑(半新半舊的中間產物不往下傳)。

目錄(catalog_hits.py:載入檢查具名查詢目錄、每個動作框架的命中寫 frame_queries.json、「至少命中一張」檢查)與
框列匯出(export_frames.py → data/action_frames.json,目錄欄的張數與雜湊;ADR-0018)緊接框架之後、在舊的
類別 → 類別匯出 之前(規格 2 總則的順序 框架 → 目錄 → 匯出);舊的兩步過渡期照跑、規格 4 介面切換後刪。

用法(repo 任意位置皆可):python .scratch/effect-tokenize/run_chain.py
"""
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

STEPS = (
    ("分詞", "tokenize.py"),
    ("框架", "frames.py"),
    ("目錄", "catalog_hits.py"),
    ("框列匯出", "export_frames.py"),
    ("類別", "categories.py"),
    ("類別匯出", "export_categories.py"),
)


def run(runner):
    """依序跑每一步;runner(腳本檔名) 回 exit code。→ (成功與否, 失敗的步驟名或 None)。"""
    for name, script in STEPS:
        if runner(script) != 0:
            return False, name
    return True, None


def _subprocess_runner(script):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    start = time.time()
    print("── %s ──" % script, flush=True)
    code = subprocess.call([sys.executable, os.path.join(HERE, script)], cwd=ROOT, env=env)
    print("(%s 結束,exit %d,%.0f 秒)" % (script, code, time.time() - start), flush=True)
    return code


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ok, failed = run(_subprocess_runner)
    if not ok:
        print("**分詞鏈在「%s」這一步失敗**,後面的步驟沒有跑;data/action_frames.json 與 "
              "data/action_categories.json 可能未更新。" % failed, file=sys.stderr)
        return 1
    print("分詞鏈重跑完成,接著重建網站資料:python script/web/build_index.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
