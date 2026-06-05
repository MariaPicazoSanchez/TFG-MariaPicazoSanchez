# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.5] - 2026-06-05

### Fixed
- **Erasmus IN table bounds are now detected from the real subject columns** instead of scanning the whole worksheet row. This avoids stopping too early or too late when there are side tables or sparse cells around the main catalogue and student rows.
- **Statistics view now resolves the city column more robustly** when several similarly named columns exist. It picks the candidate with the most real values, so auxiliary columns no longer win over the main data column.

### Removed
- **Erasmus IN no longer auto-seeds cross-course subject suggestions** into the catalog with `matriculados=0` and `cupo=0`. The catalog insertion now stays limited to the subjects coming from the current student payload.

## [1.2.4] - 2026-06-03

### Fixed
- **MSIX desktop shortcut showed a blank (white-page) icon** while the Start-menu tile rendered correctly. `ensure_msix_desktop_shortcut` copied the `.ico` under `%LOCALAPPDATA%` and wrote that same path into the shortcut's `IconLocation`. Inside an MSIX package, writes to `%LOCALAPPDATA%` are redirected to the package container (`…\Packages\<PFN>\LocalCache\Local`), but the path string the process sees is the un-redirected one — and the redirection is not even uniform (the API token lands on the un-redirected path while the launcher's data goes to the container). Explorer runs outside the package, can't follow the redirection, finds no file and paints a blank icon. The icon is now persisted to the real container path (verified, with a direct-copy fallback) and that path — which is also stable across Store updates — is what gets written to the `.lnk`. The regeneration marker was bumped `_v2` → `_v3` so existing installs with the broken shortcut fix themselves on next launch.

## [1.2.3] - 2026-06-03

### Added
- **User guide** (`docs/guia_usuario.html`): a full step-by-step manual with screenshots (`docs/figs/guia/`) covering installation (from the Microsoft Store and from the GitHub release `.exe`), data-source configuration, the map and its filters, the statistics view and exports, and the new-student forms for Erasmus OUT/IN and SICUE OUT. Linked from the landing page (`docs/index.html`).
- **Community-health files**: `SECURITY.md`, expanded `CONTRIBUTING.md`, and GitHub issue templates (`bug_report.md`, `feature_request.md`).

### Changed
- **Full MSIX icon asset set** generated from `MovilidadESII.ico` in `build-msix.yml`: `Square44x44Logo` now ships `scale-100/125/150/200/400`, `targetsize-16/24/32/48/256` and the matching `targetsize-*_altform-unplated` variants (plus `Square150x150Logo` and `StoreLogo` scale variants), so the small application icon renders consistently on the taskbar and app list. Assets are produced with `System.Drawing.Bitmap(ico)` rather than `Icon.ToBitmap()`, which fails to decode the PNG-compressed 256×256 frame.
- `README.md`, `docs/index.html` and `docs/styles.css` refreshed for the user guide and the new release.

### Fixed
- **Inno Setup installer showed a hard-coded "version 1.0"** in the wizard title and in "Add or remove programs". `AppVer` in `installer.iss` / `installer_sindata.iss` is now guarded with `#ifndef` and overridable via `ISCC /DAppVer=…`; the `build-installers.yml` workflow passes the actual release version (the tag with the leading `v` stripped), so the installer reflects the real version.

## [1.2.2] - 2026-05-14

### Added
- New universities are automatically appended to the `Coordenadas` sheet with auto-geocoded coords (Nominatim) tagged with the suffix ` (auto)` so the coordinator can review and adjust them.
- SICUE OUT (no separate `Coordenadas` sheet): the `Coordenadas` column in the course sheet is now filled by looking up an existing row with the same university; if none, by geocoding and tagging the value with ` (auto)`. On edit, the value is only refreshed when the destination changes.
- Manual "Recargar" button next to the page title (round-icon → text-on-hover, theme-adaptive) that triggers a full cache clear and reload.

### Changed
- Per-program / per-mtime cache keys for loaders: editing one Excel no longer invalidates the in-memory dataframes of the other two programs.
- Erasmus IN: when inserting an alumno, only the materias table is extended; side tables (catalog, info) are shrunk to their real last data row to repair previously over-extended ranges.

### Fixed
- Coordinates are no longer written into the alumno row's `Coordenadas` / `Latitud` / `Longitud` columns for any program (Erasmus OUT/IN/SICUE OUT). The source of truth is the `Coordenadas` sheet (Erasmus) / cross-row lookup (SICUE).
- The "Tipo de alumno" selector now keeps the user's current selection while editing and after saving.

