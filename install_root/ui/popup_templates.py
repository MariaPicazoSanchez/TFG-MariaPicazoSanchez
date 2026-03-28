import os
import logging
import unicodedata
import streamlit as st
import html
from urllib.parse import quote
from security import get_api_token
from .styles import POPUP_STYLES
from domain import CITIES_ES
from domain.validators import safe_int_to_str, normalize_int
from .popup_helpers import (
    _normalize_estudiantes,
    _clean,
    _view_line,
    _view_link,
)
from .popup_materias import build_materias_blocks
import json
from persistence.data_access_mobility import get_universities_from_coords_sheet, get_universities_from_sicue_data
from ui.new_user_view import get_university_country_map, get_university_responsable_map
from constants import PROGRAM_ERASMUS_IN, PROGRAM_ERASMUS_OUT, PROGRAM_SICUE_OUT
config = st.session_state.get("config", {})
logger = logging.getLogger("movilidad_ui")

# URL del endpoint que guarda en Excel
API_TOKEN = get_api_token()
# Obtener la URL del API desde la variable de entorno (con puerto dinámico)
API_URL = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
FORM_ACTION = f"{API_URL}/update_student"

import re
import pandas as pd
import streamlit as st



def _load_asignaturas_catalog(config: dict, sheet_name: str | None = None) -> list:
    """Carga el catálogo de asignaturas de una hoja concreta, con caché en session_state."""
    ruta = (config.get("Erasmus IN") or "").strip()
    # La clave incluye sheet_name para que cada hoja tenga su propia entrada de caché
    cache_key = f"_asignaturas_catalog_cache_v4_{ruta}_{sheet_name or ''}"

    # Si hay una entrada en caché pero está vacía, la descartamos para forzar recarga
    # (puede haberse guardado vacía por el bug del return [] prematuro)
    if cache_key in st.session_state and not st.session_state[cache_key]:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        try:
            from persistence import get_asignaturas_catalog
            result = get_asignaturas_catalog(config, sheet_name=sheet_name)
            st.session_state[cache_key] = result
            logger.debug(
                "[catalog] Cargado para sheet='%s': %d asignaturas, primer item: %s",
                sheet_name, len(result), result[0] if result else None
            )
        except Exception as e:
            logger.warning("No se pudo cargar catálogo de asignaturas: %s", e)
            st.session_state[cache_key] = []

    return st.session_state.get(cache_key, [])

def _normalize_str(s):
    s = str(s or "").strip().lower()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return s


