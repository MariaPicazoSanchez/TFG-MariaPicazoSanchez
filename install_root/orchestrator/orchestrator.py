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


async def handler(websocket) -> None:
    """
    Manejador WebSocket.

    Se ejecuta cuando el navegador se conecta. Bloquea en
    ``websocket.wait_closed()`` y cuando el cliente cierra la conexión
    (cierre de pestaña o de ventana), termina los procesos hijo y señaliza
    al bucle principal que debe terminar.
    """
    remote = getattr(websocket, "remote_address", "desconocido")
    logger.info("Cliente WebSocket conectado desde %s", remote)

    await websocket.wait_closed()

    logger.info("Cliente desconectado. Cerrando procesos hijos…")
    _kill_proc(streamlit_proc)
    _kill_proc(flask_proc)
    logger.info("Procesos terminados.")

    # Señalizar al bucle principal que puede salir limpiamente.
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
        [sys.executable, "-m", "streamlit", "run", _WEBAPP_SCRIPT],
        cwd=_ROOT,
    )

    # Servidor WebSocket: espera conexiones del cliente (my_app.py inyecta el JS)
    async with serve(handler, "localhost", 8765):
        logger.info("Servidor WebSocket listo en ws://localhost:8765")
        # Mantenerse activo hasta que handler() señalice el cierre.
        await _shutdown_event.wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupción por teclado. Cerrando procesos…")
        _kill_proc(streamlit_proc)
        _kill_proc(flask_proc)
        logger.info("Procesos terminados. Saliendo.")
