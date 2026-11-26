'use strict';
/* 第 1 份清單:.scratch/action-search-web/manual-acceptance.md
   「動作、從、到」3 的對手改 83 張、「被動作的卡」8 的中文黑魔導改 1,260 張(第 2 份清單開頭的說明)。 */

const fs = require('node:fs');
const path = require('node:path');
const { fmt } = require('./lib');

const ROOT = path.join(__dirname, '..', '..', '..');
const L = 'web';

const SHOWN14 = ['特殊召喚', '破壞', '送墓', '除外', '加入手牌', '性質變更', '通常召喚', '召喚', '返回', '解放',
                 '攻擊', '傷害', '捨棄', '發動'];
const LABELS = ['動作', '從哪裡', '到哪裡', '被動作的卡', '這個動作是', '極性', '誰做的', '落在誰身上', '因為什麼'];
const HINT = '找卡文裡有這個動作的卡;和其他條件同時成立才算';

/* 張數與無法確認一起比;expUnsure 為 undefined 時只比張數 */
function countCheck(rec, name, c, n, unsure) {
  rec.eq(`${name} 張數`, fmt(n), fmt(c.n));
  if (unsure !== undefined) rec.eq(`${name} 無法確認`, fmt(unsure), fmt(c.unsure));
}

function has(rec, set, id, name, want) {
  rec.eq(`${name}(${id})${want ? '在' : '不在'}`, want ? '在' : '不在', set.has(id) ? '在' : '不在');
}

/* ---------------- 載入時機 ---------------- */

async function loading(S, run) {
  const { rec } = S;
  let blueEyes = null;

  await run('載入時機 1', '開頁,卡名填「青眼」按搜尋', 'Network 沒有 action-data.js;結果和改版前一樣', async site => {
    await site.open();
    await site.page.fill('#fName', '青眼');
    const c = await site.search();
    blueEyes = c.n;
    S.blueEyes = c.n;
    rec.eq('action-data.js 請求數', '0', String(site.actionRequests().length));
    rec.check('有結果', '> 0 張', `${fmt(c.n)} 張`, c.n > 0);
    rec.na('結果和改版前一樣', '沒有改版前的網站可對照;只記張數');
  }, { keep: true });

  await run('載入時機 2', '展開「動作搜尋」', 'Network 出現 action-data.js;短暫顯示「動作索引載入中…」,接著出現動作詞按鈕', async site => {
    const before = site.actionRequests().length;
    const status = await site.page.evaluate(() => {
      document.getElementById('actionHead').click();
      return document.getElementById('actionStatus').textContent;
    });
    await site.page.waitForSelector('#actionFields button[data-word]', { timeout: 30000 });
    rec.eq('展開當下的狀態行', '動作索引載入中…', status);
    rec.eq('展開後 action-data.js 請求數', '1', String(site.actionRequests().length - before));
    const n = await site.page.$$eval('#actionFields button[data-word]', b => b.length);
    rec.check('出現動作詞按鈕', '> 0 顆', `${n} 顆`, n > 0);
    const st = await site.page.$eval('#actionStatus', e => (e.hidden ? '' : e.textContent));
    rec.eq('載完後狀態行', '(隱藏)', st || '(隱藏)');
  }, { keep: true });

  await run('載入時機 3', '重新整理(區塊回到收起),展開後立刻點「破壞」按搜尋', '結果區先顯示載入中,載完自動出 2,200 張', async site => {
    await site.page.reload();
    await site.page.waitForFunction(() => document.getElementById('dbInfo').textContent.length > 0);
    rec.eq('重新整理後區塊收起', 'false', await site.page.getAttribute('#actionHead', 'aria-expanded'));
    await site.page.evaluate(() => { window.__obs.results = []; });
    await site.page.click('#actionHead');
    await site.page.waitForSelector('#actionFields button[data-word="破壞"]', { timeout: 30000 });
    await site.page.click('#actionFields button[data-word="破壞"]');
    await site.page.fill('#fName', '');
    const c = await site.search();
    countCheck(rec, '破壞', c, 2200, 978);
    const seen = await site.page.evaluate(() => window.__obs.results.some(t => /動作索引載入中/.test(t)));
    rec.note(`結果區有沒有出現過「動作索引載入中」:${seen ? '有' : '沒有'}`);
    rec.na('結果區先顯示「動作索引載入中… 載完會自動出結果」',
      '動作詞按鈕要等索引載完才畫出來,載完前點不到「破壞」;載完前按搜尋時沒有動作條件,不會進載入中。'
      + '這個畫面改在「網址與瀏覽紀錄 3」(帶動作條件重新整理)驗');
  }, { keep: true });

  await run('載入時機 4', '收起再展開區塊', 'Network 不再下載 action-data.js', async site => {
    const before = site.actionRequests().length;
    await site.page.click('#actionHead');
    rec.eq('收起', 'false', await site.page.getAttribute('#actionHead', 'aria-expanded'));
    await site.page.click('#actionHead');
    await site.page.waitForSelector('#actionFields button[data-word]');
    await site.page.waitForTimeout(500);
    rec.eq('收起再展開的 action-data.js 新請求', '0', String(site.actionRequests().length - before));
  });

  await run('載入時機 5', '把 web/action-data.js 暫時改名,重新整理、展開區塊;再搜卡名「青眼」;看完改回',
    '區塊裡有載入失敗的說明;卡名「青眼」照常能搜', async site => {
    const src = path.join(ROOT, 'web', 'action-data.js');
    const tmp = src + '.acceptance-renamed';
    fs.renameSync(src, tmp);
    S.renamed = { src, tmp };
    try {
      await site.open();
      await site.page.click('#actionHead');
      await site.page.waitForFunction(() => /載入失敗/.test(document.getElementById('actionStatus').textContent),
        null, { timeout: 15000 }).catch(() => {});
      const st = await site.page.$eval('#actionStatus', e => (e.hidden ? '' : e.textContent));
      rec.check('區塊裡的載入失敗說明', '含「載入失敗」', st || '(空)', /載入失敗/.test(st));
      const shot = await site.shot('web-loading5-failed', { locator: site.page.locator('#actionBox') });
      await site.page.fill('#fName', '青眼');
      const c = await site.search();
      rec.eq('卡名「青眼」張數(同第 1 步)', fmt(S.blueEyes), fmt(c.n));
      rec.note(`失敗說明:${st}`);
      void shot;
    } finally {
      fs.renameSync(tmp, src);
      S.renamed = null;
    }
    rec.eq('action-data.js 已改回', 'true', String(fs.existsSync(src)));
  }, { expectLoadFail: true });
}

/* ---------------- 版面與文字 ---------------- */

