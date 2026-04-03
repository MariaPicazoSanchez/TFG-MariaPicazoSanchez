"""
Tests para domain/_converters.py

Cubre: safe_int_convert, safe_int_to_str, safe_float_convert,
       safe_bool_convert, normalize_*, compose_normalizers
"""
import pytest
from domain._converters import (
    safe_int_convert,
    safe_int_to_str,
    safe_float_convert,
    safe_bool_convert,
    normalize_string,
    normalize_lower,
    normalize_email,
    normalize_int,
    normalize_phone,
    compose_normalizers,
)


# ─────────────────────────────────────────────────────────────────────────────
# safe_int_convert
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeIntConvert:
    def test_entero_normal(self):
        assert safe_int_convert(3) == 3

    def test_string_entero(self):
        assert safe_int_convert("5") == 5

    def test_string_float(self):
        assert safe_int_convert("3.0") == 3

    def test_float_con_decimales_trunca(self):
        assert safe_int_convert("1.9") == 1

    def test_none_devuelve_default(self):
        assert safe_int_convert(None) is None
        assert safe_int_convert(None, default=0) == 0

    def test_string_vacio_devuelve_default(self):
        assert safe_int_convert("", default=99) == 99

    def test_string_invalido_devuelve_default(self):
        assert safe_int_convert("abc", default=0) == 0

    def test_valor_negativo(self):
        assert safe_int_convert("-4") == -4

    def test_float_nativo(self):
        assert safe_int_convert(2.7) == 2


# ─────────────────────────────────────────────────────────────────────────────
# safe_int_to_str
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeIntToStr:
    def test_entero_a_str(self):
        assert safe_int_to_str(6) == "6"

    def test_string_float_a_str(self):
        assert safe_int_to_str("3.0") == "3"

    def test_invalido_devuelve_default(self):
        assert safe_int_to_str("abc") == ""
        assert safe_int_to_str("abc", default="-") == "-"

    def test_none_devuelve_default(self):
        assert safe_int_to_str(None) == ""


# ─────────────────────────────────────────────────────────────────────────────
# safe_float_convert
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeFloatConvert:
    def test_float_normal(self):
        assert safe_float_convert(3.14) == pytest.approx(3.14)

    def test_string_float(self):
        assert safe_float_convert("2.5") == pytest.approx(2.5)

    def test_none_devuelve_default(self):
        assert safe_float_convert(None) == 0.0
        assert safe_float_convert(None, default=1.5) == pytest.approx(1.5)

    def test_invalido_devuelve_default(self):
        assert safe_float_convert("xyz") == 0.0

    def test_string_vacio_devuelve_default(self):
        assert safe_float_convert("   ") == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# safe_bool_convert
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeBoolConvert:
    @pytest.mark.parametrize("value", [True, 1, "sí", "yes", "true", "x", "v", "1"])
    def test_truthy_values(self, value):
        assert safe_bool_convert(value) is True

    @pytest.mark.parametrize("value", [False, 0, "no", "false", "", "0"])
    def test_falsy_values(self, value):
        assert safe_bool_convert(value) is False

    def test_none_devuelve_default(self):
        assert safe_bool_convert(None) is False
        assert safe_bool_convert(None, default=True) is True

    def test_string_desconocido_devuelve_default(self):
        assert safe_bool_convert("quizas") is False


# ─────────────────────────────────────────────────────────────────────────────
# Normalizadores
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizers:
    def test_normalize_string_trim(self):
        assert normalize_string("  hola  ") == "hola"

    def test_normalize_string_none(self):
        assert normalize_string(None) == ""

    def test_normalize_lower(self):
        assert normalize_lower("HELLO") == "hello"

    def test_normalize_email(self):
        assert normalize_email("  USER@Example.COM  ") == "user@example.com"

    def test_normalize_int(self):
        assert normalize_int("7") == 7
        assert normalize_int("abc") == 0
        assert normalize_int(None) == 0

    def test_normalize_phone_solo_digitos(self):
        assert normalize_phone("+34 600-123 456") == "34600123456"

    def test_normalize_phone_none(self):
        assert normalize_phone(None) == ""


# ─────────────────────────────────────────────────────────────────────────────
# compose_normalizers
# ─────────────────────────────────────────────────────────────────────────────

class TestComposeNormalizers:
    def test_compose_dos_funciones(self):
        strip_and_lower = compose_normalizers(normalize_string, normalize_lower)
        assert strip_and_lower("  HOLA MUNDO  ") == "hola mundo"

    def test_compose_vacio(self):
        identity = compose_normalizers()
        assert identity("valor") == "valor"

    def test_compose_tres_funciones(self):
        pipeline = compose_normalizers(
            normalize_string,
            normalize_lower,
            lambda v: v.replace(" ", "_"),
        )
        assert pipeline("  Hola Mundo  ") == "hola_mundo"
