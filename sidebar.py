import streamlit as st
import json
import os
import xlrd
import pandas as pd

CONFIG_FILE = "config.json"

USE_LOCAL_PICKER = True  # False en Cloud/producción (allí no puede abrir el diálogo del cliente)

def _list_sheets_in_file(path: str) -> list[str]:
    if not path or not os.path.exists(path):
        return []
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return ["__CSV__"]
    # intento con pandas
    try:
        xls = pd.ExcelFile(path)  # requiere openpyxl para .xlsx
        return list(xls.sheet_names)
    except Exception:
        pass
    # fallback para .xlsx
    try:
        if ext in (".xlsx", ".xlsm", ".xltx", ".xltm"):
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            return list(wb.sheetnames)
    except Exception:
        pass
    # fallback para .xls (si tienes xlrd 1.2.0)
    try:
        if ext == ".xls":
            
            wb = xlrd.open_workbook(path, on_demand=True)
            return wb.sheet_names()
    except Exception:
        pass
    return []

def _unique_sheets_from_config_or_files(cfg: dict) -> list[str]:
    """Une hojas de todos los Excels; si no hay 'sheets' en config, las detecta leyendo los ficheros."""
    keys = ("Erasmus OUT", "Erasmus IN", "SICUE OUT")
    sheets_map = cfg.get("sheets", {}) or {}
    names = set()
    for k in keys:
        lst = sheets_map.get(k)
        if not lst:
            p = cfg.get(k)
            if p:
                lst = _list_sheets_in_file(p)
        for name in (lst or []):
            if name and str(name) != "__CSV__":
                names.add(str(name))
    return sorted(names)

def pick_local_file(initial_path: str | None = None):
    """Abre el diálogo nativo del SO y devuelve la ruta seleccionada (o None). Solo en local."""
    import os
    try:
        import tkinter as tk
        from tkinter import filedialog as fd
    except Exception as e:
        st.sidebar.error(f"Tkinter no disponible: {e}")
        return None

    # Si el input ya tiene algo, intenta abrir en esa carpeta
    initdir = None
    if initial_path:
        cand = os.path.dirname(initial_path)
        if os.path.isdir(cand):
            initdir = cand

    root = tk.Tk()
    root.withdraw()
    try:
        root.update_idletasks()
        root.lift()
        root.attributes("-topmost", True)   # trae al frente
        root.after(0, root.focus_force)
    except Exception:
        pass

    try:
        path = fd.askopenfilename(
            parent=root,
            initialdir=initdir if initdir else None,
            title="Selecciona un archivo",
            filetypes=[("Excel/CSV", "*.xlsx *.xls"), ("Todos", "*.*")]
        )
    finally:
        try:
            root.destroy()
        except Exception:
            pass

    return path or None

def load_config():
    """Carga las rutas guardadas desde config.json, si existe."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config):
    """Guarda las rutas actuales en config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def setup_session():
    """Inicializa variables en session_state."""
    if "config" not in st.session_state:
        st.session_state["config"] = load_config()
    if "show_routes" not in st.session_state:
        st.session_state["show_routes"] = False


def open_routes_editor():
    """Callback: muestra el editor de rutas."""
    st.session_state["show_routes"] = True


def close_routes_editor(new_config=None):
    """
    Cierra el panel de modificación de rutas y, si se pasa una nueva configuración,
    comprueba las rutas y guarda en config.json si son válidas.
    """
    if new_config:
        ok, errors = verify_paths(new_config)

        if not ok:
            st.sidebar.error("❌ No se encontraron los siguientes archivos:")
            for err in errors:
                st.sidebar.error(f"- {err}")
            return

        save_config(new_config)
        st.session_state["config"] = new_config
        st.toast("✅ Rutas guardadas correctamente")

    st.session_state["show_routes"] = False
    st.rerun()


def verify_paths(config):
    """Verifica que todas las rutas existan. Devuelve (ok, lista_errores)."""
    errors = [f"{nombre}: {ruta}" for nombre, ruta in config.items() if not os.path.exists(ruta)]
    return (len(errors) == 0, errors)

def get_placeholder(config, key):
    """Devuelve un placeholder: usa la ruta guardada o un valor por defecto si está vacío."""
    ruta = config.get(key, "")
    return ruta if ruta else f"Inserte la ruta del archivo {key} aquí"

def route_editor(config):
    st.sidebar.subheader("📁 Modificar rutas de los archivos Excel")

    entries = [
        ("SICUE OUT", "📘 SICUE OUT"),
        ("Erasmus IN", "🌍 Erasmus IN"),
        ("Erasmus OUT", "✈️ Erasmus OUT"),
        ("Materias IN", "📑 Materias IN"),
    ]

    new_config = {}
    for key, label in entries:
        col_text, col_btn = st.sidebar.columns([8, 2])

        text_key = f"rt_{key}"
        buf_key  = f"__set_{text_key}"
        btn_key  = f"btn_open_{key}"

        # 1) Sembrar desde config si no existe en session_state
        if text_key not in st.session_state:
            st.session_state[text_key] = config.get(key, "")

        # 2) Aplicar buffer (si se eligió archivo) ANTES de instanciar el input
        if buf_key in st.session_state:
            st.session_state[text_key] = st.session_state.pop(buf_key)

        # 3) Input
        col_text.text_input(
            label,
            key=text_key,
            placeholder=get_placeholder(config, key)
        )

        # 4) Botón 📁: abrir selector del SO y SOLO poner la ruta en el input
        col_btn.text("")  # espacio para que no suba el boton
        col_btn.text("") 

        if col_btn.button("📁", key=btn_key, help="Seleccionar archivo del equipo"):
            if USE_LOCAL_PICKER:
                current_val = st.session_state.get(text_key, "")
                path = pick_local_file(current_val)
                if path:
                    st.session_state[buf_key] = path
                    st.rerun()
            else:
                st.sidebar.warning("Ejecuta la app en local para seleccionar rutas del equipo.")


        # 5) Al construir la nueva config, conservar lo previo si el input está vacío
        val = st.session_state.get(text_key, "")
        new_config[key] = val if val.strip() != "" else config.get(key, "")


    col1, col2 = st.sidebar.columns(2)
    if col1.button("💾", use_container_width=True):
        close_routes_editor(new_config)
    if col2.button("❌", use_container_width=True):
        st.sidebar.info("No se han guardado cambios.")
        st.session_state["show_routes"] = False
        st.rerun()

