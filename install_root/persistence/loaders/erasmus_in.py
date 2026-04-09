"""
Loader para Erasmus IN.

Pipeline de carga (clase ErasmusInLoader):
  1. _read_raw()           → lee el DataFrame bruto del Excel
  2. _detect_columns()     → mapea nombres reales de columnas (_ColMap)
  3. _load_coords_dict()   → lee la hoja "Coordenadas" (col A=país, B=universidad, C=coords)
  4. _build_students_df()  → construye las columnas normalizadas (estudiante, latitud, ...)
  5. _cluster_and_group()  → clustering espacial + groupby por ubicación
  6. _attach_materias()    → une asignaturas a cada alumno

API pública (compatible con all_dataframes.py sin cambios):
    load_erasmus_in(path, sheet_name, _messages) -> pd.DataFrame
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass

import pandas as pd

from ._common import (
    EMPTY_DF_COLS,
    _build_materias_index,
    _match_student_name,
    _norm_name,
    _parse_coords,
    _pick,
    _read_table,
    _restore_location_info,
    cluster_coordinates,
    filter_students_with_coords,
)

logger = logging.getLogger("movilidad_persistence")


# ──────────────────────────────────────────────────────────────────────────────
# Mapa de columnas detectadas
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class _ColMap:
    """Nombres reales de cada columna detectada en el Excel de Erasmus IN.

    Cada atributo es el nombre literal de la columna en el DataFrame leído,
    o None si esa columna no existe en el archivo.
    """
    nombre:      str | None = None   # nombre de pila
    ap1:         str | None = None   # primer apellido
    ap2:         str | None = None   # segundo apellido
    estudiante:  str | None = None   # columna de nombre completo
    email:       str | None = None
    cuatri:      str | None = None
    la:          str | None = None   # Learning Agreement
    uni:         str | None = None   # universidad de origen
    ciudad:      str | None = None
    pais:        str | None = None
    coords:      str | None = None   # columna con "lat, lon" en texto
    lat:         str | None = None   # columna latitud numérica
    lon:         str | None = None   # columna longitud numérica


# ──────────────────────────────────────────────────────────────────────────────
# Loader principal
# ──────────────────────────────────────────────────────────────────────────────

class ErasmusInLoader:
    """
    Encapsula toda la lógica de lectura de un Excel de Erasmus IN.

    Uso:
        df = ErasmusInLoader(path, sheet_name, messages).load()
    """

    def __init__(
        self,
        path: str,
        sheet_name: str | None = None,
        messages: list | None = None,
    ) -> None:
        self.path = path
        self.sheet_name = sheet_name
        self.messages: list[str] = messages if messages is not None else []

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def load(self) -> pd.DataFrame:
        """Ejecuta el pipeline completo y devuelve el DataFrame agrupado."""
        df_raw = self._read_raw()
        cols   = self._detect_columns(df_raw)
        coords_exact, coords_norm = self._load_coords_dict()

        df      = self._build_students_df(df_raw, cols, coords_exact, coords_norm)
        grouped = self._cluster_and_group(df, cols)

        if grouped is None:
            return pd.DataFrame(columns=EMPTY_DF_COLS)

        return self._attach_materias(grouped)

    # ── Fase 1: lectura bruta ─────────────────────────────────────────────────

    def _read_raw(self) -> pd.DataFrame:
        df = _read_table(self.path, sheet_name=self.sheet_name)
        df.columns = [str(c).strip() for c in df.columns]
        logger.debug("[IN] Columnas leídas: %s", list(df.columns))
        logger.debug("[IN] Total filas: %d", len(df))
        return df

    # ── Fase 2: detección de columnas ─────────────────────────────────────────

    def _detect_columns(self, df: pd.DataFrame) -> _ColMap:
        """Devuelve un _ColMap con el nombre real de cada columna en el Excel."""
        la  = _pick(df, "LA")
        lat = _pick(df, "Latitud", "latitud")
        lon = _pick(df, "Longitud", "longitud")

        cols = _ColMap(
            nombre      = _pick(df, "Nombre", "nombre"),
            ap1         = _pick(df, "Apellido1", "apellido1"),
            ap2         = _pick(df, "Apellido2", "apellido2"),
            estudiante  = _pick(df, "Estudiante", "estudiante", "Alumno", "alumno"),
            email       = _pick(df, "Email", "email"),
            cuatri      = _pick(df, "Cuatrimestre", "Cuatri", "Cuat"),
            la          = la,
            uni         = _pick(
                df,
                "Universidad Origen", "Univ. Origen", "UniversidadOrigen",
                "Universidad de Origen", "Universidad",
                "Centro Origen", "Centro de Origen", "Centro",
            ),
            ciudad      = _pick(df, "Ciudad", "Ciudad Origen", "Ciudad origen",
                                "City", "city", "ciudad"),
            pais        = _pick(df, "País", "Pais", "Origen"),
            coords      = _pick(df, "Coordenadas", "coords"),
            # "LA" nunca es latitud/longitud aunque su nombre coincida
            lat         = None if lat == la else lat,
            lon         = None if lon == la else lon,
        )
        logger.debug("[IN] Columnas detectadas: %s", cols)
        return cols

    # ── Fase 3: diccionario de coordenadas ────────────────────────────────────

    def _load_coords_dict(self) -> tuple[dict[str, str], dict[str, str]]:
        """
        Lee la hoja 'Coordenadas':
          col A → país (ignorado aquí)
          col B → nombre de la universidad  (clave del diccionario)
          col C → coordenadas "lat, lon"    (valor)

        Devuelve dos dicts: uno con clave exacta y otro con clave normalizada
        (sin acentos, minúsculas) para tolerar diferencias de escritura.
        """
        exact: dict[str, str] = {}
        normd: dict[str, str] = {}
        try:
            df_c = pd.read_excel(
                self.path, sheet_name="Coordenadas", header=None, dtype=str
            )
            df_c.columns = [f"col{i}" for i in range(df_c.shape[1])]
            for _, row in df_c.iterrows():
                uni   = str(row.get("col1", "") or "").strip()   # columna B
                coord = str(row.get("col2", "") or "").strip()   # columna C
                if uni and coord and coord.lower() not in ("nan", "none", ""):
                    exact[uni]              = coord
                    normd[_norm_name(uni)]  = coord
            logger.debug("[IN] Coordenadas cargadas: %d universidades", len(exact))
        except Exception as exc:
            logger.debug("[IN] Hoja 'Coordenadas' no disponible: %s", exc)
        return exact, normd

    # ── Fase 4: construcción del DataFrame de alumnos ─────────────────────────

    def _build_students_df(
        self,
        df: pd.DataFrame,
        cols: _ColMap,
        coords_exact: dict[str, str],
        coords_norm:  dict[str, str],
    ) -> pd.DataFrame:
        df = df.copy()
        df["estudiante"]   = self._build_nombre(df, cols)
        df["latitud"], \
        df["longitud"]     = self._resolve_coords(df, cols, coords_exact, coords_norm)
        df["universidad"]  = df[cols.uni].astype(str).str.strip()  if cols.uni    else None
        df["pais"]         = df[cols.pais].astype(str).str.strip() if cols.pais   else None
        df["ciudad"]       = df[cols.ciudad]                        if cols.ciudad else None
        df["link_LA"]      = df[cols.la]                            if cols.la     else None
        df["cuatrimestre"] = df[cols.cuatri]                        if cols.cuatri else None
        logger.debug(
            "[IN] Filas con coordenadas: %d / %d",
            df["latitud"].notna().sum(), len(df),
        )
        return df

    def _build_nombre(self, df: pd.DataFrame, cols: _ColMap) -> pd.Series:
        """Construye la columna 'estudiante' uniendo nombre + apellidos si existen."""
        if cols.nombre or cols.ap1 or cols.ap2:
            parts = []
            if cols.nombre: parts.append(df[cols.nombre].astype(str))
            if cols.ap1:    parts.append(df[cols.ap1].astype(str))
            if cols.ap2:    parts.append(df[cols.ap2].fillna("").astype(str))
            joined = parts[0]
            for p in parts[1:]:
                joined = joined + " " + p
            return joined.str.replace(r"\s+", " ", regex=True).str.strip()
        if cols.estudiante:
            return df[cols.estudiante].astype(str).str.strip()
        if cols.email:
            return df[cols.email].astype(str).str.split("@").str[0]
        return pd.Series("", index=df.index)

    def _resolve_coords(
        self,
        df: pd.DataFrame,
        cols: _ColMap,
        exact: dict[str, str],
        normd: dict[str, str],
    ) -> tuple[pd.Series, pd.Series]:
        """
        Resuelve latitud/longitud por alumno en dos pasos:
          1. Columna directa de coordenadas (o columnas Latitud/Longitud separadas).
          2. Rellena los NaN buscando el nombre de universidad en el dict de coordenadas
             (primero coincidencia exacta, luego normalizada sin acentos).
        """
        # Paso 1 — coordenadas directas en el Excel principal
        if cols.coords:
            pairs = df[cols.coords].map(_parse_coords)
            lat = pd.Series([p[0] for p in pairs], index=df.index, dtype=float)
            lon = pd.Series([p[1] for p in pairs], index=df.index, dtype=float)
        else:
            lat = (pd.to_numeric(df[cols.lat], errors="coerce")
                   if cols.lat else pd.Series(dtype=float, index=df.index))
            lon = (pd.to_numeric(df[cols.lon], errors="coerce")
                   if cols.lon else pd.Series(dtype=float, index=df.index))

        # Paso 2 — rellenar por nombre de universidad
        if (exact or normd) and cols.uni:
            def _lookup(name: str) -> str | None:
                return exact.get(name) or normd.get(_norm_name(name))

            lu_raw   = df[cols.uni].astype(str).str.strip().map(_lookup)
            lu_pairs = lu_raw.map(_parse_coords)
            lu_lat   = pd.Series([p[0] for p in lu_pairs], index=df.index, dtype=float)
            lu_lon   = pd.Series([p[1] for p in lu_pairs], index=df.index, dtype=float)
            lat      = lat.fillna(lu_lat)
            lon      = lon.fillna(lu_lon)

        return lat, lon

    # ── Fase 5: clustering espacial y agrupación por ubicación ───────────────

    def _cluster_and_group(
        self, df: pd.DataFrame, cols: _ColMap
    ) -> pd.DataFrame | None:
        """
        Agrupa alumnos por ubicación geográfica.
        Devuelve un DataFrame con una fila por cluster y columna 'estudiantes'
        (lista de dicts), o None si no hay alumnos con coordenadas válidas.
        """
        df = cluster_coordinates(df, max_distance_m=500)
        df["_lat_r"] = df["latitud"].round(2)
        df["_lon_r"] = df["longitud"].round(2)
        df = filter_students_with_coords(df, "Erasmus IN", self.messages)

        if df.empty:
            self.messages.append(
                "ℹ️ No hay alumnos de **Erasmus IN** con coordenadas válidas "
                "para mostrar en el mapa."
            )
            return None

        grouped = (
            df.groupby(["_lat_r", "_lon_r"], dropna=False)
              .apply(self._make_records_fn(cols), include_groups=False)
              .reset_index(name="estudiantes")
        )

        if grouped.empty:
            self.messages.append(
                "ℹ️ No hay grupos válidos de **Erasmus IN** para mostrar en el mapa."
            )
            return None

        grouped = _restore_location_info(grouped, df)
        grouped = grouped.drop(columns=["_lat_r", "_lon_r"], errors="ignore")
        gc.collect()
        return grouped

    def _make_records_fn(self, cols: _ColMap):
        """
        Devuelve la función que convierte un grupo (mismo cluster geográfico)
        en una lista de dicts de alumno, deduplicando por nombre y rellenando
        campos vacíos si el mismo alumno aparece en varias filas.
        """
        def _is_empty(v) -> bool:
            return v is None or str(v).strip().lower() in ("", "nan", "none")

        def _build_records(g: pd.DataFrame) -> list[dict]:
            seen: dict[str, dict] = {}
            records: list[dict] = []

            # Columnas que se copian directamente al dict del alumno
            base_cols = ["estudiante", "cuatrimestre", "link_LA"]
            if cols.email:
                base_cols.insert(1, cols.email)
            valid_cols = [c for c in base_cols if c in g.columns]

            for raw in g.to_dict("records"):
                nombre = raw.get("estudiante") or ""
                if not nombre:
                    continue

                if nombre not in seen:
                    rec: dict = {}
                    for col in valid_cols:
                        if col in raw:
                            key = ("email"
                                   if col == cols.email and cols.email != "email"
                                   else col)
                            rec[key] = raw[col]
                    if cols.ciudad and cols.ciudad in raw:
                        rec["ciudad"] = raw[cols.ciudad]
                    if cols.uni and cols.uni in raw:
                        rec["universidad de origen"] = raw[cols.uni]
                    seen[nombre] = rec
                    records.append(rec)
                else:
                    # El mismo alumno puede tener varias filas (una por asignatura).
                    # Rellenamos campos que estuvieran vacíos en la primera fila.
                    rec = seen[nombre]
                    for col in valid_cols:
                        if col not in raw:
                            continue
                        key = ("email"
                               if col == cols.email and cols.email != "email"
                               else col)
                        if _is_empty(rec.get(key)) and not _is_empty(raw[col]):
                            rec[key] = raw[col]

            return records

        return _build_records

    # ── Fase 6: asignaturas ───────────────────────────────────────────────────

    def _attach_materias(self, grouped: pd.DataFrame) -> pd.DataFrame:
        """
        Une las asignaturas de cada alumno al dict del alumno.
        Usa matching flexible (exacto → por apellido) si el nombre no coincide
        literalmente con la clave del dict de materias.
        """
        from persistence.materias_in_loader import get_materias_in_por_estudiante

        materias_dict = get_materias_in_por_estudiante({"Erasmus IN": self.path})

        if not materias_dict:
            logger.warning(
                "[IN] ✗ materias_dict vacío — los alumnos no tendrán asignaturas. "
                "Revisa los logs [MATERIAS-IN] para ver por qué no se detectó la tabla."
            )
            for grupo in grouped["estudiantes"]:
                for alumno in grupo:
                    alumno["materias"] = []
            return grouped

        logger.warning(
            "[IN] ✓ materias_dict cargado: %d alumnos | muestra claves: %s",
            len(materias_dict),
            list(materias_dict.keys())[:5],
        )
        exact_idx, last_idx = _build_materias_index(materias_dict)

        sin_match: list[str] = []
        for grupo in grouped["estudiantes"]:
            for alumno in grupo:
                nombre   = alumno.get("estudiante") or ""
                materias = materias_dict.get(nombre)
                if not materias:
                    clave = _match_student_name(nombre, exact_idx, last_idx)
                    if clave:
                        logger.debug("[IN] Match nombre: '%s' → '%s'", nombre, clave)
                        materias = materias_dict.get(clave, [])
                    else:
                        sin_match.append(nombre)
                alumno["materias"] = materias or []

        if sin_match:
            logger.warning(
                "[IN] ✗ Sin asignaturas para %d alumnos: %s",
                len(sin_match), sin_match[:10],
            )

        return grouped


# ──────────────────────────────────────────────────────────────────────────────
# API pública — compatible con all_dataframes.py sin cambios
# ──────────────────────────────────────────────────────────────────────────────

def load_erasmus_in(
    path: str,
    sheet_name: str | None = None,
    _messages: list | None = None,
) -> pd.DataFrame:
    """
    Carga Erasmus IN y agrupa por coordenadas.
    Devuelve DF con columnas: ['universidad','pais','ciudad','latitud','longitud','estudiantes'].
    """
    return ErasmusInLoader(path, sheet_name, _messages).load()
