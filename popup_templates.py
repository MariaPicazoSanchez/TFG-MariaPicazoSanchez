import streamlit as st
import html, json, math
from urllib.parse import quote



def _normalize_estudiantes(estudiantes):
    if isinstance(estudiantes, str):
        try:
            estudiantes = json.loads(estudiantes)
        except Exception:
            estudiantes = [{"estudiante": estudiantes}]
    if isinstance(estudiantes, dict):
        estudiantes = [estudiantes]
    if estudiantes is None or (isinstance(estudiantes, float) and math.isnan(estudiantes)):
        estudiantes = []
    out = []
    for e in estudiantes:
        if isinstance(e, dict):
            norm = {str(k).strip(): v for k, v in e.items()}
            if "link_LA" in norm and "link_la" not in norm:
                norm["link_la"] = norm["link_LA"]
            if "Plan de estudios" in norm and "link_plan" not in norm:
                norm["link_plan"] = norm["Plan de estudios"]
            out.append(norm)
    return out

def _clean(v):
    s = "" if v is None else str(v).strip()
    return "" if s.lower() in {"nan", "none", ""} else s

def _line(label, value):
    value = _clean(value)
    return f"<b>{label}:</b> {html.escape(value)}<br>" if value else ""

def _view_line(label, value):
    """
    Línea para modo *vista*:
    - Siempre muestra la etiqueta.
    - Si no hay valor, pone 'Sin datos' en gris.
    """
    v = _clean(value)
    if v:
        val_html = html.escape(v)
    else:
        val_html = "<span style='color:#9ca3af;font-style:italic;'>Sin datos</span>"
    return f"<b>{html.escape(label)}:</b> {val_html}<br>"



