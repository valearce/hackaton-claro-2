(() => {
    if(location.pathname!=='/m/admin')return{started:false};
    window.dispatchEvent(new Event('qnexus:prepare-offline'));
    return{started:true,path:location.pathname};
})()
