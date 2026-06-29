"""
Tests para utils/app_config.py

Funciones testeables (sin Streamlit real):
  - _get_cfg_path        — devuelve ruta del config
  - _read_cfg            — lee el JSON de config
  - save_course          — escribe en config.json
  - get_config_mtimes    — devuelve tuple de mtimes
  - get_available_program_types — filtra programas configurados

Las funciones que acceden a st.session_state (init_session_defaults,
get_active_programs, get_query_param) son omitidas aquí porque dependen
del estado de Streamlit que no es verificable con mocks simples.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

from utils.app_config import (
    _get_cfg_path,
    _read_cfg,
    save_course,
    get_config_mtimes,
    get_available_program_types,
    AVAILABLE_PROGRAMS,
)


# ─────────────────────────────────────────────────────────────────────────────
# _get_cfg_path
# ─────────────────────────────────────────────────────────────────────────────

class TestGetCfgPath:
    def test_usa_variable_entorno_si_existe(self, tmp_path, monkeypatch):
        expected = str(tmp_path / "mi_config.json")
        monkeypatch.setenv("APP_CONFIG_PATH", expected)
        result = _get_cfg_path()
        assert result == expected

    def test_sin_variable_devuelve_ruta_relativa(self, monkeypatch):
        monkeypatch.delenv("APP_CONFIG_PATH", raising=False)
        result = _get_cfg_path()
        assert result.endswith("config.json")

    def test_resultado_es_string(self, monkeypatch):
        monkeypatch.delenv("APP_CONFIG_PATH", raising=False)
        result = _get_cfg_path()
        assert isinstance(result, str)


# ─────────────────────────────────────────────────────────────────────────────
# _read_cfg
# ─────────────────────────────────────────────────────────────────────────────

class TestReadCfg:
    def test_devuelve_dict_con_json_valido(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text('{"curso": "2024/2025"}', encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_file))
        result = _read_cfg()
        assert result == {"curso": "2024/2025"}

    def test_devuelve_dict_vacio_si_no_existe(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APP_CONFIG_PATH", str(tmp_path / "noexiste.json"))
        result = _read_cfg()
        assert result == {}

    def test_devuelve_dict_vacio_si_json_invalido(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "bad.json"
        cfg_file.write_text("no es json", encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_file))
        result = _read_cfg()
        assert result == {}

    def test_devuelve_dict(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text('{}', encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_file))
        result = _read_cfg()
        assert isinstance(result, dict)


# ─────────────────────────────────────────────────────────────────────────────
# save_course
# ─────────────────────────────────────────────────────────────────────────────

class TestSaveCourse:
    def test_guarda_curso_en_json(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text('{}', encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_file))
        save_course("2024/2025")
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["curso"] == "2024/2025"

    def test_preserva_claves_existentes(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text('{"otraclave": "valor"}', encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_file))
        save_course("2023/2024")
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["otraclave"] == "valor"
        assert data["curso"] == "2023/2024"

    def test_sobreescribe_curso_anterior(self, tmp_path, monkeypatch):
        cfg_file = tmp_path / "config.json"
        cfg_file.write_text('{"curso": "2022/2023"}', encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG_PATH", str(cfg_file))
        save_course("2024/2025")
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        assert data["curso"] == "2024/2025"

    def test_no_lanza_si_ruta_invalida(self, monkeypatch):
        monkeypatch.setenv("APP_CONFIG_PATH", "/ruta/que/no/existe/config.json")
        # No debe lanzar excepción, solo imprime error
        save_course("2024/2025")


# ─────────────────────────────────────────────────────────────────────────────
# get_config_mtimes
# ─────────────────────────────────────────────────────────────────────────────

class TestGetConfigMtimes:
    def test_devuelve_tupla(self):
        cfg = {}
        result = get_config_mtimes(cfg)
        assert isinstance(result, tuple)

    def test_longitud_igual_a_available_programs(self):
        cfg = {}
        result = get_config_mtimes(cfg)
        assert len(result) == len(AVAILABLE_PROGRAMS)

    def test_none_para_rutas_inexistentes(self):
        cfg = {p: "/ruta/inexistente.xlsx" for p in AVAILABLE_PROGRAMS}
        result = get_config_mtimes(cfg)
        assert all(v is None for v in result)

    def test_mtime_para_fichero_existente(self, tmp_path):
        xlsx = tmp_path / "test.xlsx"
        xlsx.write_bytes(b"fake")
        cfg = {AVAILABLE_PROGRAMS[0]: str(xlsx)}
        result = get_config_mtimes(cfg)
        # El primero debe tener un mtime (float), el resto None
        assert result[0] is not None
        assert isinstance(result[0], float)

    def test_cfg_vacio_devuelve_nones(self):
        result = get_config_mtimes({})
        assert result == tuple([None] * len(AVAILABLE_PROGRAMS))


# ─────────────────────────────────────────────────────────────────────────────
# get_available_program_types
# ─────────────────────────────────────────────────────────────────────────────

class TestGetAvailableProgramTypes:
    def test_sin_config_devuelve_lista_vacia(self):
        result = get_available_program_types({})
        assert result == []

    def test_con_ruta_inexistente_excluye(self):
        cfg = {AVAILABLE_PROGRAMS[0]: "/no/existe.xlsx"}
        result = get_available_program_types(cfg)
        assert AVAILABLE_PROGRAMS[0] not in result

    def test_con_fichero_real_incluye(self, tmp_path):
        xlsx = tmp_path / "datos.xlsx"
        xlsx.write_bytes(b"fake")
        cfg = {AVAILABLE_PROGRAMS[0]: str(xlsx)}
        result = get_available_program_types(cfg)
        assert AVAILABLE_PROGRAMS[0] in result

    def test_multiples_programas(self, tmp_path):
        f1 = tmp_path / "a.xlsx"
        f2 = tmp_path / "b.xlsx"
        f1.write_bytes(b"x")
        f2.write_bytes(b"y")
        cfg = {
            AVAILABLE_PROGRAMS[0]: str(f1),
            AVAILABLE_PROGRAMS[1]: str(f2),
            AVAILABLE_PROGRAMS[2]: "/no/existe.xlsx",
        }
        result = get_available_program_types(cfg)
        assert AVAILABLE_PROGRAMS[0] in result
        assert AVAILABLE_PROGRAMS[1] in result
        assert AVAILABLE_PROGRAMS[2] not in result

    def test_devuelve_lista(self):
        result = get_available_program_types({})
        assert isinstance(result, list)
