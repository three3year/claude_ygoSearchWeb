'use strict';

const ActionPanel = (() => {
const { $, esc, DB, byId } = Util;

const SRC = 'action-data.js';

let index = null;
let failed = false;
let loading = null;
let selected = [];
let targetMode = 'none';
let targetCard = null;
let typed = '';
let given = {};
let setTyped = '';
let moreOpen = false;
const NO_ZONE = () => ({ zone: '', side: '' });
let from = NO_ZONE();
let to = NO_ZONE();
let kinds = Action.DEFAULT_KINDS;
let pol = Action.DEFAULT_POL;

const KIND_LABELS = { eff: '效果', cost: '代價', cond: '觸發條件' };
const POL_LABELS = { do: '會做', limit: '限制', resist: '抗性' };
let agent = '';
let unrestricted = false;
let recipient = '';
let cause = { kind: '', side: '' };

/* 用 `<script>` 載而不是 fetch:雙擊開啟(file://)時 fetch 會被擋(ADR-0007)。 */
function load() {
  if (loading) return loading;
  loading = new Promise(resolve => {
    const done = ok => {
      if (ok) {
        try {
          index = Action.prepare(window.ACTION_DATA, DB);
        } catch (err) {
          ok = false;
        }
        window.ACTION_DATA = undefined;
      }
      failed = !ok;
      paint();
      resolve();
    };
    const script = document.createElement('script');
    script.src = SRC;
    script.onload = () => done(!!window.ACTION_DATA);
    script.onerror = () => done(false);
    document.head.append(script);
  });
  paint();
  return loading;
}

function isOpen() {
  return $('actionHead').getAttribute('aria-expanded') === 'true';
}

function setOpen(open) {
  $('actionHead').setAttribute('aria-expanded', open ? 'true' : 'false');
  $('actionBody').hidden = !open;
  if (open) load();
}

function statusText() {
  if (failed) {
    return '動作索引載入失敗:動作條件這次不生效,其他條件照常能搜。重新整理頁面可以再試一次。';
  }
  if (loading && !index) return '動作索引載入中…';
  return '';
}

function chip(word) {
  const on = selected.indexOf(word) >= 0;
  return `<button type="button" class="tri" data-word="${esc(word)}"
    data-st="${on ? 'in' : ''}">${esc(word)}</button>`;
}

function wordsHtml() {
  const opts = Action.options(index);
  const known = opts.shown.concat(opts.more);
  const extra = moreOpen
    ? opts.more
    : opts.more.filter(w => selected.indexOf(w) >= 0);
  const unknown = selected.filter(w => known.indexOf(w) < 0);
  const toggle = opts.more.length
    ? `<button type="button" class="tri tri-more" data-more="1">${
      moreOpen ? '收起' : `更多(共 ${known.length} 個)`}</button>` : '';
  return `<span class="group-label">動作</span>
    <div class="tri-row">${opts.shown.concat(extra, unknown).map(chip).join('')}${
      toggle}</div>
    <p class="action-hint">多選時,要在同一段裡全部都有</p>`;
}

const TARGET_MODES = [['none', '不指定'], ['self', '這張卡自己'], ['card', '指定一張卡'],
                      ['cond', '給條件']];

function cardName(id) {
  const c = byId(id);
  return c ? c.n : String(id);
}

function suggestHtml() {
  return Action.suggest(DB, typed).map(c => `<button type="button" class="tri"
    data-pick="${c.id}">${esc(c.n)}${c.nj && c.nj !== c.n
      ? ` <span class="action-sub">${esc(c.nj)}</span>` : ''}</button>`).join('');
}

/* 指定卡:選中了就顯示那張卡(點了取消);還沒選就是輸入框加建議清單。 */
function cardPickHtml() {
  if (targetMode !== 'card') return '';
  if (targetCard != null) {
    return `<div class="tri-row"><button type="button" class="tri" data-st="in"
      data-unpick="1" title="取消這張卡">${esc(cardName(targetCard))} ×</button></div>`;
  }
  return `<input type="text" class="action-card-input" id="actionCardInput"
      placeholder="輸入卡名,從下面選一張" value="${esc(typed)}" autocomplete="off">
    <div class="tri-row" id="actionSuggest">${suggestHtml()}</div>`;
}

function setSuggestHtml() {
  return Action.archetypeSuggest(index, setTyped).map(a => `<button type="button" class="tri"
    data-setpick="${a.code}">${esc(a.zh)}</button>`).join('');
}

function setName(code) {
  const a = index.archetypes.find(x => x.code === code);
  return a && a.zh ? a.zh : `0x${code.toString(16)}`;
}

/* 給條件:大類、屬性、種族一列一組按鈕(單選,點已選的取消);等級、字段、卡名包含。 */
function givenHtml() {
  if (targetMode !== 'cond') return '';
  const opts = Action.conditionOptions();
  const row = (key, label) => `<span class="group-label">${label}</span>
    <div class="tri-row">${opts[key].map(e => `<button type="button" class="tri"
      data-gkey="${key}" data-gval="${esc(e.code)}" data-st="${given[key] === e.code ? 'in' : ''}">${
      esc(e.zh)}</button>`).join('')}</div>`;
  const lv = end => `<input type="number" class="range-in" data-glv="${end}" min="0" max="13"
    value="${given[end] == null ? '' : given[end]}" aria-label="等級${end === 'lvMin' ? '下限' : '上限'}">`;
  const set = given.set
    ? `<div class="tri-row"><button type="button" class="tri" data-st="in" data-setunpick="1"
        title="取消這個字段">${esc(setName(given.set))} ×</button></div>`
    : `<input type="text" class="action-card-input" id="actionSetInput"
        placeholder="輸入字段名,從下面選一個" value="${esc(setTyped)}" autocomplete="off">
      <div class="tri-row" id="actionSetSuggest">${setSuggestHtml()}</div>`;
  return `<p class="action-hint">被動作的卡要符合下面填的全部條件</p>
    ${row('cat', '大類')}${row('attr', '屬性')}${row('race', '種族')}
    <span class="group-label">等級</span>
    <div class="range-row">${lv('lvMin')}<span class="range-sep">～</span>${lv('lvMax')}</div>
    <span class="group-label">字段</span>${set}
    <span class="group-label">卡名包含</span>
    <input type="text" class="action-card-input" data-gname="1" value="${esc(given.name || '')}"
      placeholder="日文名或中文名的一部分" autocomplete="off">`;
}

function targetHtml() {
  return `<span class="group-label">被動作的卡</span>
    <p class="action-hint">這裡篩的是被動作的卡,不是有這個效果的卡</p>
    <div class="tri-row">${TARGET_MODES.map(([mode, label]) => `<button type="button"
      class="tri" data-mode="${mode}" data-st="${targetMode === mode ? 'in' : ''}">${
      label}</button>`).join('')}</div>
    ${cardPickHtml()}${givenHtml()}`;
}

const option = (value, label, cur) =>
  `<option value="${esc(value)}"${value === cur ? ' selected' : ''}>${esc(label)}</option>`;

/* 從、到:區域選項由索引的表生成;還原的區域索引裡沒有時也列出來,才看得到、取消得掉。 */
function zoneHtml(key, label, cur) {
  const zones = Action.zoneOptions(index);
  if (cur.zone && zones.indexOf(cur.zone) < 0) zones.push(cur.zone);
  return `<span class="group-label">${label}</span>
    <div class="range-row">
      <select class="range-in" data-zone="${key}">${option('', '不限', cur.zone)}${
        zones.map(z => option(z, z, cur.zone)).join('')}</select>
      <select class="range-in" data-side="${key}">${option('', '不限哪一方', cur.side)}${
        Action.SIDES.map(sd => option(sd, sd, cur.side)).join('')}</select>
    </div>`;
}

/* 段類別三個勾選:只剩一個勾著時那一個不能取消(停用)。 */
function kindsHtml() {
  return `<span class="group-label">這個動作是</span>
    <div class="tri-row">${Object.keys(KIND_LABELS).map(k => {
      const on = kinds.indexOf(k) >= 0;
      return `<label><input type="checkbox" data-kind="${k}"${on ? ' checked' : ''}${
        on && kinds.length === 1 ? ' disabled' : ''}> ${KIND_LABELS[k]}</label>`;
    }).join('')}</div>`;
}

function polHtml() {
  return `<span class="group-label">極性</span>
    <div class="tri-row">${Object.keys(POL_LABELS).map(k =>
      `<button type="button" class="tri" data-pol="${k}" data-st="${pol === k ? 'in' : ''}">${
        POL_LABELS[k]}</button>`).join('')}</div>
    <p class="action-hint">限制:不能、只能;抗性:不會被…</p>`;
}

/* 不限/我方/對手三選一的按鈕列(誰、受方共用寫法)。 */
function sideButtons(key, cur) {
  const opt = (value, label) => `<button type="button" class="tri" data-${key}="${value}"
    data-st="${cur === value ? 'in' : ''}">${label}</button>`;
  return `<div class="tri-row">${opt('', '不限')}${opt('我方', '我方')}${opt('對手', '對手')}</div>`;
}

/* 誰(票 10):不限/我方/對手三選一。 */
function agentHtml() {
  return `<span class="group-label">誰做的</span>${sideButtons('agent', agent)}`;
}

/* 受方(票 11):不限/我方/對手三選一;只比受方是玩家的段。 */
function recipientHtml() {
  return `<span class="group-label">落在誰身上</span>${sideButtons('recipient', recipient)}
    <p class="action-hint">例如傷害、回復落在哪一方;受方是卡的不算</p>`;
}

/* 原因(票 11):種類的選項由索引的原因表生成;還原的種類索引裡沒有時也列出來。 */
function causeHtml() {
  const kinds = Action.causeOptions(index);
  if (cause.kind && kinds.indexOf(cause.kind) < 0) kinds.push(cause.kind);
  return `<span class="group-label">因為什麼</span>
    <div class="range-row">
      <select class="range-in" data-cause-kind="1">${option('', '不限', cause.kind)}${
        kinds.map(k => option(k, k, cause.kind)).join('')}</select>
      <select class="range-in" data-cause-side="1">${option('', '不限哪一方', cause.side)}${
        Action.SIDES.map(sd => option(sd, `${sd}的`, cause.side)).join('')}</select>
    </div>`;
}

/* 「含不限定的」勾選(票 10,預設關;票 11 起誰與原因共用)。 */
function unrestrictedHtml() {
  return `<label class="mat-toggle"
      title="卡文沒寫是誰的觸發條件與被動句(例如「モンスターが手札に戻った場合」)、沒寫原因的被動句(例如「破壊された場合」)也算">
      <input type="checkbox" data-unrestricted="1"${unrestricted ? ' checked' : ''}>含不限定的
    </label>`;
}

function fieldsHtml() {
  return index
    ? wordsHtml() + zoneHtml('from', '從哪裡', from) + zoneHtml('to', '到哪裡', to)
      + targetHtml() + kindsHtml() + polHtml() + agentHtml() + recipientHtml() + causeHtml()
      + unrestrictedHtml()
    : '';
}

function paintCount() {
  const n = Action.count(read());
  $('actionCount').textContent = n ? String(n) : '';
}

function paint() {
  const status = statusText();
  $('actionStatus').textContent = status;
  $('actionStatus').hidden = !status;
  $('actionFields').innerHTML = fieldsHtml();
  paintCount();
}

const zoneCond = z => (z.zone ? { zone: z.zone, side: z.side } : null);

function target() {
  if (targetMode === 'self') return 'self';
  if (targetMode === 'card' && targetCard != null) return { card: targetCard };
  if (targetMode === 'cond') return { condition: given };
  return null;
}

function read() {
  return Action.condOf({ actions: selected, from: zoneCond(from), to: zoneCond(to), kinds, pol,
                         agent, unrestricted, target: target(), recipient,
                         cause: cause.kind ? { kind: cause.kind, side: cause.side } : null });
}

/* 還原帶動作條件的查詢時展開區塊(和其他軸一樣看得見設了什麼),也就載入索引。 */
function write(act) {
  const cond = Action.condOf(act) || {};
  selected = cond.actions || [];
  from = { ...NO_ZONE(), ...cond.from };
  to = { ...NO_ZONE(), ...cond.to };
  kinds = cond.kinds || Action.DEFAULT_KINDS;
  pol = cond.pol || Action.DEFAULT_POL;
  agent = cond.agent || '';
  unrestricted = !!cond.unrestricted;
  recipient = cond.recipient || '';
  cause = { kind: '', side: '', ...cond.cause };
  const t = cond.target;
  targetMode = t === 'self' ? 'self' : t && t.condition ? 'cond' : t ? 'card' : 'none';
  targetCard = t && t.card != null ? t.card : null;
  given = t && t.condition ? { ...t.condition } : {};
  typed = '';
  setTyped = '';
  if (Object.keys(cond).length) setOpen(true);
  paint();
}

/* 「清除條件」:動作詞取消,從、到、段類別、極性、誰、受方、原因、「含不限定的」、被動作的卡
   (含給條件)回到預設。 */
function clear() {
  selected = [];
  agent = '';
  recipient = '';
  cause = { kind: '', side: '' };
  unrestricted = false;
  from = NO_ZONE();
  to = NO_ZONE();
  kinds = Action.DEFAULT_KINDS;
  pol = Action.DEFAULT_POL;
  targetMode = 'none';
  targetCard = null;
  typed = '';
  given = {};
  setTyped = '';
  paint();
}

function init() {
  $('actionHead').addEventListener('click', () => setOpen(!isOpen()));
  $('actionFields').addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.more) {
      moreOpen = !moreOpen;
    } else if (btn.dataset.mode) {
      targetMode = btn.dataset.mode;
    } else if (btn.dataset.pick) {
      targetCard = Number(btn.dataset.pick);
    } else if (btn.dataset.unpick) {
      targetCard = null;
    } else if (btn.dataset.gkey) {
      const key = btn.dataset.gkey;
      if (given[key] === btn.dataset.gval) delete given[key];
      else given[key] = btn.dataset.gval;
    } else if (btn.dataset.setpick) {
      given.set = Number(btn.dataset.setpick);
    } else if (btn.dataset.setunpick) {
      delete given.set;
      setTyped = '';
    } else if (btn.dataset.pol) {
      pol = btn.dataset.pol;
    } else if (btn.dataset.agent !== undefined) {
      agent = btn.dataset.agent;
    } else if (btn.dataset.recipient !== undefined) {
      recipient = btn.dataset.recipient;
    } else if (btn.dataset.word) {
      const word = btn.dataset.word;
      selected = selected.indexOf(word) >= 0
        ? selected.filter(w => w !== word) : selected.concat(word);
    }
    paint();
  });
  $('actionFields').addEventListener('input', e => {
    const el = e.target;
    if (el.id === 'actionCardInput') {
      typed = el.value;
      $('actionSuggest').innerHTML = suggestHtml();
    } else if (el.id === 'actionSetInput') {
      setTyped = el.value;
      $('actionSetSuggest').innerHTML = setSuggestHtml();
    } else if (el.dataset.glv) {
      const v = el.value.trim() === '' ? NaN : Number(el.value);
      if (Number.isInteger(v)) given[el.dataset.glv] = v;
      else delete given[el.dataset.glv];
      paintCount();
    } else if (el.dataset.gname) {
      given.name = el.value;
      paintCount();
    }
  });
  $('actionFields').addEventListener('change', e => {
    const el = e.target;
    if (el.dataset.zone) {
      const z = el.dataset.zone === 'from' ? from : to;
      z.zone = el.value;
    } else if (el.dataset.side) {
      const z = el.dataset.side === 'from' ? from : to;
      z.side = el.value;
    } else if (el.dataset.kind) {
      kinds = Action.toggleKind(kinds, el.dataset.kind);
    } else if (el.dataset.unrestricted) {
      unrestricted = el.checked;
    } else if (el.dataset.causeKind) {
      cause.kind = el.value;
    } else if (el.dataset.causeSide) {
      cause.side = el.value;
    } else {
      return;
    }
    paint();
  });
  paint();
}

  return Object.freeze({
    init, load, read, write, clear,
    index: () => index,
    failed: () => failed,
  });
})();
