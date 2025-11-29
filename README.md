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
  - Endpoint para capturas HTML → PNG (Playwright).

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
    PyMuPDF

---

## 4. Ejecución del sistema

Primero lanzamos el microservicio Flask:

```bash
python api.py

Y luego la aplicación:

```bash
python -m streamlit run my_app.py