def generate_dynamic_popup(row, programa: str, row_index: int) -> str:
    """
    Popup con:
      - vista de información por defecto (solo lectura)
      - bloque de edición que se muestra al abrir el <details>

    Asignaturas (materias_in) SOLO si el alumno realmente las tiene.
    Botón para abrir el Excel correspondiente al tipo (Erasmus IN/OUT, SICUE OUT).

    Sin JavaScript: solo HTML + CSS.
    """
    universidad = html.escape(str(row.get("universidad", "")) or "Sin universidad")
    universidad_raw = str(row.get("universidad", "")).strip()
    pais = html.escape(str(row.get("pais", "") or ""))
    # Buscar la ciudad en varias columnas posibles del row (por si tiene distinto nombre)
    ciudad_raw = None
    for ck in ("ciudad", "Ciudad", "ciudad destino", "Ciudad destino", "City", "city", "localidad", "poblacion"):
      if ck in row and row.get(ck) and str(row.get(ck)).strip():
        ciudad_raw = row.get(ck)
        break
    ciudad = html.escape(str(ciudad_raw or "") )

    row_id = str(row.get("id", ""))
    row_id_attr = html.escape(row_id, quote=True)

    config = st.session_state.get("config", {})
    universidades_in  = get_universities_from_coords_sheet(config.get(PROGRAM_ERASMUS_IN, ""))
    universidades_out = get_universities_from_coords_sheet(config.get(PROGRAM_ERASMUS_OUT, ""))
    universidades_sicue, ciudad_map_sicue, _ = (
        get_universities_from_sicue_data(config.get(PROGRAM_SICUE_OUT, ""))
        if config.get(PROGRAM_SICUE_OUT) else ([], {}, {})
    )
    pais_map_out = get_university_country_map(config.get(PROGRAM_ERASMUS_OUT, ""))
    pais_map_in  = get_university_country_map(config.get(PROGRAM_ERASMUS_IN, ""))
    resp_map_out = get_university_responsable_map(config.get(PROGRAM_ERASMUS_OUT, ""))
    excel_path = config.get(programa)
    materias_excel_path = config.get(f"{programa}_MATERIAS")

    import pandas as pd
    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    # Filtrar estudiantes con nombre NA, nan, null, 0 o vacío
    estudiantes_filtrados = []
    for e in estudiantes:
      nombre = str(e.get("estudiante", "")).strip().lower()
      val = e.get("estudiante")
      try:
        is_na = pd.isna(val)
      except Exception:
        is_na = False
      if is_na or nombre in ("", "nan", "0") or val is None:
        continue
      estudiantes_filtrados.append(e)
    estudiantes = estudiantes_filtrados
    n = len(estudiantes)

    # Subtítulo: Programa · País (para todos los tipos de movilidad)
    subtitle_parts = []
    if programa:
        subtitle_parts.append(html.escape(programa))
    if pais:
        subtitle_parts.append(pais)
    
    subtitle_text = " · ".join(subtitle_parts)
    subtitle_html = f"<div class='sub'>{subtitle_text}</div>" if subtitle_text else ""

    # Botón "Abrir Excel <programa>" SOLO si tenemos ruta local
    excel_btn_html = ""
    if excel_path and not str(excel_path).lower().startswith(("http://", "https://")):
        qp = quote(str(excel_path))
        programa_label = html.escape(programa)
        excel_btn_html = (
            f"<a class='excel-btn' href='/?open_pdf={qp}' "
            f"title='Abrir Excel de {programa_label}' "
            "target='opener'>Abrir Excel</a>"
        )

    items_html = []

    if not estudiantes:
        items_html.append(
            "<li class='pitem'>"
            "<div class='pname'>Sin estudiantes</div>"
            "</li>"
        )
    else:
        for idx, e in enumerate(estudiantes):
            # IDs base para este estudiante (se usan en materias y en el formulario)
            idx_attr = html.escape(str(idx), quote=True)
            row_index_attr = html.escape(str(row_index), quote=True)

            nombre_raw = str(e.get("estudiante", "(sin nombre)"))
            nombre = html.escape(nombre_raw)
            email_val  = _clean(e.get("email"))
            
            curso_val_raw  = _clean(e.get("curso") or row.get("curso") or row.get("Curso"))
            cuatri_val_raw = _clean(e.get("cuatrimestre"))
            dur_val_raw = _clean(e.get("duracion_meses") or row.get("duracion meses") or row.get("Duración (meses)") or row.get("Duracion (meses)") or row.get("duracion_meses"))
            
            dur_val = safe_int_to_str(dur_val_raw)
            curso_val = safe_int_to_str(curso_val_raw)
            cuatri_val = safe_int_to_str(cuatri_val_raw)

            gest_val   = _clean(e.get("gestion_LA") or row.get("gestion_LA") or row.get("Gestión LA") or row.get("Gestion LA"))
            coord_val  = _clean(e.get("coordinador_destino") or row.get("coordinador_destino") or row.get("Coordinador en destino"))
            la_val     = _clean(e.get("link_la"))
            tor_val    = _clean(e.get("ToR") or row.get("ToR") or row.get("tor"))
            acta_val   = _clean(e.get("acta_equivalencias"))
            plan_val   = _clean(e.get("link_plan") or row.get("Plan de estudios") or row.get("Plan estudios") or row.get("Enlace plan de estudios"))
            destino_val = _clean(
              e.get("destino") or row.get("destino") or row.get("Destino") or row.get("universidad")
            )
            origen_val = _clean(
              e.get("origen")
              or row.get("origen")
              or row.get("Origen")
              or e.get("universidad de origen")
              or row.get("universidad de origen")
              or e.get("Universidad Origen")
              or row.get("Universidad Origen")
              or e.get("universidad_origen")
              or row.get("universidad_origen")
              or e.get("universidadorigen")
              or row.get("universidadorigen")
              or e.get("universidad")
              or row.get("universidad")
            )
            responsable_val = _clean(e.get("responsable") or row.get("responsable") or row.get("Responsable") or row.get("responsable programa"))
            pais_val    = _clean(e.get("pais") or row.get("pais") or row.get("País"))
            # Normalizar ciudad consultando varias claves tanto en el estudiante como en la fila
            ciudad_val  = _clean(
              e.get("ciudad")
              or e.get("Ciudad")
              or row.get("ciudad")
              or row.get("Ciudad")
              or row.get("ciudad destino")
              or row.get("Ciudad destino")
              or row.get("city")
              or row.get("localidad")
              or row.get("poblacion")
            )
            # Materias delegadas al módulo popup_materias
            # Determinar hoja: intentar obtenerlo de nivel raíz, o extraerlo de materias_in
            # Obtener la hoja del curso del estudiante: primero de sus materias_in,
            # luego del campo _sheet_name directo, y como fallback el filtro global.
            _student_sheet = ""
            _mat_in = e.get("materias_in") if isinstance(e, dict) else []
            if _mat_in and isinstance(_mat_in, list):
                _student_sheet = str(_mat_in[0].get("sheet_name", "")).strip()
            if not _student_sheet:
                _student_sheet = (e.get("_sheet_name") or "").strip()

            _global_sheet = st.session_state.get("global_sheet")

            # Priorizar SIEMPRE el curso real del estudiante. Si no existe, usar el global.
            _sheet_for_catalog = _student_sheet if _student_sheet else (_global_sheet if _global_sheet != "Todas" else None)
            
            has_materias, materias_view_html, materias_edit_block = build_materias_blocks(
                e,
                programa,
                row_index_attr=row_index_attr,
                idx_attr=idx_attr,
                asignaturas_catalog=_load_asignaturas_catalog(config, sheet_name=_sheet_for_catalog),
            )

            # Targeta del estudiante
            toggle_id = f"edit-{row_index}-{idx}"
            prog_attr = html.escape(programa, quote=True)
            universidad_options_in = "\n".join(
                f'<option value="{html.escape(u, quote=True)}"{" selected" if _clean(origen_val) == _clean(u) else ""}>{html.escape(u)}</option>'
                for u in universidades_in
            )
            universidad_options_out = "\n".join(
                f'<option value="{html.escape(u, quote=True)}"{" selected" if _clean(destino_val) == _clean(u) else ""}>{html.escape(u)}</option>'
                for u in universidades_out
            )
            universidad_options_sicue = "\n".join(
                f'<option value="{html.escape(u, quote=True)}"{" selected" if _clean(destino_val) == _clean(u) else ""}>{html.escape(u)}</option>'
                for u in universidades_sicue
            )

            
            nombre_field = f'''
                          <div class="field">
                            <label>Nombre</label>
                            <input name="estudiante" value="{html.escape(_clean(e.get("estudiante")), quote=True)}">
                          </div>'''

            email_field = f'''
                              <div class="field">
                                <label>Email</label>
                                <input name="email" value="{html.escape(email_val, quote=True)}">
                              </div>'''

            curso_field = f'''
                      <div class="field">
                      <label>Curso</label>
                      <select name="curso">
                        <option value="" {("selected" if curso_val not in ("1", "2", "3", "4") else "")}>-</option>
                        <option value="1" {("selected" if curso_val == "1" or curso_val == "1.0" else "")}>1</option>
                        <option value="2" {("selected" if curso_val == "2" or curso_val == "2.0" else "")}>2</option>
                        <option value="3" {("selected" if curso_val == "3" or curso_val == "3.0" else "")}>3</option>
                        <option value="4" {("selected" if curso_val == "4" or curso_val == "4.0" else "")}>4</option>
                      </select>
                      </div>'''

            cuatri_field = f'''
                              <div class="field">
                                <label>Cuatrimestre</label>
                                <select name="cuatrimestre">
                                  <option value="" {("selected" if cuatri_val not in ("1", "2") else "")}>-</option>
                                  <option value="1" {("selected" if cuatri_val == "1" or cuatri_val == "1.0" else "")}>1</option>
                                  <option value="2" {("selected" if cuatri_val == "2" or cuatri_val == "2.0" else "")}>2</option>
                                </select>
                              </div>'''

            dur_field = f'''
                      <div class="field">
                      <label>Duración (meses)</label>
                      <input name="duracion_meses" type="number" step="1" value="{html.escape(dur_val, quote=True)}">
                      </div>'''

            gest_field = f'''
                              <div class="field">
                                <label>Gestión LA</label>
                                <select name="gestion_LA">
                                  <option value="" {("selected" if gest_val not in ("Pendiente firma del coordinador", "Pendiente firma del estudiante", "Enviado a vicerrectorado") else "")}>-</option>
                                  <option value="Pendiente firma del coordinador" {("selected" if gest_val == "Pendiente firma del coordinador" else "")}>Pendiente firma del coordinador</option>
                                  <option value="Pendiente firma del estudiante" {("selected" if gest_val == "Pendiente firma del estudiante" else "")}>Pendiente firma del estudiante</option>
                                  <option value="Enviado a vicerrectorado" {("selected" if gest_val == "Enviado a vicerrectorado" else "")}>Enviado a vicerrectorado</option>
                                </select>
                              </div>'''

            coord_field = f'''
                              <div class="field">
                                <label>Coordinador destino</label>
                                <input name="coordinador_destino" value="{html.escape(coord_val, quote=True)}">
                              </div>'''

            la_field   = build_link_file_field("LA", "link_la",
                                   la_val, row_index_attr, idx_attr, "la")

            tor_field  = build_link_file_field("ToR", "link_tor",
                                   tor_val, row_index_attr, idx_attr, "tor")

            acta_field = f'''
                              <div class="field">
                                <label>Acta de equivalencias</label>
                                <input name="acta_equivalencias" value="{html.escape(acta_val, quote=True)}">
                              </div>'''

            plan_field = build_link_file_field("Propuesta Alumno LA", "link_plan",
                                   plan_val, row_index_attr, idx_attr, "plan")

            
            destino_field = f'''
              <div class="field">
                <label>Universidad de destino</label>
                <input name="destino" list="universidades_out_{idx_attr}" value="{html.escape(destino_val, quote=True)}" data-autofill-map="pais_out" data-autofill-target="pais_{row_index_attr}_{idx_attr}" data-ciudad-warn="ciudad_warn_{row_index_attr}_{idx_attr}"
                       data-ciudad-field="ciudad_{row_index_attr}_{idx_attr}"
                       oninput="_uniAutofill(this); _ciudadWarn(this);">
                <datalist id="universidades_out_{idx_attr}">
                  {universidad_options_out}
                </datalist>
              </div>'''

            destino_field_sicue = f'''
              <div class="field">
                <label>Universidad de destino</label>
                <input name="destino"
                       list="universidades_sicue_{idx_attr}"
                       value="{html.escape(destino_val, quote=True)}"
                       data-autofill-map="ciudad_sicue"
                       data-autofill-target="ciudad_{row_index_attr}_{idx_attr}"
                       oninput="_uniAutofill(this)">
                <datalist id="universidades_sicue_{idx_attr}">
                  {universidad_options_sicue}
                </datalist>
              </div>'''

            origen_field = f'''
              <div class="field">
                <label>Universidad de origen</label>
                <input name="origen" list="universidades_in_{idx_attr}" value="{html.escape(origen_val, quote=True)}" data-autofill-map="pais_in" data-autofill-target="pais_{row_index_attr}_{idx_attr}" oninput="_uniAutofill(this)">
                <datalist id="universidades_in_{idx_attr}">
                  {universidad_options_in}
                </datalist>
              </div>'''

            responsable_field = f'''
                              <div class="field">
                                <label>Responsable</label>
                                <input name="responsable" value="{html.escape(_clean(responsable_val), quote=True)}">
                              </div>'''

            from .new_user_view import COUNTRY_OPTIONS
            _pais_map_actual = pais_map_out if "ERASMUS OUT" in (programa or "").upper() else pais_map_in
            _pais_auto = _pais_map_actual.get((destino_val or origen_val or "").strip()) or pais_val or ""
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
                <datalist id="pais_dl_{row_index_attr}_{idx_attr}">
                  {pais_options_dl}
                </datalist>
              </div>'''

            _ciudad_auto = ciudad_map_sicue.get((destino_val or "").strip()) or ciudad_val or ""
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
                  <datalist id="ciudad_dl_{row_index_attr}_{idx_attr}">
                    {ciudad_options_dl}
                  </datalist>
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
                         value="{html.escape(ciudad_val, quote=True)}">
                </div>'''
            
            prog_upper = (programa or "").upper()
            grid_fields = [nombre_field, email_field]

            # SICUE OUT: nombre, email, duración, coordinador destino, gestión LA, LA, plan, destino, ciudad
            if "SICUE" in prog_upper:
                grid_fields += [dur_field, coord_field, gest_field, la_field, plan_field, destino_field_sicue, ciudad_field_sicue]

            # Erasmus OUT: nombre, email, curso, duración, LA, plan, ToR, destino, país, ciudad
            elif "ERASMUS OUT" == prog_upper:
                grid_fields += [curso_field, dur_field, la_field, plan_field, tor_field, destino_field, pais_field, ciudad_field]

            # Erasmus IN: nombre, email, cuatrimestre, LA, origen, país, ciudad
            elif "ERASMUS IN" == prog_upper:
              grid_fields = [nombre_field]
              grid_fields += [cuatri_field, la_field, origen_field, pais_field]
              materias = e.get("materias_in") if isinstance(e, dict) else []
              firmado_val = ""
              firmado_label = "No firmado"
              firmado_color = "#e0e0e0"
              if materias and isinstance(materias, list):
                firmado_raw = str(materias[0].get("firmado", "")).strip().lower()
                firmado_val = "x" if firmado_raw in ("x", "1", "s", "si", "sí", "true", "t") else ""
                if firmado_val == "x":
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
              grid_fields += [firmado_field]
            else:
                materias = []

            # === BLOQUES DE VISTA SEGÚN TIPO DE PROGRAMA ===
            view_small = []
            view_extras = []

            if "SICUE" in prog_upper:
              view_small.append(_view_line("Email", email_val))
              view_small.append(_view_line("Duración (meses)", dur_val))
              view_small.append(_view_line("Destino", destino_val))
              view_small.append(_view_line("Ciudad", ciudad_val))
              view_small.append(_view_line("Gestión LA", gest_val))
              view_small.append(_view_line("Coordinador destino", coord_val))
              view_small.append(_view_link("Learning Agreement", la_val, open_in_system=True))
              view_small.append(_view_link("Propuesta Alumno LA", plan_val, open_in_system=True))

            elif "ERASMUS OUT" == prog_upper:
              view_small.append(_view_line("Email", email_val))
              view_small.append(_view_line("Curso", curso_val))
              view_small.append(_view_line("Duración (meses)", dur_val))
              view_small.append(_view_line("Ciudad", ciudad_val))
              view_small.append(_view_line("Destino", destino_val))
              view_small.append(_view_line("País", pais_val))
              view_small.append(_view_link("Learning Agreement", la_val, open_in_system=True))
              view_small.append(_view_link("Propuesta Alumno LA", plan_val, open_in_system=True))
              view_small.append(_view_link("ToR", tor_val, open_in_system=True))

            elif "ERASMUS IN" == prog_upper:
              view_small.append(_view_line("Cuatrimestre", cuatri_val))
              view_small.append(_view_line("Origen", origen_val))
              view_small.append(_view_line("País", pais_val))
              # Mostrar enlace de LA y estado de firmado
              firmado_status = "No firmado"
              if has_materias and isinstance(materias, list) and materias:
                firmado_raw = str(materias[0].get("firmado", "")).strip().lower()
                if firmado_raw in ("x", "1", "s", "si", "sí", "true", "t"):
                  firmado_status = "Firmado"
              la_html = _view_link("Learning Agreement", la_val, open_in_system=True)
              firmado_html = f'<span style="margin-left:0.5em;font-weight:600;">· {firmado_status}</span>'
              view_small.append(f'<span style="display:inline-flex;align-items:center;gap:0.5em;">{la_html}{firmado_html}</span>')
              if has_materias and materias_view_html:
                view_extras.append(materias_view_html)

            else:
              view_small.append(_view_line("Email", email_val))
              view_small.append(_view_line("Curso", curso_val))
              view_small.append(_view_line("Cuatrimestre", cuatri_val))
              view_small.append(_view_line("Duración (meses)", dur_val))
              view_small.append(_view_line("Ciudad", ciudad_val))
              view_small.append(_view_line("Gestión LA", gest_val))
              view_small.append(_view_line("Coordinador destino", coord_val))
              view_small.append(_view_link("Learning Agreement", la_val, open_in_system=True))
              view_small.append(_view_link("ToR", tor_val, open_in_system=True))
              view_small.append(_view_link("Acta de equivalencias", acta_val, open_in_system=True))
              view_small.append(_view_link("Propuesta Alumno LA", plan_val, open_in_system=True))

              if has_materias and materias_view_html:
                  view_extras.append(materias_view_html)

            view_small_html = "".join(view_small)
            view_extras_html = "".join(view_extras)
            edit_fields_html = "\n".join(grid_fields)

            items_html.append(f"""
              <li class="pitem">
                <details class="pdetails">
                  <summary>
                    <div class="summary-row">
                      <div class="avatar">{html.escape((nombre_raw or ' ').strip()[:1].upper())}</div>
                      <div class="meta">
                        <div class="pname">{nombre}</div>
                      </div>
                    </div>
                  </summary>

                  <div class="pcontent">
                    <input type="checkbox" id="{toggle_id}" class="edit-toggle">

                    <div class="block view-block">
                      <div class="small">
                        {view_small_html}
                      </div>
                      <div class="extras">
                        {view_extras_html}
                      </div>
                      <div class="view-actions">
                        <label for="{toggle_id}" class="btn-icon edit-btn" title="Editar">
                          ✏️ <span>Editar</span>
                        </label>
                      </div>
                    </div>

                    <div class="block edit-block">
                      <form
                        id="edit-form-{row_index_attr}-{idx_attr}"
                        class="edit-form"
                        action="{FORM_ACTION}"
                        method="POST"
                        target="opener"
                      >
                        <!-- identificadores -->
                        <iframe name="opener" style="display:none;width:0;height:0;border:0;"></iframe>
                        <input type="hidden" name="token" value="{API_TOKEN}">
                        <input type="hidden" name="row_index" value="{row_index_attr}">
                        <input type="hidden" name="save_student" value="1">
                        <input type="hidden" name="programa" value="{prog_attr}">
                        <input type="hidden" name="idx" value="{idx_attr}">
                        <!--  mandamos también la ruta del Excel  y las materias-->
                        <input type="hidden" name="excel_path" value="{str(excel_path or '').replace('"', '&quot;')}">
                        <input type="hidden" name="materias_excel_path" value="{str(materias_excel_path or '').replace('"', '&quot;')}">
                        <input type="hidden" name="old_email" value="{html.escape(str(email_val or ''), quote=True)}">
                        <input type="hidden" name="old_nombre" value="{html.escape(str(nombre_raw or ''), quote=True)}">
                        <input type="hidden" name="students_sheet_name" value="{html.escape(str(e.get('_sheet_name') or ''), quote=True)}">
                        <input type="hidden" name="materias_sheet_name" value="{html.escape(str(e.get('materias_sheet_name') or ''), quote=True)}">


                        <div class="edit-panel-inner">
                          <div class="form-grid">
                            {edit_fields_html}
                          </div>

                          {materias_edit_block}

                          <div class="edit-actions">
                            <label for="{toggle_id}" class="btn-icon cancel-btn" title="Cancelar">✖</label>
                            <button type="submit" class="btn save-btn" title="Guardar"
                              onclick="var b=this; window._saveBtnRef=b; window._saveBtnTimeout=setTimeout(function(){{b.disabled=true; b.textContent='\u23f3 Guardando...';}},0);">Guardar</button>
                          </div>
                          <div class="recarga-toast">
                            ⚠️ Recarga la página para ver los cambios actualizados.
                          </div>
                          <div class="hint">
                            Los cambios se guardan en el Excel de {html.escape(programa)}. 
                          </div>
                        </div>
                      </form>
                    </div> <!-- edit-block -->
                  </div> <!-- pcontent -->
                </details>
              </li>
            """)

    responsable_uni = resp_map_out.get(universidad_raw, "")
    resp_chip_html = (
        f'<span class="resp-chip">👤 {html.escape(responsable_uni)}</span>'
        if responsable_uni else ""
    )

    html_out = f"""
    <div class="al-popup">

      <header class="head">
        <div class="head-top">
          <div class="title">{universidad}</div>
          {resp_chip_html}
        </div>
        <div class="head-bottom">
          <div class="badges">
            <span class="badge count">{n}</span>
          </div>
          {excel_btn_html}
        </div>
      </header>
      {subtitle_html}
      <ul class="plist">
        {''.join(items_html)}
      </ul>

      <style>
      {POPUP_STYLES}
      </style>

    </div>
    """
    return html_out
