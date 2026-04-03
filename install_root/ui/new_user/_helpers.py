"""
Helpers para el formulario de nuevo estudiante:
  - Mapas universidad→país, universidad→responsable
  - Lista de países (ISO con babel)
  - Catálogo de asignaturas
  - Geocodificación con caché
  - Utilidades de texto y selección de fichero
"""

from __future__ import annotations

import logging
import re
import unicodedata

import pandas as pd
import streamlit as st

logger = logging.getLogger("movilidad_ui")

# ──────────────────────────────────────────────────────────────────────────────
# Utilidades de selección de fichero
# ──────────────────────────────────────────────────────────────────────────────

USE_LOCAL_PICKER = True
_FILTER_ALL = None
_FILTER_PDF_WORD = "PDF y Word|*.pdf;*.docx|Todos|*.*"


def _invisible_suffix_from_id(button_id: str) -> str:
    """Genera un sufijo invisible único para evitar claves duplicadas en st.button."""
    bits = "".join(f"{ord(c):08b}" for c in button_id)
    return "".join("\u200b" if b == "0" else "\u200c" for b in bits)


def file_picker_button(
    label: str,
    text_input_key: str,
    button_id: str,
    help: str = "Seleccionar archivo del equipo",
    file_filter: str | None = _FILTER_PDF_WORD,
) -> bool:
    from ui.sidebar import pick_local_file

    invisible_suffix = _invisible_suffix_from_id(button_id)
    clicked = st.button(label + invisible_suffix, help=help, key=button_id)
    if clicked:
        if USE_LOCAL_PICKER:
            current_val = st.session_state.get(text_input_key, "")
            path = pick_local_file(current_val, file_filter=file_filter)
            if path:
                st.session_state["_buf_" + text_input_key] = path
        else:
            st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")
        st.rerun()
    return clicked


# ──────────────────────────────────────────────────────────────────────────────
# Mapas universidad → país / responsable
# ──────────────────────────────────────────────────────────────────────────────

def get_university_country_map(path: str) -> dict:
    """Devuelve {universidad: país} leyendo la hoja 'Coordenadas' (col0=País, col1=Universidad)."""
    try:
        df = pd.read_excel(path, sheet_name="Coordenadas", header=None, dtype=str)
        df = df.dropna(subset=[0, 1])
        return {str(row[1]).strip(): str(row[0]).strip() for _, row in df.iterrows()}
    except Exception:
        return {}


def get_university_responsable_map(path: str) -> dict:
    """
    Devuelve {universidad: responsable} desde la hoja 'Coordenadas' (col3).
    Si la columna no existe, escanea las hojas de alumnos y escribe el resultado en col3.
    """
    if not path:
        return {}
    try:
        df_coords = pd.read_excel(path, sheet_name="Coordenadas", header=None, dtype=str)
        if df_coords.shape[1] >= 4:
            result = {}
            for _, row in df_coords.iterrows():
                uni  = str(row.iloc[1] if pd.notna(row.iloc[1]) else "").strip()
                resp = str(row.iloc[3] if pd.notna(row.iloc[3]) else "").strip()
                if uni and resp and resp.lower() not in ("nan", "none", ""):
                    result[uni] = resp
            if result:
                return result
        resp_map = _build_responsable_from_students(path)
        if resp_map:
            _write_responsable_to_coordenadas(path, resp_map)
        return resp_map
    except Exception:
        return {}


def _build_responsable_from_students(path: str) -> dict:
    """Construye {universidad: responsable} escaneando las hojas de datos del Excel."""
    def _is_academic_sheet(name: str) -> bool:
        return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', str(name)))

    def _pick_col(df: pd.DataFrame, *names: str):
        norm = lambda s: s.strip().lower()
        for n in names:
            for c in df.columns:
                if norm(str(c)) == norm(n):
                    return c
        return None

    resp_map: dict = {}
    try:
        wb_sheets = pd.ExcelFile(path, engine="openpyxl").sheet_names
    except Exception:
        return {}

    hojas = [s for s in wb_sheets if _is_academic_sheet(s)]
    if not hojas:
        hojas = [s for s in wb_sheets if s.lower() != "coordenadas"]

    for sheet in hojas:
        try:
            df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl", dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            c_uni  = _pick_col(df, "Destino", "destino", "Universidad", "universidad")
            c_resp = _pick_col(
                df,
                "Responsable programa", "responsable programa",
                "Responsable del programa", "responsable del programa",
                "Responsable", "responsable",
            )
            if not c_uni or not c_resp:
                continue
            for _, row in df.iterrows():
                uni  = str(row.get(c_uni,  "") or "").strip()
                resp = str(row.get(c_resp, "") or "").strip()
                if (uni and resp
                        and uni.lower()  not in ("nan", "none", "")
                        and resp.lower() not in ("nan", "none", "")):
                    resp_map.setdefault(uni, resp)
        except Exception:
            continue
    return resp_map


