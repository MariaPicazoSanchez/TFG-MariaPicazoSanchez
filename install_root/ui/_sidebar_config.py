"""
Config I/O, file picker y detección de hojas para el sidebar.

Exporta:
  - CONFIG_FILE               — ruta al config.json activo
  - load_config / save_config — lectura y escritura de config.json
  - verify_paths              — comprueba que las rutas existan
  - get_placeholder           — placeholder para inputs de ruta
  - pick_local_file           — abre OpenFileDialog vía PowerShell (Windows)
  - _is_academic_year         — detecta si un nombre parece curso académico
  - _list_sheets_in_file      — hojas de un Excel/CSV (cacheado)
  - _unique_sheets_from_config_or_files — unión de hojas de todos los Excels
"""


import json
import os
import re
import subprocess

import pandas as pd
import streamlit as st
import xlrd

from constants import PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT, CSV_SHEET_MARKER
from utils.path_helpers import repair_windows_path

CONFIG_FILE = os.getenv("APP_CONFIG_PATH", "config.json")


# ─────────────────────────────────────────────────────────────────────────────
# Config JSON
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Carga las rutas guardadas desde config.json, reparando rutas mal formadas."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        key: repair_windows_path(value)
             if isinstance(value, str) and (value.startswith("C:") or value.startswith("D:") or value.startswith("/"))
             else value
        for key, value in config.items()
    }


def save_config(config: dict) -> None:
    """Guarda las rutas actuales en config.json preservando otras claves."""
    try:
        existing: dict = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        existing.update(config)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def verify_paths(config: dict) -> tuple[bool, list[str]]:
    """Verifica que todas las rutas existan. Devuelve (ok, lista_errores)."""
    errors = [f"{nombre}: {ruta}" for nombre, ruta in config.items() if not os.path.exists(ruta)]
    return len(errors) == 0, errors


def get_placeholder(config: dict, key: str) -> str:
    """Devuelve un placeholder con la ruta guardada o texto descriptivo."""
    ruta = config.get(key, "")
    return ruta if ruta else f"Inserte la ruta del archivo {key} aquí"


# ─────────────────────────────────────────────────────────────────────────────
# File picker (Windows / PowerShell)
# ─────────────────────────────────────────────────────────────────────────────

def pick_local_file(
    initial_path: str | None = None,
    file_filter: str | None = None,
) -> str | None:
    """Abre el explorador de archivos mediante PowerShell y devuelve la ruta seleccionada."""
    if file_filter is None:
        file_filter = "Todos los archivos (*.*)|*.*"
    ps_filter = file_filter.replace("'", "''")
    script = f"""
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.TopMost = $true
$form.WindowState = 'Minimized'
$form.Show()
$dialog = New-Object System.Windows.Forms.OpenFileDialog
$dialog.Filter = '{ps_filter}'
$dialog.SupportMultiDottedExtensions = $true
if ($dialog.ShowDialog($form) -eq 'OK') {{
    Write-Output $dialog.FileName
}}
$form.Close()
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        path = result.stdout.strip()
        return path if path else None
    except Exception as e:
        st.sidebar.error(f"PowerShell OpenFileDialog error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Detección de hojas académicas
# ─────────────────────────────────────────────────────────────────────────────

def _is_academic_year(name: str) -> bool:
    """True si el nombre parece un curso académico (ej: 25-26, 2025/2026, 2016)."""
    return bool(re.search(r'\d{4}|\d{2}[-/]\d{2}', name))


@st.cache_data(show_spinner=False)
def _list_sheets_in_file(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return [CSV_SHEET_MARKER]
    try:
        return list(pd.ExcelFile(path).sheet_names)
    except Exception:
        pass
    try:
        if ext in (".xlsx", ".xlsm", ".xltx", ".xltm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            return list(wb.sheetnames)
    except Exception:
        pass
    try:
        if ext == ".xls":
            wb = xlrd.open_workbook(path, on_demand=True)
            return wb.sheet_names()
    except Exception:
        pass
    return []


def _unique_sheets_from_config_or_files(cfg: dict) -> list[str]:
    """Unión de hojas de todos los Excels configurados; detecta leyendo los ficheros si no hay 'sheets'."""
    sheets_map = cfg.get("sheets", {}) or {}
    names: set[str] = set()
    for k in (PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT):
        lst = sheets_map.get(k) or (_list_sheets_in_file(cfg.get(k)) if cfg.get(k) else [])
        for name in lst:
            if name and str(name) != "__CSV__" and _is_academic_year(str(name)):
                names.add(str(name))
    return sorted(names)
