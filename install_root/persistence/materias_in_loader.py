import os
import unicodedata
import pandas as pd


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
    Lee el Excel de 'Materias IN' y extrae SOLO las tablas que tengan la cabecera
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

        print("[DEBUG] Buscando tablas Materias IN en todas las hojas...")

        for sheet_name, df_raw in xls.items():
            print(f"[DEBUG] Revisando hoja: {sheet_name}")
            if df_raw is None or df_raw.empty:
                continue

            i = 0
            n_rows = len(df_raw)

            while i < n_rows:
                row_vals = df_raw.iloc[i].tolist()
                print(f"[DEBUG] Fila {i} hoja '{sheet_name}': {row_vals}")
                header_map = _match_header_row(row_vals)

                if header_map is None:
                    i += 1
                    continue

                print(f"[DEBUG] Cabecera Materias IN encontrada en hoja '{sheet_name}', fila {i}: {row_vals}")
                print(f"[DEBUG] header_map: {header_map}")

                # Extraer filas de datos debajo de la cabecera hasta separador,
                # o hasta que aparezca otra cabecera.
                start = i + 1
                j = start
                rows_data = []

                while j < n_rows:
                    current_vals = df_raw.iloc[j].tolist()
                    print(f"[DEBUG]   Fila datos {j} hoja '{sheet_name}': {current_vals}")

                    # Parar si fila vacía (separador típico)
                    if _is_separator_or_empty_row(current_vals):
                        print(f"[DEBUG]   Fila {j} vacía/separador. Fin bloque.")
                        break

                    # Parar si aparece otra cabecera (otra tabla)
                    if _match_header_row(current_vals) is not None:
                        print(f"[DEBUG]   Fila {j} parece otra cabecera. Fin bloque.")
                        break

                    # Construir fila con solo columnas relevantes detectadas
                    record = {}
                    for key, col_idx in header_map.items():
                        record[key] = df_raw.iat[j, col_idx] if col_idx < df_raw.shape[1] else None

                    print(f"[DEBUG]   Registro extraído: {record}")
                    rows_data.append(record)
                    j += 1

                if rows_data:
                    bloque = pd.DataFrame(rows_data)
                    bloques.append(bloque)
                    print(f"[DEBUG] Bloque extraído en hoja '{sheet_name}': {len(bloque)} filas")
                else:
                    print(f"[DEBUG] Cabecera detectada pero sin filas de datos en hoja '{sheet_name}', fila {i}")

                # Continuar desde donde terminó este bloque
                i = j + 1

        if not bloques:
            print("[DEBUG] No se encontró ninguna tabla de Materias IN.")
            return pd.DataFrame()

        df = pd.concat(bloques, ignore_index=True)

        # Asegurar columnas estándar (por si alguna tabla no trae todas)
        columnas_relevantes = ["asignatura", "estudiante", "origen", "universidadorigen", "cuat", "firmado"]
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
        })

        # Limpieza básica
        for c in df.columns:
            df[c] = df[c].astype(str).str.strip()
            df.loc[df[c].isin(["", "nan", "None"]), c] = pd.NA

        df = df.dropna(subset=["Estudiante", "Asignatura"]).reset_index(drop=True)

        print(f"[DEBUG] Filas finales Materias IN: {len(df)}")
        print(f"[DEBUG] Columnas finales: {list(df.columns)}")

        return df

    except Exception as e:
        print(f"[DEBUG] Error leyendo materias: {e}")
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
        })

    return materias_por_est


def get_materias_in_por_estudiante(config):
    """
    Función de alto nivel: devuelve el diccionario listo.
    """
    df = load_materias_in(config)
    return build_materias_in_por_estudiante(df)