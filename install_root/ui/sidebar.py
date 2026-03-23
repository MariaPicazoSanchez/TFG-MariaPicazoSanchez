import json
import os
import re
import subprocess

import pandas as pd
import streamlit as st
import xlrd

from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT, CSV_SHEET_MARKER


def _is_academic_year(name: str) -> bool:
    """Devuelve True si el nombre parece un curso académico (ej: 25-26, 2025/2026, 2016)."""
    return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', name))

def repair_windows_path(path_str: str) -> str:
    """
    Repara rutas de Windows mal formadas.
    Ejemplo: 'C:UsersmariaAppDataLocalMovilidadESII' -> 'C:\\Users\\maria\\AppData\\Local\\MovilidadESII'
    """
    if not path_str:
        return ""
    
    # Si ya tiene barras invertidas, normalizarla
    if "\\" in path_str:
        return os.path.normpath(path_str)
    
    # Si tiene barras diagonales, reemplazarlas
    if "/" in path_str:
        return os.path.normpath(path_str.replace("/", "\\"))
    
    # Si NO tiene barras (ej: C:UsersmariaAppData...), insertar después de C:
    # Patrón: C:Users... -> C:\Users...
    if len(path_str) > 2 and path_str[1] == ":" and path_str[2] != "\\":
        path_str = path_str[0:2] + "\\" + path_str[2:]
    
    return os.path.normpath(path_str)

# Usa la variable de entorno APP_CONFIG_PATH si está disponible (instalación)
# Si no, usa config.json en el directorio actual (desarrollo local)
CONFIG_FILE = os.getenv("APP_CONFIG_PATH", "config.json")

USE_LOCAL_PICKER = True

