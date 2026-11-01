'use strict';

/* 目錄導覽在檔尾(Acat.catalog)。以下是舊的[[動作類別]]類別樹,引擎的 q.act 還在讀,
   規格 4 票 07 刪。
   類別樹(VOCAB.acat,建置期由分詞鏈匯出檔帶來,ADR-0017)。
   節點以路徑識別(節點名以 › 連寫):同一詞元可出現在幾個大類下,詞元節點的預設葉
   又和詞元同名,只用名稱會撞。詞元節點帶預設葉時,預設葉另成一個子節點排在最後,
   路徑是詞元節點路徑再接一次同名——選詞元節點=底下所有葉,選預設葉=只有它。 */
const Acat = (() => {
const { VOCAB } = Util;

const DOMAIN = VOCAB.acat || { leaves: [], tree: [], covered: 0 };
const SEP = '›';
const LEAVES = DOMAIN.leaves || [];
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

(DOMAIN.tree || []).forEach(node => add(node, null, 0));
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

/* 過濾框:名稱含字面(子字串)的節點連同祖先與子孫留下,祖先強制展開(命中節點
   自己與子孫照原本的展開狀態,可再點開);空字面回 null=不過濾。只決定顯示,
   不碰已選條件。 */
function filter(term) {
  const t = String(term == null ? '' : term).trim();
  if (!t) return null;
  const visible = new Set(), open = new Set();
  const down = id => {
    visible.add(id);
    BY_ID[id].kids.forEach(down);
  };
  NODES.forEach(n => {
    if (n.name.indexOf(t) < 0) return;
    down(n.id);
    for (let p = n.parent; p; p = BY_ID[p].parent) {
      visible.add(p);
      open.add(p);
    }
  });
  return { visible, open };
}

/* 目錄導覽(predicate-ui 票 02):VOCAB.catalog 依路徑建樹。目錄不是完整的樹:缺的路徑
   (規則改寫›にする、表示形式›にする)補純導覽節點;大類 召喚 與詞元節點 召喚 同路徑,
   詞元節點掛在大類底下,鍵另外編,它的葉路徑仍是 召喚。
   節點 {key, name, parent, kids, path, count}:path 是具名查詢的葉路徑,大類、中類、純導覽
   是空字串(點了只展開);count 是列上的張數,純導覽沒有。 */
const catalog = (() => {
  const nodes = new Map();
  const roots = [];
  const attach = (key, name, parentKey, row) => {
    const named = !!(row && row.predicate);
    nodes.set(key, { key, name, parent: parentKey, kids: [],
                     path: named ? row.path.join(SEP) : '',
                     count: row ? countOf(row) : null });
    if (parentKey) nodes.get(parentKey).kids.push(key);
    else roots.push(key);
  };
  const ensure = steps => {
    const key = steps.join(SEP);
    if (steps.length && !nodes.has(key)) {
      attach(key, steps[steps.length - 1], ensure(steps.slice(0, -1)), null);
    }
    return key;
  };
  (VOCAB.catalog || []).forEach(row => {
    const key = row.path.join(SEP);
    if (nodes.has(key)) attach(key + SEP + '#' + row.name, row.name, key, row);
    else attach(key, row.name, ensure(row.path.slice(0, -1)), row);
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

  return Object.freeze({
    LEAVES,
    COVERED: DOMAIN.covered || 0,
    present: NODES.length > 0,
    roots: NODES.filter(n => !n.parent).map(n => n.id),
    node, leavesOf, sortIds, filter,
    catalog,
  });
})();
