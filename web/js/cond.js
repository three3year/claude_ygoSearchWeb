'use strict';

/* 條件模型(predicate-ui 規格 4 票 02 起,票 05 加左側條件標籤與 OR 區;純函式,不碰 DOM)。
   接縫:目錄列 → 標籤;左側條件 → 標籤;兩區 + 左側條件 → 引擎查詢(含 q.or);標籤 → 具名查詢、
   葉路徑、短句。
   動作標籤 `{ex, pred, origin}`:ex 是排除;pred 是送進引擎的述詞,一定帶位置(引擎沒寫位置就
   三個位置都看,見 predicate-index 票 05);origin 是產生它的目錄列名字。
   左側條件標籤 `{key, label, val, part, target}`:每次從左側條件算出來,不存;key 也是網址 or 的鍵;
   part 是它在查詢裡佔的片段;target 告訴側欄它對應哪個控制項。
   狀態 `{and: [標籤…], or: [標籤…], orSide: [鍵…]}` 一律當不可變,改動回傳新狀態;呼叫端用
   tags、tagsIn、sideZone 讀,不直接摸欄。tags 是 AND 區再 OR 區,removeAt、moveAt 的編號照它。 */
const Cond = (() => {
const { VOCAB } = Util;

const SEP = '›';

/* 16 欄的分組與順序(規格 4 條件模型段,2026-11-02;原型 D 版 COMMON、ADVANCED)。
   短句的欄序、之後抽屜與網址的欄序都讀這張。 */
const FIELD_GROUPS = Object.freeze({
  常用: ['詞元', '位置', '極性', '來源', '目的', '所在', '動作對象', '施事者', '受事者中心詞'],
  進階: ['目的中心詞', '數量類', '方式類', '態', '否定形', '中心詞類', '修飾語類'],
});
const FIELD_ORDER = FIELD_GROUPS.常用.concat(FIELD_GROUPS.進階);

/* 位置預設:效果;效果位 0 張時依序取第一個有張數的(規格 4 裁定,2026-11-02)。 */
const DEFAULT_POSITION = '效果';
const POSITION_FALLBACK = ['代價', '條件'];
const DEFAULT_POLARITY = ['可能', '肯定'];

const REGION_FIELDS = ['來源', '目的', '所在'];

/* 短句的連接字與區域、玩家的日文(原型 D 版,站主核可 2026-11-01)。測試守區域表涵蓋值域。 */
const GLUE = { 極性: '極性', 來源: '從', 目的: '到', 所在: '在', 動作對象: '動到', 施事者: '由',
               受事者中心詞: '對象是', 目的中心詞: '目的是', 數量類: '數量', 方式類: '方式',
               態: '態', 否定形: '否定形', 中心詞類: '對象類', 修飾語類: '修飾' };
const ZONE_JA = { 手牌: '手札', 牌組: 'デッキ', 額外牌組: 'EXデッキ', 墓地: '墓地',
                  除外: '除外', 場上: 'フィールド', 靈擺區: 'Pゾーン' };
const PLAYER_JA = { 自分: '自分', 相手: '相手', お互い: 'お互いの' };

const asList = v => (v == null ? [] : Array.isArray(v) ? v : [v]);

/* 述詞的比對鍵:單值與單元素清單相同、同欄多值不看順序、空欄等於沒寫。
   認具名查詢不看位置,所以改位置還是同一個具名查詢;判「同一張標籤」要連位置一起比。 */
function predKey(pred, withPosition) {
  const out = {};
  Object.keys(pred).sort().forEach(field => {
    if (field === '位置' && !withPosition) return;
    const list = asList(pred[field]).map(v => JSON.stringify(v)).sort();
    if (list.length) out[field] = list;
  });
  return JSON.stringify(out);
}

const ROWS = (VOCAB.catalog || []).filter(row => row.predicate);
const BY_PATH = new Map(ROWS.map(row => [row.path.join(SEP), row]));
const BY_KEY = new Map(ROWS.map(row => [predKey(row.predicate, false), row]));

function defaultPosition(row) {
  if (row.cards[DEFAULT_POSITION]) return DEFAULT_POSITION;
  return POSITION_FALLBACK.find(pos => row.cards[pos]) || DEFAULT_POSITION;
}

function tagOf(row, ex) {
  const pred = JSON.parse(JSON.stringify(row.predicate));
  pred.位置 = [defaultPosition(row)];
  return { ex: !!ex, pred, origin: row.name };
}

/* 葉路徑 → 標籤;大類、中類、純導覽節點與找不到的路徑都不是具名查詢,回 null。 */
function tagAt(path, ex) {
  const row = BY_PATH.get(path);
  return row ? tagOf(row, ex) : null;
}

function named(tag) {
  return BY_KEY.get(predKey(tag.pred, false)) || null;
}

/* 網址上能只寫路徑的條件:等於具名查詢,而且位置就是那一列的預設。 */
function leafPath(tag) {
  const row = named(tag);
  if (!row) return null;
  const pos = asList(tag.pred.位置);
  return pos.length === 1 && pos[0] === defaultPosition(row) ? row.path.join(SEP) : null;
}

const empty = () => ({ and: [], or: [], orSide: [] });

const tags = state => state.and.concat(state.or);

const tagsIn = (state, zone) => state[zone];

const isEmpty = state => !tags(state).length && !state.orSide.length;

/* 一模一樣的標籤(含包含或排除)再加一次沒有意義,不另外生一張,在另一區也一樣;同一列的包含與
   排除是兩張。新標籤預設進 AND(規格 4 條件列段)。 */
function add(state, tag, zone) {
  const same = t => t.ex === tag.ex && predKey(t.pred, true) === predKey(tag.pred, true);
  if (tags(state).some(same)) return state;
  const into = zone || 'and';
  return Object.assign({}, state, { [into]: state[into].concat([tag]) });
}

function removeAt(state, i) {
  const n = state.and.length;
  return Object.assign({}, state, {
    and: state.and.filter((_, at) => at !== i),
    or: state.or.filter((_, at) => at + n !== i),
  });
}

function moveAt(state, i, zone) {
  const tag = tags(state)[i];
  const from = i < state.and.length ? 'and' : 'or';
  if (!tag || from === zone) return state;
  const left = removeAt(state, i);
  return Object.assign({}, left, { [zone]: left[zone].concat([tag]) });
}

const sideZone = (state, key) => (state.orSide.indexOf(key) >= 0 ? 'or' : 'and');

function moveSide(state, key, zone) {
  if (sideZone(state, key) === zone) return state;
  const orSide = zone === 'or' ? state.orSide.concat([key]) : state.orSide.filter(k => k !== key);
  return Object.assign({}, state, { orSide });
}

/* 左側條件清掉(含大類連動收掉子類型)後,它的區也忘掉:再選一次是新標籤,回 AND。 */
function syncSide(state, side) {
  const orSide = sideTags(side).map(t => t.key).filter(key => state.orSide.indexOf(key) >= 0);
  return JSON.stringify(orSide) === JSON.stringify(state.orSide)
    ? state : Object.assign({}, state, { orSide });
}

function usedPaths(state) {
  return tags(state).map(named).filter(Boolean).map(row => row.path.join(SEP));
}

/* 引擎的述詞序號是整個查詢的編號:主查詢的 inc,再依片段順序接各片段的 inc。左側條件的片段沒有
   述詞,所以序號 → 標籤就是這張清單。 */
function incTags(state) {
  return tags(state).filter(t => !t.ex);
}

function zhOf(dom, code) {
  const item = ((VOCAB[dom] || {}).items || []).find(it => it.code === code);
  return item ? item.zh : code;
}

function textTags(q) {
  const out = [];
  const lang = Query.LANGS.find(l => l.v === q.nameLang);
  if (q.code) {
    out.push({ key: 'code', label: '密碼', val: q.code, part: { code: q.code },
               target: { inputs: ['fId'] } });
  }
  if (q.name) {
    const suffix = lang && lang !== Query.LANGS[0] ? `(${lang.label})` : '';
    out.push({ key: 'name', label: '卡名' + suffix, val: q.name, part: { name: q.name },
               target: { inputs: ['fName'] } });
  }
  if (q.text) {
    out.push({ key: 'text', label: '效果文', val: q.text + (q.textMat ? '(含素材行)' : ''),
               part: { text: q.text }, target: { inputs: ['fText'], checks: ['fTextMat'] } });
  }
  return out;
}

function spanText(r) {
  if (!r || (r.min == null && r.max == null)) return '';
  if (r.min != null && r.max != null) return r.min === r.max ? `${r.min}` : `${r.min}〜${r.max}`;
  return r.min != null ? `≥${r.min}` : `≤${r.max}`;
}

function rangeTag(f, q) {
  const span = spanText(q[f.range]), unknown = f.unknown && q[f.unknown];
  if (!span && !unknown) return null;
  const part = {};
  if (span) part[f.range] = q[f.range];
  if (unknown) part[f.unknown] = unknown;
  const mark = !unknown ? '' : unknown > 0 ? '?' : '−?';
  return { key: f.range, label: f.zh, val: [span, mark].filter(Boolean).join(' '), part,
           target: { range: f.range } };
}

/* 選了子類型就不另列大類:子類型標籤寫明了,也帶著那個大類,換區時一起走(規格 4 條件模型段)。 */
function triTag(f, q) {
  const sel = q[f.tri] || {}, prefix = f.side ? f.side + ':' : '';
  const hasSub = cat => Object.keys(q.sub || {}).some(s => q.sub[s] && s.indexOf(cat + ':') === 0);
  const codes = Object.keys(sel).filter(code => sel[code] && code.indexOf(prefix) === 0 &&
    !(f.tri === 'cat' && hasSub(code)));
  if (!codes.length) return null;
  const zh = code => zhOf(f.dom, code.slice(prefix.length));
  const own = {};
  codes.forEach(code => { own[code] = sel[code]; });
  const part = { [f.tri]: own };
  if (f.side && (q.cat || {})[f.side]) part.cat = { [f.side]: q.cat[f.side] };
  const val = codes.filter(c => sel[c] > 0).map(zh)
    .concat(codes.filter(c => sel[c] < 0).map(c => '−' + zh(c))).join('、');
  return { key: f.side ? `${f.tri}:${f.side}` : f.tri,
           label: f.tri === 'cat' ? '' : (VOCAB[f.dom] || {}).zh || f.dom,
           val, part,
           target: { axis: f.tri, side: f.side || '',
                     codes: codes.map(code => code.slice(prefix.length)) } };
}

/* 左側條件 → 標籤,同一類併成一張。Query.FIELDS 是側欄的欄位表,一個意思一個地方,不另抄一份;
   這裡在呼叫時才讀,cond.js 載入得比 query.js 早。 */
function sideTags(q) {
  const out = textTags(q);
  Query.FIELDS.forEach(f => {
    const tag = f.group ? null : f.tri ? triTag(f, q) : rangeTag(f, q);
    if (tag) out.push(tag);
  });
  return out;
}

/* 從查詢裡拿走一個片段佔的條件。軸與範圍只拿片段裡有的子鍵:大類 {m, s} 只移走 m 時,s 留著。 */
function without(q, part) {
  const out = Object.assign({}, q);
  Object.keys(part).forEach(key => {
    if (typeof part[key] !== 'object') { delete out[key]; return; }
    const rest = Object.assign({}, out[key]);
    Object.keys(part[key]).forEach(sub => { delete rest[sub]; });
    if (Object.keys(rest).length) out[key] = rest;
    else delete out[key];
  });
  return out;
}

function predsOf(list) {
  const preds = wantEx => list.filter(t => t.ex === wantEx).map(t => t.pred);
  return { inc: preds(false), ex: preds(true) };
}

/* AND 區全部成立,再加 OR 區任一成立。textMat、nameLang 是比法,引擎的片段會繼承,所以留在主查詢
   (票 01 Comments);片段一定有內容,不會送出恆真的空片段。 */
function toQuery(state, side) {
  const orSide = sideTags(side).filter(t => state.orSide.indexOf(t.key) >= 0);
  const q = orSide.reduce((main, t) => without(main, t.part), Object.assign({}, side));
  if (state.and.length) q.preds = predsOf(state.and);
  const fragments = orSide.map(t => t.part).concat(state.or.map(t => ({ preds: predsOf([t]) })));
  if (fragments.length) q.or = fragments;
  return q;
}

function zoneText(item) {
  const player = item[0], zone = item[1];
  const who = !player ? '' : PLAYER_JA[player] || player + ':';
  return who + (ZONE_JA[zone] || zone);
}

function fieldText(field, value) {
  const list = asList(value);
  if (REGION_FIELDS.indexOf(field) >= 0) return list.map(zoneText).join('或');
  return list.join('或');
}

function isDefaultPolarity(value) {
  return JSON.stringify(asList(value).slice().sort()) === JSON.stringify(DEFAULT_POLARITY);
}

function isDefaultPosition(value) {
  const list = asList(value);
  return !list.length || (list.length === 1 && list[0] === DEFAULT_POSITION);
}

/* 短句的片段,條件列一段一段畫;field 留給抽屜「點字捲到那一欄」。極性放最後(原型如此),
   極性沒寫是不限,不是預設,要寫出來。 */
function sentenceParts(tag) {
  const pred = tag.pred, parts = [];
  if (!isDefaultPosition(pred.位置)) {
    parts.push({ field: '位置', glue: '', text: asList(pred.位置).join('或') + '位' });
  }
  parts.push({ field: '詞元', glue: '', text: fieldText('詞元', pred.詞元) });
  FIELD_ORDER.forEach(field => {
    if (field === '詞元' || field === '位置' || field === '極性') return;
    if (!asList(pred[field]).length) return;
    parts.push({ field, glue: GLUE[field], text: fieldText(field, pred[field]) });
  });
  if (!isDefaultPolarity(pred.極性)) {
    parts.push({ field: '極性', glue: GLUE.極性, text: fieldText('極性', pred.極性) || '不限' });
  }
  return parts;
}

function sentence(tag) {
  const words = sentenceParts(tag).map(p => (p.glue ? p.glue + ' ' : '') + p.text);
  return (tag.ex ? '沒有 ' : '') + words.join(' ');
}

  return Object.freeze({
    defaultPosition, tagOf, tagAt, named, leafPath,
    empty, tags, tagsIn, isEmpty, add, removeAt, moveAt, usedPaths, incTags,
    sideTags, sideZone, moveSide, syncSide, toQuery,
    sentenceParts, sentence,
  });
})();