async function layoutText(S, run) {
  const { rec } = S;

  await run('版面與文字 1', '展開「動作搜尋」,讀由上而下的標題', '說明、動作、從哪裡、到哪裡、被動作的卡、這個動作是、極性、誰做的、落在誰身上、因為什麼、含不限定的', async site => {
    await site.open();
    await site.openAction();
    const r = await site.page.evaluate(() => {
      const body = document.getElementById('actionBody');
      const hint = body.querySelector(':scope > p.action-hint').textContent;
      const labels = [...body.querySelectorAll('#actionFields > .group-label')].map(e => e.textContent);
      const last = body.querySelector('#actionFields > label.mat-toggle');
      const lastIsLast = !!last && body.querySelector('#actionFields').lastElementChild === last;
      return { hint, labels, last: last ? last.textContent.trim() : '', lastIsLast };
    });
    rec.eq('說明', HINT, r.hint);
    rec.eq('標題順序', LABELS.join('、'), r.labels.join('、'));
    rec.check('最後是「含不限定的」', '含不限定的(最後一項)', `${r.last}${r.lastIsLast ? '(最後一項)' : '(不是最後)'}`,
      r.last === '含不限定的' && r.lastIsLast);
    const shot = await site.shot('web-layout1-panel', { locator: site.page.locator('#actionBox') });
    rec.look('動作搜尋區塊的文字與擺法是否順眼(1400 寬)', shot);
  });

  await run('版面與文字 2', '數動作詞;按「更多」;選一個「更多」裡的詞再收起', '直接列 14 個(指定那 14 個);更多後共 45 個;已選的詞收起後照樣顯示', async site => {
    await site.open();
    await site.openAction();
    const shown = await site.page.$$eval('#actionFields button[data-word]', b => b.map(x => x.dataset.word));
    rec.eq('直接列出', SHOWN14.join('、'), shown.join('、'));
    const label = await site.page.$eval('#actionFields button[data-more]', b => b.textContent);
    rec.eq('更多鈕', '更多(共 45 個)', label);
    await site.page.click('#actionFields button[data-more]');
    const all = await site.page.$$eval('#actionFields button[data-word]', b => b.map(x => x.dataset.word));
    rec.eq('按更多後共', '45', String(all.length));
    const pick = all.find(w => !SHOWN14.includes(w));
    await site.page.click(`#actionFields button[data-word="${pick}"]`);
    await site.page.click('#actionFields button[data-more]');
    const after = await site.page.$$eval('#actionFields button[data-word]', b => b.map(x => `${x.dataset.word}:${x.dataset.st}`));
    rec.check(`收起後「${pick}」照樣顯示且選取`, `${pick}:in`, after.find(x => x.startsWith(pick + ':')) || '(不見)',
      after.includes(`${pick}:in`));
    rec.eq('收起後按鈕數', '15', String(after.length));
  });

  await run('版面與文字 3', '看「被動作的卡」底下的說明', '有一行「這裡篩的是被動作的卡,不是有這個效果的卡」', async site => {
    await site.open();
    await site.openAction();
    const t = await site.page.evaluate(() => {
      const lab = [...document.querySelectorAll('#actionFields > .group-label')].find(e => e.textContent === '被動作的卡');
      const n = lab && lab.nextElementSibling;
      return n ? n.textContent : '';
    });
    rec.eq('緊接標題下的說明', '這裡篩的是被動作的卡,不是有這個效果的卡', t);
    await site.target('cond');
    const shot = await site.shot('web-layout3-target', { locator: site.page.locator('#sidebar') });
    rec.look('看不看得出「被動作的卡」和側欄上方的種族等條件篩的是不同的卡(故事 31)', shot);
  });

  await run('版面與文字 4', '看「含不限定的」的滑鼠提示', '有提示,說明放寬的是沒寫誰、沒寫原因的段', async site => {
    await site.open();
    await site.openAction();
    const title = await site.page.$eval('#actionFields label.mat-toggle', l => l.title);
    rec.check('提示說到沒寫是誰', '含「沒寫是誰」', title, /沒寫是誰/.test(title));
    rec.check('提示說到沒寫原因', '含「沒寫原因」', title, /沒寫原因/.test(title));
  });

  await run('版面與文字 5', '看「因為什麼」的種類選項', '只有戰鬥、效果、作為素材、召喚方式、方法、規則', async site => {
    await site.open();
    await site.openAction();
    const opts = await site.page.$$eval('#actionFields select[data-cause-kind] option', o => o.map(x => x.textContent).slice(1));
    const want = ['戰鬥', '效果', '作為素材', '召喚方式', '方法', '規則'];
    rec.check('選項(不含「不限」)', want.join('、'), opts.join('、'),
      opts.length === want.length && want.every(w => opts.includes(w)));
    rec.check('沒有戰鬥或效果、戰鬥以外', '沒有', opts.filter(o => /或|以外/.test(o)).join('、') || '沒有',
      !opts.some(o => /或|以外/.test(o)));
  });
}

/* ---------------- 動作、從、到 ---------------- */

