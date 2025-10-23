import leafmap.foliumap as leafmap
import json
import os
import time
from geopy.geocoders import Nominatim
from pathlib import Path
import webbrowser
import pandas as pd


geolocator = Nominatim(user_agent="tfg-visualizador", timeout=5)

def obtener_coordenadas(ciudad):
    try:
        ubicacion = geolocator.geocode(ciudad)
        if ubicacion:
            return ubicacion.latitude, ubicacion.longitude
    except:
        time.sleep(1)
    return None


def generar_mapa_leafmap(ruta_json="output/datos_extraidos.json", ruta_salida="output/mapa_leafmap.html"):
    if not os.path.exists(ruta_json):
        print(f"❌ No existe el archivo {ruta_json}")
        return

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    if not datos:
        print("⚠️ No hay datos en el JSON.")
        return

    registros = []
    coordenadas_cache = {}

    for persona in datos:
        ciudad = persona["destino"]
        if ciudad not in coordenadas_cache:
            coords = obtener_coordenadas(ciudad)
            coordenadas_cache[ciudad] = coords
        else:
            coords = coordenadas_cache[ciudad]

        if not coords:
            print(f"No se encontraron coordenadas para {ciudad}")
            continue

        registros.append({
            "nombre": persona["nombre"],
            "origen": persona["origen"],
            "destino": ciudad,
            "tipo": persona["tipo"],
            "materias": ", ".join(persona["materias"]),
            "lat": coords[0],
            "lon": coords[1]
        })

    if not registros:
        print("⚠️ No se pudo generar el mapa: no hay registros válidos.")
        return

    df = pd.DataFrame(registros)

    m = leafmap.Map(center=[40, 0], zoom=4, draw_export=True)
    m.add_basemap("CartoDB.Positron")

    # Capas separadas
    df_nacional = df[df["tipo"] == "nacional"]
    df_internacional = df[df["tipo"] != "nacional"]

    # --- NUEVA FUNCIÓN PARA POPUP PERSONALIZADO ---
    def crear_popup(row):
        return f"""
        <div style='font-family:sans-serif;min-width:180px'>
            <b>{row['nombre']}</b><br>
            Origen: {row['origen']}<br>
            Materias: {row['materias']}<br><br>
            <button style='background-color:#4CAF50;color:white;border:none;
            padding:5px 10px;border-radius:5px;cursor:pointer;'>Acción</button>
        </div>
        """

    # --- NACIONALES ---
    for _, row in df_nacional.iterrows():
        m.add_marker(
            location=[row["lat"], row["lon"]],
            popup=crear_popup(row),
            tooltip=row["nombre"],
            icon_color="blue"
        )

    # --- INTERNACIONALES ---
    for _, row in df_internacional.iterrows():
        m.add_marker(
            location=[row["lat"], row["lon"]],
            popup=crear_popup(row),
            tooltip=row["nombre"],
            icon_color="orange"
        )

    m.add_layer_control()

    m.to_html(ruta_salida)
    ruta_completa = Path(ruta_salida).resolve().as_uri()
    webbrowser.open(ruta_completa)
    print(f"✅ Mapa generado y guardado en {ruta_salida}")
