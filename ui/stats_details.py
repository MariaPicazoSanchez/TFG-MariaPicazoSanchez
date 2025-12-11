from __future__ import annotations

import os
import pandas as pd
import streamlit as st


# ────────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ────────────────────────────────────────────────────────────────────────────────

def _normalize_col_name(name: str) -> str:
    """
    Normaliza un nombre de columna para comparaciones flexibles:
    - minúsculas
    - sin espacios
    - sin acentos simples
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

def _find_university_column(df: pd.DataFrame) -> str | None:
    """
    Intenta localizar la columna que guarda la universidad / centro
    (destino u origen según el tipo).
    Intenta ser muy flexible con nombres y acentos.
    """
    if df.empty:
        return None

    # Nombres típicos que pueden aparecer en tus Excels
    candidates = [
        "destino_origen",
        "destino / origen",
        "destino/origen",
        "origen (universidad)",
        "destino (universidad)",
        "universidad",
        "universidad destino",
        "universidad origen",
        "universidad de destino",
        "universidad de origen",
        "uni destino",
        "uni origen",
        "centro",
        "centro destino",
        "centro origen",
        "centro de destino",
        "centro de origen",
    ]

    norm_to_real = {_normalize_col_name(c): c for c in df.columns}

    # 1) Coincidencia exacta normalizada con la lista de candidatos
    for cand in candidates:
        norm_cand = _normalize_col_name(cand)
        if norm_cand in norm_to_real:
            return norm_to_real[norm_cand]

    # 2) Heurística: cualquier columna que contenga 'universidad', 'destino' u 'origen'
    for col in df.columns:
        norm_col = _normalize_col_name(col)
        if any(k in norm_col for k in ("universidad", "destino", "origen", "centro")):
            return col

    return None



def _stats_by_university(df: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """
    Tabla: universidades con más alumnos (top N).
    """
    if df.empty:
        return pd.DataFrame(columns=["Universidad", "Nº de alumnos"])

    col_uni = _find_university_column(df)
    if not col_uni:
        return pd.DataFrame(columns=["Universidad", "Nº de alumnos"])

    serie_uni = (
        df[col_uni]
        .fillna("")
        .astype(str)
        .str.strip()
    ).replace({"": "Desconocido"})

    tabla = (
        serie_uni.groupby(serie_uni)
        .size()
        .reset_index(name="Nº de alumnos")
    )
    tabla.columns = ["Universidad", "Nº de alumnos"]
    tabla = tabla.sort_values("Nº de alumnos", ascending=False).head(top_n)

    return tabla


def _load_materias_in(config: dict) -> pd.DataFrame:
    """
    Carga el Excel de 'Materias IN' si existe (config['Materias IN']).
    Devuelve DataFrame vacío si no hay ruta o hay error.
    """
    path = (config or {}).get("Materias IN")
    if not path or not os.path.exists(path):
        return pd.DataFrame()

    try:
        df = pd.read_excel(path)
        if df is None:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def _stats_materias_mas_frecuentes(df_mat: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Tabla: asignaturas Erasmus IN más frecuentes (usa el Excel 'Materias IN').
    """
    if df_mat.empty:
        return pd.DataFrame(columns=["Asignatura", "Nº de alumnos"])

    col_asig = None
    for cand in ["Asignatura", "asignatura", "nombre_asignatura"]:
        if cand in df_mat.columns:
            col_asig = cand
            break

    if not col_asig:
        return pd.DataFrame(columns=["Asignatura", "Nº de alumnos"])

    serie_asig = (
        df_mat[col_asig]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    tabla = (
        serie_asig.groupby(serie_asig)
        .size()
        .reset_index(name="Nº de alumnos")
    )
    tabla.columns = ["Asignatura", "Nº de alumnos"]
    tabla = tabla.sort_values("Nº de alumnos", ascending=False).head(top_n)

    return tabla


# ────────────────────────────────────────────────────────────────────────────────
# Función pública: renderizar detalles
# ────────────────────────────────────────────────────────────────────────────────

def render_stats_details(df_filtered: pd.DataFrame, mobility_filter: str, config: dict) -> None:
    """
    Renderiza el bloque de detalles (expanders) de la vista de estadísticas:

    - Universidades con más alumnos (para cualquier filtro).
    - Asignaturas más frecuentes (Erasmus IN) usando el Excel 'Materias IN'.

    Si algún día no quieres este bloque, basta con NO llamar a esta función
    desde stats_view.py o borrar este archivo.
    """
    # 1) Universidades con más alumnos
    with st.expander("Universidades con más alumnos"):
        tabla_uni = _stats_by_university(df_filtered)
        if tabla_uni.empty:
            st.info(
                "No se ha podido generar la tabla de universidades. "
                "Comprueba que tus Excels tengan alguna columna de universidad "
                "('destino_origen', 'universidad', 'centro', etc.)."
            )
        else:
            st.dataframe(
                tabla_uni,
                use_container_width=True,
                hide_index=True,
            )

    # 2) Materias más frecuentes (solo tiene sentido para Erasmus IN / Todos)
    if mobility_filter in ("Erasmus IN", "Todos"):
        with st.expander("Asignaturas más frecuentes (Erasmus IN)"):
            df_mat = _load_materias_in(config)
            tabla_mat = _stats_materias_mas_frecuentes(df_mat)
            if tabla_mat.empty:
                st.info(
                    "No se ha podido generar la tabla de asignaturas. "
                    "Comprueba que exista el Excel 'Materias IN' en la configuración "
                    "y que tenga la columna 'Asignatura'."
                )
            else:
                st.dataframe(
                    tabla_mat,
                    use_container_width=True,
                    hide_index=True,
                )
