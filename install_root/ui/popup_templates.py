
import html
import json
import logging
import os

import pandas as pd
import streamlit as st
from urllib.parse import quote

from security import get_api_token
from .styles import POPUP_STYLES
from domain import CITIES_ES
from domain.validators import safe_int_to_str
from .popup_helpers import (
    _normalize_estudiantes,
    _clean,
    _view_line,
    _view_link,
)
from .popup_materias import build_materias_blocks
from persistence.data_access_mobility import (
    get_universities_from_coords_sheet,
    get_universities_from_sicue_data,
)
from ui.new_user_view import get_university_country_map, get_university_responsable_map
from constants import PROGRAM_ERASMUS_IN, PROGRAM_ERASMUS_OUT, PROGRAM_SICUE_OUT

logger = logging.getLogger("movilidad_ui")

API_TOKEN   = get_api_token()
API_URL     = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
FORM_ACTION = f"{API_URL}/update_student"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _load_asignaturas_catalog(config: dict, sheet_name: str | None = None) -> list:
    """Carga el catálogo de asignaturas con caché en session_state.

    La clave incluye data_version para invalidar automáticamente tras
    cualquier guardado (update_student_in_excel, actualizar_materias…).
    """
    ruta = (config.get("Erasmus IN") or "").strip()
    data_version = st.session_state.get("data_version", 0)
    cache_key = f"_asignaturas_catalog_{ruta}_{sheet_name or ''}_{data_version}"

    if cache_key not in st.session_state:
        try:
            from persistence import get_asignaturas_catalog
            st.session_state[cache_key] = get_asignaturas_catalog(config, sheet_name=sheet_name)
        except Exception as exc:
            logger.warning("No se pudo cargar catálogo de asignaturas: %s", exc)
            st.session_state[cache_key] = []

    return st.session_state.get(cache_key, [])


def _is_valid_student(e: dict) -> bool:
    """Devuelve False si el estudiante tiene nombre vacío/NA."""
    val = e.get("estudiante")
    if val is None:
        return False
    try:
        if pd.isna(val):
            return False
    except Exception:
        pass
    return str(val).strip().lower() not in ("", "nan", "0")


# ─────────────────────────────────────────────────────────────────────────────
# Extracción de campos de un estudiante
# ─────────────────────────────────────────────────────────────────────────────

