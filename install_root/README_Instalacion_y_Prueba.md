# MovilidadUCLM — Guía de instalación, uso y logs (Windows)

## 1) Qué es esto
Aplicación de visualización y gestión de movilidad académica:
- Interfaz principal: **Streamlit**
- Microservicio: **Flask**
- Incluye **Excels demo** con datos inventados (carpeta `data_demo`).

---

## 2) Instalación
1. Ejecuta el instalador: **MovilidadUCLM_Installer.exe**
2. (Opcional) Marca **Crear icono en el escritorio**.
3. Finaliza la instalación.

> El instalador puede instalar **Python 3.12** automáticamente si no existe en el sistema.

---

## 3) Abrir la aplicación
- Doble clic en el icono **MovilidadUCLM** (Escritorio o Menú Inicio).
- Se abrirá automáticamente en el navegador predeterminado.

**Primera ejecución:** puede tardar más (creación de entorno virtual + dependencias).  
**Siguientes ejecuciones:** arranque más rápido.

---

## 4) Datos de prueba (demo)
En el directorio de instalación encontrarás:
- `data_demo/` (Excels demo)

La configuración de rutas se guarda de forma local en el perfil del usuario (para no escribir en “Archivos de programa”):
- `config.json` se crea automáticamente la primera vez.

---

## 5) Dónde están los logs (IMPORTANTE)
Por permisos de Windows, los logs NO se guardan en “Archivos de programa”.
Se guardan en tu perfil de usuario:

- `%LOCALAPPDATA%\MovilidadUCLM\logs`

Cómo abrirlos:
1. Pulsa **Win + R**
2. Pega:
# MovilidadUCLM — Guía de instalación, uso y logs (Windows)

## 1) Qué es esto
Aplicación de visualización y gestión de movilidad académica:
- Interfaz principal: **Streamlit**
- Microservicio: **Flask**
- Incluye **Excels demo** con datos inventados (carpeta `data_demo`).

---

## 2) Instalación
1. Ejecuta el instalador: **MovilidadUCLM_Installer.exe**
2. (Opcional) Marca **Crear icono en el escritorio**.
3. Finaliza la instalación.

> El instalador puede instalar **Python 3.12** automáticamente si no existe en el sistema.

---

## 3) Abrir la aplicación
- Doble clic en el icono **MovilidadUCLM** (Escritorio o Menú Inicio).
- Se abrirá automáticamente en el navegador predeterminado.

**Primera ejecución:** puede tardar más (creación de entorno virtual + dependencias).  
**Siguientes ejecuciones:** arranque más rápido.

---

## 4) Datos de prueba (demo)
En el directorio de instalación encontrarás:
- `data_demo/` (Excels demo)

La configuración de rutas se guarda de forma local en el perfil del usuario (para no escribir en “Archivos de programa”):
- `config.json` se crea automáticamente la primera vez.

---

## 5) Dónde están los logs (IMPORTANTE)
Por permisos de Windows, los logs NO se guardan en “Archivos de programa”.
Se guardan en tu perfil de usuario:

- `%LOCALAPPDATA%\MovilidadUCLM\logs`

Cómo abrirlos:
1. Pulsa **Win + R**.
2. Pega: `%LOCALAPPDATA%\MovilidadUCLM\logs`.
3. Enter.

Archivos:
- `launcher.log` → arranque general
- `pip.log` → instalación de dependencias
- `api.log` → microservicio Flask
- `app.log` → Streamlit

---

## 6) Cerrar la aplicación
- Cierra la pestaña del navegador.
- Los procesos (Streamlit y API) se cierran automáticamente tras unos segundos sin actividad.

---

## 7) Desinstalar
Tienes dos opciones:

### Opción A (recomendada)
- **Inicio → Configuración → Aplicaciones → Aplicaciones instaladas**
- Busca **MovilidadUCLM**
- Pulsa **Desinstalar**

### Opción B
- Panel de control → Programas → Desinstalar un programa
- Busca **MovilidadUCLM** y desinstala.

> Nota: al desinstalar, puede quedar la carpeta de datos local (logs/config/venv) en:
> `%LOCALAPPDATA%\MovilidadUCLM`
> Si quieres borrarlo todo manualmente, elimina esa carpeta.

---

## 8) Problemas frecuentes
### No se abre nada al hacer doble clic
- Revisa: `%LOCALAPPDATA%\MovilidadUCLM\logs\launcher.log`

### Error instalando dependencias
- Revisa: `%LOCALAPPDATA%\MovilidadUCLM\logs\pip.log`

### La API no arranca
- Revisa: `%LOCALAPPDATA%\MovilidadUCLM\logs\api.log`

### Streamlit no arranca / pantalla en blanco
- Revisa: `%LOCALAPPDATA%\MovilidadUCLM\logs\app.log`

---

## 9) Prueba rápida sugerida (checklist)
1. Abrir la app.
2. Cargar dataset demo.
3. Ver mapa con puntos.
4. Buscar por universidad/ciudad/estudiante.
5. Abrir ficha de estudiante.
6. Editar estudiante y guardar.
7. Verificar que se refleja el cambio.

---

## 10) Cuestionario de calidad (SUS)
- Cuestionario SUS - Calidad y Facilidad de Uso: [Rellenar formulario](https://forms.office.com/pages/responsepage.aspx?id=5rosxPRhjEmRB2qM9fAeVkFEkc6xy2RJrixnB5tt4NBUNzMzRUM1QlpXOUtDRTUzSVZUWUpVRlZLRS4u&route=shorturl)

