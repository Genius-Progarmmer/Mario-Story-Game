// Tests web.html in a REAL browser (Chromium) with a phone emulated: real layout, real CSS, real touches.
//   cd tests && npm install && cd ..        (once: installs puppeteer-core + a small Chromium, ~70 MB)
//   node tests/web_browser_test.js web.html [screenshot-folder]
// Use your own Chrome instead: CHROME_PATH="/path/to/chrome" node tests/web_browser_test.js web.html
const path = require('path'), fs = require('fs');
const require_ = (m) => require(require.resolve(m, { paths: [__dirname, process.cwd(), ...(process.env.NODE_PATH || '').split(':').filter(Boolean)] }));
const puppeteer = require_('puppeteer-core');
const htmlFile = path.resolve(process.argv[2] || 'web.html');
const shots = process.argv[3] ? path.resolve(process.argv[3]) : null; if (shots) fs.mkdirSync(shots, { recursive: true });
const results = [];
const T = (name, ok, extra) => { results.push([name, !!ok]); console.log((ok ? 'PASS ' : 'FAIL ') + name + (!ok && extra !== undefined ? '  [' + extra + ']' : '')); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function executable() {
  if (process.env.CHROME_PATH) return { executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] };
  const c = require_('@sparticuz/chromium'); const chromium = c.default || c;
  return { executablePath: await chromium.executablePath(), args: [...chromium.args, '--no-sandbox'] };
}
const PHONE_UA = 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36';

async function open(browser, w, h, { touch = true } = {}) {
  const page = await browser.newPage();
  page.errors = []; page.on('pageerror', e => page.errors.push(e.message));
  await page.setViewport({ width: w, height: h, deviceScaleFactor: 2, isMobile: touch, hasTouch: touch });
  if (touch) await page.setUserAgent(PHONE_UA);
  await page.goto('file://' + htmlFile); await sleep(500);
  // web.html may have loaded the developer's private env.js (the debug password), which adds a DEBUG button. Every test
  // starts WITHOUT it, so the results never depend on a private file that only exists on one computer. The debug tests switch it on themselves.
  await page.evaluate(`window.DEBUG_PASSWORD=undefined; showMenu();`);
  return page;
}
const rect = (page, id) => page.evaluate(id => { const e = document.getElementById(id), c = getComputedStyle(e), r = e.getBoundingClientRect(); return { display: c.display, vis: c.visibility, x: r.left, y: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + r.height / 2 }; }, id);
// Waits until a condition becomes true in the page (polling), but never longer than `ms`. It does NOT make a check pass:
// the check that follows still looks at the real state.
const waitUntil = async (page, expression, ms = 8000) => { try { await page.waitForFunction(expression, { timeout: ms, polling: 100 }); } catch (e) { /* timed out: the check after it will fail */ } };
const g = (page, expr) => page.evaluate(expr);
const overlap = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
async function startGame(page, w, h) {
  const b = await page.evaluateHandle(() => [...document.querySelectorAll('button')].find(b => /new game/i.test(b.textContent)));
  const box = await b.boundingBox(); await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  for (let i = 0; i < 40; i++) { if (await g(page, 'STATE') === 'playing') break; await page.touchscreen.tap(w / 2, h / 2); await sleep(150); }
  await sleep(400);
}

