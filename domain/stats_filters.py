from __future__ import annotations

import streamlit as st

MOBILITY_OPTIONS = ["Todos", "Erasmus OUT", "Erasmus IN", "SICUE OUT"]

MOBILITY_LABELS = {
    "Todos": "Todos",
    "Erasmus OUT": "Erasmus OUT",
    "Erasmus IN": "Erasmus IN",
    "SICUE OUT": "SICUE OUT",
}


def render_filters_stats(available_courses: list[str]) -> None:
    """
    Filtros para la vista de estadísticas.
    - Desplegable de curso académico (hoja).
    - Botonera para tipo de movilidad (chips).
    Todo se guarda en st.session_state.
    """
    # ===========================
    # CABECERA DE SECCIÓN
    # ===========================
    st.sidebar.markdown("## 📊 Ver estadísticas")
    st.sidebar.markdown(
        """
        <p style="font-size: 0.9rem; color: #6c757d;">
            Configura los filtros para explorar las estadísticas de movilidad.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # ===========================
    # CURSO ACADÉMICO (HOJA)
    # ===========================
    with st.sidebar.container():
        st.markdown("#### 📅 Curso académico", unsafe_allow_html=True)

        if available_courses:
            default_course = (
                st.session_state.get("stats_course")
                or st.session_state.get("global_sheet")
                or available_courses[0]
            )
            if default_course not in available_courses:
                default_course = available_courses[0]

            curso = st.selectbox(
                "",
                options=available_courses,
                index=available_courses.index(default_course),
                key="stats_course",
                help="Cada curso suele corresponder a una hoja del Excel (ej. 2023/2024).",
                label_visibility="collapsed",
            )

            # Por coherencia con el mapa usamos también global_sheet
            st.session_state["global_sheet"] = curso
        else:
            st.info("No hay cursos disponibles. Revisa las hojas en los Excels.")
            st.session_state["stats_course"] = None

    st.sidebar.markdown("---")

    # ===========================
    # TIPO DE MOVILIDAD (BOTONES)
    # ===========================
    st.sidebar.markdown("#### 🚀 Tipo de movilidad")
    st.sidebar.markdown(
        """
        <p style="font-size: 0.85rem; color: #6c757d; margin-bottom: 0.2rem;">
            Elige el tipo de movilidad a filtrar. Puedes ver todos o solo uno.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # Valor actual
    current = st.session_state.get("stats_mobility", "Todos")
    if current not in MOBILITY_OPTIONS:
        current = "Todos"
        st.session_state["stats_mobility"] = "Todos"

    # Botones en 2 filas x 2 columnas
    rows = [
        ["Todos", "Erasmus OUT"],
        ["Erasmus IN", "SICUE OUT"],
    ]

    for row in rows:
        cols = st.sidebar.columns(2, gap="small")
        for opt, col in zip(row, cols):
            label = MOBILITY_LABELS.get(opt, opt)
            is_selected = (current == opt)

            # type="primary" para el seleccionado, "secondary" para el resto
            clicked = col.button(
                label,
                use_container_width=True,
                key=f"mob_btn_{opt}",
                type="primary" if is_selected else "secondary",
            )

            if clicked:
                st.session_state["stats_mobility"] = opt
                st.session_state["view"] = "stats"  # para no perder la vista

    # Resumen de filtros activos
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"""
        <div style="font-size: 0.8rem; color: #6c757d;">
            <strong>Filtro activo:</strong><br>
            Curso: <code>{st.session_state.get("stats_course", "—")}</code><br>
            Movilidad: <code>{st.session_state.get("stats_mobility", "Todos")}</code>
        </div>
        """,
        unsafe_allow_html=True,
    )
