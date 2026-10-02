import {existsSync, mkdirSync, realpathSync} from 'node:fs';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, renderStill, selectComposition} from '@remotion/renderer';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const browserSetupTimeoutMs = 300000;
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

const [mode, ...rest] = process.argv.slice(2);
if (!['still', 'video'].includes(mode)) throw new Error('usage: render_ch12.mjs still <frame> <out.png> | video <out.mp4>');

const browserPromise = openBrowserWithRetries();
const serveUrl = await bundle({entryPoint: resolve(projectRoot, 'src', 'index.ts'), publicDir: resolve(projectRoot, 'public')});
const browser = await browserPromise;
try {
  const composition = await selectComposition({
    serveUrl,
    id: 'Chapter12Waves',
    puppeteerInstance: browser,
    timeoutInMilliseconds: browserSetupTimeoutMs,
  });
  console.log('composition frames:', composition.durationInFrames, `(${(composition.durationInFrames / composition.fps / 60).toFixed(1)} min)`);
  if (mode === 'still') {
    const frame = Number(rest[0]);
    const out = resolve(projectRoot, rest[1]);
    mkdirSync(dirname(out), {recursive: true});
    await renderStill({composition, serveUrl, output: out, frame, puppeteerInstance: browser, timeoutInMilliseconds: browserSetupTimeoutMs});
    console.log('still written:', out);
  } else {
    const out = resolve(projectRoot, rest[0]);
    mkdirSync(dirname(out), {recursive: true});
    if (existsSync(realpathSync(dirname(out)))) {
      await renderMedia({
        composition,
        serveUrl,
        codec: 'h264',
        outputLocation: out,
        concurrency: 4,
        overwrite: true,
        puppeteerInstance: browser,
        timeoutInMilliseconds: browserSetupTimeoutMs,
        onProgress: ({progress}) => {
          if (Math.round(progress * 200) % 10 === 0) process.stdout.write(`\r${(progress * 100).toFixed(1)}%`);
        },
      });
      console.log('\nvideo written:', out);
    }
  }
} finally {
  await browser.close({silent: true}).catch(() => undefined);
}