async function fromTo(S, run) {
  const { rec } = S;

  await run('動作、從、到 1', '選「破壞」搜尋;試排序、分頁、每頁筆數;點「無法確認」那行', '2,200 張;清單無分組無標記;排序分頁每頁筆數照常;下方一行「另有 978 張無法確認」點了沒反應', async site => {
    await site.open();
    await site.openAction();
    await site.words(['破壞']);
    const c = await site.search();
    countCheck(rec, '破壞', c, 2200, 978);
    rec.eq('無法確認那行', '另有 978 張無法確認', c.unsureText);
    const r = await site.page.evaluate(() => {
      const kids = [...document.getElementById('results').children];
      const u = document.getElementById('unsureInfo');
      return {
        allCards: kids.every(k => k.matches('article.card')),
        n: kids.length,
        badges: document.querySelectorAll('#results .eff-hit').length,
        order: u.previousElementSibling.id + ' > unsureInfo > ' + u.nextElementSibling.id,
      };
    });
    rec.check('清單只有卡片(無分組)', '全是卡片', `${r.n} 個子元素,全是卡片=${r.allCards}`, r.allCards && r.n === 100);
    rec.eq('沒有標記(底色上的標籤)', '0', String(r.badges));
    rec.eq('那行的位置', 'results > unsureInfo > pagerBottom', r.order);
    // 點了沒反應
    const snapNow = () => site.page.evaluate(() => ({
      h: history.length, url: location.href, y: Math.round(window.scrollY),
      info: document.getElementById('resultInfo').textContent,
      unsure: document.getElementById('unsureInfo').textContent,
      ids: [...document.querySelectorAll('#results article.card')].map(a => a.dataset.cid).join(','),
    }));
    const before = await snapNow();
    await site.page.click('#unsureInfo');
    await site.page.waitForTimeout(300);
    const after = await snapNow();
    after.y = before.y; // 點擊時 Playwright 自己會捲到那一行,捲動位置不算
    rec.check('點「無法確認」沒反應', '結果清單、張數、網址、瀏覽紀錄不變', JSON.stringify(before) === JSON.stringify(after) ? '都沒變' : `變了:${after.info} ${after.url} h=${after.h}`, JSON.stringify(before) === JSON.stringify(after));
    // 排序
    await site.page.selectOption('#sortKey', 'atk');
    const atks = await site.page.$$eval('#results article.card .meta-lines', ls => ls.map(l => {
      const m = l.textContent.match(/攻(\d+|\?)/); return m ? (m[1] === '?' ? -1 : +m[1]) : null; }).filter(v => v != null));
    const desc = atks.every((v, i) => i === 0 || atks[i - 1] >= v);
    const c2 = await site.counts();
    rec.check('排序改攻擊力:張數不變、攻擊力由高到低', '2,200 張、降序', `${fmt(c2.n)} 張、${desc ? '降序' : '不是降序'}(前幾張 ${atks.slice(0, 5).join(',')})`, c2.n === 2200 && desc);
    // 分頁
    const firstP1 = await site.page.$eval('#results article.card', a => a.dataset.cid);
    await site.page.click('#pagerTop button[data-p="2"]');
    const info2 = await site.page.$eval('#resultInfo', e => e.textContent);
    const firstP2 = await site.page.$eval('#results article.card', a => a.dataset.cid);
    rec.check('分頁到第 2 頁', '第 2/22 頁、清單換了', `${info2}、第一張 ${firstP1}→${firstP2}`, /第 2\/22 頁/.test(info2) && firstP1 !== firstP2);
    // 每頁筆數
    await site.page.selectOption('#perPage', '50');
    const info3 = await site.page.$eval('#resultInfo', e => e.textContent);
    const n3 = await site.page.$$eval('#results article.card', a => a.length);
    rec.check('每頁 50 筆', '第 1/44 頁、50 張', `${info3}、${n3} 張`, /第 1\/44 頁/.test(info3) && n3 === 50);
    await site.page.selectOption('#perPage', '100');
  });

  await run('動作、從、到 2', '再選「除外」搜尋;再點大類「怪獸」、種族「龍族」搜尋', '18 張;5 張', async site => {
    await site.open();
    await site.openAction();
    await site.words(['破壞', '除外']);
    countCheck(rec, '破壞+除外', await site.search(), 18, 54);
    await site.sideTri('cat', 'm', 'in');
    await site.sideTri('race', 'dragon', 'in');
    countCheck(rec, '破壞+除外,怪獸、龍族', await site.search(), 5, 0);
  });

  await run('動作、從、到 3', '清除,「特殊召喚」從「墓地」搜尋;方再選「對手」;看幾張卡文', '1,647 張;對手 83 張(第 2 份清單更新,原 37);卡文是從對手墓地特殊召喚', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['特殊召喚']);
    await site.zone('from', '墓地', '');
    countCheck(rec, '特殊召喚 從墓地', await site.search(), 1647, 2638);
    await site.zone('from', '墓地', '對手');
    countCheck(rec, '特殊召喚 從對手的墓地', await site.search(), 83, 2989);
    const hits = await site.page.$$eval('#results article.card', as => as.slice(0, 5).map(a => ({
      name: a.querySelector('.card-name').textContent,
      hit: [...a.querySelectorAll('.card-text:not(.og-text) .eff.hit')].map(p => p.textContent.replace(/\s+/g, ' ').trim()).join(' / '),
    })));
    hits.forEach(h => rec.note(`${h.name}:${h.hit}`));
    const ok = hits.every(h => /墓地/.test(h.hit) && /對手|雙方|任一方/.test(h.hit) && /特殊召喚/.test(h.hit));
    rec.check('前 5 張底色句含「墓地」「特殊召喚」與對手/雙方', '5 張都含', `${hits.filter(h => /墓地/.test(h.hit) && /對手|雙方|任一方/.test(h.hit) && /特殊召喚/.test(h.hit)).length} 張含`, ok);
    const shot = await site.shot('web-fromto3-opp-gy', { locator: site.page.locator('#results article.card').first() });
    rec.look('從對手墓地特殊召喚:第一張卡的底色句是否真的從對手墓地特殊召喚(前 5 張的句子見 result.md 該步備註)', shot);
  });

  await run('動作、從、到 4', '清除,「送墓」到「墓地」;改「加入手牌」到「手牌」', '1,417 張;2,067 張', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['送墓']);
    await site.zone('to', '墓地', '');
    countCheck(rec, '送墓 到墓地', await site.search(), 1417, 713);
    await site.words(['加入手牌']);
    await site.zone('to', '手牌', '');
    countCheck(rec, '加入手牌 到手牌', await site.search(), 2067, 495);
  });

  await run('動作、從、到 5', '看區域與方的下拉', '區域 14 個,常用的在前(場上、墓地、手牌、牌組、除外…);方只有不限哪一方、我方、對手', async site => {
    await site.open();
    await site.openAction();
    for (const key of ['from', 'to']) {
      const zones = await site.page.$$eval(`#actionFields select[data-zone="${key}"] option`, o => o.map(x => x.textContent).slice(1));
      rec.eq(`${key} 區域數`, '14', String(zones.length));
      const head = zones.slice(0, 5);
      const common = ['場上', '墓地', '手牌', '牌組', '除外'];
      rec.check(`${key} 前 5 個是常用區域`, common.join('、') + '(順序不拘)', zones.join('、'),
        common.every(z => head.includes(z)));
      const sides = await site.page.$$eval(`#actionFields select[data-side="${key}"] option`, o => o.map(x => x.textContent));
      rec.eq(`${key} 方的選項`, '不限哪一方、我方、對手', sides.join('、'));
    }
  });
}

/* ---------------- 段類別與極性 ---------------- */

async function kindsPol(S, run) {
  const { rec } = S;

  await run('段類別與極性 1', '清除,選「破壞」;看預設;再勾「觸發條件」搜尋', '預設勾效果、代價,極性會做;3,277 張', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    const st = await site.page.evaluate(() => ({
      eff: document.querySelector('#actionFields input[data-kind="eff"]').checked,
      cost: document.querySelector('#actionFields input[data-kind="cost"]').checked,
      cond: document.querySelector('#actionFields input[data-kind="cond"]').checked,
      pol: document.querySelector('#actionFields button[data-pol][data-st="in"]').dataset.pol,
    }));
    rec.eq('預設勾選', '效果✓ 代價✓ 觸發條件✗', `效果${st.eff ? '✓' : '✗'} 代價${st.cost ? '✓' : '✗'} 觸發條件${st.cond ? '✓' : '✗'}`);
    rec.eq('預設極性', 'do(會做)', `${st.pol}(${st.pol === 'do' ? '會做' : '?'})`);
    const base = await site.idSet();
    await site.kinds(['eff', 'cost', 'cond']);
    const c = await site.search();
    countCheck(rec, '破壞 勾觸發條件', c, 3277, 1100);
    const extra = [...(await site.idSet())].filter(id => !base.has(id)).length;
    rec.check('多出原本沒有的卡', '> 0 張', `${fmt(extra)} 張`, extra > 0);
  });

  await run('段類別與極性 2', '取消效果、取消代價;搜尋', '剩觸發條件時它不能取消;1,389 張', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.kinds(['cond']);
    const dis = await site.page.$eval('#actionFields input[data-kind="cond"]', e => e.disabled);
    rec.eq('觸發條件停用(不能取消)', 'true', String(dis));
    countCheck(rec, '只勾觸發條件 破壞', await site.search(), 1389, 367);
  });

  await run('段類別與極性 3', '勾回效果代價、取消觸發條件,「破壞」極性「抗性」', '621 張,縛神塚在', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.kinds(['eff', 'cost', 'cond']);
    await site.kinds(['eff', 'cost']);
    await site.pol('resist');
    countCheck(rec, '破壞 抗性', await site.search(), 621, 107);
    has(rec, await site.idSet(), 269012, '縛神塚', true);
  });

  await run('段類別與極性 4', '改「通常召喚」、極性「限制」', '421 張,芬里爾在', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['通常召喚']);
    await site.pol('limit');
    countCheck(rec, '通常召喚 限制', await site.search(), 421, 62);
    has(rec, await site.idSet(), 218704, '芬里爾', true);
  });
}

/* ---------------- 被動作的卡 ---------------- */

