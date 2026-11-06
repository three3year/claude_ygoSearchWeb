/**
 * render.test.js — 呈現縫(卡片物件 → HTML 字串)的測試
 *
 * 跑法:`node --test script/web/`
 *
 * 與接縫 3 同一個沙箱(`frontend_harness.js`)載真實的 `web/js/render.js`,
 * 餵合成卡片、斷言產出的 HTML **字面**(使用者看得到的文字)——不斷言 DOM
 * 結構與 CSS class 名稱(實作細節,重構就壞而且壞得沒有意義)。
 *
 * 目前蓋[[禁限狀態]]徽章列(spec banlist,2026-08-22 使用者裁示 render 也要
 * 自動測)與[[卡文勘誤表]]原文視圖的差異標示;其餘呈現仍走人工驗收。
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert');
const harness = require('./frontend_harness.js');

const item = (code, zh) => ({ code, zh });

/* 最小 VOCAB:只放 cardHtml 會查到的表。 */
const VOCAB = {
  cat: { zh: '大類', items: [item('m', '怪獸'), item('s', '魔法'), item('t', '陷阱')] },
  sub_m: { zh: '怪獸子類型', items: [item('effect', '效果')] },
  attr: { zh: '屬性', items: [item('dark', '闇')] },
  race: { zh: '種族', items: [item('insect', '昆蟲族')] },
  rarity: { zh: 'MD 稀有度', items: [item('UR', 'UR')] },
  ot: { zh: 'OCG・TCG', items: [item('o', 'OCG 限定'), item('t', 'TCG 限定'),
                                item('b', '兩者')] },
  ban_o: { zh: 'OCG 禁限',
           items: [item('f', '禁止'), item('l', '限制'), item('s', '準限制')] },
  ban_t: { zh: 'TCG 禁限',
           items: [item('f', '禁止'), item('l', '限制'), item('s', '準限制')] },
  ban_m: { zh: 'MD 禁限',
           items: [item('f', '禁止'), item('l', '限制'), item('s', '準限制')] },
};

const sandbox = harness.load({ cards: [], vocab: VOCAB, meta: {} });

/* 一張怪獸卡的索引條目;欄位形狀與 web/data.js 一致(空值省略)。 */
function card(kw) {
  return Object.assign({
    id: 23434538, n: '增殖的G', nj: '増殖するG', ne: 'Maxx "C"',
    c: 'm', s: ['effect'], at: 'dark', r: 'insect', lv: 2,
    atk: 500, df: 200, ra: 'UR', ot: 'b',
  }, kw);
}

const html = (kw) => harness.cardHtml(sandbox, { card: card(kw), rows: null });

test('上了 OCG 榜的卡在名稱行下方長出禁限徽章列', () => {
  const out = html({ bo: 'f' });
  assert.ok(out.includes('OCG 禁止'));
  // 位置:禁限列在日/英名稱之後(2026-08-22 使用者裁示「名稱行下面一行」)
  assert.ok(out.indexOf('OCG 禁止') > out.indexOf('Maxx'));
});

test('統一三值的字面:限制與準限制', () => {
  assert.ok(html({ bo: 'l' }).includes('OCG 限制'));
  assert.ok(html({ bo: 's' }).includes('OCG 準限制'));
});

test('沒上任何榜的卡完全不長禁限列', () => {
  const out = html({});
  assert.ok(!out.includes('禁止'));
  assert.ok(!out.includes('OCG'));  // ot 是「兩者」,畫面上不該有任何 OCG 字樣
});

test('任一賽制上榜即整列出現,各賽制欄位固定順序齊列', () => {
  // 只上 OCG 榜:TCG 欄仍在,已發行未上榜顯示半形「-」(說明字面是無限制)
  const out = html({ bo: 'f' });
  assert.ok(out.includes('OCG 禁止'));
  assert.ok(out.includes('TCG 無限制'));
  const ban = /<div class="card-ban">[\s\S]*?<\/div>/.exec(out)[0]
    .replace(/<[^>]+>/g, '');
  assert.ok(ban.includes('-'));
  assert.ok(!ban.includes('—'));
  assert.ok(out.indexOf('OCG 禁止') < out.indexOf('TCG 無限制'));
  // 同一張卡兩賽制各自的值互不干擾
  const both = html({ bo: 's', bt: 'f' });
  assert.ok(both.includes('OCG 準限制'));
  assert.ok(both.includes('TCG 禁止'));
});

