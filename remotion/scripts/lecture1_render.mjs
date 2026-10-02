import {mkdirSync, readFileSync, realpathSync, existsSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const browserSetupTimeoutMs = 300000;
const FPS = 30, GAP = 12, TAIL = 45, TRANSITION = 15;

const scenesData = JSON.parse(readFileSync(resolve(projectRoot, 'lecture1-scenes.json'), 'utf8'));
const audioData = JSON.parse(readFileSync(resolve(projectRoot, 'lecture1-audio.json'), 'utf8'));
const framesOf = (ms) => Math.round((ms * FPS) / 1000);

const laid = [];
let start = 0;
for (const s of scenesData.scenes) {
  const segs = audioData[String(s.id)];
  if (!segs) throw new Error(`audio missing for scene ${s.id}`);
  const frames = segs.reduce((a, e) => a + framesOf(e.durationMs) + GAP, 0) + TAIL;
  const windows = [];
  let t = 0;
  for (const e of segs) {
    const d = framesOf(e.durationMs);
    windows.push({voice: e.voice, start: t, end: t + d});
    t += d + GAP;
  }
  laid.push({s, frames, start, windows});
  start += frames - TRANSITION;
}
const totalFrames = start + TRANSITION;

const byId = (id) => laid.find((l) => l.s.id === id);
const urWindow = (l, i = -1) => {
  const ur = l.windows.filter((w) => w.voice === 'ur');
  const w = i === -1 ? ur[ur.length - 1] : ur[i];
  return Math.round((w.start + w.end) / 2) + 20;
};
const pick = (id, local) => {
  const l = byId(id);
  return [l.start + (typeof local === 'function' ? local(l) : local), `out/stills/l1-${String(id).padStart(2, '0')}.png`];
};

const stills = [
  pick(0, 150),
  pick(17, urWindow),
  pick(1, urWindow),
  pick(18, urWindow),
  pick(2, 400),
  pick(3, urWindow),
  pick(13, urWindow),
  pick(22, urWindow),
  pick(19, (l) => urWindow(l, 1) + 100),
  pick(14, (l) => urWindow(l) + 120),
  pick(20, (l) => urWindow(l, 1) + 40),
  pick(21, urWindow),
  pick(15, urWindow),
  pick(16, 150),
];

const openBrowserWithRetries = async (attempts = 3) => {
  for (let attempt = 1; ; attempt++) {
    try {
      return await openBrowser('chrome');
    } catch (err) {
      if (attempt >= attempts || !String(err?.message ?? '').includes('connect to the browser')) throw err;
      console.error(`Browser connect failed (attempt ${attempt}/${attempts}); retrying warm launch...`);
      await new Promise((r) => setTimeout(r, 5000));
    }
  }
};

const wantVideo = process.argv.includes('--video');
const videoOut = 'out/lecture1-chemistry-720p.mp4';

const browserPromise = openBrowserWithRetries();
const serveUrl = await bundle({entryPoint: resolve(projectRoot, 'src', 'index.ts'), publicDir: resolve(projectRoot, 'public')});
const browser = await browserPromise;
try {
  const composition = await selectComposition({serveUrl, id: 'Lecture1Chemistry', puppeteerInstance: browser, timeoutInMilliseconds: browserSetupTimeoutMs});
  console.log('composition frames:', composition.durationInFrames, '(script total:', totalFrames, ') minutes:', (composition.durationInFrames / FPS / 60).toFixed(2));
  for (const [frame, rel] of stills) {
    const out = resolve(projectRoot, rel);
    mkdirSync(dirname(out), {recursive: true});
    await renderStill({composition, serveUrl, output: out, frame, puppeteerInstance: browser, timeoutInMilliseconds: browserSetupTimeoutMs});
    console.log('still written:', out, 'frame:', frame);
  }
  if (wantVideo) {
    const out = resolve(projectRoot, videoOut);
    if (!existsSync(realpathSync(dirname(out)))) throw new Error('output dir missing');
    let lastTick = 0;
    await renderMedia({
      composition,
      serveUrl,
      codec: 'h264',
      outputLocation: out,
      scale: 2 / 3,
      concurrency: 4,
      overwrite: true,
      puppeteerInstance: browser,
      timeoutInMilliseconds: 900000,
      onProgress: ({progress}) => {
        const now = Date.now();
        if (now - lastTick > 15000) {
          lastTick = now;
          const done = Math.round(progress * composition.durationInFrames);
          console.log(`progress ${(progress * 100).toFixed(1)}% (${done}/${composition.durationInFrames} frames)`);
        }
      },
    });
    console.log('video written:', out);
  }
} catch (err) {
  console.error('render failed:', err && err.stack ? err.stack : err);
  process.exitCode = 1;
} finally {
  await browser.close({silent: true}).catch(() => undefined);
  process.exit(process.exitCode ?? 0);
}
