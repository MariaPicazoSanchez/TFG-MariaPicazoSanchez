"""
Constantes centralizadas para la aplicación de Movilidad ESII.
Mantener todas las constantes aquí para facilitar el mantenimiento.
"""

# ============================================
# PROGRAMAS DE MOVILIDAD
# ============================================
PROGRAM_ERASMUS_IN = "Erasmus IN"
PROGRAM_ERASMUS_OUT = "Erasmus OUT"
PROGRAM_SICUE_OUT = "SICUE OUT"

# Tupla con todos los programas
MOBILITY_PROGRAMS = (PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT)

# Lista que incluye "Todos" para filtros
MOBILITY_OPTIONS = ["Todos", PROGRAM_ERASMUS_OUT, PROGRAM_ERASMUS_IN, PROGRAM_SICUE_OUT]

# Etiquetas para mostrar en la UI
MOBILITY_LABELS = {
    "Todos": "Todos",
    PROGRAM_ERASMUS_OUT: "Erasmus OUT",
    PROGRAM_ERASMUS_IN: "Erasmus IN",
    PROGRAM_SICUE_OUT: "SICUE OUT",
}


# ============================================
# ALIASES DE COLUMNAS
# ============================================
COLUMN_ALIASES = {
    # Identificadores de estudiante
    "nombre": ["Nombre", "nombre"],
    "apellido1": ["Apellido1", "apellido1"],
    "apellido2": ["Apellido2", "apellido2"],
    "estudiante": ["estudiante", "Estudiante", "full_name", "nombre_completo"],
    "email": ["Email", "email", "correo"],
    
    # Ubicación
    "ciudad": ["ciudad", "Ciudad", "ciudad destino", "Ciudad destino", "City", "city", "localidad", "poblacion"],
    "pais": ["pais", "país", "País", "country", "Country"],
    "coordenadas": ["Coordenadas", "coords", "coordenadas"],
    
    # Universidad
    "universidad": ["universidad", "Universidad", "destino", "Destino", "Universidad Destino"],
    "origen": ["origen", "Origen", "Universidad Origen"],
    
    # Académico
    "curso": ["curso", "Curso"],
    "cuatrimestre": ["cuatrimestre", "Cuatrimestre", "cuatri"],
    "duracion": ["duracion_meses", "Duración (meses)", "Duracion (meses)", "duracion meses"],
    
    # Documentación
    "la": ["LA", "link_la", "Learning Agreement"],
    "tor": ["ToR", "tor", "link_tor"],
    "plan": ["link_plan", "Plan de estudios", "Plan estudios", "Enlace plan de estudios"],
    "acta": ["acta_equivalencias", "Acta de equivalencias"],
    
    # Gestión
    "gestion_la": ["gestion_LA", "Gestión LA", "Gestion LA"],
    "coordinador": ["coordinador_destino", "Coordinador en destino", "coordinador"],
    "responsable": ["responsable", "Responsable", "responsable programa"],
}


# ============================================
# VALORES ESPECIALES
# ============================================
# País por defecto para SICUE
SPAIN = "España"

# Valor especial para CSV (sin hojas)
CSV_SHEET_MARKER = "__CSV__"

# Filtro especial
FILTER_ALL = "Todos"


# ============================================
# ICONOS Y COLORES PARA MAPAS
# ============================================
PROGRAM_ICONS = {
    PROGRAM_ERASMUS_OUT: "plane",
    PROGRAM_ERASMUS_IN: "plane",
    PROGRAM_SICUE_OUT: "map-marker",
}

PROGRAM_COLORS = {
    PROGRAM_ERASMUS_OUT: "blue",
    PROGRAM_ERASMUS_IN: "green",
    PROGRAM_SICUE_OUT: "orange",
}


# ============================================
# ESTADOS DE GESTIÓN LA
# ============================================
GESTION_LA_ESTADOS = [
    "Pendiente firma del coordinador",
    "Pendiente firma del estudiante",
    "Enviado a vicerrectorado",
]


# ============================================
# CONFIGURACIÓN DE ARCHIVOS
# ============================================
# Claves de configuración
CONFIG_KEYS = {
    "erasmus_out": PROGRAM_ERASMUS_OUT,
    "erasmus_in": PROGRAM_ERASMUS_IN,
    "sicue_out": PROGRAM_SICUE_OUT,
}

# Extensiones soportadas
EXCEL_EXTENSIONS = (".xlsx", ".xlsm", ".xltx", ".xltm", ".xls")
CSV_EXTENSION = ".csv"
SUPPORTED_EXTENSIONS = EXCEL_EXTENSIONS + (CSV_EXTENSION,)
