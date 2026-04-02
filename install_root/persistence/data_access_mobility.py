"""
Módulo de compatibilidad hacia atrás.
El código real vive en persistence/loaders/.

Todos los imports externos que apunten a este módulo siguen funcionando.
"""

from .loaders import (  # noqa: F401
    load_all_dataframes,
    load_mobility_any,
    load_erasmus_out,
    load_erasmus_in,
    load_sicue_out,
    get_universities_from_coords_sheet,
    get_universities_from_sicue_data,
    filter_students_with_coords,
)
