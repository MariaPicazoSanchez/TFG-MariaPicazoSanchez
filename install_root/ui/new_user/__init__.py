"""Paquete del formulario de nuevo estudiante."""

from .view import render_new_user_form
from ._helpers import (
    get_university_responsable_map,
    get_university_responsable_map as get_university_responsable,
    get_university_country_map,
    COUNTRY_OPTIONS,
)

__all__ = [
    "render_new_user_form",
    "get_university_responsable",
    "get_university_responsable_map",
    "get_university_country_map",
    "COUNTRY_OPTIONS",
]
