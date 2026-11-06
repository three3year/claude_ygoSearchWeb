'use strict';

const View = (() => {
const { DB, META, CAT_ZH, KIND_ZH, ATTR_ZH, RACE_ZH, ROLE_ZH, OPT_ZH, OT_ZH,
        LM_ZH, LM_CODES, SUB_ZH, BAN_ZH, $, esc, pad8, byId } = Util;

/* 卡圖:salix5/query-data 的 CDN,檔名就是不補零的卡片密碼 */
const PIC = 'https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/';
const QUERY = 'https://salix5.github.io/query/?code=';
const MAT_KINDS = ['ritual', 'fusion', 'synchro', 'xyz', 'link'];

const state = { page: 1, perPage: 100,
                sortKey: Sort.KEYS[0].key, sortDir: Sort.KEYS[0].dir };

let lastResult = null;

let paintSort = () => {};

function setSort(key, dir) {
  const spec = Sort.specOf(key);
  state.sortKey = spec.key;
  state.sortDir = spec.dir ? (dir || spec.dir) : '';
  state.page = 1;
  paintSort();
}

const MARK_ZH = {
  text: () => '',
  kind: (c, i) => KIND_ZH[(c.k || [])[i]],
  opt: (c, i) => OPT_ZH[(c.o || [])[i]],
};

function highlight(marks) {
  if (!marks || !marks.length) return null;
  const text = marks.find(m => m.type === 'text');
  return { parts: text ? Engine.likeParts(text.value) : [], marks };
}

function badgeText(marks, c, i) {
  return marks.map(m => (MARK_ZH[m.type] || (() => m.type))(c, i))
    .filter(Boolean).join('・');
}

function render(result = lastResult) {
  lastResult = result;
  if (!result) return renderIdle();
  const entries = Sort.sort(result.cards, state.sortKey, state.sortDir);
  const per = state.perPage;
  const total = entries.length;
  const pages = Math.max(1, Math.ceil(total / per));
  const page = Math.min(Math.max(1, state.page), pages);
  state.page = page;
  $('resultInfo').textContent = total
    ? `共 ${total} 張，第 ${page}/${pages} 頁`
    : '沒有符合條件的卡片';

  const hl = highlight(result.marks);
  const slice = entries.slice((page - 1) * per, page * per);
  $('results').innerHTML = slice.map(e => cardHtml(e, hl)).join('');
  renderPager('pagerTop', pages, page);
  renderPager('pagerBottom', pages, page);
}

function renderIdle() {
  $('resultInfo').textContent = '';
  $('results').innerHTML = `<div class="idle">
    <p class="idle-title">設定條件後按「搜尋」</p>
  </div>`;
  renderPager('pagerTop', 1, 1);
  renderPager('pagerBottom', 1, 1);
}

function cardHtml(e, hl) {
  const c = e.card;
  const names = [c.nj, c.ne, c.ax ? '※' + c.ax : ''].filter(Boolean);
  return `<article class="card" data-cid="${c.id}">
    <div class="card-pic">
      ${imgHtml(c.id)}
      ${altNavHtml(c)}
    </div>
    <div class="card-body">
      <div class="card-head">
        <a class="card-name" href="${QUERY}${c.id}"
           target="_blank" rel="noopener">${esc(c.n)}</a>
        ${c.ra ? `<span class="card-rarity ra-${esc(c.ra)}"
           title="Master Duel 稀有度">${esc(c.ra)}</span>` : ''}
        ${otHtml(c)}
        <span class="card-id">${pad8(c.id)}</span>
        ${ogBtnHtml(c)}
      </div>
      ${names.length
        ? `<div class="card-names">${esc(names.join('｜'))}</div>` : ''}
      ${banHtml(c)}
      ${printHtml(c)}
      ${metaHtml(c)}
      <div class="card-text">${cardText(c, e.rows, hl)}</div>
      ${ogTextHtml(c)}
    </div>
  </article>`;
}

/* decoding="async":懶載入的圖在快速捲動途中陸續抵達,同步解碼會綁在繪製幀裡
   ——中鍵自動捲動由主執行緒驅動,那正是「一卡一卡」的來源之一。 */
function imgHtml(id) {
  return `<img class="card-img" loading="lazy" decoding="async"
    width="180" height="262" alt=""
    src="${PIC}${id}.jpg" onerror="this.style.visibility='hidden'">`;
}

function altNavHtml(c) {
  if (!c.al || !c.al.length) return '';
  return `<div class="alt-nav" data-i="0">
    <button type="button" data-step="-1" aria-label="上一個卡圖">‹</button>
    <span class="alt-n">1/${c.al.length + 1}</span>
    <button type="button" data-step="1" aria-label="下一個卡圖">›</button>
  </div>`;
}

function ogBtnHtml(c) {
  if (!c.og && !c.ow) return '';
  const title = c.og
    ? '此卡卡文經本站勘誤,點一下對照勘誤前的來源原文(差異會標示出來)'
    : '此卡卡文經本站改寫成新格式,點一下對照查牌網舊譯全文';
  return `<button type="button" class="og-toggle" aria-pressed="false"
    title="${title}">顯示查牌網原文</button>`;
}

function ogTextHtml(c) {
  if (!c.og && !c.ow) return '';
  const seg = c.og
    ? c.og.map(([op, t]) => {
        if (op === '-') return `<del class="og-del" title="查牌網原文有這段,本站勘誤後刪去">${esc(t)}</del>`;
        if (op === '+') return `<ins class="og-add" title="本站勘誤後補上,查牌網原文沒有這段">${esc(t)}</ins>`;
        return esc(t);
      }).join('')
    : esc(c.ow);
  return `<div class="card-text og-text" hidden>${seg}</div>`;
}

function otHtml(c) {
  if (!c.ot || c.ot === 'b') return '';
  return `<span class="card-ot ot-${esc(c.ot)}"
    title="${esc(OT_ZH[c.ot] || c.ot)}">${esc(OT_ZH[c.ot] || c.ot)}</span>`;
}

const BAN_FORMATS = [
  { key: 'bo', zh: 'OCG', released: c => c.ot !== 't' },
  { key: 'bt', zh: 'TCG', released: c => c.ot !== 'o' },
  { key: 'bm', zh: 'MD', released: c => c.ra != null },
];
const BAN_ICON_NUM = { f: '', l: '1', s: '2' };
function banCell(c, f) {
  const code = c[f.key];
  const zh = code ? (BAN_ZH[f.key][code] || code)
    : f.released(c) ? '無限制' : '未發行';
  const body = code
    ? `<i class="ban-ico ban-${code}">${BAN_ICON_NUM[code]}</i>`
    : '<span class="ban-plain">-</span>';
  return `<span class="ban-cell" title="${esc(f.zh)} ${esc(zh)}">${
    esc(f.zh)} : ${body}</span>`;
}
function banHtml(c) {
  if (!BAN_FORMATS.some(f => c[f.key])) return '';
  return `<div class="card-ban">${BAN_FORMATS.map(f => banCell(c, f))
    .join('<span class="ban-sep">/</span>')}</div>`;
}

function printHtml(c) {
  if (!c.gy) return '';
  return `<div class="card-print"><span class="card-gy">Genesys ${c.gy}</span></div>`;
}

function metaHtml(c) {
  const sub = SUB_ZH[c.c] || {};
  const lines = [`<div>${esc(
    [CAT_ZH[c.c] || c.c, ...(c.s || []).map(x => sub[x] || x)].join('／'))}</div>`];
  if (c.c === 'm') {
    lines.push(`<div>${esc([
      levelText(c),
      ATTR_ZH[c.at],
      RACE_ZH[c.r],
      c.sc == null ? '' : '刻度' + c.sc,
    ].filter(Boolean).join('／'))}</div>`);
    lines.push(`<div>攻${stat(c.atk)}${
      c.lk == null ? `／守${stat(c.df)}` : ''}</div>`);
  }
  return `<div class="card-meta">
    <div class="meta-lines">${lines.join('')}</div>
    ${lmGridHtml(c)}
  </div>`;
}

function levelText(c) {
  if (c.lk != null) return 'LINK-' + c.lk;
  if (c.lv == null) return '';
  return ((c.s || []).includes('xyz') ? '☆' : '★') + c.lv;
}

function stat(v) {
  return v == null || v < 0 ? '?' : v;
}

function lmGridHtml(c) {
  if (!c.lm) return '';
  const cells = [...LM_CODES.slice(0, 4), '', ...LM_CODES.slice(4)];
  return `<span class="lm-grid" title="連結標記">${cells.map(k => k
    ? `<i class="${c.lm.includes(k) ? 'on' : ''}">${esc(LM_ZH[k])}</i>`
    : `<b>${c.lk == null ? '' : c.lk}</b>`).join('')}</span>`;
}

function cardText(c, rows, hl) {
  const flavor = c.d ? `<p class="eff flavor">${lineHtml(c.d)}</p>` : '';
  const tx = c.tx || [];
  const line = (t, i) => effHtml(c, t, i, rows, hl);
  if (!(c.s || []).includes('pendulum')) return tx.map(line).join('') + flavor;

  const pend = new Set(c.pz || []);
  const pendLines = [], monLines = [];
  tx.forEach((t, i) => (pend.has(i) ? pendLines : monLines).push(line(t, i)));
  let out = group('【靈擺效果】',
                  pendLines.join('') || '<p class="eff empty">（無）</p>', false);
  if (monLines.length) out += group('【怪獸效果】', monLines.join(''), true);
  if (flavor) out += group('【怪獸敘述】', flavor, true);
  return out;
}

function group(label, lines, divider) {
  return `${divider ? '<hr class="pend-divider">' : ''}
    <div class="eff-group-label">${label}</div>${lines}`;
}

function effHtml(c, text, i, rows, hl) {
  const role = (c.ro && c.ro[i]) || '';
  const kind = (c.k && c.k[i]) || '';
  const labels = (role ? [ROLE_ZH[role]]
    : [KIND_ZH[kind] || kind, OPT_ZH[(c.o || [])[i]]]).filter(Boolean);
  const hit = !!rows && rows.indexOf(i) >= 0;
  const ranges = hit && hl && hl.parts.length
    ? Engine.likeRanges(text, hl.parts) : null;
  const badge = hit ? badgeText(hl.marks, c, i) : '';
  return `<p class="eff${roleClass(c, role)}${hit ? ' hit' : ''}" data-ei="${i}">${
    badge ? `<span class="eff-hit">${esc(badge)}</span>` : ''}${
    lineHtml(text, ranges)}${
    labels.length ? `<span class="eff-kinds">${labels.map(t =>
      `<span class="eff-kind">${esc(t)}</span>`).join('')}</span>` : ''}</p>`;
}

function roleClass(c, role) {
  if (!role) return '';
  if (role !== 'mat') return ' role-' + role;
  const method = MAT_KINDS.find(k => (c.s || []).includes(k));
  return ' role-mat' + (method ? ' mat-' + method : '');
}

function lineHtml(text, ranges) {
  const starts = {}, ends = {};
  (ranges || []).forEach(r => { starts[r[0]] = 1; ends[r[1]] = 1; });
  let out = '';
  for (let i = 0; i < text.length; i++) {
    if (ends[i]) out += '</mark>';
    if (starts[i]) out += '<mark class="kw">';
    const ch = text[i];
    if (ch === '\n') { out += '<br>'; continue; }
    if (ch === '●' && i > 0 && text[i - 1] !== '\n') out += '<br>';
    out += esc(ch);
  }
  return out + (ends[text.length] ? '</mark>' : '');
}

function initEffKind() {
  $('results').addEventListener('click', e => {
    const p = e.target.closest('.eff');
    if (!p || !p.querySelector('.eff-kind')) return;
    p.classList.toggle('show-kind');
  });
}

function initOgToggle() {
  $('results').addEventListener('click', e => {
    const btn = e.target.closest('.og-toggle');
    if (!btn) return;
    const art = btn.closest('article.card');
    const on = btn.getAttribute('aria-pressed') !== 'true';
    btn.setAttribute('aria-pressed', on);
    btn.textContent = on ? '隱藏查牌網原文' : '顯示查牌網原文';
    art.querySelector('.card-text').hidden = on;
    art.querySelector('.og-text').hidden = !on;
  });
}

function initSort(onChange) {
  const keySel = $('sortKey');
  const dirBtn = $('sortDir');
  keySel.innerHTML = Sort.KEYS.map(k =>
    `<option value="${esc(k.key)}">${esc(k.zh)}</option>`).join('');
  paintSort = () => {
    keySel.value = state.sortKey;
    dirBtn.hidden = !Sort.specOf(state.sortKey).dir;
    dirBtn.textContent = state.sortDir === 'desc' ? '↓ 降序' : '↑ 升序';
    dirBtn.title = state.sortDir === 'desc'
      ? '目前是降序（點一下改升序）' : '目前是升序（點一下改降序）';
  };
  const changed = () => { render(); if (onChange) onChange(); };
  keySel.addEventListener('change', () => {
    setSort(keySel.value, Sort.specOf(keySel.value).dir);
    changed();
  });
  dirBtn.addEventListener('click', () => {
    setSort(state.sortKey, state.sortDir === 'desc' ? 'asc' : 'desc');
    changed();
  });
  paintSort();
}

/* 換 src 時瀏覽器會留著舊圖直到新圖載完,CDN 慢的時候按了像沒按——所以按下
   的瞬間把舊圖調淡,新圖到了再恢復。 */
function initAltArt() {
  $('results').addEventListener('click', e => {
    const btn = e.target.closest('.alt-nav button');
    if (!btn) return;
    const nav = btn.closest('.alt-nav');
    const art = nav.closest('article.card');
    const card = byId(art.dataset.cid);
    if (!card) return;
    const ids = [card.id, ...(card.al || [])];
    const step = +btn.dataset.step;
    const i = (+nav.dataset.i + step + ids.length) % ids.length;
    nav.dataset.i = i;
    nav.querySelector('.alt-n').textContent = `${i + 1}/${ids.length}`;
    const img = art.querySelector('.card-img');
    img.style.visibility = '';
    img.classList.add('img-loading');
    const done = () => img.classList.remove('img-loading');
    img.addEventListener('load', done, { once: true });
    img.addEventListener('error', done, { once: true });
    img.src = PIC + ids[i] + '.jpg';
    new Image().src = PIC + ids[(i + step + ids.length) % ids.length] + '.jpg';
  });
}

function pagerWin(el) {
  if (typeof getComputedStyle !== 'function') return 2;
  const n = parseInt(getComputedStyle(el).getPropertyValue('--pg-win'), 10);
  return n > 0 ? n : 2;
}

function renderPager(id, pages, page) {
  const el = $(id);
  if (pages <= 1) { el.innerHTML = ''; return; }
  const w = pagerWin(el);
  const btn = (p, label, cls = '') =>
    `<button data-p="${p}" class="${cls}${p === page ? ' cur' : ''}">${label}</button>`;
  const nav = zh => `<span class="pg-txt">${zh}</span>`;
  const parts = [btn(Math.max(1, page - 1), '‹ ' + nav('上一頁'))];
  const win = [];
  for (let p = 1; p <= pages; p++) {
    if (p <= w || p > pages - w || Math.abs(p - page) <= w) win.push(p);
  }
  let last = 0;
  for (const p of win) {
    if (p - last > 1) parts.push('<span class="dots">…</span>');
    parts.push(btn(p, p));
    last = p;
  }
  parts.push(btn(Math.min(pages, page + 1), nav('下一頁') + ' ›'));
  parts.push(`<span class="page-jump"><input type="number" min="1" max="${pages}"
    placeholder="頁碼" aria-label="跳至頁碼">/${pages}</span>`);
  el.innerHTML = parts.join('');
  el.onclick = e => {
    const b = e.target.closest('button');
    if (!b) return;
    goto(+b.dataset.p);
  };
  const jump = el.querySelector('.page-jump input');
  jump.addEventListener('keydown', e => {
    if (e.key !== 'Enter' || !jump.value) return;
    goto(Math.min(pages, Math.max(1, +jump.value || 1)));
  });
}

function goto(page) {
  state.page = page;
  render();
  window.scrollTo(0, $('pagerTop').offsetTop - 60);
}

  return Object.freeze({
    render, initAltArt, initEffKind, initOgToggle, initSort,
    cardHtml,
    page: () => state.page,
    perPage: () => state.perPage,
    sort: () => ({ key: state.sortKey, dir: state.sortDir }),
    setPage(p) { state.page = p; },
    setPerPage(n) { state.perPage = n; state.page = 1; },
    setSort,
  });
})();
