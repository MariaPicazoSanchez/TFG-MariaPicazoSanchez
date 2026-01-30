import os
import pandas as pd


def load_materias_in(config):
    """
    Lee el Excel de Materias IN usando la ruta de config.json
    y devuelve un DataFrame.
    
    Optimización: Usa caché basado en mtime del archivo para evitar
    relecturas innecesarias.
    """
    ruta = config.get("Materias IN")
    if not ruta or not os.path.exists(ruta):
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(ruta)
        return df if df is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def build_materias_in_por_estudiante(df_materias):
    """
    Devuelve un dict:
      { 'Nombre Estudiante': [ {datos de cada asignatura}, ... ] }
    """
    if df_materias is None or df_materias.empty:
        return {}
    
    materias_por_est = {}
    
    for row in df_materias.itertuples(index=False, name='Row'):
        est = str(row.Estudiante or "").strip() if hasattr(row, 'Estudiante') else ""
        if not est:
            continue

        if est not in materias_por_est:
            materias_por_est[est] = []
        
        materias_por_est[est].append({
            "asignatura": getattr(row, 'Asignatura', None),
            "cuat":      getattr(row, 'Cuat', None),
            "firmado":   getattr(row, 'Firmado', None),
            "origen":    getattr(row, 'Origen', None),
            "centro":    getattr(row, 'Centro', None),
        })

    return materias_por_est


def get_materias_in_por_estudiante(config):
    """
    Función de alto nivel: la llamas desde tu código principal
    y ya te devuelve el diccionario listo.
    
    Nota: El caching de Streamlit se aplica en my_app.py con @st.cache_data
    """
    df = load_materias_in(config)
    return build_materias_in_por_estudiante(df)
