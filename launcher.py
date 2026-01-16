import ctypes
import json
import logging
import os
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
    return Path(base) / "MovilidadUCLM"


APPDATA_DIR = get_appdata_dir()
LOG_DIR = APPDATA_DIR / "logs"
DATA_DEMO_DIR = APPDATA_DIR / "data_demo"
VENV_DIR = APPDATA_DIR / "venv"
PYTHON = VENV_DIR / "Scripts" / "python.exe"
CONFIG_PATH = APPDATA_DIR / "config.json"
API_STATUS_PATH = APPDATA_DIR / "api_status.json"
PID_FILE = APPDATA_DIR / ".pids"
LAUNCHER_LOG_PATH = LOG_DIR / "launcher.log"
APP_LOG_PATH = LOG_DIR / "app.log"
API_LOG_PATH = LOG_DIR / "api.log"
PIP_LOG_PATH = LOG_DIR / "pip_install.log"
LOCK_NAME = "Global\\MovilidadUCLM_Launcher"

NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = subprocess.CREATE_NO_WINDOW

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
else:
    ROOT = Path(__file__).resolve().parent

LOGGER = logging.getLogger("movilidad_launcher")
LOGGER.addHandler(logging.NullHandler())


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
    demo_path = ROOT / "config.demo.json"
    if not demo_path.exists():
        LOGGER.warning("config.demo.json no existe en %s", ROOT)
        return
    
    try:
        demo_config = json.loads(demo_path.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.error("No se pudo leer config.demo.json: %s", exc)
        return
    
    # Si config.json ya existe y está mal, eliminarlo primero
    if CONFIG_PATH.exists():
        try:
            CONFIG_PATH.unlink()
            LOGGER.info("config.json anterior eliminado para regenerarlo")
        except Exception as exc:
            LOGGER.warning("No se pudo eliminar config.json anterior: %s", exc)
    
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
    if not VENV_DIR.exists():
        raise RuntimeError(f"El entorno virtual no existe en {VENV_DIR}. Reinstala la aplicación.")
    if not PYTHON.exists():
        raise RuntimeError("No se encuentra python.exe dentro del entorno virtual.")
    installer_marker = APPDATA_DIR / ".installer_complete"
    LOGGER.debug("Verificando dependencias en %s", PYTHON)
    def _run_import(code: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(PYTHON), "-c", code],
            capture_output=True,
            text=True,
            timeout=12
        )
    try:
        if installer_marker.exists():
            result = _run_import("import streamlit, flask")
            if result.returncode != 0:
                details = (result.stderr or result.stdout or "Sin detalles").strip()
                raise RuntimeError(
                    f"Faltan dependencias: {details}. "
                    f"Consulta {PIP_LOG_PATH}."
                )
            LOGGER.debug("Dependencias garantizadas por el instalador.")
            return True, None
        LOGGER.warning(".installer_complete ausente; asegurar dependencias mínimas.")
        result = _run_import("import streamlit")
    except Exception as exc:
        raise RuntimeError(f"No se pudo ejecutar python del entorno virtual: {exc}") from exc
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
            time.sleep(0.25)
    return False


def wait_for_http(url: str, timeout: float = 30.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status in (200, 302):
                    return True
        except Exception:
            time.sleep(0.25)
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
                str(PYTHON), "-m", "streamlit", "run", "my_app.py",
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
        LOGGER.info("Esperando que Streamlit responda en %s", url)

        if not wait_for_http(url, timeout=30.0):
            LOGGER.error("Streamlit no respondió en %s", url)
            notify_user(
                "MovilidadUCLM - Streamlit",
                "Streamlit no pudo arrancar. Consulta app.log en AppData."
            )
            raise RuntimeError("Streamlit no arrancó correctamente.")

        LOGGER.info("Abriendo navegador en %s", url)
        subprocess.Popen(
            ["rundll32", "url.dll,FileProtocolHandler", url],
            creationflags=NO_WINDOW,
        )

        api_ok_event = threading.Event()

        if api_enabled:
            LOGGER.info("Iniciando API en 127.0.0.1:%s", api_port)
            api_proc = subprocess.Popen(
                [str(PYTHON), "api.py"],
                cwd=str(ROOT),
                env=env,
                stdout=api_log,
                stderr=api_log,
                creationflags=NO_WINDOW,
            )

            PID_FILE.write_text(f"{api_proc.pid}\n{app_proc.pid}\n", encoding="utf-8")

            def _api_health_worker():
                health_url = f"{api_url}/health"
                ok = wait_for_health(health_url, timeout=20.0)
                if ok:
                    api_ok_event.set()
                    write_api_status(True, api_url)
                    LOGGER.info("API saludable en %s", api_url)
                else:
                    reason = "API no saludable tras 20s"
                    write_api_status(False, api_url, reason=reason)
                    LOGGER.warning(reason)
                    notify_user(
                        "MovilidadUCLM - API",
                        "La aplicación está abierta, pero la API no arrancó correctamente.\n"
                        "Algunas funciones pueden no estar disponibles.\n\n"
                        f"Consulta {API_LOG_PATH} y {API_STATUS_PATH}"
                    )

            threading.Thread(target=_api_health_worker, daemon=True).start()
        else:
            reason = api_disabled_reason or "API deshabilitada."
            write_api_status(False, api_url, reason=reason)
            PID_FILE.write_text(f"{app_proc.pid}\n", encoding="utf-8")
            LOGGER.warning(reason)

        GRACE_STARTUP = 20
        IDLE_TIMEOUT = 30
        start_time = time.time()
        last_seen = time.time()
        LOGGER.info("Monitor de inactividad activo.")

        while True:
            if app_proc.poll() is not None:
                LOGGER.info("Streamlit finalizó.")
                break

            if api_enabled and api_ok_event.is_set():
                ts = get_last_ping_ts(api_port)
                now = time.time()
                if ts is not None:
                    last_seen = ts
                if now - start_time > GRACE_STARTUP and now - last_seen > IDLE_TIMEOUT:
                    LOGGER.info("Sin pings del API, cerrando.")
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
    LOGGER.info("MovilidadUCLM launcher %s iniciando.", LAUNCHER_VERSION)
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
                "MovilidadUCLM",
                f"{api_reason}\nConsulta {PIP_LOG_PATH} para más detalles.\n"
                "La app arrancará solo en modo lectura (Streamlit sin API)."
            )
        ensure_data_demo()
        write_demo_config()
        start_processes(api_enabled=api_enabled, api_disabled_reason=api_reason)
    except RuntimeError as exc:
        LOGGER.error("Launcher abortado: %s", exc)
        notify_user(
            "MovilidadUCLM",
            f"{exc}\nConsulta {LAUNCHER_LOG_PATH} para más detalles."
        )
        return 1
    except Exception as exc:
        LOGGER.exception("Fallo inesperado en el launcher: %s", exc)
        notify_user(
            "MovilidadUCLM",
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
