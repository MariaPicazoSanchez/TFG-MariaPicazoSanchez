import os
import streamlit as st
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from new_user_view import render_new_user_form

from pdf import handle_open_pdf_query
from data_access import load_all_dataframes

def main():
    # Config inicial de Streamlit
    st.set_page_config(page_title="Movilidad UCLM", layout="wide", initial_sidebar_state="expanded")

    # Handler de ?open_pdf=...
    handle_open_pdf_query()

    st.title("Visualizador de Movilidad ESII")

    # Estado + Sidebar primero (para que lea selects/filtros)
    setup_session()
    base_map = sidebar_controls()

    # Cargar datos respetando filtro global de hoja
    config = st.session_state["config"]
    global_sheet = st.session_state.get("global_sheet", "Todas")
    dfs = load_all_dataframes(config, global_sheet)

    # Tipos disponibles para “Crear usuario” (por existencia de Excel)
    available_types = [k for k in ("Erasmus OUT", "Erasmus IN", "SICUE OUT")
                       if config.get(k) and os.path.exists(config[k])]

    # Router simple de vistas
    if st.session_state.get("view", "map") == "new_user":
        render_new_user_form(available_types, config)
    else:
        show_map(dfs, base_map)

if __name__ == "__main__":
    main()
