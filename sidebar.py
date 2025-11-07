import streamlit as st
import json
import os

CONFIG_FILE = "config.json"



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
                st.sidebar.write(f"- {err}")
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
    """Panel para modificar rutas, con placeholders dinámicos desde config.json."""
    st.sidebar.subheader("📁 Modificar rutas de los archivos Excel")

    new_config = {
        "SICUE OUT": st.sidebar.text_input(
            "📘 SICUE OUT",
            value=config.get("SICUE OUT", ""),
            placeholder=get_placeholder(config, "SICUE OUT")
        ),
        "Erasmus IN": st.sidebar.text_input(
            "🌍 Erasmus IN",
            value=config.get("Erasmus IN", ""),
            placeholder=get_placeholder(config, "Erasmus IN")
        ),
        "Erasmus OUT": st.sidebar.text_input(
            "✈️ Erasmus OUT",
            value=config.get("Erasmus OUT", ""),
            placeholder=get_placeholder(config, "Erasmus OUT")
        ),
        "Materias IN": st.sidebar.text_input(
            "📑 Materias IN",
            value=config.get("Materias IN", ""),
            placeholder=get_placeholder(config, "Materias IN")
        ),
    }

    col1, col2 = st.sidebar.columns(2)
    if col1.button("💾", use_container_width=True):
        close_routes_editor(new_config)

    if col2.button("❌", use_container_width=True):
        st.sidebar.info("No se han guardado cambios.")
        st.session_state["show_routes"] = False
        st.rerun()



def sidebar_controls():
    """Crea la barra lateral con filtros y gestión de rutas."""
    # Tipo de mapa fijo (por defecto OpenStreetMap)
    base_map = "OpenStreetMap"


    # ==========================
    #  SECCIÓN DE FILTROS
    # ==========================
    st.sidebar.header("Filtros")

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

