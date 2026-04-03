# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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

[Unreleased]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/releases/tag/v1.0.0
