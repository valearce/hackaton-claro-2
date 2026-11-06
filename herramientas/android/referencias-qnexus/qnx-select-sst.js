(() => {
    const select = document.querySelector('select[aria-label="Simular rol"]');
    if (!select || ![...select.options].some(o => o.value === 'sst')) return { changed: false };
    select.value = 'sst';
    select.dispatchEvent(new Event('change', { bubbles: true }));
    return { changed: true };
})()
