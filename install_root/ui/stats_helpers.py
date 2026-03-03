from __future__ import annotations

import os
from typing import Any
import pandas as pd
import streamlit as st

from export import build_stats_excel
from . import stats_details as details
from constants import MOBILITY_PROGRAMS, PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT, SPAIN

MOBILITY_TYPES: tuple[str, ...] = MOBILITY_PROGRAMS


def _read_sheet_safe(path: str, sheet_name: str) -> pd.DataFrame:
    if not path or not os.path.exists(path):
        return pd.DataFrame()
    try:
        df = pd.read_excel(path, sheet_name=sheet_name)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _normalize_col_name(name: str) -> str:
    if not isinstance(name, str):
        name = str(name)
    s = name.strip().lower().replace(" ", "")
    for k, v in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ñ":"n"}.items():
        s = s.replace(k, v)
    return s


def _find_country_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    if df.empty:
        return None
    norm_to_real = {_normalize_col_name(c): c for c in df.columns}
    for cand in candidates:
        nc = _normalize_col_name(cand)
        if nc in norm_to_real:
            return norm_to_real[nc]
    return None


def _find_city_column(df: pd.DataFrame) -> str | None:
    if df.empty:
        return None
    candidates = ["ciudad", "ciudad_sicue", "ciudad destino", "city", "localidad", "poblacion"]
    norm_to_real = {_normalize_col_name(c): c for c in df.columns}
    for cand in candidates:
        nc = _normalize_col_name(cand)
        if nc in norm_to_real:
            return norm_to_real[nc]
    return None


