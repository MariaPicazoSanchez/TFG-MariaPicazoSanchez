import streamlit as st
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from popup_templates import generate_dynamic_popup
from data_access import load_erasmus_in, load_sicue_out, load_erasmus_out


def load_dataframes(config):
    """Carga los DataFrames desde las rutas guardadas (OUT/IN/SICUE)."""
    dfs = {}

    erasmus_out_path = config.get("Erasmus OUT")
    if erasmus_out_path:
        try:
            dfs["Erasmus OUT"] = load_erasmus_out(erasmus_out_path)
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar Erasmus OUT: {e}")

    erasmus_in_path = config.get("Erasmus IN")
    if erasmus_in_path:
        try:
            dfs["Erasmus IN"] = load_erasmus_in(erasmus_in_path)
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar Erasmus IN: {e}")

    sicue_out_path = config.get("SICUE OUT")
    if sicue_out_path:
        try:
            dfs["SICUE OUT"] = load_sicue_out(sicue_out_path)
        except Exception as e:
            st.warning(f"⚠️ No se pudo cargar SICUE OUT: {e}")

    return dfs


def main():
    st.set_page_config(page_title="Movilidad UCLM", layout="wide")
    st.title("Visualizador de Movilidad ESII")

    setup_session()
    base_map = sidebar_controls()

    dfs = load_dataframes(st.session_state["config"])  # que cargue OUT/IN/SICUE si hay ruta
    show_map(dfs, base_map)


if __name__ == "__main__":
    
    main()
