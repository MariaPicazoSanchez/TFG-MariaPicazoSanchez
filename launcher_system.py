import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
def start_control_server(port: int, token: str, shutdown_event: threading.Event):

    import time
    import logging
    open_tabs = set()
    pending_close = dict()  # tab_id -> timestamp de cierre programado
    last_close_ts = [0.0]  # mutable para acceso desde handler
    CLOSE_DEBOUNCE = 1.0
    # Tiempo que se espera antes de confirmar un cierre de pestaña.
    # Debe ser mayor que el tiempo de recarga de página (F5) para evitar
    # falsos positivos: una recarga envía /close y luego /open en ~2-4s.
    PENDING_CLOSE_GRACE = 5.0
    # Guard: cleanup_pending NO puede disparar shutdown hasta que al menos
    # una pestaña haya enviado /open.  Evita cierre prematuro al arrancar,
    # cuando open_tabs está vacío simplemente porque el navegador aún no abrió.
    first_open_received = [False]   # [bool] mutable para acceso desde el hilo
    LOGGER = logging.getLogger("movilidad_launcher")

    class Handler(BaseHTTPRequestHandler):

        def end_headers(self):
            """Añade cabeceras CORS a todas las respuestas para permitir
            que el iframe de Streamlit (puerto distinto) haga fetch al
            servidor de control."""
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            super().end_headers()

        def do_OPTIONS(self):
            """Responde a las preflight CORS que el navegador envía antes
            de cada fetch cross-origin."""
            self.send_response(204)
            self.end_headers()

        def do_POST(self):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if qs.get("token", [""])[0] != token:
                self.send_response(403); self.end_headers(); return
            now = time.time()
            if u.path == "/open":
                tab_id = qs.get("id", [""])[0]
                if tab_id:
                    open_tabs.add(tab_id)
                    first_open_received[0] = True   # armar el watchdog de cierre
                    # Si estaba pendiente de cierre, cancelar
                    if tab_id in pending_close:
                        del pending_close[tab_id]
                        LOGGER.info(f"/open cancela pending_close: {tab_id}")
                    LOGGER.info(f"/open recibido: {tab_id}. Pestañas abiertas: {len(open_tabs)}")
                self.send_response(200); self.end_headers(); return
            elif u.path == "/close":
                tab_id = qs.get("id", [""])[0]
                if tab_id and tab_id in open_tabs:
                    # No eliminar inmediatamente, marcar como pendiente
                    pending_close[tab_id] = now + PENDING_CLOSE_GRACE
                    LOGGER.info(f"/close recibido: {tab_id}. Marcado como pending_close hasta {pending_close[tab_id]:.1f}")
                else:
                    LOGGER.info(f"/close recibido para id desconocido: {tab_id}")
                last_close_ts[0] = now + CLOSE_DEBOUNCE
                self.send_response(200); self.end_headers(); return
            elif u.path == "/shutdown":
                shutdown_event.set()
                LOGGER.info("/shutdown recibido")
                self.send_response(200); self.end_headers(); return
            else:
                self.send_response(404); self.end_headers(); return

        def log_message(self, *args):  # silenciar logs del HTTPServer
            pass

    def cleanup_pending():
        while True:
            now = time.time()
            to_remove = [tid for tid, ts in pending_close.items() if ts <= now]
            for tid in to_remove:
                if tid in open_tabs:
                    open_tabs.remove(tid)
                    LOGGER.info(f"pending_close ejecutado: {tid}. Pestañas abiertas: {len(open_tabs)}")
                del pending_close[tid]

            # ── Cierre inmediato cuando no queda ninguna pestaña ──────────────
            # Requisito: que la pestaña haya emitido al menos un /open antes.
            # Sin este guard, al arrancar (open_tabs={}, pending_close={}) la
            # condición sería verdadera desde el primer tick y cerraría la app
            # antes de que el navegador siquiera abriera la página.
            if first_open_received[0] and open_tabs == set() and not pending_close:
                LOGGER.info(
                    "Todas las pestañas cerradas y sin gracias pendientes "
                    "→ señal de shutdown inmediata."
                )
                shutdown_event.set()
                return  # el hilo ya no es necesario

            time.sleep(1)

    httpd = HTTPServer(("127.0.0.1", port), Handler)
    httpd.open_tabs = open_tabs
    httpd.pending_close = pending_close
    httpd.first_open_received = first_open_received
    httpd.last_close_ts = last_close_ts
    httpd.CLOSE_DEBOUNCE = CLOSE_DEBOUNCE
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    t2 = threading.Thread(target=cleanup_pending, daemon=True)
    t2.start()
    return httpd
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

