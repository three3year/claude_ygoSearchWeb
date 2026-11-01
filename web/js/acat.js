'use strict';

const Acat = (() => {
const { VOCAB } = Util;

const SEP = '›';

/* 目錄導覽(predicate-ui 票 02):VOCAB.catalog 依路徑建樹。目錄不是完整的樹:缺的路徑
   (規則改寫›にする、表示形式›にする)補純導覽節點;LP・ダメージ、表示形式、規則改寫的
   子節點排在自己的列前面,所以先補的節點等到那一列出現時要接回去。大類 召喚 與詞元節點
   召喚 同路徑,詞元節點掛在大類底下,鍵另外編,它的葉路徑仍是 召喚。
   節點 {key, name, parent, kids, path, count}:path 是具名查詢的葉路徑,大類、中類、純導覽
   是空字串(點了只展開);count 是列上的張數,純導覽沒有。 */
const catalog = (() => {
  const nodes = new Map();
  const roots = [];
  const fill = (node, row) => {
    node.path = row.predicate ? row.path.join(SEP) : '';
    node.count = countOf(row);
  };
  const attach = (key, name, parentKey) => {
    const node = { key, name, parent: parentKey, kids: [], path: '', count: null };
    nodes.set(key, node);
    if (parentKey) nodes.get(parentKey).kids.push(key);
    else roots.push(key);
    return node;
  };
  const ensure = steps => {
    const key = steps.join(SEP);
    if (steps.length && !nodes.has(key)) {
      attach(key, steps[steps.length - 1], ensure(steps.slice(0, -1)));
    }
    return key;
  };
  (VOCAB.catalog || []).forEach(row => {
    const key = ensure(row.path);
    const node = nodes.get(key);
    fill(node.count ? attach(key + SEP + '#' + row.name, row.name, key) : node, row);
  });

  /* 名字含字面的節點連同祖先與子孫留下,祖先展開;空字面回 null=不過濾。 */
  function filterNodes(term) {
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

  return Object.freeze({
    roots,
    node: key => nodes.get(key) || null,
    filter: filterNodes,
  });
})();

/* 效果位有張數就標數字;0 張的查詢灰字標條件模型會帶的那個位置。 */
function countOf(row) {
  const pos = Cond.defaultPosition(row);
  return pos === '效果' ? { text: String(row.cards.效果), zero: false }
                        : { text: pos + ' ' + row.cards[pos], zero: true };
}

  return Object.freeze({ catalog });
})();
