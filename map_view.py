import folium
import pandas as pd
import streamlit as st
import leafmap.foliumap as leafmap
from popup_templates import generate_dynamic_popup
from materias_in_loader import get_materias_in_por_estudiante
from domain import PROGRAM_COLORS


def add_points_to_map(m, df, nombre_capa, color):
    """Añade puntos de un DataFrame al mapa."""
    if {"latitud", "longitud"}.issubset(df.columns):
        for _, row in df.iterrows():
            nombre = row.get("nombre", "Sin nombre")
            lat, lon = row["latitud"], row["longitud"]
            m.add_marker(
                location=[lat, lon],
                popup=f"<b>{nombre}</b><br><i>{nombre_capa}</i>",
                icon_color=color
            )

def group_rows_by_location(df, decimals=5):
    """
    Devuelve una lista de dicts con:
      {universidad, pais, latitud, longitud, estudiantes:[...]}
    - Si df YA trae una columna 'estudiantes' con listas, la respeta (no reagrupa).
    - Si df viene “en bruto”, agrupa por ubicación y construye la lista.
    """
    df = df.copy()
    # Caso 1: df ya está agrupado (columna 'estudiantes' con listas de dicts)
    if "estudiantes" in df.columns and df["estudiantes"].apply(lambda v: isinstance(v, (list, tuple))).all():
        out = []
        for _, r in df.iterrows():
            if pd.isna(r.get("latitud")) or pd.isna(r.get("longitud")):
                continue
            out.append({
                "universidad": r.get("universidad", ""),
                "pais": r.get("pais", ""),
                "latitud": float(r["latitud"]),
                "longitud": float(r["longitud"]),
                "estudiantes": list(r["estudiantes"]) or []
            })
        return out

    df["latitud"]  = pd.to_numeric(df.get("latitud"), errors="coerce")
    df["longitud"] = pd.to_numeric(df.get("longitud"), errors="coerce")
    df = df.dropna(subset=["latitud","longitud"])

    df["_lat_r"] = df["latitud"].round(decimals)
    df["_lon_r"] = df["longitud"].round(decimals)

    student_cols = [c for c in ["estudiante","curso","link_LA","ToR","acta_equivalencias","link_plan"] if c in df.columns]
    keys = [c for c in ["universidad","pais","_lat_r","_lon_r"] if c in df.columns]

    grouped = []
    for key_vals, g in df.groupby(keys, dropna=False):
        u = g["universidad"].iloc[0] if "universidad" in g.columns else ""
        p = g["pais"].iloc[0] if "pais" in g.columns else ""
        lat = float(g["latitud"].iloc[0])
        lon = float(g["longitud"].iloc[0])
        estudiantes = g[student_cols].to_dict("records")
        grouped.append({"universidad": u, "pais": p, "latitud": lat, "longitud": lon, "estudiantes": estudiantes})
    return grouped



