'use strict';

function vocabOf(values) {
  return Array.from(new Set(values)).sort();
}

function bitset(positions) {
  const bytes = Buffer.alloc(Math.floor(Math.max(-1, ...positions) / 8) + 1);
  positions.forEach(p => { bytes[p >> 3] |= 1 << (p & 7); });
  return bytes.toString('base64');
}

const LINE_DEFAULTS = { doer: false, obj: true };

function lineZones(line) {
  return [].concat(line.from || [], line.to || []);
}

const OBJECT_CODES = { self: 1, undecidable: 2, unsub: 3 };

const U_REPLACING = 1, U_REASON = 4, U_REASON_SUBSTITUTING = 8, U_REFERENCE = 16;

function unresOf(raw) {
  const u = { kind: '效果', pol: '做', acts: [], replacing: false, reference: false,
              reason: true, substituting: true, ...raw };
  if (u.reference) { u.kind = null; u.pol = null; }
  return u;
}

function actionData(cards, ids, noText, archetypes) {
  cards = cards.map(c => ({ segs: [], unres: [], ...c }));
  const segs = cards.flatMap(c => c.segs.map(s => ({ kind: '效果', pol: '做', acts: [], ...s })));
  const unres = cards.flatMap(c => c.unres.map(unresOf));
  const actions = vocabOf(segs.flatMap(s => s.acts).concat(unres.flatMap(u => u.acts)));
  const kinds = vocabOf(segs.map(s => s.kind).concat(unres.map(u => u.kind).filter(k => k)));
  const polarities = vocabOf(segs.map(s => s.pol).concat(unres.map(u => u.pol).filter(p => p)));
  const agents = vocabOf(segs.map(s => s.agent || '算我方'));
  const rows = {};
  segs.forEach(s => s.acts.forEach(a => { rows[a] = (rows[a] || 0) + (s.rows || 1); }));
  const lineList = segs.flatMap(s => s.lines || []);
  const zones = vocabOf(lineList.flatMap(l => lineZones(l).map(z => z[0])));
  const sides = [null].concat(vocabOf(lineList.flatMap(l => lineZones(l).map(z => z[1]))
    .concat(segs.map(s => s.recipient), segs.map(s => s.cause && s.cause[1]))
    .filter(v => v != null)));
  const causes = [null].concat(vocabOf(segs.filter(s => s.cause).map(s => s.cause[0])));
  const causeRows = {};
  segs.forEach(s => { const k = s.cause ? s.cause[0] : null; causeRows[k] = (causeRows[k] || 0) + 1; });
  const causeCode = c => causes.indexOf(c ? c[0] : null) * 8 + sides.indexOf(c ? c[1] : null);
  const zoneRows = {};
  lineList.forEach(l => new Set(lineZones(l).map(z => z[0]))
    .forEach(z => { zoneRows[z] = (zoneRows[z] || 0) + 1; }));
  const position = (list, inferred) => (list
    ? [inferred ? 1 : 0, ...list.map(([z, s]) => zones.indexOf(z) * 8 + sides.indexOf(s))
      .sort((x, y) => x - y)]
    : 0);
  const order = ids || cards.map(c => c.id);
  const sets = { k: [] };
  const setOf = members => {
    const positions = members.map(id => order.indexOf(id)).filter(p => p >= 0)
      .sort((x, y) => x - y);
    const key = positions.length ? `k${positions.join('_')}` : 'k';
    sets[key] = positions;
    return key;
  };
  const objectOf = (owner, obj) => {
    if (!obj) return 0;
    if (Array.isArray(obj)) return [0, setOf(obj)];
    if (obj === 'self') return [0, setOf([owner]), OBJECT_CODES.self];
    if (OBJECT_CODES[obj]) return [0, 'k', OBJECT_CODES[obj]];
    return [0, 'k'];
  };
  const line = (owner, raw) => {
    const l = { ...LINE_DEFAULTS, ...raw };
    return [l.doer ? 1 : 0, position(l.from, l.fromInferred), position(l.to, l.toInferred),
            objectOf(owner, l.obj)];
  };
  const parts = [];
  const reference = r => {
    const ref = { block: 0, generic: false, part: {}, clause: null, ...r };
    const key = `r${Object.keys(sets).length}`;
    const positions = ref.to.map(id => order.indexOf(id)).sort((x, y) => x - y);
    sets[key] = ref.bits ? bitset(positions) : positions;
    parts.push([{ part: `部分${parts.length}` },
                Object.keys(ref.part).map(id => [order.indexOf(Number(id)), ref.part[id]])
                  .sort((x, y) => x[0] - y[0])]);
    return [ref.block, ref.generic ? 1 : 0, key, parts.length - 1, ref.clause];
  };
  const lines = cards.map(c => [
    c.id, new Array(c.blocks || 1).fill(0),
    c.segs.map((raw, i) => {
      const s = { kind: '效果', pol: '做', acts: [], block: 0, ...raw };
      return [`b${s.block}.s${i}`, s.block, kinds.indexOf(s.kind), polarities.indexOf(s.pol),
              s.replacing ? 1 : 0, s.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y),
              (s.lines || []).map(raw => line(c.id, raw))];
    }),
    c.unres.map(raw => {
      const u = unresOf(raw);
      return [u.kind === null ? null : kinds.indexOf(u.kind),
              u.pol === null ? null : polarities.indexOf(u.pol), 0,
              (u.replacing ? U_REPLACING : 0) | (u.reason ? U_REASON : 0)
                | (u.substituting ? U_REASON_SUBSTITUTING : 0) | (u.reference ? U_REFERENCE : 0),
              u.acts.map(a => actions.indexOf(a)).sort((x, y) => x - y)];
    }),
    (c.refs || []).map(reference),
    c.segs.map(s => (s.clause == null ? null : s.clause)),
    c.segs.map(s => agents.indexOf(s.agent || '算我方')),
    c.segs.map(s => sides.indexOf(s.recipient == null ? null : s.recipient)),
    c.segs.map(s => causeCode(s.cause)),
  ]);
  return {
    ids: order,
    actions: actions.map(a => [a, rows[a] || 0]),
    zones: zones.map(z => [z, zoneRows[z]]),
    sides,
    kinds,
    polarities,
    blockKinds: ['編號效果'],
    agents,
    causes: causes.map(k => [k, causeRows[k] || 0]),
    noText: noText || [],
    parts,
    archetypes: (archetypes || []).map(a => [a.code, a.zh, setOf(a.members)]),
    sets,
    cards: lines,
  };
}

module.exports = { actionData };
