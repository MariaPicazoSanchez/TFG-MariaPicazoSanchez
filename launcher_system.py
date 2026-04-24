#!python3.12
# -*- coding: utf-8 -*-
# ── Standard library ────────────────────────────────────────────────────────
import asyncio
import ctypes
import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
import urllib.request
from websockets.asyncio.server import serve as _ws_serve
# ─────────────────────────────────────────────────────────────────────────────


_WS_GRACE_SECONDS = 5  # segundos de gracia tras última desconexión WS


def start_ws_control_server(port: int, shutdown_event: threading.Event) -> None:
    """
    Inicia el servidor WebSocket de control en un hilo secundario.

    El navegador se conecta a ws://127.0.0.1:{port}/ y mantiene la conexión
    abierta mientras la pestaña está activa.  Cuando todas las conexiones se
    cierran (cierre real de pestaña), se espera _WS_GRACE_SECONDS antes de
    señalizar shutdown_event — ese margen absorbe los F5/recargas, en los que
    el navegador cierra y reabre la conexión en pocos segundos.
    """
    _log = logging.getLogger("movilidad_launcher")
    active = [0]           # contador de conexiones WS activas
    first_seen = [False]   # guard: no disparar shutdown antes de la 1ª conexión
    pending = [None]       # asyncio.Task del shutdown con gracia

    async def _handler(websocket) -> None:
        first_seen[0] = True
        active[0] += 1
        _log.info("WS conectado (activas: %d)", active[0])

        # Si había un shutdown pendiente por recarga, cancelarlo
        if pending[0] is not None and not pending[0].done():
            pending[0].cancel()
            _log.info("Shutdown WS cancelado por reconexión.")

        await websocket.wait_closed()

        active[0] -= 1
        _log.info("WS desconectado (activas: %d). Grace %ds.", active[0], _WS_GRACE_SECONDS)

        if active[0] == 0 and first_seen[0]:
            async def _delayed_shutdown() -> None:
                await asyncio.sleep(_WS_GRACE_SECONDS)
                _log.info("WS grace expirado → señal de shutdown.")
                shutdown_event.set()

            pending[0] = asyncio.create_task(_delayed_shutdown())

    async def _serve() -> None:
        async with _ws_serve(_handler, "127.0.0.1", port):
            _log.info("WS control server en ws://127.0.0.1:%d", port)
            while not shutdown_event.is_set():
                await asyncio.sleep(0.3)

    threading.Thread(
        target=lambda: asyncio.run(_serve()),
        daemon=True,
        name="ws-control",
    ).start()


LAUNCHER_VERSION = "envfix-2026-01-05-1.0"


def get_appdata_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "MovilidadESII"


APPDATA_DIR = get_appdata_dir()
LOG_DIR = APPDATA_DIR / "logs"
DEMO_MODE: bool = "--demo" in sys.argv
DEV_MODE:  bool = "--dev"  in sys.argv
DATA_DEMO_DIR = APPDATA_DIR / "data"
# Python a usar para lanzar Streamlit y la API: preferimos el embebido,
# fallback al Python del sistema si el embebido no existe.
_PYTHON_EXE: Path | None = None
if getattr(sys, "frozen", False):
    # Instalación compilada: config en AppData
    CONFIG_PATH = APPDATA_DIR / "config.json"
else:
    # Desarrollo desde el repo: config en install_root/
    CONFIG_PATH = Path(__file__).resolve().parent / "install_root" / "config.json"
API_STATUS_PATH = APPDATA_DIR / "api_status.json"
LAUNCHER_LOG_PATH = LOG_DIR / "launcher.log"
APP_LOG_PATH = LOG_DIR / "app.log"
API_LOG_PATH = LOG_DIR / "api.log"
PIP_LOG_PATH = LOG_DIR / "pip_install.log"
LOCK_NAME = "Global\\MovilidadESII_Launcher"
RESTORE_EVENT_NAME = "Global\\MovilidadESII_Restore"

# Callback que se rellena después de crear la ventana; el listener lo invoca
# cuando la segunda instancia señaliza el evento de restauración.
_restore_callback_holder: list = [None]

NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = subprocess.CREATE_NO_WINDOW

# Flags para procesos hijos: sin ventana + grupo propio para que taskkill /T
# encuentre TODOS los descendientes del proceso (subprocesos de Streamlit, etc.).
PROC_FLAGS = NO_WINDOW
if os.name == "nt":
    PROC_FLAGS |= subprocess.CREATE_NEW_PROCESS_GROUP


# ── Helpers de terminación: módulo global ──────────────────────────────────────

def _taskkill_tree(pid: int) -> None:
    """Mata el PID y toda su descendencia de forma forzada (Windows)."""
    if os.name != "nt":
        return
    logger = logging.getLogger("movilidad_launcher")
    try:
        r = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            creationflags=NO_WINDOW,
            timeout=8,
        )
        logger.info(
            "taskkill /F /T PID=%s -> rc=%s  %s",
            pid, r.returncode, (r.stdout or r.stderr or "").strip(),
        )
    except Exception as exc:
        logger.warning("taskkill falló PID=%s: %s", pid, exc)


def _pids_on_port(port: int) -> set[int]:
    """PIDs escuchando o con conexión ESTABLISHED en 127.0.0.1:port (Windows)."""
    if os.name != "nt":
        return set()
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True, creationflags=NO_WINDOW, timeout=3,
        )
    except Exception:
        return set()
    port_str = f":{port}"
    pids: set[int] = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr, state, pid_s = parts[1], parts[3], parts[4]
        if "127.0.0.1" in local_addr and port_str in local_addr and state in ("LISTENING", "ESTABLISHED"):
            try:
                pids.add(int(pid_s))
            except ValueError:
                pass
    return pids


