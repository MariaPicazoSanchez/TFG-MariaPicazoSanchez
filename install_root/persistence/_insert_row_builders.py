"""
Construcción de filas Excel para cada tipo de programa de movilidad.

Exporta:
  - build_new_sheet_row      — fila para cuando la hoja no existe aún
  - build_existing_sheet_row — fila para cuando la hoja ya existe
"""


import pandas as pd
from domain import COMMON_COLS, SPEC_COLS, SICUE_OUT_COLS

from ._insert_helpers import _pick_col


def build_new_sheet_row(
    tipo: str, row_data: dict, lat, lon
) -> tuple[dict, list[str]]:
    """
    Construye el dict de valores y la lista ordenada de columnas para crear
    una hoja nueva (cuando aún no existe en el Excel).

    Devuelve (new_row_dict, cols_order).
    """
    need_cols = COMMON_COLS + (SPEC_COLS.get(tipo) or [])
    if "Apellidos" not in need_cols:
        need_cols = need_cols + ["Apellidos"]
    if (row_data.get("ciudad") or row_data.get("ciudad_sicue")) and "Ciudad" not in need_cols:
        need_cols = need_cols + ["Ciudad"]

    coords_str = (
        f"{row_data['coordenadas'][0]}, {row_data['coordenadas'][1]}"
        if isinstance(row_data.get("coordenadas"), (tuple, list))
        and len(row_data["coordenadas"]) == 2
        and row_data["coordenadas"][0] is not None
        and row_data["coordenadas"][1] is not None
        else None
    )

    new: dict = {
        "Nombre":      row_data.get("nombre"),
        "Apellidos":   row_data.get("apellidos"),
        "Email":       row_data.get("email"),
        "Universidad": row_data.get("destino_origen"),
    }

    if tipo == "Erasmus OUT":
        need_cols = [c for c in need_cols if c.lower() != "coordenadas"]
        new.update({
            "ToR":              row_data.get("tor"),
            "Curso":            row_data.get("curso"),
            "ActaEquivalencias": row_data.get("acta_equivalencias"),
        })
        if row_data.get("ciudad"):
            new["Ciudad"] = row_data.get("ciudad")

    elif tipo == "Erasmus IN":
        new.update({
            "LA":      row_data.get("la"),
            "Horario": row_data.get("horario"),
        })
        if row_data.get("ciudad"):
            new["Ciudad"] = row_data.get("ciudad")

    else:  # SICUE OUT
        new["Coordenadas"] = coords_str
        need_cols = list(SICUE_OUT_COLS)
        apes = (row_data.get("apellidos") or "").strip()
        parts = apes.split()
        new = {
            "nombre":                 row_data.get("nombre"),
            "apellido1":              parts[0] if parts else (row_data.get("apellido1") or ""),
            "apellido2":              " ".join(parts[1:]) if len(parts) > 1 else (row_data.get("apellido2") or ""),
            "email":                  row_data.get("email"),
            "duracion meses":         row_data.get("dur_sicue"),
            "Coordinador en destino": row_data.get("coord_dest"),
            "LA":                     row_data.get("la_in"),
            "Gestión LA":             row_data.get("gestion_la"),
            "Destino":                row_data.get("destino_origen"),
            "Ciudad":                 row_data.get("ciudad_sicue"),
            "Plan de estudios":       row_data.get("plan_sic_out"),
            "Coordenadas": (
                f"{lat}, {lon}"
                if lat is not None and lon is not None
                else None
            ),
        }

    return new, need_cols


