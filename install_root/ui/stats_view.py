from __future__ import annotations

import os
from typing import Iterable
import pandas as pd
import streamlit as st
from . import stats_details as details
from export import build_stats_excel
from constants import MOBILITY_PROGRAMS, MOBILITY_OPTIONS, PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT, SPAIN

MOBILITY_TYPES: tuple[str, ...] = MOBILITY_PROGRAMS


def render_filters_stats(available_courses: list[str]) -> None:
    """
    Filtros para la vista de estadísticas.
    - Desplegable de curso académico (hoja).
    - Filtro por tipo de movilidad.
    Todo se guarda en st.session_state.
    """
    st.sidebar.markdown("## 📊 Ver estadísticas")
    st.sidebar.markdown(
        "<p style='font-size: 0.9rem; color: #6c757d;'>"
        "Selecciona un curso académico y un tipo de movilidad para ver los datos agregados."
        "</p>",
        unsafe_allow_html=True,
    )

    # ===========================
    # CURSO ACADÉMICO (HOJA)
    # ===========================
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

    # ===========================
    # TIPO DE MOVILIDAD
    # ===========================
    mobility_options = MOBILITY_OPTIONS
    if "stats_mobility" not in st.session_state:
        st.session_state["stats_mobility"] = "Todos"

    st.sidebar.markdown("#### Tipo de movilidad")
    st.sidebar.markdown(
        "<p style='font-size: 0.85rem; color: #6c757d;'>"
        "Puedes mostrar todos los tipos o filtrar solo uno."
        "</p>",
        unsafe_allow_html=True,
    )

    st.sidebar.radio(
        label="",
        options=mobility_options,
        index=mobility_options.index(st.session_state["stats_mobility"]),
        key="stats_mobility",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "<p style='font-size: 0.8rem; color: #6c757d;'>"
        "Los datos se actualizan automáticamente al cambiar el curso o el tipo de movilidad."
        "</p>",
        unsafe_allow_html=True,
    )


# ────────────────────────────────────────────────────────────────────────────────
# Helpers de estado / selección
# ────────────────────────────────────────────────────────────────────────────────

def _get_selected_course() -> str | None:
    """
    Devuelve el curso académico seleccionado para estadísticas.
    Prioriza stats_course, luego global_sheet.
    """
    return st.session_state.get("stats_course") or st.session_state.get("global_sheet")


# ────────────────────────────────────────────────────────────────────────────────
# Helpers para cargar datos desde Excel
# ────────────────────────────────────────────────────────────────────────────────

def _read_sheet_safe(path: str, sheet_name: str) -> pd.DataFrame:
    """
    Lee una hoja concreta de un Excel, devolviendo DataFrame vacío si no existe
    o hay error. NO lanza excepción.
    """
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
        if df is None:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def _normalize_col_name(name: str) -> str:
    """
    Normaliza un nombre de columna para comparaciones flexibles:
    - minúsculas
    - sin espacios
    - sin acentos simples (á -> a, í -> i, etc.)
    """
    if not isinstance(name, str):
        name = str(name)
    s = name.strip().lower().replace(" ", "")
    reemplazos = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
    }
    for k, v in reemplazos.items():
        s = s.replace(k, v)
    return s


def _find_country_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """
    Busca en df una columna que coincida con alguno de los 'candidates'
    de forma flexible (ignorando mayúsculas, espacios y acentos).
    Devuelve el nombre REAL de la columna si la encuentra.
    """
    if df.empty:
        return None

    norm_to_real: dict[str, str] = {
        _normalize_col_name(col): col for col in df.columns
    }

    for cand in candidates:
        norm_cand = _normalize_col_name(cand)
        if norm_cand in norm_to_real:
            return norm_to_real[norm_cand]

    return None