async function target(S, run) {
  const { rec } = S;

  await run('被動作的卡 1', '「破壞」抗性、這張卡自己、側欄種族龍族;再改不指定', '43 張(另有 6);天風龍女在、星塵零不在;不指定 60 張', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.pol('resist');
    await site.target('this_card');
    await site.sideTri('cat', 'm', 'in');
    await site.sideTri('race', 'dragon', 'in');
    countCheck(rec, '破壞 抗性 這張卡自己 龍族', await site.search(), 43, 6);
    const ids = await site.idSet();
    has(rec, ids, 15848542, '龍女僕 天風龍女', true);
    has(rec, ids, 26268488, '聖珖神龍 星塵零', false);
    await site.target('none');
    countCheck(rec, '破壞 抗性 不指定 龍族', await site.search(), 60, 5);
  });

  await run('被動作的卡 2', '改「指定一張卡」,逐字輸入「ブラック・マジシャン」與「黑魔導」', '出現輸入框;建議清單名字短的在前(黑魔導最前,接著龍騎士 黑魔導、黑魔導女孩…);打字時游標不跳走', async site => {
    await site.open();
    await site.openAction();
    await site.words(['破壞']);
    await site.target('card');
    rec.eq('出現輸入框', '1', String(await site.page.locator('#actionCardInput').count()));
    for (const text of ['ブラック・マジシャン', '黑魔導']) {
      const bad = await site.typeCheck('#actionCardInput', text);
      rec.check(`逐字打「${text}」游標與值`, '每個字都對', bad.join(';') || '每個字都對', !bad.length);
      const sug = await site.page.$$eval('#actionSuggest button', b => b.map(x => ({ id: +x.dataset.pick, n: x.childNodes[0].textContent.trim() })));
      rec.note(`「${text}」建議清單:${sug.map(s => s.n).join('、')}`);
      rec.eq(`「${text}」建議第一個`, '黑魔導(46986414)', `${sug[0] && sug[0].n}(${sug[0] && sug[0].id})`);
      if (text === 'ブラック・マジシャン') {
        // 清單寫的「接著龍騎士 黑魔導、黑魔導女孩」是日文輸入時的順序(比對到的是日文名的長度)
        rec.eq(`「${text}」接著兩個`, '龍騎士 黑魔導、黑魔導女孩', sug.slice(1, 3).map(s => s.n).join('、'));
      } else {
        const lens = sug.map(s => s.n.length);
        rec.check(`「${text}」名字短的在前`, '中文名長度不遞減', lens.join(','), lens.every((v, i) => !i || lens[i - 1] <= v));
      }
    }
  });

  await run('被動作的卡 3', '點「黑魔導」;清掉側欄種族,只留「破壞」搜尋;點「黑魔導 ×」', '換成一顆「黑魔導 ×」;1,242 張;可以取消、重新輸入', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.sideTri('cat', 'm', 'in');
    await site.sideTri('race', 'dragon', 'in');
    await site.target('card');
    await site.page.fill('#actionCardInput', '黑魔導');
    await site.page.click('#actionSuggest button[data-pick="46986414"]');
    const chip = await site.page.$eval('#actionFields button[data-unpick]', b => b.textContent.trim()).catch(() => '');
    rec.eq('換成的按鈕', '黑魔導 ×', chip);
    rec.eq('輸入框消失', '0', String(await site.page.locator('#actionCardInput').count()));
    await site.sideTri('race', 'dragon', '');
    await site.sideTri('cat', 'm', '');
    countCheck(rec, '破壞 指定 黑魔導', await site.search(), 1242, 1325);
    await site.page.click('#actionFields button[data-unpick]');
    rec.eq('取消後輸入框回來', '1', String(await site.page.locator('#actionCardInput').count()));
    await site.page.fill('#actionCardInput', '黑魔');
    const n = await site.page.locator('#actionSuggest button').count();
    rec.check('可重新輸入(出現建議)', '> 0', String(n), n > 0);
  });

  await run('被動作的卡 4', '改「給條件」', '出現說明、大類/屬性/種族三列(和側欄同名同序)、等級兩個數字框、字段、卡名包含;種族 26 顆', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.target('cond');
    const r = await site.page.evaluate(() => {
      const f = document.getElementById('actionFields');
      const row = k => [...f.querySelectorAll(`button[data-gkey="${k}"]`)].map(b => b.textContent.trim());
      const side = k => {
        const ax = document.querySelector(`#critParams .axis[data-axis="${k}"]`);
        return [...ax.querySelectorAll('.tri')].filter(b => b.closest('.axis') === ax).map(b => b.textContent.trim());
      };
      return {
        hint: [...f.querySelectorAll('p.action-hint')].map(p => p.textContent),
        cat: row('cat'), attr: row('attr'), race: row('race'),
        sCat: side('cat'), sAttr: side('attr'), sRace: side('race'),
        lv: f.querySelectorAll('input[data-glv]').length,
        set: !!f.querySelector('#actionSetInput'),
        name: !!f.querySelector('input[data-gname]'),
        labels: [...f.querySelectorAll('.group-label')].map(e => e.textContent),
      };
    });
    rec.check('說明', '被動作的卡要符合下面填的全部條件', r.hint.includes('被動作的卡要符合下面填的全部條件') ? '有' : '沒有', r.hint.includes('被動作的卡要符合下面填的全部條件'));
    rec.eq('大類和側欄同名同序', r.sCat.join('、'), r.cat.join('、'));
    rec.eq('屬性和側欄同名同序', r.sAttr.join('、'), r.attr.join('、'));
    rec.eq('種族和側欄同名同序', r.sRace.join('、'), r.race.join('、'));
    rec.eq('種族按鈕數', '26', String(r.race.length));
    rec.eq('等級數字框', '2', String(r.lv));
    rec.check('字段輸入框、卡名包含輸入框', '都有', `字段${r.set ? '有' : '無'}、卡名包含${r.name ? '有' : '無'}`, r.set && r.name);
    const shot = await site.shot('web-target4-given-1400', { locator: site.page.locator('#actionBox') });
    rec.look('給條件:種族 26 顆按鈕在側欄(1400 寬,側欄 400px)的樣子', shot);
  });

  await run('被動作的卡 5', '「特殊召喚」、給條件種族「龍族」搜尋;再點一次「龍族」取消', '1,178 張,喬巴姆裝甲龍在;摺疊鈕的條件數少一', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['特殊召喚']);
    await site.target('cond');
    await site.givenBtn('race', '龍族');
    const ac1 = await site.page.$eval('#actionCount', e => e.textContent);
    countCheck(rec, '特殊召喚 給條件 龍族', await site.search(), 1178, 2718);
    const f1 = await site.page.$eval('#btnFilters', e => e.textContent);
    has(rec, await site.idSet(), 27352108, '喬巴姆裝甲龍', true);
    await site.givenBtn('race', '龍族');
    const ac2 = await site.page.$eval('#actionCount', e => e.textContent);
    rec.eq('動作搜尋標題旁的條件數(即時)', `${+ac1 - 1}`, ac2 || '0');
    await site.searchOnly();
    const f2 = await site.page.$eval('#btnFilters', e => e.textContent);
    const n = t => +((t.match(/(\d+) 項/) || [0, 0])[1]);
    rec.eq('摺疊鈕「篩選條件・N 項」少一', `${f1} → 篩選條件・${n(f1) - 1} 項`, `${f1} → ${f2}`);
  });

  await run('被動作的卡 6', '等級下限 7 上限空白搜尋;再上限 4 下限清空搜尋(逐字輸入)', '結果跟著變;打字時游標不跳走', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['特殊召喚']);
    await site.target('cond');
    const c0 = await site.search();
    let bad = await site.typeCheck('#actionFields input[data-glv="lvMin"]', '7');
    const c1 = await site.search();
    bad = bad.concat(await site.typeCheck('#actionFields input[data-glv="lvMax"]', '4'));
    await site.page.fill('#actionFields input[data-glv="lvMin"]', '');
    const c2 = await site.search();
    rec.note(`不給條件 ${fmt(c0.n)}、等級≥7 ${fmt(c1.n)}、等級≤4 ${fmt(c2.n)}(票 13 當時 ≥7 是 2,271)`);
    rec.check('結果跟著變', '三個張數各不相同', `${fmt(c0.n)} / ${fmt(c1.n)} / ${fmt(c2.n)}`, c0.n !== c1.n && c1.n !== c2.n && c0.n !== c2.n);
    rec.check('打字時值與焦點不跳(數字框沒有游標位置可讀,只比值與焦點)', '每個字都對', bad.join(';') || '每個字都對', !bad.length);
  });

  await run('被動作的卡 7', '字段輸入「黑魔」,點「黑魔導」,搜尋特殊召喚;點「黑魔導 ×」', '建議有黑魔導;變成「黑魔導 ×」;約 390 張;可取消', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['特殊召喚']);
    await site.target('cond');
    const bad = await site.typeCheck('#actionSetInput', '黑魔');
    rec.check('逐字打「黑魔」游標與值', '每個字都對', bad.join(';') || '每個字都對', !bad.length);
    const sug = await site.page.$$eval('#actionSetSuggest button', b => b.map(x => x.textContent.trim()));
    rec.check('建議清單有「黑魔導」', '有', sug.join('、'), sug.includes('黑魔導'));
    await site.page.locator('#actionSetSuggest button', { hasText: /^黑魔導$/ }).first().click();
    const chip = await site.page.$eval('#actionFields button[data-setunpick]', b => b.textContent.trim()).catch(() => '');
    rec.eq('變成', '黑魔導 ×', chip);
    const c = await site.search();
    rec.check('特殊召喚 字段 黑魔導 約 390 張', '約 390(±10%)', `${fmt(c.n)}(無法確認 ${fmt(c.unsure)})`, c.n >= 351 && c.n <= 429);
    await site.page.click('#actionFields button[data-setunpick]');
    rec.eq('取消後輸入框回來', '1', String(await site.page.locator('#actionSetInput').count()));
  });

  await run('被動作的卡 8', '卡名包含「ブラック・マジシャン」、「破壞」;改中文「黑魔導」', '1,260 張(第 2 份清單更新,原 1,259);中文同樣 1,260 張', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.target('cond');
    await site.givenName('ブラック・マジシャン');
    countCheck(rec, '卡名包含 ブラック・マジシャン', await site.search(), 1260, 1323);
    await site.givenName('黑魔導');
    countCheck(rec, '卡名包含 黑魔導', await site.search(), 1260, 1323);
  });

  await run('被動作的卡 9', '給條件一項都不填就搜尋', '結果與「不指定」相同;摺疊鈕不把被動作的卡算進去', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    const none = await site.search();
    const fNone = await site.page.$eval('#btnFilters', e => e.textContent);
    const acNone = await site.page.$eval('#actionCount', e => e.textContent);
    await site.target('cond');
    const cond = await site.search();
    const fCond = await site.page.$eval('#btnFilters', e => e.textContent);
    const acCond = await site.page.$eval('#actionCount', e => e.textContent);
    rec.eq('張數與不指定相同', `${fmt(none.n)}/${fmt(none.unsure)}`, `${fmt(cond.n)}/${fmt(cond.unsure)}`);
    rec.eq('摺疊鈕', fNone, fCond);
    rec.eq('動作搜尋標題旁的條件數', acNone, acCond);
  });
}

