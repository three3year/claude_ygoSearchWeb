'use strict';

const Sort = (() => {
const { VOCAB, codesOf } = Util;

const PENDULUM = 'pendulum';

function ranker(codes) {
  const order = {};
  codes.forEach((code, i) => { order[code] = i; });
  const last = codes.length;
  return code => (code in order ? order[code] : last);
}

function domainRanker(name) {
  return ranker(codesOf(name));
}

function frameRanker(name) {
  const dom = VOCAB[name] || {};
  const groups = dom.groups || [];
  const codes = (groups.length ? groups[0].codes : codesOf(name))
    .filter(code => code !== PENDULUM);
  const rank = ranker(codes);
  const last = codes.length;
  return subs => {
    let best = -1;
    for (const code of subs) {
      const i = rank(code);
      if (i < last && i > best) best = i;
    }
    return best < 0 ? last : best;
  };
}

const CAT_RANK = domainRanker('cat');
const ATTR_RANK = domainRanker('attr');
const RACE_RANK = domainRanker('race');
const FRAME_RANK = { m: frameRanker('sub_m'), s: frameRanker('sub_s'),
                     t: frameRanker('sub_t') };

function frameOf(c) {
  const rank = FRAME_RANK[c.c];
  return rank ? rank(c.s || []) : 0;
}

function isPendulum(c) {
  return (c.s || []).indexOf(PENDULUM) >= 0 ? 1 : 0;
}

function levelOf(c) {
  if (c.lk != null) return c.lk;
  return c.lv != null ? c.lv : -1;
}

const domKeys = new WeakMap();

function domKey(c) {
  let key = domKeys.get(c);
  if (!key) {
    key = [CAT_RANK(c.c), frameOf(c), isPendulum(c), -levelOf(c),
           ATTR_RANK(c.at), RACE_RANK(c.r), c.id];
    domKeys.set(c, key);
  }
  return key;
}

function cmpDomain(a, b) {
  const ka = domKey(a), kb = domKey(b);
  for (let i = 0; i < ka.length; i++) {
    if (ka[i] !== kb[i]) return ka[i] - kb[i];
  }
  return 0;
}

const KEYS = [
  { key: 'dom', zh: '預設', dir: '' },
  { key: 'atk', zh: '攻擊力', dir: 'desc' },
  { key: 'df', zh: '守備力', dir: 'desc' },
  { key: 'lv', zh: '等級／階級', dir: 'desc' },
  { key: 'n', zh: '卡名', dir: 'asc' },
  { key: 'id', zh: '卡片密碼', dir: 'asc' },
];

function stat(v) {
  return v == null || v < 0 ? null : v;
}

const VALUE = {
  atk: c => stat(c.atk),
  df: c => stat(c.df),
  lv: c => (c.lv == null ? null : c.lv),
  // 卡名比的是 UTF-16 碼元序而不是 localeCompare:後者的結果隨環境的 ICU 版本與
  // locale 而變,同一份資料在兩台裝置上會排出不同的順序,而分享出去的網址
  // 講的就是「同一個查詢在你那邊也長這樣」。
  n: c => (c.n == null ? null : c.n),
  id: c => c.id,
};

function specOf(key) {
  return KEYS.find(k => k.key === key) || KEYS[0];
}

function comparator(key, dir) {
  const spec = specOf(key);
  if (!spec.dir) return cmpDomain;
  const sign = dir === 'desc' ? -1 : 1;
  const value = VALUE[spec.key];
  return (a, b) => {
    const va = value(a), vb = value(b);
    if (va == null || vb == null) {
      if (va != null) return -1;
      if (vb != null) return 1;
      return cmpDomain(a, b);
    }
    if (va !== vb) return va < vb ? -sign : sign;
    return cmpDomain(a, b);
  };
}

function sort(entries, key, dir) {
  const cmp = comparator(key, dir);
  return entries.slice().sort((x, y) => cmp(x.card, y.card));
}

  return Object.freeze({ KEYS, specOf, sort });
})();
