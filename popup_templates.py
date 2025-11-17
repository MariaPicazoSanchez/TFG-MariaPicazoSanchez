import html, json, math
from urllib.parse import quote
import os, tempfile



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

def _input_row(name, label, value):
    return (
        "<div class='ef-row'>"
        f"<label>{html.escape(label)}</label>"
        f"<input name=\"{html.escape(name)}\" value=\"{html.escape(value, quote=True)}\">"
        "</div>"
    )

# Reutilizables: handlers inline (evitan <script> que muchos popups no ejecutan)
_save_js = (
    "(function(btn){"
    "var li=btn.closest('.pitem');var popup=btn.closest('.al-popup');var form=li.querySelector('.edit-form');"
    "var idx=parseInt(li.getAttribute('data-idx')||'-1',10);var rowId=popup?popup.getAttribute('data-row-id'):null;"
    "var fd=new FormData(form), est={}; fd.forEach(function(v,k){ est[k]=v; });"
    "try{ if(typeof est.materias_in==='string') est.materias_in = JSON.parse(est.materias_in); }catch(e){}"
    "function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;'); }"
    "fetch('/edit_student',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({row_id:rowId,index:idx,estudiante:est})})"
    ".then(function(r){ if(!r.ok) throw new Error('net'); return r.json().catch(function(){return {ok:true};}); })"
    ".then(function(){ var newName=est.estudiante; var viewName=li.querySelector('.view-name'); if(viewName) viewName.textContent=newName||'(sin nombre)';"
    "var pname=li.querySelector('.pname'); if(pname) pname.textContent='👤 '+(newName||'(sin nombre)');"
    "var small=li.querySelector('.view-small'); if(small){ var parts=[]; if(est.email) parts.push('<b>Email:</b> '+esc(est.email)+'<br>');"
    "if(est.curso) parts.push('<b>Curso:</b> '+esc(est.curso)+'<br>'); if(est.cuatrimestre) parts.push('<b>Cuatrimestre:</b> '+esc(est.cuatrimestre)+'<br>');"
    "small.innerHTML=parts.join(''); small.style.display='block'; } form.dataset.original=JSON.stringify(est||{}); form.style.display='none'; })"
    ".catch(function(){ try{ var qp=encodeURIComponent(JSON.stringify({row_id:rowId,index:idx,estudiante:est})); window.location.href='/?edit_student='+qp; }catch(e){} });"
    "})(this)"
)

_cancel_js = """
(function(btn){
  var li   = btn.closest('.pitem');
  var form = li.querySelector('.edit-form');

  try {
    // Restaurar valores originales de los inputs
    var orig = JSON.parse(form.dataset.original || '{}');
    Array.prototype.forEach.call(
      form.querySelectorAll('input[name]'),
      function(inp){
        var k = inp.getAttribute('name');
        inp.value = (orig[k] != null ? orig[k] : '');
      }
    );

    // Reconstruir lista de materias desde el hidden
    var h  = form.querySelector('input[name="materias_in"]');
    var ul = form.querySelector('.materias-edit-list');
    if (h && ul) {
      ul.innerHTML = '';
      var arr = JSON.parse(h.value || '[]') || [];
      arr.forEach(function(m){
        var li2 = document.createElement('li');
        li2.setAttribute('data-asig', m.asignatura || '');
        li2.setAttribute('data-cuat', m.cuat || '');

        var s1 = document.createElement('span');
        s1.className  = 'masig';
        s1.textContent = m.asignatura || '';
        li2.appendChild(s1);

        var s2 = document.createElement('span');
        s2.className  = 'mcuat';
        s2.textContent = m.cuat || '';
        li2.appendChild(s2);

        var del = document.createElement('button');
        del.type = 'button';
        del.textContent = 'X';
        del.addEventListener('click', function(){
          var li3 = this.closest('li');
          li3.parentElement.removeChild(li3);

          var form2 = this.closest('.edit-form');
          var ul2   = form2.querySelector('.materias-edit-list');
          var arr2  = [];
          Array.prototype.forEach.call(
            ul2.querySelectorAll('li'),
            function(l){
              arr2.push({
                asignatura: l.getAttribute('data-asig'),
                cuat:       l.getAttribute('data-cuat')
              });
            }
          );
          var h2 = form2.querySelector('input[name="materias_in"]');
          if (h2) h2.value = JSON.stringify(arr2);
        });

        ul.appendChild(li2);
      });
    }
  } catch(e) {}

  form.style.display = 'none';
  var small = li.querySelector('.view-small');
  if (small) small.style.display = 'block';
})(this)
"""


