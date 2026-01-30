import os
import re
from typing import Iterable, Tuple, Optional
import pandas as pd
from .sheets_helpers import sheets_for, resolve_sheet
import streamlit as st
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT, EXCEL_EXTENSIONS


# ==============================
# Helpers comunes
# ==============================
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
    # contains único
    for a in aliases:
        if a is None:
            continue
        na = _norm_colname(a)
        cand = [real for norm, real in norm_map.items() if na in norm or norm in na]
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
#   ERASMUS OUT
# ==============================
def load_erasmus_out(path: str, sheet_name: str | None = None) -> pd.DataFrame:
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

    # coords
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
        
        # Convertir a lista de dicts sin .copy()
        records = []
        for row in g.itertuples(index=False, name='Row'):
            record = {}
            for col in keep:
                if hasattr(row, col):
                    record[col] = getattr(row, col)
            for orig_col, mapped_col in mapping.items():
                if hasattr(row, orig_col):
                    record[mapped_col] = getattr(row, orig_col)
            if c_ciudad and c_ciudad in g.columns:
                if hasattr(row, c_ciudad):
                    record["ciudad"] = getattr(row, c_ciudad)
            records.append(record)
        return records
    
    groupby_cols = ["universidad", "ciudad", "latitud", "longitud", "pais"]
    if "link_LA" in df.columns:
        groupby_cols.append("link_LA")
    grouped = (
        df.groupby(groupby_cols, dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )
    return grouped


# ==============================
#   ERASMUS IN
# ==============================
def load_erasmus_in(path: str, sheet_name: str | None = None) -> pd.DataFrame:
    """
    Carga Erasmus IN y agrupa por universidad/pais/coords.
    Devuelve DF con columnas: ['universidad','pais','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)
    df.columns = [str(col).strip() for col in df.columns]

    c_nombre  = _pick(df, "Nombre", "nombre")
    c_ap1     = _pick(df, "Apellido1", "apellido1")
    c_ap2     = _pick(df, "Apellido2", "apellido2")
    c_email   = _pick(df, "Email", "email")
    c_cuatri  = _pick(df, "Cuatrimestre", "Cuatrimestre")
    c_la      = _pick(df, "LA")
    c_uni     = _pick(df, "Universidad Origen", "Univ. Origen", "Universidad")
    c_ciudad  = _pick(df, "Ciudad", "Ciudad Origen", "Ciudad origen", "City", "city", "ciudad")
    c_pais    = _pick(df, "País", "Pais")
    c_coords  = _pick(df, "Coordenadas", "coords")
    c_lat     = _pick(df, "Latitud", "latitud", "lat")
    c_lon     = _pick(df, "Longitud", "longitud", "lon")

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
        df["latitud"] = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"]  = pd.to_numeric(df[c_lat], errors="coerce") if c_lat else pd.NA
        df["longitud"] = pd.to_numeric(df[c_lon], errors="coerce") if c_lon else pd.NA

    # normaliza campos
    df["universidad"]   = df[c_uni]    if c_uni    else None
    df["pais"]          = df[c_pais]   if c_pais   else None
    df["ciudad"]        = df[c_ciudad] if c_ciudad else None
    df["link_LA"]       = df[c_la]     if c_la     else None
    df["cuatrimestre"]  = df[c_cuatri] if c_cuatri else None

    def _to_records(g: pd.DataFrame) -> list[dict]:
        cols = ["estudiante", "cuatrimestre", "link_LA"]
        if c_email: cols.insert(1, c_email)
        cols = [c for c in cols if c in g.columns]
        
        records = []
        for row in g.itertuples(index=False, name='Row'):
            record = {}
            for col in cols:
                if hasattr(row, col):
                    # Renombra email si viene de otra columna
                    if col == c_email and c_email != "email":
                        record["email"] = getattr(row, col)
                    else:
                        record[col] = getattr(row, col)
            if c_ciudad and c_ciudad in g.columns and hasattr(row, c_ciudad):
                record["ciudad"] = getattr(row, c_ciudad)
            records.append(record)
        return records

    grouped = (
        df.groupby(["universidad","ciudad", "latitud", "longitud", "pais"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )
    return grouped


# ==============================
#   SICUE OUT
# ==============================
def load_sicue_out(path: str, sheet_name: str | None = None) -> pd.DataFrame:
    """
    Lee SICUE OUT y agrupa por universidad/ciudad/coords.
    Devuelve DF con columnas: ['universidad','pais','ciudad','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)
    df.columns = [str(col).strip() for col in df.columns]

    c_nombre      = _pick(df, "Nombre", "nombre")
    c_ap1         = _pick(df, "Apellido1", "apellido1")
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
        keep = ["estudiante"] + [k for k in mapping.keys() if k in g.columns]
        
        records = []
        for row in g.itertuples(index=False, name='Row'):
            record = {}
            # Agregar field estudiante
            if hasattr(row, "estudiante"):
                record["estudiante"] = getattr(row, "estudiante")
            # Agregar campos mapeados
            for orig_col, new_col in mapping.items():
                if orig_col in g.columns and hasattr(row, orig_col):
                    record[new_col] = getattr(row, orig_col)
            # Agregar ciudad si existe
            if c_ciudad and c_ciudad in g.columns and hasattr(row, c_ciudad):
                record["ciudad"] = getattr(row, c_ciudad)
            records.append(record)
        return records

    grouped = (
        df.groupby(["universidad", "ciudad", "latitud", "longitud"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )
    grouped["pais"] = "España"
    grouped = grouped[["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"]]
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
def load_all_dataframes(config: dict, global_sheet: str) -> dict[str, pd.DataFrame]:
    """
    Carga DF por tipo aplicando el filtro global de hoja:
    - 'Todas' → usa los loaders habituales.
    - Hoja concreta → lee solo esa hoja (si el loader acepta sheet_name, se usa;
      si no, se lee directo con pandas).
    """
    dfs: dict[str, pd.DataFrame] = {}

    mapping = [
        (PROGRAM_ERASMUS_OUT, config.get(PROGRAM_ERASMUS_OUT), load_erasmus_out),
        (PROGRAM_ERASMUS_IN,  config.get(PROGRAM_ERASMUS_IN),  load_erasmus_in),
        (PROGRAM_SICUE_OUT,   config.get(PROGRAM_SICUE_OUT),   load_sicue_out),
    ]
    sheets_map = (config or {}).get("sheets", {}) or {}

    for type_name, path, loader in mapping:
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
                    st.info(f"ℹ️ {type_name}: hoja ‘{global_sheet}’ no encontrada en {os.path.basename(path)}")
                    continue

                # Pasa sheet_name al loader; si no lo soporta, lee directo con pandas
                try:
                    df = loader(path, sheet_name=wanted)
                except TypeError:
                    df = _read_table(path, sheet_name=wanted)
            else:
                df = loader(path)

            if df is not None and len(df):
                dfs[type_name] = df

        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar {type_name}: {e}")

    return dfs
