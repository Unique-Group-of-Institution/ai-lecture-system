import test from 'node:test';
import assert from 'node:assert/strict';
import { loadCanonicalLecture } from '../scripts/lecture-contract.mjs';

test('embedded FINAL-02 fixture validates all seven canonical slide types', () => {
  const lecture = loadCanonicalLecture('content/samples/final-02-all-slide-types.json');
  assert.deepEqual(lecture.slides.map(slide => slide.type), [
    'concept','comparison','process','formula','worked-example','visual','quick-check',
  ]);
});
