import folium


def add_export_control(m: folium.Map):
    """
    Añade 2 botones al mapa:
      - PNG: captura la vista actual del mapa y la descarga como PNG
      - SVG: captura la vista actual del mapa y la envuelve en un SVG (imagen incrustada)
    La captura se hace sin mostrar los controles de Leaflet (zoom, etc.).
    """

    html = """
    <!-- Librería para capturar el DOM a canvas -->
    <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>

    <script>
    (function () {
        console.log("[MapExport] init");

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

        // Captura el mapa con html2canvas ignorando los controles de Leaflet
        function captureCanvas(callback) {
            var mapContainer = getMapContainer();
            if (!mapContainer) return;

            html2canvas(mapContainer, {
                useCORS: true,
                logging: false,
                // No dibujar nada que esté dentro de .leaflet-control-container
                ignoreElements: function(element) {
                    return element.closest && element.closest(".leaflet-control-container") !== null;
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

                    // SVG sencillo con la imagen PNG incrustada
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
            // Folium crea una variable global tipo window.map_xxxxx
            var mapVarName = Object.keys(window).find(function (k) {
                return k.startsWith("map_");
            });
            if (!mapVarName) {
                console.warn("[MapExport] No se encontró la variable global del mapa.");
                return;
            }
            var map = window[mapVarName];

            // Control PNG
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

            // Control SVG
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

            console.log("[MapExport] Controles PNG y SVG añadidos");
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
