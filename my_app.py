import os
import streamlit as st
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from new_user_view import render_new_user_form
from pdf import handle_open_pdf_query, handle_open_excel_query
from data_access_mobility import load_all_dataframes
from materias_in_loader import get_materias_in_por_estudiante

def main():
    st.set_page_config(page_title="Movilidad UCLM", layout="wide", initial_sidebar_state="expanded" )

    setup_session()

    # ✅ NUEVO: Detecta si viene de un guardado y limpia caché
    try:
        params = st.query_params
        clear_cache_flag = params.get("clear_cache", None)
        saved_flag = params.get("student_saved", None)
    except Exception:
        params = st.experimental_get_query_params()
        clear_cache_flag = params.get("clear_cache", [None])[0] if params.get("clear_cache") else None
        saved_flag = params.get("student_saved", [None])[0] if params.get("student_saved") else None

    # Si viene del guardado, limpia caché
    if clear_cache_flag == "1":
        st.cache_data.clear()

    if saved_flag == "1":
        st.success("✅ Alumno guardado correctamente. Los datos se han actualizado.")
        st.rerun()
    elif saved_flag == "0":
        st.error("❌ No se pudieron guardar los cambios.")

    # A partir de aquí tu flujo normal:
    base_map = sidebar_controls()
    config = st.session_state["config"]

    handle_open_pdf_query()
    handle_open_excel_query()

    st.title("Visualizador de Movilidad ESII")

    global_sheet = st.session_state.get("global_sheet", "Todas")

    dfs = load_all_dataframes(config, global_sheet)
    if dfs and isinstance(dfs, dict) and any(not df.empty for df in dfs.values()):
        materias_in_por_est = get_materias_in_por_estudiante(config)
    else:
        materias_in_por_est = {}
        st.info("No hay datos disponibles para mostrar. Por favor, revisa la configuración o selecciona otra hoja.")

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
