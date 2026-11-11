'use strict';

/* 外部站的網址集中在這裡:某站換網域時前端只改這一處。
   建置腳本(Python)的下載網址不收進來——語言不同無法共用,而且下載用的
   API／原始檔網址本來就跟給訪客的首頁網址不同。 */
const Sources = (() => {
/* 查牌網首頁:頁尾連結與單卡頁網址共用,只定義這一次 */
const QUERY_HOME = 'https://salix5.github.io/query/';
/* 卡圖:salix5/query-data 的 CDN,檔名就是不補零的卡片密碼 */
const PIC = 'https://cdn.jsdelivr.net/gh/salix5/query-data@master/pics/';

/* 頁尾的資料來源,依頁尾顯示順序。連結文字寫資料項目、站名給懸停提示用。 */
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
].map(Object.freeze));

function cardPageUrl(id) {
  return `${QUERY_HOME}?code=${id}`;
}

function cardImageUrl(id) {
  return `${PIC}${id}.jpg`;
}

return Object.freeze({ FOOTER, cardPageUrl, cardImageUrl });
})();
