# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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

[Unreleased]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/MariaPicazoSanchez/TFG-MariaPicazoSanchez/releases/tag/v1.0.0
