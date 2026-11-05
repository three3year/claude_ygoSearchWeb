// 針對卡片「挑目錄列」視窗的耗時估計(原型,target-card)。
// 接縫:script/web/frontend_harness.js 依 index.html 順序載入真前端碼與真 web/data.js;
// 逐列(目錄有 predicate 的列)跑 Cond.tagAt → Cond.soloQuery → Engine.runQuery,量現行耗時(下限)。
// 上限:把 engine.js 原始碼換名成 EngineSim、在 predHitTable 逐框加一個模擬的「針對卡片」比對
// (每段比種族位元、屬性位元、等級/攻擊數值、卡名字串包含;受事者段 + 目的段 + 模擬回指段),
// 另記「部分條件未比對」表。變體:
//   A  框表照現在去重(FRAMES 筆數)逐框比一次
//   B  去重被打破(片語帶條件字面後框元組不再共用):逐框比 refs/FRAMES 倍次
// 用法:node .scratch/target-card/tools/ui_dialog_timing.js [卡片密碼,預設 46986414 黑魔導]
// 結果寫 tools/results/ui_dialog_timing.txt(也印 stdout)。
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.resolve(__dirname, '..', '..', '..');
const harness = require(path.join(ROOT, 'script', 'web', 'frontend_harness.js'));
const OUT = path.join(__dirname, 'results', 'ui_dialog_timing.txt');
const TARGET_ID = Number(process.argv[2] || 46986414);
const REPEAT = 3;

const lines = [];
const log = (...a) => { const s = a.join(' '); lines.push(s); console.log(s); };

const data = harness.realData();
if (!data) throw new Error('沒有 web/data.js');
const box = harness.load(data);

const engineSrc = fs.readFileSync(path.join(ROOT, 'web', 'js', 'engine.js'), 'utf8');
const HOOK_FROM = 'FRAMES.forEach((f, n) => { if (checks.every(check => check(f))) table[n] = 1; });';
const HOOK_TO = 'FRAMES.forEach((f, n) => { if (checks.every(check => check(f)) && (!window.__target || window.__target(f, n))) table[n] = 1; });';
if (engineSrc.indexOf('const Engine = (() => {') < 0 || engineSrc.indexOf(HOOK_FROM) < 0) {
  throw new Error('engine.js 形狀變了,補丁對不上');
}
const EXPORT_FROM = 'return Object.freeze({ runQuery,';
if (engineSrc.indexOf(EXPORT_FROM) < 0) throw new Error('engine.js 匯出形狀變了');
vm.runInContext(engineSrc.replace('const Engine = (() => {', 'var EngineSim = (() => {').replace(HOOK_FROM, HOOK_TO)
  .replace(EXPORT_FROM, 'return Object.freeze({ predHitTable, predOnCard, frameChecks, runQuery,'),
  box, { filename: 'engine_sim.js' });

const Cond = vm.runInContext('Cond', box);
const Engine = vm.runInContext('Engine', box);
const EngineSim = box.EngineSim;
const SEP = Cond.SEP;
const cards = data.cards;
const frames = data.frames;
const heads = data.vocab.frame.heads;
const rows = data.vocab.catalog.filter(r => r.predicate);

let refs = 0;
cards.forEach(c => (c.fr || []).forEach(a => { refs += a.length; }));

/* 目標卡的卡面參數先編成位元與數值,一次。 */
const target = cards.find(c => c.id === TARGET_ID);
if (!target) throw new Error('找不到卡 ' + TARGET_ID);
const codeIndex = (dom, code) => Math.max(0, (data.vocab[dom].items || []).findIndex(it => it.code === code));
const T = {
  raceBit: target.r ? 1 << codeIndex('race', target.r) : 0,
  attrBit: target.at ? 1 << codeIndex('attr', target.at) : 0,
  lv: target.lv == null ? -1 : target.lv,
  atk: target.atk == null ? -1 : target.atk,
  name: target.nj || '',
};

/* 模擬一段片語寫出的條件:由段的碼決定性地生出種族/屬性遮罩、數值門檻、字段字串。 */
function segCheck(seg) {
  const h = seg[0] | 0;
  const raceMask = (h * 2654435761) >>> 7 & 0x3ffffff;
  const attrMask = (h * 40503) >>> 3 & 0x7f;
  const lvMax = (h % 12) + 1;
  const atkMin = (h % 30) * 100;
  const word = heads[h] || '';
  let unmatched = (seg[3] & 0x100) !== 0;
  const ok = (raceMask === 0 || (raceMask & T.raceBit) !== 0)
    && (attrMask === 0 || (attrMask & T.attrBit) !== 0)
    && (T.lv < 0 || T.lv <= lvMax || seg[2] === 3)
    && (T.atk < 0 || T.atk >= atkMin || seg[2] === 2)
    && (word.length < 2 || T.name.indexOf(word) >= 0 || word.indexOf('モンスター') >= 0);
  return ok ? (unmatched ? 2 : 1) : 0;
}

