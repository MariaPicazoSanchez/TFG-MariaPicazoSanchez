from __future__ import annotations

import streamlit as st
from ui import stats_helpers as sh
from constants import MOBILITY_OPTIONS, MOBILITY_LABELS


def render_filters_stats(available_courses: list[str]) -> None:
    """
    Filtros para la vista de estadísticas.
    - Desplegable de curso académico (hoja).
    - Botonera para tipo de movilidad (chips).
    Todo se guarda en st.session_state.
    """
    if "export_open" not in st.session_state:
        st.session_state["export_open"] = False
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

    def _set_mobility(opt: str) -> None:
        st.session_state["stats_mobility"] = opt
        st.session_state["view"] = "stats"

    for row in rows:
        cols = st.sidebar.columns(2, gap="small")
        for opt, col in zip(row, cols):
            label = MOBILITY_LABELS.get(opt, opt)
            # Leer current AQUÍ para que refleje el valor ya actualizado por on_click
            is_selected = (st.session_state.get("stats_mobility", "Todos") == opt)

            col.button(
                label,
                width='stretch',
                key=f"mob_btn_{opt}",
                type="primary" if is_selected else "secondary",
                on_click=_set_mobility,
                args=(opt,),
            )

    st.sidebar.markdown("---")

    # Estado por defecto de opciones de exportación
    st.session_state["export_panel_open"] = False
    st.session_state.setdefault("exp_mobility", True)
    st.session_state.setdefault("exp_country_all", True)
    st.session_state.setdefault("exp_country_by_type", False)
    st.session_state.setdefault("exp_country_by_type_types", ["Erasmus OUT", "Erasmus IN", "SICUE OUT"])
    st.session_state.setdefault("exp_subject_in", False)
    st.session_state.setdefault("exp_university", False)
    st.session_state.setdefault("exp_university_types", ["Todos"])

    # ===========================
    # BOTÓN DE EXPORTAR EXCEL
    # ===========================
    if not st.session_state["export_open"]:
        export_clicked = st.sidebar.button(
            "📥 Exportar a Excel",
            width='stretch',
            key="export_tables_btn",
            type="secondary",
        )
        if export_clicked:
            st.session_state["export_open"] = True
            st.rerun()  # para que desaparezca el botón y aparezca el expander ya en el siguiente render
    else:
        with st.sidebar.expander("📦 Opciones de exportación", expanded=True):

            st.markdown("**Selecciona las tablas a incluir en el Excel:**")

            # Sección: Movilidad
            st.markdown("##### Por tipo de movilidad")
            st.checkbox(
                "Total de alumnos por tipo",
                key="exp_mobility",
                help="Incluye una tabla con el total de alumnos para cada tipo de movilidad",
            )

            # Sección: País/Ciudad
            st.markdown("##### Por país y ciudad")
            st.checkbox(
                "Total de alumnos por país",
                key="exp_country_all",
                help="Incluye tabla con todos los países combinados",
            )

            st.checkbox(
                "Alumnos por país/ciudad (por tipo)",
                key="exp_country_by_type",
                help="Incluye tablas separadas por cada tipo de movilidad en una hoja",
            )

            st.multiselect(
                "Selecciona tipos:",
                ["Erasmus OUT", "Erasmus IN", "SICUE OUT"],
                default=st.session_state["exp_country_by_type_types"],
                key="exp_country_by_type_types",
                help="Elige qué tipos incluir en la exportación",
            )

            # Sección: Asignaturas
            st.markdown("##### Por asignatura")
            st.checkbox(
                "Asignaturas más frecuentes (Erasmus IN)",
                key="exp_subject_in",
                help="Incluye tabla con las asignaturas cursadas en Erasmus IN",
            )

            # Sección: Universidades
            st.markdown("##### Por universidad")
            st.checkbox(
                "Alumnos por universidad",
                key="exp_university",
                help="Incluye tabla con el número de alumnos por universidad destino/origen",
            )

            st.multiselect(
                "Selecciona tipos:",
                ["Todos", "Erasmus OUT", "Erasmus IN", "SICUE OUT"],
                default=st.session_state["exp_university_types"],
                key="exp_university_types",
                help="Elige qué tipos incluir. 'Todos' incluye datos agregados de todos los tipos",
            )

            course = st.session_state.get("stats_course") or st.session_state.get("global_sheet")
            config_fp = sh.config_fp_from_state()
            selections = sh.selections_from_state()

            if not course:
                st.warning("⚠️ Selecciona un curso académico para poder generar el Excel.")
            else:
                any_selected = (
                    st.session_state.get("exp_mobility", False)
                    or st.session_state.get("exp_country_all", False)
                    or st.session_state.get("exp_country_by_type", False)
                    or st.session_state.get("exp_subject_in", False)
                    or st.session_state.get("exp_university", False)
                )

                if not any_selected:
                    st.info("💡 Selecciona al menos una tabla para exportar.")
                else:
                    xlsx_bytes, xlsx_name = sh.build_export_xlsx(course, selections, config_fp)

                    downloaded = st.download_button(
                        "⬇️ Descargar Excel",
                        data=xlsx_bytes,
                        file_name=xlsx_name,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width='stretch',
                        type="secondary",
                    )

                    # Si quieres que tras descargar se cierre y vuelva el botón:
                    if downloaded:
                        st.session_state["export_open"] = False
                        st.rerun()


    # Resumen de filtros activos
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
