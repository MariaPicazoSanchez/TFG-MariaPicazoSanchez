"""
Tipos, protocolos y factories de validadores individuales.

Exporta:
  Tipos:    Validator, Normalizer, FieldRule
  Factories: is_not_empty, is_email, is_url, is_path, is_valid_coordinates,
             is_in_range, is_duration_valid, is_course_valid, is_semester_valid,
             matches_pattern, is_one_of
"""


import re
from dataclasses import dataclass
from typing import Any, Protocol

from ._converters import safe_int_convert, safe_float_convert


# ─────────────────────────────────────────────────────────────────────────────
# Tipos y protocolos
# ─────────────────────────────────────────────────────────────────────────────

class Validator(Protocol):
    """Protocolo para validadores."""
    def __call__(self, value: Any) -> tuple[bool, str]: ...


class Normalizer(Protocol):
    """Protocolo para normalizadores."""
    def __call__(self, value: Any) -> Any: ...


@dataclass
class FieldRule:
    """Define validación y normalización para un campo."""
    name: str
    validators: list[Validator]
    normalizers: list[Normalizer] | None = None
    required: bool = False
    label: str | None = None

    def __post_init__(self):
        if self.normalizers is None:
            self.normalizers = []
        if self.label is None:
            self.label = self.name.replace("_", " ").title()


# ─────────────────────────────────────────────────────────────────────────────
# Factories de validadores
# ─────────────────────────────────────────────────────────────────────────────

def is_not_empty() -> Validator:
    """Valida que no esté vacío."""
    def validator(value: Any) -> tuple[bool, str]:
        is_valid = bool(value.strip()) if isinstance(value, str) else bool(value)
        return is_valid, "" if is_valid else "Campo vacío"
    return validator


def is_email() -> Validator:
    """Valida formato de email."""
    _pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    def validator(value: Any) -> tuple[bool, str]:
        if not value or not isinstance(value, str):
            return False, "Email vacío"
        is_valid = bool(_pattern.match(value.strip()))
        return is_valid, "" if is_valid else "Formato de email inválido"
    return validator


def is_url() -> Validator:
    """Valida URL válida (http/https o ruta local)."""
    def validator(value: Any) -> tuple[bool, str]:
        if not value or not isinstance(value, str):
            return False, "URL vacía"
        s = value.strip().lower()
        is_valid = s.startswith(("http://", "https://", "c:\\", "d:\\", "/")) or "://" in s
        return is_valid, "" if is_valid else "URL no válida"
    return validator


def is_path() -> Validator:
    """Valida si la ruta parece válida."""
    def validator(value: Any) -> tuple[bool, str]:
        if not value or not isinstance(value, str):
            return False, "Ruta vacía"
        s = value.strip()
        is_valid = s.startswith(("/", "c:\\", "d:\\", "~", "http://", "https://"))
        return is_valid, "" if is_valid else "Ruta no válida"
    return validator


def is_valid_coordinates() -> Validator:
    """Valida si coordenadas son válidas."""
    def validator(value: Any) -> tuple[bool, str]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            return False, "Coordenadas deben ser tupla (lat, lon)"
        try:
            lat, lon = float(value[0]), float(value[1])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                return False, "Coordenadas fuera de rango"
            return True, ""
        except (ValueError, TypeError):
            return False, "Coordenadas no numéricas"
    return validator


def is_in_range(min_val: int | float | None = None, max_val: int | float | None = None) -> Validator:
    """Valida que un número esté en rango."""
    def validator(value: Any) -> tuple[bool, str]:
        try:
            num = safe_float_convert(value) if (max_val is not None or min_val is not None) else None
            if num is None:
                return False, "Valor no numérico"
            if min_val is not None and num < min_val:
                return False, f"Menor que {min_val}"
            if max_val is not None and num > max_val:
                return False, f"Mayor que {max_val}"
            return True, ""
        except (ValueError, TypeError):
            return False, "Valor no numérico"
    return validator


def is_duration_valid(min_months: int = 1, max_months: int = 12) -> Validator:
    """Valida duración en meses."""
    def validator(value: Any) -> tuple[bool, str]:
        num = safe_int_convert(value)
        if num is None:
            return False, "Duración no es número"
        if not (min_months <= num <= max_months):
            return False, f"Duración fuera de rango {min_months}-{max_months} meses"
        return True, ""
    return validator


def is_course_valid(min_course: int = 1, max_course: int = 4) -> Validator:
    """Valida número de curso."""
    def validator(value: Any) -> tuple[bool, str]:
        num = safe_int_convert(value)
        if num is None:
            return False, "Curso no es número"
        if not (min_course <= num <= max_course):
            return False, f"Curso fuera de rango {min_course}-{max_course}"
        return True, ""
    return validator


def is_semester_valid(min_semester: int = 1, max_semester: int = 2) -> Validator:
    """Valida número de cuatrimestre."""
    def validator(value: Any) -> tuple[bool, str]:
        num = safe_int_convert(value)
        if num is None:
            return False, "Cuatrimestre no es número"
        if not (min_semester <= num <= max_semester):
            return False, f"Cuatrimestre fuera de rango {min_semester}-{max_semester}"
        return True, ""
    return validator


def matches_pattern(pattern: str, description: str = "") -> Validator:
    """Valida contra patrón regex."""
    _compiled = re.compile(pattern)

    def validator(value: Any) -> tuple[bool, str]:
        if not value:
            return False, "Valor vacío"
        is_valid = bool(_compiled.match(str(value)))
        msg = f"No coincide con patrón {description}" if description else "Patrón inválido"
        return is_valid, "" if is_valid else msg
    return validator


def is_one_of(*allowed_values: Any, case_insensitive: bool = False) -> Validator:
    """Valida que esté en lista de valores permitidos."""
    def validator(value: Any) -> tuple[bool, str]:
        check_val = value.lower() if case_insensitive and isinstance(value, str) else value
        check_allowed = [
            v.lower() if case_insensitive and isinstance(v, str) else v
            for v in allowed_values
        ]
        if check_val in check_allowed:
            return True, ""
        return False, f"Debe ser uno de: {', '.join(str(v) for v in allowed_values)}"
    return validator
