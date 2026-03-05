from __future__ import annotations
import os
import re
import logging
import streamlit as st
from utils import open_in_system
import pycountry
from babel import Locale
from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT
from domain.validators import (DataValidator, safe_int_convert, is_duration_valid)
from persistence import get_asignaturas_catalog

from .sidebar import pick_local_file
USE_LOCAL_PICKER = True

logger = logging.getLogger("movilidad_ui")


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


def _load_asignaturas_catalog(config: dict) -> list:
    """Carga el catálogo de asignaturas, con caché en session_state."""
    ruta = (config.get("Materias IN") or config.get("Erasmus IN") or "").strip()
    cache_key = f"_asignaturas_catalog_cache_{ruta}"
    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = get_asignaturas_catalog(config)
        except Exception as e:
            logger.warning("No se pudo cargar catálogo de asignaturas: %s", e)
            st.session_state[cache_key] = []
    return st.session_state.get(cache_key, [])




# ────────────────────────────────────────────────────────────────────────────────
# Geocoding (con caché)
# ────────────────────────────────────────────────────────────────────────────────
try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
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

    clicked = st.button(real_label, help=help, key=button_id)

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

        st.toast("Guardado correctamente", icon="✅")
    st.header("👤 Crear nuevo estudiante")

    if not available_types:
        st.warning("No hay ficheros Excel cargados. No puedes crear estudiantes todavía.")
        if st.button("🔁 Abrir ‘Cambiar rutas’"):
            st.session_state["show_routes"] = True
            st.session_state["view"] = "map"
            st.rerun()
        return None

    cfg = st.session_state.get("config", {}) or {}
    
    # Cargar catálogo de asignaturas para Erasmus IN
    asignaturas_catalog = _load_asignaturas_catalog(cfg)

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

    # ────────────────────────────────────────────────────────────────
    # FORMULARIO PRINCIPAL (SIN st.form para permitir dinámica de asignaturas)
    # ────────────────────────────────────────────────────────────────
    
    # Inicializar variables comunes
    nombre = apellidos = destino_origen = email = ""
    extra: dict = {}

    # _____________________________________
    # Erasmus OUT
    # _____________________________________
    if tipo_norm == PROGRAM_ERASMUS_OUT:
        with st.container(border=True):
            
            # Campos comunes
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre", key="nu_nombre")
                email = st.text_input("Email", key="nu_email")
            with col2:
                apellidos = st.text_input("Apellidos", key="nu_apellidos")
                destino_origen = st.text_input("Destino (universidad)", key="nu_destino_origen")
            
            
            # Campos específicos
            col1, col2 = st.columns(2)
            with col1:
                extra["pais_out"] = st.selectbox("País", options=COUNTRY_OPTIONS, key="nu_pais_out")
                dur_out_val = st.text_input("Duración (meses)", key="nu_dur_out")
                # Validar que solo contiene números
                if dur_out_val and not dur_out_val.strip().isdigit():
                    st.toast("⚠️ La duración debe ser un número", icon="⚠️")
                    extra["dur_out"] = ""
                else:
                    extra["dur_out"] = dur_out_val
                extra["acta_equivalencias"] = st.text_input("Acta de equivalencias (ruta o enlace)", key="nu_acta")
                tor_col1, tor_col2 = st.columns([3, 1])
                with tor_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    file_picker_button("📁", "nu_tor", "nu_tor_browse", "Abrir explorador de archivos.")
                with tor_col1:
                    extra["tor"] = st.text_input("ToR (ruta o enlace)", key="nu_tor")
                plan_col1, plan_col2 = st.columns([3, 1])
                with plan_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    file_picker_button("📁", "nu_plan_out", "nu_plan_out_browse", "Abrir explorador de archivos.")
                
                with plan_col1:
                    extra["plan_out"] = st.text_input(
                        "Propuesta alumno LA (ruta o enlace)",
                        key="nu_plan_out",
                    )
                
            with col2:
                extra["curso"] = st.selectbox("Curso", options=["","1", "2", "3", "4"], key="nu_curso")
                extra["ciudad"] = st.text_input("Ciudad", key="nu_ciudad")
                extra["resp_prog"] = st.text_input("Responsable del programa", key="nu_resp_prog")
                la_col1, la_col2 = st.columns([3, 1])
                with la_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    file_picker_button("📁", "nu_la_out_opt", "nu_la_out_opt_browse", "Abrir explorador de archivos.")
                
                with la_col1:
                    extra["la_out"] = st.text_input("LA (enlace o ruta)", key="nu_la_out_opt")
    
    # _____________________________________
    # Erasmus IN
    # _____________________________________

    elif tipo_norm == PROGRAM_ERASMUS_IN:
        with st.container(border=True):


            col1, col2 = st.columns(2)

            with col1:
                nombre = st.text_input("Nombre", key="nu_nombre")
                extra["cuatrimestre_in"] = st.selectbox(
                    "Cuatrimestre",
                    options=["", "1", "2"],
                    key="nu_cuatri_in"
                )
                extra["pais_in"] = st.selectbox(
                    "País",
                    options=COUNTRY_OPTIONS,
                    key="nu_pais_in"
                )
                extra["firmado_la"] = "x" if st.checkbox(
                    "LA firmado",
                    key="nu_firmado_la"
                ) else ""

            with col2:
                apellidos = st.text_input("Apellidos", key="nu_apellidos")
                destino_origen = st.text_input(
                    "Origen (universidad)",
                    key="nu_destino_origen"
                )

                la_col1, la_col2 = st.columns([3, 1])
                with la_col1:
                    extra["la_in"] = st.text_input(
                        "LA (enlace o ruta)",
                        key="nu_la_in"
                    )
                with la_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    file_picker_button(
                        "📁",
                        "nu_la_in",
                        "nu_la_in_browse",
                        "Abrir explorador de archivos."
                    )

            # ─────────────────────────────
            # ASIGNATURAS (YA DENTRO)
            # ─────────────────────────────

            st.divider()
            st.markdown("#### 📚 Asignaturas")

            materias_key = "nu_materias_in"
            # Asegurar que materias siempre sea una lista
            if materias_key not in st.session_state or not isinstance(st.session_state[materias_key], list):
                st.session_state[materias_key] = []
            materias = st.session_state[materias_key]

            cuatrimestre_seleccionado = st.session_state.get("nu_cuatri_in", "")

            if cuatrimestre_seleccionado:
                asignaturas_sugerencias = [
                    a["asignatura"]
                    for a in asignaturas_catalog
                    if a.get("cuat") == cuatrimestre_seleccionado
                ]
            else:
                asignaturas_sugerencias = [
                    a["asignatura"]
                    for a in asignaturas_catalog
                ]

            header_cols = st.columns([8, 1])

            with header_cols[0]:
                st.caption("Nombre de la asignatura")

            with header_cols[1]:
                if st.button("➕ Añadir", key=f"{materias_key}_add"):
                    materias.append({"nombre": ""})

            delete_idx = None

            for i, mat in enumerate(materias):

                row_cols = st.columns([8, 1])

                with row_cols[0]:
                    valor_actual = mat.get("nombre", "")

                    seleccion = st.selectbox(
                        f"Asignatura {i+1}",
                        options=asignaturas_sugerencias,
                        index=asignaturas_sugerencias.index(valor_actual)
                            if valor_actual in asignaturas_sugerencias else None,
                        key=f"{materias_key}_select_{i}",
                        label_visibility="collapsed",
                        placeholder="Seleccionar o escribir...",
                        accept_new_options=True
                    )

                    mat["nombre"] = seleccion if seleccion else ""

                with row_cols[1]:
                    if st.button(
                        "❌",
                        key=f"{materias_key}_del_{i}",
                        help="Eliminar asignatura",
                        type="secondary",
                        width='stretch'
                    ):
                        delete_idx = i

            if delete_idx is not None:
                materias.pop(delete_idx)            
        
    # _____________________________________
    # SICUE OUT
    # _____________________________________

    elif tipo_norm == PROGRAM_SICUE_OUT:
        with st.container(border=True):
            
            # Campos comunes
            col1, col2 = st.columns(2)
            with col1:
                nombre = st.text_input("Nombre", key="nu_nombre")
                email = st.text_input("Email", key="nu_email")
            with col2:
                apellidos = st.text_input("Apellidos", key="nu_apellidos")
                destino_origen = st.text_input("Destino (universidad)", key="nu_destino_origen")
            
            # Campos específicos
            col1, col2 = st.columns(2)
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
                    st.toast("La duración debe ser un número", icon="⚠️")
                    extra["dur_sicue"] = ""
                else:
                    extra["dur_sicue"] = dur_sicue_val
                la_col1, la_col2 = st.columns([3, 1])
                with la_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    file_picker_button("📁", "nu_la_sicue", "nu_la_sicue_browse", "Abrir explorador de archivos.")
                with la_col1:
                    extra["la_in"] = st.text_input("LA (enlace o ruta)", key="nu_la_sicue")
            with col2:
                extra["estado_firmas"]  = st.selectbox("Estado de firmas", ESTADOS_FIRMA, key="nu_estado")
                extra["coord_dest"] = st.text_input("Coordinador en destino", key="nu_coord_dest")

                plan_col1, plan_col2 = st.columns([3, 1])
                with plan_col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    file_picker_button("📁", "nu_plan_sic_out", "nu_plan_sic_out_browse", "Abrir explorador de archivos.")
                with plan_col1:
                    extra["plan_sic_out"] = st.text_input(
                        "Propuesta alumno LA (ruta o enlace)",
                        key="nu_plan_sic_out",
                    )
    
    # — fila con los dos botones: Crear y Abrir Excel (dinámico) —
    
    bcol1, bcol2 = st.columns([1, 1], gap="small")
    
    with bcol1:
        open_clicked = st.button(open_label, width='stretch', type="secondary")
    
    with bcol2:
        submit_clicked = st.button("Crear estudiante", width='stretch', type="primary")
    
    # ────────────────────────────────────────────────────────────────
    # ACCIONES DE BOTONES
    # ────────────────────────────────────────────────────────────────
    if open_clicked:
        if xlsx_for_tipo:
            ok2, err2 = open_in_system(os.path.abspath(xlsx_for_tipo))
            if not ok2:
                st.warning(f"No se pudo abrir el archivo: {err2}")
        else:
            st.warning(f"No hay Excel configurado para '{tipo_norm}'.")
        st.stop()  # evitar validar/guardar cuando solo se quiso abrir

    if not submit_clicked:
        return None

    # ────────────────────────────────────────────────────────────────
    # VALIDACIONES
    # ────────────────────────────────────────────────────────────────
    validator = DataValidator()

    
    # Campos obligatorios con normalización
    nombre_val = (nombre or "").strip()
    destino_val = (destino_origen or "").strip()
    
    if not nombre_val:
        validator._add_error("nombre", "El nombre es obligatorio")
    else:
        validator.cleaned_data["nombre"] = nombre_val
    
    if not destino_val:
        validator._add_error("destino_origen", "El destino/universidad es obligatorio")
    else:
        validator.cleaned_data["destino_origen"] = destino_val
    
    # Campos opcionales (añadir a cleaned_data si existen)
    apellidos_val = (apellidos or "").strip()
    if apellidos_val:
        validator.cleaned_data["apellidos"] = apellidos_val
    
    email_val = (email or "").strip()
    if email_val:
        validator.cleaned_data["email"] = email_val
    
    # Validaciones específicas por tipo con normalización
    if tipo_norm == PROGRAM_ERASMUS_OUT:
        pais_val = (extra.get("pais_out") or "").strip()
        if not pais_val:
            validator._add_error("pais_out", "El país es obligatorio")
        else:
            validator.cleaned_data["pais_out"] = pais_val
            
        if extra.get("dur_out"):
            validator.validate_field("dur_out", extra["dur_out"], is_duration_valid(),
                                    normalizer=lambda x: str(safe_int_convert(x, default=0)))
            
    elif tipo_norm == PROGRAM_ERASMUS_IN:
        pais_val = (extra.get("pais_in") or "").strip()
        if not pais_val:
            validator._add_error("pais_in", "El país es obligatorio")
        else:
            validator.cleaned_data["pais_in"] = pais_val
            
    elif tipo_norm == PROGRAM_SICUE_OUT:
        ciudad_val = (extra.get("ciudad_sicue") or "").strip()
        if not ciudad_val:
            validator._add_error("ciudad_sicue", "La ciudad es obligatoria")
        else:
            validator.cleaned_data["ciudad_sicue"] = ciudad_val
            
        if extra.get("dur_sicue"):
            validator.validate_field("dur_sicue", extra["dur_sicue"], is_duration_valid(),
                                    normalizer=lambda x: str(safe_int_convert(x, default=0)))
    
    if not validator.is_valid():
        st.toast(f"{validator.get_error_messages()}", icon="❌")
        return None
    
    # Obtener datos normalizados
    clean_data = validator.get_clean_data()


    # ────────────────────────────────────────────────────────────────
    # GEOCODING (solo para SICUE OUT)
    # ────────────────────────────────────────────────────────────────
    lat, lon = None, None
    if tipo_norm == PROGRAM_SICUE_OUT:
        lat, lon, gerr = _geocode_cached(destino_origen.strip())
        if lat is None or lon is None:
            ciudad_opt = (extra.get("ciudad_sicue") or "").strip()
            if ciudad_opt:
                lat, lon, gerr2 = _geocode_cached(ciudad_opt)
                if gerr and not gerr2:
                    gerr = None  # mejoró con ciudad
        if gerr:
            st.warning(f"No se pudo geocodificar '{destino_origen}': {gerr}")
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
        
        # Obtener valores globales del estudiante para todas las asignaturas
        cuat_global = extra.get("cuatrimestre_in", "")
        firmado_global = extra.get("firmado_la", "")
        la_global = extra.get("la_in", "")
        
        for m in st.session_state.get("nu_materias_in", []):
            nom = (m.get("nombre") or "").strip()
            if not nom:
                # ignoramos filas vacías
                continue
            materias_payload.append({
                "asignatura": nom,
                "cuat": cuat_global,
                "firmado": firmado_global,
                "link_la": la_global
            })
        
        # Validar que hay al menos una asignatura
        if not materias_payload:
            st.toast("Debes añadir al menos una asignatura para Erasmus IN", icon="❌")
            return None
        
        if materias_payload:
            payload["materias_in"] = materias_payload
    else:
        materias_payload = []


    # ────────────────────────────────────────────────────────────────
    # GUARDAR EN EXCEL
    # ────────────────────────────────────────────────────────────────
    xlsx_path = config.get(tipo_norm)
    if not xlsx_path:
        st.toast(f"No hay Excel configurado para '{tipo_norm}'. Ábrelo en 'Cambiar rutas'.", icon="❌")
        return None

    ok, err = append_user_to_excel(xlsx_path, tipo_norm, payload, sheet_name=selected_sheet)
    if not ok:
        st.toast(f"Error guardando en Excel: {err}", icon="❌")
        return None

    # Marcamos éxito y forzamos incremento de `data_version` para invalidar caches
    st.session_state["_user_saved"] = True
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    st.rerun()
