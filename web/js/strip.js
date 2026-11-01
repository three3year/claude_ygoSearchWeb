'use strict';

/* 條件列(predicate-ui 規格 4 票 02 起):結果上方列出這次查詢的動作標籤;點標籤開右側抽屜
   改欄位(票 04)。
   接縫:Strip.init({onRemove, onEdit, countOf}) 接事件,Strip.render(狀態) 照條件模型的答案
   重畫。條件狀態在主流程、文字與改法在條件模型、張數由主流程算;這裡只記抽屜開在哪一張。
   目前只有 AND 區與 ×;OR 區、拖曳、左側條件標籤是票 05,手機的底部面板是票 06。 */
const Strip = (() => {
const { $, esc } = Util;

const HINT = '從左邊選條件';
const CLOSED = -1;

let handlers = null;
let shown = Cond.empty();    // 上次畫的狀態:抽屜的事件要知道改的是哪張標籤
let openAt = CLOSED;
let focusField = null;       // 開抽屜時要捲到的欄,捲完就清

function partHtml(part) {
  const glue = part.glue ? `<span class="strip-glue">${esc(part.glue)}</span> ` : '';
  const cls = part.field === '詞元' ? 'strip-lemma' : 'strip-val';
  return `${glue}<button type="button" class="strip-tok ${cls}" data-field="${esc(part.field)}">${esc(part.text)}</button>`;
}

function tagHtml(tag, i) {
  const lead = tag.ex ? '<span class="strip-lead">沒有</span> ' : '';
  const cls = (tag.ex ? ' ex' : '') + (i === openAt ? ' active' : '');
  return `<span class="strip-tag${cls}" data-tag="${i}" title="${esc(Cond.note(tag))}">
    <span>${lead}${Cond.sentenceParts(tag).map(partHtml).join(' ')}</span>
    <button type="button" class="strip-x" data-i="${i}" title="刪除">×</button></span>`;
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

function render(state) {
  shown = state;
  const tags = Cond.tags(state);
  if (openAt >= tags.length) openAt = CLOSED;
  $('condStrip').innerHTML = `<div class="strip-zone" data-zone="and">
    <span class="strip-zone-l">AND</span><div class="strip-tags">${
    tags.length ? tags.map(tagHtml).join('')
                : `<span class="strip-hint">${esc(HINT)}</span>`}</div></div>`;
  renderDrawer(openAt === CLOSED ? null : tags[openAt]);
}

function closeDrawer() {
  if (openAt === CLOSED) return;
  openAt = CLOSED;
  render(shown);
}

function removeAt(i) {
  openAt = CLOSED;
  handlers.onRemove(i);
}

function onStripClick(e) {
  const x = e.target.closest('.strip-x');
  if (x) { removeAt(+x.dataset.i); return; }
  const tag = e.target.closest('.strip-tag');
  if (!tag) return;
  const word = e.target.closest('[data-field]');
  openAt = +tag.dataset.tag;
  focusField = word ? word.dataset.field : null;
  render(shown);
}

function onDrawerClick(e) {
  const el = e.target.closest('[data-act]');
  if (!el || el.matches('select, input')) return;
  const tag = Cond.tags(shown)[openAt];
  const box = el.closest('[data-field]');
  const field = box && box.dataset.field;
  const edit = next => handlers.onEdit(openAt, next);
  switch (el.dataset.act) {
    case 'close': closeDrawer(); break;
    case 'remove': removeAt(openAt); break;
    case 'restore': edit(Cond.restore(tag)); break;
    case 'mode': edit(Cond.setEx(tag, el.dataset.ex === '1')); break;
    case 'toggle': edit(Cond.toggleValue(tag, field, el.dataset.v)); break;
    case 'drop': edit(Cond.removeValue(tag, field, Cond.values(tag, field)[+el.dataset.i])); break;
  }
}

function onDrawerChange(e) {
  const el = e.target;
  const value = el.value.trim();
  if (!value || !el.dataset.act) return;
  const tag = Cond.tags(shown)[openAt];
  const box = el.closest('[data-field]');
  const field = box.dataset.field;
  const item = el.dataset.act === 'add-region'
    ? [box.querySelector('[data-role="player"]').value || null, value] : value;
  handlers.onEdit(openAt, Cond.addValue(tag, field, item));
}

/* 事件冒到 document 時抽屜可能已經重畫,點到的節點脫離了文件,closest 找不到祖先;
   用 composedPath 看派送當下的路徑。 */
function onDocumentClick(e) {
  if (openAt === CLOSED) return;
  const inside = e.composedPath().some(el =>
    el.classList && (el.id === 'condDrawer' || el.classList.contains('strip-tag')));
  if (!inside) closeDrawer();
}

function init(callbacks) {
  handlers = callbacks;
  $('condStrip').addEventListener('click', onStripClick);
  $('condDrawer').addEventListener('click', onDrawerClick);
  $('condDrawer').addEventListener('change', onDrawerChange);
  document.addEventListener('click', onDocumentClick);
}

  return Object.freeze({ init, render, closeDrawer });
})();
