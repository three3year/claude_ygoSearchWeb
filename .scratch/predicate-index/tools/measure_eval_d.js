// D:框表——每述詞對唯一框算一張命中表(Uint8Array),再逐卡逐句查表;回命中句與命中框。
const fs = require('fs'), crypto = require('crypto');
const src = fs.readFileSync(process.argv[1].replace('measure_eval_d', 'measure_eval'), 'utf8');
const compileSrc = src.slice(src.indexOf('const idx ='), src.indexOf('function run('));
const V = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const doc = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const compile = new Function('V', compileSrc + '; return compile;')(V);
const uniq = new Map(), table = [];
const cards = V.cards.map(c => {
  if (!c.fr) return c;
  return { ...c, fr: c.fr.map(row => row.map(f => {
    const k = JSON.stringify(f); let n = uniq.get(k);
    if (n === undefined) { n = table.length; uniq.set(k, n); table.push(f); }
    return n;
  })) };
});
console.log('唯一框', table.length);
function run(preds) {
  const hits = preds.map(p => { const m = compile(p), h = new Uint8Array(table.length);
    for (let i = 0; i < table.length; i++) if (m(table[i])) h[i] = 1; return h; });
  const out = [];
  for (const c of cards) {
    if (!c.fr) continue;
    let all = true; const rows = [];
    for (const h of hits) {
      let ok = false;
      for (let r = 0; r < c.fr.length; r++) { const row = c.fr[r];
        for (let k = 0; k < row.length; k++) if (h[row[k]]) { ok = true; rows.push(r, k); } }
      if (!ok) { all = false; break; }
    }
    if (all) out.push(c.id);
  }
  return out;
}
const hash = ids => crypto.createHash('sha1').update(ids.slice().sort((a, b) => a - b).join(',')).digest('hex').slice(0, 16);
let bad = 0, n = 0; const t0 = Date.now();
for (const r of doc['目錄']) { if (!r.predicate) continue;
  for (const pos of ['代價', '效果', '條件']) { const ids = run([{ ...r.predicate, 位置: pos }]); n++;
    if (ids.length !== r.cards[pos] || hash(ids) !== r.hash[pos]) bad++; } }
console.log('逐查詢比對', n, '不符', bad, '總耗時 ms', Date.now() - t0);
const time = (name, preds) => { const ts = []; let k = 0;
  for (let i = 0; i < 30; i++) { const a = performance.now(); k = run(preds).length; ts.push(performance.now() - a); }
  ts.sort((a, b) => a - b); console.log(name, k + ' 卡', ts[15].toFixed(1) + ' ms', '最差', ts[29].toFixed(1)); };
const A = { 詞元: '特殊召喚', 位置: '效果', 來源: [[null, '墓地'], [null, '除外']] };
const B = { 詞元: '破壊', 所在: [['相手', '場上']], 受事者中心詞: ['モンスター'] };
const C = { 詞元: ['送る', '除外'], 目的: [[null, '墓地'], [null, '除外']], 極性: ['肯定'] };
const D = { 詞元: '加える', 來源: [[null, '牌組'], [null, '墓地']], 動作對象: '非此卡' };
const E = { 詞元: '対象とする', 位置: '條件' };
time('1 述詞', [A]); time('3 述詞', [A, B, C]); time('5 述詞', [A, B, C, D, E]);
time('只比中心詞', [{ 受事者中心詞: ['モンスター', '魔法'] }]);
