"""
Aplicación principal de Streamlit para visualización de movilidad estudiantil.

Este módulo orquesta la carga de datos, filtrado y pipeline de visualización.
Separa responsabilidades en funciones más pequeñas y testeables.

Ubicación: install_root/web_app/my_app.py
Se puede lanzar directamente con:
    streamlit run web_app/my_app.py
o a través del orquestador:
    python orchestrator/orchestrator.py
"""

import os
import sys

# ---------------------------------------------------------------------------
# Asegurar que install_root/ esté en el path para que los imports relativos
# (ui, utils, persistence, constants, …) se resuelvan correctamente aunque
# este fichero viva en el subdirectorio web_app/.
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

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


def _inject_orchestrator_ws() -> None:
    """Inyecta el JS de señal de cierre según el modo de lanzamiento:

    - **Modo launcher_system** (instalador): si ``CONTROL_PORT`` y
      ``SHUTDOWN_TOKEN`` están definidos en el entorno, inyecta JS que
      llama a ``/open`` al cargar la página y a ``/close`` (via
      ``sendBeacon``) al cerrarla, comunicándose con el servidor HTTP de
      control que gestiona el shutdown en ``launcher_system.py``.

    - **Modo orquestador** (desarrollo): si las variables anteriores no
      están definidas, inyecta JS que abre una conexión WebSocket a
      ``ws://localhost:8765`` y la mantiene activa mientras la pestaña
      esté abierta. Al cerrarla el orquestador detecta el cierre y mata
      los procesos hijo.

    Se usa ``components.html`` en ambos casos para garantizar la ejecución
    del script. La inicialización se ancla en ``window.top`` para sobrevivir
    a los re-renders de Streamlit.
    """
    control_port  = os.getenv("CONTROL_PORT", "")
    shutdown_token = os.getenv("SHUTDOWN_TOKEN", "")

    if control_port and shutdown_token:
        # ── Modo launcher_system: HTTP control server ────────────────────
        # Generar tabId UNA SOLA VEZ en Python y embeberlo como literal JS.
        # Esto lo hace estable ante re-renders aunque sessionStorage no esté
        # disponible (iframes con sandbox sin allow-same-origin), evitando
        # que se acumulen múltiples tabIds en open_tabs y bloqueen el shutdown.
        if "movilidad_tab_id" not in st.session_state:
            import secrets as _sec
            st.session_state["movilidad_tab_id"] = _sec.token_urlsafe(12)
        tab_id = st.session_state["movilidad_tab_id"]

        base_url = f"http://127.0.0.1:{control_port}"
        components.html(
            f"""
            <script>
            (function() {{
              // Intentar acceder a window.top para anclar estado entre re-renders.
              // usingTop=true  → iframe con acceso al padre (same-origin).
              // usingTop=false → iframe sandboxeado; host = window del iframe.
              var host;
              var usingTop = false;
              try {{
                if (window.top && window.top.setInterval) {{
                  host = window.top;
                  usingTop = (host !== window);
                }} else {{
                  host = window;
                }}
              }} catch (e) {{
                host = window; // SecurityError: sandbox bloquea window.top
              }}

              var base  = "{base_url}";
              var token = "{shutdown_token}";
              var tabId = "{tab_id}";

              var _openUrl  = base + "/open?token="  + token + "&id=" + tabId;
              var _closeUrl = base + "/close?token=" + token + "&id=" + tabId;

              function _fetch(url, opts) {{
                try {{
                  (host.fetch || window.fetch)(url, opts).catch(function() {{}});
                }} catch(e) {{}}
              }}

              // Si la pestaña ya fue cerrada explícitamente, salir sin hacer nada.
              // Esto evita que un re-render tardío reactive el heartbeat tras el cierre.
              if (host.__movilidad_tab_closed) return;

              // /open inmediato en cada render para cancelar cualquier pending_close
              // provocado por el tiempo de re-render entre la destrucción del iframe
              // anterior y la ejecución de este script.
              _fetch(_openUrl, {{method: "POST", mode: "no-cors"}});

              // ── Heartbeat ────────────────────────────────────────────────
              // SIEMPRE reinstalar el intervalo en cada render.
              // Razón: con usingTop=true el intervalo se ancla en window.top y
              // sobrevive a rerenders, pero puede haber quedado en estado zombie
              // (referencia no nula, intervalo ya cancelado) si en un render
              // anterior se llamó clearInterval(). Reinstalarlo garantiza que
              // SIEMPRE hay un intervalo vivo.
              // Con usingTop=false (iframe sandboxeado), window es fresco en cada
              // render, así que host.__movilidad_heartbeat siempre es undefined
              // y el resultado es el mismo.
              if (host.__movilidad_heartbeat) {{
                host.clearInterval(host.__movilidad_heartbeat);
              }}
              host.__movilidad_heartbeat = host.setInterval(function() {{
                if (!host.__movilidad_tab_closed) {{
                  _fetch(_openUrl, {{method: "POST", mode: "no-cors"}});
                }}
              }}, 2000);

              // ── Listeners de cierre ──────────────────────────────────────
              // Solo en usingTop=true: pagehide/beforeunload del iframe (usingTop=false)
              // se dispara en cada re-render → /close falso → shutdown al cambiar vista.
              if (usingTop && !host.__movilidad_ctrl_close) {{
                host.__movilidad_ctrl_close = true;

                host.__movilidad_notify_close = function() {{
                  host.__movilidad_tab_closed = true;
                  if (host.__movilidad_heartbeat) {{
                    host.clearInterval(host.__movilidad_heartbeat);
                    host.__movilidad_heartbeat = null;
                  }}
                  var sent = false;
                  try {{ sent = (host.navigator || navigator).sendBeacon(_closeUrl); }} catch(e) {{}}
                  if (!sent) {{
                    _fetch(_closeUrl, {{method: "POST", keepalive: true, mode: "no-cors"}});
                  }}
                }};

                try {{ host.addEventListener("pagehide",     host.__movilidad_notify_close); }} catch(e) {{}}
                try {{ host.addEventListener("beforeunload", host.__movilidad_notify_close); }} catch(e) {{}}
              }}
            }})();
            </script>
            """,
            height=0,
            width=0,
        )
    else:
        # ── Modo orquestador: WebSocket ──────────────────────────────────
        components.html(
            """
            <script>
            (function() {
              // Anclar el socket en window.top para que sobreviva a los re-renders
              // de Streamlit, que destruyen y recrean este iframe.
              var host;
              try {
                host = (window.top && window.top.setInterval) ? window.top : window;
              } catch (e) {
                host = window;
              }

              // Crear un WS nuevo en cada render salvo que ya haya uno conectándose
              // (readyState=0, CONNECTING). NO bloquear si está OPEN (1) porque ese
              // WS pertenece al iframe anterior, que va a ser destruido por Streamlit
              // al montar este iframe; si no creamos uno nuevo ahora, habrá un instante
              // en que _active_connections=0 y el orquestador dispararía un shutdown
              // falso de 5s.  Dos conexiones simultáneas son inofensivas: la vieja
              // desaparece en cuanto el iframe anterior se destruye.
              if (host.__movilidad_ws && host.__movilidad_ws.readyState === 0) {
                return;  // ya conectándose, evitar duplicado innecesario
              }

              try {
                var ws = new WebSocket("ws://localhost:8765/");
                ws.onopen  = function() { console.log("[MovilidadESII] WebSocket conectado al orquestador."); };
                ws.onclose = function() { console.log("[MovilidadESII] WebSocket cerrado."); };
                ws.onerror = function(e) { console.warn("[MovilidadESII] WebSocket error:", e); };
                host.__movilidad_ws = ws;
              } catch (e) {
                console.warn("[MovilidadESII] No se pudo abrir WebSocket al orquestador:", e);
              }
            })();
            </script>
            """,
            height=0,
            width=0,
        )


def main():

    # ==================== CONFIGURACIÓN ====================
    st.set_page_config(
        page_title="Movilidad ESII",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Conectar con el orquestador vía WebSocket para detección de cierre de pestaña.
    _inject_orchestrator_ws()

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
