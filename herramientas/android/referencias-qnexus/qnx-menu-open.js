(() => {
    const button = document.querySelector('button[aria-label="Abrir menú de navegación"]');
    if (button) button.click();
    return { path: location.pathname, opened: Boolean(button) };
})()
