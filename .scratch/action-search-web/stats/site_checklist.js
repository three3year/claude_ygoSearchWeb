/**
 * 票 17 收尾:人工驗收清單裡「要看到幾張」的數字,只在網站上量(帶側欄卡片條件,Python 沒有這些條件)。
 * 跑法(repo 根):node .scratch/action-search-web/stats/site_checklist.js
 * 用接縫三的沙箱(script/web/frontend_harness.js)載入真實的 web/data.js 與 web/action-data.js。
 * 每行:名稱、卡片條件、動作條件、命中張數、無法確認張數;有指定卡時另列它在不在。輸出決定性。
 */
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ROOT = path.join(__dirname, '..', '..', '..');
const harness = require(path.join(ROOT, 'script', 'web', 'frontend_harness.js'));

const dataCtx = {};
dataCtx.window = dataCtx;
vm.createContext(dataCtx);
vm.runInContext(fs.readFileSync(path.join(ROOT, 'web', 'data.js'), 'utf8'), dataCtx);
const sb = harness.load({
  cards: dataCtx.CARD_DATA, vocab: dataCtx.VOCAB, meta: dataCtx.META,
  action: fs.readFileSync(path.join(ROOT, 'web', 'action-data.js'), 'utf8'),
});

const DRAGON = { race: { dragon: 1 } };
const QUICK = { kind: { q: 1 } };
const ALL = ['eff', 'cost', 'cond'];
const CASES = [
  ['破壞', {}, { actions: ['破壞'] }],
  ['破壞+除外', {}, { actions: ['破壞', '除外'] }],
  ['破壞+除外,大類怪獸、龍族', { cat: { m: 1 }, race: { dragon: 1 } }, { actions: ['破壞', '除外'] }],
  ['送墓 到墓地', {}, { actions: ['送墓'], to: { zone: '墓地' } }],
  ['加入手牌 到手牌', {}, { actions: ['加入手牌'], to: { zone: '手牌' } }],
  ['破壞 勾觸發條件', {}, { actions: ['破壞'], kinds: ALL }],
  ['只勾觸發條件 破壞', {}, { actions: ['破壞'], kinds: ['cond'] }],
  ['破壞 抗性,龍族', DRAGON, { actions: ['破壞'], pol: 'resist' }],
  ['破壞 抗性 這張卡自己,龍族', DRAGON, { actions: ['破壞'], pol: 'resist', target: 'self' },
   [15848542, 26268488]],
  ['特殊召喚 誰對手 勾觸發條件', {}, { actions: ['特殊召喚'], agent: '對手', kinds: ALL }, [359563]],
  ['返回 誰對手 勾觸發條件', {}, { actions: ['返回'], agent: '對手', kinds: ALL }, [44818]],
  ['返回 誰對手 勾觸發條件 含不限定的', {}, { actions: ['返回'], agent: '對手', kinds: ALL, unrestricted: true },
   [44818]],
  ['破壞 勾觸發條件 原因戰鬥', {}, { actions: ['破壞'], kinds: ALL, cause: { kind: '戰鬥' } },
   [131182, 595626, 27551, 123709]],
  ['破壞 勾觸發條件 原因效果', {}, { actions: ['破壞'], kinds: ALL, cause: { kind: '效果' } }, [16067089]],
  ['破壞 抗性 原因對手的效果', {}, { actions: ['破壞'], pol: 'resist', cause: { kind: '效果', side: '對手' } },
   [111280, 269012]],
  ['效果類型 2速', QUICK, null],
  ['效果類型 2速 + 破壞', QUICK, { actions: ['破壞'] }, [122520, 43227]],
  ['破壞 勾觸發條件 原因戰鬥 含不限定的', {}, { actions: ['破壞'], kinds: ALL, cause: { kind: '戰鬥' }, unrestricted: true },
   [123709]],
  ['只選破壞', {}, { actions: ['破壞'] }, [35699]],
];

for (const [name, q, act, probe] of CASES) {
  const ids = harness.ids(sb, q, act);
  const unsure = act ? harness.unsure(sb, q, act).length : 0;
  let line = `${name}:${ids.length} 張,無法確認 ${unsure} 張`;
  if (probe) line += `;${probe.map(id => `${id}${ids.includes(id) ? ' 在' : ' 不在'}`).join('、')}`;
  console.log(line);
}
