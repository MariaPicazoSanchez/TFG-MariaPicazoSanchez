from __future__ import annotations
import os
import re
import streamlit as st
from utils import open_in_system
import pycountry
import pandas as pd
from babel import Locale
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT
from domain.validators import (
    DataValidator, is_not_empty, is_email, is_duration_valid,
    normalize_string, normalize_email, normalize_int,
    get_erasmus_out_schema, get_erasmus_in_schema, get_sicue_out_schema,
    safe_int_convert
)

from .sidebar import pick_local_file
USE_LOCAL_PICKER = True


def _clear_new_user_form_state():
    """
    Limpia TODO el formulario de nuevo usuario.
    """
    # 1) Borrar todos los campos del formulario (nu_*)
    for k in list(st.session_state.keys()):
        if k.startswith("nu_"):
            del st.session_state[k]

    # 2) Seguridad extra: forzar vacío en estos tres por si Streamlit
    # los vuelve a crear con valor anterior en este mismo run
    for k in ("nu_nombre", "nu_apellidos", "nu_email", "nu_destino_origen", "nu_pais_out", "nu_ciudad", "nu_tor", "nu_curso","nu_la_out_opt", "nu_acta", "nu_dur_out", "nu_resp_prog", "nu_plan_out", "nu_pais_in", "nu_la_in", "nu_horario", "nu_cuatri_in", "nu_la_sicue", "nu_estado", "nu_plan", "nu_dur_sicue", "nu_coord_dest", "nu_materias_in", "nu_plan_sic_out"):
        st.session_state[k] = ""



# ────────────────────────────────────────────────────────────────────────────────
# Lista de países (estándar ISO) con caché
# ────────────────────────────────────────────────────────────────────────────────

@st.cache_data
def get_country_options() -> list[str]:
    locale_es = Locale('es')
    nombres = []

    for c in pycountry.countries:
        # Intentamos coger el nombre en español según el código alpha_2 (ES, FR, IT...)
        nombre_es = locale_es.territories.get(c.alpha_2)
        if not nombre_es:
            # Si no hay traducción, usamos el nombre en inglés
            nombre_es = c.name
        nombres.append(nombre_es)

    # Añadimos una opción vacía al principio
    return [""] + sorted(set(nombres))

COUNTRY_OPTIONS = get_country_options()




# ────────────────────────────────────────────────────────────────────────────────
# Geocoding (con caché)
# ────────────────────────────────────────────────────────────────────────────────
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    import tkinter as tk
    from tkinter import filedialog
    _GEOCODER = Nominatim(user_agent="tfg-movilidad-esii")
    _GEOCODE = RateLimiter(_GEOCODER.geocode, min_delay_seconds=1)
except Exception:
    _GEOCODER = None
    _GEOCODE = None


def _geocode_cached(q: str) -> tuple[float | None, float | None, str | None]:
    if not q or not q.strip():
        return None, None, "Consulta vacía"
    qn = q.strip().lower()
    cache = st.session_state.setdefault("_geo_cache", {})
    if qn in cache:
        d = cache[qn]
        return d["lat"], d["lon"], None
    if _GEOCODE is None:
        return None, None, "Geocoder no disponible"
    try:
        loc = _GEOCODE(q, addressdetails=False, timeout=10)
        if loc:
            lat, lon = float(loc.latitude), float(loc.longitude)
            cache[qn] = {"lat": lat, "lon": lon}
            return lat, lon, None
        return None, None, "No encontrado"
    except Exception as e:
        return None, None, f"Error geocodificando: {e}"



# ────────────────────────────────────────────────────────────────────────────────
# UI: formulario
# ────────────────────────────────────────────────────────────────────────────────
def _is_academic_year(name: str) -> bool:
    """Devuelve True si el nombre parece un curso académico (ej: 25-26, 2025/2026, 2016)."""
    return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', name))

def _sheet_options_for(cfg: dict, tipo: str) -> list[str]:
    from persistence import sheets_for
    sheets_map = (cfg or {}).get("sheets", {}) or {}
    known = sheets_map.get(tipo) or []
    if known:
        return sorted({s for s in known if s and s != "__CSV__" and _is_academic_year(s)})
    path = (cfg or {}).get(tipo, "")
    return [s for s in sheets_for(path) if s != "__CSV__" and _is_academic_year(s)] if path else []

