'use strict';

const Query = (() => {
const { $, VOCAB, esc } = Util;

const LANGS = [
  { v: 'zh', label: '中', title: '比對中文卡名（含 ※ 別名）' },
  { v: 'ja', label: '日', title: '比對日文卡名（含 ※ 別名）' },
  { v: 'en', label: '英', title: '比對英文卡名' },
];

const FIELDS = [
  { tri: 'cat', dom: 'cat', states: 2 },
  { tri: 'kind', dom: 'kind' },
  { tri: 'opt', dom: 'optional' },
  { tri: 'sub', dom: 'sub_m', side: 'm', parent: 'cat', groupBlocks: true,
    groupAfter: { '能力': 'race' } },
  { tri: 'sub', dom: 'sub_s', side: 's', parent: 'cat' },
  { tri: 'sub', dom: 'sub_t', side: 't', parent: 'cat' },
  { tri: 'attr', dom: 'attr', mon: true, parent: 'sub_m' },
  { tri: 'race', dom: 'race', mon: true, parent: 'sub_m' },
  { range: 'lv', zh: '等級／階級', mon: true, parent: 'sub_m' },
  { range: 'lk', zh: '連結值', mon: true, parent: 'sub_m' },
  { range: 'sc', zh: '靈擺刻度', mon: true, parent: 'sub_m' },
  { range: 'atk', zh: '攻擊力', unknown: 'atkq', mon: true, parent: 'sub_m' },
  { range: 'df', zh: '守備力', unknown: 'dfq', mon: true, parent: 'sub_m' },
  { tri: 'lm', dom: 'lm', mon: true, parent: 'sub_m', grid9: true },
  { tri: 'rarity', dom: 'rarity' },
  { range: 'gy', zh: 'Genesys 點數' },
  { tri: 'ot', dom: 'ot' },
  { group: 'ban', zh: '禁限' },
  { tri: 'ban_o', dom: 'ban_o', parent: 'ban' },
  { tri: 'ban_t', dom: 'ban_t', parent: 'ban' },
  { tri: 'ban_m', dom: 'ban_m', parent: 'ban' },
];

const CATALOG_AFTER = 'opt';

const STATES = ['', 'in', 'ex'];
const STATE_TITLE = {
  3: { '': '未選（再點一次＝包含）', in: '包含（再點一次＝排除）',
       ex: '排除（再點一次＝取消）' },
  2: { '': '未選（再點一次＝選取）', in: '選取（再點一次＝取消）' },
};

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

function axes() {
  return FIELDS.filter(f => f.tri).map(f => {
    const dom = VOCAB[f.dom] || {};
    const items = dom.items || [];
    const byCode = {};
    items.forEach(it => { byCode[it.code] = it; });
    const groups = (dom.groups || []).length
      ? dom.groups.map(g => ({ zh: g.zh,
                               items: g.codes.map(c => byCode[c]).filter(Boolean) }))
      : [{ zh: '', items }];
    return { key: f.tri, dom: f.dom, side: f.side || '', zh: dom.zh || f.dom,
             states: f.states || 3, mon: !!f.mon,
             groupBlocks: !!f.groupBlocks, groupAfter: f.groupAfter || {},
             grid9: !!f.grid9, groups };
  });
}

function optionalAvailable(kindSel) {
  const dom = VOCAB.optional || {};
  const carriers = dom.carriers || [];
  const combos = dom.combos || {};
  const included = Object.keys(kindSel || {}).filter(c => kindSel[c] > 0);
  const kindsOf = code => combos[code]
    ? [combos[code].slice(0, combos[code].indexOf(':'))] : carriers;
  return (dom.groups || []).map(g => !included.length ||
    (g.codes || []).some(code => kindsOf(code)
      .some(k => included.indexOf(k) >= 0)));
}

function triBtn(code, zh, states) {
  return `<button type="button" class="tri" data-code="${esc(code)}"
    data-st="" title="${STATE_TITLE[states || 3]['']}">${esc(zh)}</button>`;
}

/* 清除鈕與標題鈕並排而不是巢狀:button 不能包 button。 */
function headHtml(zh) {
  return `<div class="axis-hrow"><button type="button" class="axis-head"
    aria-expanded="false"><span class="axis-name">${esc(zh)}</span>
    <span class="axis-count"></span></button>
    <button type="button" class="axis-clear" hidden
      title="清除這一組條件">×</button></div>`;
}

function axisHtml(ax, kids) {
  kids = kids || [];
  const anchored = {};
  let own = '';
  ax.groups.forEach((g, gi) => {
    const btns = g.items.map(it => triBtn(it.code, it.zh, ax.states));
    if (ax.grid9) btns.splice(4, 0, '<span class="tri-mid"></span>');
    const row = `<div class="tri-row${ax.grid9 ? ' tri-grid9' : ''}">${
      btns.join('')}</div>`;
    const html = g.zh && ax.groupBlocks
      ? `<div class="axis-group" data-group-key="${ax.dom}/${gi}">
        ${headHtml(g.zh)}<div class="axis-body" hidden>${row}</div></div>`
      : g.zh ? `<div class="tri-group">
      <span class="group-label">${esc(g.zh)}</span>${row}</div>` : row;
    const dest = ax.groupAfter[g.zh];
    if (dest) (anchored[dest] = anchored[dest] || []).push(html);
    else own += html;
  });
  let body = own + kids.map(k => {
    const extra = (anchored[k.key] || []).join('');
    delete anchored[k.key];
    return k.html + extra;
  }).join('');
  for (const dest in anchored) body += anchored[dest].join('');
  return `<div class="axis" data-axis="${ax.key}" data-side="${ax.side}"
    data-states="${ax.states}"${ax.side || ax.mon ? ' hidden' : ''}>
    ${headHtml(ax.zh)}<div class="axis-body" hidden>${body}</div></div>`;
}

function rangeHtml(f) {
  const num = which => `<input type="number" class="range-in"
    data-key="${f.range}" data-end="${which}" aria-label="${esc(f.zh)}${
    which === 'min' ? '下限' : '上限'}">`;
  const unknown = f.unknown
    ? `<button type="button" class="tri tri-q" data-code="?" data-st=""
        data-unknown="${f.unknown}" title="${STATE_TITLE[3]['']}">?</button>` : '';
  return `<div class="range" data-range="${f.range}"${f.mon ? ' hidden' : ''}>
    ${headHtml(f.zh)}<div class="axis-body" hidden>
    <div class="range-row">${num('min')}<span class="range-sep">～</span>${
      num('max')}${unknown}</div></div></div>`;
}

function groupBoxHtml(f, kids) {
  return `<div class="axis" data-axis="${f.group}" data-side=""
    data-states="3">${headHtml(f.zh)}<div class="axis-body" hidden>${
    (kids || []).map(k => k.html).join('')}</div></div>`;
}

/* 具名查詢目錄導覽(規格 4 目錄導覽段):樹由 Acat.catalog 來,這裡只畫。點具名查詢的列
   是包含、點 − 是排除;點大類、中類只展開。初始全部收合,寫回條件時也不動展開狀態:
   上一頁或清除條件時,使用者正在看的那一段樹不該收起來。 */
function catalogNodeHtml(key) {
  const n = Acat.catalog.node(key);
  const tog = n.kids.length
    ? '<button type="button" class="cat-tog" aria-expanded="false" aria-label="展開或收合"></button>'
    : '<span class="cat-tog-pad"></span>';
  const count = n.count
    ? `<span class="cat-n">${esc(n.count.text)}</span>` : '';
  const cls = (n.path ? '' : ' group') + (n.count && n.count.zero ? ' zero' : '');
  const pick = n.path ? ` data-path="${esc(n.path)}"` : '';
  const minus = n.path
    ? `<button type="button" class="cat-minus" data-path="${esc(n.path)}" title="排除：沒有這個動作">−</button>`
    : '';
  return `<li class="cat-node" data-key="${esc(key)}"><div class="cat-row">${tog}
    <button type="button" class="cat-pick${cls}"${pick}><span>${esc(n.name)}</span>
      <span class="cat-used" hidden>已用</span>${count}</button>${minus}</div>${
    n.kids.length ? `<ul class="cat-kids" hidden>${
      n.kids.map(catalogNodeHtml).join('')}</ul>` : ''}</li>`;
}

function catalogHtml() {
  return `<div class="catalog" id="catalogNav">
    <div class="cat-title">動作<span class="cat-note">點一列包含、點 − 排除</span></div>
    <input type="search" class="cat-filter" placeholder="過濾：例 墓地"
      aria-label="過濾具名查詢目錄（比對日文名稱）">
    <div class="cat-scroll"><ul class="cat-tree">${
      Acat.catalog.roots.map(catalogNodeHtml).join('')}</ul></div></div>`;
}

function catalogNodes() {
  return Array.prototype.slice.call($('catalogNav').querySelectorAll('.cat-node'));
}

function setNodeOpen(li, open) {
  const tog = li.querySelector(':scope > .cat-row > .cat-tog');
  const kids = li.querySelector(':scope > .cat-kids');
  if (!tog || !kids) return;
  tog.setAttribute('aria-expanded', open ? 'true' : 'false');
  kids.hidden = !open;
}

function nodeOpen(li) {
  const tog = li.querySelector(':scope > .cat-row > .cat-tog');
  return !!tog && tog.getAttribute('aria-expanded') === 'true';
}

/* 過濾框(Acat.catalog.filter 決定留哪些、展開哪些祖先):開始過濾前記下各節點的展開狀態,
   每次換字面都從那份狀態重套,清空時還原——過濾只是「找」,不改展開也不改條件。 */
let catalogSaved = null;

function applyCatalogFilter(term) {
  const f = Acat.catalog.filter(term);
  const nodes = catalogNodes();
  if (f && !catalogSaved) {
    catalogSaved = {};
    nodes.forEach(li => { catalogSaved[li.dataset.key] = nodeOpen(li); });
  }
  if (catalogSaved) nodes.forEach(li => setNodeOpen(li, catalogSaved[li.dataset.key]));
  nodes.forEach(li => {
    li.hidden = !!f && !f.visible.has(li.dataset.key);
    if (f && f.open.has(li.dataset.key)) setNodeOpen(li, true);
  });
  if (!f) catalogSaved = null;
}

function markUsed(paths) {
  const used = new Set(paths);
  $('catalogNav').querySelectorAll('.cat-pick[data-path]').forEach(btn => {
    const on = used.has(btn.dataset.path);
    btn.classList.toggle('used', on);
    btn.querySelector('.cat-used').hidden = !on;
  });
}

function initCatalog(onPick) {
  const nav = $('catalogNav');
  nav.addEventListener('click', e => {
    const minus = e.target.closest('.cat-minus');
    if (minus) { onPick(minus.dataset.path, true); return; }
    const pick = e.target.closest('.cat-pick');
    if (pick && pick.dataset.path) { onPick(pick.dataset.path, false); return; }
    if (pick || e.target.closest('.cat-tog')) {
      const li = e.target.closest('.cat-node');
      setNodeOpen(li, !nodeOpen(li));
    }
  });
  nav.addEventListener('input', e => {
    if (e.target.closest('.cat-filter')) applyCatalogFilter(e.target.value);
  });
}

function build() {
  const axisByKey = {};
  axes().forEach(ax => { axisByKey[ax.key + '/' + ax.side] = ax; });
  const htmlOf = f => f.tri
    ? axisHtml(axisByKey[f.tri + '/' + (f.side || '')], kidsOf(blockKey(f)))
    : f.group ? groupBoxHtml(f, kidsOf(blockKey(f)))
    : rangeHtml(f);
  const kidsOf = key => FIELDS.filter(f => f.parent === key)
    .map(f => ({ key: blockKey(f), html: htmlOf(f) }));
  /* 目錄接在句層條件(大類、效果類型、必發／選發)後面,不是一條軸,不進 FIELDS。 */
  $('critParams').innerHTML = FIELDS.filter(f => !f.parent).map(f =>
    htmlOf(f) + (f.tri === CATALOG_AFTER ? catalogHtml() : '')).join('');
}

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

function ownTris(el) {
  return Array.prototype.filter.call(
    el.querySelectorAll('.tri'),
    btn => btn.closest('.axis') === el);
}

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

function read() {
  const q = {
    name: $('fName').value.trim(),
    nameLang: langOf($('fNameLang').dataset.v).v,
    code: $('fId').value.trim(),
    text: $('fText').value.trim(),
  };
  if ($('fTextMat').checked) q.textMat = 1;
  FIELDS.forEach(f => {
    if (f.group) return;
    (f.tri ? readTri : readRange)(q, f);
  });
  return q;
}

function count(q) {
  const isSet = v => {
    if (v == null || v === '') return false;
    if (typeof v !== 'object') return true;
    return Object.keys(v).some(k => v[k] != null);
  };
  return Object.keys(q || {})
    .filter(k => k !== 'nameLang' && k !== 'textMat' && isSet(q[k])).length;
}

function blockKey(f) {
  return f.tri ? f.dom : (f.range || f.group);
}

function blockEl(f) {
  if (f.range) {
    return $('critParams').querySelector(`.range[data-range="${f.range}"]`);
  }
  return axisEl(f.tri || f.group, f.side);
}

function axisCounts(q) {
  q = q || {};
  const out = {};
  FIELDS.forEach(f => {
    if (f.group) { out[blockKey(f)] = 0; return; }
    if (f.tri) {
      const sel = q[f.tri] || {};
      out[blockKey(f)] = Object.keys(sel).filter(k => sel[k] &&
        (!f.side || k.indexOf(f.side + ':') === 0)).length;
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

function treeCounts(q) {
  const counts = axisCounts(q);
  const own = key => {
    if (key !== 'cat') return counts[key] || 0;
    const sel = (q || {}).cat || {};
    return Object.keys(sel).filter(c => sel[c] &&
      !FIELDS.some(f => f.parent === 'cat' && f.side === c &&
                        total(blockKey(f)) > 0)).length;
  };
  const total = key => FIELDS.filter(f => f.parent === key)
    .reduce((n, f) => n + total(blockKey(f)), own(key));
  const out = {};
  FIELDS.forEach(f => { out[blockKey(f)] = total(blockKey(f)); });
  return out;
}

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
    for (let k = key; on && k; k = parentOf[k]) open[k] = true;
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

function setOpen(open) {
  const btn = $('btnFilters');
  $('sidebar').classList.toggle('open', open);
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}

function isOpen() {
  return $('btnFilters').getAttribute('aria-expanded') === 'true';
}

function summarize(n) {
  $('btnFilters').textContent = n ? `篩選條件・${n} 項` : '篩選條件';
}

function statesOf(btn) {
  const box = btn.closest('.axis, .range');
  return box && +box.dataset.states === 2 ? 2 : 3;
}

function setTri(btn, st) {
  btn.dataset.st = st;
  btn.title = STATE_TITLE[statesOf(btn)][st];
}

function setAxisOpen(box, open) {
  const head = box.querySelector('.axis-head');
  if (!head) return;
  head.setAttribute('aria-expanded', open ? 'true' : 'false');
  box.querySelector('.axis-body').hidden = !open;
}

function updateCounts() {
  const q = read();
  const stamp = (box, n) => {
    box.querySelector('.axis-count').textContent = n ? String(n) : '';
    box.querySelector('.axis-clear').hidden = !n;
  };
  const tree = treeCounts(q);
  FIELDS.forEach(f => stamp(blockEl(f), tree[blockKey(f)]));
  const flat = axisCounts(q);
  all('.axis-group').forEach(box => stamp(box, flat[box.dataset.groupKey]));
}

function showAxis(el, show, expand) {
  if (el.hidden === !show) return;
  if (show) {
    if (expand) setAxisOpen(el, true);
  } else {
    el.querySelectorAll('.tri').forEach(b => setTri(b, ''));
    el.querySelectorAll('.range-in').forEach(input => { input.value = ''; });
    el.querySelectorAll('.axis-group').forEach(b => setAxisOpen(b, false));
    setAxisOpen(el, false);
  }
  el.hidden = !show;
}

function syncSubs() {
  const cat = axisEl('cat', '');
  const on = side => {
    const btn = ownTris(cat).find(b => b.dataset.code === side);
    return !!btn && btn.dataset.st === 'in';
  };
  FIELDS.filter(f => f.tri === 'sub').forEach(
    f => showAxis(axisEl('sub', f.side), on(f.side), true));
  FIELDS.filter(f => f.mon).forEach(f => showAxis(blockEl(f), on('m'), false));
}

function showGroup(el, show) {
  if (el.hidden === !show) return;
  if (!show) el.querySelectorAll('.tri').forEach(b => setTri(b, ''));
  el.hidden = !show;
}

function syncOptional() {
  const el = axisEl('opt', '');
  const avail = optionalAvailable(triSel(FIELDS.find(f => f.tri === 'kind')));
  el.querySelectorAll('.tri-group').forEach((g, gi) => showGroup(g, !!avail[gi]));
  showAxis(el, avail.some(Boolean), true);
}

function writeTri(q, f) {
  const el = axisEl(f.tri, f.side);
  const ex = (f.states || 3) === 2 ? '' : 'ex';
  const base = (el.hidden ? null : q[f.tri]) || {};
  ownTris(el).forEach(btn => {
    const grp = btn.closest('.tri-group');
    const sel = grp && grp.hidden ? {} : base;
    const key = f.side ? f.side + ':' + btn.dataset.code : btn.dataset.code;
    setTri(btn, sel[key] > 0 ? 'in' : (sel[key] < 0 ? ex : ''));
  });
}

function writeRange(q, f) {
  const box = $('critParams').querySelector(`.range[data-range="${f.range}"]`);
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

function write(q) {
  q = q || {};
  clear();
  $('fName').value = q.name || '';
  $('fId').value = q.code || '';
  $('fText').value = q.text || '';
  $('fTextMat').checked = !!q.textMat;
  showLang($('fNameLang'), langOf(q.nameLang).v);
  FIELDS.filter(f => f.tri === 'cat' || f.tri === 'kind')
    .forEach(f => writeTri(q, f));
  syncSubs();
  syncOptional();
  FIELDS.forEach(f => {
    if (f.group) return;
    (f.tri ? writeTri : writeRange)(q, f);
  });
  updateCounts();
  const open = expandedAxes(read());
  FIELDS.forEach(f => setAxisOpen(blockEl(f), open.indexOf(blockKey(f)) >= 0));
  all('.axis-group').forEach(box =>
    setAxisOpen(box, open.indexOf(box.dataset.groupKey) >= 0));
}

function clear() {
  $('fName').value = '';
  $('fId').value = '';
  $('fText').value = '';
  $('fTextMat').checked = false;
  showLang($('fNameLang'), LANGS[0].v);
  all('.tri').forEach(btn => setTri(btn, ''));
  all('.range-in').forEach(input => { input.value = ''; });
  syncSubs();
  syncOptional();
  all('.axis, .range, .axis-group').forEach(box => setAxisOpen(box, false));
  updateCounts();
}

function clearBlock(box) {
  box.querySelectorAll('.tri').forEach(b => setTri(b, ''));
  box.querySelectorAll('.range-in').forEach(input => { input.value = ''; });
  syncSubs();
  syncOptional();
  updateCounts();
}

function init({ onPick }) {
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
  initCatalog(onPick);
  $('critParams').addEventListener('click', e => {
    const clr = e.target.closest('.axis-clear');
    if (clr) {
      clearBlock(clr.closest('.axis, .range, .axis-group'));
      return;
    }
    const head = e.target.closest('.axis-head');
    if (head) {
      setAxisOpen(head.closest('.axis, .range, .axis-group'),
                  head.getAttribute('aria-expanded') !== 'true');
      return;
    }
    const btn = e.target.closest('.tri');
    if (!btn) return;
    setTri(btn, nextState(btn.dataset.st, statesOf(btn)));
    const ax = (btn.closest('.axis') || {}).dataset || {};
    if (ax.axis === 'cat') syncSubs();
    if (ax.axis === 'kind') syncOptional();
    updateCounts();
  });
  $('critParams').addEventListener('input', e => {
    if (e.target.closest('.range-in')) updateCounts();
  });
}

  return Object.freeze({ read, write, clear, init, axes,
                         optionalAvailable,
                         nextState, count, axisCounts, treeCounts, expandedAxes,
                         summarize, markUsed, collapse: () => setOpen(false),
                         LANGS, FIELDS });
})();
