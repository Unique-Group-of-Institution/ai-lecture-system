import fs from 'node:fs';
import path from 'node:path';

export const root = path.resolve(import.meta.dirname, '..');
export const ensureDir = p => fs.mkdirSync(path.dirname(p), { recursive: true });
export function parseArgs(argv) {
  const out = {};
  for (let i=2;i<argv.length;i++) if (argv[i].startsWith('--')) out[argv[i].slice(2)] = argv[++i];
  return out;
}
