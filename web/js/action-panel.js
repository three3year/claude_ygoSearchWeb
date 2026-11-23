'use strict';

/* 側欄的「動作搜尋」區塊(action-search-web 票 08):動作索引的載入、動作條件的輸入。

   - 動作索引是另一個檔(`action-data.js`,約 5 MB),兩種時候才載入、載過不再載:第一次展開
     這個區塊;或從瀏覽紀錄還原的查詢帶著動作條件(`write`)。用 `<script>` 載而不是 fetch:
     雙擊開啟(file://)時 fetch 會被擋(ADR-0007)。
   - 輸入的狀態只放在這裡的 `selected`,畫面照它重畫;索引還沒載完時還原的條件也先放這裡,
     載完再畫出按鈕。
   - 之後的票加的欄位(段類別、極性、從/到…)各自在 `fieldsHtml` 加一段、在 `read`/`write`
     多帶一個鍵;條件的正規形與比對在 `Action`。 */
const ActionPanel = (() => {
const { $, esc } = Util;

const SRC = 'action-data.js';

let index = null;
let failed = false;
let loading = null;
let selected = [];
let moreOpen = false;
/* 票 09:從、到({ zone, side },空字串是不限)、段類別勾選、極性。 */
const NO_ZONE = () => ({ zone: '', side: '' });
let from = NO_ZONE();
let to = NO_ZONE();
let kinds = Action.DEFAULT_KINDS;
let pol = Action.DEFAULT_POL;

const KIND_LABELS = { eff: '效果', cost: '代價', cond: '觸發條件' };
const POL_LABELS = { do: '會做', limit: '限制', resist: '抗性' };

/* 載完(或載入失敗)時 resolve,不 reject:失敗時動作條件不生效,其他條件照常查。 */
function load() {
  if (loading) return loading;
  loading = new Promise(resolve => {
    const done = ok => {
      if (ok) {
        try {
          index = Action.prepare(window.ACTION_DATA);
        } catch (err) {
          ok = false;
        }
        window.ACTION_DATA = undefined;      // 讀成比對用的形狀之後,原始的那份不必留著
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

/* 「更多」收著時,選了的詞照樣看得到(還原的條件、或展開時選的);索引裡沒有的詞
   (舊網站存的紀錄)也列出來,才取消得掉。 */
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

function fieldsHtml() {
  return index
    ? wordsHtml() + zoneHtml('from', '從哪裡', from) + zoneHtml('to', '到哪裡', to)
      + kindsHtml() + polHtml()
    : '';
}

function paint() {
  const status = statusText();
  $('actionStatus').textContent = status;
  $('actionStatus').hidden = !status;
  $('actionFields').innerHTML = fieldsHtml();
  const n = Action.count(read());
  $('actionCount').textContent = n ? String(n) : '';
}

const zoneCond = z => (z.zone ? { zone: z.zone, side: z.side } : null);

function read() {
  return Action.condOf({ actions: selected, from: zoneCond(from), to: zoneCond(to), kinds, pol });
}

/* 還原帶動作條件的查詢時展開區塊(和其他軸一樣看得見設了什麼),也就載入索引。 */
function write(act) {
  const cond = Action.condOf(act) || {};
  selected = cond.actions || [];
  from = { ...NO_ZONE(), ...cond.from };
  to = { ...NO_ZONE(), ...cond.to };
  kinds = cond.kinds || Action.DEFAULT_KINDS;
  pol = cond.pol || Action.DEFAULT_POL;
  if (Object.keys(cond).length) setOpen(true);
  paint();
}

/* 「清除條件」:動作詞取消,從、到、段類別、極性回到預設。 */
function clear() {
  selected = [];
  from = NO_ZONE();
  to = NO_ZONE();
  kinds = Action.DEFAULT_KINDS;
  pol = Action.DEFAULT_POL;
  paint();
}

function init() {
  $('actionHead').addEventListener('click', () => setOpen(!isOpen()));
  $('actionFields').addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.more) {
      moreOpen = !moreOpen;
    } else if (btn.dataset.pol) {
      pol = btn.dataset.pol;
    } else if (btn.dataset.word) {
      const word = btn.dataset.word;
      selected = selected.indexOf(word) >= 0
        ? selected.filter(w => w !== word) : selected.concat(word);
    }
    paint();
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
