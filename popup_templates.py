import html
import json
import math

def _normalize_estudiantes(estudiantes):
    # string JSON -> lista
    if isinstance(estudiantes, str):
        try:
            estudiantes = json.loads(estudiantes)
        except Exception:
            estudiantes = [{"estudiante": estudiantes}]
    # dict -> lista
    if isinstance(estudiantes, dict):
        estudiantes = [estudiantes]
    # None / NaN -> lista vacía
    if estudiantes is None or (isinstance(estudiantes, float) and math.isnan(estudiantes)):
        estudiantes = []
    # filtra formatos raros
    return [e for e in estudiantes if isinstance(e, dict) and e.get("estudiante")]

def generate_dynamic_popup(row):
    """Lista de nombres SIEMPRE visible.
    - Al pasar el ratón: muestra detalles (CSS :hover).
    - Al hacer click/tap: toggle de detalles (JS sin IDs).
    """
    universidad = html.escape(str(row.get("universidad","")))
    pais = html.escape(str(row.get("pais","")))
    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))

    def safe_line(label, value, is_link=False):
        if not value or str(value).strip() in {"nan", "None", "No disponible", ""}:
            return ""
        if is_link:
            return f"<b>{label}:</b> <a href='{value}' target='_blank' style='color:#004AAD;'>Abrir</a><br>"
        return f"<b>{label}:</b> {html.escape(str(value))}<br>"

    items_html = []
    for e in estudiantes or [{}]:
        nombre = html.escape(str(e.get("estudiante", "(sin nombre)")))
        ficha = "".join([
            safe_line("Curso", e.get("curso")),
            safe_line("Learning Agreement", e.get("link_LA"), True),
            safe_line("ToR", e.get("ToR")),
            safe_line("Acta de equivalencias", e.get("acta_equivalencias")),
            safe_line("Plan de estudios", e.get("link_plan"), True),
        ]) or "<i>Sin ficha disponible</i>"

        items_html.append(f"""
        <li class="pitem" style="margin:6px 0;">
          <div class="pname"
               style="cursor:pointer;color:#004AAD;font-weight:600;"
               onclick="var d=this.nextElementSibling; d.style.display=(d.style.display==='block')?'none':'block';">
            👤 {nombre}
          </div>
          <div class="pdetails" style="display:none;margin-top:6px;background:#f6f8fa;padding:6px;border-radius:6px;">
            {ficha}
          </div>
        </li>
        """)

    return f"""
        <div class="al-popup">
        <h4>{universidad}</h4>
        <p><b>{pais}</b></p>
        <ul>
            {''.join(items_html)}
        </ul>
        <script>
            // (opcional) nada: ya usamos onclick inline para el toggle
        </script>
        </div>
        """


