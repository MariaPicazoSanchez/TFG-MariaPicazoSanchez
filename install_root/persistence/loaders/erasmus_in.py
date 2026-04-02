"""
Loader para Erasmus IN.
"""

from __future__ import annotations

import gc
import logging

import pandas as pd

from ._common import (
    _pick, _parse_coords, _read_table,
    _build_materias_index, _match_student_name,
    cluster_coordinates, filter_students_with_coords,
    _restore_location_info, EMPTY_DF_COLS,
)

logger = logging.getLogger("movilidad_persistence")


def load_erasmus_in(
    path: str,
    sheet_name: str | None = None,
    _messages: list | None = None,
) -> pd.DataFrame:
    """
    Carga Erasmus IN y agrupa por coordenadas.
    Devuelve DF con columnas: ['universidad','pais','ciudad','latitud','longitud','estudiantes'].
    """
    from persistence.materias_in_loader import get_materias_in_por_estudiante

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
    c_lat        = _pick(df, "Latitud", "latitud")
    c_lon        = _pick(df, "Longitud", "longitud")
    # Evitar que "LA" sea detectado como latitud/longitud
    if c_lat == c_la:
        c_lat = None
    if c_lon == c_la:
        c_lon = None

    logger.debug(
        "[IN] Columnas detectadas: nombre=%s, estudiante=%s, ap1=%s, ap2=%s, uni=%s, "
        "pais=%s, coords=%s, lat=%s, lon=%s, cuatri=%s, la=%s",
        c_nombre, c_estudiante, c_ap1, c_ap2, c_uni,
        c_pais, c_coords, c_lat, c_lon, c_cuatri, c_la,
    )

    # Cargar coordenadas desde hoja "Coordenadas"
    coords_dict: dict[str, str] = {}
    try:
        df_coords = pd.read_excel(path, sheet_name="Coordenadas", header=None, dtype=str)
        df_coords.columns = [f"col{i}" for i in range(df_coords.shape[1])]
        for _, row in df_coords.iterrows():
            uni = str(row.get("col1", "") or "").strip()
            coords_raw = str(row.get("col2", "") or "").strip()
            if uni and coords_raw and coords_raw.lower() not in ("nan", "none", ""):
                coords_dict[uni] = coords_raw
        logger.debug("[IN] Coordenadas desde hoja 'Coordenadas': %d universidades", len(coords_dict))
    except Exception as e:
        logger.debug("[IN] No se pudo leer hoja 'Coordenadas': %s", e)

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
    elif c_estudiante:
        df["estudiante"] = df[c_estudiante].astype(str).str.strip()
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

    # Completar coordenadas faltantes por universidad
    if coords_dict and c_uni:
        uni_col = df[c_uni].astype(str).str.strip()
        df["_coords_lookup"] = uni_col.map(coords_dict)
        parsed = df["_coords_lookup"].map(_parse_coords)
        df["_lat_lu"] = [p[0] for p in parsed]
        df["_lon_lu"] = [p[1] for p in parsed]
        df["latitud"]  = pd.to_numeric(df["latitud"],  errors="coerce").fillna(
            pd.to_numeric(df["_lat_lu"], errors="coerce"))
        df["longitud"] = pd.to_numeric(df["longitud"], errors="coerce").fillna(
            pd.to_numeric(df["_lon_lu"], errors="coerce"))
        df.drop(columns=["_coords_lookup", "_lat_lu", "_lon_lu"], inplace=True)
        logger.debug(
            "[IN] Coords tras lookup: %d / %d filas con coords",
            df["latitud"].notna().sum(), len(df),
        )

    # Campos normalizados
    df["universidad"]  = df[c_uni].astype(str).str.strip() if c_uni   else None
    df["pais"]         = df[c_pais].astype(str).str.strip() if c_pais else None
    df["ciudad"]       = df[c_ciudad]  if c_ciudad  else None
    df["link_LA"]      = df[c_la]      if c_la      else None
    df["cuatrimestre"] = df[c_cuatri]  if c_cuatri  else None

    logger.debug("[IN] Muestra estudiantes: %s", df["estudiante"].head().tolist())
    logger.debug("[IN] Filas con coords: %d / %d", df["latitud"].notna().sum(), len(df))

    # Función local para construir registros por cluster (con deduplicación)
    def _to_records(g: pd.DataFrame) -> list[dict]:
        """
        Deduplicar por estudiante: si la primera fila tiene campos vacíos
        (ej. cuatrimestre), se rellenan con valores de filas posteriores.
        """
        seen: dict = {}
        records: list = []
        cols = ["estudiante", "cuatrimestre", "link_LA"]
        if c_email:
            cols.insert(1, c_email)
        cols = [c for c in cols if c in g.columns]

        def _is_empty(v) -> bool:
            return v is None or str(v).strip().lower() in ("", "nan", "none")

        for raw in g.to_dict("records"):
            est = raw.get("estudiante") or ""
            if not est:
                continue
            if est not in seen:
                record: dict = {}
                for col in cols:
                    if col in raw:
                        key = "email" if (col == c_email and c_email != "email") else col
                        record[key] = raw[col]
                if c_ciudad and c_ciudad in raw:
                    record["ciudad"] = raw[c_ciudad]
                if c_uni and c_uni in raw:
                    record["universidad de origen"] = raw[c_uni]
                seen[est] = record
                records.append(record)
            else:
                # Rellenar campos nulos con datos de filas posteriores
                record = seen[est]
                for col in cols:
                    if col not in raw:
                        continue
                    key = "email" if (col == c_email and c_email != "email") else col
                    if _is_empty(record.get(key)) and not _is_empty(raw[col]):
                        record[key] = raw[col]
        return records

    # Clustering y agrupado
    df = cluster_coordinates(df, max_distance_m=500)
    df["_lat_r"] = df["latitud"].round(2)
    df["_lon_r"] = df["longitud"].round(2)
    df = filter_students_with_coords(df, "Erasmus IN", _messages)
    logger.debug("[IN] Tras filtrar coords: %d filas", len(df))

    if df.empty:
        if _messages is not None:
            _messages.append(
                "ℹ️ No hay alumnos de **Erasmus IN** con coordenadas válidas para mostrar en el mapa."
            )
        return pd.DataFrame(columns=EMPTY_DF_COLS)

    grouped = (
        df.groupby(["_lat_r", "_lon_r"], dropna=False)
          .apply(_to_records, include_groups=False)
          .reset_index(name="estudiantes")
    )
    logger.debug("[IN] Grupos tras groupby: %d", len(grouped))

    if grouped.empty:
        if _messages is not None:
            _messages.append(
                "ℹ️ No hay grupos válidos de **Erasmus IN** para mostrar en el mapa."
            )
        return pd.DataFrame(columns=EMPTY_DF_COLS)

    grouped = _restore_location_info(grouped, df)
    grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")

    del df
    gc.collect()

    # Asociar materias con matching flexible de nombres
    config = {"Erasmus IN": path}
    materias_dict = get_materias_in_por_estudiante(config)

    if materias_dict:
        logger.debug("[IN] Alumnos en materias_dict: %s", list(materias_dict.keys())[:10])
        exact_idx, last_idx = _build_materias_index(materias_dict)
        for grupo in grouped["estudiantes"]:
            for alumno in grupo:
                nombre = alumno.get("estudiante") or ""
                materias = materias_dict.get(nombre)
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
