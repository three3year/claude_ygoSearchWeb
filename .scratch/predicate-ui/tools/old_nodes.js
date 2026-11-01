// 規格 4 用:舊樹 284 個節點對不上目錄路徑的組成。跑法:node .scratch/predicate-ui/tools/old_nodes.js
'use strict';
const path = require('path');
const real = require(path.join(__dirname, '..', '..', '..', 'script', 'web', 'frontend_harness.js')).realData();
const cat = real.vocab.catalog;
const q = new Set(cat.filter(r => r.predicate).map(r => r.path.join('›')));
const groups = new Set(cat.filter(r => !r.predicate).map(r => r.path.join('›')));
const out = { 對得上: 0, 大類中類: [], 預設葉: [], 其他: [] };
const walk = (n, parent) => {
  const id = parent ? parent + '›' + n[0] : n[0];
  const kids = n[2] || [];
  if (q.has(id)) out.對得上++;
  else if (groups.has(id)) out.大類中類.push(id);
  else out.其他.push(id);
  kids.forEach(c => walk(c, id));
  if (n[1] >= 0 && kids.length) {
    const own = id + '›' + n[0];
    if (q.has(own)) out.對得上++; else out.預設葉.push(own);
  }
};
real.vocab.acat.tree.forEach(n => walk(n, ''));
console.log('對得上', out.對得上, '大類中類', out.大類中類.length, '預設葉', out.預設葉.length, '其他', out.其他.length);
console.log('其他', JSON.stringify(out.其他));
