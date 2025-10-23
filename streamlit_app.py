import streamlit as st
import os
from extract_pdf import extraer_datos_pdf
from map_generator import generar_mapa
from map_generator_leaf import generar_mapa_leafmap
from streamlit.components.v1 import iframe

st.set_page_config(page_title="Visualizador de Traslados", layout="wide")
st.title("📍 Visualizador de Traslados")

RUTA_DIR = "output"
RUTA_TEMP = os.path.join(RUTA_DIR, "temp.pdf")
RUTA_JSON = os.path.join(RUTA_DIR, "datos_extraidos.json")
RUTA_MAPA = os.path.join(RUTA_DIR, "mapa.html")
os.makedirs(RUTA_DIR, exist_ok=True)

# Subida de PDF
pdf = st.file_uploader("📄 Sube un archivo PDF", type=["pdf"])

if pdf is not None:
    try:
        with open(RUTA_TEMP, "wb") as f:
            f.write(pdf.read())
        datos = extraer_datos_pdf(RUTA_TEMP)  # esta función debería actualizar output/datos_extraidos.json
        if datos:
            st.success("✅ Datos extraídos y JSON actualizado.")
        else:
            st.warning("⚠️ No se extrajo información válida del PDF.")
    except Exception as e:
        st.error(f"Error procesando el PDF: {e}")

st.divider()

# Mostrar datos extraídos
if os.path.exists(RUTA_JSON):
    if st.button("Mapa"):
        try:
            # generar_mapa(RUTA_JSON, RUTA_MAPA)
            generar_mapa_leafmap(RUTA_JSON, RUTA_MAPA)
            st.success("✅ Mapa generado.")
        except Exception as e:
            st.error(f"Error generando el mapa: {e}")
    