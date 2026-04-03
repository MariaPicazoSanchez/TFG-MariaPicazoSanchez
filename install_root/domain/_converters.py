"""
Conversores y normalizadores de tipos básicos.

Exporta:
  Conversores: safe_int_convert, safe_int_to_str, safe_float_convert, safe_bool_convert
  Normalizadores: normalize_string, normalize_lower, normalize_email,
                  normalize_int, normalize_phone, compose_normalizers
"""


from typing import Any, Callable


# ─────────────────────────────────────────────────────────────────────────────
# Conversores numéricos
# ─────────────────────────────────────────────────────────────────────────────

def safe_int_convert(value: Any, default: int | None = None) -> int | None:
    """
    Convierte a entero desde string/float, tolerando formatos variados.

    Ejemplos:
        safe_int_convert("3.0")        -> 3
        safe_int_convert("abc", 0)     -> 0
        safe_int_convert("1.5")        -> 1
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
    """Convierte a entero y luego a string (seguro para HTML/display)."""
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
        if val_lower in {"sí", "yes", "true", "x", "v", "1"}:
            return True
        if val_lower in {"no", "false", "", "0"}:
            return False
    return default


# ─────────────────────────────────────────────────────────────────────────────
# Normalizadores
# ─────────────────────────────────────────────────────────────────────────────

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
    return "".join(c for c in str(value or "").strip() if c.isdigit())


def compose_normalizers(*normalizers: Callable) -> Callable:
    """Compone múltiples normalizadores en uno solo."""
    def composed(value: Any) -> Any:
        for norm in normalizers:
            value = norm(value)
        return value
    return composed
