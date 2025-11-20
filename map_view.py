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

    js_materias = """
            <script>
            if (!window.__materiasJSInit) {
            window.__materiasJSInit = true;

            (function () {
                console.log("[MateriasJS] init");

                function escapeHtml(str) {
                str = String(str || "");
                return str
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#39;");
                }

                // Lee las materias actuales desde el DOM (data-*)
                function getMateriasFromDOM(block) {
                var rows = block.querySelectorAll(".materia-row:not(.add-row)");
                var result = [];
                for (var i = 0; i < rows.length; i++) {
                    var row = rows[i];
                    var nombre = (row.getAttribute("data-nombre") || "");
                    if (!nombre && row.querySelector(".materia-name")) {
                    nombre = row.querySelector(".materia-name").textContent || "";
                    }
                    var cuat = (row.getAttribute("data-cuat") || "");
                    var firmado = (row.getAttribute("data-firmado") || "").toUpperCase() === "X";

                    row.setAttribute("data-mindex", String(i));
                    result.push({
                    nombre: nombre.trim(),
                    cuat: cuat.trim(),
                    firmado: firmado
                    });
                }
                return result;
                }

                // Convierte array -> texto del textarea ("Nombre | cuat | x")
                function stringifyMaterias(mats) {
                var lines = [];
                if (!mats) return "";
                for (var i = 0; i < mats.length; i++) {
                    var m = mats[i];
                    var nombre = (m.nombre || "").trim();
                    var cuat = (m.cuat || "").trim();
                    var firmadoFlag = m.firmado ? "x" : "";
                    var line = nombre + " | " + cuat + " | " + firmadoFlag;
                    line = line.replace(/\\s+\\|/g, " |").replace(/\\|\\s+/g, "| ");
                    lines.push(line.trim());
                }
                return lines.join("\\n");
                }

                // Pinta la lista a partir del array y actualiza data-*
                function renderMateriasList(block, materias) {
                var list = block.querySelector(".materias-list");
                if (!list) return;

                var addRow = list.querySelector(".add-row");
                var olds = list.querySelectorAll(".materia-row:not(.add-row)");
                for (var i = 0; i < olds.length; i++) {
                    list.removeChild(olds[i]);
                }

                for (var j = 0; j < materias.length; j++) {
                    var m = materias[j];
                    var li = document.createElement("li");
                    li.className = "materia-row";
                    li.setAttribute("data-mindex", String(j));
                    li.setAttribute("data-nombre", m.nombre || "");
                    li.setAttribute("data-cuat", m.cuat || "");
                    li.setAttribute("data-firmado", m.firmado ? "x" : "");

                    var trozos = [];
                    var nombre = m.nombre || "Sin nombre";
                    trozos.push(nombre);
                    if (m.cuat) {
                    trozos.push("Cuatri: " + m.cuat);
                    }
                    trozos.push(m.firmado ? "Firmado" : "No firmado");
                    var displayTxt = trozos.join(" · ");

                    li.innerHTML =
                    '<span class="materia-name">' + escapeHtml(displayTxt) + '</span>' +
                    '<span class="materia-actions">' +
                        '<button type="button" class="icon-btn materia-edit" title="Editar">✏️</button>' +
                        '<button type="button" class="icon-btn materia-delete" title="Eliminar">🗑️</button>' +
                    '</span>';

                    list.insertBefore(li, addRow);
                }
                }

                function openEditor(block, idx, materias) {
                var editor = block.querySelector(".materia-editor");
                var list = block.querySelector(".materias-list");
                if (!editor || !list) return;

                var nombreInput = editor.querySelector('input[name="mat_nombre"]');
                var cuatSelect = editor.querySelector('select[name="mat_cuat"]');
                var firmadoCheck = editor.querySelector('input[name="mat_firmado"]');

                var mat;
                if (idx >= 0 && idx < materias.length) {
                    mat = materias[idx];
                } else {
                    mat = { nombre: "", cuat: "", firmado: false };
                }

                nombreInput.value = mat.nombre || "";
                cuatSelect.value = mat.cuat || "";
                firmadoCheck.checked = !!mat.firmado;

                editor.setAttribute("data-edit-index", String(idx));

                editor.style.display = "";
                list.style.display = "none";
                }

                function closeEditor(block) {
                var editor = block.querySelector(".materia-editor");
                var list = block.querySelector(".materias-list");
                if (!editor || !list) return;
                editor.style.display = "none";
                list.style.display = "";
                }

                document.addEventListener("click", function (ev) {
                var target = ev.target || ev.srcElement;

                var editBtn   = target.closest ? target.closest(".materia-edit")   : null;
                var delBtn    = target.closest ? target.closest(".materia-delete") : null;
                var addBtn    = target.closest ? target.closest(".materia-add")    : null;
                var saveBtn   = target.closest ? target.closest(".materia-save")   : null;
                var cancelBtn = target.closest ? target.closest(".materia-cancel") : null;

                if (!editBtn && !delBtn && !addBtn && !saveBtn && !cancelBtn) return;

                var block = target.closest ? target.closest(".materias-block") : null;
                if (!block) return;

                var textarea = block.querySelector('textarea[name="materias_raw"]');
                var editor = block.querySelector(".materia-editor");
                if (!textarea || !editor) return;

                var materias = getMateriasFromDOM(block);

                // EDITAR
                if (editBtn) {
                    var rowE = editBtn.closest(".materia-row");
                    var idxE = parseInt(rowE.getAttribute("data-mindex") || "-1", 10);
                    console.log("[MateriasJS] editar", idxE);
                    openEditor(block, idxE, materias);
                    return;
                }

                // BORRAR
                if (delBtn) {
                    var rowD = delBtn.closest(".materia-row");
                    var idxD = parseInt(rowD.getAttribute("data-mindex") || "-1", 10);
                    console.log("[MateriasJS] borrar", idxD);
                    if (idxD >= 0 && idxD < materias.length) {
                    materias.splice(idxD, 1);
                    textarea.value = stringifyMaterias(materias);
                    renderMateriasList(block, materias);
                    }
                    return;
                }

                // AÑADIR
                if (addBtn) {
                    console.log("[MateriasJS] nueva materia");
                    openEditor(block, -1, materias);
                    return;
                }

                // GUARDAR
                if (saveBtn) {
                    var nombreInput2  = editor.querySelector('input[name="mat_nombre"]');
                    var cuatSelect2   = editor.querySelector('select[name="mat_cuat"]');
                    var firmadoCheck2 = editor.querySelector('input[name="mat_firmado"]');

                    var idxS = parseInt(editor.getAttribute("data-edit-index") || "-1", 10);
                    var nueva = {
                    nombre: (nombreInput2.value || "").trim(),
                    cuat:   (cuatSelect2.value || "").trim(),
                    firmado: !!firmadoCheck2.checked
                    };

                    if (!nueva.nombre) {
                    alert("La asignatura debe tener nombre.");
                    return;
                    }

                    if (idxS >= 0 && idxS < materias.length) {
                    materias[idxS] = nueva;
                    console.log("[MateriasJS] actualizada", idxS, nueva);
                    } else {
                    materias.push(nueva);
                    console.log("[MateriasJS] añadida", nueva);
                    }

                    textarea.value = stringifyMaterias(materias);
                    renderMateriasList(block, materias);
                    closeEditor(block);
                    return;
                }

                // CANCELAR
                if (cancelBtn) {
                    console.log("[MateriasJS] cancelar edición");
                    closeEditor(block);
                    return;
                }
                });
            })();
            }
            </script>
            """
    m.get_root().html.add_child(folium.Element(js_materias))




    # m.get_root().html.add_child(folium.Element("""
    # <style>
    # .leaflet-popup-content { margin:0 !important; }
    # .leaflet-popup-content-wrapper { padding:0 !important; }
    # </style>
    # """))

    # m.get_root().html.add_child(folium.Element(js_materias))


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
