import os
import shutil
import sys
import socket
import subprocess
import time
from pathlib import Path
import urllib.request
import json
import hashlib
import traceback
import threading

LAUNCHER_VERSION = "envfix-2026-01-05-1.0"


def single_instance_lock(port: int = 49231):
    """
    Evita que el launcher se ejecute dos veces.
    Si ya hay una instancia, sale silenciosamente.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
        return s  # mantenemos el socket abierto
    except OSError:
        # ya hay otra instancia
        os._exit(0)


NO_WINDOW = 0
if os.name == "nt":
    NO_WINDOW = subprocess.CREATE_NO_WINDOW

if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent  # carpeta del .exe
else:
    ROOT = Path(__file__).resolve().parent        # carpeta del .py



def get_appdata_dir() -> Path:
    base = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or str(Path.home())
    return Path(base) / "MovilidadUCLM"

APPDATA_DIR = get_appdata_dir()
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = APPDATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Venv dentro de AppData (escribible sin admin)
VENV_DIR = APPDATA_DIR / "venv"
PYTHON = VENV_DIR / "Scripts" / "python.exe"

# runtime files en AppData
PID_FILE = APPDATA_DIR / ".pids"
STAMP_FILE = APPDATA_DIR / ".deps.sha256"

# requirements y wheelhouse siguen junto al exe (Program Files)
REQ = ROOT / "requirements.lock.txt"
WHEELHOUSE = ROOT / "wheelhouse"


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_health(url: str, timeout: float = 15.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    body = r.read().decode("utf-8", errors="ignore")
                    # opcional: validar {"ok": true}
                    try:
                        data = json.loads(body)
                        if data.get("ok") is True:
                            return True
                        # si responde 200 pero formato distinto, también lo damos por bueno
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
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status in (200, 302):
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


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def get_system_python() -> str:
    # usa el python del sistema (el que te sale con "where python")
    p = shutil.which("python")
    if p:
        return p
    # fallback: py launcher
    py = shutil.which("py")
    if py:
        return py
    raise RuntimeError("No se encuentra Python en el sistema. Instala Python 3.12 y asegúrate de tenerlo en PATH.")


def ensure_venv():
    print("[launcher] ensure_venv: inicio", flush=True)
    
    # Verificar si la instalación ya se completó
    installer_marker = APPDATA_DIR / ".installer_complete"
    if installer_marker.exists():
        print("[launcher] ensure_venv: instalación completada por installer, saltando setup", flush=True)
        if PYTHON.exists():
            print(f"[launcher] ensure_venv: venv existe en {VENV_DIR}", flush=True)
            return
    
    # Si el venv ya existe y tiene pip, asumir que está completo
    if PYTHON.exists():
        print(f"[launcher] ensure_venv: venv ya existe en {VENV_DIR}", flush=True)
        # Verificar que streamlit está instalado (indica que las dependencias están)
        try:
            result = subprocess.run(
                [str(PYTHON), "-c", "import streamlit"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print("[launcher] ensure_venv: streamlit disponible, dependencias OK", flush=True)
                return
            else:
                print("[launcher] ensure_venv: streamlit NO disponible, instalando...", flush=True)
        except Exception as e:
            print(f"[launcher] ensure_venv: error verificando streamlit: {e}", flush=True)
    
    # Si llegamos aquí, necesitamos instalar
    stamp = STAMP_FILE
    req_hash = file_sha256(REQ)
    print(f"[launcher] ensure_venv: req_hash={req_hash}", flush=True)

    if not PYTHON.exists():
        print(f"[launcher] ensure_venv: creando venv en {VENV_DIR}", flush=True)
        system_python = get_system_python()
        print(f"[launcher] ensure_venv: usando system_python={system_python}", flush=True)
        subprocess.check_call([system_python, "-m", "venv", str(VENV_DIR)], creationflags=NO_WINDOW)
        print("[launcher] ensure_venv: venv creado", flush=True)

    # Si ya hay sello y coincide, NO reinstalar
    if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == req_hash:
        print("[launcher] ensure_venv: deps ya instaladas (sello coincide)", flush=True)
        return

    print("[launcher] ensure_venv: instalando/actualizando dependencias...", flush=True)
    # Log de instalación (por si algo falla)
    pip_log_path = LOG_DIR / "pip.log"
    with open(pip_log_path, "w", encoding="utf-8") as pip_log:
        print("[launcher] ensure_venv: upgrade pip...", flush=True)
        subprocess.check_call(
            [str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"],
            creationflags=NO_WINDOW,
            stdout=pip_log,
            stderr=pip_log
        )

        if WHEELHOUSE.exists():
            print(f"[launcher] ensure_venv: instalando desde wheelhouse {WHEELHOUSE}", flush=True)
            subprocess.check_call(
                [
                    str(PYTHON), "-m", "pip", "install",
                    "--no-index", "--find-links", str(WHEELHOUSE),
                    "-r", str(REQ)
                ],
                creationflags=NO_WINDOW,
                stdout=pip_log,
                stderr=pip_log
            )
        else:
            print("[launcher] ensure_venv: instalando desde PyPI", flush=True)
            subprocess.check_call(
                [str(PYTHON), "-m", "pip", "install", "-r", str(REQ)],
                creationflags=NO_WINDOW,
                stdout=pip_log,
                stderr=pip_log
            )

    stamp.write_text(req_hash, encoding="utf-8")
    print("[launcher] ensure_venv: completado", flush=True)




def write_demo_config():
    """
    Copia data_demo de Program Files a AppData (escribible) y genera config.json
    con rutas absolutas apuntando a AppData.
    """
    demo_json = ROOT / "config.demo.json"
    cfg_path = APPDATA_DIR / "config.json"
    
    print(f"[launcher] write_demo_config: demo_json={demo_json}", flush=True)
    print(f"[launcher] write_demo_config: cfg_path={cfg_path}", flush=True)
    
    # Copiar data_demo a AppData si no existe
    data_demo_src = ROOT / "data_demo"
    data_demo_dst = APPDATA_DIR / "data_demo"
    
    print(f"[launcher] write_demo_config: data_demo_src={data_demo_src} (existe: {data_demo_src.exists()})", flush=True)
    print(f"[launcher] write_demo_config: data_demo_dst={data_demo_dst} (existe: {data_demo_dst.exists()})", flush=True)
    
    if data_demo_src.exists() and not data_demo_dst.exists():
        print(f"[launcher] Copiando data_demo a AppData...", flush=True)
        try:
            shutil.copytree(data_demo_src, data_demo_dst)
            print(f"[launcher] data_demo copiado exitosamente", flush=True)
        except Exception as e:
            print(f"[launcher] Error copiando data_demo: {e}", flush=True)
    
    # Verificar si el config.json existe y si tiene rutas relativas
    need_regenerate = False
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            # Verificar si tiene rutas relativas
            for value in existing.values():
                if isinstance(value, str) and value.startswith("./"):
                    print(f"[launcher] config.json tiene rutas relativas, regenerando...", flush=True)
                    need_regenerate = True
                    break
        except Exception as e:
            print(f"[launcher] Error leyendo config.json existente: {e}", flush=True)
            need_regenerate = True
    
    # Generar config.json si no existe o tiene rutas relativas
    if (not cfg_path.exists() or need_regenerate) and demo_json.exists():
        try:
            with open(demo_json, "r", encoding="utf-8") as f:
                demo_config = json.load(f)
            
            print(f"[launcher] config.demo.json leído: {demo_config}", flush=True)
            
            # Convertir rutas relativas a absolutas en AppData
            new_config = {}
            for key, value in demo_config.items():
                if isinstance(value, str) and value.startswith("./data_demo/"):
                    filename = value.replace("./data_demo/", "")
                    # Usar ruta absoluta normalizada para Windows
                    abs_path = os.path.join(str(data_demo_dst), filename)
                    new_config[key] = abs_path
                    print(f"[launcher] {key}: {value} -> {abs_path}", flush=True)
                else:
                    new_config[key] = value
            
            print(f"[launcher] Nuevo config.json: {new_config}", flush=True)
            
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(new_config, f, indent=4, ensure_ascii=False)
            
            print(f"[launcher] config.json generado en {cfg_path}", flush=True)
        except Exception as e:
            print(f"[launcher] Error generando config: {e}", flush=True)
            traceback.print_exc()


def start_processes():
    api_port = find_free_port()
    app_port = find_free_port()

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["APP_CONFIG_PATH"] = str(APPDATA_DIR / "config.json")
    env["API_HOST"] = "127.0.0.1"
    env["API_PORT"] = str(api_port)
    env["FLASK_SKIP_DOTENV"] = "1"

    env_app = env.copy()
    env_app["API_URL"] = f"http://127.0.0.1:{api_port}"
    env_app["APP_CONFIG_PATH"] = str(APPDATA_DIR / "config.json")
    env_app["STREAMLIT_SERVER_HEADLESS"] = "true"
    env_app["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    env_app["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"
    env_app["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"
    env_app["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"


    api_log = open(LOG_DIR / "api.log", "w", encoding="utf-8")
    app_log = open(LOG_DIR / "app.log", "w", encoding="utf-8")

    # Lanzar primero Streamlit
    print(f"[launcher] Starting Streamlit on 127.0.0.1:{app_port} ...", flush=True)
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

    # Mientras Streamlit arranca, lanzar el API
    print(f"[launcher] Starting API on {env['API_HOST']}:{api_port} ...", flush=True)
    api_proc = subprocess.Popen(
        [str(PYTHON), "api.py"],
        cwd=str(ROOT),
        env=env,
        stdout=api_log,
        stderr=api_log,
        creationflags=NO_WINDOW,
    )

    # Comprobación de salud del API en segundo plano (no bloqueante)
    def _api_health_worker():
        health_url = f"http://127.0.0.1:{api_port}/health"
        ok = wait_for_health(health_url, timeout=20.0)
        if ok:
            print("[launcher] API healthy.", flush=True)
        else:
            print("[launcher] WARNING: API not healthy after 20s.", flush=True)

    threading.Thread(target=_api_health_worker, daemon=True).start()

    PID_FILE.write_text(f"{api_proc.pid}\n{app_proc.pid}\n", encoding="utf-8")

    url = f"http://127.0.0.1:{app_port}"
    (LOG_DIR / "last_url.txt").write_text(url, encoding="utf-8")
    print(f"[launcher] Waiting Streamlit at {url}", flush=True)

    if not wait_for_http(url, timeout=30.0):
        print("[launcher] ERROR: Streamlit no responde. Mira logs/app.log", flush=True)
        try: app_proc.terminate()
        except Exception: pass
        try: api_proc.terminate()
        except Exception: pass
        return

    print(f"[launcher] Opening browser {url}", flush=True)
    subprocess.Popen(
        ["rundll32", "url.dll,FileProtocolHandler", url],
        creationflags=NO_WINDOW,
    )

    # ---- Auto-cierre por inactividad ----
    GRACE_STARTUP = 20
    IDLE_TIMEOUT = 30

    print("[launcher] Entering idle monitor...", flush=True)
    start_time = time.time()
    last_seen = time.time()

    while True:
        if app_proc.poll() is not None:
            print("[launcher] Streamlit ended.", flush=True)
            break

        ts = get_last_ping_ts(api_port)
        now = time.time()
        if ts is not None:
            last_seen = ts

        if now - start_time > GRACE_STARTUP:
            if now - last_seen > IDLE_TIMEOUT:
                print("[launcher] No pings detected. Shutting down...", flush=True)
                break

        time.sleep(2)

    for p in (app_proc, api_proc):
        try: p.terminate()
        except Exception: pass
    time.sleep(1)
    for p in (app_proc, api_proc):
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass

    print("[launcher] Shutdown complete.", flush=True)



def main():
    _lock = single_instance_lock()

    os.chdir(ROOT)
    LOG_DIR.mkdir(exist_ok=True)

    log_f = open(LOG_DIR / "launcher.log", "w", encoding="utf-8", buffering=1)
    sys.stdout = log_f
    sys.stderr = log_f

    try:
        print("[launcher] main start", flush=True)
        ensure_venv()
        print("[launcher] venv ok", flush=True)
        write_demo_config()
        print("[launcher] config ok", flush=True)
        start_processes()
        print("[launcher] start_processes returned", flush=True)
    except Exception:
        traceback.print_exc()
        log_f.flush()
        # evita el "lost sys.stderr" al salir
        os._exit(1)




if __name__ == "__main__":
    main()
