import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));

const origin = 'https://q-nexus.vercel.app';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const log = (stage, data) => console.log(JSON.stringify({ stage, at: new Date().toISOString(), ...data }));
const adb = (...args) => execFileSync(resolve(SCRIPT_DIR, '../../.local/android/platform-tools/adb.exe'), args,
    { windowsHide: true, encoding: 'utf8', timeout: 10000, stdio: ['ignore', 'pipe', 'pipe'] }).trim();

async function connect(target) {
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
    let next = 0;
    const pending = new Map();
    socket.addEventListener('message', event => {
        const value = JSON.parse(String(event.data));
        if (!pending.has(value.id)) return;
        const task = pending.get(value.id); pending.delete(value.id); clearTimeout(task.timer);
        if (value.error) task.reject(new Error(value.error.message));
        else task.resolve(value.result);
    });
    const command = (method, params = {}, timeoutMs = 15000) => new Promise((resolve, reject) => {
        const id = ++next;
        const timer = setTimeout(() => { pending.delete(id); reject(new Error('Timeout: ' + method)); }, timeoutMs);
        pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }));
    });
    const evaluate = async expression => {
        const value = await command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
        if (value.exceptionDetails) throw new Error(value.exceptionDetails.text);
        return value.result.value;
    };
    return { command, evaluate, close: () => socket.close() };
}

const stateExpression = `(() => {
    const visible = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    const buttons = [...document.querySelectorAll('button')].filter(visible);
    return { origin: location.origin, path: location.pathname, online: navigator.onLine, ready: document.readyState,
        back: buttons.some(el => el.getAttribute('aria-label') === 'Volver'),
        menu: buttons.some(el => el.getAttribute('aria-label') === 'Abrir menú de navegación'),
        headings: [...document.querySelectorAll('h1,h2')].map(el => el.textContent.trim()).filter(t => /^(Control de Personal|Administración|Panel|SST|Seguridad y Salud|Formatos y paquetes)/i.test(t)).slice(0, 3),
        dialog: Boolean([...document.querySelectorAll('[role="dialog"]')].find(visible)) };
})()`;

async function main() {
    const targets = await (await fetch('http://127.0.0.1:9223/json/list')).json();
    const target = targets.find(value => value.type === 'page' && value.url.startsWith(origin + '/'));
    if (!target) throw new Error('No QNexus phone target');
    const page = await connect(target);
    let original;
    let radios;
    let changed = false;
    try {
        const baseline = await page.evaluate(readFileSync(resolve(SCRIPT_DIR, 'qnx-inspect.js'), 'utf8'));
        if (baseline.outboxCount !== 0) throw new Error('Outbox is not empty; no connectivity change performed');
        const blockers = await page.evaluate(readFileSync(resolve(SCRIPT_DIR, 'qnx-blockers.js'), 'utf8'));
        if (blockers.blockers.length) throw new Error('Open form/dialog; no connectivity change performed');
        original = new URL(baseline.path, origin).href;
        radios = { airplane: adb('shell', 'cmd', 'connectivity', 'airplane-mode'),
            wifi: adb('shell', 'settings', 'get', 'global', 'wifi_on'),
            data: adb('shell', 'settings', 'get', 'global', 'mobile_data') };
        log('baseline', { path: baseline.path, worker: baseline.workerVersion, outboxCount: baseline.outboxCount, radios });
        if (process.argv.includes('--interrupt-preparation')) {
            await page.evaluate(`window.dispatchEvent(new Event('qnexus:prepare-offline')); true`);
            await pause(2500);
            log('background-preparation-started', { browser: await page.evaluate(stateExpression) });
        }
        changed = true;
        adb('shell', 'cmd', 'connectivity', 'airplane-mode', 'enable');
        adb('shell', 'svc', 'wifi', 'disable');
        adb('shell', 'svc', 'data', 'disable');
        await pause(1800);
        log('airplane-enabled', { airplane: adb('shell', 'cmd', 'connectivity', 'airplane-mode'), browser: await page.evaluate(stateExpression) });
        log('open-from-start-url', await page.command('Page.navigate', { url: origin + '/' }));
        await pause(4500);
        const landing = await page.evaluate(stateExpression);
        log('offline-landing', { browser: landing });
        if (landing.origin === origin && landing.back) {
            await page.evaluate(`document.querySelector('button[aria-label="Volver"]').click(); true`);
            await pause(3000);
            log('after-back', { browser: await page.evaluate(stateExpression) });
        }
        const beforeMenu = await page.evaluate(stateExpression);
        if (beforeMenu.origin === origin && beforeMenu.path !== new URL(original).pathname && beforeMenu.menu) {
            await page.evaluate(`document.querySelector('button[aria-label="Abrir menú de navegación"]').click(); true`);
            await pause(300);
            const menuLinks = await page.evaluate(`([...document.querySelectorAll('[role="dialog"] a')].filter(a => a.getClientRects().length && new URL(a.href).origin === location.origin).map(a => ({ href:new URL(a.href).pathname, text:a.textContent.trim() }))).filter(a => a.href === '/m/admin')`);
            log('menu-root-links', { links: menuLinks });
            if (menuLinks.length) {
                await page.evaluate(`([...document.querySelectorAll('[role="dialog"] a')].find(a => new URL(a.href).pathname === '/m/admin')).click(); true`);
                await pause(3000);
                log('after-menu-root', { browser: await page.evaluate(stateExpression) });
            }
        }
    } finally {
        if (changed && radios) {
            const restore = [];
            for (const args of [
                ['shell', 'cmd', 'connectivity', 'airplane-mode', radios.airplane === 'enabled' ? 'enable' : 'disable'],
                ['shell', 'svc', 'wifi', ['1', '2'].includes(radios.wifi) ? 'enable' : 'disable'],
                ['shell', 'svc', 'data', radios.data === '1' ? 'enable' : 'disable'],
            ]) {
                try { adb(...args); restore.push({ action: args.slice(-2).join(' '), ok: true }); }
                catch (error) { restore.push({ action: args.slice(-2).join(' '), ok: false, error: error.message.slice(0, 160) }); }
            }
            log('radios-restored', { actions: restore, airplane: adb('shell', 'cmd', 'connectivity', 'airplane-mode'),
                wifi: adb('shell', 'settings', 'get', 'global', 'wifi_on'), data: adb('shell', 'settings', 'get', 'global', 'mobile_data') });
            await pause(3000);
            if (original) {
                await page.command('Page.navigate', { url: original });
                await pause(1800);
            }
            const check = await page.evaluate(`fetch('/api/ping', {cache:'no-store',signal:AbortSignal.timeout(5000)}).then(r=>({status:r.status})).catch(e=>({error:e.name}))`);
            log('restored-final', { browser: await page.evaluate(stateExpression), reachability: check });
        }
        page.close();
    }
}
main().catch(error => { console.error(JSON.stringify({ error: error.message })); process.exitCode = 1; });
