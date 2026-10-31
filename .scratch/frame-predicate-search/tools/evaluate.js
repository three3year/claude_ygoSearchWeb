'use strict';
/* 票 01「索引體積與評估器速度實測」的最小述詞評估器:純函式,輸入述詞清單與每卡每句的
   框架清單,回命中卡與命中句/框。讀 project.py 寫出的投影檔(編碼 C 元組+對照表,與編碼 A
   欄名物件),在 Node 跑 1、3、5 個述詞(含多值欄位、排除述詞、只比中心詞字面的述詞),
   量 14,207 張卡一次搜尋的毫秒數。不進 web/。

   用法:node .scratch/frame-predicate-search/tools/evaluate.js <project.py 的 --out 目錄> */
const fs = require('fs');
const path = require('path');

const dir = process.argv[2];
if (!dir) { console.error('need out dir'); process.exit(2); }

const PLAYERS = ['無', '自分', '相手', '雙方', '相對'];
const ZONES = ['手牌', '牌組', '額外牌組', '墓地', '除外', '場上', '靈擺區'];
const POSITIONS = ['效果', '代價', '條件'];
const POLARITIES = ['肯定', '否定', '可能'];
const MODES = [null, '此卡', '非此卡'];
const pair = (p, z) => PLAYERS.indexOf(p) * 8 + ZONES.indexOf(z);

/* ---- 編碼 C:元組 [詞元, 位置, 極性, 態, 來源[], 目的[], 所在[], 動作對象, 中心詞[], 目的中心詞[]],
   尾端空值截掉;中心詞是對照表碼。述詞的每個欄是 Set(同欄多值 OR)。 ---- */
const F = { lemma: 0, position: 1, polarity: 2, voice: 3, source: 4, goal: 5, place: 6, mode: 7, heads: 8, goalHeads: 9 };
const SCALAR = ['lemma', 'position', 'polarity', 'voice', 'mode'];
const LISTS = ['source', 'goal', 'place', 'heads', 'goalHeads'];

function compileC(pred, lemmas, heads) {
  const out = { exclude: !!pred.exclude, scalar: [], lists: [] };
  const sets = {};
  if (pred.lemma) sets.lemma = new Set(pred.lemma.map(l => lemmas.indexOf(l)));
  if (pred.position) sets.position = new Set(pred.position.map(p => POSITIONS.indexOf(p)));
  if (pred.polarity) sets.polarity = new Set(pred.polarity.map(p => POLARITIES.indexOf(p)));
  if (pred.mode) sets.mode = new Set(pred.mode.map(m => MODES.indexOf(m)));
  for (const k of ['source', 'goal', 'place']) {
    if (pred[k]) sets[k] = new Set(pred[k].map(([p, z]) => pair(p, z)));
  }
  /* 中心詞子字串 → 一次解成對照表碼的集合(查詢期做一次,每框只比整數) */
  for (const k of ['heads', 'goalHeads']) {
    if (pred[k]) {
      const s = new Set();
      heads.forEach((h, i) => { if (pred[k].some(sub => h.includes(sub))) s.add(i); });
      sets[k] = s;
    }
  }
  for (const k of SCALAR) if (sets[k]) out.scalar.push([F[k], sets[k]]);
  for (const k of LISTS) if (sets[k]) out.lists.push([F[k], sets[k]]);
  return out;
}

function frameHitC(fr, p) {
  for (const [i, set] of p.scalar) {
    if (!set.has(fr[i] === undefined ? 0 : fr[i])) return false;
  }
  for (const [i, set] of p.lists) {
    const vals = fr[i];
    if (!vals || !vals.length) return false;
    let ok = false;
    for (const v of vals) if (set.has(v)) { ok = true; break; }
    if (!ok) return false;
  }
  return true;
}

/* ---- 編碼 A:欄名物件,值可讀;中心詞字面在比對時做子字串。 ---- */
function compileA(pred) {
  const out = { exclude: !!pred.exclude, scalar: [], lists: [], subs: [] };
  if (pred.lemma) out.scalar.push(['l', new Set(pred.lemma)]);
  if (pred.position) out.scalar.push(['p', new Set(pred.position)]);
  if (pred.polarity) out.scalar.push(['g', new Set(pred.polarity), '肯定']);
  if (pred.mode) out.scalar.push(['m', new Set(pred.mode)]);
  const zone = k => ({ source: 's', goal: 'd', place: 'a' })[k];
  for (const k of ['source', 'goal', 'place']) {
    if (pred[k]) out.lists.push([zone(k), new Set(pred[k].map(([p, z]) => p + ':' + z))]);
  }
  if (pred.heads) out.subs.push(['h', pred.heads]);
  if (pred.goalHeads) out.subs.push(['dh', pred.goalHeads]);
  return out;
}

function frameHitA(fr, p) {
  for (const [k, set, dflt] of p.scalar) {
    const v = fr[k] === undefined ? dflt : fr[k];
    if (!set.has(v)) return false;
  }
  for (const [k, set] of p.lists) {
    const vals = fr[k];
    if (!vals) return false;
    let ok = false;
    for (const v of vals) if (set.has(v)) { ok = true; break; }
    if (!ok) return false;
  }
  for (const [k, subs] of p.subs) {
    const vals = fr[k];
    if (!vals) return false;
    let ok = false;
    for (const v of vals) { if (subs.some(s => v.includes(s))) { ok = true; break; } }
    if (!ok) return false;
  }
  return true;
}

