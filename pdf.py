import time
import streamlit as st
from urllib.parse import unquote
import os, sys, subprocess, urllib.parse as up

def open_in_system(path: str):
    if not path: return False, "Ruta vacía"
    if not os.path.exists(path): return False, f"No existe: {path}"
    raw = path
    path = unquote(str(path))
    path = path.strip().strip('"').strip("'")
    path = os.path.expanduser(path)
    path = os.path.abspath(path)

    # print(f"[open_in_system] raw   = {raw!r}")
    # print(f"[open_in_system] final = {path!r}")
    # print(f"[open_in_system] exists? {os.path.exists(path)}")

    if not os.path.exists(path):
        return False, f"No existe: {path}"

    try:
        if sys.platform.startswith("win"):
            try:
                os.startfile(path)  # type: ignore[attr-defined]
            except Exception:
                subprocess.Popen(['cmd', '/c', 'start', '', path], shell=True)
            return True, None
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path]);  return True, None
        else:
            subprocess.Popen(["xdg-open", path]);  return True, None
    except Exception as e:
        if sys.platform.startswith("win"):
            try:
                subprocess.Popen(["rundll32","url.dll,FileProtocolHandler", path])
                return True, None
            except Exception as e2:
                return False, f"{e}; fallback: {e2}"
        return False, str(e)

def handle_open_pdf_query():
    """Si llega ?open_pdf=... abre el archivo con la app por defecto del SO."""
    try:
        qp = st.query_params
        raw = qp.get("open_pdf")
        if isinstance(raw, list):
            raw = raw[0] if raw else None
    except Exception:
        raw = st.experimental_get_query_params().get("open_pdf", [None])[0]

    if raw:
        path = up.unquote(raw)
        with st.spinner("⏳ Abriendo…"):
            ok, err = open_in_system(path)
            time.sleep(0.2)
        if not ok:
            st.sidebar.error(f"No se pudo abrir el PDF: {err}")

def handle_open_excel_query():
    """
    Abre el Excel del programa (Erasmus IN, Erasmus OUT, SICUE OUT)
    usando la ruta de config.json y open_in_system().
    Se usa cuando el popup llama a /?open_excel=...
    """
    params = st.query_params
    raw = params.get("open_excel")
    if not raw:
        return  # no hay nada que hacer

    programa = raw[0]  # 'Erasmus IN', 'Erasmus OUT', 'SICUE OUT'
    config = st.session_state.get("config", {})

    ruta = config.get(programa)
    if not ruta:
        st.write(f"No se ha encontrado ruta para '{programa}' en config.json")
        st.stop()
        return

    ok, err = open_in_system(ruta)
    if not ok:
        st.write(f"No se ha podido abrir el archivo: {err or 'error desconocido'}")

    # Esta sesión es la del iframe oculto, aquí terminamos
    st.stop()