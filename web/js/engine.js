'use strict';

const Engine = (() => {
const { VOCAB } = Util;

const DIGITS = /^\d+$/;

const KIND_OWN = {};
for (const code in (VOCAB.kind || {}).own || {}) {
  const pair = VOCAB.kind.own[code];
  const i = pair.indexOf(':');
  KIND_OWN[code] = { c: pair.slice(0, i), s: pair.slice(i + 1) };
}

function term(v) {
  return String(v == null ? '' : v).trim();
}

function likeParts(kw) {
  return kw.split('%').filter(Boolean);
}

function likeRanges(text, parts) {
  const out = [];
  let pos = 0;
  for (const p of parts) {
    const i = text.indexOf(p, pos);
    if (i < 0) return [];
    out.push([i, i + p.length]);
    pos = i + p.length;
  }
  return out;
}

function likeMatch(text, parts) {
  return likeRanges(text, parts).length === parts.length;
}

function nameHit(c, kw, lang) {
  const parts = likeParts(kw);
  if (!parts.length) return true;
  if (lang === 'ja') {
    return (!!c.nj && likeMatch(c.nj, parts)) || (!!c.ax && likeMatch(c.ax, parts));
  }
  if (lang === 'en') {
    const lower = parts.map(p => p.toLowerCase());
    return !!c.ne && likeMatch(c.ne.toLowerCase(), lower);
  }
  return likeMatch(c.n, parts) || (!!c.ax && likeMatch(c.ax, parts));
}

function idHit(c, digits) {
  const n = Number(digits);
  return c.id === n || (!!c.al && c.al.indexOf(n) >= 0);
}

function triHit(values, sel) {
  if (!sel) return true;
  let wanted = false, got = false;
  for (const code in sel) {
    const has = values.indexOf(code) >= 0;
    if (sel[code] < 0) {
      if (has) return false;
    } else {
      wanted = true;
      if (has) got = true;
    }
  }
  return !wanted || got;
}

function rangeHit(v, r) {
  if (!r || (r.min == null && r.max == null)) return true;
  if (v == null || v < 0) return false;
  if (r.min != null && v < r.min) return false;
  if (r.max != null && v > r.max) return false;
  return true;
}

function unknownHit(v, want) {
  if (!want) return true;
  const isUnknown = v != null && v < 0;
  return want > 0 ? isUnknown : !isUnknown;
}

function subCodes(c) {
  return (c.s || []).map(s => c.c + ':' + s);
}

function paramHit(c, q) {
  return triHit(c.c ? [c.c] : [], q.cat)
    && triHit(subCodes(c), q.sub)
    && triHit(c.at ? [c.at] : [], q.attr)
    && triHit(c.r ? [c.r] : [], q.race)
    && triHit(c.lm || [], q.lm)
    && triHit(c.ra ? [c.ra] : [], q.rarity)
    && triHit(c.ot ? [c.ot] : [], q.ot)
    && triHit(c.bo ? [c.bo] : [], q.ban_o)
    && triHit(c.bt ? [c.bt] : [], q.ban_t)
    && triHit(c.bm ? [c.bm] : [], q.ban_m)
    && rangeHit(c.lv, q.lv)
    && rangeHit(c.lk, q.lk)
    && rangeHit(c.sc, q.sc)
    && rangeHit(c.atk, q.atk)
    && rangeHit(c.df, q.df)
    && rangeHit(c.gy, q.gy)
    && unknownHit(c.atk, q.atkq)
    && unknownHit(c.df, q.dfq);
}

const OPT_COMBO = {};
for (const code in (VOCAB.optional || {}).combos || {}) {
  OPT_COMBO[VOCAB.optional.combos[code]] = code;
}

function optAt(c, i) {
  const code = c.o && c.o[i];
  if (!code) return [];
  const combo = OPT_COMBO[((c.k && c.k[i]) || '') + ':' + code];
  return combo ? [code, combo] : [code];
}

function kindAt(c, i) {
  const code = c.k && c.k[i];
  if (!code) return [];
  const own = KIND_OWN[code];
  if (own && c.c === own.c && (c.s || []).indexOf(own.s) >= 0) return [];
  return [code];
}

const ROLE_MAT = 'mat';

function sel(o) {
  return o && Object.keys(o).length ? o : null;
}

function clauseHit(c, i, conds) {
  if (conds.kindSel && !triHit(kindAt(c, i), conds.kindSel)) return false;
  if (conds.optSel && !triHit(optAt(c, i), conds.optSel)) return false;
  if (conds.textParts.length) {
    if (!conds.textMat && c.ro && c.ro[i] === ROLE_MAT) return false;
    if (!likeMatch(c.tx[i], conds.textParts)) return false;
  }
  return true;
}

/* 通過分支裡每組條件的句。 */
function clauseRows(c, condsList) {
  const tx = c.tx || [];
  const rows = [];
  for (let i = 0; i < tx.length; i++) {
    if (condsList.every(conds => clauseHit(c, i, conds))) rows.push(i);
  }
  return rows;
}

/* [[框架述詞]]的評估(語意同參考評估器 predicate.py):一個述詞編成一組欄檢查,掃框表得一張
   命中表(框號 → 中不中),逐卡只查表。框元組的欄序與碼的定義見 frameindex.py。 */
const FRAMES = window.FRAMES;
const FRAME_VOCAB = VOCAB.frame;

/* 框元組與段的欄序(2026-11-01 規格 3「索引形狀」段;frameindex.py 依同一順序編) */
const SLOT_LEMMA = 0, SLOT_POSITION = 1, SLOT_POLARITY = 2, SLOT_VOICE = 3, SLOT_NEGATION = 4,
      SLOT_AGENT = 5, SLOT_MANNER = 6, SLOT_PATIENT_MODE = 7,
      SLOT_SOURCE = 8, SLOT_GOAL_REGION = 9, SLOT_PLACE = 10,
      SLOT_PATIENT_PHRASE = 11, SLOT_GOAL_PHRASE = 12;
const SEG_HEAD = 0, SEG_HEAD_KIND = 1, SEG_QUANTITY = 2, SEG_MODIFIERS = 3;

/* 卡上一個框的位置(效果、代價、條件):hits 的框所在句與框序號 → 值域的字面。呈現層不讀框元組。 */
function framePosition(c, row, n) {
  return FRAME_VOCAB.domains.位置[FRAMES[c.fr[row][n]][SLOT_POSITION] - 1];
}

/* 尾端空值截掉,所以清單欄可能不在元組裡。 */
function someInSlot(f, slot, test) {
  const items = f[slot];
  return items !== undefined && items.some(test);
}

function enumCodes(field, values) {
  const domain = FRAME_VOCAB.domains[field];
  return new Set(values.map(v => domain.indexOf(v) + 1).filter(Boolean));
}

const segsOf = f => f[SLOT_PATIENT_PHRASE] || [];

function scalarField(slot, field) {
  return {
    check: values => {
      const codes = enumCodes(field, values);
      return f => codes.has(f[slot]);
    },
    codes: f => (f[slot] ? [f[slot]] : []),
    value: code => FRAME_VOCAB.domains[field][code - 1],
  };
}

const LEMMA_FIELD = {
  check: values => {
    const codes = new Set(values.map(v => FRAME_VOCAB.lemmas.indexOf(v)));
    codes.delete(-1);
    return f => codes.has(f[SLOT_LEMMA]);
  },
  codes: f => [f[SLOT_LEMMA]],
  value: code => FRAME_VOCAB.lemmas[code],
};

function regionField(slot) {
  const players = () => FRAME_VOCAB.domains.玩家, zones = () => FRAME_VOCAB.domains.區域;
  return {
    check: items => {
      const codes = new Set();
      for (const [player, zone] of items) {
        const z = zones().indexOf(zone);
        if (z < 0) continue;
        players().forEach((p, n) => {
          if (player == null || player === p) codes.add(n * zones().length + z);
        });
      }
      return f => someInSlot(f, slot, pair => codes.has(pair));
    },
    codes: f => f[slot] || [],
    value: code => [players()[Math.floor(code / zones().length)], zones()[code % zones().length]],
    rank: code => (code % zones().length) * players().length + Math.floor(code / zones().length),
  };
}

function headField(slot) {
  return {
    check: values => {
      const codes = new Set();
      FRAME_VOCAB.heads.forEach((head, n) => {
        if (values.some(v => head.endsWith(v))) codes.add(n);
      });
      return f => someInSlot(f, slot, seg => codes.has(seg[SEG_HEAD]));
    },
    codes: f => (f[slot] || []).map(seg => seg[SEG_HEAD]),
    value: code => FRAME_VOCAB.heads[code],
  };
}

function segmentField(segSlot, field) {
  return {
    check: values => {
      const codes = enumCodes(field, values);
      return f => someInSlot(f, SLOT_PATIENT_PHRASE, seg => codes.has(seg[segSlot]));
    },
    codes: f => segsOf(f).map(seg => seg[segSlot]).filter(Boolean),
    value: code => FRAME_VOCAB.domains[field][code - 1],
  };
}

const MODIFIER_FIELD = {
  check: values => {
    let mask = 0;
    enumCodes('修飾語類', values).forEach(code => { mask |= 1 << (code - 1); });
    return f => someInSlot(f, SLOT_PATIENT_PHRASE, seg => (seg[SEG_MODIFIERS] & mask) !== 0);
  },
  codes: f => segsOf(f).flatMap(seg => FRAME_VOCAB.domains.修飾語類
    .map((_, n) => n + 1).filter(code => (seg[SEG_MODIFIERS] & (1 << (code - 1))) !== 0)),
  value: code => FRAME_VOCAB.domains.修飾語類[code - 1],
};

/* 述詞欄 → 欄的讀法(16 欄是參考評估器的 FIELDS,2026-10-31 GLOSSARY「框架述詞」條;不認得的欄丟錯) */
const FRAME_FIELDS = new Map([
  ['詞元', LEMMA_FIELD],
  ['位置', scalarField(SLOT_POSITION, '位置')],
  ['極性', scalarField(SLOT_POLARITY, '極性')],
  ['態', scalarField(SLOT_VOICE, '態')],
  ['否定形', scalarField(SLOT_NEGATION, '否定形')],
  ['施事者', scalarField(SLOT_AGENT, '施事者')],
  ['方式類', scalarField(SLOT_MANNER, '方式類')],
  ['動作對象', scalarField(SLOT_PATIENT_MODE, '動作對象')],
  ['來源', regionField(SLOT_SOURCE)],
  ['目的', regionField(SLOT_GOAL_REGION)],
  ['所在', regionField(SLOT_PLACE)],
  ['受事者中心詞', headField(SLOT_PATIENT_PHRASE)],
  ['目的中心詞', headField(SLOT_GOAL_PHRASE)],
  ['中心詞類', segmentField(SEG_HEAD_KIND, '中心詞類')],
  ['數量類', segmentField(SEG_QUANTITY, '數量類')],
  ['修飾語類', MODIFIER_FIELD],
]);

function frameField(field) {
  if (!FRAME_FIELDS.has(field)) throw new Error('不認得的欄:' + field);
  return FRAME_FIELDS.get(field);
}

const asList = value => (typeof value === 'string' ? [value] : value);

function frameChecks(pred, skip) {
  return Object.keys(pred).filter(field => field !== skip)
    .map(field => frameField(field).check(asList(pred[field])));
}

function predHitTable(pred) {
  const checks = frameChecks(pred, null);
  const table = new Uint8Array(FRAMES.length);
  FRAMES.forEach((f, n) => { if (checks.every(check => check(f))) table[n] = 1; });
  return table;
}

let framesByLemma = null;

function lemmaFrames(lemmas) {
  if (!framesByLemma) {
    framesByLemma = new Map();
    FRAMES.forEach((f, n) => {
      const list = framesByLemma.get(f[SLOT_LEMMA]);
      if (list) list.push(n);
      else framesByLemma.set(f[SLOT_LEMMA], [n]);
    });
  }
  return asList(lemmas).flatMap(lemma => framesByLemma.get(FRAME_VOCAB.lemmas.indexOf(lemma)) || []);
}

/* 述詞其他欄都成立的框上,這一欄出現過的值(drawer-values 規格判定段:抽屜的隱藏與灰色)。
   只掃述詞詞元自己的框;值依值域順序,中心詞依中心詞表順序。沒有框表或述詞沒有詞元時回空。 */
function fieldValues(pred, field) {
  if (!FRAME_VOCAB || pred.詞元 == null) return [];
  const spec = frameField(field);
  const checks = frameChecks(pred, field);
  const seen = new Set();
  for (const n of lemmaFrames(pred.詞元)) {
    const f = FRAMES[n];
    if (checks.every(check => check(f))) spec.codes(f).forEach(code => seen.add(code));
  }
  const rank = spec.rank || (code => code);
  return Array.from(seen).sort((a, b) => rank(a) - rank(b)).map(spec.value);
}

function predTables(preds) {
  return (preds || []).map(predHitTable);
}

function predOnCard(c, table) {
  for (const ids of c.fr) {
    for (let n = 0; n < ids.length; n++) {
      if (table[ids[n]]) return true;
    }
  }
  return false;
}

/* 卡層的把關:排除看全卡;包含述詞在全卡都沒有框,就不可能在哪一句命中。只查表,所以
   排在卡面參數與句層條件之前,逐卡成本只花在過得了這關的卡上。 */
function predGate(c, inc, ex) {
  if (!c.fr) return false;
  for (const table of ex) if (predOnCard(c, table)) return false;
  for (const { table } of inc) if (!predOnCard(c, table)) return false;
  return true;
}

/* 包含述詞在通過句層條件的句上找命中框:句 → [述詞序號, 框所在句, 框序號] 清單,
   每個述詞都要有框(卡層 AND,可跨句),否則回 null。一句的框是它自己的加上領起句的:
   領起句的條件常寫在 ● 之前,而 ● 子句的效果類型可以和領起句不同(規格 2026-11-01 裁定)。 */
function predFrames(c, rows, inc) {
  const met = inc.map(() => false);
  const found = new Map();
  for (const i of rows) {
    const lead = c.fl ? c.fl[i] : -1;
    const sources = lead >= 0 ? [lead, i] : [i];
    const here = [];
    inc.forEach(({ seq, table }, k) => {
      for (const source of sources) {
        c.fr[source].forEach((id, n) => {
          if (table[id]) { met[k] = true; here.push([seq, source, n]); }
        });
      }
    });
    if (here.length) found.set(i, here);
  }
  return met.every(Boolean) ? found : null;
}

/* 一組條件:主查詢或一個 OR 片段編好的樣子。firstSeq 是這組第一個包含述詞的序號:序號是整個
   查詢的編號(主查詢的 inc,再依片段順序接各片段的 inc),介面用它對回標籤。 */
function compileConds(q, firstSeq) {
  const text = term(q.text);
  const code = term(q.code);
  return {
    q,
    name: term(q.name),
    code,
    codeOk: DIGITS.test(code),
    text,
    textParts: likeParts(text),
    textMat: !!q.textMat,
    kindSel: sel(q.kind),
    optSel: sel(q.opt),
    predInc: predTables(q.preds && q.preds.inc).map((table, n) => ({ seq: firstSeq + n, table })),
    predEx: predTables(q.preds && q.preds.ex),
  };
}

/* 片段裡的 textMat、nameLang 是效果文、卡名怎麼比,不是條件;片段沒寫就照主查詢,所以效果文或
   卡名放到 OR 區時比法不變。 */
function compileFragments(q, main) {
  let nextSeq = main.predInc.length;
  return (q.or || []).map(fragment => {
    const conds = compileConds({ textMat: q.textMat, nameLang: q.nameLang, ...fragment }, nextSeq);
    nextSeq += conds.predInc.length;
    return conds;
  });
}

function cardHit(c, conds) {
  const { q, name, code, predInc, predEx } = conds;
  if ((predInc.length || predEx.length) && !predGate(c, predInc, predEx)) return false;
  if (name && !nameHit(c, name, q.nameLang)) return false;
  if (code && !(conds.codeOk && idHit(c, code))) return false;
  return paramHit(c, q);
}

function hasClauseConds(conds) {
  return conds.textParts.length > 0 || !!conds.kindSel || !!conds.optSel || conds.predInc.length > 0;
}

/* 一個分支:主查詢加上至多一個片段,兩組條件都要成立(同一個鍵兩邊都有時也是都要成立,
   不是片段蓋掉主查詢)。 */
function makeBranch(main, fragment) {
  const condsList = fragment ? [main, fragment] : [main];
  return {
    fragment,
    condsList,
    predInc: condsList.flatMap(conds => conds.predInc),
    tracksRows: condsList.some(hasClauseConds),
  };
}

/* 卡在分支上的命中句:{rows, hits?};分支沒有句層條件時 rows 是 null,卡不中回 null。 */
function branchRows(c, branch) {
  if (!branch.tracksRows) return { rows: null };
  const passed = clauseRows(c, branch.condsList);
  if (!passed.length) return null;
  if (!branch.predInc.length) return { rows: passed };
  const found = predFrames(c, passed, branch.predInc);
  if (!found) return null;
  const hitRows = passed.filter(i => found.has(i));
  return { rows: hitRows, hits: hitRows.map(i => found.get(i)) };
}

function compareHits(a, b) {
  return a[0] - b[0] || a[1] - b[1] || a[2] - b[2];
}

function mergeHits(a, b) {
  const sorted = a.concat(b).sort(compareHits);
  return sorted.filter((hit, n) => n === 0 || compareHits(sorted[n - 1], hit) !== 0);
}

function hitsAtRow(result, row) {
  return result.hits ? result.hits[result.rows.indexOf(row)] || [] : [];
}

/* 同一張卡命中兩個分支:rows 是 null 的分支讓給有句的分支;只因沒有包含述詞的分支命中的句,
   hits[k] 是空清單。 */
function mergeBranchResults(a, b) {
  if (!a.rows) return b;
  if (!b.rows) return a;
  const rows = Array.from(new Set(a.rows.concat(b.rows))).sort((x, y) => x - y);
  if (!a.hits && !b.hits) return { rows };
  return { rows, hits: rows.map(row => mergeHits(hitsAtRow(a, row), hitsAtRow(b, row))) };
}

/* 全部分支的 marks:同種只留一筆(效果文依字面),順序固定,不隨條件在哪一區變動。 */
function queryMarks(condsList) {
  const marks = [];
  const texts = condsList.filter(conds => conds.textParts.length).map(conds => conds.text);
  new Set(texts).forEach(value => marks.push({ type: 'text', value }));
  if (condsList.some(conds => conds.kindSel)) marks.push({ type: 'kind' });
  if (condsList.some(conds => conds.optSel)) marks.push({ type: 'opt' });
  if (condsList.some(conds => conds.predInc.length)) marks.push({ type: 'pred' });
  return marks;
}

function runQuery(db, q) {
  q = q || {};
  const main = compileConds(q, 0);
  const fragments = compileFragments(q, main);
  const branches = fragments.length
    ? fragments.map(fragment => makeBranch(main, fragment))
    : [makeBranch(main, null)];
  const cards = [];
  for (const c of db) {
    if (!cardHit(c, main)) continue;
    let result = null;
    for (const branch of branches) {
      if (branch.fragment && !cardHit(c, branch.fragment)) continue;
      const got = branchRows(c, branch);
      if (got) result = result ? mergeBranchResults(result, got) : got;
    }
    if (result) cards.push({ card: c, ...result });
  }
  return { cards, marks: queryMarks([main, ...fragments]) };
}

  return Object.freeze({ runQuery, framePosition, fieldValues, likeParts, likeRanges });
})();
