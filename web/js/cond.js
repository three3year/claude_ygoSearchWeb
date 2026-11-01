'use strict';

/* 條件模型(predicate-ui 規格 4 票 02 起;純函式,不碰 DOM)。
   接縫:目錄列 → 標籤;標籤 + 左側條件 → 引擎查詢;標籤 → 具名查詢、葉路徑、短句;
   抽屜的欄位與值、改欄位(票 04);標籤 ⇄ 欄位對(票 04,分隔與轉義在 Hash,值域在這裡)。
   標籤 `{ex, pred, origin}`:ex 是排除;pred 是送進引擎的述詞,一定帶位置(引擎沒寫位置就
   三個位置都看,見 predicate-index 票 05);origin 是產生它的目錄列名字。
   狀態 `{and: [標籤…]}` 一律當不可變,改動回傳新狀態;呼叫端用 tags 讀,不直接摸欄。 */
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

/* 抽屜與網址的值都讀匯出檔的值域(規格 4 條件模型段);中心詞是尾綴比對,自由輸入,
   候選只列最常見的(規格 4,2026-11-02)。 */
const FRAME = VOCAB.frame || {};
const DOMAINS = FRAME.domains || {};
const HEAD_FIELDS = ['受事者中心詞', '目的中心詞'];
const HEAD_CANDIDATES = 300;

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
const BY_NAME = new Map(ROWS.map(row => [row.name, row]));

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

const empty = () => ({ and: [] });

const tags = state => state.and;

/* 一模一樣的標籤(含包含或排除)再加一次沒有意義,不另外生一張;同一列的包含與排除是兩張。 */
function add(state, tag) {
  const same = t => t.ex === tag.ex && predKey(t.pred, true) === predKey(tag.pred, true);
  return state.and.some(same) ? state : { and: state.and.concat([tag]) };
}

function removeAt(state, i) {
  return { and: state.and.filter((_, n) => n !== i) };
}

function replaceAt(state, i, tag) {
  return { and: state.and.map((t, n) => (n === i ? tag : t)) };
}

function usedPaths(state) {
  return state.and.map(named).filter(Boolean).map(row => row.path.join(SEP));
}

function toQuery(state, side) {
  const q = Object.assign({}, side);
  if (!state.and.length) return q;
  const preds = wantEx => state.and.filter(t => t.ex === wantEx).map(t => t.pred);
  q.preds = { inc: preds(false), ex: preds(true) };
  return q;
}

/* 這張標籤單獨的張數,抽屜顯示用。排除標籤也算有 X 的卡(原型 D 版):數字是這個述詞的大小,
   包含、排除切換時不跟著跳。 */
function soloQuery(tag) {
  return { preds: { inc: [tag.pred], ex: [] } };
}

function drawerGroups() {
  return { 常用: FIELD_GROUPS.常用.filter(f => f !== '詞元'), 進階: FIELD_GROUPS.進階 };
}

/* 這一欄在抽屜怎麼選:封閉值、玩家+區域、或自由輸入加候選。 */
function editor(field) {
  if (REGION_FIELDS.indexOf(field) >= 0) {
    return { kind: 'region', players: [null].concat(DOMAINS.玩家 || []), zones: DOMAINS.區域 || [] };
  }
  if (HEAD_FIELDS.indexOf(field) >= 0) {
    return { kind: 'text', candidates: (FRAME.heads || []).slice(0, HEAD_CANDIDATES) };
  }
  return { kind: 'values', values: DOMAINS[field] || [] };
}

const sameItem = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* 區域項先排區域、同區域不看玩家在前:網址的值序因此固定,`自分.墓地~除外`(規格 4 網址段)。 */
function orderedRegions(items) {
  const zones = DOMAINS.區域 || [], players = DOMAINS.玩家 || [];
  const valid = it => Array.isArray(it) && zones.indexOf(it[1]) >= 0 &&
    (it[0] === null || players.indexOf(it[0]) >= 0);
  const rank = it => zones.indexOf(it[1]) * (players.length + 1) + players.indexOf(it[0]) + 1;
  const unique = items.filter(valid)
    .filter((it, n, all) => all.findIndex(other => sameItem(other, it)) === n);
  return unique.sort((a, b) => rank(a) - rank(b));
}

