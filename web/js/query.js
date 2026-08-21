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

   大類排在最上(2026-08-18 使用者裁示):它是搜尋與呈現的最上層分類,子類型與
   怪獸參數整棵樹都巢狀在它底下。[[效果類型]]與[[必發/選發]]緊接其後:這兩個與
   HTML 那一段的效果文框是全部的句層條件——並用時取的是同一個效果句(句層耦合),
   彼此相鄰才看得出那是一組問題,而不是幾個獨立的篩子。 */
const FIELDS = [
  // 大類是**兩態**(票12):三值互斥,排除某一類等同勾選其餘兩類,排除態是冗餘的,
  // 而且誤入排除態會讓子類組整組收起。態數寫在宣告上,循環照宣告走——不在點擊
  // 處理裡對大類寫特例,之後別的軸要兩態化時改這裡就好。
  { tri: 'cat', dom: 'cat', states: 2 },
  { tri: 'kind', dom: 'kind' },
  { tri: 'opt', dom: 'optional' },
  // `parent`:檔案總管式的樹狀內縮——子軸的整個區塊**巢狀在父軸的摺疊體裡**,
  // 收起父軸,整棵子樹跟著消失(各自的展開狀態保留,再展開時原樣回來)。
  // 子類組掛在大類下;怪獸參數八軸掛在怪獸子類型下。
  // `groupBlocks`:值域的具名分組(卡框/能力)各自長成一個摺疊區塊,顯示方式
  // 與屬性/種族一致(標題列+已選數+預設收起)。只是顯示結構——查詢上它們仍是
  // 同一個 sub 軸的碼,條件形狀一個字都沒變
  { tri: 'sub', dom: 'sub_m', side: 'm', parent: 'cat', groupBlocks: true },
  { tri: 'sub', dom: 'sub_s', side: 's', parent: 'cat' },
  { tri: 'sub', dom: 'sub_t', side: 't', parent: 'cat' },
  // `mon`:怪獸才有的參數(CONTEXT.md:非怪獸清空 race/attr/level/atk/def 五欄;
  // 連結值/刻度/連結標記同理)。與子類組同一套連動隱藏——選了大類「怪獸」才出現,
  // 取消就藏起並清空;出現時收著不自動展開(八軸全彈開是一面牆)
  { tri: 'attr', dom: 'attr', mon: true, parent: 'sub_m' },
  { tri: 'race', dom: 'race', mon: true, parent: 'sub_m' },
  { range: 'lv', zh: '等級／階級', mon: true, parent: 'sub_m' },
  { range: 'lk', zh: '連結值', mon: true, parent: 'sub_m' },
  { range: 'sc', zh: '靈擺刻度', mon: true, parent: 'sub_m' },
  { range: 'atk', zh: '攻擊力', unknown: 'atkq', mon: true, parent: 'sub_m' },
  { range: 'df', zh: '守備力', unknown: 'dfq', mon: true, parent: 'sub_m' },
  // `grid9`:連結標記排成九宮格(2026-08-18)。只是顯示結構,條件形狀不變
  { tri: 'lm', dom: 'lm', mon: true, parent: 'sub_m', grid9: true },
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
             states: f.states || 3, mon: !!f.mon,
             groupBlocks: !!f.groupBlocks, grid9: !!f.grid9, groups };
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
   (「看不見的條件解釋不了零結果」由它接手),沒點任何鈕時不顯示數字。
   清除鈕與標題鈕**並排**而不是巢狀(button 不能包 button),區塊裡有條件才出現
   ——可見性與已選數是同一份答案,都由 updateCounts 寫。 */
function headHtml(zh) {
  return `<div class="axis-hrow"><button type="button" class="axis-head"
    aria-expanded="false"><span class="axis-name">${esc(zh)}</span>
    <span class="axis-count"></span></button>
    <button type="button" class="axis-clear" hidden
      title="清除這一組條件">×</button></div>`;
}

