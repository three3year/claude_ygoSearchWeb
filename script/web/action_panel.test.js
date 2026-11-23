'use strict';

/* 動作搜尋面板(接縫 3,經 page_driver 的假 DOM):使用者看得到的選項、按下去讀到的條件、
   清除條件、段類別至少勾一個,以及索引載入中的畫面。不斷言結構與 class。 */

const test = require('node:test');
const assert = require('node:assert');
const { open } = require('./page_driver.js');
const { actionData } = require('./action_fixture.js');

const CARDS = [
  { id: 701, n: '破壞卡甲', c: 's' },
  { id: 702, n: '破壞卡乙', c: 's' },
  { id: 703, n: '從墓地特殊召喚', c: 'm' },
  { id: 704, n: '除外到手牌', c: 's' },
];
const ACTION = actionData([
  { id: 701, segs: [{ acts: ['破壞'], rows: 3, cause: ['戰鬥', null] }] },
  { id: 702, segs: [{ acts: ['破壞'], cause: ['效果', '對手'] },
                    { acts: ['破壞'], cause: ['效果', null] }] },
  { id: 703, segs: [{ acts: ['特殊召喚'], rows: 2,
                      lines: [{ from: [['墓地', '我方']], obj: [701] }] }] },
  { id: 704, segs: [{ acts: ['除外'], lines: [{ from: [['墓地', '我方']], to: [['手牌', '我方']],
                                                obj: [702] }] }] },
], CARDS.map(c => c.id));

const WORDS = ['破壞', '特殊召喚', '除外'];
const FULL = { actions: ['特殊召喚'], from: { zone: '墓地', side: '我方' }, to: { zone: '手牌' },
               kinds: ['eff', 'cond'], pol: 'limit', agent: '對手', recipient: '我方',
               cause: { kind: '效果', side: '對手' }, target: { card: 701 },
               include_unrestricted: true };

function loadedPage() {
  const page = open({ cards: CARDS, action: ACTION });
  page.panel.init();
  page.panel.open();
  page.panel.finishLoading();
  return page;
}

test('打開面板先顯示載入中,載完才出現選項', () => {
  const { panel } = open({ cards: CARDS, action: ACTION });
  panel.init();
  panel.open();
  assert.match(panel.status(), /載入中/);
  assert.deepStrictEqual(panel.buttons(), []);
  panel.finishLoading();
  assert.strictEqual(panel.status(), '');
  assert.ok(panel.buttons().includes('破壞'));
});

test('動作詞、區域、原因的選項由動作索引生成,照列數多的排前面', () => {
  const { panel } = loadedPage();
  assert.deepStrictEqual(panel.buttons().filter(b => WORDS.includes(b)), WORDS);
  const [from, , to, , causes] = panel.selects();
  assert.deepStrictEqual(from, ['不限', '墓地', '手牌']);
  assert.deepStrictEqual(to, from);
  assert.deepStrictEqual(causes, ['不限', '效果', '戰鬥']);
});

test('按動作詞就選上,再按一次取消', () => {
  const { panel } = loadedPage();
  panel.click('除外');
  panel.click('破壞');
  assert.deepStrictEqual(panel.read(), { actions: ['破壞', '除外'] });
  assert.strictEqual(panel.count(), '1');
  panel.click('除外');
  assert.deepStrictEqual(panel.read(), { actions: ['破壞'] });
});

test('寫進面板的條件原樣讀得回來(還原瀏覽紀錄走這條)', () => {
  const { panel } = open({ cards: CARDS, action: ACTION });
  panel.init();
  panel.write(FULL);
  assert.deepStrictEqual(panel.read(), FULL);
  panel.finishLoading();
  assert.deepStrictEqual(panel.read(), FULL);
  assert.deepStrictEqual(panel.selected(), ['墓地', '我方', '手牌', '不限哪一方', '效果', '對手的']);
  panel.write({ actions: ['破壞'], target: 'this_card' });
  assert.deepStrictEqual(panel.read(), { actions: ['破壞'], target: 'this_card' });
});

test('清除條件:動作詞、區域、段類別、極性、誰、受方、原因、開關、被動作的卡都回到預設', () => {
  const { panel } = loadedPage();
  panel.write(FULL);
  panel.clear();
  assert.strictEqual(panel.read(), null);
  assert.strictEqual(panel.count(), '');
  assert.deepStrictEqual(panel.checkboxes().map(c => [c.label, c.checked]),
                         [['效果', true], ['代價', true], ['觸發條件', false], ['含不限定的', false]]);
  assert.deepStrictEqual(panel.selected(), ['不限', '不限哪一方', '不限', '不限哪一方', '不限',
                                            '不限哪一方']);
});

test('段類別至少勾一個:只剩一個時取消不掉', () => {
  const { panel } = loadedPage();
  panel.write({ actions: ['破壞'], kinds: ['cost'] });
  assert.deepStrictEqual(panel.checkboxes().find(c => c.label === '代價'),
                         { label: '代價', checked: true, disabled: true });
  panel.toggle('代價');
  assert.deepStrictEqual(panel.read().kinds, ['cost']);
  panel.toggle('觸發條件');
  assert.deepStrictEqual(panel.read().kinds, ['cost', 'cond']);
  panel.toggle('代價');
  assert.deepStrictEqual(panel.read().kinds, ['cond']);
  panel.toggle('觸發條件');
  assert.deepStrictEqual(panel.read().kinds, ['cond']);
});
