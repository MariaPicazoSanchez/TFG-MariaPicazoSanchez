import pandas as pd
import os, re, unicodedata

def norm_sheet(s: str) -> str:
    if s is None: return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("\u00A0", " ")
    s = re.sub(r"[\u2012\u2013\u2014\u2015\u2212]+", "-", s)  # guiones “raros” → -
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def resolve_sheet(sel: str, candidates: list[str]) -> str | None:
    """Match exacto normalizado; si no hay exacto, intenta contains único."""
    sel_n = norm_sheet(sel)
    for c in candidates or []:
        if norm_sheet(c) == sel_n:
            return c
    cont = [c for c in candidates or [] if sel_n in norm_sheet(c)]
    return cont[0] if len(cont) == 1 else None

def sheets_for(path: str) -> list[str]:
    """Lista hojas del Excel; CSV devuelve ['__CSV__']."""
    if not path or not os.path.exists(path):
        return []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return ["__CSV__"]
    try:
        with pd.ExcelFile(path, engine="openpyxl") as xf:
            return list(xf.sheet_names)
    except Exception:
        return []
