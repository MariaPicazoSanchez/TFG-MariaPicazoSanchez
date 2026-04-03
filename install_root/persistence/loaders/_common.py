"""
Helpers compartidos por todos los loaders de movilidad:
  - utilidades de texto y columnas (_norm_name, _norm_colname, _pick)
  - parseo de coordenadas (_parse_coords)
  - lectura de tabla (_read_table)
  - consulta de universidades (get_universities_from_coords_sheet,
    get_universities_from_sicue_data)
  - filtrado por coordenadas (filter_students_with_coords)
  - clustering de coordenadas (haversine_distance, cluster_coordinates)
"""


import gc
import math
import os
import re
import unicodedata
from typing import Iterable, Optional, Tuple

import pandas as pd
import streamlit as st

from constants import EXCEL_EXTENSIONS

import logging
logger = logging.getLogger("movilidad_persistence")


# ──────────────────────────────────────────────────────────────────────────────
# Normalización de texto
# ──────────────────────────────────────────────────────────────────────────────

def _norm_name(s: str) -> str:
    """Normaliza un nombre: minúsculas, sin acentos, sin espacios extra."""
    if not s or str(s).strip().lower() in ("", "nan", "none"):
        return ""
    s = str(s).strip().lower()
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'\s+', ' ', s).strip()


def _norm_colname(s: str) -> str:
    """Normaliza un nombre de columna para comparaciones relajadas."""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _pick(df: pd.DataFrame, *aliases: Iterable[str]) -> Optional[str]:
    """
    Devuelve el nombre REAL de la primera columna existente entre los alias dados.
    Hace match relajado y también 'contains' por si hay typos.
    """
    norm_map = {_norm_colname(c): c for c in df.columns}
    # exactos
    for a in aliases:
        if a is None:
            continue
        na = _norm_colname(a)
        if na in norm_map:
            return norm_map[na]
    # contains único — excluir columnas puramente numéricas
    non_numeric = {
        norm: real for norm, real in norm_map.items()
        if norm and not norm.replace(".", "").isdigit()
    }
    for a in aliases:
        if a is None:
            continue
        na = _norm_colname(a)
        cand = [real for norm, real in non_numeric.items() if na in norm or norm in na]
        if len(cand) == 1:
            return cand[0]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Parseo de coordenadas
# ──────────────────────────────────────────────────────────────────────────────

def _parse_coords(s: str) -> Tuple[Optional[float], Optional[float]]:
    """Extrae lat/lon tolerando coma o punto y separadores variados."""
    if s is None:
        return None, None
    nums = re.findall(r"-?\d+(?:[.,]\d+)?", str(s))
    if len(nums) >= 2:
        lat = float(nums[0].replace(",", "."))
        lon = float(nums[1].replace(",", "."))
        return lat, lon
    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# Lectura de tabla
# ──────────────────────────────────────────────────────────────────────────────

