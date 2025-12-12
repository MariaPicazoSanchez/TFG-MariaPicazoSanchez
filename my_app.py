import os
import unicodedata
import streamlit as st
from ui import setup_session, sidebar_controls, render_new_user_form, show_map, render_stats_view, build_search_index
from utils import handle_open_pdf_query, handle_open_excel_query
from persistence import load_all_dataframes, get_materias_in_por_estudiante


def quitar_tildes(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def coincide_en_estudiantes(valor, texto_busqueda_normalizado: str) -> bool:
    """
    valor: lista de dicts (columna 'estudiantes')
    texto_busqueda_normalizado: ya en minúsculas y sin tildes.
    """
    if not isinstance(valor, list):
        return False

    for e in valor:
        # Nombres, email y ciudad del estudiante
        for campo in ("estudiante", "email", "ciudad"):
            val = quitar_tildes(str(e.get(campo, "")).lower())
            if texto_busqueda_normalizado in val:
                return True
    return False

def main():
    st.set_page_config(page_title="Movilidad UCLM", layout="wide", initial_sidebar_state="expanded" )
    # Manejo de query params al inicio
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
    

    setup_session()
    config = st.session_state["config"]

    # Asegura defaults (porque ahora los vas a leer ANTES de map_filters)
    if "selected_programs" not in st.session_state:
        st.session_state["selected_programs"] = {
            "Erasmus IN": False,
            "Erasmus OUT": False,
            "SICUE OUT": False,
        }
    if "only_erasmus_out_no_LA" not in st.session_state:
        st.session_state["only_erasmus_out_no_LA"] = False
    if "global_sheet" not in st.session_state:
        st.session_state["global_sheet"] = "Todas"

    global_sheet = st.session_state.get("global_sheet", None)
    dfs = load_all_dataframes(config, global_sheet)

    # Aplica filtros de programas y OUT sin LA (para que el índice sea coherente)
    selected = st.session_state.get("selected_programs", {})
    activos = [k for k, v in selected.items() if v]
    if isinstance(dfs, dict) and activos:
        dfs = {k: v for k, v in dfs.items() if k in activos}

    only_no_la = st.session_state.get("only_erasmus_out_no_LA", False)
    if only_no_la and isinstance(dfs, dict) and "Erasmus OUT" in dfs:
        df_out = dfs["Erasmus OUT"]
        if "link_LA" in df_out.columns:
            mask = df_out["link_LA"].isna() | (df_out["link_LA"].astype(str).str.strip() == "")
            dfs["Erasmus OUT"] = df_out[mask]

    # Índice listo ANTES de pintar el sidebar
    build_search_index(dfs)

    # A partir de aquí tu flujo normal:
    base_map = sidebar_controls()

    handle_open_pdf_query()
    handle_open_excel_query()

    st.title("Visualizador de Movilidad ESII")

    # ==============================================
    # MUESTRA DE MATERIAS IN POR ESTUDIANTE
    # ==============================================
    if dfs and isinstance(dfs, dict) and any(not df.empty for df in dfs.values()):
        materias_in_por_est = get_materias_in_por_estudiante(config)
    else:
        materias_in_por_est = {}
        st.info("No hay datos disponibles para mostrar. Por favor, revisa la configuración o selecciona otra hoja.")

    # Tipos disponibles según config y existencia de ficheros
    available_types = [
        k for k in ("Erasmus OUT", "Erasmus IN", "SICUE OUT")
        if config.get(k) and os.path.exists(config[k])
    ]

    if st.session_state.get("view", "map") == "new_user":
        render_new_user_form(available_types, config)
    elif st.session_state.get("view", "map") == "stats":
        render_stats_view()
    else:
        show_map(dfs, base_map, materias_in_por_est, activos, only_no_la)
        
if __name__ == "__main__":
    main()
