"""
Vista principal de nuevo estudiante.
Orquesta la selección de tipo/hoja, los sub-formularios por programa,
la validación y el guardado en Excel.
"""


import logging
import os

import streamlit as st

from constants import PROGRAM_ERASMUS_IN, PROGRAM_ERASMUS_OUT, PROGRAM_SICUE_OUT
from domain.models import ESTADOS_FIRMA
from domain.validators import DataValidator, is_duration_valid, safe_int_convert
from utils import open_in_system
from utils.app_config import save_course

from ._helpers import (
    asig_nombre_puro,
    load_asignaturas_catalog,
    geocode_cached,
    normalize_subject_name,
    sheet_options_for,
)
from ._form_out   import render_erasmus_out_form
from ._form_in    import render_erasmus_in_form
from ._form_sicue import render_sicue_out_form

logger = logging.getLogger("movilidad_ui")


# ──────────────────────────────────────────────────────────────────────────────
# Limpieza del formulario
# ──────────────────────────────────────────────────────────────────────────────

def _clear_new_user_form_state() -> None:
    """Limpia todo el estado del formulario de nuevo usuario."""
    for k in list(st.session_state.keys()):
        if k.startswith("nu_"):
            del st.session_state[k]

    _empty_keys = (
        "nu_nombre", "nu_apellidos", "nu_email", "nu_destino_origen", "nu_pais_out",
        "nu_ciudad", "nu_tor", "nu_curso", "nu_la_out_opt", "nu_acta", "nu_dur_out",
        "nu_resp_prog", "nu_plan_out", "nu_pais_in", "nu_la_in", "nu_horario",
        "nu_cuatri_in", "nu_la_sicue", "nu_plan", "nu_dur_sicue", "nu_coord_dest",
        "nu_materias_in", "nu_plan_sic_out",
    )
    for k in _empty_keys:
        st.session_state[k] = ""

    st.session_state["nu_firmado_la"]        = False
    st.session_state["nu_investigacion_in"]  = False
    st.session_state["_nu_inv_stable"]       = False
    st.session_state["nu_estado"]            = ESTADOS_FIRMA[0] if ESTADOS_FIRMA else ""


# ──────────────────────────────────────────────────────────────────────────────
# Vista principal
# ──────────────────────────────────────────────────────────────────────────────

