"""
Tests para domain/_validator_rules.py

Cubre: is_not_empty, is_email, is_url, is_path, is_valid_coordinates,
       is_in_range, is_duration_valid, is_course_valid, is_semester_valid,
       matches_pattern, is_one_of
"""
import pytest
from domain._validator_rules import (
    is_not_empty,
    is_email,
    is_url,
    is_path,
    is_valid_coordinates,
    is_in_range,
    is_duration_valid,
    is_course_valid,
    is_semester_valid,
    matches_pattern,
    is_one_of,
)


# ─────────────────────────────────────────────────────────────────────────────
# is_not_empty
# ─────────────────────────────────────────────────────────────────────────────

class TestIsNotEmpty:
    def test_string_con_contenido(self):
        ok, _ = is_not_empty()("hola")
        assert ok is True

    def test_string_vacio(self):
        ok, msg = is_not_empty()("")
        assert ok is False
        assert msg

    def test_string_solo_espacios(self):
        ok, _ = is_not_empty()("   ")
        assert ok is False

    def test_none_es_falso(self):
        ok, _ = is_not_empty()(None)
        assert ok is False

    def test_lista_no_vacia(self):
        ok, _ = is_not_empty()([1, 2])
        assert ok is True


# ─────────────────────────────────────────────────────────────────────────────
# is_email
# ─────────────────────────────────────────────────────────────────────────────

class TestIsEmail:
    @pytest.mark.parametrize("email", [
        "user@example.com",
        "maria.picazo@uclm.es",
        "test+tag@domain.org",
    ])
    def test_emails_validos(self, email):
        ok, _ = is_email()(email)
        assert ok is True

    @pytest.mark.parametrize("email", [
        "no-arroba",
        "@sinusuario.com",
        "sin-punto@dominio",
        "",
        None,
    ])
    def test_emails_invalidos(self, email):
        ok, _ = is_email()(email)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# is_url
# ─────────────────────────────────────────────────────────────────────────────

class TestIsUrl:
    @pytest.mark.parametrize("url", [
        "https://www.google.com",
        "http://localhost:8080",
        "C:\\Users\\archivo.pdf",
        "/home/user/doc.pdf",
    ])
    def test_urls_validas(self, url):
        ok, _ = is_url()(url)
        assert ok is True

    @pytest.mark.parametrize("url", [
        "sin-protocolo.com",
        "",
        None,
    ])
    def test_urls_invalidas(self, url):
        ok, _ = is_url()(url)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# is_valid_coordinates
# ─────────────────────────────────────────────────────────────────────────────

class TestIsValidCoordinates:
    def test_coordenadas_validas(self):
        ok, _ = is_valid_coordinates()((40.4168, -3.7038))
        assert ok is True

    def test_coordenadas_extremas_validas(self):
        ok, _ = is_valid_coordinates()((90.0, 180.0))
        assert ok is True
        ok, _ = is_valid_coordinates()((-90.0, -180.0))
        assert ok is True

    def test_latitud_fuera_de_rango(self):
        ok, msg = is_valid_coordinates()((91.0, 0.0))
        assert ok is False
        assert "rango" in msg.lower()

    def test_longitud_fuera_de_rango(self):
        ok, _ = is_valid_coordinates()((0.0, 181.0))
        assert ok is False

    def test_no_es_tupla(self):
        ok, _ = is_valid_coordinates()("40.4, -3.7")
        assert ok is False

    def test_valores_no_numericos(self):
        ok, _ = is_valid_coordinates()(("lat", "lon"))
        assert ok is False

    def test_tupla_longitud_incorrecta(self):
        ok, _ = is_valid_coordinates()((40.0,))
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# is_in_range
# ─────────────────────────────────────────────────────────────────────────────

class TestIsInRange:
    def test_dentro_del_rango(self):
        ok, _ = is_in_range(1, 10)(5)
        assert ok is True

    def test_en_el_limite_inferior(self):
        ok, _ = is_in_range(1, 10)(1)
        assert ok is True

    def test_en_el_limite_superior(self):
        ok, _ = is_in_range(1, 10)(10)
        assert ok is True

    def test_por_debajo_del_minimo(self):
        ok, msg = is_in_range(1, 10)(0)
        assert ok is False
        assert "1" in msg

    def test_por_encima_del_maximo(self):
        ok, msg = is_in_range(1, 10)(11)
        assert ok is False
        assert "10" in msg

    def test_solo_minimo(self):
        ok, _ = is_in_range(min_val=0)(100)
        assert ok is True

    def test_solo_maximo(self):
        ok, _ = is_in_range(max_val=5)(6)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# is_duration_valid
# ─────────────────────────────────────────────────────────────────────────────

class TestIsDurationValid:
    def test_duracion_valida(self):
        ok, _ = is_duration_valid()(6)
        assert ok is True

    def test_duracion_minima(self):
        ok, _ = is_duration_valid()(1)
        assert ok is True

    def test_duracion_maxima(self):
        ok, _ = is_duration_valid()(12)
        assert ok is True

    def test_duracion_cero_invalida(self):
        ok, _ = is_duration_valid()(0)
        assert ok is False

    def test_duracion_13_invalida(self):
        ok, _ = is_duration_valid()(13)
        assert ok is False

    def test_string_numerico(self):
        ok, _ = is_duration_valid()("6")
        assert ok is True

    def test_no_numerico(self):
        ok, _ = is_duration_valid()("meses")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# is_course_valid / is_semester_valid
# ─────────────────────────────────────────────────────────────────────────────

class TestIsCourseValid:
    @pytest.mark.parametrize("curso", [1, 2, 3, 4])
    def test_cursos_validos(self, curso):
        ok, _ = is_course_valid()(curso)
        assert ok is True

    def test_curso_cero_invalido(self):
        ok, _ = is_course_valid()(0)
        assert ok is False

    def test_curso_cinco_invalido(self):
        ok, _ = is_course_valid()(5)
        assert ok is False


class TestIsSemesterValid:
    def test_primer_cuatrimestre(self):
        ok, _ = is_semester_valid()(1)
        assert ok is True

    def test_segundo_cuatrimestre(self):
        ok, _ = is_semester_valid()(2)
        assert ok is True

    def test_tercer_cuatrimestre_invalido(self):
        ok, _ = is_semester_valid()(3)
        assert ok is False

    def test_cero_invalido(self):
        ok, _ = is_semester_valid()(0)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# matches_pattern
# ─────────────────────────────────────────────────────────────────────────────

class TestMatchesPattern:
    def test_patron_valido(self):
        ok, _ = matches_pattern(r"^\d{4}-\d{4}$")("2024-2025")
        assert ok is True

    def test_patron_invalido(self):
        ok, msg = matches_pattern(r"^\d{4}-\d{4}$", "año académico")("abc")
        assert ok is False
        assert "año académico" in msg

    def test_valor_vacio(self):
        ok, _ = matches_pattern(r"^\d+$")("")
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# is_one_of
# ─────────────────────────────────────────────────────────────────────────────

class TestIsOneOf:
    def test_valor_permitido(self):
        ok, _ = is_one_of("A", "B", "C")("B")
        assert ok is True

    def test_valor_no_permitido(self):
        ok, msg = is_one_of("A", "B", "C")("D")
        assert ok is False
        assert "A" in msg

    def test_case_insensitive(self):
        ok, _ = is_one_of("erasmus out", "sicue", case_insensitive=True)("ERASMUS OUT")
        assert ok is True

    def test_case_sensitive_por_defecto(self):
        ok, _ = is_one_of("Erasmus OUT")("erasmus out")
        assert ok is False
