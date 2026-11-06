(() => {
    const visible = el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
    return { path: location.pathname,
        controls: [...document.querySelectorAll('[role="dialog"] button,[role="dialog"] a,[role="dialog"] select')].filter(visible).map(el => ({
            tag: el.tagName, label: el.getAttribute('aria-label'), text: el.textContent.trim().slice(0, 80), href: el.getAttribute('href')
        })).filter(el => /SST|Seguridad|Dev Nav|Rol|Preparar|Cerrar menú|Ajustes|Inicio|Panel/i.test(el.text + ' ' + el.label)) };
})()
