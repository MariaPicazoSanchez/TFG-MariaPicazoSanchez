import os
import streamlit as st
from typing import Dict, Tuple, List, Optional
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT


AVAILABLE_PROGRAMS = [PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT]
DEFAULT_PROGRAMS = {
    PROGRAM_ERASMUS_IN: False,
    PROGRAM_ERASMUS_OUT: False,
    PROGRAM_SICUE_OUT: False,
}


def init_session_defaults() -> None:
    """Inicializa el estado de la sesión con valores por defecto."""
    if "data_version" not in st.session_state:
        st.session_state["data_version"] = 0
    
    if "selected_programs" not in st.session_state:
        st.session_state["selected_programs"] = DEFAULT_PROGRAMS.copy()
    
    if "only_erasmus_out_no_LA" not in st.session_state:
        st.session_state["only_erasmus_out_no_LA"] = False
    
    if "global_sheet" not in st.session_state:
        st.session_state["global_sheet"] = "Todas"
    
    if "view" not in st.session_state:
        st.session_state["view"] = "map"


def get_query_param(key: str, default: Optional[str] = None) -> Optional[str]:
    """Obtiene parámetro de consulta de forma segura, compatible con diferentes versiones de Streamlit."""
    try:
        params = st.query_params
        value = params.get(key)
        if value is None:
            return default
        if isinstance(value, list):
            return value[0] if value else default
        return value
    except AttributeError:
        # Fallback para versiones antiguas de Streamlit
        try:
            params = st.experimental_get_query_params()
            value = params.get(key, [default])
            return value[0] if value else default
        except Exception:
            return default


def get_config_mtimes(cfg: Dict) -> Tuple:
    """Obtiene los tiempos de modificación de los archivos Excel configurados para invalidación de caché.
    
    Args:
        cfg: Diccionario de configuración con rutas de archivos de programas
    
    Returns:
        Tupla de mtimes en orden estable (uno por programa)
    """
    mtimes = []
    for program in AVAILABLE_PROGRAMS:
        path = cfg.get(program)
        try:
            if path and os.path.exists(path):
                mtimes.append(os.path.getmtime(path))
            else:
                mtimes.append(None)
        except Exception:
            mtimes.append(None)
    return tuple(mtimes)


def get_active_programs() -> List[str]:
    """Obtiene la lista de programas actualmente seleccionados."""
    selected = st.session_state.get("selected_programs", DEFAULT_PROGRAMS)
    return [prog for prog, is_selected in selected.items() if is_selected]


def get_available_program_types(config: Dict) -> List[str]:
    """Obtiene los tipos de programas que tienen archivos configurados y existentes."""
    return [
        prog for prog in AVAILABLE_PROGRAMS
        if config.get(prog) and os.path.exists(config[prog])
    ]
