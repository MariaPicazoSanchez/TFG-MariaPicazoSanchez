from .sheets_helpers import sheets_for


# Lazy wrapper for load_all_dataframes to avoid importing Streamlit-heavy module on package import
def load_all_dataframes(cfg, sheet, programs_to_load=None):
    from .data_access_mobility import load_all_dataframes as _f
    return _f(cfg, sheet, programs_to_load=programs_to_load)


# Lazy wrappers for functions that import Streamlit or heavy modules at import time
def append_user_to_excel(*args, **kwargs):
    from .data_insert import append_user_to_excel as _f
    return _f(*args, **kwargs)


def first_sheet_name(*args, **kwargs):
    from .data_insert import first_sheet_name as _f
    return _f(*args, **kwargs)


def actualizar_excel_materias_para_estudiante(*args, **kwargs):
    from .excel_update import actualizar_excel_materias_para_estudiante as _f
    return _f(*args, **kwargs)


def update_student_in_excel(*args, **kwargs):
    from .excel_update import update_student_in_excel as _f
    return _f(*args, **kwargs)


def get_materias_in_por_estudiante(*args, **kwargs):
    from .materias_in_loader import get_materias_in_por_estudiante as _f
    return _f(*args, **kwargs)


__all__ = [
    'load_all_dataframes', 'append_user_to_excel', 'first_sheet_name', 'sheets_for',
    'actualizar_excel_materias_para_estudiante', 'update_student_in_excel', 'get_materias_in_por_estudiante',
]