def build_existing_sheet_row(
    tipo: str, df: pd.DataFrame, row_data: dict, lat, lon
) -> tuple[dict, list[str]]:
    """
    Construye el dict de valores para añadir a una hoja que ya existe.
    Mapea los datos del formulario a las columnas reales del DataFrame.

    Devuelve (new_row_dict, cols_order).
    cols_order puede haberse extendido si se añade columna Ciudad al vuelo.
    """
    cols_order = list(df.columns)

    c_nombre    = _pick_col(df, "nombre", "Nombre")
    c_apellidos = _pick_col(df, "apellidos", "Apellidos")
    c_ap1       = _pick_col(df, "apellido1", "Apellido1")
    c_ap2       = _pick_col(df, "apellido2", "Apellido2")
    c_email     = _pick_col(df, "email", "Email")
    c_coords    = _pick_col(df, "Coordenadas", "coordenadas")
    c_lat       = _pick_col(df, "Latitud", "latitud", "Lat")
    c_lon       = _pick_col(df, "Longitud", "longitud", "Lon")

    if tipo == "Erasmus IN":
        c_univ = _pick_col(df, "Universidad Origen", "universidad origen", "Universidad", "Origen")
    else:
        c_univ = _pick_col(df, "Destino", "Universidad Destino", "universidad destino", "Universidad")

    new_row: dict = {c: None for c in cols_order}

    if c_nombre:
        new_row[c_nombre] = row_data.get("nombre")

    apes = (row_data.get("apellidos") or "").strip()
    if c_apellidos:
        new_row[c_apellidos] = apes
    elif c_ap1 and c_ap2:
        parts = apes.split()
        new_row[c_ap1] = parts[0] if parts else ""
        new_row[c_ap2] = " ".join(parts[1:]) if len(parts) > 1 else ""
    elif c_ap1:
        new_row[c_ap1] = apes

    if c_email:
        new_row[c_email] = row_data.get("email")
    if c_univ:
        new_row[c_univ] = row_data.get("destino_origen")

    if tipo != "Erasmus OUT":
        if c_coords and lat is not None and lon is not None:
            new_row[c_coords] = f"{lat}, {lon}"
        else:
            if c_lat:
                new_row[c_lat] = lat
            if c_lon:
                new_row[c_lon] = lon

    if tipo == "SICUE OUT":
        c_la      = _pick_col(df, "LA", "la")
        c_gestion = _pick_col(df, "Gestion LA", "Gestión LA", "gestion la", "gestión la")
        c_estado  = _pick_col(df, "EstadoFirmas", "Estado firmas", "estado de firmas")
        c_plan    = _pick_col(df, "Enlace plan de estudios", "plan de estudios", "PlanEstudios")
        c_dur     = _pick_col(df, "duracion meses", "duración meses", "duracion_meses")
        c_coord   = _pick_col(df, "Coordinador en destino")
        c_ciudad  = _pick_col(df, "Ciudad", "ciudad", "ciudad destino", "Ciudad destino", "city")
        if c_la:      new_row[c_la]      = row_data.get("la")
        if c_gestion: new_row[c_gestion] = row_data.get("gestion_la") or row_data.get("gestion")
        if c_estado:  new_row[c_estado]  = row_data.get("estado_firmas")
        if c_plan:    new_row[c_plan]    = row_data.get("plan_estudios")
        if c_dur:     new_row[c_dur]     = row_data.get("dur_sicue") or None
        if c_coord:   new_row[c_coord]   = row_data.get("coord_dest") or None
        if c_ciudad:
            new_row[c_ciudad] = row_data.get("ciudad_sicue") or None
        elif row_data.get("ciudad_sicue"):
            cols_order.append("Ciudad")
            new_row["Ciudad"] = row_data.get("ciudad_sicue")

    elif tipo == "Erasmus OUT":
        c_la     = _pick_col(df, "LA", "la")
        c_tor    = _pick_col(df, "ToR", "tor")
        c_curso  = _pick_col(df, "Curso", "curso")
        c_acta   = _pick_col(df, "Acta de equivalencias", "ActaEquivalencias", "acta equivalencias")
        c_dur    = _pick_col(df, "duracion meses", "duración meses", "duracion_meses")
        c_resp   = _pick_col(df, "responsable programa", "responsable del programa")
        c_plan   = _pick_col(df, "Enlace plan de estudios", "plan de estudios")
        c_dest   = _pick_col(df, "Destino")
        c_pais   = _pick_col(df, "País", "Pais")
        c_ciudad = _pick_col(df, "Ciudad", "ciudad", "city", "localidad", "poblacion")
        if c_la:    new_row[c_la]    = row_data.get("la")
        if c_tor:   new_row[c_tor]   = row_data.get("tor")
        if c_curso: new_row[c_curso] = row_data.get("curso")
        if c_acta:  new_row[c_acta]  = row_data.get("acta_equivalencias")
        if c_dur:   new_row[c_dur]   = row_data.get("dur_out") or None
        if c_resp:  new_row[c_resp]  = row_data.get("resp_prog") or None
        if c_la and row_data.get("la_out"):             new_row[c_la]   = row_data.get("la_out")
        if c_plan and row_data.get("plan_out"):         new_row[c_plan] = row_data.get("plan_out")
        if c_dest and row_data.get("destino_tabla_out"): new_row[c_dest] = row_data.get("destino_tabla_out")
        if c_pais and row_data.get("pais_out"):         new_row[c_pais] = row_data.get("pais_out")
        if c_ciudad and row_data.get("ciudad"):         new_row[c_ciudad] = row_data.get("ciudad")

    else:  # Erasmus IN
        c_la     = _pick_col(df, "LA", "la")
        c_horario = _pick_col(df, "Horario", "horario")
        c_cuatri = _pick_col(df, "Cuatrimestre", "Cuatrimestre")
        c_uo     = _pick_col(df, "Universidad Origen")
        c_pais   = _pick_col(df, "País", "Pais")
        c_ciudad = _pick_col(df, "Ciudad", "ciudad", "city", "localidad", "poblacion")
        if c_uo == c_univ:
            c_uo = None
        if c_la:      new_row[c_la]      = row_data.get("la")
        if c_horario: new_row[c_horario] = row_data.get("horario")
        if c_cuatri:  new_row[c_cuatri]  = row_data.get("cuatrimestre_in") or None
        if c_uo:      new_row[c_uo]      = row_data.get("uni_origen_in") or None
        if c_pais:    new_row[c_pais]    = row_data.get("pais_in") or None
        if c_ciudad and row_data.get("ciudad"):
            new_row[c_ciudad] = row_data.get("ciudad")

    return new_row, cols_order
