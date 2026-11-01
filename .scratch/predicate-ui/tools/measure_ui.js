// 規格 4 用:量目錄鍵與舊網址、OR 的耗時(每張 OR 標籤各跑一次再聯集,同原型)、卡片段舊六欄占比。
// 跑法:node .scratch/predicate-ui/tools/measure_ui.js
'use strict';
const fs = require('fs'), path = require('path'), zlib = require('zlib');
const harness = require(path.join(__dirname, '..', '..', '..', 'script', 'web', 'frontend_harness.js'));
const real = harness.realData();
const box = harness.load(real);
const vm = require('vm');
const run = q => { box.__q = JSON.stringify(q); return vm.runInContext('Engine.runQuery(window.CARD_DATA, JSON.parse(__q)).cards.length', box); };
const timed = (fn, n = 31) => {
  const t = [];
  for (let i = 0; i < n; i++) { const a = process.hrtime.bigint(); fn(); t.push(Number(process.hrtime.bigint() - a) / 1e6); }
  t.sort((a, b) => a - b);
  return t[n >> 1].toFixed(1);
};
const cat = real.vocab.catalog;
const byName = n => cat.find(r => r.name === n && r.predicate);
const eff = n => Object.assign({ 位置: ['效果'] }, byName(n).predicate);
const leaves = ['特殊召喚←墓地', '特殊召喚←除外', '破壊', 'ドロー', '除外'];
for (const n of leaves) console.log('leaf', n, byName(n).cards.效果);
const base = { cat: { m: 1 }, preds: { inc: [eff('破壊')], ex: [] } };
const orRun = k => () => {
  const seen = new Set();
  for (let i = 0; i < k; i++) {
    box.__q = JSON.stringify(Object.assign({}, base, { preds: { inc: [eff('破壊'), eff(leaves[i])], ex: [] } }));
    vm.runInContext('Engine.runQuery(window.CARD_DATA, JSON.parse(__q)).cards', box).forEach(e => seen.add(e.card.id));
  }
  return seen.size;
};
for (const k of [1, 2, 3, 5]) console.log(`OR ${k} 張標籤+AND 破壊 與 怪獸: 聯集 ${orRun(k)()} 張, 中位 ${timed(orRun(k))} ms(node vm)`);
// 舊節點路徑有多少對得上目錄路徑
const pathsNow = new Set(cat.filter(r => r.predicate).map(r => r.path.join('›')));
const oldIds = [];
const walk = (node, parent) => {
  const id = parent ? parent + '›' + node[0] : node[0];
  oldIds.push(id);
  (node[2] || []).forEach(c => walk(c, id));
  if (node[1] >= 0 && (node[2] || []).length) oldIds.push(id + '›' + node[0] + '(預設葉)');
};
(real.vocab.acat.tree || []).forEach(n => walk(n, ''));
const hit = oldIds.filter(id => pathsNow.has(id));
console.log('舊節點', oldIds.length, '路徑對得上具名查詢', hit.length, '對不上', oldIds.length - hit.length);
// 舊欄的體積
const FIELDS = ['ae', 'ac', 'aes', 'aen', 'acs', 'acn'];
const stripped = real.cards.map(c => { const o = Object.assign({}, c); FIELDS.forEach(f => delete o[f]); return o; });
const size = o => { const s = JSON.stringify(o); return [Buffer.byteLength(s), zlib.gzipSync(s).length]; };
console.log('卡片段 現在', size(real.cards), '刪舊六欄', size(stripped), 'VOCAB.acat', size(real.vocab.acat));
const file = path.join(__dirname, '..', '..', '..', 'web', 'data.js');
console.log('data.js', fs.statSync(file).size, zlib.gzipSync(fs.readFileSync(file)).length);
