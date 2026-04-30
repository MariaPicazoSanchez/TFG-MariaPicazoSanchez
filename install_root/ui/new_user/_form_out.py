"""
Formulario de nuevo estudiante para Erasmus OUT.
"""


import streamlit as st

from persistence.data_access_mobility import get_universities_from_coords_sheet

from ._helpers import (
    COUNTRY_OPTIONS,
    _FILTER_ALL,
    file_picker_button,
    get_university_country_map,
    get_university_responsable_map,
)


def render_erasmus_out_form(config: dict, asignaturas_catalog: list) -> dict:
    """
    Renderiza el formulario de Erasmus OUT.
    Devuelve un dict con: nombre, apellidos, destino_origen, email, extra.
    """
    xlsx_path = config.get("Erasmus OUT", "")
    # Formato Erasmus OUT sin cabecera: col0=Universidad, col1=País, col2=Coordenada.
    # Si el Excel incluye fila de cabecera, se detecta automáticamente.
    universidades_out   = get_universities_from_coords_sheet(xlsx_path, default_col_uni=0, default_col_pais=1)
    uni_country_map_out = get_university_country_map(xlsx_path, default_col_uni=0, default_col_pais=1)
    resp_map_out        = get_university_responsable_map(xlsx_path, default_col_uni=0, default_col_pais=1)

    nombre = apellidos = destino_origen = email = ""
    extra: dict = {}

    with st.container(border=True):
        col1, col2 = st.columns(2)

        # Necesitamos leer destino_origen antes de renderizar col1 para el autocomplete de país.
        # Leemos el valor del session_state previo.
        destino_origen = st.session_state.get("nu_destino_origen", "")
        pais_sugerido = uni_country_map_out.get((destino_origen or "").strip(), "")
        if pais_sugerido and pais_sugerido in COUNTRY_OPTIONS:
            if st.session_state.get("nu_pais_out", "") != pais_sugerido:
                st.session_state["nu_pais_out"] = pais_sugerido

        with col1:
            nombre = st.text_input("Nombre", key="nu_nombre")
            email  = st.text_input("Email",  key="nu_email")

        with col2:
            apellidos = st.text_input("Apellidos", key="nu_apellidos")
            destino_origen = st.selectbox(
                "Destino (universidad)",
                options=[""] + universidades_out,
                key="nu_destino_origen",
                help="Selecciona una universidad o escribe una nueva",
                accept_new_options=True,
            )
            # Actualizar país al cambiar universidad
            if destino_origen:
                pais_sugerido = uni_country_map_out.get(destino_origen.strip(), "")
                if pais_sugerido and pais_sugerido in COUNTRY_OPTIONS:
                    if st.session_state.get("nu_pais_out") != pais_sugerido:
                        st.session_state["nu_pais_out"] = pais_sugerido

        col1, col2 = st.columns(2)
        with col1:
            extra["pais_out"] = st.selectbox("País", options=COUNTRY_OPTIONS, key="nu_pais_out")

            dur_out_val = st.text_input("Duración (meses)", key="nu_dur_out")
            if dur_out_val and not dur_out_val.strip().isdigit():
                st.toast("⚠️ La duración debe ser un número", icon="⚠️")
                extra["dur_out"] = ""
            else:
                extra["dur_out"] = dur_out_val

            plan_col1, plan_col2 = st.columns([8, 1.5])
            with plan_col1:
                extra["plan_out"] = st.text_input(
                    "Propuesta alumno LA (ruta o enlace)", key="nu_plan_out"
                )
            with plan_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                file_picker_button("📁", "nu_plan_out", "nu_plan_out_browse", "Abrir explorador de archivos.")

            resp_auto = resp_map_out.get((destino_origen or "").strip(), "")
            extra["resp_prog"] = resp_auto
            if resp_auto:
                st.caption(f"Responsable: **{resp_auto}**")


        with col2:
            extra["curso"] = st.selectbox("Curso", options=["", "1", "2", "3", "4"], key="nu_curso")
            extra["ciudad"] = st.text_input("Ciudad", key="nu_ciudad")

            la_col1, la_col2 = st.columns([8, 1.5])
            with la_col1:
                extra["la_out"] = st.text_input("LA (enlace o ruta)", key="nu_la_out_opt")
            with la_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                file_picker_button(
                    "📁", "nu_la_out_opt", "nu_la_out_opt_browse",
                    "Abrir explorador de archivos.", file_filter=_FILTER_ALL
                )
            
            
    return {
        "nombre": nombre,
        "apellidos": apellidos,
        "destino_origen": destino_origen,
        "email": email,
        "extra": extra,
    }