def show_map(dfs: dict, base_map, materias_in_por_estudiante=None):
    """
    Muestra TODOS los programas disponibles en `dfs` sin filtrar.
    dfs: dict con posibles claves "Erasmus OUT", "Erasmus IN", "SICUE OUT" -> DataFrames agrupados
    """
    if materias_in_por_estudiante is None:
        materias_in_por_estudiante = {}

    # 1) Mapa base
    if hasattr(base_map, "add_child"):
        m = base_map
    else:
        m = leafmap.Map(center=(40.4168, -3.7038), zoom=4, tiles=None)
        try:
            m.add_basemap(base_map if isinstance(base_map, str) else "CartoDB.Positron")
        except Exception:
            m.add_basemap("CartoDB.Positron")

    # Quitar padding del popup de Leaflet (global)
    m.get_root().html.add_child(folium.Element("""
    <style>
      .leaflet-popup-content { margin:0 !important; }
      .leaflet-popup-content-wrapper { padding:0 !important; }
    </style>
    """))

    # Helpers de tamaño
    def _estimate_popup_width_px(row):
        def s(v): return str(v or "")
        textos = [s(row.get("universidad")), s(row.get("pais")), s(row.get("ciudad"))]
        for e in (row.get("estudiantes") or []):
            textos.append(s(e.get("estudiante")))
        L = max((len(t.strip()) for t in textos if t), default=12)
        px = int(7.2 * L + 48)
        return max(240, min(px, 640))

    def _estimate_popup_height_px(n_items):
        MIN_H, PER_ITEM = 150, 44
        h = MIN_H + PER_ITEM * max(0, n_items - 1)
        return min(h, 520)

    # 2) Pintar TODOS los programas presentes en dfs
    for program, df in dfs.items():
        if df is None or df.empty:
            continue

        color = PROGRAM_COLORS.get(program, "blue")
        rows_iter = df.to_dict(orient="records")

        for row_index, row in enumerate(rows_iter):
            lat, lon = row.get("latitud"), row.get("longitud")
            if pd.isna(lat) or pd.isna(lon):
                continue

            # SOLO PARA ERASMUS IN: enganchar materias IN a cada estudiante
            if program == "Erasmus IN":
                ests = row.get("estudiantes") or []
                if isinstance(ests, list):
                    for e in ests:
                        nombre = str(e.get("estudiante", "")).strip()
                        e["materias_in"] = materias_in_por_estudiante.get(nombre, [])

                # A partir de aquí todo como lo tienes
                content = generate_dynamic_popup(row, program, row_index)
                n = max(1, len(row.get("estudiantes", [])) if isinstance(row.get("estudiantes"), list) else 1)
                w = _estimate_popup_width_px(row)
                h = _estimate_popup_height_px(n)

                html_doc = f"""<!doctype html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        html, body {{
        margin:0; padding:0; background:transparent; width:100%; height:100%;
        }}
        .al-wrap {{
        width:100%; height:100%; box-sizing:border-box; padding:8px;
        background:transparent; overflow-x:hidden; overflow-y:auto;
        -webkit-overflow-scrolling: touch;
        }}
        .al-popup {{ width:100% !important; max-width:100% !important; min-width:100% !important; }}
    </style>
    </head>
    <body>
    <div class="al-wrap">{content}</div>
    </body>
    </html>"""

                popup = folium.Popup(content, max_width=480)

                folium.Marker(
                    location=[lat, lon],
                    popup=popup,
                    tooltip=f"{row.get('universidad','')} ({row.get('pais','') or row.get('ciudad','')}) · {n} alumno(s)",
                    icon=folium.Icon(color=color, icon="globe", prefix="fa"),
                ).add_to(m)

            #  Fin de asignaturas IN

            content = generate_dynamic_popup(row, program, row_index)
            n = max(1, len(row.get("estudiantes", [])) if isinstance(row.get("estudiantes"), list) else 1)
            w = _estimate_popup_width_px(row)
            h = _estimate_popup_height_px(n)

            html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      margin:0; padding:0; background:transparent; width:100%; height:100%;
    }}
    .al-wrap {{
      width:100%; height:100%; box-sizing:border-box; padding:8px;
      background:transparent; overflow-x:hidden; overflow-y:auto;
      -webkit-overflow-scrolling: touch;
    }}
    .al-popup {{ width:100% !important; max-width:100% !important; min-width:100% !important; }}
  </style>
</head>
<body>
  <div class="al-wrap">{content}</div>
</body>
</html>"""

            # iframe = folium.IFrame(html=html_doc, width=w, height=h)
            # popup  = folium.Popup(iframe, max_width=w)
            popup = folium.Popup(content, max_width=480) 

            folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=f"{row.get('universidad','')} ({row.get('pais','') or row.get('ciudad','')}) · {n} alumno(s)",
                icon=folium.Icon(color=color, icon="globe", prefix="fa"),
            ).add_to(m)

    # 3) Render en Streamlit
    html_map = m.get_root().render()
    st.components.v1.html(html_map, height=750, scrolling=True)
