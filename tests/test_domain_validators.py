"""
Tests para domain/validators.py

Cubre: DataValidator, get_converter, safe_get_nested,
       get_student_form_schema, get_erasmus_out_schema, get_erasmus_in_schema,
       get_sicue_out_schema, create_contextual_validator
"""
import pytest
from domain.validators import (
    DataValidator,
    get_converter,
    safe_get_nested,
    get_student_form_schema,
    get_erasmus_out_schema,
    get_erasmus_in_schema,
    get_sicue_out_schema,
    create_contextual_validator,
)
from domain._validator_rules import FieldRule, is_not_empty, is_email
from domain._converters import normalize_string


# ─────────────────────────────────────────────────────────────────────────────
# DataValidator — básicos
# ─────────────────────────────────────────────────────────────────────────────

class TestDataValidatorBasics:
    def test_inicialmente_valido_sin_schema(self):
        dv = DataValidator()
        assert dv.is_valid() is True

    def test_inicialmente_sin_errores(self):
        dv = DataValidator()
        assert dv.get_errors() == {}

    def test_inicialmente_sin_datos_limpios(self):
        dv = DataValidator()
        assert dv.get_clean_data() == {}

    def test_add_rule_añade_al_schema(self):
        dv = DataValidator()
        rule = FieldRule("campo", [is_not_empty()], required=True)
        dv.add_rule(rule)
        assert "campo" in dv.field_rules

    def test_get_error_messages_vacio_cuando_sin_errores(self):
        dv = DataValidator()
        assert dv.get_error_messages() == ""

    def test_get_error_messages_formato(self):
        dv = DataValidator()
        dv._add_error("nombre", "Campo vacío")
        msg = dv.get_error_messages()
        assert "nombre" in msg
        assert "Campo vacío" in msg

    def test_get_field_value_inexistente(self):
        dv = DataValidator()
        assert dv.get_field_value("no_existe") is None


# ─────────────────────────────────────────────────────────────────────────────
# DataValidator.validate_field
# ─────────────────────────────────────────────────────────────────────────────

class TestDataValidatorValidateField:
    def test_campo_valido_sin_validadores(self):
        dv = DataValidator()
        ok = dv.validate_field("nombre", "Ana")
        assert ok is True
        assert dv.get_field_value("nombre") == "Ana"

    def test_campo_requerido_vacio_falla(self):
        dv = DataValidator()
        ok = dv.validate_field("nombre", "", required=True)
        assert ok is False
        assert "nombre" in dv.errors

    def test_campo_requerido_con_valor_pasa(self):
        dv = DataValidator()
        ok = dv.validate_field("nombre", "Ana", required=True)
        assert ok is True

    def test_validador_invalido_añade_error(self):
        dv = DataValidator()
        ok = dv.validate_field("email", "no-es-email", validators=[is_email()])
        assert ok is False
        assert "email" in dv.errors

    def test_validador_valido_guarda_limpio(self):
        dv = DataValidator()
        ok = dv.validate_field("email", "test@example.com", validators=[is_email()])
        assert ok is True
        assert dv.get_field_value("email") == "test@example.com"

    def test_normalizador_aplicado(self):
        dv = DataValidator()
        dv.validate_field("nombre", "  Ana  ", normalizers=[normalize_string])
        assert dv.get_field_value("nombre") == "Ana"

    def test_normalizador_singular_compat(self):
        dv = DataValidator()
        dv.validate_field("nombre", "  Hola  ", normalizer=normalize_string)
        assert dv.get_field_value("nombre") == "Hola"

    def test_validador_como_callable_no_tuple(self):
        def mi_val(v):
            return bool(v)
        dv = DataValidator()
        ok = dv.validate_field("campo", "algo", validators=[mi_val])
        assert ok is True

    def test_validador_como_callable_retorna_false(self):
        def mi_val(v):
            return False
        dv = DataValidator()
        ok = dv.validate_field("campo", "algo", validators=[mi_val])
        assert ok is False

    def test_no_duplica_errores(self):
        dv = DataValidator()
        dv._add_error("nombre", "Campo vacío")
        dv._add_error("nombre", "Campo vacío")
        assert len(dv.errors["nombre"]) == 1

    def test_campo_vacio_no_requerido_se_salta_validadores(self):
        dv = DataValidator()
        ok = dv.validate_field("email", "", validators=[is_email()], required=False)
        # valor vacío + not required → no se llama al validador → True
        assert ok is True

    def test_errores_acumulados_multiples_campos(self):
        dv = DataValidator()
        dv.validate_field("a", "", required=True)
        dv.validate_field("b", "", required=True)
        assert len(dv.errors) == 2
        assert dv.is_valid() is False


# ─────────────────────────────────────────────────────────────────────────────
# DataValidator.validate_schema
# ─────────────────────────────────────────────────────────────────────────────