def _invisible_suffix_from_id(button_id: str) -> str:
    """
    Genera un sufijo invisible único a partir de button_id,
    usando combinaciones de caracteres zero-width.
    """
    # Codificamos el button_id en bits y los traducimos a caracteres invisibles.
    bits = "".join(f"{ord(c):08b}" for c in button_id)  # p.ej. '01101010...'
    return "".join("\u200b" if b == "0" else "\u200c" for b in bits)
    # \u200b y \u200c son invisibles, pero la secuencia será distinta para cada id.


def file_picker_button(label: str, text_input_key: str, button_id: str, help: str = "Seleccionar archivo del equipo"):
    """
    Muestra un botón para seleccionar archivo y actualiza el campo text_input correspondiente.
    Visualmente se muestra solo `label` (📁), pero internamente cada botón tendrá
    un label diferente gracias a button_id.
    """
    invisible_suffix = _invisible_suffix_from_id(button_id)
    real_label = label + invisible_suffix

    clicked = st.form_submit_button(real_label, help=help)

    if clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get(text_input_key, "")
            path = pick_local_file(current_val)
            if path:
                st.session_state[text_input_key] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()
    return clicked



def render_new_user_form(available_types: list[str], config: dict) -> dict | None:
    from domain import ESTADOS_FIRMA, ICON_BY_TIPO, CITIES_ES
    from persistence import append_user_to_excel, first_sheet_name
    # Si venimos de un guardado correcto:
    if st.session_state.pop("_user_saved", False):
        _clear_new_user_form_state()

        st.success("✅ Estudiante creado y guardado en Excel.")
        st.toast("Guardado correctamente")
    st.header("👤 Crear nuevo estudiante")

    if not available_types:
        st.warning("No hay ficheros Excel cargados. No puedes crear estudiantes todavía.")
        if st.button("🔁 Abrir ‘Cambiar rutas’"):
            st.session_state["show_routes"] = True
            st.session_state["view"] = "map"
            st.rerun()
        return None

    cfg = st.session_state.get("config", {}) or {}

    # Selectores en la misma fila
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
    tipo_norm = (tipo or "").strip()
    
    open_label = f"{ICON_BY_TIPO.get(tipo_norm, '📄')} Abrir {tipo_norm}"
    xlsx_for_tipo = config.get(tipo_norm)  # ruta del Excel del tipo seleccionado


    with col_sheet:
        sheet_opts = _sheet_options_for(cfg, tipo_norm)
        SENT_NEW = "➕ Nueva hoja…"
        options = ([SENT_NEW] + sheet_opts) if sheet_opts else [SENT_NEW]

        # índice por defecto
        prev_sheet = st.session_state.get("new_user_sheet")
        global_sel = st.session_state.get("global_sheet", "Todas")
        if prev_sheet in options:
            idx = options.index(prev_sheet)
        elif global_sel in options:
            idx = options.index(global_sel)
        else:
            idx = 1 if len(options) > 1 else 0

        choice = st.selectbox("Curso", options=options, index=idx, key="new_user_sheet")
        new_sheet_name = None
        if choice == SENT_NEW:
            new_sheet_name = st.text_input("Nombre de la nueva hoja", key="nu_sheet_new_name", placeholder="2025-2026")

    selected_sheet = (new_sheet_name.strip() if new_sheet_name else (None if choice == SENT_NEW else choice))
    st.session_state["nu_sheet"] = selected_sheet

    # Flags para los botones "📁" dentro del form
    browse_tor_clicked = False
    browse_la_out_clicked = False
    browse_plan_out_clicked = False
    browse_la_in_clicked = False
    browse_horario_clicked = False

    open_clicked = False
    # ────────────────────────────────────────────────────────────────
    # FORMULARIO PRINCIPAL
    # ────────────────────────────────────────────────────────────────
    with st.form("new_user_form", clear_on_submit=False):
        

        # — comunes (obligatorios) —
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", key="nu_nombre")
            email  = st.text_input("Email", key="nu_email")
        with col2:
            apellidos = st.text_input("Apellidos", key="nu_apellidos")
            dest_label = "Origen (universidad)" if tipo_norm.lower() == PROGRAM_ERASMUS_IN.lower() else "Destino (universidad)"
            destino_origen = st.text_input(dest_label, key="nu_destino_origen")

        extra: dict = {}

        # _____________________________________
        # Erasmus OUT
        # _____________________________________
        if tipo_norm == PROGRAM_ERASMUS_OUT:
            col1, col2 = st.columns(2)
            # obligatorios
            with col1:
                extra["pais_out"] = st.selectbox("País", options=COUNTRY_OPTIONS, key="nu_pais_out")
                dur_out_val = st.text_input("Duración (meses)", key="nu_dur_out")
                # Validar que solo contiene números
                if dur_out_val and not dur_out_val.strip().isdigit():
                    st.error("La duración debe ser un número")
                    extra["dur_out"] = ""
                else:
                    extra["dur_out"] = dur_out_val
                extra["acta_equivalencias"] = st.text_input("Acta de equivalencias (ruta o enlace)", key="nu_acta")
                tor_col1, tor_col2 = st.columns([3, 1])
                with tor_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_tor_clicked = file_picker_button("📁", "nu_tor", "nu_tor_browse", "Abrir explorador de archivos.")
                with tor_col1:
                    extra["tor"] = st.text_input("ToR (ruta o enlace)", key="nu_tor")
                plan_col1, plan_col2 = st.columns([3, 1])
                with plan_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_plan_out_clicked = file_picker_button("📁", "nu_plan_out", "nu_plan_out_browse", "Abrir explorador de archivos.")
                
                with plan_col1:
                    extra["plan_out"] = st.text_input(
                        "Propuesta alumno LA (ruta o enlace)",
                    )
                
            with col2:
                extra["curso"] = st.selectbox("Curso", options=["","1", "2", "3", "4"], key="nu_curso")
                extra["ciudad"] = st.text_input("Ciudad", key="nu_ciudad")
                extra["resp_prog"] = st.text_input("Responsable del programa", key="nu_resp_prog")
                la_col1, la_col2 = st.columns([3, 1])
                with la_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_la_out_clicked = file_picker_button("📁", "nu_la_out_opt", "nu_la_out_opt_browse", "Abrir explorador de archivos.")
                
                with la_col1:
                    extra["la_out"] = st.text_input("LA (enlace o ruta)", key="nu_la_out_opt")
                    
        # _____________________________________
        # Erasmus IN
        # _____________________________________

        elif tipo_norm == PROGRAM_ERASMUS_IN:
            col1, col2 = st.columns(2)

            with col1:
                extra["pais_in"] = st.selectbox("País", options=COUNTRY_OPTIONS, key="nu_pais_in")
                extra["cuatrimestre_in"] = st.selectbox("Cuatrimestre", options=["", "1", "2"], key="nu_cuatri_in")

                # LA con selector de archivo o ruta manual
                la_col1, la_col2 = st.columns([3, 1])

                with la_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_la_in_clicked = file_picker_button("📁", "nu_la_in", "nu_la_in_browse", "Abrir explorador de archivos.")

                with la_col1:
                    extra["la_in"] = st.text_input("LA (enlace o ruta)", key="nu_la_in")

            # opcionales
            with col2:
                extra["ciudad"] = st.text_input("Ciudad", key="nu_ciudad")

                col_hor1, col_hor2 = st.columns([3, 1])

                with col_hor2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_horario_clicked = file_picker_button("📁", "nu_horario", "nu_horario_browse", "Abrir explorador de archivos.")

                with col_hor1:
                    extra["horario"] = st.text_input(
                        "Propuesta alumno LA (ruta o enlace)",
                        key="nu_horario",
                    )
            
            
        # _____________________________________
        # SICUE OUT
        # _____________________________________

        elif tipo_norm == PROGRAM_SICUE_OUT:
            col1, col2 = st.columns(2)
            # obligatorios
            with col1:
                extra["ciudad_sicue"] = st.selectbox(
                    "Ciudad",
                    options=CITIES_ES,
                    index=0,
                    help="Si no se encuentran coordenadas por la universidad, se intentará con esta ciudad.",
                    key="nu_ciudad",
                )
                dur_sicue_val = st.text_input("Duración (meses)", key="nu_dur_sicue")
                # Validar que solo contiene números
                if dur_sicue_val and not dur_sicue_val.strip().isdigit():
                    st.error("La duración debe ser un número")
                    extra["dur_sicue"] = ""
                else:
                    extra["dur_sicue"] = dur_sicue_val
                la_col1, la_col2 = st.columns([3, 1])
                with la_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_la_in_clicked = file_picker_button("📁", "nu_la_sicue", "nu_la_sicue_browse", "Abrir explorador de archivos.")
                with la_col1:
                    extra["la_in"] = st.text_input("LA (enlace o ruta)", key="nu_la_sicue")
            with col2:
                extra["estado_firmas"]  = st.selectbox("Estado de firmas", ESTADOS_FIRMA, key="nu_estado")
                extra["coord_dest"] = st.text_input("Coordinador en destino", key="nu_coord_dest")

                plan_col1, plan_col2 = st.columns([3, 1])
                with plan_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    browse_plan_out_clicked =  file_picker_button("📁", "nu_plan_sic_out", "nu_plan_sic_out_browse", "Abrir explorador de archivos.")
                with plan_col1:
                    extra["plan_sic_out"] = st.text_input(
                        "Propuesta alumno LA (ruta o enlace)",
                        key="nu_plan_sic_out",
                    )

        # — fila con los dos botones: Crear y Abrir Excel (dinámico) —
        bcol1, bcol2 = st.columns([1, 1], gap="small")
        open_clicked   = bcol1.form_submit_button(open_label, use_container_width=True)
        submit_clicked = bcol2.form_submit_button("✅ Crear", use_container_width=True)
    # ────────────────────────────────────────────────────────────────
    # BLOQUE DE ASIGNATURAS ERASMUS IN (FUERA DEL FORM)
    # ────────────────────────────────────────────────────────────────
    if tipo_norm == "Erasmus IN":
        st.markdown("### 📚 Asignaturas (Erasmus IN)")

        materias_key = "nu_materias_in"
        materias = st.session_state.setdefault(materias_key, [])

        with st.container(border=True):
            # Cabecera tipo tabla
            header_cols = st.columns([3, 1, 1, 0.8, 0.8])
            with header_cols[0]:
                st.caption("Nombre de la asignatura")
            with header_cols[1]:
                st.caption("Cuatr.")
            with header_cols[2]:
                st.caption("Firmado")
            with header_cols[3]:
                st.caption("Acciones")
            with header_cols[4]:
                st.write("")
                if st.button("➕ Añadir", key=f"{materias_key}_add_top"):
                    materias.append({"nombre": "", "cuatrimestre": "1", "firmado": False})
                    st.rerun()

            if not materias:
                st.info("Aún no hay asignaturas añadidas para este estudiante.")

            delete_idx = None
            # Filas de asignaturas
            for i, mat in enumerate(materias):
                row_cols = st.columns([3, 1, 1, 0.8, 0.8])

                with row_cols[0]:
                    mat["nombre"] = st.text_input(
                        f"Asignatura {i+1}",
                        key=f"{materias_key}_nombre_{i}",
                        value=mat.get("nombre", ""),
                        label_visibility="collapsed",
                    )

                with row_cols[1]:
                    cuatri_val = str(mat.get("cuatrimestre", "1"))
                    opciones_cuatri = ["1", "2"]
                    idx_cuatri = opciones_cuatri.index(cuatri_val) if cuatri_val in opciones_cuatri else 0
                    mat["cuatrimestre"] = st.selectbox(
                        "Cuat.",
                        options=opciones_cuatri,
                        index=idx_cuatri,
                        key=f"{materias_key}_cuatri_{i}",
                        label_visibility="collapsed",
                    )

                with row_cols[2]:
                    mat["firmado"] = st.checkbox(
                        "Firmado",
                        value=bool(mat.get("firmado", False)),
                        key=f"{materias_key}_firmado_{i}",
                        label_visibility="collapsed",
                    )

                with row_cols[3]:
                    st.write(f"#{i+1}")

                with row_cols[4]:
                    if st.button("🗑️", key=f"{materias_key}_del_{i}"):
                        delete_idx = i
            if delete_idx is not None:
                materias.pop(delete_idx)
                st.rerun()


    # ────────────────────────────────────────────────────────────────
    # ACCIONES DE BOTONES DEL FORM
    # ────────────────────────────────────────────────────────────────
    if browse_tor_clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get("nu_tor", "")
            path = pick_local_file(current_val)
            if path:
                st.session_state["nu_tor"] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()

    if browse_la_out_clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get("nu_la_out_opt", "")
            path = pick_local_file(current_val)
            if path:
                st.session_state["nu_la_out_opt"] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()

    if browse_plan_out_clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get("nu_plan_out", "")
            path = pick_local_file(current_val)
            if path:
                st.session_state["nu_plan_out"] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()

    if browse_la_in_clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get("nu_la_in", "")
            path = pick_local_file(current_val)
            if path:
                st.session_state["nu_la_in"] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()

    if browse_horario_clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get("nu_horario", "")
            path = pick_local_file(current_val)
            if path:
                st.session_state["nu_horario"] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()

    if open_clicked:
        if xlsx_for_tipo:
            ok2, err2 = open_in_system(os.path.abspath(xlsx_for_tipo))
            if not ok2:
                st.warning(f"No se pudo abrir el archivo: {err2}")
        else:
            st.warning(f"No hay Excel configurado para ‘{tipo_norm}’.")
        st.stop()  # evitar validar/guardar cuando solo se quiso abrir

    if not submit_clicked:
        return None
    
    # ────────────────────────────────────────────────────────────────
    # VALIDACIONES
    # ────────────────────────────────────────────────────────────────
    validator = DataValidator()
    
    # Campos obligatorios con normalización
    validator.validate_field("nombre", nombre.strip(), lambda x: len(x) > 0, 
                            normalizer=lambda x: x.strip())
    validator.validate_field("apellidos", apellidos.strip(), lambda x: len(x) > 0,
                            normalizer=lambda x: x.strip())
    validator.validate_field("email", email.strip(), is_email(),
                            normalizer=lambda x: x.strip().lower())
    validator.validate_field("destino_origen", destino_origen.strip(), lambda x: len(x) > 0,
                            normalizer=lambda x: x.strip())
    
    # Validaciones específicas por tipo con normalización
    if tipo_norm == PROGRAM_ERASMUS_OUT:
        validator.validate_field("pais_out", extra["pais_out"].strip(), lambda x: len(x) > 0,
                                normalizer=lambda x: x.strip())
        if extra["dur_out"]:
            validator.validate_field("dur_out", extra["dur_out"], is_duration_valid(),
                                    normalizer=lambda x: str(safe_int_convert(x, default=0)))
            
    elif tipo_norm == PROGRAM_ERASMUS_IN:
        validator.validate_field("pais_in", extra["pais_in"].strip(), lambda x: len(x) > 0,
                                normalizer=lambda x: x.strip())
            
    elif tipo_norm == PROGRAM_SICUE_OUT:
        validator.validate_field("ciudad_sicue", extra["ciudad_sicue"].strip(), lambda x: len(x) > 0,
                                normalizer=lambda x: x.strip())
        if extra["dur_sicue"]:
            validator.validate_field("dur_sicue", extra["dur_sicue"], is_duration_valid(),
                                    normalizer=lambda x: str(safe_int_convert(x, default=0)))
    
    if not validator.is_valid():
        st.error(validator.get_error_messages())
        return None
    
    # Obtener datos normalizados
    clean_data = validator.get_clean_data()


    # ────────────────────────────────────────────────────────────────
    # GEOCODING
    # ────────────────────────────────────────────────────────────────
    lat, lon, gerr = _geocode_cached(destino_origen.strip())
    if (lat is None or lon is None) and tipo_norm == PROGRAM_SICUE_OUT:
        ciudad_opt = (extra.get("ciudad_sicue") or "").strip()
        if ciudad_opt:
            lat, lon, gerr2 = _geocode_cached(ciudad_opt)
            if gerr and not gerr2:
                gerr = None  # mejoró con ciudad
    if gerr:
        st.warning(f"No se pudo geocodificar ‘{destino_origen}’: {gerr}")
    # ────────────────────────────────────────────────────────────────
    # PAYLOAD + MATERIAS
    # ────────────────────────────────────────────────────────────────
    # Usar datos normalizados del validador - mucho más limpio
    payload = {
        "tipo": tipo_norm,
        "nombre": clean_data.get("nombre", ""),
        "apellidos": clean_data.get("apellidos", ""),
        "email": clean_data.get("email", ""),
        "destino_origen": clean_data.get("destino_origen", ""),
        "coordenadas": (lat, lon),
        **{k: (v.strip() if isinstance(v, str) else v) for k, v in extra.items()},
    }
    if tipo_norm == "Erasmus IN":
        materias_payload = []
        for m in st.session_state.get("nu_materias_in", []):
            nom = (m.get("nombre") or "").strip()
            if not nom:
                # ignoramos filas vacías
                continue
            cuatri = str(m.get("cuatrimestre") or "").strip()
            firmado_bool = bool(m.get("firmado"))
            materias_payload.append(
                {
                    "asignatura": nom,
                    "cuatrimestre": cuatri,
                    "cuat": cuatri,
                    "firmado": "x" if firmado_bool else "",
                }
            )
        if materias_payload:
            payload["materias_in"] = materias_payload
    else:
        materias_payload = []


    # ────────────────────────────────────────────────────────────────
    # GUARDAR EN EXCEL
    # ────────────────────────────────────────────────────────────────
    xlsx_path = config.get(tipo_norm)
    if not xlsx_path:
        st.error(f"No hay Excel configurado para ‘{tipo_norm}’. Ábrelo en ‘Cambiar rutas’.")
        return None

    ok, err = append_user_to_excel(xlsx_path, tipo_norm, payload, sheet_name=selected_sheet)
    if not ok:
        st.error(f"Error guardando en Excel: {err}")
        return None

    # Si es Erasmus IN y hay materias, añadimos también al Excel 'Materias IN'
    if tipo_norm == PROGRAM_ERASMUS_IN and materias_payload:
        _append_materias_in_excel_single_student(materias_payload, payload, config)


    # Marcamos éxito y forzamos incremento de `data_version` para invalidar caches
    st.session_state["_user_saved"] = True
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    st.rerun()


