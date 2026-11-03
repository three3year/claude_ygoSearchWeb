/* 鎖住具名查詢自己寫的欄,抽屜少掉多少灰鈕(drawer-lock 規格的 Further Notes)。
   跑法:node .scratch/drawer-lock/tools/lock_stats.js > .scratch/drawer-lock/tools/results/lock_stats.txt
   一、目錄:帶子的詞元節點(點了只展開、它自己移到子的最後一列);和大類同路徑的 召喚 本來就掛在
       大類底下、沒有自己的子,不算。
   二、條件葉與 耐性/限制 詞元節點:目前抽屜(Cond.drawerOptions)裡、鎖住的欄以外的灰鈕(選值鈕與
       區域鈕),有幾顆在「詞元+鎖住的欄、三個位置、三種極性」下從沒出現過(鎖住後不列)。
   三、耐性/限制 詞元節點:否定形各只留一個值時的張數(鎖住否定形少掉的就是這個)。
   走真前端程式與真 data.js;張數是標籤單獨的張數(Cond.soloQuery)。 */
'use strict';
const path = require('path');
const vm = require('vm');
const harness = require(path.join(__dirname, '..', '..', '..', 'script', 'web', 'frontend_harness.js'));

const box = harness.load(harness.realData());
vm.runInContext(`
globalThis.__lock = function () {
  const count = t => Engine.runQuery(window.CARD_DATA, Cond.soloQuery(t)).cards.length;
  const rows = VOCAB.catalog.filter(r => r.predicate);
  const key = r => r.path.join(Cond.SEP);
  const childOf = (r, o) => o !== r && o.path.length === r.path.length + 1 && key(o).indexOf(key(r) + Cond.SEP) === 0;
  const groupPaths = new Set(VOCAB.catalog.filter(r => !r.predicate).map(key));
  const parents = rows.filter(r => !groupPaths.has(key(r)) && rows.some(o => childOf(r, o)))
    .map(r => r.name + '(子 ' + rows.filter(o => childOf(r, o)).length + ')');

  const lockedFields = r => Object.keys(r.predicate).filter(k => k !== '詞元' && k !== '極性');
  const isLemma = r => Object.keys(r.predicate).every(k => ['詞元', '極性', '否定形'].indexOf(k) >= 0);
  const groups = { 條件葉: [], 耐性限制: [] };
  rows.filter(r => lockedFields(r).length).forEach(r => groups[isLemma(r) ? '耐性限制' : '條件葉'].push(r));

  const grayOf = list => {
    const out = { rows: list.length, gray: 0, gone: 0, byRow: [] };
    list.forEach(row => {
      const tag = Cond.tagAt(key(row), false);
      const locked = lockedFields(row);
      const base = { 詞元: row.predicate.詞元 };
      locked.forEach(k => { base[k] = row.predicate[k]; });
      let gray = 0, gone = 0;
      Cond.drawerOptions(tag).forEach(g => g.fields.forEach(f => {
        if (locked.indexOf(f.field) >= 0) return;
        const seen = Engine.fieldValues(base, f.field);
        if (f.kind === 'values') f.values.filter(v => v.state === Cond.CHIP.GRAY).forEach(v => {
          gray++; if (seen.indexOf(v.value) < 0) gone++;
        });
        if (f.kind === 'region') f.players.forEach(p => p.zones.filter(z => z.state === Cond.CHIP.GRAY).forEach(z => {
          gray++;
          if (!seen.some(([pp, zz]) => zz === z.value && (p.value === null || pp === p.value))) gone++;
        }));
      }));
      out.gray += gray; out.gone += gone;
      out.byRow.push(row.name + ' 灰 ' + gray + ' 不列 ' + gone);
    });
    return out;
  };

  const split = groups.耐性限制.filter(r => r.predicate.否定形.length > 1).map(row => {
    const tag = Cond.tagAt(key(row), false);
    return row.name + ' ' + count(tag) + ' 張:' + row.predicate.否定形.map(n =>
      n + ' ' + count(Object.assign({}, tag, { pred: Object.assign({}, tag.pred, { 否定形: [n] }) }))).join('、');
  });
  return JSON.stringify({ parents, leaf: grayOf(groups.條件葉), neg: grayOf(groups.耐性限制), split });
};`, box);

const { parents, leaf, neg, split } = JSON.parse(vm.runInContext('__lock()', box));
console.log('== 一、帶子的詞元節點 ==');
console.log(`${parents.length} 個:${parents.join('、')}`);
console.log('');
[['二之一、條件葉', leaf], ['二之二、耐性/限制 詞元節點', neg]].forEach(([title, g]) => {
  console.log(`== ${title}:鎖住的欄以外的灰鈕 ==`);
  console.log(`標籤 ${g.rows} 張,灰 ${g.gray} 顆,鎖住後不列 ${g.gone} 顆,仍灰 ${g.gray - g.gone} 顆`);
  g.byRow.forEach(line => console.log('  ' + line));
  console.log('');
});
console.log('== 三、耐性/限制 詞元節點:否定形只留一個值的張數 ==');
split.forEach(line => console.log(line));
