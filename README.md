# Movilidad ESII

> Herramienta de gestión y visualización de movilidad académica (Erasmus OUT/IN, SICUE)  
> para la Escuela Superior de Ingeniería Informática — Universidad de Castilla-La Mancha.

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit 1.47](https://img.shields.io/badge/Streamlit-1.47-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Flask 3.1](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Platform Windows](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white)](https://www.microsoft.com/windows)

Aplicación de escritorio Windows que expone una interfaz web local (Streamlit) respaldada por un microservicio REST (Flask). Toda la persistencia se realiza directamente sobre los ficheros Excel existentes de la institución, sin necesidad de base de datos adicional.

---

## Table of Contents

1. [Process Architecture](#1-process-architecture)
2. [Repository Structure](#2-repository-structure)
3. [Configuration](#3-configuration)
4. [Development Setup](#4-development-setup)
5. [Running the Application](#5-running-the-application)
6. [REST API Reference](#6-rest-api-reference)
7. [Security Model](#7-security-model)
8. [Build & Distribution](#8-build--distribution)

---

## 1. Process Architecture

`launcher_system.py` starts the orchestrator, which in turn spawns two independent subprocesses and supervises their lifecycle:

```text
launcher_system.py
 └── install_root/orchestrator/orchestrator.py
      ├── subprocess: streamlit run install_root/web_app/my_app.py  → http://127.0.0.1:<port_A>  (random free port)
      └── subprocess: python   install_root/api/api.py              → http://127.0.0.1:<port_B>  (random free port)
```

Both ports are allocated dynamically at startup via `pick_two_free_ports()` (OS-assigned, `socket.bind("127.0.0.1", 0)`), so they will differ between runs. The API port is passed to both subprocesses via the `API_PORT` environment variable.

The orchestrator runs a **WebSocket server on `ws://localhost:8765`**. The Streamlit app connects to it on load; when the browser tab is closed the WebSocket connection drops, the orchestrator kills both child processes and exits cleanly.

Both subprocesses read `config.json` at startup to resolve the absolute paths of the Excel data files.

---

## 2. Repository Structure

```text
TFG-MariaPicazoSanchez/
├── launcher_system.py           # Main entry point — starts the orchestrator (demo build)
├── launcher_system_sindata.py   # Production variant (no demo data)
├── config.json                  # Excel file paths per mobility programme
├── config.demo.json             # Example config pointing to data_demo/
├── installer.iss                # Inno Setup script (demo build)
├── installer_sindata.iss        # Inno Setup script (production build)
├── MovilidadESII.spec           # PyInstaller spec file
└── install_root/
    ├── orchestrator/
    │   └── orchestrator.py      # Process manager — spawns Flask + Streamlit, shuts both down when the browser tab closes (WebSocket signal)
    ├── api/
    │   └── api.py               # Flask microservice (see §6)
    ├── web_app/
    │   └── my_app.py            # Streamlit entry point — view routing
    ├── constants.py             # Global constants (programme names, Excel columns, …)
    ├── requirements.txt         # Pinned Python dependencies
    ├── domain/
    │   ├── models.py            # Dataclasses: Student, University, Mobility, …
    │   ├── map_filters.py       # Filter logic for the map view
    │   ├── stats_filters.py     # Filter logic for the statistics view
    │   ├── validators.py        # Form field validation
    │   └── es_cities.py         # Static catalogue of Spanish cities with coordinates
    ├── persistence/
    │   ├── data_access_mobility.py  # Excel → DataFrame readers (xlrd + openpyxl)
    │   ├── data_insert.py           # New row insertion into Excel
    │   ├── excel_update.py          # In-place row update (openpyxl)
    │   ├── materias_in_loader.py    # Erasmus IN subject-sheet loader
    │   └── sheets_helpers.py        # Sheet utilities: header detection, range helpers, …
    ├── export/
    │   ├── map_export.py        # Map PNG/SVG export
    │   └── stats_export.py      # Statistics export to .xlsx
    ├── ui/
    │   ├── map_view.py          # Interactive map view (Folium + streamlit-folium)
    │   ├── stats_view.py        # Statistics view (Altair / st.bar_chart)
    │   ├── sidebar.py           # Filter sidebar
    │   ├── popup_helpers.py     # Map popup HTML generation
    │   ├── popup_materias.py    # Erasmus IN subject-editing popup
    │   ├── popup_templates.py   # Jinja2 popup templates
    │   ├── search_helpers.py    # Sidebar autocomplete and search
    │   ├── stats_helpers.py     # Metric computation for the statistics view
    │   ├── stats_table.py       # Paginated results table
    │   ├── stats_details.py     # Per-row statistics detail panel
    │   ├── new_user_view.py     # New student registration form
    │   └── styles.py            # CSS injected into Streamlit
    ├── utils/
    │   ├── app_config.py        # config.json reader and validator
    │   ├── map_processing.py    # Internal geocoding and GeoJSON builder
    │   └── file_opener.py       # OS-level file opener
    ├── security/
    │   └── token_manager.py     # API token generation and persistence
    ├── static/
    │   └── materias_editor.js   # Subject-editor JS (served by Flask)
    └── data_demo/               # Sample data (bundled in the demo installer)
```

---

## 3. Configuration

`config.json` maps each mobility programme key to the absolute path of its Excel file. It is located either at the repository root (development) or at `%LOCALAPPDATA%\MovilidadESII\` (installed build).

```jsonc
{
  "SICUE OUT":   "<absolute path to SICUE outgoing .xlsx>",
  "Erasmus OUT": "<absolute path to Erasmus outgoing .xlsx>",
  "Erasmus IN":  "<absolute path to Erasmus incoming .xlsx>",
  "Materias IN": "<absolute path to Erasmus IN subjects .xlsx>"
}
```

Path resolution is handled by `utils/app_config.py`.

### Environment variables

| Variable | Default | Description |
|:---|:---|:---|
| `APP_CONFIG_PATH` | `config.json` | Override the config file location |
| `API_HOST` | `127.0.0.1` | Flask API bind address |
| `API_PORT` | *(dynamic)* | Flask API port — set automatically by the launcher; override only in manual dev mode |

---

## 4. Development Setup

**Prerequisites:** Python 3.12, pip.

```bash
git clone https://github.com/mariapicazo/TFG-MariaPicazoSanchez
cd TFG-MariaPicazoSanchez

python -m venv .venv
.venv\Scripts\activate

pip install -r install_root/requirements.txt
```

### Key dependencies

| Package | Version | Purpose |
|:---|:---|:---|
| `streamlit` | 1.47.1 | Web UI framework |
| `flask` | 3.1.2 | REST API server |
| `flask-cors` | 6.0.1 | Cross-origin support for embedded iframes |
| `websockets` | 16.0 | WebSocket server in the orchestrator (shutdown signal) |
| `psutil` | 7.2.2 | Process-tree kill in the orchestrator |
| `folium` | 0.20.0 | Interactive HTML map generation |
| `streamlit-folium` | 0.25.3 | Folium embed in Streamlit |
| `pandas` | 2.2.3 | In-memory DataFrame processing |
| `openpyxl` | 3.1.5 | `.xlsx` read/write |
| `xlrd` | 2.0.2 | Legacy `.xls` read |
| `altair` | 5.5.0 | Declarative chart generation |
| `babel` | 2.16.0 | Locale-aware country/city name formatting |

### Offline wheelhouse

```bash
py -3.12 -m pip download -r install_root/requirements.txt -d wheelhouse --only-binary=:all:
```

> The `wheelhouse/` directory is excluded from version control via `.gitignore` and can be deleted after generating the installer.

---

## 5. Running the Application

### Normal mode

```bash
py launcher_system.py
```

Starts the orchestrator, which in turn spawns Streamlit, Flask, and a WebSocket server for coordinated shutdown.

### Orchestrator only (development)

Run the orchestrator directly from `install_root/` without the launcher wrapper:

```bash
cd install_root
set APP_CONFIG_PATH=..\config.json
python orchestrator/orchestrator.py
```

Streamlit and Flask are started automatically. Close the browser tab to trigger a clean shutdown.

### Manual mode (individual processes)

Useful when debugging a single component in isolation:

```bash
# Terminal 1 — Flask API
cd install_root
set APP_CONFIG_PATH=..\config.json
python api/api.py
# → http://127.0.0.1:5000

# Terminal 2 — Streamlit UI
cd install_root
python -m streamlit run web_app/my_app.py
# → http://localhost:8501
```

> **Note:** In manual mode the WebSocket server is not running, so closing the browser tab will not shut down the processes. Stop them manually with `Ctrl+C`.

---

## 6. REST API Reference

**Base URL:** `http://127.0.0.1:<API_PORT>`

The port is allocated dynamically by the orchestrator. In manual dev mode it defaults to `5000` unless overridden by `API_PORT`.

Write endpoints require the `X-API-TOKEN` header (see [§7 Security Model](#7-security-model)). The token is also accepted as a `token` query parameter for form-based submissions.

### Endpoints

| Method | Path | Auth | Description |
|:---|:---|:---:|:---|
| `GET` | `/health` | — | Liveness check. Returns `{"ok": true}`. |
| `POST` | `/update_student` | ✔ | Updates a student record in the corresponding Excel file. |

### `POST /update_student`

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|:---|:---|:---:|:---|
| `programa` | string | ✔ | Programme key: `"Erasmus OUT"`, `"Erasmus IN"`, or `"SICUE OUT"` |
| `excel_path` | string | ✔ | Path to the Excel file (overridden by `config.json` value when present) |
| `row_index` | string | ✔ | DataFrame row index (0-based, as string) |
| `idx` | string | ✔ | Student index within the `estudiantes` cell |
| `estudiante` | string | ✔ | Student full name |
| `email` | string | | Student email |
| `ciudad` | string | | Destination city |
| `pais` | string | | Destination country |
| `old_email` | string | | Previous email (used to locate the row on update) |
| `old_nombre` | string | | Previous name |
| `materias_raw` | string | | JSON array of subjects: `[{"nombre":"…","cuat":"1","firmado":true}, …]` |

**Response:** `text/html` with an embedded `<script>` that calls `window.parent.postMessage` with the operation result.

**Error codes:**

| Status | Meaning |
|:---|:---|
| `401` | Missing or invalid `X-API-TOKEN` |
| `200` + `{"ok": false}` | Excel file locked, path not found, or invalid indices |

---

## 7. Security Model

All write operations are protected by a per-installation bearer token:

- `security/token_manager.py` generates a cryptographically random 64-character hex token on first run (`secrets.token_hex(32)`) and persists it to `security/.api_token`.
- On each startup `api.py` loads the token from that file and validates every protected request against the `X-API-TOKEN` header.
- `security/.api_token` is listed in `.gitignore` and is never committed to the repository.

---

## 8. Build & Distribution

Installers are produced by the **`Build EXE and Installers`** GitHub Actions workflow (`.github/workflows/`), triggered manually via `workflow_dispatch`. The workflow runs on `windows-latest` and produces two artifacts in `output/`.

### Pipeline overview

| Stage | Tool | Output |
|:---|:---|:---|
| Install dependencies | `pip install pyinstaller -r install_root/requirements.txt` | — |
| Build wheelhouse | `pip wheel -r install_root/requirements.txt -w install_root/wheelhouse` | `install_root/wheelhouse/` |
| Install Inno Setup | `choco install innosetup` | — |
| Build EXE — demo | `PyInstaller --onedir --noconsole … launcher_system.py` | `dist/MovilidadESII/` |
| Build installer — demo | `ISCC.exe installer.iss` | `output/MovilidadESII_Installer_ConData.exe` |
| Clean `dist/` + `build/` | `Remove-Item` | — |
| Build EXE — production | `PyInstaller --onedir --noconsole … launcher_system_sindata.py` | `dist/MovilidadESII/` |
| Build installer — production | `ISCC.exe installer_sindata.iss` | `output/MovilidadESII_Installer_SinData.exe` |
| Upload artifact — demo | `actions/upload-artifact@v4` | GitHub Actions artifact `installer-demo` |
| Upload artifact — production | `actions/upload-artifact@v4` | GitHub Actions artifact `installer-clean` |

### Triggering a build

Go to **Actions → Build EXE and Installers → Run workflow** in the GitHub UI. Once complete, two artifacts are available from the workflow run summary:

| Artifact | File | Description |
|:---|:---|:---|
| `installer-demo` | `MovilidadESII_Installer_ConData.exe` | Includes sample data for demonstration |
| `installer-clean` | `MovilidadESII_Installer_SinData.exe` | Production build — no data bundled |

### What the installer does

- Copies `dist/MovilidadESII/` to `%LOCALAPPDATA%\MovilidadESII\`.
- Creates a desktop shortcut and a Start Menu entry.
- Writes `config.json` to `%LOCALAPPDATA%\MovilidadESII\` with the correct data paths.
- Does not require Python to be installed on the target machine.
