from __future__ import annotations

import pandas as pd
import streamlit as st
from constants import PROGRAM_ERASMUS_IN
from .stats_table import render_stats_table


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
    if df.empty:
        return None

    candidates = [
        "destino_origen", "destino / origen", "destino/origen",
        "origen (universidad)", "destino (universidad)",
        "universidad", "universidad destino", "universidad origen",
        "universidad de destino", "universidad de origen",
        "uni destino", "uni origen",
        "centro", "centro destino", "centro origen",
        "centro de destino", "centro de origen",
        "destino", "Destino",
        # extras típicos en excels
        "institucion", "institución", "institution", "host institution",
        "partner", "partner institution",
    ]

    norm_to_real = {_normalize_col_name(c): c for c in df.columns}

    # 1) columnas que matchean por nombre candidato (máxima prioridad)
    name_hits: list[str] = []
    for cand in candidates:
        nc = _normalize_col_name(cand)
        if nc in norm_to_real:
            name_hits.append(norm_to_real[nc])

    if not name_hits:
        # 2) Si no hay coincidencias exactas, buscar por keywords con priorización
        # Palabras que EXCLUYEN una columna (no es universidad/centro)
        exclude_keywords = ["coordinador", "correo", "email", "mail", "telefono", "teléfono", "persona", "nombre"]
        
        # Palabras clave en orden de importancia
        priority_keywords = [
            ("universidad", 3),
            ("centro", 3),
            ("institucion", 3),
            ("institution", 3),
            ("uni", 2),
            ("partner", 2),
            ("destino", 1),
            ("origen", 1),
        ]
        
        col_scores: dict[str, int] = {}
        for col in df.columns:
            ncol = _normalize_col_name(col)
            
            # Rechazar si contiene palabras de exclusión
            if any(excl in ncol for excl in exclude_keywords):
                continue
            
            score = 0
            for keyword, weight in priority_keywords:
                if keyword in ncol:
                    score = max(score, weight)
            if score > 0:
                col_scores[col] = score
        
        # Ordenar por puntuación y luego por número de valores no vacíos
        if col_scores:
            scored_cols = []
            for col, score in col_scores.items():
                s = df[col].fillna("").astype(str).str.strip()
                n_values = int((s != "").sum())
                scored_cols.append((col, score, n_values))
            
            # Ordenar por: puntuación DESC, luego por número de valores DESC
            scored_cols.sort(key=lambda x: (-x[1], -x[2]))
            keyword_hits = [col for col, _, _ in scored_cols]

        name_hits = keyword_hits

    if not name_hits:
        return None

    # Elegimos la que tenga más valores "reales" (no vacíos) en ESTE df
    best_col = None
    best_score = 0
    for col in name_hits:
        s = df[col].fillna("").astype(str).str.strip()
        score = int((s != "").sum())
        if score > best_score:
            best_score = score
            best_col = col

    return best_col if best_score > 0 else None


def _stats_by_university(df: pd.DataFrame, top_n: int | None = 15) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Universidad", "Nº de alumnos"])

    # Priorizar columna normalizada si existe
    if "universidad" in df.columns:
        col_uni = "universidad"
    else:
        col_uni = _find_university_column(df)
        if not col_uni:
            return pd.DataFrame(columns=["Universidad", "Nº de alumnos"])

    s = df[col_uni].fillna("").astype(str).str.strip()
    s = s[s != ""]  # <- si está todo vacío, devolvemos vacío (no "Desconocido")

    if s.empty:
        return pd.DataFrame(columns=["Universidad", "Nº de alumnos"])

    tabla = s.groupby(s).size().reset_index(name="Nº de alumnos")
    tabla.columns = ["Universidad", "Nº de alumnos"]
    tabla = tabla.sort_values("Nº de alumnos", ascending=False)

    if top_n is not None:
        tabla = tabla.head(top_n)

    return tabla


def _stats_materias_mas_frecuentes(df_mat: pd.DataFrame, top_n: int | None= 20) -> pd.DataFrame:
    """
    Tabla: asignaturas Erasmus IN más frecuentes (usa el Excel 'Materias IN').
    """
    if df_mat.empty:
        return pd.DataFrame(columns=["Asignatura", "Nº de alumnos"])

    col_asig = None
    candidates_asig = [
        "Asignatura", "asignatura", "nombre_asignatura",
        "subject", "Subject", "materia", "Materia",
        "asignatura destino", "subject name", "course", "Course",
    ]
    norm_to_real = {_normalize_col_name(c): c for c in df_mat.columns}
    for cand in candidates_asig:
        nc = _normalize_col_name(cand)
        if nc in norm_to_real:
            col_asig = norm_to_real[nc]
            break

    if not col_asig:
        return pd.DataFrame(columns=["Asignatura", "Nº de alumnos"])

    serie_asig = (
        df_mat[col_asig]
        .fillna("")
        .astype(str)
        .str.strip()
    )
    serie_asig = serie_asig[serie_asig != ""]  # Eliminar vacíos

    if serie_asig.empty:
        return pd.DataFrame(columns=["Asignatura", "Nº de alumnos"])

    tabla = (
        serie_asig.groupby(serie_asig)
        .size()
        .reset_index(name="Nº de alumnos")
    )
    tabla.columns = ["Asignatura", "Nº de alumnos"]
    # tabla = tabla.sort_values("Nº de alumnos", ascending=False).head(top_n)

    tabla = tabla.sort_values("Nº de alumnos", ascending=False)
    if top_n is not None:
        tabla = tabla.head(top_n)
    return tabla


# ────────────────────────────────────────────────────────────────────────────────
# Función pública: renderizar detalles
# ────────────────────────────────────────────────────────────────────────────────

def render_stats_details(df_filtered: pd.DataFrame, mobility_filter: str, df_erasmus_raw: pd.DataFrame) -> None:
    """
    Renderiza el bloque de detalles (expanders) de la vista de estadísticas:

    - Universidades con más alumnos (para cualquier filtro).
    - Asignaturas más frecuentes (Erasmus IN) usando los datos crudos del Excel Erasmus IN
      (una fila por asignatura, sin deduplicar).

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
            render_stats_table(tabla_uni)

    # 2) Materias más frecuentes (solo tiene sentido para Erasmus IN / Todos)
    if mobility_filter in (PROGRAM_ERASMUS_IN, "Todos"):
        with st.expander("Asignaturas más frecuentes (Erasmus IN)"):
            # Usar datos crudos (sin deduplicar) para contar asignaturas correctamente
            tabla_mat = _stats_materias_mas_frecuentes(df_erasmus_raw)
            if tabla_mat.empty:
                st.info(
                    "No se ha podido generar la tabla de asignaturas. "
                    "Comprueba que el Excel de Erasmus IN tenga una columna de asignatura "
                    "('Asignatura', 'asignatura', 'nombre_asignatura', etc.)."
                )
            else:
                render_stats_table(tabla_mat)
