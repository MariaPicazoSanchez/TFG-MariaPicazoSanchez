import json
import pandas as pd
from geopy.geocoders import Nominatim
import os

_geolocator = Nominatim(user_agent="tfg-mapa-erasmus")


def _split_full_name(full_name: str):
    full_name = (full_name or "").strip()
    if not full_name:
        return "", "", ""
    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    nombre = parts[0]
    ape1 = parts[1]
    ape2 = " ".join(parts[2:])
    return nombre, ape1, ape2


def update_student_in_excel(excel_path: str, row_index: str, idx: int, data: dict) -> bool:
    print("[update_student_in_excel] excel_path =", excel_path,
          "row_index =", row_index, "idx =", idx)

    try:
        with pd.ExcelFile(excel_path) as xls:
            sheet_name = xls.sheet_names[0]
            print("[update_student_in_excel] Usando hoja:", sheet_name)
            df = pd.read_excel(xls, sheet_name=sheet_name)
            print("[update_student_in_excel] Columnas DF:", list(df.columns))
    except Exception as e:
        print("[update_student_in_excel] Error leyendo Excel:", e)
        return False

    row_i = None
    n_rows = len(df)

    # 1) Intentar por EMAIL
    email_val = (data.get("email") or "").strip().lower()
    if email_val:
        email_cols = ["email", "Email", "E-mail", "Correo", "Correo electrónico"]
        for col in email_cols:
            if col in df.columns:
                mask = df[col].astype(str).str.strip().str.lower() == email_val
                if mask.any():
                    row_i = mask[mask].index[0]
                    print(f"[update_student_in_excel] Fila localizada por email en columna '{col}':", row_i)
                    break

    # 2) Si no lo encontramos por email, probar por NOMBRE COMPLETO
    if row_i is None:
        full_name = (data.get("estudiante") or "").strip().lower()
        if full_name:
            name_cols = ["estudiante", "Estudiante", "NOMBRE COMPLETO", "Nombre completo"]
            for col in name_cols:
                if col in df.columns:
                    mask = df[col].astype(str).str.strip().str.lower() == full_name
                    if mask.any():
                        row_i = mask[mask].index[0]
                        print(f"[update_student_in_excel] Fila localizada por nombre en columna '{col}':", row_i)
                        break

    # 3) Último recurso: usar row_index tal cual (por compatibilidad)
    if row_i is None:
        try:
            row_i = int(row_index)
        except ValueError:
            print("[update_student_in_excel] row_index no es entero:", row_index)
            return False

        if row_i < 0 or row_i >= n_rows:
            print("[update_student_in_excel] row_index fuera de rango incluso como respaldo:", row_i)
            return False
        else:
            print("[update_student_in_excel] Usando row_index como respaldo:", row_i)

    # Mapa: campo del formulario -> posibles nombres de columna en Excel
        # Mapa: campo del formulario -> posibles nombres de columna en Excel
    field_to_cols = {
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
            # SICUE OUT
            "duracion meses",
            # otros posibles formatos
            "duracion_meses",
            "Duración (meses)",
            "Duración meses",
            "Duración",
        ],
        "gestion_LA": [
            # SICUE OUT
            "Gestion LA",
            # otros
            "gestion_LA",
            "Gestión LA",
        ],
        "coordinador_destino": [
            # SICUE OUT
            "Coordinador en destino",
            # otros
            "coordinador_destino",
            "Coordinador destino",
            "Coordinador de destino",
        ],
        "link_la": [
            # SICUE OUT
            "LA",
            # otros
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
            # SICUE OUT
            "Plan de estudios",
            # otros
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


    def _set_field(field_name: str):
        """Intenta escribir data[field_name] en la primera columna compatible que exista."""
        if field_name not in data:
            return
        value = data[field_name]
        posibles = field_to_cols.get(field_name, [field_name])
        for col in posibles:
            if col in df.columns:
                df.at[row_i, col] = value
                print(f"[update_student_in_excel] {field_name} -> columna '{col}' = {value}")
                return  # solo actualizamos la primera que exista

    def _actualizar_nombre_apellidos():
        full = data.get("estudiante", "").strip()
        if not full:
            return
        nombre, ape1, ape2 = _split_full_name(full)
        col_val_map = {
            # nombre
            "nombre": nombre,
            "Nombre": nombre,
            "NOMBRE": nombre,
            # apellido1
            "apellido1": ape1,
            "apellido_1": ape1,
            "Apellido1": ape1,
            "APELLIDO1": ape1,
            # apellido2
            "apellido2": ape2,
            "apellido_2": ape2,
            "Apellido2": ape2,
            "APELLIDO2": ape2,
        }
        for col, val in col_val_map.items():
            if col in df.columns:
                df.at[row_i, col] = val
                print(f"[update_student_in_excel] estudiante -> {col} = {val}")

    # 1) Si NO hay columna 'estudiantes' → modo plano (SICUE OUT, etc.)
    if "estudiantes" not in df.columns:
        print("[update_student_in_excel] No hay columna 'estudiantes'; modo plano")

        for field in field_to_cols.keys():
            _set_field(field)

        _actualizar_nombre_apellidos()
        _recalculate_coords(df, row_i)
        

        try:
            with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            print("[update_student_in_excel] Guardado OK (modo plano)")
            return True
        except Exception as e:
            print("[update_student_in_excel] Error guardando Excel:", e)
            return False

    # 2) Si SÍ hay 'estudiantes' → modo JSON (Erasmus IN)
    raw_est = df.at[row_i, "estudiantes"]
    try:
        if isinstance(raw_est, str):
            est_list = json.loads(raw_est) if raw_est.strip() else []
        elif isinstance(raw_est, list):
            est_list = raw_est
        else:
            est_list = []
    except Exception as e:
        print("[update_student_in_excel] Error parseando JSON estudiantes:", e)
        est_list = []

    if not isinstance(est_list, list) or len(est_list) == 0:
        print("[update_student_in_excel] Lista 'estudiantes' vacía; actualizando solo columnas planas")
        for field in field_to_cols.keys():
            _set_field(field)
        _actualizar_nombre_apellidos()
        try:
            with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a",
                                if_sheet_exists="replace") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            print("[update_student_in_excel] Guardado OK (fallback plano)")
            return True
        except Exception as e:
            print("[update_student_in_excel] Error guardando Excel:", e)
            return False

    if idx < 0 or idx >= len(est_list):
        print("[update_student_in_excel] idx fuera de rango:", idx,
              "len(est_list)=", len(est_list))
        return False

    est = est_list[idx]
    if not isinstance(est, dict):
        est = {}

    # Actualizamos campos dentro del JSON de estudiantes
    for field in field_to_cols.keys():
        if field in data:
            est[field] = data[field]
            print(f"[update_student_in_excel] JSON[{idx}]['{field}'] = {data[field]}")

    est_list[idx] = est
    df.at[row_i, "estudiantes"] = json.dumps(est_list, ensure_ascii=False)

    # Y además columnas sueltas + nombre/apellidos
    for field in field_to_cols.keys():
        _set_field(field)
    _actualizar_nombre_apellidos()

    try:
        with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a",
                            if_sheet_exists="replace") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        print("[update_student_in_excel] Guardado OK (modo JSON)")
        return True
    except Exception as e:
        print("[update_student_in_excel] Error guardando Excel:", e)
        return False


