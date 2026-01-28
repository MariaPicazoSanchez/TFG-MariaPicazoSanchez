import os
import unicodedata
import streamlit as st
import urllib.request
import pandas as pd
import time
import streamlit.components.v1 as components
from ui import setup_session, sidebar_controls, render_new_user_form, show_map, render_stats_view, build_search_index, render_search_box
from utils import handle_open_pdf_query, handle_open_excel_query
from persistence import load_all_dataframes, get_materias_in_por_estudiante


def quitar_tildes(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )

def coincide_en_estudiantes(valor, texto_busqueda_normalizado: str) -> bool:
    """
    valor: lista de dicts (columna 'estudiantes')
    texto_busqueda_normalizado: ya en minúsculas y sin tildes.
    """
    if not isinstance(valor, list):
        return False

    for e in valor:
        # Nombres, email y ciudad del estudiante
        for campo in ("estudiante", "email", "ciudad"):
            val = quitar_tildes(str(e.get(campo, "")).lower())
            if texto_busqueda_normalizado in val:
                return True
    return False

def main():
    st.set_page_config(page_title="Movilidad ESII", layout="wide", initial_sidebar_state="expanded" )
    inject_js_ping(8000)
    if "data_version" not in st.session_state:
        st.session_state["data_version"] = 0

    # Aviso temprano si la API aún no está lista (no bloqueante)
    try:
        api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
        with urllib.request.urlopen(f"{api_url}/health", timeout=1) as r:
            api_ok = (r.status == 200)
    except Exception:
        api_ok = False
    if not api_ok:
        st.info("La API está iniciándose…", icon="🕒")
    # Manejo de query params al inicio
    try:
        params = st.query_params
        # st.query_params returns lists for each key: {'k': ['v']}
        def _qp_val(p, k):
            v = p.get(k)
            if v is None:
                return None
            if isinstance(v, list):
                return v[0] if v else None
            return v

        clear_cache_flag = _qp_val(params, "clear_cache")
        saved_flag = _qp_val(params, "student_saved")
    except Exception:
        params = st.experimental_get_query_params()
        clear_cache_flag = params.get("clear_cache", [None])[0] if params.get("clear_cache") else None
        saved_flag = params.get("student_saved", [None])[0] if params.get("student_saved") else None

    # Si viene del guardado, limpia caché
    if clear_cache_flag == "1":
        st.cache_data.clear()

    if saved_flag == "1":
        st.session_state["data_version"] += 1
        st.success("✅ Alumno guardado correctamente. Los datos se han actualizado.")
        st.rerun()
    elif saved_flag == "0":
        st.error("❌ No se pudieron guardar los cambios.")
    

    setup_session()
    config = st.session_state["config"]

    # Render sidebar early so `global_sheet` is set before loading data
    base_map = sidebar_controls()

    # Asegura defaults (porque ahora los vas a leer ANTES de map_filters)
    if "selected_programs" not in st.session_state:
        st.session_state["selected_programs"] = {
            "Erasmus IN": False,
            "Erasmus OUT": False,
            "SICUE OUT": False,
        }
    if "only_erasmus_out_no_LA" not in st.session_state:
        st.session_state["only_erasmus_out_no_LA"] = False
    if "global_sheet" not in st.session_state:
        st.session_state["global_sheet"] = "Todas"

    global_sheet = st.session_state.get("global_sheet", None)
    def _get_config_mtimes(cfg):
        # Return a tuple of mtimes for the configured Excel files (stable order)
        keys = ["Erasmus OUT", "Erasmus IN", "SICUE OUT"]
        mtimes = []
        for k in keys:
            p = cfg.get(k)
            try:
                if p and os.path.exists(p):
                    mtimes.append(os.path.getmtime(p))
                else:
                    mtimes.append(None)
            except Exception:
                mtimes.append(None)
        return tuple(mtimes)

    @st.cache_data(show_spinner=False)
    def cached_load_all_dataframes(cfg, sheet, data_version, src_mtimes):
        # `data_version` and `src_mtimes` are dummy args used to invalidate the cache
        return load_all_dataframes(cfg, sheet)

    t0 = time.perf_counter()
    cfg_mtimes = _get_config_mtimes(config)
    dfs = cached_load_all_dataframes(config, global_sheet, st.session_state.get("data_version", 0), cfg_mtimes)
    t1 = time.perf_counter()
    try:
        print(f"[perf] load_all_dataframes: {(t1 - t0)*1000:.1f} ms")
    except Exception:
        pass

    # Debug: print modification times of configured Excel files to help diagnose stale reads
    try:
        for k in ("Erasmus OUT", "Erasmus IN", "SICUE OUT"):
            p = config.get(k)
            if p and os.path.exists(p):
                try:
                    m = os.path.getmtime(p)
                    print(f"[files] {k}: {p} -> mtime={m}")
                except Exception as e:
                    print(f"[files] {k}: {p} -> stat error: {e}")
            else:
                print(f"[files] {k}: not found or not configured: {p}")
    except Exception:
        pass

    # Aplica filtros de programas y OUT sin LA (para que el índice sea coherente)
    selected = st.session_state.get("selected_programs", {})
    activos = [k for k, v in selected.items() if v]
    if isinstance(dfs, dict) and len(activos) > 0:
        dfs = {k: v for k, v in dfs.items() if k in activos}

    only_no_la = st.session_state.get("only_erasmus_out_no_LA", False)
    if only_no_la and isinstance(dfs, dict) and "Erasmus OUT" in dfs:
        df_out = dfs["Erasmus OUT"]
        if "link_LA" in df_out.columns:
            mask = df_out["link_LA"].isna() | (df_out["link_LA"].astype(str).str.strip() == "")
            dfs["Erasmus OUT"] = df_out[mask]

  
    t2 = time.perf_counter()
    build_search_index(dfs)
    t3 = time.perf_counter()
    try:
        print(f"[perf] build_search_index: {(t3 - t2)*1000:.1f} ms")
    except Exception:
        pass

    # A partir de aquí tu flujo normal:

    # =========================
    # FILTRO POR BÚSQUEDA (SIN MÉTODOS EXTERNOS)
    # =========================
    search_text = st.session_state.get("search_text", "").strip()
    needle = quitar_tildes(search_text.lower()).strip()

    if isinstance(dfs, dict) and len(needle) >= 2:
        row_fields = [
            "universidad", "pais", "país", "ciudad", "destino",
            "nombre", "apellidos", "apellido", "apellido1", "apellido2",
            "estudiante", "email", "full_name",
        ]

        dfs_filtrado = {}
        for program, df in dfs.items():
            if df is None or df.empty:
                continue

            # 1) Match en columnas planas (vectorizado)
            cols = [c for c in row_fields if c in df.columns]
            mask_flat = pd.Series(False, index=df.index)
            if cols:
                blob = df[cols].fillna("").astype(str).agg(" ".join, axis=1)
                blob_norm = blob.map(lambda x: quitar_tildes(x.lower()))
                mask_flat = blob_norm.str.contains(needle, na=False)

            # 2) Match en estudiantes
            mask_est = pd.Series(False, index=df.index)
            if "estudiantes" in df.columns:
                mask_est = df["estudiantes"].apply(lambda v: coincide_en_estudiantes(v, needle))

            mask = mask_flat | mask_est
            df2 = df.loc[mask].copy()

            if not df2.empty:
                dfs_filtrado[program] = df2

        dfs = dfs_filtrado


    handle_open_pdf_query()
    handle_open_excel_query()

    st.title("Visualizador de Movilidad ESII")

    # ==============================================
    # MUESTRA DE MATERIAS IN POR ESTUDIANTE
    # ==============================================
    if dfs and isinstance(dfs, dict) and any(not df.empty for df in dfs.values()):
        @st.cache_data(show_spinner=False)
        def cached_materias_in_por_estudiante(cfg, data_version, src_mtimes):
            # include `data_version` and `src_mtimes` to force invalidation when data changes
            return get_materias_in_por_estudiante(cfg)

        t4 = time.perf_counter()
        materias_in_por_est = cached_materias_in_por_estudiante(config, st.session_state.get("data_version", 0), cfg_mtimes)
        t5 = time.perf_counter()
        try:
            print(f"[perf] materias_in_loader: {(t5 - t4)*1000:.1f} ms")
        except Exception:
            pass
    else:
        materias_in_por_est = {}
        st.info("No hay datos disponibles para mostrar. Por favor, revisa la configuración o selecciona otra hoja.")

    # Tipos disponibles según config y existencia de ficheros
    available_types = [
        k for k in ("Erasmus OUT", "Erasmus IN", "SICUE OUT")
        if config.get(k) and os.path.exists(config[k])
    ]
    # ==============================================
    # RENDERIZA VISTAS SEGÚN SELECCIÓN
    # ==============================================

    if st.session_state.get("view", "map") == "new_user":
        render_new_user_form(available_types, config)
    elif st.session_state.get("view", "map") == "stats":
        render_stats_view()
    else:
        if not (isinstance(dfs, dict) and any(df is not None and not df.empty for df in dfs.values())):
            st.info("Cargando datos y mapa…")
            st.stop()
        show_map(dfs, base_map, materias_in_por_est, activos, only_no_la)
        

def inject_js_ping(interval_ms: int = 8000):
    api_url = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
    components.html(
        f"""
        <script>
        (function() {{
          const url = "{api_url}/ping";
          function ping() {{
            try {{
              fetch(url, {{ method: "GET", cache: "no-store" }}).catch(() => {{}});
            }} catch (e) {{}}
          }}
          ping();
          setInterval(ping, {interval_ms});
        }})();
        </script>
        """,
        height=0, width=0
    )

if __name__ == "__main__":
    main()
