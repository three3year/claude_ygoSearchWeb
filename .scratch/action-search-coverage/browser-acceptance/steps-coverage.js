'use strict';
/* 第 2 份清單:.scratch/action-search-coverage/manual-acceptance.md
   每一步開始前按「清除條件」,再展開「動作搜尋」。 */

const { fmt } = require('./lib');

const L = 'cov';

function countCheck(rec, name, c, n, unsure) {
  rec.eq(`${name} 張數`, fmt(n), fmt(c.n));
  if (unsure !== undefined) rec.eq(`${name} 無法確認`, fmt(unsure), fmt(c.unsure));
}

function has(rec, set, id, name, want) {
  rec.eq(`${name}(${id})${want ? '在' : '不在'}`, want ? '在' : '不在', set.has(id) ? '在' : '不在');
}

async function fresh(site) {
  await site.open();
  await site.clearAll();
  await site.openAction();
}

/* ---------------- 從、到的方 ---------------- */

async function sides(S, run) {
  const { rec } = S;

  await run('從、到的方 1', '「特殊召喚」從「墓地」方「對手」', '83 張(無法確認 2,989);死者蘇生在、過早的埋葬不在、霞之谷的幼怪鳥不在', async site => {
    await fresh(site);
    await site.words(['特殊召喚']);
    await site.zone('from', '墓地', '對手');
    countCheck(rec, '特殊召喚 從對手的墓地', await site.search(), 83, 2989);
    const ids = await site.idSet();
    has(rec, ids, 83764718, '死者蘇生', true);
    has(rec, ids, 70828912, '過早的埋葬', false);
    has(rec, ids, 14983497, '霞之谷的幼怪鳥', false);
  });

  await run('從、到的方 2', '方改「我方」;再改「不限哪一方」', '1,614 張(無法確認 2,650),三張都在;不限 1,647 張', async site => {
    await fresh(site);
    await site.words(['特殊召喚']);
    await site.zone('from', '墓地', '我方');
    countCheck(rec, '特殊召喚 從我方的墓地', await site.search(), 1614, 2650);
    const ids = await site.idSet();
    has(rec, ids, 83764718, '死者蘇生', true);
    has(rec, ids, 70828912, '過早的埋葬', true);
    has(rec, ids, 14983497, '霞之谷的幼怪鳥', true);
    await site.zone('from', '墓地', '');
    countCheck(rec, '特殊召喚 從墓地', await site.search(), 1647, 2638);
  });

  await run('從、到的方 3', '「破壞」從「場上」方「對手」;改「我方」', '1,264 張(1,298),黑洞、落雷在;我方 922 張,黑洞在、落雷不在', async site => {
    await fresh(site);
    await site.words(['破壞']);
    await site.zone('from', '場上', '對手');
    countCheck(rec, '破壞 從對手的場上', await site.search(), 1264, 1298);
    let ids = await site.idSet();
    has(rec, ids, 53129443, '黑洞', true);
    has(rec, ids, 12580477, '落雷', true);
    await site.zone('from', '場上', '我方');
    countCheck(rec, '破壞 從我方的場上', await site.search(), 922, 1316);
    ids = await site.idSet();
    has(rec, ids, 53129443, '黑洞', true);
    has(rec, ids, 12580477, '落雷', false);
  });

  await run('從、到的方 4', '「送墓」到「墓地」方「對手」;改「我方」', '1,207 張(721),愚蠢的埋葬在、黑龍之雛不在;我方 1,417 張,兩張都在', async site => {
    await fresh(site);
    await site.words(['送墓']);
    await site.zone('to', '墓地', '對手');
    countCheck(rec, '送墓 到對手的墓地', await site.search(), 1207, 721);
    let ids = await site.idSet();
    has(rec, ids, 81439173, '愚蠢的埋葬', true);
    has(rec, ids, 36262024, '黑龍之雛', false);
    await site.zone('to', '墓地', '我方');
    countCheck(rec, '送墓 到我方的墓地', await site.search(), 1417, 713);
    ids = await site.idSet();
    has(rec, ids, 81439173, '愚蠢的埋葬', true);
    has(rec, ids, 36262024, '黑龍之雛', true);
  });

  await run('從、到的方 5', '「除外」到「除外」方「對手」', '1,214 張(630),次元幽閉在', async site => {
    await fresh(site);
    await site.words(['除外']);
    await site.zone('to', '除外', '對手');
    countCheck(rec, '除外 到對手的除外', await site.search(), 1214, 630);
    has(rec, await site.idSet(), 70342110, '次元幽閉', true);
  });

  await run('從、到的方 6', '「返回」到「手牌」方「對手」;改「我方」', '302 張(634),颶風在;我方 564 張,颶風也在', async site => {
    await fresh(site);
    await site.words(['返回']);
    await site.zone('to', '手牌', '對手');
    countCheck(rec, '返回 到對手的手牌', await site.search(), 302, 634);
    has(rec, await site.idSet(), 42703248, '颶風', true);
    await site.zone('to', '手牌', '我方');
    countCheck(rec, '返回 到我方的手牌', await site.search(), 564, 591);
    has(rec, await site.idSet(), 42703248, '颶風', true);
  });

  await run('從、到的方 7', '「捨棄」從「手牌」方「對手」;改「我方」', '45 張(189),暗黑界的導師 塞魯利在;我方 803 張,它不在', async site => {
    await fresh(site);
    await site.words(['捨棄']);
    await site.zone('from', '手牌', '對手');
    countCheck(rec, '捨棄 從對手的手牌', await site.search(), 45, 189);
    has(rec, await site.idSet(), 7623640, '暗黑界的導師 塞魯利', true);
    await site.zone('from', '手牌', '我方');
    countCheck(rec, '捨棄 從我方的手牌', await site.search(), 803, 133);
    has(rec, await site.idSet(), 7623640, '暗黑界的導師 塞魯利', false);
  });

  await run('從、到的方 8', '看上面幾張「在」的卡的底色句', '有底色的那一句就是做這個動作、從或到這個區域的效果(例:塞魯利是②)', async site => {
    const probes = [
      ['特殊召喚', 'from', '墓地', '對手', 83764718, '死者蘇生', /墓地/],
      ['破壞', 'from', '場上', '對手', 53129443, '黑洞', /場上/],
      ['破壞', 'from', '場上', '對手', 12580477, '落雷', /對手場上/],
      ['送墓', 'to', '墓地', '對手', 81439173, '愚蠢的埋葬', /墓地/],
      ['除外', 'to', '除外', '對手', 70342110, '次元幽閉', /除外/],
      ['返回', 'to', '手牌', '對手', 42703248, '颶風', /手牌|手卡/],
      ['捨棄', 'from', '手牌', '對手', 7623640, '暗黑界的導師 塞魯利', /手牌/],
    ];
    for (const [word, key, zone, side, id, name, re] of probes) {
      await fresh(site);
      await site.words([word]);
      await site.zone(key, zone, side);
      await site.search();
      const r = await site.cardInfo(id, `cov-sides8-${id}`);
      if (!r.info) { rec.check(`${name} 找得到`, '在', '不在', false); continue; }
      const texts = r.info.hits.map(h => h.text);
      rec.check(`${name}:有底色句、含「${word === '送墓' ? '墓地' : word}」與區域`, '有',
        texts.join(' / ') || '(沒有底色句)',
        texts.length > 0 && texts.some(t => re.test(t)));
      if (id === 7623640) {
        rec.check('塞魯利的底色句是②「對手選1張自身的手牌捨棄」', '②…對手…手牌…捨棄', texts.join(' / '),
          texts.length === 1 && /^②/.test(texts[0]) && /對手/.test(texts[0]) && /捨棄/.test(texts[0]));
      }
      rec.look(`${word} ${key === 'from' ? '從' : '到'}${side}的${zone}:${name} 的底色句是否就是這個動作、這個區域的效果`, r.shot);
    }
  });
}

