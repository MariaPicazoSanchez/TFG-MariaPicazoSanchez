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

def get_placeholder(config, key, default):
    """Devuelve un placeholder: usa la ruta guardada o un valor por defecto si está vacío."""
    ruta = config.get(key, "")
    return ruta if ruta else default


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

    if st.sidebar.button("💾 Guardar rutas"):
        close_routes_editor(new_config)

    if st.sidebar.button("❌"):
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
    st.sidebar.markdown("ERASMUS:")
    # Botones de filtro (sin funcionalidad por ahora)
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.button("IN", key="btn_erasmus_in", use_container_width=True)
    with col2:
        st.button("OUT", key="btn_erasmus_out", use_container_width=True)

    # --- SICUE ---
    st.sidebar.markdown("SICUE:")
    col3, _ = st.sidebar.columns(2)
    with col3:
        st.button("OUT", key="btn_sicue_out", use_container_width=True)


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

