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
    """
    Construye st.session_state["search_index_options"] como lista de opciones
    para un selectbox con categorías (alumnos, apellidos, ciudades, países, universidades...).

    Cada opción es una tupla: (valor_real_para_buscar, etiqueta_bonita_para_UI)
    """
    if not isinstance(dfs, dict):
        st.session_state["search_index_options"] = [("", "")]
        st.session_state["search_index"] = []
        return

    # norm -> (valor, categoria)
    items: Dict[str, Tuple[str, str]] = {}

    def add(term: str, cat: str):
        term = str(term).strip()
        if len(term) < 2:
            return
        n = _norm(term)
        if len(n) < 2:
            return
        # dedupe por norm (si hay colisión, nos quedamos con el más “bonito/largo”)
        if n not in items or len(term) > len(items[n][0]):
            items[n] = (term, cat)

    # Mapeo de columnas a categorías
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
    }

    # 1) datos anidados en columna 'estudiantes'
    for _, df in dfs.items():
        if df is None or df.empty:
            continue

        if "estudiantes" in df.columns:
            for lista in df["estudiantes"]:
                if not isinstance(lista, list):
                    continue
                for e in lista:
                    nombre = str(e.get("estudiante", "")).strip()
                    email = str(e.get("email", "")).strip()
                    ciudad = str(e.get("ciudad", "")).strip()

                    if nombre:
                        add(nombre, "alumno")
                        # tokens para sugerir apellidos/nombres sueltos (evita "de", "del", etc.)
                        for tok in nombre.replace(",", " ").split():
                            t = tok.strip()
                            if len(t) > 2 and _norm(t) not in STOPWORDS:
                                add(t, "apellido")

                    if email and "@" in email:
                        add(email, "email")

                    if ciudad:
                        add(ciudad, "ciudad")

        # 2) columnas “planas”
        for col in df.columns:
            col_norm = str(col).strip().lower()
            if col_norm in col_to_cat:
                cat = col_to_cat[col_norm]
                serie = df[col].dropna().astype(str).str.strip()
                for v in pd.unique(serie):
                    add(v, cat)

    # Orden y emojis para UI
    cat_order = [
        ("alumno", "👤 Alu."),
        ("apellido", "🧾 Ape."),
        ("ciudad", "🏙️ Ciudad"),
        ("pais", "🌍 País"),
        ("universidad", "🎓 Uni."),
        ("email", "✉️ Email"),
    ]

    by_cat: Dict[str, List[str]] = {k: [] for k, _ in cat_order}
    for _, (val, cat) in items.items():
        if cat in by_cat:
            by_cat[cat].append(val)

    options: List[Tuple[str, str]] = [("", "")]
    for cat, label in cat_order:
        vals = sorted(set(by_cat[cat]), key=_norm)
        for v in vals:
            options.append((v, f"{label} · {v}"))

    # Para compatibilidad con tu versión anterior
    st.session_state["search_index"] = [v for (v, _) in options if v]
    st.session_state["search_index_options"] = options


def render_search_box(parent=None) -> str:
    parent = parent or st.sidebar
    parent.markdown("**Buscar alumno, ciudad, universidad...**")

    # (tu CSS igual)
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] div[data-baseweb="select"] { font-size: 0.88rem; }
        div[role="listbox"] { font-size: 0.88rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    all_opts = st.session_state.get("search_index_options", [("", "")])
    options = [(v, lbl) for (v, lbl) in all_opts if v]

    current_text = st.session_state.get("search_text", "")
    cur_n = _norm(current_text)

    default_index = None
    for i, (val, _) in enumerate(options):
        if _norm(val) == cur_n:
            default_index = i
            break

    selected = parent.selectbox(
        label="",
        options=options,
        index=default_index,
        key="search_select",
        label_visibility="collapsed",
        format_func=lambda o: o[1],
        placeholder="Buscar",
    )

    st.session_state["search_text"] = selected[0] if selected else ""
    return st.session_state["search_text"].strip()
