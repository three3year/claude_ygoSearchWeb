'use strict';

const Action = (() => {
const { isObj } = Util;

const KINDS = { eff: ['效果', '召喚手續', '限制'], cost: ['代價'], cond: ['條件'] };
const KIND_KEYS = Object.keys(KINDS);
const DEFAULT_KINDS = ['eff', 'cost'];
const POLARITIES = { do: ['做', '可以', '必須'], limit: ['不能', '只能'], resist: ['不會'] };
const DEFAULT_POL = 'do';

const SIDES = ['我方', '對手'];
const BOTH_SIDES = '雙方各自';
const IMPLIED_SELF = '算我方';
const UNRESTRICTED = '不限定';

const CAUSE_COVERS = { '戰鬥或效果': ['戰鬥', '效果'], '戰鬥以外': ['效果'] };

const SHOWN_WORDS = 14;

function zoneOf(raw) {
  if (!isObj(raw) || typeof raw.zone !== 'string' || !raw.zone.trim()) return null;
  const z = { zone: raw.zone.trim() };
  if (SIDES.indexOf(raw.side) >= 0) z.side = raw.side;
  return z;
}

function causeOf(raw) {
  if (!isObj(raw) || typeof raw.kind !== 'string' || !raw.kind.trim()) return null;
  const kind = raw.kind.trim();
  if (kind === UNRESTRICTED) return null;
  const c = { kind };
  if (SIDES.indexOf(raw.side) >= 0) c.side = raw.side;
  return c;
}

const THIS_CARD = 'this_card';
function targetOf(raw) {
  if (raw === THIS_CARD) return THIS_CARD;
  if (isObj(raw) && Number.isInteger(raw.card) && raw.card > 0) return { card: raw.card };
  const condition = isObj(raw) ? givenOf(raw.condition) : null;
  return condition ? { condition } : null;
}

/* 給條件認得哪些碼照值域正典(VOCAB),換成條件式的值照動作索引的 givenValues:兩份都是建置期產出,
   前端不另抄(ADR-0008)。 */
const canon = (name, code) => Util.codesOf(name).indexOf(code) >= 0;
const level = v => (Number.isInteger(v) && v >= 0 ? v : null);

function givenOf(raw) {
  if (!isObj(raw)) return null;
  const g = {};
  if (canon('cat', raw.cat)) g.cat = raw.cat;
  if (canon('attr', raw.attr)) g.attr = raw.attr;
  if (canon('race', raw.race)) g.race = raw.race;
  if (level(raw.lvMin) !== null) g.lvMin = raw.lvMin;
  if (level(raw.lvMax) !== null) g.lvMax = raw.lvMax;
  if (Number.isInteger(raw.set) && raw.set > 0) g.set = raw.set;
  if (typeof raw.name === 'string' && raw.name.trim()) g.name = raw.name.trim();
  return Object.keys(g).length ? g : null;
}

function conditionQuery(g, index) {
  const given = (name, code) => index.given[name].get(code);
  const compare = (attr, cmp, value) => ({ op: '屬性比較', attr, cmp, value });
  const atoms = [];
  if (g.cat) atoms.push({ op: '大類', value: given('cat', g.cat) });
  if (g.attr) atoms.push(compare('屬性', '=', given('attr', g.attr)));
  if (g.race) atoms.push(compare('種族', '=', given('race', g.race)));
  if (g.lvMin != null) atoms.push(compare('等級', '≥', g.lvMin));
  if (g.lvMax != null) atoms.push(compare('等級', '≤', g.lvMax));
  if (g.set) atoms.push({ op: '字段', setcodes: [g.set] });
  if (g.name) atoms.push({ op: '卡名包含', text: g.name });
  return atoms.length === 1 ? atoms[0] : { op: '且', args: atoms };
}

function condOf(raw) {
  if (!isObj(raw)) return null;
  const c = {};
  const actions = Array.isArray(raw.actions) ? Array.from(new Set(
    raw.actions.filter(a => typeof a === 'string' && a.trim()).map(a => a.trim()))).sort() : [];
  if (actions.length) c.actions = actions;
  const from = zoneOf(raw.from);
  if (from) c.from = from;
  const to = zoneOf(raw.to);
  if (to) c.to = to;
  const kinds = kindsOf(raw.kinds);
  if (kinds.join() !== DEFAULT_KINDS.join()) c.kinds = kinds;
  if (raw.pol !== DEFAULT_POL && POLARITIES[raw.pol]) c.pol = raw.pol;
  if (SIDES.indexOf(raw.agent) >= 0) c.agent = raw.agent;
  const target = targetOf(raw.target);
  if (target) c.target = target;
  if (SIDES.indexOf(raw.recipient) >= 0) c.recipient = raw.recipient;
  const cause = causeOf(raw.cause);
  if (cause) c.cause = cause;
  if (!Object.keys(c).length) return null;
  if (raw.include_unrestricted === true) c.include_unrestricted = true;
  return c;
}

function count(cond) {
  const c = condOf(cond);
  return c ? Object.keys(c).filter(k => k !== 'include_unrestricted').length : 0;
}

function kindsOf(raw) {
  const kinds = Array.isArray(raw) ? KIND_KEYS.filter(k => raw.indexOf(k) >= 0) : [];
  return kinds.length ? kinds : DEFAULT_KINDS;
}

const zoneQuery = z => [{ zone: z.zone, side: z.side || null }];

function rowQuery(cond, index) {
  const c = condOf(cond) || {};
  const kinds = kindsOf(c.kinds);
  const rq = {
    actions: c.actions || [],
    kinds: kinds.flatMap(k => KINDS[k]),
    polarities: POLARITIES[c.pol || DEFAULT_POL],
  };
  if (kinds.indexOf('cond') >= 0) rq.include_condition = true;
  if (c.from) rq.from_zones = zoneQuery(c.from);
  if (c.to) rq.to_zones = zoneQuery(c.to);
  if (c.agent) rq.agent = c.agent;
  if (c.include_unrestricted) rq.include_unrestricted = true;
  if (c.target === THIS_CARD) rq.this_card = true;
  else if (c.target && c.target.condition) rq.condition = conditionQuery(c.target.condition, index);
  else if (c.target) rq.card = c.target.card;
  if (c.recipient) rq.recipient = c.recipient;
  if (c.cause) rq.cause = { ...c.cause };
  return rq;
}

const SUGGESTIONS = 12;
function suggest(db, text, limit) {
  const word = String(text || '').trim().toLowerCase();
  if (!word) return [];
  const found = [];
  db.forEach((c, i) => {
    const hit = [c.n, c.nj, c.ne, c.ax]
      .filter(n => typeof n === 'string' && n.toLowerCase().indexOf(word) >= 0);
    if (hit.length) found.push({ c, i, len: Math.min(...hit.map(n => n.length)) });
  });
  return found.sort((a, b) => a.len - b.len || a.i - b.i)
    .slice(0, limit || SUGGESTIONS)
    .map(f => ({ id: f.c.id, n: f.c.n, nj: f.c.nj || '' }));
}

function conditionOptions() {
  const items = name => ((Util.VOCAB[name] || {}).items || []).map(e => ({ code: e.code, zh: e.zh }));
  return { cat: items('cat'), attr: items('attr'), race: items('race') };
}

function archetypeSuggest(index, text, limit) {
  const word = foldName(String(text || '').trim());
  if (!word) return [];
  return index.archetypes
    .map((a, i) => ({ a, i }))
    .filter(({ a }) => foldName(a.zh).indexOf(word) >= 0)
    .sort((x, y) => x.a.zh.length - y.a.zh.length || x.i - y.i)
    .slice(0, limit || SUGGESTIONS)
    .map(({ a }) => ({ code: a.code, zh: a.zh }));
}

function lineOf(format, [flags, from, to, obj]) {
  const position = p => (p === 0 ? null : { inferred: !!p[0], codes: p.slice(1) });
  return { doer: !!(flags & format.lineFlags.doer), from: position(from), to: position(to),
           object: obj === 0 ? null : { set: obj[1], kind: obj[2] || 0 } };
}

function members(value) {
  if (Array.isArray(value)) {
    const set = new Set(value);
    return { has: p => set.has(p), meets: bits => value.some(p => (bits[p >> 3] >> (p & 7)) & 1),
             positions: () => value };
  }
  const bytes = atob(value);
  return {
    has: p => (p >> 3) < bytes.length && ((bytes.charCodeAt(p >> 3) >> (p & 7)) & 1) === 1,
    meets(bits) {
      const n = Math.min(bytes.length, bits.length);
      for (let i = 0; i < n; i++) if (bytes.charCodeAt(i) & bits[i]) return true;
      return false;
    },
    positions() {
      const out = [];
      for (let i = 0; i < bytes.length; i++) {
        const b = bytes.charCodeAt(i);
        for (let k = 0; k < 8; k++) if (b >> k & 1) out.push(i * 8 + k);
      }
      return out;
    },
  };
}

function clauseAt(clauses, i) {
  const c = clauses && clauses[i];
  return c == null ? null : c;
}

function causeAt(raw, code) {
  const slots = raw.format.sideSlots;
  const kind = raw.causes[Math.floor(code / slots)][0];
  return kind === null ? null : { kind, side: raw.sides[code % slots] };
}

function givenTables(raw) {
  const tables = { value: {}, code: {} };
  for (const [name, pairs] of Object.entries(raw.givenValues)) {
    tables.value[name] = new Map(pairs);
    tables.code[name] = new Map(pairs.map(([code, v]) => [v, code]));
  }
  return tables;
}

function prepare(raw, db) {
  const at = list => new Map(list.map((v, i) => [v, i]));
  const decoded = new Map();
  const setAt = key => {
    if (!decoded.has(key)) decoded.set(key, members(raw.sets[key]));
    return decoded.get(key);
  };
  const cardAt = at(raw.ids);
  const front = (db || []).map(c => [cardAt.get(c.id), c]).filter(([p]) => p !== undefined);
  const archetypes = new Map((raw.archetypes || []).map(([code, , key]) => [code, key]));
  const given = givenTables(raw);
  const index = {
    cardAt,
    sideSlots: raw.format.sideSlots,
    objectKinds: raw.format.objectKinds,
    unresolvedFlags: raw.format.unresolvedFlags,
    given: given.value,
    givenCode: given.code,
    inSet: (key, p) => setAt(key).has(p),
    archetypes: (raw.archetypes || []).map(([code, zh]) => ({ code, zh: zh || '' })),
    inArchetype: (code, p) => archetypes.has(code) && index.inSet(archetypes.get(code), p),
    satisfying(condition) {
      const bits = new Uint8Array((raw.ids.length + 7) >> 3);
      for (const [p, c] of front) {
        if (fitsCondition(index, condition, c, p)) bits[p >> 3] |= 1 << (p & 7);
      }
      return bits;
    },
    meets: (key, bits) => setAt(key).meets(bits),
    words: raw.actions,
    zones: raw.zones,
    actionAt: at(raw.actions.map(a => a[0])),
    kindAt: at(raw.kinds),
    polarityAt: at(raw.polarities),
    zoneAt: at(raw.zones.map(z => z[0])),
    sideAt: at(raw.sides),
    causes: raw.causes,
    cards: raw.cards.map(([id, , segments, unresolved, , clauses, agents, recipients, causes]) => ({
      id,
      segments: segments.map(([seg, block, kind, polarity, replacing, actions, lines], i) =>
        ({ id: seg, block, kind, polarity, replacing: !!replacing, actions,
           lines: lines.map(l => lineOf(raw.format, l)), clause: clauseAt(clauses, i),
           agent: raw.agents[agents[i]], recipient: raw.sides[recipients[i]],
           cause: causeAt(raw, causes[i]) })),
      unresolved: (unresolved || []).map(([kind, polarity, , flags, actions]) =>
        ({ kind, polarity, flags, actions })),
    })),
    noText: raw.noText || [],
    refs: references(raw, setAt),
  };
  return index;
}

const COMPARE = { '=': (a, b) => a === b, '≥': (a, b) => a >= b, '≤': (a, b) => a <= b };
const foldName = s => String(s).replace(/[\uFF01-\uFF5E]/g,
  ch => String.fromCharCode(ch.charCodeAt(0) - 0xFEE0)).replace(/\u3000/g, ' ').toLowerCase();

function cardAttr(card, attr) {
  if (attr === '種族') return card.r || null;
  if (attr === '屬性') return card.at || null;
  if (attr === '等級') return (card.s || []).indexOf('xyz') < 0 && card.lv != null ? card.lv : null;
  return null;
}

function fitsCondition(index, cond, card, p) {
  switch (cond.op) {
    case '且': return cond.args.every(a => fitsCondition(index, a, card, p));
    case '大類': return card.c === index.givenCode.cat.get(cond.value);
    case '屬性比較': {
      const want = cond.attr === '種族' ? index.givenCode.race.get(cond.value)
        : cond.attr === '屬性' ? index.givenCode.attr.get(cond.value) : cond.value;
      const have = cardAttr(card, cond.attr);
      return have != null && want != null && !!COMPARE[cond.cmp] && COMPARE[cond.cmp](have, want);
    }
    case '字段': return cond.setcodes.some(code => index.inArchetype(code, p));
    case '卡名包含': {
      const text = foldName(cond.text);
      return [card.n, card.nj, card.ne, card.ax]
        .some(n => typeof n === 'string' && foldName(n).indexOf(text) >= 0);
    }
    default: return false;
  }
}

function references(raw, setAt) {
  const of = new Map();
  for (const [id, , , , refs] of raw.cards) {
    if (refs && refs.length) {
      of.set(id, refs.map(([block, generic, key, part, clause]) =>
        ({ block, generic: !!generic, key, part, clause })));
    }
  }
  const parts = raw.parts.map(([, entries]) =>
    new Map(entries.map(([p, blocks]) => [raw.ids[p], blocks])));
  const decoded = new Map();
  return {
    of,
    blocksOf: (id, part) => parts[part].get(id) || null,
    candidates(key) {
      if (!decoded.has(key)) decoded.set(key, setAt(key).positions().map(p => raw.ids[p]));
      return decoded.get(key);
    },
  };
}

function byRows(counted) {
  return counted.map(([value, rows], i) => ({ value, rows, i }))
    .sort((a, b) => b.rows - a.rows || a.i - b.i)
    .map(c => c.value);
}

function options(index) {
  const words = byRows(index.words.filter(w => w[1] > 0));
  return { shown: words.slice(0, SHOWN_WORDS), more: words.slice(SHOWN_WORDS) };
}

function agentMatches(want, have, includeUnrestricted) {
  if (have === UNRESTRICTED) return includeUnrestricted;
  if (have === IMPLIED_SELF) return want === '我方';
  return have === want || have === BOTH_SIDES;
}

function causeMatches(want, have, includeUnrestricted) {
  if (!have) return false;
  if (have.kind === UNRESTRICTED) return includeUnrestricted;
  if (have.kind !== want.kind && (CAUSE_COVERS[have.kind] || []).indexOf(want.kind) < 0) {
    return false;
  }
  return !want.side || have.side == null || have.side === want.side || have.side === BOTH_SIDES;
}

function causeOptions(index) {
  return byRows(index.causes)
    .filter(kind => kind !== null && kind !== UNRESTRICTED && !CAUSE_COVERS[kind]);
}

function zoneOptions(index) {
  return byRows(index.zones);
}

function toggleKind(kinds, kind) {
  const now = kindsOf(kinds);
  if (now.indexOf(kind) < 0) return kindsOf(now.concat(kind));
  return now.length > 1 ? now.filter(k => k !== kind) : now;
}

function positions(map, values) {
  return values.map(v => map.get(v));
}

function kindSet(index, rq) {
  return new Set(positions(index.kindAt, rq.include_condition
    ? rq.kinds : rq.kinds.filter(k => k !== '條件')));
}

function zoneTest(index, want) {
  if (!want) return null;
  const fits = want.map(({ zone, side }) => {
    const z = index.zoneAt.get(zone);
    const s = side == null ? null : index.sideAt.get(side);
    if (z === undefined || s === undefined) return () => false;
    return s === null
      ? code => Math.floor(code / index.sideSlots) === z
      : code => code === z * index.sideSlots + s;
  });
  return pos => !!pos && !pos.inferred && pos.codes.some(code => fits.some(f => f(code)));
}

function objectTest(index, rq) {
  if (rq.this_card) return obj => obj.kind === index.objectKinds.thisCard;
  if (rq.condition != null) {
    const fits = index.satisfying(rq.condition);
    const seen = new Map();
    return obj => {
      if (!seen.has(obj.set)) seen.set(obj.set, index.meets(obj.set, fits));
      return seen.get(obj.set);
    };
  }
  if (rq.card == null) return null;
  const p = index.cardAt.get(rq.card);
  return obj => p !== undefined && index.inSet(obj.set, p);
}

function lineTest(index, rq) {
  const from = zoneTest(index, rq.from_zones);
  const to = zoneTest(index, rq.to_zones);
  const object = objectTest(index, rq);
  if (!from && !to && !object) return null;
  return line => !line.doer && !!line.object
    && (!from || from(line.from)) && (!to || to(line.to)) && (!object || object(line.object));
}

function segmentScope(index, rq) {
  const wanted = positions(index.actionAt, rq.actions);
  if (wanted.some(a => a === undefined)) return null;
  return { wanted, kinds: kindSet(index, rq),
           polarities: new Set(positions(index.polarityAt, rq.polarities)) };
}

function match(index, rq) {
  const hits = new Map();
  const scope = segmentScope(index, rq);
  if (!scope) return hits;
  const { wanted, kinds, polarities } = scope;
  const lineFits = lineTest(index, rq);
  for (const card of index.cards) {
    for (const seg of card.segments) {
      if (seg.replacing || !kinds.has(seg.kind) || !polarities.has(seg.polarity)) continue;
      if (!wanted.every(a => seg.actions.indexOf(a) >= 0)) continue;
      if (lineFits && !seg.lines.some(lineFits)) continue;
      if (rq.agent && !agentMatches(rq.agent, seg.agent, !!rq.include_unrestricted)) continue;
      if (rq.recipient && seg.recipient !== rq.recipient && seg.recipient !== BOTH_SIDES) continue;
      if (rq.cause && !causeMatches(rq.cause, seg.cause, !!rq.include_unrestricted)) continue;
      if (!hits.has(card.id)) hits.set(card.id, []);
      hits.get(card.id).push(seg);
    }
  }
  for (const [id, refs] of viaHits(index, hits)) hits.set(id, refs);
  return hits;
}

function unsure(index, rq, found) {
  const out = new Set(index.noText.filter(id => !found.has(id)));
  if (!rq.actions.length) return out;
  const scope = segmentScope(index, rq);
  if (!scope) return out;
  const { wanted, kinds, polarities } = scope;
  const substituting = rq.card != null || rq.condition != null;
  const flags = index.unresolvedFlags;
  const reason = substituting ? flags.reasonSubstituting : flags.reason;
  for (const card of index.cards) {
    if (found.has(card.id)) continue;
    for (const u of card.unresolved) {
      if (!(u.flags & reason) || !wanted.every(a => u.actions.indexOf(a) >= 0)) continue;
      if (!(u.flags & flags.reference)) {
        if (u.flags & flags.replacing && !rq.replacement) continue;
        if (!kinds.has(u.kind) || !polarities.has(u.polarity)) continue;
      }
      out.add(card.id);
      break;
    }
  }
  return out;
}

function viaHits(index, direct) {
  const blockHits = new Map();
  for (const [id, segs] of direct) blockHits.set(id, new Set(segs.map(s => s.block)));
  const out = new Map();
  for (const [id, refs] of index.refs.of) {
    if (direct.has(id)) continue;
    const led = refs.filter(ref => leads(index, blockHits, ref, new Set([id])));
    if (led.length) {
      out.set(id, led.map(ref => ({ via: true, block: ref.block, clause: ref.clause })));
    }
  }
  return out;
}

function leads(index, blockHits, ref, visiting) {
  if (ref.generic) return false;
  return index.refs.candidates(ref.key).some(cid =>
    !visiting.has(cid) && reaches(index, blockHits, cid, ref.part, visiting));
}

function reaches(index, blockHits, cid, part, visiting) {
  const blocks = index.refs.blocksOf(cid, part);
  const inPart = block => blocks === null || blocks.indexOf(block) >= 0;
  const hit = blockHits.get(cid);
  if (hit && Array.from(hit).some(inPart)) return true;
  const refs = (index.refs.of.get(cid) || []).filter(ref => inPart(ref.block));
  if (!refs.length) return false;
  visiting.add(cid);
  const found = refs.some(ref => leads(index, blockHits, ref, visiting));
  visiting.delete(cid);
  return found;
}

  return Object.freeze({ condOf, count, rowQuery, suggest, prepare, options, match, unsure,
    SIDES, DEFAULT_KINDS, DEFAULT_POL, zoneOptions, causeOptions, toggleKind,
    conditionOptions, archetypeSuggest });
})();
