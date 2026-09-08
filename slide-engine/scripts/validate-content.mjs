import { loadCanonicalLecture } from './lecture-contract.mjs';
import { parseArgs } from './lib.mjs';
const args=parseArgs(process.argv);
if(!args.input) throw new Error('Use --input <lecture.json>');
const lecture=loadCanonicalLecture(args.input);
console.log(`Valid lecture: ${lecture.metadata.subject} lecture ${lecture.metadata.lecture}`);
