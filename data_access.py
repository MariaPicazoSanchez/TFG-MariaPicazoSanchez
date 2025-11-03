import pandas as pd
import html
import os
import re

def _parse_coords(s: str):
    """extrae dos números (soporta coma o punto decimal, y separadores variados)"""
    nums = re.findall(r"-?\d+[.,]?\d*", str(s))
    if len(nums) >= 2:
        lat = float(nums[0].replace(",", "."))
        lon = float(nums[1].replace(",", "."))
        return lat, lon
    return None, None

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



def generate_student_card_out(row):
    """Ficha HTML moderna y limpia para Erasmus OUT."""
    nombre = html.escape(str(row["estudiante"]))
    destino = html.escape(str(row.get("universidad", "")))
    pais = html.escape(str(row.get("pais", "")))
    link_LA = str(row.get("link_LA", ""))
    link_plan = str(row.get("link_plan", ""))
    curso = html.escape(str(row.get("curso", "No especificado")))
    tor = html.escape(str(row.get("ToR", "No disponible")))
    acta = html.escape(str(row.get("acta_equivalencias", "No disponible")))

    return f"""
    <div style="
        font-family: 'Segoe UI', Roboto, Arial, sans-serif;
        font-size: 14px;
        color: #222;
        background: #ffffff;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 0 10px rgba(0,0,0,0.2);
        max-width: 420px;
        line-height: 1.5;
    ">
        <h4 style="
            margin: 0 0 8px 0;
            font-size: 16px;
            color: #004AAD;
            border-bottom: 2px solid #004AAD;
            padding-bottom: 4px;
        ">{nombre}</h4>

        <p style="margin: 6px 0;">
            <b>Universidad:</b> {destino}<br>
            <b>País:</b> {pais}<br>
            <b>Curso:</b> {curso}
        </p>

        <div style="background: #f6f8fa; padding: 8px; border-radius: 6px; margin-top: 10px;">
            <p style="margin: 6px 0;">
                <b>Learning Agreement:</b> <a href="{link_LA}" target="_blank" style="color:#004AAD;">Abrir LA</a><br>
                <b>ToR:</b> {tor}<br>
                <b>Acta de equivalencias:</b> {acta}<br>
                <b>Plan de estudios:</b> <a href="{link_plan}" target="_blank" style="color:#004AAD;">Ver plan</a>
            </p>
        </div>
    </div>
    """
