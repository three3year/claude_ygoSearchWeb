// 規格 3 用:對真實投影逐查詢算張數、雜湊(對匯出檔目錄欄)與耗時。
const fs = require('fs'), crypto = require('crypto');
const [, , proj, exportPath] = process.argv;
const V = JSON.parse(fs.readFileSync(proj, 'utf8'));
const doc = JSON.parse(fs.readFileSync(exportPath, 'utf8'));
const idx = a => { const m = new Map(); a.forEach((v, i) => m.set(v, i + 1)); return m; };
const T = { lem: new Map(V.lemmas.map((v, i) => [v, i])), pos: idx(V.pos), pol: idx(V.pol), voi: idx(V.voi), neg: idx(V.neg),
  agt: idx(V.agt), man: idx(V.man), pm: idx(V.pm), hk: idx(V.hk), qk: idx(V.qk) };
const MOD = new Map(V.mod.map((v, i) => [v, 1 << i]));
const list = v => (Array.isArray(v) && !(v.length === 2 && (v[0] === null || typeof v[0] === 'string') && false) ? v : [v]);
const set = (tb, v) => new Set(list(v).map(x => tb.get(x)).filter(x => x != null));
const SLOT = { 詞元: [0, 'lem'], 位置: [1, 'pos'], 極性: [2, 'pol'], 態: [3, 'voi'], 否定形: [4, 'neg'], 施事者: [5, 'agt'], 方式類: [6, 'man'], 動作對象: [7, 'pm'] };
function regionSet(items) {
  const s = new Set(); const nz = V.zones.length;
  for (const [p, z] of items) {
    const zi = V.zones.indexOf(z);
    if (p === null) for (let i = 0; i < V.players.length; i++) s.add(i * nz + zi);
    else s.add(V.players.indexOf(p) * nz + zi);
  }
  return s;
}
function headSet(vals) {
  const s = new Set();
  V.heads.forEach((h, i) => { if (list(vals).some(w => h.endsWith(w))) s.add(i); });
  return s;
}
function compile(pred) {
  const ch = [];
  for (const f in pred) {
    if (SLOT[f]) { const [i, t] = SLOT[f]; const s = set(T[t], pred[f]); ch.push(fr => s.has(fr[i])); }
    else if (f === '來源' || f === '目的' || f === '所在') {
      const i = { 來源: 8, 目的: 9, 所在: 10 }[f]; const s = regionSet(pred[f]);
      ch.push(fr => { const a = fr[i]; if (!a) return false; for (const x of a) if (s.has(x)) return true; return false; });
    } else if (f === '受事者中心詞' || f === '目的中心詞') {
      const i = f === '受事者中心詞' ? 11 : 12; const s = headSet(pred[f]);
      ch.push(fr => { const a = fr[i]; if (!a) return false; for (const g of a) if (s.has(g[0])) return true; return false; });
    } else if (f === '中心詞類' || f === '數量類') {
      const k = f === '中心詞類' ? 1 : 2; const s = set(f === '中心詞類' ? T.hk : T.qk, pred[f]);
      ch.push(fr => { const a = fr[11]; if (!a) return false; for (const g of a) if (s.has(g[k])) return true; return false; });
    } else if (f === '修飾語類') {
      let m = 0; for (const v of list(pred[f])) m |= MOD.get(v) || 0;
      ch.push(fr => { const a = fr[11]; if (!a) return false; for (const g of a) if ((g[3] || 0) & m) return true; return false; });
    } else throw new Error(f);
  }
  return fr => { for (const c of ch) if (!c(fr)) return false; return true; };
}
function run(preds) {
  const ms = preds.map(compile); const out = [];
  for (const c of V.cards) {
    if (!c.fr) continue;
    const ok = ms.map(() => false);
    for (const row of c.fr) for (const fr of row) ms.forEach((m, i) => { if (!ok[i] && m(fr)) ok[i] = true; });
    if (ok.every(Boolean)) out.push(c.id);
  }
  return out;
}
const hash = ids => crypto.createHash('sha1').update(ids.slice().sort((a, b) => a - b).join(',')).digest('hex').slice(0, 16);
let bad = 0, n = 0;
const t0 = Date.now();
for (const r of doc['目錄']) {
  if (!r.predicate) continue;
  for (const pos of ['代價', '效果', '條件']) {
    const ids = run([{ ...r.predicate, 位置: pos }]); n++;
    if (ids.length !== r.cards[pos] || hash(ids) !== r.hash[pos]) { bad++; if (bad < 10) console.log('差', r.name, pos, ids.length, r.cards[pos]); }
  }
}
console.log('逐查詢比對', n, '不符', bad, '總耗時 ms', Date.now() - t0);
const time = (name, preds) => {
  const ts = []; let k = 0;
  for (let i = 0; i < 30; i++) { const a = performance.now(); k = run(preds).length; ts.push(performance.now() - a); }
  ts.sort((a, b) => a - b); console.log(name, k + ' 卡', ts[15].toFixed(1) + ' ms', '最差', ts[29].toFixed(1));
};
const A = { 詞元: '特殊召喚', 位置: '效果', 來源: [[null, '墓地'], [null, '除外']] };
const B = { 詞元: '破壊', 所在: [['相手', '場上']], 受事者中心詞: ['モンスター'] };
const C = { 詞元: ['送る', '除外'], 目的: [[null, '墓地'], [null, '除外']], 極性: ['肯定'] };
const D = { 詞元: '加える', 來源: [[null, '牌組'], [null, '墓地']], 動作對象: '非此卡' };
const E = { 詞元: '対象とする', 位置: '條件' };
time('1 述詞', [A]); time('3 述詞', [A, B, C]); time('5 述詞', [A, B, C, D, E]);
time('只比中心詞', [{ 受事者中心詞: ['モンスター', '魔法'] }]);
const sz = JSON.stringify(V.cards);
let a = performance.now(); JSON.parse(sz); console.log('JSON.parse 卡片段 ms', (performance.now() - a).toFixed(0), 'MB', (sz.length / 1e6).toFixed(1));
