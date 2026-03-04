from __future__ import annotations

import logging
import os
from openpyxl import load_workbook

import os
import shutil
import traceback
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Iterable
from openpyxl import load_workbook

logger = logging.getLogger("movilidad_persistence")

# geocodificación (si falla/no hay internet, NO rompe el guardado)
try:
    from geopy.geocoders import Nominatim
    _geolocator = Nominatim(user_agent="movilidadesii-excel-update")
except Exception:
    _geolocator = None



# ============================================================
# Alias de campos del formulario -> columnas posibles en Excel
# ============================================================
FIELD_ALIASES = {
    "estudiante": [
        "estudiante", "Estudiante", "NOMBRE COMPLETO", "Nombre completo", "nombre", "Nombre", "NOMBRE",
    ],
    "email": [
        "email", "Email", "E-mail", "Correo", "Correo electrónico",
    ],
    "curso": [
        "curso", "Curso",
    ],
    "cuatrimestre": [
        "cuatrimestre", "Cuatrimestre", "cuat", "Cuat", "cuatri", "Cuatri",
    ],
    "duracion_meses": [
        "duracion meses",
        "duracion_meses",
        "Duración (meses)",
        "Duración meses",
        "Duración",
    ],
    "gestion_LA": [
        "Gestion LA",
        "gestion_LA",
        "Gestión LA",
    ],
    "coordinador_destino": [
        "Coordinador en destino",
        "coordinador_destino",
        "Coordinador destino",
        "Coordinador de destino",
    ],
    "link_la": [
        "LA",
        "link_la",
        "Learning agreement",
        "Learning Agreement",
    ],
    "ToR": [
        "ToR", "TOR", "Transcript of Records",
    ],
    "acta_equivalencias": [
        "acta_equivalencias", "Acta de equivalencias",
    ],
    "link_plan": [
        "Plan de estudios",
        "link_plan",
        "Plan estudios",
        "Plan",
    ],
    "destino": [
        "destino", "Destino", "Universidad de origen", "universidad de origen", "Universidad origen",
    ],
    "origen": [
        "origen", "Origen",
    ],
    "responsable": [
        "responsable", "Responsable",
    ],
    "pais": [
        "pais", "País", "Pais",
    ],
    "ciudad": [
        "ciudad", "Ciudad",
    ],
}

# Alias específicos para detectar tabla de alumnos (múltiples tablas en una hoja)
STUDENTS_HEADER_ALIASES = {
    "nombre": {"nombre", "nombre completo", "estudiante"},
    "email": {"email", "e-mail", "correo", "correo electronico", "correo electrónico"},
    "pais": {"pais", "país"},
    "cuatrimestre": {"cuatrimestre", "cuat", "cuatri"},
    "universidad_origen": {"universidad de origen", "universidad origen", "origen", "destino"},
    "coordenadas": {"coordenadas", "coords"},
    "ciudad": {"ciudad"},
}
STUDENTS_REQUIRED = {"nombre", "pais", "cuatrimestre"}

# Alias específicos para detectar tabla de Materias IN
MATERIAS_HEADER_ALIASES = {
    "asignatura": {"asignatura"},
    "estudiante": {"estudiante", "estudiantes", "alumno", "alumnos"},
    "origen": {"origen"},
    "universidad_origen": {"universidad de origen", "universidad origen", "centro", "universidadorigen"},
    "cuat": {"cuat", "cuatrimestre", "cuatri"},
    "firmado": {"firmado", "firma"},
    "link_la": {"link la", "linkla", "la", "learning agreement", "link_la"},
}
MATERIAS_REQUIRED = {"asignatura", "estudiante"}


# --- Obtener nombre real de alumno por fila (columna B, filas 2-479, hoja actual) ---
def get_student_name_by_row(excel_path, sheet_name, row):
    """
    Devuelve el nombre real del alumno en la columna B (índice 2), ignorando fórmulas y errores.
    row: número de fila (2 a 479)
    """
    from openpyxl import load_workbook
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]
    v = ws.cell(row=row, column=2).value
    wb.close()
    if v is None:
        return ""
    v = str(v).strip()
    if not v or v.upper() in {"#N/D", "#VALUE!", "#¡DESBORDAMIENTO!", "#SPILL!", "#REF!", "#NAME?"}:
        return ""
    return v
