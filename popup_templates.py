import streamlit as st
import html
from urllib.parse import quote
from styles import POPUP_STYLES
from js_scripts import POPUP_SAVE_STATUS_SCRIPT
from popup_helpers import (
    _normalize_estudiantes,
    _clean,
    _view_line,
    _view_link,
)
from popup_materias import build_materias_blocks


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
    pais = html.escape(str(row.get("pais", "") or ""))
    ciudad = html.escape(str(row.get("ciudad", "") or ""))

    row_id = str(row.get("id", ""))
    row_id_attr = html.escape(row_id, quote=True)

    config = st.session_state.get("config", {})
    excel_path = config.get(programa)
    materias_excel_path = config.get(f"{programa}_MATERIAS")

    # URL del endpoint que guarda en Excel
    form_action = "http://localhost:5000/update_student"


    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    n = len(estudiantes)

    # Subtítulo: Programa · Ciudad · País
    loc_text = " · ".join(p for p in (ciudad, pais) if p)  # primero ciudad, luego país

    if programa and loc_text:
        subtitle_text = f"{html.escape(programa)} · {loc_text}"
    elif programa:
        subtitle_text = html.escape(programa)
    else:
        subtitle_text = loc_text

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
            curso_val  = _clean(e.get("curso") or row.get("curso") or row.get("Curso"))
            curso = e.get("curso") or row.get("curso") or row.get("Curso")
            cuatri_val = _clean(e.get("cuatrimestre"))
            dur_val    = _clean(e.get("duracion_meses") or row.get("duracion meses") or row.get("Duración (meses)") or row.get("Duracion (meses)") or row.get("duracion_meses"))
            gest_val   = _clean(e.get("gestion_LA") or row.get("gestion_LA") or row.get("Gestión LA") or row.get("Gestion LA"))
            coord_val  = _clean(e.get("coordinador_destino") or row.get("coordinador_destino") or row.get("Coordinador en destino"))
            la_val     = _clean(e.get("link_la"))
            tor_val    = _clean(e.get("ToR") or row.get("ToR") or row.get("tor"))
            acta_val   = _clean(e.get("acta_equivalencias"))
            plan_val   = _clean(e.get("link_plan") or row.get("Plan de estudios") or row.get("Plan estudios") or row.get("Enlace plan de estudios"))
            destino_val = _clean(e.get("destino") or row.get("destino") or row.get("Destino") or row.get("universidad") )
            origen_val  = _clean(e.get("origen") or row.get("origen") or row.get("Origen") or row.get("universidad"))
            responsable_val = _clean(e.get("responsable") or row.get("responsable") or row.get("Responsable") or row.get("responsable programa"))
            pais_val    = _clean(e.get("pais") or row.get("pais") or row.get("País"))
            ciudad_val  = _clean(e.get("ciudad") or row.get("ciudad") or row.get("Ciudad"))
            # Materias delegadas al módulo popup_materias
            has_materias, materias_view_html, materias_edit_block = build_materias_blocks(
                e,
                programa,
                row_index_attr=row_index_attr,
                idx_attr=idx_attr,
            )

            # Targeta del estudiante
            toggle_id = f"edit-{row_index}-{idx}"
            prog_attr = html.escape(programa, quote=True)

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
                                <input name="curso" value="{html.escape(curso_val, quote=True)}">
                              </div>'''

            cuatri_field = f'''
                              <div class="field">
                                <label>Cuatrimestre</label>
                                <select name="cuatrimestre">
                                  <option value="" {("selected" if cuatri_val not in ("1", "2") else "")}>-</option>
                                  <option value="1" {("selected" if cuatri_val == "1" else "")}>1</option>
                                  <option value="2" {("selected" if cuatri_val == "2" else "")}>2</option>
                                </select>
                              </div>'''

            dur_field = f'''
                              <div class="field">
                                <label>Duración (meses)</label>
                                <input name="duracion_meses" value="{html.escape(dur_val, quote=True)}">
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

            la_field = f'''
                              <div class="field">
                                <label>Learning Agreement</label>
                                <input name="link_la" value="{html.escape(la_val, quote=True)}">
                              </div>'''

            tor_field = f'''
                              <div class="field">
                                <label>ToR</label>
                                <input name="ToR" value="{html.escape(tor_val, quote=True)}">
                              </div>'''

            acta_field = f'''
                              <div class="field">
                                <label>Acta de equivalencias</label>
                                <input name="acta_equivalencias" value="{html.escape(acta_val, quote=True)}">
                              </div>'''

            plan_field = f'''
                              <div class="field">
                                <label>Plan de estudios</label>
                                <input name="link_plan" value="{html.escape(plan_val, quote=True)}">
                              </div>'''

            destino_field = f'''
                              <div class="field">
                                <label>Destino</label>
                                <input name="destino" value="{html.escape(_clean(destino_val), quote=True)}">
                              </div>'''

            origen_field = f'''
                              <div class="field">
                                <label>Origen</label>
                                <input name="origen" value="{html.escape(_clean(origen_val), quote=True)}">
                              </div>'''

            responsable_field = f'''
                              <div class="field">
                                <label>Responsable</label>
                                <input name="responsable" value="{html.escape(_clean(responsable_val), quote=True)}">
                              </div>'''

            pais_field = f'''
                              <div class="field">
                                <label>País</label>
                                <input name="pais" value="{html.escape(_clean(pais_val), quote=True)}">
                              </div>'''

            ciudad_field = f'''
                              <div class="field">
                                <label>Ciudad</label>
                                <input name="ciudad" value="{html.escape(_clean(ciudad_val), quote=True)}">
                              </div>'''

            prog_upper = (programa or "").upper()
            grid_fields = [nombre_field, email_field]

            # SICUE OUT: nombre, email, duración, coordinador destino, gestión LA, LA, plan, destino, ciudad
            if "SICUE" in prog_upper:
                grid_fields += [dur_field, coord_field, gest_field, la_field, plan_field, destino_field, ciudad_field]

            # Erasmus OUT: nombre, email, curso, duración, LA, plan, ToR, responsable, destino, país
            elif "ERASMUS OUT" == prog_upper:
                grid_fields += [curso_field, dur_field, la_field, plan_field, tor_field, responsable_field, destino_field, pais_field]

            # Erasmus IN: nombre, email, cuatrimestre, LA, origen, país
            elif "ERASMUS IN" == prog_upper:
                grid_fields += [cuatri_field, la_field, origen_field, pais_field]

            # Cualquier otro (fallback): todo
            else:
                grid_fields += [
                    curso_field, cuatri_field, dur_field,
                    gest_field, coord_field,
                    la_field, tor_field, acta_field, plan_field
                ]

            # === BLOQUES DE VISTA SEGÚN TIPO DE PROGRAMA ===
            view_small = []
            view_extras = []

            view_small.append(_view_line("Email", email_val))

            if "SICUE" in prog_upper:
                view_small.append(_view_line("Duración (meses)", dur_val))
                view_small.append(_view_line("Destino", destino_val))
                view_extras.extend([
                    _view_line("Gestión LA", gest_val),
                    _view_line("Coordinador destino", coord_val),
                    _view_link("Learning Agreement", la_val, open_in_system=True),
                    _view_link("Plan de estudios", plan_val, open_in_system=True),
                    _view_line("Ciudad", ciudad_val),
                ])

            elif "ERASMUS OUT" == prog_upper:
                view_small.append(_view_line("Curso", curso_val))
                view_small.append(_view_line("Duración (meses)", dur_val))
                view_extras.extend([
                    _view_line("Destino", destino_val),
                    _view_line("País", pais_val),
                    _view_link("Learning Agreement", la_val, open_in_system=True),
                    _view_link("Plan de estudios", plan_val, open_in_system=True),
                    _view_link("ToR", tor_val, open_in_system=True),
                    _view_line("Responsable", responsable_val),
                ])

            elif "ERASMUS IN" == prog_upper:
                view_small.append(_view_line("Cuatrimestre", cuatri_val))
                view_small.append(_view_line("Origen", origen_val))
                view_extras.extend([
                    _view_line("País", pais_val),
                    _view_link("Learning Agreement", la_val, open_in_system=True),
                ])
                if has_materias and materias_view_html:
                    view_extras.append(materias_view_html)

            else:
                view_small.append(_view_line("Curso", curso_val))
                view_small.append(_view_line("Cuatrimestre", cuatri_val))
                view_extras.extend([
                    _view_line("Duración (meses)", dur_val),
                    _view_line("Gestión LA", gest_val),
                    _view_line("Coordinador destino", coord_val),
                    _view_link("Learning Agreement", la_val, open_in_system=True),
                    _view_link("ToR", tor_val, open_in_system=True),
                    _view_link("Acta de equivalencias", acta_val, open_in_system=True),
                    _view_link("Plan de estudios", plan_val, open_in_system=True),
                ])
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
                      action="{form_action}"
                      method="POST"
                      target="opener"
                    >
                      <!-- identificadores -->
                      <iframe name="opener" style="display:none;width:0;height:0;border:0;"></iframe>
                      <input type="hidden" name="row_index" value="{row_index_attr}">
                      <input type="hidden" name="save_student" value="1">
                      <input type="hidden" name="programa" value="{prog_attr}">
                      <input type="hidden" name="idx" value="{idx_attr}">
                      <!--  mandamos también la ruta del Excel  y las materias-->
                      <input type="hidden" name="excel_path" value="{html.escape(str(excel_path or ''), quote=True)}">
                      <input type="hidden" name="materias_excel_path" value="{html.escape(str(materias_excel_path or ''), quote=True)}">

                      <div class="edit-panel-inner">
                        <div class="form-grid">
                          {edit_fields_html}
                        </div>

                        {materias_edit_block}

                        <div class="edit-actions">
                          <label for="{toggle_id}" class="btn-icon cancel-btn" title="Cancelar">✖</label>
                          <button type="submit" class="btn save-btn" title="Guardar">Guardar</button>
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

    html_out = f"""
    <div class="al-popup">

      <header class="head">
        <div class="title-wrap">
          <div class="title">{universidad}</div>
        </div>
        <div class="head-right">
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
      <body>
    </div>
    """
    return html_out