/* 一欄的值整理成固定順序,值域外的值在這裡掉:改欄位與讀網址走同一關,引擎只看得到值域內的值。 */
function orderedValues(field, items) {
  if (REGION_FIELDS.indexOf(field) >= 0) return orderedRegions(items);
  if (HEAD_FIELDS.indexOf(field) >= 0) {
    const words = items.map(v => String(v).trim()).filter(Boolean);
    return Array.from(new Set(words)).sort();
  }
  const domain = field === '詞元' ? FRAME.lemmas || [] : DOMAINS[field] || [];
  return domain.filter(v => items.indexOf(v) >= 0);
}

const values = (tag, field) => asList(tag.pred[field]);

/* 空欄等於沒寫,不留空清單;只有位置例外,全關是三個位置都看,要明寫(規格 4 條件模型段)。 */
function withValues(tag, field, items) {
  const pred = Object.assign({}, tag.pred);
  const list = orderedValues(field, items);
  if (list.length) pred[field] = list;
  else if (field === '位置') pred[field] = DOMAINS.位置.slice();
  else delete pred[field];
  return Object.assign({}, tag, { pred });
}

function addValue(tag, field, item) {
  return withValues(tag, field, values(tag, field).concat([item]));
}

function removeValue(tag, field, item) {
  return withValues(tag, field, values(tag, field).filter(v => !sameItem(v, item)));
}

function toggleValue(tag, field, item) {
  const on = values(tag, field).some(v => sameItem(v, item));
  return on ? removeValue(tag, field, item) : addValue(tag, field, item);
}

function setEx(tag, ex) {
  return Object.assign({}, tag, { ex: !!ex });
}

/* 改過才有來源可回:欄位(含位置)和產生它的那一列的預設不同。不看 ex,切換包含、排除不算改。 */
function editedFrom(tag) {
  const row = BY_NAME.get(tag.origin);
  if (!row) return null;
  return predKey(tagOf(row, tag.ex).pred, true) === predKey(tag.pred, true) ? null : row.name;
}

function restore(tag) {
  const row = BY_NAME.get(tag.origin);
  return row ? tagOf(row, tag.ex) : tag;
}

function note(tag) {
  const row = named(tag);
  if (row) return row.name;
  return tag.origin ? '改自 ' + tag.origin : '';
}

/* 區域項在欄位對裡寫 `玩家.區域`,不看玩家只寫區域(規格 4 網址段)。玩家與區域都不含 `.`,
   多一個點或點前面是空字串,在 orderedRegions 會因為不在值域而掉。 */
function regionText(item) {
  return item[0] ? item[0] + '.' + item[1] : item[1];
}

function regionItem(text) {
  const i = text.indexOf('.');
  return i < 0 ? [null, text] : [text.slice(0, i), text.slice(i + 1)];
}

/* 標籤 → 欄位對 `[[欄, [值文字…]]…]`:欄序、值序固定,所以同樣的標籤寫出同樣的網址。
   位置只有一個效果時不寫,極性沒寫就是不限(規格 4 網址段)。 */
function toPairs(tag) {
  const pairs = [];
  FIELD_ORDER.forEach(field => {
    const list = orderedValues(field, values(tag, field));
    if (!list.length || (field === '位置' && isDefaultPosition(list))) return;
    pairs.push([field, REGION_FIELDS.indexOf(field) >= 0 ? list.map(regionText) : list]);
  });
  return pairs;
}

/* 欄位對 → 標籤。只照欄位清單取,不認得的欄與值域外的值在這裡消失,引擎看不到;沒有詞元不成
   標籤。網址不寫來源,所以欄位等於某個具名查詢才有來源(規格 4 網址段)。 */
function fromPairs(pairs, ex) {
  const pred = {};
  FIELD_ORDER.forEach(field => {
    const texts = pairs.filter(p => p[0] === field).reduce((all, p) => all.concat(p[1]), []);
    const items = REGION_FIELDS.indexOf(field) >= 0 ? texts.map(regionItem) : texts;
    const list = orderedValues(field, items);
    if (list.length) pred[field] = list;
  });
  if (!pred.詞元) return null;
  if (!pred.位置) pred.位置 = [DEFAULT_POSITION];
  const row = named({ pred });
  return { ex: !!ex, pred, origin: row ? row.name : null };
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
    empty, tags, add, removeAt, replaceAt, usedPaths, toQuery, soloQuery,
    sentenceParts, sentence, note,
    toPairs, fromPairs,
    drawerGroups, editor, values, addValue, removeValue, toggleValue, setEx, editedFrom, restore,
  });
})();
