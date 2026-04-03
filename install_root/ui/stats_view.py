
import streamlit as st

from . import stats_details as details
from .stats_table import render_stats_table
from .stats_helpers import (
    load_students_for_course,
    load_erasmus_in_raw,
    stats_by_mobility,
    stats_by_country,
    stats_by_city,
    build_export_xlsx,
    selections_from_state,
    config_fp_from_state,
)
from constants import MOBILITY_OPTIONS, PROGRAM_SICUE_OUT


# ────────────────────────────────────────────────────────────────────────────────
# Filtros del sidebar
# ────────────────────────────────────────────────────────────────────────────────

def render_filters_stats(available_courses: list[str]) -> None:
    st.sidebar.markdown("## 📊 Ver estadísticas")
    st.sidebar.markdown(
        "<p style='font-size: 0.9rem; color: #6c757d;'>"
        "Selecciona un curso académico y un tipo de movilidad para ver los datos agregados."
        "</p>",
        unsafe_allow_html=True,
    )

    if available_courses:
        default_course = (
            st.session_state.get("stats_course")
            or st.session_state.get("global_sheet")
            or available_courses[0]
        )
        if default_course not in available_courses:
            default_course = available_courses[0]

        curso = st.sidebar.selectbox(
            "📅 Curso académico",
            options=available_courses,
            index=available_courses.index(default_course),
            key="stats_course",
            help="Cada curso suele corresponder a una hoja del Excel (ej. 2023/2024).",
        )
        st.session_state["global_sheet"] = curso
    else:
        st.sidebar.info("No hay cursos disponibles. Revisa las hojas en los Excels.")
        st.session_state["stats_course"] = None

    st.sidebar.markdown("---")

    st.session_state.setdefault("stats_mobility", "Todos")
    st.sidebar.markdown("#### Tipo de movilidad")
    st.sidebar.markdown(
        "<p style='font-size: 0.85rem; color: #6c757d;'>"
        "Puedes mostrar todos los tipos o filtrar solo uno."
        "</p>",
        unsafe_allow_html=True,
    )
    st.sidebar.radio(label="", options=MOBILITY_OPTIONS, key="stats_mobility")
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<p style='font-size: 0.8rem; color: #6c757d;'>"
        "Los datos se actualizan automáticamente al cambiar el curso o el tipo de movilidad."
        "</p>",
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────────────
# Vista principal
# ────────────────────────────────────────────────────────────────────────────────

def render_stats_view() -> None:
    st.header("📊 Ver estadísticas")

    config = st.session_state.get("config", {}) or {}
    course = st.session_state.get("stats_course") or st.session_state.get("global_sheet")

    if not course:
        st.info("Selecciona un curso académico en la barra lateral para ver las estadísticas.")
        return

    mobility_filter = st.session_state.get("stats_mobility", "Todos")

    df = load_students_for_course(config, course)
    if df.empty:
        st.warning(
            f"No hay datos para el curso académico **{course}** "
            "en los Excels configurados para Erasmus/SICUE."
        )
        return

    st.markdown(
        f"**Curso académico:** `{course}`  |  "
        f"**Tipo de movilidad:** `{mobility_filter}`"
    )
    st.markdown("---")

    col_tipo = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"

    if mobility_filter and mobility_filter != "Todos":
        df_filtered = df[df[col_tipo] == mobility_filter].copy()
    else:
        df_filtered = df.copy()

    if df_filtered.empty:
        st.info(
            f"No hay datos para el curso **{course}** con el tipo de movilidad "
            f"**{mobility_filter}**."
        )
        return

    # ── Fila de tablas ───────────────────────────────────────────────────────
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("Alumnos por tipo de movilidad")
        tabla_tipo = stats_by_mobility(df)
        if tabla_tipo.empty:
            st.info("No se han encontrado alumnos con información de tipo de movilidad.")
        else:
            render_stats_table(tabla_tipo)

    with col2:
        if mobility_filter == PROGRAM_SICUE_OUT:
            st.subheader("Alumnos por ciudad (SICUE OUT)")
            tabla_geo = stats_by_city(df_filtered)
            if tabla_geo.empty:
                st.info(
                    "No se ha podido generar la tabla por ciudad; comprueba que exista alguna "
                    "columna de ciudad en el Excel (por ejemplo 'ciudad_sicue' o 'ciudad')."
                )
                return
        else:
            st.subheader("Alumnos por país")
            tabla_geo = stats_by_country(df_filtered)
            if tabla_geo.empty:
                st.info(
                    "No se ha podido generar la tabla por país; comprueba que exista una columna "
                    "de país ('pais', 'país', 'pais_out', 'pais_in', etc.) en tus Excels."
                )
                return
        render_stats_table(tabla_geo)

    # ── Exportar Excel ───────────────────────────────────────────────────────
    if st.session_state.get("export_generate"):
        xlsx_bytes, filename = build_export_xlsx(
            course=course,
            selections=selections_from_state(),
            config_fp=config_fp_from_state(),
        )
        st.session_state["export_xlsx_bytes"] = xlsx_bytes
        st.session_state["export_xlsx_name"]  = filename
        st.session_state["export_generate"]   = False

    xlsx_bytes = st.session_state.get("export_xlsx_bytes")
    xlsx_name  = st.session_state.get("export_xlsx_name")
    if xlsx_bytes and xlsx_name:
        import base64
        import streamlit.components.v1 as components

        xlsx_b64 = base64.b64encode(xlsx_bytes).decode("utf-8")
        components.html(f"""
<button onclick=\"saveExcelFile()\">💾 Guardar Excel</button>
<script>
function saveExcelFile() {{
    if (!window.pywebview) {{ alert('pywebview NO disponible'); return; }}
    window.pywebview.api.save_file(
        'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{xlsx_b64}',
        '{xlsx_name}'
    ).then(r => {{ alert(JSON.stringify(r)); }}).catch(e => {{ alert('ERROR: ' + e); }});
}}
</script>
""", height=120)
        st.download_button(
            label="⬇️ Descargar Excel",
            data=xlsx_bytes,
            file_name=xlsx_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Detalles y resumen ───────────────────────────────────────────────────
    df_erasmus_raw = load_erasmus_in_raw(config, course)
    details.render_stats_details(df_filtered, mobility_filter, df_erasmus_raw)

    st.markdown("---")
    st.markdown(
        f"📌 **Resumen**: {len(df_filtered)} alumnos en el curso `{course}` "
        f"para el filtro de tipo de movilidad `{mobility_filter}`."
    )
