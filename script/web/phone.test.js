/**
 * phone.test.js — 手機寬(predicate-ui 票 06)
 *
 * 跑法:`node --test script/web/phone.test.js`
 *
 * 接縫:`Query.summarize`(篩選鈕與看結果鈕的字)、`Strip.render`(標籤上的 ⇄)。經 harness 載入真
 * 前端程式,只把 `getElementById` 換成同一個 id 回同一個物件,才讀得到寫進去的字。
 * 版面、點擊、捲動是 CSS 與 DOM,在真瀏覽器手機寬走(票 Comments)。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const vm = require('node:vm');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const VOCAB = {
  attr: { zh: '屬性', items: [{ code: 'light', zh: '光' }] },
  catalog: [
    { name: '破壊', path: ['破壊'], cards: { 代價: 0, 效果: 3, 條件: 0 },
      predicate: { 極性: POLAR, 詞元: '破壊' } },
  ],
};

function loadPage() {
  const box = harness.load({ vocab: VOCAB });
  const els = {};
  const realStub = box.document.createElement;
  box.document.getElementById = id => (els[id] = els[id] || realStub());
  return { box, els, run: code => vm.runInContext(code, box) };
}

function stripHtml(state, sideTags) {
  const { box, els, run } = loadPage();
  box.__args = JSON.stringify({ state, sideTags });
  run(`Strip.init({ countOf: () => 0 });
       (a => Strip.render(a.state, a.sideTags))(JSON.parse(__args))`);
  return els.condStrip.innerHTML;
}

/* ── 篩選鈕與看結果鈕的字 ── */

const labels = (n, total) => {
  const { box, els, run } = loadPage();
  box.__n = n;
  box.__total = total;
  run('Query.summarize(__n, __total)');
  return [els.btnFilters.textContent, els.btnResults.textContent];
};

test('沒有條件:兩顆鈕都不帶數字', () => {
  assert.deepStrictEqual(labels(0, null), ['篩選條件', '看結果']);
});

test('有條件:篩選鈕寫條件數,看結果鈕寫張數', () => {
  assert.deepStrictEqual(labels(2, 1618), ['篩選條件・2 項', '看結果(1,618 張)']);
});

test('有條件但 0 張:看結果鈕照寫 0 張,不是當成沒有條件', () => {
  assert.deepStrictEqual(labels(1, 0), ['篩選條件・1 項', '看結果(0 張)']);
});

/* ── ⇄ ── */

const SWAP = /class="strip-swap"/g;
const swaps = html => (html.match(SWAP) || []).length;

test('⇄:動作標籤與左側條件標籤每張一顆,兩區都有', () => {
  const { box } = loadPage();
  const tag = harness.cond(box, 'tagAt', '破壊', false);
  const state = { and: [tag], or: [harness.cond(box, 'tagAt', '破壊', true)], orSide: ['attr'] };
  const sideTags = [
    { key: 'attr', label: '屬性', val: '光', part: {}, target: {} },
    { key: 'cat', label: '', val: '怪獸', part: {}, target: {} },
  ];
  assert.strictEqual(swaps(stripHtml(state, sideTags)), 4);
});

test('⇄:沒有標籤時只有提示字,沒有鈕', () => {
  assert.strictEqual(swaps(stripHtml({ and: [], or: [], orSide: [] }, [])), 0);
});
