"""
Agregador principal: carga todos los DataFrames de movilidad aplicando
el filtro de hoja y el lazy loading selectivo por programa.
"""

from __future__ import annotations

import os

import pandas as pd

from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT
from persistence.sheets_helpers import sheets_for, resolve_sheet

from ._common import _norm_colname, _read_table
from .erasmus_out import load_erasmus_out
from .erasmus_in import load_erasmus_in
from .sicue_out import load_sicue_out


def load_mobility_any(path: str, sheet_name: str | None = None) -> pd.DataFrame:
    """Detecta el tipo de programa por las cabeceras y delega al loader correcto."""
    head = _read_table(path, sheet_name=sheet_name, nrows=1)
    cols = {_norm_colname(c) for c in head.columns}

    if "universidad origen" in cols or "cuatrimestre" in cols or "cuatirmestre" in cols:
        return load_erasmus_in(path, sheet_name=sheet_name)
    if "coordinador en destino" in cols or "gestion la" in cols or "gestión la" in cols or "ciudad" in cols:
        return load_sicue_out(path, sheet_name=sheet_name)
    return load_erasmus_out(path, sheet_name=sheet_name)


def load_all_dataframes(
    config: dict,
    global_sheet: str,
    programs_to_load: list[str] | None = None,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """
    Carga DataFrames por tipo aplicando el filtro global de hoja.

    - 'Todas'         → usa los loaders sin filtro de hoja.
    - Hoja concreta   → lee solo esa hoja de cada Excel.

    Args:
        config:           Configuración con rutas a Excel.
        global_sheet:     Hoja a cargar ('Todas' o nombre específico).
        programs_to_load: Lista de programas a cargar; None = todos.

    Returns:
        (dfs, messages) donde dfs es {programa: DataFrame} y
        messages es una lista de avisos/errores para mostrar en la UI.
    """
    dfs: dict[str, pd.DataFrame] = {}
    messages: list[str] = []

    if programs_to_load is None:
        programs_to_load = [PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT]

    mapping = [
        (PROGRAM_ERASMUS_OUT, config.get(PROGRAM_ERASMUS_OUT), load_erasmus_out),
        (PROGRAM_ERASMUS_IN,  config.get(PROGRAM_ERASMUS_IN),  load_erasmus_in),
        (PROGRAM_SICUE_OUT,   config.get(PROGRAM_SICUE_OUT),   load_sicue_out),
    ]
    sheets_map = (config or {}).get("sheets", {}) or {}

    for type_name, path, loader in mapping:
        if type_name not in programs_to_load:
            continue
        if not path:
            continue

        try:
            ext = os.path.splitext(path)[1].lower()

            if global_sheet and global_sheet != "Todas":
                if ext == ".csv":
                    continue  # CSV no tiene hojas

                candidates = sheets_map.get(type_name) or sheets_for(path)
                wanted = resolve_sheet(global_sheet, candidates)
                if not wanted:
                    messages.append(
                        f"ℹ️ {type_name}: hoja '{global_sheet}' no encontrada "
                        f"en {os.path.basename(path)}"
                    )
                    continue

                try:
                    df = loader(path, sheet_name=wanted, _messages=messages)
                except TypeError:
                    df = _read_table(path, sheet_name=wanted)
            else:
                df = loader(path, _messages=messages)

            if df is not None and len(df):
                dfs[type_name] = df

        except Exception as e:
            # SICUE OUT a veces lanza errores de indexación sobre hojas vacías; suprimir
            if type_name == PROGRAM_SICUE_OUT and (
                "single positional indexer is out-of-bounds" in str(e)
                or "indexer" in str(e)
            ):
                pass
            else:
                messages.append(f"⚠️ No se pudo cargar {type_name}: {e}")

    return dfs, messages
