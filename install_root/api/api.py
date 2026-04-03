"""
Microservicio Flask para la aplicación MovilidadESII.

Expone los endpoints REST que consume la capa de presentación (Streamlit).
El ciclo de vida del proceso (arranque / parada) se delega completamente
al orquestador (orchestrator/orchestrator.py).

Uso directo:
    python api/api.py
o a través del orquestador:
    python orchestrator/orchestrator.py
"""

import json
import logging
import os
import sys
from functools import wraps

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Asegurar que install_root/ esté en el path para que los imports relativos
# (security, persistence, …) se resuelvan correctamente aunque este fichero
# viva en el subdirectorio api/.
# ---------------------------------------------------------------------------
_api_dir  = os.path.dirname(os.path.abspath(__file__))   # .../install_root/api/
_root_dir = os.path.dirname(_api_dir)                    # .../install_root/
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from security import get_api_token
from utils.path_helpers import repair_windows_path


API_TOKEN = get_api_token()

app = Flask(__name__)
CORS(app)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logger = logging.getLogger("movilidad_api")


@app.get("/health")
def health():
    return {"ok": True}


# Timestamp del último guardado exitoso. Lo lee Streamlit via polling para
# saber cuándo recargar los datos sin necesidad de recargar la página.
_last_saved_ts = 0.0

@app.get("/saved_flag")
def saved_flag():
    return jsonify({"ts": _last_saved_ts})


def require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        expected = API_TOKEN

        if expected:
            token = request.headers.get("X-API-TOKEN")
            if not token:
                token = request.form.get("token") or request.args.get("token")

            if token != expected:
                logger.warning("Token inválido en la petición.")
                return jsonify({"ok": False, "error": "Unauthorized"}), 401

        return f(*args, **kwargs)
    return wrapper


def parse_materias_raw(materias_raw: str):
    """
    Acepta dos formatos:
    1) Legacy texto: "Nombre | 1 | x"
    2) JSON (nuevo frontend): [{"nombre":"...","cuat":"1","firmado":true}, ...]
    Devuelve lista de dicts:
      {"asignatura": ..., "cuat": ..., "firmado": "x" o ""}
    """
    materias = []
    if not materias_raw:
        return materias

    raw = str(materias_raw).strip()
    if not raw:
        return materias

    # 1) Intentar JSON primero (nuevo formato del frontend)
    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue

                    asig = (
                        str(item.get("asignatura") or item.get("nombre") or "")
                        .strip()
                    )
                    # Sanear dato corrupto: si asig es un JSON anidado, extraer el valor real
                    if asig and (asig.startswith("[") or asig.startswith("{")):
                        try:
                            _inner = json.loads(asig)
                            if isinstance(_inner, list) and _inner and isinstance(_inner[0], dict):
                                asig = str(_inner[0].get("asignatura") or _inner[0].get("nombre") or asig).strip()
                            elif isinstance(_inner, dict):
                                asig = str(_inner.get("asignatura") or _inner.get("nombre") or asig).strip()
                        except Exception:
                            pass
                    if not asig:
                        continue

                    cuat = str(item.get("cuat") or "").strip()

                    firmado_val = item.get("firmado", "")
                    if isinstance(firmado_val, bool):
                        firmado = "x" if firmado_val else ""
                    else:
                        firmado_norm = str(firmado_val).strip().lower()
                        firmado = "x" if firmado_norm in ("x", "1", "s", "si", "sí", "true", "t") else ""

                    materias.append({
                        "asignatura": asig,
                        "cuat": cuat,
                        "firmado": firmado,
                        "link_la": str(item.get("link_la") or item.get("la") or "").strip(),
                    })
                return materias
        except Exception as e:
            logger.debug("parse_materias_raw: JSON inválido, pruebo formato legacy. Error: %s", e)

    # 2) Formato legacy: líneas con |
    for line in raw.splitlines():
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
            "link_la": "",
        })

    return materias


def _build_js_response(ok: bool, messages: list[str], extra: dict | None = None):
    """
    Devuelve una página mínima que solo manda el resultado al iframe padre.
    """
    clean_msgs = [m.strip() for m in (messages or []) if m and m.strip()]
    payload = {
        "type": "saveStatus",
        "ok": bool(ok),
        "messages": clean_msgs,
    }

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
    return html, 200


