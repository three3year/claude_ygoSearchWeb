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

/* 同一個效果(票 16):句層條件命中的效果句 rows 和動作命中的段要落在同一句。
   段對不回效果(clause 是 null)時當作符合,但它不標出效果句。
   回 null 表示這張卡不命中;回 [] 表示命中、但沒有可標的效果句。 */
function sameClause(rows, segments) {
  if (!rows.length) return null;
  const at = new Set(segments.map(s => s.clause));
  const same = rows.filter(i => at.has(i));
  return same.length || at.has(null) ? same : null;
}

/* 只有動作條件時命中的效果句:動作命中的段對回的那幾句(對不回的段不標)。 */
function hitClauses(segments) {
  const at = new Set(segments.map(s => s.clause));
  at.delete(null);
  return Array.from(at).sort((a, b) => a - b);
}

/* 動作條件(票 08)是另一組條件,和卡片條件取且:卡要同時命中動作索引裡的段。
   沒有動作條件時不碰動作索引(還沒載入也沒關係),結果與沒有這組條件時相同。
   有動作條件時(票 16)句層條件要和動作命中的段落在同一個效果句,rows 是那幾句;
   只有動作條件時 rows 是動作命中的段對回的效果句。marks 多一個 action(只加底色)。
   無法確認的卡(票 15,`unsure`,照 db 的順序):未解析組裡同時滿足卡片條件的卡;
   句層條件要有符合的效果句,但不做同一效果的判斷。沒有動作條件時是空的。 */
function runQuery(db, q, act, actionIndex) {
  q = q || {};
  const rq = Action.count(act) ? Action.rowQuery(act) : null;
  const acted = rq ? Action.match(actionIndex, rq) : null;
  const unresolved = rq ? Action.unsure(actionIndex, rq, acted) : null;
  const unsure = [];
  const name = term(q.name);
  const code = term(q.code);
  const codeOk = DIGITS.test(code);
  const text = term(q.text);
  const textParts = likeParts(text);
  const kindSel = sel(q.kind);
  const optSel = sel(q.opt);
  const marks = [];
  if (textParts.length) marks.push({ type: 'text', value: text });
  if (kindSel) marks.push({ type: 'kind' });
  if (optSel) marks.push({ type: 'opt' });
  const sentenced = marks.length > 0;
  if (acted) marks.push({ type: 'action' });
  const cards = [];
  for (const c of db) {
    if (name && !nameHit(c, name, q.nameLang)) continue;
    if (code && !(codeOk && idHit(c, code))) continue;
    if (!paramHit(c, q)) continue;
    if (acted && !acted.has(c.id)) {
      if (unresolved.has(c.id)
          && (!sentenced || clauseRows(c, textParts, kindSel, optSel, !!q.textMat).length)) {
        unsure.push(c.id);
      }
      continue;
    }
    let rows = null;
    if (sentenced) {
      rows = clauseRows(c, textParts, kindSel, optSel, !!q.textMat);
      rows = acted ? sameClause(rows, acted.get(c.id)) : (rows.length ? rows : null);
      if (!rows) continue;
    } else if (acted) {
      rows = hitClauses(acted.get(c.id));
    }
    cards.push({ card: c, rows });
  }
  return { cards, marks, unsure };
}

  return Object.freeze({ runQuery, likeParts, likeRanges });
})();
