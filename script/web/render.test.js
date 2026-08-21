/**
 * render.test.js — 呈現縫(卡片物件 → HTML 字串)的測試
 *
 * 跑法:`node --test script/web/`
 *
 * 與接縫 3 同一個沙箱(`frontend_harness.js`)載真實的 `web/js/render.js`,
 * 餵合成卡片、斷言產出的 HTML **字面**(使用者看得到的文字)——不斷言 DOM
 * 結構與 CSS class 名稱(實作細節,重構就壞而且壞得沒有意義)。
 *
 * 目前只蓋[[禁限狀態]]徽章列(spec banlist,2026-08-22 使用者裁示 render 也要
 * 自動測);其餘呈現仍走人工驗收。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const item = (code, zh) => ({ code, zh });

/* 最小 VOCAB:只放 cardHtml 會查到的表。 */
const VOCAB = {
  cat: { zh: '大類', items: [item('m', '怪獸'), item('s', '魔法'), item('t', '陷阱')] },
  sub_m: { zh: '怪獸子類型', items: [item('effect', '效果')] },
  attr: { zh: '屬性', items: [item('dark', '闇')] },
  race: { zh: '種族', items: [item('insect', '昆蟲族')] },
  rarity: { zh: 'MD 稀有度', items: [item('UR', 'UR')] },
  ot: { zh: 'OCG・TCG', items: [item('o', 'OCG 限定'), item('t', 'TCG 限定'),
                                item('b', '兩者')] },
  ban_o: { zh: 'OCG 禁限',
           items: [item('f', '禁止'), item('l', '限制'), item('s', '準限制')] },
  ban_t: { zh: 'TCG 禁限',
           items: [item('f', '禁止'), item('l', '限制'), item('s', '準限制')] },
};

const sandbox = harness.load({ cards: [], vocab: VOCAB, meta: {} });

/* 一張怪獸卡的索引條目;欄位形狀與 web/data.js 一致(空值省略)。 */
function card(kw) {
  return Object.assign({
    id: 23434538, n: '增殖的G', nj: '増殖するG', ne: 'Maxx "C"',
    c: 'm', s: ['effect'], at: 'dark', r: 'insect', lv: 2,
    atk: 500, df: 200, ra: 'UR', ot: 'b',
  }, kw);
}

const html = (kw) => harness.cardHtml(sandbox, { card: card(kw), rows: null });

test('上了 OCG 榜的卡在名稱行下方長出禁限徽章列', () => {
  const out = html({ bo: 'f' });
  assert.ok(out.includes('OCG 禁止'));
  // 位置:禁限列在日/英名稱之後(2026-08-22 使用者裁示「名稱行下面一行」)
  assert.ok(out.indexOf('OCG 禁止') > out.indexOf('Maxx'));
});

test('統一三值的字面:限制與準限制', () => {
  assert.ok(html({ bo: 'l' }).includes('OCG 限制'));
  assert.ok(html({ bo: 's' }).includes('OCG 準限制'));
});

test('沒上任何榜的卡完全不長禁限列', () => {
  const out = html({});
  assert.ok(!out.includes('禁止'));
  assert.ok(!out.includes('OCG'));  // ot 是「兩者」,畫面上不該有任何 OCG 字樣
});

test('任一賽制上榜即整列出現,各賽制欄位固定順序齊列', () => {
  // 只上 OCG 榜:TCG 欄仍在,已發行未上榜寫「—」
  const out = html({ bo: 'f' });
  assert.ok(out.includes('OCG 禁止'));
  assert.ok(out.includes('TCG —'));
  assert.ok(out.indexOf('OCG 禁止') < out.indexOf('TCG —'));
  // 同一張卡兩賽制各自的值互不干擾
  const both = html({ bo: 's', bt: 'f' });
  assert.ok(both.includes('OCG 準限制'));
  assert.ok(both.includes('TCG 禁止'));
});

test('未在該賽制發行的欄位寫「未發行」(由 ot 推導)', () => {
  // OCG 限定卡(ot='o')上了 OCG 榜:TCG 欄是未發行,不是「—」
  const ocgOnly = html({ ot: 'o', bo: 'l' });
  assert.ok(ocgOnly.includes('TCG 未發行'));
  assert.ok(!ocgOnly.includes('TCG —'));
  // TCG 限定卡(ot='t')上了 TCG 榜:OCG 欄是未發行
  const tcgOnly = html({ ot: 't', bt: 'f' });
  assert.ok(tcgOnly.includes('OCG 未發行'));
  assert.ok(tcgOnly.includes('TCG 禁止'));
});
