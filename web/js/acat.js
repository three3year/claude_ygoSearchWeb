'use strict';

/* 目錄導覽(predicate-ui 票 02)。接縫:VOCAB.catalog → 導覽樹 Acat.roots、Acat.node(鍵)、
   Acat.filter(字面)。目錄不是完整的樹:缺的路徑(規則改寫›にする、表示形式›にする)補純導覽節點;
   LP・ダメージ、表示形式、規則改寫的子節點排在自己的列前面,所以先補的節點等到那一列出現時要接回去。
   大類 召喚 與詞元節點 召喚 同路徑,詞元節點掛在大類底下,鍵另外編,它的葉路徑仍是 召喚。
   帶子的詞元節點只展開:那一列另成同名子節點(鍵同上另編、葉路徑不變),和詞元節點 召喚 一樣
   排在子的最後,可選的那一列一律在最下面。
   節點 {key, name, parent, kids, path, count}:path 是具名查詢的葉路徑,大類、中類、純導覽、帶子的詞元節點
   是空字串(點了只展開);count 是列上的張數,純導覽沒有。 */
const Acat = (() => {
const { VOCAB } = Util;
const { SEP, DEFAULT_POSITION } = Cond;

const nodes = new Map();
const roots = [];

/* 效果位有張數就標數字;0 張的查詢灰字標條件模型會帶的那個位置。 */
function countOf(row) {
  const pos = Cond.defaultPosition(row);
  return pos === DEFAULT_POSITION ? { text: String(row.cards[pos]), zero: false }
                                  : { text: pos + ' ' + row.cards[pos], zero: true };
}

function fill(node, row) {
  node.path = row.predicate ? row.path.join(SEP) : '';
  node.count = countOf(row);
}

function attach(key, name, parentKey) {
  const node = { key, name, parent: parentKey, kids: [], path: '', count: null };
  nodes.set(key, node);
  if (parentKey) nodes.get(parentKey).kids.push(key);
  else roots.push(key);
  return node;
}

function ensure(steps) {
  const key = steps.join(SEP);
  if (steps.length && !nodes.has(key)) {
    attach(key, steps[steps.length - 1], ensure(steps.slice(0, -1)));
  }
  return key;
}

const lastKey = node => node.key + SEP + '#' + node.name;

(VOCAB.catalog || []).forEach(row => {
  const key = ensure(row.path);
  const node = nodes.get(key);
  fill(node.count ? attach(lastKey(node), row.name, key) : node, row);
});

Array.from(nodes.values()).forEach(node => {
  if (node.path && node.kids.length) {
    Object.assign(attach(lastKey(node), node.name, node.key), { path: node.path, count: node.count });
    node.path = '';
  }
  const at = node.kids.indexOf(lastKey(node));
  if (at >= 0) node.kids.push(node.kids.splice(at, 1)[0]);
});

/* 名字含字面的節點連同祖先與子孫留下,祖先展開;空字面回 null=不過濾。 */
function filter(term) {
  const t = String(term == null ? '' : term).trim();
  if (!t) return null;
  const visible = new Set(), open = new Set();
  const down = key => {
    visible.add(key);
    nodes.get(key).kids.forEach(down);
  };
  nodes.forEach(n => {
    if (n.name.indexOf(t) < 0) return;
    down(n.key);
    for (let p = n.parent; p; p = nodes.get(p).parent) {
      visible.add(p);
      open.add(p);
    }
  });
  return { visible, open };
}

  return Object.freeze({ roots, node: key => nodes.get(key) || null, filter });
})();