def _list_sheets_in_file(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return [CSV_SHEET_MARKER]
    # intento con pandas
    try:
        xls = pd.ExcelFile(path)  # requiere openpyxl para .xlsx
        return list(xls.sheet_names)
    except Exception:
        pass
    # fallback para .xlsx
    try:
        if ext in (".xlsx", ".xlsm", ".xltx", ".xltm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            return list(wb.sheetnames)
    except Exception:
        pass
    # fallback para .xls (si tienes xlrd 1.2.0)
    try:
        if ext == ".xls":
            wb = xlrd.open_workbook(path, on_demand=True)
            return wb.sheet_names()
    except Exception:
        pass
    return []

def _unique_sheets_from_config_or_files(cfg: dict) -> list[str]:
    """Une hojas de todos los Excels; si no hay 'sheets' en config, las detecta leyendo los ficheros."""
    keys = (PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT)
    sheets_map = cfg.get("sheets", {}) or {}
    names = set()
    for k in keys:
        lst = sheets_map.get(k)
        if not lst:
            p = cfg.get(k)
            if p:
                lst = _list_sheets_in_file(p)
        for name in (lst or []):
            if name and str(name) != "__CSV__" and _is_academic_year(str(name)):
                names.add(str(name))
    return sorted(names)

def pick_local_file(initial_path: str | None = None) -> str | None:
    """Abre el explorador de archivos usando PowerShell y devuelve la ruta seleccionada (solo Windows)."""
    script = r"""
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.TopMost = $true
$form.WindowState = 'Minimized'
$form.Show()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = 'Excel Files (*.xlsx;*.xls)|*.xlsx;*.xls|CSV Files (*.csv)|*.csv|All Files (*.*)|*.*'
if ($dialog.ShowDialog($form) -eq 'OK') {
    Write-Output $dialog.FileName
}
$form.Close()
"""
    try:
        result = subprocess.run([
            "powershell", "-Command", script
        ], capture_output=True, text=True)
        path = result.stdout.strip()
        return path if path else None
    except Exception as e:
        st.sidebar.error(f"PowerShell OpenFileDialog error: {e}")
        return None

def load_config():
    """Carga las rutas guardadas desde config.json, si existe."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # REPARAR rutas mal formadas
        repaired = {}
        for key, value in config.items():
            if isinstance(value, str) and (value.startswith("C:") or value.startswith("D:") or value.startswith("/")):
                # Es una ruta: repararla y normalizarla
                repaired[key] = repair_windows_path(value)
            else:
                repaired[key] = value
        return repaired
    return {}


def save_config(config: dict) -> None:
    """Guarda las rutas actuales en config.json preservando otras claves."""
    try:
        existing = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(config)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def setup_session() -> None:
    """Inicializa variables en session_state."""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    if "show_routes" not in st.session_state:
        st.session_state["show_routes"] = False


def open_routes_editor() -> None:
    """Callback: muestra el editor de rutas."""
    st.session_state["show_routes"] = True
    st.rerun()


def close_routes_editor(new_config: dict | None = None) -> None:
    """
    Cierra el panel de modificación de rutas y, si se pasa una nueva configuración,
    comprueba las rutas y guarda en config.json si son válidas.
    """
    if new_config:
        ok, errors = verify_paths(new_config)

        if not ok:
            st.sidebar.error("❌ No se encontraron los siguientes archivos:")
            for err in errors:
                st.sidebar.error(f"- {err}")
            return

        save_config(new_config)
        st.session_state["config"] = new_config
        st.toast("✅ Rutas guardadas correctamente")

    st.session_state["show_routes"] = False
    st.rerun()


def verify_paths(config: dict) -> tuple[bool, list[str]]:
    """Verifica que todas las rutas existan. Devuelve (ok, lista_errores)."""
    errors = [f"{nombre}: {ruta}" for nombre, ruta in config.items() if not os.path.exists(ruta)]
    return (len(errors) == 0, errors)


def get_placeholder(config: dict, key: str) -> str:
    """Devuelve un placeholder: usa la ruta guardada o un valor por defecto si está vacío."""
    ruta = config.get(key, "")
    return ruta if ruta else f"Inserte la ruta del archivo {key} aquí"

def route_editor(config: dict) -> None:
    st.sidebar.subheader("📁 Modificar fuentes de datos")
    

    entries = [
        (PROGRAM_SICUE_OUT, "📘 SICUE OUT"),
        (PROGRAM_ERASMUS_IN, "🌍 Erasmus IN"),
        (PROGRAM_ERASMUS_OUT, "✈️ Erasmus OUT"),
    ]


    # Inicializar new_config con los valores actuales de todos los campos
    new_config = {}
    for key, label in entries:
        col_text, col_btn = st.sidebar.columns([8, 2])

        text_key = f"rt_{key}"
        buf_key  = f"__set_{text_key}"
        btn_key  = f"btn_open_{key}"

        # 1) Sembrar desde config si no existe en session_state
        if text_key not in st.session_state:
            st.session_state[text_key] = config.get(key, "")

        # 2) Aplicar buffer (si se eligió archivo) ANTES de instanciar el input
        if buf_key in st.session_state:
            st.session_state[text_key] = st.session_state.pop(buf_key)

        # 3) Input
        col_text.text_input(
            label,
            key=text_key,
            placeholder=get_placeholder(config, key)
        )

        # 4) Botón 📁: abrir selector PowerShell y poner la ruta en el input
        col_btn.text("")  # espacio para que no suba el boton
        col_btn.text("")

        if col_btn.button("📁", key=btn_key, help="Seleccionar archivo del equipo"):
            current_val = st.session_state.get(text_key, "")
            path = pick_local_file(current_val)
            if path:
                st.session_state[buf_key] = path
                st.rerun()

        # 5) Al construir la nueva config, usar el valor del input si existe, si no, el valor previo
        val = st.session_state.get(text_key, None)
        if val is not None and val.strip() != "":
            new_config[key] = val
        else:
            new_config[key] = config.get(key, "")
    st.sidebar.markdown(
        """
        <a href='https://mariapicazosanchez.github.io/TFG-MariaPicazoSanchez/excel_structure.html' target='_blank' style="
            display: block;
            width: 100%;
            background: #e3f2fd;
            color: #1565c0;
            font-weight: 600;
            padding: 0.4em 1em;
            border-radius: 6px;
            text-decoration: none;
            margin-bottom: 0.7em;
            text-align: center;
            box-sizing: border-box;
            transition: background 0.2s, color 0.2s;">
            📄 Ver ejemplo de estructura
        </a>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.sidebar.columns(2)
    if col1.button("❌", use_container_width=True):
        st.sidebar.info("No se han guardado cambios.")
        st.session_state["show_routes"] = False
        st.rerun()
    if col2.button("💾", use_container_width=True):
        close_routes_editor(new_config)

def _unique_sheets_from_config(cfg: dict) -> list[str]:
    """Devuelve la lista de hojas únicas (union) ignorando '__CSV__'."""
    sheets_map = cfg.get("sheets", {}) or {}
    names = set()
    for _type, lst in sheets_map.items():
        for name in (lst or []):
            if name and str(name) != "__CSV__" and _is_academic_year(str(name)):
                names.add(str(name))
    return sorted(names)


def sidebar_controls() -> tuple[str | None, st.delta_generator.DeltaGenerator | None]:
    """Crea la barra lateral con filtros y gestión de rutas."""
    # Establecer ancho del sidebar a 400px
    st.markdown(
        """
        <style>
        /* ── SIDEBAR ──────────────────────────────────────────────────
           Especificidad [0,2,0] → gana al CSS del launcher [0,1,0].
           NO tocamos height ni min-height: Streamlit (height:100%) +
           el launcher (min-height:calc(100vh/zoom)) los gestionan. */
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width:  325px;
            max-width:  450px;
            overflow-x: hidden !important;
            overflow-y: auto   !important; /* scroll solo si el contenido no cabe */
        }

        /* El div interior con especificidad [0,2,0] para ganar al launcher.
           overflow:hidden evita que su contenido "sangre" hacia el contenedor
           externo y dispare el scroll aunque visualmente todo quepa. */
        [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
            overflow:   hidden !important;
            height:     auto   !important;
            min-height: 0      !important;
        }

        /* Ocultar la barra de scroll en todo el sidebar
           (el scroll sigue funcionando con rueda del ratón) */
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] * {
            scrollbar-width:    none !important; /* Firefox */
            -ms-overflow-style: none !important; /* IE / Edge */
        }
        [data-testid="stSidebar"]::-webkit-scrollbar,
        [data-testid="stSidebar"] *::-webkit-scrollbar {
            display: none !important;
            width:   0    !important;
            height:  0    !important;
        }

        /* ── STREAMLIT HEADER / TOOLBAR ──────────────────────────────
           En pywebview la barra de título es nativa (OS). El header de
           Streamlit (botón Deploy, menú ⋮) ocupa ~2.875rem de alto y
           fuerza a stMainBlockContainer a añadir padding-top enorme.
           Lo ocultamos para que el contenido use todo el espacio. */
        [data-testid="stHeader"] {
            display: none !important;
            height:  0    !important;
        }

        /* ── MAIN CONTENT ─────────────────────────────────────────────
           Eliminar todos los paddings por defecto de Streamlit para que
           el contenido ocupe el área completa igual que el mapa.
           El mapa sobre-escribe esto con position:absolute+inset:0
           (especificidad [0,2,0] > [0,1,0] aquí), así que no le afecta. */
        [data-testid="stMainBlockContainer"] {
            padding-top:    1rem !important;
            padding-left:   1rem !important;
            padding-right:  1rem !important;
            padding-bottom: 0    !important;
            box-sizing:     border-box !important;
            width:          100% !important;
        }

        /* El hijo directo de stMainBlockContainer es el wrapper que
           Streamlit añade con margin-bottom: 1rem (16 px).
           Con zoom ≠ 1, esos 16 px hacen que el contenido supere la
           altura de stMain → scrollbar oculto → al aplicar hCalc el
           mapa no llega al borde → franja de fondo oscuro visible.
           Fijamos margin-bottom: 0 para que stMainBlockContainer
           border-box = padTop + iframe(hCalc) = stMain exactamente. */
        [data-testid="stMainBlockContainer"] > div {
            margin-bottom: 0 !important;
        }

        /* ── MAP IFRAME ───────────────────────────────────────────────
           Altura mínima de seguridad para el iframe del mapa. */
        [data-map-frame] {
            min-height: 300px !important;
        }

        /* ── STREAMLIT STATUS BAR ─────────────────────────────────────
           stBottom es position:fixed al fondo del viewport y tapa
           la parte inferior del mapa con una franja oscura.
           Ocultamos el contenedor exterior y el interior. */
        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"] {
            display: none !important;
            height:  0    !important;
        }

        /* ── ZOOM BODY FIX ────────────────────────────────────────────
           Cuando el launcher aplica zoom al body, la altura visual del
           body es zoom × 100% del viewport → deja una franja negra.
           El script de abajo inyecta min-height: calc(100% / zoom)
           para que el body llene la ventana visualmente. */
        </style>
        """,
        unsafe_allow_html=True
    )

    # ── ZOOM LAYOUT FIX ────────────────────────────────────────────────────────
    # Ajuste de layout dinámico para body.style.zoom del launcher.
    #
    # El launcher gestiona:  body.style.zoom,  body/html overflow,  hCalc del mapa.
    # Este fragmento gestiona únicamente la cadena de alturas de Streamlit para
    # que stApp llene siempre el viewport visualmente, sin scroll de página ni
    # franja negra debajo del contenido:
    #
    #   stApp       → height = 100vh / zoom  (ocupa exactamente el viewport)
    #   stAppViewContainer → 100% de stApp
    #   stMain      → 100% con overflow-y:auto  (scroll interno en vista stats)
    #   stMainBlockContainer → height:auto  (flujo natural del contenido)
    #
    # El style se mueve al final de <head> en cada llamada para ganar sobre
    # reglas anteriores con la misma especificidad.
    with st.sidebar:
        st.components.v1.html(
            """<script>
(function() {
    try {
        var p   = window.parent;
        var SID = '__zoom_layout_fix';

        function applyFix() {
            var zoom = parseFloat(p.document.body.style.zoom) || 1.0;
            // inv = 1/zoom  →  stApp altura CSS tal que visual = 100vh
            // Ej: zoom=1.1 → inv≈0.909 → stApp=818px CSS → 818×1.1=900px visual ✓
            //     zoom=0.9 → inv≈1.111 → stApp=1000px CSS → 1000×0.9=900px visual ✓
            var inv = (1 / zoom).toFixed(6);

            // Obtener o crear nuestro <style> y moverlo al final de <head>
            // para que tenga prioridad sobre reglas anteriores del launcher.
            var s = p.document.getElementById(SID);
            if (!s) {
                s = p.document.createElement('style');
                s.id = SID;
            }
            p.document.head.appendChild(s);

            // El overflow de html/body lo gestiona exclusivamente el launcher:
            //   zoom < 1 → overflow:hidden (evita scroll cuando body encoge)
            //   zoom ≥ 1 → overflow:''    (libre; stApp llena viewport exacto)
            // No lo tocamos aquí para no interferir con body.style.zoom.

            s.textContent = [
                // stApp ocupa exactamente el viewport en píxeles visuales
                '[data-testid="stApp"] {',
                '  height:   calc(100vh * ' + inv + ') !important;',
                '  overflow: hidden                     !important;',
                '}',
                // stAppViewContainer llena stApp
                '[data-testid="stAppViewContainer"] {',
                '  height:   100% !important;',
                '  overflow: hidden !important;',
                '}',
                // stMain llena stAppViewContainer. El scroll se delega a
                // stMainBlockContainer para que height:100% en el hijo funcione
                // correctamente en WebView2 (min-height:100% en flex items es
                // poco fiable en Chromium cuando el padre usa overflow:auto).
                '[data-testid="stMain"] {',
                '  height:   100%   !important;',
                '  overflow: hidden !important;',
                '}',
                // stMainBlockContainer: height:100% lo ancla exactamente a
                // stMain (llena todo el viewport → sin franja oscura aunque el
                // contenido sea corto). overflow-y:auto permite scroll cuando
                // el contenido supera la altura del viewport.
                // El mapa sobreescribe esto con position:absolute+inset:0
                // (especificidad [0,2,0] > [0,1,0]) → no le afecta.
                '[data-testid="stMainBlockContainer"] {',
                '  height:         100% !important;',
                '  overflow-y:     auto !important;',
                '  min-height:     0    !important;',
                '  padding-bottom: 0    !important;',
                '}',
            ].join('\\n');
        }

        applyFix();
        setTimeout(applyFix,  400);  // reintento: zoom puede no haberse aplicado aún
        setTimeout(applyFix, 1500);  // reintento de seguridad

        // Reaccionar cuando el launcher cambie body.style (zoom)
        new MutationObserver(applyFix).observe(p.document.body, {
            attributes: true, attributeFilter: ['style']
        });

        // Mantener el fix al redimensionar la ventana
        p.addEventListener('resize', applyFix);

    } catch(e) { /* silencioso en producción */ }
})();
</script>""",
            height=0,
        )

    if "view" not in st.session_state:
        st.session_state["view"] = "map"

    search_slot = None

    if st.session_state["view"] == "new_user":
        if st.sidebar.button("⬅️ Volver al mapa", use_container_width=True):
            st.session_state["view"] = "map"
            st.rerun()

    elif st.session_state["view"] == "stats":
        if st.sidebar.button("⬅️ Volver al mapa", use_container_width=True):
            st.session_state["view"] = "map"
            st.rerun()
        st.sidebar.markdown(
            "<p style='font-size: 0.9rem; color: #6c757d;'>"
            "Selecciona un curso académico y un tipo de movilidad para ver los datos agregados."
            "</p>",
            unsafe_allow_html=True,
        )
        cfg = st.session_state.get("config", {})
        available_courses = _unique_sheets_from_config_or_files(cfg)
        from domain import render_filters_stats
        render_filters_stats(available_courses)
    else:
        # ==========
        #  FILTROS
        # ==========
        st.sidebar.markdown(
            "<p style='font-size: 0.9rem; color: #6c757d;'>"
            "Utiliza los filtros para buscar estudiantes específicos en el mapa."
            "</p>",
            unsafe_allow_html=True,
        )
        cfg = st.session_state.get("config", {})
        unique_sheets = _unique_sheets_from_config_or_files(cfg)
        from domain import render_filters_map
        base_map = render_filters_map(unique_sheets)

        # Placeholder para el buscador debajo de los botones de filtros
        st.sidebar.markdown("**Buscar alumno, ciudad, universidad...**")
        search_slot = st.sidebar.container()

        st.sidebar.markdown("---")
        # Botón para crear estudiante (esto no es filtro, lo dejamos aquí)
        if st.sidebar.button("👤 Crear nuevo estudiante", use_container_width=True):
            st.session_state["view"] = "new_user"
            st.rerun()
        st.sidebar.markdown(
            "<p style='font-size: 0.9rem; color: #6c757d;'>"
            "Registra un nuevo estudiante en el sistema."
            "</p>",
            unsafe_allow_html=True,
        )
                
        # Botón para estadísticas
        if st.sidebar.button("📊 Ver estadísticas", use_container_width=True):
            st.session_state["view"] = "stats"
            st.rerun()
        st.sidebar.markdown(
            "<p style='font-size: 0.9rem; color: #6c757d;'>"
            "Visualiza estadísticas agregadas de movilidad."
            "</p>",
            unsafe_allow_html=True,
        )
        # ==========================
        #  GESTIÓN DE RUTAS
        # ==========================
        # Abrir automáticamente el gestor de rutas si no existe config.json
        if not os.path.exists(CONFIG_FILE) and not st.session_state.get("show_routes", False):
            st.session_state["show_routes"] = True

        st.sidebar.markdown("---")
        if st.session_state["show_routes"]:
            route_editor(st.session_state["config"])
        else:
            if st.sidebar.button("✏️ Fuentes de datos", use_container_width=True):
                open_routes_editor()
            st.sidebar.markdown(
                "<p style='font-size: 0.9rem; color: #6c757d;'>"
                "Configura las rutas de los archivos de datos (Excel/CSV)."
                "</p>",
                unsafe_allow_html=True,
            )

        return base_map, search_slot

    return None, search_slot