/* ---------------- 卡名包含 ---------------- */

async function nameContains(S, run) {
  const { rec } = S;
  const setup = async (site, word) => {
    await fresh(site);
    await site.words([word || '破壞']);
    await site.target('cond');
  };

  await run('卡名包含 1', '「破壞」給條件,卡名包含逐字打中文「黑魔導」;改日文「ブラック・マジシャン」;改英文「Dark Magician」', '1,260 張(1,323);同 1,260;英文 1,266', async site => {
    await setup(site);
    const bad = await site.typeCheck('#actionFields input[data-gname]', '黑魔導');
    rec.check('逐字打「黑魔導」游標與值', '每個字都對', bad.join(';') || '每個字都對', !bad.length);
    countCheck(rec, '黑魔導', await site.search(), 1260, 1323);
    await site.givenName('ブラック・マジシャン');
    countCheck(rec, 'ブラック・マジシャン', await site.search(), 1260, 1323);
    await site.givenName('Dark Magician');
    countCheck(rec, 'Dark Magician', await site.search(), 1266, 1323);
  });

  await run('卡名包含 2', '打「黑%導」;改全形「黑％導」', '1,550 張(1,299);全形同樣 1,550', async site => {
    await setup(site);
    await site.givenName('黑%導');
    countCheck(rec, '黑%導', await site.search(), 1550, 1299);
    await site.givenName('黑％導');
    countCheck(rec, '黑％導', await site.search(), 1550, 1299);
  });

  await run('卡名包含 3', '清除條件,只在側欄上方「卡名」(中文)打「黑%導」;改全形「黑％導」', '28 張;0 張', async site => {
    await site.open();
    await site.clearAll();
    rec.eq('卡名語言鈕', '中', await site.page.$eval('#fNameLang', b => b.textContent));
    await site.page.fill('#fName', '黑%導');
    countCheck(rec, '卡名框 黑%導', await site.search(), 28);
    await site.page.fill('#fName', '黑％導');
    const c = await site.search();
    rec.eq('卡名框 黑％導 張數', '0', fmt(c.n));
    rec.note(`全形時結果區:${c.info}`);
  });

  await run('卡名包含 4', '回到動作搜尋(破壞、給條件),卡名包含打全形「ＤＲＡＧＯＮ」;改「dragon」', '1,684 張;同樣 1,684', async site => {
    await setup(site);
    await site.givenName('ＤＲＡＧＯＮ');
    countCheck(rec, 'ＤＲＡＧＯＮ', await site.search(), 1684, 1287);
    await site.givenName('dragon');
    countCheck(rec, 'dragon', await site.search(), 1684, 1287);
  });

  await run('卡名包含 5', '打「  黑魔導 」(前後有空白)', '1,260 張,同第 1 步', async site => {
    await setup(site);
    await site.givenName('  黑魔導 ');
    countCheck(rec, '「  黑魔導 」', await site.search(), 1260, 1323);
  });

  await run('卡名包含 6', '只打「%」', '2,200 張(978),和只選破壞相同;摺疊鈕條件數不算卡名包含', async site => {
    await fresh(site);
    await site.words(['破壞']);
    const plain = await site.search();
    const fPlain = await site.page.$eval('#btnFilters', e => e.textContent);
    await site.target('cond');
    await site.givenName('%');
    const ac = await site.page.$eval('#actionCount', e => e.textContent);
    const c = await site.search();
    countCheck(rec, '「%」', c, 2200, 978);
    rec.eq('和只選破壞相同', `${fmt(plain.n)}/${fmt(plain.unsure)}`, `${fmt(c.n)}/${fmt(c.unsure)}`);
    rec.eq('摺疊鈕', fPlain, await site.page.$eval('#btnFilters', e => e.textContent));
    rec.eq('動作搜尋標題旁的條件數', '1', ac);
  });

  await run('卡名包含 7', '「加入手牌」給條件,卡名包含「白銀之城的狂時鐘」;改正名「拉比麗斯的狂時鐘」', '70 張(765);同樣 70', async site => {
    await setup(site, '加入手牌');
    await site.givenName('白銀之城的狂時鐘');
    const a = await site.search();
    countCheck(rec, '白銀之城的狂時鐘(別名)', a, 70, 765);
    const ida = await site.idSet();
    await site.givenName('拉比麗斯的狂時鐘');
    countCheck(rec, '拉比麗斯的狂時鐘', await site.search(), 70, 765);
    const idb = await site.idSet();
    rec.eq('兩次的卡逐張相同', 'true', String(ida.size === idb.size && [...ida].every(i => idb.has(i))));
  });

  await run('卡名包含 8', '「特殊召喚」給條件,卡名包含「救世龍」;改日文「救世竜」', '328 張(2,942),聚集思念之龍在;日文同樣 328', async site => {
    await setup(site, '特殊召喚');
    await site.givenName('救世龍');
    countCheck(rec, '救世龍', await site.search(), 328, 2942);
    const a = await site.idSet();
    has(rec, a, 291414, '聚集思念之龍', true);
    rec.note(`救世龍本卡(21159309):${a.has(21159309) ? '在' : '不在'}(stats 記錄不在)`);
    await site.givenName('救世竜');
    countCheck(rec, '救世竜', await site.search(), 328, 2942);
    const b = await site.idSet();
    has(rec, b, 291414, '聚集思念之龍', true);
    rec.eq('兩次的卡逐張相同', 'true', String(a.size === b.size && [...a].every(i => b.has(i))));
  });
}

