'use strict';

/* 條件模型(predicate-ui 規格 4 票 02 起,票 05 加左側條件標籤與 OR 區;純函式,不碰 DOM)。
   接縫:目錄列 → 標籤;左側條件 → 標籤;兩區 + 左側條件 → 引擎查詢(含 q.or);標籤 → 具名查詢、
   葉路徑、短句;引擎查詢 → 句尾標籤的短句;抽屜的欄位與值、改欄位(票 04);標籤 → 抽屜選項
   (drawer-values 票 02:每欄列哪些值、各是亮、最後一個、可按或灰);標籤 ⇄ 欄位對
   (票 04,分隔與轉義在 Hash,值域在這裡)。
   動作標籤 `{ex, pred, origin}`:ex 是排除;pred 是送進引擎的述詞,一定帶位置(引擎沒寫位置就
   值域的每個位置都看,見 predicate-index 票 05);origin 是產生它的目錄列名字。
   左側條件標籤 `{key, label, val, part, target}`:每次從左側條件算出來,不存;key 也是網址 or 的鍵;
   part 是它在查詢裡佔的片段;target 告訴側欄它對應哪個控制項。
   狀態 `{and: [標籤…], or: [標籤…], orSide: [鍵…]}` 一律當不可變,改動回傳新狀態;呼叫端用
   tags、tagsIn、sideZone 讀,不直接摸欄。tags 是 AND 區再 OR 區,removeAt、moveAt 的編號照它。 */
