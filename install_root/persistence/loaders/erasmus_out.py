"""
Loader para Erasmus OUT.
"""


import gc

import pandas as pd

from ._common import (
    _pick, _parse_coords, _read_table,
    cluster_coordinates, filter_students_with_coords,
    _restore_location_info, EMPTY_DF_COLS,
)


def load_erasmus_out(
    path: str,
    sheet_name: str | None = None,
    _messages: list | None = None,
) -> pd.DataFrame:
    """
    Carga Erasmus OUT y agrupa por coordenadas.
    Devuelve DF con columnas: ['universidad','pais','ciudad','latitud','longitud','estudiantes'].
    """
    df = _read_table(path, sheet_name=sheet_name)
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

    # Cargar coordenadas desde hoja "Coordenadas"
    # Formato Erasmus OUT: col0=Universidad, col1=País, col2=Coordenadas[, col3=Responsable]
    # Si la primera fila contiene etiquetas de cabecera, se detecta y se descarta.
    coords_dict: dict[str, str] = {}
    try:
        df_coords = pd.read_excel(path, sheet_name="Coordenadas", header=None, dtype=str)
        df_coords.columns = [f"col{i}" for i in range(df_coords.shape[1])]

        # Detectar cabecera: si la primera celda contiene "universidad" o "país"
        _HEADER_WORDS = {"universidad", "universidade", "university", "país", "pais", "country"}
        col_uni_idx = 0    # por defecto OUT: col0=Universidad
        col_coord_idx = 2  # siempre col2=Coordenadas
        start_row = 0

        first_row = [str(df_coords.iloc[0].get(f"col{i}", "") or "").strip().lower()
                     for i in range(min(df_coords.shape[1], 4))]
        if any(v in _HEADER_WORDS for v in first_row):
            # Detectar qué columna es "universidad"
            for i, v in enumerate(first_row):
                if v in {"universidad", "universidade", "university"}:
                    col_uni_idx = i
                    break
            start_row = 1  # saltar fila de cabecera

        col_uni_key   = f"col{col_uni_idx}"
        col_coord_key = f"col{col_coord_idx}"

        for idx, row in df_coords.iterrows():
            if idx < start_row:
                continue
            uni        = str(row.get(col_uni_key,   "") or "").strip()
            coords_raw = str(row.get(col_coord_key, "") or "").strip()
            if uni and coords_raw and coords_raw.lower() not in ("nan", "none", ""):
                coords_dict[uni] = coords_raw
    except Exception:
        pass

    # Coordenadas directas
    if c_coords:
        lats, lons = zip(*df[c_coords].map(_parse_coords))
        df["latitud"]  = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"]  = pd.to_numeric(df[c_lat], errors="coerce") if c_lat else pd.NA
        df["longitud"] = pd.to_numeric(df[c_lon], errors="coerce") if c_lon else pd.NA

    # Campos normalizados
    df["universidad"] = df[c_dest]  if c_dest  else None
    df["pais"]        = df[c_pais].str.upper() if c_pais else None
    df["ciudad"]      = df[c_ciudad] if c_ciudad else None
    df["link_LA"]     = df[c_la]    if c_la    else None
    df["link_plan"]   = df[c_plan]  if c_plan  else None

    # Completar coordenadas faltantes por universidad
    if coords_dict and c_dest:
        uni_col = df["universidad"].astype(str).str.strip()
        df["_coords_lookup"] = uni_col.map(coords_dict)
        parsed = df["_coords_lookup"].map(_parse_coords)
        df["_lat_lu"] = [p[0] for p in parsed]
        df["_lon_lu"] = [p[1] for p in parsed]
        df["latitud"]  = pd.to_numeric(df["latitud"],  errors="coerce").fillna(
            pd.to_numeric(df["_lat_lu"], errors="coerce"))
        df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce").fillna(
            pd.to_numeric(df["_lon_lu"], errors="coerce"))
        df.drop(columns=["_coords_lookup", "_lat_lu", "_lon_lu"], inplace=True)

    # Función local para construir registros por cluster
    def _to_records(g: pd.DataFrame) -> list[dict]:
        mapping: dict[str, str] = {}
        if c_email:    mapping[c_email]    = "email"
        if c_curso:    mapping[c_curso]    = "curso"
        if c_duracion: mapping[c_duracion] = "duracion_meses"
        if c_resp:     mapping[c_resp]     = "responsable"

        keep = ["estudiante"]
        if "link_LA"   in g.columns: keep.append("link_LA")
        if "link_plan" in g.columns: keep.append("link_plan")

        records = []
        for raw in g.to_dict("records"):
            record: dict = {}
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

    # Clustering y agrupado
    df = cluster_coordinates(df, max_distance_m=500)
    df["_lat_r"] = df["latitud"].round(2)
    df["_lon_r"] = df["longitud"].round(2)
    df = filter_students_with_coords(df, "Erasmus OUT", _messages)

    if df.empty:
        if _messages is not None:
            _messages.append(
                "ℹ️ No hay alumnos de **Erasmus OUT** con coordenadas válidas para mostrar en el mapa."
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
                "ℹ️ No hay grupos válidos de **Erasmus OUT** para mostrar en el mapa."
            )
        return pd.DataFrame(columns=EMPTY_DF_COLS)

    grouped = _restore_location_info(grouped, df)
    grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")

    del df
    gc.collect()

    return grouped
