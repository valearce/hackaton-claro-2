import { readFileSync, writeFileSync } from 'node:fs';

async function main() {
    const targets = await (await fetch('http://127.0.0.1:9223/json/list')).json();
    const wantedType = process.argv[2] === '--worker' ? 'service_worker' : 'page';
    const target = targets.find(value => value.type === wantedType && /^https:\/\/q-nexus\.vercel\.app(?:\/|$)/.test(value.url));
    if (!target) throw new Error('QNexus has no inspectable page on the connected phone');
    const socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
    let sequence = 0;
    const pending = new Map();
    const observed = new Map();
    socket.addEventListener('message', event => {
        const message = JSON.parse(String(event.data));
        if (message.id && pending.has(message.id)) {
            const { resolve, reject, timer } = pending.get(message.id);
            clearTimeout(timer); pending.delete(message.id);
            if (message.error) reject(new Error(message.error.message));
            else resolve(message.result);
        }
        if (process.argv[2] === '--observe' && message.method?.startsWith('Network.')) {
            const p = message.params;
            if (message.method === 'Network.requestWillBeSent') {
                const url = new URL(p.request.url);
                if (url.hostname === 'q-nexus.vercel.app' || url.hostname === 'gskjauouokflcdbqgnxu.supabase.co') {
                    const path = url.pathname.startsWith('/m/') ? url.pathname.split('/').slice(0, 4).join('/') : url.pathname;
                    observed.set(p.requestId, { path, method: p.request.method, type: p.type, at: p.timestamp });
                }
            } else if (observed.has(p.requestId)) {
                const record = observed.get(p.requestId);
                if (message.method === 'Network.responseReceived') { record.status = p.response.status; record.fromWorker = p.response.fromServiceWorker; }
                if (message.method === 'Network.loadingFailed') { record.failure = p.errorText; record.cancelled = p.canceled; }
                if (message.method === 'Network.loadingFinished' || message.method === 'Network.loadingFailed') record.durationMs = Math.round((p.timestamp - record.at) * 1000);
            }
        }
    });
    const command = (method, params = {}) => new Promise((resolve, reject) => {
        const id = ++sequence;
        const timer = setTimeout(() => { pending.delete(id); reject(new Error(`Timeout in ${method}`)); }, 20000);
        pending.set(id, { resolve, reject, timer });
        socket.send(JSON.stringify({ id, method, params }));
    });
    try {
        if (process.argv[2] === '--screenshot') {
            const captured = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
            writeFileSync(process.argv[3], Buffer.from(captured.data, 'base64'));
            console.log(JSON.stringify({ screenshot: process.argv[3] }));
            return;
        }
        if (process.argv[2] === '--observe') {
            await command('Network.enable');
            console.log(JSON.stringify({ observing: target.id, seconds: 30 }));
            await new Promise(resolve => setTimeout(resolve, 30000));
            const rows = [...observed.values()];
            const summary = {};
            for (const row of rows) { const key = String(row.failure ?? row.status ?? 'pending'); summary[key] = (summary[key] ?? 0) + 1; }
            console.log(JSON.stringify({ requests: rows.length, summary,
                auth: rows.filter(row => row.path.startsWith('/api/auth/')),
                failures: rows.filter(row => row.failure || row.status >= 400).slice(0, 15),
                slow: rows.filter(row => row.durationMs > 2000 || !row.status && !row.failure).slice(0, 8) }));
            return;
        }
        const source = readFileSync(process.argv[2] === '--worker' ? process.argv[3] : process.argv[2], 'utf8');
        const result = await command('Runtime.evaluate', { expression: source, awaitPromise: true, returnByValue: true });
        if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
        console.log(JSON.stringify({ target: target.id, result: result.result.value }));
    } finally { socket.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
