/**
 * render.js — 呈現層(卡片清單、卡文逐效果句分行、分頁)
 *
 * **資料流單向**:要顯示的卡片清單進來,畫面出去;渲染沒有內部記憶,行為完全由
 * 參數與這一層自己擁有的呈現狀態決定。分頁位置與每頁筆數歸這一層所有——兩邊都
 * 寫得到的狀態等於沒有擁有者。
 *
 * 採**全量重繪**:本站有分頁,單次渲染量只有一頁。差異更新需要「知道上一次渲染了
 * 什麼」,那是把耦合換個名字留下來。唯一不走重繪的是異圖切換:它只換 <img> 的
 * src,卡片其他資訊一個字都不動——異圖是同一張卡。
 *
 * 顯示手法沿用 oldProject(F:\AiProject\oldProject)的 render.js。
 */
'use strict';

const View = (() => {
const { CAT_ZH, KIND_ZH, ATTR_ZH, RACE_ZH, ROLE_ZH, OT_ZH, LM_ZH, LM_CODES,
        SUB_ZH, $, esc, pad8, byId } = Util;

/* 卡圖:salix5/query-data 的 CDN,檔名就是不補零的卡片密碼 */
const PIC = 'https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/';
/* 卡名連到 salix5 查卡頁:要看官方卡表或裁定時的現成出口 */
const QUERY = 'https://salix5.github.io/query/?code=';
/* 素材指定行的上色依召喚法。順序即優先序——同時帶儀式與融合位元時取先宣告的 */
const MAT_KINDS = ['ritual', 'fusion', 'synchro', 'xyz', 'link'];

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
        <span class="card-id">${pad8(c.id)}</span>
      </div>
      ${names.length
        ? `<div class="card-names">${esc(names.join('｜'))}</div>` : ''}
      ${printHtml(c)}
      ${metaHtml(c)}
      <div class="card-text">${cardText(c)}</div>
    </div>
  </article>`;
}

/* 卡圖載不到時安靜隱藏:CDN 缺圖不該在畫面上留一排破圖。用 visibility 而不是
   display,位置留著,文字才不會因為某幾張缺圖而左右跳動。 */
function imgHtml(id) {
  return `<img class="card-img" loading="lazy" width="180" height="262" alt=""
    src="${PIC}${id}.jpg" onerror="this.style.visibility='hidden'">`;
}

/* 異圖切換只長在真的有異圖的 342 張卡上:其餘 13,865 張的版面不被一列沒用的
   控制項佔走。單一介面同時應付 2 版與 17 版(黑魔導),隨時看得到目前版次。 */
function altNavHtml(c) {
  if (!c.al || !c.al.length) return '';
  return `<div class="alt-nav" data-i="0">
    <button type="button" data-step="-1" aria-label="上一個卡圖">‹</button>
    <span class="alt-n">1/${c.al.length + 1}</span>
    <button type="button" data-step="1" aria-label="下一個卡圖">›</button>
  </div>`;
}

/* MD 稀有度以外的印刷面資訊:Genesys 點數、OCG・TCG 限定。
   「兩者」是 13,822 張的常態,不寫出來——只有限定才是資訊。 */
function printHtml(c) {
  const parts = [];
  if (c.gy) parts.push(`<span class="card-gy">Genesys ${c.gy}</span>`);
  if (c.ot && c.ot !== 'b') {
    parts.push(`<span class="card-ot">${esc(OT_ZH[c.ot] || c.ot)}</span>`);
  }
  return parts.length ? `<div class="card-print">${parts.join('')}</div>` : '';
}

/* 種類與參數。怪獸參數只有怪獸有——罠モンスター的種族是它變成怪獸之後的形態,
   索引裡根本沒有那些欄位(CONTEXT.md「卡片子類型」)。 */
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
    // 連結怪獸沒有守備欄:那是「沒有這個參數」,不是 `?`
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
  // 超量的是階級不是等級,卡面上畫的星星也是反白的
  return ((c.s || []).includes('xyz') ? '☆' : '★') + c.lv;
}

/* 攻守的 `?`(攻 83 張、守 54 張)以負的哨兵值存在索引裡,與 0 區分 */
function stat(v) {
  return v == null || v < 0 ? '?' : v;
}

/* 連結標記九宮格。格子的排法直接取自值域正典的宣告序(左上到右下),
   中央那格插在第 4 個之後、放連結值。 */
function lmGridHtml(c) {
  if (!c.lm) return '';
  const cells = [...LM_CODES.slice(0, 4), '', ...LM_CODES.slice(4)];
  return `<span class="lm-grid" title="連結標記">${cells.map(k => k
    ? `<i class="${c.lm.includes(k) ? 'on' : ''}">${esc(LM_ZH[k])}</i>`
    : `<b>${c.lk == null ? '' : c.lk}</b>`).join('')}</span>`;
}

/* 卡文逐效果句分行。靈擺卡依 `pz` 分區並重建段落標頭——兩段各自從 ① 開始的
   編號不分區的話會看起來像同一串。沒有效果句的純通常怪獸只有故事文並淡化:
   689 張這類卡不是資料缺漏,只是它們真的沒有效果。

   **分區與否看的是子類型而不是 `pz` 有沒有內容**:16 張靈擺卡的靈擺欄是空的
   (卡文就寫著 `【靈擺效果】【怪獸效果】` 中間什麼都沒有),照 `pz` 判的話它們會
   連一個標頭都不長,讀的人分不出剩下那幾行是靈擺欄還是怪獸欄的效果。 */
function cardText(c) {
  const flavor = c.d ? `<p class="eff flavor">${body(c.d)}</p>` : '';
  const tx = c.tx || [];
  const line = (t, i) => effHtml(c, t, i);
  if (!(c.s || []).includes('pendulum')) return tx.map(line).join('') + flavor;

  const pend = new Set(c.pz || []);
  const pendLines = [], monLines = [];
  tx.forEach((t, i) => (pend.has(i) ? pendLines : monLines).push(line(t, i)));
  let out = group('【靈擺效果】',
                  pendLines.join('') || '<p class="eff empty">（無）</p>', false);
  if (monLines.length) out += group('【怪獸效果】', monLines.join(''), true);
  // 靈擺通常怪獸(37 張)的下半段是故事文而不是效果
  if (flavor) out += group('【怪獸敘述】', flavor, true);
  return out;
}

function group(label, lines, divider) {
  return `${divider ? '<hr class="pend-divider">' : ''}
    <div class="eff-group-label">${label}</div>${lines}`;
}

/* 一行效果句。效果外文本依 `role` 分三種弱化樣式,素材指定行另依召喚法上色;
   行首的標籤寫 role(有的話)而不是「效果外文本」——8,180 行都寫同一個詞
   等於沒寫,而那三種 role 才是使用者一眼要分出來的東西。 */
function effHtml(c, text, i) {
  const role = (c.ro && c.ro[i]) || '';
  const kind = (c.k && c.k[i]) || '';
  const label = role ? ROLE_ZH[role] : (KIND_ZH[kind] || kind);
  return `<p class="eff${roleClass(c, role)}" data-ei="${i}">${
    label ? `<span class="eff-kind">${esc(label)}</span>` : ''}${body(text)}</p>`;
}

function roleClass(c, role) {
  if (!role) return '';
  if (role !== 'mat') return ' role-' + role;
  const method = MAT_KINDS.find(k => (c.s || []).includes(k));
  return ' role-mat' + (method ? ' mat-' + method : '');
}

/* ● 選項換行(開頭的●與已經換過行的●不重複換)＋ 原文換行照顯示 */
function body(text) {
  return esc(text)
    .replace(/(?!^)(?<!\n)●/g, '<br>●')
    .replace(/\n/g, '<br>');
}

/* 異圖切換:只換 <img> 的 src 與版次,不重繪卡片——異圖是同一張卡,
   換的只是卡面圖。委派在 #results 上,全量重繪不必重綁事件。 */
function initAltArt() {
  $('results').addEventListener('click', e => {
    const btn = e.target.closest('.alt-nav button');
    if (!btn) return;
    const nav = btn.closest('.alt-nav');
    const art = nav.closest('article.card');
    const card = byId(art.dataset.cid);
    if (!card) return;
    const ids = [card.id, ...(card.al || [])];
    const i = (+nav.dataset.i + +btn.dataset.step + ids.length) % ids.length;
    nav.dataset.i = i;
    nav.querySelector('.alt-n').textContent = `${i + 1}/${ids.length}`;
    const img = art.querySelector('.card-img');
    img.style.visibility = '';   // 前一張缺圖被藏起來了,新的一張要重新有機會
    img.src = PIC + ids[i] + '.jpg';
  });
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
    render, initAltArt,
    page: () => state.page,
    perPage: () => state.perPage,
    setPage(p) { state.page = p; },
    setPerPage(n) { state.perPage = n; state.page = 1; },
  });
})();
