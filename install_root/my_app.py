"""
Aplicación principal de Streamlit para visualización de movilidad estudiantil.

Este módulo orquesta la carga de datos, filtrado y pipeline de visualización.
Separa responsabilidades en funciones más pequeñas y testeables.
"""

import os
import streamlit as st
import urllib.request
import streamlit.components.v1 as components

from ui import (
    setup_session, sidebar_controls, render_new_user_form,
    show_map, render_stats_view, build_search_index, render_search_box,
    filter_dataframes_by_search
)
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


def _check_api_health(timeout: int = 1) -> bool:
    """Verifica si la API está respondiendo.
    
    Args:
        timeout: Tiempo de espera de la petición en segundos
    
    Returns:
        True si la API está saludable, False en caso contrario
    """
    try:
        api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
        with urllib.request.urlopen(f"{api_url}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _handle_query_params() -> None:
    """Procesa parámetros de consulta para limpiar caché y notificaciones de guardado.
    
    Maneja:
    - clear_cache=1: Limpia la caché de Streamlit
    - student_saved=1: Muestra mensaje de éxito y refresca los datos
    - student_saved=0: Muestra mensaje de error
    """
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
    """Carga y cachea dataframes con registro de rendimiento.
    
    Args:
        config: Diccionario de configuración con rutas de archivos Excel
        global_sheet: Nombre de la hoja a cargar (ej. "Todas")
    
    Returns:
        Tupla de (diccionario de dataframes, tupla de tiempos de modificación de config)
    """
    @st.cache_data(show_spinner=False)
    def cached_load(cfg, sheet, data_version, src_mtimes, programs=None):
        return load_all_dataframes(cfg, sheet, programs_to_load=programs)
    
    cfg_mtimes = get_config_mtimes(config)
    
    # Obtener programas seleccionados para carga perezosa
    programs_to_load = tuple(get_active_programs()) or None
    
    dfs = cached_load(
        config, global_sheet,
        st.session_state.get("data_version", 0),
        cfg_mtimes,
        programs_to_load
    )
    
    return dfs, cfg_mtimes


def _load_materias_with_cache(config, cfg_mtimes):
    """Carga datos de materias con registro de rendimiento.
    
    Solo intenta cargar si los dataframes tienen datos.
    
    Args:
        config: Diccionario de configuración
        cfg_mtimes: Tupla de tiempos de modificación de configuración
    
    Returns:
        Diccionario de materias o diccionario vacío si no hay datos
    """
    # Verificación rápida - solo cargar si tenemos datos
    if not st.session_state.get("has_data", False):
        return {}
    
    @st.cache_data(show_spinner=False)
    def cached_materias(cfg, data_version, src_mtimes):
        return get_materias_in_por_estudiante(cfg)
    
    materias = cached_materias(
        config,
        st.session_state.get("data_version", 0),
        cfg_mtimes
    )
    
    return materias


def _render_map_view(dfs, base_map, materias):
    """Renderiza la vista del mapa con búsqueda y filtros.
    
    Aplica filtrado de LA y filtrado de búsqueda antes de renderizar.
    
    Args:
        dfs: Diccionario de programa -> DataFrame
        base_map: Objeto de mapa base de Folium
        materias: Diccionario de asignaturas de estudiantes
    """
    if not check_dataframes_have_data(dfs):
        st.info("Cargando datos y mapa…")
        st.stop()
    
    # Aplicar filtro sin-LA si es necesario
    only_no_la = st.session_state.get("only_erasmus_out_no_LA", False)
    
    if only_no_la:
        dfs = filter_out_no_la(dfs, PROGRAM_ERASMUS_OUT)
    
    # Aplicar filtro de búsqueda
    search_text = st.session_state.get("search_text", "").strip()
    dfs = filter_dataframes_by_search(dfs, search_text)
    
    # Calcular límites de auto-zoom
    has_search = bool(search_text and len(search_text) >= 2)
    auto_zoom_bounds = calculate_auto_zoom_bounds(dfs, has_search=has_search, search_margin=0.4, filter_margin=0.05)
    
    # Renderizar mapa
    show_map(dfs, base_map, materias, get_active_programs(), only_no_la, auto_zoom_bounds)


def _render_view(dfs, base_map, materias, config):
    """Renderiza la vista apropiada según el estado de la sesión.
    
    Despacha al formulario de nuevo usuario, vista de estadísticas, o vista de mapa.
    
    Args:
        dfs: Diccionario de programa -> DataFrame
        base_map: Objeto de mapa base de Folium
        materias: Diccionario de asignaturas de estudiantes
        config: Diccionario de configuración
    """
    available_types = get_available_program_types(config)
    view = st.session_state.get("view", "map")
    
    if view == "new_user":
        render_new_user_form(available_types, config)
    elif view == "stats":
        render_stats_view()
    else:
        _render_map_view(dfs, base_map, materias)


def inject_js_ping(interval_ms: int = 8000) -> None:
    """Inyecta JavaScript para hacer ping periódico a la API para chequeos de salud.
    
    Args:
        interval_ms: Intervalo de ping en milisegundos
    """
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




def main():

    # ==================== CONFIGURACIÓN ====================
    # --- Notificación de pestaña abierta/cerrada al launcher (persistente por pestaña) ---
    import uuid
    control_port = os.getenv("CONTROL_PORT")
    shutdown_token = os.getenv("SHUTDOWN_TOKEN")
    if control_port and shutdown_token:
        js = f"""
        <script>
        (function() {{
            // Usa localStorage para persistir un id de pestaña único
            let tabId = localStorage.getItem('movilidad_tab_id');
            if (!tabId) {{
                // Generar un UUID v4 en JS puro (no depende de Python)
                tabId = ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
                    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
                );
                localStorage.setItem('movilidad_tab_id', tabId);
                console.log("Nuevo tabId generado:", tabId);
            }} else {{
                console.log("tabId persistente:", tabId);
            }}
            window.__movilidad_tab_id = tabId;
            const token = '{shutdown_token}';
            const urlOpen = 'http://127.0.0.1:{control_port}/open?id=' + tabId + '&token=' + token;
            const urlClose = 'http://127.0.0.1:{control_port}/close?id=' + tabId + '&token=' + token;
            // Notificar apertura (en cada recarga)
            fetch(urlOpen, {{method: 'POST'}}).then(() => {{
                console.log("/open enviado:", urlOpen);
            }}).catch((e) => {{
                console.error("/open error:", e);
            }});
            // Notificar cierre solo al cerrar la pestaña
            window.addEventListener('beforeunload', function() {{
                navigator.sendBeacon(urlClose);
                console.log("/close enviado:", urlClose);
            }});
        }})();
        </script>
        """
        import streamlit as st
        st.markdown(js, unsafe_allow_html=True)
    import streamlit as st
    st.set_page_config(
        page_title="Movilidad ESII",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    inject_js_ping(8000)
    
    init_session_defaults()
    
    # ==================== VERIFICACIONES INICIALES ====================
    # Verificar salud de la API (no bloqueante)
    if not _check_api_health():
        st.info("La API está iniciándose…", icon="🕒")
    
    # Manejar parámetros de consulta (puede desencadenar rerun)
    _handle_query_params()
    
    # ==================== CONFIGURAR SIDEBAR ====================
    setup_session()
    config = st.session_state["config"]
    
    base_map, search_slot = sidebar_controls()
    
    # ==================== CARGAR DATOS ====================
    global_sheet = st.session_state.get("global_sheet", None)
    dfs, cfg_mtimes = _load_dataframes_with_cache(config, global_sheet)
    
    # Construir índice de búsqueda y renderizar caja de búsqueda
    build_search_index(dfs)
    if search_slot is not None:
        render_search_box(parent=search_slot)
    
    # ==================== RENDERIZAR ====================
    handle_open_pdf_query()
    handle_open_excel_query()
    

    st.title("Visualización de Movilidad ESII")
    # Botón de cierre manual
    if control_port and shutdown_token:
        if st.button("Cerrar aplicación", key="shutdown_btn"):
            shutdown_url = f"http://127.0.0.1:{control_port}/shutdown?token={shutdown_token}"
            try:
                import requests
                resp = requests.post(shutdown_url)
                if resp.status_code == 200:
                    st.success("La aplicación se ha cerrado correctamente.")
                else:
                    st.error(f"Error al cerrar: {resp.status_code}")
            except Exception as e:
                st.error(f"Error al cerrar: {e}")

    # Verificar si tenemos datos
    has_data = check_dataframes_have_data(dfs)
    st.session_state["has_data"] = has_data

    if has_data:
        materias = _load_materias_with_cache(config, cfg_mtimes)
    else:
        materias = {}
        st.info("No hay datos disponibles para mostrar. Por favor, revisa la configuración o selecciona otra hoja.")
        return

    # Renderizar la vista apropiada
    _render_view(dfs, base_map, materias, config)


if __name__ == "__main__":
    main()