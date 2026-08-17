/**
 * render.js — 呈現層(卡片清單、卡文逐效果句分行、排序、分頁)
 *
 * **資料流單向**:要顯示的卡片清單進來,畫面出去;渲染沒有內部記憶,行為完全由
 * 參數與這一層自己擁有的呈現狀態決定。分頁位置、每頁筆數與排序歸這一層所有——
 * 兩邊都寫得到的狀態等於沒有擁有者。
 *
 * 採**全量重繪**:本站有分頁,單次渲染量只有一頁。差異更新需要「知道上一次渲染了
 * 什麼」,那是把耦合換個名字留下來。唯一不走重繪的是異圖切換:它只換 <img> 的
 * src,卡片其他資訊一個字都不動——異圖是同一張卡。
 *
 * 顯示手法沿用 oldProject(F:\AiProject\oldProject)的 render.js。
 */
'use strict';

const View = (() => {
const { DB, META, CAT_ZH, KIND_ZH, ATTR_ZH, RACE_ZH, ROLE_ZH, OPT_ZH, OT_ZH,
        LM_ZH, LM_CODES, SUB_ZH, $, esc, pad8, byId } = Util;

/* 卡圖:salix5/query-data 的 CDN,檔名就是不補零的卡片密碼 */
const PIC = 'https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/';
/* 卡名連到 salix5 查卡頁:要看官方卡表或裁定時的現成出口 */
const QUERY = 'https://salix5.github.io/query/?code=';
/* 素材指定行的上色依召喚法。順序即優先序——同時帶儀式與融合位元時取先宣告的 */
const MAT_KINDS = ['ritual', 'fusion', 'synchro', 'xyz', 'link'];

/* 呈現狀態:與資料無關的幾件事。唯一的擁有者是這個模組。
   **排序住在這裡而不是查詢條件裡**:換一個排序鍵不會改變命中哪些卡,所以它是
   「怎麼看這份結果」而不是「要哪些卡」——與分頁同一類。這也正是「排序切換不重跑
   搜尋」在結構上成立的原因:重排走的是 render(),根本沒有經過引擎。 */
const state = { page: 1, perPage: 100,
                sortKey: Sort.KEYS[0].key, sortDir: Sort.KEYS[0].dir };

/* 上一次的查詢產物——換頁與換每頁筆數由此重繪,但沒有人從外面寫入它。
   形狀就是接縫 3 的回傳值 `{ cards: [{ card, rows }], marks }`:`rows` 是命中的
   效果句索引,`marks` 是生效中的句層條件。呈現層照著它畫,不自己再判一次命中。

   **`null` 是第三種值:還沒有查過(起始畫面)**,與「查了但沒有一張命中」是兩件
   不同的事——後者要說「沒有符合條件的卡片」,前者不該說任何像是結果的話。分成
   兩個狀態而不是拿 `cards: []` 兼差,是因為換排序、換每頁筆數走的都是不帶參數的
   `render()`:起始畫面上調一下每頁筆數,不該把提示換成「沒有符合條件的卡片」。 */
let lastResult = null;

/* 狀態 → 排序控制項的同步,由 initSort 裝上(在那之前 setSort 沒有控制項要更新) */
let paintSort = () => {};

/* 換排序鍵回到第 1 頁:上一次翻到第 37 頁,換成攻擊力降序之後留在第 37 頁的話,
   使用者看到的是「攻擊力最高的卡」以外的任何東西。

   方向由排序鍵決定合不合法:沒有方向的鍵(領域序)一律清空,有方向的鍵沒給值時
   回到該鍵的預設方向。狀態因此永遠是 `Sort.KEYS` 說得出口的形狀——票08 要把它
   序列化進網址,而「領域序＋降序」那種組合序列化出去也還原不回任何東西。 */
function setSort(key, dir) {
  const spec = Sort.specOf(key);
  state.sortKey = spec.key;
  state.sortDir = spec.dir ? (dir || spec.dir) : '';
  state.page = 1;
  paintSort();
}

/* 命中原因 → badge 上的文字。[[效果類型]]與[[必發/選發]]寫的是**這一行自己的值**
   ——多條件並用時 badge 就是「這一行為什麼被選中」的答案,而那個答案逐行不同:
   效果類型選了誘發即時+誘發兩顆時,命中的兩行寫的不是同一個詞。
   **效果文不進 badge**:關鍵字已經在行內上色,badge 再寫一次「效果文」是重複資訊
   ——只搜效果文時整顆 badge 因此不長。 */
const MARK_ZH = {
  text: () => '',
  kind: (c, i) => KIND_ZH[(c.k || [])[i]],
  opt: (c, i) => OPT_ZH[(c.o || [])[i]],
};

/* 句層條件 → 畫命中行要的兩樣東西:關鍵字的比對段(行內上色用)與生效中的條件。
   沒有句層條件時是 null,`effHtml` 因此連問都不必問。
   **比對段取自引擎導出的 likeParts**:呈現層自己再寫一份切法就會漂開,而漂開的
   形狀是「這一行被標亮了但沒有一個字上色」。 */
function highlight(marks) {
  if (!marks || !marks.length) return null;
  const text = marks.find(m => m.type === 'text');
  return { parts: text ? Engine.likeParts(text.value) : [], marks };
}

/* 沒有值的條件不寫進 badge:「排除必發」命中的那一句可能根本不承載這個屬性,
   那時寫得出來的只有其餘條件。
   認不得的條件退回寫短碼而不是讓整個結果區炸掉:引擎多一種句層條件而這裡忘了
   跟上時,壞掉的該是一個 badge 的字面,不是整頁卡片(那次例外會讓 innerHTML
   從頭到尾沒設成,畫面停在上一次的結果上——最難察覺的那種壞法)。 */
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

/**
 * 起始畫面:**一條條件都沒有時不列出全部**,而是說一句該做什麼。
 *
 * 空條件在引擎那裡仍然是合法的條件、仍然導出全部卡片(那是純函式的性質,沒有
 * 改)——不列出來是**呈現層的決定**:一開站就吐 14,207 張的第一頁,使用者得到的
 * 是一批與自己無關的卡,還得先捲過去才找得到條件區;手機上那還是幾十張卡圖的
 * 流量。畫面該問問題,不該先給一個沒有人問過的答案。
 *
 * 想純逛全部的人按空條件的「搜尋」就行(那裡本來就放行)——起始畫面只有一句話,
 * 不再放提示句與「仍要列出全部」鈕(2026-08-17 使用者裁示拿掉)。
 */
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
      ${printHtml(c)}
      ${metaHtml(c)}
      <div class="card-text">${cardText(c, e.rows, hl)}</div>
      ${c.og ? `<div class="card-text og-text" hidden>${esc(c.og)}</div>` : ''}
    </div>
  </article>`;
}

/* 卡圖載不到時安靜隱藏:CDN 缺圖不該在畫面上留一排破圖。用 visibility 而不是
   display,位置留著,文字才不會因為某幾張缺圖而左右跳動。
   decoding="async":懶載入的圖在快速捲動途中陸續抵達,同步解碼會綁在繪製幀裡
   ——中鍵自動捲動由主執行緒驅動,那正是「一卡一卡」的來源之一。 */
function imgHtml(id) {
  return `<img class="card-img" loading="lazy" decoding="async"
    width="180" height="262" alt=""
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

/* 「顯示原文」切換鈕,只長在[[卡文勘誤表]]勘誤過的卡上(`og` 是勘誤前的來源
   卡文原樣,ADR-0011)——其餘一萬四千多張卡的原文就是畫面上那份,鈕是雜訊。
   放密碼右邊(2026-08-17 盤問決定),與異圖切換同一個「對照出口」的角色。 */
function ogBtnHtml(c) {
  if (!c.og) return '';
  return `<button type="button" class="og-toggle" aria-pressed="false"
    title="此卡卡文經本站勘誤,點一下對照勘誤前的來源原文">顯示原文</button>`;
}

/* OCG・TCG 限定徽章,擺在標題列 MD 稀有度右邊、與稀有度同一套視覺語言。
   「兩者」是 13,822 張的常態,不寫出來——只有限定才是資訊。 */
function otHtml(c) {
  if (!c.ot || c.ot === 'b') return '';
  return `<span class="card-ot ot-${esc(c.ot)}"
    title="${esc(OT_ZH[c.ot] || c.ot)}">${esc(OT_ZH[c.ot] || c.ot)}</span>`;
}

/* MD 稀有度以外的印刷面資訊:Genesys 點數。 */
function printHtml(c) {
  if (!c.gy) return '';
  return `<div class="card-print"><span class="card-gy">Genesys ${c.gy}</span></div>`;
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
  // 靈擺通常怪獸(37 張)的下半段是故事文而不是效果
  if (flavor) out += group('【怪獸敘述】', flavor, true);
  return out;
}

function group(label, lines, divider) {
  return `${divider ? '<hr class="pend-divider">' : ''}
    <div class="eff-group-label">${label}</div>${lines}`;
}

/* 一行效果句。效果外文本依 `role` 分三種弱化樣式,素材指定行另依召喚法上色。
   標籤寫 role(有的話)而不是「效果外文本」——8,180 行都寫同一個詞等於沒寫,
   而那三種 role 才是使用者一眼要分出來的東西。

   標籤**常態不顯示,點一下該行才展開在整段效果文的下方**:讀卡文的人多數時候
   要讀的是卡文,每一行都掛著一顆類型標籤是雜訊;而想知道「這一句是誘發即時還是
   啟動」的時候,那是一次刻意的提問,值得一次點擊。放下方而不是接在文字後面——
   接在後面的話它會擠進最後一行的行尾,看起來像卡文的一部分。 */
function effHtml(c, text, i, rows, hl) {
  const role = (c.ro && c.ro[i]) || '';
  const kind = (c.k && c.k[i]) || '';
  const label = role ? ROLE_ZH[role] : (KIND_ZH[kind] || kind);
  // 命中的那幾行整行標亮、上方獨立一行掛 badge 說明命中原因,關鍵字本身再在
  // 行內上色;沒命中的行一個字都不動。只搜效果文時 badge 是空字串,整顆不長。
  const hit = !!rows && rows.indexOf(i) >= 0;
  const ranges = hit && hl && hl.parts.length
    ? Engine.likeRanges(text, hl.parts) : null;
  const badge = hit ? badgeText(hl.marks, c, i) : '';
  return `<p class="eff${roleClass(c, role)}${hit ? ' hit' : ''}" data-ei="${i}">${
    badge ? `<span class="eff-hit">${esc(badge)}</span>` : ''}${
    lineHtml(text, ranges)}${
    label ? `<span class="eff-kind">${esc(label)}</span>` : ''}</p>`;
}

function roleClass(c, role) {
  if (!role) return '';
  if (role !== 'mat') return ' role-' + role;
  const method = MAT_KINDS.find(k => (c.s || []).includes(k));
  return ' role-mat' + (method ? ' mat-' + method : '');
}

/* 一行卡文的 HTML:● 選項換行(開頭的●與已經換過行的●不重複換)、原文換行照顯示、
   命中的關鍵字上色。

   三件事在**同一次走訪**裡決定,而不是先切成「命中段/非命中段」再各自處理:段界
   上的 ● 會看不到它前面那個字,而那正是「開頭的 ● 不重複換行」要看的東西。
   `ranges` 是關鍵字在原文裡的位置(來自引擎),沒有就是不上色。 */
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

/* 效果類型標籤的展開:點一下效果句那一行,標籤在該段效果文下方出現,再點收起。
   沒有標籤的行(故事文、空的靈擺欄)不反應。展開狀態不進呈現狀態——它是一次
   「這句是什麼類型?」的提問,翻頁或重搜之後那個問題已經問完了。 */
function initEffKind() {
  $('results').addEventListener('click', e => {
    const p = e.target.closest('.eff');
    if (!p || !p.querySelector('.eff-kind')) return;
    p.classList.toggle('show-kind');
  });
}

/* 「顯示原文」的切換:換掉整個顯示區——標註視圖(效果句分行、kind 標籤、badge、
   上色)與勘誤前原文是**兩份文字**,不是同一份文字的兩種畫法,逐行對映不存在,
   所以是兩個 div 互換而不是在原視圖上摘標籤。原文那側是純文字,換行由 CSS 的
   pre-line 呈現,● 不另起新行——原樣就是原樣。
   逐卡切換、狀態不記憶(盤問決定):重繪(翻頁/重搜)即回到標註視圖,與
   show-kind 同一套哲學——看原文是一次刻意的對照,對照完就收。 */
function initOgToggle() {
  $('results').addEventListener('click', e => {
    const btn = e.target.closest('.og-toggle');
    if (!btn) return;
    const art = btn.closest('article.card');
    const on = btn.getAttribute('aria-pressed') !== 'true';
    btn.setAttribute('aria-pressed', on);
    art.querySelector('.card-text').hidden = on;
    art.querySelector('.og-text').hidden = !on;
  });
}

/* 排序選單。**選項由 `Sort.KEYS` 生成**,HTML 只留一個空的 <select>:排序鍵、
   中文名與預設方向是同一份宣告,加一個鍵時不會出現「選單有這個選項但排序沒反應」。

   方向鈕只長在有方向的鍵上——領域序是固定的七層比較,把它反過來排出來的東西
   (陷阱在前、等級低到高、密碼大到小)不對應任何一個問題。

   `onChange` 是換排序之後的回呼(票08 拿它更新網址):排序是「這份結果怎麼看」
   的一部分,分享出去的連結講的是我現在看到的這一頁。呈現層自己不知道有網址
   這回事——它只回報「排序被換過了」,要不要記進網址是主流程的事。 */
function initSort(onChange) {
  const keySel = $('sortKey');
  const dirBtn = $('sortDir');
  keySel.innerHTML = Sort.KEYS.map(k =>
    `<option value="${esc(k.key)}">${esc(k.zh)}</option>`).join('');
  // 狀態 → 控制項的單向同步。setSort 也走這一條,所以不論是誰改的排序
  // (票08 的網址狀態會是下一個),畫面上的選單都跟得上
  paintSort = () => {
    keySel.value = state.sortKey;
    dirBtn.hidden = !Sort.specOf(state.sortKey).dir;
    dirBtn.textContent = state.sortDir === 'desc' ? '↓ 降序' : '↑ 升序';
    dirBtn.title = state.sortDir === 'desc'
      ? '目前是降序（點一下改升序）' : '目前是升序（點一下改降序）';
  };
  const changed = () => { render(); if (onChange) onChange(); };
  keySel.addEventListener('change', () => {
    // 切換鍵時帶上那個鍵的預設方向:選了攻擊力就該看到最高的那張
    setSort(keySel.value, Sort.specOf(keySel.value).dir);
    changed();
  });
  dirBtn.addEventListener('click', () => {
    setSort(state.sortKey, state.sortDir === 'desc' ? 'asc' : 'desc');
    changed();
  });
  paintSort();
}

/* 異圖切換:只換 <img> 的 src 與版次,不重繪卡片——異圖是同一張卡,
   換的只是卡面圖。委派在 #results 上,全量重繪不必重綁事件。

   換 src 時瀏覽器會**留著舊圖直到新圖載完**,CDN 慢的時候按了像沒按——所以按下
   的瞬間把舊圖調淡,新圖到了再恢復,回饋不等網路。載入中再按會換掉 src、中止前
   一次下載,殘留的 once 監聽器最終只是多移除一次同一個 class,無害。
   同方向的下一張圖順手預載:連續翻圖是這個控制項的主要用法(黑魔導 17 版),
   預載一張讓下一按幾乎即時,又不必一口氣抓全部版次。 */
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
    img.style.visibility = '';   // 前一張缺圖被藏起來了,新的一張要重新有機會
    img.classList.add('img-loading');
    const done = () => img.classList.remove('img-loading');
    img.addEventListener('load', done, { once: true });
    img.addEventListener('error', done, { once: true });
    img.src = PIC + ids[i] + '.jpg';
    new Image().src = PIC + ids[(i + step + ids.length) % ids.length] + '.jpg';
  });
}

