"""
Formulario de nuevo estudiante para Erasmus IN.
"""

from __future__ import annotations

import streamlit as st

from persistence.data_access_mobility import get_universities_from_coords_sheet

from ._helpers import (
    COUNTRY_OPTIONS,
    _FILTER_ALL,
    asig_nombre_puro,
    file_picker_button,
    get_university_country_map,
    normalize_subject_name,
)


def render_erasmus_in_form(config: dict, asignaturas_catalog: list) -> dict:
    """
    Renderiza el formulario de Erasmus IN.
    Devuelve un dict con: nombre, apellidos, destino_origen, email, extra.
    """
    xlsx_path = config.get("Erasmus IN", "")
    universidades_in   = get_universities_from_coords_sheet(xlsx_path)
    uni_country_map_in = get_university_country_map(xlsx_path)

    nombre = apellidos = destino_origen = email = ""
    extra: dict = {}

    # Mantener estabilidad del checkbox investigacion entre reruns
    es_investigacion = st.session_state.get(
        "nu_investigacion_in",
        st.session_state.get("_nu_inv_stable", False),
    )

    with st.container(border=True):
        col1, col2 = st.columns(2)

        with col2:
            apellidos = st.text_input("Apellidos", key="nu_apellidos")
            destino_origen = st.selectbox(
                "Origen (universidad)",
                options=[""] + universidades_in,
                key="nu_destino_origen",
                help="Selecciona una universidad o escribe una nueva",
                accept_new_options=True,
            )
            la_col1, la_col2 = st.columns([8, 1.5])
            with la_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                file_picker_button(
                    "📁", "nu_la_in", "nu_la_in_browse",
                    "Abrir explorador de archivos.", file_filter=_FILTER_ALL
                )
            with la_col1:
                extra["la_in"] = st.text_input("LA (enlace o ruta)", key="nu_la_in")

            st.markdown("<div style='margin-top:30px'></div>", unsafe_allow_html=True)
            extra["investigacion_in"] = st.checkbox("Investigación", key="nu_investigacion_in")
            st.session_state["_nu_inv_stable"] = extra["investigacion_in"]

        # Autocomplete de país a partir de la universidad seleccionada
        if destino_origen:
            pais_sugerido = uni_country_map_in.get(destino_origen.strip(), "")
            if pais_sugerido and pais_sugerido in COUNTRY_OPTIONS:
                if st.session_state.get("nu_pais_in") != pais_sugerido:
                    st.session_state["nu_pais_in"] = pais_sugerido

        with col1:
            nombre = st.text_input("Nombre", key="nu_nombre")
            extra["cuatrimestre_in"] = st.selectbox(
                "Cuatrimestre", options=["", "1", "2"], key="nu_cuatri_in"
            )
            extra["pais_in"] = st.selectbox("País", options=COUNTRY_OPTIONS, key="nu_pais_in")
            st.markdown("<div style='margin-top:30px'></div>", unsafe_allow_html=True)
            extra["firmado_la"] = "x" if st.checkbox("LA firmado", key="nu_firmado_la") else ""

        # ── Sección de asignaturas ──────────────────────────────────────────
        if not extra.get("investigacion_in"):
            _render_asignaturas_section(asignaturas_catalog, extra)

    return {
        "nombre": nombre,
        "apellidos": apellidos,
        "destino_origen": destino_origen,
        "email": email,
        "extra": extra,
    }


