from flask import Flask, request
from excel_update import actualizar_excel_materias_para_estudiante, update_student_in_excel
import json
import streamlit as st

app = Flask(__name__)

def parse_materias_raw(materias_raw: str):
    """
    "Nombre | 1 | x"  ->  {"asignatura":..., "cuat":"1", "firmado":"x"}
    """
    materias = []
    if not materias_raw:
        return materias

    for line in materias_raw.splitlines():
        line = line.strip()
        if not line:
            continue

        partes = [p.strip() for p in line.split("|")]
        if not partes or not partes[0]:
            continue

        asig = partes[0]
        cuat = partes[1] if len(partes) > 1 else ""
        firmado_flag = partes[2] if len(partes) > 2 else ""

        firmado_norm = str(firmado_flag).strip().lower()
        firmado = "x" if firmado_norm in ("x", "1", "s", "si", "sí", "true", "t") else ""

        materias.append({
            "asignatura": asig,
            "cuat": cuat,
            "firmado": firmado,
        })

    return materias

def _build_js_response(ok: bool, messages: list[str]):
    """
    Devuelve una página mínima que solo manda el resultado al iframe padre.
    Nada más: sin window.addEventListener ni cosas raras para no romper el JS.
    """
    clean_msgs = [m.strip() for m in (messages or []) if m and m.strip()]
    payload = {
        "type": "saveStatus",
        "ok": bool(ok),
        "messages": clean_msgs,
    }

    # Evita que aparezca </script> dentro del JSON
    payload_json = json.dumps(payload).replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html>
  <head><meta charset="utf-8"></head>
  <body>
    <script>
      (function() {{
        try {{
          var data = {payload_json};
          if (window.parent && window.parent.postMessage) {{
            window.parent.postMessage(data, "*");
          }} else {{
            console.log('saveStatus (sin parent):', data);
          }}
        }} catch (e) {{
          console.log('Error en saveStatus:', e);
        }}
      }})();
    </script>
  </body>
</html>
"""
    return html, (200 if ok else 500)



@app.route("/update_student", methods=["POST"])
def update_student():
    form = request.form.to_dict()

    # Índices y ruta del Excel principal que vienen del popup
    row_index_str = form.get("row_index", "-1")
    idx = int(form.get("idx", "-1"))
    excel_path = form.get("excel_path", "")

    messages = []
    ok_global = True

    if idx < 0 or not excel_path:
        return _build_js_response(False, ["Índices o ruta del Excel principal inválidos."])

    # 1) Actualizar Excel principal (alumnos)
    try:
        # Firma real: (excel_path: str, row_index: str, idx: int, data: dict)
        ok_main = update_student_in_excel(excel_path, row_index_str, idx, form)

        if ok_main:
            messages.append("Datos del estudiante actualizados correctamente.")
        else:
            ok_global = False
            messages.append(
                f"No se han podido guardar los datos en el Excel principal ({excel_path}). "
                "Puede que el archivo esté abierto en Excel o protegido."
            )
    except Exception as e:
        ok_global = False
        messages.append(f"Error al actualizar el Excel principal ({excel_path}): {e}")


    # 2) Procesar materias_raw
    materias_raw = form.get("materias_raw", "")
    materias_in = parse_materias_raw(materias_raw)

    est = {
        "estudiante": form.get("estudiante", "").strip(),
        "origen": (form.get("origen") or form.get("pais") or "").strip(),
        "destino": (form.get("destino") or form.get("Centro") or form.get("universidad") or "").strip(),
        "pais": form.get("pais", "").strip(),
        "ciudad": form.get("ciudad", "").strip(),
    }

    # 3) Obtener la ruta del Excel de materias SIEMPRE desde config.json ("Materias IN")
    materias_path = ""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        materias_path = (config.get("Materias IN", "") or "").strip()
        print("[update_student] materias_path (Materias IN) =", materias_path)
    except Exception as e:
        print("[update_student] Error leyendo config.json:", e)
        materias_path = ""

    # 4) Actualizar Excel de asignaturas (solo si hay ruta + materias + nombre)
    if materias_path and materias_in and est.get("estudiante"):
        try:
            actualizar_excel_materias_para_estudiante(materias_in, est, materias_path)
            messages.append("Asignaturas actualizadas correctamente en el Excel de materias.")
        except Exception as e:
            ok_global = False
            messages.append(f"Error al actualizar el Excel de materias ({materias_path}): {e}")
    elif materias_in and not materias_path:
        ok_global = False
        messages.append("No se ha podido obtener la ruta del Excel de materias desde config.json (clave 'Materias IN').")

    return _build_js_response(ok_global, messages)



if __name__ == "__main__":
    app.run(debug=True, port=5000)