def load_students_for_course(config: dict, course: str) -> pd.DataFrame:
    dfs: list[pd.DataFrame] = []
    for tipo in MOBILITY_TYPES:
        path = (config or {}).get(tipo)
        if not path:
            continue

        df_tipo = _read_sheet_safe(path, course)
        if df_tipo.empty:
            continue

        df_tipo = df_tipo.copy()

        if "tipo_movilidad" not in df_tipo.columns:
            if "tipo" in df_tipo.columns:
                df_tipo = df_tipo.rename(columns={"tipo": "tipo_movilidad"})
            else:
                df_tipo["tipo_movilidad"] = tipo

        # Normalizar columna país
        common_candidates = ["pais", "país", "country", "pais destino", "país destino"]

        if tipo == PROGRAM_ERASMUS_OUT:
            candidates = common_candidates + ["pais_out", "país_out", "country_out"]
        elif tipo == PROGRAM_ERASMUS_IN:
            candidates = common_candidates + ["origen", "pais_in", "país_in", "country_in", "pais origen", "país origen"]
        else:
            candidates = common_candidates

        col_pais = _find_country_column(df_tipo, candidates)
        if col_pais:
            df_tipo["pais"] = df_tipo[col_pais]
        else:
            df_tipo["pais"] = SPAIN if tipo == PROGRAM_SICUE_OUT else ""

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

        # Normalizar columna universidad
        col_uni = details._find_university_column(df_tipo)
        if col_uni:
            df_tipo["universidad"] = df_tipo[col_uni]
        else:
            df_tipo["universidad"] = ""

        df_tipo["curso_academico"] = course
        dfs.append(df_tipo)

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def stats_by_mobility(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Tipo de movilidad", "Nº de alumnos"])
    col = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"
    return (
        df.groupby(col).size().reset_index(name="Nº de alumnos")
          .rename(columns={col: "Tipo de movilidad"})
          .sort_values("Nº de alumnos", ascending=False)
    )


def stats_by_country(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "pais" not in df.columns:
        return pd.DataFrame(columns=["País", "Nº de alumnos"])
    d = df.copy()
    d["pais"] = d["pais"].fillna("").astype(str).str.strip()
    d.loc[d["pais"] == "", "pais"] = "Desconocido"
    return (
        d.groupby("pais").size().reset_index(name="Nº de alumnos")
         .rename(columns={"pais": "País"})
         .sort_values("Nº de alumnos", ascending=False)
    )


def stats_by_city(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["Ciudad", "Nº de alumnos"])
    col = _find_city_column(df)
    if not col:
        return pd.DataFrame(columns=["Ciudad", "Nº de alumnos"])
    s = df[col].fillna("").astype(str).str.strip().replace({"": "Desconocido"})
    tab = s.groupby(s).size().reset_index(name="Nº de alumnos")
    tab.columns = ["Ciudad", "Nº de alumnos"]
    return tab.sort_values("Nº de alumnos", ascending=False)


def _config_fingerprint(config: dict) -> tuple[tuple[str, str], ...]:
    # Hash estable para cache
    items = []
    for k, v in (config or {}).items():
        items.append((str(k), str(v)))
    return tuple(sorted(items))


@st.cache_data(show_spinner=False)
def build_export_xlsx(
    course: str,
    selections: dict[str, Any],
    config_fp: tuple[tuple[str, str], ...],
) -> tuple[bytes, str]:
    # reconstruimos config desde fingerprint si quieres, pero aquí solo lo usamos para invalidar cache
    config = dict(config_fp)

    df = load_students_for_course(config, course)

    tables: list[tuple[str, pd.DataFrame]] = []
    warnings: list[str] = []

    # 1) movilidad total
    if selections.get("exp_mobility"):
        tables.append(("Movilidad - total", stats_by_mobility(df)))

    # 2) país total
    if selections.get("exp_country_all"):
        tables.append(("País - total", stats_by_country(df)))

    # 3) país/ciudad por tipo
    if selections.get("exp_country_by_type"):
        tipos = list(selections.get("exp_country_by_type_types") or [])
        col_tipo = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"
        
        # Agrupar todos los tipos en una sola hoja con bloques
        blocks = []
        for t in tipos:
            dft = df[df[col_tipo] == t].copy()
            if t == PROGRAM_SICUE_OUT:
                blocks.append((f"Ciudad - {t}", stats_by_city(dft)))
            else:
                blocks.append((f"País - {t}", stats_by_country(dft)))
        
        if blocks:
            tables.append(("País por tipo", blocks))

    # 4) asignaturas Erasmus IN (datos crudos sin deduplicar para contar asignaturas)
    if selections.get("exp_subject_in"):
        path_in = config.get("Erasmus IN", "")
        df_erasmus_raw = _read_sheet_safe(path_in, course)
        tabla_mat = details._stats_materias_mas_frecuentes(df_erasmus_raw, top_n=1000000)
        tables.append(("Asignaturas - Erasmus IN", tabla_mat))

    # 5) universidades (MISMA detección que la app)
    if selections.get("exp_university"):
        selected = list(selections.get("exp_university_types") or [])
        col_tipo = "tipo_movilidad" if "tipo_movilidad" in df.columns else "tipo"

        # Agrupar todos los tipos de universidad en una sola hoja con bloques
        blocks = []
        
        # Si selecciona "Todos", incluye total + todas las específicas
        if "Todos" in selected:
            tab = details._stats_by_university(df, top_n=1000000)
            blocks.append(("Universidad - total", tab))
            
            # Agregar también por tipo
            for t in MOBILITY_PROGRAMS:
                df_filtrado = df[df[col_tipo] == t].copy()
                tab = details._stats_by_university(df_filtrado, top_n=1000000)
                blocks.append((f"Universidad - {t}", tab))
        else:
            # Si selecciona tipos específicos, solo esos
            for t in MOBILITY_PROGRAMS:
                if t in selected:
                    df_filtrado = df[df[col_tipo] == t].copy()
                    tab = details._stats_by_university(df_filtrado, top_n=1000000)
                    blocks.append((f"Universidad - {t}", tab))
        
        if blocks:
            tables.append(("Universidad por tipo", blocks))

    if not tables:
        warnings.append("No has seleccionado ninguna tabla para exportar.")

    xlsx = build_stats_excel(
        tables=tables,
        meta={"Curso": course},
        warnings=warnings,
    )
    filename = f"estadisticas_{course}.xlsx".replace("/", "-")
    return xlsx, filename


def selections_from_state() -> dict[str, Any]:
    return {
        "exp_mobility": st.session_state.get("exp_mobility", False),
        "exp_country_all": st.session_state.get("exp_country_all", False),
        "exp_country_by_type": st.session_state.get("exp_country_by_type", False),
        "exp_country_by_type_types": tuple(st.session_state.get("exp_country_by_type_types", [])),
        "exp_subject_in": st.session_state.get("exp_subject_in", False),
        "exp_university": st.session_state.get("exp_university", False),
        "exp_university_types": tuple(st.session_state.get("exp_university_types", [])),
    }


def config_fp_from_state() -> tuple[tuple[str, str], ...]:
    return _config_fingerprint(st.session_state.get("config", {}) or {})