/* ---------------- 誰、受方、原因 ---------------- */

async function who(S, run) {
  const { rec } = S;

  await run('誰、受方、原因 1', '「特殊召喚」、勾觸發條件、誰做的「對手」', '171 張,入魔夢魘在', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['特殊召喚']);
    await site.kinds(['eff', 'cost', 'cond']);
    await site.agent('對手');
    countCheck(rec, '特殊召喚 誰對手 勾觸發條件', await site.search(), 171, 3264);
    has(rec, await site.idSet(), 359563, '入魔夢魘', true);
  });

  await run('誰、受方、原因 2', '改「返回」(仍對手、觸發條件);勾「含不限定的」', '10 張,奧比泰爾不在;45 張,它在', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['返回']);
    await site.kinds(['eff', 'cost', 'cond']);
    await site.agent('對手');
    countCheck(rec, '返回 誰對手', await site.search(), 10, 703);
    has(rec, await site.idSet(), 44818, '聖夜騎士團 奧比泰爾', false);
    await site.unrestricted(true);
    countCheck(rec, '返回 誰對手 含不限定的', await site.search(), 45, 696);
    has(rec, await site.idSet(), 44818, '聖夜騎士團 奧比泰爾', true);
  });

  await run('誰、受方、原因 3', '清除,「傷害」、落在誰身上「對手」;改「我方」', '689 張;123 張', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['傷害']);
    await site.recipient('對手');
    countCheck(rec, '傷害 受方對手', await site.search(), 689, 228);
    await site.recipient('我方');
    countCheck(rec, '傷害 受方我方', await site.search(), 123, 241);
  });

  await run('誰、受方、原因 4', '清除,「破壞」、勾觸發條件、原因「戰鬥」;勾含不限定的;原因改「效果」', '931 張(奇蹟翻轉師、安卡栗子球在,限制再生、熔岩槍杖手不在);1,285 張熔岩槍杖手在;蛇神降臨在', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.kinds(['eff', 'cost', 'cond']);
    await site.cause('戰鬥', '');
    countCheck(rec, '破壞 觸發條件 原因戰鬥', await site.search(), 931, 1650);
    let ids = await site.idSet();
    has(rec, ids, 131182, '奇蹟翻轉師', true);
    has(rec, ids, 595626, '安卡栗子球', true);
    has(rec, ids, 27551, '限制再生', false);
    has(rec, ids, 123709, '熔岩槍杖手', false);
    await site.unrestricted(true);
    countCheck(rec, '…含不限定的', await site.search(), 1285, 1575);
    has(rec, await site.idSet(), 123709, '熔岩槍杖手', true);
    await site.cause('效果', '');
    const c = await site.search();
    rec.note(`原因改效果(仍勾含不限定的):${fmt(c.n)} 張,無法確認 ${fmt(c.unsure)}`);
    has(rec, await site.idSet(), 16067089, '蛇神降臨', true);
  });

  await run('誰、受方、原因 5', '清除,「破壞」、抗性、原因「效果」、方「對手的」', '325 張,黑之魔導強化與縛神塚都在', async site => {
    await site.open();
    await site.clearAll();
    await site.openAction();
    await site.words(['破壞']);
    await site.pol('resist');
    await site.cause('效果', '對手');
    countCheck(rec, '破壞 抗性 原因對手的效果', await site.search(), 325, 136);
    const ids = await site.idSet();
    has(rec, ids, 111280, '黑之魔導強化', true);
    has(rec, ids, 269012, '縛神塚', true);
  });
}

/* ---------------- 結果的標示 ---------------- */