def _find_city_column(df: pd.DataFrame) -> str | None:
    """
    Devuelve el nombre REAL de la columna que contenga la ciudad
    (ciudad SICUE, ciudad destino, etc.), o None si no encuentra nada.
    """
    if df.empty:
        return None

    candidates = [
        "ciudad",
        "ciudad_sicue",
        "ciudad destino",
        "ciudad origen",
        "city",
        "localidad",
        "poblacion",
    ]

    norm_to_real = {_normalize_col_name(c): c for c in df.columns}

    for cand in candidates:
        norm_cand = _normalize_col_name(cand)
        if norm_cand in norm_to_real:
            return norm_to_real[norm_cand]

    return None


def _load_students_for_course(config: dict, course: str) -> pd.DataFrame:
    """
    Carga los datos de alumnos para un curso (hoja) concreto, combinando:
    - Erasmus OUT
    - Erasmus IN
    - SICUE OUT

    Devuelve un DataFrame con columnas normalizadas:
    - curso_academico
    - tipo_movilidad
    - pais
    (más todas las columnas originales de cada Excel)
    """
    dfs: list[pd.DataFrame] = []

    for tipo in MOBILITY_TYPES:
        path = (config or {}).get(tipo)
        if not path:
            continue

        df_tipo = _read_sheet_safe(path, course)
        if df_tipo.empty:
            continue

        df_tipo = df_tipo.copy()

        # Columna de tipo de movilidad
        if "tipo_movilidad" in df_tipo.columns:
            pass
        elif "tipo" in df_tipo.columns:
            df_tipo = df_tipo.rename(columns={"tipo": "tipo_movilidad"})
        else:
            df_tipo["tipo_movilidad"] = tipo

        # -------------------------------
        # Normalizar país según tipo
        # -------------------------------
        # Posibles nombres de columna que pueden contener el país
        common_candidates = [
            "pais",
            "país",
            "country",
            "pais destino",
            "país destino",
        ]

        if tipo == "Erasmus OUT":
            candidates = common_candidates + [
                "pais_out",
                "país_out",
                "country_out",
                "pais destino out",
            ]
        elif tipo == "Erasmus IN":
            candidates = common_candidates + [
                "origen",
                "pais_in",
                "país_in",
                "country_in",
                "pais origen",
                "país origen",
            ]
        else:  # SICUE OUT
            candidates = common_candidates

        col_pais_real = _find_country_column(df_tipo, candidates)

        if col_pais_real:
            # Copiamos el contenido a una columna estándar "pais"
            df_tipo["pais"] = df_tipo[col_pais_real]
        else:
            # Fallback: SICUE OUT = España, otros vacío
            if tipo == "SICUE OUT":
                df_tipo["pais"] = "España"
            else:
                df_tipo["pais"] = ""

        # Filtrar filas con país vacío
        df_tipo["pais"] = df_tipo["pais"].fillna("").astype(str).str.strip()
        df_tipo = df_tipo[df_tipo["pais"] != ""]

        # Deduplicar por alumno (por si el Excel tiene una fila por asignatura)
        student_candidates = ["estudiante", "email", "nombre", "dni", "nip"]
        norm_cols = {_normalize_col_name(c): c for c in df_tipo.columns}
        col_student = next(
            (norm_cols[_normalize_col_name(c)] for c in student_candidates if _normalize_col_name(c) in norm_cols),
            None,
        )
        if col_student:
            df_tipo = df_tipo.drop_duplicates(subset=[col_student, "tipo_movilidad"])

        # Añadimos curso académico
        df_tipo["curso_academico"] = course

        dfs.append(df_tipo)

    if not dfs:
        return pd.DataFrame()

    return pd.concat(dfs, ignore_index=True)

def _load_erasmus_in_raw(config: dict, course: str) -> pd.DataFrame:
    """
    Carga el Excel de Erasmus IN SIN deduplicar (una fila por asignatura por alumno).
    Se usa exclusivamente para las estadísticas de asignaturas.
    """
    path = (config or {}).get("Erasmus IN")
    if not path:
        return pd.DataFrame()
    return _read_sheet_safe(path, course)


# ────────────────────────────────────────────────────────────────────────────────
# Helpers de estadísticas
# ────────────────────────────────────────────────────────────────────────────────

