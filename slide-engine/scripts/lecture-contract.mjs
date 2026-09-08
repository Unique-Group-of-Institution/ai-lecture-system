import fs from 'node:fs';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import { root } from './lib.mjs';

const schema = JSON.parse(fs.readFileSync(path.join(root, 'schemas/lecture.schema.json'), 'utf8'));
const ajv = new Ajv2020({ allErrors: true, strict: true });
const validateLecture = ajv.compile(schema);

export function assertCanonicalLecture(data) {
  if (!validateLecture(data)) {
    const details = (validateLecture.errors || []).map(error => {
      const location = error.instancePath || '/';
      return `${location} ${error.message}`;
    });
    throw new Error(`Canonical lecture JSON is invalid:\n${details.join('\n')}`);
  }
  return data;
}

export function loadCanonicalLecture(filePath) {
  const absolute = path.resolve(filePath);
  return assertCanonicalLecture(JSON.parse(fs.readFileSync(absolute, 'utf8')));
}
