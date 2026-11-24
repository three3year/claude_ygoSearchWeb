/**
 * 票 07 收尾:主搜尋「卡名」框(中文)打半形 % 與全形 ％ 的張數,對照動作搜尋卡名包含的全形 ％(收尾摘要第一題)。
 * 跑法(repo 根):node .scratch/action-search-coverage/stats/main_name.js
 * 用接縫三的沙箱(script/web/frontend_harness.js)載入真實的 web/data.js;不帶動作條件。輸出決定性。
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..', '..', '..');
const harness = require(path.join(ROOT, 'script', 'web', 'frontend_harness.js'));
const ctx = {};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'web', 'data.js'), 'utf8'), ctx);
const sb = harness.load({ cards: ctx.CARD_DATA, vocab: ctx.VOCAB, meta: ctx.META });

for (const name of ['黑魔導', '黑%導', '黑％導']) {
  console.log(`卡名框(中文)「${name}」:${harness.ids(sb, { name, nameLang: 'zh' }, null).length} 張`);
}
