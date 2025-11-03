import pandas as pd
import folium
import leafmap.foliumap as leafmap
import streamlit as st
from popup_templates import generate_dynamic_popup

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



def show_map(dfs, base_map):
    # 1) Mapa base
    if hasattr(base_map, "add_child"):
        m = base_map
    else:
        m = leafmap.Map(center=(40.4168, -3.7038), zoom=4, tiles=None)
        try:
            m.add_basemap(base_map if isinstance(base_map, str) else "CartoDB.Positron")
        except Exception:
            m.add_basemap("CartoDB.Positron")

    # === helpers locales para tamaño dinámico ===
    def _estimate_popup_width_px(row):
        def s(v): return str(v or "")
        textos = [s(row.get("universidad")), s(row.get("pais"))]
        for e in (row.get("estudiantes") or []):
            textos.append(s(e.get("estudiante")))
        L = max((len(t.strip()) for t in textos if t), default=12)
        px = int(7.2 * L + 48)  # ~7.2 px/char + padding
        return max(240, min(px, 640))

    def _estimate_popup_height_px(n_items):
        MIN_H, PER_ITEM = 150, 44   # cómodo para 1 alumno; crece suave
        h = MIN_H + PER_ITEM * max(0, n_items - 1)
        return min(h, 520)

    # 2) Capa Erasmus OUT
    if "Erasmus OUT" in dfs:
        df = dfs["Erasmus OUT"]
        locations = group_rows_by_location(df, decimals=5) 

        # Quita el padding/margen del wrapper de Leaflet
        m.get_root().html.add_child(folium.Element("""
        <style>
          .leaflet-popup-content { margin:0 !important; }
          .leaflet-popup-content-wrapper { padding:0 !important; }
        </style>
        """))

        for row in locations:
            content = generate_dynamic_popup(row) 
            n = max(1, len(row.get("estudiantes", [])))
            w = _estimate_popup_width_px(row)      # ancho total del globo
            h = _estimate_popup_height_px(n)       # alto del iframe

            html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      margin: 0; padding: 0; background: transparent;
      width: 100%; height: 100%;
    }}
    /* wrapper que aporta el "aire" y el SCROLL VERTICAL */
    .al-wrap {{
      width: 100%; height: 100%;
      box-sizing: border-box;
      padding: 8px;                 /* margen entre globo y tarjeta */
      background: transparent;
      overflow-x: hidden;
      overflow-y: auto;             /* scroll cuando se expanden detalles */
      -webkit-overflow-scrolling: touch;
    }}
    /* la tarjeta ocupa TODO el ancho del wrapper */
    .al-popup {{
      width: 100% !important;
      max-width: 100% !important;
      min-width: 100% !important;
      display: block;
      box-sizing: border-box;

      font-family: Segoe UI, Arial; font-size: 14px; line-height: 1.45;
      background: #fff; border-radius: 10px; padding: 12px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.15);

      overflow-x: hidden;
      overflow-y: visible;          /* el scroll lo lleva .al-wrap */
    }}
    .al-popup ul {{ list-style: none; padding: 0; margin: 0; }}
    .al-popup h4 {{ margin: 0 0 2px 0; color: #004AAD; }}
    .al-popup p  {{ margin: 2px 0 8px 0; color: #555; }}
    .al-popup .pitem {{ margin: 6px 0; }}
    .al-popup .pname {{
      cursor: pointer; color: #004AAD; font-weight: 600;
      white-space: normal; word-break: break-word;
    }}
    .al-popup .pdetails {{
      display: none; margin-top: 6px; background: #f6f8fa; padding: 6px; border-radius: 6px;
    }}
    .al-popup .pitem:hover .pdetails {{ display: block; }}
  </style>
</head>
<body>
  <div class="al-wrap">
    {content}
  </div>
</body>
</html>"""

            iframe = folium.IFrame(html=html_doc, width=w, height=h)
            popup  = folium.Popup(iframe, max_width=w)  # mismo ancho

            folium.Marker(
                location=[row["latitud"], row["longitud"]],
                popup=popup,
                tooltip=f"{row.get('universidad','')} ({row.get('pais','')}) · {n} alumno(s)",
                icon=folium.Icon(color="blue", icon="graduation-cap", prefix="fa")
            ).add_to(m)

    # 3) Render en Streamlit
    html_map = m.get_root().render()
    st.components.v1.html(html_map, height=750, scrolling=True)
