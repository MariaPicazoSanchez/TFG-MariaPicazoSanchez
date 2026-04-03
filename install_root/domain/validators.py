"""
Módulo centralizado de validadores y conversores de datos.
Framework modular y composable para validación consistente en toda la app.

Los tipos, factories y conversores viven en submódulos privados;
este módulo los re-exporta para compatibilidad hacia atrás y añade:
  - DataValidator  — clase de validación en lote con acumulación de errores
  - Esquemas predefinidos por programa (get_student_form_schema, etc.)
  - Utilidades auxiliares (create_contextual_validator, get_converter, safe_get_nested)
"""

from __future__ import annotations

from typing import Any, Callable

# Re-exports — compatibilidad con imports externos existentes
from ._converters import (  # noqa: F401
    compose_normalizers,
    normalize_email,
    normalize_int,
    normalize_lower,
    normalize_phone,
    normalize_string,
    safe_bool_convert,
    safe_float_convert,
    safe_int_convert,
    safe_int_to_str,
)
from ._validator_rules import (  # noqa: F401
    FieldRule,
    Normalizer,
    Validator,
    is_course_valid,
    is_duration_valid,
    is_email,
    is_in_range,
    is_not_empty,
    is_one_of,
    is_path,
    is_semester_valid,
    is_url,
    is_valid_coordinates,
    matches_pattern,
)


# ─────────────────────────────────────────────────────────────────────────────
# DataValidator — validación en lote con acumulación de errores
# ─────────────────────────────────────────────────────────────────────────────

class DataValidator:
    """Framework para validación en lotes con acumulación de errores."""

    def __init__(self, schema: list[FieldRule] | None = None):
        self.schema = schema or []
        self.errors: dict[str, list[str]] = {}
        self.cleaned_data: dict[str, Any] = {}
        self.field_rules: dict[str, FieldRule] = {rule.name: rule for rule in self.schema}

    def add_rule(self, rule: FieldRule) -> None:
        self.schema.append(rule)
        self.field_rules[rule.name] = rule

    def validate_field(
        self,
        field_name: str,
        value: Any,
        validators: list[Validator] | Validator | None = None,
        normalizers: list[Normalizer] | Normalizer | None = None,
        required: bool = False,
        normalizer: Normalizer | None = None,
    ) -> bool:
        # Compatibilidad: si se pasa `normalizer` singular
        if normalizer is not None and normalizers is None:
            normalizers = normalizer

        if validators is None:
            validators = []
        elif not isinstance(validators, list):
            validators = [validators]

        if normalizers is None:
            normalizers = []
        elif not isinstance(normalizers, list):
            normalizers = [normalizers]

        try:
            if required:
                is_empty_val, is_empty_msg = is_not_empty()(value)
                if not is_empty_val:
                    self._add_error(field_name, is_empty_msg)
                    return False

            if value or required:
                for validator in validators:
                    result = validator(value)
                    if isinstance(result, tuple):
                        is_valid, msg = result
                    else:
                        is_valid = bool(result)
                        msg = "Valor inválido" if not is_valid else ""
                    if not is_valid:
                        self._add_error(field_name, msg)
                        return False

            if not self.errors.get(field_name):
                normalized = value
                for norm in normalizers:
                    normalized = norm(normalized)
                self.cleaned_data[field_name] = normalized

            return True
        except Exception as e:
            self._add_error(field_name, f"Error: {e}")
            return False

    def validate_schema(self, data: dict) -> bool:
        for rule in self.schema:
            self.validate_field(
                field_name=rule.name,
                value=data.get(rule.name),
                validators=rule.validators,
                normalizers=rule.normalizers,
                required=rule.required,
            )
        return self.is_valid()

    def validate_batch(self, data: dict, field_configs: dict[str, dict]) -> bool:
        for field_name, config in field_configs.items():
            self.validate_field(
                field_name=field_name,
                value=data.get(field_name),
                validators=config.get("validators", []),
                normalizers=config.get("normalizers", []),
                required=config.get("required", False),
            )
        return self.is_valid()

    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def _add_error(self, field_name: str, message: str) -> None:
        if field_name not in self.errors:
            self.errors[field_name] = []
        if message and message not in self.errors[field_name]:
            self.errors[field_name].append(message)

    def get_errors(self) -> dict[str, list[str]]:
        return self.errors.copy()

    def get_error_messages(self) -> str:
        if not self.errors:
            return ""
        lines = [f"  • {field}: {'; '.join(msgs)}" for field, msgs in self.errors.items()]
        return "Errores encontrados:\n" + "\n".join(lines)

    def get_clean_data(self) -> dict[str, Any]:
        return self.cleaned_data.copy()

    def get_field_value(self, field_name: str) -> Any:
        return self.cleaned_data.get(field_name)


# ─────────────────────────────────────────────────────────────────────────────
# Esquemas predefinidos
# ─────────────────────────────────────────────────────────────────────────────

def get_student_form_schema() -> list[FieldRule]:
    """Esquema base para formulario de estudiante."""
    return [
        FieldRule("nombre",         [is_not_empty()], [normalize_string], required=True,  label="Nombre"),
        FieldRule("apellidos",      [is_not_empty()], [normalize_string], required=True,  label="Apellidos"),
        FieldRule("email",          [is_email()],     [normalize_email],  required=True,  label="Email"),
        FieldRule("destino_origen", [is_not_empty()], [normalize_string], required=True,  label="Destino/Origen"),
        FieldRule("duracion_meses", [is_duration_valid()], [normalize_int], required=False, label="Duración (meses)"),
    ]


def get_erasmus_out_schema() -> list[FieldRule]:
    return get_student_form_schema() + [
        FieldRule("pais",   [is_not_empty()],    [normalize_string], required=True,  label="País"),
        FieldRule("curso",  [is_course_valid()], [normalize_int],    required=False, label="Curso"),
    ]


def get_erasmus_in_schema() -> list[FieldRule]:
    return get_student_form_schema() + [
        FieldRule("pais", [is_not_empty()], [normalize_string], required=True, label="País"),
    ]


def get_sicue_out_schema() -> list[FieldRule]:
    return get_student_form_schema() + [
        FieldRule("ciudad", [is_not_empty()], [normalize_string], required=True, label="Ciudad"),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────────────────

def create_contextual_validator(context_validator: Callable[[dict], tuple[bool, str]]) -> Validator:
    """Crea validador que depende de otros campos (contextual)."""
    return context_validator


def get_converter(target_type: str) -> Callable:
    """Devuelve el conversor apropiado según tipo ('int', 'float', 'bool', 'str')."""
    converters = {
        "int":   normalize_int,
        "float": lambda x: safe_float_convert(x),
        "bool":  safe_bool_convert,
        "str":   normalize_string,
    }
    return converters.get(target_type, normalize_string)


def safe_get_nested(data: dict, *keys: str, default: Any = None) -> Any:
    """Obtiene valor anidado de diccionario de forma segura."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    return current if current is not None else default