function axisHtml(ax, kids) {
  const body = ax.groups.map((g, gi) => {
    const btns = g.items.map(it => triBtn(it.code, it.zh, ax.states));
    // 九宮格軸(連結標記):中央格插在第 4 顆之後——與結果卡片的 lmGridHtml
    // 同一條規則,值域的宣告序就是九宮格由左上到右下的讀法
    if (ax.grid9) btns.splice(4, 0, '<span class="tri-mid"></span>');
    const row = `<div class="tri-row${ax.grid9 ? ' tri-grid9' : ''}">${
      btns.join('')}</div>`;
    // groupBlocks:具名分組升級成自己的摺疊區塊(與屬性/種族同一套標題列),
    // 鍵是 `值域名/分組序`,徽章與還原展開都認它
    if (g.zh && ax.groupBlocks) {
      return `<div class="axis-group" data-group-key="${ax.dom}/${gi}">
        ${headHtml(g.zh)}<div class="axis-body" hidden>${row}</div></div>`;
    }
    return g.zh ? `<div class="tri-group">
      <span class="group-label">${esc(g.zh)}</span>${row}</div>` : row;
  }).join('');
  // 子類型的三組與怪獸參數軸各自藏著(hidden),選了對應的大類才出現——那是
  // 連動隱藏(條件語意,收掉就清空),與摺疊(瀏覽狀態,收起保留條件)是兩個機制。
  // 態數(兩態/三態)由宣告帶在容器上,循環與 tooltip 都照它走。
  // `kids` 是巢狀的子軸區塊(檔案總管式內縮),接在自己的選項後面、同一個
  // 摺疊體裡——收起這一軸,整棵子樹自然消失。
  return `<div class="axis" data-axis="${ax.key}" data-side="${ax.side}"
    data-states="${ax.states}"${ax.side || ax.mon ? ' hidden' : ''}>
    ${headHtml(ax.zh)}<div class="axis-body" hidden>${body}${kids || ''}</div></div>`;
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
  return `<div class="range" data-range="${f.range}"${f.mon ? ' hidden' : ''}>
    ${headHtml(f.zh)}<div class="axis-body" hidden>
    <div class="range-row">${num('min')}<span class="range-sep">～</span>${
      num('max')}${unknown}</div></div></div>`;
}

/* 依 `parent` 宣告長成一棵樹:沒有 parent 的是頂層,有的塞進父區塊的摺疊體裡。
   順序仍由 FIELDS 決定(同一層照表排)。 */
function build() {
  const axisByKey = {};
  axes().forEach(ax => { axisByKey[ax.key + '/' + ax.side] = ax; });
  const htmlOf = f => f.tri
    ? axisHtml(axisByKey[f.tri + '/' + (f.side || '')], kidsOf(blockKey(f)))
    : rangeHtml(f);
  const kidsOf = key =>
    FIELDS.filter(f => f.parent === key).map(htmlOf).join('');
  $('critParams').innerHTML =
    FIELDS.filter(f => !f.parent).map(htmlOf).join('');
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

/* 一軸**自己的**鈕。軸是巢狀的(子軸住在父軸的摺疊體裡),querySelectorAll 會
   連子樹的鈕一起撈——大類軸讀到子類型的碼就是另一個軸的條件被算錯了家,
   所以按「最近的 .axis 是不是自己」過濾。 */
function ownTris(el) {
  return Array.prototype.filter.call(
    el.querySelectorAll('.tri'), btn => btn.closest('.axis') === el);
}

/* 一軸目前的三態選擇。讀出來的形狀就是引擎吃的形狀,所以「必發/選發 出不出得來」
   那條規則(optionalAvailable)拿得到現成的答案,不必自己再走一次 DOM。 */
function triSel(f) {
  const out = {};
  ownTris(axisEl(f.tri, f.side)).forEach(btn => {
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
      // 具名分組升級成區塊的軸(groupBlocks):每個分組多發一個鍵
      // (`值域名/分組序`),數的是**該組的碼**——它是同一批選擇的分組視圖,
      // 不是另一批條件,所以不進 treeCounts 的父子加總(會重複計)
      if (f.groupBlocks) {
        ((VOCAB[f.dom] || {}).groups || []).forEach((g, gi) => {
          out[f.dom + '/' + gi] = (g.codes || [])
            .filter(c => sel[f.side ? f.side + ':' + c : c]).length;
        });
      }
      return;
    }
    const r = q[f.range] || {};
    out[blockKey(f)] = (r.min != null || r.max != null ? 1 : 0) +
                       (f.unknown && q[f.unknown] ? 1 : 0);
  });
  return out;
}

