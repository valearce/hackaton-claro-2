import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { boundedInteger } from './lib/adb.mjs';
import { Cdp, selectTarget } from './lib/cdp.mjs';

async function main() {
    const [command = 'help', ...args] = process.argv.slice(2);
    if (['help', '--help', '-h'].includes(command)) {
        console.log(`Chrome Android por CDP (preparar con android.mjs connect)
  node herramientas/android/phone.mjs tabs
  node herramientas/android/phone.mjs inspect --origin https://tu-sitio.example
  node herramientas/android/phone.mjs screenshot --target ID --output .local/android/pantalla.png
  node herramientas/android/phone.mjs evaluate --origin https://tu-sitio.example --script fragmento.js
  node herramientas/android/phone.mjs observe --target ID --seconds 15
Opciones: --port 9223, --origin URL, --target ID, --worker (evaluate)
evaluate ejecuta el JavaScript del archivo con la sesión actual del navegador.`);
        return;
    }
    const allowed = {
        tabs: ['port'], inspect: ['port', 'origin', 'target'],
        screenshot: ['port', 'origin', 'target', 'output'],
        evaluate: ['port', 'origin', 'target', 'worker', 'script'],
        observe: ['port', 'origin', 'target', 'seconds'],
    };
    if (!Object.hasOwn(allowed, command)) throw new Error(`Comando desconocido: ${command}`);
    const options = {};
    for (let index = 0; index < args.length; index++) {
        const key = args[index].slice(2);
        if (!args[index].startsWith('--') || !allowed[command].includes(key) || Object.hasOwn(options, key)) throw new Error(`Opción inválida: ${args[index]}`);
        if (key === 'worker') options.worker = true;
        else {
            const value = args[++index];
            if (!value || value.startsWith('--')) throw new Error(`Falta el valor de --${key}.`);
            options[key] = value;
        }
    }
    const port = boundedInteger(options.port || 9223, '--port', 1024, 65535);
    const response = await fetch(`http://127.0.0.1:${port}/json/list`, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error(`CDP respondió HTTP ${response.status}.`);
    const targets = await response.json();
    if (command === 'tabs') {
        console.log(JSON.stringify(targets.filter(item => ['page', 'service_worker'].includes(item.type)).map(({ id, type, title, url }) => ({ id, type, title, url })), null, 2));
        return;
    }
    const target = selectTarget(targets, options);
    const source = command === 'evaluate' ? readFileSync(options.script, 'utf8') : null;
    const destination = command === 'screenshot' ? resolve(options.output || '.local/android/pantalla.png') : null;
    if (destination && existsSync(destination)) throw new Error('La captura ya existe. Indica otro --output.');
    const seconds = command === 'observe' ? boundedInteger(options.seconds || 15, '--seconds', 1, 60) : null;
    const cdp = await Cdp.connect(target.webSocketDebuggerUrl);
    try {
        let result;
        if (command === 'inspect') result = await cdp.evaluate(`(async () => ({
            path: location.pathname, title: document.title, online: navigator.onLine,
            ready: document.readyState, viewport: { width: innerWidth, height: innerHeight },
            serviceWorker: navigator.serviceWorker?.controller?.scriptURL,
            caches: typeof caches === 'undefined' ? [] : await caches.keys()
        }))()`);
        if (command === 'evaluate') result = await cdp.evaluate(source);
        if (command === 'screenshot') {
            const captured = await cdp.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
            mkdirSync(dirname(destination), { recursive: true });
            writeFileSync(destination, Buffer.from(captured.data, 'base64'), { flag: 'wx' });
            result = { output: destination };
        }
        if (command === 'observe') {
            const observed = new Map();
            cdp.onEvent = ({ method, params }) => {
                if (method === 'Network.requestWillBeSent') {
                    const url = new URL(params.request.url);
                    if (url.origin !== new URL(target.url).origin || observed.size >= 500) return;
                    observed.set(params.requestId, { path: url.pathname, method: params.request.method });
                }
                const row = observed.get(params?.requestId);
                if (row && method === 'Network.responseReceived') { row.status = params.response.status; row.fromWorker = params.response.fromServiceWorker; }
                if (row && method === 'Network.loadingFailed') row.error = params.errorText;
            };
            await cdp.command('Network.enable');
            await sleep(seconds * 1000);
            result = { seconds, requests: [...observed.values()] };
        }
        console.log(JSON.stringify({ target: target.id, result }, null, 2));
    } finally { cdp.close(); }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