# --- Utilidad para obtener nombres únicos de una columna (sin depender de fórmulas Excel) ---
def util_get_unique_names_from_column(excel_path, sheet_name, col_letter, row_start=2, row_end=479):
    """
    Devuelve una lista de nombres únicos de la columna col_letter (por ejemplo, 'B')
    entre las filas row_start y row_end (inclusive), ignorando vacíos y errores (#N/D, etc).
    """
    from openpyxl import load_workbook
    wb = load_workbook(excel_path, data_only=True)
    ws = wb[sheet_name]
    nombres_unicos = []
    vistos = set()
    for fila in range(row_start, row_end + 1):
        v = ws[f"{col_letter}{fila}"].value
        if v is None:
            continue
        v = str(v).strip()
        if not v or v.upper() in {"#N/D", "#VALUE!", "#¡DESBORDAMIENTO!", "#SPILL!", "#REF!", "#NAME?"}:
            continue
        if v not in vistos:
            vistos.add(v)
            nombres_unicos.append(v)
    wb.close()
    return nombres_unicos


# --- Helpers for robust name handling ---
def _name_to_scalar(value):
    """
    Convierte nombres que pueden venir en string plano.
    """
    while isinstance(value, (list, tuple)) and len(value) > 0:
        value = value[0]
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("[") and s.endswith("]"):
        s = s.strip("[]").strip().strip("'").strip('"').strip()
    return s

def _is_invalid_student_name_cell(v) -> bool:
    """
    True si el valor no es un nombre real (fórmula, error, 0, vacío...).
    """
    if v is None:
        return True
    s = str(v).strip()
    if s == "":
        return True
    if s.startswith("="):
        return True
    if s.upper() in {"#N/D", "#VALUE!", "#¡DESBORDAMIENTO!", "#SPILL!", "#REF!", "#NAME?"}:
        return True
    if s == "0":
        return True
    return False

def _students_table_is_dynamic_unique(ws, table_info) -> bool:
    """
    Detecta si la columna de nombre de la tabla de alumnos viene de una matriz dinámica (UNICOS/UNIQUE).
    """
    c_nombre = table_info.cols.get("nombre")
    if not c_nombre:
        return False
    r = table_info.data_start
    if r > ws.max_row:
        return False
    v = ws.cell(row=r, column=c_nombre).value
    s = str(v or "").strip().upper()
    return s.startswith("=UNICOS(") or s.startswith("=UNIQUE(")


@dataclass
class TableInfo:
    sheet_name: str
    header_row: int        # 1-based
    data_start: int        # 1-based
    data_end: int          # 1-based inclusive; puede ser header_row si no hay datos
    cols: Dict[str, int]   # clave canónica -> columna 1-based


def _norm_header(s: Any) -> str:
    s = str(s or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = " ".join(s.split())
    return s

def normalize_str(s: Any) -> str:
    return _norm_header(s)

def _sheet_priority(sheet_name: str) -> tuple:
    n = _norm_header(sheet_name)
    return (0 if n == "curso" else 1, n)

def _iter_sheets_preferred(wb) -> Iterable:
    return sorted(wb.worksheets, key=lambda ws: _sheet_priority(ws.title))

def _row_is_empty_ws(ws, row_num: int, max_col: Optional[int] = None) -> bool:
    max_col = max_col or ws.max_column
    # Considerar vacía solo si TODAS las celdas están vacías o solo contienen espacios en blanco
    # Si hay un 0, un número, o cualquier valor distinto de vacío, NO es vacía
    for c in range(1, max_col + 1):
        v = ws.cell(row=row_num, column=c).value
        # Considerar vacía si es None o cadena vacía/espacios
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        # Si es un número, aunque sea 0, NO es vacía
        return False
    return True

def _match_header_row(ws, row_num: int, aliases_map: Dict[str, set], required: set,
                      extra_min_matches: int = 0, extras_pool: Optional[set] = None) -> Optional[Dict[str, int]]:
    found: Dict[str, int] = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=row_num, column=c).value
        n = _norm_header(v)
        if not n:
            continue
        for canon, aliases in aliases_map.items():
            if n in aliases and canon not in found:
                found[canon] = c

    if not required.issubset(found.keys()):
        return None

    if extra_min_matches and extras_pool:
        if len(extras_pool.intersection(found.keys())) < extra_min_matches:
            return None

    return found

