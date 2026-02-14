import os
import json
import pandas as pd
import streamlit as st
from domain import COMMON_COLS, SPEC_COLS
from openpyxl import load_workbook
from domain.validators import safe_int_convert, DataValidator

def first_sheet_name(xlsx_path: str) -> str:
    try:
        wb = load_workbook(xlsx_path, read_only=True)
        return wb.sheetnames[0] if wb.sheetnames else "Sheet1"
    except Exception:
        return "Sheet1"

def _norm(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", str(s).strip().lower())

def _pick_col(df: pd.DataFrame, *aliases):
    norm_map = {_norm(c): c for c in df.columns}
    # exactos
    for a in aliases:
        if a and _norm(a) in norm_map:
            return norm_map[_norm(a)]
    # contains único
    for a in aliases:
        if not a:
            continue
        na = _norm(a)
        cand = [real for norm, real in norm_map.items() if na in norm or norm in na]
        if len(cand) == 1:
            return cand[0]
    return None

def _sheet_exists(xlsx_path: str, sheet_name: str) -> bool:
    try:
        wb = load_workbook(xlsx_path, read_only=True)
        return sheet_name in wb.sheetnames
    except Exception:
        return False
    


def append_user_to_excel(xlsx_path: str, tipo: str, row_data: dict, sheet_name: str | None):
    """
    Añade una fila al Excel en la hoja `sheet_name`.
    - Si la hoja NO existe -> la crea con cabeceras estándar.
    - Si SÍ existe -> mapea a las columnas reales y añade una fila (replace esa hoja).
    Devuelve: (ok: bool, err: str|None)
    """
    if not xlsx_path or not os.path.exists(xlsx_path):
        return False, f"No existe el Excel: {xlsx_path}"

    target_sheet = (sheet_name or "").strip() or first_sheet_name(xlsx_path)
    lat = None
    lon = None
    # row_data puede venir con "coordenadas": (lat, lon)
    if "coordenadas" in row_data and isinstance(row_data["coordenadas"], (tuple, list)) and len(row_data["coordenadas"]) == 2:
        lat, lon = row_data["coordenadas"]
    else:
        lat = row_data.get("lat")
        lon = row_data.get("lon")

    # ── Hoja NO existe → crear con columnas estándar ────────────────────────────
    if not _sheet_exists(xlsx_path, target_sheet):
        need_cols = COMMON_COLS + (SPEC_COLS.get(tipo) or [])
        # Si el payload incluye ciudad, añadirla a las columnas de la nueva hoja
        if (row_data.get("ciudad") or row_data.get("ciudad_sicue")) and "Ciudad" not in need_cols:
            need_cols = need_cols + ["Ciudad"]
        new = {
            "Nombre":      row_data.get("nombre"),
            "Apellidos":   row_data.get("apellidos"),
            "Email":       row_data.get("email"),
            "Universidad": row_data.get("destino_origen"),
            "Coordenadas": (
                f"{row_data.get('coordenadas')[0]}, {row_data.get('coordenadas')[1]}"
                if isinstance(row_data.get('coordenadas'), (tuple, list)) and len(row_data['coordenadas']) == 2
                else None
            ),
        }
        if tipo == "Erasmus OUT":
            new.update({"ToR": row_data.get("tor"), "Curso": row_data.get("curso"), "ActaEquivalencias": row_data.get("acta_equivalencias")})
            # ciudad (campo opcional en OUT)
            if row_data.get("ciudad"):
                new.update({"Ciudad": row_data.get("ciudad")})
        elif tipo == "Erasmus IN":
            new.update({"LA": row_data.get("la"), "Horario": row_data.get("horario")})
            # ciudad (campo opcional en IN)
            if row_data.get("ciudad"):
                new.update({"Ciudad": row_data.get("ciudad")})
            c_univ = _pick_col(df, "Destino", "Universidad Destino", "universidad destino", "Universidad")
            if c_univ:  new_row[c_univ]  = row_data.get("destino_origen") or row_data.get("universidad_origen") or row_data.get("destino")

        else:  # SICUE OUT
            new.update({"LA": row_data.get("la"), "EstadoFirmas": row_data.get("estado_firmas"), "PlanEstudios": row_data.get("plan_estudios")})

        out = pd.DataFrame([new], columns=need_cols)

        mode = "a" if os.path.exists(xlsx_path) else "w"
        try:
            with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode=mode) as w:
                out.to_excel(w, sheet_name=target_sheet, index=False)
        except PermissionError:
            return False, "El archivo está abierto en otra aplicación."
        except Exception as e:
            return False, f"Error creando la hoja '{target_sheet}': {e}"
        return True, None

    # ── Hoja SÍ existe → leer, mapear y añadir ─────────────────────────────────
    try:
        df = pd.read_excel(xlsx_path, sheet_name=target_sheet, engine="openpyxl")
    except Exception as e:
        return False, f"Error leyendo hoja '{target_sheet}': {e}"

    df.columns = [str(c).strip() for c in df.columns]
    cols_order = list(df.columns)

    # columnas comunes reales
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

    # específicas por tipo
    if tipo == "SICUE OUT":
        c_la      = _pick_col(df, "LA", "la")
        c_gestion = _pick_col(df, "Gestion LA", "Gestión LA", "gestion la", "gestión la")
        c_estado  = _pick_col(df, "EstadoFirmas", "Estado firmas", "estado de firmas")
        c_plan    = _pick_col(df, "Enlace plan de estudios", "plan de estudios", "PlanEstudios")
        c_ciudad = _pick_col(df, "Ciudad", "ciudad", "ciudad destino", "Ciudad destino", "city")
    elif tipo == "Erasmus OUT":
        c_la      = _pick_col(df, "LA", "la")
        c_tor     = _pick_col(df, "ToR", "tor")
        c_curso   = _pick_col(df, "Curso", "curso")
        c_acta    = _pick_col(df, "Acta de equivalencias", "ActaEquivalencias", "acta equivalencias")
    else:  # Erasmus IN
        c_la      = _pick_col(df, "LA", "la")
        c_horario = _pick_col(df, "Horario", "horario")

    # construir nueva fila respetando columnas reales
    new_row = {c: None for c in cols_order}
    if c_nombre: new_row[c_nombre] = row_data.get("nombre")

    apes = (row_data.get("apellidos") or "").strip()
    if c_apellidos:
        new_row[c_apellidos] = apes
    else:
        parts = apes.split()
        if c_ap1: new_row[c_ap1] = parts[0] if parts else ""
        if c_ap2: new_row[c_ap2] = " ".join(parts[1:]) if len(parts) > 1 else ""

    if c_email: new_row[c_email] = row_data.get("email")
    if c_univ:  new_row[c_univ]  = row_data.get("destino_origen")

    if c_coords and (lat is not None and lon is not None):
        new_row[c_coords] = f"{lat}, {lon}"
    else:
        if c_lat: new_row[c_lat] = lat
        if c_lon: new_row[c_lon] = lon

    if tipo == "SICUE OUT":
        if c_la:      new_row[c_la]      = row_data.get("la")
        if c_gestion: new_row[c_gestion] = row_data.get("gestion_la") or row_data.get("gestion")
        if c_estado:  new_row[c_estado]  = row_data.get("estado_firmas")
        if c_plan:    new_row[c_plan]    = row_data.get("plan_estudios")
        c_dur    = _pick_col(df, "duracion meses", "duración meses", "duracion_meses")
        c_coord  = _pick_col(df, "Coordinador en destino")
        c_ciudad = _pick_col(df, "Ciudad")
        if c_dur:    new_row[c_dur]    = (row_data.get("dur_sicue") or None)
        if c_coord:  new_row[c_coord]  = (row_data.get("coord_dest") or None)
        if c_ciudad: new_row[c_ciudad] = (row_data.get("ciudad_sicue") or None)

    elif tipo == "Erasmus OUT":
        if c_la:    new_row[c_la]    = row_data.get("la")
        if c_tor:   new_row[c_tor]   = row_data.get("tor")
        if c_curso: new_row[c_curso] = row_data.get("curso")
        if c_acta:  new_row[c_acta]  = row_data.get("acta_equivalencias")
        c_dur   = _pick_col(df, "duracion meses", "duración meses", "duracion_meses")
        c_resp  = _pick_col(df, "responsable programa", "responsable del programa")
        c_la    = _pick_col(df, "LA")
        c_plan  = _pick_col(df, "Enlace plan de estudios", "plan de estudios")
        c_dest  = _pick_col(df, "Destino")
        c_pais  = _pick_col(df, "País", "Pais")
        c_ciudad = _pick_col(df, "Ciudad", "ciudad", "city", "localidad", "poblacion")
        if c_dur:  new_row[c_dur]  = (row_data.get("dur_out") or None)
        if c_resp: new_row[c_resp] = (row_data.get("resp_prog") or None)
        if c_la and row_data.get("la_out"):   new_row[c_la] = row_data.get("la_out")
        if c_plan and row_data.get("plan_out"): new_row[c_plan] = row_data.get("plan_out")
        if c_dest and row_data.get("destino_tabla_out"): new_row[c_dest] = row_data.get("destino_tabla_out")
        if c_pais and row_data.get("pais_out"): new_row[c_pais] = row_data.get("pais_out")
        if c_ciudad and row_data.get("ciudad"): new_row[c_ciudad] = row_data.get("ciudad")

    else:
        if c_la:      new_row[c_la]      = row_data.get("la")
        if c_horario: new_row[c_horario] = row_data.get("horario")
        c_cuatri = _pick_col(df, "Cuatrimestre", "Cuatrimestre")
        c_uo     = _pick_col(df, "Universidad Origen")
        c_pais   = _pick_col(df, "País", "Pais")

        # Si 'Universidad Origen' es la MISMA columna que c_univ,
        # no la usamos para el opcional para no pisar el valor obligatorio.
        if c_uo == c_univ:
            c_uo = None

        if c_cuatri:
            new_row[c_cuatri] = (row_data.get("cuatrimestre_in") or None)
        if c_uo:
            new_row[c_uo] = (row_data.get("uni_origen_in") or None)
        if c_pais:
            new_row[c_pais] = (row_data.get("pais_in") or None)
        # ciudad para Erasmus IN
        c_ciudad = _pick_col(df, "Ciudad", "ciudad", "city", "localidad", "poblacion")
        if c_ciudad and row_data.get("ciudad"):
            new_row[c_ciudad] = row_data.get("ciudad")

    out = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True).reindex(columns=cols_order)

    # Si faltan coordenadas, intentar calcularlas automáticamente para cualquier movilidad
    last_row_idx = len(out) - 1
    coords_cols = [c for c in out.columns if str(c).strip().lower() in ("coordenadas", "latitud", "latitude", "longitud", "longitude")]
    needs_coords = False
    if coords_cols:
        # Considera que faltan si todas están vacías o nulas
        vals = [out.at[last_row_idx, c] for c in coords_cols]
        if all(pd.isna(v) or v in (None, "", "nan", "None") for v in vals):
            needs_coords = True

    if needs_coords:
        try:
            from persistence.excel_update import _recalculate_coords
            _recalculate_coords(out, last_row_idx)
        except Exception as e:
            print(f"[coords] Error al recalcular coordenadas: {e}")

    try:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
            out.to_excel(w, sheet_name=target_sheet, index=False)
    except TypeError:
        with pd.ExcelWriter(xlsx_path, engine="openpyxl", mode="w") as w:
            out.to_excel(w, sheet_name=target_sheet, index=False)
    except PermissionError:
        return False, "El archivo está abierto en otra aplicación."
    except Exception as e:
        return False, f"Error guardando: {e}"

    return True, None