def _stats_by_mobility(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla: total de alumnos por tipo de movilidad.
    """
    if df.empty:
        return pd.DataFrame(columns=["Tipo de movilidad", "Nº de alumnos"])

    col = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"
    tabla = (
        df.groupby(col)
        .size()
        .reset_index(name="Nº de alumnos")
        .rename(columns={col: "Tipo de movilidad"})
        .sort_values("Nº de alumnos", ascending=False)
    )
    return tabla

def _stats_by_country(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla: total de alumnos por país.
    - Reemplaza valores vacíos / NaN por 'Desconocido' para evitar filas en blanco.
    """
    if df.empty or "pais" not in df.columns:
        return pd.DataFrame(columns=["País", "Nº de alumnos"])

    df = df.copy()
    df["pais"] = (
        df["pais"]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    # Donde no haya país, lo mostramos como 'Desconocido'
    df.loc[df["pais"] == "", "pais"] = "Desconocido"

    tabla = (
        df.groupby("pais")
        .size()
        .reset_index(name="Nº de alumnos")
        .rename(columns={"pais": "País"})
        .sort_values("Nº de alumnos", ascending=False)
    )
    return tabla

def _stats_by_city(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tabla: total de alumnos por ciudad (pensado para SICUE OUT).
    """
    if df.empty:
        return pd.DataFrame(columns=["Ciudad", "Nº de alumnos"])

    df = df.copy()
    col_city = _find_city_column(df)
    if not col_city:
        return pd.DataFrame(columns=["Ciudad", "Nº de alumnos"])

    serie_city = (
        df[col_city]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    serie_city = serie_city.replace({"": "Desconocido"})

    tabla = (
        serie_city.groupby(serie_city)
        .size()
        .reset_index(name="Nº de alumnos")
    )
    tabla.columns = ["Ciudad", "Nº de alumnos"]
    tabla = tabla.sort_values("Nº de alumnos", ascending=False)

    return tabla


# ────────────────────────────────────────────────────────────────────────────────
# Vista principal: Ver estadísticas
# ────────────────────────────────────────────────────────────────────────────────
def render_stats_view() -> None:
    st.header("📊 Ver estadísticas")

    config = st.session_state.get("config", {}) or {}

    course = _get_selected_course()
    if not course:
        st.info("Selecciona un curso académico en la barra lateral para ver las estadísticas.")
        return

    mobility_filter = st.session_state.get("stats_mobility", "Todos")

    df = _load_students_for_course(config, course)
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

    # ===========================
    # PREPARAR DATAFRAMES
    # ===========================
    # Tabla 1: por tipo de movilidad (sin filtrar)
    tabla_tipo = _stats_by_mobility(df)

    # Tabla 2: por país, con filtro seleccionado
    if mobility_filter and mobility_filter != "Todos":
        col_tipo = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"
        df_filtered = df[df[col_tipo] == mobility_filter].copy()
    else:
        df_filtered = df.copy()

    if df_filtered.empty:
        st.info(
            f"No hay datos para el curso **{course}** con el tipo de movilidad "
            f"**{mobility_filter}**."
        )
        return

    tabla_paises = _stats_by_country(df_filtered)

    # ===========================
    # FILA 1: DOS TABLAS LADO A LADO
    # ===========================
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.subheader("Alumnos por tipo de movilidad")
        if tabla_tipo.empty:
            st.info("No se han encontrado alumnos con información de tipo de movilidad.")
        else:
            st.dataframe(
                tabla_tipo,
                use_container_width=True,
                hide_index=True,
            )

    with col2:
        # ===========================
        # GEO: por país o por ciudad según filtro
        # ===========================
        if mobility_filter and mobility_filter != "Todos":
            col_tipo = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"
            df_filtered = df[df[col_tipo] == mobility_filter].copy()
        else:
            df_filtered = df.copy()

        if df_filtered.empty:
            st.info(
                f"No hay datos para el curso **{course}** con el tipo de movilidad "
                f"**{mobility_filter}**."
            )
            return

        # Si es SICUE OUT → agrupar por ciudad
        if mobility_filter == PROGRAM_SICUE_OUT:
            st.subheader("Alumnos por ciudad (SICUE OUT)")
            tabla_geo = _stats_by_city(df_filtered)
            if tabla_geo.empty:
                st.info(
                    "No se ha podido generar la tabla por ciudad; comprueba que exista alguna "
                    "columna de ciudad en el Excel (por ejemplo 'ciudad_sicue' o 'ciudad')."
                )
                return
        else:
            st.subheader("Alumnos por país")
            tabla_geo = _stats_by_country(df_filtered)
            if tabla_geo.empty:
                st.info(
                    "No se ha podido generar la tabla por país; comprueba que exista una columna "
                    "de país ('pais', 'país', 'pais_out', 'pais_in', etc.) en tus Excels."
                )
                return

        st.dataframe(
            tabla_geo,
            use_container_width=True,
            hide_index=True,
        )
    # ===========================
    # BOTÓN DE EXPORTAR EXCEL
    # ===========================
    if st.session_state.get("export_generate"):
        tables: list[tuple[str, object]] = []
        warnings: list[str] = []

        col_tipo = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"

        # Movilidad (si la quieres aparte)
        if st.session_state.get("exp_mobility", False):
            tables.append(("Movilidad", _stats_by_mobility(df)))

        # HOJA ÚNICA: País y ciudades
        if st.session_state.get("exp_country_all", False) or st.session_state.get("exp_country_by_type", False):
            blocks_pais = [
                ("País - Total (todos los tipos)", _stats_by_country(df)),
                ("País - Erasmus IN", _stats_by_country(df[df[col_tipo] == "Erasmus IN"].copy())),
                ("País - Erasmus OUT", _stats_by_country(df[df[col_tipo] == "Erasmus OUT"].copy())),
                ("Ciudades (España) - SICUE OUT", _stats_by_city(df[df[col_tipo] == "SICUE OUT"].copy())),
            ]
            tables.append(("País y ciudades", blocks_pais))

        # Asignaturas Erasmus IN (datos sin deduplicar para contar asignaturas)
        if st.session_state.get("exp_subject_in", False):
            df_erasmus_raw = _load_erasmus_in_raw(config, course)
            tabla_mat = details._stats_materias_mas_frecuentes(df_erasmus_raw, top_n=1000000)
            tables.append(("Asignaturas - IN", tabla_mat))

        # HOJA ÚNICA: Universidades
        if st.session_state.get("exp_university", False):
            blocks_uni = [
                ("Universidades - Total (todos los tipos)", details._stats_by_university(df, top_n=1000000)),
                ("Universidades - Erasmus IN", details._stats_by_university(df[df[col_tipo] == "Erasmus IN"].copy(), top_n=1000000)),
                ("Universidades - Erasmus OUT", details._stats_by_university(df[df[col_tipo] == "Erasmus OUT"].copy(), top_n=1000000)),
                ("Universidades - SICUE OUT", details._stats_by_university(df[df[col_tipo] == "SICUE OUT"].copy(), top_n=1000000)),
            ]
            tables.append(("Universidades", blocks_uni))

        course = _get_selected_course() or "curso"
        filename = f"estadisticas_{course}.xlsx".replace("/", "-")

        xlsx_bytes = build_stats_excel(
            tables=tables,
            meta={"Curso": str(course)},
            warnings=warnings,
        )

        st.session_state["export_xlsx_bytes"] = xlsx_bytes
        st.session_state["export_xlsx_name"] = filename
        st.session_state["export_generate"] = False


    # ===========================
    # DETALLES
    # ===========================
    df_erasmus_raw = _load_erasmus_in_raw(config, course)
    details.render_stats_details(df_filtered, mobility_filter, df_erasmus_raw)
    # ===========================
    # RESUMEN
    # ===========================
    total_alumnos = len(df_filtered)
    st.markdown("---")
    st.markdown(
        f"📌 **Resumen**: {total_alumnos} alumnos en el curso `{course}` "
        f"para el filtro de tipo de movilidad `{mobility_filter}`."
    )