### Removed
- Auto-refresh polling that reloaded the app every ~10s when an Excel changed on disk. Use the new "Recargar" button instead.

## [1.2.1] - 2026-05-13

### Fixed
- Erasmus IN: new student was inserted at a random row and broke the table formatting of the side catalogue and the following alumni.
- New student form: the "Tipo de alumno" selector reverted to Erasmus OUT after saving, and then could not be changed.

### Tooling
- `.vscode/settings.json`: interpreter pointing to `.venv` and `install_root` added to `python.analysis.extraPaths` so Pylance resolves internal imports and venv dependencies.

## [1.2.0] - 2026-04-30

### Added
- **User-configurable X-button behaviour**: new "Ajustes" popover at the bottom-right of the sidebar exposes a "Mantener en segundo plano al pulsar X" checkbox (checked by default). When unchecked, clicking the window's X closes the application completely instead of minimising to the system tray. The choice persists via a new `close_to_tray` key in `config.json`; the launcher re-reads it on every close so the change takes effect without restarting the app.
- `_render_settings_popover` + `_on_close_to_tray_change` helpers in `ui/sidebar.py`. The settings entry uses `st.popover` (native to Streamlit ≥1.32) with the Material Symbol `:material/settings:` icon, so it no longer relies on the gear emoji (which renders inconsistently across operating systems) and does not require manual `st.rerun()` calls — the popover manages its own open/close state and the checkbox change is persisted via an `on_change` callback. Rendered in every view (map, stats, new student).
- Fallback in-memory PIL placeholder image for the system-tray icon so the X handler never falls through to a real close just because the `.ico` cannot be loaded.

### Changed
- **Multi-path icon discovery**: both the system-tray initialisation (`launcher_system.py`) and the MSIX desktop-shortcut helper (`desktop_shortcut.py`) now look for `MovilidadESII.ico` in `Path(sys.executable).parent`, `Path(sys.executable).parent / "_internal"`, and `sys._MEIPASS` — covering both the Inno install layout (icon next to the EXE) and the MSIX/PyInstaller 6.x layout (icon under `_internal/`).
- **Persistent icon for the MSIX shortcut**: `ensure_msix_desktop_shortcut` now copies the resolved `.ico` to `marker_dir` (LocalAppData) and sets `IconLocation` to that stable path. Previously, IconLocation pointed inside the MSIX install folder, which changes on every Store update (`WindowsApps\…\version_hash`), invalidating the icon. The marker version was bumped from `_v1` to `_v2` so existing installs with a broken shortcut regenerate it on next launch.
- README  2 (Repository Structure) rewritten to match the actual tree: `config.json` moved from the repo root to `install_root/`; `desktop_shortcut.py`, `MovilidadESII.spec`, `CHANGELOG.md` listed at the root; missing files in `persistence/`, `export/`, `ui/`, `utils/`, `static/` and the icon/PNG assets in `install_root/` added with descriptions.
- README  3 (Configuration): development path of `config.json` corrected to `install_root/config.json`; `APP_CONFIG_PATH` override mentioned.
- README  7 (REST API Reference): added `GET /saved_flag` (last-save timestamp polling) and `POST /update_plan_coord` (study-plan write into the `Coordenadas` sheet) with their full field tables and error codes.
- `docs/index.html` install section: the two `.exe` download buttons now resolve dynamically to the latest release's assets via `https://api.github.com/repos/.../releases/latest` (matched by the `data-asset-pattern` attribute). On API failure, the static `releases/latest` URL acts as a fallback so the buttons keep working.

### Fixed
- **MSIX X-button silently closed the application** instead of minimising to tray. The handler in `launcher_system.py` was opening the icon at `Path(sys.executable).parent / "MovilidadESII.ico"`, but PyInstaller 6.x onedir places datafiles under `_internal/`. The resulting `FileNotFoundError` made `_on_closing` return `None`, which pywebview interprets as "do not cancel the close." Now the icon is searched in multiple locations and a placeholder is used as last resort, so the X always minimises to tray when configured to do so. Inno builds were unaffected because the installer copies the `.ico` next to the executable explicitly.
- **MSIX desktop shortcut showed the explorer.exe (folder) icon** instead of the application icon. Same root cause: the launcher passed `None` to `ensure_msix_desktop_shortcut`, no `IconLocation` was set on the `.lnk`, and Windows fell back to the `explorer.exe` icon. Fixed by the multi-path search and persistent-copy logic above.
- `docs/index.html` install buttons no longer link to the non-existent `docs/downloads/` folder (which would 404 on GitHub Pages).