const Cond = (() => {
const { VOCAB, asList } = Util;

/* 目錄路徑的接字:葉路徑、網址 act 的路徑都用它(規格 4 網址段,2026-11-02);Acat 讀這裡。 */
const SEP = '›';

/* 16 欄的分組與順序(規格 4 條件模型段,2026-11-02;原型 D 版 COMMON、ADVANCED)。
   短句的欄序、之後抽屜與網址的欄序都讀這張。 */
const COMMON_GROUP = '常用';
const FIELD_GROUPS = Object.freeze({
  [COMMON_GROUP]: ['詞元', '位置', '極性', '來源', '目的', '所在', '動作對象', '施事者', '受事者中心詞'],
  進階: ['目的中心詞', '數量類', '方式類', '態', '否定形', '中心詞類', '修飾語類'],
});
const FIELD_ORDER = Object.values(FIELD_GROUPS).flat();

/* 位置預設:效果;效果位 0 張時依序取第一個有張數的(規格 4 裁定,2026-11-02;召喚手續排最後,
   summon-procedure 規格「效果位 0 張時的後備位置要不要排進召喚手續?」(a),2026-11-03)。後備是位置值域
   去掉效果、照值域序;conditions.test.js 守和值域一致。 */
const DEFAULT_POSITION = '效果';
const POSITION_FALLBACK = ['代價', '條件', '召喚手續'];
/* 極性的預設,短句不寫它;抄 catalog.py 的 DEFAULT_POLARITY(2026-11-01 規格 2「詞元節點極性」(a)),
   conditions.test.js 守和來源一致。排序過,比對時不看順序。 */
const DEFAULT_POLARITY = ['可能', '肯定'];
/* 至少要留一個值的欄:只剩一個亮著時那一個按不掉(drawer-values 規格,2026-11-02)。 */
const KEEP_ONE_FIELDS = ['位置', '極性'];
/* 具名查詢自己寫的欄,這兩欄以外的在它產生的標籤上鎖住(drawer-lock 規格,2026-11-03)。 */
const UNLOCKED_FIELDS = Object.freeze(['詞元', '極性']);

/* 區域三欄,抄 predicate.py 的 REGION_FIELDS(2026-11-01 規格 3);conditions.test.js 守和來源一致。 */
const REGION_FIELDS = ['來源', '目的', '所在'];

/* 抽屜與網址的值都讀匯出檔的值域(規格 4 條件模型段);中心詞是尾綴比對,抽屜只能從候選挑
   (drawer-values 規格,2026-11-02)。HEAD_FIELDS 抄 predicate.py(2026-11-01 規格 3),
   conditions.test.js 守和來源一致。 */
const FRAME = VOCAB.frame || {};
const DOMAINS = FRAME.domains || {};
const HEAD_FIELDS = ['受事者中心詞', '目的中心詞'];

/* 短句的連接字與區域、玩家的日文(原型 D 版,站主核可 2026-11-01)。區域、玩家抄 catalog.py 的
   ZONE_LABEL、PLAYER_LABEL,conditions.test.js 守和來源一致;相對、無沒有命名規則,不在表上。 */
const GLUE = { 極性: '極性', 來源: '從', 目的: '到', 所在: '在', 動作對象: '動到', 施事者: '由',
               受事者中心詞: '對象是', 目的中心詞: '目的是', 數量類: '數量', 方式類: '方式',
               態: '態', 否定形: '否定形', 中心詞類: '對象類', 修飾語類: '修飾' };
const ZONE_JA = { 手牌: '手札', 牌組: 'デッキ', 額外牌組: 'EXデッキ', 墓地: '墓地',
                  除外: '除外', 場上: 'フィールド', 靈擺區: 'Pゾーン' };
const PLAYER_JA = { 自分: '自分', 相手: '相手', お互い: 'お互いの' };

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

const empty = () => ({ and: [], or: [], orSide: [] });

const tags = state => state.and.concat(state.or);

const tagsIn = (state, zone) => state[zone];

const isEmpty = state => !tags(state).length && !state.orSide.length;

const sameTag = (a, b) => a.ex === b.ex && predKey(a.pred, true) === predKey(b.pred, true);

/* 網址的規則:只在同一區內收成一張。A 且(A 或 B)與 A 不同語意,跨區收掉就改了查詢(Story 28;
   2026-11-02 code review 裁定)。 */
function addInZone(state, tag, zone) {
  if (state[zone].some(t => sameTag(t, tag))) return state;
  return Object.assign({}, state, { [zone]: state[zone].concat([tag]) });
}

/* 目錄點列的規則:一模一樣的標籤(含包含或排除)再加一次沒有意義,不另外生一張,在另一區也一樣;
   同一列的包含與排除是兩張。新標籤預設進 AND(規格 4 條件列段)。 */
function add(state, tag, zone) {
  return tags(state).some(t => sameTag(t, tag)) ? state : addInZone(state, tag, zone || 'and');
}

function removeAt(state, i) {
  const n = state.and.length;
  return Object.assign({}, state, {
    and: state.and.filter((_, at) => at !== i),
    or: state.or.filter((_, at) => at + n !== i),
  });
}

function replaceAt(state, i, tag) {
  const n = state.and.length;
  return Object.assign({}, state, {
    and: state.and.map((t, at) => (at === i ? tag : t)),
    or: state.or.map((t, at) => (at + n === i ? tag : t)),
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

function zhOf(dom, code) {
  const item = ((VOCAB[dom] || {}).items || []).find(it => it.code === code);
  return item ? item.zh : code;
}

function textTags(q) {
  const out = [];
  const lang = Query.LANGS.find(l => l.v === q.nameLang);
  if (q.code) {
    out.push({ key: 'code', label: '密碼', val: q.code, part: { code: q.code },
               target: { text: 'code' } });
  }
  if (q.name) {
    const suffix = lang && lang !== Query.LANGS[0] ? `(${lang.label})` : '';
    out.push({ key: 'name', label: '卡名' + suffix, val: q.name, part: { name: q.name },
               target: { text: 'name' } });
  }
  if (q.text) {
    out.push({ key: 'text', label: '效果文', val: q.text + (q.textMat ? '(含素材行)' : ''),
               part: { text: q.text }, target: { text: 'text' } });
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

/* 這張標籤單獨的張數,抽屜顯示用。排除標籤也算有 X 的卡(原型 D 版):數字是這個述詞的大小,
   包含、排除切換時不跟著跳。 */
function soloQuery(tag) {
  return { preds: { inc: [tag.pred], ex: [] } };
}

function drawerGroups() {
  return Object.fromEntries(Object.entries(FIELD_GROUPS)
    .map(([group, fields]) => [group, fields.filter(f => f !== '詞元')]));
}

const kindOf = field => (REGION_FIELDS.indexOf(field) >= 0 ? 'region'
  : HEAD_FIELDS.indexOf(field) >= 0 ? 'text' : 'values');

const sameItem = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* 區域項先排區域、同區域不看玩家在前:網址的值序因此固定,`自分.墓地~除外`(規格 4 網址段)。 */
function orderedRegions(items) {
  const zones = DOMAINS.區域 || [], players = DOMAINS.玩家 || [];
  const valid = it => Array.isArray(it) && zones.indexOf(it[1]) >= 0 &&
    (it[0] === null || players.indexOf(it[0]) >= 0);
  const rank = ([player, zone]) => zones.indexOf(zone) * (players.length + 1) + players.indexOf(player) + 1;
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

/* 極性沒寫是不限,等於三種全亮(drawer-values 規格條件模型段):抽屜畫成全亮,關一顆剩另外兩顆。 */
function predValues(pred, field) {
  if (field === '極性' && !asList(pred.極性).length) return (DOMAINS.極性 || []).slice();
  return asList(pred[field]);
}

const values = (tag, field) => predValues(tag.pred, field);

function lockedPred(origin) {
  const row = BY_NAME.get(origin);
  const out = {};
  if (!row) return out;
  Object.keys(row.predicate).forEach(field => {
    if (UNLOCKED_FIELDS.indexOf(field) < 0) out[field] = asList(row.predicate[field]);
  });
  return out;
}

const isLockedField = (origin, field) => field in lockedPred(origin);

function withValues(tag, field, items) {
  if (isLockedField(tag.origin, field)) return tag;
  const pred = Object.assign({}, tag.pred);
  const list = orderedValues(field, items);
  if (list.length) pred[field] = list;
  else if (KEEP_ONE_FIELDS.indexOf(field) >= 0) return tag;
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

function isLastOne(tag, field, item) {
  const list = values(tag, field);
  return KEEP_ONE_FIELDS.indexOf(field) >= 0 && list.length === 1 && sameItem(list[0], item);
}

/* 抽屜選項的值狀態(drawer-values 規格 Implementation Decisions「抽屜選項」,2026-11-02);Strip 照它畫。 */
const CHIP = Object.freeze({ ON: '亮', LAST: '最後一個', OPEN: '可按', GRAY: '灰' });
const { ON, LAST, OPEN, GRAY } = CHIP;

const listedValues = (tag, field) =>
  Engine.fieldValues(Object.assign({ 詞元: tag.pred.詞元 }, lockedPred(tag.origin)), field);

const hitValues = (tag, field) => Engine.fieldValues(tag.pred, field);

function chipOptions(tag, field) {
  const on = values(tag, field);
  const listed = listedValues(tag, field), hits = hitValues(tag, field);
  const state = value => (on.indexOf(value) < 0 ? (hits.indexOf(value) >= 0 ? OPEN : GRAY)
    : isLastOne(tag, field, value) ? LAST : ON);
  const list = (DOMAINS[field] || []).filter(v => on.indexOf(v) >= 0 || listed.indexOf(v) >= 0)
    .map(value => ({ value, state: state(value) }));
  return list.length ? { field, kind: 'values', values: list } : null;
}

function regionOptions(tag, field) {
  const listed = listedValues(tag, field), hits = hitValues(tag, field);
  const items = values(tag, field);
  const zones = (DOMAINS.區域 || []).filter(zone => listed.some(([, z]) => z === zone));
  const players = [null].concat((DOMAINS.玩家 || []).filter(player => listed.some(([p]) => p === player)));
  if (!zones.length && !items.length) return null;
  const hit = (player, zone) => hits.some(([p, z]) => z === zone && (player === null || p === player));
  return {
    field, kind: 'region', items,
    players: players.map(player => {
      const list = zones.map(value => ({ value, state: hit(player, value) ? OPEN : GRAY }));
      return { value: player, state: list.some(z => z.state === OPEN) ? OPEN : GRAY, zones: list };
    }),
  };
}

function textOptions(tag, field) {
  const on = values(tag, field);
  const listed = listedValues(tag, field), hits = hitValues(tag, field);
  const candidates = hits.filter(w => on.indexOf(w) < 0);
  return listed.length || on.length ? { field, kind: 'text', candidates } : null;
}

const FIELD_OPTIONS = { values: chipOptions, region: regionOptions, text: textOptions };

function lockedOptions(tag, field) {
  const items = orderedValues(field, lockedPred(tag.origin)[field]);
  return { field, kind: kindOf(field), lock: tag.origin, items };
}

/* 一欄的抽屜選項;這一欄不列時回 null。 */
function fieldOptions(tag, field) {
  if (isLockedField(tag.origin, field)) return lockedOptions(tag, field);
  return FIELD_OPTIONS[kindOf(field)](tag, field);
}

/* 抽屜選項:[{group, fields: [{field, kind, …}]}];沒有欄的組不列。點選鈕的欄帶 values:
   [{value, state}];區域欄帶 players: [{value, state, zones: [{value, state}]}]
   與已加入的 items;中心詞欄帶 candidates。鎖住的欄帶 lock(來源名字)與鎖住的 items,不帶選單。 */
function drawerOptions(tag) {
  const groups = drawerGroups();
  return Object.keys(groups).map(group => ({
    group,
    fields: groups[group].map(field => fieldOptions(tag, field)).filter(Boolean),
  })).filter(g => g.fields.length);
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
function regionText([player, zone]) {
  return player ? player + '.' + zone : zone;
}

function regionItem(text) {
  const i = text.indexOf('.');
  return i < 0 ? [null, text] : [text.slice(0, i), text.slice(i + 1)];
}

/* 標籤 → 欄位對 `[[欄, [值文字…]]…]`:欄序、值序固定,所以同樣的標籤寫出同樣的網址。
   位置只有一個效果時不寫;三種極性全亮不寫,和舊網址的沒寫同義(drawer-values 規格)。 */
function toPairs(tag) {
  const pairs = [];
  FIELD_ORDER.forEach(field => {
    const list = orderedValues(field, values(tag, field));
    if (!list.length || (field === '位置' && isDefaultPosition(list)) ||
        (field === '極性' && isAnyPolarity(tag))) return;
    pairs.push([field, REGION_FIELDS.indexOf(field) >= 0 ? list.map(regionText) : list]);
  });
  return pairs;
}

/* 欄位對 → 標籤。只照欄位清單取,不認得的欄與值域外的值在這裡消失,引擎看不到;沒有詞元不成
   標籤。網址不寫來源,所以欄位等於某個具名查詢才有來源(規格 4 網址段)。沒寫極性明寫成三種
   全亮,抽屜畫出來就是實際條件(drawer-values 規格)。 */
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
  if (!pred.極性) pred.極性 = predValues(pred, '極性');
  const row = named({ pred });
  return { ex: !!ex, pred, origin: row ? row.name : null };
}

function zoneText([player, zone]) {
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

const isAnyPolarity = tag => values(tag, '極性').length === (DOMAINS.極性 || []).length;

/* 短句的片段,條件列一段一段畫;field 留給抽屜「點字捲到那一欄」。極性放最後(原型如此),
   三種全亮(含沒寫)是不限,不是預設,要寫出來。 */
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
    parts.push({ field: '極性', glue: GLUE.極性,
                 text: isAnyPolarity(tag) ? '不限' : fieldText('極性', pred.極性) });
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
    SEP, DEFAULT_POSITION, COMMON_GROUP, UNLOCKED_FIELDS, CHIP, defaultPosition, tagAt, named, leafPath,
    empty, tags, tagsIn, isEmpty, add, addInZone, removeAt, replaceAt, moveAt, usedPaths,
    sideTags, sideZone, moveSide, syncSide, toQuery,
    sentenceParts, sentence, hitLabels, positionPrefix, note, soloQuery,
    toPairs, fromPairs,
    drawerGroups, drawerOptions, fieldOptions, values, addValue, removeValue, toggleValue, setEx, editedFrom,
    restore,
  });
})();
