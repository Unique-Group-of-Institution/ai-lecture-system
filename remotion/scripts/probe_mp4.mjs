import {getVideoMetadata} from '@remotion/media-utils';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const file = resolve(process.argv[2]);
const meta = await getVideoMetadata({src: pathToFileURL(file).href});
console.log(JSON.stringify({file, ...meta}));