async function marks(S, run) {
  const { rec } = S;

  await run('結果的標示 1', '只選「破壞」,看 SPYRAL-龍捲風', '第 2、3 句有底色,其他沒有;底色上沒有標籤、字沒被標', async site => {
    await site.open();
    await site.openAction();
    await site.words(['破壞']);
    await site.search();
    const r = await site.cardInfo(35699, 'web-marks1-spyral');
    rec.check('SPYRAL-龍捲風 在結果裡', '在', r.found ? '在' : '不在', r.found);
    if (r.info) {
      rec.eq('有底色的句子(data-ei 從 0 算,1,2 即第 2、3 句)', '1,2', r.info.hits.map(h => h.ei).join(','));
      rec.eq('底色上的標籤', '(無)', r.info.hits.map(h => h.badge).filter(Boolean).join('、') || '(無)');
      rec.eq('被標的字', '(無)', r.info.hits.flatMap(h => h.kw).join('、') || '(無)');
      rec.look('SPYRAL-龍捲風 的底色是否落在會破壞的那兩個效果', r.shot);
    }
  });

  await run('結果的標示 2', '效果類型「誘發即時效果(2速)」+「破壞」;只留效果類型;看娛樂夥伴 天空徒弟', '273 張,底色句是 2 速且會破壞(例:後援者 馬格南);只留效果類型 1,438 張;天空徒弟單獨各在、一起不在', async site => {
    await site.open();
    await site.openAction();
    await site.words(['破壞']);
    await site.search();
    const onlyBreak = await site.idSet();
    await site.sideTri('kind', 'q', 'in');
    countCheck(rec, '2速+破壞', await site.search(), 273, 147);
    const both = await site.idSet();
    const pageHits = await site.page.$$eval('#results article.card', as => as.map(a => [...a.querySelectorAll('.card-text:not(.og-text) .eff.hit')].map(p => ({
      kinds: [...p.querySelectorAll('.eff-kind')].map(k => k.textContent), text: p.textContent }))));
    const flat = pageHits.flat();
    const okQ = flat.filter(h => h.kinds.includes('誘發即時效果(2速)')).length;
    const okBreak = flat.filter(h => /破壞/.test(h.text)).length;
    rec.check('第 1 頁每張卡都有底色句', '100 張都有', `${pageHits.filter(h => h.length).length} 張有`, pageHits.every(h => h.length));
    rec.check('第 1 頁底色句都是 2 速', `${flat.length} 句`, `${okQ} 句`, okQ === flat.length);
    rec.note(`第 1 頁底色句含「破壞」字樣:${okBreak}/${flat.length}`);
    const mag = await site.cardInfo(43227, 'web-marks2-magnum');
    rec.check('後援者 馬格南 在', '在', mag.found ? '在' : '不在', mag.found);
    if (mag.info) rec.look(`後援者 馬格南 的底色句是否 2 速且會破壞:${mag.info.hits.map(h => h.text).join(' / ')}`, mag.shot);
    await site.words([]);
    countCheck(rec, '只留 2 速', await site.search(), 1438, 0);
    const onlyQ = await site.idSet();
    rec.eq('天空徒弟(122520) 只選破壞/只留效果類型/兩個一起', '在/在/不在',
      `${onlyBreak.has(122520) ? '在' : '不在'}/${onlyQ.has(122520) ? '在' : '不在'}/${both.has(122520) ? '在' : '不在'}`);
  });

  await run('結果的標示 3', '效果文「墓地」+「特殊召喚」', '底色句裡「墓地」照舊被標字,且那一句是會特殊召喚的效果', async site => {
    await site.open();
    await site.openAction();
    await site.page.fill('#fText', '墓地');
    await site.words(['特殊召喚']);
    const c = await site.search();
    rec.note(`${fmt(c.n)} 張,無法確認 ${fmt(c.unsure)}`);
    const flat = (await site.page.$$eval('#results article.card .card-text:not(.og-text) .eff.hit', ps => ps.map(p => ({
      kw: [...p.querySelectorAll('mark.kw')].map(m => m.textContent), text: p.textContent })))) ;
    const kw = flat.filter(h => h.kw.includes('墓地')).length;
    const ss = flat.filter(h => /特殊召喚/.test(h.text)).length;
    rec.check('第 1 頁底色句都有被標的「墓地」', `${flat.length} 句`, `${kw} 句`, flat.length > 0 && kw === flat.length);
    rec.check('第 1 頁底色句都含「特殊召喚」', `${flat.length} 句`, `${ss} 句`, ss === flat.length);
    const shot = await site.shot('web-marks3-gy-ss', { locator: site.page.locator('#results article.card').first() });
    rec.look('效果文「墓地」+特殊召喚:被標字的那一句是否就是會特殊召喚的效果', shot);
  });

  await run('結果的標示 4', '必發/選發選「必發」+「破壞」', '底色句是必發且會破壞,標籤寫必發', async site => {
    await site.open();
    await site.openAction();
    await site.sideTri('opt', 'm', 'in');
    await site.words(['破壞']);
    const c = await site.search();
    rec.note(`${fmt(c.n)} 張,無法確認 ${fmt(c.unsure)}`);
    const flat = await site.page.$$eval('#results article.card .card-text:not(.og-text) .eff.hit', ps => ps.map(p => ({
      badge: p.querySelector('.eff-hit') ? p.querySelector('.eff-hit').textContent : '', text: p.textContent })));
    const b = flat.filter(h => /必發/.test(h.badge)).length;
    rec.check('第 1 頁底色句的標籤都寫必發', `${flat.length} 句`, `${b} 句`, flat.length > 0 && b === flat.length);
    rec.note(`第 1 頁底色句含「破壞」字樣:${flat.filter(h => /破壞/.test(h.text)).length}/${flat.length}`);
    const shot = await site.shot('web-marks4-mandatory', { locator: site.page.locator('#results article.card').first() });
    rec.look('必發+破壞:底色句是否是必發而且會破壞的那一句', shot);
  });

  await run('結果的標示 5', '效果類型「啟動效果」+「特殊召喚」+卡名「心靈大師」', '卡照樣列出,但沒有任何一句有底色', async site => {
    await site.open();
    await site.openAction();
    await site.sideTri('kind', 'i', 'in');
    await site.words(['特殊召喚']);
    await site.page.fill('#fName', '心靈大師');
    await site.search();
    const r = await site.cardInfo(96782886, 'web-marks5-mentalmaster');
    rec.check('心靈大師 列出', '在', r.found ? '在' : '不在', r.found);
    if (r.info) rec.eq('底色句數', '0', String(r.info.hits.length));
  });

  await run('結果的標示 6', '清掉動作,只用效果文「墓地」搜尋', '標示和改版前一樣', async site => {
    await site.open();
    await site.page.fill('#fText', '墓地');
    const c = await site.search();
    const flat = await site.page.$$eval('#results article.card .card-text:not(.og-text) .eff.hit', ps => ps.map(p => ({
      kw: p.querySelectorAll('mark.kw').length, badge: p.querySelector('.eff-hit') ? p.querySelector('.eff-hit').textContent : '' })));
    rec.check('底色句都有被標的字', `${flat.length} 句`, `${flat.filter(h => h.kw).length} 句`, flat.length > 0 && flat.every(h => h.kw));
    rec.eq('沒有「無法確認」那行', 'false', String(c.unsureShown));
    rec.na('和改版前一樣', '沒有改版前的網站可對照');
    const shot = await site.shot('web-marks6-text-only', { locator: site.page.locator('#results article.card').first() });
    rec.look('只用效果文「墓地」:標示樣子是否和改版前一樣', shot);
  });

  await run('結果的標示 7', '清掉動作,只用卡名「青眼」搜尋', '清單下方沒有「無法確認」那行', async site => {
    await site.open();
    await site.page.fill('#fName', '青眼');
    const c = await site.search();
    rec.eq('「無法確認」那行顯示', 'false', String(c.unsureShown));
  });
}

