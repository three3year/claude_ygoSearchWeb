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

/* 提示字(原型 D 版)。 */
const HINTS = { and: '全部都要成立', or: '任一成立即可:把標籤移到這裡' };
const ZONE_LABEL = { and: 'AND', or: 'OR' };
const OTHER_ZONE = { and: 'or', or: 'and' };
const SWAP_HTML = '<button type="button" class="strip-swap" title="換到另一區">⇄</button>';
/* 自訂型別:拖到輸入框不會貼上文字,dragover 也不必另外記「正在拖標籤」。 */
const DRAG_TYPE = 'application/x-cond-tag';
const CLOSED = -1;

let handlers = null;
let shown = null;            // 上次畫的 [狀態, 左側條件標籤]:抽屜的事件要知道改的是哪張標籤
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

const chipHtml = (value, on) =>
  `<button type="button" class="drawer-chip${on ? ' on' : ''}" data-act="toggle" data-v="${esc(value)}">${esc(value)}</button>`;

function itemsHtml(tag, field, text) {
  return `<div class="drawer-chips">${Cond.values(tag, field).map((item, i) =>
    `<span class="drawer-item">${esc(text(item))}<button type="button" class="strip-x" data-act="drop" data-i="${i}" title="刪除">×</button></span>`).join('')}</div>`;
}

function regionHtml(tag, field, editor) {
  const player = p => `<option value="${esc(p || '')}">${esc(p || '不限玩家')}</option>`;
  return `${itemsHtml(tag, field, item => (item[0] || '不限') + '・' + item[1])}
    <div class="drawer-add"><select data-role="player">${editor.players.map(player).join('')}</select>
    <select data-act="add-region"><option value="">+ 區域</option>${
      editor.zones.map(z => `<option>${esc(z)}</option>`).join('')}</select></div>`;
}

function textHtml(tag, field, editor) {
  const id = 'drawerList' + field;
  return `${itemsHtml(tag, field, String)}
    <div class="drawer-add"><input list="${esc(id)}" data-act="add-text" placeholder="中心詞(尾綴比對)"></div>
    <datalist id="${esc(id)}">${editor.candidates.map(w => `<option value="${esc(w)}">`).join('')}</datalist>`;
}

function fieldHtml(tag, field) {
  const editor = Cond.editor(field);
  const body = editor.kind === 'region' ? regionHtml(tag, field, editor)
    : editor.kind === 'text' ? textHtml(tag, field, editor)
    : `<div class="drawer-chips">${editor.values.map(v =>
        chipHtml(v, Cond.values(tag, field).indexOf(v) >= 0)).join('')}</div>`;
  return `<div class="drawer-field" data-field="${esc(field)}"><div class="drawer-label">${esc(field)}</div>${body}</div>`;
}

function drawerHtml(tag) {
  const from = Cond.editedFrom(tag);
  const seg = (label, ex) => `<button type="button" class="${tag.ex === ex ? 'on' + (ex ? ' ex' : '') : ''}" data-act="mode" data-ex="${ex ? 1 : 0}">${label}</button>`;
  const groups = Cond.drawerGroups();
  const fields = list => list.map(f => fieldHtml(tag, f)).join('');
  return `<div class="drawer-head"><span class="drawer-name${Cond.named(tag) ? ' named' : ''}">${esc(Cond.sentence(tag))}</span>
      <span class="drawer-seg">${seg('包含', false)}${seg('排除', true)}</span>
      <button type="button" class="strip-x" data-act="close" title="關閉">✕</button></div>
    <div class="drawer-note"><span>${handlers.countOf(tag).toLocaleString()} 張</span>${from ? `<span>改自 ${esc(from)}</span>
      <button type="button" class="drawer-btn" data-act="restore">還原</button>` : ''}
      <button type="button" class="drawer-btn drawer-remove" data-act="remove">刪除這張</button></div>
    ${fields(groups.常用)}<div class="drawer-group">進階</div>${fields(groups.進階)}`;
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
  shown = [state, sideTags];
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
  render(shown[0], shown[1]);
}

function openDrawer(i, field) {
  openAt = i;
  focusField = field;
  render(shown[0], shown[1]);
}

/* 刪除與換區都會讓編號移動,抽屜先關,不會開到別張去。 */
function removeAt(i) {
  openAt = CLOSED;
  handlers.onRemove(i);
}

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
  const dropped = el.dataset.act === 'drop' ? Cond.values(Cond.tags(shown[0])[openAt], field)[+el.dataset.i] : null;
  commitTyped();
  const tag = Cond.tags(shown[0])[openAt];
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

function onDrawerChange(e) {
  const el = e.target;
  const value = el.value.trim();
  if (!value || !el.dataset.act) return;
  const tag = Cond.tags(shown[0])[openAt];
  const box = el.closest('[data-field]');
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

function initDrag({ onMove, onSideMove }) {
  const strip = $('condStrip');
  strip.addEventListener('dragstart', e => {
    const tag = e.target.closest('.strip-tag');
    if (!tag) return;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData(DRAG_TYPE, tag.dataset.key ? 'k' + tag.dataset.key : 'i' + tag.dataset.i);
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
    openAt = CLOSED;
    if (ref.charAt(0) === 'k') onSideMove(ref.slice(1), zone.dataset.zone);
    else onMove(+ref.slice(1), zone.dataset.zone);
  });
}

function init(events) {
  handlers = events;
  const { onMove, onSideRemove, onSideGo, onSideMove, onClear } = events;
  $('condStrip').addEventListener('click', e => {
    commitTyped();
    if (e.target.closest('.strip-clear')) { onClear(); return; }
    const tag = e.target.closest('.strip-tag');
    if (!tag) return;
    if (e.target.closest('.strip-swap')) {
      const zone = OTHER_ZONE[tag.closest('.strip-zone').dataset.zone];
      openAt = CLOSED;
      if (tag.dataset.key) onSideMove(tag.dataset.key, zone);
      else onMove(+tag.dataset.i, zone);
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
  initDrag({ onMove, onSideMove });
}

  return Object.freeze({ init, render, closeDrawer });
})();
