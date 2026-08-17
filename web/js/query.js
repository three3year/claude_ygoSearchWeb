/**
 * query.js — 輸入層(側欄的條件控制項 ⇄ 查詢條件物件)
 *
 * 側欄是**唯一的可變真相**:條件物件由它導出,沒有第二份「上次查了什麼」的狀態。
 * 引擎(engine.js)吃的是這裡吐出來的純物件,因此測試餵條件進去不必假造 DOM。
 *
 * **卡片參數的按鈕全部由 `window.VOCAB` 生成,HTML 只留一個空殼容器**(ADR-0008)。
 * 在[[值域正典]]裡加一個種族,按鈕自動多一顆;漏一個碼則是建置期就撞得到。手抄一份
 * 選項在 HTML 裡的話,兩處必然漂移,而漂移的形狀是「某批卡點不出來」——不報錯、
 * 不白屏,只是結果少了幾百張而沒有人會察覺。
 *
 * 票08 的 `#hash` 編解碼也接在條件物件上——序列化的對象就是它。
 *
 * 側欄自己的**開合**(票09:窄螢幕上它是頂部的可摺疊區)也在這裡:那是側欄的
 * 呈現狀態,不是查詢的一部分。「現在算不算窄螢幕」這件事 JS 一個字都不知道——
 * 開合只是一個 class 與 `aria-expanded`,寬螢幕由 CSS 讓它不生效。
 */
'use strict';