test('MD 欄:上榜值、已收錄未上榜「—」、未收錄「未發行」(由稀有度推導)', () => {
  // 三榜齊上:三欄依 OCG、TCG、MD 順序齊列
  const all = html({ bo: 'f', bt: 'f', bm: 'l' });
  assert.ok(all.includes('MD 限制'));
  assert.ok(all.indexOf('TCG 禁止') < all.indexOf('MD 限制'));
  // 已收錄(有 ra)未上榜 → 「—」(說明字面是無限制)
  assert.ok(html({ bo: 'f' }).includes('MD 無限制'));
  // 未收錄進 MD(沒有 ra 欄位)→ 「未發行」
  const notInMd = harness.cardHtml(sandbox, {
    card: (() => { const c = card({ bo: 'f' }); delete c.ra; return c; })(),
    rows: null,
  });
  assert.ok(notInMd.includes('MD 未發行'));
  assert.ok(!notInMd.includes('MD 無限制'));
});

test('未在該賽制發行的欄位:title 寫「未發行」,畫面同樣顯示半形「-」', () => {
  // OCG 限定卡(ot='o')上了 OCG 榜:TCG 欄是未發行,不是無限制
  const ocgOnly = html({ ot: 'o', bo: 'l' });
  assert.ok(ocgOnly.includes('TCG 未發行'));
  assert.ok(!ocgOnly.includes('TCG 無限制'));
  // 畫面字面統一是「-」,未發行/無限制的區分只在 title(2026-08-22 使用者裁示)
  const ban = /<div class="card-ban">[\s\S]*?<\/div>/.exec(ocgOnly)[0]
    .replace(/<[^>]+>/g, '');
  assert.ok(ban.includes('-'));
  assert.ok(!ban.includes('未發行'));
  // TCG 限定卡(ot='t')上了 TCG 榜:OCG 欄是未發行
  const tcgOnly = html({ ot: 't', bt: 'f' });
  assert.ok(tcgOnly.includes('OCG 未發行'));
  assert.ok(tcgOnly.includes('TCG 禁止'));
});

test('被勘誤的卡:原文視圖帶差異標示,刪去與補上兩側說明都在', () => {
  // og 是建置期算好的差異段落表(2026-08-22 使用者裁示:原文要標示差異)
  const out = html({ og: [['=', '召喚成功時，'], ['-', '可以'],
                          ['=', '發動。'], ['+', '此效果在對手回合也能發動。']] });
  assert.ok(out.includes('顯示查牌網原文'));            // 對照鈕
  assert.ok(out.includes('可以'));                      // 原文才有的字仍看得到
  assert.ok(out.includes('本站勘誤後刪去'));            // 刪去段的說明(title)
  assert.ok(out.includes('本站勘誤後補上'));            // 補上段的說明(title)
  assert.ok(out.includes('此效果在對手回合也能發動。'));
});

test('沒被勘誤的卡:沒有對照鈕、沒有原文視圖', () => {
  const out = html({});
  assert.ok(!out.includes('顯示查牌網原文'));
  assert.ok(!out.includes('本站勘誤'));
});

test('被本站改寫的卡:對照鈕在,原文視圖是舊全文純文字、不帶差異標註', () => {
  // ow 是改寫前的查牌網舊譯全文(text-rewrite 票03):整段重寫,
  // 逐字刪改標註是滿版噪音,純文字視圖;刪除線/綠底仍是勘誤卡專屬
  const out = html({ ow: '反轉：選擇場上1隻守備表示怪獸破壞。' });
  assert.ok(out.includes('顯示查牌網原文'));              // 對照鈕沿用
  assert.ok(out.includes('本站改寫'));                    // 鈕的說明講改寫
  assert.ok(out.includes('反轉：選擇場上1隻守備表示怪獸破壞。'));
  assert.ok(!out.includes('本站勘誤後刪去'));             // 沒有勘誤的差異標註
  assert.ok(!out.includes('本站勘誤後補上'));
});
