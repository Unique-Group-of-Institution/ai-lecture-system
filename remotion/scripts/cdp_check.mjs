// Diagnostic: can chrome-headless-shell serve DevTools over HTTP (CDP)?
import {spawn} from 'node:child_process';
import {existsSync} from 'node:fs';

const CHROME =
  'E:/LMS Project/AI-Lecture-System-Agent-Workspace/remotion/node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe';

if (!existsSync(CHROME)) {
  console.log('chrome binary missing:', CHROME);
  process.exit(1);
}

const port = 9333;
const proc = spawn(
  CHROME,
  [
    `--remote-debugging-port=${port}`,
    '--remote-allow-origins=*',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    'about:blank',
  ],
  {stdio: 'ignore', detached: false},
);
console.log('spawned chrome pid', proc.pid);

proc.on('exit', (code, signal) => console.log('chrome exited early', code, signal));

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let ok = false;
for (let i = 0; i < 20; i++) {
  await sleep(1000);
  try {
    const res = await fetch(`http://127.0.0.1:${port}/json/version`);
    if (res.ok) {
      const body = await res.text();
      console.log('CDP OK after', i + 1, 's:', body.slice(0, 300));
      ok = true;
      break;
    }
    console.log('attempt', i + 1, 'status', res.status);
  } catch (err) {
    console.log('attempt', i + 1, 'error:', err.message);
  }
}

if (!ok) console.log('CDP FAILED to respond within 20s');

try {
  proc.kill();
  console.log('killed chrome');
} catch (err) {
  console.log('kill error:', err.message);
}
process.exit(ok ? 0 : 2);
