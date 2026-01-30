# popup_helpers.py
import html
import json
import math
from typing import Any
from urllib.parse import quote

def _normalize_estudiantes(estudiantes: Any) -> list[dict[str, Any]]:
    """Normaliza la lista de estudiantes y mapea los nombres de columnas
    del Excel a claves internas homogéneas.
    """
    if isinstance(estudiantes, str):
        try:
            estudiantes = json.loads(estudiantes)
        except Exception:
            estudiantes = [{"estudiante": estudiantes}]
    if isinstance(estudiantes, dict):
        estudiantes = [estudiantes]
    if estudiantes is None or (isinstance(estudiantes, float) and math.isnan(estudiantes)):
        estudiantes = []

    out = []
    for e in estudiantes:
        if not isinstance(e, dict):
            continue

        norm = {str(k).strip(): v for k, v in e.items()}

        # ---- Ciudad ----
        ciudad_val = None
        for k in ("ciudad", "Ciudad", "ciudad destino", "Ciudad destino", "City", "city"):
            if k in norm and not _is_empty(norm[k]):
                ciudad_val = norm[k]
                break
        if ciudad_val is not None:
            norm["ciudad"] = ciudad_val

        # ---- Enlaces LA ----
        if "link_la" not in norm:
            for k in ("link_LA", "LA", "la", "La"):
                if k in norm and str(norm[k]).strip():
                    norm["link_la"] = norm[k]
                    break

        # ---- Plan de estudios ----
        if "link_plan" not in norm:
            for k in ("Enlace plan de estudios", "Plan de estudios", "plan de estudios", "plan_estudios"):
                if k in norm and str(norm[k]).strip():
                    norm["link_plan"] = norm[k]
                    break

        # ---- Duración ----
        if "duracion_meses" not in norm:
            for k in ("duracion meses", "duración meses", "Duración meses",
                      "Duracion meses", "Duración (meses)", "Duracion (meses)"):
                if k in norm and str(norm[k]).strip():
                    norm["duracion_meses"] = norm[k]
                    break

        # ---- Gestión LA ----
        if "gestion_LA" not in norm:
            for k in ("Gestión LA", "Gestion LA", "gestión LA", "gestion LA"):
                if k in norm and str(norm[k]).strip():
                    norm["gestion_LA"] = norm[k]
                    break

        # ---- Coordinador destino ----
        if "coordinador_destino" not in norm:
            for k in ("Coordinador en destino", "Coordinador destino", "coordinador destino"):
                if k in norm and str(norm[k]).strip():
                    norm["coordinador_destino"] = norm[k]
                    break

        # ---- Responsable programa (Erasmus OUT) ----
        if "responsable_programa" not in norm:
            for k in ("responsable programa", "Responsable programa", "Responsable"):
                if k in norm and str(norm[k]).strip():
                    norm["responsable_programa"] = norm[k]
                    break

        out.append(norm)
    return out

def _clean(v: Any) -> str:
    s = "" if v is None else str(v).strip()
    return "" if s.lower() in {"nan", "none", ""} else s


def _line(label: str, value: Any) -> str:
    value = _clean(value)
    return f"<b>{label}:</b> {html.escape(value)}<br>" if value else ""


def _view_line(label: str, value: Any) -> str:
    """
    Línea para modo *vista*:
    - Siempre muestra la etiqueta.
    - Si no hay valor, pone 'Sin datos' en gris.
    """
    v = _clean(value)
    if v:
        val_html = html.escape(v)
    else:
        val_html = "<span style='color:#9ca3af;font-style:italic;'>Sin datos</span>"
    return f"<b>{html.escape(label)}:</b> {val_html}<br>"


def _view_link(label: str, url: Any, text: str = "Abrir", open_in_system: bool = False) -> str:
    """
    Versión genérica de links; por si la necesitas desde otros módulos.
    """
    url = _clean(url)
    if not url:
        val_html = "<span style='color:#9ca3af;font-style:italic;'>Sin datos</span>"
        return f"<b>{html.escape(label)}:</b> {val_html}<br>"

    label_html = html.escape(label, quote=True)
    text_html = html.escape(text, quote=True)

    # Abrir con la app por defecto del SISTEMA (rutas locales, no http/https)
    if open_in_system and not str(url).lower().startswith(("http://", "https://")):
        qp = quote(str(url))
        return (
            "<iframe name='opener' style='display:none;width:0;height:0;border:0'></iframe>"
            f"<b>{label_html}:</b> "
            f"<a href='/?open_pdf={qp}' target='opener'>{text_html}</a><br>"
        )

    # Comportamiento normal para enlaces web
    safe_url = html.escape(str(url), quote=True)
    return f"<b>{label_html}:</b> <a href='{safe_url}' target='_blank' rel='noopener noreferrer'>{text_html}</a><br>"

def _is_empty(value: Any) -> bool:
    import math
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False
