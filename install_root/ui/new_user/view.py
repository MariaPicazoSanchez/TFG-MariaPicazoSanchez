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
    normalize_academic_year,
    normalize_subject_name,
    sheet_options_for,
    suggest_next_academic_year,
)
from ._form_out   import render_erasmus_out_form
from ._form_in    import render_erasmus_in_form
from ._form_sicue import render_sicue_out_form

logger = logging.getLogger("movilidad_ui")


# ──────────────────────────────────────────────────────────────────────────────
# Limpieza del formulario
# ──────────────────────────────────────────────────────────────────────────────

def _clear_new_user_form_state() -> None:
    """
    Limpia los campos del formulario de nuevo usuario tras un guardado.

    Importante: NO toca `new_user_tipo` ni `new_user_sheet` (selectores de
    cabecera). Streamlit los gestiona por su clave; resetearlos hace que el
    desplegable salte al primer programa (Erasmus OUT) aunque el usuario
    estuviera en otro.
    """
    # Snapshot defensivo de los selectores de cabecera. Aunque la limpieza
    # de claves "nu_*" no debería afectarles, blindamos su valor por si
    # alguna otra ruta los hubiera borrado.
    _preserved = {
        k: st.session_state[k]
        for k in (
            "new_user_tipo", "new_user_sheet",
            "new_user_tipo_saved", "new_user_sheet_saved",
        )
        if k in st.session_state
    }

    for k in list(st.session_state.keys()):
        if k.startswith("nu_"):
            del st.session_state[k]

    _empty_keys = (
        "nu_nombre", "nu_apellidos", "nu_email", "nu_destino_origen", "nu_pais_out",
        "nu_ciudad", "nu_curso", "nu_la_out_opt", "nu_dur_out",
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

    # Restaurar los selectores de cabecera para que el usuario permanezca en
    # el mismo programa/curso tras guardar (p. ej. seguir creando SICUE OUT
    # sin volver a Erasmus OUT).
    for k, v in _preserved.items():
        st.session_state[k] = v


# ──────────────────────────────────────────────────────────────────────────────
# Vista principal
# ──────────────────────────────────────────────────────────────────────────────

def render_new_user_form(available_types: list[str], config: dict) -> dict | None:
    from domain import ICON_BY_TIPO
    from persistence import append_user_to_excel

    # Transferir valores de buffer (file picker) a claves de widget antes de renderizar
    for _buf_key in [k for k in st.session_state if k.startswith("_buf_nu_")]:
        _widget_key = _buf_key[len("_buf_"):]
        st.session_state[_widget_key] = st.session_state.pop(_buf_key)

    # Si el guardado anterior dejó una hoja "pendiente" (caso de hoja nueva),
    # la aplicamos al desplegable AHORA, antes de instanciar el selectbox.
    # Streamlit prohíbe escribir el state de un widget tras instanciarlo, así
    # que el guardado solo deja la marca y aquí la consumimos.
    _pending_sheet = st.session_state.pop("_nu_pending_sheet", None)
    if _pending_sheet:
        st.session_state["new_user_sheet"] = _pending_sheet
        st.session_state.pop("nu_sheet_new_name", None)

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
        # Si el widget tiene un valor válido (selección actual del usuario),
        # respetarlo siempre. Solo si no existe o quedó inválido, hidratar
        # desde el backup persistente "_saved" o caer al primero.
        cur_tipo = st.session_state.get("new_user_tipo")
        if cur_tipo not in available_types:
            cur_tipo = st.session_state.get("new_user_tipo_saved")
            if cur_tipo not in available_types:
                cur_tipo = available_types[0]
            st.session_state["new_user_tipo"] = cur_tipo
        tipo = st.selectbox(
            "Tipo de alumno",
            options=available_types,
            key="new_user_tipo",
        )
        st.session_state["new_user_tipo_saved"] = tipo
        open_label = f"{ICON_BY_TIPO.get(tipo, '📄')} Abrir {tipo}"

    with col_sheet:
        sheet_opts = sheet_options_for(cfg, tipo)
        SENT_NEW = "➕ Nueva hoja…"
        options = ([SENT_NEW] + sheet_opts) if sheet_opts else [SENT_NEW]

        # Mismo patrón que con `tipo`: solo hidratar si el widget no tiene
        # ya un valor válido (no pisar la selección actual del usuario).
        cur_sheet  = st.session_state.get("new_user_sheet")
        if cur_sheet not in options:
            cur_sheet = st.session_state.get("new_user_sheet_saved")
            global_sel = st.session_state.get("global_sheet", "Todas")
            if cur_sheet not in options:
                if global_sel in options:
                    cur_sheet = global_sel
                elif len(options) > 1:
                    cur_sheet = options[1]
                else:
                    cur_sheet = options[0]
            st.session_state["new_user_sheet"] = cur_sheet

        choice = st.selectbox("Curso", options=options, key="new_user_sheet")
        st.session_state["new_user_sheet_saved"] = choice
        new_sheet_name = None
        if choice == SENT_NEW:
            suggested = suggest_next_academic_year(sheet_opts)
            # Pre-rellena el input con la sugerencia la PRIMERA vez que aparece
            # (cuando aún no hay valor en session_state). De este modo el
            # usuario ve el curso autocompletado al abrir "➕ Nueva hoja…" y
            # solo lo edita si quiere otro.
            if "nu_sheet_new_name" not in st.session_state:
                st.session_state["nu_sheet_new_name"] = suggested
            raw_input = st.text_input(
                "Nombre de la nueva hoja",
                key="nu_sheet_new_name",
                help="Formatos aceptados: 2025-2026, 2025, 25-26 (se autocompleta a YYYY-YYYY).",
            )
            new_sheet_name = normalize_academic_year(raw_input) if raw_input else suggested
            if raw_input and new_sheet_name != raw_input.strip():
                st.caption(f"➡️ Se creará como **{new_sheet_name}**")

    selected_sheet = (
        new_sheet_name.strip() if new_sheet_name
        else (None if choice == SENT_NEW else choice)
    )
    st.session_state["nu_sheet"] = selected_sheet

    # Solo persistimos el cambio de curso global si el usuario eligió una hoja
    # YA EXISTENTE; mientras está tecleando un nombre nuevo no se toca
    # `global_sheet` para que la barra lateral no intente cargar una hoja que
    # aún no existe (eso provocaba mensajes "hoja 'XX-YY' no encontrada").
    if (choice != SENT_NEW
            and selected_sheet
            and selected_sheet != st.session_state.get("global_sheet")):
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

    # Catálogo de asignaturas (solo necesario para Erasmus IN). Si el usuario
    # está tecleando un nombre de hoja nueva, NO usamos esa hoja como fuente
    # del catálogo (no existe aún → recargas/errores en cada keystroke).
    # Caemos a la hoja existente más reciente.
    catalog_sheet = (
        selected_sheet if (choice != SENT_NEW and selected_sheet)
        else (sheet_opts[-1] if sheet_opts else None)
    )
    asignaturas_catalog = load_asignaturas_catalog(cfg, sheet_name=catalog_sheet)

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

    # Coordenadas: NO se calculan ni escriben en la fila del alumno. Las
    # coordenadas se resuelven en tiempo de carga desde la hoja "Coordenadas"
    # del propio Excel (universidad → lat,lon). Mantener la columna del curso
    # vacía evita duplicar la fuente de verdad.
    lat, lon = None, None
    st.session_state.pop("_sicue_coords_known", None)

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
                "cupo": 0,
            }]
        else:
            materias_payload = [
                {
                    "asignatura": asig_nombre_puro((m.get("nombre") or "").strip()),
                    "cuat": cuat_global,
                    "firmado": firmado_global,
                    "link_la": la_global,
                    "cupo": int(m.get("cupo") or 0),
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

    # Una vez creada la hoja en disco, sí podemos fijarla como curso global.
    if selected_sheet and selected_sheet != st.session_state.get("global_sheet"):
        save_course(selected_sheet)
        st.session_state["global_sheet"] = selected_sheet

    # Si se creó una hoja nueva, dejamos un "pendiente" para que en el próximo
    # run el desplegable se conmute a esa hoja (no se puede escribir el state
    # del widget aquí porque ya está instanciado).
    if choice == SENT_NEW and selected_sheet:
        st.session_state["_nu_pending_sheet"] = selected_sheet

    from ui._sidebar_config import _list_sheets_in_file
    from ui.stats_helpers import build_export_xlsx
    _list_sheets_in_file.clear()   # por si se creó una hoja nueva
    build_export_xlsx.clear()      # el export incluye al nuevo alumno
    st.session_state["_user_saved"]  = True
    st.session_state["data_version"] = st.session_state.get("data_version", 0) + 1
    st.rerun()
