"""
Formulario de nuevo estudiante para SICUE OUT.
"""

from __future__ import annotations

import streamlit as st

from persistence.data_access_mobility import get_universities_from_sicue_data

from ._helpers import _FILTER_ALL, _FILTER_PDF_WORD, file_picker_button


def render_sicue_out_form(config: dict, asignaturas_catalog: list) -> dict:
    """
    Renderiza el formulario de SICUE OUT.
    Devuelve un dict con: nombre, apellidos, destino_origen, email, extra.
    """
    from domain import ESTADOS_FIRMA, CITIES_ES

    xlsx_path = config.get("SICUE OUT", "")
    universidades_sicue, ciudad_map_sicue, coords_map_sicue = (
        get_universities_from_sicue_data(xlsx_path)
        if xlsx_path else ([], {}, {})
    )

    nombre = apellidos = destino_origen = email = ""
    extra: dict = {}

    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", key="nu_nombre")
            email  = st.text_input("Email",  key="nu_email")
        with col2:
            apellidos = st.text_input("Apellidos", key="nu_apellidos")
            destino_origen = st.selectbox(
                "Destino (universidad)",
                options=[""] + universidades_sicue,
                key="nu_destino_origen",
                help="Selecciona una universidad ya conocida o escribe una nueva",
                accept_new_options=True,
            )
            # Autocompletar ciudad
            if destino_origen:
                ciudad_sugerida = ciudad_map_sicue.get(destino_origen.strip(), "")
                if ciudad_sugerida and st.session_state.get("nu_ciudad", "") != ciudad_sugerida:
                    st.session_state["nu_ciudad"] = ciudad_sugerida

        # Guardar coordenadas conocidas para usarlas al guardar
        coords_conocidas = coords_map_sicue.get((destino_origen or "").strip())
        st.session_state["_sicue_coords_known"] = coords_conocidas

        col1, col2 = st.columns(2)
        with col1:
            extra["ciudad_sicue"] = st.selectbox(
                "Ciudad",
                options=CITIES_ES,
                index=0,
                help="Si no se encuentran coordenadas por la universidad, se usará esta ciudad.",
                key="nu_ciudad",
            )

            dur_sicue_val = st.text_input("Duración (meses)", key="nu_dur_sicue")
            if dur_sicue_val and not dur_sicue_val.strip().isdigit():
                st.toast("La duración debe ser un número", icon="⚠️")
                extra["dur_sicue"] = ""
            else:
                extra["dur_sicue"] = dur_sicue_val

            la_col1, la_col2 = st.columns([8, 1.5])
            with la_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                file_picker_button(
                    "📁", "nu_la_sicue", "nu_la_sicue_browse",
                    "Abrir explorador de archivos.", file_filter=_FILTER_ALL
                )
            with la_col1:
                extra["la_in"] = st.text_input("LA (enlace o ruta)", key="nu_la_sicue")

        with col2:
            extra["estado_firmas"] = st.selectbox("Estado de firmas", ESTADOS_FIRMA, key="nu_estado")
            extra["coord_dest"] = st.text_input("Coordinador en destino", key="nu_coord_dest")

            plan_col1, plan_col2 = st.columns([8, 1.5])
            with plan_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                file_picker_button(
                    "📁", "nu_plan_sic_out", "nu_plan_sic_out_browse",
                    "Abrir explorador de archivos."
                )
            with plan_col1:
                extra["plan_sic_out"] = st.text_input(
                    "Plan de estudios (ruta o enlace)", key="nu_plan_sic_out"
                )

    return {
        "nombre": nombre,
        "apellidos": apellidos,
        "destino_origen": destino_origen,
        "email": email,
        "extra": extra,
    }
