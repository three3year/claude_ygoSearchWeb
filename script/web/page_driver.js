/**
 * page_driver.js — 接縫 3 的頁面驅動(零 npm 依賴)
 *
 * 在 frontend_harness 的沙箱裡放一份假 DOM:元素照 id 留著、事件照型別記下來,
 * 測試就能像使用者那樣按按鈕、勾選、讀畫面上的字。控制項照看得到的字找(按鈕上的字、
 * 勾選框的標籤、選單的選項),不照 class 或結構——測試只斷言使用者看得到的東西,
 * 改版面不會讓測試跟著壞。
 *
 * 動作索引不預先放進沙箱:`ActionPanel.load()` 插進來的 `<script>` 等測試呼叫
 * `finishLoading()` 才算載完,這樣測得到「載入中」那一段。
 */
'use strict';

const vm = require('node:vm');
const harness = require('./frontend_harness.js');

class FakeElement {
  constructor(id) {
    this.id = id;
    this.innerHTML = '';
    this.textContent = '';
    this.hidden = false;
    this.value = '';
    this.checked = false;
    this.dataset = {};
    this.style = {};
    this.attributes = {};
    this.listeners = {};
    this.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };
  }

  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  removeEventListener() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return name in this.attributes ? this.attributes[name] : null; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  closest() { return null; }
  append() {}
  appendChild() {}
  focus() {}
  scrollIntoView() {}

  dispatch(type, target) {
    (this.listeners[type] || []).forEach(fn => fn({ target, preventDefault() {} }));
  }
}

const ENTITIES = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"' };
const decode = s => s.replace(/&(amp|lt|gt|quot);/g, m => ENTITIES[m]);
const strip = html => decode(html.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim();

function attrsOf(text) {
  const out = {};
  for (const m of text.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) {
    out[m[1]] = m[2] === undefined ? true : decode(m[2]);
  }
  return out;
}

function datasetOf(attrs) {
  const out = {};
  for (const [name, value] of Object.entries(attrs)) {
    if (name.startsWith('data-')) {
      out[name.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = value;
    }
  }
  return out;
}

function buttonsIn(html) {
  return Array.from(html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g),
                    m => ({ text: strip(m[2]), attrs: attrsOf(m[1]) }));
}

function checkboxesIn(html) {
  return Array.from(html.matchAll(/<label\b[^>]*>([\s\S]*?)<\/label>/g), m => {
    const input = /<input\b([^>]*)>/.exec(m[1]);
    const attrs = input ? attrsOf(input[1]) : {};
    return { label: strip(m[1]), attrs, checked: !!attrs.checked, disabled: !!attrs.disabled };
  }).filter(c => c.attrs.type === 'checkbox');
}

function selectsIn(html) {
  return Array.from(html.matchAll(/<select\b([^>]*)>([\s\S]*?)<\/select>/g), m => ({
    attrs: attrsOf(m[1]),
    options: Array.from(m[2].matchAll(/<option\b([^>]*)>([\s\S]*?)<\/option>/g), o => {
      const attrs = attrsOf(o[1]);
      return { value: attrs.value, text: strip(o[2]), selected: !!attrs.selected };
    }),
  }));
}

function open({ cards = [], vocab = {}, meta = {}, action = null } = {}) {
  const elements = new Map();
  const scripts = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, new FakeElement(id));
    return elements.get(id);
  };
  const document = {
    getElementById: element,
    createElement: () => new FakeElement(null),
    head: { append: el => scripts.push(el) },
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
    body: new FakeElement('body'),
  };
  const sandbox = harness.load({ cards, vocab, meta, document });
  const run = code => vm.runInContext(code, sandbox);
  const json = code => JSON.parse(run(`JSON.stringify(${code}) || "null"`));
  const fields = () => element('actionFields').innerHTML;
  const shown = el => (el.hidden ? '' : (el.textContent || strip(el.innerHTML)));

  const panel = {
    init: () => run('ActionPanel.init()'),
    open: () => element('actionHead').dispatch('click', element('actionHead')),
    /** 動作索引的 `<script>` 載完(還沒載完時面板顯示「載入中」) */
    finishLoading() {
      if (typeof action === 'string') run(action);
      else sandbox.ACTION_DATA = action;
      scripts.splice(0).forEach(s => s.onload());
    },
    loaded: () => run('ActionPanel.index() !== null'),
    status: () => shown(element('actionStatus')),
    count: () => element('actionCount').textContent,
    read: () => json('ActionPanel.read()'),
    write: act => run(`ActionPanel.write(${JSON.stringify(act)})`),
    clear: () => run('ActionPanel.clear()'),
    buttons: () => buttonsIn(fields()).map(b => b.text),
    checkboxes: () => checkboxesIn(fields()).map(({ label, checked, disabled }) =>
      ({ label, checked, disabled })),
    selects: () => selectsIn(fields()).map(s => s.options.map(o => o.text)),
    selected: () => selectsIn(fields()).map(s => (s.options.find(o => o.selected) || {}).text),
    click(text) {
      const btn = buttonsIn(fields()).find(b => b.text === text);
      if (!btn) throw new Error(`畫面上沒有「${text}」按鈕`);
      const target = { dataset: datasetOf(btn.attrs) };
      target.closest = sel => (sel === 'button' ? target : null);
      element('actionFields').dispatch('click', target);
    },
    /** 勾或取消勾選;停用的勾選框按不動(瀏覽器不會送出 change) */
    toggle(label) {
      const box = checkboxesIn(fields()).find(c => c.label === label);
      if (!box) throw new Error(`畫面上沒有「${label}」勾選框`);
      if (box.disabled) return;
      element('actionFields').dispatch('change',
        { dataset: datasetOf(box.attrs), checked: !box.checked, value: '' });
    },
  };

  const results = {
    initSort: () => run('View.initSort()'),
    /** 主程式在動作索引還沒載完時做的事 */
    loading: () => run('View.renderLoading()'),
    /** 主程式拿到結果時做的事 */
    show: (query, act) => run(`View.render(Engine.runQuery(Util.DB, ${JSON.stringify(query || {})},
      ${JSON.stringify(act || null)}, ActionPanel.index()))`),
    sortBy(key) {
      element('sortKey').value = key;
      element('sortKey').dispatch('change', element('sortKey'));
    },
    text: () => [shown(element('resultInfo')), strip(element('results').innerHTML)]
      .filter(Boolean).join(' '),
  };

  return { panel, results, sortKeys: () => json('Sort.KEYS.map(k => k.key)') };
}

module.exports = { open };
