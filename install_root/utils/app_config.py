import os
import json as _json
import streamlit as st
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT


def _get_cfg_path() -> str:
    path = os.getenv("APP_CONFIG_PATH")
    if path:
        return path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config.json")


def _read_cfg() -> dict:
    try:
        with open(_get_cfg_path(), "r", encoding="utf-8") as _f:
            return _json.load(_f)
    except Exception:
        return {}


def save_course(course: str) -> None:
    """Guarda el curso seleccionado en config.json."""
    import sys
    try:
        path = _get_cfg_path()
        existing = _read_cfg()
        existing["curso"] = course
        with open(path, "w", encoding="utf-8") as _f:
            _json.dump(existing, _f, indent=2)
        print(f"[save_course] OK: curso={course!r} -> {path}", file=sys.stderr)
    except Exception as e:
        print(f"[save_course] ERROR: {e} (path={_get_cfg_path()!r})", file=sys.stderr)


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
        import sys
        cfg = _read_cfg()
        saved = cfg.get("curso")
        print(f"[init_session] curso leído={saved!r} de {_get_cfg_path()!r}", file=sys.stderr)
        st.session_state["global_sheet"] = saved  # None si no hay guardado
    
    if "view" not in st.session_state:
        st.session_state["view"] = "map"


def get_query_param(key: str, default: str | None = None) -> str | None:
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


def get_config_mtimes(cfg: dict) -> tuple:
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


def get_active_programs() -> list[str]:
    """Obtiene la lista de programas actualmente seleccionados."""
    selected = st.session_state.get("selected_programs", DEFAULT_PROGRAMS)
    return [prog for prog, is_selected in selected.items() if is_selected]


def get_available_program_types(config: dict) -> list[str]:
    """Obtiene los tipos de programas que tienen archivos configurados y existentes."""
    return [
        prog for prog in AVAILABLE_PROGRAMS
        if config.get(prog) and os.path.exists(config[prog])
    ]
