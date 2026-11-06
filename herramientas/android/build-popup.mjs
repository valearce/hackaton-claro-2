import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { projectRoot, runProcess } from './lib/adb.mjs';

try {
    const jar = join(projectRoot, '.local/android/smali-2.5.2.jar');
    if (!existsSync(jar)) throw new Error('Descarga Smali 2.5.2 desde https://bitbucket.org/JesusFreke/smali/downloads/smali-2.5.2.jar en .local/android/.');
    const hash = createHash('sha256').update(readFileSync(jar)).digest('hex');
    if (hash !== '9544299578b16f771d8aa8eaefe0d3718ca03478c16f3c356f2fcf1366bfb116') throw new Error('El hash de Smali no coincide con la descarga verificada.');
    const output = join(projectRoot, '.local/android/popup/classes.dex');
    mkdirSync(join(projectRoot, '.local/android/popup'), { recursive: true });
    const result = await runProcess('java', ['-jar', jar, 'assemble', '--api', '26', '--output', output, join(projectRoot, 'herramientas/android/popup')], 30000);
    if (result) console.log(result);
    if (!existsSync(output) || readFileSync(output).subarray(0, 4).toString() !== 'dex\n') throw new Error('No se generó un DEX válido.');
    console.log(JSON.stringify({ output, assemblerSHA256: hash }));
} catch (error) { console.error(error.message); process.exitCode = 1; }
