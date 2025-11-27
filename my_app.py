import os
import unicodedata
import streamlit as st
import requests
from map_view import show_map
from sidebar import setup_session, sidebar_controls
from new_user_view import render_new_user_form
from pdf import handle_open_pdf_query, handle_open_excel_query
from data_access_mobility import load_all_dataframes
from materias_in_loader import get_materias_in_por_estudiante
from map_export import create_static_map

def main():
    st.set_page_config(page_title="Movilidad UCLM", layout="wide", initial_sidebar_state="expanded" )

    setup_session()

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

    global_sheet = st.session_state.get("global_sheet", None)

    dfs = load_all_dataframes(config, global_sheet)

    # ==============================================
    # FILTRO POR PROGRAMAS SELECCIONADOS
    # ==============================================

    # selected_programs es el dict de booleans que rellenamos en render_filters
    selected = st.session_state.get("selected_programs", {})

    # Programas realmente activos (marcados)
    activos = [k for k, v in selected.items() if v]

    if isinstance(dfs, dict) and activos:
        # Si hay alguno activo → solo esos
        dfs = {k: v for k, v in dfs.items() if k in activos}
    # Si 'activos' está vacío → NO tocamos dfs → se ve todo (todos los programas)

    # ==============================================
    # Filtro: Erasmus OUT sin LA
    # ==============================================
    only_no_la = st.session_state.get("only_erasmus_out_no_LA", False)

    if only_no_la and isinstance(dfs, dict) and "Erasmus OUT" in dfs:
        df_out = dfs["Erasmus OUT"]

        # Usamos la columna REAL: link_LA
        if "link_LA" in df_out.columns:
            # Sin LA = NaN o cadena vacía (con solo espacios)
            mask = df_out["link_LA"].isna() | (df_out["link_LA"].astype(str).str.strip() == "")
            dfs["Erasmus OUT"] = df_out[mask]
        else:
            st.warning(
                "No se encontró la columna 'link_LA' en Erasmus OUT para aplicar el filtro de LA vacía. "
                f"Columnas disponibles: {list(df_out.columns)}"
            )
    # Filtro de búsqueda (nombre, apellidos, ciudad, país, universidad...)
    def filtrar_por_nombre(df, texto):
        texto = texto.lower()
        def contiene_nombre(estudiantes):
            return any(texto in e.get("estudiante", "").lower() for e in estudiantes)
        return df[df["estudiantes"].apply(contiene_nombre)]
    
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


    # ==============================================
    # Filtro de búsqueda (nombre, apellidos, ciudad, país, universidad...)
    # ==============================================
    search_text = st.session_state.get("search_text", "").strip()
    search_text_norm = quitar_tildes(search_text.lower())

    if search_text_norm and isinstance(dfs, dict):
        filtered_dfs = {}
        columnas_objetivo = {
            "nombre", "apellido", "apellido1", "apellido2", "apellidos",
            "estudiante", "full_name", "ciudad", "city", "pais", "país",
            "country", "universidad", "destino",
        }

        for key, df in dfs.items():
            if df is None or df.empty:
                filtered_dfs[key] = df
                continue

            mask = None

            # 1) Buscar dentro de la lista de estudiantes (nombres, emails, ciudad)
            if "estudiantes" in df.columns:
                m_est = df["estudiantes"].apply(
                    lambda v: coincide_en_estudiantes(v, search_text_norm)
                )
                mask = m_est

            # 2) Buscar también en las columnas “planas” (pais, ciudad, universidad, etc.)
            for col in df.columns:
                col_norm = str(col).strip().lower()
                if col_norm in columnas_objetivo:
                    serie = df[col].astype(str).str.lower().map(quitar_tildes)
                    m2 = serie.str.contains(search_text_norm, na=False)
                    mask = m2 if mask is None else (mask | m2)

            # 3) Aplicar máscara si existe
            if mask is not None:
                filtered_dfs[key] = df[mask]
            else:
                filtered_dfs[key] = df

        dfs = filtered_dfs



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
    else:
        show_map(dfs, base_map, materias_in_por_est)
    if st.session_state.get("view", "map") == "new_user":
        render_new_user_form(available_types, config)
    else:
        show_map(dfs, base_map, materias_in_por_est)

        html_map = st.session_state.get("last_map_html")

        with st.sidebar.expander("📤 Exportar mapa tal cual (PNG)"):
            if html_map is None:
                st.info("Todavía no hay mapa para exportar.")
            else:
                width = st.number_input("Ancho (px)", 600, 3000, 1200, 100)
                height = st.number_input("Alto (px)", 400, 3000, 800, 100)

                if st.button("Generar PNG", use_container_width=True):
                    try:
                        resp = requests.post(
                            "http://localhost:5000/screenshot",
                            json={
                                "html": html_map,
                                "width": int(width),
                                "height": int(height),
                            },
                            timeout=60,
                        )
                        resp.raise_for_status()
                        png_bytes = resp.content
                        st.session_state["last_map_png"] = png_bytes
                        st.success("PNG generado. Descárgalo abajo 👇")
                    except Exception as e:
                        st.error(f"No se pudo generar el PNG: {e}")

                png_bytes = st.session_state.get("last_map_png")
                if png_bytes:
                    st.download_button(
                        "Descargar mapa como PNG",
                        data=png_bytes,
                        file_name="mapa_movilidad.png",
                        mime="image/png",
                        use_container_width=True,
                    )
if __name__ == "__main__":
    main()
