// 舊網址比對(summon-procedure 票 06):交件前 main 產生的網址,在本分支讀進來查到的卡與命中句是否和 main 相同。
// 接縫:前端沙箱 script/web/frontend_harness.js(依 index.html 順序載入真前端碼與真 data.js)——兩邊各載自己的 harness 與 web/,
// 對同一批網址跑 Hash.parse → Cond.toQuery → Engine.runQuery,逐網址比卡片密碼與每張卡的命中句索引,另比 Hash.canon。
// 網址由 main 那一份產生(main 的 Hash.stringify),所以是 main 上真的會出現的網址:目錄每個具名查詢 × 位置寫法
// (只寫路徑=預設位置、位置:代價~效果~條件、位置:條件、排除),再加手寫的欄位對與 OR 區例子。
// 用法:node .scratch/summon-procedure/tools/old_urls.js <main 的匯出目錄>
//   匯出目錄:git archive --format=tar -o main_web.tar main web script/web/frontend_harness.js,解到該目錄。
// 結果寫 tools/results/old_urls.txt(也印 stdout);有不同的網址照列,有不同時 exit 1。
'use strict';
const path = require('path');
const fs = require('fs');

const OUT = path.join(__dirname, 'results', 'old_urls.txt');
const BRANCH = path.resolve(__dirname, '..', '..', '..');
const POSITION_VARIANTS = [
  { label: '只寫路徑', edit: null },
  { label: '位置:代價~效果~條件', edit: [['代價', 'on'], ['條件', 'on']] },
  { label: '位置:條件', edit: [['條件', 'on'], ['效果', 'off']] },
];
const HAND_WRITTEN = [
  'act=' + ['詞元:破壊', '位置:代價~效果', '極性:肯定~可能', '動作對象:非此卡'].join(';'),
  'act=' + ['詞元:除外', '位置:效果~條件', '極性:肯定~可能'].join(';'),
  'act=' + ['詞元:リリース', '位置:代價~效果~條件', '極性:肯定~可能'].join(';'),
  'act=' + ['詞元:送る', '位置:代價', '極性:肯定~可能', '目的:墓地'].join(';'),
  'act=' + ['詞元:除外', '極性:肯定~可能'].join(';'),
  'actOr=' + ['詞元:破壊', '位置:代價~效果', '極性:肯定~可能'].join(';') + ',' + ['詞元:除外', '位置:條件', '極性:肯定~可能'].join(';'),
  'act=-' + ['詞元:除外', '位置:代價~效果~條件', '極性:肯定~可能'].join(';'),
];

const KNOWN = [{ lemma: '儀式召喚', position: '條件', card: 32354768, why: '票 05 抽取修正:32354768 ② 新增條件位 儀式召喚 框' }];

const lines = [];
const log = (...a) => { const s = a.join(' '); lines.push(s); console.log(s); };

function side(root) {
  const harness = require(path.join(root, 'script', 'web', 'frontend_harness.js'));
  const data = harness.realData();
  if (!data) throw new Error(`${root} 沒有 web/data.js`);
  const box = harness.load(data);
  const run = hash => {
    const st = harness.parseHash(box, hash);
    if (!st.cond) return { canon: harness.canonHash(box, hash), cards: new Map(), positions: '(沒有標籤)', tags: 0 };
    const q = harness.cond(box, 'toQuery', st.cond, st.q);
    const tags = harness.cond(box, 'tags', st.cond);
    const cards = harness.search(box, q);
    return { canon: harness.canonHash(box, hash), cards: new Map(cards.map(e => [e.id, (e.rows || []).join(',')])),
      positions: tags.map(t => [].concat(t.pred.位置 || []).join('~')).join(' / '), tags: tags.length };
  };
  return { harness, box, run };
}

function encodePairs(text) {
  return text.split(/([=,;])/).map(part => (/^[=,;]$/.test(part) ? part : part.split(':').map(s => s.split('~')
    .map(v => (v.startsWith('-') ? '-' + encodeURIComponent(v.slice(1)) : encodeURIComponent(v))).join('~')).join(':'))).join('');
}

