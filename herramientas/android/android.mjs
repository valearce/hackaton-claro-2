import { pathToFileURL } from 'node:url';
import { Android, boundedInteger, findAdb, readConfig, runProcess } from './lib/adb.mjs';

const help = `Herramientas Android (Node.js 22 o superior)

  node herramientas/android/android.mjs devices
  node herramientas/android/android.mjs doctor
  node herramientas/android/android.mjs notify --text "Mensaje de prueba" --popup
  node herramientas/android/android.mjs sms-demo --sender "Claro" --text "DEMO: tienes una oferta para ti" --image recursos/imagenes/claro-logo.jpg
  node herramientas/android/android.mjs banner --title "Una oferta para ti" --text "Contenido de demostración" --image recursos/imagenes/claro-logo.jpg
  node herramientas/android/android.mjs record --seconds 20
  node herramientas/android/android.mjs demo --seconds 20 --delay 3 --text "Tu oferta de prueba" --popup
  node herramientas/android/android.mjs connect --port 9223

Opciones comunes: --serial SERIAL, --adb RUTA
Video: --output RUTA.mp4, --seconds 1..180
Aviso: --title TEXTO, --text TEXTO, --popup (flotante), --show (abre la bandeja)
Imagen opcional: --image RUTA.png (PNG/JPEG, máximo 5 MB, requiere --popup)
Aviso tipo SMS: sms-demo --sender NOMBRE --text TEXTO --image RUTA (demo local)
Banner de demostración: --image RUTA, --title TEXTO, --text TEXTO, --seconds 3..60
La notificación local aparece como Android Shell; no es un SMS en Mensajes.
Los videos no incluyen audio. No se modifica la conectividad del teléfono.
`;

export function parseArguments(argv) {
    const [command = 'help', ...args] = argv;
    if (['help', '--help', '-h'].includes(command)) return { command: 'help', options: {} };
    const specific = {
        devices: [], doctor: [], connect: ['port'],
        notify: ['text', 'title', 'show', 'popup', 'image'], record: ['seconds', 'output'],
        demo: ['seconds', 'output', 'text', 'title', 'delay', 'show', 'popup', 'image'],
        banner: ['text', 'title', 'image', 'seconds'],
        'sms-demo': ['sender', 'text', 'image'],
    };
    if (!Object.hasOwn(specific, command)) throw new Error(`Comando desconocido: ${command}. Usa help.`);
    const allowed = new Set(['adb', 'serial', ...specific[command]]);
    const options = {};
    for (let index = 0; index < args.length; index++) {
        const key = args[index].startsWith('--') ? args[index].slice(2) : '';
        if (!allowed.has(key)) throw new Error(`Opción desconocida para ${command}: ${args[index]}`);
        if (Object.hasOwn(options, key)) throw new Error(`Opción repetida: --${key}`);
        if (['show', 'popup'].includes(key)) options[key] = true;
        else {
            const value = args[++index];
            if (!value || value.startsWith('--')) throw new Error(`Falta el valor de --${key}.`);
            options[key] = value;
        }
    }
    return { command, options };
}

export async function main(argv = process.argv.slice(2)) {
    const { command, options } = parseArguments(argv);
    if (command === 'help') { console.log(help); return; }
    if (['demo', 'notify', 'banner', 'sms-demo'].includes(command) && !options.text?.trim()) throw new Error('Indica --text con el mensaje de prueba.');
    const config = readConfig();
    const adbPath = findAdb(options.adb, config);
    const android = new Android(adbPath, options.serial || process.env.ANDROID_SERIAL || config.serial);
    if (command === 'devices') return console.log(JSON.stringify(await android.devices(), null, 2));
    if (command === 'doctor') {
        console.log(JSON.stringify({ adbPath, version: await runProcess(adbPath, ['version']), rawDevices: await runProcess(adbPath, ['devices', '-l']), devices: await android.devices() }, null, 2));
        return;
    }
    await android.select();
    let result;
    if (command === 'notify') result = await android.notify(options);
    if (command === 'sms-demo') result = await android.smsDemo(options);
    if (command === 'banner') result = await android.banner(options);
    if (command === 'record' || command === 'demo') {
        result = await android.record({ ...options, message: command === 'demo' ? options.text : undefined });
    }
    if (command === 'connect') {
        const port = boundedInteger(options.port || 9223, '--port', 1024, 65535);
        // --no-rebind no reemplaza un túnel que pueda pertenecer a otra sesión.
        await android.device(['forward', '--no-rebind', `tcp:${port}`, 'localabstract:chrome_devtools_remote']);
        result = { serial: android.serial, endpoint: `http://127.0.0.1:${port}`, next: 'node herramientas/android/phone.mjs tabs' };
    }
    console.log(JSON.stringify(result, null, 2));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
    main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
