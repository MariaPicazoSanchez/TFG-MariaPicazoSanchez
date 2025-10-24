# EJEMPLO DE EXTRACCIÓN DE DATOS
# Hay que saber como son los pdfs y modificar este código según el formato real
# TODO: hacer la inserción mediante la base de datos  

import fitz  # PyMuPDF
import re
import json
import os
#  TODO: cambiar cuando tenga ejemplos reales
def extraer_datos_pdf(ruta_pdf, ruta_json="output/datos_extraidos.json"):
    try:
        doc = fitz.open(ruta_pdf)
    except Exception as e:
        print(f"No se pudo abrir el PDF: {e}")
        return []

    texto = ""
    for pagina in doc:
        texto += pagina.get_text()

    texto = texto.replace("\n", " ").strip()

    # Expresiones regulares para extraer datos
    persona = re.search(r"Persona:\s*(.+?)\s*Origen:", texto)
    origen = re.search(r"Origen:\s*(.+?)\s*Destino:", texto)
    destino = re.search(r"Destino:\s*(.+?)\s*Fecha inicio:", texto)
    fecha_inicio = re.search(r"Fecha inicio:\s*(\d{2}/\d{2}/\d{2,4})", texto)
    fecha_fin = re.search(r"Fecha finalización:\s*(\d{2}/\d{2}/\d{2,4})", texto)
    materias = re.search(r"Materias:\s*(.+)", texto)

    nuevo_dato = {
        "nombre": persona.group(1).strip() if persona else "",
        "origen": origen.group(1).strip() if origen else "",
        "destino": destino.group(1).strip() if destino else "",
        "fecha_inicio": fecha_inicio.group(1).strip() if fecha_inicio else "",
        "fecha_fin": fecha_fin.group(1).strip() if fecha_fin else "",
        "materias": [m.strip() for m in materias.group(1).split(",")] if materias else [],
    }

    # Comprobación mínima: no guardar si no hay destino o nombre
    if not nuevo_dato["nombre"] or not nuevo_dato["destino"]:
        print("No se extrajeron datos válidos del PDF.")
        return []

    # Clasificar como nacional o internacional
    # TODO: mejorar con lista completa de destinos nacionales (automática)
    destinos_nacionales = ["Madrid", "Sevilla", "Murcia", "Barcelona", "Albacete", "Valencia"]
    nuevo_dato["tipo"] = "nacional" if nuevo_dato["destino"].capitalize() in destinos_nacionales else "internacional"

    # Leer JSON actual si existe y no está corrupto
    if os.path.exists(ruta_json):
        try:
            with open(ruta_json, "r", encoding="utf-8") as f:
                datos_actuales = json.load(f)
        except json.JSONDecodeError:
            print("Archivo JSON corrupto. Se sobrescribirá.")
            datos_actuales = []
    else:
        datos_actuales = []

    # Añadir y guardar
    datos_actuales.append(nuevo_dato)

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(datos_actuales, f, indent=2, ensure_ascii=False)

    print(f"- Datos extraídos y guardados en {ruta_json}")
    return datos_actuales