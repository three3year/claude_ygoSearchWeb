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

function clauseRows(c, parts, kindSel, optSel, matOn) {
  const tx = c.tx || [];
  const rows = [];
  for (let i = 0; i < tx.length; i++) {
    if (kindSel && !triHit(kindAt(c, i), kindSel)) continue;
    if (optSel && !triHit(optAt(c, i), optSel)) continue;
    if (parts.length) {
      if (!matOn && c.ro && c.ro[i] === ROLE_MAT) continue;
      if (!likeMatch(tx[i], parts)) continue;
    }
    rows.push(i);
  }
  return rows;
}

/* [[動作類別]]的條件:節點路徑 → 葉集合(Acat 展開;樹裡找不到的路徑不當條件)。
   包含是 AND(每個節點一組),排除合成一組;`cost` 時代價位的葉也算有效葉。 */
function actSel(q) {
  const inc = [], ex = new Set(), union = new Set();
  for (const id in q.act || {}) {
    const leaves = Acat.leavesOf(id);
    if (!leaves || !q.act[id]) continue;
    if (q.act[id] > 0) {
      inc.push(new Set(leaves));
      leaves.forEach(n => union.add(n));
    } else {
      leaves.forEach(n => ex.add(n));
    }
  }
  if (!inc.length && !ex.size) return null;
  return { inc, ex, union, cost: !!q.actCost };
}

function actLeaves(c, i, cost) {
  const eff = (c.ae && c.ae[i]) || [];
  return cost ? eff.concat((c.ac && c.ac[i]) || []) : eff;
}

function anyIn(leaves, set) {
  return leaves.some(n => set.has(n));
}

function actExcluded(c, act) {
  if (!act.ex.size) return false;
  for (let i = 0; i < c.ae.length; i++) {
    if (anyIn(actLeaves(c, i, act.cost), act.ex)) return true;
  }
  return false;
}

/* 包含:每個節點都要有一句可用的句(已過句層條件的 rows)帶它,不同節點可以是
   不同句;命中句縮成帶任一包含節點的葉的那幾句。 */
function actRows(c, rows, act) {
  const has = rows.map(i => actLeaves(c, i, act.cost));
  if (!act.inc.every(set => has.some(leaves => anyIn(leaves, set)))) return [];
  return rows.filter((i, k) => anyIn(has[k], act.union));
}

function runQuery(db, q) {
  q = q || {};
  const name = term(q.name);
  const code = term(q.code);
  const codeOk = DIGITS.test(code);
  const text = term(q.text);
  const textParts = likeParts(text);
  const kindSel = sel(q.kind);
  const optSel = sel(q.opt);
  const act = actSel(q);
  const actInc = !!act && act.inc.length > 0;
  const marks = [];
  if (textParts.length) marks.push({ type: 'text', value: text });
  if (kindSel) marks.push({ type: 'kind' });
  if (optSel) marks.push({ type: 'opt' });
  if (actInc) marks.push({ type: 'act', leaves: Array.from(act.union), cost: act.cost });
  const cards = [];
  for (const c of db) {
    if (name && !nameHit(c, name, q.nameLang)) continue;
    if (code && !(codeOk && idHit(c, code))) continue;
    if (!paramHit(c, q)) continue;
    if (act && (!c.ae || actExcluded(c, act))) continue;
    let rows = null;
    if (marks.length) {
      rows = clauseRows(c, textParts, kindSel, optSel, !!q.textMat);
      if (actInc) rows = actRows(c, rows, act);
      if (!rows.length) continue;
    }
    cards.push({ card: c, rows });
  }
  return { cards, marks };
}

  return Object.freeze({ runQuery, likeParts, likeRanges });
})();
