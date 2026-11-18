// Headless check on the real GPU (Chrome + ANGLE Metal), loading index.html from file://.
//   node tools/shot.mjs shots a="?t=3.3" b="?view=film&t=5"   screenshots of frozen moments
//   node tools/shot.mjs shots fps                              frame rate at 1920x1080 while the film plays
//   node tools/shot.mjs shots play                             mouse, drag, keys, wheel, sound button
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import path from 'path';
const require = createRequire('/Users/joao/flowharbor/node_modules/');
const { chromium } = require('playwright-core');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const [dir, ...jobs] = process.argv.slice(2);
const out = path.resolve(root, dir);
const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=metal', '--enable-gpu', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: +(process.env.W || 1920), height: +(process.env.H || 1080) }, deviceScaleFactor: +(process.env.DPR || 1) });
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('[' + m.type() + ']', m.text().slice(0, 600)); });
page.on('pageerror', e => console.log('[pageerror]', e.message));
const reqs = new Set();
page.on('request', r => { if (!r.url().startsWith('file:')) reqs.add(new URL(r.url()).host); });
const base = 'file://' + root + '/index.html';
const ready = () => page.waitForFunction(() => { const v = document.getElementById('film'); return v.readyState >= 2 && !v.seeking; }, null, { timeout: 20000 }).catch(e => console.log('video not ready', e.message));
const measure = ms => page.evaluate(ms => new Promise(res => { let n = 0, t0 = performance.now(), worst = 0, last = t0, slow = 0; const f = t => { n++; const d = t - last; worst = Math.max(worst, d); if (d > 20) slow++; last = t; if (t - t0 > ms) res({ fps: +(n * 1000 / (t - t0)).toFixed(1), worstMs: +worst.toFixed(1), slowFrames: slow, state: window.__state() }); else requestAnimationFrame(f); }; requestAnimationFrame(f); }), ms);
for (const job of jobs) {
  if (job === 'fps') {
    await page.goto(base); await ready();
    for (let i = 0; i < 4; i++) console.log(JSON.stringify(await measure(5000)));
    const q = await page.evaluate(() => { const v = document.getElementById('film').getVideoPlaybackQuality(); return { total: v.totalVideoFrames, dropped: v.droppedVideoFrames }; });
    console.log('video frames', JSON.stringify(q));
    continue;
  }
  if (job === 'play') {
    await page.goto(base); await ready(); await page.waitForTimeout(900);
    await page.screenshot({ path: `${out}/p0_load.png` });
    await page.mouse.move(400, 300); await page.mouse.move(1100, 700, { steps: 8 }); await page.waitForTimeout(400);
    console.log('after move', JSON.stringify(await page.evaluate(() => ({ awake: document.body.classList.contains('awake'), tf: document.getElementById('film').style.transform }))));
    await page.screenshot({ path: `${out}/p1_mouse.png` });
    await page.mouse.move(600, 500); await page.mouse.down(); await page.mouse.move(1000, 520, { steps: 12 }); await page.waitForTimeout(300);
    await page.screenshot({ path: `${out}/p2_drag.png` }); await page.mouse.up();
    console.log('after drag', JSON.stringify(await page.evaluate(() => window.__state())));
    await page.keyboard.press('Space'); await page.keyboard.press('3'); await page.waitForTimeout(500);
    await page.keyboard.press('ArrowRight'); await page.keyboard.press('ArrowRight'); await page.waitForTimeout(400);
    console.log('after keys', JSON.stringify(await page.evaluate(() => window.__state())));
    await page.mouse.move(1700, 600); await page.mouse.wheel(0, 900); await page.waitForTimeout(700);
    await page.screenshot({ path: `${out}/p3_wheel.png` });
    await page.keyboard.press('c'); await page.waitForTimeout(900); await page.screenshot({ path: `${out}/p4_filmonly.png` }); await page.keyboard.press('c');
    await page.click('#sound'); await page.waitForTimeout(400);
    console.log('sound:', await page.textContent('#sound'), JSON.stringify(await page.evaluate(() => window.__state())));
    continue;
  }
  const i = job.indexOf('='), name = job.slice(0, i), q = job.slice(i + 1);
  await page.goto(base + q); await ready(); await page.waitForTimeout(900);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log(name, JSON.stringify(await page.evaluate(() => window.__state())));
}
console.log('network hosts:', [...reqs].join(', ') || 'none');
await browser.close();