def _write_responsable_to_coordenadas(path: str, resp_map: dict) -> None:
    """Escribe el responsable en col D de la hoja 'Coordenadas'."""
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path)
        if "Coordenadas" not in wb.sheetnames:
            return
        ws = wb["Coordenadas"]
        for r_idx in range(1, ws.max_row + 1):
            uni_val = str(ws.cell(row=r_idx, column=2).value or "").strip()
            if uni_val and uni_val.lower() not in ("nan", "none", ""):
                resp_val = resp_map.get(uni_val, "")
                if resp_val:
                    ws.cell(row=r_idx, column=4).value = resp_val
        wb.save(path)
        logger.info("Responsables escritos en hoja Coordenadas: %d universidades", len(resp_map))
    except Exception as e:
        logger.warning("No se pudo escribir responsable en Coordenadas: %s", e)


# ──────────────────────────────────────────────────────────────────────────────
# Lista de países (ISO con babel, cacheada)
# ──────────────────────────────────────────────────────────────────────────────

COUNTRY_ALIASES = {
    "Chequia": "República Checa",
    "Eslovaquia": "República Eslovaca",
    "Corea del Sur": "Corea, República de",
    "Corea del Norte": "Corea, República Popular Democrática de",
}


@st.cache_data
def get_country_options() -> list[str]:
    import pycountry
    from babel import Locale
    locale_es = Locale("es")
    nombres = []
    for country in pycountry.countries:
        nombre_es = locale_es.territories.get(country.alpha_2, country.name)
        nombre_es = COUNTRY_ALIASES.get(nombre_es, nombre_es)
        nombres.append(nombre_es)
    return [""] + sorted(set(nombres))


COUNTRY_OPTIONS: list[str] = get_country_options()


# ──────────────────────────────────────────────────────────────────────────────
# Catálogo de asignaturas (con caché en session_state)
# ──────────────────────────────────────────────────────────────────────────────

def load_asignaturas_catalog(config: dict, sheet_name: str | None = None) -> list:
    ruta = (config.get("Erasmus IN") or "").strip()
    cache_key = f"_asignaturas_catalog_cache_{ruta}_{sheet_name or ''}"
    cached = st.session_state.get(cache_key)
    if cached and isinstance(cached, list) and len(cached) > 0 and "matriculados" not in cached[0]:
        del st.session_state[cache_key]
    if cache_key not in st.session_state:
        try:
            from persistence import get_asignaturas_catalog
            st.session_state[cache_key] = get_asignaturas_catalog(config, sheet_name=sheet_name)
        except Exception as e:
            logger.warning("No se pudo cargar catálogo de asignaturas: %s", e)
            st.session_state[cache_key] = []
    return st.session_state.get(cache_key, [])


# ──────────────────────────────────────────────────────────────────────────────
# Geocodificación (con caché en session_state)
# ──────────────────────────────────────────────────────────────────────────────

try:
    from geopy.geocoders import Nominatim
    from geopy.extra.rate_limiter import RateLimiter
    _GEOCODER = Nominatim(user_agent="tfg-movilidad-esii")
    _GEOCODE = RateLimiter(_GEOCODER.geocode, min_delay_seconds=1)
except Exception:
    _GEOCODER = None
    _GEOCODE = None


def geocode_cached(q: str) -> tuple[float | None, float | None, str | None]:
    if not q or not q.strip():
        return None, None, "Consulta vacía"
    qn = q.strip().lower()
    cache = st.session_state.setdefault("_geo_cache", {})
    if qn in cache:
        d = cache[qn]
        return d["lat"], d["lon"], None
    if _GEOCODE is None:
        return None, None, "Geocoder no disponible"
    try:
        loc = _GEOCODE(q, addressdetails=False, timeout=10)
        if loc:
            lat, lon = float(loc.latitude), float(loc.longitude)
            cache[qn] = {"lat": lat, "lon": lon}
            return lat, lon, None
        return None, None, "No encontrado"
    except Exception as e:
        return None, None, f"Error geocodificando: {e}"


# ──────────────────────────────────────────────────────────────────────────────
# Utilidades de asignaturas y hojas
# ──────────────────────────────────────────────────────────────────────────────

def is_academic_year(name: str) -> bool:
    return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', name))


def sheet_options_for(cfg: dict, tipo: str) -> list[str]:
    from persistence import sheets_for
    sheets_map = (cfg or {}).get("sheets", {}) or {}
    known = sheets_map.get(tipo) or []
    if known:
        return sorted({s for s in known if s and s != "__CSV__" and is_academic_year(s)})
    path = (cfg or {}).get(tipo, "")
    return [s for s in sheets_for(path) if s != "__CSV__" and is_academic_year(s)] if path else []


def normalize_subject_name(s: str) -> str:
    """Normaliza nombre de asignatura para comparación insensible a acentos/mayúsculas."""
    s = (s or "").strip()
    s = re.sub(r'\s+', ' ', s)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    return s.casefold()


def asig_nombre_puro(label: str) -> str:
    """Extrae el nombre de asignatura quitando el sufijo '(matr/cupo)'."""
    return label.split("  (")[0].strip() if "  (" in label else label.strip()