def build_link_file_field(label, input_name, current_value,
                          row_index_attr, idx_attr, slug):
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


def get_autofill_script(config: dict) -> str:
    """
    Devuelve el <script> de autocompletado universidad->país/ciudad
    para inyectarlo en el mapa principal (fuera del popup).
    Debe llamarse desde show_map con m.get_root().html.add_child(folium.Element(...))
    """
    universidades_sicue, ciudad_map_sicue, _ = (
        get_universities_from_sicue_data(config.get(PROGRAM_SICUE_OUT, ""))
        if config.get(PROGRAM_SICUE_OUT) else ([], {}, {})
    )
    pais_map_out = get_university_country_map(config.get(PROGRAM_ERASMUS_OUT, ""))
    pais_map_in  = get_university_country_map(config.get(PROGRAM_ERASMUS_IN, ""))

    _pais_out_json    = json.dumps(pais_map_out,     ensure_ascii=True)
    _pais_in_json     = json.dumps(pais_map_in,      ensure_ascii=True)
    _ciudad_sicue_json = json.dumps(ciudad_map_sicue, ensure_ascii=True)

    return (
        '<script>'
        'var _AM={'
        '"pais_out":'      + _pais_out_json     + ','
        '"pais_in":'       + _pais_in_json      + ','
        '"ciudad_sicue":'  + _ciudad_sicue_json +
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
    ).replace('</script>', '</script>')