/* ---------------- 介面沒變 ---------------- */

async function ui(S, run) {
  const { rec } = S;

  await run('介面沒變 1', '看動作搜尋區塊的欄位、按鈕、下拉', '與上一輪相同,沒有新按鈕或選項;方的下拉仍只有不限哪一方、我方、對手', async site => {
    await fresh(site);
    const r = await site.page.evaluate(() => {
      const f = document.getElementById('actionFields');
      const texts = s => [...f.querySelectorAll(s)].map(e => e.textContent.trim());
      return {
        labels: texts(':scope > .group-label').join('、'),
        modes: texts('button[data-mode]').join('、'),
        kinds: texts('label:has(input[data-kind])').join('、'),
        pol: texts('button[data-pol]').join('、'),
        agent: texts('button[data-agent]').join('、'),
        recipient: texts('button[data-recipient]').join('、'),
        sideFrom: texts('select[data-side="from"] option').join('、'),
        sideTo: texts('select[data-side="to"] option').join('、'),
        causeSide: texts('select[data-cause-side] option').join('、'),
        selects: f.querySelectorAll('select').length,
        checkboxes: f.querySelectorAll('input[type="checkbox"]').length,
        textInputs: f.querySelectorAll('input[type="text"], input[type="number"]').length,
      };
    });
    rec.eq('標題', '動作、從哪裡、到哪裡、被動作的卡、這個動作是、極性、誰做的、落在誰身上、因為什麼', r.labels);
    rec.eq('被動作的卡選項', '不指定、這張卡自己、指定一張卡、給條件', r.modes);
    rec.eq('段類別', '效果、代價、觸發條件', r.kinds);
    rec.eq('極性', '會做、限制、抗性', r.pol);
    rec.eq('誰做的', '不限、我方、對手', r.agent);
    rec.eq('落在誰身上', '不限、我方、對手', r.recipient);
    rec.eq('從哪裡的方', '不限哪一方、我方、對手', r.sideFrom);
    rec.eq('到哪裡的方', '不限哪一方、我方、對手', r.sideTo);
    rec.eq('原因的方', '不限哪一方、我方的、對手的', r.causeSide);
    rec.eq('下拉數(從、到各兩個,原因兩個)', '6', String(r.selects));
    rec.eq('勾選數', '4', String(r.checkboxes));
    rec.eq('輸入框數(不指定時)', '0', String(r.textInputs));
    rec.note('另以 git 確認:web/js/action-panel.js、web/index.html 與 action-search-web 分支相同(這一輪只改 web/js/action.js);web/style.css 的工作樹改動是側欄寬度');
  });

  await run('介面沒變 2', '在幾個步驟之間按上一頁、下一頁', '條件(含方與卡名包含)跟著還原,結果和當時一樣', async site => {
    const snap = async () => {
      await site.settle();
      const c = await site.counts();
      const r = await site.page.evaluate(() => {
        const f = document.getElementById('actionFields');
        const v = s => (f.querySelector(s) || {}).value || '';
        return {
          words: [...f.querySelectorAll('button[data-word][data-st="in"]')].map(b => b.dataset.word).join(','),
          from: v('select[data-zone="from"]') + '/' + v('select[data-side="from"]'),
          mode: (f.querySelector('button[data-mode][data-st="in"]') || { dataset: {} }).dataset.mode,
          name: v('input[data-gname]'),
        };
      });
      return { ...r, n: c.n, unsure: c.unsure };
    };
    const show = s => `[${s.words}] 從${s.from} ${s.mode} 卡名「${s.name}」 ${fmt(s.n)}/${fmt(s.unsure)}`;
    const states = [];
    await fresh(site);
    await site.words(['特殊召喚']);
    await site.zone('from', '墓地', '對手');
    await site.search();
    states.push(await snap());
    await site.zone('from', '墓地', '我方');
    await site.search();
    states.push(await snap());
    await site.clearAll();
    await site.words(['破壞']);
    await site.target('cond');
    await site.givenName('黑魔導');
    await site.search();
    states.push(await snap());
    await site.givenName('黑%導');
    await site.search();
    states.push(await snap());
    rec.note('走過的狀態:' + states.map(show).join(' → '));
    rec.eq('第 1 個狀態張數', '83/2,989', `${fmt(states[0].n)}/${fmt(states[0].unsure)}`);
    rec.eq('第 3 個狀態張數', '1,260/1,323', `${fmt(states[2].n)}/${fmt(states[2].unsure)}`);
    for (let i = states.length - 2; i >= 0; i--) {
      await site.page.goBack();
      await site.page.waitForTimeout(300);
      const s = await snap();
      rec.eq(`上一頁回到第 ${i + 1} 個狀態`, show(states[i]), show(s));
    }
    for (let i = 1; i < states.length; i++) {
      await site.page.goForward();
      await site.page.waitForTimeout(300);
      const s = await snap();
      rec.eq(`下一頁到第 ${i + 1} 個狀態`, show(states[i]), show(s));
    }
  });
}

module.exports = { sections: [['從、到的方', sides], ['卡名包含', nameContains], ['介面沒變', ui]], L };