/**
 * 子樹已選數:`查詢條件 → { 區塊鍵: 自己 + 整棵子樹點了幾顆 }`。
 *
 * 軸是巢狀的(檔案總管式內縮),收起大類時子樹整個看不見——標題列的數字因此
 * 要**彙總後代**:大類收著也看得出裡面藏著幾條條件,「看不見的條件解釋不了
 * 零結果」在樹狀結構下靠它成立(與窄螢幕摺疊鈕彙總全部條件是同一個道理)。
 * 葉軸的數字就是 axisCounts 的數字。
 */
function treeCounts(q) {
  const counts = axisCounts(q);
  const total = key => FIELDS.filter(f => f.parent === key)
    .reduce((n, f) => n + total(blockKey(f)), counts[key] || 0);
  const out = {};
  FIELDS.forEach(f => { out[blockKey(f)] = total(blockKey(f)); });
  return out;
}

/**
 * 還原展開判定(票14):`查詢條件 → 該展開的區塊鍵清單`。
 *
 * 網址還原時 DOM 照這份清單開軸——收到連結的人一眼看到這個查詢設了什麼,
 * 而不是一排收起的標題列。三種成員:
 *
 * 1. **有已選條件的軸**(逐軸已選數 > 0),排除也是條件。
 * 2. **有條件的軸的祖先**——軸是巢狀的,屬性藏在 怪獸子類型 藏在 大類 裡,
 *    祖先不開,展開的葉軸沒有人看得到。
 * 3. **承載的效果類型連動帶出的必發/選發**——與 optionalAvailable 同一份承載
 *    宣告(`VOCAB.optional.carriers`),排除不算已選也是同一條規則。但注意兩者
 *    答的問題不同:optionalAvailable 管「出不出得來」(一顆都沒選也出得來),
 *    這裡管「要不要自動展開」(連動出現才展開,預設可見不代表要展開)。
 *
 * 連動出現但**自己沒有條件**的軸不在清單裡(2026-08-17 使用者裁示的檔案總管
 * 規矩:節點收著出現,要看再點開)。
 */