def _recalculate_coords(df: pd.DataFrame, row_i: int):
    print(f"[coords] Recalculando para fila {row_i}")
    destino = None
    ciudad = None
    pais = None

    for col in df.columns:
        col_norm = str(col).strip().lower()
        val = df.at[row_i, col]
        if col_norm in ("destino", "universidad", "universidad destino"):
            destino = val
        elif col_norm == "ciudad":
            ciudad = val
        elif col_norm == "país" or col_norm == "pais":
            pais = val

    print(f"[coords] Valores: destino={destino!r}, ciudad={ciudad!r}, pais={pais!r}")

    # Prueba con todas las combinaciones posibles
    queries = []
    partes = [str(x).strip() for x in (destino, ciudad, pais) if x is not None and str(x).strip() and str(x).strip().lower() != "none"]
    if partes:
        queries.append(", ".join(partes))
    if ciudad and pais:
        queries.append(f"{ciudad}, {pais}")
    if pais:
        queries.append(str(pais).strip())

    loc = None
    for query in queries:
        print(f"[coords] Geocodificando: {query!r}")
        try:
            loc = _geolocator.geocode(query, timeout=10)
        except Exception as e:
            print(f"[coords] Error geocodificando {query!r}: {e}")
            loc = None
        if loc:
            break

    if not loc:
        print(f"[coords] No se han encontrado coords para ninguna combinación: {queries}")
        return

    lat, lon = loc.latitude, loc.longitude
    print(f"[coords] -> lat={lat}, lon={lon}")

    # Escribimos en las columnas que existan
    for col in df.columns:
        col_norm = str(col).strip().lower()
        if col_norm in ("latitud", "latitude"):
            df.at[row_i, col] = lat
        elif col_norm in ("longitud", "longitude"):
            df.at[row_i, col] = lon
        elif col_norm == "coordenadas":
            df.at[row_i, col] = f"{lat},{lon}"