def shutdown_processes(
    procs: list,
    ports: list[int] | None = None,
) -> None:
    """
    Termina de forma robusta todos los procesos hijos y sus árboles.

    Estrategia (Windows):
      1. Recolectar PIDs desde los Popen + puertos conocidos.
      2. taskkill /F /T /PID <pid> para cada uno — mata el árbol completo.
      3. Verificar con poll() y registrar lo que siga vivo.

    En plataformas no-Windows se usa terminate() como fallback sin árbol.
    """
    logger = logging.getLogger("movilidad_launcher")
    logger.info("shutdown_processes: iniciando terminación forzada.")

    if os.name != "nt":
        # Plataforma no-Windows: terminate suave, sin árbol
        for proc in procs:
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception as exc:
                    logger.warning("terminate fallo PID=%s: %s", getattr(proc, 'pid', '?'), exc)
        return

    # ── Recopilar todos los PIDs relevantes ─────────────────────────────────
    pids: set[int] = set()

    for proc in procs:
        if proc is not None and proc.pid:
            if proc.poll() is None:          # solo si sigue vivo
                pids.add(proc.pid)
            else:
                logger.debug("PID=%s ya ha terminado (rc=%s).", proc.pid, proc.returncode)

    for port in (ports or []):
        try:
            pids |= _pids_on_port(port)
        except Exception as exc:
            logger.debug("_pids_on_port(%s) fallo: %s", port, exc)

    if not pids:
        logger.info("shutdown_processes: ningún proceso vivo encontrado.")
        return

    logger.info("shutdown_processes: matando PIDs %s", sorted(pids))

    # ── taskkill /F /T por cada PID (mata el árbol completo) ────────────────
    for pid in sorted(pids):
        _taskkill_tree(pid)

    # ── Verificación final ───────────────────────────────────────────────────
    time.sleep(0.5)   # pequeña espera para que el SO procese las señales
    for proc in procs:
        if proc is not None:
            rc = proc.poll()
            if rc is None:
                logger.warning(
                    "ADVERTENCIA: PID=%s sigue vivo tras taskkill. "
                    "Intentando segunda pasada.", proc.pid
                )
                _taskkill_tree(proc.pid)
            else:
                logger.info("PID=%s confirmado terminado (rc=%s).", proc.pid, rc)

    logger.info("shutdown_processes: completado.")


# ── Verificación final ────────────────────────────────────────────────────────
# Elimina el import local de time (ya importado a nivel de módulo)
# que existía en versiones anteriores de shutdown_processes.
# ─────────────────────────────────────────────────────────────────────────────


if getattr(sys, "frozen", False):
    # Si está compilado con PyInstaller, el ejecutable está en la raíz de MovilidadESII
    # El código está en MovilidadESII/app/
    ROOT = Path(sys.executable).resolve().parent / "app"
    if not ROOT.exists():
        # Fallback a la raíz si app/ no existe
        ROOT = Path(sys.executable).resolve().parent
else:
    # En desarrollo, apuntar a install_root/ desde el directorio del launcher
    ROOT = Path(__file__).resolve().parent / "install_root"
    if not ROOT.exists():
        # Fallback si no existe
        ROOT = Path(__file__).resolve().parent

LOGGER = logging.getLogger("movilidad_launcher")
LOGGER.addHandler(logging.NullHandler())


def _run_capture(cmd: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=NO_WINDOW,
    )


