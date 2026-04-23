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

    // En navegador: este script corre dentro de un iframe (st.components.v1.html),
    // por eso usa window.parent.document para acceder al DOM de Streamlit.
    // En pywebview el botón se inyecta directamente desde el launcher (evaluate_js).

    function getDoc() {
        return window.parent ? window.parent.document : document;
    }

    function getSidebar() {
        return getDoc().querySelector('[data-testid="stSidebar"]');
    }

    // Detección por ancho real (cubre versiones donde aria-expanded no basta).
    function isSidebarCollapsed() {
        var s = getSidebar();
        if (!s) return false;
        if (s.getAttribute('aria-expanded') === 'false') return true;
        var rect = s.getBoundingClientRect();
        if (rect.width < 50 || rect.right <= 0) return true;
        return false;
    }

    // Lista de selectores candidatos del botón de toggle, por orden de preferencia.
    function findToggleBtn() {
        var doc = getDoc();
        var selectors = [
            '[data-testid="stSidebarCollapseButton"] button',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="stSidebarCollapsedControl"] button',
            '[data-testid="stSidebarCollapsedControl"]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="panel" i]'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var el = doc.querySelector(selectors[i]);
            if (el) return el;
        }
        return null;
    }

    function syntheticClick(el) {
        try {
            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function(t) {
                el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window }));
            });
        } catch (e) { /* ignore */ }
    }

    function expandSidebar() {
        var btn = findToggleBtn();
        if (btn) {
            try { btn.click(); } catch (e) {}
            syntheticClick(btn);
        }
        // Fallback: si nada cambió, forzar aria-expanded.
        setTimeout(function() {
            var s = getSidebar();
            if (s && s.getAttribute('aria-expanded') === 'false') {
                s.setAttribute('aria-expanded', 'true');
            }
        }, 80);
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
        btn.addEventListener('click', expandSidebar);
        doc.body.appendChild(btn);
        return btn;
    }

    function update() {
        var doc = getDoc();
        var btn = doc.getElementById(BTN_ID) || createBtn(doc);
        btn.style.display = isSidebarCollapsed() ? 'block' : 'none';
    }

    function start() {
        var sidebar = getSidebar();
        if (!sidebar) { setTimeout(start, 300); return; }
        update();
        try {
            new MutationObserver(update).observe(sidebar, {
                attributes: true, attributeFilter: ['aria-expanded', 'style', 'class']
            });
        } catch (e) {}
        // Poll como red de seguridad si Streamlit recrea el DOM del sidebar.
        setInterval(update, 500);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', start);
    } else {
        start();
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
