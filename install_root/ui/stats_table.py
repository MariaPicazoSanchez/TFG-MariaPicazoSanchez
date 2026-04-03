"""
Utilidad de renderizado de tablas de estadísticas.
Módulo independiente para evitar importaciones circulares.
"""

import pandas as pd
import streamlit as st


def render_stats_table(df: pd.DataFrame, count_col: str = "Nº de alumnos") -> None:
    """
    Muestra una tabla de estadísticas con barra de progreso y columna de porcentaje.
    """
    if df.empty:
        return
    df = df.copy()
    total = df[count_col].sum()
    df["%"] = (df[count_col] / total * 100).round(1) if total > 0 else 0.0
    max_val = int(df[count_col].max()) if not df.empty else 1

    # Configurar explícitamente todas las columnas de etiqueta como texto
    col_cfg: dict = {}
    for c in df.columns:
        if c == count_col:
            col_cfg[c] = st.column_config.ProgressColumn(
                c,
                min_value=0,
                max_value=max_val,
                format="%d",
            )
        elif c == "%":
            col_cfg[c] = st.column_config.NumberColumn(
                c,
                format="%.1f %%",
            )
        else:
            col_cfg[c] = st.column_config.TextColumn(c)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=col_cfg,
    )
