/**
 * typed_commit.test.js — 中心詞框沒按 Enter 就點別的(predicate-ui 票 09,修票 04 記的缺口)
 *
 * 跑法:`node --test script/web/typed_commit.test.js`
 *
 * 真瀏覽器的症狀:框裡有字時按下按鈕,先失焦、框裡的字收進標籤、抽屜與條件列重畫,按到的鈕被換掉,
 * 那一下點擊落空。修法是框裡有字時按下不搶焦點,點擊再先收字才做事。
 * 接縫:`Strip.init` 註冊的事件與 `onEdit`。經 harness 載入真前端程式,事件物件是假的,只有用到的幾個
 * 方法;事件順序照瀏覽器(按下 → 點擊;blur 同步發 change)。真實點擊在真瀏覽器走過(票 09 Comments)。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const vm = require('node:vm');
const harness = require('./frontend_harness.js');

const POLAR = ['肯定', '可能'];
const VOCAB = {
  frame: {
    lemmas: ['破壊', '除外'],
    heads: ['モンスター', '甲', '丁', '罠'],
    domains: {
      位置: ['代價', '效果', '條件'], 極性: ['肯定', '否定', '可能'], 動作對象: ['此卡', '非此卡'],
      數量類: ['定數'], 中心詞類: ['卡'], 修飾語類: ['種族'],
    },
  },
  catalog: [
    { name: '破壊', path: ['破壊'], cards: { 代價: 0, 效果: 3, 條件: 0 }, predicate: { 極性: POLAR, 詞元: '破壊' } },
    { name: '除外', path: ['除外'], cards: { 代價: 0, 效果: 2, 條件: 0 }, predicate: { 極性: POLAR, 詞元: '除外' } },
  ],
};
const FIELD = '受事者中心詞';
const seg = word => [VOCAB.frame.heads.indexOf(word), 0, 0, 0];
const FRAMES = [
  [0, 2, 1, 0, 0, 0, 0, 2, [], [], [], ['モンスター', '甲', '丁'].map(seg)],
  [1, 2, 1, 0, 0, 0, 0, 0, [], [], [], [seg('罠')]],
];

/* 只帶選擇器比對的假節點:closest 走 parent,matches 看建立時給的選擇器。 */
function fakeEl(selectors, props = {}, parent = null) {
  const el = {
    dataset: {}, parent, ...props,
    matches: s => selectors.indexOf(s) >= 0,
    closest: s => (el.matches(s) ? el : parent && parent.closest(s)),
  };
  return el;
}

function page() {
  const box = harness.load({ vocab: VOCAB, frames: FRAMES });
  const els = {};
  const on = {};
  const listen = name => (type, fn) => { (on[`${name}.${type}`] = on[`${name}.${type}`] || []).push(fn); };
  const realStub = box.document.createElement;
  box.document.getElementById = id => {
    if (!els[id]) {
      els[id] = realStub();
      els[id].addEventListener = listen(id);
      els[id].querySelector = () => realStub();
    }
    return els[id];
  };
  box.document.addEventListener = listen('document');
  box.document.activeElement = null;
  const fire = (key, e) => (on[key] || []).forEach(fn => fn(e));
  const ev = target => ({ target, prevented: false, preventDefault() { this.prevented = true; }, composedPath: () => [] });
  box.__edits = [];
  vm.runInContext(`
    var state = { and: [Cond.tagAt('破壊', false), Cond.tagAt('除外', true)], or: [], orSide: [] };
    var cleared = 0, removed = [];
    function repaint() { Strip.render(state, []); }
    Strip.init({
      countOf: () => 0,
      onEdit: (i, tag) => { state = Cond.replaceAt(state, i, tag); __edits.push(Cond.sentence(tag)); repaint(); },
      onRemove: i => { removed.push([i, Cond.tags(state).map(Cond.sentence)]); state = Cond.removeAt(state, i); repaint(); },
      onMove: () => {}, onSideRemove: () => {}, onSideGo: () => {}, onSideMove: () => {},
      onClear: () => { cleared = Cond.tags(state).map(Cond.sentence); state = Cond.empty(); repaint(); },
    });
    repaint();`, box);
  /* 開第 0 張的抽屜。 */
  const tag0 = fakeEl(['.strip-tag'], { dataset: { i: '0' } });
  fire('condStrip.click', ev(fakeEl([], {}, tag0)));

  const fieldBox = fakeEl(['[data-field]'], { dataset: { field: FIELD } });
  const typing = value => {
    const input = fakeEl(['#condDrawer input'], { dataset: { act: 'add-text' }, value }, fieldBox);
    input.blur = () => {
      box.document.activeElement = null;
      if (input.value.trim()) fire('condDrawer.change', ev(input));
    };
    box.document.activeElement = input;
    return input;
  };
  const chip = () => {
    const f = fakeEl(['[data-field]'], { dataset: { field: '動作對象' } });
    return fakeEl(['[data-act]', 'button', '#condDrawer button'], { dataset: { act: 'toggle', v: '非此卡' } }, f);
  };
  const press = target => {
    const down = ev(target);
    fire('document.mousedown', down);
    return down;
  };
  return { box, fire, ev, typing, chip, press, tag0, sentences: () => JSON.parse(vm.runInContext('JSON.stringify(Cond.tags(state).map(Cond.sentence))', box)) };
}

