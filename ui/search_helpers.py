from __future__ import annotations
import unicodedata
from typing import Dict, List, Tuple
import pandas as pd
import streamlit as st

STOPWORDS = {"de", "del", "la", "las", "los", "y", "da", "do", "dos", "das"}

def quitar_tildes(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def _norm(s: str) -> str:
    return quitar_tildes(str(s).strip().lower())

def build_search_index(dfs: Dict[str, pd.DataFrame]) -> None:
    if not isinstance(dfs, dict):
        st.session_state["search_index_options"] = [("", "")]
        st.session_state["search_index"] = []
        return

    by_cat: Dict[str, Dict[str, str]] = {
        "alumno": {},
        "nombre": {},
        "apellido": {},
        "ciudad": {},
        "pais": {},
        "universidad": {},
        "email": {},
    }

    particles = {"de", "del", "la", "las", "los", "da", "do", "dos", "das"}

    def add(term: str, cat: str):
        term = str(term).strip()
        if len(term) < 2:
            return
        n = _norm(term)
        if len(n) < 2:
            return
        if cat not in by_cat:
            by_cat[cat] = {}
        # si hay colisión, quédate con el más largo/bonito
        if n not in by_cat[cat] or len(term) > len(by_cat[cat][n]):
            by_cat[cat][n] = term

    def split_nombre_apellidos(full: str) -> tuple[list[str], list[str]]:
        """Según tu regla: primer espacio separa nombre de apellidos."""
        s = " ".join(str(full).replace("\u00A0", " ").split())
        if not s:
            return [], []

        if "," in s:
            # "APELLIDOS, NOMBRES"
            ap_part, nom_part = [p.strip() for p in s.split(",", 1)]
            nombres = [t for t in nom_part.split() if t]
            apellidos = [t for t in ap_part.split() if t]
            return nombres, apellidos

        parts = s.split()
        if len(parts) == 1:
            return [parts[0]], []
        # criterio: primer token = nombre, resto = apellidos
        return [parts[0]], parts[1:]

    col_to_cat = {
        "ciudad": "ciudad",
        "city": "ciudad",
        "pais": "pais",
        "país": "pais",
        "country": "pais",
        "universidad": "universidad",
        "destino": "universidad",
        "nombre": "alumno",
        "apellido": "apellido",
        "apellido1": "apellido",
        "apellido2": "apellido",
        "apellidos": "apellido",
        "estudiante": "alumno",
        "full_name": "alumno",
        "email": "email",
    }

    # 1) datos anidados en 'estudiantes'
    for _, df in dfs.items():
        if df is None or df.empty:
            continue

        if "estudiantes" in df.columns:
            for lista in df["estudiantes"]:
                if not isinstance(lista, list):
                    continue
                for e in lista:
                    full = str(e.get("estudiante", "")).strip()
                    email = str(e.get("email", "")).strip()
                    ciudad = str(e.get("ciudad", "")).strip()

                    if full:
                        # Alumno: solo nombre completo
                        add(full, "alumno")

                        # Separación bonita: nombre (solo 1º token) y apellidos (resto)
                        nombres, apellidos = split_nombre_apellidos(full)

                        # Nombre(s): nos quedamos con el primero (tu regla)
                        if nombres:
                            n0 = nombres[0].strip()
                            if len(n0) > 1 and _norm(n0) not in STOPWORDS:
                                add(n0, "nombre")

                        # Apellidos: tokens “núcleo” (sin partículas) + apellidos completos juntos
                        if apellidos:
                            ap_full = " ".join(apellidos).strip()
                            if len(ap_full) > 2:
                                add(ap_full, "apellido")

                            for tok in apellidos:
                                t = tok.strip()
                                if len(t) > 2 and _norm(t) not in particles and _norm(t) not in STOPWORDS:
                                    add(t, "apellido")

                    if email and "@" in email:
                        add(email, "email")

                    if ciudad:
                        add(ciudad, "ciudad")

        # 2) columnas planas
        for col in df.columns:
            col_norm = str(col).strip().lower()
            if col_norm in col_to_cat:
                cat = col_to_cat[col_norm]
                serie = df[col].dropna().astype(str).str.strip()
                for v in pd.unique(serie):
                    add(v, cat)

    cat_order = [
        ("alumno", "Alumno"),
        ("nombre", "Nombre"),
        ("apellido", "Apellido"),
        ("ciudad", "Ciudad"),
        ("pais", "País"),
        ("universidad", "Universidad"),
        ("email", "Email"),
    ]

    options: List[Tuple[str, str]] = [("", "")]
    for cat, label in cat_order:
        vals = sorted(set(by_cat.get(cat, {}).values()), key=_norm)
        for v in vals:
            options.append((v, f"{label} · {v}"))

    st.session_state["search_index"] = [v for (v, _) in options if v]
    st.session_state["search_index_options"] = options



def render_search_box(parent=None) -> str:
    parent = parent or st.sidebar
    parent.markdown("**Buscar alumno, ciudad, universidad...**")

    all_opts = st.session_state.get("search_index_options", [("", "")])
    options = [(v, lbl) for (v, lbl) in all_opts if v]

    selected = parent.selectbox(
        label=" ",
        options=options,
        index=None,
        key="search_select",
        label_visibility="collapsed",
        format_func=lambda o: o[1],
        placeholder="Buscar",
    )

    st.session_state["search_text"] = selected[0] if selected else ""
    return st.session_state["search_text"].strip()

