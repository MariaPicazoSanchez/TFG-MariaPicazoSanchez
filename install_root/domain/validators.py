"""
Módulo centralizado de validadores y conversores de datos.
Framework modular y composable para validación consistente en toda la app.

Características:
- Validadores reutilizables con mensajes contextuales
- Composición de normalización
- Esquemas de validación declarativos
- Validación en lote eficiente
- Soporte para validación contextual (dependencias entre campos)
"""

from __future__ import annotations

import re
from typing import Any, Callable, Protocol
from dataclasses import dataclass


# ============================================
# TIPOS Y PROTOCOLOS
# ============================================

class Validator(Protocol):
    """Protocolo para validadores."""
    def __call__(self, value: Any) -> tuple[bool, str]:
        """Valida un valor. Devuelve (es_valido, mensaje_error)."""
        ...


class Normalizer(Protocol):
    """Protocolo para normalizadores."""
    def __call__(self, value: Any) -> Any:
        """Normaliza un valor."""
        ...


@dataclass
class FieldRule:
    """Define validación y normalización para un campo."""
    name: str
    validators: list[Validator]  # Se ejecutan en orden
    normalizers: list[Normalizer] | None = None  # Se ejecutan en orden
    required: bool = False
    label: str | None = None  # Nombre amigable para mensajes de error
    
    def __post_init__(self):
        if self.normalizers is None:
            self.normalizers = []
        if self.label is None:
            self.label = self.name.replace("_", " ").title()


# ============================================
# CONVERSORES NUMÉRICOS
# ============================================

def safe_int_convert(value: Any, default: int | None = None) -> int | None:
    """
    Convierte a entero desde string/float, tolerando formatos variados.
    
    Args:
        value: Valor a convertir (str, float, int, etc.)
        default: Valor por defecto si la conversión falla (entero o None)
        
    Returns:
        Número entero, None si falla y no hay default
        
    Ejemplos:
        safe_int_convert("3.0") -> 3
        safe_int_convert("abc", default=0) -> 0
        safe_int_convert("1.5") -> 1
    """
    try:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            return default
        val_str = str(value).strip()
        try:
            return int(val_str)
        except ValueError:
            return int(float(val_str))
    except (ValueError, TypeError, AttributeError):
        return default


def safe_int_to_str(value: Any, default: str = "") -> str:
    """
    Convierte a entero y luego a string (seguro para HTML/display).
    
    Args:
        value: Valor a convertir
        default: String por defecto si falla
        
    Returns:
        String con el entero, o default si falla
        
    Ejemplos:
        safe_int_to_str("3.0") -> "3"
        safe_int_to_str("abc") -> ""
    """
    result = safe_int_convert(value, default=None)
    return str(result) if result is not None else default


