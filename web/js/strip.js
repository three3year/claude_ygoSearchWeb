'use strict';

/* 條件列(predicate-ui 規格 4 票 02 起,票 05 加左側條件標籤與 OR 區):結果上方列出這次查詢的
   全部條件,分 AND、OR 兩區。
   接縫:Strip.init(事件) 接事件,Strip.render(狀態, 左側條件標籤) 照條件模型的答案重畫。自己不留
   狀態、不跑查詢:狀態在主流程,文字在條件模型。
   事件:onRemove(編號)、onMove(編號, 區)、onSideRemove(鍵)、onSideGo(鍵)、onSideMove(鍵, 區)、
   onClear()。編號是 Cond.tags 的編號。點動作標籤開抽屜是票 04,手機的 ⇄ 是票 06。 */
const Strip = (() => {
const { $, esc } = Util;

/* 提示字(原型 D 版)。 */
const HINTS = { and: '全部都要成立', or: '任一成立即可:把標籤移到這裡' };
const ZONE_LABEL = { and: 'AND', or: 'OR' };
/* 自訂型別:拖到輸入框不會貼上文字,dragover 也不必另外記「正在拖標籤」。 */
const DRAG_TYPE = 'application/x-cond-tag';

function partHtml(part) {
  const glue = part.glue ? `<span class="strip-glue">${esc(part.glue)}</span> ` : '';
  const cls = part.field === '詞元' ? 'strip-lemma' : 'strip-val';
  return `${glue}<span class="${cls}">${esc(part.text)}</span>`;
}

function tagHtml(tag, i) {
  const row = Cond.named(tag);
  const lead = tag.ex ? '<span class="strip-lead">沒有</span> ' : '';
  return `<span class="strip-tag${tag.ex ? ' ex' : ''}" draggable="true" data-i="${i}"
    title="${esc(row ? row.name : '')}">
    <span>${lead}${Cond.sentenceParts(tag).map(partHtml).join(' ')}</span>
    <button type="button" class="strip-x" title="刪除">×</button></span>`;
}

function sideHtml(tag) {
  const label = tag.label ? `<span class="strip-glue">${esc(tag.label)}</span> ` : '';
  return `<span class="strip-tag side" draggable="true" data-key="${esc(tag.key)}" title="到左邊改">
    <span>${label}<span class="strip-val">${esc(tag.val)}</span></span>
    <button type="button" class="strip-x" title="清掉這項">×</button></span>`;
}

function zoneHtml(zone, html) {
  return `<div class="strip-zone" data-zone="${zone}">
    <span class="strip-zone-l">${ZONE_LABEL[zone]}</span><div class="strip-tags">${
    html || `<span class="strip-hint">${esc(HINTS[zone])}</span>`}</div></div>`;
}

/* 同一區裡左側條件在前、動作標籤在後(原型 D 版)。 */
function render(state, sideTags) {
  const andCount = Cond.tagsIn(state, 'and').length;
  const zone = (name, first) => sideTags.filter(t => Cond.sideZone(state, t.key) === name)
    .map(sideHtml).join('') +
    Cond.tagsIn(state, name).map((tag, i) => tagHtml(tag, first + i)).join('');
  const none = !sideTags.length && !Cond.tags(state).length;
  $('condStrip').innerHTML = `<div class="strip-top"><button type="button" class="strip-clear"${
    none ? ' disabled' : ''}>清除條件</button></div>` +
    zoneHtml('and', zone('and', 0)) + zoneHtml('or', zone('or', andCount));
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
    if (ref.charAt(0) === 'k') onSideMove(ref.slice(1), zone.dataset.zone);
    else onMove(+ref.slice(1), zone.dataset.zone);
  });
}

function init({ onRemove, onMove, onSideRemove, onSideGo, onSideMove, onClear }) {
  $('condStrip').addEventListener('click', e => {
    if (e.target.closest('.strip-clear')) { onClear(); return; }
    const tag = e.target.closest('.strip-tag');
    if (!tag) return;
    const x = e.target.closest('.strip-x');
    if (tag.dataset.key) (x ? onSideRemove : onSideGo)(tag.dataset.key);
    else if (x) onRemove(+tag.dataset.i);
  });
  initDrag({ onMove, onSideMove });
}

  return Object.freeze({ init, render });
})();