LAUNCHER_VERSION = "envfix-2026-01-05-1.0"


def get_appdata_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "MovilidadESII"


APPDATA_DIR = get_appdata_dir()
LOG_DIR = APPDATA_DIR / "logs"
DATA_DEMO_DIR = APPDATA_DIR / "data"
# Python embebido instalado por el installer (preferido)
PYTHON_DIR = APPDATA_DIR / "runtime" / "python"

# Python a usar para lanzar Streamlit y la API: preferimos el embebido,
# fallback al Python del sistema si el embebido no existe.
_PYTHON_EXE: Path | None = None
CONFIG_PATH = APPDATA_DIR / "config.json"
API_STATUS_PATH = APPDATA_DIR / "api_status.json"
LAUNCHER_LOG_PATH = LOG_DIR / "launcher.log"
APP_LOG_PATH = LOG_DIR / "app.log"
API_LOG_PATH = LOG_DIR / "api.log"
PIP_LOG_PATH = LOG_DIR / "pip_install.log"
LOCK_NAME = "Global\\MovilidadESII_Launcher"

NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = subprocess.CREATE_NO_WINDOW

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


def _is_under(child: Path, parent: Path) -> bool:
    """Devuelve True si child está dentro de parent (resolviendo rutas)."""
    try:
        child_r = child.resolve()
        parent_r = parent.resolve()
        return os.path.commonpath([str(child_r), str(parent_r)]) == str(parent_r)
    except Exception:
        return False


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


def get_runtime_python() -> Path:
    """
    Preferimos el Python embebido instalado por el installer.
    Si no existe o está roto, usamos Python del sistema.
    """
    # Python embebido instalado por el installer
    embedded_py = APPDATA_DIR / "runtime" / "python" / "python.exe"
    if _python_works(embedded_py):
        LOGGER.debug("Python runtime seleccionado (embebido): %s", embedded_py)
        return embedded_py.resolve()

    # fallback al Python del sistema
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
    for folder in (APPDATA_DIR, LOG_DIR, DATA_DEMO_DIR):
        folder.mkdir(parents=True, exist_ok=True)


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
        LOGGER.warning("Ya hay otra instancia en ejecución, saliendo.")
        return None
    LOGGER.debug("Mutex de instancia adquirido.")
    return handle


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
    # Si config.json ya existe y es válido, no regenerar
    if CONFIG_PATH.exists():
        try:
            existing = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if existing and "excel_path" in existing:
                LOGGER.debug("config.json ya existe y es válido, omitiendo regeneración")
                return
        except Exception:
            pass  # Si falla la lectura, regenerar
    
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