def _find_table_in_workbook(excel_path: str, aliases_map: Dict[str, set], required: set,
                            extra_min_matches: int = 0, extras_pool: Optional[set] = None,
                            target_sheet: str = "") -> Optional[TableInfo]:
    wb = load_workbook(excel_path)
    try:
        if target_sheet and target_sheet in wb.sheetnames:
            sheets_to_search = [wb[target_sheet]]
            logger.debug("[detect] Buscando tabla solo en hoja '%s' (sheet_name recibido)", target_sheet)
        else:
            sheets_to_search = _iter_sheets_preferred(wb)
        for ws in sheets_to_search:
            max_r = ws.max_row
            max_c = ws.max_column
            if max_r <= 0 or max_c <= 0:
                continue

            r = 1
            while r <= max_r:
                cols = _match_header_row(ws, r, aliases_map, required,
                                         extra_min_matches=extra_min_matches, extras_pool=extras_pool)
                if not cols:
                    r += 1
                    continue

                data_start = r + 1
                data_end = r
                rr = data_start
                # Mejorar: solo considerar parte de la tabla mientras haya datos válidos (no filas vacías completas)
                while rr <= max_r:
                    # Si encontramos una fila vacía, paramos (fin de la tabla)
                    if _row_is_empty_ws(ws, rr, max_c):
                        break
                    # Si encontramos otra cabecera (otra tabla), paramos
                    if _match_header_row(ws, rr, aliases_map, required,
                                         extra_min_matches=extra_min_matches, extras_pool=extras_pool):
                        break
                    # Si la fila tiene solo un valor (por ejemplo, un 0 aislado), también paramos
                    non_empty_cells = [ws.cell(row=rr, column=c).value for c in range(1, max_c + 1) if ws.cell(row=rr, column=c).value not in (None, "")]
                    if len(non_empty_cells) == 1:
                        # Si es un número y está solo, probablemente no es parte de la tabla
                        v = non_empty_cells[0]
                        if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
                            break
                    data_end = rr
                    rr += 1

                info = TableInfo(
                    sheet_name=ws.title,
                    header_row=r,
                    data_start=data_start,
                    data_end=data_end,
                    cols=cols,
                )
                logger.debug(
                    "[detect] Tabla encontrada en hoja='%s' header=%s datos=%s..%s cols=%s",
                    info.sheet_name, info.header_row, info.data_start, info.data_end, info.cols
                )
                return info
        return None
    finally:
        wb.close()

def _build_header_maps_from_ws(ws, header_row_idx_0based: int):
    row_excel = header_row_idx_0based + 1
    norm_to_col = {}
    raw_headers = {}
    for c in range(1, ws.max_column + 1):
        v = ws.cell(row=row_excel, column=c).value
        if v is None:
            continue
        raw = str(v).strip()
        if not raw:
            continue
        raw_headers[c] = raw
        n = _norm_header(raw)
        if n and n not in norm_to_col:
            norm_to_col[n] = c
    return norm_to_col, raw_headers

def _find_col_in_ws_by_aliases(norm_to_col_1based: Dict[str, int], aliases: List[str]) -> Optional[int]:
    for a in aliases:
        n = _norm_header(a)
        if n in norm_to_col_1based:
            return norm_to_col_1based[n]
    return None

def _set_ws_cell_if_field_exists(ws, excel_row: int, norm_to_col_1based: Dict[str, int], field_name: str, data: dict):
    if field_name not in data:
        return False
    value = data[field_name]
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False

    aliases = FIELD_ALIASES.get(field_name, [field_name])
    col = _find_col_in_ws_by_aliases(norm_to_col_1based, aliases)
    if col is None:
        return False

    ws.cell(row=excel_row, column=col).value = value
    logger.debug("[excel][set] row=%d col=%d field=%s value=%r", excel_row, col, field_name, value)
    return True

def _split_full_name(full_name: str):
    full_name = (full_name or "").strip()
    if not full_name:
        return "", "", ""
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])

def _recalculate_coords_ws(ws, excel_row: int, norm_to_col_1based: Dict[str, int]):

    # Detectar el programa de movilidad
    col_programa = _find_col_in_ws_by_aliases(norm_to_col_1based, ["programa", "tipo", "program", "type"])
    programa = None
    if col_programa:
        programa = ws.cell(row=excel_row, column=col_programa).value
        if programa:
            programa = str(programa).strip().lower()

    # Si es Erasmus IN o Erasmus OUT, saltar cálculo de coordenadas
    if programa in ("erasmus in", "erasmus out"):
        logger.debug("[coords/ws] Programa '%s' detectado, se omite geocodificación.", programa)
        return

    if _geolocator is None:
        logger.debug("[coords/ws] geopy no disponible; se omite geocodificación.")
        return

    def _get_first(*aliases):
        col = _find_col_in_ws_by_aliases(norm_to_col_1based, list(aliases))
        if col is None:
            return None
        return ws.cell(row=excel_row, column=col).value

    destino = _get_first("destino", "universidad", "universidad destino", "universidad de origen")
    ciudad = _get_first("ciudad")
    pais = _get_first("país", "pais")

    queries: List[str] = []
    partes = [str(x).strip() for x in (destino, ciudad, pais) if x is not None and str(x).strip() and str(x).strip().lower() != "none"]
    if partes:
        queries.append(", ".join(partes))
    if ciudad and pais:
        queries.append(f"{str(ciudad).strip()}, {str(pais).strip()}")
    if ciudad:
        queries.append(str(ciudad).strip())
    if pais:
        queries.append(str(pais).strip())

    if not queries:
        return

    loc = None
    for query in queries:
        try:
            logger.debug("[coords/ws] Geocodificando: %r", query)
            loc = _geolocator.geocode(query, timeout=10)
        except Exception as e:
            logger.debug("[coords/ws] Error geocodificando %r: %s", query, e)
            loc = None
        if loc:
            break

    if not loc:
        logger.debug("[coords/ws] No se encontraron coordenadas.")
        return

    lat, lon = loc.latitude, loc.longitude
    col_lat = _find_col_in_ws_by_aliases(norm_to_col_1based, ["latitud", "latitude"])
    col_lon = _find_col_in_ws_by_aliases(norm_to_col_1based, ["longitud", "longitude"])
    col_coo = _find_col_in_ws_by_aliases(norm_to_col_1based, ["coordenadas", "coords"])

    if col_lat:
        ws.cell(row=excel_row, column=col_lat).value = lat
    if col_lon:
        ws.cell(row=excel_row, column=col_lon).value = lon
    if col_coo:
        ws.cell(row=excel_row, column=col_coo).value = f"{lat},{lon}"

    logger.debug("[coords/ws] Escritas coords lat=%s, lon=%s", lat, lon)