def _unique_sheets_from_config(cfg: dict) -> list[str]:
    """Devuelve la lista de hojas únicas (union) ignorando '__CSV__'."""
    sheets_map = cfg.get("sheets", {}) or {}
    names = set()
    for _type, lst in sheets_map.items():
        for name in (lst or []):
            if name and str(name) != "__CSV__":
                names.add(str(name))
    return sorted(names)


def sidebar_controls():
    """Crea la barra lateral con filtros y gestión de rutas."""  
    # --- NUEVO USUARIO ---
    if "view" not in st.session_state:
        st.session_state["view"] = "map"

    if st.session_state["view"] == "new_user":
        if st.sidebar.button("⬅️ Volver al mapa", use_container_width=True):
            st.session_state["view"] = "map"
            st.rerun()
        # Si quieres ocultar el resto de controles cuando estás en 'new_user',
    else:
        # ==========================
        #  SECCIÓN DE FILTROS
        # ==========================
        st.sidebar.header("Filtros")  
        cfg = st.session_state.get("config", {})
        unique_sheets = _unique_sheets_from_config_or_files(cfg)

    
        # --- SELECCIÓN DE CURSO (HOJA) ---
        options = ["Todas"] + unique_sheets
        current = st.session_state.get("global_sheet", "Todas")
        idx = options.index(current) if current in options else 0

        col_lbl, col_sel = st.sidebar.columns([1, 3], gap="small")
        with col_lbl:
            st.markdown("**Curso**")  # etiqueta a la izquierda (misma fila)
        with col_sel:
            choice = st.selectbox(
                "Curso",
                options,
                index=idx,
                key="global_sheet_select",
                label_visibility="collapsed",   # oculta el label del widget
            )

        st.session_state["global_sheet"] = choice
        # Tipo de mapa fijo (por defecto OpenStreetMap)
        base_map = "OpenStreetMap"


        

        # --- ERASMUS ---
        c1, c2, c3 = st.sidebar.columns([1.2, 1, 1], gap="small")

        with c1:
            st.markdown(
            """
            <div class="label-erasmus">Erasmus:</div>
            <style>
            .label-erasmus{
                height:40px;
                display:flex; align-items:center; justify-content:flex-start;
                font-weight:400 !important;
                font-size:18px;
                margin:0!important; padding:0!important;
                background:transparent!important; color:inherit;
                text-transform:none;
            }
            /* por si algún envoltorio aplica bold */
            .label-erasmus *{ font-weight:400 !important; }
            </style>
            """,
            unsafe_allow_html=True
        )

        with c2:
            if st.button("IN", use_container_width=True, key="btn_erasmus_in"):
                st.session_state.active_program_filter = "Erasmus IN"

        with c3:
            if st.button("OUT", use_container_width=True, key="btn_erasmus_out"):
                st.session_state.active_program_filter = "Erasmus OUT"



        # --- SICUE ---
        c4, c5, _ = st.sidebar.columns([1.2, 1, 1], gap="small")
        with c4:
            st.markdown(
                """
                <div class="label-erasmus">SICUE:</div>
                <style>
                .label-erasmus{
                    height:40px;
                    display:flex; align-items:center; justify-content:flex-start;
                    font-weight:400 !important;
                    font-size:16px;
                    margin:0!important; padding:0!important;
                    background:transparent!important; color:inherit;
                    text-transform:none;
                }
                /* por si algún envoltorio aplica bold */
                .label-erasmus *{ font-weight:400 !important; }
                </style>
                """,
                unsafe_allow_html=True
            )
        with c5:
            if st.button("OUT", use_container_width=True, key="btn_sicue_out"):
                st.session_state.active_program_filter = "SICUE OUT"
        

        fmap = {
            "ALL": "Todos",
            "ERASMUS_IN": "Erasmus IN",
            "ERASMUS_OUT": "Erasmus OUT",
            "SICUE_OUT": "SICUE OUT",
        }

        # Campo de texto (para búsqueda o filtro futuro)
        st.sidebar.text_input("Buscar o filtrar por palabra clave:")
        if st.sidebar.button("👤 Crear nuevo estudiante", use_container_width=True):
            st.session_state["view"] = "new_user"
            st.rerun()

        st.sidebar.markdown("---")

        # ==========================
        #  GESTIÓN DE RUTAS
        # ==========================
        if not st.session_state["show_routes"]:
            st.sidebar.button("🔁 Cambiar rutas", on_click=open_routes_editor)
        else:
            route_editor(st.session_state["config"])

        # Devuelve solo el nivel de zoom (ya no hace falta base_map dinámico)
        return base_map