/* 頁碼窗的大小(頭尾各幾頁、目前頁前後各幾頁)**由 CSS 決定**:窄螢幕上 285 頁的
   分頁器照桌機的窗畫會排到三四排去,而「多窄算窄」只該有一份說法——斷點住在
   style.css 的 `--pg-win`,這裡只是問它。JS 自己記一次 720 的話,改了 CSS 之後
   分頁器會在另一個寬度才變窄,那是看不出原因的版面錯位(ADR-0008 的同一條理由)。
   讀不到就回桌機的 2:沒有 CSS 的環境(測試沙箱)不該因此少畫頁碼。 */
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
  // 「上一頁」三個字包起來,小螢幕上由 CSS 收掉只留箭頭:360px 寬的手機上那兩個
  // 詞佔掉近八十點,留著就會把頁碼擠到第二排去(整個分頁器因此變成三排)
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

/* 換頁後捲回結果頂端:看完一頁不必自己找回去。**立刻跳而不是平滑捲**——
   內容已經換成新的一頁,舊位置沒有什麼好告別的,動畫只是讓新內容晚半秒能讀
   (2026-08-17 使用者裁示)。 */
function goto(page) {
  state.page = page;
  render();
  window.scrollTo(0, $('pagerTop').offsetTop - 60);
}

  /* state 關在閉包裡:讀寫都走具名函式,繞過「換每頁筆數要回到第 1 頁」這條
     不變式的第二條路徑(View.state.page = …)從結構上不存在 */
  return Object.freeze({
    render, initAltArt, initEffKind, initOgToggle, initSort,
    page: () => state.page,
    perPage: () => state.perPage,
    sort: () => ({ key: state.sortKey, dir: state.sortDir }),
    setPage(p) { state.page = p; },
    setPerPage(n) { state.perPage = n; state.page = 1; },
    setSort,
  });
})();
