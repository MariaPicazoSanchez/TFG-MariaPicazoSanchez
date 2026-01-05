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
import socket

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

VENV_DIR = Path(r"C:\tfg_venv")
PYTHON = VENV_DIR / "Scripts" / "python.exe"

REQ = ROOT / "requirements.lock.txt"
WHEELHOUSE = ROOT / "wheelhouse"

PID_FILE = ROOT / ".pids"

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


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
    stamp = ROOT / ".deps.sha256"
    req_hash = file_sha256(REQ)

    if not PYTHON.exists():
        system_python = get_system_python()
        subprocess.check_call([system_python, "-m", "venv", str(VENV_DIR)], creationflags=NO_WINDOW)

    # Si ya hay sello y coincide, NO reinstalar
    if stamp.exists() and stamp.read_text(encoding="utf-8").strip() == req_hash:
        return

    # Log de instalación (por si algo falla)
    pip_log_path = LOG_DIR / "pip.log"
    with open(pip_log_path, "w", encoding="utf-8") as pip_log:
        subprocess.check_call(
            [str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"],
            creationflags=NO_WINDOW,
            stdout=pip_log,
            stderr=pip_log
        )

        if WHEELHOUSE.exists():
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
            subprocess.check_call(
                [str(PYTHON), "-m", "pip", "install", "-r", str(REQ)],
                creationflags=NO_WINDOW,
                stdout=pip_log,
                stderr=pip_log
            )

    stamp.write_text(req_hash, encoding="utf-8")




def write_demo_config():
    demo = ROOT / "config.demo.json"
    cfg = ROOT / "config.json"
    if demo.exists():
        cfg.write_text(demo.read_text(encoding="utf-8"), encoding="utf-8")


def start_processes():
    api_port = 5000
    app_port = find_free_port()

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"

    env_app = env.copy()
    env_app["API_URL"] = f"http://127.0.0.1:{api_port}"

    api_log = open(LOG_DIR / "api.log", "w", encoding="utf-8")
    app_log = open(LOG_DIR / "app.log", "w", encoding="utf-8")

    print("[launcher] Starting API...", flush=True)
    api_proc = subprocess.Popen(
        [str(PYTHON), "api.py"],
        cwd=str(ROOT),
        env=env,
        stdout=api_log,
        stderr=api_log,
        creationflags=NO_WINDOW
    )

    health_url = f"http://127.0.0.1:{api_port}/health"
    print("[launcher] Waiting API health...", flush=True)
    if not wait_for_health(health_url, timeout=20.0):
        print("[launcher] ERROR: API /health no responde. Mira logs/api.log", flush=True)
        try: api_proc.terminate()
        except: pass
        return

    print("[launcher] Starting Streamlit...", flush=True)
    app_proc = subprocess.Popen(
        [
            str(PYTHON), "-m", "streamlit", "run", "my_app.py",
            "--server.address=127.0.0.1",
            f"--server.port={app_port}",
            "--server.headless=true",
        ],
        cwd=str(ROOT),
        env=env_app,
        stdout=app_log,
        stderr=app_log,
        creationflags=NO_WINDOW
    )

    PID_FILE.write_text(f"{api_proc.pid}\n{app_proc.pid}\n", encoding="utf-8")

    url = f"http://127.0.0.1:{app_port}"
    (LOG_DIR / "last_url.txt").write_text(url, encoding="utf-8")
    print(f"[launcher] Waiting Streamlit at {url}", flush=True)

    if not wait_for_http(url, timeout=30.0):
        print("[launcher] ERROR: Streamlit no responde. Mira logs/app.log", flush=True)
        try: app_proc.terminate()
        except: pass
        try: api_proc.terminate()
        except: pass
        return

    subprocess.Popen(
        ["cmd", "/c", "start", "", url],
        creationflags=NO_WINDOW
    )



    # ---- Auto-cierre por inactividad ----
    # Da margen para que el navegador empiece a pinguear
    GRACE_STARTUP = 20
    IDLE_TIMEOUT = 60

    print("[launcher] Entering idle monitor...", flush=True)
    start_time = time.time()
    last_seen = time.time()

    while True:
        # si Streamlit muere, salimos
        if app_proc.poll() is not None:
            print("[launcher] Streamlit ended.", flush=True)
            break

        ts = get_last_ping_ts(api_port)
        now = time.time()
        if ts is not None:
            last_seen = ts

        # no aplicar idle durante el arranque
        if now - start_time > GRACE_STARTUP:
            if now - last_seen > IDLE_TIMEOUT:
                print("[launcher] No pings detected. Shutting down...", flush=True)
                break

        time.sleep(2)

    # matar procesos
    for p in (app_proc, api_proc):
        try: p.terminate()
        except: pass
    time.sleep(1)
    for p in (app_proc, api_proc):
        try:
            if p.poll() is None:
                p.kill()
        except: pass

    print("[launcher] Shutdown complete.", flush=True)



# def main():
#     os.chdir(ROOT)
#     ensure_venv()
#     write_demo_config()
#     start_processes()

import traceback

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
