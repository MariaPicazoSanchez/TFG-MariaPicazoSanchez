import html, json, math, re

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
    universidad = html.escape(_clean(row.get("universidad",""))) or "Sin universidad"
    pais = html.escape(_clean(row.get("pais","")))
    ciudad = html.escape(_clean(row.get("ciudad","")))
    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    n = len(estudiantes)

    # Cabecera secundaria
    sub = ""
    if pais and ciudad:
        sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{pais}</b> · {ciudad}</p>"
    elif pais:
        sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{pais}</b></p>"
    elif ciudad:
        sub = f"<p style='margin:4px 0 0 0;color:#555'><b>{ciudad}</b></p>"

    # Items con <details>/<summary> (sin JS)
    items_html = []
    if not estudiantes:
        items_html.append("""
        <li class="pitem">
          <details open>
            <summary>(sin estudiantes)</summary>
            <div class="pdetails"><i>Sin ficha disponible</i></div>
          </details>
        </li>
        """)
    else:
        for e in estudiantes:
            nombre = html.escape(_clean(e.get("estudiante"))) or "(sin nombre)"
            ficha_parts = [
                _line("Email", e.get("email")),
                _line("Curso", e.get("curso")),                       # OUT
                _line("Cuatrimestre", e.get("cuatrimestre")),         # IN
                _line("Duración (meses)", e.get("duracion_meses")),   # SICUE/OUT
                _line("Gestión LA", e.get("gestion_LA")),             # SICUE
                _line("Coordinador destino", e.get("coordinador_destino")),  # SICUE
                _link("Learning Agreement", e.get("link_la")),
                _line("ToR", e.get("ToR")),
                _line("Acta de equivalencias", e.get("acta_equivalencias")),
                _link("Plan de estudios", e.get("link_plan")),
            ]
            ficha = "".join(x for x in ficha_parts if x) or "<i>Sin ficha disponible</i>"
            items_html.append(f"""
            <li class="pitem">
              <details>
                <summary>👤 {nombre}</summary>
                <div class="pdetails">{ficha}</div>
              </details>
            </li>
            """)

    return f"""
    <div class="al-popup" style="
        font-family:'Segoe UI', Roboto, Arial, sans-serif;
        font-size:14px; color:#222; background:#fff;
        border-radius:12px; padding:12px;
        box-shadow:0 2px 10px rgba(0,0,0,0.18);
        width:max-content; max-width:480px;
    ">
      <h4 style="margin:0 0 4px 0;font-size:16px;color:#0B5ED7;border-bottom:2px solid #0B5ED7;padding-bottom:4px;display:flex;gap:8px;align-items:baseline;">
        <span>{universidad}</span>
        <span style="font-size:12px;color:#666">({n} estudiante{'s' if n!=1 else ''})</span>
      </h4>
      {sub}
      <ul style="list-style:none;padding:8px 0 0 0;margin:6px 0 0 0;max-height:300px;overflow:auto;">
        {''.join(items_html)}
      </ul>

      <style>
        .al-popup a {{ color:#0B5ED7; text-decoration:underline; word-break:break-all; }}

        .al-popup .pitem {{ margin:6px 0; }}
        .al-popup details {{
          background:#f6f8fa; border-radius:8px; padding:6px 8px;
        }}
        .al-popup summary {{
          list-style:none; cursor:pointer; color:#0B5ED7; font-weight:600;
        }}
        /* Quitar triángulo nativo y crear uno custom */
        .al-popup summary::-webkit-details-marker {{ display:none; }}
        .al-popup summary::before {{
          content:'▸'; display:inline-block; margin-right:6px; transition:transform .15s;
        }}
        .al-popup details[open] summary::before {{ transform:rotate(90deg); }}
        .al-popup .pdetails {{ margin-top:6px; }}
      </style>
    </div>
    """
