'use strict';

const Sites = (() => {
const QUERY_HOME = 'https://salix5.github.io/query/';
/* 卡圖:salix5/query-data 的 CDN,檔名就是不補零的卡片密碼 */
const CARD_IMAGE_BASE = 'https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/';
const LINK_REL = 'noopener noreferrer';

const FOOTER = Object.freeze([
  { label: '中文卡文、卡圖', site: '查牌網', url: QUERY_HOME },
  { label: '日英卡名、日文卡文', site: 'ygopro-database',
    url: 'https://github.com/mycard/ygopro-database' },
  { label: 'MD 稀有度、MD 禁限', site: 'Master Duel Meta',
    url: 'https://www.masterduelmeta.com/' },
  { label: 'Genesys 點數、OCG/TCG 禁限', site: 'YGOPRODeck',
    url: 'https://ygoprodeck.com/' },
  { label: '效果類型', site: 'Yu-Gi-Oh! Neuron',
    url: 'https://www.db.yugioh-card.com/yugiohdb/?request_locale=ja' },
]);

function cardPageUrl(id) {
  return `${QUERY_HOME}?code=${id}`;
}

function cardImageUrl(id) {
  return `${CARD_IMAGE_BASE}${id}.jpg`;
}

  return Object.freeze({ FOOTER, LINK_REL, cardPageUrl, cardImageUrl });
})();