def actualizar_excel_materias_para_estudiante(
    materias_in,      # lista de dicts: {"asignatura", "cuat", "firmado"}
    est,              # dict del estudiante (nombre, origen, destino/centro, etc.)
    materias_path: str
):
    """
    Actualiza el Excel de asignaturas (Asignatura, Estudiante, Origen, Centro, Cuat, Firmado)
    para un estudiante concreto: borra sus filas antiguas y mete las nuevas.

    - Las hojas del fichero van por curso (2023-2024, 2024-2025, 2025-2026, ...).
    - Se elige la hoja en la que YA está el estudiante (columna 'Estudiante').
    - Si no está en ninguna, se usa por defecto la última hoja.
    - Si no se puede leer o escribir el Excel, SE LANZA EXCEPCIÓN.
    """
    if not materias_path:
        raise ValueError("No se ha recibido la ruta del Excel de materias.")

    nombre = (est.get("estudiante") or "").strip()
    origen = (est.get("origen") or est.get("pais") or "").strip()
    centro = (est.get("destino") or est.get("Centro") or est.get("universidad") or "").strip()

    if not nombre:
        raise ValueError("El estudiante no tiene nombre; no se puede actualizar el Excel de asignaturas.")

    # ----------------------
    # 1) Cargar libro y decidir hoja
    # ----------------------
    sheet_name = None
    all_sheets = {}

    if not os.path.exists(materias_path):
        raise FileNotFoundError(f"El archivo de materias no existe: {materias_path}")

    try:
        # 🔐 Usar contexto para que NO deje el fichero abierto
        with pd.ExcelFile(materias_path) as xls:
            # Leer todas las hojas en memoria
            for sh in xls.sheet_names:
                try:
                    df_sh = pd.read_excel(xls, sheet_name=sh)
                except Exception as e:
                    print(f"[materias] Error leyendo hoja '{sh}':", e)
                    continue
                all_sheets[sh] = df_sh

        # Buscar en qué hoja está ya el estudiante
        for sh, df_sh in all_sheets.items():
            if "Estudiante" in df_sh.columns:
                mask = df_sh["Estudiante"].astype(str).str.strip().str.lower() == nombre.lower()
                if mask.any():
                    sheet_name = sh
                    break

        # Si no lo hemos encontrado en ninguna hoja, usamos la última hoja como curso actual
        if sheet_name is None:
            if all_sheets:
                sheet_name = list(all_sheets.keys())[-1]
            else:
                # Libro vacío: lo tratamos como error
                raise RuntimeError("El Excel de materias no contiene ninguna hoja válida.")
    except Exception as e:
        # Lo dejamos caer para que api.py pueda mostrar el error
        raise RuntimeError(f"No se ha podido leer el Excel de materias: {e}") from e

    # DataFrame de la hoja elegida
    df_mat = all_sheets.get(sheet_name)
    if df_mat is None or df_mat.empty:
        df_mat = pd.DataFrame(columns=["Asignatura", "Estudiante", "Origen", "Centro", "Cuat", "Firmado"])

    # ----------------------
    # 2) Eliminar filas actuales de ese estudiante en esa hoja
    # ----------------------
    if "Estudiante" in df_mat.columns:
        mask = df_mat["Estudiante"].astype(str).str.strip().str.lower() == nombre.lower()
        df_mat = df_mat[~mask].copy()

    # ----------------------
    # 3) Añadir filas nuevas desde materias_in
    # ----------------------
    nuevas = []
    for m in materias_in or []:
        nuevas.append({
            "Asignatura": m.get("asignatura", ""),
            "Estudiante": nombre,
            "Origen": origen,
            "Centro": centro,
            "Cuat": m.get("cuat", ""),
            "Firmado": m.get("firmado", "") or "",   # 'x' o vacío
        })

    if nuevas:
        df_mat = pd.concat([df_mat, pd.DataFrame(nuevas)], ignore_index=True)

    # Actualizar el diccionario de hojas en memoria
    all_sheets[sheet_name] = df_mat

    # ----------------------
    # 4) Guardar TODAS las hojas, reemplazando solo la del curso del alumno
    # ----------------------
    try:
        from openpyxl import load_workbook  # asegura motor disponible
        # Este with también cierra bien el fichero al terminar
        with pd.ExcelWriter(materias_path, engine="openpyxl", mode="w") as writer:
            for sh, df_sh in all_sheets.items():
                df_sh.to_excel(writer, sheet_name=sh, index=False)
    except Exception as e:
        raise RuntimeError(f"No se ha podido guardar el Excel de materias: {e}") from e

    print(f"[materias] Actualizado Excel de asignaturas para {nombre} en hoja '{sheet_name}' -> {materias_path}")
