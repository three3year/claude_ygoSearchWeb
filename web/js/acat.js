'use strict';

/* [[動作類別]]的類別樹(VOCAB.acat,建置期由分詞鏈匯出檔帶來,ADR-0017)。
   節點以路徑識別(節點名以 › 連寫):同一詞元可出現在幾個大類下,詞元節點的預設葉
   又和詞元同名,只用名稱會撞。詞元節點帶預設葉時,預設葉另成一個子節點排在最後,
   路徑是詞元節點路徑再接一次同名——選詞元節點=底下所有葉,選預設葉=只有它。 */
const Acat = (() => {
const { VOCAB } = Util;

const DOM = VOCAB.acat || { leaves: [], tree: [], covered: 0 };
const SEP = '›';
const LEAVES = DOM.leaves || [];
const NODES = [];
const BY_ID = {};

function add(node, parent, depth) {
  const name = node[0], leaf = node[1], children = node[2] || [];
  const id = parent ? parent.id + SEP + name : name;
  const entry = { id, name, depth, parent: parent ? parent.id : '',
                  kids: [], leaves: [], isDefault: false };
  NODES.push(entry);
  BY_ID[id] = entry;
  if (parent) parent.kids.push(id);
  children.forEach(child => {
    entry.leaves.push(...add(child, entry, depth + 1));
  });
  if (leaf >= 0) {
    if (children.length) {
      const own = { id: id + SEP + name, name, depth: depth + 1, parent: id,
                    kids: [], leaves: [leaf], isDefault: true };
      NODES.push(own);
      BY_ID[own.id] = own;
      entry.kids.push(own.id);
    }
    entry.leaves.push(leaf);
  }
  return entry.leaves;
}

(DOM.tree || []).forEach(node => add(node, null, 0));
const ORDER = {};
NODES.forEach((n, i) => { ORDER[n.id] = i; });

function node(id) {
  return BY_ID[id] || null;
}

function leavesOf(id) {
  const n = BY_ID[id];
  return n ? n.leaves : null;
}

function sortIds(ids) {
  return ids.filter(id => BY_ID[id]).sort((a, b) => ORDER[a] - ORDER[b]);
}

  return Object.freeze({
    LEAVES, NODES, SEP,
    COVERED: DOM.covered || 0,
    present: NODES.length > 0,
    roots: NODES.filter(n => !n.parent).map(n => n.id),
    node, leavesOf, sortIds,
  });
})();