def _render_asignaturas_section(asignaturas_catalog: list, extra: dict) -> None:
    """Renderiza la sección de asignaturas dentro del formulario Erasmus IN."""
    st.divider()
    st.markdown("#### 📚 Asignaturas")

    materias_key = "nu_materias_in"
    if materias_key not in st.session_state or not isinstance(st.session_state[materias_key], list):
        st.session_state[materias_key] = []
    materias = st.session_state[materias_key]

    cuatrimestre_sel = st.session_state.get("nu_cuatri_in", "")
    if cuatrimestre_sel:
        sugerencias = [
            a["asignatura"]
            for a in asignaturas_catalog
            if a.get("cuat") == cuatrimestre_sel
            and a["asignatura"].strip().lower() != "estancia investigación"
        ]
    else:
        sugerencias = [
            a["asignatura"]
            for a in asignaturas_catalog
            if a["asignatura"].strip().lower() != "estancia investigación"
        ]

    catalog_map = {a["asignatura"]: a for a in asignaturas_catalog}

    header_cols = st.columns([8, 2, 1], vertical_alignment="bottom")
    with header_cols[0]:
        st.caption("Nombre de la asignatura")
    with header_cols[1]:
        st.caption("Matr. / Cupo")
    with header_cols[2]:
        if st.button("➕ Añadir", key=f"{materias_key}_add"):
            materias.append({"nombre": ""})

    delete_idx = None
    for i, mat in enumerate(materias):
        raw_sel  = st.session_state.get(f"{materias_key}_select_{i}")
        nom_actual = asig_nombre_puro(raw_sel) if raw_sel else asig_nombre_puro(mat.get("nombre", ""))
        info = catalog_map.get(nom_actual)

        row_cols = st.columns([8, 2, 1], vertical_alignment="center")
        with row_cols[0]:
            valor_actual = mat.get("nombre", "")
            seleccion = st.selectbox(
                f"Asignatura {i+1}",
                options=sugerencias,
                index=sugerencias.index(valor_actual) if valor_actual in sugerencias else None,
                key=f"{materias_key}_select_{i}",
                label_visibility="collapsed",
                placeholder="Seleccionar o escribir...",
                accept_new_options=True,
            )
            mat["nombre"] = asig_nombre_puro(seleccion) if seleccion else ""

        with row_cols[1]:
            if info:
                matr = info.get("matriculados")
                cupo = info.get("cupo")
                matr_display = (matr + 1) if matr is not None else None
                if matr_display is not None and cupo is not None:
                    color = "#e05252" if matr_display > cupo else "#4caf50"
                    st.markdown(
                        f"<p style='margin:-0.5rem 0 0 -0.1rem;font-size:1.1rem;font-weight:700;"
                        f"color:{color};text-align:left;line-height:2.4rem'>"
                        f"{matr_display}&nbsp;/&nbsp;{cupo}</p>",
                        unsafe_allow_html=True,
                    )
                elif matr_display is not None:
                    st.markdown(
                        f"<p style='margin:-0.5rem 0 0 -0.1rem;font-size:1.1rem;font-weight:700;"
                        f"color:#888;text-align:left;line-height:2.4rem'>"
                        f"{matr_display}</p>",
                        unsafe_allow_html=True,
                    )
            else:
                st.empty()

        with row_cols[2]:
            if st.button("❌", key=f"{materias_key}_del_{i}", help="Eliminar asignatura",
                         type="secondary", use_container_width=True):
                delete_idx = i

    if delete_idx is not None:
        materias.pop(delete_idx)

    # Validación en tiempo real
    if not materias:
        st.warning("Debes añadir al menos una asignatura antes de guardar el estudiante.")
    else:
        nombres_rellenos = [(i, (m.get("nombre") or "").strip()) for i, m in enumerate(materias)]
        vacias = [i + 1 for i, n in nombres_rellenos if not n]
        if vacias:
            fila_txt = ", ".join(f"#{f}" for f in vacias)
            st.warning(
                f"⚠️ {'La asignatura' if len(vacias) == 1 else 'Las asignaturas'} "
                f"{fila_txt} {'está vacía' if len(vacias) == 1 else 'están vacías'}. "
                f"Rellénala{'s' if len(vacias) > 1 else ''} o elimínala{'s' if len(vacias) > 1 else ''}."
            )

        seen_norm: dict[str, int] = {}
        duplicadas: list[str] = []
        for i, n in nombres_rellenos:
            if not n:
                continue
            nk = normalize_subject_name(n)
            if nk in seen_norm:
                duplicadas.append(n)
            else:
                seen_norm[nk] = i + 1
        if duplicadas:
            dup_txt = ", ".join(sorted(set(duplicadas)))
            st.error(
                f"❌ Asignatura{'s' if len(set(duplicadas)) > 1 else ''} "
                f"repetida{'s' if len(set(duplicadas)) > 1 else ''}: {dup_txt}"
            )
