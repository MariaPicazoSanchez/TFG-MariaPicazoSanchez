from __future__ import annotations

import re
import streamlit as st
from constants import PROGRAM_ERASMUS_IN, PROGRAM_ERASMUS_OUT, PROGRAM_SICUE_OUT

def rerun() -> None:
    st.rerun()

def filter_button(label: str, program_key: str, key: str, container: st.delta_generator.DeltaGenerator) -> None:
    """
    label: texto que se muestra en el botón
    program_key: nombre en el diccionario selected_programs
    key: key de streamlit (para st.button)
    container: el col / contenedor donde pintar el botón
    """
    is_active = st.session_state["selected_programs"].get(program_key, False)

    # Cambiamos el aspecto según esté activo o no.
    # Aquí uso negrita + emoji, tú puedes añadir CSS para ponerlo rojo, etc.
    btn_label = label if not is_active else f"✅ {label}"

    with container:
        if st.button(btn_label, width='stretch', key=key):
            # toggle
            st.session_state["selected_programs"][program_key] = not is_active
            st.rerun()

def _latest_sheet_name(names: list[str]) -> str | None:
    """Devuelve el nombre de hoja 'más nueva', por ejemplo 2024/2025 > 2023/2024."""
    if not names:
        return None

    def key(name):
        # intenta patrón tipo '2024/2025'
        m = re.search(r'(\d{4})\s*/\s*(\d{4})', name)
        if m:
            return (int(m.group(1)), int(m.group(2)))
        # si no, primer año de 4 cifras que encuentre
        m = re.search(r'(\d{4})', name)
        if m:
            return (int(m.group(1)), 0)
        # si no tiene año, se va al principio
        return (0, 0)

    return max(names, key=key)


def render_filters_map(unique_sheets: list[str]) -> str:
    import streamlit as st
    """
    Pinta los filtros de la barra lateral.
    - unique_sheets: lista de hojas disponibles (cursos)
    """
    # --- ESTADO DE PROGRAMAS SELECCIONADOS ---
    if "selected_programs" not in st.session_state:
            st.session_state["selected_programs"] = {
            PROGRAM_ERASMUS_IN: False,
            PROGRAM_ERASMUS_OUT: False,
            PROGRAM_SICUE_OUT: False,
        }
    if "only_erasmus_out_no_LA" not in st.session_state:
        st.session_state["only_erasmus_out_no_LA"] = False
            
    def toggle(program: str) -> None:
        d = st.session_state["selected_programs"]

        # cambiamos solo el pulsado
        d[program] = not d.get(program, False)

        main_keys = [PROGRAM_ERASMUS_IN, PROGRAM_ERASMUS_OUT, PROGRAM_SICUE_OUT]

        # si los 3 están activos, es como no filtrar nada -> los apagamos
        if all(d.get(k, False) for k in main_keys):
            for k in main_keys:
                d[k] = False

        st.session_state["selected_programs"] = d


    if "filter_only_no_LA" not in st.session_state:
        st.session_state["filter_only_no_LA"] = False

    if "global_sheet" not in st.session_state:
        st.session_state["global_sheet"] = "Todas"

    # ==========================
    #  SECCIÓN DE FILTROS
    # ==========================
    st.sidebar.header("Filtros")

    # --- SELECCIÓN DE CURSO (HOJA) ---
    options = unique_sheets[:]
    default_sheet = _latest_sheet_name(unique_sheets) or (options[0] if options else "Sin hojas")
    
    # si aún no hay global_sheet, pon la más nueva
    if "global_sheet" not in st.session_state:
        st.session_state["global_sheet"] = default_sheet

    current = st.session_state.get("global_sheet", default_sheet)
    if current not in options and options:
            current = default_sheet

    idx = options.index(current) if (options and current in options) else 0

    col_lbl, col_sel = st.sidebar.columns([1, 3], gap="small")
    with col_lbl:
        st.markdown("**Curso**")
    with col_sel:
        choice = st.selectbox(
            "Curso",
            options if options else ["Sin hojas"],
            index=idx,
            key="global_sheet_select",
            label_visibility="collapsed",
        )

    if options:
        st.session_state["global_sheet"] = choice
    else:
        st.session_state["global_sheet"] = None


    # --- ERASMUS ---
    c1, c2, c3 = st.sidebar.columns([1.2, 1, 1], gap="small")
    with c1:
        st.markdown("**Erasmus:**")
    # Erasmus IN
    with c2:
        is_active_in = st.session_state["selected_programs"][PROGRAM_ERASMUS_IN]
        if st.button(
            "IN",
            width='stretch',
            key="btn_erasmus_in",
            type="primary" if is_active_in else "secondary",   # color sólo si activo
        ):
            toggle(PROGRAM_ERASMUS_IN)
            st.rerun()

    # Erasmus OUT
    with c3:
        is_active_out = st.session_state["selected_programs"][PROGRAM_ERASMUS_OUT]
        if st.button(
            "OUT",
            width='stretch',
            key="btn_erasmus_out",
            type="primary" if is_active_out else "secondary",
        ):
            toggle(PROGRAM_ERASMUS_OUT)
            st.rerun()


    # Segunda fila: OUT sin LA
    c_la_label, c_la_btn = st.sidebar.columns([1.2, 2], gap="small")
    with c_la_label:
        st.write("")

    is_only_no_la = st.session_state.get("only_erasmus_out_no_LA", False)

    with c_la_btn:
        if st.button(
            "OUT sin LA",
            width='stretch',
            key="btn_erasmus_out_no_la",
            type="primary" if is_only_no_la else "secondary",
        ):
            # SOLO togglear el flag; NO tocar selected_programs
            st.session_state["only_erasmus_out_no_LA"] = not is_only_no_la
            st.rerun()

    # --- SICUE ---
    c4, c5, _ = st.sidebar.columns([1.2, 1, 1], gap="small")
    with c4:
        st.markdown("**SICUE:**")
    with c5:
        is_active_sicue = st.session_state["selected_programs"][PROGRAM_SICUE_OUT]
        if st.button(
            "OUT",
            width='stretch',
            key="btn_sicue_out",
            type="primary" if is_active_sicue else "secondary",
        ):
            toggle(PROGRAM_SICUE_OUT)
            st.rerun()
            
    # Mapa base
    base_map = "OpenStreetMap"
    return base_map