def has_active_streamlit_client(app_port: int) -> bool:
    """
    True si hay alguna conexión TCP ESTABLISHED hacia el puerto de Streamlit
    Y además el servidor está respondiendo activamente a peticiones.
    
    Verificamos:
    1. Conexiones TCP ESTABLISHED en netstat
    2. Que el servidor responde a peticiones HTTP (heartbeat)
    
    El servidor de Streamlit responde aunque el usuario esté inactivo,
    while hay connections TCP ESTABLISHED.
    """
    if os.name != "nt":
        return False

    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            creationflags=NO_WINDOW,
            timeout=3,
        )
    except Exception as e:
        LOGGER.debug("netstat falló (%s), asumiendo sin clientes", e)
        return False

    port_str = f":{app_port}"
    tcp_pids = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_addr = parts[1]
        state = parts[3] if len(parts) > 3 else ""
        pid = parts[4]
        if port_str in local_addr and "127.0.0.1" in local_addr and state == "ESTABLISHED":
            tcp_pids.add(pid)

    if not tcp_pids:
        LOGGER.debug("No hay conexiones TCP en puerto %d", app_port)
        return False

    # Refuerzo: comprobar que al menos un PID corresponde a un navegador conocido
    browser_names = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe"]
    browser_found = False
    try:
        tasklist = subprocess.check_output(["tasklist", "/FO", "CSV", "/NH"], text=True, creationflags=NO_WINDOW, timeout=3)
        for line in tasklist.splitlines():
            for bname in browser_names:
                if f'"{bname}"' in line:
                    # CSV: "imagename","pid",...
                    fields = line.split(",")
                    if len(fields) > 1:
                        pid = fields[1].strip('"')
                        if pid in tcp_pids:
                            browser_found = True
                            break
            if browser_found:
                break
    except Exception as e:
        LOGGER.debug("tasklist falló (%s), asumiendo sin browser", e)

    if not browser_found:
        LOGGER.debug("No hay navegador asociado a conexiones TCP en puerto %d", app_port)
        return False

    # Si hay conexiones TCP y navegador, verificar que el servidor responde
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{app_port}/_stcore/health", timeout=2) as r:
            if r.status in (200, 401):
                LOGGER.debug("Clientes activos: navegador detectado y servidor respondiendo")
                return True
    except Exception:
        pass

    LOGGER.debug("Puerto %d tiene conexiones TCP y navegador, pero servidor no responde", app_port)
    return False


def get_last_ping_ts(api_port: int) -> float | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/last_ping", timeout=2) as r:
            if r.status != 200:
                return None
            body = r.read().decode("utf-8", errors="ignore")
            data = json.loads(body)
            ts = data.get("ts")
            return float(ts) if ts is not None else None
    except Exception:
        return None


