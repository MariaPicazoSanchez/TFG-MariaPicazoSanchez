import folium
import json

def count_students_by_type(dfs, active_names):
    """
    Cuenta alumnos por tipo de movilidad a partir del dict de DataFrames `dfs`.

    dfs: dict[str, DataFrame]  (lo que se usa para pintar el mapa)
    active_names: lista de tipos de movilidad a mostrar en la leyenda.

    Para cada tipo:
      - Si la columna 'estudiantes' existe y contiene listas de dicts, se cuenta
        el número total de dicts (estudiantes reales).
      - En caso contrario, se usa simplemente len(df) como aproximación.
    """
    if not active_names or not isinstance(dfs, dict):
        return {}

    counts = {name: 0 for name in active_names}

    for name in active_names:
        df = dfs.get(name)
        if df is None:
            continue

        # Si el DataFrame está vacío, dejamos el 0
        try:
            if hasattr(df, "empty") and df.empty:
                continue
        except Exception:
            pass

        total = 0

        try:
            # Caso 1: columna 'estudiantes' con listas de dicts
            if hasattr(df, "columns") and "estudiantes" in list(df.columns):
                serie = df["estudiantes"]
                for valor in serie:
                    if isinstance(valor, list):
                        for e in valor:
                            if isinstance(e, dict):
                                total += 1

                # Si no hemos contado nada pero hay filas, usamos len(df)
                if total == 0:
                    try:
                        total = len(df)
                    except TypeError:
                        total = 0
            else:
                # Caso 2: no hay columna 'estudiantes' → usamos len(df)
                try:
                    total = len(df)
                except TypeError:
                    total = 0
        except Exception:
            total = 0

        counts[name] = int(total)

    return counts


def add_program_legend(
    m: folium.Map,
    active_programs,
    only_erasmus_out_no_LA: bool,
    student_list=None,
):
    """
    Inserta en el mapa una leyenda con los tipos de movilidad y, opcionalmente,
    el número de alumnos por tipo.

    active_programs:
        - puede ser un dict: {"Erasmus IN": True, "SICUE OUT": False, ...}
        - o una lista: ["Erasmus IN", "SICUE OUT", ...]
    only_erasmus_out_no_LA:
        - si es True, la leyenda muestra solo "Erasmus OUT".
    student_list:
        - normalmente es el dict `dfs` ya filtrado que se usa para pintar el mapa.
          Si se pasa y es un dict, se usa count_students_by_type(...) para obtener
          un dict {tipo: total}.
    """

    # --- 1. Normalizar a lista de nombres activos ---

    if only_erasmus_out_no_LA:
        active_names = ["Erasmus OUT"]
    else:
        if isinstance(active_programs, dict):
            active_names = [name for name, is_on in active_programs.items() if is_on]
        elif isinstance(active_programs, (list, tuple, set)):
            active_names = list(active_programs)
        else:
            active_names = []
    from domain import PROGRAM_COLORS
    # Fallback: si no hay nada activo, usamos todos los programas definidos
    if not active_names:
        active_names = list(PROGRAM_COLORS.keys())

    # --- 2. Calcular conteos, si tenemos dfs ---
    alumnos_por_tipo = None
    if isinstance(student_list, dict):
        alumnos_por_tipo = count_students_by_type(student_list, active_names)

    # --- 3. Construir las filas HTML de la leyenda ---
    legend_rows = ""
    for name in active_names:
        color = PROGRAM_COLORS.get(name, "#888")  # por si acaso
        n_alumnos = 0
        if alumnos_por_tipo and name in alumnos_por_tipo:
            n_alumnos = alumnos_por_tipo[name]
        legend_rows += f"""
        <div class=\"map-legend-row\">
            <span class=\"map-legend-color\" style=\"background-color: {color};\"></span>
            <span>{name} ( {n_alumnos} )</span>
        </div>
        """

    # HTML interior de la leyenda (solo el contenido, sin <style> ni <script>)
    legend_inner_html = f"""
    <div class=\"map-legend\">
        <div class=\"map-legend-title\">Tipos de movilidad</div>
        {legend_rows}
    </div>
    """.strip()

    # Lo convertimos a string JS seguro usando JSON (escapa comillas, saltos de línea, etc.)
    legend_inner_html_js = json.dumps(legend_inner_html)

    # --- 4. CSS + definición de window.__PROGRAM_LEGEND_HTML__ ---
    legend_html = (
        '<style>'
        '.map-legend {'
        '    position: absolute;'
        '    bottom: 18px;'
        '    right: 18px;'
        '    z-index: 9999;'
        '    background: rgba(255, 255, 255, 0.85); /* fondo blanco semitransparente */'
        '    padding: 10px 14px;'
        '    border-radius: 8px;'
        '    /* box-shadow eliminado para evitar sombra sin leyenda */'
        '    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;'
        '    font-size: 12px;'
        '    color: #222;'
        '}'
        '.map-legend-title {'
        '    margin: 0 0 6px 0;'
        '    font-size: 13px;'
        '    font-weight: 600;'
        '}'
        '.map-legend-row {'
        '    display: flex;'
        '    align-items: center;'
        '    gap: 6px;'
        '    margin-bottom: 4px;'
        '}'
        '.map-legend-row:last-child {'
        '    margin-bottom: 0;'
        '}'
        '.map-legend-color {'
        '    width: 14px;'
        '    height: 14px;'
        '    border-radius: 3px;'
        '    border: 1px solid rgba(0,0,0,0.4);'
        '    opacity: 0.75;   /* colores más suaves que el original del mapa */'
        '}'
        '</style>'
        f"""
        <script>
        (function () {{
            // HTML completo de la leyenda que usará html2canvas en el clon
            window.__PROGRAM_LEGEND_HTML__ = {legend_inner_html_js};
        }})();
        </script>
        """
    )

    m.get_root().html.add_child(folium.Element(legend_html))



