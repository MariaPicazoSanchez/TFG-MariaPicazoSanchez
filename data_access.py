import pandas as pd
import os
import re
import html

# --- util: robustez para columnas con variantes/typos ---
def _pick(df, *aliases):
    """Devuelve el nombre real de la primera columna existente entre los alias dados."""
    def norm(s): 
        return re.sub(r"\s+", " ", str(s).strip().lower())
    norm_map = {norm(c): c for c in df.columns}
    for a in aliases:
        if a is None: 
            continue
        if norm(a) in norm_map:
            return norm_map[norm(a)]
    # intenta con variantes comunes (p.ej. Cuatirmestre -> Cuatrimestre)
    for a in aliases:
        if a is None: 
            continue
        for k, v in norm_map.items():
            if norm(a) in k or k in norm(a):
                return v
    return None

def _parse_coords(s: str):
    """Extrae lat/lon tolerando coma o punto y separadores variados."""
    nums = re.findall(r"-?\d+[.,]?\d*", str(s))
    if len(nums) >= 2:
        lat = float(nums[0].replace(",", "."))
        lon = float(nums[1].replace(",", "."))
        return lat, lon
    return None, None

# ==============================
#   ERASMUS OUT (ya lo tienes)
# ==============================
def load_erasmus_out(path):
    """Carga los datos de Erasmus OUT y agrupa por universidad."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [col.strip() for col in df.columns]

    df["estudiante"] = (
        df["nombre"].astype(str)
        + " "
        + df["apellido1"].astype(str)
        + " "
        + df.get("apellido2", "").fillna("").astype(str)
    )

    lats, lons = [], []
    for val in df["Coordenadas"]:
        lat, lon = _parse_coords(val)
        lats.append(lat); lons.append(lon)
    df["latitud"] = pd.to_numeric(lats, errors="coerce")
    df["longitud"] = pd.to_numeric(lons, errors="coerce")

    df.rename(
        columns={
            "Destino": "universidad",
            "País": "pais",
            "LA": "link_LA",
            "Plan de estudios": "link_plan",
        },
        inplace=True,
    )

    grouped = (
        df.groupby(["universidad", "pais", "latitud", "longitud"], dropna=False)
          .apply(lambda g: g.to_dict(orient="records"))
          .reset_index(name="estudiantes")
    )
    return grouped

# ==============================
#   ERASMUS IN
# ==============================
def load_erasmus_in(path):
    """Carga Erasmus IN y agrupa por universidad/pais/coords."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [col.strip() for col in df.columns]

    # aliases
    col_nombre = _pick(df, "nombre")
    col_ap1 = _pick(df, "apellido1")
    col_ap2 = _pick(df, "apellido2")
    col_email = _pick(df, "email")
    col_cuatri = _pick(df, "Cuatrimestre", "Cuatirmestre")
    col_la = _pick(df, "LA")
    col_uni = _pick(df, "Universidad Origen")
    col_pais = _pick(df, "País")
    col_coords = _pick(df, "Coordenadas")

    # estudiante
    parts = []
    if col_nombre: parts.append(df[col_nombre].astype(str))
    if col_ap1:    parts.append(df[col_ap1].astype(str))
    if col_ap2:    parts.append(df[col_ap2].fillna("").astype(str))
    if parts:
        s = parts[0]
        for p in parts[1:]:
            s = s + " " + p
        df["estudiante"] = s.str.replace(r"\s+", " ", regex=True).str.strip()
    else:
        df["estudiante"] = df[col_email].astype(str).str.split("@").str[0] if col_email else ""

    # coords
    if col_coords:
        lats, lons = zip(*df[col_coords].map(_parse_coords))
    else:
        lats, lons = [None]*len(df), [None]*len(df)
    df["latitud"] = pd.to_numeric(lats, errors="coerce")
    df["longitud"] = pd.to_numeric(lons, errors="coerce")

    # normaliza nombres
    df["universidad"] = df[col_uni] if col_uni else None
    df["pais"] = df[col_pais] if col_pais else None
    df["link_LA"] = df[col_la] if col_la else None
    df["cuatrimestre"] = df[col_cuatri] if col_cuatri else None

    def _to_records(g):
        cols = ["estudiante", "cuatrimestre", "link_LA"]
        if col_email: cols.insert(1, col_email)
        cols = [c for c in cols if c in g.columns]
        out = g[cols].copy()
        if col_email and col_email in out.columns:
            out = out.rename(columns={col_email: "email"})
        return out.to_dict(orient="records")

    grouped = (
        df.groupby(["universidad", "pais", "latitud", "longitud"], dropna=False)
          .apply(_to_records)
          .reset_index(name="estudiantes")
    )
    return grouped