def _recalculate_coords(df: "pd.DataFrame", row_idx: int):
    """
    Versión pandas de _recalculate_coords_ws.
    Geocodifica la fila row_idx del DataFrame y escribe las coordenadas en él.
    """
    import pandas as pd
    if _geolocator is None:
        logger.debug("[coords/df] geopy no disponible; se omite geocodificación.")
        return

    col_map = {str(c).strip().lower(): c for c in df.columns}

    def _col(*aliases):
        for a in aliases:
            if a in col_map:
                return col_map[a]
        return None

    def _val(*aliases):
        col = _col(*aliases)
        if col is None:
            return None
        v = df.at[row_idx, col]
        if pd.isna(v) or str(v).strip().lower() in ("", "none", "nan"):
            return None
        return str(v).strip()

    destino = _val("universidad", "destino", "universidad destino")
    ciudad = _val("ciudad")
    pais = _val("país", "pais")

    queries: List[str] = []
    partes = [x for x in (destino, ciudad, pais) if x]
    if partes:
        queries.append(", ".join(partes))
    if ciudad and pais:
        queries.append(f"{ciudad}, {pais}")
    if ciudad:
        queries.append(ciudad)
    if pais:
        queries.append(pais)

    if not queries:
        return

    loc = None
    for query in queries:
        try:
            logger.debug("[coords/df] Geocodificando: %r", query)
            loc = _geolocator.geocode(query, timeout=10)
        except Exception as e:
            logger.debug("[coords/df] Error geocodificando %r: %s", query, e)
            loc = None
        if loc:
            break

    if not loc:
        logger.debug("[coords/df] No se encontraron coordenadas.")
        return

    lat, lon = float(loc.latitude), float(loc.longitude)
    c_coo = _col("coordenadas", "coords")
    c_lat = _col("latitud", "latitude")
    c_lon = _col("longitud", "longitude")
    if c_coo:
        df.at[row_idx, c_coo] = f"{lat}, {lon}"
    if c_lat:
        df.at[row_idx, c_lat] = lat
    if c_lon:
        df.at[row_idx, c_lon] = lon
    logger.debug("[coords/df] Escritas coords lat=%s, lon=%s", lat, lon)


def _normalize_firmado(v: Any) -> str:
    if isinstance(v, bool):
        return "x" if v else ""
    s = str(v or "").strip().lower()
    return "x" if s in ("x", "1", "s", "si", "sí", "true", "t") else ""

def _ensure_rows_for_append(ws, insert_at: int, count: int):
    if count <= 0:
        return
    need_insert = False
    for r in range(insert_at, insert_at + count):
        if r <= ws.max_row and not _row_is_empty_ws(ws, r, ws.max_column):
            need_insert = True
            break
    if need_insert:
        ws.insert_rows(insert_at, count)
        logger.debug("[materias] Insertadas %d filas en %d para no pisar contenido inferior.", count, insert_at)