def _extract_student_fields(e: dict, row: dict) -> dict:
    """Extrae y normaliza todos los campos escalares de un estudiante."""
    _mat_in = e.get("materias_in") if isinstance(e, dict) else []
    _cuat_from_mat = (
        _clean(_mat_in[0].get("cuat"))
        if _mat_in and isinstance(_mat_in, list) and isinstance(_mat_in[0], dict)
        else None
    )

    return {
        "nombre_raw":      str(e.get("estudiante", "(sin nombre)")),
        "email_val":       _clean(e.get("email")),
        "curso_val":       safe_int_to_str(_clean(e.get("curso") or row.get("curso") or row.get("Curso"))),
        "cuatri_val":      safe_int_to_str(_clean(e.get("cuatrimestre")) or _cuat_from_mat),
        "dur_val":         safe_int_to_str(_clean(
            e.get("duracion_meses") or row.get("duracion meses")
            or row.get("Duración (meses)") or row.get("Duracion (meses)")
            or row.get("duracion_meses")
        )),
        "gest_val":        _clean(e.get("gestion_LA") or row.get("gestion_LA") or row.get("Gestión LA") or row.get("Gestion LA")),
        "coord_val":       _clean(e.get("coordinador_destino") or row.get("coordinador_destino") or row.get("Coordinador en destino")),
        "la_val":          _clean(e.get("link_la")),
        "tor_val":         _clean(e.get("ToR") or row.get("ToR") or row.get("tor")),
        "acta_val":        _clean(e.get("acta_equivalencias")),
        "plan_val":        _clean(e.get("link_plan") or row.get("Plan de estudios") or row.get("Plan estudios") or row.get("Enlace plan de estudios")),
        "destino_val":     _clean(e.get("destino") or row.get("destino") or row.get("Destino") or row.get("universidad")),
        "origen_val":      _clean(
            e.get("origen") or row.get("origen") or row.get("Origen")
            or e.get("universidad de origen") or row.get("universidad de origen")
            or e.get("Universidad Origen") or row.get("Universidad Origen")
            or e.get("universidad_origen") or row.get("universidad_origen")
            or e.get("universidadorigen") or row.get("universidadorigen")
            or e.get("universidad") or row.get("universidad")
        ),
        "responsable_val": _clean(e.get("responsable") or row.get("responsable") or row.get("Responsable") or row.get("responsable programa")),
        "pais_val":        _clean(e.get("pais") or row.get("pais") or row.get("País")),
        "ciudad_val":      _clean(
            e.get("ciudad") or e.get("Ciudad")
            or row.get("ciudad") or row.get("Ciudad")
            or row.get("ciudad destino") or row.get("Ciudad destino")
            or row.get("city") or row.get("localidad") or row.get("poblacion")
        ),
        "_mat_in": _mat_in,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Bloque de vista (solo lectura) por programa
# ─────────────────────────────────────────────────────────────────────────────

def _build_view_lines(
    d: dict,
    programa: str,
    has_materias: bool,
    materias_view_html: str,
) -> tuple[str, str]:
    """Devuelve (view_small_html, view_extras_html)."""
    prog_upper  = (programa or "").upper()
    view_small  = []
    view_extras = []

    if "SICUE" in prog_upper:
        view_small += [
            _view_line("Email",                d["email_val"]),
            _view_line("Duración (meses)",     d["dur_val"]),
            _view_line("Destino",              d["destino_val"]),
            _view_line("Ciudad",               d["ciudad_val"]),
            _view_line("Gestión LA",           d["gest_val"]),
            _view_line("Coordinador destino",  d["coord_val"]),
            _view_link("Learning Agreement",   d["la_val"],   open_in_system=True),
            _view_link("Propuesta Alumno LA",  d["plan_val"], open_in_system=True),
        ]

    elif prog_upper == "ERASMUS OUT":
        view_small += [
            _view_line("Email",               d["email_val"]),
            _view_line("Curso",               d["curso_val"]),
            _view_line("Duración (meses)",    d["dur_val"]),
            _view_line("Ciudad",              d["ciudad_val"]),
            _view_line("Destino",             d["destino_val"]),
            _view_line("País",                d["pais_val"]),
            _view_link("Learning Agreement",  d["la_val"],   open_in_system=True),
            _view_link("Propuesta Alumno LA", d["plan_val"], open_in_system=True),
            _view_link("ToR",                 d["tor_val"],  open_in_system=True),
        ]

    elif prog_upper == "ERASMUS IN":
        mat_in = d.get("_mat_in") or []
        firmado_status = "No firmado"
        if has_materias and mat_in:
            if str(mat_in[0].get("firmado", "")).strip().lower() in ("x", "1", "s", "si", "sí", "true", "t"):
                firmado_status = "Firmado"
        la_html      = _view_link("Learning Agreement", d["la_val"], open_in_system=True)
        firmado_html = f'<span style="margin-left:0.5em;font-weight:600;">· {firmado_status}</span>'
        view_small += [
            _view_line("Cuatrimestre", d["cuatri_val"]),
            _view_line("Origen",       d["origen_val"]),
            _view_line("País",         d["pais_val"]),
            f'<span style="display:inline-flex;align-items:center;gap:0.5em;">{la_html}{firmado_html}</span>',
        ]
        if has_materias and materias_view_html:
            view_extras.append(materias_view_html)

    else:
        view_small += [
            _view_line("Email",                d["email_val"]),
            _view_line("Curso",                d["curso_val"]),
            _view_line("Cuatrimestre",         d["cuatri_val"]),
            _view_line("Duración (meses)",     d["dur_val"]),
            _view_line("Ciudad",               d["ciudad_val"]),
            _view_line("Gestión LA",           d["gest_val"]),
            _view_line("Coordinador destino",  d["coord_val"]),
            _view_link("Learning Agreement",   d["la_val"],   open_in_system=True),
            _view_link("ToR",                  d["tor_val"],  open_in_system=True),
            _view_link("Acta de equivalencias", d["acta_val"], open_in_system=True),
            _view_link("Propuesta Alumno LA",  d["plan_val"], open_in_system=True),
        ]
        if has_materias and materias_view_html:
            view_extras.append(materias_view_html)

    return "".join(view_small), "".join(view_extras)


# ─────────────────────────────────────────────────────────────────────────────
# Campos del formulario de edición por programa
# ─────────────────────────────────────────────────────────────────────────────

def _build_edit_fields(
    d: dict,
    programa: str,
    row_index_attr: str,
    idx_attr: str,
    universidades_in: list,
    universidades_out: list,
    universidades_sicue: list,
    ciudad_map_sicue: dict,
    pais_map_out: dict,
    pais_map_in: dict,
    toggle_id: str,
    e: dict,
) -> list[str]:
    """Devuelve la lista de campos HTML del formulario de edición."""
    prog_upper = (programa or "").upper()

    # ── Campos reutilizables ──────────────────────────────────────────────────
    nombre_field = f'''
        <div class="field">
          <label>Nombre</label>
          <input name="estudiante" value="{html.escape(_clean(e.get('estudiante')), quote=True)}">
        </div>'''

    email_field = f'''
        <div class="field">
          <label>Email</label>
          <input name="email" value="{html.escape(d['email_val'], quote=True)}">
        </div>'''

    cv = d["curso_val"]
    curso_field = f'''
        <div class="field">
          <label>Curso</label>
          <select name="curso">
            <option value="" {("selected" if cv not in ("1","2","3","4") else "")}>-</option>
            <option value="1" {("selected" if cv in ("1","1.0") else "")}>1</option>
            <option value="2" {("selected" if cv in ("2","2.0") else "")}>2</option>
            <option value="3" {("selected" if cv in ("3","3.0") else "")}>3</option>
            <option value="4" {("selected" if cv in ("4","4.0") else "")}>4</option>
          </select>
        </div>'''

    qv = d["cuatri_val"]
    cuatri_field = f'''
        <div class="field">
          <label>Cuatrimestre</label>
          <select name="cuatrimestre">
            <option value="" {("selected" if qv not in ("1","2") else "")}>-</option>
            <option value="1" {("selected" if qv in ("1","1.0") else "")}>1</option>
            <option value="2" {("selected" if qv in ("2","2.0") else "")}>2</option>
          </select>
        </div>'''

    dur_field = f'''
        <div class="field">
          <label>Duración (meses)</label>
          <input name="duracion_meses" type="number" step="1" value="{html.escape(d['dur_val'], quote=True)}">
        </div>'''

    gv = d["gest_val"]
    _opts = ("Pendiente firma del coordinador", "Pendiente firma del estudiante", "Enviado a vicerrectorado")
    gest_field = f'''
        <div class="field">
          <label>Gestión LA</label>
          <select name="gestion_LA">
            <option value="" {("selected" if gv not in _opts else "")}>-</option>
            <option value="Pendiente firma del coordinador" {("selected" if gv=="Pendiente firma del coordinador" else "")}>Pendiente firma del coordinador</option>
            <option value="Pendiente firma del estudiante" {("selected" if gv=="Pendiente firma del estudiante" else "")}>Pendiente firma del estudiante</option>
            <option value="Enviado a vicerrectorado" {("selected" if gv=="Enviado a vicerrectorado" else "")}>Enviado a vicerrectorado</option>
          </select>
        </div>'''

    coord_field = f'''
        <div class="field">
          <label>Coordinador destino</label>
          <input name="coordinador_destino" value="{html.escape(d['coord_val'], quote=True)}">
        </div>'''

    acta_field = f'''
        <div class="field">
          <label>Acta de equivalencias</label>
          <input name="acta_equivalencias" value="{html.escape(d['acta_val'], quote=True)}">
        </div>'''

    la_field   = build_link_file_field("LA",                "link_la",   d["la_val"],   row_index_attr, idx_attr, "la")
    tor_field  = build_link_file_field("ToR",               "link_tor",  d["tor_val"],  row_index_attr, idx_attr, "tor")
    plan_field = build_link_file_field("Propuesta Alumno LA","link_plan", d["plan_val"], row_index_attr, idx_attr, "plan")

    # ── Campos de universidad ─────────────────────────────────────────────────
    def _uni_opts(unis, selected_val):
        return "\n".join(
            f'<option value="{html.escape(u, quote=True)}"{" selected" if _clean(selected_val) == _clean(u) else ""}>{html.escape(u)}</option>'
            for u in unis
        )

    destino_field = f'''
        <div class="field">
          <label>Universidad de destino</label>
          <input name="destino" list="universidades_out_{idx_attr}"
                 value="{html.escape(d['destino_val'], quote=True)}"
                 data-autofill-map="pais_out"
                 data-autofill-target="pais_{row_index_attr}_{idx_attr}"
                 data-ciudad-warn="ciudad_warn_{row_index_attr}_{idx_attr}"
                 data-ciudad-field="ciudad_{row_index_attr}_{idx_attr}"
                 oninput="_uniAutofill(this); _ciudadWarn(this);">
          <datalist id="universidades_out_{idx_attr}">{_uni_opts(universidades_out, d["destino_val"])}</datalist>
        </div>'''

    destino_field_sicue = f'''
        <div class="field">
          <label>Universidad de destino</label>
          <input name="destino" list="universidades_sicue_{idx_attr}"
                 value="{html.escape(d['destino_val'], quote=True)}"
                 data-autofill-map="ciudad_sicue"
                 data-autofill-target="ciudad_{row_index_attr}_{idx_attr}"
                 oninput="_uniAutofill(this)">
          <datalist id="universidades_sicue_{idx_attr}">{_uni_opts(universidades_sicue, d["destino_val"])}</datalist>
        </div>'''

    origen_field = f'''
        <div class="field">
          <label>Universidad de origen</label>
          <input name="origen" list="universidades_in_{idx_attr}"
                 value="{html.escape(d['origen_val'], quote=True)}"
                 data-autofill-map="pais_in"
                 data-autofill-target="pais_{row_index_attr}_{idx_attr}"
                 oninput="_uniAutofill(this)">
          <datalist id="universidades_in_{idx_attr}">{_uni_opts(universidades_in, d["origen_val"])}</datalist>
        </div>'''

    # ── País / ciudad ─────────────────────────────────────────────────────────
    from .new_user_view import COUNTRY_OPTIONS
    _pais_map = pais_map_out if prog_upper == "ERASMUS OUT" else pais_map_in
    _pais_auto = _pais_map.get((d["destino_val"] or d["origen_val"] or "").strip()) or d["pais_val"] or ""
    pais_options_dl = "\n".join(
        f'<option value="{html.escape(p, quote=True)}">{html.escape(p)}</option>'
        for p in COUNTRY_OPTIONS if p
    )
    pais_field = f'''
        <div class="field">
          <label>País</label>
          <input name="pais"
                 id="pais_{row_index_attr}_{idx_attr}"
                 list="pais_dl_{row_index_attr}_{idx_attr}"
                 value="{html.escape(_pais_auto, quote=True)}">
          <datalist id="pais_dl_{row_index_attr}_{idx_attr}">{pais_options_dl}</datalist>
        </div>'''

    _ciudad_auto = ciudad_map_sicue.get((d["destino_val"] or "").strip()) or d["ciudad_val"] or ""
    ciudad_options_dl = "\n".join(
        f'<option value="{html.escape(c, quote=True)}">{html.escape(c)}</option>'
        for c in CITIES_ES if c
    )
    ciudad_field_sicue = f'''
        <div class="field">
          <label>Ciudad</label>
          <input name="ciudad"
                 id="ciudad_{row_index_attr}_{idx_attr}"
                 list="ciudad_dl_{row_index_attr}_{idx_attr}"
                 value="{html.escape(_ciudad_auto, quote=True)}">
          <datalist id="ciudad_dl_{row_index_attr}_{idx_attr}">{ciudad_options_dl}</datalist>
        </div>'''

    ciudad_field = f'''
        <div class="field">
          <label>Ciudad
            <span id="ciudad_warn_{row_index_attr}_{idx_attr}"
                  title="Has cambiado la universidad - revisa si esta ciudad sigue siendo correcta o bórrala."
                  style="display:none;cursor:help;margin-left:0.3rem;font-size:1.5rem;">⚠️</span>
          </label>
          <input id="ciudad_{row_index_attr}_{idx_attr}"
                 name="ciudad"
                 value="{html.escape(d['ciudad_val'], quote=True)}">
        </div>'''

    # ── Campo firmado LA (solo Erasmus IN) ────────────────────────────────────
    mat_in = d.get("_mat_in") or []
    firmado_val   = ""
    firmado_label = "No firmado"
    firmado_color = "#e0e0e0"
    if mat_in:
        if str(mat_in[0].get("firmado", "")).strip().lower() in ("x", "1", "s", "si", "sí", "true", "t"):
            firmado_val   = "x"
            firmado_label = "Firmado"
            firmado_color = "#4caf50"
    firmado_hidden_id = f"firmado-hidden-{toggle_id}"
    firmado_field = f'''
        <div class="field">
          <label>Firmado LA</label>
          <input type="hidden" name="firmado" id="{firmado_hidden_id}" value="{firmado_val}">
          <button type="button" class="toggle-btn{' active' if firmado_val == 'x' else ''}"
            style="width:100%;height:2.5rem;font-size:1.25rem;font-weight:500;border-radius:8px;border:1px solid #ddd;background:{firmado_color};color:{'#fff' if firmado_val == 'x' else '#333'};transition:background 0.2s;display:flex;align-items:center;justify-content:center;gap:0.5rem;flex:1;min-width:0;"
            onclick="this.classList.toggle('active'); this.style.background = this.classList.contains('active') ? '#4caf50' : '#e0e0e0'; this.style.color = this.classList.contains('active') ? '#fff' : '#333'; this.querySelector('span').textContent = this.classList.contains('active') ? 'Firmado' : 'No firmado'; document.getElementById('{firmado_hidden_id}').value = this.classList.contains('active') ? 'x' : '';">
            <span>{firmado_label}</span>
          </button>
        </div>'''

    # ── Ensamblado por programa ───────────────────────────────────────────────
    if "SICUE" in prog_upper:
        return [nombre_field, email_field, dur_field, coord_field, gest_field,
                la_field, plan_field, destino_field_sicue, ciudad_field_sicue]

    if prog_upper == "ERASMUS OUT":
        return [nombre_field, email_field, curso_field, dur_field, la_field,
                plan_field, tor_field, destino_field, pais_field, ciudad_field]

    if prog_upper == "ERASMUS IN":
        return [nombre_field, cuatri_field, la_field, origen_field, pais_field, firmado_field]

    # fallback
    return [nombre_field, email_field, curso_field, cuatri_field, dur_field, gest_field,
            coord_field, la_field, tor_field, acta_field, plan_field]


# ─────────────────────────────────────────────────────────────────────────────
# Tarjeta de un estudiante
# ─────────────────────────────────────────────────────────────────────────────

def _build_student_card(
    e: dict,
    row: dict,
    programa: str,
    idx: int,
    row_index: int,
    universidades_in: list,
    universidades_out: list,
    universidades_sicue: list,
    ciudad_map_sicue: dict,
    pais_map_out: dict,
    pais_map_in: dict,
    excel_path: str,
    materias_excel_path: str,
    config: dict,
) -> str:
    """Devuelve el <li class='pitem'> HTML de un estudiante."""
    idx_attr       = html.escape(str(idx),       quote=True)
    row_index_attr = html.escape(str(row_index), quote=True)
    toggle_id      = f"edit-{row_index}-{idx}"
    prog_attr      = html.escape(programa,        quote=True)

    d      = _extract_student_fields(e, row)
    nombre = html.escape(d["nombre_raw"])

    # Hoja del catálogo de asignaturas
    _mat_in = d["_mat_in"]
    _student_sheet = ""
    if _mat_in and isinstance(_mat_in, list):
        _student_sheet = str(_mat_in[0].get("sheet_name", "")).strip()
    if not _student_sheet:
        _student_sheet = (e.get("_sheet_name") or "").strip()
    _global_sheet = st.session_state.get("global_sheet")
    _sheet_for_catalog = _student_sheet or (_global_sheet if _global_sheet != "Todas" else None)

    has_materias, materias_view_html, materias_edit_block = build_materias_blocks(
        e, programa,
        row_index_attr=row_index_attr,
        idx_attr=idx_attr,
        asignaturas_catalog=_load_asignaturas_catalog(config, sheet_name=_sheet_for_catalog),
    )

    view_small_html, view_extras_html = _build_view_lines(d, programa, has_materias, materias_view_html)
    edit_fields_html = "\n".join(_build_edit_fields(
        d, programa, row_index_attr, idx_attr,
        universidades_in, universidades_out, universidades_sicue,
        ciudad_map_sicue, pais_map_out, pais_map_in,
        toggle_id, e,
    ))

    return f"""
      <li class="pitem">
        <details class="pdetails">
          <summary>
            <div class="summary-row">
              <div class="avatar">{html.escape((d['nombre_raw'] or ' ').strip()[:1].upper())}</div>
              <div class="meta"><div class="pname">{nombre}</div></div>
            </div>
          </summary>

          <div class="pcontent">
            <input type="checkbox" id="{toggle_id}" class="edit-toggle">

            <div class="block view-block">
              <div class="small">{view_small_html}</div>
              <div class="extras">{view_extras_html}</div>
              <div class="view-actions">
                <label for="{toggle_id}" class="btn-icon edit-btn" title="Editar">✏️ <span>Editar</span></label>
              </div>
            </div>

            <div class="block edit-block">
              <form id="edit-form-{row_index_attr}-{idx_attr}" class="edit-form"
                    action="{FORM_ACTION}" method="POST" target="opener">
                <iframe name="opener" style="display:none;width:0;height:0;border:0;"></iframe>
                <input type="hidden" name="token"              value="{API_TOKEN}">
                <input type="hidden" name="row_index"          value="{row_index_attr}">
                <input type="hidden" name="save_student"       value="1">
                <input type="hidden" name="programa"           value="{prog_attr}">
                <input type="hidden" name="idx"                value="{idx_attr}">
                <input type="hidden" name="excel_path"         value="{str(excel_path or '').replace('"', '&quot;')}">
                <input type="hidden" name="materias_excel_path" value="{str(materias_excel_path or '').replace('"', '&quot;')}">
                <input type="hidden" name="old_email"          value="{html.escape(str(d['email_val'] or ''), quote=True)}">
                <input type="hidden" name="old_nombre"         value="{html.escape(str(d['nombre_raw'] or ''), quote=True)}">
                <input type="hidden" name="students_sheet_name" value="{html.escape(str(e.get('_sheet_name') or ''), quote=True)}">
                <input type="hidden" name="materias_sheet_name" value="{html.escape(str(e.get('materias_sheet_name') or ''), quote=True)}">

                <div class="edit-panel-inner">
                  <div class="form-grid">{edit_fields_html}</div>
                  {materias_edit_block}
                  <div class="edit-actions">
                    <label for="{toggle_id}" class="btn-icon cancel-btn" title="Cancelar">✖</label>
                    <button type="submit" class="btn save-btn" title="Guardar"
                      onclick="var b=this; window._saveBtnRef=b; window._saveBtnTimeout=setTimeout(function(){{b.disabled=true; b.textContent='\u23f3 Guardando...';}},0);">Guardar</button>
                  </div>
                  <div class="recarga-toast">⚠️ Recarga la página para ver los cambios actualizados.</div>
                  <div class="hint">Los cambios se guardan en el Excel de {html.escape(programa)}.</div>
                </div>
              </form>
            </div>
          </div>
        </details>
      </li>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Popup principal
# ─────────────────────────────────────────────────────────────────────────────

def generate_dynamic_popup(row, programa: str, row_index: int) -> str:
    """Genera el HTML completo del popup de un marcador del mapa."""
    config = st.session_state.get("config", {})

    # Lookups (todos @st.cache_data → rápidos tras la primera llamada)
    universidades_in  = get_universities_from_coords_sheet(config.get(PROGRAM_ERASMUS_IN, ""))
    universidades_out = get_universities_from_coords_sheet(config.get(PROGRAM_ERASMUS_OUT, ""))
    universidades_sicue, ciudad_map_sicue, _ = (
        get_universities_from_sicue_data(config.get(PROGRAM_SICUE_OUT, ""))
        if config.get(PROGRAM_SICUE_OUT) else ([], {}, {})
    )
    pais_map_out = get_university_country_map(config.get(PROGRAM_ERASMUS_OUT, ""))
    pais_map_in  = get_university_country_map(config.get(PROGRAM_ERASMUS_IN, ""))
    resp_map_out = get_university_responsable_map(config.get(PROGRAM_ERASMUS_OUT, ""))
    excel_path          = config.get(programa)
    materias_excel_path = config.get(f"{programa}_MATERIAS")

    # Datos de cabecera
    universidad_raw = str(row.get("universidad", "")).strip()
    universidad     = html.escape(universidad_raw or "Sin universidad")
    pais            = html.escape(str(row.get("pais", "") or ""))

    subtitle_parts = [html.escape(programa)] if programa else []
    if pais:
        subtitle_parts.append(pais)
    subtitle_html = f"<div class='sub'>{' · '.join(subtitle_parts)}</div>" if subtitle_parts else ""

    excel_btn_html = ""
    if excel_path and not str(excel_path).lower().startswith(("http://", "https://")):
        excel_btn_html = (
            f"<a class='excel-btn' href='/?open_pdf={quote(str(excel_path))}' "
            f"title='Abrir Excel de {html.escape(programa)}' target='opener'>Abrir Excel</a>"
        )

    # Estudiantes
    estudiantes = [e for e in _normalize_estudiantes(row.get("estudiantes", [])) if _is_valid_student(e)]
    n = len(estudiantes)

    if not estudiantes:
        items_html = "<li class='pitem'><div class='pname'>Sin estudiantes</div></li>"
    else:
        items_html = "".join(
            _build_student_card(
                e, row, programa, idx, row_index,
                universidades_in, universidades_out, universidades_sicue,
                ciudad_map_sicue, pais_map_out, pais_map_in,
                excel_path, materias_excel_path, config,
            )
            for idx, e in enumerate(estudiantes)
        )

    responsable_uni = resp_map_out.get(universidad_raw, "")
    resp_chip_html  = (
        f'<span class="resp-chip">👤 {html.escape(responsable_uni)}</span>'
        if responsable_uni else ""
    )

    return f"""
    <div class="al-popup">
      <header class="head">
        <div class="head-top">
          <div class="title">{universidad}</div>
          {resp_chip_html}
        </div>
        <div class="head-bottom">
          <div class="badges"><span class="badge count">{n}</span></div>
          {excel_btn_html}
        </div>
      </header>
      {subtitle_html}
      <ul class="plist">{items_html}</ul>
      <style>{POPUP_STYLES}</style>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Campo de enlace/fichero (compartido)
# ─────────────────────────────────────────────────────────────────────────────

def build_link_file_field(label, input_name, current_value, row_index_attr, idx_attr, slug):
    safe_val = html.escape(current_value or "", quote=True)
    input_id = f"{slug}_input_{row_index_attr}_{idx_attr}"
    file_id  = f"{slug}_file_{row_index_attr}_{idx_attr}"

    return f"""
      <div class="field">
        <label>{html.escape(label)}</label>
        <div class="file-input-row"
             style="display:flex;align-items:center;gap:0.5rem;">
          <input name="{input_name}"
                 value="{safe_val}"
                 id="{input_id}"
                 style="flex:1;min-width:0;">

          <button type="button"
                  class="file-picker-btn"
                  style="
                    padding:0.7rem 0.75rem;
                    font-size:1.2rem;
                    border-radius:6px;
                    border:1px solid #ddd;
                    background:#f5f5f5;
                    display:inline-flex;
                    align-items:center;
                    gap:0.35rem;
                    cursor:pointer;
                  "
                  onclick="(function(){{
                    var inp = document.getElementById('{input_id}');
                    var pw = null;
                    try {{ pw = (window.top || window).pywebview; }} catch(e) {{}}
                    if (pw && pw.api && pw.api.pick_file) {{
                      pw.api.pick_file().then(function(d){{
                        if (d && d.ok) {{ inp.value = d.path; }}
                        else if (!d || d.reason !== 'cancelled') {{
                          document.getElementById('{file_id}').click();
                        }}
                      }}).catch(function(){{
                        document.getElementById('{file_id}').click();
                      }});
                    }} else {{
                      document.getElementById('{file_id}').click();
                    }}
                  }})();">
            📂
          </button>

          <input type="file"
                 id="{file_id}"
                 accept=".pdf,.doc,.docx,.xlsx,.xls"
                 style="display:none;"
                 onchange="
                   var inp = document.getElementById('{input_id}');
                   if (this.files && this.files[0]) {{
                     inp.value = this.files[0].name;
                   }} else {{
                     inp.value = '';
                   }}
                 ">
        </div>
      </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# Script de autocompletado para el mapa principal
# ─────────────────────────────────────────────────────────────────────────────

def get_autofill_script(config: dict) -> str:
    """
    Devuelve el <script> de autocompletado universidad->país/ciudad
    para inyectarlo en el mapa principal.
    """
    universidades_sicue, ciudad_map_sicue, _ = (
        get_universities_from_sicue_data(config.get(PROGRAM_SICUE_OUT, ""))
        if config.get(PROGRAM_SICUE_OUT) else ([], {}, {})
    )
    pais_map_out = get_university_country_map(config.get(PROGRAM_ERASMUS_OUT, ""))
    pais_map_in  = get_university_country_map(config.get(PROGRAM_ERASMUS_IN, ""))

    return (
        '<script>'
        'var _AM={'
        '"pais_out":'      + json.dumps(pais_map_out,      ensure_ascii=True) + ','
        '"pais_in":'       + json.dumps(pais_map_in,       ensure_ascii=True) + ','
        '"ciudad_sicue":'  + json.dumps(ciudad_map_sicue,  ensure_ascii=True) +
        '};'
        'function _uniAutofill(inp){'
        'var m=_AM[inp.getAttribute("data-autofill-map")]||{};'
        'var v=m[inp.value];'
        'if(!v)return;'
        'var t=document.getElementById(inp.getAttribute("data-autofill-target"));'
        'if(t){t.value=v;}'
        '}'
        'function _ciudadWarn(inp){'
        'var warnId=inp.getAttribute("data-ciudad-warn");'
        'var cityId=inp.getAttribute("data-ciudad-field");'
        'if(!warnId||!cityId)return;'
        'var warn=document.getElementById(warnId);'
        'var city=document.getElementById(cityId);'
        'if(warn&&city){'
        'warn.style.display=city.value.trim()?"inline":"none";'
        '}'
        '}'
        '</script>'
    )
