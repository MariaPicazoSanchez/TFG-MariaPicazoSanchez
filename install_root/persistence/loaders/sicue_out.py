"""
Loader para SICUE OUT.
"""

from __future__ import annotations

import gc

import pandas as pd

from ._common import (
    _pick, _parse_coords, _read_table,
    cluster_coordinates, filter_students_with_coords,
    _restore_location_info, EMPTY_DF_COLS,
)


def load_sicue_out(
    path: str,
    sheet_name: str | None = None,
    _messages: list | None = None,
) -> pd.DataFrame:
    """
    Carga SICUE OUT y agrupa por coordenadas.
    Devuelve DF con columnas: ['universidad','pais','ciudad','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)

    # Cargar coordenadas desde hoja "coordenadas"
    coords_dict: dict[str, str] = {}
    try:
        df_coords = pd.read_excel(path, sheet_name="coordenadas", header=None, dtype=str)
        df_coords.columns = ["pais", "universidad", "coords"]
        df_coords["universidad"] = df_coords["universidad"].str.strip()
        df_coords["coords"]      = df_coords["coords"].str.strip()
        coords_dict = {
            str(k).strip(): v
            for k, v in dict(zip(df_coords["universidad"], df_coords["coords"])).items()
        }
    except Exception:
        pass

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
    c_plan        = _pick(df, "Plan de estudios", "Plan estudios", "Plan_estudios",
                          "Enlace plan de estudios", "plan de es")

    # Construir columna estudiante
    if c_nombre or c_ap1 or c_ap2:
        parts = []
        if c_nombre: parts.append(df[c_nombre].astype(str))
        if c_ap1:    parts.append(df[c_ap1].astype(str))
        if c_ap2:    parts.append(df[c_ap2].fillna("").astype(str))
        s = parts[0]
        for p in parts[1:]:
            s = s + " " + p
        df["estudiante"] = s.str.replace(r"\s+", " ", regex=True).str.strip()
    elif c_email:
        df["estudiante"] = df[c_email].astype(str).str.split("@").str[0]
    else:
        df["estudiante"] = ""

    # Coordenadas directas
    if c_coords:
        lats, lons = zip(*df[c_coords].map(_parse_coords))
        df["latitud"]  = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"]  = pd.to_numeric(df[c_lat], errors="coerce") if c_lat else pd.NA
        df["longitud"] = pd.to_numeric(df[c_lon], errors="coerce") if c_lon else pd.NA

    # Campos normalizados
    df["universidad"] = df[c_destino].astype(str).str.strip() if c_destino else None
    df["ciudad"]      = df[c_ciudad] if c_ciudad else None
    df["pais"]        = "España"

    # Completar coordenadas faltantes por universidad
    if coords_dict:
        df["universidad"] = df["universidad"].astype(str).str.strip()
        df["_coords_lookup"] = df["universidad"].map(coords_dict)
        parsed = df["_coords_lookup"].map(_parse_coords)
        df["_lat_lu"] = [p[0] for p in parsed]
        df["_lon_lu"] = [p[1] for p in parsed]
        df["latitud"]  = df["latitud"].fillna(df["_lat_lu"])
        df["longitud"] = df["longitud"].fillna(df["_lon_lu"])
        df.drop(columns=["_coords_lookup", "_lat_lu", "_lon_lu"], inplace=True)

    # Mapeo de columnas específicas a nombres homogéneos
    mapping: dict[str, str] = {}
    if c_la:         mapping[c_la]         = "link_LA"
    if c_gestion:    mapping[c_gestion]    = "gestion_LA"
    if c_coord_dest: mapping[c_coord_dest] = "coordinador_destino"
    if c_dur:        mapping[c_dur]        = "duracion_meses"
    if c_email:      mapping[c_email]      = "email"
    if c_plan:       mapping[c_plan]       = "link_plan"

    def _to_records(g: pd.DataFrame) -> list[dict]:
        records = []
        for raw in g.to_dict("records"):
            record: dict = {}
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

    # Clustering y agrupado
    df = cluster_coordinates(df, max_distance_m=500)
    df["_lat_r"] = df["latitud"].round(2)
    df["_lon_r"] = df["longitud"].round(2)
    df = filter_students_with_coords(df, "SICUE OUT", _messages)

    if df.empty:
        if _messages is not None:
            _messages.append(
                "ℹ️ No hay alumnos de **SICUE OUT** con coordenadas válidas para mostrar en el mapa."
            )
        return pd.DataFrame(columns=EMPTY_DF_COLS)

    grouped = (
        df.groupby(["_lat_r", "_lon_r"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )

    if grouped.empty:
        if _messages is not None:
            _messages.append(
                "ℹ️ No hay grupos válidos de **SICUE OUT** para mostrar en el mapa."
            )
        return pd.DataFrame(columns=EMPTY_DF_COLS)

    grouped = _restore_location_info(grouped, df)
    grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")
    grouped["pais"] = "España"
    grouped = grouped[EMPTY_DF_COLS]

    del df
    gc.collect()

    return grouped
