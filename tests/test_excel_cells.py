"""
Tests para persistence/_excel_cells.py

Cubre: _name_to_scalar, _is_invalid_student_name_cell, _split_full_name,
       _normalize_firmado
"""
import pytest
from persistence._excel_cells import (
    _is_invalid_student_name_cell,
    _name_to_scalar,
    _normalize_firmado,
    _split_full_name,
)


# ─────────────────────────────────────────────────────────────────────────────
# _name_to_scalar
# ─────────────────────────────────────────────────────────────────────────────

class TestNameToScalar:
    def test_string_normal(self):
        assert _name_to_scalar("María García") == "María García"

    def test_none_devuelve_vacio(self):
        assert _name_to_scalar(None) == ""

    def test_lista_un_elemento(self):
        assert _name_to_scalar(["Ana López"]) == "Ana López"

    def test_lista_anidada(self):
        assert _name_to_scalar([["Carlos"]]) == "Carlos"

    def test_string_con_corchetes(self):
        assert _name_to_scalar("['Pedro Martín']") == "Pedro Martín"

    def test_string_con_comillas_dobles_en_corchetes(self):
        assert _name_to_scalar('["Lucía"]') == "Lucía"

    def test_numero_se_convierte_a_string(self):
        assert _name_to_scalar(42) == "42"

    def test_espacios_se_eliminan(self):
        assert _name_to_scalar("  nombre  ") == "nombre"

    def test_tupla(self):
        assert _name_to_scalar(("Juan",)) == "Juan"


# ─────────────────────────────────────────────────────────────────────────────
# _is_invalid_student_name_cell
# ─────────────────────────────────────────────────────────────────────────────

class TestIsInvalidStudentNameCell:
    def test_none_es_invalido(self):
        assert _is_invalid_student_name_cell(None) is True

    def test_vacio_es_invalido(self):
        assert _is_invalid_student_name_cell("") is True

    def test_solo_espacios_es_invalido(self):
        assert _is_invalid_student_name_cell("   ") is True

    def test_formula_excel_es_invalida(self):
        assert _is_invalid_student_name_cell("=A1+B1") is True

    def test_error_excel_nd_es_invalido(self):
        assert _is_invalid_student_name_cell("#N/D") is True

    def test_error_excel_value_es_invalido(self):
        assert _is_invalid_student_name_cell("#VALUE!") is True

    def test_error_excel_spill_es_invalido(self):
        assert _is_invalid_student_name_cell("#SPILL!") is True

    def test_cero_es_invalido(self):
        assert _is_invalid_student_name_cell("0") is True

    def test_nombre_valido(self):
        assert _is_invalid_student_name_cell("María Picazo") is False

    def test_nombre_con_espacios_valido(self):
        assert _is_invalid_student_name_cell("  Ana  ") is False


# ─────────────────────────────────────────────────────────────────────────────
# _split_full_name
# ─────────────────────────────────────────────────────────────────────────────

class TestSplitFullName:
    def test_vacio_devuelve_tres_vacios(self):
        assert _split_full_name("") == ("", "", "")

    def test_none_devuelve_tres_vacios(self):
        assert _split_full_name(None) == ("", "", "")

    def test_solo_nombre(self):
        assert _split_full_name("María") == ("María", "", "")

    def test_nombre_y_apellido(self):
        assert _split_full_name("María García") == ("María", "García", "")

    def test_nombre_dos_apellidos(self):
        assert _split_full_name("María García López") == ("María", "García", "López")

    def test_nombre_varios_apellidos(self):
        nombre, ap1, ap2 = _split_full_name("María García López Ruiz")
        assert nombre == "María"
        assert ap1 == "García"
        assert ap2 == "López Ruiz"

    def test_espacios_extra_se_normalizan(self):
        assert _split_full_name("  Ana  López  ") == ("Ana", "López", "")


# ─────────────────────────────────────────────────────────────────────────────
# _normalize_firmado
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeFirmado:
    @pytest.mark.parametrize("valor", ["x", "X", "1", "s", "S", "si", "sí", "SÍ", "true", "True", "TRUE", "t", "T"])
    def test_valores_firmado(self, valor):
        assert _normalize_firmado(valor) == "x"

    @pytest.mark.parametrize("valor", ["", "0", "no", "n", "false", "f", None])
    def test_valores_no_firmado(self, valor):
        assert _normalize_firmado(valor) == ""

    def test_bool_true(self):
        assert _normalize_firmado(True) == "x"

    def test_bool_false(self):
        assert _normalize_firmado(False) == ""
