import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { existsSync, mkdirSync, openSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const mode = process.argv[2] === 'start' ? 'start' : 'dev';
const windows = process.platform === 'win32';
const candidates = windows ? ['.local/consola-web/Scripts/python.exe', '.venv/Scripts/python.exe'] : ['.venv/bin/python', '.local/consola-web/bin/python'];
const python = process.env.NBA_PYTHON || candidates.map(p => path.join(root, p)).find(existsSync) || (windows ? 'python' : 'python3');
const require = createRequire(path.join(root, 'web/package.json'));
const next = require.resolve('next/dist/bin/next');
const logs = path.join(root, '.local/consola/logs');
mkdirSync(logs, { recursive: true });
const children = [];
const healthy = async url => { try { return (await fetch(url, { signal: AbortSignal.timeout(1200) })).ok; } catch { return false; } };
function launch(executable, args, name, cwd = root) {
  const out = openSync(path.join(logs, `${name}.log`), 'a');
  const error = openSync(path.join(logs, `${name}.error.log`), 'a');
  const child = spawn(executable, args, { cwd, windowsHide: true, stdio: ['ignore', out, error], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  child.on('error', error => { console.error(`${name}: ${error.message}`); process.exitCode = 1; });
  child.on('exit', code => { if (code && !process.exitCode) { console.error(`${name} terminó con código ${code}. Revisa ${logs}`); process.exitCode = code; } });
  children.push(child);
}
async function wait(url) {
  for (let i = 0; i < 60; i++) { if (await healthy(url)) return; await new Promise(resolve => setTimeout(resolve, 500)); }
  throw new Error(`El servicio no respondió en ${url}. Revisa ${logs}`);
}
function stop() { for (const child of children) if (child.exitCode === null) child.kill(); }
process.on('SIGINT', () => { stop(); process.exit(); });
process.on('SIGTERM', () => { stop(); process.exit(); });
process.on('exit', stop);
try {
  if (!await healthy('http://127.0.0.1:8001/api/health')) { launch(python, ['-B', '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '8001'], 'api'); await wait('http://127.0.0.1:8001/api/health'); }
  if (!await healthy('http://127.0.0.1:3000')) { launch(process.execPath, [next, mode, '--hostname', '127.0.0.1', '--port', '3000'], 'web', path.join(root, 'web')); await wait('http://127.0.0.1:3000'); }
  console.log('Consola NBA: http://localhost:3000');
} catch (error) { console.error(error.message); stop(); process.exitCode = 1; }
