(async () => {
    const result = await resumeCachedPage();
    const destination = result?.headers.get('location');
    const url = destination ? new URL(destination) : null;
    return { workerVersion: CACHE_VERSION, fallbackStatus: result?.status ?? null,
        wouldReopen: url ? url.pathname.split('/').slice(0, 4).join('/') : null,
        wasNavigationTriggered: false };
})()
