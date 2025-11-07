import html, json, math

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

def _link(label, url, text="Abrir"):
    url = _clean(url)
    if not url: return ""
    safe_url = html.escape(url, quote=True)
    return f"<b>{label}:</b> <a href='{safe_url}' target='_blank' rel='noopener noreferrer'>{html.escape(text)}</a><br>"

def generate_dynamic_popup(row):
    universidad = html.escape(str(row.get("universidad","")) or "Sin universidad")
    pais = html.escape(str(row.get("pais","") or ""))
    ciudad = html.escape(str(row.get("ciudad","") or ""))
    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    n = len(estudiantes)

    # subtítulo
    if pais and ciudad:
        sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{pais}</b> · {ciudad}</p>"
    elif pais:
        sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{pais}</b></p>"
    elif ciudad:
        sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{ciudad}</b></p>"
    else:
        sub = ""

    # items (sin <details>, solo divs + :hover / :focus-within)
    items_html = []
    for e in estudiantes or [{}]:
        nombre = html.escape(str(e.get("estudiante", "(sin nombre)")))

        ficha_parts = [
            _line("Email", e.get("email")),
            _line("Curso", e.get("curso")),
            _line("Cuatrimestre", e.get("cuatrimestre")),
            _line("Duración (meses)", e.get("duracion_meses")),
            _line("Gestión LA", e.get("gestion_LA")),
            _line("Coordinador destino", e.get("coordinador_destino")),
            _link("Learning Agreement", e.get("link_la")),
            _line("ToR", e.get("ToR")),
            _line("Acta de equivalencias", e.get("acta_equivalencias")),
            _link("Plan de estudios", e.get("link_plan")),
        ]
        ficha = "".join(p for p in ficha_parts if p) or "<i>Sin ficha disponible</i>"

        items_html.append(f"""
        <li class="pitem" tabindex="0" style="margin:6px 0; outline: none;">
          <div class="pname">👤 {nombre}</div>
          <div class="pdetails">{ficha}</div>
        </li>
        """)

    return f"""
    <div class="al-popup" style="
        font-family:'Segoe UI', Roboto, Arial, sans-serif;
        font-size:14px; color:#222; background:#fff;
        border-radius:12px; padding:12px; box-sizing:border-box;
        box-shadow:0 2px 10px rgba(0,0,0,0.18);
        width:460px; max-width:460px; min-width:460px;   /* ancho fijo */
    ">
      <h4 style="margin:0 0 4px 0;font-size:16px;color:#0B5ED7;border-bottom:2px solid #0B5ED7;padding-bottom:4px;display:flex;gap:8px;align-items:baseline;">
        <span>{universidad}</span>
        <span style="font-size:12px;color:#666">({n} estudiante{'s' if n!=1 else ''})</span>
      </h4>
      {sub}
      <ul class="plist" style="list-style:none;padding:8px 0 0 0;margin:6px 0 0 0;">
        {''.join(items_html)}
      </ul>

      <style>
        .al-popup a {{ color:#0B5ED7; text-decoration:underline; word-break:break-all; }}

        .al-popup .pname {{
          color:#0B5ED7; font-weight:600; cursor:default;
          white-space:normal; word-break:break-word;
        }}

        /* Detalles ocultos por defecto */
        .al-popup .pdetails {{
          display:none;
          margin-top:6px; background:#f6f8fa;
          padding:6px; border-radius:6px;
        }}

        /* Mostrar al pasar el ratón o al enfocar con teclado */
        .al-popup .pitem:hover .pdetails,
        .al-popup .pitem:focus-within .pdetails {{
          display:block;
        }}

        /* realce leve del item activo */
        .al-popup .pitem:hover .pname,
        .al-popup .pitem:focus-within .pname {{
          text-decoration:underline;
        }}
      </style>
    </div>
    """

