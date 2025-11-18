import os
import json
import streamlit as st
from data_insert import export_materias_in_excel
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from new_user_view import render_new_user_form
from pdf import handle_open_pdf_query, handle_open_excel_query
from data_access_mobility import load_all_dataframes
from materias_in_loader import get_materias_in_por_estudiante
from popup_templates import _normalize_estudiantes
# OJO: de momento NO usamos handle_save_student_query ni components.html

def main():
    # Configuración básica de la página
    st.set_page_config(
        page_title="Movilidad UCLM",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Estado inicial, sidebar, etc.
    setup_session()
    base_map = sidebar_controls()

    config = st.session_state["config"]

    # Gestionar enlaces que abren PDF/Excel (esto ya lo tenías)
    handle_open_pdf_query()
    handle_open_excel_query()

    st.title("Visualizador de Movilidad ESII")

    global_sheet = st.session_state.get("global_sheet", "Todas")

    # Cargar datos y materias
    dfs = load_all_dataframes(config, global_sheet)
    materias_in_por_est = get_materias_in_por_estudiante(config)

    available_types = [
        k for k in ("Erasmus OUT", "Erasmus IN", "SICUE OUT")
        if config.get(k) and os.path.exists(config[k])
    ]

    # Vista actual: mapa o formulario de nuevo usuario
    if st.session_state.get("view", "map") == "new_user":
        render_new_user_form(available_types, config)
    else:
        show_map(dfs, base_map, materias_in_por_est)

    # Si en el futuro volvemos a usar guardados "normales", esto no molesta
    if st.session_state.pop("_student_saved", False):
        st.success("Alumno guardado correctamente.")

if __name__ == "__main__":
    main()
