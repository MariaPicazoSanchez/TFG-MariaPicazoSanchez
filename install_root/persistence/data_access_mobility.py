import os
import re
import logging
import unicodedata
from typing import Iterable, Tuple, Optional
import pandas as pd
import math
from .sheets_helpers import sheets_for, resolve_sheet
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT, EXCEL_EXTENSIONS
from .materias_in_loader import (
    get_materias_in_por_estudiante,
    get_alumnos_in
)

logger = logging.getLogger("movilidad_persistence")

# ==============================
# Helpers comunes
# ==============================

def _norm_name(s: str) -> str:
    """Normaliza un nombre: minúsculas, sin acentos, sin espacios extra."""
    if not s or str(s).strip().lower() in ("", "nan", "none"):
        return ""
    s = str(s).strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s).strip()


def _build_materias_index(materias_dict: dict) -> dict:
    """
    Construye índices de búsqueda para hacer matching flexible de nombres:
    1. Nombre completo normalizado -> clave original
    2. Apellido (última palabra) -> lista de claves originales
    3. Primer apellido + segundo apellido -> clave original
    """
    exact = {}      # nombre_norm -> clave_original
    by_last = {}    # ultima_palabra -> [clave_original]

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
    # 1. Exacto
    if norm in exact:
        return exact[norm]
    # 2. Por apellido (última palabra del nombre completo)
    words = norm.split()
    for last in reversed(words):  # prueba desde el último apellido hacia atrás
        if last in by_last:
            candidates = by_last[last]
            if len(candidates) == 1:
                return candidates[0]
            # Si hay varios, buscar el que comparte más palabras
            best = max(candidates, key=lambda c: len(set(_norm_name(c).split()) & set(words)))
            return best
    return None

def get_universities_from_coords_sheet(path: str) -> list[str]:
    """
    Devuelve la lista de universidades desde la hoja 'Coordenadas'
    de un Excel de movilidad.
    
    Formato esperado hoja Coordenadas:
    col0 -> País
    col1 -> Universidad
    col2 -> Coordenadas
    """

    try:
        df_coords = pd.read_excel(
            path,
            sheet_name="Coordenadas",
            header=None,
            dtype=str
        )

        universidades = (
            df_coords.iloc[:, 1]      # columna universidad
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
        )

        return sorted(universidades)

    except Exception:
        return []

def get_universities_from_sicue_data(path: str) -> tuple[list[str], dict, dict]:
    """
    Extrae universidades únicas del Excel de SICUE OUT leyendo todas las hojas
    de datos (las que parecen cursos académicos).

    Devuelve:
        universidades : list[str]          — lista ordenada de nombres únicos
        ciudad_map    : dict[str, str]     — {universidad: ciudad}
        coords_map    : dict[str, tuple]   — {universidad: (lat, lon)} solo las ya geocodificadas
    """
    import re

    def _is_academic_sheet(name: str) -> bool:
        return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', str(name)))

    universidades: dict[str, dict] = {}  # uni -> {"ciudad": ..., "lat": ..., "lon": ...}

    try:
        wb_sheets = pd.ExcelFile(path, engine="openpyxl").sheet_names
    except Exception:
        return [], {}, {}

    hojas_datos = [s for s in wb_sheets if _is_academic_sheet(s)]
    # Si no hay hojas con patrón académico, usar todas excepto "coordenadas"
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

                # Intentar extraer coordenadas ya guardadas
                lat, lon = None, None
                if c_coords:
                    raw_coords = str(row.get(c_coords) or "")
                    lat, lon = _parse_coords(raw_coords)
                elif c_lat and c_lon:
                    try:
                        lat = float(str(row.get(c_lat) or "").replace(",", "."))
                        lon = float(str(row.get(c_lon) or "").replace(",", "."))
                    except (ValueError, TypeError):
                        lat, lon = None, None

                existing = universidades.get(uni, {})
                # Actualizar ciudad si aún no la tenemos
                if not existing.get("ciudad") and ciudad:
                    existing["ciudad"] = ciudad
                # Actualizar coords si aún no las tenemos
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


def filter_students_with_coords(
    df: pd.DataFrame,
    tipo: str,
    _messages: list | None = None,
) -> pd.DataFrame:
    """
    Filtra filas sin coordenadas.
    Los avisos se acumulan en _messages (lista de strings) para mostrarlos
    fuera de cualquier función cacheada con @st.cache_data.
    """
    mask_coords = df["latitud"].notna() & df["longitud"].notna()
    if not mask_coords.all():
        for _, row in df[~mask_coords].iterrows():
            nombre = row.get("estudiante", "(sin nombre)")
            nombre_str = str(nombre).strip().lower()
            if pd.isna(nombre) or nombre_str == "" or nombre_str == "nan" or nombre_str == "0":
                continue
            if _messages is not None:
                _messages.append(
                    f"⚠️ El alumno **{nombre}** ({tipo}) no tiene coordenadas "
                    "y no se mostrará en el mapa."
                )
    return df[mask_coords].copy()

