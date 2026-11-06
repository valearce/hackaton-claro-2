import { findAdb, readConfig, runProcess } from './lib/adb.mjs';

// Acceso ADB directo. Los argumentos son los oficiales de ADB (incluido -s SERIAL).
try {
    const result = await runProcess(findAdb(undefined, readConfig()), process.argv.slice(2));
    if (result) console.log(result);
} catch (error) {
    console.error(error.message);
    process.exitCode = 1;
}
