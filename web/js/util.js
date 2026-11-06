'use strict';

const Util = (() => {

const DB = window.CARD_DATA || [];
const META = window.META || {};
const VOCAB = window.VOCAB || {};

function zhTable(name) {
  const table = {};
  ((VOCAB[name] || {}).items || []).forEach(e => { table[e.code] = e.zh; });
  return table;
}
function codesOf(name) {
  return ((VOCAB[name] || {}).items || []).map(e => e.code);
}
const CAT_ZH = zhTable('cat');
const KIND_ZH = zhTable('kind');
const ATTR_ZH = zhTable('attr');
const RACE_ZH = zhTable('race');
const ROLE_ZH = zhTable('role');
const OPT_ZH = zhTable('optional');
const OT_ZH = zhTable('ot');
const LM_ZH = zhTable('lm');
const LM_CODES = codesOf('lm');
const BAN_ZH = { bo: zhTable('ban_o'), bt: zhTable('ban_t'),
                 bm: zhTable('ban_m') };
const SUB_ZH = { m: zhTable('sub_m'), s: zhTable('sub_s'), t: zhTable('sub_t') };

const $ = id => document.getElementById(id);

function esc(s) {
  return String(s).replace(/[&<>"]/g, m =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
}

const pad8 = id => String(id).padStart(8, '0');

function fmtTime(v) {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}):\d{2}\+0800$/
    .exec(typeof v === 'string' ? v : '');
  return m ? `${m[1]} ${m[2]} (UTC+8)` : v;
}

const INDEX = new Map(DB.map(c => [c.id, c]));
const byId = id => INDEX.get(+id);

  return Object.freeze({
    DB, META, VOCAB,
    CAT_ZH, KIND_ZH, ATTR_ZH, RACE_ZH, ROLE_ZH, OPT_ZH, OT_ZH, LM_ZH, LM_CODES,
    SUB_ZH, BAN_ZH,
    zhTable, codesOf, $, esc, pad8, byId, fmtTime,
  });
})();
