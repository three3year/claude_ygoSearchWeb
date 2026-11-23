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

function fieldsHtml() {
  return index ? wordsHtml() : '';
}

function paint() {
  const status = statusText();
  $('actionStatus').textContent = status;
  $('actionStatus').hidden = !status;
  $('actionFields').innerHTML = fieldsHtml();
  const n = selected.length;
  $('actionCount').textContent = n ? String(n) : '';
}

function read() {
  return Action.condOf({ actions: selected });
}

/* 還原帶動作條件的查詢時展開區塊(和其他軸一樣看得見設了什麼),也就載入索引。 */
function write(act) {
  const cond = Action.condOf(act);
  selected = cond ? cond.actions : [];
  if (cond) setOpen(true);
  paint();
}

function clear() {
  selected = [];
  paint();
}

function init() {
  $('actionHead').addEventListener('click', () => setOpen(!isOpen()));
  $('actionFields').addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.more) {
      moreOpen = !moreOpen;
    } else if (btn.dataset.word) {
      const word = btn.dataset.word;
      selected = selected.indexOf(word) >= 0
        ? selected.filter(w => w !== word) : selected.concat(word);
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
