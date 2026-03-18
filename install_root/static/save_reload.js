(() => {
    if (window.__saveReloadInitialized) return;
    window.__saveReloadInitialized = true;

    function doReload() {
        // Buscar la ventana real de Streamlit subiendo por la cadena de iframes
        // hasta encontrar una con location.href que empiece por http
        var win = window;
        for (var i = 0; i < 10; i++) {
            try {
                var href = win.location.href;
                if (href && (href.startsWith("http://") || href.startsWith("https://"))) {
                    var url = new URL(href);
                    url.searchParams.set("student_saved", "1");
                    win.location.href = url.toString();
                    return;
                }
                if (win.parent && win.parent !== win) {
                    win = win.parent;
                } else {
                    break;
                }
            } catch(e) {
                // cross-origin, intentar subir igualmente
                try { win = win.parent; } catch(_) { break; }
            }
        }
        // Fallback: recargar lo que sea
        window.location.reload();
    }

    function handleSaveStatus(ev) {
        let data = ev.data ?? {};
        if (typeof data === "string") {
            try { data = JSON.parse(data); } catch (_) { return; }
        }
        if (data.type !== "saveStatus" || !data.ok) return;
        setTimeout(doReload, 1500);
    }

    // Instalar en toda la cadena de ventanas accesible
    var win = window;
    for (var i = 0; i < 10; i++) {
        try {
            win.addEventListener("message", handleSaveStatus);
            if (win.parent && win.parent !== win) {
                win = win.parent;
            } else {
                break;
            }
        } catch(e) { break; }
    }
})();