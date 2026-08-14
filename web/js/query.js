/**
 * query.js — 輸入層(側欄的條件控制項 ⇄ 查詢條件物件)
 *
 * 側欄是**唯一的可變真相**:條件物件由它導出,沒有第二份「上次查了什麼」的狀態。
 * 引擎(engine.js)吃的是這裡吐出來的純物件,因此測試餵條件進去不必假造 DOM。
 *
 * 後面幾張票的條件軸(效果文、卡片參數、效果類型)各自在 read/clear 加一段;
 * 票08 的 `#hash` 編解碼也接在這個物件上——序列化的對象就是它。
 */
'use strict';

const Query = (() => {
const { $ } = Util;

/* 卡名語言三態循環:中 → 日 → 英 → 中。碼、鈕面文字與說明在這裡一處決定,
   HTML 只給起始態(`data-v`)。 */
const LANGS = [
  { v: 'zh', label: '中', title: '比對中文卡名（含 ※ 別名）' },
  { v: 'ja', label: '日', title: '比對日文卡名（含 ※ 別名）' },
  { v: 'en', label: '英', title: '比對英文卡名' },
];

function langOf(v) {
  return LANGS.find(l => l.v === v) || LANGS[0];
}

function showLang(el, v) {
  const lang = langOf(v);
  el.dataset.v = lang.v;
  el.textContent = lang.label;
  el.title = lang.title;
}

/** 側欄目前的設定 → 查詢條件物件(接縫 3 的輸入) */
function read() {
  return {
    name: $('fName').value.trim(),
    nameLang: langOf($('fNameLang').dataset.v).v,
    code: $('fId').value.trim(),
  };
}

/** 清除條件:回到「什麼都沒設」的狀態,也就是列出全部卡片的那個狀態 */
function clear() {
  $('fName').value = '';
  $('fId').value = '';
  showLang($('fNameLang'), LANGS[0].v);
}

function init() {
  const langBtn = $('fNameLang');
  showLang(langBtn, langBtn.dataset.v);
  langBtn.addEventListener('click', () => {
    const i = LANGS.findIndex(l => l.v === langBtn.dataset.v);
    showLang(langBtn, LANGS[(i + 1) % LANGS.length].v);
  });
}

  return Object.freeze({ read, clear, init, LANGS });
})();
