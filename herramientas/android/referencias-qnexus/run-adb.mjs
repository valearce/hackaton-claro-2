import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
try {
    const result = execFileSync(resolve(SCRIPT_DIR, '../../.local/android/platform-tools/adb.exe'), process.argv.slice(2), {
        windowsHide: true, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 20000,
    });
    process.stdout.write(result);
} catch (error) {
    if (error.stdout) process.stdout.write(error.stdout);
    if (error.stderr) process.stderr.write(error.stderr);
    process.exitCode = typeof error.status === 'number' ? error.status : 1;
}
