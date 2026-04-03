from .sheets_helpers import sheets_for
from .excel_update import (
    actualizar_excel_materias_para_estudiante,
    update_student_in_excel,
)
from .materias_in_loader import get_materias_in_por_estudiante, get_asignaturas_catalog

# Lazy wrappers solo para módulos que importan Streamlit en el nivel de módulo
# (data_insert y loaders usan st.cache_data / st.query_params)

def load_all_dataframes(cfg, sheet, programs_to_load=None):
    from .data_access_mobility import load_all_dataframes as _f
    return _f(cfg, sheet, programs_to_load=programs_to_load)


def append_user_to_excel(*args, **kwargs):
    from .data_insert import append_user_to_excel as _f
    return _f(*args, **kwargs)


def first_sheet_name(*args, **kwargs):
    from ._insert_helpers import first_sheet_name as _f
    return _f(*args, **kwargs)


__all__ = [
    'load_all_dataframes', 'append_user_to_excel', 'first_sheet_name', 'sheets_for',
    'actualizar_excel_materias_para_estudiante', 'update_student_in_excel',
    'get_materias_in_por_estudiante', 'get_asignaturas_catalog',
]