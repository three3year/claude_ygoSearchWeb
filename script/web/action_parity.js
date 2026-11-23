/**
 * action_parity.js — 「兩邊答案一致」的前端那一邊(spec 測試決策;零 npm 依賴)
 *
 * Python 測試(`script/action_structure/test_web_parity.py`)把測試內建的卡片結構建成
 * 動作索引,連同前端索引的卡與一批動作條件從 stdin 餵進來:
 *   { "actionData": "window.ACTION_DATA=…;", "cards": [前端索引的卡], "conds": [動作條件] }
 * 這裡用接縫三的沙箱(載入 web/ 底下真實的前端檔)逐條查,stdout 回:
 *   [{ "rowQuery": 這條動作條件換成的列查詢, "ids": 前端引擎命中的卡號,
 *      "unsure": 無法確認的卡號 }]
 * Python 那邊把同一份列查詢交給 `run_query`,比命中的卡號與未解析組。
 */
'use strict';

const fs = require('node:fs');
const harness = require('./frontend_harness.js');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const sandbox = harness.load({ cards: input.cards, action: input.actionData });
const out = input.conds.map(cond => ({
  rowQuery: harness.rowQuery(sandbox, cond),
  ids: harness.ids(sandbox, {}, cond),
  unsure: harness.unsure(sandbox, {}, cond),
}));
process.stdout.write(JSON.stringify(out));
