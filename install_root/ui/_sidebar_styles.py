"""
Constantes CSS y JS del sidebar y layout de la app.

Exporta:
  - SIDEBAR_CSS        — estilos del sidebar, header, mapa y zoom body fix
  - SIDEBAR_TOGGLE_JS  — botón flotante para expandir sidebar colapsado
  - ZOOM_FIX_JS        — ajuste de alturas Streamlit cuando body.style.zoom != 1
"""

SIDEBAR_CSS: str = """
<style>
/* ── SIDEBAR ──────────────────────────────────────────────────
   Especificidad [0,2,0] → gana al CSS del launcher [0,1,0]. */
[data-testid="stSidebar"][aria-expanded="true"] {
    min-width:  325px;
    max-width:  450px;
    overflow-x: hidden !important;
    overflow-y: auto   !important;
}

[data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
    overflow:   hidden !important;
    height:     auto   !important;
    min-height: 0      !important;
}

/* Ocultar barra de scroll (rueda del ratón sigue funcionando) */
[data-testid="stSidebar"],
[data-testid="stSidebar"] * {
    scrollbar-width:    none !important;
    -ms-overflow-style: none !important;
}
[data-testid="stSidebar"]::-webkit-scrollbar,
[data-testid="stSidebar"] *::-webkit-scrollbar {
    display: none !important;
    width:   0    !important;
    height:  0    !important;
}

/* ── STREAMLIT HEADER / TOOLBAR ──────────────────────────────
   height:0 + overflow:visible para que el botón del sidebar
   pueda escapar del header y ser visible. */
[data-testid="stHeader"] {
    height:     0           !important;
    min-height: 0           !important;
    overflow:   visible     !important;
    background: transparent !important;
    padding:    0           !important;
}

[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

[data-testid="stSidebarCollapseButton"] {
    position: fixed   !important;
    top:      0.4rem  !important;
    left:     0.4rem  !important;
    z-index:  9999    !important;
    display:  block   !important;
}

/* ── MAIN CONTENT ─────────────────────────────────────────────*/
[data-testid="stMainBlockContainer"] {
    padding-top:    1rem !important;
    padding-left:   1rem !important;
    padding-right:  1rem !important;
    padding-bottom: 0    !important;
    box-sizing:     border-box !important;
    width:          100% !important;
}

[data-testid="stMainBlockContainer"] > div {
    margin-bottom: 0 !important;
}

/* ── MAP IFRAME ───────────────────────────────────────────────*/
[data-map-frame] {
    min-height: 300px !important;
}

/* ── STREAMLIT STATUS BAR ─────────────────────────────────────*/
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {
    display: none !important;
    height:  0    !important;
}
</style>
"""

SIDEBAR_TOGGLE_JS: str = """
<script>
(function() {
    var BTN_ID = '__sidebar_expand_btn';

    function getSidebarBtn() {
        var doc = window.parent ? window.parent.document : document;
        return doc.querySelector('[data-testid="stSidebarCollapseButton"] button')
            || doc.querySelector('[data-testid="stSidebarCollapseButton"]');
    }

    function isSidebarCollapsed() {
        var doc = window.parent ? window.parent.document : document;
        var sidebar = doc.querySelector('[data-testid="stSidebar"]');
        return sidebar && sidebar.getAttribute('aria-expanded') === 'false';
    }

    function createBtn(doc) {
        var btn = doc.createElement('button');
        btn.id = BTN_ID;
        btn.title = 'Mostrar panel lateral';
        btn.innerHTML = '&#9776;';
        btn.style.cssText = [
            'position:fixed', 'top:8px', 'left:8px', 'z-index:99999',
            'background:#262730', 'color:#fff', 'border:none',
            'border-radius:6px', 'padding:6px 10px', 'font-size:18px',
            'cursor:pointer', 'display:none', 'line-height:1',
            'box-shadow:0 2px 6px rgba(0,0,0,.4)'
        ].join(';');
        btn.addEventListener('click', function() {
            var nb = getSidebarBtn();
            if (nb) nb.click();
        });
        doc.body.appendChild(btn);
        return btn;
    }

    function update() {
        var doc = window.parent ? window.parent.document : document;
        var btn = doc.getElementById(BTN_ID) || createBtn(doc);
        btn.style.display = isSidebarCollapsed() ? 'block' : 'none';
    }

    function startObserver() {
        var doc = window.parent ? window.parent.document : document;
        var sidebar = doc.querySelector('[data-testid="stSidebar"]');
        if (!sidebar) { setTimeout(startObserver, 300); return; }
        update();
        new MutationObserver(update).observe(sidebar,
            { attributes: true, attributeFilter: ['aria-expanded'] });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserver);
    } else {
        startObserver();
    }
})();
</script>
"""

ZOOM_FIX_JS: str = """<script>
(function() {
    try {
        var p   = window.parent;
        var SID = '__zoom_layout_fix';

        function applyFix() {
            var zoom = parseFloat(p.document.body.style.zoom) || 1.0;
            var inv = (1 / zoom).toFixed(6);

            var s = p.document.getElementById(SID);
            if (!s) {
                s = p.document.createElement('style');
                s.id = SID;
            }
            p.document.head.appendChild(s);

            s.textContent = [
                '[data-testid="stApp"] {',
                '  height:   calc(100vh * ' + inv + ') !important;',
                '  overflow: hidden                     !important;',
                '}',
                '[data-testid="stAppViewContainer"] {',
                '  height:   100% !important;',
                '  overflow: hidden !important;',
                '}',
                '[data-testid="stMain"] {',
                '  height:   100%   !important;',
                '  overflow: hidden !important;',
                '}',
                '[data-testid="stMainBlockContainer"] {',
                '  height:         100% !important;',
                '  overflow-y:     auto !important;',
                '  min-height:     0    !important;',
                '  padding-bottom: 0    !important;',
                '}',
            ].join('\\n');
        }

        applyFix();
        setTimeout(applyFix,  400);
        setTimeout(applyFix, 1500);

        new MutationObserver(applyFix).observe(p.document.body, {
            attributes: true, attributeFilter: ['style']
        });
        p.addEventListener('resize', applyFix);

    } catch(e) { /* silencioso en producción */ }
})();
</script>"""