def add_export_control(m: folium.Map):
    html = """
    <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>

    <script>
    (function () {
        function downloadBlob(blob, filename) {
            var url = URL.createObjectURL(blob);
            var a = document.createElement("a");
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        }

        function getMapContainer() {
            var mapContainer = document.querySelector(".leaflet-container");
            if (!mapContainer) {
                alert("No se ha encontrado el contenedor del mapa.");
                return null;
            }
            return mapContainer;
        }

        function captureCanvas(callback) {
            var mapContainer = getMapContainer();
            if (!mapContainer) return;

            html2canvas(mapContainer, {
                useCORS: true,
                logging: false,
                ignoreElements: function(element) {
                    return element.closest && element.closest(".leaflet-control-container") !== null;
                },
                onclone: function(clonedDoc) {
                    try {
                        if (!window.__PROGRAM_LEGEND_HTML__) {
                            return;
                        }
                        var clonedMapContainer = clonedDoc.querySelector(".leaflet-container");
                        if (!clonedMapContainer) return;

                        var wrapper = clonedDoc.createElement("div");
                        wrapper.innerHTML = window.__PROGRAM_LEGEND_HTML__.trim();
                        var legend = wrapper.firstElementChild;
                        if (legend) {
                            clonedMapContainer.appendChild(legend);
                        }
                        // --- overlay extra (tabla, etc.) ---
                        try {
                            if (window.__EXPORT_OVERLAY_HTML__) {
                                var wrapper2 = clonedDoc.createElement("div");
                                wrapper2.innerHTML = window.__EXPORT_OVERLAY_HTML__.trim();
                                var overlay = wrapper2.firstElementChild;
                                if (overlay) {
                                    clonedMapContainer.appendChild(overlay);
                                }
                            }
                        } catch (e) {
                            console.warn("[MapExport] No se pudo añadir overlay al clon:", e);
                        }
                    } catch (e) {
                        console.warn("[MapExport] No se pudo añadir la leyenda al clon:", e);
                    }
                }
            }).then(function (canvas) {
                callback(canvas);
            }).catch(function (err) {
                console.error("Error capturando el mapa:", err);
                alert("Error capturando el mapa. Mira la consola para más detalles.");
            });
        }

        function exportMapAsPNG() {
            try {
                captureCanvas(function (canvas) {
                    canvas.toBlob(function (blob) {
                        if (!blob) {
                            alert("No se pudo generar la imagen del mapa (PNG).");
                            return;
                        }
                        downloadBlob(blob, "mapa_movilidad.png");
                    });
                });
            } catch (err) {
                console.error("Error exportando el mapa (PNG):", err);
                alert("Error exportando el mapa (PNG). Mira la consola para más detalles.");
            }
        }

        function exportMapAsSVG() {
            try {
                captureCanvas(function (canvas) {
                    var pngDataUrl = canvas.toDataURL("image/png");
                    var width = canvas.width;
                    var height = canvas.height;

                    var svgContent =
                        '<?xml version="1.0" encoding="UTF-8"?>\\n' +
                        '<svg xmlns="http://www.w3.org/2000/svg" ' +
                        'width="' + width + '" height="' + height + '" ' +
                        'viewBox="0 0 ' + width + ' ' + height + '">' +
                        '<image href="' + pngDataUrl + '" ' +
                        'width="' + width + '" height="' + height + '"/>' +
                        '</svg>';

                    var blob = new Blob([svgContent], {type: "image/svg+xml;charset=utf-8"});
                    downloadBlob(blob, "mapa_movilidad.svg");
                });
            } catch (err) {
                console.error("Error exportando el mapa (SVG):", err);
                alert("Error exportando el mapa (SVG). Mira la consola para más detalles.");
            }
        }

        function addExportButtons() {
            var mapVarName = Object.keys(window).find(function (k) {
                return k.startsWith("map_");
            });
            if (!mapVarName) {
                console.warn("[MapExport] No se encontró la variable global del mapa.");
                return;
            }
            var map = window[mapVarName];

            var PngControl = L.Control.extend({
                options: { position: "topleft" },
                onAdd: function (map) {
                    var container = L.DomUtil.create("div", "leaflet-bar leaflet-control");
                    var link = L.DomUtil.create("a", "", container);
                    link.href = "#";
                    link.title = "Exportar mapa como PNG";
                    link.innerHTML = "PNG";

                    L.DomEvent.on(link, "click", L.DomEvent.stop)
                              .on(link, "click", function (e) {
                                  exportMapAsPNG();
                              });

                    return container;
                }
            });

            var SvgControl = L.Control.extend({
                options: { position: "topleft" },
                onAdd: function (map) {
                    var container = L.DomUtil.create("div", "leaflet-bar leaflet-control");
                    var link = L.DomUtil.create("a", "", container);
                    link.href = "#";
                    link.title = "Exportar mapa como SVG";
                    link.innerHTML = "SVG";

                    L.DomEvent.on(link, "click", L.DomEvent.stop)
                              .on(link, "click", function (e) {
                                  exportMapAsSVG();
                              });

                    return container;
                }
            });

            map.addControl(new PngControl());
            map.addControl(new SvgControl());

        }

        function initWhenReady() {
            if (typeof L === "undefined") {
                console.warn("[MapExport] Leaflet aún no está disponible");
                return;
            }
            addExportButtons();
        }

        if (document.readyState === "complete") {
            initWhenReady();
        } else {
            window.addEventListener("load", initWhenReady);
        }
    })();
    </script>
    """

    m.get_root().html.add_child(folium.Element(html))
