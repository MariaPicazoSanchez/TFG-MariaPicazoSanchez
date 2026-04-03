"""
Sidebar principal de la aplicación.

Responsabilidades:
  - setup_session     — inicializa session_state
  - route_editor      — UI del editor de fuentes de datos
  - sidebar_controls  — barra lateral completa (filtros, navegación, rutas)
"""

import os

import streamlit as st

from ._sidebar_config import (
    CONFIG_FILE,
    get_placeholder,
    load_config,
    pick_local_file,
    save_config,
    verify_paths,
    _unique_sheets_from_config_or_files,
)
from ._sidebar_styles import SIDEBAR_CSS, SIDEBAR_TOGGLE_JS, ZOOM_FIX_JS
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT


# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────

def setup_session() -> None:
    """Inicializa variables en session_state."""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    if "show_routes" not in st.session_state:
        st.session_state["show_routes"] = False


# ─────────────────────────────────────────────────────────────────────────────
# Gestión del editor de rutas
# ─────────────────────────────────────────────────────────────────────────────

def open_routes_editor() -> None:
    st.session_state["show_routes"] = True
    st.rerun()


def close_routes_editor(new_config: dict | None = None) -> None:
    """Cierra el editor de rutas; si se pasa new_config, verifica y guarda."""
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


def route_editor(config: dict) -> None:
    """Componente UI para editar las fuentes de datos."""
    st.sidebar.subheader("📁 Modificar fuentes de datos")

    entries = [
        (PROGRAM_SICUE_OUT,  "📘 SICUE OUT"),
        (PROGRAM_ERASMUS_IN, "🌍 Erasmus IN"),
        (PROGRAM_ERASMUS_OUT, "✈️ Erasmus OUT"),
    ]

    new_config: dict = {}
    for key, label in entries:
        col_text, col_btn = st.sidebar.columns([8, 2])
        text_key = f"rt_{key}"
        buf_key  = f"__set_{text_key}"
        btn_key  = f"btn_open_{key}"

        if text_key not in st.session_state:
            st.session_state[text_key] = config.get(key, "")
        if buf_key in st.session_state:
            st.session_state[text_key] = st.session_state.pop(buf_key)

        col_text.text_input(label, key=text_key, placeholder=get_placeholder(config, key))
        col_btn.text("")
        col_btn.text("")

        if col_btn.button("📁", key=btn_key, help="Seleccionar archivo del equipo"):
            path = pick_local_file(st.session_state.get(text_key, ""))
            if path:
                st.session_state[buf_key] = path
                st.rerun()

        val = st.session_state.get(text_key, None)
        new_config[key] = val.strip() if val and val.strip() else config.get(key, "")

    st.sidebar.markdown(
        """
        <a href='https://mariapicazosanchez.github.io/TFG-MariaPicazoSanchez/excel_structure.html'
           target='_blank'
           style="display:block;width:100%;background:#e3f2fd;color:#1565c0;font-weight:600;
                  padding:0.4em 1em;border-radius:6px;text-decoration:none;margin-bottom:0.7em;
                  text-align:center;box-sizing:border-box;transition:background 0.2s,color 0.2s;">
            📄 Ver ejemplo de estructura
        </a>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.sidebar.columns(2)
    if col1.button("❌", use_container_width=True):
        st.sidebar.info("No se han guardado cambios.")
        st.session_state["show_routes"] = False
        st.rerun()
    if col2.button("💾", use_container_width=True):
        close_routes_editor(new_config)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar principal
# ─────────────────────────────────────────────────────────────────────────────

def sidebar_controls() -> tuple[str | None, st.delta_generator.DeltaGenerator | None]:
    """Crea la barra lateral con filtros y gestión de rutas."""

    # CSS global de layout
    st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)

    # Botón flotante para expandir el sidebar cuando está colapsado
    st.components.v1.html(SIDEBAR_TOGGLE_JS, height=0)

    # Zoom layout fix (dentro del sidebar para acceder a window.parent)
    with st.sidebar:
        st.components.v1.html(ZOOM_FIX_JS, height=0)

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
            "<p style='font-size:0.9rem;color:#6c757d;'>"
            "Selecciona un curso académico y un tipo de movilidad para ver los datos agregados."
            "</p>",
            unsafe_allow_html=True,
        )
        cfg = st.session_state.get("config", {})
        from domain import render_filters_stats
        render_filters_stats(_unique_sheets_from_config_or_files(cfg))

    else:
        # ── Vista mapa ─────────────────────────────────────────────────────
        st.sidebar.markdown(
            "<p style='font-size:0.9rem;color:#6c757d;'>"
            "Utiliza los filtros para buscar estudiantes específicos en el mapa."
            "</p>",
            unsafe_allow_html=True,
        )
        cfg = st.session_state.get("config", {})
        from domain import render_filters_map
        base_map = render_filters_map(_unique_sheets_from_config_or_files(cfg))

        st.sidebar.markdown("**Buscar alumno, ciudad, universidad...**")
        search_slot = st.sidebar.container()
        st.sidebar.markdown("---")

        if st.sidebar.button("👤 Crear nuevo estudiante", use_container_width=True):
            st.session_state["view"] = "new_user"
            st.rerun()
        st.sidebar.markdown(
            "<p style='font-size:0.9rem;color:#6c757d;'>"
            "Registra un nuevo estudiante en el sistema."
            "</p>",
            unsafe_allow_html=True,
        )

        if st.sidebar.button("📊 Ver estadísticas", use_container_width=True):
            st.session_state["view"] = "stats"
            st.rerun()
        st.sidebar.markdown(
            "<p style='font-size:0.9rem;color:#6c757d;'>"
            "Visualiza estadísticas agregadas de movilidad."
            "</p>",
            unsafe_allow_html=True,
        )

        # Abrir automáticamente si no existe config
        if not os.path.exists(CONFIG_FILE) and not st.session_state.get("show_routes", False):
            st.session_state["show_routes"] = True

        st.sidebar.markdown("---")
        if st.session_state["show_routes"]:
            route_editor(st.session_state["config"])
        else:
            if st.sidebar.button("✏️ Fuentes de datos", use_container_width=True):
                open_routes_editor()
            st.sidebar.markdown(
                "<p style='font-size:0.9rem;color:#6c757d;'>"
                "Configura las rutas de los archivos de datos (Excel/CSV)."
                "</p>",
                unsafe_allow_html=True,
            )

        return base_map, search_slot

    return None, search_slot
