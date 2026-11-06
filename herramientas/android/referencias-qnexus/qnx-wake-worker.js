(async () => {
    const controller = navigator.serviceWorker.controller;
    if (!controller) return { path: location.pathname, workerVersion: null };
    return await new Promise(resolve => {
        const channel = new MessageChannel();
        const timer = setTimeout(() => { channel.port1.close(); resolve({ path: location.pathname, workerVersion: null }); }, 5000);
        channel.port1.onmessage = event => { clearTimeout(timer); channel.port1.close(); resolve({ path: location.pathname, workerVersion: event.data.version ?? null }); };
        controller.postMessage({ type: 'OFFLINE_VERSION' }, [channel.port2]);
    });
})()