def _python_is_312(exe: Path) -> bool:
    """Valida que el ejecutable es Python 3.12.x y no es el alias de Windows Store."""
    try:
        if not exe.exists():
            return False
        # Evitar el alias de Microsoft Store
        if "WindowsApps" in str(exe):
            return False
        r = _run_capture([str(exe), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"], timeout=6)
        if r.returncode != 0:
            return False
        ver = (r.stdout or "").strip().splitlines()[-1] if (r.stdout or "").strip() else ""
        return ver == "3.12"
    except Exception:
        return False


def _registry_python312_candidates() -> list[Path]:
    """Busca rutas de Python 3.12 en el registro de Windows."""
    if os.name != "nt":
        return []
    try:
        import winreg  # type: ignore
    except Exception:
        return []

    keys = [
        r"SOFTWARE\\Python\\PythonCore\\3.12\\InstallPath",
        r"SOFTWARE\\WOW6432Node\\Python\\PythonCore\\3.12\\InstallPath",
    ]
    roots = [winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE]
    out: list[Path] = []
    for root in roots:
        for k in keys:
            try:
                with winreg.OpenKey(root, k) as h:
                    install_path, _ = winreg.QueryValueEx(h, "")
                    if install_path:
                        out.append(Path(str(install_path)) / "python.exe")
            except Exception:
                continue
    return out


def _python_works(exe: Path) -> bool:
    try:
        if not exe.exists():
            return False
        r = _run_capture([str(exe), "-c", "import sys; print(sys.executable)"], timeout=6)
        return r.returncode == 0
    except Exception:
        return False


def _is_msix_install() -> bool:
    """
    Detecta si el launcher corre dentro de un paquete MSIX (WindowsApps).
    En ese caso el Python embebido está junto al exe, no en AppData.
    """
    return "WindowsApps" in str(Path(sys.executable).resolve())


def get_runtime_python() -> Path:
    """
    Resuelve el Python embebido a usar para lanzar Streamlit y la API.

    Orden de búsqueda:
      1. runtime/python/ relativo al exe  → instalación MSIX
      2. %LOCALAPPDATA%/MovilidadESII/runtime/python/ → instalación Inno Setup
      3. Python del sistema (fallback)
    """
    # 1) MSIX: Python preinstalado junto al exe dentro del paquete
    exe_dir = Path(sys.executable).resolve().parent
    msix_py = exe_dir / "runtime" / "python" / "python.exe"
    if _python_works(msix_py):
        LOGGER.debug("Python runtime seleccionado (MSIX): %s", msix_py)
        return msix_py.resolve()

    # 2) Inno Setup: Python extraído por el installer en AppData
    embedded_py = APPDATA_DIR / "runtime" / "python" / "python.exe"
    if _python_works(embedded_py):
        LOGGER.debug("Python runtime seleccionado (embebido AppData): %s", embedded_py)
        return embedded_py.resolve()

    # 3) Fallback al Python del sistema
    py = get_system_python()
    LOGGER.debug("Python runtime seleccionado (system): %s", py)
    return py


def get_system_python() -> Path:
    """Resuelve un Python 3.12.x del sistema."""
    global _PYTHON_EXE
    if _PYTHON_EXE is not None:
        return _PYTHON_EXE

    candidates: list[Path] = []

    # 1) Python Launcher (py -3.12)
    if os.name == "nt" and shutil.which("py"):
        try:
            r = _run_capture(["py", "-3.12", "-c", "import sys; print(sys.executable)"])
            if r.returncode == 0:
                exe = (r.stdout or "").strip().splitlines()[-1]
                if exe:
                    candidates.append(Path(exe))
        except Exception:
            pass

    # 2) python en PATH
    for name in ("python", "python3", "python3.12"):
        p = shutil.which(name)
        if p:
            candidates.append(Path(p))

    # 3) Registro
    candidates.extend(_registry_python312_candidates())

    # 4) Rutas comunes
    common = []
    if os.name == "nt":
        local = os.getenv("LOCALAPPDATA") or ""
        common = [
            Path(local) / "Programs" / "Python" / "Python312" / "python.exe",
            Path("C:/Program Files/Python312/python.exe"),
            Path("C:/Python312/python.exe"),
        ]
    candidates.extend(common)

    # Filtrar duplicados manteniendo orden
    seen = set()
    uniq: list[Path] = []
    for c in candidates:
        s = str(c).lower()
        if s in seen:
            continue
        seen.add(s)
        uniq.append(c)

    for exe in uniq:
        if _python_is_312(exe):
            _PYTHON_EXE = exe.resolve()
            LOGGER.debug("Python del sistema seleccionado: %s", _PYTHON_EXE)
            return _PYTHON_EXE

    raise RuntimeError(
        "No se encontró Python 3.12 del sistema. "
        "Instala Python 3.12.x y marca 'Add to PATH' o instala el Python Launcher (py)."
    )


def prepare_appdata_dirs() -> None:
    for folder in (APPDATA_DIR, LOG_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    if DEMO_MODE:
        DATA_DEMO_DIR.mkdir(parents=True, exist_ok=True)


def touch_initial_logs() -> None:
    for path in (LAUNCHER_LOG_PATH, APP_LOG_PATH, API_LOG_PATH, PIP_LOG_PATH):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        except OSError:
            # Logging is not configured yet; failure will be captured later.
            pass


def setup_launcher_logging() -> None:
    handler = logging.FileHandler(LAUNCHER_LOG_PATH, encoding="utf-8", mode="a")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    LOGGER.handlers = []
    LOGGER.addHandler(handler)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    console.setLevel(logging.INFO)
    LOGGER.addHandler(console)
    LOGGER.setLevel(logging.DEBUG)


def single_instance_lock():
    if os.name != "nt":
        LOGGER.debug("Mutex no requerido en esta plataforma.")
        return None
    ERROR_ALREADY_EXISTS = 183
    handle = ctypes.windll.kernel32.CreateMutexW(None, True, LOCK_NAME)
    if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        LOGGER.warning("Ya hay otra instancia en ejecución — señalizando restauración.")
        # Señalizar a la instancia en ejecución que restaure su ventana
        EVENT_MODIFY_STATE = 0x0002
        ev = ctypes.windll.kernel32.OpenEventW(EVENT_MODIFY_STATE, False, RESTORE_EVENT_NAME)
        if ev:
            ctypes.windll.kernel32.SetEvent(ev)
            ctypes.windll.kernel32.CloseHandle(ev)
        return None
    LOGGER.debug("Mutex de instancia adquirido.")
    return handle


def _start_restore_listener() -> None:
    """
    Inicia un hilo de fondo que espera el evento de restauración de ventana.
    Cuando la segunda instancia señaliza RESTORE_EVENT_NAME, este hilo invoca
    _restore_callback_holder[0]() para sacar la ventana de la bandeja.
    """
    if os.name != "nt":
        return

    def _listen():
        kernel32 = ctypes.windll.kernel32
        INFINITE = 0xFFFFFFFF
        ev = kernel32.CreateEventW(None, False, False, RESTORE_EVENT_NAME)
        if not ev:
            return
        try:
            while True:
                result = kernel32.WaitForSingleObject(ev, INFINITE)
                if result != 0:   # WAIT_FAILED o WAIT_ABANDONED
                    break
                cb = _restore_callback_holder[0]
                if cb:
                    try:
                        cb()
                    except Exception:
                        pass
        finally:
            kernel32.CloseHandle(ev)

    threading.Thread(target=_listen, daemon=True, name="restore-listener").start()


def release_instance_lock(handle) -> None:
    if handle and os.name == "nt":
        ctypes.windll.kernel32.ReleaseMutex(handle)
        ctypes.windll.kernel32.CloseHandle(handle)


def ensure_data_demo() -> None:
    if DATA_DEMO_DIR.exists() and any(DATA_DEMO_DIR.iterdir()):
        LOGGER.debug("data_demo disponible en AppData (%s)", DATA_DEMO_DIR)
        return
    LOGGER.warning(
        "data_demo no está presente en %s. La instalación debería copiarlo desde AppData.",
        DATA_DEMO_DIR
    )


def write_demo_config() -> None:
    """Escribe config.json desde config.demo.json reemplazando rutas de data_demo."""
    # Si config.json ya existe y tiene rutas de programas de movilidad, no regenerar
    if CONFIG_PATH.exists():
        try:
            existing = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            _MOBILITY_KEYS = ("SICUE OUT", "Erasmus IN", "Erasmus OUT")
            if existing and any(k in existing for k in _MOBILITY_KEYS):
                LOGGER.debug("config.json ya existe y es válido, omitiendo regeneración")
                return
        except Exception:
            pass  # Si falla la lectura (JSON inválido, etc.), regenerar
    
    demo_path = ROOT / "config.demo.json"
    if not demo_path.exists():
        LOGGER.warning("config.demo.json no existe en %s", ROOT)
        return
    
    try:
        demo_config = json.loads(demo_path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.error("No se pudo leer config.demo.json: %s", exc)
        return
    
    new_config = {}
    for key, value in demo_config.items():
        if isinstance(value, str) and value.startswith("./data_demo/"):
            rel = value.split("./data_demo/", 1)[1]
            full_path = DATA_DEMO_DIR / rel
            # Normalizar: Windows usa \ en rutas. Asegurar que es Path y convertir a str con \
            normalized_path = str(full_path.resolve()).replace("/", "\\")
            new_config[key] = normalized_path
            LOGGER.info("Config %s: %s", key, normalized_path)
        else:
            new_config[key] = value
    
    try:
        # Asegurar que el directorio de config existe
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(new_config, ensure_ascii=False, indent=4),
            encoding="utf-8"
        )
        LOGGER.info("config.json regenerado correctamente en %s", CONFIG_PATH)
    except Exception as exc:
        LOGGER.error("No se pudo escribir config.json en %s: %s", CONFIG_PATH, exc)


def ensure_installation() -> tuple[bool, str | None]:
    # En instalación MSIX las dependencias vienen preinstaladas dentro del paquete:
    # no existe .installer_complete (ese marcador solo lo crea Inno Setup) y
    # hacer el import-check ralentizaría el arranque innecesariamente.
    if _is_msix_install():
        LOGGER.debug("Instalación MSIX detectada — saltando verificación de dependencias.")
        return True, None

    installer_marker = APPDATA_DIR / ".installer_complete"

    # Si el instalador completó, confiar en que todo está OK (arranque rápido)
    if installer_marker.exists():
        LOGGER.debug("Instalación completa detectada, saltando verificación de dependencias.")
        return True, None

    # Solo verificar si no hay marcador
    py = get_runtime_python()
    LOGGER.debug("Verificando dependencias con %s", py)
    def _run_import(code: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(py), "-c", code],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=NO_WINDOW,
        )
    try:
        LOGGER.warning(".installer_complete ausente; asegurar dependencias mínimas.")
        result = _run_import("import streamlit")
    except Exception as exc:
        raise RuntimeError(f"No se pudo ejecutar Python del sistema: {exc}") from exc
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "Sin detalles").strip()
        raise RuntimeError(
            f"Faltan dependencias críticas: {details}. "
            f"Consulta {PIP_LOG_PATH}."
        )
    reason = (
        "Instalación incompleta: falta .installer_complete; "
        f"consulta {PIP_LOG_PATH} para revisar pip_install.log. API deshabilitada."
    )
    LOGGER.warning(reason)
    return False, reason


def notify_user(title: str, msg: str) -> None:
    LOGGER.debug("notify_user: %s", msg.replace("\n", " "))
    try:
        if os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x10)
    except Exception:
        pass