def _read_table(path: str, sheet_name: str | None = None, nrows: int | None = None) -> pd.DataFrame:
    """
    Lee CSV/XLS/XLSX con motor adecuado.
    Si sheet_name es None en Excel, usa la primera hoja (índice 0).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path, nrows=nrows, encoding="utf-8", sep=None, engine="python")

    if ext in EXCEL_EXTENSIONS:
        effective_sheet = 0 if sheet_name is None else sheet_name
        try:
            engine = "openpyxl" if ext in EXCEL_EXTENSIONS[:-1] else None
            return pd.read_excel(path, sheet_name=effective_sheet, engine=engine, nrows=nrows)
        except TypeError:
            return pd.read_excel(path, sheet_name=effective_sheet, nrows=nrows)

    effective_sheet = 0 if sheet_name is None else sheet_name
    return pd.read_excel(path, sheet_name=effective_sheet, nrows=nrows)


# ──────────────────────────────────────────────────────────────────────────────
# Índice de nombres para matching flexible (Erasmus IN)
# ──────────────────────────────────────────────────────────────────────────────

def _build_materias_index(materias_dict: dict) -> tuple[dict, dict]:
    """
    Construye índices de búsqueda para hacer matching flexible de nombres:
    1. Nombre completo normalizado -> clave original
    2. Última palabra -> lista de claves originales
    """
    exact: dict = {}
    by_last: dict = {}

    for nombre in materias_dict:
        norm = _norm_name(nombre)
        exact[norm] = nombre
        words = norm.split()
        if words:
            last = words[-1]
            by_last.setdefault(last, []).append(nombre)

    return exact, by_last


def _match_student_name(nombre_completo: str, exact: dict, by_last: dict) -> str | None:
    """
    Intenta encontrar la clave correcta en materias_dict para un nombre de alumno.
    Orden: exacto → apellido → primera palabra del apellido.
    """
    if not nombre_completo:
        return None
    norm = _norm_name(nombre_completo)
    if norm in exact:
        return exact[norm]
    words = norm.split()
    for last in reversed(words):
        if last in by_last:
            candidates = by_last[last]
            if len(candidates) == 1:
                return candidates[0]
            best = max(
                candidates,
                key=lambda c: len(set(_norm_name(c).split()) & set(words))
            )
            return best
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Consulta de universidades
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def get_universities_from_coords_sheet(path: str) -> list[str]:
    """
    Devuelve la lista de universidades desde la hoja 'Coordenadas' de un Excel.
    Formato: col0=País, col1=Universidad, col2=Coordenadas.
    """
    try:
        df_coords = pd.read_excel(
            path, sheet_name="Coordenadas", header=None, dtype=str
        )
        universidades = (
            df_coords.iloc[:, 1]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )
        return sorted(universidades)
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def get_universities_from_sicue_data(path: str) -> tuple[list[str], dict, dict]:
    """
    Extrae universidades únicas del Excel de SICUE OUT leyendo todas las hojas
    de datos (las que parecen cursos académicos).

    Returns:
        universidades : list[str]          - lista ordenada de nombres únicos
        ciudad_map    : dict[str, str]     - {universidad: ciudad}
        coords_map    : dict[str, tuple]   - {universidad: (lat, lon)}
    """
    def _is_academic_sheet(name: str) -> bool:
        return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', str(name)))

    universidades: dict[str, dict] = {}

    try:
        wb_sheets = pd.ExcelFile(path, engine="openpyxl").sheet_names
    except Exception:
        return [], {}, {}

    hojas_datos = [s for s in wb_sheets if _is_academic_sheet(s)]
    if not hojas_datos:
        hojas_datos = [s for s in wb_sheets if s.lower() != "coordenadas"]

    for sheet in hojas_datos:
        try:
            df_sheet = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", dtype=str)
            df_sheet.columns = [str(c).strip() for c in df_sheet.columns]

            c_dest   = _pick(df_sheet, "Destino", "Universidad Destino", "Universidad")
            c_ciudad = _pick(df_sheet, "Ciudad")
            c_coords = _pick(df_sheet, "Coordenadas", "coords")
            c_lat    = _pick(df_sheet, "Latitud", "latitud", "lat")
            c_lon    = _pick(df_sheet, "Longitud", "longitud", "lon")

            if not c_dest:
                continue

            for _, row in df_sheet.iterrows():
                uni = str(row.get(c_dest) or "").strip()
                if not uni or uni.lower() in ("nan", "none", ""):
                    continue

                ciudad = str(row.get(c_ciudad) or "").strip() if c_ciudad else ""
                if ciudad.lower() in ("nan", "none"):
                    ciudad = ""

                lat, lon = None, None
                if c_coords:
                    lat, lon = _parse_coords(str(row.get(c_coords) or ""))
                elif c_lat and c_lon:
                    try:
                        lat = float(str(row.get(c_lat) or "").replace(",", "."))
                        lon = float(str(row.get(c_lon) or "").replace(",", "."))
                    except (ValueError, TypeError):
                        lat, lon = None, None

                existing = universidades.get(uni, {})
                if not existing.get("ciudad") and ciudad:
                    existing["ciudad"] = ciudad
                if existing.get("lat") is None and lat is not None:
                    existing["lat"] = lat
                    existing["lon"] = lon
                universidades[uni] = existing

        except Exception:
            continue

    sorted_unis = sorted(universidades.keys())
    ciudad_map = {u: d.get("ciudad", "") for u, d in universidades.items()}
    coords_map = {
        u: (d["lat"], d["lon"])
        for u, d in universidades.items()
        if d.get("lat") is not None and d.get("lon") is not None
    }
    return sorted_unis, ciudad_map, coords_map


# ──────────────────────────────────────────────────────────────────────────────
# Filtrado por coordenadas
# ──────────────────────────────────────────────────────────────────────────────

def filter_students_with_coords(
    df: pd.DataFrame,
    tipo: str,
    _messages: list | None = None,
) -> pd.DataFrame:
    """
    Filtra filas sin coordenadas válidas.
    Los avisos se acumulan en _messages para mostrarlos fuera de @st.cache_data.
    """
    mask_coords = df["latitud"].notna() & df["longitud"].notna()
    if not mask_coords.all() and _messages is not None:
        sin_coords = df.loc[~mask_coords, "estudiante"] if "estudiante" in df.columns else pd.Series(dtype=object)
        sin_coords_str = sin_coords.astype(str).str.strip().str.lower()
        validos = sin_coords[~(sin_coords.isna() | sin_coords_str.isin({"", "nan", "0"}))]
        _messages += [
            f"⚠️ El alumno **{n}** ({tipo}) no tiene coordenadas y no se mostrará en el mapa."
            for n in validos
        ]
    return df[mask_coords].copy()


# ──────────────────────────────────────────────────────────────────────────────
# Clustering de coordenadas
# ──────────────────────────────────────────────────────────────────────────────

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distancia en metros entre dos puntos (Haversine)."""
    if any(v is None or pd.isna(v) for v in [lat1, lon1, lat2, lon2]):
        return float('inf')
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def cluster_coordinates(df: pd.DataFrame, max_distance_m: int = 150) -> pd.DataFrame:
    """
    Agrupa coordenadas próximas (Union-Find) promediando su posición.
    Si dos puntos están a menos de max_distance_m se les asignan las mismas
    coordenadas, de modo que el groupby posterior los agrupe correctamente.
    """
    if df.empty or "latitud" not in df.columns or "longitud" not in df.columns:
        return df

    valid_mask = df["latitud"].notna() & df["longitud"].notna()
    if not valid_mask.any():
        return df

    df = df.reset_index(drop=True).copy()
    parent = list(range(len(df)))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(len(df)):
        if not valid_mask.iloc[i]:
            continue
        lat1, lon1 = df.iloc[i]["latitud"], df.iloc[i]["longitud"]
        for j in range(i + 1, len(df)):
            if not valid_mask.iloc[j]:
                continue
            lat2, lon2 = df.iloc[j]["latitud"], df.iloc[j]["longitud"]
            if haversine_distance(lat1, lon1, lat2, lon2) < max_distance_m:
                union(i, j)

    clusters_map: dict[int, list[int]] = {}
    for i in range(len(df)):
        if valid_mask.iloc[i]:
            root = find(i)
            clusters_map.setdefault(root, []).append(i)

    new_coords: dict[int, tuple[float, float]] = {}
    for indices in clusters_map.values():
        cluster_data = df.iloc[indices]
        avg_lat = cluster_data["latitud"].mean()
        avg_lon = cluster_data["longitud"].mean()
        for idx in indices:
            new_coords[idx] = (avg_lat, avg_lon)

    for idx, (new_lat, new_lon) in new_coords.items():
        df.iloc[idx, df.columns.get_loc("latitud")] = new_lat
        df.iloc[idx, df.columns.get_loc("longitud")] = new_lon

    return df


