"""
Helpers de nivel celda para leer y escribir en hojas openpyxl.

Exporta:
  - FIELD_ALIASES            — alias de campos de formulario → columnas Excel
  - _name_to_scalar          — convierte valor de celda a str escalar
  - _is_invalid_student_name_cell
  - _students_table_is_dynamic_unique
  - _set_ws_cell_if_field_exists
  - _split_full_name
  - _normalize_firmado
  - _ensure_rows_for_append
"""


import logging
from typing import Any

from ._excel_tables import (
    _find_col_in_ws_by_aliases,
    _row_is_empty_ws,
)

logger = logging.getLogger("movilidad_persistence")


# ─────────────────────────────────────────────────────────────────────────────
# Alias de campos del formulario -> columnas posibles en Excel
# ─────────────────────────────────────────────────────────────────────────────

FIELD_ALIASES: dict[str, list[str]] = {
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
        "duracion meses", "duracion_meses", "Duración (meses)", "Duración meses", "Duración",
    ],
    "gestion_LA": [
        "Gestion LA", "gestion_LA", "Gestión LA",
    ],
    "coordinador_destino": [
        "Coordinador en destino", "coordinador_destino", "Coordinador destino", "Coordinador de destino",
    ],
    "link_la": [
        "LA", "link_la", "Learning agreement", "Learning Agreement",
    ],
    "link_plan": [
        "Plan de estudios", "link_plan", "Plan estudios", "Plan",
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


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de nombre
# ─────────────────────────────────────────────────────────────────────────────

def _name_to_scalar(value: Any) -> str:
    while isinstance(value, (list, tuple)) and len(value) > 0:
        value = value[0]
    if value is None:
        return ""
    s = str(value).strip()
    if s.startswith("[") and s.endswith("]"):
        s = s.strip("[]").strip().strip("'").strip('"').strip()
    return s


def _is_invalid_student_name_cell(v: Any) -> bool:
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
    c_nombre = table_info.cols.get("nombre")
    if not c_nombre:
        return False
    r = table_info.data_start
    if r > ws.max_row:
        return False
    v = ws.cell(row=r, column=c_nombre).value
    s = str(v or "").strip().upper()
    return s.startswith("=UNICOS(") or s.startswith("=UNIQUE(")


def _split_full_name(full_name: str) -> tuple[str, str, str]:
    full_name = (full_name or "").strip()
    if not full_name:
        return "", "", ""
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], " ".join(parts[2:])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de celda
# ─────────────────────────────────────────────────────────────────────────────

def _set_ws_cell_if_field_exists(
    ws, excel_row: int, norm_to_col_1based: dict[str, int], field_name: str, data: dict
) -> bool:
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


def _normalize_firmado(v: Any) -> str:
    if isinstance(v, bool):
        return "x" if v else ""
    s = str(v or "").strip().lower()
    return "x" if s in ("x", "1", "s", "si", "sí", "true", "t") else ""


def _ensure_rows_for_append(ws, insert_at: int, count: int) -> None:
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

