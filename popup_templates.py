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

# def generate_dynamic_popup(row):
#     universidad = html.escape(str(row.get("universidad","")) or "Sin universidad")
#     pais = html.escape(str(row.get("pais","") or ""))
#     ciudad = html.escape(str(row.get("ciudad","") or ""))
#     estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
#     n = len(estudiantes)

#     # subtítulo
#     if pais and ciudad:
#         sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{pais}</b> · {ciudad}</p>"
#     elif pais:
#         sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{pais}</b></p>"
#     elif ciudad:
#         sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{ciudad}</b></p>"
#     else:
#         sub = ""

#     # items (sin <details>, solo divs + :hover / :focus-within)
#     items_html = []
#     for e in estudiantes or [{}]:
#         nombre = html.escape(str(e.get("estudiante", "(sin nombre)")))

#         ficha_parts = [
#             _line("Email", e.get("email")),
#             _line("Curso", e.get("curso")),
#             _line("Cuatrimestre", e.get("cuatrimestre")),
#             _line("Duración (meses)", e.get("duracion_meses")),
#             _line("Gestión LA", e.get("gestion_LA")),
#             _line("Coordinador destino", e.get("coordinador_destino")),
#             _link("Learning Agreement", e.get("link_la"),"Abrir", open_in_system=True),
#             _link("ToR", e.get("ToR"),"Abrir", open_in_system=True),
#             _line("Acta de equivalencias", e.get("acta_equivalencias")),
#             _link("Plan de estudios", e.get("link_plan"),"Abrir",open_in_system=True),
#         ]
#         ficha = "".join(p for p in ficha_parts if p) or "<i>Sin ficha disponible</i>"

#         items_html.append(f"""
#         <li class="pitem" tabindex="0" style="margin:6px 0; outline: none;">
#           <div class="pname">👤 {nombre}</div>
#           <div class="pdetails">{ficha}</div>
#         </li>
#         """)

#     return f"""
#     <div class="al-popup" style="
#         font-family:'Segoe UI', Roboto, Arial, sans-serif;
#         font-size:14px; color:#222; background:#fff;
#         border-radius:12px; padding:12px; box-sizing:border-box;
#         box-shadow:0 2px 10px rgba(0,0,0,0.18);
#         width:460px; max-width:460px; min-width:460px;   /* ancho fijo */
#     ">
#       <h4 style="margin:0 0 4px 0;font-size:16px;color:#0B5ED7;border-bottom:2px solid #0B5ED7;padding-bottom:4px;display:flex;gap:8px;align-items:baseline;">
#         <span>{universidad}</span>
#         <span style="font-size:12px;color:#666">({n} estudiante{'s' if n!=1 else ''})</span>
#       </h4>
#       {sub}
#       <ul class="plist" style="list-style:none;padding:8px 0 0 0;margin:6px 0 0 0;">
#         {''.join(items_html)}
#       </ul>

#       <style>
#         .al-popup a {{ color:#0B5ED7; text-decoration:underline; word-break:break-all; }}

#         .al-popup .pname {{
#           color:#0B5ED7; font-weight:600; cursor:default;
#           white-space:normal; word-break:break-word;
#         }}

#         /* Detalles ocultos por defecto */
#         .al-popup .pdetails {{
#           display:none;
#           margin-top:6px; background:#f6f8fa;
#           padding:6px; border-radius:6px;
#         }}

#         /* Mostrar al pasar el ratón o al enfocar con teclado */
#         .al-popup .pitem:hover .pdetails,
#         .al-popup .pitem:focus-within .pdetails {{
#           display:block;
#         }}

#         /* realce leve del item activo */
#         .al-popup .pitem:hover .pname,
#         .al-popup .pitem:focus-within .pname {{
#           text-decoration:underline;
#         }}
#       </style>
#     </div>
#     """

