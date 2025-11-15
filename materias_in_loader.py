# materias_in_loader.py
import pandas as pd

def load_materias_in(config):
    """
    Lee el Excel de Materias IN usando la ruta de config.json
    y devuelve un DataFrame.
    """
    ruta = config["Materias IN"]
    df = pd.read_excel(ruta)
    return df


def build_materias_in_por_estudiante(df_materias):
    """
    Devuelve un dict:
      { 'Nombre Estudiante': [ {datos de cada asignatura}, ... ] }
    """
    materias_por_est = {}

    for _, row in df_materias.iterrows():
        est = str(row.get("Estudiante", "")).strip()
        if not est:
            continue

        materias_por_est.setdefault(est, []).append({
            "asignatura": row.get("Asignatura"),
            "cuat":      row.get("Cuat"),
            "firmado":   row.get("Firmado"),
            "origen":    row.get("Origen"),
            "centro":    row.get("Centro"),
        })

    return materias_por_est


def get_materias_in_por_estudiante(config):
    """
    Función de alto nivel: la llamas desde tu código principal
    y ya te devuelve el diccionario listo.
    """
    df = load_materias_in(config)
    return build_materias_in_por_estudiante(df)
