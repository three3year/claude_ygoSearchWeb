/**
 * render.js — 呈現層(卡片清單、卡文逐效果句分行、分頁)
 *
 * **資料流單向**:要顯示的卡片清單進來,畫面出去;渲染沒有內部記憶,行為完全由
 * 參數與這一層自己擁有的呈現狀態決定。分頁位置與每頁筆數歸這一層所有——兩邊都
 * 寫得到的狀態等於沒有擁有者。
 *
 * 採**全量重繪**:本站有分頁,單次渲染量只有一頁。差異更新需要「知道上一次渲染了
 * 什麼」,那是把耦合換個名字留下來。
 */
'use strict';

const View = (() => {
const { CAT_ZH, KIND_ZH, $, esc, pad8 } = Util;

/* 呈現狀態:與資料無關的兩件事。唯一的擁有者是這個模組。 */
const state = { page: 1, perPage: 50 };

/* 上一次要顯示的卡片清單——render() 由此重繪,但沒有人從外面寫入它 */
let lastCards = [];

function render(cards = lastCards) {
  lastCards = cards;
  const per = state.perPage;
  const total = cards.length;
  const pages = Math.max(1, Math.ceil(total / per));
  const page = Math.min(Math.max(1, state.page), pages);
  state.page = page;
  $('resultInfo').textContent = total
    ? `共 ${total} 張，第 ${page}/${pages} 頁`
    : '沒有符合條件的卡片';

  const slice = cards.slice((page - 1) * per, page * per);
  $('results').innerHTML = slice.map(cardHtml).join('');
  renderPager('pagerTop', pages, page);
  renderPager('pagerBottom', pages, page);
}

function cardHtml(c) {
  return `<article class="card" data-cid="${c.id}">
    <div class="card-head">
      <span class="card-name">${esc(c.n)}</span>
      <span class="card-id">${pad8(c.id)}</span>
      <span class="card-cat">${esc(CAT_ZH[c.c] || c.c)}</span>
    </div>
    ${c.nj || c.ne ? `<div class="card-names">${
      esc([c.nj, c.ne].filter(Boolean).join('｜'))}</div>` : ''}
    <div class="card-text">${cardText(c)}</div>
  </article>`;
}

/* 卡文逐效果句分行。沒有效果句的純通常怪獸顯示故事文並淡化——689 張這類卡不是
   資料缺漏,只是它們真的沒有效果。 */
function cardText(c) {
  if (!c.tx || !c.tx.length) {
    return c.d ? `<p class="eff flavor">${body(c.d)}</p>` : '';
  }
  const lines = c.tx.map((t, i) => {
    const kind = c.k && c.k[i] ? KIND_ZH[c.k[i]] || c.k[i] : '';
    return `<p class="eff" data-ei="${i}">${
      kind ? `<span class="eff-kind">${esc(kind)}</span>` : ''}${body(t)}</p>`;
  });
  return lines.join('') + (c.d ? `<p class="eff flavor">${body(c.d)}</p>` : '');
}

/* ● 選項換行(開頭的●與已經換過行的●不重複換)＋ 原文換行照顯示 */
function body(text) {
  return esc(text)
    .replace(/(?!^)(?<!\n)●/g, '<br>●')
    .replace(/\n/g, '<br>');
}

function renderPager(id, pages, page) {
  const el = $(id);
  if (pages <= 1) { el.innerHTML = ''; return; }
  const btn = (p, label, cls = '') =>
    `<button data-p="${p}" class="${cls}${p === page ? ' cur' : ''}">${label}</button>`;
  const parts = [btn(Math.max(1, page - 1), '‹ 上一頁')];
  const win = [];
  for (let p = 1; p <= pages; p++) {
    if (p <= 2 || p > pages - 2 || Math.abs(p - page) <= 2) win.push(p);
  }
  let last = 0;
  for (const p of win) {
    if (p - last > 1) parts.push('<span class="dots">…</span>');
    parts.push(btn(p, p));
    last = p;
  }
  parts.push(btn(Math.min(pages, page + 1), '下一頁 ›'));
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

/* 換頁後捲回結果頂端:看完一頁不必自己找回去 */
function goto(page) {
  state.page = page;
  render();
  window.scrollTo({ top: $('pagerTop').offsetTop - 60, behavior: 'smooth' });
}

  /* state 關在閉包裡:讀寫都走具名函式,繞過「換每頁筆數要回到第 1 頁」這條
     不變式的第二條路徑(View.state.page = …)從結構上不存在 */
  return Object.freeze({
    render,
    page: () => state.page,
    perPage: () => state.perPage,
    setPage(p) { state.page = p; },
    setPerPage(n) { state.perPage = n; state.page = 1; },
  });
})();