def export_materias_in_excel(dfs, config):
    """
    Crea / actualiza el Excel 'Materias IN' a partir del df de 'Erasmus IN'.
    dfs: dict de DataFrames como el que usas en show_map.
    config: dict cargado de config.json con la clave 'Materias IN'.
    """
    from ui.popup_helpers import _normalize_estudiantes  # import local para evitar ciclos
    erasmus_in_df = dfs.get("Erasmus IN")
    if erasmus_in_df is None:
        return

    rows_out = []
    for _, row in erasmus_in_df.iterrows():
        pais = row.get("pais") or ""
        centro = row.get("universidad") or row.get("centro") or ""
        estudiantes = _normalize_estudiantes(row.get("estudiantes", []))

        for est in estudiantes:
            nombre_est = est.get("estudiante", "")
            materias = est.get("materias_in") or []
            if not isinstance(materias, list):
                continue

            for m in materias:
                if not isinstance(m, dict):
                    continue
                asig = m.get("asignatura", "")
                if not asig:
                    continue
                cuat = m.get("cuat") or ""
                firmado = m.get("firmado") or "x"  # o "" si prefieres

                rows_out.append({
                    "Asignatura": asig,
                    "Estudiante": nombre_est,
                    "Origen": pais,
                    "Centro": centro,
                    "Cuat": cuat,
                    "Firmado": firmado,
                })

    cols = ["Asignatura", "Estudiante", "Origen", "Centro", "Cuat", "Firmado"]
    if rows_out:
        df_out = pd.DataFrame(rows_out, columns=cols)
    else:
        df_out = pd.DataFrame(columns=cols)

    path_materias = config.get("Materias IN")
    if not path_materias:
        return

    df_out.to_excel(path_materias, index=False)



