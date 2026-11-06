(() => {
    const select=document.querySelector('select[aria-label="Simular rol"]');
    const scope=select?.closest('.rounded-xl');
    return { path:location.pathname, role:select?.value,
        selectedLabel:select?.selectedOptions[0]?.textContent,
        status:scope?.querySelector('[role="status"]')?.textContent?.trim(),
        statuses:[...document.querySelectorAll('[role="dialog"] [role="status"]')].map(el=>el.textContent.trim()).filter(text=>/copia|pantallas|Preparando/i.test(text)) };
})()
