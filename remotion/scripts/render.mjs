import {existsSync, readFileSync, realpathSync, renameSync} from 'node:fs';
import {dirname, extname, relative, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const workspaceRoot = resolve(projectRoot, '..');
const videoRoot = resolve(workspaceRoot, 'data', 'lectures', 't050-video');

const contained = (root, target) => {
  const result = relative(root, target);
  return result !== '..' && !result.startsWith(`..${sep}`) && !result.includes(`${sep}..${sep}`);
};
const exact = (value, keys, name) => {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join('|') !== [...keys].sort().join('|')) {
    throw new Error(`Invalid ${name}.`);
  }
};
const boundedText = (value, maximum, name, allowEmpty = false) => {
  if (typeof value !== 'string' || value.length > maximum || (!allowEmpty && value.trim().length === 0)) throw new Error(`Invalid ${name}.`);
};
const integer = (value, minimum, maximum, name) => {
  if (!Number.isInteger(value) || value < minimum || value > maximum) throw new Error(`Invalid ${name}.`);
};

if (process.argv.length !== 4) throw new Error('The trusted renderer accepts only a manifest and output path.');
const manifestPath = resolve(process.argv[2]);
const outputPath = resolve(process.argv[3]);
if (!contained(videoRoot, manifestPath) || !contained(videoRoot, outputPath) || extname(outputPath) !== '.mp4' || !manifestPath.endsWith(`${sep}manifest.json`)) {
  throw new Error('Render paths are outside the trusted local boundary.');
}
if (!existsSync(manifestPath) || existsSync(outputPath) || existsSync(`${outputPath}.part`)) throw new Error('Immutable render path is unavailable.');
if (!contained(videoRoot, realpathSync(manifestPath))) throw new Error('Manifest resolved outside the trusted boundary.');
const raw = readFileSync(manifestPath);
if (raw.length > 65536) throw new Error('Manifest exceeds the safe limit.');
const manifest = JSON.parse(raw.toString('utf8'));
exact(manifest, ['schemaVersion','compositionId','fps','width','height','renderReference','publicDir','slides','branding','captions','transitionMs','holdAfterMs'], 'manifest');
if (manifest.schemaVersion !== 1 || manifest.compositionId !== 'LectureAssembly' || manifest.fps !== 30 || manifest.width !== 1920 || manifest.height !== 1080) throw new Error('Unsupported composition parameters.');
boundedText(manifest.renderReference, 128, 'render reference');
integer(manifest.transitionMs, 0, 1000, 'transition timing');
integer(manifest.holdAfterMs, 0, 5000, 'hold timing');
exact(manifest.branding, ['accentColor','institutionName'], 'branding');
if (!/^#[0-9A-F]{6}$/u.test(manifest.branding.accentColor)) throw new Error('Invalid accent color.');
boundedText(manifest.branding.institutionName, 120, 'institution name');
exact(manifest.captions, ['position','fontScale'], 'captions');
if (!['top','bottom'].includes(manifest.captions.position)) throw new Error('Invalid caption position.');
integer(manifest.captions.fontScale, 80, 130, 'caption scale');
if (!Array.isArray(manifest.slides) || manifest.slides.length < 1 || manifest.slides.length > 100) throw new Error('Invalid slides.');
const publicDir = resolve(manifest.publicDir);
if (publicDir !== resolve(dirname(manifestPath), 'public') || !contained(videoRoot, publicDir)) throw new Error('Invalid public media boundary.');
for (const [index, slide] of manifest.slides.entries()) {
  exact(slide, ['position','title','claims','caption','audioSrc','durationMs','cuts'], 'slide');
  integer(slide.position, 1, 100, 'slide position');
  if (slide.position !== index + 1) throw new Error('Slides must be ordered.');
  boundedText(slide.title, 200, 'slide title');
  boundedText(slide.caption, 10000, 'caption', true);
  if (!Array.isArray(slide.claims) || slide.claims.length > 120) throw new Error('Invalid slide claims.');
  for (const claim of slide.claims) boundedText(claim, 5000, 'slide claim');
  if (!/^audio\/slide-[1-9][0-9]*\.(?:wav|webm|ogg|opus|m4a|mp4)$/u.test(slide.audioSrc)) throw new Error('Invalid audio reference.');
  const audioPath = resolve(publicDir, slide.audioSrc);
  if (!contained(publicDir, audioPath) || !existsSync(audioPath)) throw new Error('Audio is unavailable.');
  integer(slide.durationMs, 1, 1200000, 'slide duration');
  if (!Array.isArray(slide.cuts) || slide.cuts.length > 10) throw new Error('Invalid spoken-content edits.');
  let cursor = 0;
  for (const cut of slide.cuts) {
    exact(cut, ['startMs','endMs','transcriptExcerpt','evidenceSha256'], 'spoken-content evidence');
    integer(cut.startMs, 0, slide.durationMs - 1, 'cut start');
    integer(cut.endMs, cut.startMs + 1, slide.durationMs, 'cut end');
    if (cut.startMs < cursor || !/^[0-9a-f]{64}$/u.test(cut.evidenceSha256)) throw new Error('Invalid spoken-content evidence.');
    boundedText(cut.transcriptExcerpt, 500, 'transcript evidence');
    cursor = cut.endMs;
  }
}

const serveUrl = await bundle({entryPoint: resolve(projectRoot, 'src', 'index.ts'), publicDir});
const composition = await selectComposition({serveUrl, id: 'LectureAssembly', inputProps: manifest});
await renderMedia({
  composition,
  serveUrl,
  codec: 'h264',
  outputLocation: `${outputPath}.part`,
  inputProps: manifest,
  concurrency: 1,
  overwrite: false,
});
if (existsSync(outputPath)) throw new Error('Immutable output was created concurrently.');
renameSync(`${outputPath}.part`, outputPath);
