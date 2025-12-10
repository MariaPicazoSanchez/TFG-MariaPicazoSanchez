import folium
import pandas as pd
import streamlit as st
import leafmap.foliumap as leafmap
from popup_templates import generate_dynamic_popup
from domain import PROGRAM_COLORS, PROGRAM_ICONS

from map_export import add_export_control



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
        m = leafmap.Map(center=(40.4168, -3.7038), zoom=4, tiles=None, draw_control=False,
            measure_control=False,
            search_control=True
        )
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
                function refreshMateriasView() {
                    var blocks = document.querySelectorAll(".materias-block");
                    for (var b = 0; b < blocks.length; b++) {
                        var block = blocks[b];

                        // Leemos las materias actuales de la parte editable
                        var materias = getMateriasFromDOM(block);

                        // Buscamos el <details class="mat"> de la vista
                        var pcontent   = block.closest(".pcontent");
                        if (!pcontent) continue;

                        var matDetails = pcontent.querySelector(".view-block .extras details.mat");
                        if (!matDetails) continue;

                        var summary = matDetails.querySelector("summary");
                        var ul      = matDetails.querySelector("ul.mlist");
                        if (!summary || !ul) continue;

                        // Actualizar contador y lista
                        summary.textContent = "📚 Materias (" + materias.length + ")";

                        while (ul.firstChild) {
                        ul.removeChild(ul.firstChild);
                        }

                        for (var i = 0; i < materias.length; i++) {
                        var m = materias[i];
                        var trozos = [];
                        var nombre = m.nombre || "Sin nombre";
                        trozos.push(nombre);
                        if (m.cuat) {
                            trozos.push("Cuatri: " + m.cuat);
                        }
                        trozos.push(m.firmado ? "Firmado" : "No firmado");
                        var displayTxt = trozos.join(" · ");

                        var li = document.createElement("li");
                        li.className = "mitem";
                        li.textContent = displayTxt;
                        ul.appendChild(li);
                        }
                    }
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
                
                function closeAllEditModes() {
                    var toggles = document.querySelectorAll(".edit-toggle");
                    for (var i = 0; i < toggles.length; i++) {
                        toggles[i].checked = false;  // vuelve a la vista "normal"
                    }
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
                // Muestra un popup de estado (ok, mensajes)
                function showStatusPopup(ok, messages) {
                    var popup = document.getElementById("save-status-popup");
                    if (!popup) {
                        popup = document.createElement("div");
                        popup.id = "save-status-popup";
                        popup.style.position = "fixed";
                        popup.style.top = "50%";
                        popup.style.left = "50%";
                        popup.style.transform = "translate(-50%, -50%)";
                        popup.style.zIndex = "999999";
                        popup.style.maxWidth = "420px";
                        popup.style.width = "90%";
                        popup.style.background = "#1f1f1f";
                        popup.style.color = "#fff";
                        popup.style.padding = "16px 20px";
                        popup.style.borderRadius = "12px";
                        popup.style.boxShadow = "0 8px 24px rgba(0,0,0,0.45)";
                        popup.style.fontFamily = "Segoe UI, Arial, sans-serif";
                        popup.style.fontSize = "14px";

                        popup.innerHTML =
                        '<div id="save-status-title" style="font-weight:600;margin-bottom:8px;"></div>' +
                        '<ul id="save-status-list" style="margin:0 0 8px 18px;padding:0;"></ul>' +
                        '<div style="text-align:right;margin-top:4px;">' +
                            '<button id="save-status-close" type="button" ' +
                            'style="padding:4px 10px;border-radius:8px;border:none;cursor:pointer;">' +
                            'Cerrar' +
                            '</button>' +
                        '</div>';

                        document.body.appendChild(popup);

                        var btn = document.getElementById("save-status-close");
                        btn.onclick = function () {
                        popup.style.display = "none";
                        };
                    }

                    var titleEl = document.getElementById("save-status-title");
                    var listEl  = document.getElementById("save-status-list");

                    titleEl.textContent = ok ? "Cambios guardados" : "Se ha producido un problema";
                    popup.style.borderLeft = ok ? "4px solid #4caf50" : "4px solid #f44336";

                    while (listEl.firstChild) {
                        listEl.removeChild(listEl.firstChild);
                    }

                    if (messages && messages.length) {
                        for (var i = 0; i < messages.length; i++) {
                        var li = document.createElement("li");
                        li.textContent = messages[i];
                        listEl.appendChild(li);
                        }
                    }

                    popup.style.display = "block";

                    if (ok) {
                        setTimeout(function () {
                        popup.style.display = "none";
                        }, 3000);
                    }
                    }

                    // DEBUG + listener de mensajes del iframe
                    window.addEventListener("message", function (event) {
                    console.log("[MateriasJS] message recibido:", event.data);
                    var data = event.data;

                    // Puede venir como string o como objeto
                    if (typeof data === "string") {
                        try {
                        data = JSON.parse(data);
                        } catch (e) {
                        console.log("[MateriasJS] no es JSON, se ignora");
                        return;
                        }
                    }

                    if (!data || data.type !== "saveStatus") return;

                    var msgs = data.messages || [];
                    showStatusPopup(!!data.ok, msgs);
                    });

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

            console.log("[Mapa] saveStatus recibido:", data);

            // Solo actuamos si todo ha ido bien
            if (!data.ok) return;

            // Desmarcar todos los checkboxes de edición
            var toggles = document.querySelectorAll(".edit-toggle");
            if (!toggles || !toggles.length) {
            console.log("[Mapa] No se han encontrado .edit-toggle");
            return;
            }

            toggles.forEach(function(ch) {
            ch.checked = false;
            });
        });
        })();
        </script>
        """))

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

            content = generate_dynamic_popup(row, program, row_index)
            n = max(1, len(row.get("estudiantes", [])) if isinstance(row.get("estudiantes"), list) else 1)

            popup = folium.Popup(content, max_width=480)
            marker_icon = PROGRAM_ICONS.get(program, "map-marker")

            icon = folium.Icon(
                color=color,
                icon_color='black',
                icon=marker_icon,
                prefix="fa",
            )

            folium.Marker(
                location=[lat, lon],
                popup=popup,
                tooltip=f"{row.get('universidad','')} ({row.get('pais','') or row.get('ciudad','')}) · {n} alumno(s)",
                icon=icon,
            ).add_to(m)


    add_export_control(m)

    # 3) Render en Streamlit
    html_map = m.get_root().render()

    # Guardamos el HTML completo del mapa para poder descargarlo luego
    st.session_state["last_map_html"] = html_map

    st.components.v1.html(html_map, height=750, scrolling=True)