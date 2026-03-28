"""
Aplicación principal de Streamlit para visualización de movilidad estudiantil.

Ubicación: install_root/web_app/my_app.py
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
import urllib.request
import streamlit.components.v1 as components
import pathlib

from ui import (
    setup_session, sidebar_controls, render_new_user_form,
    show_map, render_stats_view, build_search_index, render_search_box,
    filter_dataframes_by_search
)

js_path = pathlib.Path(__file__).parent.parent / "static" / "materias_editor.js"
if js_path.exists():
    st.markdown(f'<script src="/static/materias_editor.js?ts={os.path.getmtime(js_path)}"></script>', unsafe_allow_html=True)

from utils import handle_open_pdf_query, handle_open_excel_query
from utils.app_config import (
    init_session_defaults, get_query_param, get_config_mtimes,
    get_active_programs, get_available_program_types
)
from utils.map_processing import (
    calculate_auto_zoom_bounds, check_dataframes_have_data, filter_out_no_la
)
from persistence import load_all_dataframes, get_materias_in_por_estudiante
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT


# ---------------------------------------------------------------------------
# Caché al nivel de módulo para que st.cache_data.clear() funcione bien
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _cached_load(cfg_items: tuple, sheet: str, data_version: int,
                 src_mtimes: tuple, programs: tuple | None = None):
    cfg = dict(cfg_items)
    return load_all_dataframes(cfg, sheet, programs_to_load=list(programs) if programs else None)


@st.cache_data(show_spinner=False)
def _cached_materias(cfg_items: tuple, data_version: int, src_mtimes: tuple):
    return get_materias_in_por_estudiante(dict(cfg_items))


# ---------------------------------------------------------------------------
# Fragment de auto-refresco: detecta cambios en disco cada 3s
# ---------------------------------------------------------------------------

@st.fragment(run_every=3)
def _auto_refresh_on_excel_change() -> None:
    """Cada 3s comprueba si algún Excel cambió en disco. Si cambió, recarga."""
    config = st.session_state.get("config", {})
    if not config:
        return

    stored  = st.session_state.get("_excel_mtimes_snapshot", {})
    current = {}
    changed = False

    for key, path in config.items():
        if not path or not isinstance(path, str):
            continue
        try:
            if os.path.exists(path):
                mtime = os.path.getmtime(path)
                current[key] = mtime
                if key in stored and stored[key] != mtime:
                    changed = True
        except Exception:
            pass

    st.session_state["_excel_mtimes_snapshot"] = current

    if changed:
        st.cache_data.clear()
        st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
        st.rerun()


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def _check_api_health(timeout: int = 1) -> bool:
    try:
        api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
        with urllib.request.urlopen(f"{api_url}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _handle_query_params() -> None:
    clear_cache = get_query_param("clear_cache")
    saved       = get_query_param("student_saved")

    if clear_cache == "1":
        st.cache_data.clear()

    if saved == "1":
        st.cache_data.clear()
        st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
        st.query_params.clear()
        st.success("✅ Alumno guardado correctamente.")
        st.rerun()
    elif saved == "0":
        st.query_params.clear()
        st.error("❌ No se pudieron guardar los cambios.")


def _load_dataframes_with_cache(config, global_sheet: str):
    cfg_mtimes       = get_config_mtimes(config)
    programs_to_load = tuple(get_active_programs()) or None
    cfg_items        = tuple(sorted(config.items()))

    result = _cached_load(
        cfg_items, global_sheet,
        st.session_state.get("data_version", 0),
        cfg_mtimes, programs_to_load,
    )

    # load_all_dataframes devuelve (dfs, messages) desde Streamlit 1.35+
    # para evitar llamar a st.* dentro de @st.cache_data
    if isinstance(result, tuple) and len(result) == 2:
        dfs, messages = result
    else:
        dfs = result  # compatibilidad con versiones anteriores
        messages = []

    return dfs, cfg_mtimes, messages


def _load_materias_with_cache(config, cfg_mtimes):
    if not st.session_state.get("has_data", False):
        return {}

    return _cached_materias(
        tuple(sorted(config.items())),
        st.session_state.get("data_version", 0),
        cfg_mtimes,
    )


def _render_map_view(dfs, base_map, materias):
    if not check_dataframes_have_data(dfs):
        st.info("Cargando datos y mapa…")
        st.stop()

    only_no_la  = st.session_state.get("only_erasmus_out_no_LA", False)
    if only_no_la:
        dfs = filter_out_no_la(dfs, PROGRAM_ERASMUS_OUT)

    search_text = st.session_state.get("search_text", "").strip()
    dfs = filter_dataframes_by_search(dfs, search_text)

    has_search       = bool(search_text and len(search_text) >= 2)
    auto_zoom_bounds = calculate_auto_zoom_bounds(
        dfs, has_search=has_search, search_margin=0.4, filter_margin=0.05
    )
    show_map(dfs, base_map, materias, get_active_programs(), only_no_la, auto_zoom_bounds)


def _render_view(dfs, base_map, materias, config):
    available_types = get_available_program_types(config)
    view = st.session_state.get("view", "map")

    if view == "new_user":
        render_new_user_form(available_types, config)
    elif view == "stats":
        render_stats_view()
    else:
        _render_map_view(dfs, base_map, materias)


def _inject_orchestrator_ws() -> None:
    ws_port = os.getenv("WS_PORT")
    if not ws_port:
        return
    components.html(
        f"""
        <script>
        (function() {{
          var host;
          try {{ host = (window.top && window.top.setInterval) ? window.top : window; }}
          catch (e) {{ host = window; }}
          if (host.__movilidad_ws && host.__movilidad_ws.readyState <= 1) return;
          try {{
            var ws = new WebSocket("ws://127.0.0.1:{ws_port}/");
            ws.onopen  = function() {{ console.log("[MovilidadESII] WS conectado."); }};
            ws.onclose = function() {{ console.log("[MovilidadESII] WS cerrado."); }};
            ws.onerror = function(e) {{ console.warn("[MovilidadESII] WS error:", e); }};
            host.__movilidad_ws = ws;
          }} catch (e) {{ console.warn("[MovilidadESII] No se pudo abrir WebSocket:", e); }}
        }})();
        </script>
        """,
        height=0, width=0,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Movilidad ESII",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Limpiar caché al inicio de cada nueva sesión de navegador
    if not st.session_state.get("_session_cache_cleared"):
        st.cache_data.clear()
        for _k in [k for k in st.session_state if "cache" in k.lower()]:
            try:
                del st.session_state[_k]
            except Exception:
                pass
        st.session_state["_session_cache_cleared"] = True

    _inject_orchestrator_ws()
    init_session_defaults()

    if not _check_api_health():
        st.info("La API está iniciándose…", icon="🕒")

    _handle_query_params()

    setup_session()
    config = st.session_state["config"]

    base_map, search_slot = sidebar_controls()

    # Auto-refresco cuando el Excel cambia en disco
    _auto_refresh_on_excel_change()

    # Cargar datos
    global_sheet = st.session_state.get("global_sheet", None)
    dfs, cfg_mtimes, load_messages = _load_dataframes_with_cache(config, global_sheet)

    build_search_index(dfs)
    if search_slot is not None:
        render_search_box(parent=search_slot)

    handle_open_pdf_query()
    handle_open_excel_query()

    st.title("Visualización de Movilidad ESII")

    # Avisos de coordenadas faltantes, justo bajo el título
    for msg in load_messages:
        if msg.startswith("⚠️"):
            st.warning(msg)
        else:
            st.info(msg)

    has_data = check_dataframes_have_data(dfs)
    st.session_state["has_data"] = has_data

    if has_data:
        materias = _load_materias_with_cache(config, cfg_mtimes)
    else:
        materias = {}
        st.info("No hay datos disponibles. Revisa la configuración o selecciona otra hoja.")
        return

    _render_view(dfs, base_map, materias, config)


if __name__ == "__main__":
    main()