function makeTarget(times, forcePass) {
  const unmatched = new Uint8Array(frames.length);
  return (f, n) => {
    let hit = false;
    for (let t = 0; t < times; t++) {
      hit = false;
      const groups = [f[11] || [], f[12] || [], f[11] || []]; // 受事者、目的、模擬回指目標
      for (const segs of groups) {
        for (const seg of segs) {
          const r = segCheck(seg);
          if (r) { hit = true; if (r === 2) unmatched[n] = 1; }
        }
      }
      if (!groups[0].length && !groups[1].length) hit = true;
    }
    return forcePass || hit;
  };
}

function median(a) {
  const s = a.slice().sort((x, y) => x - y);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

function timeRows(engine, label, targetFn) {
  box.__target = targetFn;
  const per = rows.map(() => Infinity);
  const counts = rows.map(() => 0);
  let wallMin = Infinity;
  for (let rep = 0; rep < REPEAT; rep++) {
    const wall0 = process.hrtime.bigint();
    rows.forEach((row, k) => {
      const tag = Cond.tagAt(row.path.join(SEP), false);
      const q = Cond.soloQuery(tag);
      const t0 = process.hrtime.bigint();
      const res = engine.runQuery(cards, q);
      const ms = Number(process.hrtime.bigint() - t0) / 1e6;
      if (ms < per[k]) per[k] = ms;
      counts[k] = res.cards.length;
    });
    wallMin = Math.min(wallMin, Number(process.hrtime.bigint() - wall0) / 1e6);
  }
  box.__target = null;
  const worstK = per.indexOf(Math.max(...per));
  const nonzero = counts.filter(n => n > 0).length;
  log(`${label}`);
  log(`  列數 ${rows.length}、有命中 ${nonzero} 列`);
  log(`  逐列 中位數 ${median(per).toFixed(2)} ms、最差 ${per[worstK].toFixed(2)} ms(${rows[worstK].name})`);
  log(`  全部列合計(${REPEAT} 次取最快一輪)${wallMin.toFixed(0)} ms;手機 ×4 ≈ ${(wallMin * 4).toFixed(0)} ms`);
  return { per, wallMin, counts };
}

/* 只算一次目標卡命中表、各列只 AND:視窗實作可走的捷徑。 */
function timeSharedTable(times) {
  const fn = makeTarget(times);
  let best = Infinity;
  for (let rep = 0; rep < REPEAT; rep++) {
    const t0 = process.hrtime.bigint();
    const table = new Uint8Array(frames.length);
    frames.forEach((f, n) => { if (fn(f, n)) table[n] = 1; });
    best = Math.min(best, Number(process.hrtime.bigint() - t0) / 1e6);
  }
  return best;
}

log(`資料:卡 ${cards.length}、框表 ${frames.length} 筆、卡上框參照 ${refs}(倍數 ${(refs / frames.length).toFixed(2)})`);
log(`目錄 ${data.vocab.catalog.length} 列,帶 predicate ${rows.length} 列(其餘是大類/中類導覽節點)`);
log(`目標卡 ${target.id} ${target.n}(${target.nj});node ${process.version};每列跑 ${REPEAT} 次取最快`);
log('');
// 暖機
rows.slice(0, 20).forEach(row => Engine.runQuery(cards, Cond.soloQuery(Cond.tagAt(row.path.join(SEP), false))));
rows.slice(0, 20).forEach(row => EngineSim.runQuery(cards, Cond.soloQuery(Cond.tagAt(row.path.join(SEP), false))));

const base = timeRows(Engine, '下限:現行 Engine.runQuery(不帶新欄)', null);
log('');
const simA = timeRows(EngineSim, '上限 A:逐框加模擬比對(框表照現在去重;比完一律放行,命中數同下限)', makeTarget(1, true));
log('');
const times = Math.ceil(refs / frames.length);
const simB = timeRows(EngineSim, `上限 B:去重打破(逐框比 ${times} 次,約等於 ${refs} 筆框參照;一律放行)`, makeTarget(times, true));
log('');
const simR = timeRows(EngineSim, '參考:逐框模擬比對、照模擬結果擋(命中列變少,只當形狀參考)', makeTarget(1, false));
log('');
/* 視窗只要張數:目標卡表算一次,各列 predHitTable AND 目標卡表,逐卡查表數張數(不建命中句)。 */
function timeCountOnly(times, forcePass) {
  const fn = makeTarget(times, forcePass);
  const per = rows.map(() => Infinity);
  const counts = rows.map(() => 0);
  let wallMin = Infinity;
  for (let rep = 0; rep < REPEAT; rep++) {
    const wall0 = process.hrtime.bigint();
    const tgt = new Uint8Array(frames.length);
    frames.forEach((f, n) => { if (fn(f, n)) tgt[n] = 1; });
    rows.forEach((row, k) => {
      const t0 = process.hrtime.bigint();
      const table = EngineSim.predHitTable(Cond.tagAt(row.path.join(SEP), false).pred);
      for (let n = 0; n < table.length; n++) table[n] &= tgt[n];
      let count = 0;
      for (const c of cards) if (c.fr && EngineSim.predOnCard(c, table)) count++;
      counts[k] = count;
      const ms = Number(process.hrtime.bigint() - t0) / 1e6;
      if (ms < per[k]) per[k] = ms;
    });
    wallMin = Math.min(wallMin, Number(process.hrtime.bigint() - wall0) / 1e6);
  }
  return { per, wallMin, counts };
}
/* 再省:各列只掃自己詞元的框(引擎 fieldValues 已有同款索引),框 → 卡的反查表建一次,張數 = 命中框的卡聯集。 */
function timeLemmaIndex(times, forcePass) {
  const fn = makeTarget(times, forcePass);
  const lemmas = data.vocab.frame.lemmas;
  const t00 = process.hrtime.bigint();
  const byLemma = new Map();
  frames.forEach((f, n) => { (byLemma.get(f[0]) || byLemma.set(f[0], []).get(f[0])).push(n); });
  const inv = frames.map(() => []);
  cards.forEach((c, ci) => (c.fr || []).forEach(ids => ids.forEach(id => inv[id].push(ci))));
  const buildMs = Number(process.hrtime.bigint() - t00) / 1e6;
  const per = rows.map(() => Infinity);
  const counts = rows.map(() => 0);
  let wallMin = Infinity;
  for (let rep = 0; rep < REPEAT; rep++) {
    const wall0 = process.hrtime.bigint();
    const tgt = new Uint8Array(frames.length);
    frames.forEach((f, n) => { if (fn(f, n)) tgt[n] = 1; });
    const seen = new Uint32Array(cards.length);
    rows.forEach((row, k) => {
      const t0 = process.hrtime.bigint();
      const pred = Cond.tagAt(row.path.join(SEP), false).pred;
      const checks = EngineSim.frameChecks(pred, null);
      const stamp = rep * rows.length + k + 1;
      let count = 0;
      for (const lemma of [].concat(pred.詞元)) {
        for (const n of byLemma.get(lemmas.indexOf(lemma)) || []) {
          if (!tgt[n] || !checks.every(check => check(frames[n]))) continue;
          for (const ci of inv[n]) if (seen[ci] !== stamp) { seen[ci] = stamp; count++; }
        }
      }
      counts[k] = count;
      const ms = Number(process.hrtime.bigint() - t0) / 1e6;
      if (ms < per[k]) per[k] = ms;
    });
    wallMin = Math.min(wallMin, Number(process.hrtime.bigint() - wall0) / 1e6);
  }
  return { per, wallMin, counts, buildMs };
}
box.__target = null;
const lem = timeLemmaIndex(1, true);
log(`詞元索引 + 框→卡反查(索引建一次 ${lem.buildMs.toFixed(1)} ms;一律放行):逐列 中位數 ${median(lem.per).toFixed(3)} ms、最差 ${Math.max(...lem.per).toFixed(3)} ms、合計(含目標卡表)${lem.wallMin.toFixed(0)} ms(手機 ×4 ≈ ${(lem.wallMin * 4).toFixed(0)} ms);張數與下限 runQuery ${lem.counts.every((n, k) => n === base.counts[k]) ? '逐列相同' : '有不同'}`);
const cnt = timeCountOnly(1, true);
const same = cnt.counts.every((n, k) => n === base.counts[k]);
log(`只數張數(目標卡表一次 + 各列 AND + 逐卡查表;一律放行):逐列 中位數 ${median(cnt.per).toFixed(2)} ms、最差 ${Math.max(...cnt.per).toFixed(2)} ms、合計 ${cnt.wallMin.toFixed(0)} ms(手機 ×4 ≈ ${(cnt.wallMin * 4).toFixed(0)} ms);張數與下限 runQuery ${same ? '逐列相同' : '有不同'}`);
log(`捷徑:目標卡命中表全框算一次 A ${timeSharedTable(1).toFixed(2)} ms、B ${timeSharedTable(times).toFixed(2)} ms(之後各列只 AND 兩張表)`);
log(`每列平均:下限 ${(base.wallMin / rows.length).toFixed(2)} ms、A ${(simA.wallMin / rows.length).toFixed(2)} ms、B ${(simB.wallMin / rows.length).toFixed(2)} ms`);
log(`下限與 A、B 張數逐列相同:${base.counts.every((n, k) => n === simA.counts[k] && n === simB.counts[k])};參考變體有命中 ${simR.counts.filter(Boolean).length} 列`);

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, lines.join('\n') + '\n', 'utf8');
