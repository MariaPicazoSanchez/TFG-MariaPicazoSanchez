from __future__ import annotations

import streamlit as st

from ui import stats_helpers as sh


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
                " ",
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
    st.sidebar.markdown("#### Tipo de movilidad")
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

    st.sidebar.markdown("---")
    st.session_state.setdefault("export_panel_open", False)
    # Estado por defecto de opciones de exportación
    st.session_state.setdefault("export_panel_open", False)

    st.session_state.setdefault("exp_mobility", True)
    st.session_state.setdefault("exp_country_all", True)
    st.session_state.setdefault("exp_country_by_type", False)
    st.session_state.setdefault("exp_country_by_type_types", ["Erasmus OUT", "Erasmus IN", "SICUE OUT"])

    st.session_state.setdefault("exp_subject_in", False)

    st.session_state.setdefault("exp_university", False)
    st.session_state.setdefault("exp_university_types", ["Todos"])
    # Botón de abrir/cerrar panel de exportación
    export_clicked = st.sidebar.button(
        "📥 Exportar tablas",
        use_container_width=True,
        key="export_tables_btn",
        type="secondary",
    )

    if export_clicked:
        st.session_state["export_panel_open"] = not st.session_state["export_panel_open"]
        # al abrir: limpia export anterior
        if st.session_state["export_panel_open"]:
            st.session_state.pop("export_xlsx_bytes", None)
            st.session_state.pop("export_xlsx_name", None)

    # SOLO mostramos opciones si está abierto
    if st.session_state["export_panel_open"]:
        with st.sidebar.expander("📦 Opciones de exportación", expanded=True):
            st.checkbox("Num de alumnos por tipo de movilidad", key="exp_mobility")
            st.checkbox("Num de alumnos por país (todos los tipos)", key="exp_country_all")

            st.checkbox("Num de alumnos por país/ciudad por tipo de movilidad", key="exp_country_by_type")
            if st.session_state["exp_country_by_type"]:
                st.multiselect(
                    "Tipos a incluir",
                    ["Erasmus OUT", "Erasmus IN", "SICUE OUT"],
                    key="exp_country_by_type_types",
                )

            st.checkbox("Num de alumnos por asignatura (solo Erasmus IN)", key="exp_subject_in")

            st.checkbox("Num de alumnos por universidad", key="exp_university")
            if st.session_state["exp_university"]:
                st.multiselect(
                    "Tipos a incluir",
                    ["Todos", "Erasmus OUT", "Erasmus IN", "SICUE OUT"],
                    key="exp_university_types",
                )

            course = st.session_state.get("stats_course") or st.session_state.get("global_sheet")
            config_fp = sh.config_fp_from_state()
            selections = sh.selections_from_state()

            if not course:
                st.info("Selecciona un curso para poder generar el Excel.")
            else:
                xlsx_bytes, xlsx_name = sh.build_export_xlsx(course, selections, config_fp)

                st.download_button(
                    "Generar Excel",
                    data=xlsx_bytes,
                    file_name=xlsx_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="secondary",
                    on_click=lambda: st.session_state.__setitem__("export_panel_open", False),
                )
           
                st.session_state["export_generate"] = True
                st.session_state["view"] = "stats"

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
