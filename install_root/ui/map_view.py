import logging
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from constants import PROGRAM_ERASMUS_IN, PROGRAM_ERASMUS_OUT, PROGRAM_SICUE_OUT
from domain import PROGRAM_COLORS, PROGRAM_ICONS
from ui.new_user_view import get_university_responsable_map
from export import add_export_control, add_program_legend
from .popup_templates import generate_dynamic_popup,get_autofill_script

logger = logging.getLogger("movilidad_ui")


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

def group_rows_by_location(df, decimals=2):
    """
    Devuelve una lista de dicts con:
      {universidad, pais, latitud, longitud, estudiantes:[...]}
    - Si df YA trae una columna 'estudiantes' con listas, la respeta (no reagrupa).
    - Si df viene “en bruto”, agrupa por ubicación y construye la lista.
    """
    df = df.copy()
    
    # Caso 1: df ya está agrupado (columna 'estudiantes' con listas de dicts)
    # En este caso, solo hay que convertir a lista de dicts
    if "estudiantes" in df.columns and df["estudiantes"].apply(lambda v: isinstance(v, (list, tuple))).all():
        out = []
        for _, r in df.iterrows():
            if pd.isna(r.get("latitud")) or pd.isna(r.get("longitud")):
                continue
            ests = r.get("estudiantes") or []
            out.append({
                "universidad": r.get("universidad", ""),
                "pais": r.get("pais", ""),
                "latitud": float(r["latitud"]),
                "longitud": float(r["longitud"]),
                "estudiantes": list(ests) or []
            })
        return out

    # Caso 2: df viene "en bruto" (filas individuales de estudiantes)
    # Necesitamos agrupar por ubicación
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
        estudiantes = []
        for est in g[student_cols].to_dict("records"):
            nombre = str(est.get("estudiante", "")).strip().lower()
            if nombre in ("", "nan", "0") or est.get("estudiante") is None:
                continue
            estudiantes.append(est)
        if not estudiantes:
            continue
        grouped.append({"universidad": u, "pais": p, "latitud": lat, "longitud": lon, "estudiantes": estudiantes})
    return grouped

def render_map(m: folium.Map) -> None:
    """Renderiza el mapa en Streamlit forzando un recálculo de tamaño."""
    map_id = m.get_name()

    # Fuerza a Leaflet a recalcular tamaño y repintar tiles
    m.get_root().html.add_child(folium.Element(f"""
    <script>
      setTimeout(function() {{
        try {{
          var map = {map_id};
          if (map) {{
            map.invalidateSize(true);
          }}
        }} catch(e) {{}}
      }}, 350);
    </script>
    """))

    st_folium(m, height=900, use_container_width=True, key="main_map")