def render_new_user_form(available_types: list[str], config: dict) -> dict | None:
    from domain import ICON_BY_TIPO
    from persistence import append_user_to_excel, first_sheet_name

    # Transferir valores de buffer (file picker) a claves de widget antes de renderizar
    for _buf_key in [k for k in st.session_state if k.startswith("_buf_nu_")]:
        _widget_key = _buf_key[len("_buf_"):]
        st.session_state[_widget_key] = st.session_state.pop(_buf_key)

    if st.session_state.pop("_user_saved", False):
        _clear_new_user_form_state()
        st.toast("Guardado correctamente", icon="✅")

    st.header("👤 Crear nuevo estudiante")

    if not available_types:
        st.warning("No hay ficheros Excel cargados. No puedes crear estudiantes todavía.")
        if st.button("🔁 Abrir 'Cambiar rutas'"):
            st.session_state["show_routes"] = True
            st.session_state["view"] = "map"
            st.rerun()
        return None

    cfg = st.session_state.get("config", {}) or {}

    # ── Selectores tipo de alumno y curso ─────────────────────────────────────
    col_tipo, col_sheet = st.columns([1, 1], gap="small")

    with col_tipo:
        prev_tipo = st.session_state.get("new_user_tipo", available_types[0])
        if prev_tipo not in available_types:
            prev_tipo = available_types[0]
        tipo = st.selectbox(
            "Tipo de alumno",
            options=available_types,
            index=available_types.index(prev_tipo),
            key="new_user_tipo",
        )
        open_label = f"{ICON_BY_TIPO.get(tipo, '📄')} Abrir {tipo}"

    with col_sheet:
        sheet_opts = sheet_options_for(cfg, tipo)
        SENT_NEW = "➕ Nueva hoja…"
        options = ([SENT_NEW] + sheet_opts) if sheet_opts else [SENT_NEW]

        prev_sheet  = st.session_state.get("new_user_sheet")
        global_sel  = st.session_state.get("global_sheet", "Todas")
        if prev_sheet in options:
            idx = options.index(prev_sheet)
        elif global_sel in options:
            idx = options.index(global_sel)
        else:
            idx = 1 if len(options) > 1 else 0

        choice = st.selectbox("Curso", options=options, index=idx, key="new_user_sheet")
        new_sheet_name = None
        if choice == SENT_NEW:
            new_sheet_name = st.text_input(
                "Nombre de la nueva hoja", key="nu_sheet_new_name", placeholder="2025-2026"
            )

    selected_sheet = (
        new_sheet_name.strip() if new_sheet_name
        else (None if choice == SENT_NEW else choice)
    )
    st.session_state["nu_sheet"] = selected_sheet

    if selected_sheet and selected_sheet != st.session_state.get("global_sheet"):
        save_course(selected_sheet)
        st.session_state["global_sheet"] = selected_sheet

    # CSS para botones 📁
    st.markdown("""
    <style>
    button[aria-label^="📁"] {
        height: 38px !important;
        width: 38px !important;
        padding: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Catálogo de asignaturas (solo necesario para Erasmus IN)
    asignaturas_catalog = load_asignaturas_catalog(cfg, sheet_name=selected_sheet)

    # ── Sub-formulario por programa ───────────────────────────────────────────
    if tipo == PROGRAM_ERASMUS_OUT:
        form_data = render_erasmus_out_form(config, asignaturas_catalog)
    elif tipo == PROGRAM_ERASMUS_IN:
        form_data = render_erasmus_in_form(config, asignaturas_catalog)
    elif tipo == PROGRAM_SICUE_OUT:
        form_data = render_sicue_out_form(config, asignaturas_catalog)
    else:
        st.warning(f"Tipo de programa desconocido: {tipo}")
        return None

    nombre         = form_data["nombre"]
    apellidos      = form_data["apellidos"]
    destino_origen = form_data["destino_origen"]
    email          = form_data["email"]
    extra          = form_data["extra"]

    # ── Botones de acción ─────────────────────────────────────────────────────
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        open_clicked = st.button(open_label, key="open_xlsx_button", use_container_width=True)
    with col_btn2:
        submit_clicked = st.button(
            "Guardar estudiante", key="submit_new_user",
            use_container_width=True, type="primary"
        )

    if open_clicked:
        xlsx_for_tipo = config.get(tipo)
        if xlsx_for_tipo:
            ok2, err2 = open_in_system(os.path.abspath(xlsx_for_tipo))
            if not ok2:
                st.warning(f"No se pudo abrir el archivo: {err2}")
        else:
            st.warning(f"No hay Excel configurado para '{tipo}'.")
        st.stop()

    if not submit_clicked:
        return None

    # ── Validación ────────────────────────────────────────────────────────────
    validator = DataValidator()

    nombre_val  = (nombre or "").strip()
    destino_val = (destino_origen or "").strip()

    if not nombre_val:
        validator._add_error("nombre", "El nombre es obligatorio")
    else:
        validator.cleaned_data["nombre"] = nombre_val

    if not destino_val:
        validator._add_error("destino_origen", "El destino/universidad es obligatorio")
    else:
        validator.cleaned_data["destino_origen"] = destino_val

    apellidos_val = (apellidos or "").strip()
    if apellidos_val:
        validator.cleaned_data["apellidos"] = apellidos_val

    email_val = (email or "").strip()
    if email_val:
        validator.cleaned_data["email"] = email_val

    if tipo == PROGRAM_ERASMUS_OUT:
        pais_val = (extra.get("pais_out") or "").strip()
        if not pais_val:
            validator._add_error("pais_out", "El país es obligatorio")
        else:
            validator.cleaned_data["pais_out"] = pais_val
        if extra.get("dur_out"):
            validator.validate_field(
                "dur_out", extra["dur_out"], is_duration_valid(),
                normalizer=lambda x: str(safe_int_convert(x, default=0)),
            )

    elif tipo == PROGRAM_ERASMUS_IN:
        pais_val = (extra.get("pais_in") or "").strip()
        if not pais_val:
            validator._add_error("pais_in", "El país es obligatorio")
        else:
            validator.cleaned_data["pais_in"] = pais_val

    elif tipo == PROGRAM_SICUE_OUT:
        ciudad_val = (extra.get("ciudad_sicue") or "").strip()
        if not ciudad_val:
            validator._add_error("ciudad_sicue", "La ciudad es obligatoria")
        else:
            validator.cleaned_data["ciudad_sicue"] = ciudad_val
        if extra.get("dur_sicue"):
            validator.validate_field(
                "dur_sicue", extra["dur_sicue"], is_duration_valid(),
                normalizer=lambda x: str(safe_int_convert(x, default=0)),
            )

    if not validator.is_valid():
        st.toast(f"{validator.get_error_messages()}", icon="❌")
        return None

    # Validación de asignaturas (Erasmus IN)
    if tipo == PROGRAM_ERASMUS_IN:
        materias_raw = st.session_state.get("nu_materias_in", []) or []
        nombres      = [asig_nombre_puro((m.get("nombre") or "").strip()) for m in materias_raw]
        nombres_limpios = [n for n in nombres if n]

        seen: dict = {}
        duplicados: list[str] = []
        for idx_m, n in enumerate(nombres_limpios):
            nk = normalize_subject_name(n)
            if nk in seen:
                duplicados.append(n)
            else:
                seen[nk] = idx_m

        if duplicados:
            validator._add_error(
                "materias_in",
                "Hay asignaturas repetidas: " + ", ".join(sorted(set(duplicados))),
            )
        else:
            validator.cleaned_data["materias_in"] = nombres_limpios

    clean_data = validator.get_clean_data()

    # ── Geocoding (solo SICUE OUT) ────────────────────────────────────────────
    lat, lon = None, None
    if tipo == PROGRAM_SICUE_OUT:
        coords_conocidas = st.session_state.pop("_sicue_coords_known", None)
        if coords_conocidas:
            lat, lon = coords_conocidas
        else:
            lat, lon, gerr = geocode_cached(destino_origen.strip())
            if lat is None or lon is None:
                ciudad_opt = (extra.get("ciudad_sicue") or "").strip()
                if ciudad_opt:
                    lat, lon, gerr2 = geocode_cached(ciudad_opt)
                    if gerr and not gerr2:
                        gerr = None
            if lat is None and lon is None:
                st.warning(f"No se pudo geocodificar '{destino_origen}'")

    # ── Construcción del payload ──────────────────────────────────────────────
    if tipo == PROGRAM_SICUE_OUT:
        duracion = extra.get("dur_sicue", "")
        payload = {
            "tipo": tipo,
            "nombre": clean_data.get("nombre", ""),
            "apellidos": clean_data.get("apellidos", ""),
            "email": clean_data.get("email", ""),
            "destino_origen": clean_data.get("destino_origen", ""),
            "coordenadas": (lat, lon),
            "ciudad_sicue": extra.get("ciudad_sicue", ""),
            "duracion_meses": duracion,
            "dur_sicue": duracion,
            "coord_dest": extra.get("coord_dest", ""),
            "estado_firmas": extra.get("estado_firmas", ""),
            "la_in": extra.get("la_in", ""),
            "firmado_la": extra.get("firmado_la", ""),
            "plan_sic_out": extra.get("plan_sic_out", ""),
            "la": extra.get("la_in", ""),
            "gestion_la": extra.get("firmado_la", ""),
            "plan_estudios": extra.get("plan_sic_out", ""),
        }
    else:
        payload = {
            "tipo": tipo,
            "nombre": clean_data.get("nombre", ""),
            "apellidos": clean_data.get("apellidos", ""),
            "email": clean_data.get("email", ""),
            "destino_origen": clean_data.get("destino_origen", ""),
            "coordenadas": (lat, lon),
            **{k: (v.strip() if isinstance(v, str) else v) for k, v in extra.items()},
        }

    # Materias para Erasmus IN
    if tipo == PROGRAM_ERASMUS_IN:
        cuat_global     = extra.get("cuatrimestre_in", "")
        firmado_global  = extra.get("firmado_la", "")
        la_global       = extra.get("la_in", "")
        es_investigacion = extra.get("investigacion_in", False)

        if es_investigacion:
            materias_payload = [{
                "asignatura": "Estancia Investigación",
                "cuat": cuat_global,
                "firmado": firmado_global,
                "link_la": la_global,
            }]
        else:
            materias_payload = [
                {
                    "asignatura": asig_nombre_puro((m.get("nombre") or "").strip()),
                    "cuat": cuat_global,
                    "firmado": firmado_global,
                    "link_la": la_global,
                }
                for m in st.session_state.get("nu_materias_in", [])
                if asig_nombre_puro((m.get("nombre") or "").strip())
            ]

            if not materias_payload:
                st.toast("Debes añadir al menos una asignatura para Erasmus IN", icon="❌")
                return None

        if materias_payload:
            payload["materias_in"] = materias_payload

    # ── Guardar en Excel ──────────────────────────────────────────────────────
    xlsx_path = config.get(tipo)
    if not xlsx_path:
        st.toast(f"No hay Excel configurado para '{tipo}'. Ábrelo en 'Cambiar rutas'.", icon="❌")
        return None

    ok, err = append_user_to_excel(xlsx_path, tipo, payload, sheet_name=selected_sheet)
    if not ok:
        st.toast(f"Error guardando en Excel: {err}", icon="❌")
        return None

    st.cache_data.clear()
    st.session_state["_user_saved"]  = True
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    st.rerun()
