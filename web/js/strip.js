'use strict';

/* 條件列(predicate-ui 規格 4 票 02 起,票 05 加左側條件標籤與 OR 區):結果上方列出這次查詢的
   全部條件,分 AND、OR 兩區。
   點動作標籤開右側抽屜改欄位(票 04)。
   接縫:Strip.init(事件) 接事件,Strip.render(狀態, 左側條件標籤) 照條件模型的答案重畫。條件狀態
   在主流程、文字與改法在條件模型、張數由主流程算;這裡只記抽屜開在哪一張。
   事件:onRemove(編號)、onEdit(編號, 新標籤)、onMove(編號, 區)、onSideRemove(鍵)、onSideGo(鍵)、
   onSideMove(鍵, 區)、onClear();countOf(標籤) 回單張張數。編號是 Cond.tags 的編號。
   桌面拖曳換區;手機拖不了,標籤上才看得到 ⇄(票 06)。底部面板只差 CSS。 */
const Strip = (() => {
const { $, esc } = Util;

/* 兩區的提示字與標示(原型 D 版,站主核可 2026-11-01)。 */
const HINTS = { and: '全部都要成立', or: '任一成立即可:把標籤移到這裡' };
const ZONE_LABEL = { and: 'AND', or: 'OR' };
/* ⇄ 換到的區:只有 AND、OR 兩區(規格 4 條件列段、Story 23,2026-11-02)。 */
const OTHER_ZONE = { and: 'or', or: 'and' };
const SWAP_HTML = '<button type="button" class="strip-swap" title="換到另一區">⇄</button>';
/* 自訂型別:拖到輸入框不會貼上文字,dragover 也不必另外記「正在拖標籤」。 */
const DRAG_TYPE = 'application/x-cond-tag';
const CLOSED = -1;

let handlers = null;
let shownState = null;       // 上次畫的狀態:抽屜的事件要知道改的是哪張標籤
let shownSide = null;        // 上次畫的左側條件標籤
let openAt = CLOSED;
let focusField = null;       // 開抽屜時要捲到的欄,捲完就清

function partHtml(part) {
  const glue = part.glue ? `<span class="strip-glue">${esc(part.glue)}</span> ` : '';
  const cls = part.field === '詞元' ? 'strip-lemma' : 'strip-val';
  return `${glue}<span class="${cls}" data-field="${esc(part.field)}">${esc(part.text)}</span>`;
}

function tagHtml(tag, i) {
  const lead = tag.ex ? '<span class="strip-lead">沒有</span> ' : '';
  const cls = (tag.ex ? ' ex' : '') + (i === openAt ? ' active' : '');
  return `<span class="strip-tag${cls}" draggable="true" data-i="${i}"
    title="${esc(Cond.note(tag))}">
    <span>${lead}${Cond.sentenceParts(tag).map(partHtml).join(' ')}</span>
    ${SWAP_HTML}<button type="button" class="strip-x" title="刪除">×</button></span>`;
}

function sideHtml(tag) {
  const label = tag.label ? `<span class="strip-glue">${esc(tag.label)}</span> ` : '';
  return `<span class="strip-tag side" draggable="true" data-key="${esc(tag.key)}" title="到左邊改">
    <span>${label}<span class="strip-val">${esc(tag.val)}</span></span>
    ${SWAP_HTML}<button type="button" class="strip-x" title="清掉這項">×</button></span>`;
}

function zoneHtml(zone, html) {
  return `<div class="strip-zone" data-zone="${zone}">
    <span class="strip-zone-l">${ZONE_LABEL[zone]}</span><div class="strip-tags">${
    html || `<span class="strip-hint">${esc(HINTS[zone])}</span>`}</div></div>`;
}

/* 選值鈕的狀態 → 樣式與提示(drawer-values 規格條件列與抽屜段):鎖住亮著但不能按,灰不能按;
   有提示的就是不能按的。 */
const CHIP_CLASS = { 亮: ' on', 鎖住: ' on', 可按: '', 灰: '' };
const CHIP_HINT = { 鎖住: '至少要留一個', 灰: '目前條件下沒有結果' };

function chipHtml({ value, state }) {
  const hint = CHIP_HINT[state];
  return `<button type="button" class="drawer-chip${CHIP_CLASS[state]}" data-act="toggle" data-v="${esc(value)}"${
    hint ? ` disabled title="${esc(hint)}"` : ''}>${esc(value)}</button>`;
}

function chipsHtml(tag, option) {
  return `<div class="drawer-chips">${option.values.map(chipHtml).join('')}</div>`;
}

function itemsHtml(tag, field, text) {
  return `<div class="drawer-chips">${Cond.values(tag, field).map((item, i) =>
    `<span class="drawer-item">${esc(text(item))}<button type="button" class="strip-x" data-act="drop" data-i="${i}" title="刪除">×</button></span>`).join('')}</div>`;
}

function regionHtml(tag, option) {
  const player = p => `<option value="${esc(p || '')}">${esc(p || '不限玩家')}</option>`;
  return `${itemsHtml(tag, option.field, item => (item[0] || '不限') + '・' + item[1])}
    <div class="drawer-add"><select data-role="player">${option.players.map(player).join('')}</select>
    <select data-act="add-region"><option value="">+ 區域</option>${
      option.zones.map(z => `<option>${esc(z)}</option>`).join('')}</select></div>`;
}

function textHtml(tag, option) {
  const id = 'drawerList' + option.field;
  return `${itemsHtml(tag, option.field, String)}
    <div class="drawer-add"><input list="${esc(id)}" data-act="add-text" placeholder="中心詞(尾綴比對)"></div>
    <datalist id="${esc(id)}">${option.candidates.map(w => `<option value="${esc(w)}">`).join('')}</datalist>`;
}

/* 抽屜選項一欄的種類 → 那一欄的畫法。 */
const FIELD_BODY = { values: chipsHtml, region: regionHtml, text: textHtml };

function fieldHtml(tag, option) {
  return `<div class="drawer-field" data-field="${esc(option.field)}"><div class="drawer-label">${
    esc(option.field)}</div>${FIELD_BODY[option.kind](tag, option)}</div>`;
}

/* 常用欄在抽屜頭下面直接接,不畫小標;其他組畫小標。組沒有欄時抽屜選項不列它,小標也不畫。 */
const PLAIN_GROUP = '常用';

function groupHtml(tag, { group, fields }) {
  const head = group === PLAIN_GROUP ? '' : `<div class="drawer-group">${esc(group)}</div>`;
  return head + fields.map(option => fieldHtml(tag, option)).join('');
}

function drawerHtml(tag) {
  const from = Cond.editedFrom(tag);
  const seg = (label, ex) => `<button type="button" class="${tag.ex === ex ? 'on' + (ex ? ' ex' : '') : ''}" data-act="mode" data-ex="${ex ? 1 : 0}">${label}</button>`;
  return `<div class="drawer-head"><span class="drawer-name${Cond.named(tag) ? ' named' : ''}">${esc(Cond.sentence(tag))}</span>
      <span class="drawer-seg">${seg('包含', false)}${seg('排除', true)}</span>
      <button type="button" class="strip-x" data-act="close" title="關閉">✕</button></div>
    <div class="drawer-note"><span>${handlers.countOf(tag).toLocaleString()} 張</span>${from ? `<span>改自 ${esc(from)}</span>
      <button type="button" class="drawer-btn" data-act="restore">還原</button>` : ''}
      <button type="button" class="drawer-btn drawer-remove" data-act="remove">刪除這張</button></div>
    ${Cond.drawerOptions(tag).map(group => groupHtml(tag, group)).join('')}`;
}

/* 整個重畫:捲動位置與正在打字的中心詞框要留著,加完一個詞可以接著打下一個。 */
function renderDrawer(tag) {
  const drawer = $('condDrawer');
  drawer.hidden = !tag;
  if (!tag) { drawer.innerHTML = ''; return; }
  const typing = document.activeElement && document.activeElement.matches('#condDrawer input')
    ? document.activeElement.closest('[data-field]').dataset.field : null;
  const top = drawer.scrollTop;
  drawer.innerHTML = drawerHtml(tag);
  drawer.scrollTop = top;
  if (typing) drawer.querySelector(`[data-field="${typing}"] input`).focus();
  const target = focusField && drawer.querySelector(`[data-field="${focusField}"]`);
  if (target) {
    target.classList.add('focus');
    target.scrollIntoView({ block: 'center' });
  }
  focusField = null;
}

/* 同一區裡左側條件在前、動作標籤在後(原型 D 版)。 */
function render(state, sideTags) {
  shownState = state;
  shownSide = sideTags;
  if (openAt >= Cond.tags(state).length) openAt = CLOSED;
  const andCount = Cond.tagsIn(state, 'and').length;
  const zone = (name, first) => sideTags.filter(t => Cond.sideZone(state, t.key) === name)
    .map(sideHtml).join('') +
    Cond.tagsIn(state, name).map((tag, i) => tagHtml(tag, first + i)).join('');
  const none = !sideTags.length && !Cond.tags(state).length;
  $('condStrip').innerHTML = `<div class="strip-top"><button type="button" class="strip-clear"${
    none ? ' disabled' : ''}>清除條件</button></div>` +
    zoneHtml('and', zone('and', 0)) + zoneHtml('or', zone('or', andCount));
  renderDrawer(openAt === CLOSED ? null : Cond.tags(state)[openAt]);
}

function closeDrawer() {
  if (openAt === CLOSED) return;
  openAt = CLOSED;
  render(shownState, shownSide);
}

function openDrawer(i, field) {
  openAt = i;
  focusField = field;
  render(shownState, shownSide);
}

/* 刪除與換區都會讓編號移動,抽屜先關,不會開到別張去。 */
function removeAt(i) {
  openAt = CLOSED;
  handlers.onRemove(i);
}

/* 一張標籤怎麼指:左側條件標籤走鍵,動作標籤走編號。拖曳與 ⇄ 共用。 */
const refOf = el => (el.dataset.key ? { key: el.dataset.key } : { i: +el.dataset.i });

function moveRef(ref, zone) {
  openAt = CLOSED;
  if (ref.key) handlers.onSideMove(ref.key, zone);
  else handlers.onMove(ref.i, zone);
}

const openTag = () => Cond.tags(shownState)[openAt];

/* 中心詞框還沒按 Enter 就按別的鈕:失焦會先把字收進標籤、重畫抽屜與條件列,按到的鈕被換掉,那一下
   點擊落空。所以框裡有字時按下不搶焦點,點擊才收字。下拉選單攔不了(會打不開),仍要再點一次。 */
function typedInput() {
  const el = document.activeElement;
  return el && el.matches('#condDrawer input') && el.value.trim() ? el : null;
}

function holdFocus(e) {
  if (!typedInput()) return;
  const t = e.target;
  if (t.closest('#condDrawer button') || t.closest('#condStrip .strip-tag') || t.closest('#condStrip .strip-clear')) {
    e.preventDefault();
  }
}

/* blur 同步發 change,字走 onDrawerChange 收進標籤。 */
function commitTyped() {
  const el = typedInput();
  if (el) el.blur();
}

function onDrawerClick(e) {
  const el = e.target.closest('[data-act]');
  if (!el || el.matches('select, input')) return;
  const box = el.closest('[data-field]');
  const field = box && box.dataset.field;
  /* × 的編號是點下去時畫面上的清單;字收進來後清單可能重排,所以先取出那個值。 */
  const dropped = el.dataset.act === 'drop' ? Cond.values(openTag(), field)[+el.dataset.i] : null;
  commitTyped();
  const tag = openTag();
  const edit = next => handlers.onEdit(openAt, next);
  switch (el.dataset.act) {
    case 'close': closeDrawer(); break;
    case 'remove': removeAt(openAt); break;
    case 'restore': edit(Cond.restore(tag)); break;
    case 'mode': edit(Cond.setEx(tag, el.dataset.ex === '1')); break;
    case 'toggle': edit(Cond.toggleValue(tag, field, el.dataset.v)); break;
    case 'drop': edit(Cond.removeValue(tag, field, dropped)); break;
  }
}

/* 中心詞框只能挑清單:字等於這一欄候選的某一項才收(drawer-values 規格條件列與抽屜段)。 */
function candidatesOf(tag, field) {
  const option = Cond.drawerOptions(tag).flatMap(g => g.fields).find(f => f.field === field);
  return option ? option.candidates : [];
}

function onDrawerChange(e) {
  const el = e.target;
  const value = el.value.trim();
  if (!value || !el.dataset.act) return;
  const tag = openTag();
  const box = el.closest('[data-field]');
  if (el.dataset.act === 'add-text' && candidatesOf(tag, box.dataset.field).indexOf(value) < 0) {
    el.value = '';
    return;
  }
  const item = el.dataset.act === 'add-region'
    ? [box.querySelector('[data-role="player"]').value || null, value] : value;
  handlers.onEdit(openAt, Cond.addValue(tag, box.dataset.field, item));
}

/* 事件冒到 document 時抽屜可能已經重畫,點到的節點脫離了文件,closest 找不到祖先;
   用 composedPath 看派送當下的路徑。左側條件標籤不開抽屜,算外面。 */
function onDocumentClick(e) {
  if (openAt === CLOSED) return;
  const inside = e.composedPath().some(el => el.matches &&
    el.matches('#condDrawer, .strip-tag:not(.side)'));
  if (!inside) closeDrawer();
}

function clearOver(except) {
  $('condStrip').querySelectorAll('.strip-zone.over').forEach(z => {
    if (z !== except) z.classList.remove('over');
  });
}

function initDrag() {
  const strip = $('condStrip');
  strip.addEventListener('dragstart', e => {
    const tag = e.target.closest('.strip-tag');
    if (!tag) return;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData(DRAG_TYPE, JSON.stringify(refOf(tag)));
  });
  strip.addEventListener('dragover', e => {
    const zone = e.target.closest('.strip-zone');
    if (!zone || Array.from(e.dataTransfer.types).indexOf(DRAG_TYPE) < 0) return;
    e.preventDefault();
    clearOver(zone);
    zone.classList.add('over');
  });
  strip.addEventListener('dragleave', e => {
    if (e.target === strip) clearOver(null);
  });
  strip.addEventListener('dragend', () => clearOver(null));
  strip.addEventListener('drop', e => {
    const zone = e.target.closest('.strip-zone');
    const ref = e.dataTransfer.getData(DRAG_TYPE);
    if (!zone || !ref) return;
    e.preventDefault();
    clearOver(null);
    moveRef(JSON.parse(ref), zone.dataset.zone);
  });
}

function init(events) {
  handlers = events;
  const { onSideRemove, onSideGo, onClear } = events;
  $('condStrip').addEventListener('click', e => {
    commitTyped();
    if (e.target.closest('.strip-clear')) { onClear(); return; }
    const tag = e.target.closest('.strip-tag');
    if (!tag) return;
    if (e.target.closest('.strip-swap')) {
      moveRef(refOf(tag), OTHER_ZONE[tag.closest('.strip-zone').dataset.zone]);
      return;
    }
    const x = e.target.closest('.strip-x');
    if (tag.dataset.key) (x ? onSideRemove : onSideGo)(tag.dataset.key);
    else if (x) removeAt(+tag.dataset.i);
    else {
      const word = e.target.closest('[data-field]');
      openDrawer(+tag.dataset.i, word ? word.dataset.field : null);
    }
  });
  $('condDrawer').addEventListener('click', onDrawerClick);
  $('condDrawer').addEventListener('change', onDrawerChange);
  document.addEventListener('mousedown', holdFocus);
  document.addEventListener('click', onDocumentClick);
  initDrag();
}

  return Object.freeze({ init, render, closeDrawer });
})();