def generate_dynamic_popup(row):
    universidad = html.escape(str(row.get("universidad","")) or "Sin universidad")
    pais = html.escape(str(row.get("pais","") or ""))
    ciudad = html.escape(str(row.get("ciudad","") or ""))
    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    n = len(estudiantes)

    # subtítulo compacto
    subtitle = " · ".join(p for p in (pais, ciudad) if p)
    subtitle_html = f"<div class='sub'>{html.escape(subtitle)}</div>" if subtitle else ""

    items_html = []
    for e in estudiantes or [{}]:
        nombre = html.escape(str(e.get("estudiante", "(sin nombre)")))
        email_line = _line("Email", e.get("email"))
        curso_line = _line("Curso", e.get("curso"))
        cuatr_line = _line("Cuatrimestre", e.get("cuatrimestre"))
        extras = "".join(p for p in [
            _line("Duración (meses)", e.get("duracion_meses")),
            _line("Gestión LA", e.get("gestion_LA")),
            _line("Coordinador destino", e.get("coordinador_destino")),
            _link("Learning Agreement", e.get("link_la"), "Abrir", open_in_system=True),
            _link("ToR", e.get("ToR"), "Abrir", open_in_system=True),
            _line("Acta de equivalencias", e.get("acta_equivalencias")),
            _link("Plan de estudios", e.get("link_plan"), "Abrir", open_in_system=True),
        ] if p)

        # materias IN: si existe la clave 'materias_in' mostramos desplegable o mensaje
        materias = e.get("materias_in") if isinstance(e, dict) else None
        materias_html = ""
        if materias is not None:
            # si es lista con elementos, renderizamos detalles; si no, mostramos texto indicativo
            if isinstance(materias, (list, tuple)) and materias:
                pills = []
                for m in materias:
                    asign = html.escape(str(m.get("asignatura","")))
                    cuat = html.escape(str(m.get("cuat","")))
                    centro = html.escape(str(m.get("centro","")))
                    parts = " — ".join(p for p in (asign, cuat, centro) if p)
                    pills.append(f"<li class='mitem'>{parts}</li>")
                materias_html = (
                    "<details class='mat' role='group'>"
                    f"<summary>📚 Materias ({len(materias)})</summary>"
                    f"<ul class='mlist'>{''.join(pills)}</ul>"
                    "</details>"
                )
            else:
                materias_html = "<div class='no-mat'>Sin asignaturas asignadas</div>"

        ficha = f"""
        <div class='ficha'>
          <div class='frow'>
            <div class='avatar'>{nombre[:1].upper()}</div>
            <div class='meta'>
              <div class='name'>{nombre}</div>
              <div class='small'>{email_line}{curso_line}{cuatr_line}</div>
            </div>
          </div>
          <div class='extras'>{extras}{materias_html}</div>
        </div>
        """

        items_html.append(f"<li class='pitem'>{ficha}</li>")

    html_out = f"""
    <div class="al-popup">
      <header class="head">
        <div class="title">{universidad}</div>
        <div class="badges">
          <span class="badge count">{n}</span>
          {'<span class="badge country">' + html.escape(pais) + '</span>' if pais else ''}
        </div>
      </header>
      {subtitle_html}
      <ul class="plist">{''.join(items_html)}</ul>

      <style>
        .al-popup{{font-family:Inter, Segoe UI, Roboto, Arial; font-size:13px; color:#1f2937;
                   background:#fff; border-radius:12px; padding:12px; width:480px; box-sizing:border-box;
                   box-shadow:0 6px 18px rgba(15,23,42,0.12);}}
        .head{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px}}
        .title{{font-weight:700;color:#0B5ED7;font-size:15px}}
        .badges{{
          display:flex;gap:6px;align-items:center;
        }}
        .badge{{background:#eef2ff;color:#0b4bd6;padding:4px 8px;border-radius:999px;font-weight:600;font-size:12px}}
        .badge.count{{background:#0b5ed7;color:white}}
        .sub{{color:#6b7280;font-size:12px;margin-bottom:6px}}
        .plist{{list-style:none;padding:0;margin:6px 0 0 0;max-height:340px;overflow:auto}}
        .pitem + .pitem{{margin-top:8px}}
        .ficha{{background:#fbfbff;border-radius:8px;padding:8px;border:1px solid #eef2ff}}
        .frow{{display:flex;gap:10px;align-items:center}}
        .avatar{{width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#7c3aed,#60a5fa);
                 color:white;display:flex;align-items:center;justify-content:center;font-weight:700}}
        .meta{{flex:1;min-width:0}}
        .name{{font-weight:700;color:#0b5ed7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
        .small{{font-size:12px;color:#374151;margin-top:4px}}
        .extras{{margin-top:8px;font-size:13px;color:#374151}}
        .extras a{{color:#0b5ed7;text-decoration:underline}}
        /* materias */
        .mat summary{{cursor:pointer;list-style:none;outline:none;font-weight:700;color:#0b5ed7}}
        .mlist{{list-style:none;padding-left:12px;margin:6px 0 0 0;display:flex;flex-direction:column;gap:4px}}
        .mitem{{background:#f1f5f9;padding:6px;border-radius:6px;font-size:12px;color:#0f1724}}
        .no-mat{{margin-top:6px;color:#6b7280;font-size:13px;font-style:italic}}
        /* enlace que abre archivos locales usa misma apariencia */
        a[target="_blank"]{{text-decoration:underline}}
      </style>
    </div>
    """
    return html_out