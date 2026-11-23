"""現有查詢測試的新舊比對(測試檔不改):每次查詢兩條路徑各跑一次,看新路徑與舊的讀法是否逐項相同
(spec「查詢判斷」:新路徑通過全部現有查詢測試、結果與舊的相同後才刪舊的)。

    python -X utf8 script/action_structure/run_tests_on_rows.py [--parity] [unittest 的其他參數]

- 預設:`run_query` 已預設走攤平成列的路徑,等同直接 discover 本目錄的測試。
- `--parity`:每次查詢讀卡片結構(舊)與攤平成列(新)各跑一次,整份結果(命中、各組、未解析組明細、
  `via`、`mark`、`replaced_by`)不同就拋 AssertionError;回傳新路徑的結果。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import action_query  # noqa: E402

_run_query = action_query.run_query


def _parity(structures, cards, query, path=None):
    if path is not None:   # 測試自己指定了路徑:照它跑
        return _run_query(structures, cards, query, path=path)
    old = _run_query(structures, cards, query, path=action_query.PATH_STRUCTURE)
    new = _run_query(structures, cards, query, path=action_query.PATH_ROWS)
    if old != new:
        raise AssertionError(f"新舊結果不同:查詢 {query}\n舊 {old}\n新 {new}")
    return new


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--parity" in args:
        args.remove("--parity")
        action_query.run_query = _parity
    unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", HERE, *args])
