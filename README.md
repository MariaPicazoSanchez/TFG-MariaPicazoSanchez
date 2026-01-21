# TFG – Visualización de Movilidad UCLM

Aplicación desarrollada con **Streamlit** y **Leafmap** para visualizar y gestionar datos de movilidad internacional de estudiantes de la UCLM.

La app permite:

- Visualizar destinos de movilidad en un mapa interactivo.
- Filtrar por programas / tipos de movilidad.
- Ver información detallada de cada destino y de los estudiantes asociados.
- Exportar capturas del mapa tal y como se ve en pantalla (PNG / SVG).
- (Solo en local) Modificar información de estudiantes a través de un microservicio Flask que actualiza ficheros Excel.

---

## 1. Tecnologías principales

- Python (recomendado ≥ 3.10)
- Streamlit – interfaz web
- Leafmap / Folium – mapas
- Pandas – manipulación de datos
- Flask – microservicio de apoyo
- Otras librerías: `pycountry`, `Babel`, `geopy`, `openpyxl`, `PyMuPDF`, etc.

---

## 2. Estructura del proyecto (resumen)

Ficheros principales:

- `my_app.py` → **Aplicación principal** de Streamlit.
- `map_view.py` → Construcción del mapa con Leafmap/Folium.
- `map_export.py` → Botones de exportación dentro del mapa (PNG / SVG).
- `api.py` → **Microservicio Flask**:
  - Endpoints para modificar estudiantes en Excel.
---

## 3. Dependencias

### 3.1. Instalación rápida (lista mínima)

En una terminal, dentro de la carpeta del proyecto:

```bash
pip install \
    streamlit \
    leafmap[maplibre] \
    folium \
    pandas \
    openpyxl \
    geopy \
    pycountry \
    Babel \
    flask \
    requests \
    PyMuPDF \
    reportlab
```
---

## 4. Ejecución del sistema

Primero lanzamos el microservicio Flask:

```bash
python api.py
```
Y luego la aplicación:

```bash
python -m streamlit run my_app.py
```
Compilar el sistema
```bash
py -3.12 -m PyInstaller --onedir --noconsole --clean --noconfirm --name MovilidadESII launcher.py
```

---

## 5. Uso de internet y privacidad

Aunque la aplicación se ejecuta de forma local en el ordenador del usuario, hace un uso limitado de internet:

### 5.1. Dependencias y ejecución

- Las librerías Python (`streamlit`, `flask`, `pandas`, `leafmap`, `folium`, etc.) **no necesitan conexión a internet para ejecutarse**, una vez instaladas.
- Solo se requiere internet en el momento de instalarlas con `pip install ...`.

### 5.2. Mapas base (tiles)

- Los mapas base (p.ej. OpenStreetMap) se cargan por defecto desde **servidores externos**.
- Al mover o hacer zoom en el mapa, el navegador descarga las “teselas” (tiles) desde esos servidores.
- Solo se descargan imágenes de fondo; **los datos de movilidad (estudiantes, universidades, etc.) se cargan desde ficheros locales** y no se envían fuera.
- Sin conexión, la app puede seguir funcionando, pero el mapa puede aparecer sin fondo (blanco/gris).

### 5.3. Librerías JavaScript desde CDNs

- En `map_export.py` se usa la librería `html2canvas` cargada desde un CDN:
  ```html
  <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
  ```