/* ---------------- 清除條件與手機版 ---------------- */

async function clearMobile(S, run) {
  const { rec } = S;

  await run('清除條件與手機版 1', '各欄位都設值後按「清除條件」;再點「給條件」', '全部回到預設;給條件各項是空的', async site => {
    await site.open();
    await site.openAction();
    await site.words(['破壞', '除外']);
    await site.zone('from', '墓地', '對手');
    await site.zone('to', '除外', '我方');
    await site.target('cond');
    await site.givenBtn('race', '龍族');
    await site.givenBtn('attr', '闇');
    await site.page.fill('#actionFields input[data-glv="lvMin"]', '4');
    await site.givenName('龍');
    await site.page.fill('#actionSetInput', '黑魔');
    await site.page.locator('#actionSetSuggest button', { hasText: /^黑魔導$/ }).first().click();
    await site.kinds(['cond']);
    await site.pol('resist');
    await site.agent('對手');
    await site.recipient('我方');
    await site.cause('戰鬥', '對手');
    await site.unrestricted(true);
    await site.clearAll();
    const st = await site.page.evaluate(() => {
      const f = document.getElementById('actionFields');
      const q = s => f.querySelector(s);
      return {
        words: f.querySelectorAll('button[data-word][data-st="in"]').length,
        zones: [...f.querySelectorAll('select[data-zone], select[data-side]')].map(s => s.value).join('|'),
        mode: q('button[data-mode][data-st="in"]').dataset.mode,
        kinds: ['eff', 'cost', 'cond'].map(k => q(`input[data-kind="${k}"]`).checked).join(','),
        pol: q('button[data-pol][data-st="in"]').dataset.pol,
        agent: q('button[data-agent][data-st="in"]').dataset.agent,
        recipient: q('button[data-recipient][data-st="in"]').dataset.recipient,
        cause: q('select[data-cause-kind]').value + '|' + q('select[data-cause-side]').value,
        unr: q('input[data-include-unrestricted]').checked,
        count: document.getElementById('actionCount').textContent,
      };
    });
    rec.eq('動作詞沒選', '0', String(st.words));
    rec.eq('區域與方不限', '|||', st.zones);
    rec.eq('被動作的卡', 'none(不指定)', `${st.mode}${st.mode === 'none' ? '(不指定)' : ''}`);
    rec.eq('段類別', 'true,true,false(效果、代價)', `${st.kinds}${st.kinds === 'true,true,false' ? '(效果、代價)' : ''}`);
    rec.eq('極性', 'do', st.pol);
    rec.eq('誰做的/落在誰身上', '不限/不限', `${st.agent || '不限'}/${st.recipient || '不限'}`);
    rec.eq('原因', '|', st.cause);
    rec.eq('含不限定的', 'false', String(st.unr));
    rec.eq('條件數', '(空)', st.count || '(空)');
    await site.target('cond');
    const g = await site.page.evaluate(() => {
      const f = document.getElementById('actionFields');
      return {
        on: f.querySelectorAll('button[data-gkey][data-st="in"]').length,
        lv: [...f.querySelectorAll('input[data-glv]')].map(i => i.value).join('|'),
        set: f.querySelector('#actionSetInput') ? f.querySelector('#actionSetInput').value : '(字段已選)',
        name: f.querySelector('input[data-gname]').value,
      };
    });
    rec.eq('給條件各項是空的', '按鈕0 等級| 字段「」 卡名「」', `按鈕${g.on} 等級${g.lv} 字段「${g.set}」 卡名「${g.name}」`);
  });

  await run('清除條件與手機版 2', '手機寬度(390):選動作詞與被動作的卡後搜尋', '動作搜尋區塊跟著側欄一起摺疊;摺疊鈕「篩選條件・N 項」把動作條件算進去(每欄一項,含不限定的不算)', async site => {
    await site.page.setViewportSize({ width: 390, height: 844 });
    await site.open();
    const vis0 = await site.page.isVisible('#actionBox');
    rec.eq('手機寬度一開頁,動作搜尋區塊收在側欄裡(看不見)', 'false', String(vis0));
    await site.page.click('#btnFilters');
    rec.eq('打開摺疊鈕後看得見', 'true', String(await site.page.isVisible('#actionBox')));
    await site.openAction();
    await site.words(['破壞']);
    await site.target('this_card');
    await site.unrestricted(true);
    await site.searchOnly();
    const t1 = await site.page.$eval('#btnFilters', e => e.textContent);
    rec.eq('破壞+這張卡自己+含不限定的', '篩選條件・2 項', t1);
    rec.eq('搜尋後側欄收起,動作搜尋區塊一起看不見', 'false', String(await site.page.isVisible('#actionBox')));
    await site.page.click('#btnFilters');
    await site.zone('from', '墓地', '');
    await site.page.fill('#fName', '龍');
    await site.searchOnly();
    const t2 = await site.page.$eval('#btnFilters', e => e.textContent);
    rec.eq('再加從哪裡、卡名', '篩選條件・4 項', t2);
  });

  await run('清除條件與手機版 3', '手機寬度(390):按鈕列、下拉、數字框、輸入框與建議清單', '不超出側欄', async site => {
    await site.page.setViewportSize({ width: 390, height: 844 });
    await site.open();
    await site.page.click('#btnFilters');
    await site.openAction();
    await site.page.click('#actionFields button[data-more]');
    await site.words(['破壞']);
    const results = [];
    await site.target('card');
    await site.page.fill('#actionCardInput', '黑魔導');
    results.push(['指定一張卡+建議清單', await S.overflow(site)]);
    await site.target('cond');
    await site.page.fill('#actionSetInput', '黑');
    await site.givenName('ブラック・マジシャン・ガール');
    results.push(['給條件+字段建議清單', await S.overflow(site)]);
    for (const [name, o] of results) {
      rec.check(`${name}:側欄內元素右緣不超出側欄`, '0 個超出', o.bad.length ? o.bad.slice(0, 5).join(';') : '0 個超出', !o.bad.length);
      rec.check(`${name}:頁面無橫向捲動`, `scrollWidth ≤ ${o.cw}`, `scrollWidth=${o.sw}`, o.sw <= o.cw);
    }
    const shot = await site.shot('web-mobile3-sidebar', { fullPage: true });
    rec.look('手機寬度(390)動作搜尋區塊的按鈕、下拉、輸入框與建議清單', shot);
  });
}

/* ---------------- 網址與瀏覽紀錄 ---------------- */