_toggle_js = """
(function(btn){
  var li   = btn.closest('.pitem');
  var form = li.querySelector('.edit-form');
  var small = li.querySelector('.view-small');

  var show = form.style.display !== 'block';
  form.style.display = show ? 'block' : 'none';
  if (small) small.style.display = show ? 'none' : 'block';

  if (!show) return;

  // Si mostramos el formulario, reconstruimos la lista de materias desde el hidden
  var h  = form.querySelector('input[name="materias_in"]');
  var ul = form.querySelector('.materias-edit-list');
  if (!h || !ul) return;

  ul.innerHTML = '';
  try {
    var arr = JSON.parse(h.value || '[]') || [];
    arr.forEach(function(m){
      var li2 = document.createElement('li');
      li2.setAttribute('data-asig', m.asignatura || '');
      li2.setAttribute('data-cuat', m.cuat || '');

      var s1 = document.createElement('span');
      s1.className  = 'masig';
      s1.textContent = m.asignatura || '';
      li2.appendChild(s1);

      var s2 = document.createElement('span');
      s2.className  = 'mcuat';
      s2.textContent = m.cuat || '';
      li2.appendChild(s2);

      var del = document.createElement('button');
      del.type = 'button';
      del.textContent = 'X';
      del.addEventListener('click', function(){
        var li3 = this.closest('li');
        li3.parentElement.removeChild(li3);

        var form2 = this.closest('.edit-form');
        var ul2   = form2.querySelector('.materias-edit-list');
        var arr2  = [];
        Array.prototype.forEach.call(
          ul2.querySelectorAll('li'),
          function(l){
            arr2.push({
              asignatura: l.getAttribute('data-asig'),
              cuat:       l.getAttribute('data-cuat')
            });
          }
        );
        var h2 = form2.querySelector('input[name="materias_in"]');
        if (h2) h2.value = JSON.stringify(arr2);
      });

      ul.appendChild(li2);
    });
  } catch(e){}
})(this)
"""
def _escape_js_attr(js):
    # escapar &, <, >, " y adicionalmente ' y normalizar saltos de línea
    s = html.escape(js, quote=True)
    s = s.replace("'", "&#x27;")
    s = s.replace("\r", " ").replace("\n", " ")
    return s


