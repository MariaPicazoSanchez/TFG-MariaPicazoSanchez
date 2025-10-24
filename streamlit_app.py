import streamlit as st
import os
# TODO: descomentar cuando se use
# from extract_pdf import extraer_datos_pdf
# from map_generator import generar_mapa
from map_generator_leaf import generar_mapa_leafmap
from database import DatabaseManager

st.set_page_config(page_title="Visualizador de Traslados", layout="wide")
st.title("📍 Visualizador de Traslados")

db = DatabaseManager()
# USUARIOS DE PRUEBA
# --- ESTUDIANTE OUT ---
id_out = db.insertar_estudiante(
    nombre="Juan Pérez",
    origen="Universidad de Madrid (Madrid)",
    destino="Universidad de Barcelona (Barcelona)",
    tipo="out",
    la_link="http://enlace_la_out"
)
db.insertar_estudiante_out(
    estudiante_id=id_out,
    tor_link="http://enlace_tor",
    curso="2024-2025",
    acta_equivalencias="http://enlace_acta"
)

# --- ESTUDIANTE IN ---
id_in = db.insertar_estudiante(
    nombre="María López",
    origen="Universidad de Valencia (Valencia)",
    destino="Universidad de Sevilla (Sevilla)",
    tipo="in",
    la_link="http://enlace_la_in"
)
db.insertar_estudiante_in(
    estudiante_id=id_in,
    horario_link="http://enlace_horario"
)

# --- ESTUDIANTE SICUE ---
id_sicue = db.insertar_estudiante(
    nombre="Carlos García",
    origen="Universidad de Zaragoza (Zaragoza)",
    destino="Universidad de Salamanca (Salamanca)",
    tipo="SICUE",
    la_link="http://enlace_la_sicue"
)
db.insertar_estudiante_sicue(
    estudiante_id=id_sicue,
    plan_estudios_link="http://enlace_plan",
    firmado_origen="Firmado",
    firmado_destino="Firmado",
    enviado_vicerrectorado="Pendiente"
)

RUTA_DIR = "output"
RUTA_TEMP = os.path.join(RUTA_DIR, "temp.pdf")
RUTA_MAPA = os.path.join(RUTA_DIR, "mapa.html")
os.makedirs(RUTA_DIR, exist_ok=True)

# Subida de PDF
pdf = st.file_uploader("📄 Sube un archivo PDF", type=["pdf"])

if pdf is not None:
    try:
        with open(RUTA_TEMP, "wb") as f:
            f.write(pdf.read())
        # TODO: descomentar cuando se use
        # datos = extraer_datos_pdf(RUTA_TEMP)  # esta función debería actualizar output/datos_extraidos.json
        # if datos:
        #     st.success("✅ Datos extraídos y JSON actualizado.")
        # else:
        #     st.warning("⚠️ No se extrajo información válida del PDF.")
    except Exception as e:
        st.error(f"Error procesando el PDF: {e}")

st.divider()

# Mostrar datos 
estudiantes = db.obtener_estudiantes()
if estudiantes:
    if st.button("Mapa"):
        try:
            # Debes modificar generar_mapa_leafmap para que acepte datos directamente o lea de la base de datos
            generar_mapa_leafmap(estudiantes, RUTA_MAPA)
            st.success("✅ Mapa generado.")
        except Exception as e:
            st.error(f"Error generando el mapa: {e}")