@app.route("/update_student", methods=["POST"])
@require_token
def update_student():
    from persistence import actualizar_excel_materias_para_estudiante, update_student_in_excel

    try:
        form = request.form.to_dict()

        # Índices y ruta del Excel principal que vienen del popup
        row_index_str = form.get("row_index", "-1")
        idx = int(form.get("idx", "-1"))
        excel_path_raw = form.get("excel_path", "")

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
            logger.debug("No se pudo leer config.json para '%s': %s", programa, e)

        # Si la ruta de config existe, usarla; si no, mantener la del form
        if excel_cfg and os.path.exists(excel_cfg):
            excel_path = excel_cfg

        logger.debug(
            "Ruta Excel procesada: raw=%r -> final=%r (existe=%s)",
            excel_path_raw, excel_path, os.path.exists(excel_path)
        )

    except Exception as e:
        logger.exception("Excepción no capturada al procesar update_student")
        return _build_js_response(False, [f"EXCEPCION NO CAPTURADA: {e}"])

    old_email = (form.get("old_email") or "").strip()
    old_nombre = (form.get("old_nombre") or "").strip()
    students_sheet_name = (form.get("students_sheet_name") or "").strip()
    logger.debug("students_sheet_name=%r", students_sheet_name)

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
    email  = (form.get("email") or "").strip()
    ciudad = (form.get("ciudad") or "").strip()
    pais   = (form.get("pais") or "").strip()

    if not nombre:
        return _build_js_response(False, ["El nombre no puede estar vacío."])
    if not ciudad and not pais:
        return _build_js_response(False, ["Debe indicar ciudad o país."])

    if idx < 0 or not excel_path:
        return _build_js_response(False, ["Índices o ruta del Excel principal inválidos."])

    # 1) Actualizar Excel principal (alumnos)
    try:
        # Para Erasmus IN no existe tabla de alumnos separada: los datos del alumno
        # están en el Excel de materias. Se salta update_student_in_excel y se va
        # directamente al guardado de materias.
        es_erasmus_in = programa.lower() in ("erasmus in",)
        if es_erasmus_in:
            logger.debug("Programa Erasmus IN: se omite update_student_in_excel.")
            ok_main = True
        else:
            # Firma real: (excel_path: str, row_index: str, idx: int, data: dict)
            ok_main = update_student_in_excel(excel_path, row_index_str, idx, form, old_email=old_email, old_nombre=old_nombre, target_sheet=students_sheet_name)

        if ok_main:
            # 2) Procesar materias_raw
            materias_raw = form.get("materias_raw", "")
            logger.debug("materias_raw (primeros 200 chars) = %r", (materias_raw or '')[:200])
            materias_in = parse_materias_raw(materias_raw)
            logger.debug("materias_in parseadas = %d", len(materias_in))

            # Validación Erasmus IN: debe tener al menos una asignatura
            # (los alumnos de investigación están exentos; siempre conservan "Estancia Investigación")
            is_investigacion = (form.get("is_investigacion", "") == "1")
            if es_erasmus_in and not materias_in and not is_investigacion:
                return _build_js_response(False, ["El alumno debe tener al menos una asignatura."])

            # Si es investigación y materias_raw llegó vacío, restaurar la materia por defecto
            if is_investigacion and not materias_in:
                materias_in = [{"asignatura": "Estancia Investigaci\u00f3n", "cuat": "", "firmado": "", "link_la": ""}]

            materias_sheet_name = (form.get("materias_sheet_name") or "").strip()
            logger.debug("materias_sheet_name='%s'", materias_sheet_name)

            est = {
                "estudiante":         (form.get("estudiante") or "").strip(),
                "old_nombre":         (old_nombre or "").strip(),
                "old_email":          (old_email or "").strip(),

                # ORIGEN en materias = país (prioridad)
                "pais":               (form.get("pais") or "").strip(),
                "origen":             (form.get("pais") or form.get("origen") or "").strip(),

                # UNIVERSIDAD (prioridad explícita)
                "universidad_origen": (
                    form.get("universidad_origen")
                    or form.get("destino")
                    or form.get("Centro")
                    or form.get("universidad")
                    or ""
                ).strip(),

                # compatibilidad con código antiguo
                "destino": (
                    form.get("universidad_origen")
                    or form.get("destino")
                    or form.get("Centro")
                    or form.get("universidad")
                    or ""
                ).strip(),

                "ciudad":  (form.get("ciudad") or "").strip(),

                # Campos globales del alumno (mismos para todas sus filas en el Excel de materias)
                "cuat":    (form.get("cuatrimestre") or "").strip(),
                "firmado": (form.get("firmado") or "").strip().lower(),
                "link_la": (form.get("link_la") or "").strip(),
            }

            # 3) Obtener la ruta del Excel de materias SIEMPRE desde config.json ("Erasmus IN")
            materias_path = ""
            try:
                cfg_path = os.getenv("APP_CONFIG_PATH", "config.json")
                with open(cfg_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                materias_path_raw = (config.get("Erasmus IN", "") or "").strip()
                # REPARAR y normalizar ruta
                materias_path = repair_windows_path(materias_path_raw)
                logger.debug(
                    "materias_path: raw=%r -> reparado=%r (existe=%s)",
                    materias_path_raw, materias_path,
                    os.path.exists(materias_path) if materias_path else False
                )
            except Exception as e:
                logger.exception("Error leyendo config.json para materias_path")
                materias_path = ""

            # 4) Actualizar Excel de asignaturas
            if materias_path and est.get("estudiante"):
                try:
                    actualizar_excel_materias_para_estudiante(materias_in, est, materias_path, sheet_name=materias_sheet_name)
                except PermissionError:
                    ok_global = False
                    logger.warning("PermissionError al guardar el Excel de materias (%s): archivo abierto.", materias_path)
                    messages.append("No se puede guardar: el archivo Excel de materias está abierto en otro programa. Ciérralo e inténtalo de nuevo.")
                except Exception as e:
                    ok_global = False
                    logger.exception("Error al actualizar el Excel de materias '%s'", materias_path)
                    messages.append(f"Error al actualizar el Excel de materias: {e}")
            elif not materias_path and est.get("estudiante"):
                ok_global = False
                logger.error("No se pudo obtener la ruta del Excel de materias desde config.json.")
                messages.append("No se ha podido obtener la ruta del Excel de materias desde config.json (clave 'Erasmus IN').")

        else:
            ok_global = False
            messages.append(
                f"No se han podido guardar los datos en el Excel principal ({excel_path}). "
                "Puede que el archivo esté abierto en Excel o protegido."
            )
    except PermissionError:
        ok_global = False
        logger.warning("PermissionError al guardar el Excel principal: archivo abierto.")
        messages.append("No se puede guardar: el archivo Excel principal está abierto en otro programa. Ciérralo e inténtalo de nuevo.")
    except Exception as e:
        logger.exception("Error al actualizar el Excel principal '%s'", excel_path)
        ok_global = False
        messages.append(f"Error al actualizar el Excel principal: {e}")

    # Si el guardado fue OK, leer la fila actualizada del Excel
    extra = None
    if ok_global:
        try:
            if excel_path and os.path.exists(excel_path):
                try:
                    df_check = pd.read_excel(excel_path)
                    ri = int(row_index_str) if row_index_str and str(row_index_str).isdigit() else None
                    row_dict = None
                    student_obj = None
                    if ri is not None and 0 <= ri < len(df_check):
                        row_series = df_check.iloc[ri]
                        row_dict = row_series.to_dict()
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
                        'programa':    programa,
                        'row_index':   row_index_str,
                        'idx':         idx,
                        'row':         row_dict,
                        'student':     student_obj,
                    }
                except Exception as e:
                    logger.debug("Error leyendo fila actualizada: %s", e)
        except Exception:
            pass

    logger.info("update_student resultado: ok=%s messages=%s", ok_global, messages)
    if ok_global:
        import time as _time
        global _last_saved_ts
        _last_saved_ts = _time.time()
    return _build_js_response(ok_global, messages, extra)


if __name__ == "__main__":
    # Configurar logging a nivel DEBUG para el proceso de la API
    _log_dir = os.path.join(os.getenv("LOCALAPPDATA", "."), "MovilidadESII", "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_file = os.path.join(_log_dir, "api.log")
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(_log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "5000"))
    app.run(host=host, port=port, debug=False)