def _append_materias_in_excel_single_student(
    materias_payload: list[dict],
    student_payload: dict,
    config: dict,
):
    """
    Añade las materias de UN estudiante Erasmus IN al Excel 'Materias IN'
    indicado en config["ERASMUS IN"].
    """
    path_materias = (config or {}).get("Erasmus IN")
    if not path_materias or not materias_payload:
        return

    # Datos comunes
    nombre_est = f"{student_payload.get('nombre', '')} {student_payload.get('apellidos', '')}".strip()
    origen = student_payload.get("pais_in") or ""
    centro = student_payload.get("destino_origen") or ""

    rows_out = []
    for m in materias_payload:
        asig = m.get("asignatura", "").strip()
        if not asig:
            continue
        cuat = (m.get("cuat") or m.get("cuatrimestre") or "").strip()
        firmado = m.get("firmado") or ""
        rows_out.append(
            {
                "Asignatura": asig,
                "Estudiante": nombre_est,
                "Origen": origen,
                "Universidad Origen": centro,
                "Cuat": cuat,
                "Firmado": firmado,
            }
        )

    if not rows_out:
        return

    cols = ["Asignatura", "Estudiante", "Origen", "Universidad Origen", "Cuat", "Firmado"]
    df_new = pd.DataFrame(rows_out, columns=cols)

    try:
        if os.path.exists(path_materias):
            try:
                df_old = pd.read_excel(path_materias)
                # alineamos columnas
                for c in cols:
                    if c not in df_old.columns:
                        df_old[c] = None
                for c in df_old.columns:
                    if c not in df_new.columns:
                        df_new[c] = None
                df_out = pd.concat(
                    [df_old[cols], df_new[cols]],
                    ignore_index=True,
                )
            except Exception:
                df_out = df_new
        else:
            df_out = df_new

        df_out.to_excel(path_materias, index=False)
    except Exception as e:
        st.warning(f"No se pudo actualizar el Excel de 'ERASMUS IN': {e}")
