(() => {
    const select = document.querySelector('select[aria-label="Simular rol"]');
    return { path: location.pathname, current: select?.value,
        options: select ? [...select.options].map(o => ({ value: o.value, label: o.textContent })) : [] };
})()