async function history(S, run) {
  const { rec } = S;
  const state = {};

  await run('網址與瀏覽紀錄 1', '卡名「青眼」搜尋', '網址列與搜尋前相同,沒有 # 或 ?', async site => {
    await site.open();
    state.url0 = await site.url();
    await site.page.fill('#fName', '青眼');
    state.blue = await site.search();
    const u = await site.url();
    rec.eq('網址', state.url0, u);
    rec.check('沒有 # 或 ?', '沒有', /[#?]/.test(u) ? '有' : '沒有', !/[#?]/.test(u));
  }, { keep: true });

  await run('網址與瀏覽紀錄 2', '展開動作搜尋選「破壞」、極性「抗性」搜尋,再把排序改成攻擊力', '網址一直沒變', async site => {
    await site.openAction();
    await site.words(['破壞']);
    await site.pol('resist');
    state.act = await site.search();
    const u1 = await site.url();
    await site.page.selectOption('#sortKey', 'atk');
    state.firstAtk = await site.page.$eval('#results article.card', a => a.dataset.cid);
    const u2 = await site.url();
    rec.eq('搜尋後網址', state.url0, u1);
    rec.eq('改排序後網址', state.url0, u2);
    rec.note(`青眼+破壞抗性:${fmt(state.act.n)} 張`);
  }, { keep: true });

  await run('網址與瀏覽紀錄 3', '重新整理', '條件(含動作條件與區塊展開)、排序、結果都還在;索引沒載完時結果區先顯示載入中,接著自動出結果', async site => {
    await site.page.reload();
    await site.page.waitForFunction(() => document.getElementById('dbInfo').textContent.length > 0);
    await site.page.waitForSelector('#actionFields button[data-word]', { timeout: 30000 });
    await site.settle();
    const seen = await site.page.evaluate(() => window.__obs.results.some(t => /動作索引載入中/.test(t) && /載完會自動出結果/.test(t)));
    rec.eq('結果區先顯示「動作索引載入中… 載完會自動出結果」', 'true', String(seen));
    const r = await site.page.evaluate(() => ({
      name: document.getElementById('fName').value,
      open: document.getElementById('actionHead').getAttribute('aria-expanded'),
      words: [...document.querySelectorAll('#actionFields button[data-word][data-st="in"]')].map(b => b.dataset.word).join(','),
      pol: document.querySelector('#actionFields button[data-pol][data-st="in"]').dataset.pol,
      sort: document.getElementById('sortKey').value,
      first: (document.querySelector('#results article.card') || {}).dataset?.cid,
    }));
    const c = await site.counts();
    rec.eq('條件', '青眼|true|破壞|resist', `${r.name}|${r.open}|${r.words}|${r.pol}`);
    rec.eq('排序', 'atk', r.sort);
    rec.eq('結果(張數、第一張)', `${fmt(state.act.n)}、${state.firstAtk}`, `${fmt(c.n)}、${r.first}`);
    rec.eq('網址', state.url0, await site.url());
  }, { keep: true });

  await run('網址與瀏覽紀錄 4', '按上一頁三次,再下一頁三次', '回到改排序前 → 只有青眼 → 空白首頁;下一頁依序回來,動作條件跟著還原', async site => {
    const snap = async () => {
      await site.settle();
      return site.page.evaluate(() => ({
        name: document.getElementById('fName').value,
        words: [...document.querySelectorAll('#actionFields button[data-word][data-st="in"]')].map(b => b.dataset.word).join(','),
        pol: (document.querySelector('#actionFields button[data-pol][data-st="in"]') || { dataset: {} }).dataset.pol || '',
        sort: document.getElementById('sortKey').value,
        info: document.getElementById('resultInfo').textContent,
        idle: !!document.querySelector('#results .idle'),
      }));
    };
    const fmtS = s => `卡名「${s.name}」 動作[${s.words}] 極性${s.pol} 排序${s.sort} ${s.idle ? '(空白首頁)' : s.info}`;
    const back = async () => { await site.page.goBack(); await site.page.waitForTimeout(300); return snap(); };
    const fwd = async () => { await site.page.goForward(); await site.page.waitForTimeout(300); return snap(); };
    const nAct = fmt(state.act.n);
    const b1 = await back();
    rec.check('上一頁 1:改排序前', `青眼 破壞 抗性 排序dom 共 ${nAct} 張`, fmtS(b1),
      b1.name === '青眼' && b1.words === '破壞' && b1.pol === 'resist' && b1.sort === 'dom' && b1.info.includes(`共 ${state.act.n} 張`));
    const b2 = await back();
    rec.check('上一頁 2:只有青眼', `青眼 無動作 共 ${fmt(state.blue.n)} 張`, fmtS(b2),
      b2.name === '青眼' && b2.words === '' && b2.info.includes(`共 ${state.blue.n} 張`));
    const b3 = await back();
    rec.check('上一頁 3:空白首頁', '卡名空、空白首頁', fmtS(b3), b3.name === '' && b3.idle);
    const f1 = await fwd();
    rec.check('下一頁 1:只有青眼', `青眼 無動作 共 ${fmt(state.blue.n)} 張`, fmtS(f1),
      f1.name === '青眼' && f1.words === '' && f1.info.includes(`共 ${state.blue.n} 張`));
    const f2 = await fwd();
    rec.check('下一頁 2:青眼+破壞抗性', `青眼 破壞 抗性 排序dom 共 ${nAct} 張`, fmtS(f2),
      f2.name === '青眼' && f2.words === '破壞' && f2.pol === 'resist' && f2.sort === 'dom' && f2.info.includes(`共 ${state.act.n} 張`));
    const f3 = await fwd();
    rec.check('下一頁 3:改排序後', `青眼 破壞 抗性 排序atk 共 ${nAct} 張`, fmtS(f3),
      f3.name === '青眼' && f3.words === '破壞' && f3.pol === 'resist' && f3.sort === 'atk' && f3.info.includes(`共 ${state.act.n} 張`));
    rec.eq('網址全程沒變', state.url0, await site.url());
  });

  await run('網址與瀏覽紀錄 5', '在網址後面加 #name=%E9%9D%92&attr=dark 開啟', '首頁、條件全空、網址上的參數被清掉、Console 沒有紅字', async site => {
    const before = site.errors().length;
    await site.open(site.base + '#name=%E9%9D%92&attr=dark');
    await site.page.waitForTimeout(300);
    const r = await site.page.evaluate(() => ({
      name: document.getElementById('fName').value,
      idle: !!document.querySelector('#results .idle'),
      filters: document.getElementById('btnFilters').textContent,
      url: location.href,
    }));
    rec.eq('網址', site.base, r.url);
    rec.eq('卡名', '', r.name);
    rec.eq('條件數(摺疊鈕)', '篩選條件', r.filters);
    rec.eq('首頁(空白)', 'true', String(r.idle));
    rec.eq('Console 紅字', '0', String(site.errors().length - before));
    await site.open(site.base + '?name=%E9%9D%92');
    rec.eq('舊連結 ?name= 也被清掉', site.base, await site.url());
  });

  await run('網址與瀏覽紀錄 6', '沒有任何條件時看畫面', '與改版前相同', async site => {
    await site.open();
    const t = await site.page.$eval('#results', e => e.textContent.replace(/\s+/g, ''));
    rec.eq('空白首頁文字', '設定條件後按「搜尋」', t);
    rec.na('與改版前相同', '沒有改版前的網站可對照');
    const shot = await site.shot('web-history6-idle', { fullPage: false });
    rec.look('沒有任何條件時的畫面是否與改版前相同', shot);
  });
}

module.exports = { sections: [
  ['載入時機', loading], ['版面與文字', layoutText], ['動作、從、到', fromTo], ['段類別與極性', kindsPol],
  ['被動作的卡', target], ['誰、受方、原因', who], ['結果的標示', marks], ['清除條件與手機版', clearMobile],
  ['網址與瀏覽紀錄', history],
], L };
