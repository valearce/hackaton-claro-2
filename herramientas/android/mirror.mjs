import { spawn } from 'node:child_process';
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { Android, findAdb, projectRoot, readConfig } from './lib/adb.mjs';

try {
    const args = process.argv.slice(2);
    if (args.length && (args.length !== 2 || args[0] !== '--serial')) throw new Error('Uso: node herramientas/android/mirror.mjs [--serial SERIAL]');
    const config = readConfig();
    const adbPath = findAdb(undefined, config);
    const android = new Android(adbPath, args[1] || process.env.ANDROID_SERIAL || config.serial);
    await android.select();
    const executable = config.scrcpyPath
        ? resolve(projectRoot, config.scrcpyPath)
        : join(projectRoot, '.local/android/scrcpy/scrcpy-win64-v5.0.1/scrcpy.exe');
    if (!existsSync(executable)) throw new Error('Prepara scrcpy oficial en .local/android/scrcpy o indica scrcpyPath en la configuración local.');
    const stateFile = join(projectRoot, '.local/android/scrcpy-session.json');
    if (existsSync(stateFile)) {
        const previous = JSON.parse(readFileSync(stateFile, 'utf8'));
        let alive = false;
        try { process.kill(previous.pid, 0); alive = true; } catch {}
        if (alive) throw new Error(`La sesión registrada sigue activa (PID ${previous.pid}). Usa la ventana ${previous.title}.`);
    }
    mkdirSync(join(projectRoot, '.local/android'), { recursive: true });
    const title = 'Celular - Claro Demo';
    const out = openSync(join(projectRoot, '.local/android/scrcpy.stdout.log'), 'a');
    const err = openSync(join(projectRoot, '.local/android/scrcpy.stderr.log'), 'a');
    try {
        const child = spawn(executable, ['--serial', android.serial, '--window-title', title, '--window-height=800', '--no-audio', '--max-size=1600', '--max-fps=30', '--no-terminal-title'], {
            windowsHide: true, detached: true, shell: false, stdio: ['ignore', out, err],
            env: { ...process.env, ADB: adbPath },
        });
        await new Promise((accept, reject) => { child.once('spawn', accept); child.once('error', reject); });
        const state = { pid: child.pid, serial: android.serial, title, executable, startedAt: new Date().toISOString() };
        writeFileSync(stateFile, JSON.stringify(state, null, 2));
        child.unref();
        console.log(JSON.stringify(state, null, 2));
    } finally { closeSync(out); closeSync(err); }
} catch (error) { console.error(error.message); process.exitCode = 1; }
