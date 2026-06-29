"""
Tests para api/api.py

Cubre: /health, /saved_flag, require_token (401/200), parse_materias_raw
"""
import sys
import os
import pytest

# Asegurar que install_root/api y install_root están en el path
_tests_dir = os.path.dirname(__file__)
_install_root = os.path.abspath(os.path.join(_tests_dir, "..", "install_root"))
_api_dir = os.path.join(_install_root, "api")
for _p in (_install_root, _api_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Mockear security.get_api_token antes de importar api.py
from unittest.mock import patch, MagicMock

_FAKE_TOKEN = "test-token-abc123"


@pytest.fixture(scope="module")
def client():
    with patch("security.get_api_token", return_value=_FAKE_TOKEN):
        import api as api_module
        api_module.API_TOKEN = _FAKE_TOKEN
        api_module.app.config["TESTING"] = True
        with api_module.app.test_client() as c:
            yield c, api_module


# ─────────────────────────────────────────────────────────────────────────────
# /health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_ok(self, client):
        c, _ = client
        r = c.get("/health")
        assert r.status_code == 200
        assert r.get_json()["ok"] is True


# ─────────────────────────────────────────────────────────────────────────────
# /saved_flag
# ─────────────────────────────────────────────────────────────────────────────

class TestSavedFlag:
    def test_saved_flag_devuelve_ts(self, client):
        c, _ = client
        r = c.get("/saved_flag")
        assert r.status_code == 200
        data = r.get_json()
        assert "ts" in data
        assert isinstance(data["ts"], float)


# ─────────────────────────────────────────────────────────────────────────────
# require_token — decorator de autenticación
# ─────────────────────────────────────────────────────────────────────────────

class TestRequireToken:
    def test_sin_token_devuelve_401(self, client):
        c, _ = client
        r = c.post("/update_student")
        assert r.status_code == 401

    def test_token_incorrecto_devuelve_401(self, client):
        c, _ = client
        r = c.post("/update_student", headers={"X-API-TOKEN": "token-incorrecto"})
        assert r.status_code == 401

    def test_token_correcto_no_devuelve_401(self, client):
        c, _ = client
        # Con token correcto el endpoint puede fallar por datos faltantes,
        # pero NO por autenticación (no debe devolver 401)
        r = c.post("/update_student", headers={"X-API-TOKEN": _FAKE_TOKEN})
        assert r.status_code != 401

    def test_token_en_query_param(self, client):
        c, _ = client
        r = c.post(f"/update_student?token={_FAKE_TOKEN}")
        assert r.status_code != 401


# ─────────────────────────────────────────────────────────────────────────────
# parse_materias_raw — lógica de parseo de materias
# ─────────────────────────────────────────────────────────────────────────────

class TestParseMaterias:
    @pytest.fixture(autouse=True)
    def _get_fn(self, client):
        _, api_module = client
        self.parse = api_module.parse_materias_raw

    def test_vacio_devuelve_lista_vacia(self):
        assert self.parse("") == []
        assert self.parse(None) == []

    def test_formato_json(self):
        raw = '[{"nombre": "Cálculo", "cuat": "1", "firmado": true}]'
        result = self.parse(raw)
        assert len(result) == 1
        assert result[0]["asignatura"] == "Cálculo"
        assert result[0]["cuat"] == "1"
        assert result[0]["firmado"] == "x"

    def test_formato_json_firmado_false(self):
        raw = '[{"nombre": "Álgebra", "cuat": "2", "firmado": false}]'
        result = self.parse(raw)
        assert result[0]["firmado"] == ""

    def test_formato_json_varios(self):
        raw = '[{"nombre": "A", "cuat": "1"}, {"nombre": "B", "cuat": "2"}]'
        result = self.parse(raw)
        assert len(result) == 2
        assert result[0]["asignatura"] == "A"
        assert result[1]["asignatura"] == "B"

    def test_formato_legacy_pipe(self):
        raw = "Cálculo | 1 | x\nÁlgebra | 2 |"
        result = self.parse(raw)
        assert len(result) == 2
        assert result[0]["asignatura"] == "Cálculo"
        assert result[0]["firmado"] == "x"
        assert result[1]["firmado"] == ""

    def test_formato_legacy_sin_firmado(self):
        raw = "Física | 1"
        result = self.parse(raw)
        assert result[0]["asignatura"] == "Física"
        assert result[0]["cuat"] == "1"
        assert result[0]["firmado"] == ""

    def test_json_item_sin_nombre_se_ignora(self):
        raw = '[{"asignatura": "", "cuat": "1"}]'
        result = self.parse(raw)
        assert result == []

    def test_json_con_campo_asignatura(self):
        raw = '[{"asignatura": "Redes", "cuat": "1", "firmado": "x"}]'
        result = self.parse(raw)
        assert result[0]["asignatura"] == "Redes"
        assert result[0]["firmado"] == "x"

    def test_json_unico_dict(self):
        raw = '{"nombre": "Sistemas", "cuat": "2"}'
        result = self.parse(raw)
        assert len(result) == 1
        assert result[0]["asignatura"] == "Sistemas"
