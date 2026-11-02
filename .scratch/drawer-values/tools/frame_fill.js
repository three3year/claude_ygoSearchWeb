/* 框表的值分布(drawer-values 規格的 Further Notes):各欄各值出現在幾個框、否定形與極性的交叉、
   框是否都在卡上(框層有命中 ⇔ 卡層有命中的前提)、目錄的極性、每個詞元的框數上限(抽屜一次掃描的量)。
   跑法:node .scratch/drawer-values/tools/frame_fill.js > .scratch/drawer-values/tools/results/frame_fill.txt */
'use strict';
const path = require('path');
const harness = require(path.join(__dirname, '..', '..', '..', 'script', 'web', 'frontend_harness.js'));

const { frames: F, vocab, cards } = harness.realData();
const D = vocab.frame.domains;
console.log('框數', F.length);

const onCards = new Set();
cards.forEach(c => (c.fr || []).forEach(ids => ids.forEach(i => onCards.add(i))));
console.log('掛在卡上的框', onCards.size);
console.log('中心詞表', vocab.frame.heads.length, '個;詞元表', vocab.frame.lemmas.length, '個');

const tally = (name, get) => {
  const c = {};
  let any = 0;
  F.forEach(f => {
    const vals = get(f);
    if (vals.length) any++;
    vals.forEach(v => { c[v] = (c[v] || 0) + 1; });
  });
  const missing = (D[name] || []).filter(v => !c[v]);
  console.log(`${name}:有值的框 ${any}(${(100 * any / F.length).toFixed(1)}%)`, JSON.stringify(c),
    missing.length ? '全語料沒有:' + missing.join('、') : '');
};
const scalar = (slot, field) => f => (f[slot] ? [D[field][f[slot] - 1]] : []);
const segs = f => f[11] || [];
tally('位置', scalar(1, '位置'));
tally('極性', scalar(2, '極性'));
tally('態', scalar(3, '態'));
tally('否定形', scalar(4, '否定形'));
tally('施事者', scalar(5, '施事者'));
tally('方式類', scalar(6, '方式類'));
tally('動作對象', scalar(7, '動作對象'));
tally('中心詞類', f => [...new Set(segs(f).filter(s => s[1]).map(s => D.中心詞類[s[1] - 1]))]);
tally('數量類', f => [...new Set(segs(f).filter(s => s[2]).map(s => D.數量類[s[2] - 1]))]);
tally('修飾語類', f => D.修飾語類.filter((_, i) => segs(f).some(s => (s[3] || 0) & (1 << i))));

const cross = {};
F.forEach(f => {
  if (!f[4]) return;
  const k = D.否定形[f[4] - 1] + '×' + (f[2] ? D.極性[f[2] - 1] : '無');
  cross[k] = (cross[k] || 0) + 1;
});
console.log('否定形×極性', JSON.stringify(cross));

const pol = {};
vocab.catalog.filter(r => r.predicate).forEach(r => {
  const k = JSON.stringify(r.predicate.極性 || null);
  pol[k] = (pol[k] || 0) + 1;
});
console.log('具名查詢的極性', JSON.stringify(pol));

const perLemma = {};
F.forEach(f => { perLemma[f[0]] = (perLemma[f[0]] || 0) + 1; });
const top = Object.entries(perLemma).sort((a, b) => b[1] - a[1]).slice(0, 5)
  .map(([l, n]) => `${vocab.frame.lemmas[l]} ${n}`);
console.log('框數最多的詞元', top.join('、'));
