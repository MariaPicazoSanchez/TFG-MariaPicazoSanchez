ESTADOS_FIRMA = [
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