(async () => {
  const { executablePath, args } = await executable();
  const browser = await require_('puppeteer-core').launch({ executablePath, args, headless: 'shell' });

  // ================= phone, landscape, several sizes: layout =================
  for (const [w, h, name] of [[844, 390, 'Pixel/iPhone 14 landscape'], [667, 375, 'small phone (iPhone SE) landscape'], [932, 430, 'big phone landscape'], [1024, 768, 'tablet landscape']]) {
    const page = await open(browser, w, h);
    const menuUi = await rect(page, 'touchui');
    T(`${name}: the page knows it is a touch device`, await g(page, `document.documentElement.classList.contains('touch')`));
    T(`${name}: no controls in the menu (nothing to control yet)`, menuUi.vis === 'hidden');
    T(`${name}: side panels are hidden`, await g(page, `getComputedStyle(document.querySelector('.sidebar')).display`) === 'none');
    const nb = await page.evaluateHandle(() => [...document.querySelectorAll('button')].find(b => /new game/i.test(b.textContent)));
    const nbox = await nb.boundingBox();
    T(`${name}: the New Game button is big enough to tap (>= 36px high)`, nbox.height >= 36, Math.round(nbox.height));
    await startGame(page, w, h);
    const R = {}; for (const id of ['mcStick', 'mcJ', 'mcZ', 'mcT', 'mcD', 'mcP', 'fsbtn']) R[id] = await rect(page, id);
    T(`${name}: all controls are visible while playing`, ['mcStick', 'mcJ', 'mcZ', 'mcT', 'mcD', 'mcP'].every(id => R[id].display !== 'none' && R[id].vis === 'visible' && R[id].w > 30), JSON.stringify(Object.fromEntries(Object.entries(R).map(([k, v]) => [k, v.display + '/' + v.vis + '/' + Math.round(v.w)]))));
    T(`${name}: every control lies completely inside the screen`, Object.values(R).every(r => r.x >= 0 && r.y >= 0 && r.x + r.w <= w + 0.5 && r.y + r.h <= h + 0.5), JSON.stringify(R));
    T(`${name}: joystick is at the bottom LEFT`, R.mcStick.cx < w * 0.35 && R.mcStick.cy > h * 0.5);
    T(`${name}: jump is at the bottom RIGHT`, R.mcJ.cx > w * 0.65 && R.mcJ.cy > h * 0.5);
    T(`${name}: punch is ABOVE jump (same column)`, R.mcZ.cy < R.mcJ.cy - R.mcJ.h * 0.6 && Math.abs(R.mcZ.cx - R.mcJ.cx) < 12, `punch ${Math.round(R.mcZ.cx)},${Math.round(R.mcZ.cy)} jump ${Math.round(R.mcJ.cx)},${Math.round(R.mcJ.cy)}`);
    const ids = ['mcStick', 'mcJ', 'mcZ', 'mcT', 'mcD', 'mcP', 'fsbtn']; let clash = [];
    for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) if (overlap(R[ids[i]], R[ids[j]])) clash.push(ids[i] + '/' + ids[j]);
    T(`${name}: no two controls overlap`, clash.length === 0, clash.join(' '));
    T(`${name}: the rotate message is not shown in landscape`, (await rect(page, 'rotate')).display === 'none');
    // the small buttons must not cover the ground where enemies walk (bottom 22% of the game picture)
    const cv = await page.evaluate(() => { const r = document.getElementById('c').getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
    const groundBand = { x: cv.x, y: cv.y + cv.h * 0.80, w: cv.w, h: cv.h * 0.20 };
    T(`${name}: the small buttons (switch / dash) do not cover the ground strip of the game`, !overlap(R.mcT, groundBand) && !overlap(R.mcD, groundBand));
    if (shots) await page.screenshot({ path: path.join(shots, `play_${w}x${h}.png`) });
    T(`${name}: no JavaScript error`, page.errors.length === 0, page.errors.join('|'));
    await page.close();
  }

  // ================= phone: real touches =================
  {
    const W = 844, H = 390; const page = await open(browser, W, H); await startGame(page, W, H);
    const st = await rect(page, 'mcStick'), jp = await rect(page, 'mcJ'), pu = await rect(page, 'mcZ'), pa = await rect(page, 'mcP');
    const x0 = await g(page, 'mario.rect.x');
    const f1 = await page.touchscreen.touchStart(st.cx, st.cy); await f1.move(st.cx + st.w * 0.4, st.cy);
    await waitUntil(page, `mario.rect.x > ${x0 + 40}`);          // wait for the walk (a slow machine may draw no frame for a while), do not guess a delay
    const x1 = await g(page, 'mario.rect.x');
    T('touch: dragging the joystick right walks Mario right', x1 > x0 + 40, `${Math.round(x0)} -> ${Math.round(x1)}`);
    T('touch: the joystick knob follows the finger', (await g(page, `document.getElementById('stickKnob').style.transform`)).includes('translate('));
    await f1.move(st.cx - st.w * 0.4, st.cy);
    await waitUntil(page, `mario.rect.x < ${x1 - 40}`);
    const x2 = await g(page, 'mario.rect.x'); T('touch: dragging it left walks Mario left', x2 < x1 - 40, `${Math.round(x1)} -> ${Math.round(x2)}`);
    await f1.end(); await sleep(250); const x3 = await g(page, 'mario.rect.x'); await sleep(300);
    T('touch: letting go stops Mario', Math.abs((await g(page, 'mario.rect.x')) - x3) < 2);
    T('touch: ...and the knob goes back to the middle', (await g(page, `document.getElementById('stickKnob').style.transform`)).includes('(0px, 0px)'));
    // jump
    const y0 = await g(page, 'mario.rect.y'); await page.touchscreen.tap(jp.cx, jp.cy); await sleep(120);
    T('touch: tapping the jump button makes Mario jump', (await g(page, 'mario.rect.y')) < y0 - 10, `${y0} -> ${await g(page, 'mario.rect.y')}`);
    await sleep(900);
    // punch
    await page.touchscreen.tap(pu.cx, pu.cy); await sleep(60);
    T('touch: tapping the punch button punches', await g(page, 'mario.punching===true||mario.punchT>0'));
    await sleep(500);
    // two fingers: hold the stick right AND press jump
    const xa = await g(page, 'mario.rect.x'); const a = await page.touchscreen.touchStart(st.cx, st.cy); await a.move(st.cx + st.w * 0.4, st.cy);
    const b = await page.touchscreen.touchStart(jp.cx, jp.cy); await sleep(150);
    T('touch: two fingers at once: walking AND jumping together', (await g(page, 'mario.rect.y')) < 500 && (await g(page, 'mario.rect.x')) > xa + 10, `y=${await g(page, 'mario.rect.y')} x=${Math.round(await g(page, 'mario.rect.x'))}`);
    await b.end(); await a.end(); await sleep(900);
    // pause
    await page.touchscreen.tap(pa.cx, pa.cy); await sleep(250);
    T('touch: the pause button pauses', await g(page, 'STATE') === 'paused');
    const pb = await rect(page, 'pausebox'); T('touch: RESUME / SAVE & QUIT buttons appear', pb.display === 'flex');
    const rb = await page.evaluate(() => { const r = document.getElementById('btnResume').getBoundingClientRect(); return { cx: r.left + r.width / 2, cy: r.top + r.height / 2, h: r.height }; });
    T('touch: ...and are big enough to tap', rb.h >= 30, Math.round(rb.h));
    const xp = await g(page, 'mario.rect.x'), yp = await g(page, 'mario.rect.y'); const lp = await page.touchscreen.touchStart(st.cx, st.cy); await lp.move(st.cx + st.w * 0.4, st.cy); await page.touchscreen.tap(jp.cx, jp.cy); await page.touchscreen.tap(pu.cx, pu.cy); await sleep(400);
    T('touch: while paused the joystick, jump and punch do nothing', (await g(page, 'mario.rect.x')) === xp && (await g(page, 'mario.rect.y')) === yp && !(await g(page, 'mario.punching')), `x ${xp}->${await g(page, 'mario.rect.x')}`);
    await lp.end();
    await page.touchscreen.tap(rb.cx, rb.cy); await sleep(250);
    T('touch: RESUME continues the game', await g(page, 'STATE') === 'playing');
    await page.touchscreen.tap(pa.cx, pa.cy); await sleep(200);
    const sb = await page.evaluate(() => { const r = document.getElementById('btnSaveQuit').getBoundingClientRect(); return { cx: r.left + r.width / 2, cy: r.top + r.height / 2 }; });
    await page.touchscreen.tap(sb.cx, sb.cy); await sleep(400);
    T('touch: SAVE & QUIT saves the game', await g(page, `!!localStorage.getItem(SAVE_KEY)&&hs()`));
    T('touch: no JavaScript error during all this', page.errors.length === 0, page.errors.join('|'));
    await page.close();
  }

  // ================= phone held upright =================
  {
    const page = await open(browser, 844, 390); await startGame(page, 844, 390);
    await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    // The browser delivers the orientation change at its next drawn frame. On a slow (software rendered) machine that can
    // take more than a fixed 600 ms, so WAIT for the result (up to 8 s) instead of guessing a delay. If it never comes, the check still fails.
    await waitUntil(page, "STATE==='paused'");
    T('portrait: the "rotate your phone" message covers the screen', (await rect(page, 'rotate')).display === 'flex');
    T('portrait: the game was paused automatically', await g(page, 'STATE') === 'paused', await g(page, 'STATE'));
    if (shots) await page.screenshot({ path: path.join(shots, 'portrait.png') });
    await page.setViewport({ width: 844, height: 390, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
    await waitUntil(page, "getComputedStyle(document.getElementById('rotate')).display==='none'");
    T('portrait -> landscape: the message goes away', (await rect(page, 'rotate')).display === 'none');
    T('portrait -> landscape: the game is still paused (nothing was lost)', await g(page, 'STATE') === 'paused');
    await page.close();
  }

  // ================= desktop (mouse + keyboard) must stay as it was =================
  {
    const page = await open(browser, 1280, 720, { touch: false });
    T('desktop: not treated as a touch device', !(await g(page, `document.documentElement.classList.contains('touch')`)));
    T('desktop: no on-screen controls', (await rect(page, 'touchui')).display === 'none');
    T('desktop: side panels are visible', (await g(page, `getComputedStyle(document.querySelector('.sidebar')).display`)) !== 'none');
    T('desktop: the rotate message never shows', (await rect(page, 'rotate')).display === 'none');
    if (shots) await page.screenshot({ path: path.join(shots, 'desktop.png') });
    T('desktop: no JavaScript error', page.errors.length === 0, page.errors.join('|'));
    await page.close();
  }
  // ================= desktop keyboard with REAL browser key events (including the browser's auto-repeat) =================
  {
    const page = await open(browser, 1280, 720, { touch: false });
    const press = async (k) => { await page.keyboard.press(k); };
    await page.evaluate(`localStorage.removeItem(SAVE_KEY); showMenu();`);
    T('keyboard menu: without a save only NEW GAME is offered, and it is highlighted', await g(page, `menuOpts().join()`) === 'new' && await g(page, `document.getElementById('btnNew').classList.contains('sel')`));
    await press('Enter'); await waitUntil(page, `STATE==='playing'`);
    T('keyboard menu: ENTER starts a New Game when there is no save', await g(page, `STATE==='playing'&&curLv===1`));
    // the game runs at real speed even though this machine draws only a few frames per second
    await sleep(500);
    // Five one-second windows; the MEDIAN is used, so one long stall of the renderer (this machine draws in software) cannot
    // decide the result, while the old bug (one logic step per drawn frame: ~15 per second here) is still clearly caught.
    const rates = await page.evaluate(() => new Promise(res => { const out = []; let f0 = mario.fc, t0 = performance.now(); const id = setInterval(() => { const now = performance.now(); out.push((mario.fc - f0) / (now - t0) * 1000); f0 = mario.fc; t0 = now; if (out.length === 5) { clearInterval(id); res(out); } }, 1000); }));
    const fps = await page.evaluate(() => new Promise(res => { let n = 0; const t0 = performance.now(); (function f() { n++; if (performance.now() - t0 < 1500) requestAnimationFrame(f); else res(n / (performance.now() - t0) * 1000); })(); }));
    const rate = [...rates].sort((a, b) => a - b)[2];
    T(`game speed: the game logic runs at ~60 steps per real second (median ${rate.toFixed(1)}; windows ${rates.map(r => r.toFixed(0)).join(', ')}), although only ${fps.toFixed(1)} frames per second are drawn here`, rate > 52 && rate < 68, rates.map(r => r.toFixed(1)).join(' '));
    // a held Space (the browser repeats keydown) must not double jump
    await page.evaluate(`mario.jl=2;mario.onGround=true;`);
    await page.keyboard.down('Space');
    const jlAfterFirst = await g(page, `mario.jl`);
    for (let i = 0; i < 6; i++) await page.keyboard.down('Space');          // puppeteer sends these with repeat=true
    T('keyboard: the first Space press jumps', jlAfterFirst === 1, jlAfterFirst);
    T('keyboard: holding Space (auto-repeat) does NOT double jump', await g(page, `mario.jl`) === 1, await g(page, `mario.jl`));
    await page.keyboard.up('Space');
    await sleep(1200);
    // a held arrow key must not dash
    await page.evaluate(`mario.dashCd=0;mario.dashing=false;mario.lRt=mario.lLt=-99;`);
    await page.keyboard.down('ArrowRight');
    for (let i = 0; i < 8; i++) { await page.keyboard.down('ArrowRight'); await sleep(40); }
    T('keyboard: holding the right arrow does NOT dash', await g(page, `mario.dashing`) === false);
    T('keyboard: ...but Mario does walk while it is held', await g(page, `mario.vx>0`));
    await page.keyboard.up('ArrowRight');
    // T switches once per press
    await page.evaluate(`loadLv(25);STATE='playing';mario.activeChar='mario';`);
    await page.keyboard.down('KeyT'); for (let i = 0; i < 5; i++) await page.keyboard.down('KeyT'); await page.keyboard.up('KeyT');
    T('keyboard: holding T switches the hero only once', await g(page, `mario.activeChar`) === 'luigi', await g(page, `mario.activeChar`));
    for (const want of ['princess', 'yoshi', 'mario']) { await press('KeyT'); T(`keyboard: pressing T again selects ${want}`, await g(page, `mario.activeChar`) === want, await g(page, `mario.activeChar`)); }
    // pause / resume with Escape, held Escape does not flicker
    await page.keyboard.down('Escape'); await page.keyboard.down('Escape'); await page.keyboard.down('Escape'); await page.keyboard.up('Escape');
    T('keyboard: Escape pauses (and a held Escape does not resume)', await g(page, `STATE`) === 'paused', await g(page, `STATE`));
    const frozen = await g(page, `mario.fc`); await sleep(500);
    T('pause: nothing moves while paused', await g(page, `mario.fc`) === frozen);
    await press('Escape'); T('keyboard: a new Escape press resumes', await g(page, `STATE`) === 'playing');
    // menu with a save: Up / Down choose, Space confirms
    await page.evaluate(`sg(7,2,null,7,null,0);STATE='menu';showMenu();`);
    T('keyboard menu: with a save both options exist and CONTINUE is selected', await g(page, `menuOpts().join()`) === 'new,cont' && await g(page, `document.getElementById('btnCont').classList.contains('sel')`));
    await press('ArrowUp'); T('keyboard menu: Up highlights NEW GAME', await g(page, `document.getElementById('btnNew').classList.contains('sel')&&!document.getElementById('btnCont').classList.contains('sel')`));
    await press('ArrowDown'); T('keyboard menu: Down highlights CONTINUE', await g(page, `document.getElementById('btnCont').classList.contains('sel')`));
    await press('Space'); await waitUntil(page, `STATE==='playing'`);
    T('keyboard menu: SPACE confirms CONTINUE (level 7, 2 lives)', await g(page, `curLv===7&&mario.lives===2`));
    // saving that fails must not say SAVED
    await page.evaluate(`window.__real=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new Error('QuotaExceededError');};`);
    await press('Escape'); await press('KeyQ');
    T('save error: when the browser refuses to store, Q does NOT show SAVED and the game stays paused', await g(page, `STATE==='paused'&&/FAILED/.test(pauseMsg)`), await g(page, `STATE+' / '+pauseMsg`));
    await page.evaluate(`Storage.prototype.setItem=window.__real;`);
    await press('KeyQ'); T('save error: after the problem is gone, Q saves and goes back to the menu', await g(page, `STATE==='falling_text'&&faNext==='menu'&&!!lg()`));
    if (shots) await page.screenshot({ path: path.join(shots, 'desktop-keyboard.png') });
    T('keyboard run: no JavaScript error', page.errors.length === 0, page.errors.join('|'));
    await page.close();
  }
  // ================= DEBUG MODE in the real browser (real clicks and real typing) =================
  {
    const page = await open(browser, 1280, 720, { touch: false });
    // (the password normally comes from env.js, made from .env; here it is set directly so the test does not need that private file)
    await page.evaluate(`window.DEBUG_PASSWORD='8830'; sg(7,2,null,9,null,0); showMenu();`);
    const saved = await g(page, `localStorage.getItem(SAVE_KEY)`);
    const vis = (id) => g(page, `getComputedStyle(document.getElementById('${id}')).display`);
    T('debug (browser): the DEBUG button is visible in the menu', await vis('btnDebug') !== 'none');
    await page.click('#btnDebug'); await waitUntil(page, `STATE==='debug_pw'`);
    T('debug (browser): clicking DEBUG shows the password box', await g(page, `STATE`) === 'debug_pw' && await vis('dbg') !== 'none');
    T('debug (browser): the password box hides what is typed', await g(page, `document.getElementById('dbgPw').type`) === 'password');
    await page.type('#dbgPw', '1234'); await page.keyboard.press('Enter');
    T('debug (browser): a wrong password is refused with a message', await g(page, `STATE`) === 'debug_pw' && /WRONG/.test(await g(page, `document.getElementById('dbgPwMsg').textContent`)));
    T('debug (browser): ...and the box is emptied', await g(page, `document.getElementById('dbgPw').value`) === '');
    await page.type('#dbgPw', '8830'); await page.keyboard.press('Enter'); await waitUntil(page, `STATE==='debug_pick'`);
    T('debug (browser): the right password opens the level picker with 50 levels', await g(page, `STATE`) === 'debug_pick' && await g(page, `document.querySelectorAll('#dbgGrid .dbgc').length`) === 50);
    if (shots) await page.screenshot({ path: path.join(shots, 'debug-picker.png') });
    await page.click('#dbgGrid [data-lv="23"]'); await waitUntil(page, `STATE==='playing'`);
    T('debug (browser): clicking level 23 starts level 23 in debug mode', await g(page, `curLv===23&&debugActive&&companions.length===3`));
    T('debug (browser): the LEAVE button is visible while playing', await vis('dbgLeave') !== 'none');
    await sleep(400);
    await page.click('#dbgLeave'); await waitUntil(page, `STATE==='debug_pick'`);
    T('debug (browser): LEAVE goes back to the picker, level 23 still selected', await g(page, `STATE==='debug_pick'&&dbgPick===23&&debugActive`));
    await page.keyboard.type('41'); await page.keyboard.press('Enter'); await waitUntil(page, `STATE==='playing'`);
    T('debug (browser): typing 41 and ENTER starts level 41', await g(page, `curLv===41`));
    await page.keyboard.press('KeyL'); await waitUntil(page, `STATE==='debug_pick'`);
    T('debug (browser): the L key leaves too', await g(page, `STATE`) === 'debug_pick');
    T('debug (browser): the real save was never touched', await g(page, `localStorage.getItem(SAVE_KEY)`) === saved);
    await page.keyboard.press('Escape'); await waitUntil(page, `STATE==='menu'`);
    T('debug (browser): ESC leaves debug mode back to the main menu', await g(page, `STATE==='menu'&&!debugActive`) && await vis('dbg') === 'none');
    await page.evaluate(`window.DEBUG_PASSWORD=undefined; showMenu();`);
    T('debug (browser): without a password the DEBUG button disappears', await vis('btnDebug') === 'none');
    T('debug (browser): no JavaScript error', page.errors.length === 0, page.errors.join('|'));
    await page.close();
  }
  await browser.close();
  const fails = results.filter(r => !r[1]);
  console.log(`\n${results.length - fails.length}/${results.length} checks passed`); fails.forEach(f => console.log('  FAILED: ' + f[0]));
  console.log('RESULT: ' + (fails.length ? 'FAIL' : 'PASS')); process.exit(fails.length ? 1 : 0);
})().catch(e => { console.log('CRASH: ' + String(e && e.stack || e).split('\n').slice(0, 6).join(' | ')); process.exit(2); });