const Query = (() => {
const { $, VOCAB, esc } = Util;

/* 卡名語言三態循環:中 → 日 → 英 → 中。碼、鈕面文字與說明在這裡一處決定,
   HTML 只給起始態(`data-v`)。 */
const LANGS = [
  { v: 'zh', label: '中', title: '比對中文卡名（含 ※ 別名）' },
  { v: 'ja', label: '日', title: '比對日文卡名（含 ※ 別名）' },
  { v: 'en', label: '英', title: '比對英文卡名' },
];

/* 生成的條件軸的欄位表,**順序即側欄由上到下的排列**。一張表同時餵給三件事:
   按鈕生成、read()、clear()——分成三份的話,加一軸要記得改三個地方,而漏改的那一處
   會安靜地不生效。
   - `tri`:三態鈕軸;`dom` 是[[值域正典]]的值域名,選項與軸標題都從 VOCAB 導出。
   - `side`:子類型是**一個**軸的三段(怪獸/魔法/陷阱),不是三個軸——三個軸的話
     「融合怪獸或速攻魔法」會變成軸間 AND、永遠零筆。短碼跨側重複,所以帶大類前綴。
   - `range`:數值範圍,只給一邊也要正確。
   - `unknown`:攻守 `?` 的獨立條件——`?` 與 0 是不同的東西,不被數值範圍納入。

   [[效果類型]]與[[必發/選發]]排在最前面,緊接著 HTML 那一段的效果文框:引擎的分界
   是卡層/句層,而這三個是全部的句層條件——它們並用時取的是同一個效果句(句層耦合),
   排在一起才看得出那是一組問題,而不是三個獨立的篩子。 */
const FIELDS = [
  { tri: 'kind', dom: 'kind' },
  { tri: 'opt', dom: 'optional' },
  // 大類是**兩態**(票12):三值互斥,排除某一類等同勾選其餘兩類,排除態是冗餘的,
  // 而且誤入排除態會讓子類組整組收起。態數寫在宣告上,循環照宣告走——不在點擊
  // 處理裡對大類寫特例,之後別的軸要兩態化時改這裡就好。
  { tri: 'cat', dom: 'cat', states: 2 },
  { tri: 'sub', dom: 'sub_m', side: 'm' },
  { tri: 'sub', dom: 'sub_s', side: 's' },
  { tri: 'sub', dom: 'sub_t', side: 't' },
  { tri: 'attr', dom: 'attr' },
  { tri: 'race', dom: 'race' },
  { range: 'lv', zh: '等級／階級' },
  { range: 'lk', zh: '連結值' },
  { range: 'sc', zh: '靈擺刻度' },
  { range: 'atk', zh: '攻擊力', unknown: 'atkq' },
  { range: 'df', zh: '守備力', unknown: 'dfq' },
  { tri: 'lm', dom: 'lm' },
  { tri: 'rarity', dom: 'rarity' },
  { range: 'gy', zh: 'Genesys 點數' },
  { tri: 'ot', dom: 'ot' },
];

/* 三態:未選 → 包含 → 排除 → 未選。'' 不是狀態的缺席而是第三個狀態,所以循環表
   把它排在裡面而不是用另一條路徑處理。兩態軸(大類)走前兩段:未選 ⇄ 選取,
   循環長度就是宣告的態數——同一張表、同一條規則,沒有第二條路徑。 */
const STATES = ['', 'in', 'ex'];
const STATE_TITLE = {
  3: { '': '未選（再點一次＝包含）', in: '包含（再點一次＝排除）',
       ex: '排除（再點一次＝取消）' },
  2: { '': '未選（再點一次＝選取）', in: '選取（再點一次＝取消）' },
};

/** 狀態循環規則:`(目前狀態, 態數) → 下一個狀態`。態數來自軸宣告(axes() 的
    `states`),DOM 只照它循環——兩態軸因此永遠碰不到排除。 */
function nextState(st, states) {
  const n = states === 2 ? 2 : 3;
  return STATES[(STATES.indexOf(st) + 1) % n];
}

function langOf(v) {
  return LANGS.find(l => l.v === v) || LANGS[0];
}

function showLang(el, v) {
  const lang = langOf(v);
  el.dataset.v = lang.v;
  el.textContent = lang.label;
  el.title = lang.title;
}

/**
 * 分類類條件的按鈕清單,**由 `window.VOCAB` 導出**。
 *
 * 導出而不是在 DOM 建好之後再回頭數:這是「按鈕由正典生成」這條性質唯一測得到的
 * 形狀(接縫 3 的沙箱沒有真的 DOM)。值域多一個成員,這裡就多一顆鈕。
 */
function axes() {
  return FIELDS.filter(f => f.tri).map(f => {
    const dom = VOCAB[f.dom] || {};
    const items = dom.items || [];
    const byCode = {};
    items.forEach(it => { byCode[it.code] = it; });
    // 有分組的值域(子類型的卡框/能力、效果類型的怪獸側/魔陷卡)照分組排;
    // 其餘整批一組,組名留空——沒有分組的軸不該長出一個沒有意義的小標題。
    const groups = (dom.groups || []).length
      ? dom.groups.map(g => ({ zh: g.zh,
                               items: g.codes.map(c => byCode[c]).filter(Boolean) }))
      : [{ zh: '', items }];
    return { key: f.tri, dom: f.dom, side: f.side || '', zh: dom.zh || f.dom,
             states: f.states || 3, groups };
  });
}

/**
 * 「[[必發/選發]]」那一組條件在目前的[[效果類型]]選擇下出不出得來(Story 25)。
 *
 * 承載這個屬性的只有誘發即時(2速)、誘發(1速)與[[魔陷卡效果]]十值,**承載關係由
 * [[值域正典]]宣告**(`VOCAB.optional.carriers`)——抄一份在這裡的話,某天多一個
 * 承載型的效果類型時這一組會安靜地不出現。
 *
 * 規則:已選(包含)的效果類型全都不承載時收起來——「永續效果是必發」是一個永遠
 * 零結果的條件,不該設得出來。**一顆都沒包含時仍然出得來**:那時「必發」自己就是
 * 一個有結果的條件(Story 24 要找的「必須發動的效果」不必先點滿十二顆鈕才問得出)。
 * 排除不算已選:排除永續效果之後,命中的句子仍然可能是承載型的。
 */
function optionalAvailable(kindSel) {
  const carriers = (VOCAB.optional || {}).carriers || [];
  const included = Object.keys(kindSel || {}).filter(c => kindSel[c] > 0);
  return !included.length || included.some(c => carriers.indexOf(c) >= 0);
}

/* ── 側欄的生成 ───────────────────────────────────────── */

function triBtn(code, zh, states) {
  return `<button type="button" class="tri" data-code="${esc(code)}"
    data-st="" title="${STATE_TITLE[states || 3]['']}">${esc(zh)}</button>`;
}

/* 摺疊標題列(票13):軸名 + 已選數。每一個生成的區塊都有一條,預設收起——
   側欄初見只剩一排標題列,不必捲過兩百多顆鈕。已選數讓收起的條件保持可見
   (「看不見的條件解釋不了零結果」由它接手),沒點任何鈕時不顯示數字。 */
function headHtml(zh) {
  return `<button type="button" class="axis-head" aria-expanded="false">
    <span class="axis-name">${esc(zh)}</span><span class="axis-count"></span></button>`;
}

function axisHtml(ax) {
  const body = ax.groups.map(g => {
    const row = `<div class="tri-row">${
      g.items.map(it => triBtn(it.code, it.zh, ax.states)).join('')}</div>`;
    return g.zh ? `<div class="tri-group">
      <span class="group-label">${esc(g.zh)}</span>${row}</div>` : row;
  }).join('');
  // 子類型的三組各自藏著(hidden),選了對應的大類才出現——那是連動隱藏
  // (條件語意,收掉就清空),與摺疊(瀏覽狀態,收起保留條件)是兩個機制。
  // 態數(兩態/三態)由宣告帶在容器上,循環與 tooltip 都照它走。
  return `<div class="axis" data-axis="${ax.key}" data-side="${ax.side}"
    data-states="${ax.states}"${ax.side ? ' hidden' : ''}>
    ${headHtml(ax.zh)}<div class="axis-body" hidden>${body}</div></div>`;
}

function rangeHtml(f) {
  const num = which => `<input type="number" class="range-in"
    data-key="${f.range}" data-end="${which}" aria-label="${esc(f.zh)}${
    which === 'min' ? '下限' : '上限'}">`;
  // 攻守的 `?` 是第三種值而不是某個數字:83 張攻 `?`、54 張守 `?`,它們在數值
  // 範圍裡被靜靜排除的話就再也找不到了,所以自己一顆三態鈕
  const unknown = f.unknown
    ? `<button type="button" class="tri tri-q" data-code="?" data-st=""
        data-unknown="${f.unknown}" title="${STATE_TITLE[3]['']}">?</button>` : '';
  return `<div class="range" data-range="${f.range}">
    ${headHtml(f.zh)}<div class="axis-body" hidden>
    <div class="range-row">${num('min')}<span class="range-sep">～</span>${
      num('max')}${unknown}</div></div></div>`;
}

function build() {
  const axisByKey = {};
  axes().forEach(ax => { axisByKey[ax.key + '/' + ax.side] = ax; });
  $('critParams').innerHTML = FIELDS.map(f => f.tri
    ? axisHtml(axisByKey[f.tri + '/' + (f.side || '')])
    : rangeHtml(f)).join('');
}

/* ── 讀取 ─────────────────────────────────────────────── */

function all(sel) {
  return Array.prototype.slice.call($('critParams').querySelectorAll(sel));
}

function axisEl(key, side) {
  return $('critParams').querySelector(
    `.axis[data-axis="${key}"][data-side="${side || ''}"]`);
}

function num(v) {
  return v === '' || v == null || isNaN(+v) ? null : +v;
}

/* 一軸目前的三態選擇。讀出來的形狀就是引擎吃的形狀,所以「必發/選發 出不出得來」
   那條規則(optionalAvailable)拿得到現成的答案,不必自己再走一次 DOM。 */
function triSel(f) {
  const out = {};
  axisEl(f.tri, f.side).querySelectorAll('.tri').forEach(btn => {
    if (!btn.dataset.st) return;
    const key = f.side ? f.side + ':' + btn.dataset.code : btn.dataset.code;
    out[key] = btn.dataset.st === 'ex' ? -1 : 1;
  });
  return out;
}

function readTri(q, f) {
  const one = triSel(f);
  // 子類型三段併進同一個軸(`sub`),所以是合併而不是覆寫
  for (const key in one) (q[f.tri] = q[f.tri] || {})[key] = one[key];
}

function readRange(q, f) {
  const box = $('critParams').querySelector(`.range[data-range="${f.range}"]`);
  const at = end => num(box.querySelector(`[data-end="${end}"]`).value);
  const min = at('min'), max = at('max');
  if (min != null || max != null) q[f.range] = { min, max };
  if (!f.unknown) return;
  const btn = box.querySelector('.tri-q');
  if (btn.dataset.st) q[f.unknown] = btn.dataset.st === 'ex' ? -1 : 1;
}

/** 側欄目前的設定 → 查詢條件物件(接縫 3 的輸入) */
function read() {
  const q = {
    name: $('fName').value.trim(),
    nameLang: langOf($('fNameLang').dataset.v).v,
    code: $('fId').value.trim(),
    text: $('fText').value.trim(),
  };
  FIELDS.forEach(f => (f.tri ? readTri : readRange)(q, f));
  return q;
}

/**
 * 目前生效中的**條件數**(票09 的摺疊鈕寫它)。
 *
 * 純函式,吃的就是 `read()` 吐出來的那個物件——摺疊鈕上的數字因此不必自己再走一遍
 * DOM,加一條條件軸時它也自動算得到。數的是**軸**而不是點亮的鈕:「屬性 3 顆」是
 * 一條條件(軸內 OR),寫成 3 會讓人以為那是三道篩子。
 *
 * `nameLang` 不算:它是「卡名那一格拿哪一種卡名比」,不是一條會篩掉卡的條件——
 * 算進去的話清空所有條件之後鈕面仍然寫著 1。
 */
function count(q) {
  const isSet = v => {
    if (v == null || v === '') return false;
    if (typeof v !== 'object') return true;
    // 三態軸 `{dark: 1}`、範圍 `{min: 2500, max: null}` 同一條判準:有沒有任何
    // 一個給了值的鍵。空物件(壞掉的網址解出來的殘骸)因此不算一條。
    // **空著的那一邊是 null 而不是 0**:刻度 0(28 張)與攻擊力 0 都是真的值,
    // 把 0 當成沒設的話那幾條條件會從鈕面的數字裡消失
    return Object.keys(v).some(k => v[k] != null);
  };
  return Object.keys(q || {}).filter(k => k !== 'nameLang' && isSet(q[k])).length;
}

/**
 * 逐軸已選數(票13):`查詢條件 → { 區塊鍵: 點了幾顆 }`。
 *
 * 軸摺疊之後,收起的軸看不見自己設了什麼——標題列寫的就是這個數字,「看不見的
 * 條件解釋不了零結果」那條原則由它接手。`count()` 數的是「幾條條件」(整軸一條),
 * 這裡數的是「這一軸點了幾顆」,兩個數字答的是不同的問題。
 *
 * 鍵是**畫面上的區塊**:三態軸用值域名(`sub_m`)、範圍用欄位名(`atk`)——
 * 子類型三段各自一個標題列,所以共用的 `sub` 軸物件照大類前綴拆回三份,
 * 誰的選擇誰計數。攻守的 `?` 落在自己那一格範圍的區塊裡,設了就多一筆。
 */
/* 一個 FIELDS 條目對應畫面上的一個區塊。鍵(三態軸用值域名、範圍用欄位名)與
   元素的對應只寫這一次——逐軸已選數、還原展開與 DOM 寫回都用同一份。 */
function blockKey(f) {
  return f.tri ? f.dom : f.range;
}

function blockEl(f) {
  return f.tri ? axisEl(f.tri, f.side)
    : $('critParams').querySelector(`.range[data-range="${f.range}"]`);
}

function axisCounts(q) {
  q = q || {};
  const out = {};
  FIELDS.forEach(f => {
    if (f.tri) {
      const sel = q[f.tri] || {};
      out[blockKey(f)] = Object.keys(sel).filter(k => sel[k] &&
        (!f.side || k.indexOf(f.side + ':') === 0)).length;
      return;
    }
    const r = q[f.range] || {};
    out[blockKey(f)] = (r.min != null || r.max != null ? 1 : 0) +
                       (f.unknown && q[f.unknown] ? 1 : 0);
  });
  return out;
}

/**
 * 還原展開判定(票14):`查詢條件 → 該展開的區塊鍵清單`。
 *
 * 網址還原時 DOM 照這份清單開軸——收到連結的人一眼看到這個查詢設了什麼,
 * 而不是一排收起的標題列。三種成員:
 *
 * 1. **有已選條件的軸**(逐軸已選數 > 0),排除也是條件。
 * 2. **大類選取連動帶出的子類組**——點了怪獸就是要篩子類,子類還沒點也展開。
 * 3. **承載的效果類型連動帶出的必發/選發**——與 optionalAvailable 同一份承載
 *    宣告(`VOCAB.optional.carriers`),排除不算已選也是同一條規則。但注意兩者
 *    答的問題不同:optionalAvailable 管「出不出得來」(一顆都沒選也出得來),
 *    這裡管「要不要自動展開」(連動出現才展開,預設可見不代表要展開)。
 */
function expandedAxes(q) {
  q = q || {};
  const counts = axisCounts(q);
  const cat = q.cat || {};
  const kindSel = q.kind || {};
  const carriers = (VOCAB.optional || {}).carriers || [];
  const out = [];
  FIELDS.forEach(f => {
    const key = blockKey(f);
    let on = counts[key] > 0;
    if (f.side) on = on || cat[f.side] > 0;
    if (f.tri === 'opt') on = on || Object.keys(kindSel)
      .some(c => kindSel[c] > 0 && carriers.indexOf(c) >= 0);
    if (on) out.push(key);
  });
  return out;
}

/* ── 互動 ─────────────────────────────────────────────── */

/**
 * 摺疊(票09):窄螢幕上側欄是頂部的可摺疊區,預設收起、點一下展開。
 *
 * **開關狀態只有一份說法**:`aria-expanded` 是它,`.open` 只是給 CSS 的選擇器用。
 * 桌機呼叫這幾個函式是安全的空動作——側欄在寬螢幕由 CSS 常駐顯示,`.open` 在那裡
 * 不影響任何東西。「現在算不算窄螢幕」因此不必在 JS 裡再寫一次斷點(斷點只住在
 * style.css,ADR-0008 擋的是同一種第二份真相)。
 */
function setOpen(open) {
  const btn = $('btnFilters');
  $('sidebar').classList.toggle('open', open);
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function isOpen() {
  return $('btnFilters').getAttribute('aria-expanded') === 'true';
}

/** 摺疊鈕的鈕面:摺起來也看得見「還有幾條條件在生效」 */
function summarize(q) {
  const n = count(q);
  $('btnFilters').textContent = n ? `篩選條件・${n} 項` : '篩選條件';
}

/* 一顆鈕屬於兩態還是三態軸:宣告寫在 .axis 容器上。範圍旁的 `?` 鈕不在
   .axis 裡,closest 找不到就是三態——它本來就是三態。 */
function statesOf(btn) {
  const ax = btn.closest('.axis');
  return ax && +ax.dataset.states === 2 ? 2 : 3;
}

function setTri(btn, st) {
  btn.dataset.st = st;
  btn.title = STATE_TITLE[statesOf(btn)][st];
}

/**
 * 摺疊(票13):收起只是視覺收納,**條件保留生效**——與連動隱藏(showAxis,
 * 藏掉就清空)語意相反,兩個機制並存。開合狀態只有一份說法:標題列的
 * `aria-expanded`;body 的 hidden 跟著它走,CSS 的箭頭也讀它。
 */
function setAxisOpen(box, open) {
  const head = box.querySelector('.axis-head');
  if (!head) return;
  head.setAttribute('aria-expanded', open ? 'true' : 'false');
  box.querySelector('.axis-body').hidden = !open;
}

/**
 * 逐軸已選數寫上標題列。數字由純函式(axisCounts)算,吃的就是 read() 吐出來
 * 的條件物件——DOM 只把答案寫上去,與窄螢幕摺疊鈕的 summarize 同一個結構。
 */
function updateCounts() {
  const counts = axisCounts(read());
  FIELDS.forEach(f => {
    const n = counts[blockKey(f)];
    blockEl(f).querySelector('.axis-count').textContent = n ? String(n) : '';
  });
}

/* 連動隱藏的開關。**只在轉換時動作**:同一個狀態重複呼叫不做事,否則點另一顆
   大類鈕會把使用者剛手動收起的子類組又彈開。
   - 藏掉:狀態一併清掉——留著的話條件還在生效但使用者看不到它,而看不見的
     條件是解釋不了的零結果。摺疊同時歸位(收起)。
   - 出現:**自動展開**(票14)——連動出現的軸就是使用者下一步要用的軸
     (點了怪獸就是要篩子類),躲在收起的標題後面等於沒出現。 */
function showAxis(el, show) {
  if (el.hidden === !show) return;
  if (show) {
    setAxisOpen(el, true);
  } else {
    el.querySelectorAll('.tri').forEach(b => setTri(b, ''));
    setAxisOpen(el, false);
  }
  el.hidden = !show;
}

/* 大類選了「包含」才展開對應的子類型組。 */
function syncSubs() {
  const cat = axisEl('cat', '');
  FIELDS.filter(f => f.tri === 'sub').forEach(f => {
    const btn = cat.querySelector(`.tri[data-code="${f.side}"]`);
    showAxis(axisEl('sub', f.side), !!btn && btn.dataset.st === 'in');
  });
}

/* 「必發/選發」只在選得出結果時展開(規則見 optionalAvailable)。 */
function syncOptional() {
  showAxis(axisEl('opt', ''),
           optionalAvailable(triSel(FIELDS.find(f => f.tri === 'kind'))));
}

/* ── 寫入(網址還原條件走這一條) ───────────────────────── */

/* 收起來的軸不寫:子類型那三組要選了對應的大類才展得開,而網址上可能帶著
   「有子類型、沒有大類」這種過期的組合。看不見的條件是解釋不了的零結果,
   所以那一段忽略——與 showAxis 收軸時清狀態是同一條規則。 */
function writeTri(q, f) {
  const el = axisEl(f.tri, f.side);
  const sel = (el.hidden ? null : q[f.tri]) || {};
  // 兩態軸沒有排除:寫進來的負值(理論上只有手拼的條件物件做得出來)當未選,
  // 兩態鈕才不會被寫成一個循環永遠回不到的狀態
  const ex = (f.states || 3) === 2 ? '' : 'ex';
  el.querySelectorAll('.tri').forEach(btn => {
    const key = f.side ? f.side + ':' + btn.dataset.code : btn.dataset.code;
    setTri(btn, sel[key] > 0 ? 'in' : (sel[key] < 0 ? ex : ''));
  });
}

function writeRange(q, f) {
  const box = $('critParams').querySelector(`.range[data-range="${f.range}"]`);
  const r = q[f.range] || {};
  const set = (end, v) => {
    box.querySelector(`[data-end="${end}"]`).value = v == null ? '' : v;
  };
  set('min', r.min);
  set('max', r.max);
  if (!f.unknown) return;
  const u = q[f.unknown];
  setTri(box.querySelector('.tri-q'), u > 0 ? 'in' : (u < 0 ? 'ex' : ''));
}

/**
 * 查詢條件物件 → 側欄(`read()` 的反向)。網址還原條件走的就是這一條。
 *
 * 先清空再逐項寫:沒出現在條件裡的軸一律回到未選,否則上一次的設定會留在
 * 畫面上繼續生效,而使用者以為自己看的是網址裡那個查詢。
 *
 * 大類與效果類型**先寫一輪**,子類型與必發/選發那幾組才展得開——收著的軸
 * 寫進去等於沒寫(writeTri 會把它清掉),而那正是過期網址該有的下場。
 */
function write(q) {
  q = q || {};
  clear();
  $('fName').value = q.name || '';
  $('fId').value = q.code || '';
  $('fText').value = q.text || '';
  showLang($('fNameLang'), langOf(q.nameLang).v);
  FIELDS.filter(f => f.tri === 'cat' || f.tri === 'kind')
    .forEach(f => writeTri(q, f));
  syncSubs();
  syncOptional();
  FIELDS.forEach(f => (f.tri ? writeTri : writeRange)(q, f));
  updateCounts();
  // 還原展開(票14):有已選條件的軸與連動帶出的軸自動展開,其餘收起。
  // 吃 read() 而不是傳進來的 q:過期的段(有子類型沒大類)在上面已被丟掉,
  // 展開判定看的該是真的還原成功的那一份條件。
  const open = expandedAxes(read());
  FIELDS.forEach(f => setAxisOpen(blockEl(f), open.indexOf(blockKey(f)) >= 0));
}

/** 清除條件:回到「什麼都沒設」的狀態,也就是列出全部卡片的那個狀態。
    摺疊一併歸位(全軸收起)——清除就是回到初始狀態,不是只清數值。 */
function clear() {
  $('fName').value = '';
  $('fId').value = '';
  $('fText').value = '';
  showLang($('fNameLang'), LANGS[0].v);
  all('.tri').forEach(btn => setTri(btn, ''));
  all('.range-in').forEach(input => { input.value = ''; });
  syncSubs();
  syncOptional();
  // 收合放在連動之後:必發/選發那一組若因連動從隱藏轉回可見,轉換會讓它自動
  // 展開——清除要的是初始狀態,最後一律收回
  all('.axis, .range').forEach(box => setAxisOpen(box, false));
  updateCounts();
}

function init() {
  $('btnFilters').addEventListener('click', () => setOpen(!isOpen()));
  const langBtn = $('fNameLang');
  showLang(langBtn, langBtn.dataset.v);
  langBtn.addEventListener('click', () => {
    const i = LANGS.findIndex(l => l.v === langBtn.dataset.v);
    showLang(langBtn, LANGS[(i + 1) % LANGS.length].v);
  });
  build();
  syncSubs();
  syncOptional();
  // 委派在容器上:按鈕是生成的,一顆一顆綁事件等於把生成的好處還回去
  $('critParams').addEventListener('click', e => {
    const head = e.target.closest('.axis-head');
    if (head) {
      setAxisOpen(head.parentElement,
                  head.getAttribute('aria-expanded') !== 'true');
      return;
    }
    const btn = e.target.closest('.tri');
    if (!btn) return;
    setTri(btn, nextState(btn.dataset.st, statesOf(btn)));
    if (btn.closest('.axis[data-axis="cat"]')) syncSubs();
    if (btn.closest('.axis[data-axis="kind"]')) syncOptional();
    updateCounts();
  });
  // 範圍輸入框打字也要讓標題列的已選數跟上(收起時看得見自己設了範圍)
  $('critParams').addEventListener('input', e => {
    if (e.target.closest('.range-in')) updateCounts();
  });
}

  return Object.freeze({ read, write, clear, init, axes, optionalAvailable,
                         nextState, count, axisCounts, expandedAxes, summarize,
                         collapse: () => setOpen(false), LANGS, FIELDS });
})();
