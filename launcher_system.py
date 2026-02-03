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
DATA_DEMO_DIR = APPDATA_DIR / "data_demo"
# Legacy: el instalador antiguo creaba un venv en AppData. Ya no lo usamos,
# pero lo dejamos para no romper rutas en logs / mensajes.
VENV_DIR = APPDATA_DIR / "venv"

# Python a usar para lanzar Streamlit y la API: se resuelve dinámicamente
# desde el Python del sistema (PATH/py launcher/registro), no desde AppData.
_PYTHON_EXE: Path | None = None
CONFIG_PATH = APPDATA_DIR / "config.json"
API_STATUS_PATH = APPDATA_DIR / "api_status.json"
PID_FILE = APPDATA_DIR / ".pids"
LAUNCHER_LOG_PATH = LOG_DIR / "launcher.log"
APP_LOG_PATH = LOG_DIR / "app.log"
API_LOG_PATH = LOG_DIR / "api.log"
PIP_LOG_PATH = LOG_DIR / "pip_install.log"
LOCK_NAME = "Global\\MovilidadESII_Launcher"

NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = subprocess.CREATE_NO_WINDOW

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
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

def _venv_python_exe() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


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
    Preferimos el venv si existe (porque ahí están las dependencias de la app).
    Si no existe o está roto, usamos Python del sistema.
    """
    vpy = _venv_python_exe()
    if _python_works(vpy):
        LOGGER.debug("Python runtime seleccionado (venv): %s", vpy)
        return vpy.resolve()

    # fallback
    py = get_system_python()
    LOGGER.debug("Python runtime seleccionado (system): %s", py)
    return py


def get_system_python() -> Path:
    """Resuelve un Python 3.12.x del sistema (no el empaquetado en MovilidadESII)."""
    global _PYTHON_EXE
    if _PYTHON_EXE is not None:
        return _PYTHON_EXE

    blocked_base = APPDATA_DIR  # no queremos usar python dentro de MovilidadESII
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
        # No usar el python instalado en la carpeta de la propia app
        if _is_under(exe, blocked_base):
            continue
        if _python_is_312(exe):
            _PYTHON_EXE = exe.resolve()
            LOGGER.debug("Python del sistema seleccionado: %s", _PYTHON_EXE)
            return _PYTHON_EXE

    raise RuntimeError(
        "No se encontró Python 3.12 del sistema (fuera de MovilidadESII). "
        "Instala Python 3.12.x y marca 'Add to PATH' o instala el Python Launcher (py)."
    )


def prepare_appdata_dirs() -> None:
    for folder in (APPDATA_DIR, LOG_DIR, APPDATA_DIR / "cache", DATA_DEMO_DIR):
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
    True si hay alguna conexión TCP ESTABLISHED hacia el puerto de Streamlit.
    En Windows lo detectamos con netstat.
    """
    if os.name != "nt":
        return True  # en otros SO no apagamos por este criterio

    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            creationflags=NO_WINDOW,
        )
    except Exception:
        return True  # si falla netstat, no cerramos

    needle = f":{app_port}"
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("TCP"):
            continue
        parts = line.split()
        # Formato típico: TCP 127.0.0.1:8501 127.0.0.1:xxxxx ESTABLISHED PID
        if len(parts) < 4:
            continue
        local_addr = parts[1]
        state = parts[3].upper()
        if local_addr.endswith(needle) and state == "ESTABLISHED":
            return True

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
        
        # Abrir navegador INMEDIATAMENTE (esperará a que Streamlit esté listo)
        LOGGER.info("Abriendo navegador en %s", url)
        subprocess.Popen(
            ["rundll32", "url.dll,FileProtocolHandler", url],
            creationflags=NO_WINDOW,
        )

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
            PID_FILE.write_text(f"{api_proc.pid}\n{app_proc.pid}\n", encoding="utf-8")

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
            PID_FILE.write_text(f"{app_proc.pid}\n", encoding="utf-8")
            LOGGER.warning(reason)

        GRACE_STARTUP = 10
        IDLE_TIMEOUT = 10

        start_time = time.time()
        last_seen = time.time()
        seen_client_once = False

        LOGGER.info("Monitor: cerrar cuando se cierre la pestaña (sin conexiones).")

        while True:
            if app_proc.poll() is not None:
                LOGGER.info("Streamlit finalizó.")
                break

            now = time.time()

            # No empezamos a cerrar hasta que:
            # 1) haya pasado el arranque
            # 2) y hayamos visto al menos una conexión real de navegador alguna vez
            if now - start_time > GRACE_STARTUP:
                active = has_active_streamlit_client(app_port)

                if active:
                    last_seen = now
                    seen_client_once = True
                else:
                    if seen_client_once and (now - last_seen > IDLE_TIMEOUT):
                        LOGGER.info("Sin pestañas conectadas durante %ss, cerrando.", IDLE_TIMEOUT)
                        break

            time.sleep(2)


    except Exception as exc:
        write_api_status(False, api_url, reason=str(exc))
        LOGGER.exception("Error iniciando procesos: %s", exc)
        raise
    finally:
        for proc in (app_proc, api_proc):
            if proc is None:
                continue
            try:
                proc.terminate()
            except Exception:
                pass
        time.sleep(1)
        for proc in (app_proc, api_proc):
            if proc is None:
                continue
            try:
                if proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
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
