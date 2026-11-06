(() => {
    const button = [...document.querySelectorAll('button[aria-label="Cerrar menú"]')].find(el=>el.getClientRects().length);
    if(button)button.click();
    return {path:location.pathname,closed:Boolean(button)};
})()
