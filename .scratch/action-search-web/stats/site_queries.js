/**
 * 票 17 收尾:網站那一邊的常用查詢(零 npm 依賴)。
 * 用接縫三的沙箱(`script/web/frontend_harness.js`,載入 web/ 底下真實的前端檔)
 * 載入真實的 `web/data.js` 與 `web/action-data.js`,逐條跑 stdin 給的動作條件。
 *   stdin:{ "root": repo 根, "conds": [{ "name", "act" }] }
 *   stdout:[{ "name", "rowQuery", "ids", "unsure", "ms" }]
 * 由同目錄 `common_queries.py` 呼叫,不單獨跑。
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const harness = require(path.join(input.root, 'script', 'web', 'frontend_harness.js'));

const dataCtx = {};
dataCtx.window = dataCtx;
vm.createContext(dataCtx);
vm.runInContext(fs.readFileSync(path.join(input.root, 'web', 'data.js'), 'utf8'), dataCtx);

const sandbox = harness.load({
  cards: dataCtx.CARD_DATA, vocab: dataCtx.VOCAB, meta: dataCtx.META,
  action: fs.readFileSync(path.join(input.root, 'web', 'action-data.js'), 'utf8'),
});

const out = input.conds.map(({ name, act }) => {
  const t0 = process.hrtime.bigint();
  const ids = harness.ids(sandbox, {}, act);
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  return { name, rowQuery: harness.rowQuery(sandbox, act), ids,
           unsure: harness.unsure(sandbox, {}, act), ms };
});
process.stdout.write(JSON.stringify(out));
