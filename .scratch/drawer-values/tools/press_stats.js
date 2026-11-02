/* 抽屜選值鈕按下去的張數變化(drawer-values 規格的 Further Notes)。
   跑法:node .scratch/drawer-values/tools/press_stats.js > .scratch/drawer-values/tools/results/press_stats.txt
   一、單詞標籤(述詞只有詞元與極性的目錄列):位置、極性以外的選值鈕各按一次(加值),0 張時分原因——
       放開極性有命中、放開位置有命中、兩者都放開才有命中、都放開仍沒有(這個詞元沒有這個值)。
   二、全部具名查詢:每顆選值鈕(含位置、極性)按一次(切換),結果 0 張、張數不變、張數改變各幾次。
   張數都是標籤單獨的張數(Cond.soloQuery),走真前端程式與真 data.js。 */
'use strict';
const path = require('path');
const vm = require('vm');
const harness = require(path.join(__dirname, '..', '..', '..', 'script', 'web', 'frontend_harness.js'));

const box = harness.load(harness.realData());
vm.runInContext(`
globalThis.__stats = function () {
  const count = t => Engine.runQuery(window.CARD_DATA, Cond.soloQuery(t)).cards.length;
  const groups = Cond.drawerGroups();
  const chipFields = groups.常用.concat(groups.進階).filter(f => Cond.editor(f).kind === 'values');
  const rows = VOCAB.catalog.filter(r => r.predicate);
  const tagOf = row => Cond.tagAt(row.path.join(Cond.SEP), false);
  const ALL_POS = VOCAB.frame.domains.位置, ALL_POL = VOCAB.frame.domains.極性;

  const single = rows.filter(r => Object.keys(r.predicate).every(k => k === '詞元' || k === '極性'));
  const one = { rows: single.length, presses: 0, hit: 0, polarity: 0, position: 0, both: 0, never: 0, byField: {} };
  single.forEach(row => {
    const tag = tagOf(row);
    chipFields.filter(f => f !== '位置' && f !== '極性').forEach(f => Cond.editor(f).values.forEach(v => {
      const t = Cond.addValue(tag, f, v);
      const relax = (pol, pos) => Object.assign({}, t, { pred: Object.assign({}, t.pred,
        pol ? { 極性: ALL_POL } : {}, pos ? { 位置: ALL_POS } : {}) });
      const k = count(t) ? 'hit' : count(relax(true, false)) ? 'polarity'
        : count(relax(false, true)) ? 'position' : count(relax(true, true)) ? 'both' : 'never';
      const b = one.byField[f] = one.byField[f] || { hit: 0, polarity: 0, position: 0, both: 0, never: 0 };
      one.presses++; one[k]++; b[k]++;
    }));
  });

  const all = { rows: rows.length, presses: 0, zero: 0, same: 0, changed: 0, deadEverywhere: [] };
  const perValue = {};
  rows.forEach(row => {
    const tag = tagOf(row), base = count(tag);
    chipFields.forEach(f => Cond.editor(f).values.forEach(v => {
      const n = count(Cond.toggleValue(tag, f, v));
      const k = n === 0 ? 'zero' : n === base ? 'same' : 'changed';
      all.presses++; all[k]++;
      const key = f + '=' + v;
      perValue[key] = (perValue[key] || 0) + (n === 0 ? 1 : 0);
    }));
  });
  all.deadEverywhere = Object.keys(perValue).filter(k => perValue[k] === rows.length);
  return JSON.stringify({ one, all });
};`, box);

const { one, all } = JSON.parse(vm.runInContext('__stats()', box));
const pct = (n, d) => (100 * n / d).toFixed(1) + '%';
console.log('== 一、單詞標籤:位置與極性以外的選值鈕各加一次 ==');
console.log(`標籤 ${one.rows} 張,按 ${one.presses} 次`);
console.log(`有命中 ${one.hit}(${pct(one.hit, one.presses)})`);
console.log(`0 張・放開極性有命中 ${one.polarity}、放開位置有命中 ${one.position}、兩者都放開才有 ${one.both}`
  + `(合計 ${one.polarity + one.position + one.both},${pct(one.polarity + one.position + one.both, one.presses)})`);
console.log(`0 張・這個詞元沒有這個值 ${one.never}(${pct(one.never, one.presses)})`);
console.log('欄\t有命中\t放開極性\t放開位置\t兩者\t沒有');
Object.entries(one.byField).forEach(([f, b]) =>
  console.log([f, b.hit, b.polarity, b.position, b.both, b.never].join('\t')));
console.log('');
console.log('== 二、全部具名查詢:每顆選值鈕切換一次 ==');
console.log(`標籤 ${all.rows} 張,按 ${all.presses} 次`);
console.log(`0 張 ${all.zero}(${pct(all.zero, all.presses)})、張數不變 ${all.same}(${pct(all.same, all.presses)})、`
  + `張數改變 ${all.changed}(${pct(all.changed, all.presses)})`);
console.log(`在全部 ${all.rows} 張標籤上按了都是 0 張的值:${all.deadEverywhere.join('、') || '無'}`);