def start_processes(api_enabled: bool = True, api_disabled_reason: str | None = None) -> None:
    py = get_runtime_python()

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

    # --- CONTROL SERVER PARA SHUTDOWN EXPLÍCITO ---
    shutdown_event = threading.Event()
    control_port = find_free_port()
    shutdown_token = secrets.token_urlsafe(24)
    control_httpd = start_control_server(control_port, shutdown_token, shutdown_event)
    env_app["CONTROL_PORT"] = str(control_port)
    env_app["SHUTDOWN_TOKEN"] = shutdown_token


    try:
        LOGGER.info("Iniciando Streamlit en 127.0.0.1:%s", app_port)
        app_proc = subprocess.Popen(
            [
                str(py), "-m", "streamlit", "run", "my_app.py",
                "--server.address=127.0.0.1",
                f"--server.port={app_port}",
                "--server.headless=true",
                "--server.fileWatcherType=none",
                "--server.runOnSave=false",
                "--browser.gatherUsageStats=false",
            ],
            cwd=str(ROOT),
            env=env_app,
            stdout=app_log,
            stderr=app_log,
            creationflags=NO_WINDOW,
        )

        url = f"http://127.0.0.1:{app_port}"
        (LOG_DIR / "last_url.txt").write_text(url, encoding="utf-8")

        # Arrancar API en paralelo si está habilitada
        api_ok_event = threading.Event()
        if api_enabled:
            LOGGER.info("Iniciando API en 127.0.0.1:%s", api_port)
            api_proc = subprocess.Popen(
                [str(py), "api.py"],
                cwd=str(ROOT),
                env=env,
                stdout=api_log,
                stderr=api_log,
                creationflags=NO_WINDOW,
            )

        # --- JOB OBJECT para evitar huérfanos en Windows ---
        if os.name == "nt":
            import ctypes
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

        # Abrir navegador INMEDIATAMENTE (esperará a que Streamlit esté listo)
        LOGGER.info("Abriendo navegador en %s", url)
        subprocess.Popen(
            ["rundll32", "url.dll,FileProtocolHandler", url],
            creationflags=NO_WINDOW,
        )

        if api_enabled:
            def _api_health_worker():
                health_url = f"{api_url}/health"
                ok = wait_for_health(health_url, timeout=15.0)
                if ok:
                    api_ok_event.set()
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

        # Verificar en segundo plano que Streamlit arrancó (sin bloquear)
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

        # ── Watchdog de heartbeat ──────────────────────────────────────────────
        # Dos mecanismos de cierre independientes:
        #
        # A) CIERRE INMEDIATO (ruta rápida, ~5-6 s):
        #    beforeunload JS → POST /close → PENDING_CLOSE_GRACE (5 s) → si ningún
        #    /open llega (no es un F5), cleanup_pending() llama shutdown_event.set()
        #    → el watchdog lo detecta en la siguiente iteración (CHECK_INTERVAL = 1 s)
        #    y termina los procesos.
        #
        # B) FALLBACK POR HEARTBEAT (para crashes de navegador sin beforeunload):
        #    Si no llega /ping en HEARTBEAT_TIMEOUT segundos, el watchdog cierra.
        # ──────────────────────────────────────────────────────────────────────
        GRACE_STARTUP      = 30           # s — esperar el primer ping antes de activar watchdog
        HEARTBEAT_TIMEOUT  = 120          # s — fallback: sin ping durante este tiempo → cerrar
        CHECK_INTERVAL     = 1            # s — latencia máxima de reacción al shutdown_event
        MAX_RUNTIME        = 8 * 60 * 60  # 8 h — límite absoluto de seguridad

        start_time        = time.time()
        last_seen_client  = time.time()  # se actualiza al recibir ping

        LOGGER.info("=" * 60)
        LOGGER.info("Watchdog de heartbeat configurado:")
        LOGGER.info("  Gracia inicial          : %ds", GRACE_STARTUP)
        LOGGER.info("  Ping JS cada            : ~20s")
        LOGGER.info("  Gracia F5 refresh       : 5s (PENDING_CLOSE_GRACE)")
        LOGGER.info("  Cierre tab → shutdown   : ~6s (ruta rápida, sin esperar heartbeat)")
        LOGGER.info("  Fallback sin ping       : %ds (~%d pings de margen)",
                    HEARTBEAT_TIMEOUT, HEARTBEAT_TIMEOUT // 20)
        LOGGER.info("  Tiempo máx. ejecución   : %ds (%.1fh)", MAX_RUNTIME, MAX_RUNTIME / 3600)
        LOGGER.info("  Intervalo watchdog      : %ds", CHECK_INTERVAL)
        LOGGER.info("  API habilitada          : %s", api_enabled)
        LOGGER.info("  Cerrar manualmente      : crear %s/.shutdown", APPDATA_DIR)
        LOGGER.info("=" * 60)

        while True:

            # 1. Shutdown explícito desde el navegador (botón "Cerrar aplicación")
            if shutdown_event.is_set():
                LOGGER.info("Shutdown explícito recibido desde el navegador.")
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

            # 5. Periodo de gracia inicial: esperar a que la API arranque y llegue
            #    el primer heartbeat antes de activar el watchdog.
            if elapsed <= GRACE_STARTUP:
                LOGGER.debug("Gracia inicial: %.1fs restantes.", GRACE_STARTUP - elapsed)
                time.sleep(CHECK_INTERVAL)
                continue

            # ── 6. Watchdog de heartbeat (fallback para crash de navegador) ──
            # La ruta rápida de cierre (beforeunload → /close → grace 5s →
            # cleanup_pending → shutdown_event.set()) ya fue gestionada en el
            # paso 1. Este bloque actúa solo si el navegador muere sin enviar
            # beforeunload (kill del proceso, caída del sistema, etc.).
            #
            # IMPORTANTE: last_ping es None si el navegador aún no envió ningún
            # /ping (arranque, carga lenta).  En ese caso no se activa el fallback
            # para evitar cierres prematuros antes de que la primera página cargue.
            last_ping = get_last_ping_ts(api_port)

            if last_ping is None:
                # Primera carga todavía: mantener last_seen_client al día para
                # que, cuando llegue el primer ping, ping_age empiece en 0.
                last_seen_client = now
                LOGGER.debug("Heartbeat: esperando primer ping del navegador.")
                time.sleep(CHECK_INTERVAL)
                continue

            if last_ping > last_seen_client:
                last_seen_client = last_ping

            ping_age    = now - last_seen_client
            open_tabs   = getattr(control_httpd, "open_tabs", set())

            if ping_age > HEARTBEAT_TIMEOUT:
                LOGGER.info(
                    "Fallback heartbeat: sin ping desde hace %.1fs "
                    "(timeout=%ds, pestañas_abiertas=%d) — cerrando.",
                    ping_age, HEARTBEAT_TIMEOUT, len(open_tabs),
                )
                break

            LOGGER.debug(
                "Heartbeat OK: último_ping hace %.1fs | timeout=%ds | "
                "pestañas_abiertas=%d",
                ping_age, HEARTBEAT_TIMEOUT, len(open_tabs),
            )
            time.sleep(CHECK_INTERVAL)


    except Exception as exc:
        write_api_status(False, api_url, reason=str(exc))
        LOGGER.exception("Error iniciando procesos: %s", exc)
        raise
    finally:
        LOGGER.info("Deteniendo procesos...")

        # 0) Apagar servidor de control
        try:
            control_httpd.shutdown()
            control_httpd.server_close()
        except Exception:
            pass

        def _taskkill_tree(pid: int) -> None:
            """Mata PID + descendencia (Windows)."""
            if os.name != "nt":
                return
            try:
                r = subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    text=True,
                    creationflags=NO_WINDOW,
                    timeout=8,
                )
                LOGGER.warning(
                    "taskkill /F /T PID=%s rc=%s stdout=%s stderr=%s",
                    pid, r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
                )
            except Exception as e:
                LOGGER.warning("taskkill falló para PID=%s: %s", pid, e)

        def _pids_on_port(port: int) -> set[int]:
            """PIDs que están LISTENING/ESTABLISHED en 127.0.0.1:port (Windows)."""
            if os.name != "nt":
                return set()
            try:
                out = subprocess.check_output(
                    ["netstat", "-ano", "-p", "TCP"],
                    text=True,
                    creationflags=NO_WINDOW,
                    timeout=3,
                )
            except Exception as e:
                LOGGER.debug("netstat falló al buscar PIDs por puerto (%s)", e)
                return set()

            port_str = f":{port}"
            pids: set[int] = set()
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                local_addr = parts[1]
                state = parts[3] if len(parts) > 3 else ""
                pid_s = parts[4]
                if "127.0.0.1" in local_addr and port_str in local_addr and state in ("LISTENING", "ESTABLISHED"):
                    try:
                        pids.add(int(pid_s))
                    except ValueError:
                        pass
            return pids

        # 1) Intento suave: terminate
        for proc in (app_proc, api_proc):
            if proc and proc.poll() is None:
                try:
                    LOGGER.debug("terminate() PID=%s", proc.pid)
                    proc.terminate()
                except Exception as e:
                    LOGGER.debug("terminate falló PID=%s: %s", proc.pid, e)

        # 2) Espera corta a cierre limpio
        for proc in (app_proc, api_proc):
            if proc:
                try:
                    proc.wait(timeout=3)
                except Exception:
                    pass

        # 3) Forzar cierre: matar árbol por PID del Popen
        pids: set[int] = set()
        for proc in (app_proc, api_proc):
            if proc and proc.pid:
                pids.add(int(proc.pid))

        # 4) Cinturón y tirantes: matar lo que esté usando los puertos elegidos
        try:
            pids |= _pids_on_port(app_port)
        except Exception:
            pass
        try:
            pids |= _pids_on_port(api_port)
        except Exception:
            pass

        # 5) taskkill /T a todo lo encontrado
        if os.name == "nt":
            for pid in sorted(pids):
                _taskkill_tree(pid)

        # 6) Cerrar logs
        for logfile in (app_log, api_log):
            try:
                logfile.close()
            except Exception:
                pass

        LOGGER.info("Procesos detenidos.")


def run_launcher() -> int:
    prepare_appdata_dirs()
    touch_initial_logs()
    setup_launcher_logging()
    LOGGER.info("MovilidadESII launcher %s iniciando.", LAUNCHER_VERSION)
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