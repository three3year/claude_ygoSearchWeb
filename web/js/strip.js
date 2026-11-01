'use strict';

/* 條件列(predicate-ui 規格 4 票 02 起):結果上方列出這次查詢的動作標籤。
   接縫:Strip.init({onRemove}) 接事件,Strip.render(狀態) 照條件模型的答案重畫。自己不留
   狀態、不跑查詢:狀態在主流程,文字在條件模型。目前只有 AND 區與 ×;OR 區、拖曳、
   左側條件標籤是票 05,點標籤開抽屜是票 04。 */
const Strip = (() => {
const { $, esc } = Util;

const HINT = '從左邊選條件';

function partHtml(part) {
  const glue = part.glue ? `<span class="strip-glue">${esc(part.glue)}</span> ` : '';
  const cls = part.field === '詞元' ? 'strip-lemma' : 'strip-val';
  return `${glue}<span class="${cls}">${esc(part.text)}</span>`;
}

function tagHtml(tag, i) {
  const row = Cond.named(tag);
  const lead = tag.ex ? '<span class="strip-lead">沒有</span> ' : '';
  return `<span class="strip-tag${tag.ex ? ' ex' : ''}" title="${esc(row ? row.name : '')}">
    <span>${lead}${Cond.sentenceParts(tag).map(partHtml).join(' ')}</span>
    <button type="button" class="strip-x" data-i="${i}" title="刪除">×</button></span>`;
}

function render(state) {
  const tags = Cond.tags(state);
  $('condStrip').innerHTML = `<div class="strip-zone" data-zone="and">
    <span class="strip-zone-l">AND</span><div class="strip-tags">${
    tags.length ? tags.map(tagHtml).join('')
                : `<span class="strip-hint">${esc(HINT)}</span>`}</div></div>`;
}

function init({ onRemove }) {
  $('condStrip').addEventListener('click', e => {
    const x = e.target.closest('.strip-x');
    if (x) onRemove(+x.dataset.i);
  });
}

  return Object.freeze({ init, render });
})();