# ──────────────────────────────────────────────────────────────────────────────
# Helper compartido: restaurar info de ubicación tras groupby
# ──────────────────────────────────────────────────────────────────────────────

def _restore_location_info(grouped: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """
    Rellena las columnas latitud/longitud/pais/ciudad/universidad del grouped
    usando los valores reales del df original (promedio / moda por cluster).
    """
    def _mode_str(s: pd.Series) -> str:
        m = s.dropna().mode()
        return str(m.iloc[0]) if not m.empty else ""

    keys = ["_lat_r", "_lon_r"]

    # Calcular media de coordenadas por cluster de una sola vez
    coord_agg = (
        df.groupby(keys, dropna=False)
          .agg(latitud=("latitud", "mean"), longitud=("longitud", "mean"))
          .reset_index()
    )

    # Calcular moda de columnas de texto por cluster de una sola vez
    text_cols = [c for c in ("pais", "ciudad", "universidad") if c in df.columns]
    if text_cols:
        text_agg = (
            df.groupby(keys, dropna=False)[text_cols]
              .agg(_mode_str)
              .reset_index()
        )
        location_agg = coord_agg.merge(text_agg, on=keys, how="left")
    else:
        location_agg = coord_agg

    # Sustituir columnas de ubicación del grouped con los valores calculados
    cols_to_drop = [c for c in ("latitud", "longitud", *text_cols) if c in grouped.columns]
    return grouped.drop(columns=cols_to_drop, errors="ignore").merge(
        location_agg, on=keys, how="left"
    )


EMPTY_DF_COLS = ["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"]