def handle_save_student_query():
    params = st.query_params
    if "save_student" not in params:
        return

    # helper robusto para extraer query params (lista o string)
    def _qp_val(p, key):
        v = p.get(key)
        if v is None:
            return None
        if isinstance(v, list):
            return v[0] if v else ""
        if isinstance(v, str):
            return v
        return str(v)

    # 1) Parámetros básicos
    programa = _qp_val(params, "programa")
    row_id   = _qp_val(params, "row_id")
    idx_str  = _qp_val(params, "idx")

    if programa is None or row_id is None or idx_str is None:
        st.error("Faltan parámetros para guardar el alumno.")
        return

    try:
        idx = int(idx_str)
    except ValueError:
        st.error("Índice de estudiante no válido.")
        return

    # 2) Campos simples del formulario
    campos = {}
    for key in ("estudiante","email","curso","cuatrimestre",
                "duracion_meses","gestion_LA","coordinador_destino",
                "link_la","ToR","acta_equivalencias","link_plan"):
        v = _qp_val(params, key)
        # Solo añadimos el campo si aparece en la query (si el input existía en el form)
        if v is not None:
            campos[key] = v


    # 3) Materias IN (solo Erasmus IN)
    materias_list = []
    materias_raw = _qp_val(params, "materias_raw") or ""
    if materias_raw.strip():
        for line in materias_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                asig, cuat = [p.strip() for p in line.split("|", 1)]
            else:
                asig, cuat = line, ""
            if asig:
                materias_list.append({"asignatura": asig, "cuat": cuat})

    # 4) Localizar ruta del Excel desde config
    config = st.session_state.get("config", {})
    ruta = config.get(programa)

    if ruta is None:
        key_norm = (programa or "").strip().lower()
        norm_map = {
            (k.strip().lower() if isinstance(k, str) else k): v
            for k, v in config.items()
        }
        ruta = norm_map.get(key_norm)
        if ruta is None:
            for k, v in norm_map.items():
                if key_norm and key_norm in str(k):
                    ruta = v
                    break

    if not ruta:
        st.error(f"No se ha encontrado ruta para {programa!r} en config.json")
        return

    try:
        df = pd.read_excel(ruta)
    except Exception as e:
        st.error(f"No se ha podido leer el Excel {ruta}: {e}")
        return

    # --- Caso sin columna 'id' → buscar por email/nombre o añadir ---
    if "id" not in df.columns:
        c_email     = _pick_col(df, "email", "Email")
        c_nombre    = _pick_col(df, "nombre", "Nombre")
        c_apellidos = _pick_col(df, "apellidos", "Apellidos", "apellido1", "apellido2")

        found_idx = None

        # 1) por email
        email_val = (campos.get("email") or "").strip()
        if c_email and email_val:
            mask = df[c_email].astype(str).str.strip().eq(email_val)
            if mask.any():
                found_idx = df.index[mask][0]

        # 2) por nombre + apellidos
        if found_idx is None:
            nombre_val = (campos.get("estudiante") or "").strip()
            apes_val   = (campos.get("apellidos") or "").strip()
            if c_nombre and nombre_val:
                mask_n = df[c_nombre].astype(str).str.strip().str.lower().eq(nombre_val.lower())
                if c_apellidos and apes_val:
                    mask_a = df[c_apellidos].astype(str).str.strip().str.lower().eq(apes_val.lower())
                    mask = mask_n & mask_a
                else:
                    mask = mask_n
                if mask.any():
                    found_idx = df.index[mask][0]

        # 2.1) si se encuentra fila → actualizar
        if found_idx is not None:
            for k, v in campos.items():
                col = _pick_col(df, k, k.capitalize())
                if col:
                    df.at[found_idx, col] = v
            if materias_list:
                col_m = _pick_col(df, "materias_in", "Materias", "materias")
                if col_m:
                    df.at[found_idx, col_m] = str(materias_list)

            try:
                df.to_excel(ruta, index=False)
                st.session_state["_student_saved"] = True
                st.success("✅ Alumno actualizado correctamente.")
            except Exception as e:
                st.error(f"Error guardando Excel: {e}")
            return

        # 2.2) no se encontró → añadir fila nueva
        st.warning("No se encontró 'id' ni coincidencia por email/nombre: se añadirá una nueva fila.")
        try:
            append_user_to_excel(ruta, programa, {**campos, "materias": materias_list}, None)
            st.session_state["_student_saved"] = True
            st.success("✅ Alumno añadido correctamente.")
        except Exception as e:
            st.error(f"Error añadiendo fila: {e}")
        return

    # --- Caso con columna 'id' → actualizar lista 'estudiantes' ---
    mask = df["id"].astype(str) == str(row_id)
    if not mask.any():
        st.error(f"No se ha encontrado la fila con id={row_id} en {programa}.")
        return

    fila_idx = df[mask].index[0]

    est_raw = df.at[fila_idx, "estudiantes"]
    lista_est = _normalize_estudiantes(est_raw)

    if not (0 <= idx < len(lista_est)):
        st.error(f"Índice de estudiante {idx} fuera de rango.")
        return

    est = lista_est[idx] if isinstance(lista_est[idx], dict) else {}
    est.update(campos)
    if programa == "Erasmus IN":
        est["materias_in"] = materias_list

    lista_est[idx] = est
    df.at[fila_idx, "estudiantes"] = json.dumps(lista_est, ensure_ascii=False)

    try:
        df.to_excel(ruta, index=False)
        st.session_state["_student_saved"] = True
        st.success("✅ Alumno actualizado correctamente.")
    except Exception as e:
        st.error(f"No se ha podido guardar en {ruta}: {e}")
