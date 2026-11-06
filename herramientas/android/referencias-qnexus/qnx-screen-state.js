(() => {
    const visible = el => el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
    const text = document.body.innerText;
    return { path: location.pathname, title: document.title, online: navigator.onLine, ready: document.readyState,
        headings: [...document.querySelectorAll('h1,h2')].filter(visible).map(el=>el.textContent.trim()).filter(t=>/Sin conexión|SST|Formatos|Control|Administr|Panel|Acceso|Error|Módulo/i.test(t)),
        staticMessages: ['Sin conexión', 'No hay señal para cargar', 'No se pudo', 'Cargando', 'Sin copia', 'Acceso denegado', 'Acceso no autorizado'].filter(t=>text.includes(t)),
        actions: [...document.querySelectorAll('button,a')].filter(visible).map(el=>({tag:el.tagName,label:el.getAttribute('aria-label'),text:el.textContent.trim(),href:el.getAttribute('href')}))
            .filter(el=>/^(Reintentar|Volver|Volver al menú|Inicio|Menú|Recargar|Abrir copia)/.test(el.text)||/Volver|Abrir menú/.test(el.label??'')).slice(0,10) };
})()
