ESTADOS_FIRMA = [
    "",
    "Pendiente firma estudiante",
    "Pendiente firma coordinador",
    "Enviado a Vicerrectorado",
]

COMMON_COLS = ["Nombre", "Apellidos", "Email", "Universidad", "Coordenadas"]
SPEC_COLS = {
    "Erasmus OUT": ["ToR", "Curso", "ActaEquivalencias"],
    "Erasmus IN":  ["LA", "Horario"],
    "SICUE OUT":   ["LA", "EstadoFirmas", "PlanEstudios"],
}

PROGRAM_COLORS = {
    "Erasmus OUT": "blue",
    "Erasmus IN": "green",
    "SICUE OUT": "orange",
}

PROGRAM_ICONS = {
    "Erasmus OUT": "sign-out",
    "Erasmus IN": "sign-in",
    "SICUE OUT": "sign-out",
}


ICON_BY_TIPO = {"SICUE OUT": "📘", "Erasmus IN": "🌍", "Erasmus OUT": "✈️"}

FIELD_ALIASES = {
    "estudiante": [
        "estudiante", "Estudiante", "NOMBRE COMPLETO", "Nombre completo",
    ],
    "email": [
        "email", "Email", "E-mail", "Correo", "Correo electrónico",
    ],
    "curso": [
        "curso", "Curso",
    ],
    "cuatrimestre": [
        "cuatrimestre", "Cuatrimestre",
    ],
    "duracion_meses": [
        "duracion meses",
        "duracion_meses",
        "Duración (meses)",
        "Duración meses",
        "Duración",
    ],
    "gestion_LA": [
        "Gestion LA",
        "gestion_LA",
        "Gestión LA",
    ],
    "coordinador_destino": [
        "Coordinador en destino",
        "coordinador_destino",
        "Coordinador destino",
        "Coordinador de destino",
    ],
    "link_la": [
        "LA",
        "link_la",
        "Learning agreement",
        "Learning Agreement",
    ],
    "ToR": [
        "ToR", "TOR", "Transcript of Records",
    ],
    "acta_equivalencias": [
        "acta_equivalencias", "Acta de equivalencias",
    ],
    "link_plan": [
        "Plan de estudios",
        "link_plan",
        "Plan estudios",
        "Plan",
    ],
    "destino": [
        "destino", "Destino",
    ],
    "origen": [
        "origen", "Origen",
    ],
    "responsable": [
        "responsable", "Responsable",
    ],
    "pais": [
        "pais", "País", "Pais",
    ],
    "ciudad": [
        "ciudad", "Ciudad",
    ],
}