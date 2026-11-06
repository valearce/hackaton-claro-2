(async () => {
    const names = (await caches.keys()).filter(n=>n.startsWith('qnx-')&&n.endsWith('-pages'));
    const result=[];
    for (const name of names) {
        const cache=await caches.open(name);
        const roots=[];
        for (const path of ['/m/sst','/m/sst/mi-asistencia','/m/sst/documentos','/m/admin']) {
            const value=await cache.match(path);
            roots.push({path,present:Boolean(value),status:value?.status,copyRole:value?.headers.get('x-qnx-offline-copy'),savedAt:value?.headers.get('x-qnx-page-saved-at')});
        }
        const keys=await cache.keys();
        result.push({name,roots,sstPages:keys.filter(k=>new URL(k.url).pathname.startsWith('/m/sst/')).length});
    }
    return {path:location.pathname,title:document.title,online:navigator.onLine,caches:result};
})()
