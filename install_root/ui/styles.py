"""
Carga el CSS de los popups del mapa desde static/popup_styles.css.

El contenido se cachea en memoria la primera vez que se accede,
para no releer el disco en cada render del popup.
"""

from __future__ import annotations

from pathlib import Path

_CSS_PATH = Path(__file__).resolve().parents[1] / "static" / "popup_styles.css"
_cache: str | None = None


def _load() -> str:
    global _cache
    if _cache is None:
        try:
            _cache = _CSS_PATH.read_text(encoding="utf-8")
        except OSError:
            _cache = ""
    return _cache


# POPUP_STYLES sigue siendo un string: el resto del código no cambia
POPUP_STYLES = _load()
