import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

const workspace = resolve(import.meta.dirname, '..');
const manifest = JSON.parse(readFileSync(resolve(workspace, 'remotion/package.json'), 'utf8'));
const lock = JSON.parse(readFileSync(resolve(workspace, 'remotion/package-lock.json'), 'utf8'));
const entries = Object.entries(lock.packages ?? {});
const expected = {...manifest.dependencies, ...manifest.devDependencies};

const failures = [];
if (lock.lockfileVersion !== 3) failures.push(`unexpected lockfileVersion ${lock.lockfileVersion}`);
for (const [name, version] of Object.entries(expected)) {
  const actual = lock.packages?.[`node_modules/${name}`]?.version;
  if (actual !== version) failures.push(`${name}: expected ${version}, received ${actual ?? 'missing'}`);
}
for (const [key, pkg] of entries) {
  if (pkg.resolved && !pkg.resolved.startsWith('https://registry.npmjs.org/')) {
    failures.push(`${key}: unexpected source ${pkg.resolved}`);
  }
  if (key && pkg.resolved && !pkg.integrity) failures.push(`${key}: missing integrity`);
  if (/^node_modules\/(?:remotion|@remotion\/)/u.test(key) && pkg.version !== '4.0.514') {
    failures.push(`${key}: Remotion version ${pkg.version}`);
  }
}

if (failures.length) {
  console.error(failures.join('\n'));
  process.exit(1);
}

console.log(`Validated ${entries.length} locked packages from registry.npmjs.org; Remotion packages are 4.0.514.`);
