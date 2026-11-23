/**
 * stdin:
 *   { "actionData": "window.ACTION_DATA=…;", "cards": [前端索引的卡], "vocab": 值域正典,
 *     "conds": [動作條件] }
 * stdout:
 *   [{ "rowQuery": 這條動作條件換成的列查詢, "ids": 前端引擎命中的卡號,
 *      "unsure": 無法確認的卡號 }]
 */
'use strict';

const fs = require('node:fs');
const harness = require('./frontend_harness.js');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const sandbox = harness.load({ cards: input.cards, vocab: input.vocab || {},
                                action: input.actionData });
const out = input.conds.map(cond => ({
  rowQuery: harness.rowQuery(sandbox, cond),
  ids: harness.ids(sandbox, {}, cond),
  unsure: harness.unsure(sandbox, {}, cond),
}));
process.stdout.write(JSON.stringify(out));