def _norm_colname(s: str) -> str:
    """Normaliza un nombre de columna para comparaciones relajadas."""
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _pick(df: pd.DataFrame, *aliases: Iterable[str]) -> Optional[str]:
    """
    Devuelve el nombre REAL de la primera columna existente entre los alias dados.
    Hace match relajado y también 'contains' por si hay typos (Cuatirmestre/Cuatrimestre).
    """
    norm_map = {_norm_colname(c): c for c in df.columns}
    # exactos
    for a in aliases:
        if a is None:
            continue
        na = _norm_colname(a)
        if na in norm_map:
            return norm_map[na]
    # contains único — excluir columnas cuyo nombre normalizado sea puramente numérico
    # (p.ej. columna "1" coincidiría con "Apellido1" al buscar substring "1")
    non_numeric_norm_map = {
        norm: real for norm, real in norm_map.items()
        if norm and not norm.replace(".", "").isdigit()
    }
    for a in aliases:
        if a is None:
            continue
        na = _norm_colname(a)
        cand = [real for norm, real in non_numeric_norm_map.items() if na in norm or norm in na]
        if len(cand) == 1:
            return cand[0]
    return None

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

def _read_table(path: str, sheet_name: str | None = None, nrows: int | None = None) -> pd.DataFrame:
    """
    Lee CSV/XLS/XLSX con motor adecuado.
    - CSV → read_csv
    - Excel → read_excel (openpyxl para .xlsx/.xlsm)
    Nota: si sheet_name es None en Excel, pandas devuelve dict; aquí lo
    forzamos a 0 (primera hoja) para devolver siempre un DataFrame.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path, nrows=nrows, encoding="utf-8", sep=None, engine="python")

    if ext in EXCEL_EXTENSIONS:
        effective_sheet = 0 if sheet_name is None else sheet_name
        try:
            # usa openpyxl cuando aplica; pandas elegirá motor para .xls
            engine = "openpyxl" if ext in EXCEL_EXTENSIONS[:-1] else None
            return pd.read_excel(path, sheet_name=effective_sheet, engine=engine, nrows=nrows)
        except TypeError:
            # algunos pandas no aceptan engine=None; reintenta sin engine
            return pd.read_excel(path, sheet_name=effective_sheet, nrows=nrows)

    # fallback genérico
    effective_sheet = 0 if sheet_name is None else sheet_name
    return pd.read_excel(path, sheet_name=effective_sheet, nrows=nrows)


# ==============================
#   CLUSTERING DE COORDENADAS
# ==============================
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula distancia en metros entre dos puntos usando Haversine.
    Retorna distancia en metros.
    """
    if any(v is None or pd.isna(v) for v in [lat1, lon1, lat2, lon2]):
        return float('inf')
    
    R = 6371000  # Radio terrestre en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def cluster_coordinates(df: pd.DataFrame, max_distance_m: int = 150) -> pd.DataFrame:
    """
    Agrupa coordenadas que están muy cerca (clustering con Union-Find).
    Si dos puntos están a menos de max_distance_m, asignan las MISMAS coordenadas (promediadas).
    Esto permite que el groupby posterior los agrupe correctamente sin perder filas.
    
    Args:
        df: DataFrame con columnas 'latitud' y 'longitud'
        max_distance_m: Distancia máxima en metros para agrupar (default: 150m)
    
    Returns:
        DataFrame con coordenadas normalizadas (filas sin cambios, solo coordinadas)
    """
    if df.empty or "latitud" not in df.columns or "longitud" not in df.columns:
        return df
    
    # Validar que hay coordenadas
    valid_mask = df["latitud"].notna() & df["longitud"].notna()
    if not valid_mask.any():
        return df
    
    # Reiniciar índices para tracking
    df = df.reset_index(drop=True).copy()
    
    # Union-Find para agrupar índices
    parent = list(range(len(df)))
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # Construir clusters usando distancia Haversine
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
    
    # Agrupar por cluster y calcular promedios
    clusters_map = {}
    for i in range(len(df)):
        if valid_mask.iloc[i]:
            root = find(i)
            if root not in clusters_map:
                clusters_map[root] = []
            clusters_map[root].append(i)
    
    # Crear mapa de índice -> coordenadas promediadas
    new_coords = {}
    for cluster_id, indices in clusters_map.items():
        cluster_data = df.iloc[indices]
        avg_lat = cluster_data["latitud"].mean()
        avg_lon = cluster_data["longitud"].mean()
        for idx in indices:
            new_coords[idx] = (avg_lat, avg_lon)
    
    # Aplicar las nuevas coordenadas (mantener TODAS las filas)
    for idx, (new_lat, new_lon) in new_coords.items():
        df.iloc[idx, df.columns.get_loc("latitud")] = new_lat
        df.iloc[idx, df.columns.get_loc("longitud")] = new_lon
    
    return df