def safe_float_convert(value: Any, default: float = 0.0) -> float:
    """Convierte a float de forma segura."""
    try:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool_convert(value: Any, default: bool = False) -> bool:
    """Convierte a booleano de forma segura."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        val_lower = value.strip().lower()
        true_vals = {'sí', 'yes', 'true', 'x', 'v', '1'}
        false_vals = {'no', 'false', '', '0'}
        if val_lower in true_vals:
            return True
        if val_lower in false_vals:
            return False
    return default


# ============================================
# NORMALIZADORES
# ============================================

def normalize_string(value: Any) -> str:
    """Normaliza a string (trim, strip)."""
    return str(value or "").strip()


def normalize_lower(value: Any) -> str:
    """Normaliza a string minúsculas."""
    return normalize_string(value).lower()


def normalize_email(value: Any) -> str:
    """Normaliza email: lower + trim."""
    return normalize_lower(value)


def normalize_int(value: Any, default: int = 0) -> int:
    """Normaliza a entero."""
    return safe_int_convert(value, default=default) or default


def normalize_phone(value: Any) -> str:
    """Normaliza teléfono: solo dígitos."""
    s = str(value or "").strip()
    return "".join(c for c in s if c.isdigit())


def compose_normalizers(*normalizers: Normalizer) -> Normalizer:
    """Compone múltiples normalizadores en uno solo."""
    def composed(value: Any) -> Any:
        for norm in normalizers:
            value = norm(value)
        return value
    return composed


# ============================================
# VALIDADORES SIMPLES (FACTORY)
# ============================================

def is_not_empty() -> Validator:
    """Valida que no esté vacío."""
    def validator(value: Any) -> tuple[bool, str]:
        if isinstance(value, str):
            is_valid = bool(value.strip())
        else:
            is_valid = bool(value)
        return is_valid, "Campo vacío" if not is_valid else ""
    return validator


def is_email() -> Validator:
    """Valida formato de email."""
    def validator(value: Any) -> tuple[bool, str]:
        if not value or not isinstance(value, str):
            return False, "Email vacío"
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(pattern, value.strip()))
        return is_valid, "Formato de email inválido" if not is_valid else ""
    return validator


def is_url() -> Validator:
    """Valida URL válida (http/https o ruta local)."""
    def validator(value: Any) -> tuple[bool, str]:
        if not value or not isinstance(value, str):
            return False, "URL vacía"
        url_str = value.strip().lower()
        is_valid = (url_str.startswith(('http://', 'https://', 'c:\\', 'd:\\', '/')) or 
                   '://' in url_str)
        return is_valid, "URL no válida" if not is_valid else ""
    return validator


def is_path() -> Validator:
    """Valida si la ruta parece válida."""
    def validator(value: Any) -> tuple[bool, str]:
        if not value or not isinstance(value, str):
            return False, "Ruta vacía"
        path_str = value.strip()
        is_valid = (path_str.startswith(('/', 'c:\\', 'd:\\', '~')) or
                   path_str.startswith(('http://', 'https://')))
        return is_valid, "Ruta no válida" if not is_valid else ""
    return validator


def is_valid_coordinates() -> Validator:
    """Valida si coordenadas son válidas."""
    def validator(value: Any) -> tuple[bool, str]:
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            return False, "Coordenadas deben ser tupla (lat, lon)"
        try:
            lat = float(value[0])
            lon = float(value[1])
            is_valid = -90 <= lat <= 90 and -180 <= lon <= 180
            if not is_valid:
                return False, "Coordenadas fuera de rango"
            return True, ""
        except (ValueError, TypeError):
            return False, "Coordenadas no numéricas"
    return validator


def is_in_range(min_val: int | float | None = None, max_val: int | float | None = None) -> Validator:
    """Valida que un número esté en rango."""
    def validator(value: Any) -> tuple[bool, str]:
        try:
            num = safe_float_convert(value) if max_val or min_val else None
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
    def validator(value: Any) -> tuple[bool, str]:
        if not value:
            return False, "Valor vacío"
        is_valid = bool(re.match(pattern, str(value)))
        msg = f"No coincide con patrón {description}" if description else "Patrón inválido"
        return is_valid, msg if not is_valid else ""
    return validator


def is_one_of(*allowed_values: Any, case_insensitive: bool = False) -> Validator:
    """Valida que esté en lista de valores permitidos."""
    def validator(value: Any) -> tuple[bool, str]:
        check_val = value.lower() if case_insensitive and isinstance(value, str) else value
        check_allowed = [v.lower() if case_insensitive and isinstance(v, str) else v 
                        for v in allowed_values]
        is_valid = check_val in check_allowed
        if not is_valid:
            return False, f"Debe ser uno de: {', '.join(str(v) for v in allowed_values)}"
        return True, ""
    return validator


# ============================================
# VALIDACIÓN EN LOTE
# ============================================

class DataValidator:
    """Framework para validación en lotes con acumulación de errores."""
    
    def __init__(self, schema: list[FieldRule] | None = None):
        """
        Inicializa validador.
        
        Args:
            schema: Lista de FieldRule que define la validación
        """
        self.schema = schema or []
        self.errors: dict[str, list[str]] = {}
        self.cleaned_data: dict[str, Any] = {}
        self.field_rules: dict[str, FieldRule] = {rule.name: rule for rule in self.schema}
    
    def add_rule(self, rule: FieldRule) -> None:
        """Agrega una regla de validación."""
        self.schema.append(rule)
        self.field_rules[rule.name] = rule
    
    def validate_field(self, field_name: str, value: Any, 
                      validators: list[Validator] | Validator | None = None,
                      normalizers: list[Normalizer] | Normalizer | None = None,
                      required: bool = False,
                      normalizer: Normalizer | None = None) -> bool:
        """
        Valida un campo individual.
        
        Args:
            field_name: Nombre del campo
            value: Valor a validar
            validators: Validador(es) a aplicar
            normalizers: Normalizador(es) a aplicar
            required: Si es campo requerido
            
        Returns:
            True si válido, False si no
        """
        # Compatibilidad: si se pasa `normalizer`, lo tratamos como `normalizers`
        if normalizer is not None and normalizers is None:
            normalizers = normalizer

        # Convertir a listas si es necesario
        if validators is None:
            validators = []
        elif not isinstance(validators, list):
            validators = [validators]
        
        if normalizers is None:
            normalizers = []
        elif not isinstance(normalizers, list):
            normalizers = [normalizers]
        
        # Validar
        try:
            # Si requerido y vacío
            if required:
                is_empty_val, is_empty_msg = is_not_empty()(value)
                if not is_empty_val:
                    self._add_error(field_name, is_empty_msg)
                    return False
            
            # Si no es vacío (o requerido pero pasó vacío), ejecutar validadores
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
            
            # Normalizar si válido
            if not self.errors.get(field_name):
                normalized = value
                for normalizer in normalizers:
                    normalized = normalizer(normalized)
                self.cleaned_data[field_name] = normalized
            
            return True
        except Exception as e:
            self._add_error(field_name, f"Error: {str(e)}")
            return False
    
    def validate_schema(self, data: dict) -> bool:
        """
        Valida datos contra esquema definido.
        
        Args:
            data: Diccionario con datos a validar
            
        Returns:
            True si todos los campos válidos
        """
        for rule in self.schema:
            value = data.get(rule.name)
            self.validate_field(
                field_name=rule.name,
                value=value,
                validators=rule.validators,
                normalizers=rule.normalizers,
                required=rule.required
            )
        return self.is_valid()
    
    def validate_batch(self, data: dict, field_configs: dict[str, dict]) -> bool:
        """
        Valida en lote con configuración dinámica.
        
        Formato de field_configs:
        {
            "email": {
                "validators": [is_email()],
                "normalizers": [normalize_email],
                "required": True
            },
            "duration": {
                "validators": [is_duration_valid()],
                "normalizers": [normalize_int],
                "required": False
            }
        }
        
        Args:
            data: Datos a validar
            field_configs: Configuración de campos
            
        Returns:
            True si válido
        """
        for field_name, config in field_configs.items():
            value = data.get(field_name)
            self.validate_field(
                field_name=field_name,
                value=value,
                validators=config.get("validators", []),
                normalizers=config.get("normalizers", []),
                required=config.get("required", False)
            )
        return self.is_valid()
    
    def is_valid(self) -> bool:
        """Devuelve True si no hay errores."""
        return len(self.errors) == 0
    
    def _add_error(self, field_name: str, message: str) -> None:
        """Agrega error para un campo."""
        if field_name not in self.errors:
            self.errors[field_name] = []
        if message and message not in self.errors[field_name]:
            self.errors[field_name].append(message)
    
    def get_errors(self) -> dict[str, list[str]]:
        """Devuelve todos los errores acumulados."""
        return self.errors.copy()
    
    def get_error_messages(self) -> str:
        """Devuelve mensajes de error formateados."""
        if not self.errors:
            return ""
        lines = []
        for field, msgs in self.errors.items():
            lines.append(f"  • {field}: {'; '.join(msgs)}")
        return "Errores encontrados:\n" + "\n".join(lines)
    
    def get_clean_data(self) -> dict[str, Any]:
        """Devuelve datos validados y normalizados."""
        return self.cleaned_data.copy()
    
    def get_field_value(self, field_name: str) -> Any:
        """Obtiene valor normalizado de un campo."""
        return self.cleaned_data.get(field_name)


# ============================================
# ESQUEMAS PREDEFINIDOS
# ============================================

def get_student_form_schema() -> list[FieldRule]:
    """Esquema para validación de formulario de estudiante."""
    return [
        FieldRule(
            name="nombre",
            validators=[is_not_empty()],
            normalizers=[normalize_string],
            required=True,
            label="Nombre"
        ),
        FieldRule(
            name="apellidos",
            validators=[is_not_empty()],
            normalizers=[normalize_string],
            required=True,
            label="Apellidos"
        ),
        FieldRule(
            name="email",
            validators=[is_email()],
            normalizers=[normalize_email],
            required=True,
            label="Email"
        ),
        FieldRule(
            name="destino_origen",
            validators=[is_not_empty()],
            normalizers=[normalize_string],
            required=True,
            label="Destino/Origen"
        ),
        FieldRule(
            name="duracion_meses",
            validators=[is_duration_valid()],
            normalizers=[normalize_int],
            required=False,
            label="Duración (meses)"
        ),
    ]


def get_erasmus_out_schema() -> list[FieldRule]:
    """Esquema para validación de Erasmus OUT."""
    return get_student_form_schema() + [
        FieldRule(
            name="pais",
            validators=[is_not_empty()],
            normalizers=[normalize_string],
            required=True,
            label="País"
        ),
        FieldRule(
            name="curso",
            validators=[is_course_valid()],
            normalizers=[normalize_int],
            required=False,
            label="Curso"
        ),
    ]


def get_erasmus_in_schema() -> list[FieldRule]:
    """Esquema para validación de Erasmus IN."""
    return get_student_form_schema() + [
        FieldRule(
            name="pais",
            validators=[is_not_empty()],
            normalizers=[normalize_string],
            required=True,
            label="País"
        ),
    ]


def get_sicue_out_schema() -> list[FieldRule]:
    """Esquema para validación de SICUE OUT."""
    return get_student_form_schema() + [
        FieldRule(
            name="ciudad",
            validators=[is_not_empty()],
            normalizers=[normalize_string],
            required=True,
            label="Ciudad"
        ),
    ]


# ============================================
# VALIDADORES CONTEXTUALES (Avanzado)
# ============================================

def create_contextual_validator(context_validator: Callable[[dict], tuple[bool, str]]) -> Validator:
    """
    Crea validador que depende de otros campos (contextual).
    
    Uso:
        def no_duplicate_emails(all_data: dict) -> tuple[bool, str]:
            email = all_data.get('email', '')
            existing_emails = ['test@example.com']
            if email in existing_emails:
                return False, "Email ya existe"
            return True, ""
        
        validator = create_contextual_validator(no_duplicate_emails)
    """
    return context_validator


# ============================================
# FACTORY DE CONVERSORES (Retrocompatibilidad)
# ============================================

def get_converter(target_type: str) -> Callable:
    """
    Devuelve el conversor apropiado según tipo.
    
    Args:
        target_type: 'int', 'float', 'bool', 'str'
        
    Returns:
        Función conversora
    """
    converters = {
        'int': normalize_int,
        'float': lambda x: safe_float_convert(x),
        'bool': safe_bool_convert,
        'str': normalize_string,
    }
    return converters.get(target_type, normalize_string)


# ============================================
# UTILIDADES
# ============================================

def safe_get_nested(data: dict, *keys: str, default: Any = None) -> Any:
    """Obtiene valor anidado de diccionario de forma segura."""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
    return current if current is not None else default