def generate_dynamic_popup(row):
    """
    Popup SOLO con panel de edición visual (inputs dentro del popup).
    De momento NO guarda nada en el servidor: sirve para ver y editar
    los datos en pantalla (para copiar, revisar, etc.).
    """
    universidad = html.escape(str(row.get("universidad","")) or "Sin universidad")
    pais = html.escape(str(row.get("pais","") or ""))
    ciudad = html.escape(str(row.get("ciudad","") or ""))
    estudiantes = _normalize_estudiantes(row.get("estudiantes", []))
    n = len(estudiantes)

    subtitle = " · ".join(p for p in (pais, ciudad) if p)
    subtitle_html = f"<div class='sub'>{subtitle}</div>" if subtitle else ""

    items_html = []

    if not estudiantes:
        items_html.append(
            "<li class='pitem'>"
            "<div class='pname'>Sin estudiantes</div>"
            "</li>"
        )
    else:
        for idx, e in enumerate(estudiantes):
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

            # materias_in -> texto editable (una línea por materia, opcionalmente "Asignatura | Cuat")
            materias = e.get("materias_in") if isinstance(e, dict) else []
            if not isinstance(materias, list):
                materias = []
            lines = []
            for m in materias:
                if not isinstance(m, dict):
                    continue
                asig = _clean(m.get("asignatura"))
                cuat = _clean(m.get("cuat"))
                if not asig:
                    continue
                if cuat:
                    lines.append(f"{asig} | {cuat}")
                else:
                    lines.append(asig)
            materias_text = "\n".join(lines)

            items_html.append(f"""
            <li class="pitem">
              <div class="pname">👤 {nombre}</div>
              <div class="pdetails">
                <div class="edit-panel">
                  <div class="frow">
                    <div class="avatar">{html.escape((nombre_raw or ' ').strip()[:1].upper())}</div>
                    <div class="meta">
                      <div class="name">{nombre}</div>
                      <div class="small">
                        {_line("Email", email_val)}
                        {_line("Curso", curso_val)}
                        {_line("Cuatrimestre", cuatri_val)}
                      </div>
                    </div>
                  </div>

                  <div class="form-grid">
                    <div class="field">
                      <label>Nombre</label>
                      <input value="{html.escape(_clean(e.get("estudiante")), quote=True)}">
                    </div>
                    <div class="field">
                      <label>Email</label>
                      <input value="{html.escape(email_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Curso</label>
                      <input value="{html.escape(curso_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Cuatrimestre</label>
                      <input value="{html.escape(cuatri_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Duración (meses)</label>
                      <input value="{html.escape(dur_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Gestión LA</label>
                      <input value="{html.escape(gest_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Coordinador destino</label>
                      <input value="{html.escape(coord_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Learning Agreement (ruta/enlace)</label>
                      <input value="{html.escape(la_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>ToR (ruta/enlace)</label>
                      <input value="{html.escape(tor_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Acta de equivalencias</label>
                      <input value="{html.escape(acta_val, quote=True)}">
                    </div>
                    <div class="field">
                      <label>Plan de estudios (ruta/enlace)</label>
                      <input value="{html.escape(plan_val, quote=True)}">
                    </div>
                  </div>

                  <div class="field full">
                    <label>Materias IN (una por línea, opcionalmente "Asignatura | Cuatrimestre")</label>
                    <textarea rows="5">{html.escape(materias_text)}</textarea>
                  </div>

                  <div class="hint">
                    ⚠ De momento estos cambios son solo visuales en el popup.
                    Sirven para revisar o copiar datos; la lógica de guardado se puede añadir después.
                  </div>
                </div>
              </div>
            </li>
            """)

    html_out = f"""
    <div class="al-popup">
      <header class="head">
        <div class="title">{universidad}</div>
        <div class="badges">
          <span class="badge count">{n}</span>
          {f"<span class='badge country'>{pais}</span>" if pais else ""}
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
        padding: 12px;
        width: 520px;
        max-width: 520px;
        box-sizing: border-box;
        box-shadow: 0 6px 18px rgba(15,23,42,0.12);
      }}
      .head {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
        gap: 8px;
      }}
      .title {{
        font-weight: 700;
        color: #0B5ED7;
        font-size: 15px;
      }}
      .badges {{
        display: flex;
        gap: 6px;
        align-items: center;
      }}
      .badge {{
        background: #eef2ff;
        color: #0b4bd6;
        padding: 4px 8px;
        border-radius: 999px;
        font-weight: 600;
        font-size: 12px;
      }}
      .badge.count {{
        background: #0b5ed7;
        color: white;
      }}
      .sub {{
        color: #6b7280;
        font-size: 12px;
        margin-bottom: 6px;
      }}
      .plist {{
        list-style: none;
        padding: 0;
        margin: 6px 0 0 0;
        max-height: 360px;
        overflow: auto;
      }}
      .pitem + .pitem {{
        margin-top: 8px;
      }}
      .pname {{
        font-weight: 700;
        color: #0b5ed7;
        cursor: default;
        padding: 6px 8px;
        border-radius: 6px;
        background: #f3f4ff;
      }}
      .pdetails {{
        margin-top: 6px;
        background: #fbfbff;
        border-radius: 8px;
        padding: 8px;
        border: 1px solid #eef2ff;
      }}
      .edit-panel {{
        display: flex;
        flex-direction: column;
        gap: 8px;
      }}
      .frow {{
        display: flex;
        gap: 10px;
        align-items: center;
      }}
      .avatar {{
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background: linear-gradient(135deg,#7c3aed,#60a5fa);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
      }}
      .meta {{
        flex: 1;
        min-width: 0;
      }}
      .name {{
        font-weight: 700;
        color: #0b5ed7;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}
      .small {{
        font-size: 12px;
        color: #374151;
        margin-top: 4px;
      }}
      .form-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 6px 10px;
        margin-top: 6px;
      }}
      .field {{
        display: flex;
        flex-direction: column;
        gap: 3px;
        font-size: 12px;
      }}
      .field.full {{
        margin-top: 6px;
      }}
      .field label {{
        font-weight: 600;
        color: #4b5563;
      }}
      .field input, .field textarea {{
        width: 100%;
        font-size: 12px;
        padding: 5px 6px;
        border-radius: 4px;
        border: 1px solid #e5e7eb;
        box-sizing: border-box;
      }}
      .field textarea {{
        resize: vertical;
      }}
      .hint {{
        font-size: 11px;
        color: #6b7280;
        margin-top: 4px;
        font-style: italic;
      }}
      </style>
    </div>
    """
    return html_out