/* ---- 查詢:排除述詞卡層優先;包含述詞各自要有一句某框命中(可以不同句),回命中句與命中框。 ---- */
function runQuery(cards, preds, frameHit) {
  const inc = preds.filter(p => !p.exclude), ex = preds.filter(p => p.exclude);
  const hits = [];
  for (const c of cards) {
    const fr = c.fr;
    if (!fr) continue;
    let excluded = false;
    for (const p of ex) {
      for (let i = 0; i < fr.length && !excluded; i++) {
        const row = fr[i];
        for (let j = 0; j < row.length; j++) if (frameHit(row[j], p)) { excluded = true; break; }
      }
      if (excluded) break;
    }
    if (excluded) continue;
    let rows = null;
    if (inc.length) {
      const sentenceHits = new Map();   // 句 → [框序]
      let allMet = true;
      for (const p of inc) {
        let met = false;
        for (let i = 0; i < fr.length; i++) {
          const row = fr[i];
          for (let j = 0; j < row.length; j++) {
            if (frameHit(row[j], p)) {
              met = true;
              if (!sentenceHits.has(i)) sentenceHits.set(i, []);
              sentenceHits.get(i).push(j);
            }
          }
        }
        if (!met) { allMet = false; break; }
      }
      if (!allMet) continue;
      rows = Array.from(sentenceHits.keys()).sort((a, b) => a - b);
    }
    hits.push({ id: c.id, rows });
  }
  return hits;
}

/* ---- 述詞樣本 ---- */
const P = {
  // 特殊召喚←墓地/除外(效果位;來源多值)
  spsummon: { lemma: ['特殊召喚'], position: ['效果'], source: [['無', '墓地'], ['自分', '墓地'], ['無', '除外'], ['自分', '除外']] },
  // 破壊@相手フィールド:モンスター(所在+中心詞子字串)
  destroy: { lemma: ['破壊'], place: [['相手', '場上']], heads: ['モンスター'] },
  // 送る/除外 → 墓地/除外(詞元多值、目的多值、極性)
  send: { lemma: ['送る', '除外'], polarity: ['肯定'], goal: [['無', '墓地'], ['自分', '墓地'], ['相手', '墓地'], ['無', '除外']] },
  // 加える:デッキ/墓地→手札,非此卡
  search: { lemma: ['加える'], source: [['無', '牌組'], ['自分', '牌組'], ['無', '墓地'], ['自分', '墓地']], goal: [['無', '手牌']], mode: ['非此卡'] },
  // 排除:有 対象とする 的卡整張不要
  noTarget: { lemma: ['対象とする'], exclude: true },
  // 只比中心詞(沒有詞元,每框都要跑子字串/集合):最差分支
  headsOnly: { heads: ['カード', 'モンスター'] },
  // 條件位:存在@自分フィールド
  exists: { lemma: ['存在'], position: ['條件'], goal: [['自分', '場上']] },
};
const SUITES = {
  '1 述詞': ['spsummon'],
  '3 述詞': ['spsummon', 'destroy', 'send'],
  '5 述詞(含 1 排除)': ['spsummon', 'destroy', 'send', 'search', 'noTarget'],
  '只比中心詞(2 子字串)': ['headsOnly'],
  '條件位 1 述詞': ['exists'],
  '3 述詞 + 中心詞 + 排除': ['destroy', 'headsOnly', 'noTarget'],
};

function bench(label, fn, warm = 5, runs = 30) {
  for (let i = 0; i < warm; i++) fn();
  const times = [];
  let result;
  for (let i = 0; i < runs; i++) {
    const t = process.hrtime.bigint();
    result = fn();
    times.push(Number(process.hrtime.bigint() - t) / 1e6);
  }
  times.sort((a, b) => a - b);
  return { label, median: +times[Math.floor(runs / 2)].toFixed(2), min: +times[0].toFixed(2), p90: +times[Math.floor(runs * 0.9)].toFixed(2), cards: result.length };
}

function parseBench(file) {
  const text = fs.readFileSync(file, 'utf8');
  const t = process.hrtime.bigint();
  const doc = JSON.parse(text);
  const ms = Number(process.hrtime.bigint() - t) / 1e6;
  return { doc, bytes: Buffer.byteLength(text), parseMs: +ms.toFixed(1) };
}

const C = parseBench(path.join(dir, 'proj_C_dict.json'));
const A = parseBench(path.join(dir, 'proj_A_objects.json'));
const out = { parse: { C: { bytes: C.bytes, ms: C.parseMs }, A: { bytes: A.bytes, ms: A.parseMs } }, C: [], A: [] };
const cardsC = C.doc.cards, cardsA = A.doc.cards;
out.cards = cardsC.length;
out.covered = cardsC.filter(c => c.fr).length;

for (const [name, keys] of Object.entries(SUITES)) {
  const predsC = keys.map(k => compileC(P[k], C.doc.lemmas, C.doc.heads));
  const predsA = keys.map(k => compileA(P[k]));
  const rC = bench(name, () => runQuery(cardsC, predsC, frameHitC));
  const rA = bench(name, () => runQuery(cardsA, predsA, frameHitA));
  if (rC.cards !== rA.cards) rC.mismatchWithA = rA.cards;
  out.C.push(rC);
  out.A.push(rA);
}
/* 述詞編譯(中心詞子字串 → 碼集合)本身的成本,查詢期每次做一次 */
out.compileHeadsMs = bench('compile heads', () => [compileC(P.destroy, C.doc.lemmas, C.doc.heads), compileC(P.headsOnly, C.doc.lemmas, C.doc.heads)], 5, 30).median;
console.log(JSON.stringify(out, null, 1));
fs.writeFileSync(path.join(dir, 'timing.json'), JSON.stringify(out, null, 1));
