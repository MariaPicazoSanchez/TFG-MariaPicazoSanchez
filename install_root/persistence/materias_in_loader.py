import logging
import os
import unicodedata
import pandas as pd

logger = logging.getLogger("movilidad_persistence")


def _norm(s):
    """Normaliza texto: minúsculas, sin acentos, sin espacios."""
    if pd.isna(s):
        return ""
    s = str(s).strip().lower()
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    s = s.replace(" ", "")
    return s


# Alias de cabeceras (puedes ampliar si tus excels reales usan variantes)
HEADER_ALIASES = {
    "asignatura": {"asignatura"},
    "estudiante": {"estudiante", "estudiantes", "alumno", "alumnos"},
    "origen": {"origen"},
    "universidadorigen": {
        "universidadorigen",
        "universidaddeorigen",
        "univorigen",
        "univ.deorigen"
    },
    "cuat": {"cuat", "cuatrimestre", "cuatri"},
    "firmado": {"firmado", "firma"},
    "la": {"la", "learningagreement", "acuerdoaprendizaje"},
}

# Columnas que deben existir para considerar que una tabla es "Materias IN"
# (ajústalo si quieres ser más estricto)
REQUIRED_KEYS = {"asignatura", "estudiante"}


def _match_header_row(row_values):
    """
    Intenta mapear una fila como cabecera de Materias IN.
    Devuelve dict {clave_canonica: indice_columna} o None.
    """
    found = {}
    normalized_cells = [_norm(v) for v in row_values]

    for idx, cell in enumerate(normalized_cells):
        if not cell:
            continue
        for canon_key, aliases in HEADER_ALIASES.items():
            if cell in aliases and canon_key not in found:
                found[canon_key] = idx

    # Mínimo imprescindible
    if not REQUIRED_KEYS.issubset(found.keys()):
        return None

    # Opcional: filtro adicional para reducir falsos positivos
    # Exigir que además aparezcan al menos 2 de estas 4:
    extras = {"origen", "universidadorigen", "cuat", "firmado"}
    if len(extras.intersection(found.keys())) < 2:
        return None

    return found


def _is_separator_or_empty_row(row_values):
    """True si la fila está vacía (o casi vacía)."""
    vals = [_norm(v) for v in row_values]
    return all(v == "" for v in vals)


