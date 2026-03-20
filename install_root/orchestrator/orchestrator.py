"""
Orquestador principal del sistema MovilidadESII.

Arranca los procesos de Flask y Streamlit, levanta un servidor WebSocket
en localhost:8765, y cierra ambos servicios limpiamente cuando el navegador
cierra la conexión WebSocket (es decir, cuando el usuario cierra la pestaña).

Uso:
    python orchestrator/orchestrator.py
    (ejecutar desde el directorio install_root/)
"""

import asyncio
import logging
import subprocess
import sys
import os
import psutil

from websockets.asyncio.server import serve

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [Orchestrator] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Rutas base: siempre relativas al directorio install_root (padre de este
# fichero), independientemente del directorio de trabajo actual.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))           # .../install_root/orchestrator/
_ROOT = os.path.dirname(_HERE)                               # .../install_root/

_API_SCRIPT       = os.path.join(_ROOT, "api",     "api.py")
_WEBAPP_SCRIPT    = os.path.join(_ROOT, "web_app", "my_app.py")

# Variables globales para los procesos hijo
streamlit_proc: subprocess.Popen | None = None
flask_proc:     subprocess.Popen | None = None

# Evento que señaliza al bucle principal que debe terminar
_shutdown_event: asyncio.Event | None = None

# Tarea de shutdown pendiente (se cancela si hay reconexión)
_shutdown_task: asyncio.Task | None = None

# Número de conexiones WebSocket activas
_active_connections: int = 0

# Segundos de gracia tras la última desconexión antes de matar procesos
_SHUTDOWN_GRACE_SECONDS = 5


def _kill_proc(proc: subprocess.Popen | None) -> None:
    """Mata un proceso hijo y todos sus descendientes usando psutil."""
    if proc is None:
        return
    try:
        parent = psutil.Process(proc.pid)
    except psutil.NoSuchProcess:
        return
    for child in parent.children(recursive=True):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.kill()
    except psutil.NoSuchProcess:
        pass


async def _delayed_shutdown() -> None:
    """Espera el periodo de gracia y luego apaga los procesos."""
    await asyncio.sleep(_SHUTDOWN_GRACE_SECONDS)
    logger.info("Periodo de gracia expirado. Cerrando procesos hijos…")
    _kill_proc(streamlit_proc)
    _kill_proc(flask_proc)
    logger.info("Procesos terminados.")
    if _shutdown_event is not None:
        _shutdown_event.set()


async def handler(websocket) -> None:
    """
    Manejador WebSocket.

    Se ejecuta cuando el navegador se conecta. Al desconectarse, espera
    _SHUTDOWN_GRACE_SECONDS antes de matar procesos, por si es un simple
    recargo de página (en ese caso llega una nueva conexión que cancela
    el shutdown pendiente).
    """
    global _active_connections, _shutdown_task

    remote = getattr(websocket, "remote_address", "desconocido")
    _active_connections += 1
    logger.info("Cliente WebSocket conectado desde %s (activas: %d)", remote, _active_connections)

    # Si había un shutdown pendiente por recarga, cancelarlo
    if _shutdown_task is not None and not _shutdown_task.done():
        _shutdown_task.cancel()
        logger.info("Shutdown cancelado por nueva conexión.")

    await websocket.wait_closed()

    _active_connections -= 1
    logger.info("Cliente desconectado (activas: %d). Esperando %ds antes de cerrar…",
                _active_connections, _SHUTDOWN_GRACE_SECONDS)

    # Solo programar shutdown si no quedan conexiones activas
    if _active_connections == 0:
        _shutdown_task = asyncio.create_task(_delayed_shutdown())


import time
import threading
import urllib.request


def _wait_for_streamlit(url: str, timeout: int = 30) -> bool:
    """Espera hasta que Streamlit esté respondiendo."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


import json as _json

_CFG_PATH = os.path.join(_ROOT, "window_config.json")


def _read_cfg() -> dict:
    try:
        with open(_CFG_PATH, "r", encoding="utf-8") as _f:
            return _json.load(_f)
    except Exception:
        return {}


def _write_cfg(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_CFG_PATH), exist_ok=True)
        existing = _read_cfg()
        existing.update(data)
        with open(_CFG_PATH, "w", encoding="utf-8") as _f:
            _json.dump(existing, _f, indent=2)
    except Exception:
        pass


class _PyWebViewAPI:
    """Funciones Python expuestas al JS de la ventana via pywebview js_api."""

    def pick_file(self):
        """Abre el diálogo nativo de ficheros y devuelve la ruta completa."""
        import webview
        windows = webview.windows
        if not windows:
            return {"ok": False, "reason": "no_window"}
        result = windows[0].create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=(
                "Documentos (*.pdf;*.doc;*.docx;*.xlsx;*.xls)",
                "Todos los archivos (*.*)",
            )
        )
        if result and len(result) > 0:
            return {"ok": True, "path": result[0]}
        return {"ok": False, "reason": "cancelled"}

    def save_file(self, base64_data: str, filename: str):
        """Abre el diálogo nativo de guardado, escribe los datos y devuelve la ruta."""
        import base64 as _b64
        import os
        import webview
        windows = webview.windows
        if not windows:
            return {"ok": False, "reason": "no_window"}
        ext = os.path.splitext(filename)[1].lower() or ".png"
        file_types = (f"Imagen (*{ext})", "Todos los archivos (*.*)")
        result = windows[0].create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=file_types,
        )
        if not result:
            return {"ok": False, "reason": "cancelled"}
        save_path = result if isinstance(result, str) else result[0]
        # base64_data puede venir como data URL "data:...;base64,XXX" o solo base64
        raw = base64_data.split(",", 1)[1] if "," in base64_data else base64_data
        with open(save_path, "wb") as f:
            f.write(_b64.b64decode(raw))
        return {"ok": True, "path": save_path}

    def save_zoom(self, level: float):
        _write_cfg({"zoom": float(level)})
        return {}


_ZOOM_JS = """
(function() {
    if (window.__zoomHandlerReady) return;
    window.__zoomHandlerReady = true;
    var _cur = 1.0;

    function applyZoom(cur) {
        _cur = cur;
        document.body.style.zoom = cur === 1.0 ? '' : cur;
        try { if (window.pywebview && window.pywebview.api) window.pywebview.api.save_zoom(cur); } catch(e) {}

        setTimeout(function() {
            var mapFrame = null, maxH = 0;
            document.querySelectorAll('iframe').forEach(function(f) {
                if (f.offsetHeight > maxH) { maxH = f.offsetHeight; mapFrame = f; }
            });

            var styleEl = document.getElementById('__map_fill_style');
            if (!styleEl) {
                styleEl = document.createElement('style');
                styleEl.id = '__map_fill_style';
                document.head.appendChild(styleEl);
            }

            if (!mapFrame || maxH < 100 || cur === 1.0) {
                styleEl.textContent = '';
                return;
            }

            mapFrame.setAttribute('data-map-frame', '1');
            var el = mapFrame.parentElement;
            while (el && el !== document.body) {
                el.setAttribute('data-map-wrap', '1');
                el = el.parentElement;
            }

            var topPx = Math.round(mapFrame.getBoundingClientRect().top);
            var hCalc = 'calc((100vh - ' + topPx + 'px) / ' + cur + ')';

            styleEl.textContent =
                '[data-map-frame] { height: ' + hCalc + ' !important; } ' +
                '[data-map-wrap]  { height: ' + hCalc + ' !important; overflow: visible !important; } ' +
                '[data-testid="stSidebar"] { min-height: calc(100vh / ' + cur + ') !important; }';

            setTimeout(function() {
                try {
                    var w = mapFrame.contentWindow;
                    if (!w) return;
                    Object.keys(w).forEach(function(k) {
                        try {
                            var obj = w[k];
                            if (obj && obj._leaflet_id && typeof obj.invalidateSize === 'function') {
                                obj.invalidateSize(true);
                            }
                        } catch(e) {}
                    });
                } catch(e) {}
            }, 80);
        }, 150);
    }

    if (_cur !== 1.0) applyZoom(_cur);

    document.addEventListener('wheel', function(e) {
        if (!e.ctrlKey) return;
        e.preventDefault();
        var cur = _cur;
        if (e.deltaY < 0) cur = Math.min(+(cur + 0.1).toFixed(1), 3.0);
        else               cur = Math.max(+(cur - 0.1).toFixed(1), 0.3);
        applyZoom(cur);
    }, { passive: false });

    document.addEventListener('keydown', function(e) {
        if (!e.ctrlKey) return;
        var k = e.key;
        var c = e.keyCode || e.which;
        var zoomIn  = (k === '+' || k === '=' || k === 'Add'      || c === 187 || c === 107);
        var zoomOut = (k === '-' || k === 'Subtract'              || c === 189 || c === 109);
        var zoomRst = (k === '0'                                  || c === 48);
        if (!zoomIn && !zoomOut && !zoomRst) return;
        e.preventDefault();
        var cur = _cur;
        if (zoomIn)  cur = Math.min(+(cur + 0.1).toFixed(1), 3.0);
        if (zoomOut) cur = Math.max(+(cur - 0.1).toFixed(1), 0.3);
        if (zoomRst) cur = 1.0;
        applyZoom(cur);
    });
})();
"""


def _open_webview(url: str) -> None:
    """Abre la app en ventana nativa. Bloquea hasta que el usuario la cierra."""
    try:
        import webview
    except ImportError:
        logger.error("pywebview no instalado. Instala con: pip install pywebview")
        import webbrowser
        webbrowser.open(url)
        return

    api = _PyWebViewAPI()
    icon_path = os.path.join(_ROOT, "MovilidadESII.ico")

    # En Windows, cambiar el icono de la barra de tareas via ctypes
    if sys.platform == "win32" and os.path.exists(icon_path):
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MovilidadESII")

    _cfg = _read_cfg()
    _init_zoom = float(_cfg.get("zoom", 1.0))
    _was_maximized = bool(_cfg.get("maximized", True))
    _kw = {}
    if "x" in _cfg and "y" in _cfg:
        _kw["x"], _kw["y"] = int(_cfg["x"]), int(_cfg["y"])

    win = webview.create_window(
        "Movilidad ESII", url,
        width=int(_cfg.get("width", 1400)),
        height=int(_cfg.get("height", 900)),
        min_size=(800, 600), resizable=True,
        js_api=api, background_color='#FFFFFF',
        **_kw,
    )

    if _was_maximized:
        win.events.shown += lambda: win.maximize()

    def _save_window_state():
        try:
            import ctypes, ctypes.wintypes
            hwnd = ctypes.windll.user32.FindWindowW(None, "Movilidad ESII")
            if not hwnd:
                return
            class _WP(ctypes.Structure):
                _fields_ = [("length", ctypes.c_uint), ("flags", ctypes.c_uint),
                             ("showCmd", ctypes.c_uint),
                             ("ptMin", ctypes.wintypes.POINT), ("ptMax", ctypes.wintypes.POINT),
                             ("rcNormal", ctypes.wintypes.RECT)]
            wp = _WP(); wp.length = ctypes.sizeof(wp)
            ctypes.windll.user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
            _write_cfg({
                "maximized": wp.showCmd == 3,
                "x": wp.rcNormal.left, "y": wp.rcNormal.top,
                "width":  wp.rcNormal.right  - wp.rcNormal.left,
                "height": wp.rcNormal.bottom - wp.rcNormal.top,
            })
        except Exception:
            pass

    win.events.closed += _save_window_state

    def _inject_zoom():
        try:
            js = _ZOOM_JS.replace("var _cur = 1.0;", "var _cur = " + str(_init_zoom) + ";")
            win.evaluate_js(js)
        except Exception:
            pass

    win.events.loaded += _inject_zoom
    webview.start()
    logger.info("Ventana cerrada por el usuario.")
    if _shutdown_event is not None:
        _shutdown_event.set()


async def main() -> None:
    global streamlit_proc, flask_proc, _shutdown_event
    _shutdown_event = asyncio.Event()

    logger.info("Arrancando Flask desde: %s", _API_SCRIPT)
    flask_proc = subprocess.Popen(
        [sys.executable, _API_SCRIPT],
        cwd=_ROOT,
    )

    logger.info("Arrancando Streamlit desde: %s", _WEBAPP_SCRIPT)
    streamlit_proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", _WEBAPP_SCRIPT,
         "--server.headless", "true",
         "--server.port", "8501"],
        cwd=_ROOT,
    )

    # Servidor WebSocket en segundo plano
    async with serve(handler, "localhost", 8765):
        logger.info("Servidor WebSocket listo en ws://localhost:8765")
        await _shutdown_event.wait()


if __name__ == "__main__":
    # pywebview DEBE correr en el hilo principal.
    # El loop asyncio (Flask + Streamlit + WebSocket) corre en un hilo secundario.

    def _run_async():
        try:
            asyncio.run(main())
        except Exception as e:
            logger.error("Error en bucle asyncio: %s", e)

    async_thread = threading.Thread(target=_run_async, daemon=True)
    async_thread.start()

    # Esperar a que Streamlit esté listo
    streamlit_url = "http://localhost:8501"
    logger.info("Esperando a que Streamlit arranque…")
    if _wait_for_streamlit(streamlit_url):
        logger.info("Streamlit listo. Abriendo ventana nativa.")
        _open_webview(streamlit_url)  # bloquea en el hilo principal hasta cerrar
    else:
        logger.error("Streamlit no arrancó en 30s.")

    # Shutdown limpio
    if _shutdown_event is not None:
        _shutdown_event.set()
    _kill_proc(streamlit_proc)
    _kill_proc(flask_proc)
    logger.info("Procesos terminados. Saliendo.")