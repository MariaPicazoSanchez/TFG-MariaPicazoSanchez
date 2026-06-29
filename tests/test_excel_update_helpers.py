"""
Tests para persistence/excel_update.py

Cubre: _cuat_to_cell_value (helper puro).
Las demás funciones requieren ficheros Excel reales y se omiten.
"""
import pytest
from persistence.excel_update import _cuat_to_cell_value


class TestCuatToCellValue:
    def test_entero_como_string(self):
        assert _cuat_to_cell_value("1") == 1

    def test_float_entero_como_string(self):
        assert _cuat_to_cell_value("1.0") == 1

    def test_float_entero_dos(self):
        assert _cuat_to_cell_value("2.0") == 2

    def test_float_no_entero(self):
        result = _cuat_to_cell_value("1.5")
        assert result == pytest.approx(1.5)
        assert isinstance(result, float)

    def test_string_letra(self):
        assert _cuat_to_cell_value("A") == "A"

    def test_string_con_coma_decimal(self):
        # "1,0" → float("1.0") → int 1
        assert _cuat_to_cell_value("1,0") == 1

    def test_string_con_coma_no_entero(self):
        result = _cuat_to_cell_value("1,5")
        assert result == pytest.approx(1.5)

    def test_vacio_devuelve_vacio(self):
        assert _cuat_to_cell_value("") == ""

    def test_none_devuelve_none(self):
        assert _cuat_to_cell_value(None) is None

    def test_entero_directo(self):
        assert _cuat_to_cell_value(2) == 2

    def test_texto_no_numerico(self):
        assert _cuat_to_cell_value("primero") == "primero"

    def test_devuelve_int_no_float_para_enteros(self):
        result = _cuat_to_cell_value("3.0")
        assert isinstance(result, int)
        assert result == 3
