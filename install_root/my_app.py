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

# --- INYECTAR EL SCRIPT DE MATERIAS EDITOR EN TODA LA APP ---
import pathlib
js_path = pathlib.Path(__file__).parent / "static" / "materias_editor.js"
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


def inject_js_heartbeat(interval_ms: int = 20_000) -> None:
    """Inyecta el sistema completo de heartbeat y detección de cierre de pestaña.

    Combina en una sola llamada a components.html (que SIEMPRE ejecuta scripts):
    - Ping periódico al endpoint /ping de la API Flask.
    - Registro de apertura de pestaña (/open) en el servidor de control.
    - Detección de cierre con beforeunload + pagehide (/close beacon).

    Por qué components.html y no st.markdown:
      st.markdown usa innerHTML, y los navegadores modernos NO ejecutan
      <script> tags insertados por innerHTML (política de seguridad HTML5).
      components.html crea un <iframe> nuevo en cada render, cuyo documento
      se carga con un src data-URL — los scripts dentro sí se ejecutan.

    Todo se ancla en window.top (el documento raíz de Streamlit) para que
    los timers y listeners sobrevivan a los re-renders de Streamlit, que
    destruyen y recrean el iframe pero dejan window.top intacto.

    Args:
        interval_ms: Intervalo entre pings en milisegundos (default 20 s).
    """
    api_url      = os.getenv("API_URL",       "http://127.0.0.1:5000").rstrip("/")
    control_port = os.getenv("CONTROL_PORT",  "")
    shutdown_token = os.getenv("SHUTDOWN_TOKEN", "")

    # URLs del servidor de control (vacías en modo desarrollo sin launcher)
    url_open_base  = (
        f"http://127.0.0.1:{control_port}/open?token={shutdown_token}"
        if control_port and shutdown_token else ""
    )
    url_close_base = (
        f"http://127.0.0.1:{control_port}/close?token={shutdown_token}"
        if control_port and shutdown_token else ""
    )

    components.html(
        f"""
        <script>
        (function() {{
          // ── URLs ───────────────────────────────────────────────────────────────────
          const pingUrl      = "{api_url}/ping";
          const urlOpenBase  = "{url_open_base}";
          const urlCloseBase = "{url_close_base}";
          const iv           = {interval_ms};

          // ── Seleccionar window.top como host de todos los timers y listeners ──
          // window.top NO se destruye en los re-renders de Streamlit (a diferencia
          // del iframe de components.html, que sí se recrea en cada st.rerun).
          var host;
          try {{
            host = (window.top && window.top.setInterval) ? window.top : window;
          }} catch (e) {{
            host = window;
          }}

          // ── Tab ID persistente entre recargas (localStorage en window.top) ──
          var tabId = "";
          try {{
            tabId = host.localStorage.getItem("movilidad_tab_id") || "";
            if (!tabId) {{
              // UUID v4 en JS puro
              tabId = ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, function(c) {{
                return (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16);
              }});
              host.localStorage.setItem("movilidad_tab_id", tabId);
              console.log("[MovilidadESII] NuevoTabId generado:", tabId);
            }} else {{
              console.log("[MovilidadESII] TabId recuperado:", tabId);
            }}
          }} catch (e) {{ tabId = "nols-" + Math.random().toString(36).slice(2); }}

          var urlOpen  = urlOpenBase  ? (urlOpenBase  + "&id=" + tabId) : "";
          var urlClose = urlCloseBase ? (urlCloseBase + "&id=" + tabId) : "";

          // ── Registrar /open solo una vez por sesión de browser (no en reruns) ──
          // host.__movilidad_tab_registered se conserva entre re-renders de
          // Streamlit (mismo window.top), pero desaparece en F5 (nuevo window),
          // lo que hace que F5 reenvíe /open y cancele el pending /close. ✓
          if (urlOpen && !host.__movilidad_tab_registered) {{
            host.__movilidad_tab_registered = true;
            fetch(urlOpen, {{ method: "POST" }})
              .then(function() {{ console.log("[MovilidadESII] /open enviado:", tabId); }})
              .catch(function(e) {{ console.warn("[MovilidadESII] /open error:", e); }});
          }}

          // ── Ping interval: cancelar el anterior y arrancar uno nuevo ──
          // Necesario porque el iframe es destruido y recreado en cada st.rerun();
          // sin esto, el intervalo del iframe anterior se pierde silenciosamente.
          if (host.__movilidad_ping_id) {{
            try {{ host.clearInterval(host.__movilidad_ping_id); }} catch (e) {{}}
          }}
          function ping() {{
            try {{ fetch(pingUrl, {{ method: "GET", cache: "no-store" }}).catch(function(){{}}); }}
            catch (e) {{}}
          }}
          ping();
          host.__movilidad_ping_id = host.setInterval(ping, iv);

          // ── Detección de cierre de pestaña ───────────────────────────────────
          // Enviar /close al servidor de control (que espera 5 s de gracia).
          // Si el navegador envía /open antes de que expire la gracia (F5/recarga)
          // el servidor cancela el cierre. Si no llega /open → shutdown. ✔
          function sendClose() {{
            if (urlClose) {{
              console.log("[MovilidadESII] sendBeacon /close:", tabId);
              try {{ navigator.sendBeacon(urlClose); }} catch (e) {{}}
            }}
            // Último ping para mantener LAST_PING fresco hasta el momento de cierre.
            try {{ navigator.sendBeacon(pingUrl); }} catch (e) {{}}
          }}

          // Eliminar listeners anteriores (evitar duplicados entre re-renders)
          if (host.__movilidad_unload_fn) {{
            try {{ host.removeEventListener("beforeunload", host.__movilidad_unload_fn); }} catch (e) {{}}
          }}
          if (host.__movilidad_pagehide_fn) {{
            try {{ host.removeEventListener("pagehide", host.__movilidad_pagehide_fn); }} catch (e) {{}}
          }}

          // beforeunload: se ejecuta antes de cerrar o navegar fuera de la página.
          host.__movilidad_unload_fn = function() {{
            sendClose();
          }};

          // pagehide: más fiable que beforeunload en navegadores móviles y Chrome
          // moderno.  persisted=true significa BF cache (F5); intentamos enviar
          // /close en ambos casos — la gracia de 5 s en el servidor lo maneja. ✔
          host.__movilidad_pagehide_fn = function(ev) {{
            sendClose();
          }};

          host.addEventListener("beforeunload", host.__movilidad_unload_fn);
          host.addEventListener("pagehide",     host.__movilidad_pagehide_fn);

          console.log("[MovilidadESII] Heartbeat registrado.",
                      "pingUrl:", pingUrl, "tabId:", tabId);
        }})();
        </script>
        """,
        height=0, width=0,
    )




def main():

    # ==================== CONFIGURACIÓN ====================
    control_port   = os.getenv("CONTROL_PORT", "")
    shutdown_token = os.getenv("SHUTDOWN_TOKEN", "")

    st.set_page_config(
        page_title="Movilidad ESII",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    # Sistema completo de heartbeat + detección de cierre de pestaña.
    # Sustituye a st.markdown(js) (que no ejecuta scripts) + inject_js_ping.
    inject_js_heartbeat(20_000)
    
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