function expandedAxes(q) {
  q = q || {};
  const counts = axisCounts(q);
  const kindSel = q.kind || {};
  const carriers = (VOCAB.optional || {}).carriers || [];
  const parentOf = {};
  FIELDS.forEach(f => { parentOf[blockKey(f)] = f.parent || ''; });
  const open = {};
  const groupKeys = [];
  FIELDS.forEach(f => {
    const key = blockKey(f);
    let on = counts[key] > 0;
    if (f.tri === 'opt') on = on || Object.keys(kindSel)
      .some(c => kindSel[c] > 0 && carriers.indexOf(c) >= 0);
    // 連同祖先鏈一起開
    for (let k = key; on && k; k = parentOf[k]) open[k] = true;
    // 分組區塊(卡框/能力):組內有條件才開,祖先鏈跟軸自己的一樣
    if (f.groupBlocks) {
      ((VOCAB[f.dom] || {}).groups || []).forEach((g, gi) => {
        const gk = f.dom + '/' + gi;
        if (!(counts[gk] > 0)) return;
        groupKeys.push(gk);
        for (let k = key; k; k = parentOf[k]) open[k] = true;
      });
    }
  });
  return FIELDS.map(blockKey).filter(k => open[k]).concat(groupKeys);
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

/* 一顆鈕屬於兩態還是三態軸:宣告寫在 .axis 容器上。範圍旁的 `?` 鈕先命中
   自己的 .range(它沒有 data-states → 三態,它本來就是三態)——軸是巢狀的,
   直接找 .axis 會越過 .range 撞到祖先軸的宣告。 */
function statesOf(btn) {
  const box = btn.closest('.axis, .range');
  return box && +box.dataset.states === 2 ? 2 : 3;
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
  const q = read();
  // querySelector 撈到的是**自己的**標題列:軸是巢狀的,但自己的 .axis-hrow
  // 在文件序上先於摺疊體裡的子軸,首個命中必是自己
  const stamp = (box, n) => {
    box.querySelector('.axis-count').textContent = n ? String(n) : '';
    box.querySelector('.axis-clear').hidden = !n;
  };
  const tree = treeCounts(q);
  FIELDS.forEach(f => stamp(blockEl(f), tree[blockKey(f)]));
  // 分組區塊(卡框/能力)是同一批選擇的分組視圖,各自數自己那一組(flat 不彙總)
  const flat = axisCounts(q);
  all('.axis-group').forEach(box => stamp(box, flat[box.dataset.groupKey]));
}

/* 連動隱藏的開關。**只在轉換時動作**:同一個狀態重複呼叫不做事,否則點另一顆
   大類鈕會把使用者剛手動收起的子類組又彈開。
   - 藏掉:狀態一併清掉(三態鈕與範圍輸入都是)——留著的話條件還在生效但使用者
     看不到它,而看不見的條件是解釋不了的零結果。摺疊同時歸位(收起)。
   - 出現:`expand` 決定要不要**自動展開**——必發/選發與子類組連動出現時展開
     (子類組原本收著出現,2026-08-21 使用者裁示改為展開一層:點了大類還要再點
     一次才看得到子類型,多的那一步沒有資訊量);怪獸參數軸照檔案總管的規矩
     **收著出現**(八軸全彈開是一面牆),各自的展開狀態在父軸收合之間保留。
     「一層」止於子類組自己:巢在裡面的卡框/能力分組與怪獸參數軸不跟著開。 */
function showAxis(el, show, expand) {
  if (el.hidden === !show) return;
  if (show) {
    if (expand) setAxisOpen(el, true);
  } else {
    el.querySelectorAll('.tri').forEach(b => setTri(b, ''));
    el.querySelectorAll('.range-in').forEach(input => { input.value = ''; });
    // 子樹裡的分組區塊(卡框/能力)一併收回:連動再出現時從預設狀態重新開始
    el.querySelectorAll('.axis-group').forEach(b => setAxisOpen(b, false));
    setAxisOpen(el, false);
  }
  el.hidden = !show;
}

/* 大類連動:選了「包含」才出現。子類組跟著自己那一側;怪獸參數軸(mon)跟著
   「怪獸」——屬性/種族/等級這些是怪獸才有的參數(CONTEXT.md:非怪獸清空
   那五欄,連結值/刻度/連結標記同理),大類沒選怪獸時它們是問不出結果的條件。 */
function syncSubs() {
  const cat = axisEl('cat', '');
  // 只看大類**自己的**鈕:子樹裡的軸(子類型、連結標記)也住在這個容器下,
  // 用選擇器直搜會把撞碼的子軸鈕誤當大類
  const on = side => {
    const btn = ownTris(cat).find(b => b.dataset.code === side);
    return !!btn && btn.dataset.st === 'in';
  };
  FIELDS.filter(f => f.tri === 'sub').forEach(
    f => showAxis(axisEl('sub', f.side), on(f.side), true));
  FIELDS.filter(f => f.mon).forEach(f => showAxis(blockEl(f), on('m'), false));
}

/* 「必發/選發」只在選得出結果時展開(規則見 optionalAvailable)。 */
function syncOptional() {
  showAxis(axisEl('opt', ''),
           optionalAvailable(triSel(FIELDS.find(f => f.tri === 'kind'))), true);
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
  ownTris(el).forEach(btn => {
    const key = f.side ? f.side + ':' + btn.dataset.code : btn.dataset.code;
    setTri(btn, sel[key] > 0 ? 'in' : (sel[key] < 0 ? ex : ''));
  });
}

function writeRange(q, f) {
  const box = $('critParams').querySelector(`.range[data-range="${f.range}"]`);
  // 藏著的軸不寫(與 writeTri 同一條規則):怪獸參數軸要選了大類「怪獸」才在,
  // 「有攻擊力、沒有大類」是過期網址的組合,寫進去等於一條看不見的條件
  const r = (box.hidden ? null : q[f.range]) || {};
  const set = (end, v) => {
    box.querySelector(`[data-end="${end}"]`).value = v == null ? '' : v;
  };
  set('min', r.min);
  set('max', r.max);
  if (!f.unknown) return;
  const u = box.hidden ? null : q[f.unknown];
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
  all('.axis-group').forEach(box =>
    setAxisOpen(box, open.indexOf(box.dataset.groupKey) >= 0));
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
  // 展開——清除要的是初始狀態,最後一律收回(分組區塊也是)
  all('.axis, .range, .axis-group').forEach(box => setAxisOpen(box, false));
  updateCounts();
}

/**
 * 單一區塊的清除鈕(2026-08-17):只重置**這個區塊與其整棵子樹**的條件,其餘軸
 * 不動,也不重跑搜尋(與全域清除同一條裁示)。子樹跟著清是因為標題列的已選數
 * 彙總整棵子樹——鈕就在那個數字旁邊,按下去數字歸零才對得上;DOM 上子軸就巢狀
 * 在區塊裡,一次 querySelectorAll 撈得完。展開狀態不動:使用者正在這一軸上操作,
 * 順手收起來等於把人踢出去(全域清除的「回到初始狀態」不適用於單軸)。
 */
function clearBlock(box) {
  box.querySelectorAll('.tri').forEach(b => setTri(b, ''));
  box.querySelectorAll('.range-in').forEach(input => { input.value = ''; });
  // 清掉的可能是大類或效果類型:連動的子類組/怪獸參數/必發選發要跟著藏或現
  syncSubs();
  syncOptional();
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
    const clr = e.target.closest('.axis-clear');
    if (clr) {
      clearBlock(clr.closest('.axis, .range, .axis-group'));
      return;
    }
    const head = e.target.closest('.axis-head');
    if (head) {
      // 標題鈕的父層是 .axis-hrow(清除鈕的並排容器),摺疊的對象要往上找區塊
      setAxisOpen(head.closest('.axis, .range, .axis-group'),
                  head.getAttribute('aria-expanded') !== 'true');
      return;
    }
    const btn = e.target.closest('.tri');
    if (!btn) return;
    setTri(btn, nextState(btn.dataset.st, statesOf(btn)));
    // 比**最近的**軸而不是 closest 選擇器:軸是巢狀的,子類型的鈕往上也找得到
    // 大類的容器,直接用選擇器會把子軸的點擊誤判成大類的
    const ax = (btn.closest('.axis') || {}).dataset || {};
    if (ax.axis === 'cat') syncSubs();
    if (ax.axis === 'kind') syncOptional();
    updateCounts();
  });
  // 範圍輸入框打字也要讓標題列的已選數跟上(收起時看得見自己設了範圍)
  $('critParams').addEventListener('input', e => {
    if (e.target.closest('.range-in')) updateCounts();
  });
}

  return Object.freeze({ read, write, clear, init, axes, optionalAvailable,
                         nextState, count, axisCounts, treeCounts, expandedAxes,
                         summarize, collapse: () => setOpen(false),
                         LANGS, FIELDS });
})();