### Removed
- **Erasmus OUT: `ToR` and `Acta de equivalencias` columns** dropped from the read/write pipeline and from the structure documentation. The institution does not use either field, so keeping them in the schema only added clutter to the popup, the new-student form and the destination Excel files.
  - Read path: `tor`/`acta` removed from `COLUMN_ALIASES` (`constants.py`), `FIELD_ALIASES` and `SPEC_COLS["Erasmus OUT"]` (`domain/models.py`), the `_excel_cells.py` alias dictionary, the `loaders/erasmus_out.py` `_pick`/`mapping` block, and the `student_cols` projection in `ui/map_view.py`.
  - Write path: `ToR` / `ActaEquivalencias` removed from the new-sheet row builder and from the existing-sheet `Erasmus OUT` branch in `persistence/_insert_row_builders.py`; also from the form-data extraction tuple in `persistence/data_insert.py`.
  - UI: `nu_tor` / `nu_acta` text inputs and their file pickers removed from `ui/new_user/_form_out.py`; the corresponding session-state keys removed from `ui/new_user/view.py::_clear_form()`. Popup view + edit fields cleaned in `ui/popup_templates.py` (the `tor_val`/`acta_val` keys, the `_view_link` rows for ToR/Acta, the `acta_field` HTML block, the `tor_field` `build_link_file_field` call, and the field assembly lists for both Erasmus OUT and the fallback case).
  - Documentation: `docs/excel_structure.html` now shows the Erasmus-OUT sheet with 11 columns instead of 12 (header `<th>`s, header row, both example rows, and the `colspan` for the "más filas" footer all updated). The note "LA / ToR" is now just "LA".
  - Existing Excel files with these columns still in place are not modified — the loader simply ignores them and the writer skips them, so legacy data is preserved without manual cleanup.
- `psutil==7.2.2` from `install_root/requirements.txt`. The package was unused: `shutdown_processes` in `launcher_system.py` uses Windows' native `taskkill /F /T` to terminate process trees. The corresponding row was also removed from the dependency table in README  4.

## [1.1.2] - 2026-04-25

### Added
- **Erasmus IN cross-course catalogue**: each academic-year sheet now aggregates the subjects seen in the other years' catalogues (with `matriculados=0`, `cupo=0`) so the editor's subject suggestions cover the full historical inventory regardless of which year the student is being enrolled in. Subjects already present in the current sheet are not duplicated.
- **Per-subject `Cupo` input** in the *New student → Erasmus IN* form. The default is the catalogue value when the subject already exists; otherwise 0. The new value flows through the payload and updates the row in the catalogue (both for new subjects and for existing ones the user re-priced).
- **Automatic creation of an academic-year sheet** when a student is added for a year that does not yet exist in the workbook. The most recent year is cloned as a template: header rows, banding, fills, font styles and `openpyxl.Table` objects (renamed to remain unique in the workbook) are preserved so the new sheet keeps the visual identity of the previous year.
- **MSIX close-to-tray**: when the application is installed from the Microsoft Store, closing the window minimises to the system tray (Teams/Claude-style) instead of exiting; the launcher keeps running so notifications and the local API stay alive.
- **MSIX desktop shortcut**: on first launch from a Microsoft Store install, a `.lnk` is generated on the user's Desktop pointing at `shell:AppsFolder\<PFN>!MovilidadESII`. A marker file under `%APPDATA%` prevents recreation if the user later removes the icon. Inert on Inno installs (Inno already creates its own shortcut) and on non-Windows platforms.
- **Plan de estudios (study plan) for Erasmus OUT**: dedicated button in the popup and a new visualisation that surfaces the destination's study plan when available.
- **Sidebar collapse/expand toggle button** with persisted state.
- New `persistence/_erasmus_in_catalog.py` module gathering catalogue helpers (`find_catalog_in_ws`, `append_to_catalog`, `clone_sheet_as_new_course`, `insert_materias_rows`, `gather_other_course_subjects`, `extend_tables_ref_to_row`, `pick_template_sheet`).
- `desktop_shortcut.py` at repo root with the MSIX-only `ensure_msix_desktop_shortcut(marker_dir, icon_path)` helper that detects the package context via `kernel32.GetCurrentPackageFamilyName` before doing anything.

