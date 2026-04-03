"""Módulo de compatibilidad hacia atrás. El código real vive en ui/new_user/."""

from .new_user import (  # noqa: F401
    render_new_user_form,
    get_university_responsable_map,
    get_university_country_map,
    COUNTRY_OPTIONS,
)
