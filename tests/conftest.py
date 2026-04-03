"""
Configuración global de pytest.

- Añade install_root al sys.path para que los imports funcionen sin instalar.
- Mockea streamlit, folium y los paquetes de UI con import circular para que
  los __init__.py de domain/ y utils/ no fallen al recopilar los tests.

Cadena problemática:
  domain/__init__ → stats_filters → ui → map_view → domain  (circular)
  domain/__init__ → map_filters   → streamlit              (no instalado en test)
  utils/__init__  → file_opener   → streamlit
"""
import sys
import os
from unittest.mock import MagicMock

# ── 1. Mocks de librerías externas de UI ─────────────────────────────────────
_st = MagicMock()
for _mod in (
    "streamlit", "streamlit.components", "streamlit.components.v1",
    "streamlit_folium", "folium", "altair",
    "pystray", "pywebview", "xlrd",
):
    sys.modules.setdefault(_mod, _st)

# ── 2. Mocks de paquetes internos que forman el ciclo circular ────────────────
# Al pre-registrar ui y sus submódulos, evitamos que domain/__init__ los
# intente importar realmente (y falle por el ciclo domain → ui → domain).
for _mod in (
    "ui", "ui.map_view", "ui.sidebar", "ui.new_user",
    "ui.stats_view", "ui.popup_templates", "ui.stats_helpers",
    "ui.search_helpers", "ui.styles", "ui.stats_table",
):
    sys.modules.setdefault(_mod, MagicMock())

# ── 3. Añadir install_root al path ───────────────────────────────────────────
ROOT = os.path.join(os.path.dirname(__file__), "..", "install_root")
sys.path.insert(0, os.path.abspath(ROOT))