def load_materias_in(config):
    """
    Lee el Excel de 'Erasmus IN' y extrae SOLO las tablas que tengan la cabecera
    de materias IN aunque haya otras tablas en el mismo archivo (y en distintas hojas).
    """
    ruta = config.get("Erasmus IN")
    if not ruta or not os.path.exists(ruta):
        return pd.DataFrame()

    try:
        # Leer TODAS las hojas
        # dtype=str para evitar mezclas raras de tipos
        xls = pd.read_excel(ruta, sheet_name=None, header=None, dtype=str)

        bloques = []

        logger.debug("[DEBUG] Buscando tablas Materias IN en todas las hojas...")

        for sheet_name, df_raw in xls.items():
            logger.debug("[DEBUG] Revisando hoja: %s", sheet_name)
            if df_raw is None or df_raw.empty:
                continue

            i = 0
            n_rows = len(df_raw)

            while i < n_rows:
                row_vals = df_raw.iloc[i].tolist()
                logger.debug("[DEBUG] Fila %d hoja '%s': %s", i, sheet_name, row_vals)
                header_map = _match_header_row(row_vals)

                if header_map is None:
                    i += 1
                    continue

                logger.debug("[DEBUG] Cabecera Materias IN encontrada en hoja '%s', fila %d: %s", sheet_name, i, row_vals)
                logger.debug("[DEBUG] header_map: %s", header_map)

                # Extraer filas de datos debajo de la cabecera hasta separador,
                # o hasta que aparezca otra cabecera.
                start = i + 1
                j = start
                rows_data = []

                while j < n_rows:
                    current_vals = df_raw.iloc[j].tolist()
                    logger.debug("[DEBUG]   Fila datos %d hoja '%s': %s", j, sheet_name, current_vals)

                    # Parar si fila vacía (separador típico)
                    if _is_separator_or_empty_row(current_vals):
                        logger.debug("[DEBUG]   Fila %d vacía/separador. Fin bloque.", j)
                        break

                    # Parar si las columnas CLAVE (asignatura + estudiante) están ambas vacías
                    # aunque otras columnas (ej. contadores) sean no vacías
                    c_asig = header_map.get("asignatura")
                    c_est  = header_map.get("estudiante")
                    key_asig = _norm(current_vals[c_asig]) if c_asig is not None and c_asig < len(current_vals) else ""
                    key_est  = _norm(current_vals[c_est])  if c_est  is not None and c_est  < len(current_vals) else ""
                    if not key_asig and not key_est:
                        logger.debug("[DEBUG]   Fila %d sin asignatura ni estudiante. Fin bloque.", j)
                        break

                    # Parar si aparece otra cabecera (otra tabla)
                    if _match_header_row(current_vals) is not None:
                        logger.debug("[DEBUG]   Fila %d parece otra cabecera. Fin bloque.", j)
                        break

                    # Construir fila con solo columnas relevantes detectadas
                    record = {}
                    for key, col_idx in header_map.items():
                        record[key] = df_raw.iat[j, col_idx] if col_idx < df_raw.shape[1] else None

                    record["_sheet_name"] = sheet_name
                    logger.debug("[DEBUG]   Registro extraído: %s", record)
                    rows_data.append(record)
                    j += 1

                if rows_data:
                    # Descartar bloque si todos los valores de 'estudiante' parecen numéricos
                    # (falso positivo: tabla de conteos u otra tabla adyacente)
                    est_vals = [str(r.get("estudiante") or "").strip() for r in rows_data]
                    est_vals_nonempty = [v for v in est_vals if v and v.lower() not in ("nan", "none", "")]
                    def _es_numerico(s):
                        try:
                            float(s.replace(",", "."))
                            return True
                        except (ValueError, TypeError):
                            return False
                    if est_vals_nonempty and all(_es_numerico(v) for v in est_vals_nonempty):
                        logger.debug(
                            "[DEBUG] Bloque descartado en hoja '%s' fila %d: todos los 'estudiante' son numéricos (%s)",
                            sheet_name, i, est_vals_nonempty[:3]
                        )
                    else:
                        bloque = pd.DataFrame(rows_data)
                        bloques.append(bloque)
                        logger.debug("[DEBUG] Bloque extraído en hoja '%s': %d filas", sheet_name, len(bloque))
                else:
                    logger.debug("[DEBUG] Cabecera detectada pero sin filas de datos en hoja '%s', fila %d", sheet_name, i)

                # Continuar desde donde terminó este bloque
                i = j + 1

        if not bloques:
            logger.debug("[DEBUG] No se encontró ninguna tabla de Materias IN.")
            return pd.DataFrame()

        df = pd.concat(bloques, ignore_index=True)

        # Asegurar columnas estándar (por si alguna tabla no trae todas)
        columnas_relevantes = ["asignatura", "estudiante", "origen", "universidadorigen", "cuat", "firmado", "la", "_sheet_name"]
        for c in columnas_relevantes:
            if c not in df.columns:
                df[c] = None

        # Dejar solo columnas en orden
        df = df[columnas_relevantes]

        # Renombrado estándar (sin espacios para acceso por atributos)
        df = df.rename(columns={
            "asignatura": "Asignatura",
            "estudiante": "Estudiante",
            "origen": "Origen",
            "universidadorigen": "UniversidadOrigen",
            "cuat": "Cuat",
            "firmado": "Firmado",
            "la": "LA",
            "_sheet_name": "SheetName",
        })

        # Limpieza básica
        for c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df.loc[df[c].isin(["", "nan", "None"]), c] = pd.NA

        df = df.dropna(subset=["Estudiante", "Asignatura"]).reset_index(drop=True)

        # Filtro de seguridad: descartar filas donde Estudiante es puramente numérico
        def _parece_numero(s):
            try:
                float(str(s).strip().replace(",", "."))
                return True
            except (ValueError, TypeError):
                return False
        mask_num = df["Estudiante"].apply(_parece_numero)
        if mask_num.any():
            logger.debug(
                "[DEBUG] Descartando %d filas con Estudiante numérico: %s",
                mask_num.sum(), df.loc[mask_num, 'Estudiante'].tolist()[:5]
            )
        df = df[~mask_num].reset_index(drop=True)

        logger.debug("[DEBUG] Filas finales Materias IN: %d", len(df))
        logger.debug("[DEBUG] Columnas finales: %s", list(df.columns))

        return df

    except Exception as e:
        logger.warning("[DEBUG] Error leyendo materias: %s", e)
        return pd.DataFrame()


