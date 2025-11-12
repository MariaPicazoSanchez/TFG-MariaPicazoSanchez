import streamlit as st
import os, sys, subprocess, urllib.parse as up
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from data_access import load_erasmus_in, load_sicue_out, load_erasmus_out


def load_dataframes(config):
    """Carga los DataFrames desde las rutas guardadas (OUT/IN/SICUE)."""
    dfs = {}

    erasmus_out_path = config.get("Erasmus OUT")
    if erasmus_out_path:
        try:
            dfs["Erasmus OUT"] = load_erasmus_out(erasmus_out_path)
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar Erasmus OUT: {e}")

    erasmus_in_path = config.get("Erasmus IN")
    if erasmus_in_path:
        try:
            dfs["Erasmus IN"] = load_erasmus_in(erasmus_in_path)
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar Erasmus IN: {e}")

    sicue_out_path = config.get("SICUE OUT")
    if sicue_out_path:
        try:
            dfs["SICUE OUT"] = load_sicue_out(sicue_out_path)
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar SICUE OUT: {e}")

    return dfs


def open_in_system(path: str):
    if not path: return False, "Ruta vacía"
    if not os.path.exists(path): return False, f"No existe: {path}"
    try:
        if sys.platform.startswith("win"):
            try:
                os.startfile(path)                      # asociación por defecto
            except Exception:
                subprocess.Popen(['cmd','/c','start','', path], shell=True)  # fallback
            return True, None
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path]);  return True, None
        else:
            subprocess.Popen(["xdg-open", path]); return True, None
    except Exception as e:
        if sys.platform.startswith("win"):
            try:
                subprocess.Popen(["rundll32","url.dll,FileProtocolHandler", path])
                return True, None
            except Exception as e2:
                return False, f"{e}; fallback: {e2}"
        return False, str(e)

def handle_open_pdf_query():
    # lee ?open_pdf=... (soporta APIs nuevas y antiguas)
    try:
        qp = st.query_params
        raw = qp.get("open_pdf")
        if isinstance(raw, list):
            raw = raw[0] if raw else None
    except Exception:
        raw = st.experimental_get_query_params().get("open_pdf", [None])[0]

    if raw:
        path = up.unquote(raw)
        ok, err = open_in_system(path)
        if not ok:
            st.sidebar.error(f"No se pudo abrir el PDF: {err}")


def main():
    # Debe ser la primera llamada de Streamlit
    st.set_page_config(page_title="Movilidad UCLM", layout="wide", initial_sidebar_state="expanded")

    # NUEVO: si llega ?open_pdf=..., lo abrimos en el SO y limpiamos la URL
    handle_open_pdf_query()

    st.title("Visualizador de Movilidad ESII")

    setup_session()
    base_map = sidebar_controls()

    dfs = load_dataframes(st.session_state["config"])  # que cargue OUT/IN/SICUE si hay ruta
    show_map(dfs, base_map)


if __name__ == "__main__":
    main()
