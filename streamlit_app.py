import streamlit as st
import os
from datos_prueba_bd import datos_prueba 
# TODO: descomentar cuando se use
# from extract_pdf import extraer_datos_pdf
# from map_generator import generar_mapa
from map_generator_leaf import generar_mapa_leafmap
from database import DatabaseManager

st.set_page_config(page_title="Visualizador de Traslados", layout="wide")
st.title("📍 Visualizador de Traslados")

db = DatabaseManager()


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
# if estudiantes != None:
#     datos_prueba()
if st.button("Mapa"):
    try:
        # Debes modificar generar_mapa_leafmap para que acepte datos directamente o lea de la base de datos
        generar_mapa_leafmap(estudiantes, RUTA_MAPA)
        st.success("✅ Mapa generado.")
    except Exception as e:
        st.error(f"Error generando el mapa: {e}")