def _link(label, url, text="Abrir", open_in_system=False):
    url = _clean(url)
    if not url:
        return ""

    label_html = html.escape(label, quote=True)
    text_html  = html.escape(text,  quote=True)

    # Abrir con la app por defecto del SISTEMA (rutas locales, no http/https)
    if open_in_system and not str(url).lower().startswith(("http://", "https://")):
        qp = quote(str(url))
        # iframe oculto receptor (para evitar navegar el top)
        # el enlace apunta a ese iframe por 'target="opener"'
        return (
            "<iframe name='opener' style='display:none;width:0;height:0;border:0'></iframe>"
            f"<b>{label_html}:</b> "
            f"<a href='/?open_pdf={qp}' target='opener'>{text_html}</a><br>"
        )

    # Comportamiento normal para enlaces web
    safe_url = html.escape(str(url), quote=True)
    return f"<b>{label_html}:</b> <a href='{safe_url}' target='_blank' rel='noopener noreferrer'>{text_html}</a><br>"


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
    # # Intentar deducir el tipo del programa de forma robusta
    # tipo = (
    #     row.get("tipo")
    #     or row.get("programa")
    #     or row.get("sheet")
    #     or row.get("origen_programa")
    #     or ""
    # )
    # tipo = str(tipo).strip()

    config = st.session_state.get("config", {})
    excel_path = config.get(programa)

    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    n = len(estudiantes)

    
    # subtitle = " · ".join(p for p in (pais, ciudad) if p)
    # subtitle_html = f"<div class='sub'>{subtitle}</div>" if subtitle else ""

    loc_text = " · ".join(p for p in (ciudad, pais) if p)  # primero ciudad, luego país

    if programa and loc_text:
        subtitle_text = f"{html.escape(programa)} · {loc_text}"
    elif programa:
        subtitle_text = html.escape(programa)
    else:
        subtitle_text = loc_text

    subtitle_html = f"<div class='sub'>{subtitle_text}</div>" if subtitle_text else ""
    # 🔹 Botón "Abrir Excel <programa>" SOLO si tenemos ruta local
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
            # 🔹 IDs base para este estudiante (se usan en materias y en el formulario)
            idx_attr = html.escape(str(idx), quote=True)
            row_index_attr = html.escape(str(row_index), quote=True)

            nombre_raw = str(e.get("estudiante", "(sin nombre)"))
            nombre = html.escape(nombre_raw)

            email_val  = _clean(e.get("email"))
            curso_val  = _clean(e.get("curso"))
            cuatri_val = _clean(e.get("cuatrimestre"))
            dur_val    = _clean(e.get("duracion_meses"))
            gest_val   = _clean(e.get("gestion_LA"))
            coord_val  = _clean(e.get("coordinador_destino"))
            la_val     = _clean(e.get("link_la"))
            tor_val    = _clean(e.get("ToR"))
            acta_val   = _clean(e.get("acta_equivalencias"))
            plan_val   = _clean(e.get("link_plan"))

            # Materias: mostrar SOLO si el alumno tiene materias_in no vacías
            materias = e.get("materias_in") if isinstance(e, dict) else []
            has_materias = isinstance(materias, list) and len(materias) > 0

            has_materias = False
            materias_view_html = ""
            materias_edit_block = ""

            if programa == "Erasmus IN":
                has_materias = True
                materias = e.get("materias_in") if isinstance(e, dict) else []
                if not isinstance(materias, list):
                    materias = []

                pills = []
                lines = []
                for m in materias:
                    if not isinstance(m, dict):
                        continue
                    asig = _clean(m.get("asignatura"))
                    cuat = _clean(m.get("cuat"))
                    if not asig:
                        continue

                    pill = html.escape(asig)
                    if cuat:
                        pill += f". Cuatri: {html.escape(cuat)}"
                        lines.append(f"{asig} | {cuat}")
                    else:
                        lines.append(asig)
                    pills.append(f"<li class='mitem'>{pill}</li>")

                if pills:
                    materias_view_html = (
                        "<details class='mat' role='group'>"
                        f"<summary>📚 Materias ({len(pills)})</summary>"
                        "<ul class='mlist'>" + "".join(pills) + "</ul></details>"
                    )
                else:
                    materias_view_html = "<div class='no-mat'>Sin asignaturas asignadas</div>"

                # materias_text a partir de las líneas
                materias_text = "\n".join(lines)

                materias_items = []
                for j, line in enumerate([l for l in materias_text.splitlines() if l.strip()]):
                    nombre_asig = line.split("|", 1)[0].strip() or "Sin nombre"
                    asig = html.escape(nombre_asig)
                    mid = f"{row_index_attr}-{idx_attr}-mat-{j}"
                    materias_items.append(f"""
                      <li class="materia-row" data-mindex="{j}">
                        <span class="materia-name">{asig}</span>
                        <span class="materia-actions">
                          <button type="button" class="icon-btn materia-edit" title="Editar" data-mid="{mid}">✏️</button>
                          <button type="button" class="icon-btn materia-delete" title="Eliminar" data-mid="{mid}">🗑️</button>
                        </span>
                      </li>
                    """)

                materias_items_html = "\n".join(materias_items)

                materias_edit_block = f"""
                  <div class="field full materias-block">
                    <label>Asignaturas (materias_in)</label>

                    <ul class="materias-list">
                      {materias_items_html}
                      <li class="materia-row add-row">
                        <button type="button" class="icon-btn materia-add">+ Añadir asignatura</button>
                      </li>
                    </ul>

                    <div class="materia-editor" style="display:none;">
                      <div class="field">
                        <label>Asignatura</label>
                        <input type="text" name="mat_nombre">
                      </div>
                      <div class="field">
                        <label>Cuatrimestre</label>
                        <select name="mat_cuat" class="slim-select">
                          <option value="">--</option>
                          <option value="1">1</option>
                          <option value="2">2</option>
                        </select>
                      </div>
                      <div class="field">
                        <label class="checkbox-label">
                          <input type="checkbox" name="mat_firmado">
                          Firmado
                        </label>
                      </div>
                    </div>

                    <textarea name="materias_raw" style="display:none;">{html.escape(materias_text)}</textarea>
                  </div>
                """
            # Targeta del estudiante
            toggle_id = f"edit-{idx}"
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
                                  <option value="1" {("selected" if gest_val == "Pendiente firma del coordinador" else "")}>Pendiente firma del coordinador</option>
                                  <option value="2" {("selected" if gest_val == "Pendiente firma del estudiante" else "")}>Pendiente firma del estudiante</option>
                                  <option value="3" {("selected" if gest_val == "Enviado a vicerrectorado" else "")}>Enviado a vicerrectorado</option>
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
                                <input name="destino" value="{html.escape(_clean(e.get("destino")), quote=True)}">
                              </div>'''
            origen_field = f'''
                              <div class="field">
                                <label>Origen</label>
                                <input name="origen" value="{html.escape(_clean(e.get("origen")), quote=True)}">
                              </div>'''
            responsable_field = f'''
                              <div class="field">
                                <label>Responsable</label>
                                <input name="responsable" value="{html.escape(_clean(e.get("responsable")), quote=True)}">
                              </div>'''
            pais_field = f'''
                              <div class="field">
                                <label>País</label>
                                <input name="pais" value="{html.escape(_clean(e.get("pais")), quote=True)}">
                              </div>'''
            ciudad_field = f'''
                              <div class="field">
                                <label>Ciudad</label>
                                <input name="ciudad" value="{html.escape(_clean(e.get("ciudad")), quote=True)}">
                              </div>'''
            prog_upper = (programa or "").upper()
            grid_fields = [nombre_field, email_field]

            # SICUE OUT: nombre, email, duración, coordinador destino, gestión LA, LA, plan
            if "SICUE" in prog_upper:
                grid_fields += [dur_field, coord_field, gest_field, la_field, plan_field, destino_field, ciudad_field]

            # Erasmus OUT: nombre, email, curso, duración, gestión LA, LA, plan, ToR
            elif "ERASMUS OUT" == prog_upper:
                grid_fields += [curso_field, dur_field, la_field, plan_field, tor_field, responsable_field, destino_field, pais_field]

            # Erasmus IN: nombre, email, cuatrimestre, LA
            elif "ERASMUS IN" == prog_upper:
                grid_fields += [cuatri_field, la_field, origen_field, pais_field]

            # Cualquier otro (fallback): todo
            else:
                grid_fields += [
                    curso_field, cuatri_field, dur_field,
                    gest_field, coord_field,
                    la_field, tor_field, acta_field, plan_field
                ]
            # Valores extra para vista (además de los *_val que ya tienes)
            destino_val     = _clean(e.get("destino"))
            origen_val      = _clean(e.get("origen"))
            responsable_val = _clean(e.get("responsable"))
            pais_val        = _clean(e.get("pais"))
            ciudad_val      = _clean(e.get("ciudad"))

            # === BLOQUES DE VISTA SEGÚN TIPO DE PROGRAMA ===
            view_small = []
            view_extras = []

            # Parte "small" común (puedes ajustarla si quieres)
            view_small.append(_view_line("Email", email_val))

            if "SICUE" in prog_upper:
                # SICUE OUT: email + duración y destino en pequeño
                view_small.append(_view_line("Duración (meses)", dur_val))
                view_small.append(_view_line("Destino", destino_val))

                # Extras: gestión, coordinador, LA, plan, ciudad
                view_extras.extend([
                    _view_line("Gestión LA", gest_val),
                    _view_line("Coordinador destino", coord_val),
                    _view_line("Learning Agreement", la_val),
                    _view_line("Plan de estudios", plan_val),
                    _view_line("Ciudad", ciudad_val),
                ])

            elif "ERASMUS OUT" == prog_upper:
                # Erasmus OUT: email + curso + duración
                view_small.append(_view_line("Curso", curso_val))
                view_small.append(_view_line("Duración (meses)", dur_val))

                # Extras: destino, país, LA, plan, ToR, responsable
                view_extras.extend([
                    _view_line("Destino", destino_val),
                    _view_line("País", pais_val),
                    _view_line("Learning Agreement", la_val),
                    _view_line("Plan de estudios", plan_val),
                    _view_line("ToR", tor_val),
                    _view_line("Responsable", responsable_val),
                ])

            elif "ERASMUS IN" == prog_upper:
                # Erasmus IN: email + cuatrimestre + origen
                view_small.append(_view_line("Cuatrimestre", cuatri_val))
                view_small.append(_view_line("Origen", origen_val))

                # Extras: país, coordinador, LA (si lo usáis), materias
                view_extras.extend([
                    _view_line("País", pais_val),
                    _view_line("Coordinador destino", coord_val),
                    _view_line("Learning Agreement", la_val),
                ])
                if has_materias and materias_view_html:
                    view_extras.append(materias_view_html)

            else:
                # Fallback genérico (similar a lo que tenías antes)
                view_small.append(_view_line("Curso", curso_val))
                view_small.append(_view_line("Cuatrimestre", cuatri_val))

                view_extras.extend([
                    _view_line("Duración (meses)", dur_val),
                    _view_line("Gestión LA", gest_val),
                    _view_line("Coordinador destino", coord_val),
                    _view_line("Learning Agreement", la_val),
                    _view_line("ToR", tor_val),
                    _view_line("Acta de equivalencias", acta_val),
                    _view_line("Plan de estudios", plan_val),
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
                  <!-- interruptor ver/editar -->
                  <input type="checkbox" id="{toggle_id}" class="edit-toggle">


                  <!-- Bloque de VISTA -->
                  <div class="block view-block">
                    <!-- resumen pequeño -->
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

                  <!-- BLOQUE EDICIÓN -->
                  <div class="block edit-block">
                    <!-- FORMULARIO: evitamos la navegación desde el iframe y usamos postMessage -->
                    <form id="edit-form-{row_index_attr}-{idx_attr}" class="edit-form">
                      <!-- identificadores -->
                      <input type="hidden" name="row_index" value="{row_index_attr}" onsubmit="return false;">
                      <input type="hidden" name="save_student" value="1">
                      <input type="hidden" name="programa" value="{prog_attr}">
                      <input type="hidden" name="row_id" value="{row_id_attr}">
                      <input type="hidden" name="idx" value="{idx_attr}">

                      <div class="edit-panel-inner">
                        <div class="form-grid">
                          {edit_fields_html}
                        </div>

                        {materias_edit_block if has_materias else ""}

                        <div class="edit-actions">
                          <!-- cancelar vuelve a la vista (label para el checkbox) -->
                          <label for="{toggle_id}" class="btn-icon cancel-btn" title="Cancelar">✖</label>
                          <!-- guardar: botón real que envía el formulario -->
                          <button type="submit" class="btn save-btn" title="Guardar">Guardar</button>
                        </div>

                        <div class="hint">
                          Los cambios se guardan en el Excel de {html.escape(programa)} (fila {row_id_attr}).
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
      <!-- iframe oculto para que los enlaces no naveguen la página principal -->
      <iframe name="opener" style="display:none;width:0;height:0;border:0;"></iframe>

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
      .al-popup {{
        font-family: Inter, Segoe UI, Roboto, Arial;
        font-size: 13px;
        color: #1f2937;
        background: #fff;
        border-radius: 12px;
        padding: 6px 12px 12px 12px;  /* 👈 solo 6px arriba */
        width: 520px;
        max-width: 520px;
        box-sizing: border-box;
        box-shadow: 0 6px 18px rgba(15,23,42,0.12);
      }}
      .al-popup .field {{
        margin-bottom: 8px;
      }}
      .al-popup .field label {{
        display: block;
        font-size: 12px;
        font-weight: 500;
        margin-bottom: 4px;
      }}

      .al-popup .field input,
      .al-popup .field select {{
        width: 100%;
        padding: 6px 8px;
        border-radius: 6px;
        border: 1px solid #d0d7de;
        font-size: 13px;
        box-sizing: border-box;
        background-color: #fff;
      }}
      .al-popup .field select {{
        cursor: pointer;
      }}
      .title {{
        font-weight:700;color:#0B5ED7;font-size:15px;
      }}
      .excel-btn {{
        display:inline-block;
        font-size:12px;
        font-weight:600;
        background:#f97316;      /* naranja */
        color:#ffffff !important; /* texto blanco, por encima de .al-popup a */
        padding:4px 10px;
        border-radius:999px;
        text-decoration:none;
        border:none;
        box-shadow:0 1px 3px rgba(0,0,0,0.15);
      }}
      .excel-btn:hover {{
        filter:brightness(0.95);
      }}

      .head {{
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:6px;
        gap:8px;
      }}
      .title-wrap {{
        display:flex;
        flex-direction:column;
        gap:2px;
      }}
      .head-right {{
        display:flex;
        flex-direction:column;
        align-items:flex-end;
        gap:4px;
      }}
      .badges {{
        display:flex;gap:6px;align-items:center;
      }}
      .badge {{
        background:#eef2ff;color:#0b4bd6;padding:4px 8px;
        border-radius:999px;font-weight:600;font-size:12px;
      }}
      .badge.count {{
        background:#0b5ed7;color:white;
      }}
      .sub {{
        color:#6b7280;font-size:12px;margin-bottom:6px;
      }}
      .plist {{
        list-style:none;padding:0;margin:6px 0 0 0;
        max-height:360px;overflow:auto;
      }}
      .pitem + .pitem {{
        margin-top:8px;
      }}
      .pdetails {{
        margin-top:6px;background:#fbfbff;border-radius:8px;
        padding:0;border:1px solid #eef2ff;
      }}
      .pdetails > summary {{
        list-style:none;
        cursor:pointer;
        padding:8px;
        border-radius:8px 8px 0 0;
      }}
      .pdetails[open] > summary {{
        border-bottom:1px solid #e5e7eb;
      }}
      .summary-row {{
        display:flex;gap:10px;align-items:center;
      }}
      .avatar {{
        width:32px;height:32px;border-radius:8px;
        background:linear-gradient(135deg,#7c3aed,#60a5fa);
        color:white;display:flex;align-items:center;
        justify-content:center;font-weight:700;font-size:13px;
      }}
      .meta {{
        flex:1;min-width:0;
      }}
      .name {{
        font-weight:700;color:#0b5ed7;white-space:nowrap;
        overflow:hidden;text-overflow:ellipsis;
      }}
      .mode-tags {{
        display:flex;gap:4px;margin-top:2px;font-size:11px;
      }}
      .tag-mode {{
        padding:2px 8px;border-radius:999px;
        border:1px solid #d1d5db;
        color:#4b5563;
      }}
      .tag-edit {{
        display:none;
        background:#0b5ed7;
        color:white;
        border-color:#0b5ed7;
      }}
      .pdetails[open] .tag-view {{
        display:none;
      }}
      .pdetails[open] .tag-edit {{
        display:inline-flex;
      }}
      .small {{
        font-size:12px;color:#374151;margin-top:4px;
      }}
      .block {{
        padding:8px;
      }}
      .extras {{
        font-size:13px;color:#374151;
      }}
      .extras b {{
        font-weight:600;
      }}
      .mat summary {{
        cursor:pointer;list-style:none;outline:none;
        font-weight:700;color:#0b5ed7;
      }}
      .mlist {{
        list-style:none;padding-left:12px;margin:6px 0 0 0;
        display:flex;flex-direction:column;gap:4px;
      }}
      .mitem {{
        background:#f1f5f9;padding:6px;border-radius:6px;
        font-size:12px;color:#0f1724;
      }}
      .no-mat {{
        margin-top:6px;color:#6b7280;font-size:13px;font-style:italic;
      }}
      .edit-panel-inner {{
        display:flex;flex-direction:column;gap:8px;
      }}
      .form-grid {{
        display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
        gap:6px 10px;margin-top:6px;
      }}
      .field {{
        display:flex;flex-direction:column;gap:3px;font-size:12px;
      }}
      .field.full {{
        margin-top:6px;
      }}
      .field label {{
        font-weight:600;color:#4b5563;
      }}
      .field input, .field textarea {{
        width:100%;font-size:12px;padding:5px 6px;
        border-radius:4px;border:1px solid #e5e7eb;
        box-sizing:border-box;
      }}
      .field textarea {{
        resize:vertical;
      }}
      .hint {{
        font-size:11px;color:#6b7280;margin-top:4px;font-style:italic;
      }}
      .leaflet-popup-content {{
          margin-top: 0 !important;
      }}
      .edit-toggle {{ display:none; }}        /* el checkbox NO se ve */
      .view-block {{ display:block; }}
      .edit-block {{ display:none; }}

      .edit-toggle:checked ~ .view-block {{ display:none; }}
      .edit-toggle:checked ~ .edit-block {{ display:block; }}
      .btn-icon,
      .save-btn {{
        font-size: 12px;
        border-radius: 999px;
        padding: 4px 10px;
        cursor: pointer;
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 4px;              /* espacio entre el icono y el texto */
        border: none;
      }}

      /* BOTÓN EDITAR (lápiz) */
      .edit-btn {{
        background: #eff6ff;       /* azul muy clarito */
        color: #1d4ed8;            /* azul intenso texto */
        border: 1px solid #bfdbfe; /* borde suave */
        font-weight: 600;
      }}

      .edit-btn:hover {{
        background: #dbeafe;
      }}
      /* BOTÓN CANCELAR (X) */
      .cancel-btn {{  
        background: #f3f4f6;
        color: #111827;
        border: 1px solid #e5e7eb;
      }}

      /* BOTÓN GUARDAR */
      .save-btn {{
        background: #10b981;
        color: #ffffff;
        font-weight: 600;
      }}
      .save-btn:hover {{
        filter: brightness(0.95);
      }}
      .al-popup .materias-list {{
        list-style: none;
        margin: 4px 0 0 0;
        padding: 0;
      }}
      .al-popup .materia-row {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4px 6px;
        border-radius: 4px;
        font-size: 13px;
      }}
      .al-popup .materia-row:nth-child(odd) {{
        background: #f6f8fa;
      }}

      .al-popup .materia-name {{
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}

      .al-popup .materia-actions {{
        display: flex;
        gap: 4px;
      }}

      .al-popup .icon-btn {{
        border: none;
        background: #e9ecef;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 12px;
        cursor: pointer;
      }}

      .al-popup .icon-btn:hover {{
        background: #d0d7de;
      }}
      .al-popup .materia-row.add-row {{
        justify-content: center;
      }}

      .al-popup .materia-row.add-row .icon-btn {{
        width: 100%;
        justify-content: center;
      }}

      .al-popup .materia-editor {{
        margin-top: 8px;
        padding: 8px;
        border-radius: 6px;
        background: #f6f8fa;
      }}
  
      </style>
    </div>
    """
    return html_out




