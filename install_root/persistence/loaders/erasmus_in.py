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
import os
from dataclasses import dataclass

import pandas as pd

from ._common import (
    EMPTY_DF_COLS,
    _build_materias_index,
    _match_student_name,
    _norm_colname,
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
        coords_exact, coords_norm, country_exact, country_norm = self._load_coords_dict()

        df      = self._build_students_df(
            df_raw,
            cols,
            coords_exact,
            coords_norm,
            country_exact,
            country_norm,
        )
        grouped = self._cluster_and_group(df, cols)

        if grouped is None:
            return pd.DataFrame(columns=EMPTY_DF_COLS)

        return self._attach_materias(grouped)

    # ── Fase 1: lectura bruta ─────────────────────────────────────────────────

    # Columnas que identifican una hoja de datos de alumnos (al menos una debe estar presente)
    _STUDENT_COL_HINTS = {
        "nombre", "apellido1", "apellido2", "estudiante", "alumno",
        "email", "cuatrimestre", "cuatri", "cuat",
        "la", "universidad origen", "univ. origen", "universidadorigen",
        "universidad de origen", "universidad", "centro origen", "centro",
    }

    def _read_raw(self) -> pd.DataFrame:
        # Si se especificó hoja concreta, usarla directamente
        if self.sheet_name is not None:
            df = _read_table(self.path, sheet_name=self.sheet_name)
            df.columns = [str(c).strip() for c in df.columns]
            logger.debug("[IN] Columnas leídas (hoja '%s'): %s", self.sheet_name, list(df.columns))
            logger.debug("[IN] Total filas: %d", len(df))
            return df

        # Sin hoja especificada: buscar la primera hoja con cabeceras de alumnos
        ext = os.path.splitext(self.path)[1].lower()
        if ext in (".xlsx", ".xlsm", ".xltx", ".xltm", ".xls"):
            try:
                xl = pd.ExcelFile(self.path, engine="openpyxl")
                sheet_names = xl.sheet_names
            except Exception:
                sheet_names = []

            if sheet_names:
                for sname in sheet_names:
                    try:
                        candidate = pd.read_excel(
                            self.path, sheet_name=sname, nrows=3, engine="openpyxl"
                        )
                        candidate.columns = [str(c).strip() for c in candidate.columns]
                        norm_cols = {_norm_colname(c) for c in candidate.columns}
                        if norm_cols & self._STUDENT_COL_HINTS:
                            logger.debug("[IN] Hoja de alumnos detectada: '%s'", sname)
                            df = _read_table(self.path, sheet_name=sname)
                            df.columns = [str(c).strip() for c in df.columns]
                            logger.debug("[IN] Columnas leídas: %s", list(df.columns))
                            logger.debug("[IN] Total filas: %d", len(df))
                            return df
                    except Exception:
                        continue

        # Fallback: primera hoja
        df = _read_table(self.path, sheet_name=None)
        df.columns = [str(c).strip() for c in df.columns]
        logger.debug("[IN] Columnas leídas (fallback hoja 0): %s", list(df.columns))
        logger.debug("[IN] Total filas: %d", len(df))
        return df

    # ── Fase 2: detección de columnas ─────────────────────────────────────────

    def _detect_columns(self, df: pd.DataFrame) -> _ColMap:
        """Devuelve un _ColMap con el nombre real de cada columna en el Excel.

        Algunos Excels contienen varias tablas en la misma hoja (por ejemplo,
        una tabla principal de asignaturas × alumno y otra auxiliar con un
        resumen por alumno). Si se detectan sus columnas mezcladas, los datos
        acaban desalineados: un alumno aparece con coordenadas o universidad
        de otro. Para evitarlo se detecta el "ancla" de la tabla principal
        (Estudiante + Universidad Origen) y se restringe la búsqueda del
        resto de columnas al rango [0, fin de la tabla principal).
        """
        df_main = self._restrict_to_main_table(df)

        la  = _pick(df_main, "LA")
        lat = _pick(df_main, "Latitud", "latitud")
        lon = _pick(df_main, "Longitud", "longitud")

        cols = _ColMap(
            nombre      = _pick(df_main, "Nombre", "nombre"),
            ap1         = _pick(df_main, "Apellido1", "apellido1"),
            ap2         = _pick(df_main, "Apellido2", "apellido2"),
            estudiante  = _pick(df_main, "Estudiante", "estudiante", "Alumno", "alumno"),
            email       = _pick(df_main, "Email", "email"),
            cuatri      = _pick(df_main, "Cuatrimestre", "Cuatri", "Cuat"),
            la          = la,
            uni         = _pick(
                df_main,
                "Universidad Origen", "Univ. Origen", "UniversidadOrigen",
                "Universidad de Origen", "Universidad",
                "Centro Origen", "Centro de Origen", "Centro",
            ),
            ciudad      = _pick(df_main, "Ciudad", "Ciudad Origen", "Ciudad origen",
                                "City", "city", "ciudad"),
            pais        = _pick(df_main, "Origen", "País", "Pais"),
            coords      = _pick(df_main, "Coordenadas", "coords"),
            # "LA" nunca es latitud/longitud aunque su nombre coincida
            lat         = None if lat == la else lat,
            lon         = None if lon == la else lon,
        )

        # Si existen ambas "Estudiante" y "nombre" como columnas separadas,
        # "Estudiante" ya lleva el nombre completo — las partes "nombre/ap1/ap2"
        # suelen pertenecer a otra tabla auxiliar y estarían desalineadas.
        if cols.estudiante and cols.nombre and cols.nombre != cols.estudiante:
            cols.nombre = None
            cols.ap1 = None
            cols.ap2 = None

        # _pick puede caer en el fallback "contains" y confundir ciudad con
        # la columna de país (por ej. alias "Ciudad Origen" → "Origen").
        # Si ciudad y pais apuntan a la misma columna, no hay columna real
        # de ciudad en la tabla principal.
        if cols.ciudad and cols.ciudad == cols.pais:
            cols.ciudad = None

        logger.debug("[IN] Columnas detectadas: %s", cols)
        return cols

    def _restrict_to_main_table(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Devuelve el subconjunto de columnas que componen la tabla principal
        de alumnos. Si detecta una columna separadora (Unnamed, Contador,
        etc.) después del ancla (Estudiante/Universidad), corta ahí.
        Si no hay separadores, devuelve el df completo sin cambios.
        """
        est = _pick(df, "Estudiante", "estudiante", "Alumno", "alumno")
        uni = _pick(
            df,
            "Universidad Origen", "Univ. Origen", "UniversidadOrigen",
            "Universidad de Origen", "Universidad",
            "Centro Origen", "Centro de Origen", "Centro",
        )
        anchors = [c for c in (est, uni) if c is not None and c in df.columns]
        if not anchors:
            return df

        max_anchor_pos = max(df.columns.get_loc(c) for c in anchors)

        # Buscar la primera columna "separadora" después del ancla: columnas
        # sin nombre real (Unnamed) o columnas contenedoras de metainfo
        # ("Contador ...") indican el final de la tabla principal.
        end_idx = len(df.columns)
        for i in range(max_anchor_pos + 1, len(df.columns)):
            col = str(df.columns[i]).strip()
            col_low = col.lower()
            if (col.startswith("Unnamed")
                    or col_low.startswith("contador")
                    or col_low.startswith("n alumnos")
                    or col == "" or col_low == "nan"):
                end_idx = i
                break

        if end_idx < len(df.columns):
            logger.debug(
                "[IN] Tabla principal detectada: columnas [0, %d) — se ignora el resto",
                end_idx,
            )
            return df.iloc[:, :end_idx]
        return df

    # ── Fase 3: diccionario de coordenadas ────────────────────────────────────

    def _load_coords_dict(
        self,
    ) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
        """
        Lee la hoja 'Coordenadas':
          col A → país (ignorado aquí)
          col B → nombre de la universidad  (clave del diccionario)
          col C → coordenadas "lat, lon"    (valor)

                Devuelve cuatro dicts:
                    - coords exactas y normalizadas (universidad -> "lat,lon")
                    - países exactos y normalizados (universidad -> país)
        """
        exact: dict[str, str] = {}
        normd: dict[str, str] = {}
        country_exact: dict[str, str] = {}
        country_norm: dict[str, str] = {}
        try:
            df_c = pd.read_excel(
                self.path, sheet_name="Coordenadas", header=None, dtype=str
            )
            df_c.columns = [f"col{i}" for i in range(df_c.shape[1])]

            # Detectar cabecera: Erasmus IN → col0=País, col1=Universidad, col2=Coordenadas.
            # Si la primera fila contiene esas etiquetas, se detecta y se descarta.
            _HEADER_WORDS = {
                "universidad", "universidade", "university",
                "país", "pais", "country",
                "coordenadas", "coordenada", "coords", "coordinates",
            }
            col_pais_idx  = 0   # por defecto IN: col0=País
            col_uni_idx   = 1   # por defecto IN: col1=Universidad
            col_coord_idx = 2   # siempre col2=Coordenadas
            start_row     = 0

            first_row = [str(df_c.iloc[0].get(f"col{i}", "") or "").strip().lower()
                         for i in range(min(df_c.shape[1], 4))]
            if any(v in _HEADER_WORDS for v in first_row):
                for i, v in enumerate(first_row):
                    if v in {"país", "pais", "country"}:
                        col_pais_idx = i
                    if v in {"universidad", "universidade", "university"}:
                        col_uni_idx = i
                    if v in {"coordenadas", "coordenada", "coords", "coordinates"}:
                        col_coord_idx = i
                start_row = 1   # saltar fila de cabecera

            col_pais_key  = f"col{col_pais_idx}"
            col_uni_key   = f"col{col_uni_idx}"
            col_coord_key = f"col{col_coord_idx}"

            for idx, row in df_c.iterrows():
                if idx < start_row:
                    continue
                pais  = str(row.get(col_pais_key,  "") or "").strip()
                uni   = str(row.get(col_uni_key,   "") or "").strip()
                coord = str(row.get(col_coord_key, "") or "").strip()
                if uni and coord and coord.lower() not in ("nan", "none", ""):
                    exact[uni]             = coord
                    normd[_norm_name(uni)] = coord
                if uni and pais and pais.lower() not in ("nan", "none", ""):
                    country_exact[uni]             = pais
                    country_norm[_norm_name(uni)] = pais
            logger.debug("[IN] Coordenadas cargadas: %d universidades", len(exact))
        except Exception as exc:
            logger.debug("[IN] Hoja 'Coordenadas' no disponible: %s", exc)
        return exact, normd, country_exact, country_norm

    # ── Fase 4: construcción del DataFrame de alumnos ─────────────────────────

    def _build_students_df(
        self,
        df: pd.DataFrame,
        cols: _ColMap,
        coords_exact: dict[str, str],
        coords_norm:  dict[str, str],
        country_exact: dict[str, str],
        country_norm: dict[str, str],
    ) -> pd.DataFrame:
        df = df.copy()
        df["estudiante"]   = self._build_nombre(df, cols)
        df["latitud"], \
        df["longitud"]     = self._resolve_coords(df, cols, coords_exact, coords_norm)
        df["universidad"]  = df[cols.uni].astype(str).str.strip()  if cols.uni    else None
        df["pais"]         = df[cols.pais].astype(str).str.strip() if cols.pais   else None

        # Erasmus IN: país correcto por alumno según su universidad en la hoja
        # "Coordenadas" (fuente de verdad), evitando arrastres por agrupación.
        if cols.uni and (country_exact or country_norm):
            def _lookup_country(name: str) -> str:
                return country_exact.get(name) or country_norm.get(_norm_name(name)) or ""

            uni_series = df[cols.uni].astype(str).str.strip()
            mapped_country = uni_series.map(_lookup_country).astype(str).str.strip()
            mapped_ok = ~mapped_country.str.lower().isin({"", "nan", "none", "0"})

            if "pais" not in df.columns or df["pais"] is None:
                df["pais"] = mapped_country.where(mapped_ok, "")
            else:
                df["pais"] = df["pais"].astype(str).str.strip()
                # Si existe país mapeado por universidad, tiene prioridad.
                df.loc[mapped_ok, "pais"] = mapped_country[mapped_ok]

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

        # Paso 2 — resolver por nombre de universidad
        if (exact or normd) and cols.uni:
            def _lookup(name: str) -> str | None:
                return exact.get(name) or normd.get(_norm_name(name))

            lu_raw   = df[cols.uni].astype(str).str.strip().map(_lookup)
            lu_pairs = lu_raw.map(_parse_coords)
            lu_lat   = pd.Series([p[0] for p in lu_pairs], index=df.index, dtype=float)
            lu_lon   = pd.Series([p[1] for p in lu_pairs], index=df.index, dtype=float)
            # Erasmus IN: priorizar coordenadas de la hoja "Coordenadas" por
            # universidad. Si no hay match, usar coordenadas directas de la fila.
            lat      = lu_lat.fillna(lat)
            lon      = lu_lon.fillna(lon)

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
        # Erasmus IN: no unir puntos por proximidad. Si se usan umbrales altos
        # (ej. 500m) o redondeos bajos, alumnos de universidades distintas pueden
        # acabar en el mismo marcador con coordenada promedio.
        df = cluster_coordinates(df, max_distance_m=0)
        # Mantener precisión alta para agrupar solo coordenadas prácticamente
        # idénticas (evita mezclar ubicaciones cercanas pero distintas).
        df["_lat_r"] = df["latitud"].round(6)
        df["_lon_r"] = df["longitud"].round(6)
        df = filter_students_with_coords(df, "Erasmus IN", self.messages)

        # En algunos Excels hay filas auxiliares o repetidas con estudiante vacío
        # (por ejemplo, por celdas fusionadas). Si no se filtran aquí, pueden
        # contaminar la etiqueta de universidad del cluster aunque no aparezcan
        # como alumnos en el popup.
        if "estudiante" in df.columns:
            est = df["estudiante"].astype(str).str.strip().str.lower()
            df = df[~est.isin({"", "nan", "none", "0"})].copy()

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
        def _student_key(raw):
            email = str(raw.get("email") or "").strip().lower()
            if email and email not in {"nan", "none"}:
                return email
            nombre = _norm_name(str(raw.get("estudiante") or ""))
            uni = _norm_name(str(raw.get(cols.uni) or ""))
            pais = _norm_name(str(raw.get(cols.pais) or ""))
            return f"{nombre}|{uni}|{pais}"
        
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
                            field_key = ("email"
                                        if col == cols.email and cols.email != "email"
                                        else col)
                            rec[field_key] = raw[col]
                    if cols.ciudad and cols.ciudad in raw:
                        rec["ciudad"] = raw[cols.ciudad]
                    if cols.uni and cols.uni in raw:
                        rec["universidad de origen"] = raw[cols.uni]
                    if cols.pais and cols.pais in raw:
                        rec["pais"] = raw[cols.pais]
                    seen[nombre] = rec
                    records.append(rec)
                else:
                    # El mismo alumno puede tener varias filas (una por asignatura).
                    # Rellenamos campos que estuvieran vacíos en la primera fila,
                    # incluidos los de ubicación para evitar mezclar universidades.
                    rec = seen[nombre]
                    for col in valid_cols:
                        if col not in raw:
                            continue
                        field_key = ("email"
                                    if col == cols.email and cols.email != "email"
                                    else col)
                        if _is_empty(rec.get(field_key)) and not _is_empty(raw[col]):
                            rec[field_key] = raw[col]

                    if cols.ciudad and cols.ciudad in raw:
                        if _is_empty(rec.get("ciudad")) and not _is_empty(raw[cols.ciudad]):
                            rec["ciudad"] = raw[cols.ciudad]

                    if cols.uni and cols.uni in raw:
                        if _is_empty(rec.get("universidad de origen")) and not _is_empty(raw[cols.uni]):
                            rec["universidad de origen"] = raw[cols.uni]

                    if cols.pais and cols.pais in raw:
                        if _is_empty(rec.get("pais")) and not _is_empty(raw[cols.pais]):
                            rec["pais"] = raw[cols.pais]

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