def build_materias_in_por_estudiante(df_materias):
    """
    Devuelve un dict:
      { 'Nombre Estudiante': [ {datos de cada asignatura}, ... ] }
    """
    if df_materias is None or df_materias.empty:
        return {}

    materias_por_est = {}

    for row in df_materias.itertuples(index=False, name='Row'):
        est = str(getattr(row, "Estudiante", "") or "").strip()
        if not est:
            continue

        if est not in materias_por_est:
            materias_por_est[est] = []

        materias_por_est[est].append({
            "asignatura": getattr(row, 'Asignatura', None),
            "cuat":      getattr(row, 'Cuat', None),
            "firmado":   getattr(row, 'Firmado', None),
            "origen":    getattr(row, 'Origen', None),
            # antes usabas 'Centro' (no existía); ahora usa UniversidadOrigen
            "centro":    getattr(row, 'UniversidadOrigen', None),
            "la":        getattr(row, 'LA', None),
            "sheet_name": getattr(row, 'SheetName', None) or "",
        })

    return materias_por_est


def get_materias_in_por_estudiante(config):
    """
    Función de alto nivel: devuelve el diccionario listo.
    """
    df = load_materias_in(config)
    return build_materias_in_por_estudiante(df)

def get_alumnos_in(config):
    df = load_materias_in(config)

    if df.empty:
        return df

    alumnos = (
        df[["Estudiante", "Origen", "UniversidadOrigen"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    return alumnos


# ---------------------------------------------------------------------------
# Catálogo de asignaturas ofertadas (tabla con Asignaturas, Cuatrimestre, ...)
# ---------------------------------------------------------------------------
def _find_catalog_block(row_values):
    """
    Busca en una fila la subcabecera del catálogo de asignaturas.
    Devuelve dict con índices de columna o None.

    Evalúa TODOS los candidatos 'asignatura/asignaturas' de la fila y elige
    el que tenga mayor puntuación (tener matr+cupo+cuat juntos = catálogo real).
    Así ignora la columna 'Asignatura' de la tabla de alumnos, que no tiene
    'matriculados' ni 'cupo' cerca.
    """
    normalized = [_norm(v) for v in row_values]

    asig_candidates = [
        idx for idx, cell in enumerate(normalized)
        if cell in ("asignaturas", "asignatura", "materias", "materia")
    ]
    if not asig_candidates:
        return None

    best = None
    best_score = -1

    for asig_idx in asig_candidates:
        indices = {"asig": asig_idx, "cuat": -1, "matr": -1, "cupo": -1}
        for idx in range(asig_idx + 1, min(asig_idx + 10, len(normalized))):
            cell = normalized[idx]
            if cell in ("cuat", "cuatrimestre", "periodo", "semestre"):
                indices["cuat"] = idx
            elif cell in ("matriculados", "matricula", "nmatric", "inscritos", "matr"):
                indices["matr"] = idx
            elif cell in ("cupo", "plazas", "capacidad", "cupos", "aforo"):
                indices["cupo"] = idx

        has_matr = indices["matr"] != -1
        has_cupo = indices["cupo"] != -1
        has_cuat = indices["cuat"] != -1
        # Tener matr+cupo juntos es la señal clave de que es el catálogo
        score = (has_matr and has_cupo) * 4 + has_matr * 2 + has_cupo * 2 + has_cuat

        if score > best_score and (has_matr or has_cupo):
            best_score = score
            best = indices

    return best

def get_asignaturas_catalog(config, sheet_name: str | None = None):
    """
    Lee el catálogo de asignaturas desde el Excel de Materias IN (o Erasmus IN).
    Si se pasa sheet_name, solo busca en esa hoja.
    Devuelve lista de dicts [{asignatura, cuat, matriculados, cupo}, ...] ordenados por cuat.

    Soporta tablas en paralelo: la tabla del catálogo puede estar a la derecha
    de la tabla de alumnos en las mismas filas.
    """
    ruta = config.get("Erasmus IN") or ""
    if not ruta or not os.path.exists(ruta):
        return []

    def _normalize_sheet(s):
        return str(s).strip().replace(" ", "").replace("-", "").replace("/", "").lower()

    def _safe_int(val):
        try:
            if pd.isna(val):
                return None
            s = str(val).strip().replace(',', '.')
            if s == "" or s.lower() in ("nan", "none"):
                return None
            return int(float(s))
        except Exception:
            return None

    def _cell(row, idx):
        """Devuelve el valor de una celda o '' si está fuera de rango / es NaN."""
        if idx < 0 or idx >= len(row):
            return ""
        v = row.iloc[idx]
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        return str(v).strip()

    try:
        xls = pd.read_excel(ruta, sheet_name=None, header=None, dtype=str)

        # Las fórmulas tipo COUNTIF no se evalúan al leer con pandas/openpyxl.
        # Recalculamos la columna Matriculados contando cuántas veces aparece
        # cada asignatura en la columna de asignaturas de alumnos (col 0).
        # Para eso necesitamos saber los índices, que hacemos por hoja.
        rows = []

        sheet_candidates = list(xls.keys())
        sheet_to_use = None
        if sheet_name:
            norm_target = _normalize_sheet(sheet_name)
            for s in sheet_candidates:
                if _normalize_sheet(s) == norm_target:
                    sheet_to_use = s
                    break
            if not sheet_to_use:
                for s in sheet_candidates:
                    if norm_target in _normalize_sheet(s):
                        sheet_to_use = s
                        break

        sheets_iter = [sheet_to_use] if sheet_to_use else sheet_candidates

        for sname in sheets_iter:
            df_raw = xls[sname]
            if df_raw is None or df_raw.empty:
                continue

            n_rows = len(df_raw)
            i = 0
            while i < n_rows:
                row_vals = df_raw.iloc[i].tolist()
                indices = _find_catalog_block(row_vals)
                if indices is None:
                    i += 1
                    continue

                asig_idx = indices["asig"]
                cuat_idx = indices["cuat"]
                matr_idx = indices["matr"]
                cupo_idx = indices["cupo"]

                logger.debug(
                    "[catalog] Cabecera catálogo encontrada en hoja '%s' fila %d: "
                    "asig=%d matr=%d cuat=%d cupo=%d",
                    sname, i, asig_idx, matr_idx, cuat_idx, cupo_idx
                )

                # Buscar la columna de asignaturas de la tabla de alumnos
                # (es el otro candidato 'asignatura' distinto del catálogo)
                alumnos_asig_idx = next(
                    (idx for idx, cell in enumerate([_norm(v) for v in df_raw.iloc[i].tolist()])
                     if cell in ("asignatura", "asignaturas") and idx != asig_idx),
                    None
                )
                # Contar cuántas veces aparece cada asignatura en la columna de ALUMNOS
                # (replica el COUNTIF de Excel, que puede no estar cacheado si hay fórmulas)
                _countif_cache = {}
                if alumnos_asig_idx is not None:
                    for _r in range(i + 1, n_rows):
                        _val = _cell(df_raw.iloc[_r], alumnos_asig_idx)
                        if _val and _val.lower() not in ("nan", "none"):
                            _countif_cache[_val] = _countif_cache.get(_val, 0) + 1

                j = i + 1
                while j < n_rows:
                    row = df_raw.iloc[j]

                    # La columna del catálogo (asig_idx) puede tener datos aunque
                    # la columna de alumnos (col 0) esté vacía — NO parar por eso.
                    asig = _cell(row, asig_idx)
                    if not asig or asig.lower() in ("nan", "none", "total", "subtotal"):
                        break

                    cuat = ""
                    if cuat_idx != -1:
                        c_val = _cell(row, cuat_idx)
                        if c_val and c_val.lower() not in ("nan", "none"):
                            cuat = c_val.split('.')[0] if '.' in c_val else c_val

                    # Matriculados: leer del Excel; si es NaN (fórmula no evaluada), usar countif
                    matr_val = _safe_int(row.iloc[matr_idx]) if matr_idx != -1 else None
                    if matr_val is None:
                        matr_val = _countif_cache.get(asig, 0)

                    # Cupo: leer directamente del Excel
                    cupo_val = _safe_int(row.iloc[cupo_idx]) if cupo_idx != -1 else None

                    rows.append({
                        "asignatura": asig,
                        "cuat": cuat,
                        "matriculados": matr_val,
                        "cupo": cupo_val,
                    })
                    j += 1

                i = j + 1

        def _sort_key(r):
            c = r.get("cuat", "")
            if c in ("1", "1.0"): return (0, r["asignatura"])
            if c in ("2", "2.0"): return (1, r["asignatura"])
            return (2, r["asignatura"])

        rows.sort(key=_sort_key)
        logger.debug("[catalog] Catálogo cargado: %d asignaturas", len(rows))
        return rows

    except Exception as e:
        logger.warning("[catalog] Error leyendo catálogo de asignaturas: %s", e)
        return []