import {mkdirSync, realpathSync, existsSync} from 'node:fs';
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

const stills = [];
const videoOut = 'out/branches-sample-720p.mp4';

const browserPromise = openBrowserWithRetries();
const serveUrl = await bundle({entryPoint: resolve(projectRoot, 'src', 'index.ts'), publicDir: resolve(projectRoot, 'public')});
const browser = await browserPromise;
try {
  const composition = await selectComposition({serveUrl, id: 'BranchesSample', puppeteerInstance: browser, timeoutInMilliseconds: browserSetupTimeoutMs});
  console.log('composition frames:', composition.durationInFrames);
  for (const [frame, rel] of stills) {
    const out = resolve(projectRoot, rel);
    mkdirSync(dirname(out), {recursive: true});
    await renderStill({composition, serveUrl, output: out, frame, puppeteerInstance: browser, timeoutInMilliseconds: browserSetupTimeoutMs});
    console.log('still written:', out);
  }
  const out = resolve(projectRoot, videoOut);
  if (!existsSync(realpathSync(dirname(out)))) throw new Error('output dir missing');
  try {
    await renderMedia({
      composition,
      serveUrl,
      codec: 'h264',
      outputLocation: out,
      scale: 2 / 3,
      concurrency: 4,
      overwrite: true,
      puppeteerInstance: browser,
      timeoutInMilliseconds: browserSetupTimeoutMs,
      onProgress: ({progress}) => {
        if (Math.round(progress * 200) % 10 === 0) process.stdout.write(`\r${(progress * 100).toFixed(1)}%`);
      },
    });
    console.log('\nvideo written:', out);
  } catch (err) {
    console.error('renderMedia failed:', err && err.stack ? err.stack : err);
    process.exitCode = 1;
  }
} finally {
  await browser.close({silent: true}).catch(() => undefined);
  process.exit(process.exitCode ?? 0);
}
