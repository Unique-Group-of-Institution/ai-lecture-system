import fs from 'node:fs';

const path = new URL('../fixtures/teacherless-smoke-props.json', import.meta.url);
const props = JSON.parse(fs.readFileSync(path, 'utf8'));
const fail = (message) => { throw new Error(message); };

if (props.schemaVersion !== 1) fail('Unsupported schema version.');
if (props.fps !== 30 || props.width !== 1920 || props.height !== 1080) fail('Invalid render dimensions.');
if (!Array.isArray(props.scenes) || props.scenes.length === 0) fail('No scenes supplied.');

const ids = new Set();
for (const scene of props.scenes) {
  if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(scene.id) || ids.has(scene.id)) fail('Invalid or duplicate scene id.');
  ids.add(scene.id);
  if (!Number.isInteger(scene.durationMs) || scene.durationMs < 250) fail('Invalid scene duration.');
  if (!Array.isArray(scene.elements) || !Array.isArray(scene.animations)) fail('Invalid scene arrays.');
  const elementIds = new Set();
  for (const element of scene.elements) {
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(element.id) || elementIds.has(element.id)) fail('Invalid or duplicate element id.');
    elementIds.add(element.id);
  }
  for (const animation of scene.animations) {
    if (!['fadeIn', 'draw', 'highlight', 'stepReveal'].includes(animation.type)) fail('Unsupported animation.');
    if (animation.type === 'highlight' && !elementIds.has(animation.target)) fail('Highlight target does not exist.');
    if (animation.type === 'stepReveal' && (!Number.isInteger(animation.stepCount) || animation.stepCount < 1 || animation.stepCount > 20)) fail('Invalid stepReveal.');
  }
}

const totalFrames = props.scenes.reduce((sum, scene) => sum + Math.max(1, Math.round(scene.durationMs * props.fps / 1000)), 0);
if (totalFrames < 1) fail('Calculated duration is invalid.');
console.log('TEACHERLESS FIXTURE CHECK PASSED');
console.log(JSON.stringify({scenes: props.scenes.length, totalFrames}));
