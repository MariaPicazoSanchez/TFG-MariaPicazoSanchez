"""
Paquete de loaders de movilidad estudiantil.
Re-exporta las funciones públicas de cada módulo.
"""

from ._common import (
    get_universities_from_coords_sheet,
    get_universities_from_sicue_data,
    filter_students_with_coords,
)
from .erasmus_out import load_erasmus_out
from .erasmus_in import load_erasmus_in
from .sicue_out import load_sicue_out
from .all_dataframes import load_all_dataframes, load_mobility_any

__all__ = [
    "load_all_dataframes",
    "load_mobility_any",
    "load_erasmus_out",
    "load_erasmus_in",
    "load_sicue_out",
    "get_universities_from_coords_sheet",
    "get_universities_from_sicue_data",
    "filter_students_with_coords",
]