### Changed
- **PyInstaller bundling for system-tray support**: `MovilidadESII.spec` now collects `pystray` and `PIL` submodules and data files dynamically (`collect_submodules` / `collect_data_files`) instead of relying on a hard-coded `pystray._win32` hidden import, and the application icon (`MovilidadESII.ico`) is shipped alongside the executable so MSIX builds (which, unlike Inno, don't copy it) can paint the tray icon.
- **MSIX GitHub Actions workflow** (`.github/workflows/build-msix.yml`) now invokes PyInstaller via the `MovilidadESII.spec` file, so the bundling rules above apply consistently to the Store package.
- **Per-entry `matriculados` and `cupo` in `append_to_catalog`**: the function now respects the value passed in each entry instead of always writing the global default, which is what makes the form's `Cupo` input visible in the saved sheet and what lets the actual enrolment count (`Counter` over the student's subjects) reach the catalogue.
- **Style copying on insert is column-scoped**: both `insert_materias_rows` and `append_to_catalog` now copy cell styles only across their own table's columns, so writing the catalogue no longer clobbers the materias table (and vice-versa) when the two tables share rows on the same sheet.
- Erasmus OUT popup updated with the study-plan section and refreshed `popup_styles.css`.
- Statistics helpers reworked alongside the SVG exploration changes.
- Documentation (`README.md`, `docs/index.html`) refreshed for the new release.

### Fixed
- **Inserted student rows rendered with the header's dark-blue / bold style** after a sheet was cloned for a new academic year. Two compounding bugs:
  1. `append_to_catalog` was using `header_row` as the style template when the catalogue was empty after cloning (so freshly inserted rows inherited the header style).
  2. Both insert helpers iterated `range(1, max_column + 1)`, so writing one table overwrote the styles of the neighbouring table on the same row.
  Fixed by falling back to `header_row + 1` (whose style is preserved by `_clear_rows_preserve_style`) and restricting the column range to each table's own columns.
- **`ws.tables.items()` returning `(name, ref_str)` instead of `(name, Table)`** in openpyxl 3.x silently broke the table-copy step in `clone_sheet_as_new_course` (`deepcopy` of a string, `new_tbl.name = ...` raised `AttributeError`, exception was swallowed). Now uses `ws.tables.values()` so the cloned sheet keeps a proper `TableStyleMedium2` with banding.
- **Matriculados always written as 0** for new student subjects in the catalogue. Now uses a `Counter` over the student's subjects so the catalogue row reads `1` for a single enrolment, `n` for `n`.
- **Search by the selected academic year** returned no rows in some configurations.
- Statistics view crash / off-by-one when exploring SVG-rendered charts.

---

## [1.1.1] - 2026-04-17

### Added
- **Microsoft Store distribution channel**: dedicated `build-msix.yml` GitHub Actions workflow that builds the MSIX package directly from the PyInstaller tree with `makeappx` and `signtool`, independent of the Inno Setup `.exe` pipeline.
- Store tile assets (`Square44x44Logo.png`, `Square150x150Logo.png`, `Square310x310Logo.png`, `StoreLogo.png`) in `install_root/assets_png/`.
- New `_restrict_to_main_table` helper in `erasmus_in.py` that detects separators (`Unnamed:`, `Contador…`) to bound the main students table when the Excel sheet contains several tables side-by-side.

### Changed
- **Application accepted in Microsoft Partner Center and published in the Microsoft Store.** Users installing from the Store receive a package signed by Microsoft with no SmartScreen warnings.
- Launcher detects MSIX execution context and skips the dependency check (`import streamlit`) that would otherwise exceed the certifier's startup time limit.
- `token_manager.py` adapted to the MSIX sandbox so the API token can be written/read when running as an installed Store app.
- README and Pages site (`docs/index.html`, `docs/privacy.html`, `docs/styles.css`) updated with Store distribution info.
- Erasmus IN country alias order: `Origen` is now preferred over `País` so the main table's country column wins when both exist.

### Fixed
- **Erasmus IN students mixed across universities** when the source Excel contained several tables in the same sheet (e.g. a main "subjects × student" table plus an auxiliary per-student summary). Columns from the auxiliary table (`nombre`, `Coordenadas`, `País`, `Ciudad`, `LA`) were misaligned with the main rows and placed students in wrong locations; column detection is now restricted to the main table.
- Bug in `_make_records_fn` (`erasmus_in.py`): inconsistent use of a loop-local variable as dictionary key caused student records spread across multiple rows (one per subject) not to be merged, leading to data being mixed between students.
- Ghost `cols.ciudad` detection when `_pick` fell back to `contains` matching and mistook the country column (`Origen`) for `Ciudad Origen`.
- Erasmus IN / OUT map filters now handle rows without a signed Learning Agreement correctly.
- Search field is cleared properly when switching views.
- Sidebar hide/show button state fixed.

