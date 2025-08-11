import folium
import json
import os
from geopy.geocoders import Nominatim
from folium import CircleMarker, FeatureGroup, LayerControl
import webbrowser
import time
from pathlib import Path


geolocator = Nominatim(user_agent="tfg-visualizador", timeout=5)

def obtener_coordenadas(ciudad):
    try:
        ubicacion = geolocator.geocode(ciudad)
        if ubicacion:
            return ubicacion.latitude, ubicacion.longitude
    except:
        time.sleep(1)
    return None

def generar_mapa(ruta_json="output/datos_extraidos.json", ruta_salida="output/mapa.html"):
    if not os.path.exists(ruta_json):
        print(f"❌ No existe el archivo {ruta_json}")
        return

    with open(ruta_json, "r", encoding="utf-8") as f:
        datos = json.load(f)

    if not datos:
        print("⚠️ No hay datos en el JSON.")
        return

    mapa = folium.Map(location=[40.0, -3.7], zoom_start=5)

    grupo_nacional = FeatureGroup(name="Traslados Nacionales")
    grupo_internacional = FeatureGroup(name="Traslados Internacionales")

    # Agrupar datos por ciudad
    agrupados = {}  # clave: ciudad, valor: lista de personas
    coordenadas_cache = {}

    for persona in datos:
        ciudad = persona["destino"]
        if ciudad not in agrupados:
            agrupados[ciudad] = []
        agrupados[ciudad].append(persona)

    for ciudad, lista_personas in agrupados.items():
        # Obtener coordenadas con caché
        if ciudad not in coordenadas_cache:
            coords = obtener_coordenadas(ciudad)
            coordenadas_cache[ciudad] = coords
        else:
            coords = coordenadas_cache[ciudad]

        if not coords:
            print(f"No se encontraron coordenadas para {ciudad}")
            continue

        texto_popup = "<b>" + ciudad + "</b><br>Total traslados: " + str(len(lista_personas)) + "<br><br>"
        for persona in lista_personas:
            texto_popup += f"👤 <b>{persona['nombre']}</b><br>"
            texto_popup += f"📍 Origen: {persona['origen']}<br>"
            texto_popup += f"📚 Materias: {', '.join(persona['materias'])}<br><hr>"

        marcador = CircleMarker(
            location=coords,
            radius=10 + len(lista_personas),  # tamaño dinámico
            color="black",
            fill=True,
            fill_color="blue" if lista_personas[0]["tipo"] == "nacional" else "orange",
            fill_opacity=0.6,
            tooltip=f"{ciudad}: {len(lista_personas)} traslado(s)",
            popup=folium.Popup(texto_popup, max_width=300)
        )

        if lista_personas[0]["tipo"] == "nacional":
            marcador.add_to(grupo_nacional)
        else:
            marcador.add_to(grupo_internacional)

    grupo_nacional.add_to(mapa)
    grupo_internacional.add_to(mapa)
    LayerControl().add_to(mapa)


    mapa.save(ruta_salida)

    # Abrir el HTML
    ruta_completa = Path(ruta_salida).resolve().as_uri()
    webbrowser.open(ruta_completa)
    print(f"- Mapa generado y guardado en {ruta_salida}")
