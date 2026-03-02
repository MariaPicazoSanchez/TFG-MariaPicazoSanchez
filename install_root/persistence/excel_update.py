from __future__ import annotations

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
                            extra_min_matches: int = 0, extras_pool: Optional[set] = None) -> Optional[TableInfo]:
    wb = load_workbook(excel_path)
    try:
        for ws in _iter_sheets_preferred(wb):
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
                print(f"[detect] Tabla encontrada en hoja='{info.sheet_name}' header={info.header_row} "
                      f"datos={info.data_start}..{info.data_end} cols={info.cols}")
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
    print(f"[excel][set] row={excel_row} col={col} field={field_name} value={value!r}")
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
        print(f"[coords/ws] Programa '{programa}' detectado, se omite geocodificación.")
        return

    if _geolocator is None:
        print("[coords/ws] geopy no disponible; se omite geocodificación.")
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
            print(f"[coords/ws] Geocodificando: {query!r}")
            loc = _geolocator.geocode(query, timeout=10)
        except Exception as e:
            print(f"[coords/ws] Error geocodificando {query!r}: {e}")
            loc = None
        if loc:
            break

    if not loc:
        print("[coords/ws] No se encontraron coordenadas.")
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

    print(f"[coords/ws] Escritas coords lat={lat}, lon={lon}")

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
        print(f"[materias] Insertadas {count} filas en {insert_at} para no pisar contenido inferior.")


def update_student_in_excel(excel_path: str, row_index: str, idx: int, data: dict, old_email: str = None, old_nombre: str = None) -> bool:
    """
    Actualiza SOLO la misma fila del alumno dentro de la tabla de alumnos.
    No crea hojas, no reemplaza hojas, no elimina filas.
    """
    print("[update_student_in_excel] excel_path =", excel_path, "row_index =", row_index, "idx =", idx)

    try:
        table_info = _find_table_in_workbook(
            excel_path,
            STUDENTS_HEADER_ALIASES,
            STUDENTS_REQUIRED,
            extra_min_matches=1,
            extras_pool={"universidad_origen", "coordenadas", "email"},
        )
        if not table_info:
            print("[update_student_in_excel] No se encontró tabla de alumnos.")
            return False
    except Exception as e:
        print("[update_student_in_excel] Error localizando tabla:", e)
        print(traceback.format_exc())
        return False

    wb = None
    try:
        wb = load_workbook(excel_path)
        ws = wb[table_info.sheet_name]


        norm_to_col_1based, raw_headers = _build_header_maps_from_ws(ws, table_info.header_row - 1)
        print("[update_student_in_excel] headers detectados:", raw_headers)

        # Si es matriz dinámica, solo impedir editar el nombre, pero permitir editar otros campos
        is_dynamic_matrix = _students_table_is_dynamic_unique(ws, table_info)
        if is_dynamic_matrix:
            print("[update_student_in_excel] La tabla detectada de alumnos es una matriz dinámica (UNICOS). Solo se editarán campos distintos al nombre.")


        # Buscar solo la primera fila válida que coincida por email o nombre (robusto)
        row_found = None
        email_col = table_info.cols.get("email")
        email_target = (data.get("old_email") or old_email or "").strip().lower()
        if email_col and email_target:
            print("[update_student_in_excel] Buscando por email:", email_target)
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
                        print("[update_student_in_excel] Fila válida localizada por email:", r)
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
                            print("[update_student_in_excel] Fila válida localizada por nombre (robusto):", r)
                            break

        if row_found is None:
            print("[update_student_in_excel] ERROR: no se ha encontrado ninguna fila válida con ese email/nombre. No se añadirá ninguna fila nueva.")
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
            print("[update_student_in_excel] Aviso: no se pudieron recalcular coords:", e)

        # _make_backup(excel_path, tag="alumnos_before_update")  # Desactivado: no crear backup
        wb.save(excel_path)
        print("[update_student_in_excel] Guardado OK (misma fila, in-place).")
        return True

    except Exception as e:
        print("[update_student_in_excel] Error guardando in-place:", e)
        print(traceback.format_exc())
        return False
    finally:
        try:
            if wb is not None:
                wb.close()
        except Exception:
            pass