def update_student_in_excel(excel_path: str, row_index: str, idx: int, data: dict, old_email: str = None, old_nombre: str = None) -> bool:
    """
    Actualiza SOLO la misma fila del alumno dentro de la tabla de alumnos.
    No crea hojas, no reemplaza hojas, no elimina filas.
    """
    logger.debug("[update_student_in_excel] excel_path=%s row_index=%s idx=%s", excel_path, row_index, idx)

    try:
        table_info = _find_table_in_workbook(
            excel_path,
            STUDENTS_HEADER_ALIASES,
            STUDENTS_REQUIRED,
            extra_min_matches=1,
            extras_pool={"universidad_origen", "coordenadas", "email"},
        )
        if not table_info:
            logger.warning("[update_student_in_excel] No se encontró tabla de alumnos.")
            return False
    except Exception as e:
        logger.exception("[update_student_in_excel] Error localizando tabla")
        return False

    wb = None
    try:
        wb = load_workbook(excel_path)
        ws = wb[table_info.sheet_name]


        norm_to_col_1based, raw_headers = _build_header_maps_from_ws(ws, table_info.header_row - 1)
        logger.debug("[update_student_in_excel] headers detectados: %s", raw_headers)

        # Si es matriz dinámica, solo impedir editar el nombre, pero permitir editar otros campos
        is_dynamic_matrix = _students_table_is_dynamic_unique(ws, table_info)
        if is_dynamic_matrix:
            logger.debug("[update_student_in_excel] Tabla de alumnos es una matriz dinámica (UNICOS). Solo se editarán campos distintos al nombre.")


        # Buscar solo la primera fila válida que coincida por email o nombre (robusto)
        row_found = None
        email_col = table_info.cols.get("email")
        email_target = (data.get("old_email") or old_email or "").strip().lower()
        if email_col and email_target:
            logger.debug("[update_student_in_excel] Buscando por email: %s", email_target)
            for r in range(table_info.data_start, table_info.data_end + 1):
                v = ws.cell(row=r, column=email_col).value
                cell_email = _name_to_scalar(v)
                if _is_invalid_student_name_cell(cell_email):
                    continue
                # Comprobar que la fila no es basura (al menos un campo clave válido)
                if str(cell_email).strip().lower() == email_target:
                    # Comprobar que la fila no es basura (al menos país/cuatrimestre válidos)
                    pais_col = table_info.cols.get("pais")
                    cuat_col = table_info.cols.get("cuatrimestre")
                    pais_val = ws.cell(row=r, column=pais_col).value if pais_col else None
                    cuat_val = ws.cell(row=r, column=cuat_col).value if cuat_col else None
                    if not _is_invalid_student_name_cell(pais_val) or not _is_invalid_student_name_cell(cuat_val):
                        row_found = r
                        logger.debug("[update_student_in_excel] Fila válida localizada por email: %d", r)
                        break

        if row_found is None:
            nombre_col = table_info.cols.get("nombre")
            full_name_raw = (data.get("old_nombre") or old_nombre or data.get("estudiante") or "").strip()
            cand_norm = normalize_str(_name_to_scalar(full_name_raw))
            if nombre_col and cand_norm:
                for r in range(table_info.data_start, table_info.data_end + 1):
                    v = ws.cell(row=r, column=nombre_col).value
                    cell_name = _name_to_scalar(v)
                    if _is_invalid_student_name_cell(cell_name):
                        continue
                    # Comprobar que la fila no es basura (al menos país/cuatrimestre válidos)
                    pais_col = table_info.cols.get("pais")
                    cuat_col = table_info.cols.get("cuatrimestre")
                    pais_val = ws.cell(row=r, column=pais_col).value if pais_col else None
                    cuat_val = ws.cell(row=r, column=cuat_col).value if cuat_col else None
                    if normalize_str(cell_name) == cand_norm:
                        if not _is_invalid_student_name_cell(pais_val) or not _is_invalid_student_name_cell(cuat_val):
                            row_found = r
                            logger.debug("[update_student_in_excel] Fila válida localizada por nombre (robusto): %d", r)
                            break

        if row_found is None:
            logger.warning("[update_student_in_excel] No se encontró ninguna fila válida con ese email/nombre.")
            return False



        # Editar solo la primera fila válida encontrada
        for field in FIELD_ALIASES.keys():
            # Si es matriz dinámica, no editar el nombre
            if is_dynamic_matrix and field in ("estudiante", "nombre"):
                continue
            _set_ws_cell_if_field_exists(ws, row_found, norm_to_col_1based, field, data)

        # Solo editar el nombre si NO es matriz dinámica
        if not is_dynamic_matrix:
            full = (data.get("estudiante") or "").strip()
            if full:
                nombre, ape1, ape2 = _split_full_name(full)
                col_nombre = _find_col_in_ws_by_aliases(norm_to_col_1based, ["nombre", "estudiante", "nombre completo"])
                col_ape1 = _find_col_in_ws_by_aliases(norm_to_col_1based, ["apellido1", "apellido_1"])
                col_ape2 = _find_col_in_ws_by_aliases(norm_to_col_1based, ["apellido2", "apellido_2"])

                if col_nombre:
                    header_norm = _norm_header(ws.cell(row=table_info.header_row, column=col_nombre).value)
                    if header_norm in ("nombre completo", "estudiante"):
                        ws.cell(row=row_found, column=col_nombre).value = full
                    elif header_norm == "nombre" and col_ape1:
                        ws.cell(row=row_found, column=col_nombre).value = nombre
                    else:
                        ws.cell(row=row_found, column=col_nombre).value = full

                if col_ape1 and ape1:
                    ws.cell(row=row_found, column=col_ape1).value = ape1
                if col_ape2 and ape2:
                    ws.cell(row=row_found, column=col_ape2).value = ape2

        try:
            _recalculate_coords_ws(ws, row_found, norm_to_col_1based)
        except Exception as e:
            logger.warning("[update_student_in_excel] No se pudieron recalcular coords: %s", e)

        # _make_backup(excel_path, tag="alumnos_before_update")  # Desactivado: no crear backup
        wb.save(excel_path)
        logger.info("[update_student_in_excel] Guardado OK (misma fila, in-place).")
        return True

    except Exception as e:
        logger.exception("[update_student_in_excel] Error guardando in-place")
        return False
    finally:
        try:
            if wb is not None:
                wb.close()
        except Exception:
            pass


