(async () => {
    const route = value => {
        const u = new URL(value, location.href);
        return u.pathname.startsWith('/m/') ? u.pathname.split('/').slice(0, 4).join('/') : u.pathname;
    };
    const boot = [...document.scripts].map(script => script.textContent ?? '').find(text => text.includes('window.__qnxBoot')) ?? '';
    const clientRelease = boot.match(/var version="([a-zA-Z0-9+._-]+)"/)?.[1] ?? null;
    const registrations = await navigator.serviceWorker.getRegistrations();
    const readWorker = worker => new Promise(resolve => {
        if (!worker) return resolve(null);
        const channel = new MessageChannel();
        const finish = version => { clearTimeout(timer); channel.port1.close(); channel.port2.close(); resolve(version); };
        const timer = setTimeout(() => finish(null), 5000);
        channel.port1.onmessage = event => finish(event.data.version ?? null);
        worker.postMessage({ type: 'OFFLINE_VERSION' }, [channel.port2]);
    });
    const workerVersion = await readWorker(navigator.serviceWorker.controller);
    const waitingVersions = await Promise.all(registrations.map(r => readWorker(r.waiting)));
    const stored = [];
    for (const name of (await caches.keys()).filter(name => name.startsWith('qnx-'))) {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        if (name.endsWith('-pages')) {
            const pages = [];
            for (const key of keys) {
                const response = await cache.match(key);
                pages.push({ path: route(key.url), savedAt: Number(response.headers.get('x-qnx-page-saved-at')) || 0,
                    copyRole: response.headers.get('x-qnx-offline-copy'), ownerProtected: response.headers.has('x-qnx-cache-owner') });
            }
            pages.sort((a, b) => b.savedAt - a.savedAt);
            stored.push({ name, count: keys.length, latestPages: pages.slice(0, 12) });
        } else {
            const cacheVersion = name.replace(/-static$/, '');
            const key = keys.find(key => new URL(key.url).pathname === `/_next/static/${cacheVersion}/offline-assets.json`);
            const manifest = key ? await (await cache.match(key)).json() : null;
            stored.push({ name, count: keys.length, manifest: manifest ? { version: manifest.version, assets: manifest.assets?.length,
                preparedAt: manifest.preparedAt, pendingPages: manifest.pendingPages?.length ?? 0 } : null });
        }
    }
    let outboxCount = null;
    const databases = typeof indexedDB.databases === 'function' ? await indexedDB.databases() : [];
    if (databases.some(db => db.name === 'keyval-store')) {
        outboxCount = await new Promise(resolve => {
            const request = indexedDB.open('keyval-store');
            request.onupgradeneeded = () => request.transaction.abort();
            request.onerror = () => resolve(null);
            request.onsuccess = () => {
                const db = request.result;
                if (!db.objectStoreNames.contains('keyval')) { db.close(); return resolve(null); }
                const tx = db.transaction('keyval', 'readonly');
                const count = tx.objectStore('keyval').get('qnx-outbox');
                count.onsuccess = () => resolve(Array.isArray(count.result) ? count.result.length : 0);
                count.onerror = () => resolve(null);
                tx.oncomplete = () => db.close();
            };
        });
    }
    return { path: location.pathname, title: document.title, clientRelease, online: navigator.onLine,
        standalone: matchMedia('(display-mode: standalone)').matches, visibility: document.visibilityState,
        network: navigator.connection ? { effectiveType: navigator.connection.effectiveType, rtt: navigator.connection.rtt,
            downlink: navigator.connection.downlink, saveData: navigator.connection.saveData } : null,
        workerVersion, waitingVersions, controllerState: navigator.serviceWorker.controller?.state,
        registrations: registrations.map(r => ({ scope: r.scope, active: r.active?.state, waiting: r.waiting?.state, installing: r.installing?.state })),
        outboxCount, caches: stored,
        recentRequests: performance.getEntriesByType('resource').filter(r => new URL(r.name).origin === location.origin && !new URL(r.name).pathname.startsWith('/_next/')).slice(-12)
            .map(r => ({ path: route(r.name), duration: Math.round(r.duration), status: r.responseStatus, initiator: r.initiatorType })) };
})()
