from flask import Flask, jsonify, request
from flask_cors import CORS
# from persistence import actualizar_excel_materias_para_estudiante, update_student_in_excel
import json
import os
import pandas as pd
from functools import wraps
from security import get_api_token
import logging
import warnings
import time

def repair_windows_path(path_str: str) -> str:
    """
    Repara rutas de Windows mal formadas.
    Ejemplo: 'C:UsersmariaAppDataLocalMovilidadESII' -> 'C:\\Users\\maria\\AppData\\Local\\MovilidadESII'
    """
    if not path_str:
        return ""
    
    # Si ya tiene barras invertidas, normalizarla
    if "\\" in path_str:
        return os.path.normpath(path_str)
    
    # Si tiene barras diagonales, reemplazarlas
    if "/" in path_str:
        return os.path.normpath(path_str.replace("/", "\\"))
    
    # Si NO tiene barras (ej: C:UsersmariaAppData...), insertar después de C:
    # Patrón: C:Users... -> C:\Users...
    if len(path_str) > 2 and path_str[1] == ":" and path_str[2] != "\\":
        path_str = path_str[0:2] + "\\" + path_str[2:]
    
    return os.path.normpath(path_str)

LAST_PING = time.time()
API_TOKEN = get_api_token()


app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/ping")
def ping():
    global LAST_PING
    LAST_PING = time.time()
    return {"ok": True}

@app.get("/last_ping")
def last_ping():
    return {"ok": True, "ts": LAST_PING}

def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        expected = API_TOKEN

        if expected:
            token = request.headers.get("X-API-TOKEN")
            if not token:
                token = request.form.get("token") or request.args.get("token")

            if token != expected:
                print("❌ Token inválido. Esperado:", expected, "Recibido:", token)
                return jsonify({"ok": False, "error": "Unauthorized"}), 401
            else:
                print("Token válido recibido.")

        return f(*args, **kwargs)
    return wrapper



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

