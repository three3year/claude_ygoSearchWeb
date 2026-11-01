'use strict';

/* 條件模型(predicate-ui 規格 4 票 02 起;純函式,不碰 DOM)。
   接縫:目錄列 → 標籤;標籤 + 左側條件 → 引擎查詢;標籤 → 具名查詢、葉路徑、短句;引擎查詢 → 句尾標籤的短句。
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

/* 句尾標籤的位置前綴:預設位置不寫,同短句省略預設的規則。 */
function positionPrefix(position) {
  return position === DEFAULT_POSITION ? '' : position + ':';
}

function partsText(parts) {
  return parts.map(p => (p.glue ? p.glue + ' ' : '') + p.text).join(' ');
}

function sentence(tag) {
  return (tag.ex ? '沒有 ' : '') + partsText(sentenceParts(tag));
}

/* 述詞序號 → 句尾標籤的短句。讀查詢本身,編號規則同引擎(先主查詢的 inc,再依片段順序接各片段的
   inc),所以 OR 區怎麼進查詢都對得上。不寫位置:句尾的位置前綴取命中框,標籤自己的位置是搜尋範圍。 */
function hitLabels(q) {
  return [q, ...(q.or || [])].flatMap(part => ((part.preds && part.preds.inc) || []).map(pred =>
    partsText(sentenceParts({ pred }).filter(p => p.field !== '位置'))));
}

  return Object.freeze({
    defaultPosition, tagOf, tagAt, named, leafPath,
    empty, tags, add, removeAt, usedPaths, toQuery,
    sentenceParts, sentence, hitLabels, positionPrefix,
  });
})();