def actualizar_excel_materias_para_estudiante(materias_in, est, materias_path: str, sheet_name: str = ""):
    """
    Modo seguro:
    - edita en la misma fila (por orden) las materias existentes del alumno
    - añade nuevas debajo del final de la tabla
    """


    if not materias_path:
        raise ValueError("No se ha recibido la ruta del Excel de materias.")
    if not os.path.exists(materias_path):
        raise FileNotFoundError(f"El archivo de materias no existe: {materias_path}")

    # ---- datos alumno (defaults correctos) ----
    nombre_nuevo = str(est.get("estudiante") or "").strip()
    nombre_antiguo = str(est.get("old_nombre") or est.get("old_estudiante") or "").strip()

    # ORIGEN = país (PRIORIDAD)
    origen_default = str(est.get("pais") or est.get("origen") or "").strip()

    # UNIVERSIDAD = universidad_origen / destino
    uni_default = str(
        est.get("universidad_origen")
        or est.get("destino")
        or est.get("Centro")
        or est.get("centro")
        or est.get("universidad")
        or ""
    ).strip()

    # Campos globales del alumno (mismos en todas sus filas)
    cuat_default  = str(est.get("cuat") or "").strip()
    firmado_default = _normalize_firmado(est.get("firmado", ""))
    la_default    = str(est.get("link_la") or "").strip()

    if not nombre_nuevo and not nombre_antiguo:
        raise ValueError("No hay nombre de estudiante para actualizar materias.")

    # ---- localizar tabla materias (usa tu detector actual) ----
    table_info = _find_table_in_workbook(
        materias_path,
        MATERIAS_HEADER_ALIASES,
        MATERIAS_REQUIRED,
        extra_min_matches=2,
        extras_pool={"origen", "universidad_origen", "cuat", "firmado"},
        target_sheet=sheet_name or "",
    )
    if not table_info:
        raise RuntimeError("No se ha encontrado tabla de Materias IN en el Excel.")

    # ---- normalizar payload ----
    nuevas = []
    for m in (materias_in or []):
        if not isinstance(m, dict):
            continue

        asig = str(m.get("asignatura") or m.get("nombre") or "").strip()
        if not asig:
            continue

        # OJO: solo usar valores explícitos del item si vienen; si no, defaults
        item_origen = str(m.get("origen") or "").strip()
        item_uni = str(m.get("universidad_origen") or m.get("centro") or "").strip()

        nuevas.append({
            "asignatura": asig,
            "estudiante": nombre_nuevo or nombre_antiguo,
            "origen": item_origen if item_origen else origen_default,
            "universidad_origen": item_uni if item_uni else uni_default,
            "cuat": str(m.get("cuat") or "").strip(),
            "firmado": _normalize_firmado(m.get("firmado", "")),
            "link_la": str(m.get("link_la") or m.get("la") or "").strip(),
            "_origen_explicit": bool(item_origen),
            "_uni_explicit": bool(item_uni),
        })

    if not nuevas:
        logger.debug("[materias] No hay materias válidas; no se modifica Excel.")
        return

    wb = load_workbook(materias_path)
    try:
        ws = wb[table_info.sheet_name]

        c_asig = table_info.cols.get("asignatura")
        c_est  = table_info.cols.get("estudiante")
        c_ori  = table_info.cols.get("origen")

        # Detección robusta de la columna de universidad de origen
        c_uni = None
        uni_aliases = list(MATERIAS_HEADER_ALIASES.get("universidad_origen", set()))
        uni_aliases += [
            "universidad_origen", "centro", "universidad de origen", "universidad origen",
            "Universidad Origen", "Universidad  Origen", "universidad  origen"
        ]

        # Normalizar aliases
        uni_aliases = list({normalize_str(a) for a in uni_aliases})

        # Leer cabeceras reales de la fila de la tabla
        norm_to_col, raw_headers = _build_header_maps_from_ws(ws, table_info.header_row - 1)

        # ✅ USAR norm_to_col directamente (texto normalizado -> nº columna)
        for alias in uni_aliases:
            if alias in norm_to_col:
                c_uni = norm_to_col[alias]
                break

        if not c_uni:
            logger.warning(
                "[materias] No se detectó columna de universidad de origen. "
                "Alias buscados=%s | Cabeceras detectadas=%s",
                uni_aliases, raw_headers
            )
        else:
            logger.debug("[materias] Columna universidad detectada: c_uni=%s header=%s", c_uni, raw_headers.get(c_uni))

        c_cuat = table_info.cols.get("cuat")
        c_fir  = table_info.cols.get("firmado")
        c_la   = table_info.cols.get("link_la")

        # ---- normalizar payload ----
        nuevas = []
        for m in (materias_in or []):
            if not isinstance(m, dict):
                continue
            asig = str(m.get("asignatura") or m.get("nombre") or "").strip()
            if not asig:
                continue
            item_origen = str(m.get("origen") or "").strip()
            item_uni = str(m.get("universidad_origen") or m.get("centro") or "").strip()
            nuevas.append({
                "asignatura": asig,
                "estudiante": nombre_nuevo or nombre_antiguo,
                "origen": item_origen if item_origen else origen_default,
                "universidad_origen": item_uni if item_uni else uni_default,
                "cuat": str(m.get("cuat") or "").strip(),
                "firmado": _normalize_firmado(m.get("firmado", "")),
                "link_la": str(m.get("link_la") or m.get("la") or "").strip(),
                "_origen_explicit": bool(item_origen),
                "_uni_explicit": bool(item_uni),
            })
        logger.debug("[materias] nuevas=%d asignaturas a guardar", len(nuevas))

        # ---- buscar filas existentes del alumno (escanea hasta max_row para cubrir filas añadidas) ----
        rows_student = []
        lookup_names = [x for x in [nombre_antiguo, nombre_nuevo] if x]
        if c_est:
            for candidate in lookup_names:
                cand_norm = normalize_str(candidate)
                rows = []
                for r in range(table_info.data_start, ws.max_row + 1):
                    v = ws.cell(row=r, column=c_est).value
                    if normalize_str(v) == cand_norm:
                        rows.append(r)
                if rows:
                    rows_student = rows
                    logger.debug("[materias] Filas existentes para '%s': %s", candidate, rows_student)
                    break

        # ---- editar filas existentes (misma fila) ----
        common = min(len(rows_student), len(nuevas))
        for i in range(common):
            r = rows_student[i]
            fila = nuevas[i]

            # leer valores actuales para NO machacar con vacío
            old_ori = ws.cell(row=r, column=c_ori).value if c_ori else None
            old_uni = ws.cell(row=r, column=c_uni).value if c_uni else None

            if c_asig:
                ws.cell(row=r, column=c_asig).value = fila["asignatura"]
            if c_est:
                ws.cell(row=r, column=c_est).value = fila["estudiante"]
            if c_cuat and cuat_default:
                ws.cell(row=r, column=c_cuat).value = cuat_default
            if c_fir:
                ws.cell(row=r, column=c_fir).value = firmado_default
            if c_la and la_default:
                ws.cell(row=r, column=c_la).value = la_default

            # Origen (país): solo si hay valor no vacío; si no, conservar
            if c_ori:
                v_ori = fila["origen"]
                if isinstance(v_ori, str):
                    v_ori = v_ori.strip()
                if v_ori:
                    ws.cell(row=r, column=c_ori).value = v_ori
                else:
                    ws.cell(row=r, column=c_ori).value = old_ori

            # Universidad: solo si hay valor no vacío; si no, conservar
            if c_uni:
                v_uni = fila["universidad_origen"]
                if isinstance(v_uni, str):
                    v_uni = v_uni.strip()
                if v_uni:
                    ws.cell(row=r, column=c_uni).value = v_uni
                else:
                    ws.cell(row=r, column=c_uni).value = old_uni

            logger.debug("[materias] Editada fila %d: %s", r, fila['asignatura'])

        # ---- eliminar filas sobrantes y compactar la tabla (sin insert/delete_rows) ----
        if len(rows_student) > len(nuevas):
            sobrantes = rows_student[len(nuevas):]
            cols_to_clear = [c for c in [c_asig, c_est, c_ori, c_uni, c_cuat, c_fir, c_la] if c]
            num_sobrantes = len(sobrantes)
            first_sobrante = sobrantes[0]

            # Última fila de la tabla que tiene algún dato en las columnas de materias
            last_data_row = table_info.data_start - 1
            for r in range(table_info.data_start, ws.max_row + 1):
                if any(
                    ws.cell(row=r, column=col).value not in (None, "")
                    for col in cols_to_clear
                ):
                    last_data_row = r

            if last_data_row >= first_sobrante + num_sobrantes:
                # Hay filas con datos debajo de los sobrantes: subirlas
                for r in range(first_sobrante, last_data_row - num_sobrantes + 1):
                    source = r + num_sobrantes
                    for col in cols_to_clear:
                        ws.cell(row=r, column=col).value = ws.cell(row=source, column=col).value
                    logger.debug("[materias] Subida fila %d -> %d", source, r)
                # Limpiar las filas duplicadas al final
                for r in range(last_data_row - num_sobrantes + 1, last_data_row + 1):
                    for col in cols_to_clear:
                        ws.cell(row=r, column=col).value = None
                    logger.debug("[materias] Limpiada cola fila %d", r)
            else:
                # No hay nada debajo: solo vaciar
                for r in sobrantes:
                    for col in cols_to_clear:
                        ws.cell(row=r, column=col).value = None
                    logger.debug("[materias] Vaciada fila sobrante %d", r)
        # ---- añadir filas nuevas ----
        if len(nuevas) > len(rows_student):
            pendientes = nuevas[len(rows_student):]
            # Buscar la última fila con valor en la columna de asignatura
            last_row_with_asig = table_info.data_start - 1
            if c_asig:
                for r in range(table_info.data_start, ws.max_row + 1):
                    v = ws.cell(row=r, column=c_asig).value
                    if v is not None and str(v).strip() != "":
                        last_row_with_asig = r
            insert_at = last_row_with_asig + 1
            if insert_at < table_info.data_start:
                insert_at = table_info.data_start

            # Columnas propias de la tabla de materias
            mat_cols = [c for c in [c_asig, c_est, c_ori, c_uni, c_cuat, c_fir, c_la] if c]

            # Buscar hueco: fila en la que las columnas de la tabla de materias estén vacías.
            # NO se insertan filas (eso desplaza otras tablas adyacentes).
            def _mat_cols_empty(row_num):
                for col in mat_cols:
                    v = ws.cell(row=row_num, column=col).value
                    if v is not None and str(v).strip() != "":
                        return False
                return True

            write_at = insert_at
            while write_at <= ws.max_row and not _mat_cols_empty(write_at):
                write_at += 1
            # Si write_at > ws.max_row la fila no existe aún: openpyxl la crea al escribir

            # Obtener universidad de origen de la última asignatura existente del alumno
            valor_uni_existente = None
            if rows_student and c_uni:
                last_row = rows_student[-1]
                valor_uni_existente = ws.cell(row=last_row, column=c_uni).value
                if valor_uni_existente:
                    valor_uni_existente = str(valor_uni_existente).strip()

            for i, fila in enumerate(pendientes):
                r = write_at + i
                valor_uni = fila.get("universidad_origen")
                if not valor_uni:
                    valor_uni = valor_uni_existente if valor_uni_existente else uni_default
                if c_asig: ws.cell(row=r, column=c_asig).value = fila["asignatura"]
                if c_est:  ws.cell(row=r, column=c_est).value  = fila["estudiante"]
                if c_ori:  ws.cell(row=r, column=c_ori).value  = fila["origen"] or ""
                if c_uni:
                    ws.cell(row=r, column=c_uni).value = valor_uni or ""
                    logger.debug("[materias] Escribiendo universidad en fila %d, col %d: %s", r, c_uni, valor_uni)
                else:
                    logger.warning("[materias] No se encontró columna para universidad en fila %d. Valor: %s", r, valor_uni)
                if c_cuat and cuat_default: ws.cell(row=r, column=c_cuat).value = cuat_default
                if c_fir:                   ws.cell(row=r, column=c_fir).value   = firmado_default
                if c_la and la_default:     ws.cell(row=r, column=c_la).value    = la_default
                logger.debug("[materias] Añadida fila %d: %s | universidad_origen=%s",
                             r, fila['asignatura'], valor_uni)

        # _make_backup(materias_path, tag="materias_before_update")  # Desactivado: no crear backup
        wb.save(materias_path)
        logger.info("[materias] Guardado OK")

    finally:
        wb.close()