# ==============================
#   SICUE OUT
# ==============================
def load_sicue_out(path):
    """Lee SICUE OUT y agrupa por universidad+ciudad (coords si existen)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo: {path}")

    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [col.strip() for col in df.columns]

    col_nombre = _pick(df, "nombre")
    col_ap1 = _pick(df, "apellido1")
    col_ap2 = _pick(df, "apellido2")
    col_email = _pick(df, "email")
    col_dur = _pick(df, "duracion meses", "duracion_meses")
    col_coord_dest = _pick(df, "Coordinador en destino")
    col_la = _pick(df, "LA")
    col_gestion = _pick(df, "Gestion LA", "Gestión LA")
    col_destino = _pick(df, "Destino")
    col_ciudad = _pick(df, "Ciudad")
    col_coords = _pick(df, "Coordenadas")

    parts = []
    if col_nombre: parts.append(df[col_nombre].astype(str))
    if col_ap1:    parts.append(df[col_ap1].astype(str))
    if col_ap2:    parts.append(df[col_ap2].fillna("").astype(str))
    if parts:
        s = parts[0]
        for p in parts[1:]:
            s = s + " " + p
        df["estudiante"] = s.str.replace(r"\s+", " ", regex=True).str.strip()
    else:
        df["estudiante"] = df[col_email].astype(str).str.split("@").str[0] if col_email else ""


    if col_coords:
        lats, lons = zip(*df[col_coords].map(_parse_coords))
        df["latitud"] = pd.to_numeric(lats, errors="coerce")
        df["longitud"] = pd.to_numeric(lons, errors="coerce")
    else:
        df["latitud"] = pd.NA
        df["longitud"] = pd.NA

    df["universidad"] = df[col_destino] if col_destino else None
    df["ciudad"] = df[col_ciudad] if col_ciudad else None
    df["pais"] = None

    def _to_records(g):
        cols = ["estudiante", "link_LA", "gestion_LA", "coordinador_destino", "duracion_meses"]
        # mapear nombres fuente -> destino si existen
        mapping = {}
        if col_la:          mapping[col_la] = "link_LA"
        if col_gestion:     mapping[col_gestion] = "gestion_LA"
        if col_coord_dest:  mapping[col_coord_dest] = "coordinador_destino"
        if col_dur:         mapping[col_dur] = "duracion_meses"
        if col_email:       mapping[col_email] = "email"

        keep = ["estudiante"] + [k for k in mapping.keys() if k in g.columns]
        out = g[keep].copy()
        out = out.rename(columns=mapping)
        return out.to_dict(orient="records")

    grouped = (
        df.groupby(["universidad", "ciudad", "latitud", "longitud"], dropna=False)
          .apply(_to_records)
          .reset_index(name="estudiantes")
    )
    grouped["pais"] = None
    grouped = grouped[["universidad", "pais", "ciudad", "latitud", "longitud", "estudiantes"]]
    return grouped


# ==============================
#   Auto-detección
# ==============================
def load_mobility_any(path):
    """Detecta por columnas y llama al loader correspondiente."""
    df_head = pd.read_excel(path, engine="openpyxl", nrows=1)
    cols = {c.strip().lower() for c in df_head.columns}

    # pistas de tipo
    if "universidad origen" in cols or "cuatrimestre" in cols or "cuatirmestre" in cols:
        return load_erasmus_in(path)
    if "coordinador en destino" in cols or "gestion la" in cols or "ciudad" in cols:
        return load_sicue_out(path)
    return load_erasmus_out(path)