# ==============================
#   ERASMUS OUT
# ==============================
def load_erasmus_out(path: str, sheet_name: str | None = None, _messages: list | None = None) -> pd.DataFrame:
    """
    Carga Erasmus OUT y agrupa por universidad/pais/coords.
    Devuelve DF con columnas: ['universidad','pais','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)
    # limpieza de cabeceras
    df.columns = [str(col).strip() for col in df.columns]

    c_nombre   = _pick(df, "Nombre", "nombre")
    c_ap1      = _pick(df, "Apellido1", "apellido1")
    c_ap2      = _pick(df, "Apellido2", "apellido2")
    c_email    = _pick(df, "Email", "email")
    c_coords   = _pick(df, "Coordenadas", "coords")
    c_dest     = _pick(df, "Destino", "Universidad Destino", "Universidad")
    c_ciudad   = _pick(df, "Ciudad", "Ciudad Origen", "Ciudad origen", "City", "city", "ciudad")
    c_pais     = _pick(df, "País", "Pais")
    c_la       = _pick(df, "LA")
    c_plan     = _pick(df, "Plan de estudios", "Plan estudios", "Plan_estudios", "Enlace plan de estudios")
    c_lat      = _pick(df, "Latitud", "latitud", "lat")
    c_lon      = _pick(df, "Longitud", "longitud", "lon")
    c_curso    = _pick(df, "Curso", "curso")
    c_duracion = _pick(df, "Duracion meses", "Duración meses", "duracion_meses", "duración_meses")
    c_resp     = _pick(df, "Responsable programa", "Responsable", "responsable")
    c_tor      = _pick(df, "ToR", "tor")

    # estudiante
    if c_nombre or c_ap1 or c_ap2:
        parts = []
        if c_nombre: parts.append(df[c_nombre].astype(str))
        if c_ap1:    parts.append(df[c_ap1].astype(str))
        if c_ap2:    parts.append(df[c_ap2].fillna("").astype(str))
        s = parts[0] if parts else pd.Series([""])
        for p in parts[1:]:
            s = (s + " " + p)
        df["estudiante"] = s.str.replace(r"\s+", " ", regex=True).str.strip()
    elif c_email:
        df["estudiante"] = df[c_email].astype(str).str.split("@").str[0]
    else:
        df["estudiante"] = ""

    # Cargar coordenadas desde hoja "Coordenadas" cruzando por universidad
    coords_dict = {}
    try:
        df_coords = pd.read_excel(path, sheet_name="Coordenadas", header=None, dtype=str)
        df_coords.columns = [f"col{i}" for i in range(df_coords.shape[1])]
        # Formato esperado: col0=País, col1=Universidad, col2=Coordenadas
        for _, row in df_coords.iterrows():
            uni = str(row.get("col1", "") or "").strip()
            coords_raw = str(row.get("col2", "") or "").strip()
            if uni and coords_raw and coords_raw.lower() not in ("nan", "none", ""):
                coords_dict[uni] = coords_raw
    except Exception:
        coords_dict = {}

    # coords: primero columna directa, luego lookup por universidad
    if c_coords:
        lats, lons = zip(*df[c_coords].map(_parse_coords))
        df["latitud"] = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"]  = pd.to_numeric(df[c_lat], errors="coerce") if c_lat else pd.NA
        df["longitud"] = pd.to_numeric(df[c_lon], errors="coerce") if c_lon else pd.NA

    # normalización campos "macro"
    df["universidad"] = df[c_dest] if c_dest else None
    df["pais"]        = df[c_pais] if c_pais else None
    # Normalizar país a mayúsculas para consistencia
    df["pais"] = df["pais"].str.upper() if c_pais else None

    # Completar coordenadas faltantes por universidad desde hoja Coordenadas
    if coords_dict and c_dest:
        uni_col = df["universidad"].astype(str).str.strip()
        df["_coords_lookup"] = uni_col.map(coords_dict)
        parsed = df["_coords_lookup"].map(_parse_coords)
        df["_lat_lu"] = [p[0] for p in parsed]
        df["_lon_lu"] = [p[1] for p in parsed]
        df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce").fillna(pd.to_numeric(df["_lat_lu"], errors="coerce"))
        df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce").fillna(pd.to_numeric(df["_lon_lu"], errors="coerce"))
        df.drop(columns=["_coords_lookup", "_lat_lu", "_lon_lu"], inplace=True)
    df["ciudad"]      = df[c_ciudad] if c_ciudad else None
    df["link_LA"]     = df[c_la]   if c_la   else None
    df["link_plan"]   = df[c_plan] if c_plan else None

    def _to_records(g: pd.DataFrame) -> list[dict]:
        mapping = {}
        if c_email:    mapping[c_email]    = "email"
        if c_curso:    mapping[c_curso]    = "curso"
        if c_duracion: mapping[c_duracion] = "duracion_meses"
        if c_resp:     mapping[c_resp]     = "responsable"
        if c_tor:      mapping[c_tor]      = "ToR"
        
        keep = ["estudiante"]
        if "link_LA" in g.columns:
            keep.append("link_LA")
        if "link_plan" in g.columns:
            keep.append("link_plan")
        keep_mapped = keep + list(mapping.keys())
        
        # Convertir a lista de dicts usando to_dict para soportar columnas con espacios
        records = []
        for raw in g.to_dict('records'):
            record = {}
            for col in keep:
                if col in raw:
                    record[col] = raw[col]
            for orig_col, mapped_col in mapping.items():
                if orig_col in raw:
                    record[mapped_col] = raw[orig_col]
            if c_ciudad and c_ciudad in raw:
                record["ciudad"] = raw[c_ciudad]
            record["_sheet_name"] = sheet_name or ""
            records.append(record)
        return records
    
    # Fase 4: Clustering de coordenadas - agrupar puntos cercanos
    df = cluster_coordinates(df, max_distance_m=500)

    # Redondear coordenadas para agrupar (2 decimales = ~1km de precisión)
    df["_lat_r"] = df["latitud"].round(2)
    df["_lon_r"] = df["longitud"].round(2)

    df = filter_students_with_coords(df, "Erasmus OUT", _messages)

    if df.empty:
        if _messages is not None:
            _messages.append("ℹ️ No hay alumnos de **Erasmus OUT** con coordenadas válidas para mostrar en el mapa.")
        return pd.DataFrame(columns=["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"])

    grouped = (
        df.groupby(["_lat_r", "_lon_r"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )

    if grouped.empty:
        if _messages is not None:
            _messages.append("ℹ️ No hay grupos válidos de **Erasmus OUT** para mostrar en el mapa.")
        return pd.DataFrame(columns=["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"])

    # Restaurar info de ubicación solo si hay filas
    for i, row in grouped.iterrows():
        if row["estudiantes"]:
            grupo_df = df[
                (df["_lat_r"] == row["_lat_r"]) & 
                (df["_lon_r"] == row["_lon_r"])
            ]
            if not grupo_df.empty:
                grouped.at[i, "latitud"] = grupo_df["latitud"].mean()
                grouped.at[i, "longitud"] = grupo_df["longitud"].mean()
                if not grupo_df["pais"].isna().all():
                    grouped.at[i, "pais"] = str(grupo_df["pais"].mode()[0] if not grupo_df["pais"].mode().empty else grupo_df["pais"].iloc[0])
                if not grupo_df["ciudad"].isna().all():
                    grouped.at[i, "ciudad"] = str(grupo_df["ciudad"].mode()[0] if not grupo_df["ciudad"].mode().empty else grupo_df["ciudad"].iloc[0])
                if not grupo_df["universidad"].isna().all():
                    grouped.at[i, "universidad"] = str(grupo_df["universidad"].mode()[0] if not grupo_df["universidad"].mode().empty else grupo_df["universidad"].iloc[0])

    # Limpiar columnas temporales
    grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")

    # Fase 3: Liberar memoria del DataFrame original tras agrupar
    del df
    import gc
    gc.collect()

    return grouped


# ==============================
#   ERASMUS IN
# ==============================
def load_erasmus_in(path: str, sheet_name: str | None = None, _messages: list | None = None) -> pd.DataFrame:
    """
    Carga Erasmus IN y agrupa por universidad/pais/coords.
    Devuelve DF con columnas: ['universidad','pais','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)
    df.columns = [str(col).strip() for col in df.columns]
    logger.debug("[IN] Columnas leídas: %s", list(df.columns))
    logger.debug("[IN] Total filas: %d", len(df))

    c_nombre     = _pick(df, "Nombre", "nombre")
    c_ap1        = _pick(df, "Apellido1", "apellido1")
    c_ap2        = _pick(df, "Apellido2", "apellido2")
    c_estudiante = _pick(df, "Estudiante", "estudiante", "Alumno", "alumno")
    c_email      = _pick(df, "Email", "email")
    c_cuatri     = _pick(df, "Cuatrimestre", "Cuatri", "Cuat")
    c_la         = _pick(df, "LA")
    c_uni        = _pick(df, "Universidad Origen", "Univ. Origen", "UniversidadOrigen", "Universidad")
    c_ciudad     = _pick(df, "Ciudad", "Ciudad Origen", "Ciudad origen", "City", "city", "ciudad")
    c_pais       = _pick(df, "País", "Pais", "Origen")
    c_coords     = _pick(df, "Coordenadas", "coords")
    # Buscar lat/lon con nombres exactos para evitar falso match con "LA"
    c_lat        = _pick(df, "Latitud", "latitud")
    c_lon        = _pick(df, "Longitud", "longitud")
    # Evitar que "LA" sea detectado como latitud
    if c_lat == c_la:
        c_lat = None
    if c_lon == c_la:
        c_lon = None
    logger.debug(
        "[IN] Columnas detectadas: nombre=%s, estudiante=%s, ap1=%s, ap2=%s, uni=%s, "
        "pais=%s, coords=%s, lat=%s, lon=%s, cuatri=%s, la=%s",
        c_nombre, c_estudiante, c_ap1, c_ap2, c_uni,
        c_pais, c_coords, c_lat, c_lon, c_cuatri, c_la
    )

    # Cargar coordenadas desde hoja "Coordenadas" cruzando por universidad
    coords_dict = {}
    try:
        df_coords = pd.read_excel(path, sheet_name="Coordenadas", header=None, dtype=str)
        df_coords.columns = [f"col{i}" for i in range(df_coords.shape[1])]
        # Formato esperado: col0=País, col1=Universidad, col2=Coordenadas
        for _, row in df_coords.iterrows():
            uni = str(row.get("col1", "") or "").strip()
            coords_raw = str(row.get("col2", "") or "").strip()
            if uni and coords_raw and coords_raw.lower() not in ("nan", "none", ""):
                coords_dict[uni] = coords_raw
        logger.debug("[IN] Coordenadas cargadas desde hoja 'Coordenadas': %d universidades", len(coords_dict))
    except Exception as e:
        logger.debug("[IN] No se pudo leer hoja 'Coordenadas': %s", e)

    # estudiante
    if c_nombre or c_ap1 or c_ap2:
        parts = []
        if c_nombre: parts.append(df[c_nombre].astype(str))
        if c_ap1:    parts.append(df[c_ap1].astype(str))
        if c_ap2:    parts.append(df[c_ap2].fillna("").astype(str))
        s = parts[0] if parts else pd.Series([""])
        for p in parts[1:]:
            s = (s + " " + p)
        df["estudiante"] = s.str.replace(r"\s+", " ", regex=True).str.strip()
    elif c_estudiante:
        df["estudiante"] = df[c_estudiante].astype(str).str.strip()
    elif c_email:
        df["estudiante"] = df[c_email].astype(str).str.split("@").str[0]
    else:
        df["estudiante"] = ""

    # coords: primero columna directa, luego lookup por universidad
    if c_coords:
        lats, lons = zip(*df[c_coords].map(_parse_coords))
        df["latitud"]  = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"]  = pd.to_numeric(df[c_lat], errors="coerce") if c_lat else pd.NA
        df["longitud"] = pd.to_numeric(df[c_lon], errors="coerce") if c_lon else pd.NA

    # Completar coordenadas faltantes por universidad desde hoja Coordenadas
    if coords_dict and c_uni:
        uni_col = df[c_uni].astype(str).str.strip()
        df["_coords_lookup"] = uni_col.map(coords_dict)
        parsed = df["_coords_lookup"].map(_parse_coords)
        df["_lat_lu"] = [p[0] for p in parsed]
        df["_lon_lu"] = [p[1] for p in parsed]
        df["latitud"]  = pd.to_numeric(df["latitud"], errors="coerce").fillna(pd.to_numeric(df["_lat_lu"], errors="coerce"))
        df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce").fillna(pd.to_numeric(df["_lon_lu"], errors="coerce"))
        df.drop(columns=["_coords_lookup", "_lat_lu", "_lon_lu"], inplace=True)
        logger.debug("[IN] Coords tras lookup por universidad: %d / %d filas con coords",
                     df['latitud'].notna().sum(), len(df))

    # normaliza campos
    df["universidad"] = df[c_uni].astype(str).str.strip() if c_uni else None
    df["pais"]         = df[c_pais].astype(str).str.strip() if c_pais else None
    df["ciudad"]       = df[c_ciudad] if c_ciudad else None
    df["link_LA"]      = df[c_la]     if c_la     else None
    df["cuatrimestre"] = df[c_cuatri] if c_cuatri else None

    logger.debug("[IN] Muestra estudiantes (primeros 5): %s", df['estudiante'].head().tolist())
    logger.debug("[IN] Muestra latitud:  %s", df['latitud'].head().tolist())
    logger.debug("[IN] Muestra longitud: %s", df['longitud'].head().tolist())
    logger.debug("[IN] Filas con coords válidas: %d / %d", df['latitud'].notna().sum(), len(df))
    logger.debug("[IN] Muestra universidad: %s",
                 df['universidad'].head().tolist() if 'universidad' in df.columns else 'N/A')

    def _to_records(g: pd.DataFrame) -> list[dict]:
        # Deduplicar por estudiante (hay múltiples filas por alumno, una por asignatura)
        seen = set()
        records = []
        cols = ["estudiante", "cuatrimestre", "link_LA"]
        if c_email: cols.insert(1, c_email)
        cols = [c for c in cols if c in g.columns]
        for raw in g.to_dict('records'):
            est = raw.get("estudiante") or ""
            if est in seen:
                continue
            seen.add(est)
            record = {}
            for col in cols:
                if col in raw:
                    if col == c_email and c_email != "email":
                        record["email"] = raw[col]
                    else:
                        record[col] = raw[col]
            if c_ciudad and c_ciudad in raw:
                record["ciudad"] = raw[c_ciudad]
            if c_uni and c_uni in raw:
                record["universidad de origen"] = raw[c_uni]
            records.append(record)
        return records

    # Fase 4: Clustering de coordenadas
    df = cluster_coordinates(df, max_distance_m=500)

    # Redondear coordenadas para agrupar (2 decimales = ~1km)
    df["_lat_r"] = df["latitud"].round(2)
    df["_lon_r"] = df["longitud"].round(2)

    df = filter_students_with_coords(df, "Erasmus IN", _messages)
    logger.debug("[IN] Tras filtrar coords: %d filas", len(df))

    if df.empty:
        if _messages is not None:
            _messages.append("ℹ️ No hay alumnos de **Erasmus IN** con coordenadas válidas para mostrar en el mapa.")
        return pd.DataFrame(columns=["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"])

    grouped = (
        df.groupby(["_lat_r", "_lon_r"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )
    logger.debug("[IN] Grupos tras groupby: %d", len(grouped))

    if grouped.empty:
        if _messages is not None:
            _messages.append("ℹ️ No hay grupos válidos de **Erasmus IN** para mostrar en el mapa.")
        return pd.DataFrame(columns=["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"])

    # Restaurar info de ubicación solo si hay filas
    for i, row in grouped.iterrows():
        if row["estudiantes"]:
            grupo_df = df[
                (df["_lat_r"] == row["_lat_r"]) & 
                (df["_lon_r"] == row["_lon_r"])
            ]
            if not grupo_df.empty:
                grouped.at[i, "latitud"] = grupo_df["latitud"].mean()
                grouped.at[i, "longitud"] = grupo_df["longitud"].mean()
                if not grupo_df["pais"].isna().all():
                    grouped.at[i, "pais"] = str(grupo_df["pais"].mode()[0] if not grupo_df["pais"].mode().empty else grupo_df["pais"].iloc[0])
                if not grupo_df["ciudad"].isna().all():
                    grouped.at[i, "ciudad"] = str(grupo_df["ciudad"].mode()[0] if not grupo_df["ciudad"].mode().empty else grupo_df["ciudad"].iloc[0])
                if not grupo_df["universidad"].isna().all():
                    grouped.at[i, "universidad"] = str(grupo_df["universidad"].mode()[0] if not grupo_df["universidad"].mode().empty else grupo_df["universidad"].iloc[0])

    # Limpiar columnas temporales
    grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")

    # Fase 3: Liberar memoria
    del df
    import gc
    gc.collect()
    # Cargar materias y asociar con matching flexible de nombres
    config = {"Erasmus IN": path}
    materias_dict = get_materias_in_por_estudiante(config)

    if materias_dict:
        logger.debug("[IN] Alumnos en materias_dict: %s", list(materias_dict.keys())[:10])
        exact_idx, last_idx = _build_materias_index(materias_dict)
        for grupo in grouped["estudiantes"]:
            for alumno in grupo:
                nombre = alumno.get("estudiante") or ""
                # Intento 1: lookup directo
                materias = materias_dict.get(nombre)
                # Intento 2: matching flexible por apellido
                if not materias:
                    clave = _match_student_name(nombre, exact_idx, last_idx)
                    if clave:
                        logger.debug("[IN] Matching '%s' -> '%s'", nombre, clave)
                        materias = materias_dict.get(clave, [])
                    else:
                        logger.debug("[IN] Sin match para '%s'", nombre)
                alumno["materias"] = materias or []
    else:
        logger.debug("[IN] materias_dict vacío — no se cargaron materias")

    return grouped


# ==============================
#   SICUE OUT
# ==============================
def load_sicue_out(path: str, sheet_name: str | None = None, _messages: list | None = None) -> pd.DataFrame:
    """
    Lee SICUE OUT y agrupa por universidad/ciudad/coords.
    Devuelve DF con columnas: ['universidad','pais','ciudad','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)
    # ==============================
    # Cargar coordenadas desde hoja "coordenadas"
    # ==============================
    try:
        df_coords = pd.read_excel(
            path,
            sheet_name="coordenadas",
            header=None,
            dtype=str
        )

        # columnas sin cabecera:
        # A -> país
        # B -> universidad
        # C -> coordenadas
        df_coords.columns = ["pais", "universidad", "coords"]

        # limpiar texto
        df_coords["universidad"] = df_coords["universidad"].str.strip()
        df_coords["coords"] = df_coords["coords"].str.strip()

        # crear diccionario universidad -> coords
        coords_dict = dict(
            zip(df_coords["universidad"], df_coords["coords"])
        )
        coords_dict = {
            str(k).strip(): v
            for k, v in coords_dict.items()
        }

    except Exception:
        coords_dict = {}


    df.columns = [str(col).strip() for col in df.columns]

    c_nombre      = _pick(df, "Nombre", "nombre")
    c_ap1         = _pick(df, "Apellido1", "apellido1", "Apellidos", "apellidos")
    c_ap2         = _pick(df, "Apellido2", "apellido2")
    c_email       = _pick(df, "Email", "email")
    c_dur         = _pick(df, "Duracion meses", "Duración meses", "duracion_meses", "duración_meses")
    c_coord_dest  = _pick(df, "Coordinador en destino", "Coordinador destino")
    c_la          = _pick(df, "LA")
    c_gestion     = _pick(df, "Gestion LA", "Gestión LA", "gestion la", "gestión la")
    c_destino     = _pick(df, "Destino", "Universidad Destino", "Universidad")
    c_ciudad      = _pick(df, "Ciudad")
    c_coords      = _pick(df, "Coordenadas", "coords")
    c_lat         = _pick(df, "Latitud", "latitud", "lat")
    c_lon         = _pick(df, "Longitud", "longitud", "lon")
    c_plan = _pick(df, "Plan de estudios", "Plan estudios", "Plan_estudios", "Enlace plan de estudios", "plan de es")

    # estudiante
    if c_nombre or c_ap1 or c_ap2:
        parts = []
        if c_nombre: parts.append(df[c_nombre].astype(str))
        if c_ap1:    parts.append(df[c_ap1].astype(str))
        if c_ap2:    parts.append(df[c_ap2].fillna("").astype(str))
        s = parts[0] if parts else pd.Series([""])
        for p in parts[1:]:
            s = (s + " " + p)
        df["estudiante"] = s.str.replace(r"\s+", " ", regex=True).str.strip()
    elif c_email:
        df["estudiante"] = df[c_email].astype(str).str.split("@").str[0]
    else:
        df["estudiante"] = ""

    # coords
    if c_coords:
        lats, lons = zip(*df[c_coords].map(_parse_coords))
        df["latitud"]  = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"]  = pd.to_numeric(df[c_lat], errors="coerce") if c_lat else pd.NA
        df["longitud"] = pd.to_numeric(df[c_lon], errors="coerce") if c_lon else pd.NA

    # normaliza
    df["universidad"]        = df[c_destino] if c_destino else None
    # ==============================
    # Completar coordenadas faltantes por universidad
    # ==============================
    if coords_dict:

        # limpiar universidad (MUY IMPORTANTE)
        df["universidad"] = df["universidad"].astype(str).str.strip()

        df["coords_lookup"] = df["universidad"].map(coords_dict)

        parsed = df["coords_lookup"].map(_parse_coords)

        df["lat_lookup"] = [p[0] for p in parsed]
        df["lon_lookup"] = [p[1] for p in parsed]

        # SOLO rellenar donde falten coords
        df["latitud"] = df["latitud"].fillna(df["lat_lookup"])
        df["longitud"] = df["longitud"].fillna(df["lon_lookup"])

        # limpiar columnas auxiliares
        df.drop(columns=["coords_lookup", "lat_lookup", "lon_lookup"], inplace=True)
    df["ciudad"]             = df[c_ciudad]  if c_ciudad  else None
    df["pais"]               = "España"
    # mapeo de columnas específicas a names homogéneos
    mapping = {}
    if c_la:         mapping[c_la] = "link_LA"
    if c_gestion:    mapping[c_gestion] = "gestion_LA"
    if c_coord_dest: mapping[c_coord_dest] = "coordinador_destino"
    if c_dur:        mapping[c_dur] = "duracion_meses"
    if c_email:      mapping[c_email] = "email"
    if c_plan:       mapping[c_plan] = "link_plan"

    def _to_records(g: pd.DataFrame) -> list[dict]:
        records = []
        for raw in g.to_dict('records'):
            record = {}
            if "estudiante" in raw:
                record["estudiante"] = raw["estudiante"]
            for orig_col, new_col in mapping.items():
                if orig_col in raw:
                    record[new_col] = raw[orig_col]
            if c_ciudad and c_ciudad in raw:
                record["ciudad"] = raw[c_ciudad]
            record["_sheet_name"] = sheet_name or ""
            records.append(record)
        return records

    # Fase 4: Clustering de coordenadas
    df = cluster_coordinates(df, max_distance_m=500)

    # Redondear coordenadas para agrupar (2 decimales = ~1km)
    df["_lat_r"] = df["latitud"].round(2)
    df["_lon_r"] = df["longitud"].round(2)

    df = filter_students_with_coords(df, "SICUE OUT", _messages)

    if df.empty:
        if _messages is not None:
            _messages.append("ℹ️ No hay alumnos de **SICUE OUT** con coordenadas válidas para mostrar en el mapa.")
        return pd.DataFrame(columns=["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"])

    grouped = (
        df.groupby(["_lat_r", "_lon_r"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )

    if grouped.empty:
        if _messages is not None:
            _messages.append("ℹ️ No hay grupos válidos de **SICUE OUT** para mostrar en el mapa.")
        return pd.DataFrame(columns=["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"])

    # Restaurar info de ubicación solo si hay filas
    for i, row in grouped.iterrows():
        if row["estudiantes"]:
            grupo_df = df[
                (df["_lat_r"] == row["_lat_r"]) & 
                (df["_lon_r"] == row["_lon_r"])
            ]
            if not grupo_df.empty:
                grouped.at[i, "latitud"] = grupo_df["latitud"].mean()
                grouped.at[i, "longitud"] = grupo_df["longitud"].mean()
                if not grupo_df["ciudad"].isna().all():
                    grouped.at[i, "ciudad"] = grupo_df["ciudad"].mode()[0] if not grupo_df["ciudad"].mode().empty else grupo_df["ciudad"].iloc[0]
                if not grupo_df["universidad"].isna().all():
                    grouped.at[i, "universidad"] = grupo_df["universidad"].mode()[0] if not grupo_df["universidad"].mode().empty else grupo_df["universidad"].iloc[0]

    # Limpiar columnas temporales y añadir país
    grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")
    grouped["pais"] = "España"
    grouped = grouped[["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"]]

    # Fase 3: Liberar memoria
    del df
    import gc
    gc.collect()

    return grouped


# ==============================
#   Auto-detección (por columnas)
# ==============================
def load_mobility_any(path: str, sheet_name: str | None = None) -> pd.DataFrame:
    """Detecta por cabeceras y enruta al loader adecuado."""
    head = _read_table(path, sheet_name=sheet_name, nrows=1)
    cols = {_norm_colname(c) for c in head.columns}

    if "universidad origen" in cols or "cuatrimestre" in cols or "cuatirmestre" in cols:
        return load_erasmus_in(path, sheet_name=sheet_name)
    if "coordinador en destino" in cols or "gestion la" in cols or "gestión la" in cols or "ciudad" in cols:
        return load_sicue_out(path, sheet_name=sheet_name)
    return load_erasmus_out(path, sheet_name=sheet_name)


# ==============================
#   Agregador con filtro global
# ==============================
def load_all_dataframes(config: dict, global_sheet: str, programs_to_load: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """
    Carga DF por tipo aplicando el filtro global de hoja:
    - 'Todas' → usa los loaders habituales.
    - Hoja concreta → lee solo esa hoja (si el loader acepta sheet_name, se usa;
      si no, se lee directo con pandas).
    
    Args:
        config: Configuración con rutas a Excel
        global_sheet: Hoja a cargar ('Todas' o nombre específico)
        programs_to_load: Lista de programas a cargar. Si None, carga todos.
                         Ej: [PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN]
    
    Optimización (Fase 3): Lazy loading selectivo evita cargar datos innecesarios.
    """
    dfs: dict[str, pd.DataFrame] = {}
    # Lista de mensajes acumulados para mostrar FUERA de @st.cache_data
    messages: list[str] = []

    # Si no se especifica, carga todos
    if programs_to_load is None:
        programs_to_load = [PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT]

    mapping = [
        (PROGRAM_ERASMUS_OUT, config.get(PROGRAM_ERASMUS_OUT), load_erasmus_out),
        (PROGRAM_ERASMUS_IN,  config.get(PROGRAM_ERASMUS_IN),  load_erasmus_in),
        (PROGRAM_SICUE_OUT,   config.get(PROGRAM_SICUE_OUT),   load_sicue_out),
    ]
    sheets_map = (config or {}).get("sheets", {}) or {}

    for type_name, path, loader in mapping:
        # Fase 3: Lazy loading - solo cargar programas seleccionados
        if type_name not in programs_to_load:
            continue

        if not path:
            continue

        try:
            ext = os.path.splitext(path)[1].lower()

            if global_sheet and global_sheet != "Todas":
                if ext == ".csv":
                    # CSV no tiene hojas → omitir bajo filtro de hoja
                    continue

                candidates = sheets_map.get(type_name) or sheets_for(path)
                wanted = resolve_sheet(global_sheet, candidates)
                if not wanted:
                    messages.append(
                        f"ℹ️ {type_name}: hoja ‘{global_sheet}’ no encontrada "
                        f"en {os.path.basename(path)}"
                    )
                    continue

                # Pasa sheet_name y _messages al loader
                try:
                    df = loader(path, sheet_name=wanted, _messages=messages)
                except TypeError:
                    df = _read_table(path, sheet_name=wanted)
            else:
                df = loader(path, _messages=messages)

            if df is not None and len(df):
                dfs[type_name] = df

        except Exception as e:
            # Si es SICUE OUT y el error es de indexación, suprimir mensaje genérico
            if type_name == PROGRAM_SICUE_OUT and (
                ‘single positional indexer is out-of-bounds’ in str(e)
                or ‘indexer’ in str(e)
            ):
                pass
            else:
                messages.append(f"⚠️ No se pudo cargar {type_name}: {e}")

    return dfs, messages