import os
import time
import streamlit as st
import urllib.request
import streamlit.components.v1 as components

from ui import (
    setup_session, sidebar_controls, render_new_user_form,
    show_map, render_stats_view, build_search_index, render_search_box
)
from utils import handle_open_pdf_query, handle_open_excel_query
from utils.app_config import (
    init_session_defaults, get_query_param, get_config_mtimes,
    get_active_programs, get_available_program_types,
    log_performance, debug_file_mtimes
)
from utils.text_search import filter_dataframes_by_search, normalize_text
from utils.map_processing import (
    calculate_auto_zoom_bounds, check_dataframes_have_data, filter_out_no_la
)
from persistence import load_all_dataframes, get_materias_in_por_estudiante
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT


def _check_api_health(timeout: int = 1) -> bool:
    """Check if API is responding."""
    try:
        api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
        with urllib.request.urlopen(f"{api_url}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _handle_query_params() -> None:
    """Process query parameters for cache clearing and save notifications."""
    clear_cache = get_query_param("clear_cache")
    saved = get_query_param("student_saved")
    
    if clear_cache == "1":
        st.cache_data.clear()
    
    if saved == "1":
        st.session_state["data_version"] += 1
        st.success("✅ Alumno guardado correctamente. Los datos se han actualizado.")
        st.rerun()
    elif saved == "0":
        st.error("❌ No se pudieron guardar los cambios.")


def _load_dataframes_with_cache(config, global_sheet: str):
    """Load and cache dataframes with performance logging."""
    @st.cache_data(show_spinner=False)
    def cached_load(cfg, sheet, data_version, src_mtimes, programs=None):
        return load_all_dataframes(cfg, sheet, programs_to_load=programs)
    
    t0 = time.perf_counter()
    cfg_mtimes = get_config_mtimes(config)
    
    # Get selected programs for lazy loading
    programs_to_load = tuple(get_active_programs()) or None
    
    dfs = cached_load(
        config, global_sheet,
        st.session_state.get("data_version", 0),
        cfg_mtimes,
        programs_to_load
    )
    
    t1 = time.perf_counter()
    log_performance("load_all_dataframes", t0, t1)
    
    return dfs, cfg_mtimes


def _load_materias_with_cache(config, cfg_mtimes):
    """Load materias in data with performance logging."""
    if not check_dataframes_have_data(st.session_state.get("dfs", {})):
        return {}
    
    @st.cache_data(show_spinner=False)
    def cached_materias(cfg, data_version, src_mtimes):
        return get_materias_in_por_estudiante(cfg)
    
    t0 = time.perf_counter()
    materias = cached_materias(
        config,
        st.session_state.get("data_version", 0),
        cfg_mtimes
    )
    t1 = time.perf_counter()
    log_performance("materias_in_loader", t0, t1)
    
    return materias


def _render_view(dfs, base_map, materias, config):
    """Render the appropriate view based on session state."""
    available_types = get_available_program_types(config)
    view = st.session_state.get("view", "map")
    
    if view == "new_user":
        render_new_user_form(available_types, config)
    elif view == "stats":
        render_stats_view()
    else:
        _render_map_view(dfs, base_map, materias)


def _render_map_view(dfs, base_map, materias):
    """Render the map view with search and filters."""
    if not check_dataframes_have_data(dfs):
        st.info("Cargando datos y mapa…")
        st.stop()
    
    # Apply no-LA filter if needed
    only_no_la = st.session_state.get("only_erasmus_out_no_LA", False)
    if only_no_la:
        dfs = filter_out_no_la(dfs, PROGRAM_ERASMUS_OUT)
    
    # Apply search filter
    search_text = st.session_state.get("search_text", "").strip()
    dfs = filter_dataframes_by_search(dfs, search_text)
    
    # Calculate auto-zoom bounds
    has_search = bool(search_text and len(search_text) >= 2)
    auto_zoom_bounds = calculate_auto_zoom_bounds(
        dfs,
        has_search=has_search,
        search_margin=0.4,
        filter_margin=0.05
    )
    
    # Render map
    show_map(
        dfs,
        base_map,
        materias,
        get_active_programs(),
        only_no_la,
        auto_zoom_bounds
    )

    api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
    components.html(
        f"""
        <script>
        (function() {{
          const url = "{api_url}/ping";
          function ping() {{
            try {{
              fetch(url, {{ method: "GET", cache: "no-store" }}).catch(() => {{}});
            }} catch (e) {{}}
          }}
          ping();
          setInterval(ping, {interval_ms});
        }})();
        </script>
        """,
        height=0, width=0
    )

if __name__ == "__main__":
    main()
