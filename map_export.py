from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from domain import PROGRAM_COLORS


def create_static_map(dfs: dict, export_format: str = "png"):
    """
    Crea una imagen estática más bonita:
      - Fondo con tiles (TonerLite)
      - Puntos coloreados por programa
      - Sin ejes, estilo "mapa"
    """
    if not dfs or not isinstance(dfs, dict):
        return None, None, None

    fmt = (export_format or "png").lower()
    if fmt not in ("png", "svg"):
        fmt = "png"

    # 1) Construir GeoDataFrame con todos los puntos
    rows = []
    for program, df in dfs.items():
        if df is None or df.empty:
            continue
        if not {"latitud", "longitud"}.issubset(df.columns):
            continue

        lats = pd.to_numeric(df["latitud"], errors="coerce")
        lons = pd.to_numeric(df["longitud"], errors="coerce")
        mask = lats.notna() & lons.notna()
        lats = lats[mask]
        lons = lons[mask]

        for lon, lat in zip(lons, lats):
            rows.append(
                {
                    "program": program,
                    "geometry": Point(lon, lat),
                }
            )

    if not rows:
        return None, None, None

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")

    # 2) Reproyectar a Web Mercator (necesario para contextily)
    gdf_3857 = gdf.to_crs(epsg=3857)

    # 3) Calcular bounds con un pequeño margen
    minx, miny, maxx, maxy = gdf_3857.total_bounds
    dx = (maxx - minx) or 1
    dy = (maxy - miny) or 1
    pad_x = 0.2 * dx
    pad_y = 0.2 * dy

    fig, ax = plt.subplots(figsize=(10, 6), facecolor="white")

    # 4) Fondo de mapa bonito con contextily
    try:
        import contextily as ctx

        ctx.add_basemap(
            ax,
            source=ctx.providers.Stamen.TonerLite,
            crs=gdf_3857.crs,
            alpha=0.9,
        )
    except Exception as e:
        # Si falla contextily, no petes: dibuja nada de fondo y ya
        print("No se pudo cargar contextily:", e)

    # 5) Dibujar puntos por programa
    for program, color in PROGRAM_COLORS.items():
        sub = gdf_3857[gdf_3857["program"] == program]
        if sub.empty:
            continue
        sub.plot(
            ax=ax,
            markersize=60,
            color=color,
            edgecolor="white",
            linewidth=0.7,
            alpha=0.95,
            label=program,
        )

    # 6) Ajustar límites y estilo
    ax.set_xlim(minx - pad_x, maxx + pad_x)
    ax.set_ylim(miny - pad_y, maxy + pad_y)

    ax.set_axis_off()
    ax.set_title("Mapa de movilidad", fontsize=16, pad=12)

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        # Leyenda con fondo blanco semitransparente
        leg = ax.legend(
            loc="lower left",
            frameon=True,
            framealpha=0.85,
            facecolor="white",
            edgecolor="#cccccc",
        )
        for txt in leg.get_texts():
            txt.set_fontsize(10)

    buf = BytesIO()
    mime = "image/png" if fmt == "png" else "image/svg+xml"
    fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=180)
    plt.close(fig)
    buf.seek(0)

    return buf, mime, fmt


# map_export.py
import folium

def add_export_control(m):
    """
    Añade al mapa Folium `m` un control Leaflet con botones PNG / SVG
    que usan dom-to-image-more para exportar el mapa tal cual se ve.
    Este control funcionará bien cuando el mapa se abra en un HTML
    standalone (fuera de Streamlit).
    """
    export_js = """
    <script>
    (function() {
      function initExport() {
        var map = window.%MAP_NAME%;
        if (!map || !map.getContainer) {
          setTimeout(initExport, 300);
          return;
        }
        if (map.__exportControlAdded) return;
        map.__exportControlAdded = true;

        function ensureDomToImage(cb) {
          if (window.domtoimage) {
            cb(window.domtoimage);
            return;
          }
          var s = document.createElement('script');
          s.src = 'https://cdn.jsdelivr.net/npm/dom-to-image-more@2.8.0/dist/dom-to-image-more.min.js';
          s.onload = function() { cb(window.domtoimage); };
          s.onerror = function(e) {
            console.error("[ExportMap] Error cargando dom-to-image-more", e);
            alert("No se pudo cargar la librería de exportación.");
          };
          document.body.appendChild(s);
        }

        function exportMap(format) {
          var container = map.getContainer();
          if (!container) return;

          ensureDomToImage(function(domtoimage) {
            var options = {
              bgcolor: "#ffffff",
              width: container.clientWidth,
              height: container.clientHeight
            };

            var promise = (format === "png")
              ? domtoimage.toPng(container, options)
              : domtoimage.toSvg(container, options);

            promise.then(function(dataUrlOrSvg) {
              var fileName = "mapa_movilidad_" +
                new Date().toISOString().slice(0,19).replace(/[:T]/g, "-") +
                "." + format;

              if (format === "png") {
                var link = document.createElement("a");
                link.href = dataUrlOrSvg;
                link.download = fileName;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
              } else {
                var blob = new Blob([dataUrlOrSvg], {type: "image/svg+xml;charset=utf-8"});
                var url = URL.createObjectURL(blob);
                var link = document.createElement("a");
                link.href = url;
                link.download = fileName;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                URL.revokeObjectURL(url);
              }
            }).catch(function(err) {
              console.error("Error exportando el mapa:", err);
              alert("No se pudo exportar el mapa (revisa la consola).");
            });
          });
        }

        var ExportControl = L.Control.extend({
          options: { position: "topleft" },
          onAdd: function(map) {
            var container = L.DomUtil.create(
              "div",
              "leaflet-bar leaflet-control leaflet-control-custom"
            );
            container.style.backgroundColor = "white";
            container.style.cursor = "pointer";

            var btnPng = L.DomUtil.create("a", "", container);
            btnPng.innerHTML = "PNG";
            btnPng.href = "#";
            btnPng.title = "Exportar mapa a PNG";

            var btnSvg = L.DomUtil.create("a", "", container);
            btnSvg.innerHTML = "SVG";
            btnSvg.href = "#";
            btnSvg.title = "Exportar mapa a SVG";

            L.DomEvent.on(btnPng, "click", function(e) {
              L.DomEvent.stopPropagation(e);
              L.DomEvent.preventDefault(e);
              exportMap("png");
            });

            L.DomEvent.on(btnSvg, "click", function(e) {
              L.DomEvent.stopPropagation(e);
              L.DomEvent.preventDefault(e);
              exportMap("svg");
            });

            L.DomEvent.disableClickPropagation(container);
            return container;
          }
        });

        map.addControl(new ExportControl());
      }

      initExport();
    })();
    </script>
    """.replace("%MAP_NAME%", m.get_name())

    m.get_root().html.add_child(folium.Element(export_js))