def _build_js_response(ok: bool, messages: list[str], extra: dict | None = None):
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
    # Merge extra payload if provided (e.g., updated row info)
    if extra and isinstance(extra, dict):
        payload.update(extra)

    # Evita que aparezca </script> dentro del JSON
    payload_json = json.dumps(payload, default=str).replace("</", "<\\/")

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
@require_token
def update_student():
    from persistence import actualizar_excel_materias_para_estudiante, update_student_in_excel

    form = request.form.to_dict()

    # Índices y ruta del Excel principal que vienen del popup
    row_index_str = form.get("row_index", "-1")
    idx = int(form.get("idx", "-1"))
    excel_path_raw = form.get("excel_path", "")
    
    print(f"\n{'='*60}")
    print(f"[API] FORM recibido del frontend:")
    for k, v in form.items():
        if 'path' in k.lower():
            print(f"  {k} (raw)   = {repr(v)}")
    
    # REPARAR y normalizar ruta (desde el formulario)
    excel_path = repair_windows_path(excel_path_raw)

    # Preferir SIEMPRE la ruta desde config.json según el programa
    programa = (form.get("programa") or "").strip()
    excel_cfg_raw = ""
    excel_cfg = ""
    try:
        cfg_path = os.getenv("APP_CONFIG_PATH", "config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        if programa:
            excel_cfg_raw = (config.get(programa, "") or "").strip()
            excel_cfg = repair_windows_path(excel_cfg_raw)
    except Exception as e:
        print(f"[API] No se pudo leer config.json para '{programa}': {e}")

    # Si la ruta de config existe, usarla; si no, mantener la del form
    if excel_cfg:
        print(f"[API] excel (config) raw={repr(excel_cfg_raw)} -> {repr(excel_cfg)} exists={os.path.exists(excel_cfg)}")
        if os.path.exists(excel_cfg):
            excel_path = excel_cfg
    
    print(f"\n[API] RUTA PROCESADA:")
    print(f"  excel_path_raw  = {repr(excel_path_raw)}")
    print(f"  excel_path (OK) = {repr(excel_path)}")
    print(f"  Existe archivo? {os.path.exists(excel_path)}")
    print(f"{'='*60}\n")

    old_email = (form.get("old_email") or "").strip()
    old_nombre = (form.get("old_nombre") or "").strip()

    messages = []
    ok_global = True
    
    # Validación: la ruta debe venir y el archivo debe existir
    if not excel_path:
        return _build_js_response(False, [
            "ERROR: No se recibió ruta del Excel.",
            "Intenta recargar la página o revisa config.json."])
    
    if not os.path.exists(excel_path):
        return _build_js_response(False, [
            f"ERROR: El archivo Excel no existe en: {excel_path}",
            "Verifica que el archivo esté en AppData\\Local\\MovilidadESII\\data_demo y que config.json apunte ahí."])
    
    # === Validación de campos obligatorios ===
    nombre = (form.get("estudiante") or "").strip()
    email = (form.get("email") or "").strip()
    ciudad = (form.get("ciudad") or "").strip()
    pais = (form.get("pais") or "").strip()

    if not nombre:
        return _build_js_response(False, ["El nombre no puede estar vacío."])
    if not email:
        return _build_js_response(False, ["El correo no puede estar vacío."])
    if not ciudad and not pais:
        return _build_js_response(False, ["Debe indicar ciudad o país."])

    if idx < 0 or not excel_path:
        return _build_js_response(False, ["Índices o ruta del Excel principal inválidos."])


    if idx < 0 or not excel_path:
        return _build_js_response(False, ["Índices o ruta del Excel principal inválidos."])

    # 1) Actualizar Excel principal (alumnos)
    try:
        # Firma real: (excel_path: str, row_index: str, idx: int, data: dict)
        ok_main = update_student_in_excel(excel_path, row_index_str, idx, form, old_email=old_email, old_nombre=old_nombre)

        if ok_main:
            messages.append("Datos del estudiante actualizados correctamente.")
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
                cfg_path = os.getenv("APP_CONFIG_PATH", "config.json")
                with open(cfg_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                materias_path_raw = (config.get("Materias IN", "") or "").strip()
                # REPARAR y normalizar ruta
                materias_path = repair_windows_path(materias_path_raw)
                print(f"[update_student] materias_path_raw={materias_path_raw}")
                print(f"[update_student] materias_path (reparado)={materias_path}")
            except Exception as e:
                print(f"[update_student] Error leyendo config.json: {e}")
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


           
        else:
            ok_global = False
            messages.append(
                f"No se han podido guardar los datos en el Excel principal ({excel_path}). "
                "Puede que el archivo esté abierto en Excel o protegido."
            )
    except Exception as e:
        ok_global = False
        messages.append(f"Error al actualizar el Excel principal ({excel_path}): {e}")
    
    
    

    # If the save went OK, attempt to read the updated row from the Excel
    extra = None
    if ok_global:
        try:
            # Leer el Excel y extraer la fila por índice
            if excel_path and os.path.exists(excel_path):
                try:
                    df_check = pd.read_excel(excel_path)
                    ri = int(row_index_str) if row_index_str and str(row_index_str).isdigit() else None
                    row_dict = None
                    student_obj = None
                    if ri is not None and 0 <= ri < len(df_check):
                        row_series = df_check.iloc[ri]
                        row_dict = row_series.to_dict()
                        # intentar extraer estudiante concreto si existe columna 'estudiantes'
                        try:
                            raw = row_series.get('estudiantes')
                            if isinstance(raw, str) and raw.strip():
                                lst = json.loads(raw)
                            elif isinstance(raw, list):
                                lst = raw
                            else:
                                lst = []
                            if isinstance(lst, list) and 0 <= idx < len(lst):
                                student_obj = lst[idx]
                        except Exception:
                            student_obj = None
                    extra = {
                        'programa': programa,
                        'row_index': row_index_str,
                        'idx': idx,
                        'row': row_dict,
                        'student': student_obj,
                    }
                except Exception as e:
                    print('[API] Error leyendo fila actualizada:', e)
        except Exception:
            pass

    return _build_js_response(ok_global, messages, extra)



if __name__ == "__main__":
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "5000"))
    app.run(host=host, port=port, debug=False)

