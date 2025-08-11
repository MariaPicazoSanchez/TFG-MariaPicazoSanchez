import streamlit as st
import os
from extract_pdf import extraer_datos_pdf
from map_generator import generar_mapa
from streamlit.components.v1 import iframe

st.set_page_config(page_title="Visualizador de Traslados", layout="wide")
st.title("📍 Visualizador de Erasmus mediante PDFs y JSON")

# Subida de PDF
pdf = st.file_uploader("📄 Sube un archivo PDF", type=["pdf"])

if pdf:
    # Guardar PDF temporalmente
    ruta_temp = "output/temp.pdf"
    with open(ruta_temp, "wb") as f:
        f.write(pdf.read())

    # Extraer datos y actualizar JSON
    datos = extraer_datos_pdf(ruta_temp)
    if datos:
        st.success("✅ Datos extraídos correctamente.")

        # Generar mapa con los datos acumulados
        generar_mapa()

        # Mostrar el mapa dentro del navegador
        ruta_mapa = "output/mapa.html"
        if os.path.exists(ruta_mapa):
            st.markdown("### 🌍 Mapa de traslados")
            iframe(ruta_mapa, height=600, width=1000)
        else:
            st.error("❌ No se pudo generar el mapa.")
    else:
        st.warning("⚠️ No se extrajo información válida del PDF.")
