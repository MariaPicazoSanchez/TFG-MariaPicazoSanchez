from flask import Flask, request
from excel_update import actualizar_excel_materias_para_estudiante, update_student_in_excel
import json

app = Flask(__name__)

STREAMLIT_URL = "http://localhost:8501"


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
    print(f"[parse_materias_raw] Parsed materias: {materias}")
    return materias


@app.route("/update_student", methods=["POST"])
def update_student():
    form = request.form.to_dict()

    # Índices y ruta que vienen del formulario oculto del popup
    row_index_str = form.get("row_index", "-1")
    idx = int(form.get("idx", "-1"))
    excel_path = form.get("excel_path", "")

    if idx < 0 or not excel_path:
        return "Índices o ruta inválidos", 400

    # 1) Actualizar Excel principal con TU función antigua
    #    Firma: (excel_path, row_index, idx, data)
    update_student_in_excel(excel_path, row_index_str, idx, form)

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

    # 3) Ruta del Excel de materias desde config.json
    materias_path = ""
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        materias_path = config.get("Materias IN", "")
    except Exception as e:
        print(f"[update_student] Error al cargar config.json: {e}")
        materias_path = ""

    # 4) Actualizar Excel de asignaturas
    if materias_path and materias_in and est.get("estudiante"):
        actualizar_excel_materias_para_estudiante(materias_in, est, materias_path)

    return "<html><body><script>console.log('Alumno y materias actualizados');</script>OK</body></html>"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