## [1.1.0] - 2026-04-04

### Added
- Unit test suite (128 tests, 0.52 s) covering converters, validators and map processing utilities.
- `tests/` directory with `conftest.py`, `test_converters.py`, `test_validators.py` and `test_map_processing.py`.
- **Tests** GitHub Actions workflow (`.github/workflows/tests.yml`) — runs automatically on every push and pull request to `main`.
- `requirements-dev.txt` — development dependencies (app requirements + pytest) for local test runs.
- `pytest.ini` — pytest configuration; `testpaths = tests` so `pytest -v` works from the repo root.
- Search by `responsable del programa` in Erasmus OUT filter.
- Reload button in the UI header to manually invalidate cache.
- Per-student loading indicator while the map is rendering.

### Changed
- **Refactored `new_user_view.py`** (1 046 lines) into a package: `ui/new_user/view.py` + `_form_in.py` + `_form_out.py` + `_form_sicue.py` + `_helpers.py`.
- **Refactored `stats_view.py`** into `ui/stats_view.py` + `ui/stats_helpers.py` + `ui/stats_table.py` + `ui/stats_details.py`.
- **Refactored `data_insert.py`** (702 lines) into `persistence/data_insert.py` + `_insert_row_builders.py` + `_insert_helpers.py` + `_excel_cells.py` + `_excel_tables.py`.
- **Refactored `validators.py`** (646 lines) into `validators.py` + `_converters.py` + `_validator_rules.py`.
- **Refactored `sidebar.py`** (677 lines) into `sidebar.py` + `_sidebar_config.py`.
- **Refactored `data_access_mobility.py`** into `persistence/loaders/` package (`all_dataframes.py`, `erasmus_in.py`, `erasmus_out.py`, `sicue_out.py`, `_common.py`).
- Moved all inline CSS from Python files to `ui/styles.py` / `static/` for separation of concerns.
- Map popup logic extracted to `ui/popup_templates.py` with dedicated template functions per programme.
- Selective `st.cache_data` invalidation on student save — only `_list_sheets_in_file` and `build_export_xlsx` are cleared instead of the full cache.
- Auto-refresh fragment interval raised from 3 s to 10 s; API health-check TTL raised from 30 s to 120 s.
- Cuatrimestre now read and displayed correctly for Erasmus IN students.

### Performance
- Replaced all `iterrows()` loops in hot rendering paths with vectorised pandas operations (`to_dict("records")`, boolean masks, `groupby` + `merge`): `group_rows_by_location`, map render loop, `_restore_location_info`, `_build_responsable_from_students`, `get_university_responsable_map`, `filter_students_with_coords`.
- `_build_responsable_from_students` now uses vectorised column operations instead of per-row string access.
- Deduplicated asignaturas-catalog loading — single implementation in `new_user/_helpers.py`; `popup_templates.py` delegates to it.

### Removed
- Dead code: `get_alumnos_in` (`materias_in_loader.py`), `export_materias_in_excel` (`data_insert.py`), `add_points_to_map` (`map_view.py`).
- `from __future__ import annotations` removed from 31 files (redundant on Python 3.10+).

### Fixed
- Cache key for asignaturas catalog unified to `_asignaturas_catalog_{path}_{sheet}_{data_version}` in both `popup_templates.py` and `new_user/_helpers.py`, preventing stale subject lists after saving a student.
- Map filter state no longer triggers a spurious extra reload when changing the academic year.

## [1.0.0] - 2026-03-08

### Added
- Full Streamlit + Flask dual-process architecture for mobility data management.
- Interactive map view with Folium/Leaflet, filterable by year, program, and country.
- Statistics view with Altair charts and exportable Excel reports.
- REST API (`api.py`) protected by per-installation bearer token.
- `materias_editor.js` in-browser editor for subject mappings.
- Automated GitHub Actions CI/CD workflow producing signed Inno Setup installers.
- Demo installer (`MovilidadESII_Installer_ConData.exe`) with sample ERASMUS/SICUE data.
- Production installer (`MovilidadESII_Installer_SinData.exe`) without bundled data.
- Embedded Python 3.12 runtime bundled in installer for zero-dependency deployment.
- SHA256 checksums published alongside each GitHub Release.

[Unreleased]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.2.5...HEAD
[1.2.5]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.2.4...v1.2.5
[1.2.4]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.2.3...v1.2.4
[1.2.3]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.1.2...v1.2.0
[1.1.2]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/releases/tag/v1.0.0
