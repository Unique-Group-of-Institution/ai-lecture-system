import {existsSync, readFileSync, realpathSync, renameSync} from 'node:fs';
import {dirname, extname, relative, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {openBrowser, renderMedia, selectComposition} from '@remotion/renderer';

// Trusted local renderer for the teacherless (automated) lecture path.
// It is a sibling of render.mjs but bound to the teacherless composition and
// the data/lectures/teacherless storage boundary, so the T050 teacher-
// recording contract stays untouched.

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const workspaceRoot = resolve(projectRoot, '..');
const teacherlessRoot = resolve(workspaceRoot, 'data', 'lectures', 'teacherless');

const contained = (root, target) => {
  const result = relative(root, target);
  return result !== '..' && !result.startsWith(`..${sep}`) && !result.includes(`${sep}..${sep}`);
};
const boundedText = (value, maximum, name, allowEmpty = false) => {
  if (typeof value !== 'string' || value.length > maximum || (!allowEmpty && value.trim().length === 0)) throw new Error(`Invalid ${name}.`);
};
const integer = (value, minimum, maximum, name) => {
  if (!Number.isInteger(value) || value < minimum || value > maximum) throw new Error(`Invalid ${name}.`);
};
const assetFile = (value, pattern, name) => {
  if (typeof value !== 'string' || !pattern.test(value) || value.includes('..') || value.startsWith('/') || value.includes('\\')) {
    throw new Error(`Invalid ${name}.`);
  }
  const target = resolve(publicDir, value);
  if (!contained(publicDir, target) || !existsSync(target)) throw new Error(`${name} is unavailable.`);
  return target;
};

if (process.argv.length !== 4) throw new Error('The trusted renderer accepts only a manifest and output path.');
// chrome-headless-shell processes can outlive browser.close() on this machine; without a
// forced exit the event loop keeps waiting on their handles and the Python caller stalls.
process.on('uncaughtException', (err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
process.on('unhandledRejection', (err) => {
  console.error(err && err.stack ? err.stack : String(err ?? 'Renderer failed.'));
  process.exit(1);
});
const manifestPath = resolve(process.argv[2]);
const outputPath = resolve(process.argv[3]);
if (!contained(teacherlessRoot, manifestPath) || !contained(teacherlessRoot, outputPath) || extname(outputPath) !== '.mp4' || !manifestPath.endsWith(`${sep}manifest.json`)) {
  throw new Error('Render paths are outside the trusted local boundary.');
}
if (!existsSync(manifestPath) || existsSync(outputPath) || existsSync(`${outputPath}.part.mp4`)) throw new Error('Immutable render path is unavailable.');
if (!contained(teacherlessRoot, realpathSync(manifestPath))) throw new Error('Manifest resolved outside the trusted boundary.');
const raw = readFileSync(manifestPath);
if (raw.length > 2 * 1024 * 1024) throw new Error('Manifest exceeds the safe limit.');
const manifest = JSON.parse(raw.toString('utf8'));

if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) throw new Error('Invalid teacherless manifest.');
if (manifest.schemaVersion !== 1 || manifest.compositionId !== 'TeacherlessLecture' || manifest.fps !== 30 || manifest.width !== 1920 || manifest.height !== 1080) {
  throw new Error('Unsupported teacherless composition parameters.');
}
boundedText(manifest.renderReference, 256, 'render reference');
if (!Array.isArray(manifest.scenes) || manifest.scenes.length < 1 || manifest.scenes.length > 120) throw new Error('Invalid teacherless scenes.');
if (!manifest.branding || typeof manifest.branding !== 'object' || !/^#[0-9A-Fa-f]{6}$/u.test(manifest.branding.accentColor)) throw new Error('Invalid teacherless branding.');
let renderScale = 1;
if (manifest.renderScale !== undefined) {
  if (typeof manifest.renderScale !== 'number' || !(manifest.renderScale >= 0.5 && manifest.renderScale <= 1)) throw new Error('Invalid teacherless render scale.');
  renderScale = manifest.renderScale;
}

const publicDir = resolve(manifest.publicDir);
if (publicDir !== resolve(dirname(manifestPath), 'public') || !contained(teacherlessRoot, publicDir)) {
  throw new Error('Invalid public media boundary.');
}

const AUDIO = /^audio\/[A-Za-z0-9][A-Za-z0-9_-]*\.wav$/u;
const BRAND = /^branding\/[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:mp4|png|jpg|jpeg|webm|wav|mp3)$/u;
for (const [index, scene] of manifest.scenes.entries()) {
  if (!scene || typeof scene !== 'object') throw new Error('Invalid teacherless scene.');
  boundedText(scene.id, 64, 'scene id');
  integer(scene.durationMs, 250, 1_800_000, 'scene duration');
  if (scene.narrationAudioSrc !== undefined) {
    assetFile(scene.narrationAudioSrc, AUDIO, 'scene narration audio');
  }
  if (index === 0 && scene.narrationAudioSrc === undefined && !scene.narration) {
    throw new Error('Teacherless scenes must carry narration text or audio.');
  }
}
if (manifest.production) {
  for (const key of ['introSrc', 'outroSrc', 'logoSrc', 'musicSrc']) {
    const src = manifest.production[key];
    if (src !== undefined) assetFile(src, BRAND, `production ${key}`);
  }
}

// This evaluation PC starts chrome-headless-shell slowly (Defender scan) while
// bundling competes for CPU, so the browser is opened before bundling with a
// raised budget and the internal 25s connect timeout is retried (attempt 2 is warm).
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
const browserPromise = openBrowserWithRetries();
let serveUrl;
try {
  serveUrl = await bundle({entryPoint: resolve(projectRoot, 'src', 'teacherlessEntry.ts'), publicDir});
} catch (err) {
  await browserPromise.then((b) => b.close({silent: true})).catch(() => undefined);
  throw err;
}
const browser = await browserPromise;
try {
  const composition = await selectComposition({
    serveUrl,
    id: 'TeacherlessLecture',
    inputProps: manifest,
    puppeteerInstance: browser,
    timeoutInMilliseconds: browserSetupTimeoutMs,
  });
  await renderMedia({
    composition,
    serveUrl,
    codec: 'h264',
    outputLocation: `${outputPath}.part.mp4`,
    inputProps: manifest,
    concurrency: 1,
    scale: renderScale,
    overwrite: false,
    puppeteerInstance: browser,
    timeoutInMilliseconds: browserSetupTimeoutMs,
  });
} finally {
  await browser.close({silent: true}).catch(() => undefined);
}
if (existsSync(outputPath)) throw new Error('Immutable output was created concurrently.');
renameSync(`${outputPath}.part.mp4`, outputPath);
process.exit(0);
