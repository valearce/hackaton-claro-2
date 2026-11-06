(() => {
    const link=[...document.querySelectorAll('a')].find(a=>a.textContent.trim()==='Reintentar'&&a.getAttribute('href')==='/');
    if(link)link.click();
    return {clicked:Boolean(link)};
})()
