"""
Tests para persistence/sheets_helpers.py

Funciones testeables:
  - norm_sheet   — normalización de nombres de hoja (pura)
  - resolve_sheet — resolución de hoja por nombre normalizado (pura)
  - sheets_for    — lista hojas de un Excel; usa tmp_path para evitar ficheros reales
"""
import os
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from persistence.sheets_helpers import norm_sheet, resolve_sheet, sheets_for


# ─────────────────────────────────────────────────────────────────────────────
# norm_sheet
# ─────────────────────────────────────────────────────────────────────────────

class TestNormSheet:
    def test_minusculas(self):
        assert norm_sheet("ERASMUS IN") == "erasmus in"

    def test_strip_espacios(self):
        assert norm_sheet("  hoja  ") == "hoja"

    def test_none_devuelve_vacio(self):
        assert norm_sheet(None) == ""

    def test_guiones_raros_normalizados(self):
        # – es un guion largo; debe convertirse a '-'
        result = norm_sheet("2023–2024")
        assert result == "2023-2024"

    def test_guion_em_normalizado(self):
        result = norm_sheet("Curso—2025")
        assert result == "curso-2025"

    def test_guion_minus_normalizado(self):
        result = norm_sheet("Dato−2025")
        assert result == "dato-2025"

    def test_espacios_no_break_convertidos(self):
        #   es espacio no separable
        result = norm_sheet("Hoja Datos")
        assert result == "hoja datos"

    def test_colapsa_espacios_multiples(self):
        result = norm_sheet("Hoja   Datos")
        assert result == "hoja datos"

    def test_nfkc_aplicado(self):
        # Algunas letras en forma compatibilidad se normalizan
        result = norm_sheet("ＡＢＣ")  # fullwidth ASCII
        assert result == "abc"

    def test_cadena_vacia_devuelve_vacia(self):
        assert norm_sheet("") == ""

    def test_numero_convertido_a_string(self):
        result = norm_sheet(2024)
        assert result == "2024"


# ─────────────────────────────────────────────────────────────────────────────
# resolve_sheet
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveSheet:
    def test_match_exacto(self):
        candidates = ["2023/2024", "2024/2025"]
        result = resolve_sheet("2024/2025", candidates)
        assert result == "2024/2025"

    def test_match_exacto_case_insensitive(self):
        candidates = ["Erasmus IN"]
        result = resolve_sheet("erasmus in", candidates)
        assert result == "Erasmus IN"

    def test_match_exacto_con_espacios(self):
        candidates = ["  Hoja Uno  "]
        result = resolve_sheet("Hoja Uno", candidates)
        # norm_sheet normaliza espacios -> debe coincidir
        assert result == "  Hoja Uno  "

    def test_no_match_devuelve_none(self):
        candidates = ["2023/2024"]
        result = resolve_sheet("2025/2026", candidates)
        assert result is None

    def test_contains_unico_match(self):
        candidates = ["Datos 2024/2025", "Datos 2023/2024"]
        # "2024" está en el primero pero también en el segundo ->
        # dos matches -> None
        result = resolve_sheet("2024", candidates)
        # Hay dos candidatos que contienen "2024", no debe devolver ninguno
        assert result is None

    def test_contains_unico_resultado(self):
        candidates = ["Erasmus IN 2024", "SICUE OUT 2024"]
        result = resolve_sheet("erasmus", candidates)
        # Solo "Erasmus IN 2024" contiene "erasmus"
        assert result == "Erasmus IN 2024"

    def test_candidates_vacio_devuelve_none(self):
        result = resolve_sheet("cualquier", [])
        assert result is None

    def test_candidates_none_devuelve_none(self):
        result = resolve_sheet("cualquier", None)
        assert result is None

    def test_match_con_guion_largo(self):
        # El candidato tiene guion normal, la selección tiene guion largo
        candidates = ["2023-2024"]
        result = resolve_sheet("2023–2024", candidates)
        assert result == "2023-2024"


# ─────────────────────────────────────────────────────────────────────────────
# sheets_for
# ─────────────────────────────────────────────────────────────────────────────

class TestSheetsFor:
    def test_path_vacio_devuelve_lista_vacia(self):
        result = sheets_for("")
        assert result == []

    def test_path_none_devuelve_lista_vacia(self):
        result = sheets_for(None)
        assert result == []

    def test_path_no_existe_devuelve_lista_vacia(self):
        result = sheets_for("/ruta/que/no/existe/archivo.xlsx")
        assert result == []

    def test_csv_devuelve_csv_virtual(self, tmp_path):
        csv_file = tmp_path / "datos.csv"
        csv_file.write_text("a,b\n1,2\n")
        result = sheets_for(str(csv_file))
        assert result == ["__CSV__"]

    def test_excel_con_hojas_reales(self, tmp_path):
        """Crea un Excel real con openpyxl y verifica que sheets_for lo lee.

        sheets_for usa pd.ExcelFile con engine='openpyxl'. En el entorno de
        test xlrd está mockeado, pero openpyxl está disponible; lo usamos
        directamente para crear el workbook y luego parcheamos pd.ExcelFile
        para devolver las hojas correctas.
        """
        from openpyxl import Workbook
        from unittest.mock import patch, MagicMock
        xlsx_file = tmp_path / "test.xlsx"
        wb = Workbook()
        wb.active.title = "Hoja1"
        wb.create_sheet("Hoja2")
        wb.save(str(xlsx_file))

        # pd.ExcelFile puede fallar si hay conflicto con el mock de xlrd;
        # lo simulamos directamente.
        mock_xf = MagicMock()
        mock_xf.__enter__ = lambda s: s
        mock_xf.__exit__ = MagicMock(return_value=False)
        mock_xf.sheet_names = ["Hoja1", "Hoja2"]

        with patch("persistence.sheets_helpers.pd.ExcelFile", return_value=mock_xf):
            result = sheets_for(str(xlsx_file))

        assert "Hoja1" in result
        assert "Hoja2" in result

    def test_excel_corrupto_devuelve_lista_vacia(self, tmp_path):
        """Un fichero que no es Excel real debe devolver []."""
        bad_file = tmp_path / "bad.xlsx"
        bad_file.write_bytes(b"esto no es un excel")
        result = sheets_for(str(bad_file))
        assert result == []