def write_api_status(ok: bool, api_url: str, reason: str = "") -> None:
    try:
        status = {"ok": ok, "api_url": api_url, "reason": reason, "ts": time.time()}
        API_STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        LOGGER.debug("api_status.json actualizado: %s", status)
    except Exception as exc:
        LOGGER.debug("No se pudo escribir api_status.json: %s", exc)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def pick_two_free_ports() -> tuple[int, int]:
    for attempt in range(1, 21):
        sockets = []
        ports = set()
        success = True
        try:
            for _ in range(2):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    sock.bind(("127.0.0.1", 0))
                except OSError:
                    success = False
                    break
                sockets.append(sock)
                ports.add(sock.getsockname()[1])
        finally:
            for sock in sockets:
                sock.close()
        if success and len(ports) == 2:
            chosen = tuple(ports)
            LOGGER.debug("Puertos libres seleccionados: %s (intento %s)", chosen, attempt)
            return chosen
        time.sleep(0.05)
    raise RuntimeError("No se pudieron reservar dos puertos libres.")


def wait_for_health(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    body = r.read().decode("utf-8", errors="ignore")
                    try:
                        data = json.loads(body)
                        if data.get("ok") is True:
                            return True
                    except Exception:
                        return True
        except Exception:
            time.sleep(0.15)
    return False


def wait_for_http(url: str, timeout: float = 20.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status in (200, 302):
                    return True
        except Exception:
            time.sleep(0.15)
    return False

def start_processes(api_enabled: bool = True, api_disabled_reason: str | None = None) -> None:
    py = Path(sys.executable) if DEV_MODE else get_runtime_python()

    # En MSIX el código de la app está en ROOT (dentro del paquete, sólo-lectura).
    # Usamos ROOT como cwd para que los módulos relativos (web_app/, api/) se resuelvan
    # correctamente, pero aseguramos que los logs y archivos temporales vayan a APPDATA_DIR.
    # Nota: subprocess.Popen con cwd de sólo lectura es válido en Windows; el SO
    # no escribe en ese directorio, sólo lo usa como directorio de trabajo del proceso.
    proc_cwd = str(ROOT)

    api_port, app_port = pick_two_free_ports()
    api_url = f"http://127.0.0.1:{api_port}"
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["APP_CONFIG_PATH"] = str(CONFIG_PATH)
    env["API_HOST"] = "127.0.0.1"
    env["API_PORT"] = str(api_port)
    env["FLASK_SKIP_DOTENV"] = "1"

    env_app = env.copy()
    env_app["API_URL"] = api_url
    env_app["STREAMLIT_SERVER_HEADLESS"] = "true"
    env_app["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    env_app["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    env_app["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"

    app_proc = None
    api_proc = None
    app_log = open(APP_LOG_PATH, "w", encoding="utf-8")
    api_log = open(API_LOG_PATH, "w", encoding="utf-8")

    # --- CONTROL SERVER WEBSOCKET PARA SHUTDOWN ---
    shutdown_event = threading.Event()
    ws_port = find_free_port()
    start_ws_control_server(ws_port, shutdown_event)
    env_app["WS_PORT"] = str(ws_port)


    try:
        LOGGER.info("Iniciando Streamlit en 127.0.0.1:%s", app_port)
        app_proc = subprocess.Popen(
            [
                str(py), "-m", "streamlit", "run", "web_app/my_app.py",
                "--server.address=127.0.0.1",
                f"--server.port={app_port}",
                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",
                "--browser.gatherUsageStats=false",
            ],
            cwd=proc_cwd,
            env=env_app,
            stdout=app_log,
            stderr=app_log,
            creationflags=PROC_FLAGS,  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        )

        url = f"http://127.0.0.1:{app_port}"
        (LOG_DIR / "last_url.txt").write_text(url, encoding="utf-8")

        # Arrancar API en paralelo si está habilitada
        if api_enabled:
            LOGGER.info("Iniciando API en 127.0.0.1:%s", api_port)
            api_proc = subprocess.Popen(
                [str(py), "api/api.py"],
                cwd=proc_cwd,
                env=env,
                stdout=api_log,
                stderr=api_log,
                creationflags=PROC_FLAGS,  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
            )

        # --- JOB OBJECT para evitar huérfanos en Windows ---
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", ctypes.c_uint32),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", ctypes.c_uint32),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", ctypes.c_uint32),
                    ("SchedulingClass", ctypes.c_uint32)
                ]
            class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                _fields_ = [
                    ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                    ("Reserved1", ctypes.c_byte * 40),
                    ("Reserved2", ctypes.c_size_t * 16),
                    ("Reserved3", ctypes.c_size_t * 2)
                ]
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
            for proc in (app_proc, api_proc):
                if proc is not None:
                    kernel32.AssignProcessToJobObject(job, int(proc._handle))

        # Arrancar workers en hilos secundarios ANTES de abrir pywebview
        if api_enabled:
            def _api_health_worker():
                health_url = f"{api_url}/health"
                ok = wait_for_health(health_url, timeout=15.0)
                if ok:
                    write_api_status(True, api_url)
                    LOGGER.info("API saludable en %s", api_url)
                else:
                    reason = "API no saludable tras 15s"
                    write_api_status(False, api_url, reason=reason)
                    LOGGER.warning(reason)
                    notify_user(
                        "MovilidadESII - API",
                        "La aplicación está abierta, pero la API no arrancó correctamente.\n"
                        "Algunas funciones pueden no estar disponibles.\n\n"
                        f"Consulta {API_LOG_PATH} y {API_STATUS_PATH}"
                    )
            threading.Thread(target=_api_health_worker, daemon=True).start()

        def _streamlit_check():
            if not wait_for_http(url, timeout=15.0):
                LOGGER.error("Streamlit no respondió en %s", url)
                notify_user(
                    "MovilidadESII - Streamlit",
                    "Streamlit tardó en arrancar. Si el navegador no carga, consulta app.log."
                )
        threading.Thread(target=_streamlit_check, daemon=True).start()

        if not api_enabled:
            reason = api_disabled_reason or "API deshabilitada."
            write_api_status(False, api_url, reason=reason)
            LOGGER.warning(reason)

        # Abrir ventana nativa pywebview en el hilo principal (requisito de pywebview)
        LOGGER.info("Abriendo ventana nativa en %s", url)

        _webview_ok = False
        try:
            import webview as _wv
            import json as _json_cfg

            _CFG_PATH = str(CONFIG_PATH)

            def _read_cfg():
                try:
                    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
                        return _json_cfg.load(_f)
                except Exception:
                    return {}

            def _write_cfg(data):
                try:
                    existing = _read_cfg()
                    existing.update(data)
                    with open(_CFG_PATH, "w", encoding="utf-8") as _f:
                        _json_cfg.dump(existing, _f, indent=2)
                except Exception:
                    pass

            # pywebview ≥ 5.x: FileDialog.OPEN / FileDialog.SAVE
            # pywebview < 5.x: OPEN_DIALOG / SAVE_DIALOG (deprecado)
            _FD = getattr(_wv, "FileDialog", None)
            _OPEN_DIALOG = getattr(_FD, "OPEN", None) if _FD else getattr(_wv, "OPEN_DIALOG")
            _SAVE_DIALOG = getattr(_FD, "SAVE", None) if _FD else getattr(_wv, "SAVE_DIALOG")

            class _API:
                def pick_file(self):
                    windows = _wv.windows
                    if not windows:
                        return {"ok": False, "reason": "no_window"}
                    result = windows[0].create_file_dialog(
                        _OPEN_DIALOG,
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
                    import base64 as _b64
                    import os
                    from urllib.parse import unquote
                    windows = _wv.windows
                    if not windows:
                        return {"ok": False, "reason": "no_window"}
                    ext = os.path.splitext(filename)[1].lower() or ".png"
                    file_types = (f"Imagen (*{ext})", "Todos los archivos (*.*)")
                    result = windows[0].create_file_dialog(
                        _SAVE_DIALOG,
                        save_filename=filename,
                        file_types=file_types,
                    )
                    if not result:
                        return {"ok": False, "reason": "cancelled"}
                    save_path = result if isinstance(result, str) else result[0]

                    # Data URLs tienen dos formatos:
                    #   data:<mime>;base64,<datos>           → PNG, JPG, etc.
                    #   data:<mime>;charset=utf-8,<datos>    → SVG (URL-encoded)
                    header, _, payload = base64_data.partition(",")
                    if not payload and header:
                        payload, header = header, ""
                    if ";base64" in header:
                        with open(save_path, "wb") as f:
                            f.write(_b64.b64decode(payload))
                    else:
                        # Texto URL-encoded (SVG, etc.)
                        with open(save_path, "w", encoding="utf-8", newline="") as f:
                            f.write(unquote(payload))
                    return {"ok": True, "path": save_path}

                def save_zoom(self, level):
                    _write_cfg({"zoom": float(level)})
                    return {}

            _ZOOM_JS = """
(function() {
    if (window.__zoomHandlerReady) return;
    window.__zoomHandlerReady = true;
    var _cur = 1.0;

    function applyZoom(cur) {
        _cur = cur;

        // =========================
        // ZOOM BASE
        // =========================
        document.body.style.zoom = cur === 1.0 ? '' : cur;
        document.body.style.minHeight = cur < 1.0 ? 'calc(100% / ' + cur + ')' : '';
        document.body.style.overflow = cur < 1.0 ? 'hidden' : '';
        document.documentElement.style.overflow = cur < 1.0 ? 'hidden' : '';

        try {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.save_zoom(cur);
            }
        } catch(e) {}

        // =========================
        // GLOBAL
        // =========================
        var globalFix = document.getElementById('__global_layout_fix');
        if (!globalFix) {
            globalFix = document.createElement('style');
            globalFix.id = '__global_layout_fix';
            document.head.appendChild(globalFix);
        }

        globalFix.textContent = `
            html, body {
                height: 100% !important;
                min-height: 100% !important;
            }

            [data-testid="stAppViewContainer"] {
                min-height: calc(100vh / ${cur}) !important;
            }

            [data-testid="stMain"] {
                min-height: calc(100vh / ${cur}) !important;
            }

            [data-testid="stMainBlockContainer"] {
                min-height: calc(100vh / ${cur}) !important;
            }
        `;

        // =========================
        // MAPA 
        // =========================
        setTimeout(function() {

            var mapFrame = null, maxH = 0;
            document.querySelectorAll('iframe').forEach(function(f) {
                if (f.offsetHeight > maxH) {
                    maxH = f.offsetHeight;
                    mapFrame = f;
                }
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

            if (!window.__mapNatPadH) {
                var _mbc = document.querySelector('[data-testid="stMainBlockContainer"]');
                if (_mbc) {
                    var _s = getComputedStyle(_mbc);
                    var _pl = parseFloat(_s.paddingLeft) || 0;
                    var _pr = parseFloat(_s.paddingRight) || 0;
                    window.__mapNatPadH = Math.max(_pl, _pr, 8);
                } else {
                    window.__mapNatPadH = 16;
                }
            }

            var padH = window.__mapNatPadH;
            var marginH = 'calc(' + padH + 'px / ' + cur + ')';

            mapFrame.setAttribute('data-map-frame', '1');

            var el = mapFrame.parentElement;
            while (el && el !== document.body) {
                el.setAttribute('data-map-wrap', '1');
                el = el.parentElement;
            }

            styleEl.textContent =
                '[data-map-wrap][data-testid="stMain"]' +
                ' { position: relative !important; overflow: hidden !important; } ' +

                '[data-map-wrap][data-testid="stMainBlockContainer"]' +
                ' { position: absolute !important; inset: 0 !important;' +
                '   height: auto !important;' +
                '   padding: 0 ' + marginH + ' !important;' +
                '   box-sizing: border-box !important;' +
                '   overflow: hidden !important; } ' +

                '[data-map-frame] { height: 100% !important; } ' +

                '[data-map-wrap]' +
                ':not([data-testid="stMainBlockContainer"])' +
                ':not([data-testid="stMain"])' +
                ':not([data-testid="stAppViewContainer"])' +
                ':not([data-testid="stApp"])' +
                ' { height: 100% !important; overflow: visible !important; } ' +

                '[data-testid="stSidebar"] { min-height: calc(100vh / ' + cur + ') !important; overflow-x: hidden !important; overflow-y: visible !important; } ' +
                '[data-testid="stSidebar"] > div:first-child { overflow: visible !important; height: auto !important; min-height: 0 !important; }';

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

        if (e.deltaY < 0) cur = Math.min(+(cur + 0.1).toFixed(1), 1.1);
        else cur = Math.max(+(cur - 0.1).toFixed(1), 0.8);

        applyZoom(cur);
    }, { passive: false });

    document.addEventListener('keydown', function(e) {
        if (!e.ctrlKey) return;

        var k = e.key;
        var c = e.keyCode || e.which;

        var zoomIn  = (k === '+' || k === '=' || k === 'Add' || c === 187 || c === 107);
        var zoomOut = (k === '-' || k === 'Subtract' || c === 189 || c === 109);
        var zoomRst = (k === '0' || c === 48);

        if (!zoomIn && !zoomOut && !zoomRst) return;

        e.preventDefault();

        var cur = _cur;

        if (zoomIn)  cur = Math.min(+(cur + 0.1).toFixed(1), 1.1);
        if (zoomOut) cur = Math.max(+(cur - 0.1).toFixed(1), 0.9);
        if (zoomRst) cur = 1.0;

        applyZoom(cur);
    });

})();
"""

            if wait_for_http(url, timeout=30.0):
                _cfg = _read_cfg()
                _init_zoom = max(0.8, min(1.1, float(_cfg.get("zoom", 1.0))))
                _was_maximized = bool(_cfg.get("maximized", True))
                _kw = {}
                if "x" in _cfg and "y" in _cfg:
                    _x, _y = int(_cfg["x"]), int(_cfg["y"])
                    _w = int(_cfg.get("width", 1400))
                    _h = int(_cfg.get("height", 900))
                    # Validar que la ventana queda al menos parcialmente visible
                    # en el escritorio virtual (multi-monitor).  GetSystemMetrics:
                    #   76=SM_XVIRTUALSCREEN, 77=SM_YVIRTUALSCREEN
                    #   78=SM_CXVIRTUALSCREEN, 79=SM_CYVIRTUALSCREEN
                    _sm = ctypes.windll.user32.GetSystemMetrics
                    _vx, _vy = _sm(76), _sm(77)
                    _vw, _vh = _sm(78), _sm(79)
                    _on_screen = (
                        _x < _vx + _vw - 50 and _y < _vy + _vh - 50
                        and _x > _vx - _w + 50 and _y > _vy - _h + 50
                    )
                    if _on_screen:
                        _kw["x"], _kw["y"] = _x, _y

                _win = _wv.create_window(
                    "Movilidad ESII", url,
                    width=int(_cfg.get("width", 1400)),
                    height=int(_cfg.get("height", 900)),
                    min_size=(800, 600),
                    resizable=True,
                    js_api=_API(),
                    background_color='#FFFFFF',
                    **_kw,
                )

                if _was_maximized:
                    _win.events.shown += lambda: _win.maximize()

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
                        _is_max = wp.showCmd == 3
                        _state: dict = {"maximized": _is_max}
                        # Cuando la ventana está maximizada, rcNormal contiene la
                        # posición de restauración virtual de Win32 (-32768, 32767),
                        # que no corresponde a ninguna coordenada visible en pantalla.
                        # Solo guardamos x/y cuando la ventana está en estado normal.
                        if not _is_max:
                            _rx = wp.rcNormal.left
                            _ry = wp.rcNormal.top
                            _rw = wp.rcNormal.right  - wp.rcNormal.left
                            _rh = wp.rcNormal.bottom - wp.rcNormal.top
                            if _rw > 0 and _rh > 0:
                                _state.update({
                                    "x": _rx, "y": _ry,
                                    "width": _rw, "height": _rh,
                                })
                        _write_cfg(_state)
                    except Exception:
                        pass

                _win.events.closed += _save_window_state

                # -------------------------------------------------------
                # Bandeja del sistema (system tray)
                # Al pulsar X la ventana se oculta; el programa sigue
                # corriendo. Desde el icono de bandeja el usuario puede
                # restaurar la ventana o cerrar la app por completo.
                # -------------------------------------------------------
                try:
                    import pystray as _pystray
                    from PIL import Image as _PILImage

                    if getattr(sys, "frozen", False):
                        _ico_path = str(Path(sys.executable).parent / "MovilidadESII.ico")
                    else:
                        _ico_path = str(
                            Path(__file__).parent / "install_root" / "MovilidadESII.ico"
                        )
                    _tray_ref = [None]   # [pystray.Icon | None]
                    _quit_flag = [False]  # True → cierre real desde la bandeja

                    def _tray_stop():
                        if _tray_ref[0] is not None:
                            try:
                                _tray_ref[0].stop()
                            except Exception:
                                pass
                            _tray_ref[0] = None

                    def _tray_restore(icon, item):
                        """Restaurar ventana desde la bandeja."""
                        _tray_stop()
                        try:
                            _win.show()
                        except Exception:
                            pass

                    def _do_restore():
                        """Restaurar ventana desde el listener de segunda instancia."""
                        _tray_stop()
                        try:
                            _win.show()
                        except Exception:
                            pass

                    _restore_callback_holder[0] = _do_restore

                    def _tray_quit(icon, item):
                        """Cerrar aplicación completamente desde la bandeja."""
                        _quit_flag[0] = True
                        _tray_stop()
                        try:
                            _win.destroy()
                        except Exception:
                            pass

                    def _on_closing():
                        """
                        Intercepta el cierre de ventana (clic en X).
                        Si _quit_flag está activo, permite el cierre real.
                        Si no, oculta la ventana y crea el icono en la bandeja.
                        Devuelve False para cancelar el cierre real.
                        """
                        if _quit_flag[0]:
                            return  # Cierre real desde bandeja → no cancelar
                        _save_window_state()
                        if _tray_ref[0] is None:
                            try:
                                _img = _PILImage.open(_ico_path)
                                _menu = _pystray.Menu(
                                    _pystray.MenuItem(
                                        "Restaurar ventana",
                                        _tray_restore,
                                        default=True,
                                    ),
                                    _pystray.MenuItem(
                                        "Cerrar aplicación",
                                        _tray_quit,
                                    ),
                                )
                                _icon = _pystray.Icon(
                                    "MovilidadESII",
                                    _img,
                                    "Movilidad ESII",
                                    _menu,
                                )
                                _tray_ref[0] = _icon
                                threading.Thread(
                                    target=_icon.run, daemon=True
                                ).start()
                            except Exception as _te:
                                LOGGER.warning(
                                    "No se pudo crear icono de bandeja: %s", _te
                                )
                                return  # Sin bandeja → permite el cierre normal
                        threading.Timer(0.05, lambda: _win.hide()).start()
                        return False  # Cancela el cierre de la ventana

                    _win.events.closing += _on_closing
                    LOGGER.info("Bandeja del sistema configurada.")
                except ImportError:
                    LOGGER.warning(
                        "pystray no instalado — la X cerrará la app directamente."
                    )
                except Exception as _tray_err:
                    LOGGER.warning("Error configurando bandeja: %s", _tray_err)

                # JS del botón hamburguesa inyectado directamente en el contexto
                # principal de pywebview (sin iframe), así no necesita window.parent.
                # La guardia __sidebarToggleReady evita doble inicialización.
                _SIDEBAR_TOGGLE_JS = """
(function() {
    if (window.__sidebarToggleReady) return;
    window.__sidebarToggleReady = true;
    var BTN_ID = '__sidebar_expand_btn';

    function getSidebar() {
        return document.querySelector('[data-testid="stSidebar"]');
    }
    function isSidebarCollapsed() {
        var s = getSidebar();
        if (!s) return false;
        if (s.getAttribute('aria-expanded') === 'false') return true;
        var r = s.getBoundingClientRect();
        if (r.width < 50 || r.right <= 0) return true;
        return false;
    }
    function findToggleBtn() {
        var selectors = [
            '[data-testid="stSidebarCollapseButton"] button',
            '[data-testid="stSidebarCollapseButton"]',
            '[data-testid="stSidebarCollapsedControl"] button',
            '[data-testid="stSidebarCollapsedControl"]',
            'button[aria-label*="sidebar" i]',
            'button[aria-label*="panel" i]'
        ];
        for (var i = 0; i < selectors.length; i++) {
            var el = document.querySelector(selectors[i]);
            if (el) return el;
        }
        return null;
    }
    function syntheticClick(el) {
        try {
            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(function(t) {
                el.dispatchEvent(new MouseEvent(t, { bubbles: true, cancelable: true, view: window }));
            });
        } catch (e) {}
    }
    function expandSidebar() {
        var btn = findToggleBtn();
        if (btn) {
            try { btn.click(); } catch (e) {}
            syntheticClick(btn);
        }
        setTimeout(function() {
            var s = getSidebar();
            if (s && s.getAttribute('aria-expanded') === 'false') {
                s.setAttribute('aria-expanded', 'true');
            }
        }, 80);
    }
    function createBtn() {
        var btn = document.createElement('button');
        btn.id = BTN_ID;
        btn.title = 'Mostrar panel lateral';
        btn.innerHTML = '&#9776;';
        btn.style.cssText = 'position:fixed;top:8px;left:8px;z-index:99999;'
            + 'background:#262730;color:#fff;border:none;border-radius:6px;'
            + 'padding:6px 10px;font-size:18px;cursor:pointer;display:none;'
            + 'line-height:1;box-shadow:0 2px 6px rgba(0,0,0,.4)';
        btn.addEventListener('click', expandSidebar);
        document.body.appendChild(btn);
        return btn;
    }
    function update() {
        var btn = document.getElementById(BTN_ID) || createBtn();
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
        setInterval(update, 500);
    }
    start();
})();
"""

                def _inject_zoom():
                    try:
                        js = _ZOOM_JS.replace("var _cur = 1.0;", "var _cur = " + str(_init_zoom) + ";")
                        _win.evaluate_js(js)
                        _win.evaluate_js(_SIDEBAR_TOGGLE_JS)
                    except Exception:
                        pass

                _win.events.loaded += _inject_zoom
                _wv.start()  # Bloquea en el hilo principal hasta que el usuario cierra la ventana
                LOGGER.info("Ventana pywebview cerrada.")
                _webview_ok = True
            else:
                LOGGER.warning("Streamlit no arrancó en 30s — abriendo navegador.")
        except ImportError:
            LOGGER.warning("pywebview no instalado — abriendo navegador.")
        except Exception as e:
            LOGGER.error("Error pywebview: %s — abriendo navegador.", e)

        if not _webview_ok:
            # Fallback: abrir en navegador y usar watchdog para detectar cierre
            subprocess.Popen(
                ["rundll32", "url.dll,FileProtocolHandler", url],
                creationflags=NO_WINDOW,
            )

            GRACE_STARTUP      = 30           # s — gracia inicial antes de activar watchdog
            CHECK_INTERVAL     = 1            # s — latencia máxima de reacción al shutdown_event
            MAX_RUNTIME        = 8 * 60 * 60  # 8 h — límite absoluto de seguridad

            start_time        = time.time()

            LOGGER.info("=" * 60)
            LOGGER.info("Watchdog configurado (modo navegador):")
            LOGGER.info("  Gracia inicial          : %ds", GRACE_STARTUP)
            LOGGER.info("  Cierre pestaña          : ~7s (heartbeat 5s + grace 2s)")
            LOGGER.info("  Tiempo máx. ejecución   : %ds (%.1fh)", MAX_RUNTIME, MAX_RUNTIME / 3600)
            LOGGER.info("  Intervalo watchdog      : %ds", CHECK_INTERVAL)
            LOGGER.info("  API habilitada          : %s", api_enabled)
            LOGGER.info("  Cerrar manualmente      : crear %s/.shutdown", APPDATA_DIR)
            LOGGER.info("=" * 60)

            while True:

                # 1. Shutdown desde el servidor de control (cierre de pestaña detectado)
                if shutdown_event.is_set():
                    LOGGER.info("Shutdown recibido desde el servidor de control.")
                    break

                # 2. Streamlit terminó por sí solo
                if app_proc.poll() is not None:
                    LOGGER.info("Streamlit finalizó (rc=%s).", app_proc.returncode)
                    break

                # 3. Apagado manual por archivo .shutdown
                shutdown_file = APPDATA_DIR / ".shutdown"
                if shutdown_file.exists():
                    LOGGER.info("Archivo .shutdown detectado — cerrando.")
                    try:
                        shutdown_file.unlink()
                    except Exception:
                        pass
                    break

                now     = time.time()
                elapsed = now - start_time

                # 4. Límite de tiempo absoluto (seguridad)
                if elapsed > MAX_RUNTIME:
                    LOGGER.info("Tiempo máximo de ejecución alcanzado (%.1fs) — cerrando.", elapsed)
                    break

                # 5. Periodo de gracia inicial
                if elapsed <= GRACE_STARTUP:
                    LOGGER.debug("Gracia inicial: %.1fs restantes.", GRACE_STARTUP - elapsed)

                time.sleep(CHECK_INTERVAL)


    except Exception as exc:
        write_api_status(False, api_url, reason=str(exc))
        LOGGER.exception("Error iniciando procesos: %s", exc)
        raise
    finally:
        LOGGER.info("Deteniendo procesos...")

        # 1) Terminar todos los procesos hijos y sus árboles
        shutdown_processes(
            [app_proc, api_proc],
            ports=[app_port, api_port],
        )

        # 2) Cerrar archivos de log
        for logfile in (app_log, api_log):
            try:
                logfile.close()
            except Exception:
                pass

        # 3) Eliminar caché de Streamlit en disco
        for _cache_dir in (
            Path.home() / ".streamlit" / ".cache",
            Path.home() / ".streamlit" / "cache",
        ):
            if _cache_dir.exists():
                shutil.rmtree(_cache_dir, ignore_errors=True)
                LOGGER.info("Caché eliminada: %s", _cache_dir)

        LOGGER.info("Procesos detenidos.")
        # Forzar salida del launcher para evitar que hilos daemon lo retengan
        sys.exit(0)



def run_launcher() -> int:
    prepare_appdata_dirs()
    touch_initial_logs()
    setup_launcher_logging()
    LOGGER.info("MovilidadESII launcher %s iniciando.", LAUNCHER_VERSION)

    # En el primer arranque desde MSIX (Store), crea un acceso directo en el
    # escritorio. No-op para Inno (que ya lo crea) ni en modo desarrollo.
    try:
        from desktop_shortcut import ensure_msix_desktop_shortcut
        _ico = Path(sys.executable).parent / "MovilidadESII.ico"
        ensure_msix_desktop_shortcut(APPDATA_DIR, _ico if _ico.exists() else None)
    except Exception as _e:
        LOGGER.debug("desktop_shortcut skipped: %s", _e)

    if DEV_MODE:
        # Modo desarrollo: sin lock de instancia, sin verificación de instalación,
        # usa el Python que ejecuta este script directamente.
        LOGGER.info("Modo --dev: saltando lock de instancia y verificación de dependencias.")
        try:
            start_processes(api_enabled=True)
        except Exception as exc:
            LOGGER.exception("Fallo en modo dev: %s", exc)
            return 1
        return 0

    _start_restore_listener()   # crea el evento antes de adquirir el mutex
    lock_handle = single_instance_lock()
    if lock_handle is None and os.name == "nt":
        return 0
    exit_code = 0
    try:
        api_enabled, api_reason = ensure_installation()
        if not api_enabled:
            exit_code = 1
            LOGGER.warning("Modo degradado: %s", api_reason)
            notify_user(
                "MovilidadESII",
                f"{api_reason}\nConsulta {PIP_LOG_PATH} para más detalles.\n"
                "La app arrancará solo en modo lectura (Streamlit sin API)."
            )
        if DEMO_MODE:
            ensure_data_demo()
            write_demo_config()
        start_processes(api_enabled=api_enabled, api_disabled_reason=api_reason)
    except RuntimeError as exc:
        LOGGER.error("Launcher abortado: %s", exc)
        notify_user(
            "MovilidadESII",
            f"{exc}\nConsulta {LAUNCHER_LOG_PATH} para más detalles."
        )
        return 1
    except Exception as exc:
        LOGGER.exception("Fallo inesperado en el launcher: %s", exc)
        notify_user(
            "MovilidadESII",
            f"Error inesperado. Consulta {LAUNCHER_LOG_PATH}"
        )
        return 1
    finally:
        release_instance_lock(lock_handle)
    LOGGER.info("Launcher finalizado correctamente.")
    return exit_code


def main() -> int:
    return run_launcher()


if __name__ == "__main__":
    sys.exit(main())