def actualizar_excel_materias_para_estudiante(materias_in, est, materias_path: str):
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
        print("[materias] No hay materias válidas; no se modifica Excel.")
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
            print(
                f"[materias] AVISO: No se detectó columna de universidad de origen. "
                f"Alias buscados={uni_aliases} | Cabeceras detectadas={raw_headers}"
            )
        else:
            print(f"[materias] Columna universidad detectada: c_uni={c_uni} header={raw_headers.get(c_uni)}")

        c_cuat = table_info.cols.get("cuat")
        c_fir  = table_info.cols.get("firmado")
        c_la   = table_info.cols.get("link_la")

        # ---- buscar filas existentes del alumno (primero old_nombre, luego nuevo) ----
        rows_student = []
        lookup_names = [x for x in [nombre_antiguo, nombre_nuevo] if x]
        if c_est:
            for candidate in lookup_names:
                cand_norm = normalize_str(candidate)
                rows = []
                for r in range(table_info.data_start, table_info.data_end + 1):
                    v = ws.cell(row=r, column=c_est).value
                    if normalize_str(v) == cand_norm:
                        rows.append(r)
                if rows:
                    rows_student = rows
                    print(f"[materias] Filas existentes para '{candidate}': {rows_student}")
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

            print(f"[materias] Editada fila {r}: {fila['asignatura']}")

        # ---- actualizar filas sobrantes del alumno (todos los campos del alumno) ----
        if len(rows_student) > len(nuevas):
            sobrantes = rows_student[len(nuevas):]
            for r in sobrantes:
                if c_est and nombre_nuevo:
                    ws.cell(row=r, column=c_est).value = nombre_nuevo
                if c_ori and origen_default:
                    ws.cell(row=r, column=c_ori).value = origen_default
                if c_uni and uni_default:
                    ws.cell(row=r, column=c_uni).value = uni_default
                if c_cuat and cuat_default:
                    ws.cell(row=r, column=c_cuat).value = cuat_default
                if c_fir:
                    ws.cell(row=r, column=c_fir).value = firmado_default
                if c_la and la_default:
                    ws.cell(row=r, column=c_la).value = la_default
                print(f"[materias] Actualizada fila sobrante {r}: nombre={nombre_nuevo}, cuat={cuat_default}, firmado={firmado_default}")
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

            _ensure_rows_for_append(ws, insert_at, len(pendientes))

            # Obtener universidad de origen de la última asignatura existente del alumno
            valor_uni_existente = None
            if rows_student and c_uni:
                last_row = rows_student[-1]
                valor_uni_existente = ws.cell(row=last_row, column=c_uni).value
                if valor_uni_existente:
                    valor_uni_existente = str(valor_uni_existente).strip()

            for i, fila in enumerate(pendientes):
                r = insert_at + i
                # Forzar universidad_origen a tener siempre valor:
                # 1. Si el alumno ya tenía asignaturas, copiar el valor de la última
                # 2. Si no, usar el valor por defecto
                valor_uni = fila.get("universidad_origen")
                if not valor_uni:
                    valor_uni = valor_uni_existente if valor_uni_existente else uni_default
                if c_asig: ws.cell(row=r, column=c_asig).value = fila["asignatura"]
                if c_est:  ws.cell(row=r, column=c_est).value  = fila["estudiante"]
                if c_ori:  ws.cell(row=r, column=c_ori).value  = fila["origen"] or ""
                # Escribir SIEMPRE la universidad detectada si hay columna
                if c_uni:
                    ws.cell(row=r, column=c_uni).value = valor_uni or ""
                    print(f"[materias] DEBUG: Escribiendo universidad en fila {r}, col {c_uni}: {valor_uni}")
                else:
                    print(f"[materias] ERROR: No se encontró columna para universidad en fila {r}. Valor: {valor_uni}")
                if c_cuat and cuat_default: ws.cell(row=r, column=c_cuat).value = cuat_default
                if c_fir:                   ws.cell(row=r, column=c_fir).value   = firmado_default
                if c_la and la_default:     ws.cell(row=r, column=c_la).value    = la_default
                print(f"[materias] Añadida fila {r}: {fila['asignatura']} | universidad_origen={valor_uni}")

        # _make_backup(materias_path, tag="materias_before_update")  # Desactivado: no crear backup
        wb.save(materias_path)
        print("[materias] Guardado OK")

    finally:
        wb.close()
