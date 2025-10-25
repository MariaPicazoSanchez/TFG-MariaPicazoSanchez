import leafmap.foliumap as leafmap
import time
from geopy.geocoders import Nominatim
from pathlib import Path
import webbrowser
import pandas as pd
import random
import re


geolocator = Nominatim(user_agent="tfg-visualizador", timeout=5)

def obtener_coordenadas(ciudad):
    try:
        ubicacion = geolocator.geocode(ciudad)
        if ubicacion:
            return ubicacion.latitude, ubicacion.longitude
    except:
        time.sleep(1)
    return None

def extraer_ciudad(texto):
    """Extrae el texto entre paréntesis. Ej: 'Universidad de Salamanca (Salamanca)' -> 'Salamanca'"""
    match = re.search(r'\(([^)]+)\)', texto)
    return match.group(1) if match else texto


def generar_mapa_leafmap(estudiantes, ruta_salida="output/mapa_leafmap.html"):
    if not estudiantes:
        print("⚠️ No hay datos en la base de datos.")
        return

    registros = []
    coordenadas_cache = {}

    for persona in estudiantes:
        # persona es una tupla: (nombre, origen, destino, tipo, la_link)
        nombre = persona[0]
        origen = persona[1]
        destino = persona[2]
        tipo = persona[3]
        la_link = persona[4] if len(persona) > 4 else ""

        ciudad = extraer_ciudad(destino)
        if ciudad not in coordenadas_cache:
            coords = obtener_coordenadas(ciudad)
            coordenadas_cache[ciudad] = coords
        else:
            coords = coordenadas_cache[ciudad]

        if not coords:
            print(f"No se encontraron coordenadas para {ciudad}")
            continue

        registros.append({
            "nombre": nombre,
            "origen": origen,
            "destino": destino,
            "tipo": tipo,
            "la_link": la_link,
            "lat": coords[0],
            "lon": coords[1]
        })

    if not registros:
        print("⚠️ No se pudo generar el mapa: no hay registros válidos.")
        return

    df = pd.DataFrame(registros)

    m = leafmap.Map(center=[40, 0], zoom=4, draw_export=True)

    grupos = {}
    for _, row in df.iterrows():
        key = (row["lat"], row["lon"])
        grupos.setdefault(key, []).append(row.to_dict())

    colors = ["red", "blue", "green", "purple", "darkred", "darkblue", "darkgreen", "cadetblue", "orange", "darkpurple"]

    for (lat, lon), personas in grupos.items():
        # Construir popup con listado de personas en esa ubicación
        items_html = ""
        for p in personas:
            la_link_html = f"<a href='{p['la_link']}' target='_blank'>LA</a>" if p.get("la_link") else "—"
            items_html += f"<li><b>{p['nombre']}</b> ({p['tipo']}) — Origen: {p['origen']} — {la_link_html}</li>"

        destino = personas[0].get("destino", "")
        popup_html = f"""
        <div style='font-family:sans-serif;min-width:220px'>
            <b>{destino}</b><br>
            <ul style='padding-left:18px;margin:6px 0'>{items_html}</ul>
        </div>
        """

        m.add_marker(
            location=[lat, lon],
            popup=popup_html,
            tooltip=f"{len(personas)} estudiante(s) en {destino}",
            icon_color=random.choice(colors)
        )

    # df_nacional = df[df["tipo"] == "SICUE"]
    # df_internacional = df[df["tipo"] != "SICUE"]

    # def crear_popup(row):
    #     return f"""
    #     <div style='font-family:sans-serif;min-width:180px'>
    #         <b>{row['nombre']}</b><br>
    #         Origen: {row['origen']}<br>
    #         LA Link: {row['la_link']}<br><br>
    #         <button style='background-color:#4CAF50;color:white;border:none;
    #         padding:5px 10px;border-radius:5px;cursor:pointer;'>Acción</button>
    #     </div>
    #     """

    # colors = ["red", "blue", "green", "purple", "darkred", "darkblue", "darkgreen", "cadetblue", "orange", "darkpurple"]
    # for _, row in df_nacional.iterrows():
    #     m.add_marker(
    #         location=[row["lat"], row["lon"]],
    #         popup=crear_popup(row),
    #         tooltip=row["nombre"],
    #         icon_color=random.choice(colors)
    #     )

    # for _, row in df_internacional.iterrows():
    #     m.add_marker(
    #         location=[row["lat"], row["lon"]],
    #         popup=crear_popup(row),
    #         tooltip=row["nombre"],
    #         icon_color=random.choice(colors)
    #     )

    m.add_layer_control()
    m.to_html(ruta_salida)
    ruta_completa = Path(ruta_salida).resolve().as_uri()
    webbrowser.open(ruta_completa)
    print(f"✅ Mapa generado y guardado en {ruta_salida}")
    for persona in estudiantes:
        print(persona)
