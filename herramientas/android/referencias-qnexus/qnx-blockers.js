(async () => {
    const selector = 'form, [role="dialog"], [aria-busy="true"], [contenteditable="true"], textarea, input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"]):not([type="button"]):not([type="submit"])';
    const visible = element => element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden';
    return { path: location.pathname, readyState: document.readyState, online: navigator.onLine,
        blockers: [...document.querySelectorAll(selector)].filter(visible).map(element => ({ tag: element.tagName, role: element.getAttribute('role'), type: element.getAttribute('type'), busy: element.getAttribute('aria-busy'), placeholder: element.getAttribute('placeholder') })),
        navigation: [...document.querySelectorAll('button,a')].filter(visible).map(element => ({ tag: element.tagName, text: element.textContent.trim(), label: element.getAttribute('aria-label'), href: element.getAttribute('href') }))
            .filter(element => /^(Ajustes|Configuración|Abrir menú|Actualizar|Preparar|Mi Asistencia)$/i.test(element.text) || /menú|actualiza|conexión|ajustes/i.test(element.label ?? '')) };
})()
