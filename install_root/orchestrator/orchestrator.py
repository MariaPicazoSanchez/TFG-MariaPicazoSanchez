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
