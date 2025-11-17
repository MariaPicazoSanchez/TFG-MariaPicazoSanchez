import os
import streamlit as st
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from new_user_view import render_new_user_form
from pdf import handle_open_pdf_query
from data_access_mobility import load_all_dataframes
from materias_in_loader import get_materias_in_por_estudiante

def main():
    st.set_page_config(
        page_title="Movilidad UCLM",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    handle_open_pdf_query()

    st.title("Visualizador de Movilidad ESII")

    setup_session()
    base_map = sidebar_controls()

    config = st.session_state["config"]
    global_sheet = st.session_state.get("global_sheet", "Todas")

    dfs = load_all_dataframes(config, global_sheet)
    materias_in_por_est = get_materias_in_por_estudiante(config)

    available_types = [
        k for k in ("Erasmus OUT", "Erasmus IN", "SICUE OUT")
        if config.get(k) and os.path.exists(config[k])
    ]

    if st.session_state.get("view", "map") == "new_user":
        render_new_user_form(available_types, config)
    else:
        show_map(dfs, base_map, materias_in_por_est)

if __name__ == "__main__":
    main()