function mainUrls(main) {
  const { harness, box } = main;
  const rc = (fn, ...args) => harness.cond(box, fn, ...args);
  const rows = box.VOCAB.catalog.filter(r => r.predicate);
  const urls = [];
  for (const row of rows) {
    const key = row.path.join('›');
    for (const v of POSITION_VARIANTS) {
      let tag = rc('tagAt', key, false);
      if (v.edit) {
        const has = p => [].concat(tag.pred.位置).includes(p);
        for (const [pos, want] of v.edit) if (has(pos) !== (want === 'on')) tag = rc('toggleValue', tag, '位置', pos);
      }
      urls.push({ from: `${row.name}(${v.label})`, hash: harness.hash(box, { q: {}, cond: rc('add', rc('empty'), tag), sort: {} }) });
    }
    urls.push({ from: `${row.name}(排除)`, hash: harness.hash(box, { q: {}, cond: rc('add', rc('empty'), rc('tagAt', key, true)), sort: {} }) });
  }
  HAND_WRITTEN.forEach(h => urls.push({ from: '手寫', hash: encodePairs(h) }));
  return { urls, rows: rows.length };
}

function compare(a, b) {
  const plus = [...b.cards.keys()].filter(id => !a.cards.has(id));
  const minus = [...a.cards.keys()].filter(id => !b.cards.has(id));
  const rows = [...a.cards.keys()].filter(id => b.cards.has(id) && a.cards.get(id) !== b.cards.get(id))
    .map(id => `${id} 命中句 [${a.cards.get(id)}] → [${b.cards.get(id)}]`);
  return { plus, minus, rows, canon: a.canon !== b.canon, positions: a.positions !== b.positions };
}

function main() {
  const mainRoot = process.argv[2];
  if (!mainRoot) { console.error('用法:node old_urls.js <main 的匯出目錄>'); process.exitCode = 2; return; }
  const m = side(path.resolve(mainRoot));
  const br = side(BRANCH);
  const { urls, rows } = mainUrls(m);
  log(`main ${path.resolve(mainRoot)};分支 ${BRANCH}`);
  log(`網址 ${urls.length} 條(目錄具名查詢 ${rows} 列 × 位置寫法 ${POSITION_VARIANTS.length} 種 + 排除 1 種,手寫 ${HAND_WRITTEN.length} 條)`);
  log(`含位置參數(欄位對寫法)的 ${urls.filter(u => decodeURIComponent(u.hash).includes('位置:')).length} 條`);
  let same = 0, zero = 0;
  const diffs = [];
  for (const u of urls) {
    const a = m.run(u.hash), b = br.run(u.hash);
    if (!a.cards.size) zero++;
    if (!a.tags) log(`  main 讀不出標籤:${u.from} ${decodeURIComponent(u.hash)}`);
    const d = compare(a, b);
    if (!d.plus.length && !d.minus.length && !d.rows.length && !d.canon && !d.positions) { same++; continue; }
    diffs.push({ u, a, b, d });
  }
  log(`main 查到 0 張的 ${zero} 條(多是該列在條件位沒有框,照樣比)`);
  log(`卡片密碼、命中句、正規網址、讀進來的位置都相同 ${same} 條;不同 ${diffs.length} 條`);
  let unexplained = 0;
  for (const { u, a, b, d } of diffs) {
    const text = decodeURIComponent(u.hash);
    const known = KNOWN.find(k => text.includes(`詞元:${k.lemma};`) && b.positions.split('~').includes(k.position)
      && d.plus.length === 1 && d.plus[0] === k.card && !d.minus.length && !d.rows.length && !d.canon && !d.positions);
    if (!known) unexplained++;
    log(`\n-- ${u.from}:${text}`);
    log(`  main ${a.cards.size} 張(位置 ${a.positions})→ 分支 ${b.cards.size} 張(位置 ${b.positions})`);
    if (d.plus.length) log(`  分支多 ${d.plus.join('、')}`);
    if (d.minus.length) log(`  分支少 ${d.minus.join('、')}`);
    d.rows.forEach(r => log(`  ${r}`));
    if (d.canon) log(`  正規網址 ${decodeURIComponent(a.canon)} → ${decodeURIComponent(b.canon)}`);
    log(`  成因:${known ? known.why : '沒有說明'}`);
  }
  log(`\n沒有說明的不同 ${unexplained} 條`);
  process.exitCode = unexplained ? 1 : 0;
}

try { main(); } finally { fs.writeFileSync(OUT, lines.join('\n') + '\n'); }