def show_map(
    dfs: dict,
    base_map,
    materias_in_por_estudiante: dict | None = None,
    filtros_activos=None,
    only_no_la: bool = False,
    auto_zoom_bounds=None,
) -> None:
    """
    Muestra TODOS los programas disponibles en `dfs` sin filtrar.

    Args:
        dfs: dict con posibles claves "Erasmus OUT", "Erasmus IN", "SICUE OUT" -> DataFrames agrupados
        base_map: mapa folium base o cualquier objeto con ``add_child``
        materias_in_por_estudiante: dict nombre_alumno -> lista de materias
        filtros_activos: filtros aplicados (se reenvían a la leyenda)
        only_no_la: si True, filtra sólo alumnos sin Learning Agreement
        auto_zoom_bounds: tuple ((min_lat, min_lon), (max_lat, max_lon)) para auto-zoom
    """
    if materias_in_por_estudiante is None:
        materias_in_por_estudiante = {}

    # Selector de tipo de mapa base
    selected_tile = "CartoDB Voyager"

    # 1) Mapa base
    if hasattr(base_map, "add_child"):
        m = base_map
    else:
        try:
            m = folium.Map(location=(40.4168, -3.7038), zoom_start=4, tiles=selected_tile)
        except Exception:
            m = folium.Map(location=(40.4168, -3.7038), zoom_start=4, tiles="OpenStreetMap")

    # Quitar padding del popup de Leaflet (global) y estilizar el botón ×
    m.get_root().html.add_child(folium.Element("""
    <style>
      .leaflet-popup-content { margin:0 !important; overflow-x:hidden !important; }
      .leaflet-popup-content-wrapper {
        padding:0 !important;
        overflow:hidden !important;
        width:460px !important;
        min-width:460px !important;
        box-sizing:border-box !important;
      }
      .leaflet-popup-close-button:hover {
        color:#dc2626 !important;
      }
    </style>
    """))


    m.get_root().html.add_child(folium.Element("""
        <script>
        (function() {
        // evitar registrar el listener varias veces
        if (window.__erasmusSaveStatusInit) return;
        window.__erasmusSaveStatusInit = true;

        window.addEventListener("message", function(event) {
            var data = event.data || {};

            // Por si viene como string JSON
            if (typeof data === "string") {
            try {
                data = JSON.parse(data);
            } catch (e) {
                console.log("[Mapa] Mensaje no JSON, se ignora");
                return;
            }
            }

            if (!data || data.type !== "saveStatus") return;


            // Solo actuamos si todo ha ido bien
            if (!data.ok) return;

            // Desmarcar todos los checkboxes de edición
            var toggles = document.querySelectorAll(".edit-toggle");
            if (toggles && toggles.length) {
                toggles.forEach(function(ch) { ch.checked = false; });
            }
            // La recarga la gestiona el toast de materias_editor.js al hacer clic
        });
        })();
        </script>
        """))
    # Autocompletado universidad → país/ciudad en popups de edición
    m.get_root().html.add_child(folium.Element(
        get_autofill_script(st.session_state.get("config", {}))
    ))

    # Cargar mapa {universidad → responsable} por programa
    _config = st.session_state.get("config", {})
    _resp_maps = {
        prog: get_university_responsable_map(_config.get(prog, ""))
        for prog in (PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT)
    }

    # 2) Pintar TODOS los programas presentes en dfs
    for program, df in dfs.items():
        if df is None or df.empty:
            continue

        color    = PROGRAM_COLORS.get(program, "blue")
        resp_map = _resp_maps.get(program, {})
        
        # Convertir df a lista de dicts agrupados
        # El df ya viene agrupado de load_erasmus_out con columna 'estudiantes' como lista
        if "estudiantes" in df.columns and df["estudiantes"].apply(lambda v: isinstance(v, (list, tuple))).all():
            grouped = []
            for _, row in df.iterrows():
                if pd.isna(row.get("latitud")) or pd.isna(row.get("longitud")):
                    continue
                grouped.append({
                    "universidad": row.get("universidad", ""),
                    "pais": row.get("pais", ""),
                    "ciudad": row.get("ciudad", ""),
                    "latitud": float(row["latitud"]),
                    "longitud": float(row["longitud"]),
                    "estudiantes": list(row.get("estudiantes", [])) or []
                })
        else:
            # Fallback si no viene agrupado (ej. datos custom)
            grouped = group_rows_by_location(df, decimals=1)

        for row_index, row in enumerate(grouped):
            lat, lon = row.get("latitud"), row.get("longitud")
            if pd.isna(lat) or pd.isna(lon):
                continue

            # Skip group if all students are nan/null/0/NA
            ests = row.get("estudiantes") or []
            filtered_ests = []
            for e in ests:
                nombre = str(e.get("estudiante", "")).strip().lower()
                val = e.get("estudiante")
                # Check for pandas NA
                try:
                    is_na = pd.isna(val)
                except Exception:
                    is_na = False
                if is_na or nombre in ("", "nan", "0") or val is None:
                    continue
                filtered_ests.append(e)
            if not filtered_ests:
                continue
            row["estudiantes"] = filtered_ests

            # SOLO PARA ERASMUS IN: enganchar materias IN a cada estudiante dentro del grupo
            if program == PROGRAM_ERASMUS_IN:
                for e in filtered_ests:
                    nombre = str(e.get("estudiante", "")).strip()
                    materias_list = materias_in_por_estudiante.get(nombre, [])
                    e["materias_in"] = materias_list
                    # Guardar la hoja origen para que el guardado vaya a la hoja correcta
                    e["materias_sheet_name"] = materias_list[0].get("sheet_name", "") if materias_list else ""

            # Pass only filtered students to popup
            row_for_popup = row.copy()
            row_for_popup["estudiantes"] = filtered_ests
            content = generate_dynamic_popup(row_for_popup, program, row_index)
            n = max(1, len(filtered_ests))

            popup = folium.Popup(content, max_width=460)
            marker_icon = PROGRAM_ICONS.get(program, "map-marker")
            angle = 0
            if program == PROGRAM_ERASMUS_IN:
                angle = 180

            icon = folium.Icon(
                color=color,
                icon_color='black',
                icon=marker_icon,
                prefix="fa",
                angle=angle
            )

            # Tooltip HTML: universidad + responsable + nº alumnos
            uni_name  = row.get("universidad", "")
            resp_val  = resp_map.get(uni_name.strip(), "")
            resp_line = (
                f"<div style='color:#6b7280;font-size:11px;margin-top:2px;'>👤 {resp_val}</div>"
                if resp_val else ""
            )
            n_label = f"{n} alumno{'s' if n != 1 else ''}"
            tooltip = folium.Tooltip(
                f"<div style='font-family:sans-serif;padding:2px 4px;'>"
                f"<div style='font-weight:700;font-size:13px;'>{uni_name}</div>"
                f"{resp_line}"
                f"<div style='color:#2563eb;font-size:11px;font-weight:600;margin-top:3px;'>"
                f"({n_label})</div>"
                f"</div>"
            )

            folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=tooltip,
                icon=icon,
            ).add_to(m)


    # Pasar el número de alumnos por tipo a la leyenda
    add_program_legend(m, filtros_activos, only_no_la, student_list=dfs)

    add_export_control(m)

    # Aplicar auto-zoom si se proporciona bounds
    if auto_zoom_bounds:
        try:
            m.fit_bounds(auto_zoom_bounds)
        except Exception:
            pass

    # 3) Render en Streamlit
    html_map = m.get_root().render()

    # Incrustar materias_editor.js dentro del iframe del mapa (más robusto que src externo)
    try:
        js_path = Path(__file__).resolve().parents[1] / "static" / "materias_editor.js"
        # Ajusta parents[...] si tu estructura es distinta
        if js_path.exists():
            js_code = js_path.read_text(encoding="utf-8")
            inline_tag = f"<script>\n{js_code}\n</script>"
            if "</body>" in html_map:
                html_map = html_map.replace("</body>", inline_tag + "</body>")
            else:
                html_map += inline_tag
        else:
            logger.warning("No se encontró JS de materias en: %s", js_path)
    except Exception as e:
        logger.warning("Error inyectando materias_editor.js inline: %s", e)

    # Inyectar script de reinicio de Leaflet con reintentos para pywebview
    _reinit_script = """
<script>
(function() {
    function _invalidateAll() {
        try {
            Object.keys(window).forEach(function(k) {
                try {
                    var obj = window[k];
                    if (obj && obj._leaflet_id && typeof obj.invalidateSize === 'function') {
                        obj.invalidateSize(true);
                    }
                } catch(e) {}
            });
        } catch(e) {}
    }
    // Reintentos: 300ms, 700ms, 1500ms, 3000ms
    [300, 700, 1500, 3000].forEach(function(t) {
        setTimeout(_invalidateAll, t);
    });
})();
</script>"""
    if "</body>" in html_map:
        html_map = html_map.replace("</body>", _reinit_script + "</body>")
    else:
        html_map += _reinit_script

    # Guardamos el HTML completo del mapa para poder descargarlo luego
    st.session_state["last_map_html"] = html_map

    st.components.v1.html(html_map, height=1080, scrolling=True)