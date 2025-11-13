from __future__ import annotations
import os
import time
import streamlit as st
from sheets import sheets_for
from pdf import open_in_system
from domain import ESTADOS_FIRMA,ICON_BY_TIPO
from data_insert import append_user_to_excel, first_sheet_name

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
def _sheet_options_for(cfg: dict, tipo: str) -> list[str]:
    sheets_map = (cfg or {}).get("sheets", {}) or {}
    known = sheets_map.get(tipo) or []
    if known:
        return sorted({s for s in known if s and s != "__CSV__"})
    path = (cfg or {}).get(tipo, "")
    return [s for s in sheets_for(path) if s != "__CSV__"] if path else []


def render_new_user_form(available_types: list[str], config: dict) -> dict | None:
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

    open_clicked = False
    # Formulario
    with st.form("new_user_form", clear_on_submit=False):
        

        # — comunes (obligatorios) —
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre", key="nu_nombre")
            email  = st.text_input("Email", key="nu_email")
        with col2:
            apellidos = st.text_input("Apellidos", key="nu_apellidos")
            dest_label = "Origen (universidad)" if tipo_norm.lower() == "erasmus in" else "Destino (universidad)"
            destino_origen = st.text_input(dest_label, key="nu_destino_origen")

        # — específicos obligatorios (los que ya tenías) + OPCIONALES nuevos —
        extra: dict = {}

        if tipo_norm == "Erasmus OUT":
            # obligatorios
            extra["tor"] = st.text_input("ToR (ruta o enlace)", key="nu_tor")
            extra["curso"] = st.text_input("Curso", key="nu_curso")
            extra["acta_equivalencias"] = st.text_input("Acta de equivalencias (ruta o enlace)", key="nu_acta")
            # opcionales
            with st.expander("Campos opcionales (Erasmus OUT)", expanded=False):
                extra["dur_out"]  = st.text_input("Duración (meses) — opcional", key="nu_dur_out")
                extra["resp_prog"] = st.text_input("Responsable del programa — opcional", key="nu_resp_prog")
                extra["la_out"]    = st.text_input("LA (enlace) — opcional", key="nu_la_out_opt")
                extra["plan_out"]  = st.text_input("Plan de estudios (enlace) — opcional", key="nu_plan_out")
                # extra["destino_tabla_out"] = st.text_input("Destino (tabla) — opcional", key="nu_destino_tabla")
                extra["pais_out"]  = st.text_input("País — opcional", key="nu_pais_out")

        elif tipo_norm == "Erasmus IN":
            # obligatorios
            extra["la"]      = st.text_input("LA (enlace)", key="nu_la_in")
            extra["horario"] = st.text_input("Horario (enlace)", key="nu_horario")
            # opcionales
            with st.expander("Campos opcionales (Erasmus IN)", expanded=False):
                extra["cuatrimestre_in"]   = st.text_input("Cuatrimestre — opcional", key="nu_cuatri_in")
                # extra["uni_origen_in"]     = st.text_input("Universidad Origen — opcional", key="nu_uni_origen_opt")
                extra["pais_in"]           = st.text_input("País — opcional", key="nu_pais_in")

        elif tipo_norm == "SICUE OUT":
            # obligatorios
            extra["la"]             = st.text_input("LA (enlace)", key="nu_la_sicue")
            extra["estado_firmas"]  = st.selectbox("Estado de firmas", ESTADOS_FIRMA, key="nu_estado")
            extra["plan_estudios"]  = st.text_input("Plan de estudios (enlace)", key="nu_plan")
            # opcionales
            with st.expander("Campos opcionales (SICUE OUT)", expanded=False):
                extra["dur_sicue"]  = st.text_input("Duración (meses) — opcional", key="nu_dur_sicue")
                extra["coord_dest"] = st.text_input("Coordinador en destino — opcional", key="nu_coord_dest")
                extra["ciudad_sicue"] = st.text_input(
                    "Ciudad — opcional",
                    help="Si no se encuentran coordenadas por la universidad, se intentará con esta ciudad.",
                    key="nu_ciudad",
                )

        # — fila con los dos botones: Crear y Abrir Excel (dinámico) —
        bcol1, bcol2 = st.columns([1, 1], gap="small")
        submit_clicked = bcol1.form_submit_button("✅ Crear", use_container_width=True)
        open_clicked   = bcol2.form_submit_button(open_label, use_container_width=True)

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


    # Validaciones mínimas
    missing = []
    if not nombre.strip():          missing.append("Nombre")
    if not apellidos.strip():       missing.append("Apellidos")
    if not email.strip():           missing.append("Email")
    if not destino_origen.strip():  missing.append("Destino/Origen")
    if tipo_norm == "Erasmus OUT":
        if not extra["tor"].strip():   missing.append("ToR")
        if not extra["curso"].strip(): missing.append("Curso")
        if not extra["acta_equivalencias"].strip(): missing.append("Acta de equivalencias")
    elif tipo_norm == "Erasmus IN":
        if not extra["la"].strip():      missing.append("LA")
        if not extra["horario"].strip(): missing.append("Horario")
    elif tipo_norm == "SICUE OUT":
        if not extra["la"].strip():            missing.append("LA")
        if not extra["plan_estudios"].strip(): missing.append("Plan de estudios")

    if missing:
        st.error("Faltan campos: " + ", ".join(missing))
        return None

    # Geocodificar
    lat, lon, gerr = _geocode_cached(destino_origen.strip())
    if (lat is None or lon is None) and tipo_norm == "SICUE OUT":
        ciudad_opt = (extra.get("ciudad_sicue") or "").strip()
        if ciudad_opt:
            lat, lon, gerr2 = _geocode_cached(ciudad_opt)
            if gerr and not gerr2:
                gerr = None  # mejoró con ciudad
    if gerr:
        st.warning(f"No se pudo geocodificar ‘{destino_origen}’: {gerr}")

    payload = {
        "tipo": tipo_norm,
        "nombre": nombre.strip(),
        "apellidos": apellidos.strip(),
        "email": email.strip(),
        "destino_origen": destino_origen.strip(),
        "coordenadas": (lat, lon),
        **{k: (v.strip() if isinstance(v, str) else v) for k, v in extra.items()},
    }

    # Excel destino desde config
    xlsx_path = config.get(tipo_norm)
    if not xlsx_path:
        st.error(f"No hay Excel configurado para ‘{tipo_norm}’. Ábrelo en ‘Cambiar rutas’.")
        return None

    ok, err = append_user_to_excel(xlsx_path, tipo_norm, payload, sheet_name=selected_sheet)
    if not ok:
        st.error(f"Error guardando en Excel: {err}")
        return None

    st.success("✅ Estudiante creado y guardado en Excel.")
    # st.session_state["last_save"] = {
    #     "path": os.path.abspath(xlsx_path),
    #     "sheet": st.session_state.get("nu_sheet")
    # }
    # with st.container(border=True):
    #     c1, c2 = st.columns([3, 1], gap="small")
    #     with c1:
    #         st.caption(f"📄 {os.path.basename(xlsx_path)} — hoja: {selected_sheet or first_sheet_name(xlsx_path)}")
    #     with c2:
    #         if st.button("Abrir en Excel", key=f"open_excel_{int(time.time()*1000)}"):
    #             ok2, err2 = open_in_system(os.path.abspath(xlsx_path))
    #             if not ok2:
    #                 st.warning(f"No se pudo abrir el archivo: {err2}")
    st.toast("Guardado correctamente")
    # if "last_save" in st.session_state:
    #     last = st.session_state["last_save"]
    #     with st.container(border=True):
    #         c1, c2 = st.columns([3, 1], gap="small")
    #         with c1:
    #             st.caption(f"📄 {os.path.basename(last['path'])}"
    #                     + (f" — hoja: {last.get('sheet')}" if last.get('sheet') else ""))
    #         with c2:
    #             if st.button("Abrir en Excel", key="btn_open_excel_persist"):
    #                 ok2, err2 = open_in_system(last["path"])
    #                 if not ok2:
    #                     st.warning(f"No se pudo abrir el archivo: {err2}")
    # return payload
