"""把現有查詢測試改走攤平成列的路徑跑一次(測試檔不改),看新路徑還差哪些
(spec「查詢判斷」:新路徑通過全部現有查詢測試後才刪舊的)。

    python -X utf8 script/action_structure/run_tests_on_rows.py [--parity] [unittest 的其他參數]

- 預設:`run_query` 的預設路徑換成 `rows`,再 discover 本目錄的測試。
- `--parity`:每次查詢兩條路徑各跑一次,直接命中(特定、泛用組與各卡的命中段)不同就拋 AssertionError;
  回傳舊路徑的結果,所以只有直接命中不同的查詢會失敗。
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import action_query  # noqa: E402

_run_query = action_query.run_query


def _rows(structures, cards, query, path=None):
    return _run_query(structures, cards, query, path=path or action_query.PATH_ROWS)


def direct_hits(result):
    """結果裡的直接命中:卡號 → (組, 命中段)。經引用組不算。"""
    return {hit["id"]: (hit["group"], hit["segments"]) for hit in result["hits"]
            if hit["group"] != action_query.VIA_GROUP}


def _parity(structures, cards, query, path=None):
    if path is not None:   # 測試自己指定了路徑(新路徑的測試):照它跑
        return _run_query(structures, cards, query, path=path)
    old = _run_query(structures, cards, query)
    new = _run_query(structures, cards, query, path=action_query.PATH_ROWS)
    if direct_hits(old) != direct_hits(new):
        raise AssertionError(f"直接命中不同:查詢 {query}\n舊 {direct_hits(old)}\n新 {direct_hits(new)}")
    return old


if __name__ == "__main__":
    args = sys.argv[1:]
    parity = "--parity" in args
    if parity:
        args.remove("--parity")
    action_query.run_query = _parity if parity else _rows
    unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", HERE, *args])