class TestDataValidatorValidateSchema:
    def test_schema_valido_pasa(self):
        schema = [
            FieldRule("nombre", [is_not_empty()], required=True),
            FieldRule("email", [is_email()], required=True),
        ]
        dv = DataValidator(schema)
        ok = dv.validate_schema({"nombre": "Ana", "email": "ana@test.com"})
        assert ok is True

    def test_schema_invalido_falla(self):
        schema = [FieldRule("nombre", [is_not_empty()], required=True)]
        dv = DataValidator(schema)
        ok = dv.validate_schema({"nombre": ""})
        assert ok is False

    def test_campo_faltante_en_data_tratado_como_none(self):
        schema = [FieldRule("nombre", [is_not_empty()], required=True)]
        dv = DataValidator(schema)
        ok = dv.validate_schema({})
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# DataValidator.validate_batch
# ─────────────────────────────────────────────────────────────────────────────

class TestDataValidatorValidateBatch:
    def test_batch_valido(self):
        dv = DataValidator()
        config = {
            "nombre": {"validators": [is_not_empty()], "required": True},
        }
        ok = dv.validate_batch({"nombre": "Luis"}, config)
        assert ok is True

    def test_batch_invalido(self):
        dv = DataValidator()
        config = {
            "nombre": {"validators": [is_not_empty()], "required": True},
        }
        ok = dv.validate_batch({"nombre": ""}, config)
        assert ok is False


# ─────────────────────────────────────────────────────────────────────────────
# get_converter
# ─────────────────────────────────────────────────────────────────────────────

class TestGetConverter:
    def test_converter_int(self):
        conv = get_converter("int")
        assert conv("5") == 5

    def test_converter_float(self):
        conv = get_converter("float")
        assert conv("3.14") == pytest.approx(3.14)

    def test_converter_bool_true(self):
        conv = get_converter("bool")
        assert conv("yes") is True

    def test_converter_bool_false(self):
        conv = get_converter("bool")
        assert conv("no") is False

    def test_converter_str(self):
        conv = get_converter("str")
        assert conv("  hola  ") == "hola"

    def test_converter_desconocido_usa_normalize_string(self):
        conv = get_converter("desconocido")
        assert conv("  test  ") == "test"


# ─────────────────────────────────────────────────────────────────────────────
# safe_get_nested
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeGetNested:
    def test_clave_simple(self):
        d = {"a": 1}
        assert safe_get_nested(d, "a") == 1

    def test_clave_anidada(self):
        d = {"a": {"b": {"c": 42}}}
        assert safe_get_nested(d, "a", "b", "c") == 42

    def test_clave_inexistente_devuelve_default(self):
        d = {"a": 1}
        assert safe_get_nested(d, "x") is None

    def test_clave_inexistente_con_default_personalizado(self):
        d = {}
        assert safe_get_nested(d, "x", default="N/A") == "N/A"

    def test_ruta_parcial_inexistente(self):
        d = {"a": {"b": 5}}
        assert safe_get_nested(d, "a", "z") is None

    def test_valor_none_devuelve_default(self):
        d = {"a": None}
        assert safe_get_nested(d, "a", default="fallback") == "fallback"

    def test_valor_intermedio_no_dict(self):
        d = {"a": "string"}
        assert safe_get_nested(d, "a", "b") is None


# ─────────────────────────────────────────────────────────────────────────────
# Esquemas predefinidos
# ─────────────────────────────────────────────────────────────────────────────

class TestEsquemasPredefinidos:
    def test_student_form_schema_tiene_campos_obligatorios(self):
        schema = get_student_form_schema()
        names = [r.name for r in schema]
        assert "nombre" in names
        assert "apellidos" in names
        assert "email" in names

    def test_erasmus_out_schema_incluye_pais_y_curso(self):
        schema = get_erasmus_out_schema()
        names = [r.name for r in schema]
        assert "pais" in names
        assert "curso" in names

    def test_erasmus_in_schema_incluye_pais(self):
        schema = get_erasmus_in_schema()
        names = [r.name for r in schema]
        assert "pais" in names

    def test_sicue_out_schema_incluye_ciudad(self):
        schema = get_sicue_out_schema()
        names = [r.name for r in schema]
        assert "ciudad" in names

    def test_todos_los_schemas_son_listas(self):
        for fn in [get_student_form_schema, get_erasmus_out_schema,
                   get_erasmus_in_schema, get_sicue_out_schema]:
            assert isinstance(fn(), list)

    def test_erasmus_out_mayor_o_igual_que_base(self):
        base = get_student_form_schema()
        out = get_erasmus_out_schema()
        assert len(out) >= len(base)


# ─────────────────────────────────────────────────────────────────────────────
# create_contextual_validator
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateContextualValidator:
    def test_devuelve_el_callable(self):
        def mi_val(d):
            return (True, "")
        result = create_contextual_validator(mi_val)
        assert callable(result)
        assert result({"a": 1}) == (True, "")