test('框裡有字:按下抽屜的鈕不搶焦點,點擊落得到', () => {
  const { typing, chip, press } = page();
  typing('モンスター');
  assert.strictEqual(press(chip()).prevented, true);
});

test('框是空的:按下照常,不攔', () => {
  const { typing, chip, press } = page();
  typing('   ');
  assert.strictEqual(press(chip()).prevented, false);
});

test('沒有焦點在框裡:按下照常,標籤拖得動', () => {
  const { chip, press, tag0 } = page();
  assert.strictEqual(press(chip()).prevented, false);
  assert.strictEqual(press(tag0).prevented, false);
});

test('點抽屜的鈕:框裡的字先收進標籤,鈕的動作接在它上面', () => {
  const { box, fire, ev, typing, chip, sentences } = page();
  typing('モンスター');
  fire('condDrawer.click', ev(chip()));
  assert.strictEqual(sentences()[0].includes('モンスター'), true);
  assert.strictEqual(sentences()[0].includes('非此卡'), true);
  assert.strictEqual(box.__edits.length, 2);
});

test('點條件列的 ×:字先收進正在改的那張,再刪另一張', () => {
  const { box, fire, ev, typing } = page();
  typing('モンスター');
  const other = fakeEl(['.strip-tag'], { dataset: { i: '1' } });
  fire('condStrip.click', ev(fakeEl(['.strip-x'], {}, other)));
  const removed = JSON.parse(vm.runInContext('JSON.stringify(removed)', box));
  assert.strictEqual(removed[0][0], 1);
  assert.strictEqual(removed[0][1][0].includes('モンスター'), true);
});

test('點清除條件:走到清除', () => {
  const { box, fire, ev, typing, sentences } = page();
  typing('モンスター');
  fire('condStrip.click', ev(fakeEl(['.strip-clear'])));
  assert.deepStrictEqual(sentences(), []);
  assert.strictEqual(vm.runInContext('Array.isArray(cleared)', box), true);
});

test('刪框旁已有的詞:照點下去時看到的那一個,不因新字排進來而刪錯', () => {
  const { box, fire, ev, typing, sentences } = page();
  typing('甲');
  const f = fakeEl(['[data-field]'], { dataset: { field: FIELD } });
  /* 先收一個詞:框裡清單是 [甲]。 */
  box.document.activeElement.blur();
  /* 再打一個排序在前的詞,點「甲」旁的 ×(編號 0)。 */
  typing('丁');
  const drop = fakeEl(['[data-act]', 'button', '#condDrawer button'], { dataset: { act: 'drop', i: '0' } }, f);
  fire('condDrawer.click', ev(drop));
  assert.strictEqual(sentences()[0].includes('丁'), true);
  assert.strictEqual(sentences()[0].includes('甲'), false);
});

test('打了清單外的字按 Enter 或離開框:不送 onEdit,框被清空', () => {
  const { box, typing } = page();
  const input = typing('乙');
  input.blur();
  assert.strictEqual(box.__edits.length, 0);
  assert.strictEqual(input.value, '');
});

test('中心詞表裡有、但不在這張標籤清單上的字:一樣不收', () => {
  const { box, typing } = page();
  const input = typing('罠');
  input.blur();
  assert.strictEqual(box.__edits.length, 0);
  assert.strictEqual(input.value, '');
});

test('框裡是清單外的字時點抽屜的鈕:字被清掉,鈕照樣生效', () => {
  const { box, fire, ev, typing, chip, sentences } = page();
  const input = typing('乙');
  fire('condDrawer.click', ev(chip()));
  assert.strictEqual(input.value, '');
  assert.strictEqual(sentences()[0].includes('乙'), false);
  assert.strictEqual(sentences()[0].includes('非此卡'), true);
  assert.strictEqual(box.__edits.length, 1);
});
