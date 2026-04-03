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
from constants import PROGRAM_ERASMUS_OUT
from ui._sidebar_config import _list_sheets_in_file
from ui.stats_helpers import build_export_xlsx


# ---------------------------------------------------------------------------
# Caché al nivel de módulo para que st.cache_data.clear() funcione bien
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def _cached_load(cfg_items: tuple, sheet: str, data_version: int,
                 src_mtimes: tuple):
    cfg = dict(cfg_items)
    return load_all_dataframes(cfg, sheet, programs_to_load=None)


@st.cache_data(show_spinner=False)
def _cached_materias(cfg_items: tuple, data_version: int, src_mtimes: tuple):
    return get_materias_in_por_estudiante(dict(cfg_items))


# ---------------------------------------------------------------------------
# Fragment de auto-refresco: detecta cambios en disco cada 3s
# ---------------------------------------------------------------------------

@st.fragment(run_every=10)
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
    import time as _time
    cached = st.session_state.get("_api_health_cache")
    if cached and _time.time() - cached["ts"] < 120:
        return cached["ok"]
    try:
        api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
        with urllib.request.urlopen(f"{api_url}/health", timeout=timeout) as r:
            ok = r.status == 200
    except Exception:
        ok = False
    st.session_state["_api_health_cache"] = {"ok": ok, "ts": _time.time()}
    return ok


def _handle_query_params() -> None:
    clear_cache   = get_query_param("clear_cache")
    saved         = get_query_param("student_saved")
    saved_program = get_query_param("saved_program")
    force_reload  = get_query_param("force_reload")

    if force_reload == "1":
        st.cache_data.clear()
        st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
        st.session_state.pop("_map_html_key", None)
        st.session_state.pop("last_map_html", None)
        st.query_params.clear()
        st.rerun()

    if clear_cache == "1" and not saved:
        st.cache_data.clear()

    if saved == "1":
        # Solo limpiamos las cachés que cambian al añadir un alumno.
        # _cached_load y _cached_materias se invalidan automáticamente via data_version.
        # Las cachés de universidades/países/coordenadas NO cambian al guardar un alumno.
        _list_sheets_in_file.clear()   # por si se creó una hoja nueva
        build_export_xlsx.clear()      # el export incluye al nuevo alumno
        st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
        # Actualizar snapshot de mtime para evitar doble reload del auto-refresh
        if saved_program:
            _cfg = st.session_state.get("config", {})
            _excel_path = _cfg.get(saved_program, "")
            if _excel_path and os.path.exists(_excel_path):
                _snap = dict(st.session_state.get("_excel_mtimes_snapshot", {}))
                _snap[saved_program] = os.path.getmtime(_excel_path)
                st.session_state["_excel_mtimes_snapshot"] = _snap
        st.query_params.clear()
        st.success("✅ Alumno guardado correctamente.")
        st.rerun()
    elif saved == "0":
        st.query_params.clear()
        st.error("❌ No se pudieron guardar los cambios.")


def _load_dataframes_with_cache(config, global_sheet: str):
    cfg_mtimes = get_config_mtimes(config)
    cfg_items  = tuple(sorted(config.items()))

    result = _cached_load(
        cfg_items, global_sheet,
        st.session_state.get("data_version", 0),
        cfg_mtimes,
    )

    if isinstance(result, tuple) and len(result) == 2:
        dfs, messages = result
    else:
        dfs, messages = result, []
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

    # Filtrar por programas seleccionados (en memoria, sin recargar desde disco)
    active_programs = get_active_programs()
    if active_programs:
        dfs = {k: v for k, v in dfs.items() if k in active_programs}

    only_no_la  = st.session_state.get("only_erasmus_out_no_LA", False)
    if only_no_la:
        dfs = filter_out_no_la(dfs, PROGRAM_ERASMUS_OUT)

    search_text = st.session_state.get("search_text", "").strip()
    dfs = filter_dataframes_by_search(dfs, search_text)

    # Clave que identifica unívocamente el mapa a renderizar.
    # Si no ha cambiado nada, reutilizamos el HTML ya generado.
    _render_key = (
        st.session_state.get("data_version", 0),
        st.session_state.get("global_sheet", ""),
        tuple(sorted((k, v) for k, v in st.session_state.get("selected_programs", {}).items())),
        only_no_la,
        search_text,
    )
    cached_html = st.session_state.get("last_map_html")
    if cached_html and st.session_state.get("_map_render_key") == _render_key:
        import streamlit.components.v1 as _components
        _components.html(cached_html, height=1080, scrolling=True)
        return

    has_search       = bool(search_text and len(search_text) >= 2)
    auto_zoom_bounds = calculate_auto_zoom_bounds(
        dfs, has_search=has_search, search_margin=0.4, filter_margin=0.05
    )
    with st.spinner("Cargando mapa…"):
        show_map(dfs, base_map, materias, get_active_programs(), only_no_la, auto_zoom_bounds)
    st.session_state["_map_render_key"] = _render_key


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

    # Reconstruir el índice de búsqueda solo cuando los datos cambian
    _index_ver = st.session_state.get("data_version", 0) + sum(
        st.session_state.get(f"_prog_ver_{p}", 0)
        for p in (tuple(get_active_programs()) or [])
    )
    if st.session_state.get("_search_index_ver") != _index_ver:
        build_search_index(dfs)
        st.session_state["_search_index_ver"] = _index_ver
    if search_slot is not None:
        render_search_box(parent=search_slot)

    handle_open_pdf_query()
    handle_open_excel_query()

    _col_title, _col_btn = st.columns([14, 1])
    with _col_title:
        st.title("Visualización de Movilidad ESII")
    with _col_btn:
        st.markdown("""
            <form action="" method="get">
                <button name="force_reload" value="1" class="reload-btn">
                    ⟳ Recargar
                </button>
            </form>

            <style>
            .reload-btn {
                border:1px solid #d1d5db;
                background:#f9fafb;
                color:#111827;
                padding:6px 12px;
                border-radius:8px;
                font-size:14px;
                cursor:pointer;
                transition:all 0.15s ease;
            }

            .reload-btn:hover {
                background:#f3f4f6;
                border-color:#9ca3af;
            }
            </style>
            """, unsafe_allow_html=True)

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